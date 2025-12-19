from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    app_host: str = Field("0.0.0.0", env="APP_HOST")
    app_port: int = Field(8000, env="APP_PORT")
    log_level: str = Field("info", env="LOG_LEVEL")
    poll_interval_seconds: int = Field(3, env="POLL_INTERVAL_SECONDS")

    model_name: str = Field("gpt-4", env="MODEL_NAME")
    model_temperature: float = Field(0.7, env="MODEL_TEMPERATURE")
    model_max_tokens: Optional[int] = Field(None, env="MODEL_MAX_TOKENS")
    soft_qc_retries: int = Field(2, env="SOFT_QC_RETRIES")

    # WordPress defaults（入力優先、ここはデフォルト値）
    wp_default_url: str = Field("", env="WP_DEFAULT_URL")
    wp_default_username: str = Field("", env="WP_DEFAULT_USERNAME")
    wp_default_app_password: str = Field("", env="WP_DEFAULT_APP_PASSWORD")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
