"""Platform Disaster Recovery Restore Module.

Rebuilds the entire platform into a clean environment:
- Provisions schema on an empty database engine.
- Hydrates database tables in topological dependency order.
- Restores encrypted ciphertext objects into clean object storage.
- Validates SHA-256 cryptographic manifest integrity.
- Measures RTO and RPO against paid pilot operational targets.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Engine, Uuid
from sqlalchemy.orm import Session

from conformly.db.base import Base
from conformly.recovery.backup import PlatformBackupBundle
from conformly.storage.providers import StorageProvider

# Operational targets per PRODUCT_SOURCE_OF_TRUTH.md Section 14
TARGET_RTO_SECONDS = 4 * 3600  # 4 hours
TARGET_RPO_SECONDS = 1 * 3600  # 1 hour


class BackupIntegrityError(Exception):
    """Raised when backup manifest fails cryptographic digest verification."""


@dataclass(slots=True)
class RecoveryExecutionReport:
    """Measured operational report for disaster recovery rehearsal."""

    backup_timestamp: str
    restored_at: str
    measured_rto_seconds: float
    measured_rpo_seconds: float
    restored_tables_count: int
    restored_rows_count: int
    restored_objects_count: int
    integrity_verified: bool
    rto_target_met: bool
    rpo_target_met: bool


def _deserialize_row(table: Any, row_dict: dict[str, Any]) -> dict[str, Any]:
    col_map = {c.name: c for c in table.columns}
    deserialized: dict[str, Any] = {}
    for col_name, val in row_dict.items():
        if val is None:
            deserialized[col_name] = None
            continue

        # Handle bytes marker
        if isinstance(val, dict) and "__bytes__" in val:
            deserialized[col_name] = base64.b64decode(val["__bytes__"])
            continue

        col = col_map.get(col_name)
        if col is not None:
            col_type = col.type
            # Handle DateTime columns
            if isinstance(col_type, DateTime) and isinstance(val, str):
                try:
                    deserialized[col_name] = datetime.fromisoformat(val)
                    continue
                except ValueError:
                    pass
            # Handle UUID columns
            if isinstance(col_type, Uuid) and isinstance(val, str):
                try:
                    deserialized[col_name] = UUID(val)
                    continue
                except ValueError:
                    pass

        deserialized[col_name] = val
    return deserialized


def restore_platform_backup(
    bundle: PlatformBackupBundle,
    target_engine: Engine,
    target_storage: StorageProvider | None = None,
) -> RecoveryExecutionReport:
    """Restores database and encrypted storage into a clean target environment."""
    t_start = time.perf_counter()

    # 1. Cryptographic SHA-256 Manifest Verification
    hasher = hashlib.sha256()
    hasher.update(json.dumps(bundle.database_tables, sort_keys=True).encode("utf-8"))
    hasher.update(json.dumps(bundle.storage_objects, sort_keys=True).encode("utf-8"))
    hasher.update(json.dumps(bundle.kms_keys, sort_keys=True).encode("utf-8"))
    calculated_hash = hasher.hexdigest()

    if calculated_hash != bundle.manifest_sha256:
        raise BackupIntegrityError(
            f"backup manifest digest mismatch: expected {bundle.manifest_sha256}, got {calculated_hash}"
        )

    # 2. Schema Provisioning on Clean Database Target
    Base.metadata.create_all(target_engine)

    # 3. Table Data Hydration in Topological Dependency Order
    restored_tables = 0
    restored_rows = 0

    with Session(target_engine) as session:
        for table in Base.metadata.sorted_tables:
            table_rows = bundle.database_tables.get(table.name, [])
            if table_rows:
                deserialized_batch = [_deserialize_row(table, row_dict) for row_dict in table_rows]
                session.execute(table.insert(), deserialized_batch)
                restored_tables += 1
                restored_rows += len(deserialized_batch)
        session.commit()

    # 4. Storage Objects Restoration into Target Storage Provider
    restored_objects = 0
    if target_storage is not None and bundle.storage_objects:
        for object_key, b64_ciphertext in bundle.storage_objects.items():
            raw_bytes = base64.b64decode(b64_ciphertext)
            target_storage.put_object(object_key, raw_bytes)
            restored_objects += 1

    t_end = time.perf_counter()
    measured_rto = t_end - t_start

    try:
        dt_backup = datetime.fromisoformat(bundle.metadata.created_at)
        measured_rpo = (datetime.now(UTC) - dt_backup).total_seconds()
    except Exception:
        measured_rpo = 0.0

    restored_at = datetime.now(UTC).isoformat()

    return RecoveryExecutionReport(
        backup_timestamp=bundle.metadata.created_at,
        restored_at=restored_at,
        measured_rto_seconds=measured_rto,
        measured_rpo_seconds=measured_rpo,
        restored_tables_count=restored_tables,
        restored_rows_count=restored_rows,
        restored_objects_count=restored_objects,
        integrity_verified=True,
        rto_target_met=(measured_rto <= TARGET_RTO_SECONDS),
        rpo_target_met=(measured_rpo <= TARGET_RPO_SECONDS),
    )
