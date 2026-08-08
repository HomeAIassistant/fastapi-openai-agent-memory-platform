"""Environment-backed application settings and startup validation."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EmbeddingProviderName = Literal["deterministic", "openai"]


class Settings(BaseSettings):
    """Validated process configuration loaded from environment variables."""

    app_name: str = "Agent Memory Platform"
    app_version: str = "0.1.0"
    app_env: str = "local"
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    memory_api_token: SecretStr = Field(min_length=32)
    cors_origins: str = ""

    database_url: str = Field(min_length=1)

    embedding_provider: EmbeddingProviderName = "deterministic"
    embedding_model: str = Field(default="text-embedding-3-small", min_length=1)
    embedding_dimensions: int = Field(default=1536, gt=0, le=4096)
    openai_api_key: SecretStr | None = None

    policy_path: Path = Path("config/policy.yaml")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("memory_api_token")
    @classmethod
    def reject_placeholder_token(cls, value: SecretStr) -> SecretStr:
        """Reject the documented placeholder bearer token."""

        if value.get_secret_value() == "GENERATE_ME":
            raise ValueError("MEMORY_API_TOKEN is still set to GENERATE_ME")
        return value

    @field_validator("database_url")
    @classmethod
    def reject_placeholder_database_url(cls, value: str) -> str:
        """Reject an unresolved Compose credential placeholder."""

        if "GENERATE_ME" in value:
            raise ValueError("DATABASE_URL still contains an unresolved GENERATE_ME")
        return value

    @model_validator(mode="after")
    def require_openai_key_for_openai_provider(self) -> "Settings":
        """Require an API key only when the OpenAI embedding provider is selected."""

        if self.embedding_provider == "openai" and self.openai_api_key is None:
            raise ValueError(
                "OPENAI_API_KEY is required when MEMORY_EMBEDDING_PROVIDER=openai"
            )
        return self

    @property
    def parsed_cors_origins(self) -> list[str]:
        """Return non-empty, comma-separated CORS origins."""

        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


def get_settings() -> Settings:
    """Construct settings from the process environment on demand."""

    return Settings()  # type: ignore[call-arg]
