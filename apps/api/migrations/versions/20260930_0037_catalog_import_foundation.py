"""Add the durable conservative-import ledger and reconciliation seal."""

import sqlalchemy as sa
from alembic import op

revision = "20260930_0037"
down_revision = "20260930_0036"
branch_labels = None
depends_on = None

TABLES = (
    "catalog_import_batches",
    "catalog_import_inputs",
    "catalog_import_reuse_ledger",
    "catalog_import_reconciliation_manifests",
)


def upgrade() -> None:
    op.create_table(
        "catalog_import_batches",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("batch_key", sa.String(128), nullable=False),
        sa.Column("batch_fingerprint", sa.LargeBinary(32), nullable=False),
        sa.Column("adapter_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="Accepted", nullable=False),
        sa.Column("total_inputs", sa.Integer(), nullable=False),
        sa.Column("reconciled_inputs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("payload_digest", sa.LargeBinary(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("batch_key", name="uq_catalog_import_batch_key"),
        sa.CheckConstraint(
            "status IN ('Accepted','Running','Reconciled','Interrupted','Cancelled','Aborted')",
            name="catalog_import_batch_status",
        ),
        sa.CheckConstraint(
            "reconciled_inputs >= 0 AND reconciled_inputs <= total_inputs",
            name="catalog_import_batch_reconciled_bounds",
        ),
        sa.CheckConstraint(
            "total_inputs > 0 AND total_inputs <= 5000", name="catalog_import_batch_total_bounds"
        ),
        sa.CheckConstraint(
            "octet_length(batch_fingerprint) = 32", name="catalog_import_batch_fingerprint_32"
        ),
        sa.CheckConstraint(
            "octet_length(payload_digest) = 32", name="catalog_import_batch_payload_digest_32"
        ),
    )
    op.create_table(
        "catalog_import_inputs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "batch_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_import_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("input_type", sa.String(32), nullable=False),
        sa.Column("origin_namespace", sa.String(64), nullable=False),
        sa.Column("origin_id", sa.String(128), nullable=False),
        sa.Column("input_fingerprint", sa.LargeBinary(32), nullable=False),
        sa.Column("disposition", sa.String(32), server_default="Pending", nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("target_entity_type", sa.String(32), nullable=True),
        sa.Column("target_version_id", sa.Uuid(), nullable=True),
        sa.Column("target_revision", sa.Integer(), nullable=True),
        sa.Column("target_digest", sa.LargeBinary(32), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("batch_id", "sequence", name="uq_catalog_import_input_seq"),
        sa.UniqueConstraint(
            "batch_id", "origin_namespace", "origin_id", name="uq_catalog_import_input_origin"
        ),
        sa.CheckConstraint(
            "input_type IN ('Requirement','CommonControl','Mapping','Pack','PackMembership','EvidenceRequirement','AssessmentProcedure')",
            name="catalog_import_input_type",
        ),
        sa.CheckConstraint(
            "disposition IN ('Pending','ImportedDraft','ReusedExact','NeedsPermission','NeedsSource','NeedsMappingReview','NeedsConflictReview','NeedsDependency','DeferredByScope','Rejected')",
            name="catalog_import_input_disposition",
        ),
        sa.CheckConstraint(
            "target_entity_type IS NULL OR target_entity_type IN ('RequirementVersion','ControlVersion','MappingVersion','PackVersion','PackMembership')",
            name="catalog_import_input_target_type",
        ),
        sa.CheckConstraint(
            "octet_length(input_fingerprint) = 32", name="catalog_import_input_fingerprint_32"
        ),
        sa.CheckConstraint(
            "target_digest IS NULL OR octet_length(target_digest) = 32",
            name="catalog_import_input_target_digest_32",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 3", name="catalog_import_input_attempt_bounds"
        ),
    )
    op.create_table(
        "catalog_import_reuse_ledger",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("origin_namespace", sa.String(64), nullable=False),
        sa.Column("origin_id", sa.String(128), nullable=False),
        sa.Column("adapter_version", sa.String(32), nullable=False),
        sa.Column("input_fingerprint", sa.LargeBinary(32), nullable=False),
        sa.Column("target_entity_type", sa.String(32), nullable=False),
        sa.Column("target_version_id", sa.Uuid(), nullable=False),
        sa.Column("target_revision", sa.Integer(), nullable=False),
        sa.Column("target_digest", sa.LargeBinary(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "origin_namespace",
            "origin_id",
            "adapter_version",
            name="uq_catalog_import_reuse_origin",
        ),
        sa.CheckConstraint(
            "target_entity_type IN ('RequirementVersion','ControlVersion','MappingVersion','PackVersion')",
            name="catalog_import_reuse_target_type",
        ),
        sa.CheckConstraint(
            "octet_length(input_fingerprint) = 32", name="catalog_import_reuse_fingerprint_32"
        ),
        sa.CheckConstraint(
            "octet_length(target_digest) = 32", name="catalog_import_reuse_digest_32"
        ),
        sa.CheckConstraint("target_revision > 0", name="catalog_import_reuse_revision_positive"),
    )
    op.create_table(
        "catalog_import_reconciliation_manifests",
        sa.Column(
            "batch_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_import_batches.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("manifest_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("total_inputs", sa.Integer(), nullable=False),
        sa.Column("reconciled_inputs", sa.Integer(), nullable=False),
        sa.Column("counts_by_disposition", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("sealed_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "sealed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "octet_length(manifest_hash) = 32", name="catalog_import_manifest_hash_32"
        ),
        sa.CheckConstraint(
            "reconciled_inputs = total_inputs", name="catalog_import_manifest_counts_match"
        ),
    )

    op.execute("""
        CREATE FUNCTION public.catalog_import_reject_change() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
            RAISE EXCEPTION 'CATALOG_IMPORT_APPEND_ONLY';
        END $$;
    """)
    op.execute("""
        CREATE FUNCTION public.catalog_import_input_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
            IF OLD.disposition <> 'Pending' THEN
                RAISE EXCEPTION 'CANNOT_MODIFY_PROCESSED_INPUT';
            END IF;
            IF (NEW.id, NEW.batch_id, NEW.sequence, NEW.input_type, NEW.origin_namespace,
                NEW.origin_id, NEW.input_fingerprint, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.batch_id, OLD.sequence, OLD.input_type, OLD.origin_namespace,
                OLD.origin_id, OLD.input_fingerprint, OLD.created_at) THEN
                RAISE EXCEPTION 'CATALOG_IMPORT_INPUT_IDENTITY_IMMUTABLE';
            END IF;
            RETURN NEW;
        END $$;
    """)
    op.execute("""
        CREATE FUNCTION public.catalog_import_batch_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
            IF OLD.status IN ('Reconciled','Cancelled','Aborted') THEN
                RAISE EXCEPTION 'CANNOT_MODIFY_TERMINAL_IMPORT_BATCH';
            END IF;
            IF (NEW.id, NEW.batch_key, NEW.batch_fingerprint, NEW.adapter_version,
                NEW.total_inputs, NEW.payload_digest, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.batch_key, OLD.batch_fingerprint, OLD.adapter_version,
                OLD.total_inputs, OLD.payload_digest, OLD.created_at) THEN
                RAISE EXCEPTION 'CATALOG_IMPORT_BATCH_IDENTITY_IMMUTABLE';
            END IF;
            IF NEW.status = 'Reconciled' AND NOT EXISTS (
                SELECT 1 FROM public.catalog_import_reconciliation_manifests m
                WHERE m.batch_id = NEW.id AND m.total_inputs = NEW.total_inputs
                  AND m.reconciled_inputs = NEW.reconciled_inputs
            ) THEN
                RAISE EXCEPTION 'IMPORT_BATCH_REQUIRES_VALID_MANIFEST';
            END IF;
            RETURN NEW;
        END $$;
    """)
    op.execute("""
        CREATE FUNCTION public.catalog_import_validate_reuse_target() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        DECLARE actual_revision integer;
        DECLARE actual_digest bytea;
        BEGIN
            IF NEW.target_entity_type = 'RequirementVersion' THEN
                SELECT revision, content_digest INTO actual_revision, actual_digest
                  FROM public.catalog_requirement_versions WHERE id = NEW.target_version_id;
            ELSIF NEW.target_entity_type = 'ControlVersion' THEN
                SELECT revision, content_digest INTO actual_revision, actual_digest
                  FROM public.catalog_control_versions WHERE id = NEW.target_version_id;
            ELSIF NEW.target_entity_type = 'MappingVersion' THEN
                SELECT revision, content_digest INTO actual_revision, actual_digest
                  FROM public.catalog_mapping_versions WHERE id = NEW.target_version_id;
            ELSIF NEW.target_entity_type = 'PackVersion' THEN
                SELECT revision, content_digest INTO actual_revision, actual_digest
                  FROM public.catalog_pack_versions WHERE id = NEW.target_version_id;
            END IF;
            IF actual_revision IS NULL OR actual_revision <> NEW.target_revision
               OR actual_digest IS DISTINCT FROM NEW.target_digest THEN
                RAISE EXCEPTION 'CATALOG_IMPORT_REUSE_TARGET_MISMATCH';
            END IF;
            RETURN NEW;
        END $$;
    """)
    op.execute(
        "CREATE TRIGGER catalog_import_input_guard BEFORE UPDATE ON public.catalog_import_inputs FOR EACH ROW EXECUTE FUNCTION public.catalog_import_input_guard()"
    )
    op.execute(
        "CREATE TRIGGER catalog_import_input_no_delete BEFORE DELETE ON public.catalog_import_inputs FOR EACH ROW EXECUTE FUNCTION public.catalog_import_reject_change()"
    )
    op.execute(
        "CREATE TRIGGER catalog_import_batch_guard BEFORE UPDATE ON public.catalog_import_batches FOR EACH ROW EXECUTE FUNCTION public.catalog_import_batch_guard()"
    )
    op.execute(
        "CREATE TRIGGER catalog_import_reuse_validate BEFORE INSERT ON public.catalog_import_reuse_ledger FOR EACH ROW EXECUTE FUNCTION public.catalog_import_validate_reuse_target()"
    )
    for table in (
        "catalog_import_batches",
        "catalog_import_reuse_ledger",
        "catalog_import_reconciliation_manifests",
    ):
        op.execute(
            f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.catalog_import_reject_change()"
        )
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON public.{table} FOR EACH STATEMENT EXECUTE FUNCTION public.catalog_import_reject_change()"
        )
    for table in ("catalog_import_reuse_ledger", "catalog_import_reconciliation_manifests"):
        op.execute(
            f"CREATE TRIGGER {table}_no_update BEFORE UPDATE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.catalog_import_reject_change()"
        )

    op.execute("""
        CREATE FUNCTION public.catalog_seal_import_batch(p_batch_id uuid, p_actor_id uuid)
        RETURNS bytea LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public AS $$
        DECLARE b public.catalog_import_batches%ROWTYPE;
        DECLARE counts jsonb;
        DECLARE reconciled integer;
        DECLARE seal bytea;
        BEGIN
            IF p_actor_id IS NULL THEN RAISE EXCEPTION 'IMPORT_SEAL_ACTOR_REQUIRED'; END IF;
            SELECT * INTO b FROM public.catalog_import_batches WHERE id = p_batch_id FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'IMPORT_BATCH_NOT_FOUND'; END IF;
            IF b.status = 'Reconciled' THEN
                RETURN (SELECT manifest_hash FROM public.catalog_import_reconciliation_manifests WHERE batch_id = p_batch_id);
            END IF;
            SELECT coalesce(sum(amount), 0)::integer, jsonb_object_agg(disposition, amount)
              INTO reconciled, counts
              FROM (SELECT disposition, count(*)::integer amount
                      FROM public.catalog_import_inputs
                     WHERE batch_id = p_batch_id AND disposition <> 'Pending'
                     GROUP BY disposition) d;
            IF reconciled <> b.total_inputs OR EXISTS (
                SELECT 1 FROM public.catalog_import_inputs
                 WHERE batch_id = p_batch_id AND disposition = 'Pending'
            ) THEN RAISE EXCEPTION 'IMPORT_BATCH_NOT_RECONCILED'; END IF;
            seal := sha256(convert_to(b.batch_key || ':' || encode(b.payload_digest, 'hex') || ':' || counts::text, 'UTF8'));
            INSERT INTO public.catalog_import_reconciliation_manifests
                (batch_id, manifest_hash, total_inputs, reconciled_inputs, counts_by_disposition, sealed_by_actor_id)
            VALUES (b.id, seal, b.total_inputs, reconciled, counts, p_actor_id);
            UPDATE public.catalog_import_batches SET status = 'Reconciled',
                reconciled_inputs = reconciled, updated_at = clock_timestamp() WHERE id = b.id;
            RETURN seal;
        END $$;
    """)

    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM PUBLIC")
        op.execute(
            f"CREATE POLICY catalog_import_owner_access ON public.{table} USING (true) WITH CHECK (true)"
        )
    op.execute("REVOKE ALL ON FUNCTION public.catalog_seal_import_batch(uuid, uuid) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.catalog_import_reject_change() FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.catalog_import_input_guard() FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.catalog_import_batch_guard() FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.catalog_import_validate_reuse_target() FROM PUBLIC")
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_app') THEN
            REVOKE ALL ON public.catalog_import_batches FROM conformly_app;
            REVOKE ALL ON public.catalog_import_inputs FROM conformly_app;
            REVOKE ALL ON public.catalog_import_reuse_ledger FROM conformly_app;
            REVOKE ALL ON public.catalog_import_reconciliation_manifests FROM conformly_app;
            REVOKE ALL ON FUNCTION public.catalog_seal_import_batch(uuid, uuid) FROM conformly_app;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_catalog') THEN
            GRANT SELECT, INSERT ON public.catalog_import_batches TO conformly_catalog;
            GRANT UPDATE (status, updated_at) ON public.catalog_import_batches TO conformly_catalog;
            GRANT SELECT, INSERT, UPDATE (disposition, reason_code, target_entity_type,
              target_version_id, target_revision, target_digest, attempt_count, processed_at)
              ON public.catalog_import_inputs TO conformly_catalog;
            GRANT SELECT, INSERT ON public.catalog_import_reuse_ledger TO conformly_catalog;
            GRANT SELECT ON public.catalog_import_reconciliation_manifests TO conformly_catalog;
            GRANT EXECUTE ON FUNCTION public.catalog_seal_import_batch(uuid, uuid) TO conformly_catalog;
          END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.catalog_seal_import_batch(uuid, uuid)")
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute("DROP FUNCTION IF EXISTS public.catalog_import_batch_guard()")
    op.execute("DROP FUNCTION IF EXISTS public.catalog_import_input_guard()")
    op.execute("DROP FUNCTION IF EXISTS public.catalog_import_validate_reuse_target()")
    op.execute("DROP FUNCTION IF EXISTS public.catalog_import_reject_change()")
