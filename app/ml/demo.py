import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.churn import ChurnEnsemble
from app.ml.features import CUSTOMER_FEATURE_COLUMNS
from app.ml.recommender import CollaborativeRecommender
from app.ml.segmentation import CustomerSegmenter


def create_demo_artifacts(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    customer_count = 220

    features = pd.DataFrame(
        {
            "recency_days": rng.gamma(shape=2.1, scale=32, size=customer_count).clip(1, 220),
            "frequency": rng.poisson(lam=9, size=customer_count).clip(1, 45),
            "monetary": rng.gamma(shape=3.2, scale=420, size=customer_count).clip(20, 9000),
            "tenure_days": rng.integers(20, 730, size=customer_count),
            "avg_order_value": rng.gamma(shape=2.4, scale=55, size=customer_count).clip(5, 850),
            "total_items": rng.integers(3, 900, size=customer_count),
            "unique_products": rng.integers(1, 130, size=customer_count),
        }
    )
    churn_score = (
        0.035 * features["recency_days"]
        - 0.11 * features["frequency"]
        - 0.00025 * features["monetary"]
        - 0.001 * features["tenure_days"]
        + rng.normal(0, 0.8, size=customer_count)
    )
    churn_target = (churn_score > np.median(churn_score)).astype(int)

    xgb_like_model = RandomForestClassifier(n_estimators=80, random_state=42, min_samples_leaf=3)
    neural_model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("mlp", MLPClassifier(hidden_layer_sizes=(16, 8), max_iter=700, random_state=42)),
        ]
    )
    xgb_like_model.fit(features[CUSTOMER_FEATURE_COLUMNS], churn_target)
    neural_model.fit(features[CUSTOMER_FEATURE_COLUMNS], churn_target)
    churn_model = ChurnEnsemble(
        xgb_model=xgb_like_model,
        neural_model=neural_model,
        feature_columns=CUSTOMER_FEATURE_COLUMNS,
    )
    joblib.dump(churn_model, output_dir / "churn_model.joblib")

    segment_pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("kmeans", KMeans(n_clusters=4, n_init=20, random_state=42)),
        ]
    )
    segment_pipeline.fit(features[CUSTOMER_FEATURE_COLUMNS])
    labels = _label_demo_clusters(segment_pipeline, features)
    joblib.dump(
        CustomerSegmenter(
            pipeline=segment_pipeline,
            feature_columns=CUSTOMER_FEATURE_COLUMNS,
            cluster_labels=labels,
        ),
        output_dir / "segment_model.joblib",
    )

    transactions = _build_demo_transactions(rng)
    recommender = CollaborativeRecommender.fit(transactions, n_components=8)
    joblib.dump(recommender, output_dir / "recommender.joblib")

    metadata = {
        "model_version": "demo-0.1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "demo_mode": True,
        "feature_columns": CUSTOMER_FEATURE_COLUMNS,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _label_demo_clusters(pipeline: Pipeline, features: pd.DataFrame) -> dict[int, str]:
    clusters = pipeline.predict(features[CUSTOMER_FEATURE_COLUMNS])
    cluster_frame = features.assign(cluster=clusters)
    summary = cluster_frame.groupby("cluster")[CUSTOMER_FEATURE_COLUMNS].mean()

    labels: dict[int, str] = {}
    high_value = summary.sort_values(["monetary", "frequency", "recency_days"], ascending=[False, False, True]).index[0]
    labels[int(high_value)] = "high-value"

    remaining = summary.drop(index=high_value)
    dormant = remaining.sort_values(["recency_days", "frequency", "monetary"], ascending=[False, True, True]).index[0]
    labels[int(dormant)] = "dormant"

    remaining = remaining.drop(index=dormant)
    new_customer = remaining.sort_values(["tenure_days", "frequency"], ascending=[True, True]).index[0]
    labels[int(new_customer)] = "new"

    for cluster_id in remaining.drop(index=new_customer).index:
        labels[int(cluster_id)] = "at-risk"

    return labels


def _build_demo_transactions(rng: np.random.Generator) -> pd.DataFrame:
    customer_ids = [f"C{customer_id:04d}" for customer_id in range(1, 61)]
    product_ids = [f"P{product_id:04d}" for product_id in range(1, 41)]
    product_names = {product_id: f"Demo product {product_id}" for product_id in product_ids}
    rows = []

    for customer_id in customer_ids:
        preferred = rng.choice(product_ids, size=rng.integers(4, 9), replace=False)
        for product_id in preferred:
            rows.append(
                {
                    "customer_id": customer_id,
                    "stock_code": product_id,
                    "description": product_names[product_id],
                    "quantity": int(rng.integers(1, 8)),
                }
            )

    return pd.DataFrame(rows)
