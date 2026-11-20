"""Dormant source metadata/history; migrations 0032/0033 deny runtime access."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    column,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.expression import ColumnElement

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CCKeyFormat(ColumnElement[bool]):
    inherit_cache = True

    def __init__(self, column: Any) -> None:
        self.column = column


@compiles(CCKeyFormat, "postgresql")
def compile_cc_key_format_pg(element: CCKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return f"{col} ~ '^CC-[A-Z]{{2,4}}-[0-9]{{3}}$'"


@compiles(CCKeyFormat, "sqlite")
def compile_cc_key_format_sqlite(element: CCKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return (
        f"({col} GLOB 'CC-[A-Z][A-Z]-[0-9][0-9][0-9]' OR "
        f"{col} GLOB 'CC-[A-Z][A-Z][A-Z]-[0-9][0-9][0-9]' OR "
        f"{col} GLOB 'CC-[A-Z][A-Z][A-Z][A-Z]-[0-9][0-9][0-9]')"
    )


class PackKeyFormat(ColumnElement[bool]):
    inherit_cache = True

    def __init__(self, column: Any) -> None:
        self.column = column


@compiles(PackKeyFormat, "postgresql")
def compile_pack_key_format_pg(element: PackKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return f"{col} ~ '^[A-Z0-9_-]{{3,64}}$'"


@compiles(PackKeyFormat, "sqlite")
def compile_pack_key_format_sqlite(element: PackKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return f"(length({col}) BETWEEN 3 AND 64 AND {col} NOT GLOB '*[^A-Z0-9_-]*')"


class ERKeyFormat(ColumnElement[bool]):
    inherit_cache = True

    def __init__(self, column: Any) -> None:
        self.column = column


@compiles(ERKeyFormat, "postgresql")
def compile_er_key_format_pg(element: ERKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return f"{col} ~ '^ER-[A-Z0-9_-]{{3,61}}$'"


@compiles(ERKeyFormat, "sqlite")
def compile_er_key_format_sqlite(element: ERKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return (
        f"(length({col}) BETWEEN 6 AND 64 AND {col} GLOB 'ER-*' AND "
        f"substr({col}, 4) NOT GLOB '*[^A-Z0-9_-]*')"
    )


class APKeyFormat(ColumnElement[bool]):
    inherit_cache = True

    def __init__(self, column: Any) -> None:
        self.column = column


@compiles(APKeyFormat, "postgresql")
def compile_ap_key_format_pg(element: APKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return f"{col} ~ '^AP-[A-Z0-9_-]{{3,61}}$'"


@compiles(APKeyFormat, "sqlite")
def compile_ap_key_format_sqlite(element: APKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return (
        f"(length({col}) BETWEEN 6 AND 64 AND {col} GLOB 'AP-*' AND "
        f"substr({col}, 4) NOT GLOB '*[^A-Z0-9_-]*')"
    )


class MetadataKeyFormat(ColumnElement[bool]):
    inherit_cache = True

    def __init__(self, column: Any) -> None:
        self.column = column


@compiles(MetadataKeyFormat, "postgresql")
def compile_metadata_key_format_pg(element: MetadataKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return f"{col} ~ '^[a-z][a-z0-9_]{{0,63}}$'"


@compiles(MetadataKeyFormat, "sqlite")
def compile_metadata_key_format_sqlite(element: MetadataKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return (
        f"(length({col}) BETWEEN 1 AND 64 AND "
        f"substr({col}, 1, 1) GLOB '[a-z]' AND "
        f"{col} NOT GLOB '*[^a-z0-9_]*')"
    )


class FactKeyFormat(ColumnElement[bool]):
    inherit_cache = True

    def __init__(self, column: Any) -> None:
        self.column = column


@compiles(FactKeyFormat, "postgresql")
def compile_fact_key_format_pg(element: FactKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return f"{col} ~ '^[a-z][a-z0-9_]{{2,63}}$'"


@compiles(FactKeyFormat, "sqlite")
def compile_fact_key_format_sqlite(element: FactKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return (
        f"(length({col}) BETWEEN 3 AND 64 AND "
        f"substr({col}, 1, 1) GLOB '[a-z]' AND "
        f"{col} NOT GLOB '*[^a-z0-9_]*')"
    )


class FactEnumValueCodeFormat(ColumnElement[bool]):
    inherit_cache = True

    def __init__(self, column: Any) -> None:
        self.column = column


@compiles(FactEnumValueCodeFormat, "postgresql")
def compile_fact_enum_value_code_format_pg(
    element: FactEnumValueCodeFormat, compiler: Any, **kw: Any
) -> str:
    col = compiler.process(element.column, **kw)
    return f"{col} ~ '^[a-z][a-z0-9_]{{0,63}}$'"


@compiles(FactEnumValueCodeFormat, "sqlite")
def compile_fact_enum_value_code_format_sqlite(
    element: FactEnumValueCodeFormat, compiler: Any, **kw: Any
) -> str:
    col = compiler.process(element.column, **kw)
    return (
        f"(length({col}) BETWEEN 1 AND 64 AND "
        f"substr({col}, 1, 1) GLOB '[a-z]' AND "
        f"{col} NOT GLOB '*[^a-z0-9_]*')"
    )


class CatalogPublisher(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_publishers"
    __table_args__ = (
        UniqueConstraint("publisher_key"),
        CheckConstraint("length(publisher_key) BETWEEN 1 AND 128", name="publisher_key_length"),
        CheckConstraint("length(name) BETWEEN 1 AND 1024", name="name_length"),
        CheckConstraint("status = 'Draft'", name="draft_only"),
    )

    publisher_key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)


class CatalogSourceProvenance(UUIDPrimaryKeyMixin, Base):
    """Immutable metadata observation, not source-use permission or stored content."""

    __tablename__ = "catalog_source_provenance"
    __table_args__ = (
        UniqueConstraint("source_version_id"),
        UniqueConstraint("id", "source_version_id", name="uq_catalog_provenance_id_version"),
        CheckConstraint("source_revision >= 1", name="positive_source_revision"),
        CheckConstraint("length(content_sha256) = 32", name="sha256_bytes"),
        CheckConstraint("content_size >= 0", name="nonnegative_size"),
        CheckConstraint("length(mime_type) BETWEEN 1 AND 255", name="mime_type_length"),
        CheckConstraint("length(locator) BETWEEN 1 AND 4096", name="locator_length"),
    )

    source_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_source_versions.id", ondelete="RESTRICT"), nullable=False
    )
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    locator: Mapped[str] = mapped_column(String(4096), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by_actor_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogSourcePermissionProposal(UUIDPrimaryKeyMixin, Base):
    """Append-only Draft proposal. An Allowed outcome is NOT an effective grant."""

    __tablename__ = "catalog_source_permission_proposals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["provenance_id", "source_version_id"],
            ["catalog_source_provenance.id", "catalog_source_provenance.source_version_id"],
            name="fk_catalog_permission_provenance_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "source_version_id",
            "use_case",
            "scope_key",
            "sequence",
            name="uq_catalog_permission_scope_sequence",
        ),
        UniqueConstraint(
            "id",
            "source_version_id",
            "use_case",
            "scope_key",
            "sequence",
            name="uq_catalog_permission_predecessor_identity",
        ),
        ForeignKeyConstraint(
            ["supersedes_id", "source_version_id", "use_case", "scope_key", "supersedes_sequence"],
            [
                "catalog_source_permission_proposals.id",
                "catalog_source_permission_proposals.source_version_id",
                "catalog_source_permission_proposals.use_case",
                "catalog_source_permission_proposals.scope_key",
                "catalog_source_permission_proposals.sequence",
            ],
            name="fk_catalog_permission_predecessor_context",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "use_case IN ('reference','store','excerpt','paraphrase','translate','map','ui','api','export','search','ai')",
            name="known_use_case",
        ),
        CheckConstraint("length(scope_key) BETWEEN 1 AND 128", name="scope_key_length"),
        CheckConstraint("proposed_outcome IN ('Unknown','Denied','Allowed')", name="known_outcome"),
        CheckConstraint("review_state = 'Draft'", name="draft_only"),
        CheckConstraint(
            "(conditions_state IN ('Unknown','None') AND conditions_reference IS NULL) OR "
            "(conditions_state = 'ExternalReference' AND conditions_reference IS NOT NULL)",
            name="conditions_shape",
        ),
        CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from",
            name="valid_time_order",
        ),
        CheckConstraint(
            "(sequence = 1 AND supersedes_id IS NULL AND supersedes_sequence IS NULL) OR "
            "(sequence > 1 AND supersedes_id IS NOT NULL AND supersedes_sequence IS NOT NULL "
            "AND supersedes_sequence >= 1 AND sequence = supersedes_sequence + 1)",
            name="successor_sequence",
        ),
    )

    source_version_id: Mapped[UUID] = mapped_column(nullable=False)
    provenance_id: Mapped[UUID] = mapped_column(nullable=False)
    use_case: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(nullable=True)
    supersedes_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposed_outcome: Mapped[str] = mapped_column(
        String(16), server_default="Unknown", nullable=False
    )
    review_state: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)
    conditions_state: Mapped[str] = mapped_column(
        String(32), server_default="Unknown", nullable=False
    )
    conditions_reference: Mapped[UUID | None] = mapped_column(nullable=True)
    evidence_reference: Mapped[UUID | None] = mapped_column(nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by_actor_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_sources"
    __table_args__ = (
        UniqueConstraint("publisher_id", "source_key"),
        CheckConstraint("length(source_key) BETWEEN 1 AND 128", name="source_key_length"),
        CheckConstraint("length(title) BETWEEN 1 AND 1024", name="title_length"),
        CheckConstraint("status = 'Draft'", name="draft_only"),
    )

    publisher_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_publishers.id", ondelete="RESTRICT"), nullable=False
    )
    source_key: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)


class CatalogSourceVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_source_versions"
    __table_args__ = (
        UniqueConstraint("source_id", "edition"),
        UniqueConstraint("id", "source_id", name="uq_catalog_source_versions_id_source"),
        ForeignKeyConstraint(
            ["predecessor_id", "source_id"],
            ["catalog_source_versions.id", "catalog_source_versions.source_id"],
            name="fk_catalog_source_versions_predecessor_lineage",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "predecessor_id IS NULL OR predecessor_id <> id", name="not_self_predecessor"
        ),
        CheckConstraint("length(edition) BETWEEN 1 AND 128", name="edition_length"),
        CheckConstraint(
            "language IS NULL OR length(language) BETWEEN 1 AND 35", name="language_length"
        ),
        CheckConstraint(
            "official_locator IS NULL OR length(official_locator) BETWEEN 1 AND 4096",
            name="official_locator_length",
        ),
        CheckConstraint("revision >= 1", name="positive_revision"),
        CheckConstraint("status = 'Draft'", name="draft_only"),
        CheckConstraint("length(content_digest) = 32", name="source_version_digest_32_bytes"),
        CheckConstraint(
            "digest_schema = 'catalog-draft-v1'", name="source_version_digest_schema_v1"
        ),
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="RESTRICT"), nullable=False
    )
    edition: Mapped[str] = mapped_column(String(128), nullable=False)
    predecessor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    language: Mapped[str | None] = mapped_column(String(35), nullable=True)
    official_locator: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)
    content_digest: Mapped[bytes] = mapped_column(
        LargeBinary,
        default=b"\x00" * 32,
        nullable=False,
    )
    digest_schema: Mapped[str] = mapped_column(
        String(64), server_default="catalog-draft-v1", nullable=False
    )


class CatalogRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stable requirement identity within one authoritative source lineage."""

    __tablename__ = "catalog_requirements"
    __table_args__ = (
        UniqueConstraint("source_id", "requirement_key", name="uq_catalog_requirements_source_key"),
        UniqueConstraint("id", "source_id", name="uq_catalog_requirements_id_source"),
        CheckConstraint("length(requirement_key) BETWEEN 1 AND 128", name="requirement_key_length"),
        CheckConstraint("status = 'Draft'", name="req_draft_only"),
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="RESTRICT"), nullable=False
    )
    requirement_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)


class CatalogRequirementVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable normalized meaning of a requirement at a specific SourceVersion."""

    __tablename__ = "catalog_requirement_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_id", "source_id"],
            ["catalog_requirements.id", "catalog_requirements.source_id"],
            name="fk_catalog_req_versions_requirement_lineage",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_version_id", "source_id"],
            ["catalog_source_versions.id", "catalog_source_versions.source_id"],
            name="fk_catalog_req_versions_source_version_lineage",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["predecessor_id", "requirement_id"],
            ["catalog_requirement_versions.id", "catalog_requirement_versions.requirement_id"],
            name="fk_catalog_req_versions_predecessor_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("requirement_id", "version_label", name="uq_catalog_req_versions_version"),
        UniqueConstraint(
            "id", "source_version_id", name="uq_catalog_req_versions_id_source_version"
        ),
        UniqueConstraint("id", "requirement_id", name="uq_catalog_req_versions_id_requirement"),
        CheckConstraint(
            "predecessor_id IS NULL OR predecessor_id <> id", name="not_self_predecessor_req"
        ),
        CheckConstraint("length(version_label) BETWEEN 1 AND 64", name="req_version_label_length"),
        CheckConstraint("revision >= 1", name="positive_req_revision"),
        CheckConstraint(
            "length(normalized_outcome) BETWEEN 1 AND 4096", name="normalized_outcome_length"
        ),
        CheckConstraint(
            "requirement_type IN ('mandatory', 'conditional', 'recommendation', 'prohibition', 'permission')",
            name="known_requirement_type",
        ),
        CheckConstraint("length(obligated_actor) BETWEEN 1 AND 64", name="obligated_actor_length"),
        CheckConstraint(
            "text_origin IN ('verbatim_source', 'authorized_excerpt', 'conformly_paraphrase', 'official_translation', 'reference_only')",
            name="known_text_origin",
        ),
        CheckConstraint(
            "customer_display_text IS NULL OR length(customer_display_text) BETWEEN 1 AND 4096",
            name="customer_display_text_length",
        ),
        CheckConstraint(
            "effective_from IS NULL OR effective_until IS NULL OR effective_until >= effective_from",
            name="req_effective_date_order",
        ),
        CheckConstraint("status = 'Draft'", name="req_version_draft_only"),
        CheckConstraint("length(content_digest) = 32", name="req_version_digest_32_bytes"),
        CheckConstraint("digest_schema = 'catalog-draft-v1'", name="req_version_digest_schema_v1"),
    )

    requirement_id: Mapped[UUID] = mapped_column(nullable=False)
    source_id: Mapped[UUID] = mapped_column(nullable=False)
    source_version_id: Mapped[UUID] = mapped_column(nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    predecessor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    normalized_outcome: Mapped[str] = mapped_column(String(4096), nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    obligated_actor: Mapped[str] = mapped_column(String(64), nullable=False)
    text_origin: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_display_text: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)
    content_digest: Mapped[bytes] = mapped_column(
        LargeBinary,
        default=b"\x00" * 32,
        nullable=False,
    )
    digest_schema: Mapped[str] = mapped_column(
        String(64), server_default="catalog-draft-v1", nullable=False
    )


class CatalogRequirementSourceReference(UUIDPrimaryKeyMixin, Base):
    """Normalized child locator relation. At least one required per RequirementVersion."""

    __tablename__ = "catalog_requirement_source_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_version_id", "source_version_id"],
            ["catalog_requirement_versions.id", "catalog_requirement_versions.source_version_id"],
            name="fk_catalog_req_source_ref_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "requirement_version_id",
            "locator_kind",
            "locator_value",
            name="uq_catalog_req_source_ref_value",
        ),
        UniqueConstraint(
            "requirement_version_id",
            "sequence",
            name="uq_catalog_req_source_ref_sequence",
        ),
        CheckConstraint(
            "locator_kind IN ('article', 'section', 'paragraph', 'clause', 'criterion', 'table', 'annex', 'page')",
            name="known_locator_kind",
        ),
        CheckConstraint("length(locator_value) BETWEEN 1 AND 512", name="locator_value_length"),
        CheckConstraint("sequence >= 1", name="positive_ref_sequence"),
    )

    requirement_version_id: Mapped[UUID] = mapped_column(nullable=False)
    source_version_id: Mapped[UUID] = mapped_column(nullable=False)
    locator_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    locator_value: Mapped[str] = mapped_column(String(512), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogCommonControl(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stable identity for technology-neutral Conformly Common Control."""

    __tablename__ = "catalog_common_controls"
    __table_args__ = (
        UniqueConstraint("control_key", name="uq_catalog_common_controls_key"),
        UniqueConstraint("id", "control_key", name="uq_catalog_common_controls_id_key"),
        CheckConstraint(CCKeyFormat(column("control_key")), name="cc_key_format"),
        CheckConstraint("length(domain) BETWEEN 1 AND 64", name="domain_length"),
        CheckConstraint("status = 'Draft'", name="ctrl_draft_only"),
    )

    control_key: Mapped[str] = mapped_column(String(32), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)


class CatalogControlVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable content version of a Common Control."""

    __tablename__ = "catalog_control_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["control_id"],
            ["catalog_common_controls.id"],
            name="fk_catalog_control_versions_control",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["predecessor_id", "control_id"],
            ["catalog_control_versions.id", "catalog_control_versions.control_id"],
            name="fk_catalog_control_versions_predecessor_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("control_id", "version_label", name="uq_catalog_control_versions_version"),
        UniqueConstraint("id", "control_id", name="uq_catalog_control_versions_id_control"),
        CheckConstraint(
            "predecessor_id IS NULL OR predecessor_id <> id", name="not_self_predecessor_ctrl"
        ),
        CheckConstraint("length(version_label) BETWEEN 1 AND 64", name="ctrl_version_label_length"),
        CheckConstraint("revision >= 1", name="positive_ctrl_revision"),
        CheckConstraint("length(title) BETWEEN 1 AND 512", name="control_title_length"),
        CheckConstraint("length(objective) BETWEEN 1 AND 4096", name="control_objective_length"),
        CheckConstraint(
            "guidance IS NULL OR length(guidance) BETWEEN 1 AND 4096",
            name="control_guidance_length",
        ),
        CheckConstraint(
            "control_type IN ('governance', 'preventive', 'detective', 'corrective', 'compensating')",
            name="known_control_type",
        ),
        CheckConstraint("length(frequency) BETWEEN 1 AND 64", name="control_frequency_length"),
        CheckConstraint(
            "automation_level IN ('manual', 'partially_automated', 'automated')",
            name="known_automation_level",
        ),
        CheckConstraint("length(suggested_owner_role) BETWEEN 1 AND 64", name="owner_role_length"),
        CheckConstraint(
            "assurance_level IN ('foundational', 'conditional', 'enhanced')",
            name="known_assurance_level",
        ),
        CheckConstraint("tags_state IN ('Unknown', 'None', 'Provided')", name="tags_state_enum"),
        CheckConstraint(
            "(tags_state IN ('Unknown', 'None') AND tags IS NULL) OR (tags_state = 'Provided' AND tags IS NOT NULL)",
            name="tags_shape",
        ),
        CheckConstraint("status = 'Draft'", name="ctrl_version_draft_only"),
        CheckConstraint("length(content_digest) = 32", name="ctrl_version_digest_32_bytes"),
        CheckConstraint("digest_schema = 'catalog-draft-v1'", name="ctrl_version_digest_schema_v1"),
    )

    control_id: Mapped[UUID] = mapped_column(nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    predecessor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    objective: Mapped[str] = mapped_column(String(4096), nullable=False)
    guidance: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    control_type: Mapped[str] = mapped_column(String(32), nullable=False)
    frequency: Mapped[str] = mapped_column(String(64), nullable=False)
    automation_level: Mapped[str] = mapped_column(String(32), nullable=False)
    suggested_owner_role: Mapped[str] = mapped_column(String(64), nullable=False)
    assurance_level: Mapped[str] = mapped_column(String(32), nullable=False)
    tags_state: Mapped[str] = mapped_column(String(32), server_default="Unknown", nullable=False)
    tags: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)
    content_digest: Mapped[bytes] = mapped_column(
        LargeBinary,
        default=b"\x00" * 32,
        nullable=False,
    )
    digest_schema: Mapped[str] = mapped_column(
        String(64), server_default="catalog-draft-v1", nullable=False
    )


class CatalogPack(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stable identity for curated Framework Pack."""

    __tablename__ = "catalog_packs"
    __table_args__ = (
        UniqueConstraint("pack_key", name="uq_catalog_packs_key"),
        UniqueConstraint("id", "pack_key", name="uq_catalog_packs_id_key"),
        CheckConstraint(PackKeyFormat(column("pack_key")), name="pack_key_format"),
        CheckConstraint("length(pack_key) BETWEEN 1 AND 64", name="pack_key_length"),
        CheckConstraint("length(name) BETWEEN 1 AND 256", name="pack_name_length"),
        CheckConstraint(
            "pack_type IN ('regulatory', 'certification', 'contractual', 'baseline')",
            name="known_pack_type",
        ),
        CheckConstraint(
            "jurisdiction IS NULL OR length(jurisdiction) BETWEEN 1 AND 64",
            name="jurisdiction_length",
        ),
        CheckConstraint("status = 'Draft'", name="pack_draft_only"),
    )

    pack_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    pack_type: Mapped[str] = mapped_column(String(32), nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)


class CatalogPackVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable versioned composition of a Framework Pack."""

    __tablename__ = "catalog_pack_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["pack_id"],
            ["catalog_packs.id"],
            name="fk_catalog_pack_versions_pack",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["predecessor_id", "pack_id"],
            ["catalog_pack_versions.id", "catalog_pack_versions.pack_id"],
            name="fk_catalog_pack_versions_predecessor_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("pack_id", "version_label", name="uq_catalog_pack_versions_label"),
        UniqueConstraint("id", "pack_id", name="uq_catalog_pack_versions_id_pack"),
        CheckConstraint(
            "predecessor_id IS NULL OR predecessor_id <> id", name="not_self_predecessor_pack"
        ),
        CheckConstraint("length(version_label) BETWEEN 1 AND 64", name="pack_version_label_length"),
        CheckConstraint("revision >= 1", name="positive_pack_revision"),
        CheckConstraint("length(title) BETWEEN 1 AND 512", name="pack_title_length"),
        CheckConstraint(
            "description IS NULL OR length(description) BETWEEN 1 AND 4096",
            name="pack_description_length",
        ),
        CheckConstraint(
            "audience IS NULL OR length(audience) BETWEEN 1 AND 256",
            name="pack_audience_length",
        ),
        CheckConstraint(
            "effective_from IS NULL OR effective_until IS NULL OR effective_until >= effective_from",
            name="pack_effective_dates_order",
        ),
        CheckConstraint(
            "release_notes IS NULL OR length(release_notes) BETWEEN 1 AND 4096",
            name="pack_release_notes_length",
        ),
        CheckConstraint("status = 'Draft'", name="pack_version_draft_only"),
        CheckConstraint("length(content_digest) = 32", name="pack_version_digest_32_bytes"),
        CheckConstraint("digest_schema = 'catalog-draft-v1'", name="pack_version_digest_schema_v1"),
    )

    pack_id: Mapped[UUID] = mapped_column(nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    predecessor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    audience: Mapped[str | None] = mapped_column(String(256), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    release_notes: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)
    content_digest: Mapped[bytes] = mapped_column(
        LargeBinary,
        default=b"\x00" * 32,
        nullable=False,
    )
    digest_schema: Mapped[str] = mapped_column(
        String(64), server_default="catalog-draft-v1", nullable=False
    )


class CatalogPackMembership(UUIDPrimaryKeyMixin, Base):
    """Append-only membership relation between PackVersion and RequirementVersion."""

    __tablename__ = "catalog_pack_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["pack_version_id"],
            ["catalog_pack_versions.id"],
            name="fk_catalog_pack_memberships_pack_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requirement_version_id"],
            ["catalog_requirement_versions.id"],
            name="fk_catalog_pack_memberships_req_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "pack_version_id",
            "requirement_version_id",
            name="uq_catalog_pack_memberships_pair",
        ),
        UniqueConstraint(
            "pack_version_id",
            "sequence",
            name="uq_catalog_pack_memberships_seq",
        ),
        CheckConstraint("sequence >= 1", name="positive_pack_membership_sequence"),
        CheckConstraint(
            "inclusion_conditions_state IN ('Unknown', 'None', 'Provided')",
            name="inclusion_conditions_state_enum",
        ),
        CheckConstraint(
            "(inclusion_conditions_state IN ('Unknown', 'None') AND inclusion_conditions IS NULL) OR (inclusion_conditions_state = 'Provided' AND inclusion_conditions IS NOT NULL)",
            name="inclusion_conditions_shape",
        ),
        CheckConstraint(
            "inclusion_conditions IS NULL OR length(inclusion_conditions) BETWEEN 1 AND 2048",
            name="inclusion_conditions_length",
        ),
        CheckConstraint("requirement_version_revision > 0", name="pack_mem_req_revision_positive"),
        CheckConstraint(
            "length(requirement_version_digest) = 32", name="pack_mem_req_digest_32_bytes"
        ),
    )

    pack_version_id: Mapped[UUID] = mapped_column(nullable=False)
    requirement_version_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    inclusion_conditions_state: Mapped[str] = mapped_column(
        String(32), server_default="Unknown", nullable=False
    )
    inclusion_conditions: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    requirement_version_revision: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )
    requirement_version_digest: Mapped[bytes] = mapped_column(
        LargeBinary, default=b"\x00" * 32, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogRequirementControlMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stable identity for mapping relationship between Requirement and Common Control lineages."""

    __tablename__ = "catalog_requirement_control_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_id"],
            ["catalog_requirements.id"],
            name="fk_catalog_req_ctrl_mappings_requirement",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["control_id"],
            ["catalog_common_controls.id"],
            name="fk_catalog_req_ctrl_mappings_control",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("mapping_key", name="uq_catalog_req_ctrl_mappings_key"),
        UniqueConstraint(
            "requirement_id",
            "control_id",
            name="uq_catalog_req_ctrl_mappings_pair",
        ),
        UniqueConstraint(
            "id",
            "requirement_id",
            "control_id",
            name="uq_catalog_req_ctrl_mappings_composite",
        ),
        CheckConstraint("length(mapping_key) BETWEEN 1 AND 128", name="mapping_key_length"),
        CheckConstraint("status = 'Draft'", name="mapping_draft_only"),
    )

    mapping_key: Mapped[str] = mapped_column(String(128), nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(nullable=False)
    control_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)


class CatalogMappingVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable semantic mapping specification between exact RequirementVersion and ControlVersion."""

    __tablename__ = "catalog_mapping_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mapping_id", "requirement_id", "control_id"],
            [
                "catalog_requirement_control_mappings.id",
                "catalog_requirement_control_mappings.requirement_id",
                "catalog_requirement_control_mappings.control_id",
            ],
            name="fk_catalog_mapping_versions_lineage",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id"],
            [
                "catalog_requirement_versions.id",
                "catalog_requirement_versions.requirement_id",
            ],
            name="fk_catalog_mapping_versions_req_lineage",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["control_version_id", "control_id"],
            [
                "catalog_control_versions.id",
                "catalog_control_versions.control_id",
            ],
            name="fk_catalog_mapping_versions_ctrl_lineage",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["predecessor_id", "mapping_id"],
            [
                "catalog_mapping_versions.id",
                "catalog_mapping_versions.mapping_id",
            ],
            name="fk_catalog_mapping_versions_predecessor_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("mapping_id", "version_label", name="uq_catalog_mapping_versions_label"),
        UniqueConstraint(
            "requirement_version_id",
            "control_version_id",
            "version_label",
            name="uq_catalog_mapping_versions_endpoints",
        ),
        UniqueConstraint("id", "mapping_id", name="uq_catalog_mapping_versions_id_mapping"),
        CheckConstraint(
            "predecessor_id IS NULL OR predecessor_id <> id",
            name="not_self_predecessor_mapping",
        ),
        CheckConstraint(
            "length(version_label) BETWEEN 1 AND 64",
            name="mapping_version_label_length",
        ),
        CheckConstraint("revision >= 1", name="positive_mapping_revision"),
        CheckConstraint(
            "mapping_type IN ('Full', 'Partial', 'Supporting')",
            name="known_mapping_type",
        ),
        CheckConstraint("length(rationale) BETWEEN 1 AND 4096", name="mapping_rationale_length"),
        CheckConstraint(
            "covered_dimensions IS NULL OR length(covered_dimensions) BETWEEN 1 AND 2048",
            name="covered_dimensions_length",
        ),
        CheckConstraint(
            "excluded_dimensions IS NULL OR length(excluded_dimensions) BETWEEN 1 AND 2048",
            name="excluded_dimensions_length",
        ),
        CheckConstraint(
            "(mapping_type = 'Partial' AND excluded_dimensions IS NOT NULL) OR (mapping_type != 'Partial')",
            name="partial_mapping_excluded_dims_required",
        ),
        CheckConstraint(
            "conditions IS NULL OR length(conditions) BETWEEN 1 AND 2048",
            name="mapping_conditions_length",
        ),
        CheckConstraint(
            "source_basis IN ('direct_text', 'authoritative_guidance', 'expert_analysis', 'regulatory_precedent')",
            name="known_source_basis",
        ),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="known_mapping_confidence",
        ),
        CheckConstraint(
            "review_state IN ('Draft', 'InReview', 'Approved', 'Rejected')",
            name="known_review_state",
        ),
        CheckConstraint("status = 'Draft'", name="mapping_version_draft_only"),
        CheckConstraint("length(content_digest) = 32", name="map_version_digest_32_bytes"),
        CheckConstraint("digest_schema = 'catalog-draft-v1'", name="map_version_digest_schema_v1"),
        CheckConstraint("requirement_version_revision > 0", name="map_req_revision_positive"),
        CheckConstraint("length(requirement_version_digest) = 32", name="map_req_digest_32_bytes"),
        CheckConstraint("control_version_revision > 0", name="map_ctrl_revision_positive"),
        CheckConstraint("length(control_version_digest) = 32", name="map_ctrl_digest_32_bytes"),
    )

    mapping_id: Mapped[UUID] = mapped_column(nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(nullable=False)
    control_id: Mapped[UUID] = mapped_column(nullable=False)
    requirement_version_id: Mapped[UUID] = mapped_column(nullable=False)
    control_version_id: Mapped[UUID] = mapped_column(nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    predecessor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    mapping_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(String(4096), nullable=False)
    covered_dimensions: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    excluded_dimensions: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    conditions: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_basis: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    review_state: Mapped[str] = mapped_column(String(32), server_default="Draft", nullable=False)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)
    content_digest: Mapped[bytes] = mapped_column(
        LargeBinary,
        default=b"\x00" * 32,
        nullable=False,
    )
    digest_schema: Mapped[str] = mapped_column(
        String(64), server_default="catalog-draft-v1", nullable=False
    )
    requirement_version_revision: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )
    requirement_version_digest: Mapped[bytes] = mapped_column(
        LargeBinary,
        default=b"\x00" * 32,
        nullable=False,
    )
    control_version_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    control_version_digest: Mapped[bytes] = mapped_column(
        LargeBinary, default=b"\x00" * 32, nullable=False
    )


class CatalogSourcePermissionGuard(Base):
    """Locks and serializes permission decisions and source-dependent mutations."""

    __tablename__ = "catalog_source_permission_guards"
    __table_args__ = (CheckConstraint("revision > 0", name="guard_revision_positive"),)

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="RESTRICT"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(BigInteger, server_default=text("1"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogSourcePermissionDecision(UUIDPrimaryKeyMixin, Base):
    """Append-only, reviewed effective source-use permission decision."""

    __tablename__ = "catalog_source_permission_decisions"
    __table_args__ = (
        UniqueConstraint(
            "source_version_id",
            "use_case",
            "scope_key",
            "sequence",
            name="uq_decision_version_use_scope_seq",
        ),
        CheckConstraint("sequence > 0", name="decision_sequence_positive"),
        CheckConstraint("decision IN ('Allowed', 'Denied')", name="known_decision"),
        CheckConstraint("conditions_state = 'None'", name="conditions_state_none"),
        CheckConstraint(
            "use_case IN ('reference', 'store', 'excerpt', 'paraphrase', 'map')",
            name="known_use_case",
        ),
        CheckConstraint("length(scope_key) BETWEEN 1 AND 128", name="scope_key_length"),
        CheckConstraint("length(evidence_reference) > 0", name="evidence_reference_nonempty"),
        CheckConstraint("policy_version = 'catalog-permission-v1'", name="known_policy_version"),
        CheckConstraint("guard_revision > 0", name="decision_guard_revision_positive"),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_window_order"
        ),
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="RESTRICT"), nullable=False
    )
    source_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_source_versions.id", ondelete="RESTRICT"), nullable=False
    )
    proposal_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_source_permission_proposals.id", ondelete="RESTRICT"), nullable=False
    )
    use_case: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    predecessor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_source_permission_decisions.id", ondelete="RESTRICT"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    conditions_state: Mapped[str] = mapped_column(String(16), server_default="None", nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_actor_id: Mapped[UUID] = mapped_column(nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(
        String(64), server_default="catalog-permission-v1", nullable=False
    )
    guard_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogAuditHead(Base):
    """Current head state for a serialized catalog audit chain."""

    __tablename__ = "catalog_audit_heads"
    __table_args__ = (
        CheckConstraint("current_sequence >= 0", name="head_current_sequence_nonnegative"),
        CheckConstraint("length(head_hash) = 32", name="head_hash_32_bytes"),
    )

    chain_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    current_sequence: Mapped[int] = mapped_column(
        BigInteger, server_default=text("0"), nullable=False
    )
    head_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogAuditEvent(UUIDPrimaryKeyMixin, Base):
    """Dedicated serialized append-only catalog audit journal."""

    __tablename__ = "catalog_audit_events"
    __table_args__ = (
        UniqueConstraint("chain_key", "sequence", name="uq_audit_chain_sequence"),
        CheckConstraint("sequence > 0", name="audit_sequence_positive"),
        CheckConstraint("length(previous_hash) = 32", name="audit_prev_hash_32_bytes"),
        CheckConstraint("length(event_hash) = 32", name="audit_event_hash_32_bytes"),
        CheckConstraint("outcome IN ('Success', 'Denied', 'Conflict')", name="known_audit_outcome"),
        CheckConstraint("length(request_key) BETWEEN 1 AND 128", name="audit_request_key_length"),
    )

    chain_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("catalog_audit_heads.chain_key", ondelete="RESTRICT"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    previous_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    event_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB(), "postgresql"),
        server_default=text("'{}'"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogEventIntent(UUIDPrimaryKeyMixin, Base):
    """Append-only transactionally recorded catalog event intent."""

    __tablename__ = "catalog_event_intents"
    __table_args__ = (
        UniqueConstraint("request_key", "event_kind", name="uq_catalog_intent_request_event"),
        CheckConstraint("revision > 0", name="intent_revision_positive"),
        CheckConstraint("length(content_digest) = 32", name="intent_digest_32_bytes"),
        CheckConstraint("length(request_key) BETWEEN 1 AND 128", name="intent_request_key_length"),
    )

    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_digest: Mapped[bytes] = mapped_column(
        LargeBinary,
        default=b"\x00" * 32,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogMutationReceipt(UUIDPrimaryKeyMixin, Base):
    """Append-only mutation receipt for idempotent exact retries."""

    __tablename__ = "catalog_mutation_receipts"
    __table_args__ = (
        UniqueConstraint(
            "actor_id", "operation", "request_key", name="uq_receipt_actor_op_request"
        ),
        CheckConstraint("length(request_fingerprint) = 32", name="receipt_fingerprint_32_bytes"),
        CheckConstraint("length(result_digest) = 32", name="receipt_digest_32_bytes"),
        CheckConstraint("result_revision > 0", name="receipt_result_revision_positive"),
        CheckConstraint("length(request_key) BETWEEN 1 AND 128", name="receipt_request_key_length"),
    )

    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    result_id: Mapped[UUID] = mapped_column(nullable=False)
    result_type: Mapped[str] = mapped_column(String(64), nullable=False)
    result_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    result_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogEvidenceRequirementVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable content version of a Common Control evidence requirement."""

    __tablename__ = "catalog_evidence_requirement_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["control_version_id", "control_id"],
            ["catalog_control_versions.id", "catalog_control_versions.control_id"],
            name="fk_catalog_er_versions_control_version_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id", "control_version_id", name="uq_catalog_er_versions_id_control_version"
        ),
        UniqueConstraint(
            "control_version_id",
            "requirement_key",
            name="uq_catalog_er_versions_control_version_key",
        ),
        UniqueConstraint(
            "control_version_id",
            "sequence",
            name="uq_catalog_er_versions_control_version_seq",
        ),
        CheckConstraint(ERKeyFormat(column("requirement_key")), name="er_key_format"),
        CheckConstraint("length(requirement_key) BETWEEN 6 AND 64", name="er_key_length"),
        CheckConstraint("sequence > 0", name="er_sequence_positive"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 512", name="er_title_length"),
        CheckConstraint(
            "frequency IN ('continuous', 'event_driven', 'monthly', 'quarterly', 'semiannual', 'annual', 'custom')",
            name="known_er_frequency",
        ),
        CheckConstraint(
            "(frequency = 'custom' AND custom_frequency IS NOT NULL AND length(trim(custom_frequency)) BETWEEN 1 AND 256) "
            "OR (frequency <> 'custom' AND custom_frequency IS NULL)",
            name="er_frequency_shape",
        ),
        CheckConstraint(
            "scope_state IN ('All', 'Conditional')",
            name="known_er_scope_state",
        ),
        CheckConstraint(
            "(scope_state = 'Conditional' AND scope_guidance IS NOT NULL AND length(trim(scope_guidance)) BETWEEN 1 AND 2048) "
            "OR (scope_state = 'All' AND scope_guidance IS NULL)",
            name="er_scope_shape",
        ),
        CheckConstraint(
            "assurance_purpose IN ('design', 'implementation', 'operating_effectiveness', 'combined')",
            name="known_assurance_purpose",
        ),
        CheckConstraint(
            "validity_rule IN ('point_in_time', 'period_coverage', 'continuous', 'event_driven')",
            name="known_validity_rule",
        ),
        CheckConstraint(
            "(validity_rule = 'point_in_time' AND max_age_days IS NOT NULL AND max_age_days BETWEEN 1 AND 3660) "
            "OR (validity_rule <> 'point_in_time' AND max_age_days IS NULL)",
            name="er_validity_shape",
        ),
        CheckConstraint(
            "missing_data_behavior = 'requires_human_review'",
            name="er_missing_data_behavior",
        ),
        CheckConstraint(
            "guidance IS NULL OR length(trim(guidance)) BETWEEN 1 AND 4096",
            name="er_guidance_length",
        ),
        CheckConstraint("status = 'Draft'", name="er_draft_only"),
        CheckConstraint("length(content_digest) = 32", name="er_digest_32_bytes"),
        CheckConstraint(
            "digest_schema = 'catalog-assurance-draft-v1'", name="er_known_digest_schema"
        ),
    )

    control_version_id: Mapped[UUID] = mapped_column(nullable=False)
    control_id: Mapped[UUID] = mapped_column(nullable=False)
    requirement_key: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    custom_frequency: Mapped[str | None] = mapped_column(String(256), nullable=True)
    scope_state: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_guidance: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    assurance_purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    validity_rule: Mapped[str] = mapped_column(String(32), nullable=False)
    max_age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    missing_data_behavior: Mapped[str] = mapped_column(
        String(32), server_default="requires_human_review", nullable=False
    )
    guidance: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)
    content_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    digest_schema: Mapped[str] = mapped_column(
        String(64), server_default="catalog-assurance-draft-v1", nullable=False
    )


class CatalogEvidenceRequirementArtifactType(UUIDPrimaryKeyMixin, Base):
    """Ordered controlled artifact expectation for an evidence requirement."""

    __tablename__ = "catalog_evidence_requirement_artifact_types"
    __table_args__ = (
        ForeignKeyConstraint(
            ["evidence_requirement_version_id", "control_version_id"],
            [
                "catalog_evidence_requirement_versions.id",
                "catalog_evidence_requirement_versions.control_version_id",
            ],
            name="fk_catalog_er_art_types_er_version_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "evidence_requirement_version_id",
            "sequence",
            name="uq_catalog_er_art_types_version_seq",
        ),
        UniqueConstraint(
            "evidence_requirement_version_id",
            "artifact_type",
            name="uq_catalog_er_art_types_version_type",
        ),
        CheckConstraint("sequence BETWEEN 1 AND 16", name="er_artifact_type_sequence_bounds"),
        CheckConstraint(
            "artifact_type IN ('document', 'record', 'configuration', 'log', 'ticket', 'report', 'attestation', 'observation', 'interview', 'other')",
            name="known_er_artifact_type",
        ),
    )

    evidence_requirement_version_id: Mapped[UUID] = mapped_column(nullable=False)
    control_version_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogEvidenceRequirementMetadataKey(UUIDPrimaryKeyMixin, Base):
    """Ordered required metadata name for an evidence requirement."""

    __tablename__ = "catalog_evidence_requirement_metadata_keys"
    __table_args__ = (
        ForeignKeyConstraint(
            ["evidence_requirement_version_id", "control_version_id"],
            [
                "catalog_evidence_requirement_versions.id",
                "catalog_evidence_requirement_versions.control_version_id",
            ],
            name="fk_catalog_er_meta_keys_er_version_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "evidence_requirement_version_id",
            "sequence",
            name="uq_catalog_er_meta_keys_version_seq",
        ),
        UniqueConstraint(
            "evidence_requirement_version_id",
            "metadata_key",
            name="uq_catalog_er_meta_keys_version_key",
        ),
        CheckConstraint("sequence BETWEEN 1 AND 32", name="er_metadata_key_sequence_bounds"),
        CheckConstraint(MetadataKeyFormat(column("metadata_key")), name="er_metadata_key_format"),
        CheckConstraint("length(metadata_key) BETWEEN 1 AND 64", name="er_metadata_key_length"),
    )

    evidence_requirement_version_id: Mapped[UUID] = mapped_column(nullable=False)
    control_version_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogAssessmentProcedureVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable content version of a Common Control assessment procedure."""

    __tablename__ = "catalog_assessment_procedure_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["control_version_id", "control_id"],
            ["catalog_control_versions.id", "catalog_control_versions.control_id"],
            name="fk_catalog_ap_versions_control_version_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id", "control_version_id", name="uq_catalog_ap_versions_id_control_version"
        ),
        UniqueConstraint(
            "control_version_id",
            "procedure_key",
            name="uq_catalog_ap_versions_control_version_key",
        ),
        UniqueConstraint(
            "control_version_id",
            "sequence",
            name="uq_catalog_ap_versions_control_version_seq",
        ),
        CheckConstraint(APKeyFormat(column("procedure_key")), name="ap_key_format"),
        CheckConstraint("length(procedure_key) BETWEEN 6 AND 64", name="ap_key_length"),
        CheckConstraint("sequence > 0", name="ap_sequence_positive"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 512", name="ap_title_length"),
        CheckConstraint("length(trim(objective)) BETWEEN 1 AND 4096", name="ap_objective_length"),
        CheckConstraint(
            "sample_guidance IS NULL OR length(trim(sample_guidance)) BETWEEN 1 AND 2048",
            name="ap_sample_guidance_length",
        ),
        CheckConstraint(
            "scope_guidance IS NULL OR length(trim(scope_guidance)) BETWEEN 1 AND 2048",
            name="ap_scope_guidance_length",
        ),
        CheckConstraint(
            "length(trim(decision_guidance)) BETWEEN 1 AND 4096",
            name="ap_decision_guidance_length",
        ),
        CheckConstraint(
            "assessor_qualifications IS NULL OR length(trim(assessor_qualifications)) BETWEEN 1 AND 2048",
            name="ap_assessor_qualifications_length",
        ),
        CheckConstraint(
            "missing_data_behavior = 'requires_human_review'",
            name="ap_missing_data_behavior",
        ),
        CheckConstraint("status = 'Draft'", name="ap_draft_only"),
        CheckConstraint("length(content_digest) = 32", name="ap_digest_32_bytes"),
        CheckConstraint(
            "digest_schema = 'catalog-assurance-draft-v1'", name="ap_known_digest_schema"
        ),
    )

    control_version_id: Mapped[UUID] = mapped_column(nullable=False)
    control_id: Mapped[UUID] = mapped_column(nullable=False)
    procedure_key: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    objective: Mapped[str] = mapped_column(String(4096), nullable=False)
    sample_guidance: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    scope_guidance: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    decision_guidance: Mapped[str] = mapped_column(String(4096), nullable=False)
    assessor_qualifications: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    missing_data_behavior: Mapped[str] = mapped_column(
        String(32), server_default="requires_human_review", nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), server_default="Draft", nullable=False)
    content_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    digest_schema: Mapped[str] = mapped_column(
        String(64), server_default="catalog-assurance-draft-v1", nullable=False
    )


class CatalogAssessmentProcedureStep(UUIDPrimaryKeyMixin, Base):
    """Ordered declarative step within a Common Control assessment procedure."""

    __tablename__ = "catalog_assessment_procedure_steps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assessment_procedure_version_id", "control_version_id"],
            [
                "catalog_assessment_procedure_versions.id",
                "catalog_assessment_procedure_versions.control_version_id",
            ],
            name="fk_catalog_ap_steps_ap_version_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "assessment_procedure_version_id",
            "sequence",
            name="uq_catalog_ap_steps_version_seq",
        ),
        CheckConstraint("sequence BETWEEN 1 AND 50", name="ap_step_sequence_bounds"),
        CheckConstraint(
            "step_kind IN ('inspect', 'inquire', 'observe', 'reperform', 'analyze')",
            name="known_ap_step_kind",
        ),
        CheckConstraint(
            "length(trim(instruction)) BETWEEN 1 AND 4096",
            name="ap_step_instruction_length",
        ),
        CheckConstraint(
            "expected_output IS NULL OR length(trim(expected_output)) BETWEEN 1 AND 2048",
            name="ap_step_expected_output_length",
        ),
    )

    assessment_procedure_version_id: Mapped[UUID] = mapped_column(nullable=False)
    control_version_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    step_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    instruction: Mapped[str] = mapped_column(String(4096), nullable=False)
    expected_output: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogAssessmentProcedureEvidenceRequirement(UUIDPrimaryKeyMixin, Base):
    """Ordered link pinning an assessment procedure to an evidence requirement under the same ControlVersion."""

    __tablename__ = "catalog_assessment_procedure_evidence_requirements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assessment_procedure_version_id", "control_version_id"],
            [
                "catalog_assessment_procedure_versions.id",
                "catalog_assessment_procedure_versions.control_version_id",
            ],
            name="fk_catalog_ap_er_links_ap_version_lineage",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["evidence_requirement_version_id", "control_version_id"],
            [
                "catalog_evidence_requirement_versions.id",
                "catalog_evidence_requirement_versions.control_version_id",
            ],
            name="fk_catalog_ap_er_links_er_version_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "assessment_procedure_version_id",
            "sequence",
            name="uq_catalog_ap_er_links_version_seq",
        ),
        UniqueConstraint(
            "assessment_procedure_version_id",
            "evidence_requirement_version_id",
            name="uq_catalog_ap_er_links_version_er",
        ),
        CheckConstraint("sequence BETWEEN 1 AND 32", name="ap_er_link_sequence_bounds"),
    )

    assessment_procedure_version_id: Mapped[UUID] = mapped_column(nullable=False)
    evidence_requirement_version_id: Mapped[UUID] = mapped_column(nullable=False)
    control_version_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogFactDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stable identity for a shared-catalog fact definition; draft-only."""

    __tablename__ = "catalog_fact_definitions"
    __table_args__ = (
        CheckConstraint(FactKeyFormat(column("fact_key")), name="fact_def_key_format"),
        CheckConstraint("length(fact_key) BETWEEN 3 AND 64", name="fact_def_key_length"),
        CheckConstraint("status = 'Draft'", name="fact_def_status_draft"),
    )

    fact_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'Draft'"))


class CatalogFactDefinitionVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable version of a shared-catalog fact definition; draft-only."""

    __tablename__ = "catalog_fact_definition_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["fact_definition_id"],
            ["catalog_fact_definitions.id"],
            name="fk_catalog_fact_def_versions_definition",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "fact_definition_id",
            "revision",
            name="uq_catalog_fact_def_versions_def_rev",
        ),
        UniqueConstraint(
            "fact_definition_id",
            "version_label",
            name="uq_catalog_fact_def_versions_def_label",
        ),
        UniqueConstraint(
            "id",
            "fact_definition_id",
            "revision",
            name="uq_catalog_fact_def_versions_lineage",
        ),
        ForeignKeyConstraint(
            ["predecessor_id", "fact_definition_id", "predecessor_revision"],
            [
                "catalog_fact_definition_versions.id",
                "catalog_fact_definition_versions.fact_definition_id",
                "catalog_fact_definition_versions.revision",
            ],
            name="fk_catalog_fact_def_versions_predecessor",
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision BETWEEN 1 AND 32767", name="fact_def_version_revision_bounds"),
        CheckConstraint(
            "((revision = 1 AND predecessor_id IS NULL AND predecessor_revision IS NULL) OR "
            "(revision > 1 AND predecessor_id IS NOT NULL AND predecessor_revision IS NOT NULL "
            "AND predecessor_revision = revision - 1 AND predecessor_id != id))",
            name="fact_def_version_predecessor_shape",
        ),
        CheckConstraint(
            "version_label = trim(version_label) AND length(version_label) BETWEEN 1 AND 64",
            name="fact_def_version_label_trim",
        ),
        CheckConstraint(
            "label = trim(label) AND length(label) BETWEEN 1 AND 512",
            name="fact_def_version_name_trim",
        ),
        CheckConstraint(
            "description = trim(description) AND length(description) BETWEEN 1 AND 4096",
            name="fact_def_version_desc_trim",
        ),
        CheckConstraint(
            "collection_guidance IS NULL OR (collection_guidance = trim(collection_guidance) AND length(collection_guidance) BETWEEN 1 AND 4096)",
            name="fact_def_version_guidance_trim",
        ),
        CheckConstraint(
            "value_type IN ('boolean', 'integer', 'decimal', 'date', 'enum', 'string', 'entity_reference')",
            name="fact_def_version_value_type_known",
        ),
        CheckConstraint(
            "sensitivity IN ('Public', 'Internal', 'Confidential', 'Restricted')",
            name="fact_def_version_sensitivity_known",
        ),
        CheckConstraint(
            "effective_from IS NULL OR effective_until IS NULL OR effective_until >= effective_from",
            name="fact_def_version_effective_dates",
        ),
        CheckConstraint("status = 'Draft'", name="fact_def_version_status_draft"),
        CheckConstraint(
            "digest_schema = 'catalog-fact-definition-draft-v1'",
            name="fact_def_version_digest_schema_valid",
        ),
        CheckConstraint("length(content_digest) = 32", name="fact_def_version_digest_32_bytes"),
    )

    fact_definition_id: Mapped[UUID] = mapped_column(nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    predecessor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    predecessor_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(String(4096), nullable=False)
    collection_guidance: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    value_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'Draft'"))
    content_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    digest_schema: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'catalog-fact-definition-draft-v1'")
    )


class CatalogFactDefinitionScope(UUIDPrimaryKeyMixin, Base):
    """Allowed target entity scope for a shared-catalog fact definition version."""

    __tablename__ = "catalog_fact_definition_scopes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["fact_definition_version_id"],
            ["catalog_fact_definition_versions.id"],
            name="fk_catalog_fact_def_scopes_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "fact_definition_version_id",
            "sequence",
            name="uq_catalog_fact_def_scopes_version_seq",
        ),
        UniqueConstraint(
            "fact_definition_version_id",
            "scope_type",
            name="uq_catalog_fact_def_scopes_version_scope",
        ),
        CheckConstraint("sequence BETWEEN 1 AND 6", name="fact_def_scope_sequence_bounds"),
        CheckConstraint(
            "scope_type IN ('tenant', 'legal_entity', 'service', 'processing_activity', 'system', 'location')",
            name="fact_def_scope_type_known",
        ),
    )

    fact_definition_version_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogFactDefinitionEnumValue(UUIDPrimaryKeyMixin, Base):
    """Controlled enum value for an enum-typed shared-catalog fact definition version."""

    __tablename__ = "catalog_fact_definition_enum_values"
    __table_args__ = (
        ForeignKeyConstraint(
            ["fact_definition_version_id"],
            ["catalog_fact_definition_versions.id"],
            name="fk_catalog_fact_def_enum_values_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "fact_definition_version_id",
            "sequence",
            name="uq_catalog_fact_def_enum_values_version_seq",
        ),
        UniqueConstraint(
            "fact_definition_version_id",
            "code",
            name="uq_catalog_fact_def_enum_values_version_code",
        ),
        CheckConstraint("sequence BETWEEN 1 AND 64", name="fact_def_enum_value_sequence_bounds"),
        CheckConstraint(
            FactEnumValueCodeFormat(column("code")), name="fact_def_enum_value_code_format"
        ),
        CheckConstraint("length(code) BETWEEN 1 AND 64", name="fact_def_enum_value_code_length"),
        CheckConstraint(
            "label = trim(label) AND length(label) BETWEEN 1 AND 256",
            name="fact_def_enum_value_label_trim",
        ),
    )

    fact_definition_version_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RuleKeyFormat(ColumnElement[bool]):
    inherit_cache = True

    def __init__(self, column: Any) -> None:
        self.column = column


@compiles(RuleKeyFormat, "postgresql")
def compile_rule_key_format_pg(element: RuleKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return f"{col} ~ '^[a-z][a-z0-9_]{{2,63}}$'"


@compiles(RuleKeyFormat, "sqlite")
def compile_rule_key_format_sqlite(element: RuleKeyFormat, compiler: Any, **kw: Any) -> str:
    col = compiler.process(element.column, **kw)
    return (
        f"(length({col}) BETWEEN 3 AND 64 AND "
        f"substr({col}, 1, 1) GLOB '[a-z]' AND "
        f"{col} NOT GLOB '*[^a-z0-9_]*')"
    )


class CatalogApplicabilityRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stable identity for a shared-catalog applicability rule; draft-only."""

    __tablename__ = "catalog_applicability_rules"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_id"],
            ["catalog_requirements.id"],
            name="fk_catalog_app_rules_requirement",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "requirement_id", name="uq_catalog_app_rules_id_requirement"),
        UniqueConstraint("rule_key", name="uq_catalog_app_rules_key"),
        CheckConstraint(RuleKeyFormat(column("rule_key")), name="app_rule_key_format"),
        CheckConstraint("length(rule_key) BETWEEN 3 AND 64", name="app_rule_key_length"),
        CheckConstraint("status = 'Draft'", name="app_rule_status_draft"),
    )

    rule_key: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'Draft'"))


class CatalogApplicabilityRuleVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable version of a shared-catalog applicability rule; draft-only."""

    __tablename__ = "catalog_applicability_rule_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_id", "requirement_id"],
            ["catalog_applicability_rules.id", "catalog_applicability_rules.requirement_id"],
            name="fk_catalog_app_rule_versions_rule",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id"],
            ["catalog_requirement_versions.id", "catalog_requirement_versions.requirement_id"],
            name="fk_catalog_app_rule_versions_req_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["predecessor_id", "rule_id", "predecessor_revision"],
            [
                "catalog_applicability_rule_versions.id",
                "catalog_applicability_rule_versions.rule_id",
                "catalog_applicability_rule_versions.revision",
            ],
            name="fk_catalog_app_rule_versions_predecessor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "rule_id",
            "revision",
            name="uq_catalog_app_rule_versions_rule_rev",
        ),
        UniqueConstraint(
            "rule_id",
            "version_label",
            name="uq_catalog_app_rule_versions_rule_label",
        ),
        UniqueConstraint(
            "id",
            "rule_id",
            "revision",
            name="uq_catalog_app_rule_versions_lineage",
        ),
        CheckConstraint("revision BETWEEN 1 AND 32767", name="app_rule_version_revision_bounds"),
        CheckConstraint(
            "((revision = 1 AND predecessor_id IS NULL AND predecessor_revision IS NULL) OR "
            "(revision > 1 AND predecessor_id IS NOT NULL AND predecessor_revision IS NOT NULL "
            "AND predecessor_revision = revision - 1 AND predecessor_id != id))",
            name="app_rule_version_predecessor_shape",
        ),
        CheckConstraint(
            "version_label = trim(version_label) AND length(version_label) BETWEEN 1 AND 64",
            name="app_rule_version_label_trim",
        ),
        CheckConstraint("expression_ast_version = 1", name="app_rule_version_ast_version"),
        CheckConstraint(
            "length(expression_canonical) BETWEEN 2 AND 16384",
            name="app_rule_version_expression_bytes",
        ),
        CheckConstraint(
            "effective_from IS NULL OR effective_until IS NULL OR effective_until >= effective_from",
            name="app_rule_version_effective_dates",
        ),
        CheckConstraint("status = 'Draft'", name="app_rule_version_status_draft"),
        CheckConstraint("length(content_digest) = 32", name="app_rule_version_digest_32_bytes"),
        CheckConstraint(
            "digest_schema = 'catalog-applicability-rule-draft-v1'",
            name="app_rule_version_digest_schema",
        ),
        CheckConstraint(
            "length(requirement_version_digest_snapshot) = 32",
            name="app_rule_version_target_digest_32_bytes",
        ),
    )

    rule_id: Mapped[UUID] = mapped_column(nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(nullable=False)
    requirement_version_id: Mapped[UUID] = mapped_column(nullable=False)
    requirement_version_digest_snapshot: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    predecessor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    predecessor_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expression_ast_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    expression_canonical: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'Draft'"))
    content_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    digest_schema: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'catalog-applicability-rule-draft-v1'"),
    )


class CatalogApplicabilityRuleFactRef(UUIDPrimaryKeyMixin, Base):
    """Pinned fact-definition version reference within an applicability rule version."""

    __tablename__ = "catalog_applicability_rule_fact_refs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_version_id"],
            ["catalog_applicability_rule_versions.id"],
            name="fk_catalog_app_fact_refs_rule_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["fact_definition_version_id"],
            ["catalog_fact_definition_versions.id"],
            name="fk_catalog_app_fact_refs_fact_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "rule_version_id",
            "sequence",
            name="uq_catalog_app_fact_refs_version_seq",
        ),
        UniqueConstraint(
            "rule_version_id",
            "fact_definition_version_id",
            name="uq_catalog_app_fact_refs_version_fact",
        ),
        CheckConstraint("sequence BETWEEN 1 AND 64", name="app_fact_ref_sequence_bounds"),
        CheckConstraint(
            "length(content_digest_snapshot) = 32",
            name="app_fact_ref_digest_32_bytes",
        ),
    )

    rule_version_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    fact_definition_version_id: Mapped[UUID] = mapped_column(nullable=False)
    content_digest_snapshot: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogApplicabilityRuleSourceRef(UUIDPrimaryKeyMixin, Base):
    """Pinned source version attribution reference within an applicability rule version."""

    __tablename__ = "catalog_applicability_rule_source_refs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_version_id"],
            ["catalog_applicability_rule_versions.id"],
            name="fk_catalog_app_source_refs_rule_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_version_id"],
            ["catalog_source_versions.id"],
            name="fk_catalog_app_source_refs_source_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "rule_version_id",
            "sequence",
            name="uq_catalog_app_source_refs_version_seq",
        ),
        UniqueConstraint(
            "rule_version_id",
            "source_version_id",
            name="uq_catalog_app_source_refs_version_source",
        ),
        CheckConstraint("sequence BETWEEN 1 AND 64", name="app_source_ref_sequence_bounds"),
        CheckConstraint(
            "length(content_digest_snapshot) = 32",
            name="app_source_ref_digest_32_bytes",
        ),
    )

    rule_version_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    source_version_id: Mapped[UUID] = mapped_column(nullable=False)
    content_digest_snapshot: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
