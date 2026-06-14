from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CI_",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    app_name: str = "Customer Intelligence API"
    model_dir: Path = Field(default=Path("models"))
    model_artifact_uri: str | None = Field(
        default=None,
        description="Optional artifact URI. Supports gs://bucket/prefix, s3://bucket/prefix, or a local directory.",
    )
    allow_demo_models: bool = Field(
        default=True,
        description="Create tiny local demo artifacts when real trained artifacts are missing.",
    )
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
