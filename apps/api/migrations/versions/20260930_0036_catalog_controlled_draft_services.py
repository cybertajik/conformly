"""Add controlled Draft services support schema, digests, pins, and catalog role privileges."""

import sqlalchemy as sa
from alembic import op

revision = "20260930_0036"
down_revision = "20260929_0035"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "catalog_source_permission_guards",
    "catalog_source_permission_decisions",
    "catalog_audit_heads",
    "catalog_audit_events",
    "catalog_event_intents",
    "catalog_mutation_receipts",
)

ALL_CATALOG_TABLES = (
    "catalog_publishers",
    "catalog_sources",
    "catalog_source_versions",
    "catalog_source_provenance",
    "catalog_source_permission_proposals",
    "catalog_source_permission_guards",
    "catalog_source_permission_decisions",
    "catalog_requirements",
    "catalog_requirement_versions",
    "catalog_requirement_source_references",
    "catalog_common_controls",
    "catalog_control_versions",
    "catalog_requirement_control_mappings",
    "catalog_mapping_versions",
    "catalog_packs",
    "catalog_pack_versions",
    "catalog_pack_memberships",
    "catalog_audit_heads",
    "catalog_audit_events",
    "catalog_event_intents",
    "catalog_mutation_receipts",
)


def upgrade() -> None:
    # 1. Forward-reconciliation safety stop:
    # Refuse before alteration if any exact-version, mapping, or membership table contains rows.
    op.execute("""
        DO $$
        BEGIN
            IF (SELECT COUNT(*) FROM public.catalog_source_versions) > 0
               OR (SELECT COUNT(*) FROM public.catalog_requirement_versions) > 0
               OR (SELECT COUNT(*) FROM public.catalog_control_versions) > 0
               OR (SELECT COUNT(*) FROM public.catalog_mapping_versions) > 0
               OR (SELECT COUNT(*) FROM public.catalog_pack_versions) > 0
               OR (SELECT COUNT(*) FROM public.catalog_requirement_source_references) > 0
               OR (SELECT COUNT(*) FROM public.catalog_pack_memberships) > 0 THEN
                RAISE EXCEPTION 'V2 exact-version/mapping/membership tables contain rows; unsafe non-empty V2 digest backfill refused';
            END IF;
        END $$;
    """)

    # 2. catalog_source_permission_guards
    op.create_table(
        "catalog_source_permission_guards",
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_sources.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("revision", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("revision > 0", name="guard_revision_positive"),
    )
    # Backfill guard rows for existing stable sources
    op.execute("""
        INSERT INTO public.catalog_source_permission_guards (source_id, revision, updated_at)
        SELECT id, 1, clock_timestamp() FROM public.catalog_sources
        ON CONFLICT DO NOTHING;
    """)

    # 3. catalog_source_permission_decisions
    op.create_table(
        "catalog_source_permission_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_source_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "proposal_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_source_permission_proposals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("use_case", sa.String(64), nullable=False),
        sa.Column("scope_key", sa.String(128), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "predecessor_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_source_permission_decisions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("conditions_state", sa.String(16), server_default="None", nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.Column("evidence_reference", sa.Text(), nullable=False),
        sa.Column(
            "policy_version", sa.String(64), server_default="catalog-permission-v1", nullable=False
        ),
        sa.Column("guard_revision", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("sequence > 0", name="decision_sequence_positive"),
        sa.CheckConstraint("decision IN ('Allowed', 'Denied')", name="known_decision"),
        sa.CheckConstraint("conditions_state = 'None'", name="conditions_state_none"),
        sa.CheckConstraint(
            "use_case IN ('reference', 'store', 'excerpt', 'paraphrase', 'map')",
            name="known_use_case",
        ),
        sa.CheckConstraint("length(scope_key) BETWEEN 1 AND 128", name="scope_key_length"),
        sa.CheckConstraint("length(evidence_reference) > 0", name="evidence_reference_nonempty"),
        sa.CheckConstraint("policy_version = 'catalog-permission-v1'", name="known_policy_version"),
        sa.CheckConstraint("guard_revision > 0", name="decision_guard_revision_positive"),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_window_order"
        ),
        sa.UniqueConstraint(
            "source_version_id",
            "use_case",
            "scope_key",
            "sequence",
            name="uq_decision_version_use_scope_seq",
        ),
    )

    # 4. catalog_audit_heads
    op.create_table(
        "catalog_audit_heads",
        sa.Column("chain_key", sa.String(64), primary_key=True),
        sa.Column("current_sequence", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("head_hash", sa.LargeBinary(32), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("current_sequence >= 0", name="head_current_sequence_nonnegative"),
        sa.CheckConstraint("octet_length(head_hash) = 32", name="head_hash_32_bytes"),
    )
    # Seed initial head row for chain 'draft-catalog-v1'
    op.execute("""
        INSERT INTO public.catalog_audit_heads (chain_key, current_sequence, head_hash, updated_at)
        VALUES ('draft-catalog-v1', 0, decode(repeat('00', 32), 'hex'), clock_timestamp())
        ON CONFLICT DO NOTHING;
    """)

    # 5. catalog_audit_events
    op.create_table(
        "catalog_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "chain_key",
            sa.String(64),
            sa.ForeignKey("catalog_audit_heads.chain_key", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("previous_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("event_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("sequence > 0", name="audit_sequence_positive"),
        sa.CheckConstraint("octet_length(previous_hash) = 32", name="audit_prev_hash_32_bytes"),
        sa.CheckConstraint("octet_length(event_hash) = 32", name="audit_event_hash_32_bytes"),
        sa.CheckConstraint(
            "outcome IN ('Success', 'Denied', 'Conflict')", name="known_audit_outcome"
        ),
        sa.CheckConstraint(
            "length(request_key) BETWEEN 1 AND 128", name="audit_request_key_length"
        ),
        sa.UniqueConstraint("chain_key", "sequence", name="uq_audit_chain_sequence"),
    )

    # 6. catalog_event_intents
    op.create_table(
        "catalog_event_intents",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("event_kind", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("content_digest", sa.LargeBinary(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("revision > 0", name="intent_revision_positive"),
        sa.CheckConstraint("octet_length(content_digest) = 32", name="intent_digest_32_bytes"),
        sa.CheckConstraint(
            "length(request_key) BETWEEN 1 AND 128", name="intent_request_key_length"
        ),
        sa.UniqueConstraint("request_key", "event_kind", name="uq_catalog_intent_request_event"),
    )

    # 7. catalog_mutation_receipts
    op.create_table(
        "catalog_mutation_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.LargeBinary(32), nullable=False),
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("result_type", sa.String(64), nullable=False),
        sa.Column("result_revision", sa.BigInteger(), nullable=False),
        sa.Column("result_digest", sa.LargeBinary(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "octet_length(request_fingerprint) = 32", name="receipt_fingerprint_32_bytes"
        ),
        sa.CheckConstraint("octet_length(result_digest) = 32", name="receipt_digest_32_bytes"),
        sa.CheckConstraint("result_revision > 0", name="receipt_result_revision_positive"),
        sa.CheckConstraint(
            "length(request_key) BETWEEN 1 AND 128", name="receipt_request_key_length"
        ),
        sa.UniqueConstraint(
            "actor_id", "operation", "request_key", name="uq_receipt_actor_op_request"
        ),
    )

    # 8. Add digest columns to version tables
    op.add_column(
        "catalog_source_versions",
        sa.Column(
            "content_digest",
            sa.LargeBinary(32),
            server_default=sa.text(
                "'\\x0000000000000000000000000000000000000000000000000000000000000000'::bytea"
            ),
            nullable=False,
        ),
    )
    op.add_column(
        "catalog_source_versions",
        sa.Column(
            "digest_schema", sa.String(64), server_default="catalog-draft-v1", nullable=False
        ),
    )
    op.create_check_constraint(
        "source_version_digest_32_bytes",
        "catalog_source_versions",
        "octet_length(content_digest) = 32",
    )
    op.create_check_constraint(
        "source_version_digest_schema_v1",
        "catalog_source_versions",
        "digest_schema = 'catalog-draft-v1'",
    )

    op.add_column(
        "catalog_requirement_versions",
        sa.Column(
            "content_digest",
            sa.LargeBinary(32),
            server_default=sa.text(
                "'\\x0000000000000000000000000000000000000000000000000000000000000000'::bytea"
            ),
            nullable=False,
        ),
    )
    op.add_column(
        "catalog_requirement_versions",
        sa.Column(
            "digest_schema", sa.String(64), server_default="catalog-draft-v1", nullable=False
        ),
    )
    op.create_check_constraint(
        "req_version_digest_32_bytes",
        "catalog_requirement_versions",
        "octet_length(content_digest) = 32",
    )
    op.create_check_constraint(
        "req_version_digest_schema_v1",
        "catalog_requirement_versions",
        "digest_schema = 'catalog-draft-v1'",
    )

    op.add_column(
        "catalog_control_versions",
        sa.Column(
            "content_digest",
            sa.LargeBinary(32),
            server_default=sa.text(
                "'\\x0000000000000000000000000000000000000000000000000000000000000000'::bytea"
            ),
            nullable=False,
        ),
    )
    op.add_column(
        "catalog_control_versions",
        sa.Column(
            "digest_schema", sa.String(64), server_default="catalog-draft-v1", nullable=False
        ),
    )
    op.create_check_constraint(
        "ctrl_version_digest_32_bytes",
        "catalog_control_versions",
        "octet_length(content_digest) = 32",
    )
    op.create_check_constraint(
        "ctrl_version_digest_schema_v1",
        "catalog_control_versions",
        "digest_schema = 'catalog-draft-v1'",
    )

    op.add_column(
        "catalog_mapping_versions",
        sa.Column(
            "content_digest",
            sa.LargeBinary(32),
            server_default=sa.text(
                "'\\x0000000000000000000000000000000000000000000000000000000000000000'::bytea"
            ),
            nullable=False,
        ),
    )
    op.add_column(
        "catalog_mapping_versions",
        sa.Column(
            "digest_schema", sa.String(64), server_default="catalog-draft-v1", nullable=False
        ),
    )
    op.add_column(
        "catalog_mapping_versions",
        sa.Column(
            "requirement_version_revision",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.add_column(
        "catalog_mapping_versions",
        sa.Column(
            "requirement_version_digest",
            sa.LargeBinary(32),
            server_default=sa.text(
                "'\\x0000000000000000000000000000000000000000000000000000000000000000'::bytea"
            ),
            nullable=False,
        ),
    )
    op.add_column(
        "catalog_mapping_versions",
        sa.Column(
            "control_version_revision", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
    )
    op.add_column(
        "catalog_mapping_versions",
        sa.Column(
            "control_version_digest",
            sa.LargeBinary(32),
            server_default=sa.text(
                "'\\x0000000000000000000000000000000000000000000000000000000000000000'::bytea"
            ),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "map_version_digest_32_bytes",
        "catalog_mapping_versions",
        "octet_length(content_digest) = 32",
    )
    op.create_check_constraint(
        "map_version_digest_schema_v1",
        "catalog_mapping_versions",
        "digest_schema = 'catalog-draft-v1'",
    )
    op.create_check_constraint(
        "map_req_revision_positive", "catalog_mapping_versions", "requirement_version_revision > 0"
    )
    op.create_check_constraint(
        "map_req_digest_32_bytes",
        "catalog_mapping_versions",
        "octet_length(requirement_version_digest) = 32",
    )
    op.create_check_constraint(
        "map_ctrl_revision_positive", "catalog_mapping_versions", "control_version_revision > 0"
    )
    op.create_check_constraint(
        "map_ctrl_digest_32_bytes",
        "catalog_mapping_versions",
        "octet_length(control_version_digest) = 32",
    )

    op.add_column(
        "catalog_pack_versions",
        sa.Column(
            "content_digest",
            sa.LargeBinary(32),
            server_default=sa.text(
                "'\\x0000000000000000000000000000000000000000000000000000000000000000'::bytea"
            ),
            nullable=False,
        ),
    )
    op.add_column(
        "catalog_pack_versions",
        sa.Column(
            "digest_schema", sa.String(64), server_default="catalog-draft-v1", nullable=False
        ),
    )
    op.create_check_constraint(
        "pack_version_digest_32_bytes", "catalog_pack_versions", "octet_length(content_digest) = 32"
    )
    op.create_check_constraint(
        "pack_version_digest_schema_v1",
        "catalog_pack_versions",
        "digest_schema = 'catalog-draft-v1'",
    )

    op.add_column(
        "catalog_pack_memberships",
        sa.Column(
            "requirement_version_revision",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.add_column(
        "catalog_pack_memberships",
        sa.Column(
            "requirement_version_digest",
            sa.LargeBinary(32),
            server_default=sa.text(
                "'\\x0000000000000000000000000000000000000000000000000000000000000000'::bytea"
            ),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "pack_mem_req_revision_positive",
        "catalog_pack_memberships",
        "requirement_version_revision > 0",
    )
    op.create_check_constraint(
        "pack_mem_req_digest_32_bytes",
        "catalog_pack_memberships",
        "octet_length(requirement_version_digest) = 32",
    )

    # 9. Triggers: Decision sequence, gap-free, predecessor, and author separation
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_source_permission_decision_validate()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog
        AS $$
        DECLARE
            rec_actor uuid;
            prop_use_case varchar;
            prop_scope_key varchar;
            max_seq integer;
            expected_pred uuid;
        BEGIN
            -- Lock parent source guard to serialize decision allocations
            PERFORM 1 FROM public.catalog_source_permission_guards WHERE source_id = NEW.source_id FOR UPDATE;

            -- Verify decider != proposal recorder AND use_case / scope_key equality
            SELECT recorded_by_actor_id, use_case, scope_key INTO rec_actor, prop_use_case, prop_scope_key
            FROM public.catalog_source_permission_proposals
            WHERE id = NEW.proposal_id;

            IF rec_actor IS NULL THEN
                RAISE EXCEPTION 'Proposal % does not exist', NEW.proposal_id;
            END IF;

            IF NEW.decided_by_actor_id = rec_actor THEN
                RAISE EXCEPTION 'Decision actor cannot be the proposal recorder';
            END IF;

            IF NEW.use_case != prop_use_case OR NEW.scope_key != prop_scope_key THEN
                RAISE EXCEPTION 'Decision use_case and scope_key must match proposal';
            END IF;

            -- Verify gap-free sequence and predecessor
            SELECT COALESCE(MAX(sequence), 0) INTO max_seq
            FROM public.catalog_source_permission_decisions
            WHERE source_version_id = NEW.source_version_id
              AND use_case = NEW.use_case
              AND scope_key = NEW.scope_key;

            IF NEW.sequence != max_seq + 1 THEN
                RAISE EXCEPTION 'Decision sequence must be gap-free, expected % but got %', max_seq + 1, NEW.sequence;
            END IF;

            IF max_seq = 0 THEN
                IF NEW.predecessor_id IS NOT NULL THEN
                    RAISE EXCEPTION 'First decision in scope must have null predecessor';
                END IF;
            ELSE
                SELECT id INTO expected_pred
                FROM public.catalog_source_permission_decisions
                WHERE source_version_id = NEW.source_version_id
                  AND use_case = NEW.use_case
                  AND scope_key = NEW.scope_key
                  AND sequence = max_seq;

                IF NEW.predecessor_id IS DISTINCT FROM expected_pred THEN
                    RAISE EXCEPTION 'Decision predecessor mismatch: expected %, got %', expected_pred, NEW.predecessor_id;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.catalog_source_permission_decision_validate() FROM PUBLIC"
    )
    op.execute("""
        CREATE TRIGGER trg_catalog_permission_decision_validate
        BEFORE INSERT ON public.catalog_source_permission_decisions
        FOR EACH ROW
        EXECUTE FUNCTION public.catalog_source_permission_decision_validate()
    """)

    # Controlled source reference replacement function (SECURITY DEFINER)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_delete_requirement_source_references(p_requirement_version_id uuid)
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            IF p_requirement_version_id IS NULL THEN
                RAISE EXCEPTION 'requirement_version_id cannot be null';
            END IF;
            PERFORM pg_catalog.set_config('conformly.internal_ref_replacement', 'on', true);
            DELETE FROM public.catalog_requirement_source_references
            WHERE requirement_version_id = p_requirement_version_id;
            PERFORM pg_catalog.set_config('conformly.internal_ref_replacement', 'off', true);
        END;
        $$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.catalog_delete_requirement_source_references(uuid) FROM PUBLIC"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_app') THEN
                REVOKE ALL ON FUNCTION public.catalog_delete_requirement_source_references(uuid) FROM conformly_app;
            END IF;
        END $$;
    """)

    # Enable atomic source reference replacement under controlled draft service
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_requirement_source_references_append_only()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND pg_catalog.current_setting('conformly.internal_ref_replacement', true) = 'on' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'catalog requirement source references are append-only';
        END;
        $$;
    """)

    # Append-only and no-truncate functions/triggers
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_support_append_only()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog
        AS $$
        BEGIN
            RAISE EXCEPTION 'Catalog support table % is append-only', TG_TABLE_NAME;
        END;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_support_append_only() FROM PUBLIC")

    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_support_no_truncate()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog
        AS $$
        BEGIN
            RAISE EXCEPTION 'TRUNCATE is not permitted on catalog support table %', TG_TABLE_NAME;
        END;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_support_no_truncate() FROM PUBLIC")

    for table in (
        "catalog_source_permission_decisions",
        "catalog_audit_events",
        "catalog_event_intents",
        "catalog_mutation_receipts",
    ):
        op.execute(f"""
            CREATE TRIGGER "{table}_immutable"
            BEFORE UPDATE OR DELETE ON public."{table}"
            FOR EACH ROW
            EXECUTE FUNCTION public.catalog_support_append_only()
        """)
        op.execute(f"""
            CREATE TRIGGER "{table}_no_truncate"
            BEFORE TRUNCATE ON public."{table}"
            EXECUTE FUNCTION public.catalog_support_no_truncate()
        """)

    # 10. Security: RLS, deny-all, revoke from PUBLIC and conformly_app
    for table in NEW_TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public."{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL PRIVILEGES ON TABLE public."{table}" FROM PUBLIC')
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_app') "
            f'THEN REVOKE ALL PRIVILEGES ON TABLE public."{table}" FROM conformly_app; '
            "END IF; END $$"
        )

    # 11. Role boundary: conformly_catalog execution role
    # When role conformly_catalog exists, grant reviewed privileges and RLS policies
    op.execute("""
        DO $$
        DECLARE
            tbl text;
            tables text[] := ARRAY[
                'catalog_publishers',
                'catalog_sources',
                'catalog_source_versions',
                'catalog_source_provenance',
                'catalog_source_permission_proposals',
                'catalog_source_permission_guards',
                'catalog_source_permission_decisions',
                'catalog_requirements',
                'catalog_requirement_versions',
                'catalog_requirement_source_references',
                'catalog_common_controls',
                'catalog_control_versions',
                'catalog_requirement_control_mappings',
                'catalog_mapping_versions',
                'catalog_packs',
                'catalog_pack_versions',
                'catalog_pack_memberships',
                'catalog_audit_heads',
                'catalog_audit_events',
                'catalog_event_intents',
                'catalog_mutation_receipts'
            ];
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_catalog') THEN
                -- Grant table privileges
                FOREACH tbl IN ARRAY tables LOOP
                    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON TABLE public.%I TO conformly_catalog', tbl);
                    -- Install RLS policy
                    EXECUTE format('DROP POLICY IF EXISTS catalog_role_access ON public.%I', tbl);
                    EXECUTE format('CREATE POLICY catalog_role_access ON public.%I TO conformly_catalog USING (true) WITH CHECK (true)', tbl);
                END LOOP;

                -- Functions
                GRANT EXECUTE ON FUNCTION public.catalog_check_pack_version_acyclic() TO conformly_catalog;
                GRANT EXECUTE ON FUNCTION public.catalog_check_mapping_version_acyclic() TO conformly_catalog;
                GRANT EXECUTE ON FUNCTION public.catalog_pack_membership_check_sequence() TO conformly_catalog;
                GRANT EXECUTE ON FUNCTION public.catalog_source_permission_decision_validate() TO conformly_catalog;
                GRANT EXECUTE ON FUNCTION public.catalog_delete_requirement_source_references(uuid) TO conformly_catalog;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("SET LOCAL row_security = off")
    op.execute("""
        LOCK TABLE
            public.catalog_source_permission_guards,
            public.catalog_source_permission_decisions,
            public.catalog_audit_heads,
            public.catalog_audit_events,
            public.catalog_event_intents,
            public.catalog_mutation_receipts
        IN ACCESS EXCLUSIVE MODE
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.catalog_source_permission_decisions)
               OR EXISTS (SELECT 1 FROM public.catalog_audit_events)
               OR EXISTS (SELECT 1 FROM public.catalog_event_intents)
               OR EXISTS (SELECT 1 FROM public.catalog_mutation_receipts) THEN
                RAISE EXCEPTION 'V2 controlled draft services is populated; forward recovery required';
            END IF;
        END $$;
    """)

    # Drop triggers and functions
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_permission_decision_validate ON public.catalog_source_permission_decisions"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_source_permission_decision_validate()")

    for table in (
        "catalog_source_permission_decisions",
        "catalog_audit_events",
        "catalog_event_intents",
        "catalog_mutation_receipts",
    ):
        op.execute(f'DROP TRIGGER IF EXISTS "{table}_immutable" ON public."{table}"')
        op.execute(f'DROP TRIGGER IF EXISTS "{table}_no_truncate" ON public."{table}"')

    op.execute("DROP FUNCTION IF EXISTS public.catalog_delete_requirement_source_references(uuid)")
    op.execute("DROP FUNCTION IF EXISTS public.catalog_support_append_only()")
    op.execute("DROP FUNCTION IF EXISTS public.catalog_support_no_truncate()")
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_requirement_source_references_append_only()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$ BEGIN RAISE EXCEPTION 'catalog requirement source references are append-only'; END; $$;
    """)

    # Drop catalog_role_access policies and revoke grants
    op.execute("""
        DO $$
        DECLARE
            tbl text;
            tables text[] := ARRAY[
                'catalog_publishers',
                'catalog_sources',
                'catalog_source_versions',
                'catalog_source_provenance',
                'catalog_source_permission_proposals',
                'catalog_source_permission_guards',
                'catalog_source_permission_decisions',
                'catalog_requirements',
                'catalog_requirement_versions',
                'catalog_requirement_source_references',
                'catalog_common_controls',
                'catalog_control_versions',
                'catalog_requirement_control_mappings',
                'catalog_mapping_versions',
                'catalog_packs',
                'catalog_pack_versions',
                'catalog_pack_memberships',
                'catalog_audit_heads',
                'catalog_audit_events',
                'catalog_event_intents',
                'catalog_mutation_receipts'
            ];
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_catalog') THEN
                FOREACH tbl IN ARRAY tables LOOP
                    EXECUTE format('DROP POLICY IF EXISTS catalog_role_access ON public.%I', tbl);
                    EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM conformly_catalog', tbl);
                END LOOP;
            END IF;
        END $$;
    """)

    # Drop added columns from version tables
    op.drop_column("catalog_pack_memberships", "requirement_version_digest")
    op.drop_column("catalog_pack_memberships", "requirement_version_revision")

    op.drop_column("catalog_pack_versions", "digest_schema")
    op.drop_column("catalog_pack_versions", "content_digest")

    op.drop_column("catalog_mapping_versions", "control_version_digest")
    op.drop_column("catalog_mapping_versions", "control_version_revision")
    op.drop_column("catalog_mapping_versions", "requirement_version_digest")
    op.drop_column("catalog_mapping_versions", "requirement_version_revision")
    op.drop_column("catalog_mapping_versions", "digest_schema")
    op.drop_column("catalog_mapping_versions", "content_digest")

    op.drop_column("catalog_control_versions", "digest_schema")
    op.drop_column("catalog_control_versions", "content_digest")

    op.drop_column("catalog_requirement_versions", "digest_schema")
    op.drop_column("catalog_requirement_versions", "content_digest")

    op.drop_column("catalog_source_versions", "digest_schema")
    op.drop_column("catalog_source_versions", "content_digest")

    # Drop support tables in reverse order
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
