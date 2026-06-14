from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.ml.features import customer_to_frame
from app.ml.registry import ModelRegistry
from app.schemas import (
    ChurnRequest,
    ChurnResponse,
    HealthResponse,
    RecommendationRequest,
    RecommendationResponse,
    SegmentRequest,
    SegmentResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    registry = ModelRegistry(settings)
    registry.load()
    app.state.model_registry = registry
    yield


app = FastAPI(
    title="Customer Intelligence API",
    description="Churn prediction, customer segmentation, and product recommendations for e-commerce.",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_registry(request: Request) -> ModelRegistry:
    registry = getattr(request.app.state, "model_registry", None)
    if registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet.",
        )
    return registry


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health(registry: ModelRegistry = Depends(get_registry)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        models_loaded=registry.models_loaded,
        model_version=registry.model_version,
        demo_mode=registry.demo_mode,
        artifact_uri=registry.artifact_uri,
    )


@app.post("/predict/churn", response_model=ChurnResponse, tags=["churn"])
def predict_churn(
    payload: ChurnRequest,
    registry: ModelRegistry = Depends(get_registry),
) -> ChurnResponse:
    frame = customer_to_frame(payload.customer)
    probability = float(registry.churn_model.predict_proba(frame)[0, 1])

    if probability >= 0.65:
        risk_band = "high"
    elif probability >= 0.35:
        risk_band = "medium"
    else:
        risk_band = "low"

    return ChurnResponse(
        customer_id=payload.customer.customer_id,
        churn_probability=round(probability, 4),
        risk_band=risk_band,
        model_version=registry.model_version,
    )


@app.post("/segment/customer", response_model=SegmentResponse, tags=["segmentation"])
def segment_customer(
    payload: SegmentRequest,
    registry: ModelRegistry = Depends(get_registry),
) -> SegmentResponse:
    frame = customer_to_frame(payload.customer)
    prediction = registry.segment_model.predict_customer(frame)

    return SegmentResponse(
        customer_id=payload.customer.customer_id,
        segment=prediction.segment,
        cluster_id=prediction.cluster_id,
        distance_to_centroid=round(prediction.distance_to_centroid, 4),
        model_version=registry.model_version,
    )


@app.post("/recommend", response_model=RecommendationResponse, tags=["recommendations"])
def recommend(
    payload: RecommendationRequest,
    registry: ModelRegistry = Depends(get_registry),
) -> RecommendationResponse:
    recommendations = registry.recommender.recommend(
        customer_id=payload.customer_id,
        recent_product_ids=payload.recent_product_ids,
        top_n=payload.top_n,
        include_seen=payload.include_seen,
    )

    return RecommendationResponse(
        customer_id=payload.customer_id,
        recommendations=recommendations,
        model_version=registry.model_version,
    )
