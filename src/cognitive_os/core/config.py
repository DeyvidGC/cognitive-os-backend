from typing import Literal
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COGNITIVE_", env_file=".env", extra="ignore"
    )

    app_name: str = "Cognitive OS API"
    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: SecretStr | None = None
    registration_enabled: bool = False
    token_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    evidence_directory: Path = Path(".data/evidence")
    max_evidence_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
