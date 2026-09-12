import json
import os
from functools import lru_cache

from conformly.config import get_settings
from conformly.crypto.providers import (
    AES_256_KEY_BYTES,
    AES256GCMProvider,
    CryptoProvider,
    InvalidCiphertextError,
    KeyConfigurationError,
    KeyManagementProvider,
    LocalKeyManagementProvider,
)
from conformly.crypto.types import (
    AEADCiphertext,
    EncryptedPayload,
    EncryptionContext,
    WrappedKey,
)


def authenticated_context(context: EncryptionContext) -> bytes:
    return json.dumps(
        {
            "field_name": context.field_name,
            "resource_id": context.resource_id,
            "resource_type": context.resource_type,
            "tenant_id": str(context.tenant_id),
            "version": context.version,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class EnvelopeEncryptionService:
    def __init__(self, crypto: CryptoProvider, keys: KeyManagementProvider) -> None:
        self._crypto = crypto
        self._keys = keys

    def encrypt(self, plaintext: bytes, context: EncryptionContext) -> EncryptedPayload:
        aad = authenticated_context(context)
        dek = os.urandom(AES_256_KEY_BYTES)
        encrypted = self._crypto.encrypt(dek, plaintext, aad)
        wrapped_dek = self._keys.wrap_key(dek, aad)
        return EncryptedPayload(
            algorithm="AES-256-GCM",
            context_version=context.version,
            key_version=wrapped_dek.key_version,
            wrapped_dek_nonce=wrapped_dek.nonce,
            wrapped_dek=wrapped_dek.ciphertext,
            nonce=encrypted.nonce,
            ciphertext=encrypted.ciphertext,
        )

    def decrypt(self, payload: EncryptedPayload, context: EncryptionContext) -> bytes:
        if payload.algorithm != self._crypto.algorithm:
            raise InvalidCiphertextError("unsupported encryption algorithm")
        if payload.context_version != context.version:
            raise InvalidCiphertextError("encryption context version mismatch")
        aad = authenticated_context(context)
        dek = self._keys.unwrap_key(
            WrappedKey(
                key_version=payload.key_version,
                nonce=payload.wrapped_dek_nonce,
                ciphertext=payload.wrapped_dek,
            ),
            aad,
        )
        return self._crypto.decrypt(
            dek,
            AEADCiphertext(nonce=payload.nonce, ciphertext=payload.ciphertext),
            aad,
        )

    def rewrap(self, payload: EncryptedPayload, context: EncryptionContext) -> EncryptedPayload:
        if payload.algorithm != self._crypto.algorithm:
            raise InvalidCiphertextError("unsupported encryption algorithm")
        if payload.context_version != context.version:
            raise InvalidCiphertextError("encryption context version mismatch")
        aad = authenticated_context(context)
        dek = self._keys.unwrap_key(
            WrappedKey(
                key_version=payload.key_version,
                nonce=payload.wrapped_dek_nonce,
                ciphertext=payload.wrapped_dek,
            ),
            aad,
        )
        wrapped_dek = self._keys.wrap_key(dek, aad)
        return EncryptedPayload(
            algorithm=payload.algorithm,
            context_version=payload.context_version,
            key_version=wrapped_dek.key_version,
            wrapped_dek_nonce=wrapped_dek.nonce,
            wrapped_dek=wrapped_dek.ciphertext,
            nonce=payload.nonce,
            ciphertext=payload.ciphertext,
        )


@lru_cache
def get_envelope_encryption_service() -> EnvelopeEncryptionService:
    settings = get_settings()
    if not settings.local_keks or not settings.active_kek_version:
        raise KeyConfigurationError("local development KEK settings are incomplete")
    return EnvelopeEncryptionService(
        AES256GCMProvider(),
        LocalKeyManagementProvider(settings.local_keks, settings.active_kek_version),
    )
