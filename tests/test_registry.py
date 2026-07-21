import json

import pytest

from app.config import Settings
from app.ml.registry import ModelRegistry


def test_registry_reads_metadata(tmp_path):
    metadata = {"model_version": "test-version", "demo_mode": False}
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (model_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    registry = ModelRegistry(Settings(model_dir=model_dir, allow_demo_models=False))

    assert registry._load_metadata() == metadata


def test_registry_errors_when_artifacts_missing_and_demo_disabled(tmp_path):
    registry = ModelRegistry(Settings(model_dir=tmp_path / "models", allow_demo_models=False))

    with pytest.raises(RuntimeError, match="Missing model artifacts"):
        registry.load()
