"""Application settings and configuration."""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "AI Task Management Agent"
    debug: bool = False
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/taskagent",
        description="PostgreSQL connection string"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/taskagent",
        description="Sync PostgreSQL connection string for migrations"
    )

    # Redis (for caching and Celery)
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Agent
    default_model: str = "gpt-4o"
    openai_api_key: str = ""
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0

    # Memory
    hot_memory_max_tokens: int = 1000
    warm_memory_max_items: int = 50
    context_window_turns: int = 10

    # Skills
    skill_timeout_ms: int = 30000
    max_concurrent_skills: int = 5

    # Approval
    auto_approve_internal: bool = True
    require_approval_external: bool = True

    # Sandbox (for future use)
    sandbox_enabled: bool = False
    sandbox_timeout_ms: int = 30000
    sandbox_memory_mb: int = 512

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
