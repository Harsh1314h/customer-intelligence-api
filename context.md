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
- AWS deployment files have been prepared, but actual AWS deployment is paused.
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
- AWS App Runner for hosted API.
- GitHub Actions for CI/CD.

AWS deployment is not completed yet. It is intentionally paused while learning the project.

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

### Phase 7 - AWS Deployment Preparation

Goal:

Prepare AWS resources without rushing deployment.

Tasks:

- Understand where AWS commands run:
  - AWS CloudShell for `aws ...` commands
  - local PowerShell for project commands
  - GitHub website for secrets
- Create S3 bucket for model artifacts.
- Upload model files:

```text
churn_model.joblib
segment_model.joblib
recommender.joblib
metadata.json
```

- Create ECR repository.
- Create IAM role for App Runner to pull from ECR.
- Create IAM role for App Runner runtime to read from S3.
- Create GitHub Actions deploy role.
- Add first GitHub secret:

```text
AWS_ROLE_TO_ASSUME
```

Completion criteria:

- AWS has S3 bucket and IAM roles ready.
- GitHub can authenticate to AWS using OIDC.

### Phase 8 - AWS Deployment

Goal:

Deploy the API publicly on AWS App Runner.

Tasks:

- Push workflow to GitHub.
- Let GitHub Actions build image and push to ECR.
- Create App Runner service from the ECR image.
- Configure environment variables:

```text
CI_MODEL_ARTIFACT_URI=s3://YOUR_BUCKET/customer-intelligence/models/
CI_ALLOW_DEMO_MODELS=false
```

- Add remaining GitHub secrets:

```text
APP_RUNNER_SERVICE_ARN
APP_RUNNER_ACCESS_ROLE_ARN
CI_MODEL_ARTIFACT_URI
```

- Push again or rerun workflow.
- Test deployed API:

```text
https://YOUR_APP_RUNNER_URL/health
https://YOUR_APP_RUNNER_URL/docs
```

Completion criteria:

- Public API is live.
- `/health` shows real models loaded.
- Swagger UI works from App Runner URL.

### Phase 9 - Resume And Portfolio Polish

Goal:

Turn the project into a strong resume/interview artifact.

Tasks:

- Improve README with:
  - project overview
  - architecture diagram
  - endpoints table
  - ML methods used
  - metrics
  - deployment link
  - screenshots
- Add a short `docs/model-card.md`.
- Add a short `docs/interview-notes.md` explaining:
  - why FastAPI
  - why Docker
  - why MLflow
  - why time-based churn labels
  - why S3/ECR/App Runner
- Add final architecture diagram showing:
  - client
  - App Runner
  - FastAPI
  - model registry
  - S3 model artifacts
  - ECR image
  - GitHub Actions

Completion criteria:

- Project can be explained in interviews.
- README is polished enough to send to recruiters.
- Deployment URL and screenshots prove it works.

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

Paused for now.

Remaining AWS tasks:

1. Create or use AWS account.
2. Open AWS CloudShell.
3. Create S3 bucket.
4. Upload model files to S3.
5. Create IAM roles for App Runner and GitHub Actions.
6. Add GitHub repository secrets.
7. Push workflow to GitHub.
8. Let GitHub Actions build and push Docker image to ECR.
9. Create App Runner service.
10. Test deployed `/health` and `/docs`.

## Known Notes And Issues

- Local `git status --short` failed once because Windows tried to read this config path and hit permission denied:

```text
C:/Users/azadh/AppData/Roaming/SPB_Data/.gitconfig
```

This is a local Git configuration issue, not an application code issue.

- On 2026-07-21, `.venv` could not run tests from the Codex shell because it pointed to a Python 3.11 executable that was not visible to that shell. On 2026-07-22, the user recreated the environment and ran `python -m pytest` successfully with `12 passed`.
- On 2026-07-21, `docker version` reported `docker` was not recognized in the Codex shell. On 2026-07-22, the user reported Docker is working locally after fixing Docker Desktop.
- On 2026-07-21, `.gitignore` was verified with `git check-ignore`; `data/`, `models/`, `mlruns/`, and `.venv/` are ignored correctly.
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

Before continuing AWS deployment, the best next step is repairing local validation:

1. Confirm the GitHub Actions run status on GitHub.
2. Move to AWS model storage preparation.
3. Create S3 bucket and upload model artifacts.
4. Prepare AWS IAM roles for App Runner and GitHub Actions.
