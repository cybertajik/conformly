"""Durable, platform-only state for conservative catalog imports."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from conformly.db.base import Base, UUIDPrimaryKeyMixin


class CatalogImportBatch(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "catalog_import_batches"
    __table_args__ = (
        UniqueConstraint("batch_key", name="uq_catalog_import_batch_key"),
        CheckConstraint(
            "status IN ('Accepted','Running','Reconciled','Interrupted','Cancelled','Aborted')",
            name="catalog_import_batch_status",
        ),
        CheckConstraint(
            "reconciled_inputs >= 0 AND reconciled_inputs <= total_inputs",
            name="catalog_import_batch_reconciled_bounds",
        ),
        CheckConstraint(
            "total_inputs > 0 AND total_inputs <= 5000", name="catalog_import_batch_total_bounds"
        ),
        CheckConstraint(
            "length(batch_fingerprint) = 32", name="catalog_import_batch_fingerprint_32"
        ),
        CheckConstraint(
            "length(payload_digest) = 32", name="catalog_import_batch_payload_digest_32"
        ),
    )

    batch_key: Mapped[str] = mapped_column(String(128), nullable=False)
    batch_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), server_default="Accepted", nullable=False)
    total_inputs: Mapped[int] = mapped_column(Integer, nullable=False)
    reconciled_inputs: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    payload_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CatalogImportInput(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "catalog_import_inputs"
    __table_args__ = (
        UniqueConstraint("batch_id", "sequence", name="uq_catalog_import_input_seq"),
        UniqueConstraint(
            "batch_id", "origin_namespace", "origin_id", name="uq_catalog_import_input_origin"
        ),
        CheckConstraint(
            "input_type IN ('Requirement','CommonControl','Mapping','Pack','PackMembership','EvidenceRequirement','AssessmentProcedure')",
            name="catalog_import_input_type",
        ),
        CheckConstraint(
            "disposition IN ('Pending','ImportedDraft','ReusedExact','NeedsPermission','NeedsSource','NeedsMappingReview','NeedsConflictReview','NeedsDependency','DeferredByScope','Rejected')",
            name="catalog_import_input_disposition",
        ),
        CheckConstraint(
            "target_entity_type IS NULL OR target_entity_type IN ('RequirementVersion','ControlVersion','MappingVersion','PackVersion','PackMembership','EvidenceRequirementVersion','AssessmentProcedureVersion')",
            name="catalog_import_input_target_type",
        ),
        CheckConstraint(
            "length(input_fingerprint) = 32", name="catalog_import_input_fingerprint_32"
        ),
        CheckConstraint(
            "target_digest IS NULL OR length(target_digest) = 32",
            name="catalog_import_input_target_digest_32",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 3", name="catalog_import_input_attempt_bounds"
        ),
    )

    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_import_batches.id", ondelete="RESTRICT"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    input_type: Mapped[str] = mapped_column(String(32), nullable=False)
    origin_namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_id: Mapped[str] = mapped_column(String(128), nullable=False)
    input_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    disposition: Mapped[str] = mapped_column(String(32), server_default="Pending", nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_digest: Mapped[bytes | None] = mapped_column(LargeBinary(32), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CatalogImportReuseLedger(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "catalog_import_reuse_ledger"
    __table_args__ = (
        UniqueConstraint(
            "origin_namespace",
            "origin_id",
            "adapter_version",
            name="uq_catalog_import_reuse_origin",
        ),
        CheckConstraint(
            "target_entity_type IN ('RequirementVersion','ControlVersion','MappingVersion','PackVersion','EvidenceRequirementVersion','AssessmentProcedureVersion')",
            name="catalog_import_reuse_target_type",
        ),
        CheckConstraint(
            "length(input_fingerprint) = 32", name="catalog_import_reuse_fingerprint_32"
        ),
        CheckConstraint("length(target_digest) = 32", name="catalog_import_reuse_digest_32"),
        CheckConstraint("target_revision > 0", name="catalog_import_reuse_revision_positive"),
    )

    origin_namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_id: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_version_id: Mapped[UUID] = mapped_column(nullable=False)
    target_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    target_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogImportReconciliationManifest(Base):
    __tablename__ = "catalog_import_reconciliation_manifests"
    __table_args__ = (
        CheckConstraint("length(manifest_hash) = 32", name="catalog_import_manifest_hash_32"),
        CheckConstraint(
            "reconciled_inputs = total_inputs", name="catalog_import_manifest_counts_match"
        ),
    )

    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_import_batches.id", ondelete="RESTRICT"), primary_key=True
    )
    manifest_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    total_inputs: Mapped[int] = mapped_column(Integer, nullable=False)
    reconciled_inputs: Mapped[int] = mapped_column(Integer, nullable=False)
    counts_by_disposition: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    sealed_by_actor_id: Mapped[UUID] = mapped_column(nullable=False)
    sealed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
