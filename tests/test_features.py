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
