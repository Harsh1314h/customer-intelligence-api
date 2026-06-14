# Customer Intelligence API

Production-style FastAPI service for e-commerce customer intelligence:

- `POST /predict/churn` returns churn probability from an XGBoost plus neural-network ensemble.
- `POST /segment/customer` assigns a K-Means customer segment.
- `POST /recommend` returns collaborative-filtering product recommendations.
- `GET /health` reports model loading status for Cloud Run, App Runner, or container probes.

The API starts with tiny demo artifacts so you can run it immediately. For the real project, train on Kaggle's Online Retail II dataset and replace the demo artifacts in `models/`.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
python -m scripts.create_demo_artifacts
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for Swagger.

## Train Real Models

1. Download the Online Retail II dataset from Kaggle.
2. Put the file at `data/online_retail_II.xlsx` or pass your own path.
3. Run:

```powershell
python -m scripts.train --transactions data/online_retail_II.xlsx --output-dir models
```

For the cleaned CSV currently used in this project:

```powershell
python -m scripts.train --transactions data\online_retail_cleaned.csv --output-dir models
```

The churn model is trained with time-based snapshots: it builds customer features from behavior before each cutoff date, then labels churn from whether the customer returns in the next prediction window. The trainer logs MLflow metrics locally under `mlruns/` and writes:

- `models/churn_model.joblib`
- `models/segment_model.joblib`
- `models/recommender.joblib`
- `models/metadata.json`

## Example Requests

```powershell
curl -X POST http://127.0.0.1:8000/predict/churn `
  -H "Content-Type: application/json" `
  -d "{\"customer\":{\"customer_id\":\"17850\",\"recency_days\":22,\"frequency\":18,\"monetary\":3420.5,\"tenure_days\":340,\"avg_order_value\":190.03,\"total_items\":620,\"unique_products\":47}}"
```

```powershell
curl -X POST http://127.0.0.1:8000/recommend `
  -H "Content-Type: application/json" `
  -d "{\"customer_id\":\"17850\",\"recent_product_ids\":[\"85123A\",\"71053\"],\"top_n\":5}"
```

## GCP Deployment

Use Google Cloud Run when you want the architecture in your diagram.

```powershell
gcloud services enable run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com
gcloud artifacts repositories create customer-intelligence --repository-format=docker --location=asia-south1
gcloud storage buckets create gs://YOUR_BUCKET_NAME --location=asia-south1
gcloud storage cp models/* gs://YOUR_BUCKET_NAME/customer-intelligence/models/
```

Set these GitHub secrets:

- `GCP_PROJECT_ID`
- `GCP_SA_KEY`
- `CI_MODEL_ARTIFACT_URI=gs://YOUR_BUCKET_NAME/customer-intelligence/models/`

The workflow in `.github/workflows/deploy.yml` runs tests, builds the Docker image, pushes to Artifact Registry, and deploys to Cloud Run.

## AWS Alternative

The same API can run on AWS App Runner or ECS Fargate. Store artifacts in S3 and set:

```powershell
aws s3 cp models/ s3://YOUR_BUCKET_NAME/customer-intelligence/models/ --recursive
```

Runtime environment variables:

- `CI_MODEL_ARTIFACT_URI=s3://YOUR_BUCKET_NAME/customer-intelligence/models/`
- `CI_ALLOW_DEMO_MODELS=false`

Use ECR for the Docker image and App Runner for the managed service if you want a Cloud Run-like AWS setup.

## Production Notes

- Keep `CI_ALLOW_DEMO_MODELS=false` in production so missing artifacts fail fast.
- Use GCP service account permissions for Cloud Storage reads, or AWS IAM permissions for S3 reads.
- The included neural model uses `sklearn.neural_network.MLPClassifier` to keep the container lightweight. You can swap it for TensorFlow/Keras later without changing the API contract.
