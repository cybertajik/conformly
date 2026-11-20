from functools import lru_cache
from urllib.parse import urlparse

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
    enable_catalog_demo: bool = False
    enable_customer_demo: bool = False
    enable_customer_preaudit: bool = False
    enable_customer_readiness_verification: bool = False
    workforce_oidc_issuer: str | None = None
    workforce_oidc_audience: str | None = None
    workforce_oidc_jwks_url: str | None = None
    catalog_demo_database_url: str | None = Field(default=None, repr=False)
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


def _is_safe_url(url_str: str) -> bool:
    """Validate that URL uses HTTPS or explicit permitted loopback."""
    parsed = urlparse(url_str)
    if parsed.scheme == "https":
        return True
    if parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1"):
        return True
    return False


def validate_catalog_demo_settings(settings: Settings) -> None:
    """Validate catalog demo configuration when enabled before activation."""
    if not settings.enable_catalog_demo:
        return

    # Dedicated PostgreSQL DSN required; fail closed without app/owner/default/sqlite fallback
    if not settings.catalog_demo_database_url:
        raise ValueError(
            "CONFORMLY_CATALOG_DEMO_DATABASE_URL must be configured when catalog demo is enabled"
        )

    if not (
        settings.catalog_demo_database_url.startswith("postgresql://")
        or settings.catalog_demo_database_url.startswith("postgresql+")
    ):
        raise ValueError(
            "CONFORMLY_CATALOG_DEMO_DATABASE_URL must be a dedicated PostgreSQL DSN (SQLite or other schemes not permitted)"
        )

    # Workforce OIDC trust values required
    if not settings.workforce_oidc_issuer:
        raise ValueError(
            "CONFORMLY_WORKFORCE_OIDC_ISSUER must be configured when catalog demo is enabled"
        )
    if not settings.workforce_oidc_audience:
        raise ValueError(
            "CONFORMLY_WORKFORCE_OIDC_AUDIENCE must be configured when catalog demo is enabled"
        )
    if not settings.workforce_oidc_jwks_url:
        raise ValueError(
            "CONFORMLY_WORKFORCE_OIDC_JWKS_URL must be configured when catalog demo is enabled"
        )

    # Safe HTTPS or explicit loopback endpoints
    if not _is_safe_url(settings.workforce_oidc_issuer):
        raise ValueError("CONFORMLY_WORKFORCE_OIDC_ISSUER must use HTTPS or permitted loopback")
    if not _is_safe_url(settings.workforce_oidc_jwks_url):
        raise ValueError("CONFORMLY_WORKFORCE_OIDC_JWKS_URL must use HTTPS or permitted loopback")

    # Normalized workforce issuer must be distinct from customer issuer
    if settings.oidc_issuer:
        cust_norm = settings.oidc_issuer.rstrip("/")
        work_norm = settings.workforce_oidc_issuer.rstrip("/")
        if cust_norm == work_norm:
            raise ValueError(
                "CONFORMLY_WORKFORCE_OIDC_ISSUER must be distinct from customer OIDC issuer (CONFORMLY_OIDC_ISSUER)"
            )


def validate_customer_demo_settings(settings: Settings) -> None:
    """Validate customer demo configuration when enabled before activation."""
    if not settings.enable_customer_demo:
        return
    if settings.environment not in ("local", "development", "test"):
        raise ValueError(
            "CONFORMLY_ENABLE_CUSTOMER_DEMO can only be enabled in local, development, or test environments"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
