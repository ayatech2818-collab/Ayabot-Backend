
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

    # Gemini Live
    gemini_live_model: str = "gemini-2.5-flash-native-audio-preview-09-2025"

    # Gemini Text Generation
    gemini_text_model: str = "gemini-3.8-flash"

    # Voice session authentication
    voice_session_secret: str
    voice_session_ttl_seconds: int = 60

    # Voice WebSocket lifecycle and protocol limits
    voice_auth_timeout_seconds: int = 10
    voice_session_idle_timeout_seconds: int = 120
    voice_session_max_duration_seconds: int = 1800
    voice_tool_timeout_seconds: int = 8
    voice_max_ticket_chars: int = 200
    voice_max_text_chars: int = 4096
    voice_max_audio_bytes: int = 32768
    voice_input_queue_max_messages: int = 50
    voice_output_queue_max_messages: int = 100
    voice_audio_activity_rms_threshold: int = 200

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
