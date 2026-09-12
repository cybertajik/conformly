import base64
import binascii
import hashlib
import hmac
import secrets
from functools import lru_cache

from conformly.config import get_settings


class InvitationTokenConfigurationError(RuntimeError):
    """Raised when secure invitation verification is not configured."""


class InvitationTokenService:
    def __init__(self, pepper: bytes) -> None:
        if len(pepper) < 32:
            raise InvitationTokenConfigurationError(
                "invitation token pepper must contain at least 32 bytes"
            )
        self._pepper = pepper

    def issue(self) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        return token, self.digest(token)

    def digest(self, token: str) -> str:
        return hmac.new(self._pepper, token.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify(self, token: str, expected_digest: str) -> bool:
        return hmac.compare_digest(self.digest(token), expected_digest)


@lru_cache
def get_invitation_token_service() -> InvitationTokenService:
    encoded_pepper = get_settings().invitation_token_pepper
    if not encoded_pepper:
        raise InvitationTokenConfigurationError("invitation token pepper is not configured")
    try:
        pepper = base64.b64decode(encoded_pepper, validate=True)
    except (binascii.Error, ValueError) as error:
        raise InvitationTokenConfigurationError(
            "invitation token pepper is not valid base64"
        ) from error
    return InvitationTokenService(pepper)
