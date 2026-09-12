from uuid import uuid4

import pytest
from pydantic import ValidationError

from conformly.tenancy.namespace import TenantJobPayload, tenant_cache_key


def test_cache_keys_are_tenant_namespaced() -> None:
    first_tenant = uuid4()
    second_tenant = uuid4()

    first = tenant_cache_key(first_tenant, "memberships", "active")
    second = tenant_cache_key(second_tenant, "memberships", "active")

    assert first != second
    assert str(first_tenant) in first


@pytest.mark.parametrize("namespace", ["", "UPPERCASE", "unsafe space", ":escape"])
def test_cache_key_rejects_unsafe_namespaces(namespace: str) -> None:
    with pytest.raises(ValueError):
        tenant_cache_key(uuid4(), namespace, "record")


def test_tenant_job_payload_requires_tenant_and_idempotency_key() -> None:
    with pytest.raises(ValidationError):
        TenantJobPayload.model_validate({"idempotency_key": "job:1"})
    with pytest.raises(ValidationError):
        TenantJobPayload.model_validate({"tenant_id": str(uuid4()), "idempotency_key": ""})
