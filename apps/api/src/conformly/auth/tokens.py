from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import jwt
from jwt import PyJWKClient

from conformly.config import get_settings


class AuthenticationError(Exception):
    """Raised for invalid or untrusted authentication material."""


class AuthenticationConfigurationError(RuntimeError):
    """Raised when authentication is used before OIDC is configured."""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    issuer: str
    subject: str
    session_id: str
    expires_at: int
    email: str | None = None
    display_name: str | None = None
    email_verified: bool = False


class TokenVerifier(Protocol):
    def verify(self, token: str) -> TokenClaims: ...


class OIDCTokenVerifier:
    """Validate signed OIDC access tokens using the provider's JWKS."""

    def __init__(self, issuer: str, audience: str, jwks_url: str) -> None:
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._jwks_client = PyJWKClient(jwks_url, cache_keys=True)

    def verify(self, token: str) -> TokenClaims:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "sub", "sid", "email", "email_verified"]},
            )
            return TokenClaims(
                issuer=str(payload["iss"]),
                subject=str(payload["sub"]),
                session_id=str(payload["sid"]),
                expires_at=int(payload["exp"]),
                email=str(payload["email"]) if payload.get("email") else None,
                display_name=str(payload["name"]) if payload.get("name") else None,
                email_verified=payload.get("email_verified") is True,
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
            raise AuthenticationError("invalid bearer token") from error


@lru_cache
def get_token_verifier() -> TokenVerifier:
    settings = get_settings()
    if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
        raise AuthenticationConfigurationError("OIDC settings are incomplete")
    return OIDCTokenVerifier(
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        jwks_url=settings.oidc_jwks_url,
    )
