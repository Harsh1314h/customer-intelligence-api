from pydantic import BaseModel, ConfigDict, Field


class CustomerFeatures(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_id": "17850",
                "recency_days": 22,
                "frequency": 18,
                "monetary": 3420.5,
                "tenure_days": 340,
                "avg_order_value": 190.03,
                "total_items": 620,
                "unique_products": 47,
            }
        }
    )

    customer_id: str | None = Field(default=None)
    recency_days: float = Field(..., ge=0)
    frequency: float = Field(..., ge=0)
    monetary: float = Field(..., ge=0)
    tenure_days: float = Field(..., ge=0)
    avg_order_value: float = Field(..., ge=0)
    total_items: float = Field(..., ge=0)
    unique_products: float = Field(..., ge=0)


class ChurnRequest(BaseModel):
    customer: CustomerFeatures


class ChurnResponse(BaseModel):
    customer_id: str | None
    churn_probability: float = Field(..., ge=0, le=1)
    risk_band: str
    model_version: str


class SegmentRequest(BaseModel):
    customer: CustomerFeatures


class SegmentResponse(BaseModel):
    customer_id: str | None
    segment: str
    cluster_id: int
    distance_to_centroid: float
    model_version: str


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_id": "17850",
                "recent_product_ids": ["85123A", "71053"],
                "top_n": 5,
                "include_seen": False,
            }
        }
    )

    customer_id: str | None = None
    recent_product_ids: list[str] = Field(default_factory=list)
    top_n: int = Field(default=5, ge=1, le=50)
    include_seen: bool = False


class ProductRecommendation(BaseModel):
    product_id: str
    score: float
    name: str | None = None


class RecommendationResponse(BaseModel):
    customer_id: str | None
    recommendations: list[ProductRecommendation]
    model_version: str


class HealthResponse(BaseModel):
    status: str
    models_loaded: dict[str, bool]
    model_version: str
    demo_mode: bool
    artifact_uri: str | None
