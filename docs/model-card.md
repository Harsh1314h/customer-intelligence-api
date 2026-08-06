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

## Reproducibility

All metrics above were re-verified on 2026-08-07 by re-running the full training pipeline
from the raw CSV. Every value reproduced to four decimal places — `random_state=42` is
set consistently across XGBoost, the MLP, K-Means, and TruncatedSVD. See
[`verification-report.md`](verification-report.md).

## Limitations

- The dataset is historical retail data, not live production traffic.
- The churn definition is based on future return behavior within a fixed prediction window.
- **The churn train/test split is random rather than a strict time-based holdout.** Snapshots
  overlap in time and the same customer appears in multiple rows, so training examples are
  not fully independent and the reported ROC AUC is likely slightly optimistic. A stricter
  evaluation would train on early cutoffs and test only on the latest.
- **There is no recommendation quality metric.** No precision@k or recall@k is reported,
  because offline evaluation of implicit-feedback recommenders is difficult to do honestly;
  the real answer is an online A/B test. The recommender is therefore *unevaluated*, not
  *evaluated as good*.
- Recommendations are collaborative-filtering based and do not use product images, text embeddings, or real-time session behavior.
- Segment labels are business-friendly names mapped from K-Means clusters, not manually labeled ground truth. `k=4` was chosen for interpretability, not by optimizing the silhouette score.
- The `distance_to_centroid` field should be read as a confidence signal — a large distance means the customer sits between clusters and the segment label is less meaningful.
- The neural network is intentionally lightweight for local CPU training.
- The ensemble weights (XGBoost `0.65` / MLP `0.35`) are a judgement call, not the result of a tuning sweep.
- **No model monitoring exists.** Nothing detects feature drift or a collapse in the churn
  score distribution, which is the standard failure mode of a deployed model.

## Next Improvements

- Add a strict time-based holdout for churn evaluation.
- Add periodic scheduled retraining, gated on a metric threshold before promoting artifacts to S3.
- Add batch scoring jobs.
- Add model monitoring for feature drift and score-distribution shift.
- Tune the ensemble weights, or replace the fixed blend with a stacking meta-learner.
- Add richer product/customer features.

## Related Documentation

- [`architecture.md`](architecture.md) — system, request, startup, and training diagrams
- [`interview-notes.md`](interview-notes.md) — why each modeling decision was made
- [`verification-report.md`](verification-report.md) — end-to-end verification evidence
