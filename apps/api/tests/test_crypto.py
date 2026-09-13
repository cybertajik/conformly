import base64
import os
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.policy import DataClassification, requires_application_encryption
from conformly.crypto.providers import (
    AES256GCMProvider,
    InvalidCiphertextError,
    KeyConfigurationError,
    LocalKeyManagementProvider,
)
from conformly.crypto.types import EncryptionContext


def encoded_key() -> str:
    return base64.b64encode(os.urandom(32)).decode("ascii")


def context(*, tenant_id: UUID | None = None, field_name: str = "body") -> EncryptionContext:
    return EncryptionContext(
        tenant_id=tenant_id or uuid4(),
        resource_type="whistleblower_message",
        resource_id="message-123",
        field_name=field_name,
    )


def service(keys: dict[str, str] | None = None, active: str = "v1") -> EnvelopeEncryptionService:
    configured_keys = keys or {"v1": encoded_key()}
    return EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider(configured_keys, active)
    )


def test_envelope_encryption_round_trip() -> None:
    encryption = service()
    encryption_context = context()

    payload = encryption.encrypt(b"restricted plaintext", encryption_context)

    assert payload.algorithm == "AES-256-GCM"
    assert payload.key_version == "v1"
    assert encryption.decrypt(payload, encryption_context) == b"restricted plaintext"
    assert b"restricted plaintext" not in payload.ciphertext


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("ciphertext", b"tampered ciphertext"),
        ("nonce", b"0" * 12),
        ("wrapped_dek", b"tampered wrapped key"),
        ("wrapped_dek_nonce", b"1" * 12),
    ],
)
def test_tampering_is_detected(field: str, replacement: bytes) -> None:
    encryption = service()
    encryption_context = context()
    payload = encryption.encrypt(b"protected", encryption_context)

    if field == "ciphertext":
        tampered = replace(payload, ciphertext=replacement)
    elif field == "nonce":
        tampered = replace(payload, nonce=replacement)
    elif field == "wrapped_dek":
        tampered = replace(payload, wrapped_dek=replacement)
    else:
        tampered = replace(payload, wrapped_dek_nonce=replacement)

    with pytest.raises(InvalidCiphertextError):
        encryption.decrypt(tampered, encryption_context)


def test_wrong_tenant_context_fails() -> None:
    encryption = service()
    original_context = context()
    payload = encryption.encrypt(b"protected", original_context)
    other_tenant_context = replace(original_context, tenant_id=uuid4())

    with pytest.raises(InvalidCiphertextError):
        encryption.decrypt(payload, other_tenant_context)


def test_wrong_field_context_fails() -> None:
    encryption = service()
    original_context = context()
    payload = encryption.encrypt(b"protected", original_context)

    with pytest.raises(InvalidCiphertextError):
        encryption.decrypt(payload, replace(original_context, field_name="other_field"))


def test_old_key_version_decrypts_and_rewraps_to_active_version() -> None:
    keys = {"v1": encoded_key(), "v2": encoded_key()}
    old_service = service(keys, active="v1")
    new_service = service(keys, active="v2")
    encryption_context = context()
    old_payload = old_service.encrypt(b"rotate me", encryption_context)

    assert new_service.decrypt(old_payload, encryption_context) == b"rotate me"
    rewrapped = new_service.rewrap(old_payload, encryption_context)

    assert rewrapped.key_version == "v2"
    assert rewrapped.ciphertext == old_payload.ciphertext
    assert new_service.decrypt(rewrapped, encryption_context) == b"rotate me"


def test_missing_old_key_version_fails_closed() -> None:
    encryption_context = context()
    payload = service({"v1": encoded_key()}, active="v1").encrypt(b"protected", encryption_context)

    with pytest.raises(KeyConfigurationError):
        service({"v2": encoded_key()}, active="v2").decrypt(payload, encryption_context)


def test_invalid_key_configuration_is_rejected() -> None:
    with pytest.raises(KeyConfigurationError):
        LocalKeyManagementProvider({"v1": "not-base64"}, "v1")
    with pytest.raises(KeyConfigurationError):
        LocalKeyManagementProvider({"v1": base64.b64encode(b"short").decode()}, "v1")
    with pytest.raises(KeyConfigurationError):
        LocalKeyManagementProvider({"v1": encoded_key()}, "missing")


@pytest.mark.parametrize(
    ("classification", "is_file", "selected", "expected"),
    [
        (DataClassification.PUBLIC, False, False, False),
        (DataClassification.INTERNAL, False, False, False),
        (DataClassification.CONFIDENTIAL, False, False, False),
        (DataClassification.CONFIDENTIAL, False, True, True),
        (DataClassification.RESTRICTED, False, False, True),
        (DataClassification.PUBLIC, True, False, True),
    ],
)
def test_classification_encryption_policy(
    classification: DataClassification,
    is_file: bool,
    selected: bool,
    expected: bool,
) -> None:
    assert (
        requires_application_encryption(
            classification,
            is_file=is_file,
            confidential_field_selected=selected,
        )
        is expected
    )


def test_vault_kms_provider_roundtrip() -> None:
    import json

    import httpx

    from conformly.config import Settings
    from conformly.crypto.providers import VaultKmsProvider, get_kms_provider

    def handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        if "/encrypt/" in url_path:
            body = json.loads(request.content)
            plaintext = body["plaintext"]
            context_b64 = body.get("context", "")
            ct = f"vault:v1:{plaintext}.{context_b64}"
            return httpx.Response(200, json={"data": {"ciphertext": ct}})
        if "/decrypt/" in url_path:
            body = json.loads(request.content)
            ct = body["ciphertext"]
            context_b64 = body.get("context", "")
            parts = ct.split(":")
            payload = parts[2]
            pt, saved_context = payload.split(".", 1)
            if saved_context != context_b64:
                return httpx.Response(400, json={"errors": ["context mismatch"]})
            return httpx.Response(200, json={"data": {"plaintext": pt}})
        return httpx.Response(404)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://vault:8200")
    kms = VaultKmsProvider(
        endpoint="http://vault:8200",
        token="test-token",
        key_name="master",
        mount="transit",
        active_key_version="1",
        http_client=mock_client,
    )

    test_dek = os.urandom(32)
    aad = b"tenant-123:field"

    wrapped = kms.wrap_key(test_dek, aad)
    assert wrapped.key_version == "1"
    assert wrapped.ciphertext.startswith(b"vault:v1:")

    unwrapped = kms.unwrap_key(wrapped, aad)
    assert unwrapped == test_dek

    # Tampered context fails
    with pytest.raises(InvalidCiphertextError):
        kms.unwrap_key(wrapped, b"wrong-tenant")

    # Factory instantiation test
    settings = Settings(
        kms_provider="vault",
        vault_endpoint="http://vault:8200",
        vault_token="root",
    )
    provider = get_kms_provider(settings)
    assert isinstance(provider, VaultKmsProvider)
