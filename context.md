# Customer Intelligence API - Project Context

This file is a handoff note for continuing the project later. It records what has been built so far, what commands were used, what each major piece does, and what remains.

## Current Project Status

The project is a local, Dockerized FastAPI machine learning API for e-commerce customer intelligence.

Current status:

- Local FastAPI API is working.
- Swagger UI works locally.
- Real ML models have been trained from `data/online_retail_cleaned.csv`.
- MLflow experiment tracking works locally.
- Tests pass.
- Docker build and Docker run work locally.
- GitHub repository is connected.
- AWS deployment files have been pivoted from App Runner to ECS Express Mode because App Runner is no longer accepting new customers after April 30, 2026.
- S3 model artifact upload is complete:
  - `s3://customer-intelligence-models-harsh1314h/customer-intelligence/models/`
- Phase 1 cleanup work has been started and mostly implemented:
  - training progress logs added
  - example request/response files added
  - stronger tests added
  - README updated with training output and examples
- Phase 2 GitHub finalization is complete:
  - `.gitignore` correctly ignores local-heavy folders
  - Git works when bypassing the broken global config with `GIT_CONFIG_GLOBAL=NUL`
  - Python 3.11 tests were repaired in the user terminal and passed with `12 passed`
  - Docker was repaired and reported working in the user terminal
  - source/docs/tests/examples were committed in `5c22730`
  - `main` was pushed to `https://github.com/Harsh1314h/customer-intelligence-api.git`
- Portfolio documentation polish has been started:
  - README rewritten with architecture, tech stack, endpoints, setup, ML metrics, Docker, tests, and AWS status
  - `docs/model-card.md` added
- GitHub Actions test import failure was fixed:
  - added `pytest.ini` with `pythonpath = .`
  - ignored local AWS policy JSON helper files in `.gitignore`
- AWS CLI is configured locally as `arn:aws:iam::188947281989:user/customer-intelligence-admin`, so deployment can continue from local PowerShell instead of CloudShell.
- Phase 7 (AWS deployment prep) is complete: ECR repo, GitHub OIDC provider/deploy role, and both ECS roles (task execution + infrastructure) exist with correct permissions.
- Phase 8 (AWS deployment) is complete: the API was deployed live to ECS Express Mode on 2026-08-07, verified working end-to-end (`/health`, `/docs`, `/predict/churn` all returned real model output), then torn down to stop billing. See "AWS Deployment History" section below for full detail and re-deploy steps.
- Phase 9 (resume/portfolio polish) is complete as of 2026-08-07. All 9 phases are now done. See "Phase 9 Completion" section below.

## Project Status: COMPLETE

All 9 phases are finished. The project was fully re-verified end-to-end on 2026-08-07 —
12/12 checks passed, recorded verbatim in `docs/verification-report.md`.

Working copy note: this work was done in `C:\customer-intelligence-api-main\customer-intelligence-api-main`
(an extracted copy of the repo). The actual git repository with `.git`, `.venv`, `data/`,
`models/`, and `mlruns/` lives at `C:\Users\azadh\OneDrive\Documents\ecommerceAPI`.
Changes were synced from the working copy into the git repo and pushed from there.

GitHub remote:

```text
https://github.com/Harsh1314h/customer-intelligence-api.git
```

Project root:

```text
C:\Users\azadh\OneDrive\Documents\ecommerceAPI
```

## Project Structure

Important files and folders:

```text
app/
  main.py                 FastAPI app and API endpoints
  schemas.py              Pydantic request/response schemas
  config.py               App settings from environment variables
  ml/
    artifacts.py          Loads model artifacts from local path, S3, or GCS
    churn.py              Churn ensemble model wrapper
    demo.py               Demo model generator for local smoke tests
    features.py           Data cleaning and feature engineering
    recommender.py        Collaborative filtering recommender
    registry.py           Loads trained model files for API serving
    segmentation.py       K-Means segment prediction wrapper

scripts/
  train.py                Main training pipeline
  create_demo_artifacts.py Creates tiny demo model artifacts

tests/
  test_api.py             API contract tests
  test_features.py        Time-based churn feature test
  test_registry.py        Model registry tests
  test_recommender.py     Recommender fallback tests

examples/
  churn_request.json      Sample churn request
  segment_request.json    Sample segmentation request
  recommend_request.json  Sample recommendation request
  health_response.json    Sample health response

docs/
  aws-deployment.md       AWS deployment guide
  model-card.md           ML model summary, metrics, limitations, and intended use

models/
  churn_model.joblib      Trained churn model
  segment_model.joblib    Trained segmentation model
  recommender.joblib      Trained recommendation model
  metadata.json           Model version, metrics, training info

data/
  online_retail_cleaned.csv Main dataset used for training

.github/workflows/
  deploy.yml              GitHub Actions AWS CI/CD workflow

Dockerfile                Container packaging
README.md                 Main project instructions
requirements.txt          Runtime dependencies
requirements-dev.txt      Test/development dependencies
.gitignore                Files/folders Git should not track
.dockerignore             Files/folders Docker should not copy
```

## What Was Built

### 1. FastAPI Backend

Main file:

```text
app/main.py
```

Endpoints:

```text
GET  /health
POST /predict/churn
POST /segment/customer
POST /recommend
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Purpose:

- `/health` checks service and model loading status.
- `/predict/churn` returns churn probability and risk band.
- `/segment/customer` returns customer segment from K-Means.
- `/recommend` returns top product recommendations.

### 2. Pydantic Schemas

Main file:

```text
app/schemas.py
```

Purpose:

- Defines request JSON format.
- Defines response JSON format.
- Validates inputs before ML model code runs.
- Powers Swagger UI documentation automatically.

Important schemas:

- `CustomerFeatures`
- `ChurnRequest`
- `ChurnResponse`
- `SegmentRequest`
- `SegmentResponse`
- `RecommendationRequest`
- `RecommendationResponse`
- `HealthResponse`

### 3. Feature Engineering

Main file:

```text
app/ml/features.py
```

Purpose:

- Normalizes dataset column names.
- Cleans raw transaction data.
- Builds customer-level ML features.
- Builds time-based churn training examples.

Customer features:

```text
recency_days
frequency
monetary
tenure_days
avg_order_value
total_items
unique_products
```

Important functions:

- `normalize_transactions()`
- `build_customer_features()`
- `build_time_based_churn_dataset()`
- `customer_to_frame()`

### 4. Model Training

Main file:

```text
scripts/train.py
```

Training command used:

```powershell
python -m scripts.train --transactions data\online_retail_cleaned.csv --output-dir models
```

This command:

1. Loads the CSV dataset.
2. Cleans transactions.
3. Creates customer features.
4. Creates time-based churn labels.
5. Trains churn model.
6. Trains K-Means segmentation model.
7. Trains collaborative filtering recommender.
8. Logs metrics to MLflow.
9. Saves model artifacts to `models/`.

Training now prints visible progress:

```text
[1/8] Loading transactions...
[2/8] Cleaning transactions...
[3/8] Building latest customer features...
[4/8] Building time-based churn training snapshots...
[5/8] Starting MLflow experiment...
[6/8] Training churn ensemble...
[7/8] Training K-Means customer segmentation...
[8/8] Training collaborative filtering recommender and saving artifacts...
```

### 5. Trained Models

Model files:

```text
models/churn_model.joblib
models/segment_model.joblib
models/recommender.joblib
models/metadata.json
```

The models were trained from:

```text
data/online_retail_cleaned.csv
```

Current metadata:

```text
model_version: 20260613-194657
demo_mode: false
churn strategy: time_based_snapshots
prediction_window_days: 90
min_history_days: 90
snapshots: 8
churn training rows: 30823
churn training customers: 5281
```

Current metrics:

```text
churn_roc_auc: 0.7916483366437135
churn_average_precision: 0.8232340833069525
churn_accuracy: 0.7372108178559792
segment_silhouette: 0.40614202923091813
recommender_items: 4631
recommender_users: 5878
```

### 6. Model Registry

Main file:

```text
app/ml/registry.py
```

Purpose:

- Loads saved `.joblib` model files when the API starts.
- Keeps models ready in memory.
- Provides loaded models to FastAPI endpoints.

ModelRegistry does not train models. It only loads already-trained models.

Flow:

```text
API starts
  -> ModelRegistry loads models from models/
  -> endpoints reuse loaded models for predictions
```

### 7. MLflow

MLflow tracks training experiments.

Command used:

```powershell
python -m mlflow ui --backend-store-uri mlruns --port 5000
```

MLflow UI:

```text
http://127.0.0.1:5000
```

Logged information:

- training parameters
- churn metrics
- segmentation metrics
- recommender stats
- model artifacts

### 8. Tests

Tests:

```text
tests/test_api.py
tests/test_features.py
```

Command:

```powershell
python -m pytest
```

Last known result:

```text
5 passed
```

Tests verify:

- `/health`
- `/predict/churn`
- `/segment/customer`
- `/recommend`
- time-based churn dataset logic
- invalid API input validation
- data cleaning aliases
- missing required transaction columns
- registry metadata loading
- registry missing artifact failure
- recommender popular-item fallback

### 9. Docker

Files:

```text
Dockerfile
.dockerignore
```

Build command:

```powershell
docker build -t customer-intelligence-api:local .
```

Run command:

```powershell
docker run --rm -p 8080:8080 -e CI_MODEL_DIR=/app/models -e CI_ALLOW_DEMO_MODELS=false -v "C:\Users\azadh\OneDrive\Documents\ecommerceAPI\models:/app/models:ro" customer-intelligence-api:local
```

Docker Swagger URL:

```text
http://127.0.0.1:8080/docs
```

Docker local test was reported working.

### 10. AWS Deployment Preparation

Files:

```text
docs/aws-deployment.md
.github/workflows/deploy.yml
```

AWS deployment target:

- Amazon ECR for Docker image.
- Amazon S3 for model artifacts.
- Amazon ECS Express Mode for hosted API.
- GitHub Actions for CI/CD.

AWS deployment is not completed yet. App Runner was blocked for new customers, so deployment has pivoted to ECS Express Mode.

Completed AWS preparation:

- S3 bucket created.
- Model artifacts uploaded to:

```text
s3://customer-intelligence-models-harsh1314h/customer-intelligence/models/
```

## AWS Deployment History (Phases 7-8, completed 2026-08-07)

This section records exactly what was created in AWS account `188947281989` (region `ap-south-1`) and how to redeploy.

### AWS resources created

Persistent (kept, near-zero cost):

```text
ECR repository:            customer-intelligence-api
S3 model artifacts:        s3://customer-intelligence-models-harsh1314h/customer-intelligence/models/
IAM: CustomerIntelligenceECSTaskExecutionRole   (pulls image, reads S3 models, writes logs)
IAM: CustomerIntelligenceECSInfrastructureRole  (manages ALB/SG/autoscaling for ECS Express)
IAM: GitHubActionsCustomerIntelligenceDeployRole (GitHub OIDC deploy role)
IAM OIDC provider: token.actions.githubusercontent.com
Service-linked roles: AWSServiceRoleForECS, AWSServiceRoleForElasticLoadBalancing
ECS cluster: default (empty cluster, no charge)
ECR image tags pushed: manual-20260807, latest
```

Torn down after verification (these are the billable pieces):

```text
ECS Express service: customer-intelligence-api (deleted)
Application Load Balancer: ecs-express-gateway-alb-* (deleted)
Target groups, ECS-managed security groups (deleted automatically with the service)
```

### What actually happened

1. AWS CLI v2 and GitHub CLI were installed locally (via winget) and authenticated (`customer-intelligence-admin` IAM user for AWS; device-code browser login for GitHub as `Harsh1314h`).
2. Found the GitHub Actions deploy role's inline policy (`CustomerIntelligenceDeployPolicy`) was stale from an earlier App Runner attempt — replaced it with ECS/Express-Gateway-scoped permissions (`ecr:*` push actions, `ecs:CreateExpressGatewayService`/`UpdateExpressGatewayService`/etc., `iam:PassRole` scoped to the two ECS roles).
3. Created `CustomerIntelligenceECSTaskExecutionRole` (trusts `ecs-tasks.amazonaws.com`, has `AmazonECSTaskExecutionRolePolicy` + an inline S3 read policy scoped to the models bucket/prefix) and `CustomerIntelligenceECSInfrastructureRole` (trusts `ecs.amazonaws.com`, has managed policy `AmazonECSInfrastructureRoleforExpressGatewayServices` — this is the real current AWS managed-policy name for ECS Express Mode; the name `AmazonECSInfrastructureRolePolicyForManagedInstances` referenced earlier in this doc's step-by-step guide is a *different*, unrelated policy for a different ECS launch mode and should not be used for Express services).
4. Confirmed all 4 GitHub secrets (`AWS_ROLE_TO_ASSUME`, `ECS_TASK_EXECUTION_ROLE_ARN`, `ECS_INFRASTRUCTURE_ROLE_ARN`, `CI_MODEL_ARTIFACT_URI`) were set on the repo via `gh secret set`.
5. Re-ran the existing GitHub Actions workflow run to pick up the new secrets, but **GitHub Actions was in a platform-wide outage starting 2026-08-06** ("Incident with Actions" on githubstatus.com — hosted runners delayed/stuck queued). The workflow run stayed queued indefinitely.
6. To avoid an open-ended wait on GitHub's outage, deployed manually from the local machine instead of via CI:
   - `docker build` the image from the repo's `Dockerfile`.
   - `docker login`/`push` to ECR — note: on Windows PowerShell, `aws ecr get-login-password | docker login --password-stdin` **fails with a 400 Bad Request** because PowerShell's pipe mangles the token's encoding for native binaries. Workaround used: `docker login --username AWS --password $pw $registry` (password as an argument; a minor local-only exposure, acceptable for a one-off manual deploy, not for anything checked in).
   - `aws ecs create-express-gateway-service` directly (the AWS CLI has native `create-express-gateway-service` / `update-` / `describe-` / `delete-` / `monitor-express-gateway-service` subcommands — no need for the `aws-actions/amazon-ecs-deploy-express-service` GitHub Action).
7. First `create-express-gateway-service` call failed with `Unable to assume the service linked role` — the `AWSServiceRoleForElasticLoadBalancing` service-linked role didn't exist yet in this account. Fixed with `aws iam create-service-linked-role --aws-service-name elasticloadbalancing.amazonaws.com`, then the create call succeeded.
8. Deployment used a **canary strategy by default** (5% canary, 3-minute bake time). With `desiredCount=1`, 5% of 1 rounds down to 0, so the service showed 0 running tasks for the first several minutes before the canary step auto-promoted to 100%. This is expected behavior for Express services with very low task counts, not a failure — just be patient (took about 6 minutes total from `create` to a running task) rather than assuming it's stuck.
9. Verified live and working:
   - `GET /health` → `200`, `demo_mode: false`, all 3 models loaded from S3.
   - `GET /docs` → `200`, Swagger UI served.
   - `POST /predict/churn` with `examples/churn_request.json` → `200`, real prediction (`churn_probability: 0.1117`, `risk_band: low`).
   - Full evidence saved locally at `aws-tmp/deployment-evidence.txt` (not committed to git — local only).
10. Torn down with `aws ecs delete-express-gateway-service`. Deletion is asynchronous: the service went `DRAINING` immediately but the ALB/target groups/security groups took roughly 9-13 minutes to actually disappear. Confirmed fully gone via `aws elbv2 describe-load-balancers` (empty) and `aws ec2 describe-security-groups --filters Name=tag:AmazonECSManaged,Values=true` (empty) before considering teardown complete.

### Redeploying later (e.g. for a live recruiter demo)

Once GitHub Actions recovers from its outage, pushing to `main` (or re-running the workflow) should work end-to-end on its own, since secrets and IAM roles are already in place.

To redeploy manually instead (same steps used above):

```powershell
$env:Path += ";$env:LOCALAPPDATA\Programs\Amazon\AWSCLIV2"
$registry = "188947281989.dkr.ecr.ap-south-1.amazonaws.com"
$repo = "customer-intelligence-api"
$pw = aws ecr get-login-password --region ap-south-1
docker login --username AWS --password $pw $registry   # use --password, not stdin, on Windows PowerShell
docker build -t "$registry/${repo}:latest" .
docker push "$registry/${repo}:latest"

aws ecs create-express-gateway-service `
  --service-name customer-intelligence-api `
  --cluster default `
  --execution-role-arn "arn:aws:iam::188947281989:role/CustomerIntelligenceECSTaskExecutionRole" `
  --infrastructure-role-arn "arn:aws:iam::188947281989:role/CustomerIntelligenceECSInfrastructureRole" `
  --task-role-arn "arn:aws:iam::188947281989:role/CustomerIntelligenceECSTaskExecutionRole" `
  --health-check-path "/health" `
  --cpu "256" --memory "512" `
  --primary-container '{"image":"'$registry'/'$repo':latest","containerPort":8080,"environment":[{"name":"CI_MODEL_ARTIFACT_URI","value":"s3://customer-intelligence-models-harsh1314h/customer-intelligence/models/"},{"name":"CI_ALLOW_DEMO_MODELS","value":"false"}]}' `
  --region ap-south-1
```

**Remember to tear it down again after demoing** to avoid ongoing ALB/Fargate charges:

```powershell
aws ecs delete-express-gateway-service --service-arn "arn:aws:ecs:ap-south-1:188947281989:service/default/customer-intelligence-api" --region ap-south-1
```

Then wait ~10-15 minutes and confirm with `aws elbv2 describe-load-balancers --region ap-south-1` that the load balancer is gone before considering it done.

## Common Commands Used

### Activate Virtual Environment

```powershell
cd "C:\Users\azadh\OneDrive\Documents\ecommerceAPI"
.\.venv\Scripts\Activate.ps1
```

### Install Dependencies

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
```

### Train Models

```powershell
python -m scripts.train --transactions data\online_retail_cleaned.csv --output-dir models
```

### Run API Locally

```powershell
$env:CI_MODEL_DIR="models"
$env:CI_ALLOW_DEMO_MODELS="false"
python -m uvicorn app.main:app --reload
```

### Run Tests

```powershell
python -m pytest
```

### Run MLflow UI

```powershell
python -m mlflow ui --backend-store-uri mlruns --port 5000
```

### Build Docker Image

```powershell
docker build -t customer-intelligence-api:local .
```

### Run Docker Container

```powershell
docker run --rm -p 8080:8080 -e CI_MODEL_DIR=/app/models -e CI_ALLOW_DEMO_MODELS=false -v "C:\Users\azadh\OneDrive\Documents\ecommerceAPI\models:/app/models:ro" customer-intelligence-api:local
```

## Current Local Workflow

Training workflow:

```text
data/online_retail_cleaned.csv
  -> normalize_transactions()
  -> build_customer_features()
  -> build_time_based_churn_dataset()
  -> train churn + segmentation + recommender
  -> save models/
  -> log MLflow run
```

Serving workflow:

```text
Start Uvicorn
  -> FastAPI starts
  -> ModelRegistry loads models
  -> external client calls endpoint
  -> Pydantic validates request
  -> endpoint uses loaded model
  -> API returns JSON response
```

## What Remains To Be Done

## Remaining Work By Phase

### Phase 1 - Learning And Code Walkthrough

Goal:

Understand the project deeply before adding more production features.

Tasks:

- Explain every command used so far:
  - virtual environment commands
  - dependency installation commands
  - training command
  - API run command
  - MLflow command
  - Docker build/run commands
  - Git commands
- Explain every major file:
  - `app/main.py`
  - `app/schemas.py`
  - `app/ml/features.py`
  - `app/ml/registry.py`
  - `scripts/train.py`
  - `Dockerfile`
  - `requirements.txt`
- Explain the full request flow:
  - external client
  - Uvicorn
  - FastAPI endpoint
  - Pydantic validation
  - ModelRegistry
  - ML model prediction
  - JSON response
- Explain the full training flow:
  - raw CSV
  - cleaning
  - feature engineering
  - churn labels
  - model training
  - MLflow logging
  - joblib artifacts

Completion criteria:

- You can explain what happens when `python -m scripts.train ...` runs.
- You can explain what happens when `/predict/churn` is called.
- You can explain why `models/`, `data/`, `.venv/`, and `mlruns/` are ignored by Git.

### Phase 2 - Improve Training Observability

Goal:

Make training visible and easier to understand while it runs.

Tasks:

- Add progress logs to `scripts/train.py`, for example:

```text
[1/8] Loading transactions...
[2/8] Cleaning transactions...
[3/8] Building customer features...
[4/8] Building time-based churn dataset...
[5/8] Training churn ensemble...
[6/8] Training K-Means segmentation...
[7/8] Training recommender...
[8/8] Saving artifacts...
```

- Print dataset counts:
  - raw transaction rows
  - cleaned transaction rows
  - customer count
  - churn training rows
  - product count
- Print final metrics after training.
- Re-run training and confirm logs are clear.
- Update `README.md` with the clearer training output expectation.

Completion criteria:

- Training no longer feels silent.
- You can watch each stage complete in the terminal.

### Phase 3 - Add Example Requests And Demo Evidence

Goal:

Make the project easier to demo to recruiters/interviewers.

Tasks:

- Create an `examples/` folder.
- Add:

```text
examples/churn_request.json
examples/segment_request.json
examples/recommend_request.json
examples/health_response.json
```

- Add README examples showing:
  - Swagger UI usage
  - curl usage
  - expected responses
- Capture screenshots:
  - Swagger UI
  - `/health` showing `demo_mode: false`
  - MLflow run page
  - Docker API running

Completion criteria:

- A reviewer can test the API quickly without guessing request JSON.
- README has copy-pasteable examples.

### Phase 4 - Strengthen Tests

Goal:

Make the project more reliable before deployment.

Tasks:

- Add tests for column alias cleaning:
  - `stockcode`
  - `Stock Code`
  - `InvoiceDate`
  - `Customer ID`
- Add tests for invalid API input.
- Add tests for recommender fallback behavior.
- Add tests for model metadata loading.
- Add a note explaining warnings seen during tests.

Completion criteria:

- Tests cover API behavior, cleaning behavior, and model loading behavior.
- `python -m pytest` passes consistently.

### Phase 5 - Git And GitHub Cleanup

Goal:

Make the repository clean and shareable.

Tasks:

- Fix the local Git config permission issue if it blocks Git commands.
- Run:

```powershell
git status
```

- Confirm ignored folders are not staged:

```text
data/
models/
mlruns/
.venv/
```

- Stage code files.
- Commit project.
- Push to GitHub.
- Confirm GitHub repo shows:
  - app code
  - scripts
  - tests
  - Dockerfile
  - README
  - docs
  - GitHub Actions workflow

Completion criteria:

- GitHub has the source code.
- GitHub does not contain dataset, trained models, venv, or MLflow logs.

### Phase 6 - Local Production Readiness

Goal:

Verify the project works like a production container before cloud.

Tasks:

- Rebuild Docker image:

```powershell
docker build -t customer-intelligence-api:local .
```

- Run Docker container with mounted model files.
- Test:

```text
http://127.0.0.1:8080/health
http://127.0.0.1:8080/docs
```

- Confirm:

```json
"demo_mode": false
```

- Add Docker instructions to README if needed.

Completion criteria:

- API works outside the local Python virtual environment.
- Dockerized API uses real trained model artifacts.

### Phase 7 - AWS Deployment Preparation (COMPLETE, 2026-08-07)

Goal:

Prepare AWS resources without rushing deployment.

Status: done. S3 bucket + model files, ECR repository, both ECS IAM roles, GitHub OIDC provider, and the GitHub Actions deploy role all exist and are correctly scoped. See "AWS Deployment History" above for exact resource names and what was fixed (the deploy role's policy was stale from an earlier App Runner attempt and had to be replaced with ECS-scoped permissions).

### Phase 8 - AWS Deployment (COMPLETE, 2026-08-07)

Goal:

Deploy the API publicly on AWS ECS Express Mode.

Status: done, then intentionally torn down. The API was deployed live to ECS Express Mode, verified working (`/health` showed `demo_mode: false` with all 3 models loaded, `/docs` served Swagger UI, `/predict/churn` returned a real prediction), then the ECS service/ALB were deleted to stop billing — this was a deliberate cost-control decision, not a failure. GitHub Actions itself was down for a platform-wide outage during this work, so the deploy was done manually via AWS CLI/Docker from local PowerShell rather than through the CI workflow; the workflow should still work on its own next time GitHub Actions is healthy, since all required secrets and IAM roles are now in place. See "AWS Deployment History" above for exact commands to redeploy and re-verify.

### Phase 9 - Resume And Portfolio Polish (COMPLETE, 2026-08-07)

Goal:

Turn the project into a strong resume/interview artifact.

Status: done. Delivered:

- `README.md` rewritten: status banner, endpoints table, mermaid architecture diagram,
  tech stack table, ML explanations (including why time-based churn labels beat the leaky
  `recency_days > 90` approach), verified metrics table, quick start, training output,
  example requests with real responses, tests, smoke test, Docker (both volume-mount and
  S3 modes), AWS deployment status with the cost-control warning, configuration table,
  project structure, and an explicit known-limitations section.
- `docs/architecture.md` (new): five mermaid diagrams — system overview, request sequence
  for `POST /predict/churn`, startup/model-loading decision flow, training pipeline, and
  IAM trust relationships. Plus an AWS resource table with per-resource idle cost and the
  redeploy/teardown commands.
- `docs/interview-notes.md` (new): why FastAPI, why Docker, why models load from S3 rather
  than being baked into the image, why MLflow, why time-based churn labels (with the target
  leakage explanation), why the XGBoost+MLP ensemble, why K-Means and how clusters get
  business names, why TruncatedSVD collaborative filtering, why ECS Express over
  App Runner/Lambda/EKS, what is missing, and a 60-second verbal summary.
- `docs/verification-report.md` (new): verbatim evidence for all 12 verification checks.
- `docs/model-card.md` updated: added a reproducibility section, expanded limitations
  (random vs time-based split, no recommendation metric, untuned ensemble weights, no
  monitoring), refreshed next improvements, cross-links to the other docs.
- `scripts/inspect_metadata.py` (new): CLI that summarizes a trained model bundle —
  version, features, churn training config, metrics, artifact sizes. Exits non-zero on an
  incomplete bundle so it works as a pre-deploy gate. `--json` prints raw metadata.
- `scripts/smoke_test.py` (new): exercises all endpoints plus a 422 validation case against
  any base URL (local, Docker, or a deployed AWS URL). `--wait` polls a booting container,
  `--require-real-models` turns `demo_mode: true` into a failure. Exit code 0/1.
- `.gitignore`: added `aws-tmp/` and `verify_models/`.
- `.github/workflows/deploy.yml`: gated `deploy-aws` behind `workflow_dispatch` so pushes
  no longer create billable AWS resources. See "CI deployment is now manual" below.

Note on screenshots: the original task list asked for UI screenshots. This session ran
headless, so verbatim terminal transcripts in `docs/verification-report.md` were captured
instead — including `GET /docs -> 200` proving Swagger UI is served locally and in Docker.
Screenshots can still be added later by running the app and capturing `/docs`, `/health`,
the MLflow run page, and the Docker container.

## Phase 9 Completion - Verification Run (2026-08-07)

Everything was re-verified before the final commit. Full transcripts are in
`docs/verification-report.md`. Summary — 12/12 passed:

```text
 1. pytest                      12 passed
 2. All 4 endpoints, real models 200, demo_mode: false
 3. Input validation            422 with the offending field named
 4. Churn discrimination        0.1117 (active) vs 0.9360 (dormant)
 5. Recommender cold start      unknown ID -> popular items, 200 not 500
 6. Full training pipeline      1,062,989 raw rows -> metrics reproduced to 4 dp
 7. MLflow                      params + metrics + artifacts logged, run FINISHED
 8. Docker build                2.12 GB
 9. Docker run                  all endpoints 200, non-root user apiuser, Python 3.11.15
10. S3 artifact loading         boto3 downloaded all 4 artifacts, predictions identical
11. AWS resource state          S3 + ECR present; 0 ECS services, 0 load balancers
12. CI workflow YAML            parses, 2 jobs, deploy-aws depends on test
```

Key result: the same churn input returns `0.1117` in the local venv, in the Docker
container, when loading artifacts from S3, and on the live AWS deployment recorded in
`aws-tmp/deployment-evidence.txt`. Identical predictions across four environments.

Also confirmed: **the AWS account is not accruing charges** for this project.
`aws ecs list-services --cluster default` returns `[]` and
`aws elbv2 describe-load-balancers` returns `[]`.

### CI deployment is now manual (changed in Phase 9)

Previously `.github/workflows/deploy.yml` ran the `deploy-aws` job on every push to
`main`. Since all four repository secrets are set, that meant any push — even a README
typo fix — would create a live ECS Express service and ALB (~**\$26/month**), silently
undoing the Phase 8 teardown.

Changed on 2026-08-07 to:

```yaml
on:
  push: ...
  pull_request: ...
  workflow_dispatch:        # added

jobs:
  deploy-aws:
    needs: test
    if: github.event_name == 'workflow_dispatch'    # was: push && ref == refs/heads/main
```

Now:

- Pushing to `main` runs the **test** job only. No AWS resources are created.
- To deploy, open the repo's **Actions** tab and click **Run workflow**.
- The workflow's summary step prints the teardown command as a reminder.

After any manual deploy, tear it down:

```powershell
aws ecs delete-express-gateway-service --service-arn "arn:aws:ecs:ap-south-1:188947281989:service/default/customer-intelligence-api" --region ap-south-1
```

Then wait 9-13 minutes and confirm `aws elbv2 describe-load-balancers --region ap-south-1`
returns an empty list.

### Learning And Documentation

- Continue explaining each step of the project in beginner-friendly language.
- Explain training script line by line.
- Explain model registry, model artifacts, and serving flow deeply.
- Explain each ML model:
  - churn classifier
  - neural network
  - ensemble
  - K-Means
  - recommender
- Add training progress logs so training does not look silent.
- Possibly add a beginner architecture diagram.

### Code Improvements

- Training progress logging has been added to `scripts/train.py`.
- Sample request/response files have been added under `examples/`.

- Add model cards or notes explaining each model and metric.
- Add optional CLI command to inspect `metadata.json`.
- Add more robust column alias configuration for future datasets.

### Testing Improvements

- Tests for data cleaning aliases have been added.
- Tests for invalid API input have been added.
- Tests for recommender fallback behavior have been added.
- Tests for registry metadata loading have been added.
- Add Docker smoke test instructions.

### Git And GitHub

- Resolve local `git status` permission/config issue if it appears again.
- Commit current project files.
- Push to GitHub.
- Confirm `.gitignore` excludes:

```text
data/
models/
mlruns/
.venv/
```

### AWS Deployment

Complete as of 2026-08-07. All 10 of the original steps below are done — kept here for historical reference only. See "AWS Deployment History" above for what actually happened and how to redeploy.

1. ~~Create or use AWS account.~~ (existing account, `188947281989`)
2. ~~Open AWS CloudShell.~~ (used local PowerShell + AWS CLI instead)
3. ~~Create S3 bucket.~~
4. ~~Upload model files to S3.~~
5. ~~Create IAM roles for ECS Express Mode and GitHub Actions.~~
6. ~~Add GitHub repository secrets.~~
7. ~~Push workflow to GitHub.~~ (workflow existed already; re-ran it, but GitHub Actions was down)
8. ~~Let GitHub Actions build and push Docker image to ECR.~~ (done manually via local Docker instead, due to the GitHub Actions outage)
9. ~~Deploy ECS Express service.~~ (deployed, verified, then deliberately torn down to stop billing)
10. ~~Test deployed `/health` and `/docs`.~~ (both confirmed working, plus a real `/predict/churn` call)

## Known Notes And Issues

- Local `git status --short` failed once because Windows tried to read this config path and hit permission denied:

```text
C:/Users/azadh/AppData/Roaming/SPB_Data/.gitconfig
```

This is a local Git configuration issue, not an application code issue.

- On 2026-07-21, `.venv` could not run tests from the Codex shell because it pointed to a Python 3.11 executable that was not visible to that shell. On 2026-07-22, the user recreated the environment and ran `python -m pytest` successfully with `12 passed`.
- On 2026-07-21, `docker version` reported `docker` was not recognized in the Codex shell. On 2026-07-22, the user reported Docker is working locally after fixing Docker Desktop.
- On 2026-07-21, `.gitignore` was verified with `git check-ignore`; `data/`, `models/`, `mlruns/`, and `.venv/` are ignored correctly.
- On 2026-07-25, GitHub Actions failed during pytest collection because Linux CI could not import the local `app` package from new tests. Fixed by adding `pytest.ini` with `pythonpath = .` and pushed commit `cbbf65c`.
- Git commands can currently be run by bypassing the broken global config for the command:

```powershell
$env:GIT_CONFIG_GLOBAL='NUL'
git status --short
```

- `.venv/`, `data/`, `models/`, and `mlruns/` are intentionally ignored by Git.
- `models/` is needed locally to run with real models.
- In production, models should be loaded from S3 through `CI_MODEL_ARTIFACT_URI`.
- `CI_ALLOW_DEMO_MODELS=false` should be used when running with real models.

## Next Best Step

All 9 phases are complete as of 2026-08-07. The project is finished for now.

Optional follow-ups, none of them blocking:

1. **Confirm GitHub Actions works end-to-end.** The workflow has still never completed a
   full CI run — GitHub Actions was in a platform-wide outage during Phase 8, so the
   working deployment was done manually via AWS CLI. The YAML is valid and all secrets and
   IAM roles are in place, but the CI path is unproven. Note that a successful run will
   deploy a live ECS service (see the cost warning above).
2. **Capture UI screenshots** for the README: Swagger UI at `/docs`, the `/health` response
   showing `demo_mode: false`, the MLflow run page, and the Docker container running.
   Terminal evidence for all of these already exists in `docs/verification-report.md`.
3. **Before a live recruiter demo,** redeploy with the commands in "AWS Deployment History"
   above, then tear it down afterwards. The service is not left running by default.
4. **Engineering improvements**, in rough priority order: a strict time-based holdout for
   churn evaluation; structured logging with request IDs and latency metrics; API
   authentication and rate limiting; model monitoring for feature drift; a multi-stage
   Docker build to cut the 2.1 GB image.
