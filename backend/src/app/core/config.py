"""Application settings loaded from environment variables via pydantic-settings."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ─── Platform Database ───
    DATABASE_URL: str

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # ─── Redis ───
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── Security ───
    PLATFORM_ENCRYPTION_KEY: str  # base64-encoded 32-byte key for AES-256-GCM
    ALLOWED_ORIGINS: str = "http://localhost:3000"  # comma-separated

    # ─── Admin User ───
    ADMIN_USERNAME: str = "admin"
    ADMIN_DISPLAY_NAME: str = "Administrator"
    ADMIN_PASSWORD: str = ""
    ADMIN_API_KEY: str = ""  # Simple admin auth for Phase 1

    # ─── LLM Provider ───
    LLM_PROVIDER: str = "ollama"  # anthropic | openai | gemini | ollama
    LLM_MODEL_NAME: str = ""  # overrides default model per provider
    LLM_API_KEY_ANTHROPIC: str = ""
    LLM_API_KEY_OPENAI: str = ""
    LLM_API_KEY_GEMINI: str = ""
    LLM_BASE_URL_OLLAMA: str = "http://localhost:11434"

    # ─── Source Database ───
    SOURCE_DB_NAME: str = "source_analytics"
    SOURCE_DB_HOST: str = "localhost"
    SOURCE_DB_PORT: int = 5434
    SOURCE_DB_USER: str = "pagila_user"
    SOURCE_DB_PASSWORD: str = "pagila_dev_pwd"
    SOURCE_DB_SSL_MODE: str = "disable"

    # ─── Application ───
    QUERY_TIMEOUT_SECONDS: int = 30
    MAX_QUESTION_LENGTH: int = 2000
    SESSION_IDLE_TIMEOUT_HOURS: int = 8
    SCHEMA_CACHE_TTL_SECONDS: int = 300
    MAX_SCHEMA_TOKENS: int = 60000

    # ─── Logging ───
    LOG_LEVEL: str = "INFO"

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def validate_allowed_origins(cls, v: str) -> str:
        """Ensure ALLOWED_ORIGINS is non-empty."""
        if not v.strip():
            raise ValueError("ALLOWED_ORIGINS must not be empty")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure DATABASE_URL uses asyncpg driver."""
        if not v:
            raise ValueError("DATABASE_URL is required")
        return v

    @field_validator("PLATFORM_ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Ensure PLATFORM_ENCRYPTION_KEY is provided."""
        if not v.strip():
            raise ValueError("PLATFORM_ENCRYPTION_KEY is required")
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse ALLOWED_ORIGINS as a list."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()
