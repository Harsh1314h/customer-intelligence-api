import importlib
from contextlib import contextmanager

from fastapi.testclient import TestClient


def test_health_endpoint_loads_demo_models(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch) as client:
        response = client.get("/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["models_loaded"] == {"churn": True, "segment": True, "recommender": True}
        assert payload["demo_mode"] is True


def test_churn_prediction_contract(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch) as client:
        response = client.post("/predict/churn", json={"customer": sample_customer()})

        assert response.status_code == 200
        payload = response.json()
        assert 0 <= payload["churn_probability"] <= 1
        assert payload["risk_band"] in {"low", "medium", "high"}


def test_customer_segmentation_contract(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch) as client:
        response = client.post("/segment/customer", json={"customer": sample_customer()})

        assert response.status_code == 200
        payload = response.json()
        assert payload["segment"] in {"high-value", "at-risk", "new", "dormant"}
        assert isinstance(payload["cluster_id"], int)


def test_recommendation_contract(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch) as client:
        response = client.post(
            "/recommend",
            json={"customer_id": "C0001", "recent_product_ids": ["P0001"], "top_n": 3},
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["recommendations"]) == 3
        assert {"product_id", "score", "name"} <= set(payload["recommendations"][0])


def test_churn_rejects_negative_customer_features(tmp_path, monkeypatch):
    customer = sample_customer()
    customer["recency_days"] = -1
    with build_client(tmp_path, monkeypatch) as client:
        response = client.post("/predict/churn", json={"customer": customer})

        assert response.status_code == 422


def test_recommend_rejects_unbounded_top_n(tmp_path, monkeypatch):
    with build_client(tmp_path, monkeypatch) as client:
        response = client.post("/recommend", json={"top_n": 500})

        assert response.status_code == 422


@contextmanager
def build_client(tmp_path, monkeypatch):
    monkeypatch.setenv("CI_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("CI_ALLOW_DEMO_MODELS", "true")
    import app.config
    import app.main

    app.config.get_settings.cache_clear()
    importlib.reload(app.main)
    with TestClient(app.main.app) as client:
        yield client


def sample_customer() -> dict:
    return {
        "customer_id": "C0001",
        "recency_days": 28,
        "frequency": 12,
        "monetary": 1850.75,
        "tenure_days": 420,
        "avg_order_value": 154.2,
        "total_items": 330,
        "unique_products": 32,
    }
