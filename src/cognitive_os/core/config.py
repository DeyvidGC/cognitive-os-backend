from typing import Literal
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COGNITIVE_", env_file=".env", extra="ignore"
    )

    app_name: str = "Cognitive OS API"
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY", repr=False)
    openai_model: str = Field(default="gpt-5.6-luna", validation_alias="OPENAI_MODEL", min_length=1)
    openai_embedding_model: str = Field(default="text-embedding-3-small", validation_alias="OPENAI_EMBEDDING_MODEL", min_length=1, max_length=100)
    openai_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL")
    worker_lease_seconds: int = Field(default=300, ge=180, le=3600)
    azure_storage_connection_string: SecretStr | None = Field(
        default=None, validation_alias="AZURE_STORAGE_CONNECTION_STRING", repr=False)
    azure_storage_container: str = Field(default="cognitive-recordings",
                                         validation_alias="AZURE_STORAGE_CONTAINER",
                                         pattern=r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
    recording_max_bytes: int = Field(default=262144000, ge=1024, le=1073741824)
    recording_max_seconds: int = Field(default=600, ge=1, le=600)
    recording_frame_interval_seconds: int = Field(default=10, ge=10, le=60)
    recording_lease_seconds: int = Field(default=900, ge=600, le=3600)
    cors_origins: list[str] = Field(default_factory=list)
    openai_transcription_model: str = Field(default="gpt-4o-mini-transcribe",
                                            validation_alias="OPENAI_TRANSCRIPTION_MODEL")
    agent_max_turns_per_session: int = Field(default=120, ge=1, le=1000)
    agent_min_interval_seconds: int = Field(default=3, ge=1, le=60)
    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: SecretStr | None = None
    registration_enabled: bool = False
    token_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    evidence_directory: Path = Path(".data/evidence")
    max_evidence_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
