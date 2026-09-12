from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.auth.lifecycle import SessionLifecycleError, issue_auth_session
from conformly.auth.session import hash_session_id
from conformly.auth.tokens import TokenClaims
from conformly.identity.models import AuthSession, User, UserStatus, normalize_email_address


class IdentityBootstrapError(Exception):
    """Raised when verified OIDC claims cannot establish an application session."""


def bootstrap_identity_session(
    database: Session,
    claims: TokenClaims,
    *,
    request_id: str,
    now: datetime | None = None,
) -> tuple[User, AuthSession]:
    current_time = now or datetime.now(UTC)
    if claims.email is None or not claims.email_verified:
        raise IdentityBootstrapError("verified identity is missing email")
    try:
        email = normalize_email_address(claims.email)
    except ValueError as error:
        raise IdentityBootstrapError("verified identity has invalid email") from error

    user = database.scalar(
        select(User).where(
            User.oidc_issuer == claims.issuer,
            User.oidc_subject == claims.subject,
        )
    )
    if user is None:
        email_owner = database.scalar(select(User).where(User.email == email))
        if email_owner is not None:
            raise IdentityBootstrapError("verified identity cannot be linked automatically")
        user = User(
            oidc_issuer=claims.issuer,
            oidc_subject=claims.subject,
            email=email,
            display_name=(claims.display_name or email).strip()[:200],
        )
        database.add(user)
        database.flush()
    elif user.status is not UserStatus.ACTIVE or user.email != email:
        raise IdentityBootstrapError("verified identity cannot start a session")

    existing = database.scalar(
        select(AuthSession).where(AuthSession.session_id_hash == hash_session_id(claims.session_id))
    )
    if existing is not None:
        if existing.user_id != user.id or existing.revoked_at is not None:
            raise IdentityBootstrapError("verified identity cannot start a session")
        return user, existing

    try:
        auth_session = issue_auth_session(
            database,
            user=user,
            session_id=claims.session_id,
            expires_at=datetime.fromtimestamp(claims.expires_at, UTC),
            request_id=request_id,
            now=current_time,
        )
    except SessionLifecycleError as error:
        raise IdentityBootstrapError("verified identity cannot start a session") from error
    return user, auth_session
