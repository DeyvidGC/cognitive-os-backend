from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COGNITIVE_", env_file=".env", extra="ignore"
    )

    app_name: str = "Cognitive OS API"
    environment: Literal["local", "test", "staging", "production"] = "local"
