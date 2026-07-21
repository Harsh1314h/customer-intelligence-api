import pytest
import pandas as pd

from app.ml.features import build_time_based_churn_dataset, normalize_transactions


def test_time_based_churn_dataset_uses_future_return_behavior():
    raw_transactions = pd.DataFrame(
        [
            {
                "invoice": "1",
                "stockcode": "A",
                "description": "Alpha",
                "quantity": 2,
                "invoicedate": "2024-01-01",
                "price": 10,
                "customer_id": "C1",
            },
            {
                "invoice": "2",
                "stockcode": "B",
                "description": "Beta",
                "quantity": 1,
                "invoicedate": "2024-03-10",
                "price": 12,
                "customer_id": "C1",
            },
            {
                "invoice": "3",
                "stockcode": "A",
                "description": "Alpha",
                "quantity": 4,
                "invoicedate": "2024-01-10",
                "price": 10,
                "customer_id": "C2",
            },
            {
                "invoice": "4",
                "stockcode": "C",
                "description": "Gamma",
                "quantity": 1,
                "invoicedate": "2024-04-10",
                "price": 15,
                "customer_id": "C3",
            },
        ]
    )
    transactions = normalize_transactions(raw_transactions)

    churn_dataset = build_time_based_churn_dataset(
        transactions,
        prediction_window_days=45,
        min_history_days=30,
        max_snapshots=1,
    )

    c1_label = churn_dataset.loc[churn_dataset["customer_id"] == "C1", "churned"].iloc[0]
    c2_label = churn_dataset.loc[churn_dataset["customer_id"] == "C2", "churned"].iloc[0]
    assert c1_label == 0
    assert c2_label == 1


def test_normalize_transactions_accepts_common_column_aliases():
    raw_transactions = pd.DataFrame(
        [
            {
                "InvoiceNo": "1001",
                "Stock Code": "SKU-1",
                "Description": "Reusable bag",
                "Quantity": "2",
                "InvoiceDate": "2024-01-01",
                "UnitPrice": "25.5",
                "Customer ID": 17850.0,
            }
        ]
    )

    transactions = normalize_transactions(raw_transactions)

    assert list(transactions["invoice_id"]) == ["1001"]
    assert list(transactions["stock_code"]) == ["SKU-1"]
    assert list(transactions["customer_id"]) == ["17850"]
    assert float(transactions["line_total"].iloc[0]) == 51.0


def test_normalize_transactions_reports_missing_required_columns():
    raw_transactions = pd.DataFrame([{"invoice": "1001", "stockcode": "SKU-1"}])

    with pytest.raises(ValueError, match="Missing required transaction columns"):
        normalize_transactions(raw_transactions)
