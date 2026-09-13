from typing import Literal

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
