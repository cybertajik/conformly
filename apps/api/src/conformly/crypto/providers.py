import base64
import binascii
import os
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from conformly.crypto.types import AEADCiphertext, WrappedKey

AES_256_KEY_BYTES = 32
GCM_NONCE_BYTES = 12


class CryptoError(Exception):
    """Base class for failures that must not expose cryptographic material."""


class InvalidCiphertextError(CryptoError):
    """Raised when ciphertext or authenticated context cannot be verified."""


class KeyConfigurationError(CryptoError):
    """Raised when a configured key is absent or invalid."""


class CryptoProvider(Protocol):
    algorithm: str

    def encrypt(self, key: bytes, plaintext: bytes, aad: bytes) -> AEADCiphertext: ...

    def decrypt(self, key: bytes, payload: AEADCiphertext, aad: bytes) -> bytes: ...


class KeyManagementProvider(Protocol):
    @property
    def active_key_version(self) -> str: ...

    def wrap_key(self, key: bytes, aad: bytes) -> WrappedKey: ...

    def unwrap_key(self, wrapped_key: WrappedKey, aad: bytes) -> bytes: ...


class AES256GCMProvider:
    algorithm = "AES-256-GCM"

    def encrypt(self, key: bytes, plaintext: bytes, aad: bytes) -> AEADCiphertext:
        if len(key) != AES_256_KEY_BYTES:
            raise KeyConfigurationError("AES-256-GCM requires a 32-byte key")
        nonce = os.urandom(GCM_NONCE_BYTES)
        return AEADCiphertext(
            nonce=nonce,
            ciphertext=AESGCM(key).encrypt(nonce, plaintext, aad),
        )

    def decrypt(self, key: bytes, payload: AEADCiphertext, aad: bytes) -> bytes:
        if len(key) != AES_256_KEY_BYTES:
            raise KeyConfigurationError("AES-256-GCM requires a 32-byte key")
        try:
            return AESGCM(key).decrypt(payload.nonce, payload.ciphertext, aad)
        except (InvalidTag, ValueError) as error:
            raise InvalidCiphertextError("ciphertext authentication failed") from error


class LocalKeyManagementProvider:
    """Development KEK provider; production deployments replace this with KMS/HSM."""

    def __init__(self, encoded_keys: dict[str, str], active_key_version: str) -> None:
        self._keys = {
            version: self._decode_key(encoded_key) for version, encoded_key in encoded_keys.items()
        }
        if active_key_version not in self._keys:
            raise KeyConfigurationError("active KEK version is not configured")
        self._active_key_version = active_key_version
        self._crypto = AES256GCMProvider()

    @staticmethod
    def _decode_key(encoded_key: str) -> bytes:
        try:
            key = base64.b64decode(encoded_key, validate=True)
        except (binascii.Error, ValueError) as error:
            raise KeyConfigurationError("KEK is not valid base64") from error
        if len(key) != AES_256_KEY_BYTES:
            raise KeyConfigurationError("KEK must decode to exactly 32 bytes")
        return key

    @property
    def active_key_version(self) -> str:
        return self._active_key_version

    def wrap_key(self, key: bytes, aad: bytes) -> WrappedKey:
        encrypted = self._crypto.encrypt(self._keys[self._active_key_version], key, aad)
        return WrappedKey(
            key_version=self._active_key_version,
            nonce=encrypted.nonce,
            ciphertext=encrypted.ciphertext,
        )

    def unwrap_key(self, wrapped_key: WrappedKey, aad: bytes) -> bytes:
        key_encryption_key = self._keys.get(wrapped_key.key_version)
        if key_encryption_key is None:
            raise KeyConfigurationError("wrapped key version is unavailable")
        return self._crypto.decrypt(
            key_encryption_key,
            AEADCiphertext(nonce=wrapped_key.nonce, ciphertext=wrapped_key.ciphertext),
            aad,
        )
