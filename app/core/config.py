"""Central application configuration, loaded from environment / .env file."""
from functools import lru_cache
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BluntScore"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    database_url: str = "sqlite:///./bluntscore.db"
    api_prefix: str = "/api/v1"
    cors_origins: List[str] = ["*"]

    # NLP: VADER compound score thresholds (standard values from the VADER paper)
    sentiment_positive_threshold: float = 0.05
    sentiment_negative_threshold: float = -0.05

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _check_thresholds(self) -> "Settings":
        if not (-1 < self.sentiment_negative_threshold < self.sentiment_positive_threshold < 1):
            raise ValueError("Require -1 < negative_threshold < positive_threshold < 1")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read once per process)."""
    return Settings()
