
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AYABOT API"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    supabase_url: str
    supabase_auth_key: str
    supabase_service_role_key: str
    gemini_api_key: str
    database_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
