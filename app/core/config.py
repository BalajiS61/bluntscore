"""Central application configuration, loaded from environment / .env file."""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BluntScore"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    database_url: str = "sqlite:///./bluntscore.db"
    api_prefix: str = "/api/v1"
    cors_origins: List[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read once per process)."""
    return Settings()
