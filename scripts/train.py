import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import accuracy_score, average_precision_score, roc_auc_score, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.churn import ChurnEnsemble
from app.ml.features import (
    CUSTOMER_FEATURE_COLUMNS,
    build_customer_features,
    build_time_based_churn_dataset,
    normalize_transactions,
)
from app.ml.recommender import CollaborativeRecommender
from app.ml.segmentation import CustomerSegmenter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train customer intelligence models.")
    parser.add_argument("--transactions", required=True, help="Path to Online Retail II CSV/XLSX dataset.")
    parser.add_argument("--output-dir", default="models", help="Directory where joblib artifacts are written.")
    parser.add_argument("--experiment-name", default="customer-intelligence", help="MLflow experiment name.")
    parser.add_argument(
        "--prediction-window-days",
        "--churn-after-days",
        dest="prediction_window_days",
        type=int,
        default=90,
        help="Future window used to label churn from real customer return behavior.",
    )
    parser.add_argument(
        "--min-history-days",
        type=int,
        default=90,
        help="Minimum history before the first churn training snapshot.",
    )
    parser.add_argument(
        "--churn-snapshots",
        type=int,
        default=8,
        help="Number of historical cutoff dates used to build churn training examples.",
    )
    parser.add_argument("--n-clusters", type=int, default=4, help="Number of K-Means customer segments.")
    parser.add_argument("--svd-components", type=int, default=50, help="Latent factors for collaborative filtering.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_transactions = load_transactions(Path(args.transactions))
    transactions = normalize_transactions(raw_transactions)
    customer_features = build_customer_features(transactions)
    churn_dataset = build_time_based_churn_dataset(
        transactions,
        prediction_window_days=args.prediction_window_days,
        min_history_days=args.min_history_days,
        max_snapshots=args.churn_snapshots,
    )

    mlflow.set_experiment(args.experiment_name)
    with mlflow.start_run(run_name=f"training-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"):
        mlflow.log_params(
            {
                "prediction_window_days": args.prediction_window_days,
                "min_history_days": args.min_history_days,
                "churn_snapshots": args.churn_snapshots,
                "churn_training_rows": len(churn_dataset),
                "churn_training_customers": churn_dataset["customer_id"].nunique(),
                "n_clusters": args.n_clusters,
                "svd_components": args.svd_components,
                "transactions": len(transactions),
                "customers": len(customer_features),
            }
        )

        churn_model, churn_metrics = train_churn_model(churn_dataset)
        joblib.dump(churn_model, output_dir / "churn_model.joblib")
        mlflow.log_metrics({f"churn_{key}": value for key, value in churn_metrics.items()})

        segment_model, segment_metrics = train_segment_model(customer_features, args.n_clusters)
        joblib.dump(segment_model, output_dir / "segment_model.joblib")
        mlflow.log_metrics({f"segment_{key}": value for key, value in segment_metrics.items()})

        recommender = CollaborativeRecommender.fit(transactions, n_components=args.svd_components)
        joblib.dump(recommender, output_dir / "recommender.joblib")
        mlflow.log_metric("recommender_items", len(recommender.item_ids))
        mlflow.log_metric("recommender_users", len(recommender.user_to_index))

        metadata = {
            "model_version": datetime.now(UTC).strftime("%Y%m%d-%H%M%S"),
            "created_at": datetime.now(UTC).isoformat(),
            "demo_mode": False,
            "feature_columns": CUSTOMER_FEATURE_COLUMNS,
            "churn_training": {
                "strategy": "time_based_snapshots",
                "prediction_window_days": args.prediction_window_days,
                "min_history_days": args.min_history_days,
                "snapshots": args.churn_snapshots,
                "rows": len(churn_dataset),
                "customers": int(churn_dataset["customer_id"].nunique()),
            },
            "metrics": {
                "churn": churn_metrics,
                "segmentation": segment_metrics,
                "recommender": {
                    "items": len(recommender.item_ids),
                    "users": len(recommender.user_to_index),
                },
            },
        }
        (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        for artifact in output_dir.glob("*"):
            mlflow.log_artifact(str(artifact), artifact_path="model_artifacts")

    print(f"Artifacts written to {output_dir.resolve()}")


def load_transactions(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    if path.suffix.lower() in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None)
        return pd.concat(sheets.values(), ignore_index=True)

    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)

    raise ValueError("Unsupported dataset type. Use .csv, .xls, or .xlsx.")


def train_churn_model(churn_dataset: pd.DataFrame) -> tuple[ChurnEnsemble, dict[str, float]]:
    churn_target = churn_dataset["churned"].astype(int)
    if churn_target.nunique() < 2:
        raise ValueError("Churn target contains only one class. Adjust --prediction-window-days.")

    x_train, x_test, y_train, y_test = split_churn_examples(churn_dataset, churn_target)

    xgb_model = _build_xgb_classifier()
    neural_model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("mlp", MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=800, early_stopping=True, random_state=42)),
        ]
    )

    xgb_model.fit(x_train, y_train)
    neural_model.fit(x_train, y_train)
    ensemble = ChurnEnsemble(
        xgb_model=xgb_model,
        neural_model=neural_model,
        feature_columns=CUSTOMER_FEATURE_COLUMNS,
    )

    probabilities = ensemble.predict_proba(x_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "average_precision": float(average_precision_score(y_test, probabilities)),
        "accuracy": float(accuracy_score(y_test, predictions)),
    }
    return ensemble, metrics


def split_churn_examples(
    churn_dataset: pd.DataFrame,
    churn_target: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    from sklearn.model_selection import GroupShuffleSplit

    groups = churn_dataset["customer_id"]
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_index, test_index = next(splitter.split(churn_dataset, churn_target, groups=groups))

    y_train = churn_target.iloc[train_index]
    y_test = churn_target.iloc[test_index]
    if y_train.nunique() < 2 or y_test.nunique() < 2:
        return train_test_split(
            churn_dataset[CUSTOMER_FEATURE_COLUMNS],
            churn_target,
            test_size=0.2,
            random_state=42,
            stratify=churn_target,
        )

    return (
        churn_dataset.iloc[train_index][CUSTOMER_FEATURE_COLUMNS],
        churn_dataset.iloc[test_index][CUSTOMER_FEATURE_COLUMNS],
        y_train,
        y_test,
    )


def _build_xgb_classifier():
    try:
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=250,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingClassifier

        return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, random_state=42)


def train_segment_model(customer_features: pd.DataFrame, n_clusters: int) -> tuple[CustomerSegmenter, dict[str, float]]:
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("kmeans", KMeans(n_clusters=n_clusters, n_init=20, random_state=42)),
        ]
    )
    features = customer_features[CUSTOMER_FEATURE_COLUMNS]
    clusters = pipeline.fit_predict(features)
    labels = label_clusters(customer_features, clusters)
    scaled_features = pipeline.named_steps["scaler"].transform(features)
    metrics = {"silhouette": float(silhouette_score(scaled_features, clusters))}
    return (
        CustomerSegmenter(
            pipeline=pipeline,
            feature_columns=CUSTOMER_FEATURE_COLUMNS,
            cluster_labels=labels,
        ),
        metrics,
    )


def label_clusters(customer_features: pd.DataFrame, clusters) -> dict[int, str]:
    summary = customer_features.assign(cluster=clusters).groupby("cluster")[CUSTOMER_FEATURE_COLUMNS].mean()
    labels: dict[int, str] = {}

    high_value = summary.sort_values(["monetary", "frequency", "recency_days"], ascending=[False, False, True]).index[0]
    labels[int(high_value)] = "high-value"

    remaining = summary.drop(index=high_value)
    if not remaining.empty:
        dormant = remaining.sort_values(["recency_days", "frequency", "monetary"], ascending=[False, True, True]).index[0]
        labels[int(dormant)] = "dormant"
        remaining = remaining.drop(index=dormant)

    if not remaining.empty:
        new_customer = remaining.sort_values(["tenure_days", "frequency"], ascending=[True, True]).index[0]
        labels[int(new_customer)] = "new"
        remaining = remaining.drop(index=new_customer)

    for cluster_id in remaining.index:
        labels[int(cluster_id)] = "at-risk"

    return labels


if __name__ == "__main__":
    main()
