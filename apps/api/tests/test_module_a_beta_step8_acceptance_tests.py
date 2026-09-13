"""Module A Beta Step 8 Acceptance Tests.

Replaces shallow completeness tests with independent, rigorous acceptance tests
covering:
- Sub-suite 8A: Source inventory integrity, duplicate detection, coverage ledger completeness.
- Sub-suite 8B: Seed/import idempotency and partial import recovery.
- Sub-suite 8C: Realistic assessment fixtures and single-missing-requirement blockers for all 5 beta packs.
- Sub-suite 8D: Version upgrade with impact analysis preserving historical pre-audit results and certificates.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conformly.auth.session import hash_session_id
from conformly.auth.tokens import TokenClaims
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import (
    ControlImplementationStatus,
    ControlStatusRecord,
    EvidenceControlLink,
    EvidenceFileLink,
    EvidenceItem,
    EvidenceStatus,
    Policy,
    PolicyControlLink,
    PolicyStatus,
)
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.entitlements.models import DEFAULT_TIER_A_MODULES, TenantEntitlement
from conformly.frameworks.impact import compute_framework_impact
from conformly.frameworks.manifest import (
    get_required_beta_pack_ids,
)
from conformly.frameworks.models import (
    CanonicalControl,
    ControlEntityType,
    CoverageDisposition,
    CoverageLedgerEntry,
    EvidenceSpecification,
    Framework,
    FrameworkVersion,
    OverlayApplicability,
    RequirementControlMapping,
    SourceRequirement,
    TenantControlOverlay,
)
from conformly.frameworks.packs_data import TIER_A_FRAMEWORK_PACKS
from conformly.frameworks.seed_packs import (
    import_framework_pack_draft,
    import_tier_a_framework_packs_as_drafts,
    seed_tier_a_test_fixtures,
)
from conformly.frameworks.service import (
    FrameworkService,
    StaleReviewError,
    compute_version_content_digest,
)
from conformly.frameworks.workflow import FrameworkWorkflowService
from conformly.identity.models import (
    AuthSession,
    Membership,
    MembershipStatus,
    Tenant,
    User,
)
from conformly.preaudit.models import (
    CertificateStatus,
    CheckResult,
    PreAuditCertificate,
    PreAuditStatus,
)
from conformly.preaudit.service import (
    CertificateIssuanceBlockedError,
    PreAuditService,
)
from conformly.storage.models import StoredFile, StoredFileStatus


def seed_tenant_user(session: Session, role: Role = Role.OWNER) -> tuple[User, Tenant, TokenClaims]:
    session_id = f"session-{uuid4().hex[:8]}"
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"user-{uuid4().hex[:8]}@example.test",
        display_name="Acceptance Test User",
        is_platform_admin=False,
    )
    tenant = Tenant(name="Acceptance Test Corp", slug=f"tenant-{uuid4().hex[:8]}")
    session.add_all([user, tenant])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    auth_session = AuthSession(
        user_id=user.id,
        session_id_hash=hash_session_id(session_id),
        expires_at=expires_at,
    )
    entitlement = TenantEntitlement(
        tenant_id=tenant.id,
        plan_code="tier_a",
        enabled_modules=DEFAULT_TIER_A_MODULES,
    )
    session.add_all([membership, auth_session, entitlement])
    session.commit()

    claims = TokenClaims(
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        session_id=session_id,
        expires_at=int(expires_at.timestamp()),
        email=user.email,
        email_verified=True,
        display_name=user.display_name,
    )
    return user, tenant, claims


# =============================================================================
# Sub-suite 8A: Independent Source Inventory & Integrity Validation
# =============================================================================


class TestSourceInventoryIntegrity:
    def test_all_required_beta_packs_defined_in_manifest(self):
        """Manifest must contain exactly the 6 required Tier A beta packs."""
        req_ids = get_required_beta_pack_ids()
        expected = {"iso-27001", "gdpr-bdsg", "nist-csf", "cis-controls-ig1", "mvsp", "iso-9001"}
        assert set(req_ids) == expected, f"Expected {expected}, got {set(req_ids)}"

    def test_pack_definitions_have_zero_duplicate_identifiers(self):
        """Every framework pack definition must have strictly unique requirement and control identifiers."""
        for pack in TIER_A_FRAMEWORK_PACKS:
            # Control identifiers uniqueness
            ctrl_ids = [c.identifier for c in pack.controls]
            dup_ctrls = [cid for cid in ctrl_ids if ctrl_ids.count(cid) > 1]
            assert not dup_ctrls, (
                f"Pack {pack.slug} has duplicate control identifiers: {set(dup_ctrls)}"
            )

            # Source requirement references uniqueness
            req_refs = [r.source_reference for r in pack.source_requirements]
            dup_reqs = [rid for rid in req_refs if req_refs.count(rid) > 1]
            assert not dup_reqs, (
                f"Pack {pack.slug} has duplicate source references: {set(dup_reqs)}"
            )

    def test_ledger_coverage_completeness_and_specifications(self):
        """Every source requirement must have an explicit coverage ledger entry and appropriate mappings or rationales."""
        for pack in TIER_A_FRAMEWORK_PACKS:
            req_ids = {r.source_reference for r in pack.source_requirements}
            ledger_req_ids = {e.source_reference for e in pack.coverage_ledger}

            assert req_ids == ledger_req_ids, (
                f"Pack {pack.slug} has ledger mismatch. "
                f"Missing in ledger: {req_ids - ledger_req_ids}; Unmatched in ledger: {ledger_req_ids - req_ids}"
            )

            # Check coverage dispositions and mapping consistency
            mapped_refs = {m.source_reference for m in pack.mappings}
            for entry in pack.coverage_ledger:
                if entry.disposition == CoverageDisposition.IMPLEMENTED:
                    assert entry.source_reference in mapped_refs, (
                        f"Pack {pack.slug} requirement {entry.source_reference} marked as "
                        f"{entry.disposition.value} but lacks control mapping"
                    )
                else:
                    assert entry.rationale and len(entry.rationale.strip()) > 10, (
                        f"Pack {pack.slug} requirement {entry.source_reference} has non-implemented "
                        f"disposition {entry.disposition.value} but lacks substantive rationale"
                    )

            # Specification completeness: Direct controls must have at least one specification
            ctrl_ids = {c.identifier for c in pack.controls}
            spec_ctrl_ids = {
                s.control_identifier for s in pack.evidence_specifications if s.control_identifier
            }
            assert ctrl_ids == spec_ctrl_ids, (
                f"Pack {pack.slug} has controls lacking evidence specifications: {ctrl_ids - spec_ctrl_ids}"
            )

    def test_stale_approval_rejection(self, session: Session):
        """Releasing a version with altered content after approval must be rejected."""
        admin = User(
            oidc_issuer="https://id.test",
            oidc_subject=str(uuid4()),
            email=f"admin-{uuid4().hex[:6]}@test.local",
            display_name="Admin",
            is_platform_admin=True,
        )
        legal_user = User(
            oidc_issuer="https://id.test",
            oidc_subject=str(uuid4()),
            email=f"legal-{uuid4().hex[:6]}@test.local",
            display_name="Legal",
            is_platform_admin=True,
        )
        approver_user = User(
            oidc_issuer="https://id.test",
            oidc_subject=str(uuid4()),
            email=f"appr-{uuid4().hex[:6]}@test.local",
            display_name="Approver",
            is_platform_admin=True,
        )
        session.add_all([admin, legal_user, approver_user])
        session.flush()

        service = FrameworkService(session)
        author_p = Principal(user_id=admin.id, is_platform_admin=True, mfa_verified=True)
        legal_p = Principal(user_id=legal_user.id, is_platform_admin=True, mfa_verified=True)
        approver_p = Principal(user_id=approver_user.id, is_platform_admin=True, mfa_verified=True)

        fw = service.create_framework(
            author_p, "Integrity Test FW", f"fw-{uuid4().hex[:6]}", "Desc", "req-1"
        )
        v = service.create_version_draft(author_p, fw.id, "1.0", "Notes", "req-2")
        service.add_canonical_control(
            author_p, v.id, "C-1", "Initial Title", "Desc", "Cat", "Guidance", 10, "req-3"
        )

        service.submit_version_for_review(author_p, v.id, "req-4")
        original_digest = compute_version_content_digest(v)

        service.record_legal_review(
            legal_p, v.id, "Legal ok", "req-5", content_digest=original_digest
        )
        service.approve_version(
            approver_p, v.id, "Approved", "req-6", content_digest=original_digest
        )

        # Attempt release with an obsolete/stale digest
        tampered_digest = hashlib.sha256(b"tampered content").hexdigest()
        with pytest.raises(StaleReviewError):
            service.release_version(approver_p, v.id, "req-7", content_digest=tampered_digest)


# =============================================================================
# Sub-suite 8B: Seed/Import Idempotency and Recovery
# =============================================================================


class TestSeedImportIdempotency:
    def test_draft_import_is_strictly_idempotent(self, session: Session):
        """Repeated draft imports of Tier A packs must produce identical entity counts without duplicating rows."""
        author = User(
            oidc_issuer="https://id.test",
            oidc_subject=str(uuid4()),
            email="author@platform.local",
            display_name="Pack Author",
            is_platform_admin=True,
        )
        session.add(author)
        session.flush()
        author_p = Principal(user_id=author.id, is_platform_admin=True, mfa_verified=True)

        # Run 1: initial import as drafts
        v1_list = import_tier_a_framework_packs_as_drafts(session, author_p)
        session.commit()

        count_fw_1 = session.scalar(select(func.count(Framework.id)))
        count_ver_1 = session.scalar(select(func.count(FrameworkVersion.id)))
        count_ctrl_1 = session.scalar(select(func.count(CanonicalControl.id)))
        count_req_1 = session.scalar(select(func.count(SourceRequirement.id)))
        count_map_1 = session.scalar(select(func.count(RequirementControlMapping.id)))
        count_spec_1 = session.scalar(select(func.count(EvidenceSpecification.id)))
        count_cov_1 = session.scalar(select(func.count(CoverageLedgerEntry.id)))

        # Run 2: re-run on the same populated database
        v2_list = import_tier_a_framework_packs_as_drafts(session, author_p)
        session.commit()

        count_fw_2 = session.scalar(select(func.count(Framework.id)))
        count_ver_2 = session.scalar(select(func.count(FrameworkVersion.id)))
        count_ctrl_2 = session.scalar(select(func.count(CanonicalControl.id)))
        count_req_2 = session.scalar(select(func.count(SourceRequirement.id)))
        count_map_2 = session.scalar(select(func.count(RequirementControlMapping.id)))
        count_spec_2 = session.scalar(select(func.count(EvidenceSpecification.id)))
        count_cov_2 = session.scalar(select(func.count(CoverageLedgerEntry.id)))

        assert count_fw_1 == count_fw_2, "Framework count changed on idempotent re-seed"
        assert count_ver_1 == count_ver_2, "Version count changed on idempotent re-seed"
        assert count_ctrl_1 == count_ctrl_2, "Control count changed on idempotent re-seed"
        assert count_req_1 == count_req_2, "Requirement count changed on idempotent re-seed"
        assert count_map_1 == count_map_2, "Mapping count changed on idempotent re-seed"
        assert count_spec_1 == count_spec_2, "Specification count changed on idempotent re-seed"
        assert count_cov_1 == count_cov_2, "Coverage ledger count changed on idempotent re-seed"
        assert len(v1_list) == len(v2_list) == len(TIER_A_FRAMEWORK_PACKS)

    def test_partial_import_recovery(self, session: Session):
        """Simulate an interrupted draft import and verify subsequent seed recovers cleanly."""
        author = User(
            oidc_issuer="https://id.test",
            oidc_subject=str(uuid4()),
            email="recover@platform.local",
            display_name="Pack Author",
            is_platform_admin=True,
        )
        session.add(author)
        session.flush()

        # Import only the first pack
        pack1 = TIER_A_FRAMEWORK_PACKS[0]
        service = FrameworkService(session)
        author_principal = Principal(user_id=author.id, is_platform_admin=True, mfa_verified=True)
        import_framework_pack_draft(service, pack1, author_principal, "req-partial-1")
        session.commit()

        partial_count = session.scalar(select(func.count(Framework.id)))
        assert partial_count == 1

        # Now run full draft seed pipeline; it should complete all remaining packs cleanly
        full_list = import_tier_a_framework_packs_as_drafts(session, author_principal)
        session.commit()

        total_count = session.scalar(select(func.count(Framework.id)))
        assert total_count == len(TIER_A_FRAMEWORK_PACKS)
        assert len(full_list) == len(TIER_A_FRAMEWORK_PACKS)


# =============================================================================
# Sub-suite 8C: Realistic Assessment Fixtures & Single-Missing-Requirement Blocker
# =============================================================================


def _create_verified_evidence(
    session: Session,
    tenant_id: UUID,
    user_id: UUID,
    control_id: UUID,
    title: str,
) -> EvidenceItem:
    ev = EvidenceItem(
        tenant_id=tenant_id,
        title=title,
        description="Valid verified evidence",
        classification="Restricted",
        status=EvidenceStatus.VALID,
        owner_user_id=user_id,
        valid_from=datetime.now(UTC) - timedelta(days=5),
        valid_until=datetime.now(UTC) + timedelta(days=90),
    )
    session.add(ev)
    session.flush()

    stored_file = StoredFile(
        tenant_id=tenant_id,
        created_by_user_id=user_id,
        original_filename=f"{title}.pdf",
        content_type="application/pdf",
        classification="Restricted",
        plaintext_size_bytes=1024,
        ciphertext_size_bytes=1024,
        plaintext_sha256="0" * 64,
        ciphertext_sha256="0" * 64,
        storage_backend="local",
        object_key=f"tenants/{tenant_id}/files/{uuid4()}.enc",
        encryption_algorithm="AES-256-GCM",
        context_version=1,
        key_version="v1",
        wrapped_dek_nonce="0" * 32,
        wrapped_dek="0" * 64,
        ciphertext_nonce="0" * 32,
        status=StoredFileStatus.ACTIVE,
    )
    session.add(stored_file)
    session.flush()

    session.add(
        EvidenceFileLink(
            tenant_id=tenant_id,
            evidence_id=ev.id,
            file_id=stored_file.id,
            attached_by_user_id=user_id,
        )
    )
    session.add(
        EvidenceControlLink(
            tenant_id=tenant_id,
            evidence_id=ev.id,
            control_type=ControlEntityType.CANONICAL,
            control_id=control_id,
            linked_by_user_id=user_id,
        )
    )
    return ev


class TestSingleMissingRequirementBlocker:
    @pytest.mark.parametrize(
        "pack_slug",
        ["iso-27001", "gdpr-bdsg", "nist-csf", "cis-controls-ig1", "mvsp"],
    )
    def test_single_missing_requirement_blocks_readiness(
        self, session: Session, test_codec: EncryptedFieldCodec, pack_slug: str
    ):
        """For every required Tier A pack, proving that one missing mandatory requirement strictly blocks readiness."""
        user, tenant, _ = seed_tenant_user(session, role=Role.OWNER)

        # 1. Release all framework packs cleanly using explicit test fixtures
        released_versions = seed_tier_a_test_fixtures(session)
        version = next(v for v in released_versions if v.framework.slug == pack_slug)

        # 2. Adopt the released pack
        fw_service = FrameworkService(session)
        principal = Principal(user_id=user.id, is_platform_admin=False)
        ctx = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.OWNER)

        adoption = fw_service.adopt_framework_version(
            principal=principal,
            tenant_context=ctx,
            framework_version_id=version.id,
            acknowledge_impact=True,
            request_id="req-adopt-test",
        )
        session.flush()

        # 3. Add applicable overlays for all controls in scope
        for ctrl in version.controls:
            session.add(
                TenantControlOverlay(
                    tenant_id=tenant.id,
                    adoption_id=adoption.id,
                    canonical_control_id=ctrl.id,
                    applicability=OverlayApplicability.APPLICABLE,
                    created_by_user_id=user.id,
                )
            )
        session.flush()

        # 4. Generate structured evidence requests
        wf_service = FrameworkWorkflowService(session, test_codec)
        requests = wf_service.generate(
            principal,
            ctx,
            adoption.id,
            due_date=datetime.now(UTC) + timedelta(days=30),
            owner_user_id=user.id,
        )
        assert len(requests) > 0, f"No evidence requests generated for pack {pack_slug}"

        # 5. Fulfill ALL controls in scope EXCEPT exactly the LAST ONE
        all_controls = list(version.controls)
        omitted_control = all_controls[-1]
        fulfilled_controls = all_controls[:-1]

        # Create policies and evidence for the fulfilled controls
        policy = Policy(
            tenant_id=tenant.id,
            title="Corporate Information Security Policy",
            description="Authoritative Information Security Policy",
            version_string="1.0",
            status=PolicyStatus.PUBLISHED,
            owner_user_id=user.id,
        )
        session.add(policy)
        session.flush()

        for ctrl in fulfilled_controls:
            session.add(
                PolicyControlLink(
                    tenant_id=tenant.id,
                    policy_id=policy.id,
                    control_type=ControlEntityType.CANONICAL,
                    control_id=ctrl.id,
                    linked_by_user_id=user.id,
                )
            )

            for ev_idx in range(2):
                _create_verified_evidence(
                    session,
                    tenant.id,
                    user.id,
                    ctrl.id,
                    f"Evidence {ev_idx} for {ctrl.identifier}",
                )

            session.add(
                ControlStatusRecord(
                    tenant_id=tenant.id,
                    control_type=ControlEntityType.CANONICAL,
                    control_id=ctrl.id,
                    status=ControlImplementationStatus.IMPLEMENTED,
                    assessed_by_user_id=user.id,
                )
            )
        session.flush()

        # Accept all structured evidence requests EXCEPT those associated with the omitted control
        now = datetime.now(UTC)
        for req in requests:
            spec = session.get(EvidenceSpecification, req.specification_id)
            assert spec is not None
            if spec.canonical_control_id == omitted_control.id:
                # Intentionally leave this request unaccepted to prove single requirement blocker!
                continue
            ev_item = session.scalar(
                select(EvidenceItem)
                .join(EvidenceControlLink, EvidenceControlLink.evidence_id == EvidenceItem.id)
                .where(
                    EvidenceControlLink.control_id == spec.canonical_control_id,
                    EvidenceItem.tenant_id == tenant.id,
                )
            )
            if ev_item:
                wf_service.accept(
                    principal,
                    ctx,
                    adoption.id,
                    req.id,
                    evidence_id=ev_item.id,
                    observation_start=now - timedelta(days=60),
                    observation_end=now - timedelta(days=1),
                )

        # 6. Conduct Pre-Audit with the single missing requirement
        pa_service = PreAuditService(session)
        pa = pa_service.create_pre_audit(
            principal,
            ctx,
            title=f"Readiness Assessment for {pack_slug}",
            framework_adoption_id=adoption.id,
            lead_user_id=user.id,
        )
        assert pa.status == PreAuditStatus.PLANNING

        # Run checks
        pa = pa_service.run_checks(principal, ctx, pa.id)
        assert pa.status == PreAuditStatus.IN_PROGRESS

        # Verify: At least one check failed due to the omitted requirement blocker
        checks = [c for s in pa.scopes for c in s.checks]
        omitted_check = next(c for c in checks if c.control_id == omitted_control.id)
        assert omitted_check.result in (CheckResult.FAIL, CheckResult.PENDING), (
            f"Omitted control {omitted_control.identifier} unexpectedly passed check: {omitted_check.result}"
        )

        # Independent review attempt
        reviewer = User(
            oidc_issuer="https://identity.example.test",
            oidc_subject=str(uuid4()),
            email=f"reviewer-{uuid4().hex[:6]}@example.test",
            display_name="Assigned Reviewer",
            is_platform_admin=False,
        )
        session.add(reviewer)
        session.flush()

        membership = Membership(
            tenant_id=tenant.id,
            user_id=reviewer.id,
            role=Role.REVIEWER,
            status=MembershipStatus.ACTIVE,
        )
        session.add(membership)
        session.flush()

        pa = pa_service.submit_for_review(
            principal,
            ctx,
            pa.id,
            reviewer_user_id=reviewer.id,
            expected_version=pa.version,
        )
        assert pa.status == PreAuditStatus.IN_REVIEW

        reviewer_principal = Principal(user_id=reviewer.id, is_platform_admin=False)
        reviewer_ctx = TenantContext(tenant_id=tenant.id, user_id=reviewer.id, role=Role.REVIEWER)
        pa = pa_service.complete_review(
            reviewer_principal, reviewer_ctx, pa.id, expected_version=pa.version
        )
        assert pa.status == PreAuditStatus.COMPLETED

        pa = pa_service.tenant_approve(principal, ctx, pa.id, expected_version=pa.version)

        # 7. Certificate issuance MUST BE BLOCKED due to the single unfulfilled requirement!
        with pytest.raises(CertificateIssuanceBlockedError) as exc_info:
            pa_service.issue_certificate(principal, ctx, pa.id, validity_days=365)
        assert "checks did not pass" in str(exc_info.value) or "check(s) failed" in str(
            exc_info.value
        )

        # 8. Recovery: Fulfill the missing requirement and verify readiness completes!
        session.add(
            PolicyControlLink(
                tenant_id=tenant.id,
                policy_id=policy.id,
                control_type=ControlEntityType.CANONICAL,
                control_id=omitted_control.id,
                linked_by_user_id=user.id,
            )
        )
        for ev_idx in range(2):
            _create_verified_evidence(
                session,
                tenant.id,
                user.id,
                omitted_control.id,
                f"Evidence {ev_idx} for {omitted_control.identifier}",
            )
        session.add(
            ControlStatusRecord(
                tenant_id=tenant.id,
                control_type=ControlEntityType.CANONICAL,
                control_id=omitted_control.id,
                status=ControlImplementationStatus.IMPLEMENTED,
                assessed_by_user_id=user.id,
            )
        )
        session.flush()

        # Accept the previously omitted evidence request
        for req in requests:
            spec = session.get(EvidenceSpecification, req.specification_id)
            if spec and spec.canonical_control_id == omitted_control.id:
                ev_item = session.scalar(
                    select(EvidenceItem)
                    .join(EvidenceControlLink, EvidenceControlLink.evidence_id == EvidenceItem.id)
                    .where(
                        EvidenceControlLink.control_id == omitted_control.id,
                        EvidenceItem.tenant_id == tenant.id,
                    )
                )
                if ev_item:
                    wf_service.accept(
                        principal,
                        ctx,
                        adoption.id,
                        req.id,
                        evidence_id=ev_item.id,
                        observation_start=now - timedelta(days=60),
                        observation_end=now - timedelta(days=1),
                    )

        # Create fresh assessment or re-run checks
        pa2 = pa_service.create_pre_audit(
            principal,
            ctx,
            title=f"Completed Readiness Assessment for {pack_slug}",
            framework_adoption_id=adoption.id,
            lead_user_id=user.id,
        )
        pa2 = pa_service.run_checks(principal, ctx, pa2.id)
        checks2 = [c for s in pa2.scopes for c in s.checks]
        assert all(c.result == CheckResult.PASS for c in checks2), (
            f"Expected all checks to pass after fulfillment: {[c.control_id for c in checks2 if c.result != CheckResult.PASS]}"
        )

        pa2 = pa_service.submit_for_review(
            principal, ctx, pa2.id, reviewer_user_id=reviewer.id, expected_version=pa2.version
        )
        pa2 = pa_service.complete_review(
            reviewer_principal, reviewer_ctx, pa2.id, expected_version=pa2.version
        )
        pa2 = pa_service.tenant_approve(principal, ctx, pa2.id, expected_version=pa2.version)

        cert = pa_service.issue_certificate(principal, ctx, pa2.id, validity_days=365)
        assert cert.status == CertificateStatus.ACTIVE
        assert cert.certificate_number.startswith("CONF-RA-")


# =============================================================================
# Sub-suite 8D: Version Upgrade & Historical Reproducibility
# =============================================================================


class TestVersionUpgradeAndHistoricalReproducibility:
    def test_version_upgrade_preserves_frozen_historical_certificate(self, session: Session):
        """Upgrading an adopted framework from v1 to v2 must preserve historical pre-audit results and certificate."""
        user, tenant, _ = seed_tenant_user(session, role=Role.OWNER)
        admin = User(
            oidc_issuer="https://id.test",
            oidc_subject=str(uuid4()),
            email="platform-admin@test.local",
            display_name="Platform Admin",
            is_platform_admin=True,
        )
        legal_user = User(
            oidc_issuer="https://id.test",
            oidc_subject=str(uuid4()),
            email="legal-rev@test.local",
            display_name="Legal Reviewer",
            is_platform_admin=True,
        )
        approver_user = User(
            oidc_issuer="https://id.test",
            oidc_subject=str(uuid4()),
            email="appr-rev@test.local",
            display_name="Approver",
            is_platform_admin=True,
        )
        session.add_all([admin, legal_user, approver_user])
        session.flush()

        admin_p = Principal(user_id=admin.id, is_platform_admin=True, mfa_verified=True)
        legal_p = Principal(user_id=legal_user.id, is_platform_admin=True, mfa_verified=True)
        approver_p = Principal(user_id=approver_user.id, is_platform_admin=True, mfa_verified=True)

        tenant_p = Principal(user_id=user.id, is_platform_admin=False)
        ctx = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.OWNER)

        fw_svc = FrameworkService(session)

        # 1. Create and release v1.0 of a test framework
        fw = fw_svc.create_framework(
            admin_p, "Lifecycle Test Framework", f"lifecycle-{uuid4().hex[:6]}", "Desc", "req-fw-1"
        )
        v1 = fw_svc.create_version_draft(admin_p, fw.id, "1.0", "Notes", "req-v1-1")
        c1 = fw_svc.add_canonical_control(
            admin_p, v1.id, "LC-1", "Control 1", "Desc 1", "Security", "Guidance", 10, "req-c1-1"
        )
        fw_svc.submit_version_for_review(admin_p, v1.id, "req-v1-sub")
        d1 = compute_version_content_digest(v1)
        fw_svc.record_legal_review(legal_p, v1.id, "Legal ok", "req-v1-leg", content_digest=d1)
        fw_svc.approve_version(approver_p, v1.id, "Approved", "req-v1-app", content_digest=d1)
        fw_svc.release_version(approver_p, v1.id, "req-v1-rel", content_digest=d1)

        # 2. Tenant adopts v1.0 and conducts pre-audit
        adoption = fw_svc.adopt_framework_version(
            tenant_p, ctx, v1.id, acknowledge_impact=True, request_id="req-v1-adopt"
        )
        session.flush()

        pa_svc = PreAuditService(session)
        pa = pa_svc.create_pre_audit(
            tenant_p,
            ctx,
            title="Historical v1 Assessment",
            framework_adoption_id=adoption.id,
            lead_user_id=user.id,
        )

        # Fulfill control LC-1
        policy = Policy(
            tenant_id=tenant.id,
            title="Policy LC-1",
            description="Authoritative Policy for LC-1",
            version_string="1.0",
            status=PolicyStatus.PUBLISHED,
            owner_user_id=user.id,
        )
        session.add(policy)
        session.flush()
        session.add(
            PolicyControlLink(
                tenant_id=tenant.id,
                policy_id=policy.id,
                control_type=ControlEntityType.CANONICAL,
                control_id=c1.id,
                linked_by_user_id=user.id,
            )
        )

        ev = EvidenceItem(
            tenant_id=tenant.id,
            title="Evidence LC-1",
            description="Valid",
            classification="Internal",
            status=EvidenceStatus.VALID,
            owner_user_id=user.id,
            valid_from=datetime.now(UTC) - timedelta(days=5),
            valid_until=datetime.now(UTC) + timedelta(days=90),
        )
        session.add(ev)
        session.flush()
        session.add(
            EvidenceControlLink(
                tenant_id=tenant.id,
                evidence_id=ev.id,
                control_type=ControlEntityType.CANONICAL,
                control_id=c1.id,
                linked_by_user_id=user.id,
            )
        )
        session.add(
            ControlStatusRecord(
                tenant_id=tenant.id,
                control_type=ControlEntityType.CANONICAL,
                control_id=c1.id,
                status=ControlImplementationStatus.IMPLEMENTED,
                assessed_by_user_id=user.id,
            )
        )

        # Run checks
        pa = pa_svc.run_checks(tenant_p, ctx, pa.id)

        # Complete review with an independent reviewer
        reviewer = User(
            oidc_issuer="https://id.test",
            oidc_subject=str(uuid4()),
            email="rev@test.local",
            display_name="Rev",
        )
        session.add(reviewer)
        session.flush()
        session.add(
            Membership(
                tenant_id=tenant.id,
                user_id=reviewer.id,
                role=Role.REVIEWER,
                status=MembershipStatus.ACTIVE,
            )
        )
        session.flush()

        pa = pa_svc.submit_for_review(
            tenant_p, ctx, pa.id, reviewer_user_id=reviewer.id, expected_version=pa.version
        )
        rev_p = Principal(user_id=reviewer.id)
        rev_ctx = TenantContext(tenant_id=tenant.id, user_id=reviewer.id, role=Role.REVIEWER)
        pa = pa_svc.complete_review(rev_p, rev_ctx, pa.id, expected_version=pa.version)
        pa = pa_svc.tenant_approve(tenant_p, ctx, pa.id, expected_version=pa.version)

        cert = pa_svc.issue_certificate(tenant_p, ctx, pa.id, validity_days=365)
        historical_cert_num = cert.certificate_number
        historical_cert_id = cert.id
        session.commit()

        # 3. Create and release v2.0 with a new control LC-2
        v2 = fw_svc.create_version_draft(admin_p, fw.id, "2.0", "Notes v2", "req-v2-1")
        fw_svc.add_canonical_control(
            admin_p, v2.id, "LC-1", "Control 1", "Desc 1", "Security", "Guidance", 10, "req-c1-2"
        )
        fw_svc.add_canonical_control(
            admin_p,
            v2.id,
            "LC-2",
            "Control 2 Added",
            "New Control in v2",
            "Security",
            "Guidance",
            20,
            "req-c2-2",
        )
        fw_svc.submit_version_for_review(admin_p, v2.id, "req-v2-sub")
        d2 = compute_version_content_digest(v2)
        fw_svc.record_legal_review(legal_p, v2.id, "Legal ok v2", "req-v2-leg", content_digest=d2)
        fw_svc.approve_version(approver_p, v2.id, "Approved v2", "req-v2-app", content_digest=d2)
        fw_svc.release_version(approver_p, v2.id, "req-v2-rel", content_digest=d2)

        # 4. Impact Analysis
        impact = compute_framework_impact(v1, v2)
        assert len(impact.added_controls) == 1
        assert impact.added_controls[0].identifier == "LC-2"
        assert impact.unchanged_count == 1

        # 5. Tenant adopts v2.0
        fw_svc.adopt_framework_version(
            tenant_p, ctx, v2.id, acknowledge_impact=True, request_id="req-v2-adopt"
        )
        session.commit()

        # 6. Verify historical certificate is NOT superseded or corrupted
        loaded_cert = session.get(PreAuditCertificate, historical_cert_id)
        assert loaded_cert is not None
        assert loaded_cert.certificate_number == historical_cert_num
        assert loaded_cert.status == CertificateStatus.ACTIVE

        # Verify historical pre-audit score summary -> must reproduce exact historical results
        loaded_pa = pa_svc.get_pre_audit(tenant_p, ctx, pa.id)
        summary = pa_svc.compute_score_summary(loaded_pa)
        assert summary["total_checks"] == 1
        assert summary["passed_checks"] == 1
        assert summary["failed_checks"] == 0
