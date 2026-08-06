# Verification Report

Full end-to-end verification of the project, run on **2026-08-07**.

Every command below was actually executed and every response is copied verbatim from the
terminal. Nothing here is illustrative.

**Environment:** Windows 11 · Python 3.11.9 (`.venv`) · Docker 29.5.3 · AWS CLI v2
authenticated as `arn:aws:iam::188947281989:user/customer-intelligence-admin`

**Summary: 12 of 12 checks passed.**

| # | Area | Check | Result |
| ---: | --- | --- | :---: |
| 1 | Tests | `pytest` suite | ✅ 12 passed |
| 2 | API | All four endpoints, real models | ✅ 200 |
| 3 | API | Input validation rejects bad requests | ✅ 422 |
| 4 | ML | Churn model discriminates risk | ✅ 0.11 vs 0.94 |
| 5 | ML | Recommender cold-start fallback | ✅ 200 |
| 6 | Training | Full pipeline on 1.06 M rows | ✅ metrics reproduced exactly |
| 7 | MLflow | Params + metrics + artifacts logged | ✅ run `FINISHED` |
| 8 | Docker | Image builds | ✅ 2.12 GB |
| 9 | Docker | Container serves all endpoints | ✅ 200, non-root |
| 10 | AWS | S3 artifact loading (production path) | ✅ models loaded from S3 |
| 11 | AWS | Resource state matches docs | ✅ no billable resources |
| 12 | CI | Workflow YAML parses, jobs correct | ✅ 2 jobs |

---

## 1. Test suite

```powershell
python -m pytest -v
```

```text
platform win32 -- Python 3.11.9, pytest-8.2.2, pluggy-1.6.0
rootdir: C:\customer-intelligence-api-main\customer-intelligence-api-main
configfile: pytest.ini
collected 12 items

tests/test_api.py::test_health_endpoint_loads_demo_models PASSED         [  8%]
tests/test_api.py::test_churn_prediction_contract PASSED                 [ 16%]
tests/test_api.py::test_customer_segmentation_contract PASSED            [ 25%]
tests/test_api.py::test_recommendation_contract PASSED                   [ 33%]
tests/test_api.py::test_churn_rejects_negative_customer_features PASSED  [ 41%]
tests/test_api.py::test_recommend_rejects_unbounded_top_n PASSED         [ 50%]
tests/test_features.py::test_time_based_churn_dataset_uses_future_return_behavior PASSED [ 58%]
tests/test_features.py::test_normalize_transactions_accepts_common_column_aliases PASSED [ 66%]
tests/test_features.py::test_normalize_transactions_reports_missing_required_columns PASSED [ 75%]
tests/test_recommender.py::test_recommender_falls_back_to_popular_items_for_unknown_customer PASSED [ 83%]
tests/test_registry.py::test_registry_reads_metadata PASSED              [ 91%]
tests/test_registry.py::test_registry_errors_when_artifacts_missing_and_demo_disabled PASSED [100%]

======================= 12 passed, 7 warnings in 6.60s ========================
```

### About the warnings

Both are benign and expected:

- `PendingDeprecationWarning: Please use 'import python_multipart' instead` — raised
  inside Starlette's form parser, not this project's code. It disappears when Starlette
  updates its own import.
- `ConvergenceWarning: Stochastic Optimizer: Maximum iterations (700) reached` — the
  `MLPClassifier` in the *demo* artifacts is intentionally tiny and trained on a handful
  of synthetic rows, so it does not converge. This affects demo artifacts only, never the
  real trained models.

---

## 2. Live API — all endpoints with real trained models

Server started against the real artifacts:

```powershell
$env:CI_MODEL_DIR="models"; $env:CI_ALLOW_DEMO_MODELS="false"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

### `GET /health` → `200`

```json
{
  "status": "ok",
  "models_loaded": { "churn": true, "segment": true, "recommender": true },
  "model_version": "20260613-194657",
  "demo_mode": false,
  "artifact_uri": null
}
```

`demo_mode: false` with all three models loaded — this is real model serving, not demo
fallback.

### `POST /predict/churn` → `200`

Request — `examples/churn_request.json`:

```json
{ "customer": { "customer_id": "17850", "recency_days": 22, "frequency": 18,
  "monetary": 3420.5, "tenure_days": 340, "avg_order_value": 190.03,
  "total_items": 620, "unique_products": 47 } }
```

Response:

```json
{ "customer_id": "17850", "churn_probability": 0.1117, "risk_band": "low",
  "model_version": "20260613-194657" }
```

### `POST /segment/customer` → `200`

```json
{ "customer_id": "17850", "segment": "new", "cluster_id": 0,
  "distance_to_centroid": 1.3553, "model_version": "20260613-194657" }
```

### `POST /recommend` → `200`

```json
{ "customer_id": "17850", "recommendations": [
    { "product_id": "72752A", "score": 68.4423, "name": "F.FAIRY,CANDLE IN GLASS,LILY/VALLEY" },
    { "product_id": "72751A", "score": 68.4423, "name": "F.FAIRY S/3 SML CANDLE,LILY/VALLEY" },
    { "product_id": "72751B", "score": 68.4423, "name": "F.FAIRY S/3 SML CANDLE, LAVENDER" },
    { "product_id": "35603B", "score": 55.0456, "name": "S/16 BLACK SHINY/MAT BAUBLES" },
    { "product_id": "21343", "score": 44.9041, "name": "GOLD JEWELERY BOX" }
  ], "model_version": "20260613-194657" }
```

Real product names resolved from the training data, correctly ranked by score.

### Docs endpoints

```text
GET /docs         -> 200   (Swagger UI)
GET /openapi.json -> 200   (OpenAPI schema)
```

---

## 3. Input validation

| Request | Expected | Actual |
| --- | --- | --- |
| `recency_days: -5` | reject | `422` — `"Input should be greater than or equal to 0"`, `loc: [body, customer, recency_days]` |
| customer missing all features | reject | `422` — one `"Field required"` entry per missing field |
| `top_n: 500` | reject | `422` — `"Input should be less than or equal to 50"` |

Each error names the exact offending field. Validation fires before any model code runs.

---

## 4. Churn model actually discriminates

A model that returns a constant would still pass a contract test. Two opposite customer
profiles were sent to confirm real signal:

| Profile | Input | `churn_probability` | `risk_band` |
| --- | --- | ---: | --- |
| Active, high-value | recency 22 d, frequency 18, monetary 3420.5 | `0.1117` | `low` |
| Dormant, low-value | recency 400 d, frequency 1, monetary 15.5 | `0.9360` | `high` |

A spread of `0.11` → `0.94` in the expected direction, with both risk bands exercised.

---

## 5. Recommender cold-start fallback

Unknown customer ID (never seen in training):

```json
POST /recommend  { "customer_id": "NOT_A_REAL_ID_999", "top_n": 3 }
```

```json
{ "customer_id": "NOT_A_REAL_ID_999", "recommendations": [
  { "product_id": "84077",  "score": 4631.0, "name": "WORLD WAR 2 GLIDERS ASSTD DESIGNS" },
  { "product_id": "85099B", "score": 4630.0, "name": "JUMBO BAG RED WHITE SPOTTY " },
  { "product_id": "85123A", "score": 4629.0, "name": "WHITE HANGING HEART T-LIGHT HOLDER" } ] }
```

Degrades to global popularity instead of erroring — `200`, not `500`.

`include_seen: true` was also verified to return a different (unfiltered) ranking,
confirming the seen-item filter is applied.

---

## 6. Full training pipeline — metrics reproduce exactly

The complete pipeline was re-run from the raw CSV to a scratch output directory (the real
`models/` was left untouched):

```powershell
python -m scripts.train `
  --transactions data\online_retail_cleaned.csv `
  --output-dir <scratch>\verify_models `
  --experiment-name customer-intelligence-verify
```

```text
[1/8] Loading transactions from ...online_retail_cleaned.csv...
  - raw rows: 1,062,989
[2/8] Cleaning transactions...
  - cleaned rows: 805,549
[3/8] Building latest customer features...
  - customers: 5,878
[4/8] Building time-based churn training snapshots...
  - churn rows: 30,823
  - churn customers: 5,281
[5/8] Starting MLflow experiment 'customer-intelligence-verify'...
[6/8] Training churn ensemble...
  Churn metrics:
  - roc_auc: 0.7916
  - average_precision: 0.8232
  - accuracy: 0.7372
[7/8] Training K-Means customer segmentation...
  Segmentation metrics:
  - silhouette: 0.4061
[8/8] Training collaborative filtering recommender and saving artifacts...
  Recommender stats:
  - items: 4631
  - users: 5878
Done. Artifacts written to ...\verify_models
```

**Every metric matches the values recorded in `README.md` and `docs/model-card.md` to
four decimal places.** Training is fully reproducible — the `random_state=42` seeding
across XGBoost, the MLP, K-Means, and TruncatedSVD holds.

All four artifacts were written (`churn_model.joblib`, `segment_model.joblib`,
`recommender.joblib`, `metadata.json`), with byte sizes identical to the committed
production artifacts.

---

## 7. MLflow tracking

Queried the run written by the training above:

```text
experiment: customer-intelligence-verify (400846662422888326)
run: training-20260806-201728   status: FINISHED

  metrics.churn_accuracy           = 0.7372108178559792
  metrics.churn_average_precision  = 0.8232340833069525
  metrics.churn_roc_auc            = 0.7916483366437135
  metrics.recommender_items        = 4631.0
  metrics.recommender_users        = 5878.0
  metrics.segment_silhouette       = 0.40614202923091813

  params.churn_snapshots           = 8
  params.churn_training_customers  = 5281
  params.churn_training_rows       = 30823
  params.customers                 = 5878
  params.min_history_days          = 90
  params.n_clusters                = 4
  params.prediction_window_days    = 90
  params.svd_components            = 50
  params.transactions              = 805549
```

All parameters and metrics logged, run status `FINISHED`, model artifacts attached under
`model_artifacts`.

---

## 8–9. Docker

### Build

```powershell
docker build -t customer-intelligence-api:local .
```

```text
exporting to image ... DONE
naming to docker.io/library/customer-intelligence-api:local done
customer-intelligence-api:local   2.12GB
```

### Run with mounted real artifacts

```powershell
docker run -d --name ci-api-verify -p 8012:8080 `
  -e CI_MODEL_DIR=/app/models -e CI_ALLOW_DEMO_MODELS=false `
  -v "C:\Users\azadh\OneDrive\Documents\ecommerceAPI\models:/app/models:ro" `
  customer-intelligence-api:local
```

```text
INFO:     Started server process [7]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

### Endpoints through the container

| Endpoint | Status | Response |
| --- | :---: | --- |
| `GET /health` | `200` | `demo_mode: false`, all three models loaded |
| `POST /predict/churn` | `200` | `churn_probability: 0.1117`, `risk_band: low` |
| `POST /segment/customer` | `200` | `segment: new`, `distance_to_centroid: 1.3553` |
| `POST /recommend` | `200` | same 5 ranked products as local |
| `GET /docs` | `200` | Swagger UI |

**Byte-identical predictions between the local venv and the container.** The pinned
dependency set reproduces exactly across environments — which is the whole reason the
service is containerized.

### Container hardening

```text
$ docker exec ci-api-verify whoami
apiuser

$ docker exec ci-api-verify python -c "import sys; print(sys.version)"
3.11.15 (main, Aug  5 2026, 01:10:23) [GCC 14.2.0]
```

Runs as a non-root user, on the pinned Python 3.11.

> **Windows note:** run this `docker run` from **PowerShell**, not Git Bash. Git Bash
> rewrites the Windows path in `-v` and the mount silently resolves to an empty
> directory, which makes the container exit with
> `RuntimeError: Missing model artifacts`.

---

## 10. S3 artifact loading — the production code path

This is the exact path the live ECS deployment used. Started with an **empty** model
directory and only an S3 URI:

```powershell
$env:CI_MODEL_DIR="<scratch>\s3_models"          # empty, does not exist
$env:CI_MODEL_ARTIFACT_URI="s3://customer-intelligence-models-harsh1314h/customer-intelligence/models/"
$env:CI_ALLOW_DEMO_MODELS="false"
```

```text
S3 /health           -> 200  {"status": "ok", "models_loaded": {"churn": true, "segment": true,
                              "recommender": true}, "model_version": "20260613-194657",
                              "demo_mode": false,
                              "artifact_uri": "s3://customer-intelligence-models-harsh1314h/customer-intelligence/models/"}
S3 /predict/churn    -> 200  {'churn_probability': 0.1117, 'risk_band': 'low'}
S3 /segment/customer -> 200  {'segment': 'new', 'cluster_id': 0, 'distance_to_centroid': 1.3553}
S3 /recommend        -> 200  5 items
```

Files downloaded into the previously empty directory:

```text
churn_model.joblib     444,896
metadata.json              803
recommender.joblib   7,077,516
segment_model.joblib    25,744
```

`boto3` downloaded all four artifacts from the real bucket, `ModelRegistry` loaded them,
and predictions matched the local run exactly.

### Demo fallback also verified

With `CI_ALLOW_DEMO_MODELS=true` and no artifacts present, the registry generates demo
models and reports them honestly:

```text
demo /health -> {'model_version': 'demo-0.1.0', 'demo_mode': True, ...}
demo churn   -> {'churn_probability': 0.0589, 'risk_band': 'low', 'model_version': 'demo-0.1.0'}
```

`demo_mode: true` makes it impossible to mistake demo output for real predictions.

---

## 11. AWS resource state

```text
$ aws sts get-caller-identity
{ "Account": "188947281989",
  "Arn": "arn:aws:iam::188947281989:user/customer-intelligence-admin" }
```

**S3 model artifacts — present:**

```text
2026-07-22 02:28:49     444896 churn_model.joblib
2026-07-22 02:28:48        803 metadata.json
2026-07-22 02:28:48    7077516 recommender.joblib
2026-07-22 02:28:41      25744 segment_model.joblib
```

**ECR images — present:**

```text
["manual-20260807", "latest"]                        pushed 2026-08-07T01:05:09
["b78df7d442ad030f9a8dac5977f04f2615d6ed31"]         pushed 2026-07-26T00:55:12
["cbbf65ce8fee01bd77cff813900a7e879b4b4e10"]         pushed 2026-07-25T23:58:07
```

**Billable resources — confirmed absent:**

```text
$ aws ecs list-services --cluster default --region ap-south-1
{ "serviceArns": [] }

$ aws elbv2 describe-load-balancers --region ap-south-1 --query "LoadBalancers[].LoadBalancerName"
[]
```

No running ECS service and no load balancer — **the AWS account is not accruing charges
for this project.** Teardown after the Phase 8 deployment is confirmed complete.

### Cross-check against the live deployment

The live ECS deployment on 2026-08-07 recorded (`aws-tmp/deployment-evidence.txt`, local
only):

```text
Service URL: https://cu-2e0fbe4eb0454f1facc22a5cf4b20836.ecs.ap-south-1.on.aws
POST /predict/churn -> {"churn_probability":0.1117,"risk_band":"low",
                        "model_version":"20260613-194657"}
```

Today's local, Docker, and S3-backed runs all return **`0.1117`** for the same input.
Identical predictions across four environments — laptop venv, local container, S3-backed
load, and the live AWS deployment.

---

## 12. CI workflow

`.github/workflows/deploy.yml` parses as valid YAML with the expected job graph:

```text
jobs: ['test', 'deploy-aws']
  test       -> [checkout@v4, setup-python@v5, Install dependencies, Run tests]
  deploy-aws -> [checkout@v4, Configure AWS credentials, Create ECR repository if missing,
                 Login to Amazon ECR, Build and push image, Deploy ECS Express service,
                 Print deployment summary]
```

`deploy-aws` depends on `test`, so a failing test suite blocks deployment. AWS auth is
via OIDC (`id-token: write`) with no long-lived access keys stored in GitHub.

The `deploy-aws` job is gated on `if: github.event_name == 'workflow_dispatch'`, so
pushing to `main` runs the tests but does **not** create AWS resources. Deployment is a
deliberate manual action from the Actions tab. This was changed during Phase 9 — before
it, every push to `main` would have created a live ECS service and ALB (~\$26/month),
silently undoing the Phase 8 teardown.

---

## Not verified

Stated plainly rather than implied:

- **GitHub Actions has never completed a full run end-to-end.** GitHub Actions was in a
  platform-wide outage during Phase 8, so the working deployment was done manually via
  AWS CLI. The workflow YAML is valid and all four repository secrets and IAM roles are
  in place, but the CI path itself remains unproven.
- **No live public URL right now.** The ECS service is intentionally torn down. Live
  behavior is evidenced by the Phase 8 deployment record, not by a currently reachable
  endpoint.
- **No UI screenshots.** This verification was run headless; the terminal transcripts
  above are the evidence in their place. `GET /docs` returning `200` confirms Swagger UI
  is served, in both the local and containerized runs.
- **No load or latency testing.** Throughput, p99 latency, and concurrent-request
  behavior are unmeasured.
