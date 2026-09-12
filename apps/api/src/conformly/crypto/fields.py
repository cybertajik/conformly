import base64
import binascii
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Self

from conformly.crypto.envelope import EnvelopeEncryptionService, get_envelope_encryption_service
from conformly.crypto.providers import InvalidCiphertextError
from conformly.crypto.types import EncryptedPayload, EncryptionContext


@dataclass(frozen=True, slots=True)
class EncryptedFieldValue:
    """JSON-safe persistence representation for one encrypted application field."""

    algorithm: str
    context_version: int
    key_version: str
    wrapped_dek_nonce: str
    wrapped_dek: str
    nonce: str
    ciphertext: str

    @classmethod
    def from_payload(cls, payload: EncryptedPayload) -> Self:
        encode = base64.b64encode
        return cls(
            algorithm=payload.algorithm,
            context_version=payload.context_version,
            key_version=payload.key_version,
            wrapped_dek_nonce=encode(payload.wrapped_dek_nonce).decode("ascii"),
            wrapped_dek=encode(payload.wrapped_dek).decode("ascii"),
            nonce=encode(payload.nonce).decode("ascii"),
            ciphertext=encode(payload.ciphertext).decode("ascii"),
        )

    @classmethod
    def from_storage(cls, value: dict[str, Any]) -> Self:
        required = {
            "algorithm",
            "context_version",
            "key_version",
            "wrapped_dek_nonce",
            "wrapped_dek",
            "nonce",
            "ciphertext",
        }
        if set(value) != required:
            raise InvalidCiphertextError("encrypted field metadata is incomplete")
        try:
            return cls(
                algorithm=str(value["algorithm"]),
                context_version=int(value["context_version"]),
                key_version=str(value["key_version"]),
                wrapped_dek_nonce=str(value["wrapped_dek_nonce"]),
                wrapped_dek=str(value["wrapped_dek"]),
                nonce=str(value["nonce"]),
                ciphertext=str(value["ciphertext"]),
            )
        except (TypeError, ValueError) as error:
            raise InvalidCiphertextError("encrypted field metadata is invalid") from error

    def to_payload(self) -> EncryptedPayload:
        if self.algorithm != "AES-256-GCM":
            raise InvalidCiphertextError("unsupported encrypted field algorithm")
        try:
            return EncryptedPayload(
                algorithm="AES-256-GCM",
                context_version=self.context_version,
                key_version=self.key_version,
                wrapped_dek_nonce=base64.b64decode(self.wrapped_dek_nonce, validate=True),
                wrapped_dek=base64.b64decode(self.wrapped_dek, validate=True),
                nonce=base64.b64decode(self.nonce, validate=True),
                ciphertext=base64.b64decode(self.ciphertext, validate=True),
            )
        except (binascii.Error, ValueError) as error:
            raise InvalidCiphertextError("encrypted field encoding is invalid") from error

    def to_storage(self) -> dict[str, Any]:
        return asdict(self)


class EncryptedFieldCodec:
    """Explicit text field encryption that always requires authenticated context."""

    def __init__(self, envelope: EnvelopeEncryptionService) -> None:
        self._envelope = envelope

    def encrypt_text(self, plaintext: str, context: EncryptionContext) -> dict[str, Any]:
        payload = self._envelope.encrypt(plaintext.encode("utf-8"), context)
        return EncryptedFieldValue.from_payload(payload).to_storage()

    def decrypt_text(self, stored: dict[str, Any], context: EncryptionContext) -> str:
        value = EncryptedFieldValue.from_storage(stored)
        try:
            return self._envelope.decrypt(value.to_payload(), context).decode("utf-8")
        except UnicodeDecodeError as error:
            raise InvalidCiphertextError("encrypted field plaintext encoding is invalid") from error

    def rewrap(self, stored: dict[str, Any], context: EncryptionContext) -> dict[str, Any]:
        value = EncryptedFieldValue.from_storage(stored)
        payload = self._envelope.rewrap(value.to_payload(), context)
        return EncryptedFieldValue.from_payload(payload).to_storage()


@lru_cache
def get_encrypted_field_codec() -> EncryptedFieldCodec:
    return EncryptedFieldCodec(get_envelope_encryption_service())
