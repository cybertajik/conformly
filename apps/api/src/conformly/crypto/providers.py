import base64
import binascii
import os
from typing import Any, Protocol

import httpx
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


class VaultKmsProvider:
    """Production KEK provider backed by HashiCorp Vault or OpenBao transit secret engine."""

    def __init__(
        self,
        endpoint: str,
        token: str,
        key_name: str = "conformly-master-key",
        mount: str = "transit",
        active_key_version: str = "1",
        http_client: httpx.Client | None = None,
    ) -> None:
        if not endpoint or not token:
            raise KeyConfigurationError("Vault/OpenBao endpoint and token must be configured")
        self._endpoint = endpoint.rstrip("/")
        self._token = token
        self._key_name = key_name
        self._mount = mount.strip("/")
        self._active_key_version = str(active_key_version)
        if http_client is not None:
            self._client = http_client
            if "X-Vault-Token" not in self._client.headers:
                self._client.headers["X-Vault-Token"] = self._token
        else:
            self._client = httpx.Client(
                base_url=self._endpoint,
                headers={"X-Vault-Token": self._token},
                timeout=10.0,
            )

    @property
    def active_key_version(self) -> str:
        return self._active_key_version

    def wrap_key(self, key: bytes, aad: bytes) -> WrappedKey:
        if len(key) != AES_256_KEY_BYTES:
            raise KeyConfigurationError("Key to wrap must be exactly 32 bytes")
        b64_plaintext = base64.b64encode(key).decode("ascii")
        b64_context = base64.b64encode(aad).decode("ascii") if aad else ""
        url = f"/v1/{self._mount}/encrypt/{self._key_name}"
        payload: dict[str, str] = {"plaintext": b64_plaintext}
        if b64_context:
            payload["context"] = b64_context
        try:
            resp = self._client.post(url, json=payload)
            if resp.status_code != 200:
                raise InvalidCiphertextError(
                    f"Vault transit encrypt failed with status {resp.status_code}"
                )
            data = resp.json().get("data", {})
            ciphertext_str = data.get("ciphertext")
            if not ciphertext_str or not ciphertext_str.startswith("vault:v"):
                raise InvalidCiphertextError("Invalid transit ciphertext returned by Vault")

            parts = ciphertext_str.split(":", 2)
            key_version = parts[1].removeprefix("v")
            raw_ciphertext = ciphertext_str.encode("utf-8")
            return WrappedKey(
                key_version=key_version,
                nonce=b"",
                ciphertext=raw_ciphertext,
            )
        except httpx.RequestError as error:
            raise InvalidCiphertextError(
                "Vault communication failed during key wrapping"
            ) from error

    def unwrap_key(self, wrapped_key: WrappedKey, aad: bytes) -> bytes:
        ciphertext_str = wrapped_key.ciphertext.decode("utf-8")
        b64_context = base64.b64encode(aad).decode("ascii") if aad else ""
        url = f"/v1/{self._mount}/decrypt/{self._key_name}"
        payload: dict[str, str] = {"ciphertext": ciphertext_str}
        if b64_context:
            payload["context"] = b64_context
        try:
            resp = self._client.post(url, json=payload)
            if resp.status_code != 200:
                raise InvalidCiphertextError(
                    "Vault transit decrypt failed or authenticated context mismatch"
                )
            data = resp.json().get("data", {})
            b64_plaintext = data.get("plaintext")
            if not b64_plaintext:
                raise InvalidCiphertextError("No plaintext returned by Vault transit engine")
            key = base64.b64decode(b64_plaintext, validate=True)
            if len(key) != AES_256_KEY_BYTES:
                raise KeyConfigurationError("Unwrapped key length mismatch")
            return key
        except (httpx.RequestError, binascii.Error, ValueError) as error:
            raise InvalidCiphertextError("Vault key unwrapping failed") from error


def get_kms_provider(settings: Any | None = None) -> KeyManagementProvider:
    if settings is None:
        from conformly.config import get_settings

        settings = get_settings()

    provider_type = getattr(settings, "kms_provider", "local").lower()
    if provider_type in ("vault", "openbao"):
        return VaultKmsProvider(
            endpoint=getattr(settings, "vault_endpoint", None) or "http://localhost:8200",
            token=getattr(settings, "vault_token", None) or "root",
            key_name=getattr(settings, "vault_key_name", "conformly-master-key"),
            mount=getattr(settings, "vault_transit_mount", "transit"),
            active_key_version=getattr(settings, "active_kek_version", None) or "1",
        )
    local_keks = dict(getattr(settings, "local_keks", {}) or {})
    active_key = getattr(settings, "active_kek_version", None) or "v1"
    if not local_keks and getattr(settings, "environment", "production") in (
        "development",
        "local",
        "test",
    ):
        local_keks = {"v1": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="}
        active_key = "v1"

    return LocalKeyManagementProvider(
        encoded_keys=local_keks,
        active_key_version=active_key,
    )
