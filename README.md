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

During training, the script prints progress like:

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

## Example Requests

Ready-to-copy request examples are also available in:

- `examples/churn_request.json`
- `examples/segment_request.json`
- `examples/recommend_request.json`
- `examples/health_response.json`

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

## AWS Deployment

The production workflow uses AWS App Runner, ECR, and S3:

- GitHub Actions runs tests on every push and pull request.
- Docker images are pushed to Amazon ECR.
- Trained model artifacts are loaded from Amazon S3.
- AWS App Runner serves the public HTTPS API.

Store artifacts in S3 and set:

```powershell
aws s3 cp models/ s3://YOUR_BUCKET_NAME/customer-intelligence/models/ --recursive
```

Runtime environment variables:

- `CI_MODEL_ARTIFACT_URI=s3://YOUR_BUCKET_NAME/customer-intelligence/models/`
- `CI_ALLOW_DEMO_MODELS=false`

Full step-by-step setup is in `docs/aws-deployment.md`.

## Production Notes

- Keep `CI_ALLOW_DEMO_MODELS=false` in production so missing artifacts fail fast.
- Use AWS IAM permissions for S3 model artifact reads.
- The included neural model uses `sklearn.neural_network.MLPClassifier` to keep the container lightweight. You can swap it for TensorFlow/Keras later without changing the API contract.
