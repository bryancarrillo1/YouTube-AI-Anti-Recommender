from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    youtube_api_key: str = Field(min_length=1)
    gemini_api_key: str = Field(min_length=1)
    gemini_model: str = "gemini-2.0-flash"
    default_language: str = "en"
    results_count: int = 5
    search_results_per_concept: int = 5
    exclude_same_channel: bool = False
    cache_ttl_seconds: int = 900
    request_timeout_seconds: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
