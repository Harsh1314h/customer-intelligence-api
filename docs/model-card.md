# Model Card

## Project

Customer Intelligence API for e-commerce.

## Models

| Model | Type | Endpoint | Output |
| --- | --- | --- | --- |
| Churn ensemble | Supervised classification | `/predict/churn` | Churn probability and risk band |
| Customer segmenter | K-Means clustering | `/segment/customer` | Business segment and cluster ID |
| Product recommender | Collaborative filtering | `/recommend` | Ranked product recommendations |

## Dataset

The models were trained from cleaned Online Retail transaction data stored locally as:

```text
data/online_retail_cleaned.csv
```

The raw transaction columns are normalized into standard names such as:

```text
invoice_id
stock_code
description
quantity
invoice_date
unit_price
customer_id
country
```

## Feature Set

Customer-level models use:

```text
recency_days
frequency
monetary
tenure_days
avg_order_value
total_items
unique_products
```

## Churn Modeling Approach

The churn model uses time-based snapshots:

1. Select historical cutoff dates.
2. Build customer features using only transactions before each cutoff.
3. Check whether each customer returns in the next prediction window.
4. Train the classifier on past behavior and future return/non-return labels.

This avoids directly using current inactivity as both feature and label.

## Current Metrics

| Metric | Value |
| --- | ---: |
| Churn ROC AUC | `0.7916` |
| Churn average precision | `0.8232` |
| Churn accuracy | `0.7372` |
| Segmentation silhouette | `0.4061` |
| Recommender products | `4,631` |
| Recommender customers | `5,878` |

## Artifact Files

```text
models/churn_model.joblib
models/segment_model.joblib
models/recommender.joblib
models/metadata.json
```

For AWS deployment, these artifacts are stored in:

```text
s3://customer-intelligence-models-harsh1314h/customer-intelligence/models/
```

## Intended Use

The API is intended for portfolio and learning use as an example of:

- serving ML models through REST endpoints
- validating API contracts with Pydantic
- tracking experiments with MLflow
- packaging ML services with Docker
- preparing cloud deployment with AWS

## Limitations

- The dataset is historical retail data, not live production traffic.
- The churn definition is based on future return behavior within a fixed prediction window.
- Recommendations are collaborative-filtering based and do not use product images, text embeddings, or real-time session behavior.
- Segment labels are business-friendly names mapped from K-Means clusters, not manually labeled ground truth.
- The neural network is intentionally lightweight for local CPU training.

## Next Improvements

- Add periodic retraining.
- Add batch scoring jobs.
- Add model monitoring.
- Add stronger recommendation evaluation metrics.
- Add richer product/customer features.
- Deploy and verify the public AWS ECS Express API.
