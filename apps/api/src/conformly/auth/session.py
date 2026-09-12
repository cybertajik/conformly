import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.auth.tokens import AuthenticationError, TokenClaims
from conformly.authz.policy import Principal
from conformly.identity.models import AuthSession, User, UserStatus


def hash_session_id(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def authenticate_claims(
    database: Session, claims: TokenClaims, *, now: datetime | None = None
) -> Principal:
    current_time = now or datetime.now(UTC)
    if claims.expires_at <= int(current_time.timestamp()):
        raise AuthenticationError("expired bearer token")

    auth_session = database.scalar(
        select(AuthSession)
        .join(AuthSession.user)
        .where(
            AuthSession.session_id_hash == hash_session_id(claims.session_id),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > current_time,
            User.oidc_issuer == claims.issuer,
            User.oidc_subject == claims.subject,
            User.status == UserStatus.ACTIVE,
        )
    )
    if auth_session is None:
        raise AuthenticationError("active application session not found")
    return Principal(
        user_id=auth_session.user_id,
        is_platform_admin=auth_session.user.is_platform_admin,
    )
