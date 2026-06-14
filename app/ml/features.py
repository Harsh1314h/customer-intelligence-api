import pandas as pd

from app.schemas import CustomerFeatures


CUSTOMER_FEATURE_COLUMNS = [
    "recency_days",
    "frequency",
    "monetary",
    "tenure_days",
    "avg_order_value",
    "total_items",
    "unique_products",
]


COLUMN_ALIASES = {
    "invoice": "invoice_id",
    "invoiceno": "invoice_id",
    "invoice_no": "invoice_id",
    "stockcode": "stock_code",
    "stock_code": "stock_code",
    "description": "description",
    "quantity": "quantity",
    "invoicedate": "invoice_date",
    "invoice_date": "invoice_date",
    "price": "unit_price",
    "unitprice": "unit_price",
    "unit_price": "unit_price",
    "customer id": "customer_id",
    "customerid": "customer_id",
    "customer_id": "customer_id",
    "country": "country",
}


def customer_to_frame(customer: CustomerFeatures) -> pd.DataFrame:
    return pd.DataFrame([{column: getattr(customer, column) for column in CUSTOMER_FEATURE_COLUMNS}])


def normalize_transactions(raw_frame: pd.DataFrame) -> pd.DataFrame:
    normalized = raw_frame.rename(columns={column: _normalize_column_name(column) for column in raw_frame.columns})
    required_columns = {"invoice_id", "stock_code", "quantity", "invoice_date", "unit_price", "customer_id"}
    missing = sorted(required_columns - set(normalized.columns))
    if missing:
        raise ValueError(f"Missing required transaction columns: {', '.join(missing)}")

    normalized = normalized.copy()
    normalized["customer_id"] = normalized["customer_id"].map(_stringify_identifier)
    normalized["stock_code"] = normalized["stock_code"].map(_stringify_identifier)
    normalized["invoice_id"] = normalized["invoice_id"].map(_stringify_identifier)
    normalized["invoice_date"] = pd.to_datetime(normalized["invoice_date"], errors="coerce")
    normalized["quantity"] = pd.to_numeric(normalized["quantity"], errors="coerce")
    normalized["unit_price"] = pd.to_numeric(normalized["unit_price"], errors="coerce")

    if "description" not in normalized.columns:
        normalized["description"] = normalized["stock_code"]

    normalized = normalized.dropna(subset=["customer_id", "stock_code", "invoice_date", "quantity", "unit_price"])
    normalized = normalized[normalized["customer_id"].str.lower() != "nan"]
    normalized = normalized[~normalized["invoice_id"].str.startswith("C", na=False)]
    normalized = normalized[(normalized["quantity"] > 0) & (normalized["unit_price"] > 0)]
    normalized["line_total"] = normalized["quantity"] * normalized["unit_price"]

    return normalized


def build_customer_features(transactions: pd.DataFrame, as_of_date: pd.Timestamp | None = None) -> pd.DataFrame:
    if as_of_date is None:
        as_of_date = transactions["invoice_date"].max() + pd.Timedelta(days=1)

    order_totals = transactions.groupby(["customer_id", "invoice_id"], as_index=False)["line_total"].sum()
    customer_orders = order_totals.groupby("customer_id")
    customer_transactions = transactions.groupby("customer_id")

    features = pd.DataFrame(
        {
            "recency_days": (as_of_date - customer_transactions["invoice_date"].max()).dt.days,
            "frequency": customer_orders["invoice_id"].nunique(),
            "monetary": customer_transactions["line_total"].sum(),
            "tenure_days": (as_of_date - customer_transactions["invoice_date"].min()).dt.days,
            "avg_order_value": customer_orders["line_total"].mean(),
            "total_items": customer_transactions["quantity"].sum(),
            "unique_products": customer_transactions["stock_code"].nunique(),
        }
    )
    features = features.replace([float("inf"), float("-inf")], 0).fillna(0)
    return features.reset_index()


def build_time_based_churn_dataset(
    transactions: pd.DataFrame,
    prediction_window_days: int = 90,
    min_history_days: int = 90,
    max_snapshots: int = 8,
) -> pd.DataFrame:
    min_date = transactions["invoice_date"].min().normalize()
    max_date = transactions["invoice_date"].max().normalize()
    earliest_cutoff = min_date + pd.Timedelta(days=min_history_days)
    latest_cutoff = max_date - pd.Timedelta(days=prediction_window_days)

    if earliest_cutoff >= latest_cutoff:
        raise ValueError(
            "Not enough transaction history for time-based churn training. "
            "Reduce --min-history-days or --prediction-window-days."
        )

    snapshot_count = max(1, max_snapshots)
    cutoffs = pd.date_range(start=earliest_cutoff, end=latest_cutoff, periods=snapshot_count)
    snapshots = []

    for cutoff in cutoffs:
        cutoff_start = cutoff.normalize()
        cutoff_end = cutoff_start + pd.Timedelta(days=1)
        prediction_end = cutoff_end + pd.Timedelta(days=prediction_window_days)

        historical_transactions = transactions[transactions["invoice_date"] < cutoff_end]
        future_transactions = transactions[
            (transactions["invoice_date"] >= cutoff_end)
            & (transactions["invoice_date"] < prediction_end)
        ]

        if historical_transactions.empty:
            continue

        features = build_customer_features(historical_transactions, as_of_date=cutoff_end)
        returning_customers = set(future_transactions["customer_id"].unique())
        features["snapshot_date"] = cutoff_start.date().isoformat()
        features["churned"] = (~features["customer_id"].isin(returning_customers)).astype(int)
        snapshots.append(features)

    if not snapshots:
        raise ValueError("Could not create any time-based churn snapshots.")

    churn_dataset = pd.concat(snapshots, ignore_index=True)
    churn_dataset = churn_dataset.drop_duplicates(subset=["customer_id", "snapshot_date"])

    if churn_dataset["churned"].nunique() < 2:
        raise ValueError(
            "Time-based churn target contains only one class. "
            "Try changing --prediction-window-days or --churn-snapshots."
        )

    return churn_dataset


def _normalize_column_name(column: str) -> str:
    compact = str(column).strip().lower().replace(" ", "")
    spaced = str(column).strip().lower()
    snake = spaced.replace(" ", "_")
    return COLUMN_ALIASES.get(compact) or COLUMN_ALIASES.get(spaced) or COLUMN_ALIASES.get(snake) or snake


def _stringify_identifier(value) -> str:
    if pd.isna(value):
        return "nan"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()
