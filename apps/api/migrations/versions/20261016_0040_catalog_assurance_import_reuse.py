"""Extend catalog import target constraints and reuse validation trigger for assurance content.

Revision ID: 20261016_0040
Revises: 20261002_0039
Create Date: 2026-10-16 12:00:00.000000+00:00
"""

from alembic import op

revision = "20261016_0040"
down_revision = "20261002_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Update catalog_import_inputs target constraint
    op.drop_constraint("catalog_import_input_target_type", "catalog_import_inputs", type_="check")
    op.create_check_constraint(
        "catalog_import_input_target_type",
        "catalog_import_inputs",
        "target_entity_type IS NULL OR target_entity_type IN ('RequirementVersion','ControlVersion','MappingVersion','PackVersion','PackMembership','EvidenceRequirementVersion','AssessmentProcedureVersion')",
    )

    # 2. Update catalog_import_reuse_ledger target constraint
    op.drop_constraint(
        "catalog_import_reuse_target_type", "catalog_import_reuse_ledger", type_="check"
    )
    op.create_check_constraint(
        "catalog_import_reuse_target_type",
        "catalog_import_reuse_ledger",
        "target_entity_type IN ('RequirementVersion','ControlVersion','MappingVersion','PackVersion','EvidenceRequirementVersion','AssessmentProcedureVersion')",
    )

    # 3. Replace trigger function to validate assurance targets
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_import_validate_reuse_target() RETURNS trigger
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
            ELSIF NEW.target_entity_type = 'EvidenceRequirementVersion' THEN
                SELECT sequence, content_digest INTO actual_revision, actual_digest
                  FROM public.catalog_evidence_requirement_versions WHERE id = NEW.target_version_id;
            ELSIF NEW.target_entity_type = 'AssessmentProcedureVersion' THEN
                SELECT sequence, content_digest INTO actual_revision, actual_digest
                  FROM public.catalog_assessment_procedure_versions WHERE id = NEW.target_version_id;
            END IF;
            IF actual_revision IS NULL OR actual_revision <> NEW.target_revision
               OR actual_digest IS DISTINCT FROM NEW.target_digest THEN
                RAISE EXCEPTION 'CATALOG_IMPORT_REUSE_TARGET_MISMATCH';
            END IF;
            RETURN NEW;
        END $$;
    """)


def downgrade() -> None:
    # 1. Strict downgrade refusal if populated with assurance reuse entries
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.catalog_import_reuse_ledger
                WHERE target_entity_type IN ('EvidenceRequirementVersion', 'AssessmentProcedureVersion')
            ) OR EXISTS (
                SELECT 1 FROM public.catalog_import_inputs
                WHERE target_entity_type IN ('EvidenceRequirementVersion', 'AssessmentProcedureVersion')
            ) THEN
                RAISE EXCEPTION 'CANNOT_DOWNGRADE_ASSURANCE_REUSE_DATA_EXISTS';
            END IF;
        END $$;
    """)

    # 2. Revert trigger function to WP-04 definition
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_import_validate_reuse_target() RETURNS trigger
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

    # 3. Revert check constraints
    op.drop_constraint(
        "catalog_import_reuse_target_type", "catalog_import_reuse_ledger", type_="check"
    )
    op.create_check_constraint(
        "catalog_import_reuse_target_type",
        "catalog_import_reuse_ledger",
        "target_entity_type IN ('RequirementVersion','ControlVersion','MappingVersion','PackVersion')",
    )

    op.drop_constraint("catalog_import_input_target_type", "catalog_import_inputs", type_="check")
    op.create_check_constraint(
        "catalog_import_input_target_type",
        "catalog_import_inputs",
        "target_entity_type IS NULL OR target_entity_type IN ('RequirementVersion','ControlVersion','MappingVersion','PackVersion','PackMembership')",
    )
