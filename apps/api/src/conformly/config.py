from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded exclusively from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="CONFORMLY_",
        env_file=".env",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+psycopg://conformly:conformly@localhost:5432/conformly",
        repr=False,
    )
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    local_keks: dict[str, str] = Field(default_factory=dict, repr=False)
    active_kek_version: str | None = None
    kms_provider: str = "local"
    vault_endpoint: str | None = None
    vault_token: str | None = Field(default=None, repr=False)
    vault_transit_mount: str = "transit"
    vault_key_name: str = "conformly-master-key"
    enable_whistleblower_addon: bool = False
    invitation_token_pepper: str | None = Field(default=None, repr=False)
    storage_backend: str = "memory"
    storage_local_dir: str = ".conformly_storage"
    storage_endpoint: str | None = None
    storage_bucket: str = "conformly-files"
    storage_access_key: str | None = None
    storage_secret_key: str | None = Field(default=None, repr=False)
    storage_region: str = "us-east-1"
    max_file_size_bytes: int = 25 * 1024 * 1024
    redis_url: str = "redis://localhost:6379/0"
    notification_provider: str = "smtp"
    clamav_host: str | None = None
    clamav_port: int = 3310
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = Field(default=None, repr=False)
    smtp_use_tls: bool = False
    smtp_from_email: str = "no-reply@conformly.de"
    webhook_timeout_seconds: float = 10.0
    worker_poll_interval_seconds: float = 5.0
    worker_compliance_interval_seconds: int = 3600
    worker_batch_size: int = 25


@lru_cache
def get_settings() -> Settings:
    return Settings()
