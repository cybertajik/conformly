"""Fail-closed admission for the local/disposable PostgreSQL integration harness.

This module intentionally uses only the standard library so its validation can be
exercised without importing the application, opening connections, or loading .env files.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit


class UnsafePostgresTargetError(ValueError):
    """A sanitized configuration/preflight failure; never include supplied values."""


@dataclass(frozen=True)
class PostgresTestTarget:
    database: str
    role: str
    host: str
    port: int
    password: str | None = field(repr=False)


def require_postgres_test_target(environment: Mapping[str, str]) -> PostgresTestTarget:
    """Validate explicit operator intent before an engine or connection is created."""
    raw_url = environment.get("CONFORMLY_TEST_APP_DATABASE_URL", "")
    if not raw_url:
        raise UnsafePostgresTargetError("Dedicated PostgreSQL test URL is required; no fallback.")
    if environment.get("CONFORMLY_TEST_DATABASE_DISPOSABLE") != "yes":
        raise UnsafePostgresTargetError("Explicit disposable-database acknowledgement is required.")
    database = environment.get("CONFORMLY_TEST_DATABASE_NAME", "")
    role = environment.get("CONFORMLY_TEST_DATABASE_ROLE", "")
    if not database or not role or database != database.strip() or role != role.strip():
        raise UnsafePostgresTargetError(
            "Exact expected test database and runtime role are required."
        )
    if any(key.startswith("PG") and value for key, value in environment.items()):
        raise UnsafePostgresTargetError("Inherited libpq environment overrides are not allowed.")
    if any(character.isspace() or ord(character) < 32 for character in raw_url):
        raise UnsafePostgresTargetError("Invalid PostgreSQL test URL.")
    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
        username = unquote(parsed.username or "", errors="strict")
        password = (
            unquote(parsed.password, errors="strict") if parsed.password is not None else None
        )
        database_name = unquote(parsed.path.removeprefix("/"), errors="strict")
    except (ValueError, UnicodeError):
        raise UnsafePostgresTargetError("Invalid PostgreSQL test URL.") from None
    if parsed.scheme != "postgresql+psycopg":
        raise UnsafePostgresTargetError("The PostgreSQL psycopg driver is required.")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or port is None or port == 0:
        raise UnsafePostgresTargetError("An explicit loopback host and port are required.")
    if parsed.query or parsed.fragment:
        raise UnsafePostgresTargetError("Test URL query overrides and fragments are not allowed.")
    if username != role or database_name != database or "/" in database_name:
        raise UnsafePostgresTargetError("Test URL does not match the expected database and role.")
    # Do not pass the raw URL to a second parser with potentially different rules.
    host = "::1" if parsed.hostname == "::1" else "127.0.0.1"
    return PostgresTestTarget(database, role, host, port, password)


def require_safe_runtime_identity(
    target: PostgresTestTarget, observed: Mapping[str, object]
) -> None:
    """Validate read-only preflight results before any fixture write is permitted."""
    if (
        observed.get("database_name") != target.database
        or observed.get("runtime_role") != target.role
        or observed.get("login_role") != target.role
    ):
        raise UnsafePostgresTargetError(
            "Connected database or role does not match the test target."
        )
    for flag in (
        "is_superuser",
        "bypasses_rls",
        "can_create_roles",
        "can_create_databases",
        "can_assume_privileged_role",
        "owns_database",
        "owns_relations",
    ):
        if observed.get(flag) is not False:
            raise UnsafePostgresTargetError(
                "Test runtime role is privileged or cannot be verified."
            )
    if observed.get("row_security") != "on":
        raise UnsafePostgresTargetError("Test runtime row security must be enabled.")


# Executed only after URL admission, in a read-only transaction. No fixture DML.
RUNTIME_IDENTITY_SQL = """
SELECT current_database() AS database_name,
       current_user AS runtime_role,
       session_user AS login_role,
       r.rolsuper AS is_superuser,
       r.rolbypassrls AS bypasses_rls,
       r.rolcreaterole AS can_create_roles,
       r.rolcreatedb AS can_create_databases,
       current_setting('row_security') AS row_security,
       EXISTS (
           SELECT 1 FROM pg_roles privileged
           WHERE (privileged.rolsuper OR privileged.rolbypassrls
                  OR privileged.rolcreaterole OR privileged.rolcreatedb)
             AND pg_has_role(current_user, privileged.oid, 'MEMBER')
       ) AS can_assume_privileged_role,
       pg_has_role(current_user, d.datdba, 'MEMBER') AS owns_database,
       EXISTS (
           SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
             AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
             AND pg_has_role(current_user, c.relowner, 'MEMBER')
       ) AS owns_relations
FROM pg_roles r CROSS JOIN pg_database d
WHERE r.rolname = current_user AND d.datname = current_database()
"""
