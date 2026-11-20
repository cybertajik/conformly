"""Workforce OIDC/MFA authentication, staff session lifecycle, and actor context."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Protocol

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from jwt import PyJWKClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from conformly.auth.bootstrap import IdentityBootstrapError, bootstrap_identity_session
from conformly.auth.lifecycle import SessionLifecycleError, revoke_own_auth_session
from conformly.auth.session import authenticate_claims, hash_session_id
from conformly.auth.tokens import AuthenticationError, TokenClaims
from conformly.catalog_demo.schemas import CatalogDemoSessionResponse
from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
)
from conformly.config import get_settings
from conformly.db.session import get_db
from conformly.identity.models import AuthSession, User, UserStatus, normalize_email_address

logger = logging.getLogger(__name__)

MFA_AMR_ALLOWED = frozenset({"otp", "totp", "mfa", "webauthn"})
MFA_ACR_ALLOWED = frozenset({"loa2", "2", "mfa"})
ALLOWED_ALGORITHMS = ["RS256", "ES256"]


class WorkforceAuthError(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_401_UNAUTHORIZED) -> None:
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


@dataclass(frozen=True, slots=True)
class WorkforceClaims:
    issuer: str
    subject: str
    session_id: str
    expires_at: int
    auth_time: int
    email: str
    email_verified: bool
    display_name: str | None
    amr: list[str]
    acr: str | None
    mfa_verified: bool


class WorkforceTokenVerifier(Protocol):
    def verify(self, token: str) -> WorkforceClaims: ...


def parse_workforce_payload(
    payload: dict[str, Any],
    expected_issuer: str | None = None,
    expected_audience: str | None = None,
) -> WorkforceClaims:
    """Strictly validate typed claims, auth_time, and signed MFA proof."""
    # Check issuer
    iss = payload.get("iss")
    if not isinstance(iss, str) or not iss.strip():
        raise WorkforceAuthError("Missing or invalid iss claim")
    if expected_issuer is not None and iss.rstrip("/") != expected_issuer.rstrip("/"):
        raise WorkforceAuthError("Untrusted workforce token issuer")

    # Check subject
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise WorkforceAuthError("Missing or invalid sub claim")

    # Check session_id (sid)
    sid = payload.get("sid")
    if not isinstance(sid, str) or not sid.strip():
        raise WorkforceAuthError("Missing or invalid signed sid claim")

    # Check audience
    aud = payload.get("aud")
    if expected_audience is not None:
        if isinstance(aud, list):
            if expected_audience not in aud:
                raise WorkforceAuthError("Untrusted workforce token audience")
        elif aud != expected_audience:
            raise WorkforceAuthError("Untrusted workforce token audience")

    # Check exp
    exp = payload.get("exp")
    if not isinstance(exp, int) or isinstance(exp, bool):
        raise WorkforceAuthError("Missing or invalid integer exp claim")

    # Check auth_time: must be integer and strictly not bool
    raw_auth_time = payload.get("auth_time")
    if not isinstance(raw_auth_time, int) or isinstance(raw_auth_time, bool):
        raise WorkforceAuthError("Missing or invalid integer auth_time claim in token")

    # Check email and email_verified
    email = payload.get("email")
    if not isinstance(email, str) or not email.strip():
        raise WorkforceAuthError("Missing or invalid email claim")
    if payload.get("email_verified") is not True:
        raise WorkforceAuthError("Workforce email must be verified")

    # Check MFA proof: recognized AMR or ACR required; bare mfa_verified flag rejected
    raw_amr = payload.get("amr") or []
    amr_list = (
        [str(x) for x in raw_amr]
        if isinstance(raw_amr, list)
        else ([str(raw_amr)] if isinstance(raw_amr, str) else [])
    )
    acr_val = str(payload["acr"]) if payload.get("acr") else None

    mfa_ok = any(m in MFA_AMR_ALLOWED for m in amr_list) or (acr_val in MFA_ACR_ALLOWED)
    if not mfa_ok:
        raise WorkforceAuthError("Signed MFA proof (AMR/ACR) required for staff catalog demo")

    display_name = str(payload["name"]).strip() if payload.get("name") else None

    return WorkforceClaims(
        issuer=iss,
        subject=sub,
        session_id=sid,
        expires_at=exp,
        auth_time=raw_auth_time,
        email=email.strip(),
        email_verified=True,
        display_name=display_name,
        amr=amr_list,
        acr=acr_val,
        mfa_verified=True,
    )


class DefaultWorkforceTokenVerifier:
    """Validates asymmetric workforce JWTs against configured JWKS URL."""

    def __init__(self, issuer: str, audience: str, jwks_url: str) -> None:
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._jwks_client = PyJWKClient(jwks_url, cache_keys=True)

    def verify(self, token: str) -> WorkforceClaims:
        try:
            unverified_header = jwt.get_unverified_header(token)
            alg = unverified_header.get("alg")
            if alg not in ALLOWED_ALGORITHMS:
                raise WorkforceAuthError(
                    "Unsupported token algorithm: only RS256 and ES256 permitted"
                )

            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": ["exp", "iss", "sub", "sid", "auth_time", "email", "email_verified"]
                },
            )
            return parse_workforce_payload(payload, self._issuer, self._audience)
        except jwt.ExpiredSignatureError:
            raise WorkforceAuthError("Workforce bearer token has expired") from None
        except WorkforceAuthError:
            raise
        except Exception:
            logger.warning("Workforce JWT verification failed")
            raise WorkforceAuthError("Invalid workforce bearer token") from None


class TestWorkforceTokenVerifier:
    """Verifier for testing with explicit public keys or mock JWKS."""

    __test__ = False

    def __init__(self, issuer: str, audience: str, public_key_pem: bytes | str) -> None:
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._public_key = public_key_pem

    def verify(self, token: str) -> WorkforceClaims:
        try:
            unverified_header = jwt.get_unverified_header(token)
            alg = unverified_header.get("alg")
            if alg not in ALLOWED_ALGORITHMS:
                raise WorkforceAuthError(
                    "Unsupported token algorithm: only RS256 and ES256 permitted"
                )

            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": ["exp", "iss", "sub", "sid", "auth_time", "email", "email_verified"]
                },
            )
            return parse_workforce_payload(payload, self._issuer, self._audience)
        except jwt.ExpiredSignatureError:
            raise WorkforceAuthError("Workforce bearer token has expired") from None
        except WorkforceAuthError:
            raise
        except Exception:
            logger.warning("Test workforce JWT verification failed")
            raise WorkforceAuthError("Invalid workforce bearer token") from None


def get_workforce_verifier() -> WorkforceTokenVerifier:
    """Return configured workforce token verifier."""
    settings = get_settings()
    if (
        settings.workforce_oidc_issuer
        and settings.workforce_oidc_audience
        and settings.workforce_oidc_jwks_url
    ):
        return DefaultWorkforceTokenVerifier(
            issuer=settings.workforce_oidc_issuer,
            audience=settings.workforce_oidc_audience,
            jwks_url=settings.workforce_oidc_jwks_url,
        )
    raise WorkforceAuthError(
        "Workforce OIDC is not configured (issuer, audience, and jwks_url required)",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def get_db_now(db: Session) -> datetime:
    """Fetch accurate database clock timestamp. Fails closed if unavailable."""
    try:
        bind = db.get_bind()
        if bind is not None and bind.dialect.name == "sqlite":
            raw = db.execute(text("SELECT strftime('%Y-%m-%d %H:%M:%f', 'now')")).scalar()
            if isinstance(raw, str):
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            elif isinstance(raw, datetime):
                return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
            raise RuntimeError("Could not retrieve sqlite clock time")
        else:
            val = db.execute(text("SELECT clock_timestamp()")).scalar()
            if isinstance(val, datetime):
                return val if val.tzinfo else val.replace(tzinfo=UTC)
            raise RuntimeError("Could not retrieve postgresql clock_timestamp")
    except Exception as exc:
        logger.error("Database clock failure: %s", exc.__class__.__name__)
        raise WorkforceAuthError(
            "Database clock unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc


def verify_auth_time_and_token_expiry(claims: WorkforceClaims, db_now: datetime) -> datetime:
    """Enforce token exp and signed auth_time clock drift/freshness (900 seconds max)."""
    auth_dt = datetime.fromtimestamp(claims.auth_time, UTC)

    # Future clock drift check (max 5s)
    if auth_dt > db_now + timedelta(seconds=5):
        raise WorkforceAuthError("Authentication timestamp cannot be in the future")

    # Freshness: age must be within 15 minutes (900 seconds)
    age_seconds = (db_now - auth_dt).total_seconds()
    if age_seconds > 900.0:
        raise WorkforceAuthError("Authentication expired: auth_time exceeds 15 minutes")

    # Token expiry check
    if claims.expires_at <= int(db_now.timestamp()):
        raise WorkforceAuthError("Workforce bearer token has expired")

    return auth_dt


def resolve_and_authorize_admin_user(
    db: Session, claims: WorkforceClaims, request: Request | None = None
) -> User:
    """Resolve pre-existing active platform admin by verified issuer and subject only."""
    stmt = select(User).where(
        User.oidc_issuer == claims.issuer,
        User.oidc_subject == claims.subject,
    )
    user = db.scalar(stmt)
    if user is None:
        raise WorkforceAuthError(
            "User is not an active platform administrator",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if request is not None:
        request.state.staff_user = user

    if user.status != UserStatus.ACTIVE:
        raise WorkforceAuthError(
            "User account is not active",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if not user.is_platform_admin:
        raise WorkforceAuthError(
            "User is not an active platform administrator",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    try:
        norm_claim_email = normalize_email_address(claims.email)
        norm_user_email = normalize_email_address(user.email)
    except ValueError as exc:
        raise WorkforceAuthError(
            "Invalid email address format",
            status_code=status.HTTP_403_FORBIDDEN,
        ) from exc

    if norm_claim_email != norm_user_email:
        raise WorkforceAuthError(
            "Verified workforce email mismatch with administrator record",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return user


def claims_to_token_claims(claims: WorkforceClaims) -> TokenClaims:
    """Adapt WorkforceClaims to existing TokenClaims structure."""
    return TokenClaims(
        issuer=claims.issuer,
        subject=claims.subject,
        session_id=claims.session_id,
        expires_at=claims.expires_at,
        email=claims.email,
        display_name=claims.display_name,
        email_verified=True,
        amr=claims.amr,
        acr=claims.acr,
        mfa_verified=True,
    )


def create_staff_session(
    db: Session,
    token: str,
    request_id: str,
    verifier: WorkforceTokenVerifier | None = None,
    request: Request | None = None,
) -> CatalogDemoSessionResponse:
    """Bootstrap a revocable staff demo session from a valid workforce JWT."""
    v = verifier or get_workforce_verifier()
    claims = v.verify(token)
    db_now = get_db_now(db)
    auth_dt = verify_auth_time_and_token_expiry(claims, db_now)

    # Pre-existing administrator authorization before calling bootstrap
    _user = resolve_and_authorize_admin_user(db, claims, request=request)

    token_claims = claims_to_token_claims(claims)

    try:
        user, auth_session = bootstrap_identity_session(
            db,
            token_claims,
            request_id=request_id,
            now=db_now,
        )
    except (IdentityBootstrapError, SessionLifecycleError):
        raise WorkforceAuthError(
            "Session cannot be created for identity",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from None
    db.commit()

    # Session expiry: min(token_exp, persisted_session_expiry, signed_auth_time + 900)
    session_exp = (
        auth_session.expires_at.replace(tzinfo=UTC)
        if auth_session.expires_at.tzinfo is None
        else auth_session.expires_at
    )
    token_exp_dt = datetime.fromtimestamp(claims.expires_at, UTC)
    auth_limit_dt = auth_dt + timedelta(seconds=900)
    expires_at = min(token_exp_dt, session_exp, auth_limit_dt)

    if expires_at <= db_now:
        raise WorkforceAuthError(
            "Session cannot be created with past expiry",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    return CatalogDemoSessionResponse(
        user_id=str(user.id),
        display_name=user.display_name or user.email,
        authenticated_at=auth_dt.isoformat(),
        expires_at=expires_at.isoformat(),
        capabilities=["DRAFT_READ"],
    )


def get_current_staff_session_data(
    db: Session,
    token: str,
    verifier: WorkforceTokenVerifier | None = None,
    request: Request | None = None,
) -> tuple[User, AuthSession, datetime, datetime]:
    """Retrieve and revalidate active session and workforce claims on every request."""
    v = verifier or get_workforce_verifier()
    claims = v.verify(token)
    db_now = get_db_now(db)
    auth_dt = verify_auth_time_and_token_expiry(claims, db_now)

    # Recheck persisted user/admin status
    user = resolve_and_authorize_admin_user(db, claims, request=request)

    token_claims = claims_to_token_claims(claims)

    # Authenticate claims against existing session lifecycle
    try:
        authenticate_claims(db, token_claims, now=db_now)
    except AuthenticationError as exc:
        raise WorkforceAuthError(
            "Active staff session not found or expired",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc

    # Retrieve active session
    stmt = select(AuthSession).where(
        AuthSession.session_id_hash == hash_session_id(claims.session_id),
        AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > db_now,
    )
    auth_session = db.scalar(stmt)
    if auth_session is None:
        raise WorkforceAuthError("Active staff session not found or expired")

    session_exp = (
        auth_session.expires_at.replace(tzinfo=UTC)
        if auth_session.expires_at.tzinfo is None
        else auth_session.expires_at
    )
    token_exp_dt = datetime.fromtimestamp(claims.expires_at, UTC)
    auth_limit_dt = auth_dt + timedelta(seconds=900)
    expires_at = min(token_exp_dt, session_exp, auth_limit_dt)

    return user, auth_session, auth_dt, expires_at


def revoke_staff_session(
    db: Session,
    token: str,
    request_id: str,
    verifier: WorkforceTokenVerifier | None = None,
    request: Request | None = None,
) -> None:
    """Revoke caller's own active staff session using existing lifecycle behavior."""
    v = verifier or get_workforce_verifier()
    claims = v.verify(token)
    db_now = get_db_now(db)
    verify_auth_time_and_token_expiry(claims, db_now)

    __user = resolve_and_authorize_admin_user(db, claims, request=request)

    token_claims = claims_to_token_claims(claims)
    try:
        principal = authenticate_claims(db, token_claims, now=db_now)
    except AuthenticationError as exc:
        raise WorkforceAuthError(
            "Active staff session not found or expired",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc

    revoke_own_auth_session(
        db,
        principal,
        session_id=claims.session_id,
        request_id=request_id,
        now=db_now,
    )
    db.commit()


def extract_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Extract token strictly from Authorization: Bearer <token>."""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    raise WorkforceAuthError("Missing or invalid Authorization Bearer header")


def build_staff_actor_context(user: User, auth_time: datetime) -> CatalogActorContext:
    """Construct CatalogActorContext preserving signed auth_time."""
    tz_auth = auth_time if auth_time.tzinfo is not None else auth_time.replace(tzinfo=UTC)
    return CatalogActorContext(
        actor_id=user.id,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=tz_auth,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )


def get_current_staff_actor(
    request: Request,
    token: Annotated[str, Depends(extract_bearer_token)],
    db: Annotated[Session, Depends(get_db)],
    verifier: Annotated[WorkforceTokenVerifier, Depends(get_workforce_verifier)],
) -> tuple[User, CatalogActorContext]:
    """FastAPI dependency providing verified staff user and CatalogActorContext."""
    user, _auth_session, auth_dt, _expires_at = get_current_staff_session_data(
        db, token, verifier, request=request
    )
    actor_context = build_staff_actor_context(user, auth_dt)
    return user, actor_context
