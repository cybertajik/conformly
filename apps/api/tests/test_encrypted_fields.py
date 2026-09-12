import base64
import json
import os
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec, EncryptedFieldValue
from conformly.crypto.providers import (
    AES256GCMProvider,
    InvalidCiphertextError,
    LocalKeyManagementProvider,
)
from conformly.crypto.types import EncryptionContext
from conformly.identity.models import Tenant
from conformly.notifications.models import NotificationOutbox
from conformly.notifications.service import enqueue_encrypted_notification


def make_codec(*, active: str = "v1", keys: dict[str, str] | None = None) -> EncryptedFieldCodec:
    configured_keys = keys or {"v1": base64.b64encode(os.urandom(32)).decode("ascii")}
    envelope = EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider(configured_keys, active)
    )
    return EncryptedFieldCodec(envelope)


def make_context() -> EncryptionContext:
    return EncryptionContext(
        tenant_id=uuid4(),
        resource_type="case",
        resource_id="case-123",
        field_name="description",
    )


def test_encrypted_field_storage_round_trip_contains_no_plaintext() -> None:
    codec = make_codec()
    context = make_context()
    plaintext = "highly restricted report content"

    stored = codec.encrypt_text(plaintext, context)

    assert plaintext not in json.dumps(stored)
    assert codec.decrypt_text(stored, context) == plaintext


def test_restricted_payload_plaintext_is_absent_from_persisted_row(session: Session) -> None:
    codec = make_codec()
    tenant = Tenant(name="Encryption Tenant", slug=f"encryption-{uuid4()}")
    session.add(tenant)
    session.flush()
    plaintext = "restricted incident narrative 7b62f9"
    enqueue_encrypted_notification(
        session,
        codec,
        message_id=uuid4(),
        tenant_id=tenant.id,
        kind="restricted_test",
        idempotency_key=f"restricted-test:{uuid4()}",
        payload={"body": plaintext},
    )
    session.commit()
    session.expire_all()

    stored = session.execute(select(NotificationOutbox.encrypted_payload)).scalar_one()
    assert plaintext not in json.dumps(stored)


def test_encrypted_field_wrong_context_fails() -> None:
    codec = make_codec()
    context = make_context()
    stored = codec.encrypt_text("protected", context)

    with pytest.raises(InvalidCiphertextError):
        codec.decrypt_text(stored, replace(context, tenant_id=uuid4()))


def test_encrypted_field_rewrap_preserves_ciphertext() -> None:
    keys = {
        "v1": base64.b64encode(os.urandom(32)).decode("ascii"),
        "v2": base64.b64encode(os.urandom(32)).decode("ascii"),
    }
    context = make_context()
    old_codec = make_codec(active="v1", keys=keys)
    new_codec = make_codec(active="v2", keys=keys)
    stored = old_codec.encrypt_text("protected", context)

    rewrapped = new_codec.rewrap(stored, context)

    assert rewrapped["key_version"] == "v2"
    assert rewrapped["ciphertext"] == stored["ciphertext"]
    assert new_codec.decrypt_text(rewrapped, context) == "protected"


def test_encrypted_field_rejects_missing_metadata() -> None:
    with pytest.raises(InvalidCiphertextError):
        EncryptedFieldValue.from_storage({"algorithm": "AES-256-GCM"})


def test_encrypted_field_rejects_invalid_base64() -> None:
    codec = make_codec()
    context = make_context()
    stored = codec.encrypt_text("protected", context)
    stored["ciphertext"] = "not base64!"

    with pytest.raises(InvalidCiphertextError):
        codec.decrypt_text(stored, context)


def test_encrypted_field_rejects_unknown_algorithm() -> None:
    codec = make_codec()
    context = make_context()
    stored = codec.encrypt_text("protected", context)
    stored["algorithm"] = "custom-cipher"

    with pytest.raises(InvalidCiphertextError):
        codec.decrypt_text(stored, context)
