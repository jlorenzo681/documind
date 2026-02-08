"""Configuration management for DocuMind using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    openai_api_key: SecretStr = Field(default=SecretStr(""))
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    cohere_api_key: SecretStr = Field(default=SecretStr(""))
    huggingface_api_key: SecretStr = Field(default=SecretStr(""))

    # Default models
    default_model: str = Field(default="gpt-4o")
    embedding_model: str = Field(default="text-embedding-3-large")

    # Model routing thresholds
    simple_model: str = Field(default="gpt-4o-mini")
    complex_model: str = Field(default="claude-3-5-sonnet-20241022")


class VectorStoreSettings(BaseSettings):
    """Vector store configuration."""

    model_config = SettingsConfigDict(env_prefix="QDRANT_", extra="ignore")

    url: str = Field(default="http://localhost:6333")
    api_key: SecretStr = Field(default=SecretStr(""))
    collection_name: str = Field(default="documents")
    embedding_dimension: int = Field(default=3072)  # text-embedding-3-large


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://documind:documind@localhost:5432/documind"
    )


class RedisSettings(BaseSettings):
    """Redis cache configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    redis_url: str = Field(default="redis://localhost:6379/0")
    cache_ttl: int = Field(default=3600)  # 1 hour


class S3Settings(BaseSettings):
    """S3/Object storage configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    aws_access_key_id: SecretStr = Field(default=SecretStr(""))
    aws_secret_access_key: SecretStr = Field(default=SecretStr(""))
    aws_region: str = Field(default="us-east-1")
    s3_bucket_name: str = Field(default="documind-documents")


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    langsmith_api_key: SecretStr = Field(default=SecretStr(""))
    langsmith_project: str = Field(default="documind")
    langsmith_tracing_v2: bool = Field(default=True)


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    environment: Literal["development", "staging", "production"] = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # Security
    secret_key: SecretStr = Field(default=SecretStr("change-me-in-production"))
    api_key_header: str = Field(default="X-API-Key")

    # Nested settings
    llm: LLMSettings = Field(default_factory=LLMSettings)
    vectorstore: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    s3: S3Settings = Field(default_factory=S3Settings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
