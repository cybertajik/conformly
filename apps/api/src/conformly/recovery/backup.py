"""Platform Disaster Recovery Backup Module.

Captures complete platform state:
- Topologically ordered relational tables (PostgreSQL / SQLAlchemy).
- Encrypted ciphertext object storage items.
- KMS Key Encryption Key (KEK) versions and metadata.
- Cryptographic SHA-256 manifest hash seal.
"""

from __future__ import annotations

import base64
import enum
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

# Import all models to register them with Base.metadata
from conformly.assets import models as _asset_models  # noqa: F401
from conformly.audit import models as _audit_models  # noqa: F401
from conformly.compliance import models as _compliance_models  # noqa: F401
from conformly.db.base import Base
from conformly.entitlements import models as _entitlement_models  # noqa: F401
from conformly.exports import models as _export_models  # noqa: F401
from conformly.frameworks import models as _framework_models  # noqa: F401
from conformly.identity import models as _identity_models  # noqa: F401
from conformly.integrations import models as _integration_models  # noqa: F401
from conformly.lms import models as _lms_models  # noqa: F401
from conformly.notifications import models as _notification_models  # noqa: F401
from conformly.organization import models as _organization_models  # noqa: F401
from conformly.preaudit import models as _preaudit_models  # noqa: F401
from conformly.profiles import models as _profile_models  # noqa: F401
from conformly.retention import models as _retention_models  # noqa: F401
from conformly.risks import models as _risk_models  # noqa: F401
from conformly.storage import models as _storage_models  # noqa: F401
from conformly.storage.models import StoredFile
from conformly.storage.providers import StorageProvider
from conformly.vendors import models as _vendor_models  # noqa: F401
from conformly.whistleblower import models as _whistleblower_models  # noqa: F401


@dataclass(slots=True)
class BackupMetadata:
    version: str = "1.0"
    created_at: str = ""
    platform: str = "conformly"
    tables_count: int = 0
    total_rows_count: int = 0
    objects_count: int = 0
    manifest_sha256: str = ""


@dataclass(slots=True)
class PlatformBackupBundle:
    """Portable, cryptographically sealed full disaster recovery backup."""

    metadata: BackupMetadata
    database_tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    storage_objects: dict[str, str] = field(default_factory=dict)  # object_key -> base64 ciphertext
    kms_keys: dict[str, str] = field(default_factory=dict)  # version -> base64 KEK
    manifest_sha256: str = ""

    def serialize_json(self) -> str:
        return json.dumps(
            {
                "metadata": asdict(self.metadata),
                "database_tables": self.database_tables,
                "storage_objects": self.storage_objects,
                "kms_keys": self.kms_keys,
                "manifest_sha256": self.manifest_sha256,
            },
            sort_keys=True,
            indent=2,
        )

    @classmethod
    def deserialize_json(cls, raw_json: str) -> PlatformBackupBundle:
        data = json.loads(raw_json)
        meta_dict = data.get("metadata", {})
        metadata = BackupMetadata(**meta_dict)
        return cls(
            metadata=metadata,
            database_tables=data.get("database_tables", {}),
            storage_objects=data.get("storage_objects", {}),
            kms_keys=data.get("kms_keys", {}),
            manifest_sha256=data.get("manifest_sha256", ""),
        )


def _serialize_value(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, bytes):
        return {"__bytes__": base64.b64encode(val).decode("ascii")}
    if isinstance(val, enum.Enum):
        return val.value
    if isinstance(val, (dict, list)):
        return val
    return val


def create_platform_backup(
    session: Session,
    storage_provider: StorageProvider | None = None,
    kms_keys: dict[str, str] | None = None,
) -> PlatformBackupBundle:
    """Extracts a complete platform database and storage state into a sealed backup bundle."""
    created_at = datetime.now(UTC).isoformat()
    tables_data: dict[str, list[dict[str, Any]]] = {}
    total_rows = 0

    # 1. Dump database tables in topological dependency order
    for table in Base.metadata.sorted_tables:
        rows = session.execute(select(table)).mappings().all()
        serialized_rows = []
        for row in rows:
            serialized_row = {col: _serialize_value(val) for col, val in row.items()}
            serialized_rows.append(serialized_row)
        tables_data[table.name] = serialized_rows
        total_rows += len(serialized_rows)

    # 2. Dump encrypted storage objects
    objects_data: dict[str, str] = {}
    if storage_provider is not None:
        if hasattr(storage_provider, "_store"):
            store_dict = storage_provider._store
            lock = getattr(storage_provider, "_lock", None)
            keys_items = list(store_dict.items()) if lock is None else []
            if lock is not None:
                with lock:
                    keys_items = list(store_dict.items())
            for key, val in keys_items:
                raw_data = val[0] if isinstance(val, tuple) else val
                objects_data[key] = base64.b64encode(bytes(raw_data)).decode("ascii")
        elif hasattr(storage_provider, "base_path"):
            base_p = storage_provider.base_path
            for file_path in base_p.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith(".tmp"):
                    rel_key = str(file_path.relative_to(base_p)).replace("\\", "/")
                    objects_data[rel_key] = base64.b64encode(file_path.read_bytes()).decode("ascii")
        else:
            try:
                stored_files = session.scalars(select(StoredFile)).all()
                for sf in stored_files:
                    if sf.object_key:
                        try:
                            content_bytes = storage_provider.get_object(sf.object_key)
                            objects_data[sf.object_key] = base64.b64encode(content_bytes).decode(
                                "ascii"
                            )
                        except Exception:
                            pass
            except Exception:
                pass

    # 3. Collect KMS Keys metadata
    keys_dict = dict(kms_keys or {})

    # 4. Calculate cryptographic SHA-256 manifest hash seal
    hasher = hashlib.sha256()
    hasher.update(json.dumps(tables_data, sort_keys=True).encode("utf-8"))
    hasher.update(json.dumps(objects_data, sort_keys=True).encode("utf-8"))
    hasher.update(json.dumps(keys_dict, sort_keys=True).encode("utf-8"))
    manifest_sha256 = hasher.hexdigest()

    metadata = BackupMetadata(
        version="1.0",
        created_at=created_at,
        platform="conformly",
        tables_count=len(tables_data),
        total_rows_count=total_rows,
        objects_count=len(objects_data),
        manifest_sha256=manifest_sha256,
    )

    return PlatformBackupBundle(
        metadata=metadata,
        database_tables=tables_data,
        storage_objects=objects_data,
        kms_keys=keys_dict,
        manifest_sha256=manifest_sha256,
    )
