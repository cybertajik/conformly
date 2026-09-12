from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EncryptionContext:
    tenant_id: UUID
    resource_type: str
    resource_id: str
    field_name: str
    version: int = 1


@dataclass(frozen=True, slots=True)
class AEADCiphertext:
    nonce: bytes
    ciphertext: bytes


@dataclass(frozen=True, slots=True)
class WrappedKey:
    key_version: str
    nonce: bytes
    ciphertext: bytes


@dataclass(frozen=True, slots=True)
class EncryptedPayload:
    algorithm: Literal["AES-256-GCM"]
    context_version: int
    key_version: str
    wrapped_dek_nonce: bytes
    wrapped_dek: bytes
    nonce: bytes
    ciphertext: bytes
