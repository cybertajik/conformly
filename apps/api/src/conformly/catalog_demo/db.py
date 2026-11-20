"""Database engine, role boundaries, and application audit adapter for catalog demo."""

import logging
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.catalog_v2.audit import DeniedAuditSink
from conformly.config import get_settings, validate_catalog_demo_settings
from conformly.db.session import SessionLocal

logger = logging.getLogger(__name__)


class AuditPersistenceError(HTTPException):
    def __init__(
        self, detail: str = "Catalog service or audit infrastructure temporarily unavailable"
    ) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


@lru_cache
def get_catalog_engine() -> Engine:
    """Create or return cached dedicated read engine for catalog queries."""
    settings = get_settings()
    validate_catalog_demo_settings(settings)

    url = settings.catalog_demo_database_url
    if not url:
        raise RuntimeError("Dedicated catalog demo database URL is not configured")

    engine = create_engine(
        url,
        hide_parameters=True,
        pool_pre_ping=True,
    )
    return engine


class AppAuditDeniedSink(DeniedAuditSink):
    """Sanitized application-level audit sink for catalog denials using the app DB boundary."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory or SessionLocal
        self.last_error: Exception | None = None

    def record_denial(
        self,
        actor_id: UUID,
        operation: str,
        reason_code: str,
        request_key: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> None:
        sanitized_reason = str(reason_code)[:128]
        sanitized_operation = str(operation)[:64]
        # Validate and bound request key (correlation identifier)
        raw_key = str(request_key).strip()[:64] if request_key else ""
        sanitized_key = (
            raw_key
            if raw_key.replace("-", "").replace("_", "").isalnum()
            else "sanitized-correlation-id"
        )
        sanitized_res_type = str(resource_type)[:64] if resource_type else "catalog_demo"

        try:
            with self._session_factory() as app_db:
                record_audit_event(
                    app_db,
                    tenant_id=None,
                    actor_type=AuditActorType.USER,
                    actor_id=actor_id,
                    action=f"catalog.{sanitized_operation}",
                    resource_type=sanitized_res_type,
                    resource_id=str(resource_id) if resource_id else "catalog-demo-v1",
                    request_id=sanitized_key,
                    outcome=AuditOutcome.DENIED,
                    metadata={"reason": sanitized_reason},
                    occurred_at=datetime.now(UTC),
                )
                app_db.commit()
        except Exception as exc:
            self.last_error = exc
            logger.error(
                "Audit event persistence failed on application database: %s", exc.__class__.__name__
            )
            raise AuditPersistenceError("Audit event persistence failed") from None


def get_catalog_db() -> Generator[Session, None, None]:
    """Dependency yielding a read-only database session under conformly_catalog role."""
    engine = get_catalog_engine()
    with engine.connect() as connection:
        if connection.dialect.name == "postgresql":
            # 1. Verify actual role is conformly_catalog and has no elevated or bypass privileges
            role_row = connection.execute(
                text(
                    "SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            ).fetchone()
            if not role_row or role_row[0] != "conformly_catalog":
                user_found = role_row[0] if role_row else "unknown"
                raise RuntimeError(
                    f"Catalog DB session boundary violation: expected role 'conformly_catalog', got '{user_found}'"
                )
            if role_row[1] or role_row[2] or role_row[3] or role_row[4]:
                raise RuntimeError(
                    f"Catalog role '{role_row[0]}' possesses elevated privileges (rolsuper={role_row[1]}, rolbypassrls={role_row[2]})"
                )

            # Check membership in owner/superuser roles or assumable privilege
            elevated_check = connection.execute(
                text(
                    """
                    SELECT (
                        EXISTS (
                            SELECT 1 FROM pg_roles privileged
                            WHERE (privileged.rolsuper OR privileged.rolbypassrls
                                   OR privileged.rolcreaterole OR privileged.rolcreatedb)
                              AND pg_has_role(current_user, privileged.oid, 'MEMBER')
                        ) OR pg_has_role(current_user, d.datdba, 'MEMBER')
                    )
                    FROM pg_database d
                    WHERE d.datname = current_database()
                    """
                )
            ).scalar()
            if elevated_check:
                raise RuntimeError(
                    "Catalog role unexpectedly has membership in elevated/owner role"
                )

            # End check transaction so SET TRANSACTION ISOLATION LEVEL is first in new transaction
            connection.rollback()
            connection.execute(text("SET TRANSACTION READ ONLY ISOLATION LEVEL REPEATABLE READ"))

        with Session(bind=connection) as session:
            yield session
