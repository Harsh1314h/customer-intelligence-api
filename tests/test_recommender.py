import pandas as pd

from app.ml.recommender import CollaborativeRecommender


def test_recommender_falls_back_to_popular_items_for_unknown_customer():
    transactions = pd.DataFrame(
        [
            {"customer_id": "C1", "stock_code": "A", "description": "Alpha", "quantity": 5},
            {"customer_id": "C2", "stock_code": "A", "description": "Alpha", "quantity": 4},
            {"customer_id": "C3", "stock_code": "B", "description": "Beta", "quantity": 2},
            {"customer_id": "C4", "stock_code": "C", "description": "Gamma", "quantity": 1},
        ]
    )
    recommender = CollaborativeRecommender.fit(transactions, n_components=2)

    recommendations = recommender.recommend(
        customer_id="unknown",
        recent_product_ids=[],
        top_n=2,
    )

    assert [recommendation.product_id for recommendation in recommendations] == ["A", "B"]
