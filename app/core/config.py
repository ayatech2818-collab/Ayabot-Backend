
from functools import lru_cache

from pydantic import Field
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

    # Gemini Live
    gemini_live_model: str = "gemini-2.5-flash-native-audio-preview-09-2025"

    # Gemini Text Generation
    gemini_text_model: str = "gemini-3.8-flash"

    # Voice session authentication
    voice_session_secret: str
    voice_session_ttl_seconds: int = Field(default=60, gt=0)

    # Voice WebSocket lifecycle and protocol limits
    voice_auth_timeout_seconds: int = Field(default=10, gt=0)
    voice_session_idle_timeout_seconds: int = Field(default=120, gt=0)
    voice_session_max_duration_seconds: int = Field(default=1800, gt=0)
    voice_tool_timeout_seconds: int = Field(default=8, gt=0)
    voice_max_ticket_chars: int = Field(default=200, gt=0)
    voice_max_text_chars: int = Field(default=4096, gt=0)
    voice_max_audio_bytes: int = Field(default=32768, gt=0)
    voice_input_queue_max_messages: int = Field(default=50, gt=0)
    voice_output_queue_max_messages: int = Field(default=100, gt=0)
    voice_audio_activity_rms_threshold: int = Field(default=200, ge=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
