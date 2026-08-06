# Architecture

How the pieces fit together, and what happens on a single request.

---

## System overview

```mermaid
flowchart TB
    subgraph dev["Development / Offline"]
        csv[("data/online_retail_cleaned.csv<br/>1,062,989 raw rows")]
        train["scripts/train.py<br/>training pipeline"]
        mlflow["MLflow<br/>params · metrics · artifacts"]
        artifacts[("models/<br/>churn · segment · recommender<br/>+ metadata.json")]

        csv --> train
        train --> mlflow
        train --> artifacts
    end

    subgraph cicd["CI/CD"]
        gh["GitHub<br/>main branch"]
        actions["GitHub Actions<br/>test → build → deploy"]
        ecr["Amazon ECR<br/>customer-intelligence-api"]

        gh --> actions
        actions --> ecr
    end

    subgraph aws["AWS Runtime — ap-south-1"]
        s3[("Amazon S3<br/>customer-intelligence-models-harsh1314h")]
        alb["Application Load Balancer<br/>managed by ECS Express"]
        ecs["ECS Express Mode<br/>Fargate task · 256 CPU / 512 MB"]

        alb --> ecs
    end

    subgraph container["Inside the container"]
        uvicorn["Uvicorn ASGI server :8080"]
        fastapi["FastAPI app"]
        pydantic["Pydantic schemas<br/>validate · reject 422"]
        registry["ModelRegistry<br/>models held in memory"]
        churn["ChurnEnsemble<br/>XGBoost 0.65 + MLP 0.35"]
        segment["CustomerSegmenter<br/>StandardScaler → K-Means k=4"]
        recommend["CollaborativeRecommender<br/>TruncatedSVD 50 factors"]

        uvicorn --> fastapi
        fastapi --> pydantic
        pydantic --> registry
        registry --> churn
        registry --> segment
        registry --> recommend
    end

    client["Client<br/>frontend · CRM · curl · Swagger UI"]
    client -->|HTTPS JSON| alb
    ecs --> uvicorn
    ecr -.->|image pull| ecs
    s3 -.->|artifact download<br/>at startup| ecs
    artifacts -->|aws s3 sync| s3

    classDef store fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef model fill:#e6f4ea,stroke:#34a853,color:#111
    class csv,artifacts,s3 store
    class churn,segment,recommend model
```

---

## Request path — a single `POST /predict/churn`

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant U as Uvicorn
    participant F as FastAPI route
    participant P as Pydantic ChurnRequest
    participant R as ModelRegistry
    participant M as ChurnEnsemble

    C->>U: POST /predict/churn {customer: {...}}
    U->>F: ASGI scope + body
    F->>P: parse & validate body
    alt invalid (e.g. recency_days = -5)
        P-->>C: 422 with the offending field name
    else valid
        P->>F: CustomerFeatures
        F->>F: customer_to_frame() → 1-row DataFrame
        F->>R: Depends(get_registry)
        R->>M: predict_proba(frame)
        M->>M: 0.65 × XGBoost + 0.35 × MLP
        M-->>F: 0.1117
        F->>F: band: ≥0.65 high · ≥0.35 medium · else low
        F-->>C: 200 {churn_probability: 0.1117, risk_band: "low", model_version: ...}
    end
```

Two things worth noting:

- **Models are loaded once**, in the FastAPI `lifespan` startup hook, not per request.
  `ModelRegistry` holds them in memory for the process's lifetime, so a prediction is
  pure CPU with no disk or network I/O.
- **Validation happens before any model code runs.** A malformed request never reaches
  scikit-learn.

---

## Startup path — where models come from

```mermaid
flowchart TD
    start["Container starts<br/>uvicorn app.main:app"] --> lifespan["FastAPI lifespan hook"]
    lifespan --> reg["ModelRegistry(settings).load()"]
    reg --> sync{"CI_MODEL_ARTIFACT_URI set?"}

    sync -->|"s3://…"| s3dl["boto3: download all keys<br/>under the prefix"]
    sync -->|"gs://…"| gcsdl["google-cloud-storage: download blobs"]
    sync -->|"local path"| localcp["copy files from directory"]
    sync -->|"not set"| skip["use CI_MODEL_DIR as-is"]

    check{"all 3 .joblib<br/>artifacts present?"}
    s3dl --> check
    gcsdl --> check
    localcp --> check
    skip --> check

    check -->|yes| load["joblib.load × 3<br/>+ read metadata.json"]
    check -->|"no, and<br/>CI_ALLOW_DEMO_MODELS=true"| demo["generate tiny demo artifacts<br/>demo_mode: true"]
    check -->|"no, and<br/>CI_ALLOW_DEMO_MODELS=false"| fail["RuntimeError<br/>startup aborts, container exits"]

    demo --> load
    load --> ready["/health → 200<br/>models_loaded: all true"]

    classDef bad fill:#fce8e6,stroke:#d93025,color:#111
    classDef good fill:#e6f4ea,stroke:#34a853,color:#111
    class fail bad
    class ready good
```

**Why the failure branch matters.** In production, `CI_ALLOW_DEMO_MODELS=false` means a
missing artifact **crashes the container at startup** rather than silently serving toy
predictions. Failing loudly at deploy time is much better than a healthy-looking service
returning meaningless numbers. That branch is covered by
`tests/test_registry.py::test_registry_errors_when_artifacts_missing_and_demo_disabled`.

---

## Training pipeline

```mermaid
flowchart LR
    raw[("raw CSV<br/>1,062,989 rows")] --> norm["normalize_transactions()<br/>column aliases, drop cancellations,<br/>drop non-positive qty/price"]
    norm --> clean[("805,549 clean rows")]

    clean --> feat["build_customer_features()"]
    feat --> cust[("5,878 customers<br/>7 features each")]

    clean --> snap["build_time_based_churn_dataset()<br/>8 cutoffs · 90-day lookahead"]
    snap --> churnds[("30,823 rows<br/>5,281 customers")]

    churnds --> tc["train churn ensemble"]
    cust --> ts["train K-Means k=4"]
    clean --> tr["fit TruncatedSVD recommender"]

    tc --> out[("models/*.joblib<br/>+ metadata.json")]
    ts --> out
    tr --> out

    tc -.-> ml["MLflow run"]
    ts -.-> ml
    tr -.-> ml
```

The churn branch is the one that matters — see
[interview-notes.md](interview-notes.md#why-time-based-churn-labels-the-most-important-ml-decision-here)
for why features and labels are drawn from disjoint time windows.

---

## AWS resources

Region `ap-south-1`, account `188947281989`.

| Resource | Name | State | Cost when idle |
| --- | --- | --- | ---: |
| ECR repository | `customer-intelligence-api` | kept | ~\$0 (a few GB storage) |
| S3 bucket | `customer-intelligence-models-harsh1314h` | kept | ~\$0 (7.5 MB) |
| IAM role | `CustomerIntelligenceECSTaskExecutionRole` | kept | free |
| IAM role | `CustomerIntelligenceECSInfrastructureRole` | kept | free |
| IAM role | `GitHubActionsCustomerIntelligenceDeployRole` | kept | free |
| IAM OIDC provider | `token.actions.githubusercontent.com` | kept | free |
| ECS cluster | `default` (empty) | kept | free |
| **ECS Express service** | `customer-intelligence-api` | **torn down** | ~\$9/mo if running |
| **Application Load Balancer** | ECS-managed | **torn down** | ~\$17/mo if running |

The two billable resources are deliberately **not** left running. The service was
deployed, verified end-to-end, and removed — see
[`verification-report.md`](verification-report.md) and the "AWS Deployment History"
section of `context.md`.

### IAM trust relationships

```mermaid
flowchart LR
    ghrepo["GitHub repo<br/>Harsh1314h/customer-intelligence-api"] -->|OIDC token| oidc["IAM OIDC provider<br/>token.actions.githubusercontent.com"]
    oidc -->|sts:AssumeRoleWithWebIdentity| deployrole["GitHubActionsCustomerIntelligenceDeployRole<br/>ecr:push · ecs:*ExpressGatewayService · iam:PassRole"]
    deployrole -->|iam:PassRole| execrole
    deployrole -->|iam:PassRole| infrarole

    ecssvc["ecs-tasks.amazonaws.com"] --> execrole["CustomerIntelligenceECSTaskExecutionRole<br/>pull image · read S3 models · write logs"]
    ecsctl["ecs.amazonaws.com"] --> infrarole["CustomerIntelligenceECSInfrastructureRole<br/>manage ALB · SG · autoscaling"]
```

No long-lived AWS access keys exist in GitHub. CI authenticates with a short-lived OIDC
token exchanged for temporary credentials.

---

## Redeploying (for a live demo)

Full commands and the teardown step are in the "AWS Deployment History" section of
`context.md`. The short version:

```powershell
$env:Path += ";$env:LOCALAPPDATA\Programs\Amazon\AWSCLIV2"
$registry = "188947281989.dkr.ecr.ap-south-1.amazonaws.com"
$pw = aws ecr get-login-password --region ap-south-1
docker login --username AWS --password $pw $registry
docker build -t "$registry/customer-intelligence-api:latest" .
docker push "$registry/customer-intelligence-api:latest"
aws ecs create-express-gateway-service --service-name customer-intelligence-api --cluster default ...
```

Expect roughly **6 minutes** before traffic is served — the canary step holds at 0 running
tasks first. **Tear it down afterwards:**

```powershell
aws ecs delete-express-gateway-service `
  --service-arn "arn:aws:ecs:ap-south-1:188947281989:service/default/customer-intelligence-api" `
  --region ap-south-1
```

Deletion is asynchronous; the ALB takes 9–13 minutes to disappear. Confirm with
`aws elbv2 describe-load-balancers --region ap-south-1` returning an empty list before
considering teardown complete.

> **Note on Windows PowerShell:** `aws ecr get-login-password | docker login --password-stdin`
> fails with a `400 Bad Request` because the pipe mangles the token's encoding for native
> binaries. Pass the password as an argument instead, as shown above.
