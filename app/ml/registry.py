import json
from pathlib import Path
from typing import Any

import joblib

from app.config import Settings
from app.ml.artifacts import sync_artifacts
from app.ml.demo import create_demo_artifacts


REQUIRED_ARTIFACTS = {
    "churn": "churn_model.joblib",
    "segment": "segment_model.joblib",
    "recommender": "recommender.joblib",
}


class ModelRegistry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_dir = Path(settings.model_dir)
        self.artifact_uri = settings.model_artifact_uri
        self.churn_model: Any | None = None
        self.segment_model: Any | None = None
        self.recommender: Any | None = None
        self.metadata: dict[str, Any] = {}

    @property
    def model_version(self) -> str:
        return str(self.metadata.get("model_version", "unknown"))

    @property
    def demo_mode(self) -> bool:
        return bool(self.metadata.get("demo_mode", False))

    @property
    def models_loaded(self) -> dict[str, bool]:
        return {
            "churn": self.churn_model is not None,
            "segment": self.segment_model is not None,
            "recommender": self.recommender is not None,
        }

    def load(self) -> None:
        self.model_dir.mkdir(parents=True, exist_ok=True)
        sync_artifacts(self.artifact_uri, self.model_dir)

        missing = self._missing_artifacts()
        if missing and self.settings.allow_demo_models:
            create_demo_artifacts(self.model_dir)
            missing = self._missing_artifacts()

        if missing:
            missing_list = ", ".join(missing)
            raise RuntimeError(
                f"Missing model artifacts: {missing_list}. "
                "Run `python -m scripts.train --transactions <dataset>` or set CI_MODEL_ARTIFACT_URI."
            )

        self.churn_model = joblib.load(self.model_dir / REQUIRED_ARTIFACTS["churn"])
        self.segment_model = joblib.load(self.model_dir / REQUIRED_ARTIFACTS["segment"])
        self.recommender = joblib.load(self.model_dir / REQUIRED_ARTIFACTS["recommender"])
        self.metadata = self._load_metadata()

    def _missing_artifacts(self) -> list[str]:
        return [filename for filename in REQUIRED_ARTIFACTS.values() if not (self.model_dir / filename).exists()]

    def _load_metadata(self) -> dict[str, Any]:
        metadata_path = self.model_dir / "metadata.json"
        if not metadata_path.exists():
            return {"model_version": "unknown", "demo_mode": False}
        return json.loads(metadata_path.read_text(encoding="utf-8"))
