"""Tests for Module A Beta Step 2 — Removal of Simulated Approval & Rigorous Human Gating.

Verifies:
1. One actor cannot self-approve (creator != approver, legal reviewer != approver).
2. Content import creates unapproved DRAFTS only and cannot manufacture approval.
3. Content edits invalidate pending approvals and stale content digests are rejected.
4. Unauthorized direct API calls (non-admin, missing MFA) fail.
5. Version retirement and quarantine preserve historical tenant adoptions and assessments.
"""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.frameworks.models import (
    AdoptionStatus,
    ReleaseState,
)
from conformly.frameworks.packs_data import TIER_A_FRAMEWORK_PACKS
from conformly.frameworks.seed_packs import (
    import_framework_pack_draft,
)
from conformly.frameworks.service import (
    FrameworkService,
    FrameworkVersionNotFoundError,
    ImmutableCanonicalVersionError,
    IndependentApprovalRequiredError,
    InvalidStateTransitionError,
    StaleReviewError,
    compute_version_content_digest,
)
from conformly.identity.models import Tenant, TenantStatus, User, UserStatus


def test_independent_approval_enforces_author_and_approver_separation(session: Session) -> None:
    """Creator of a framework version draft cannot approve their own version."""
    service = FrameworkService(session)
    author_id = uuid4()
    author = Principal(user_id=author_id, is_platform_admin=True, mfa_verified=True)

    fw = service.create_framework(author, "ISO 27001", "test-iso", "Test ISMS", "req-1")
    ver = service.create_version_draft(author, fw.id, "2026.1", "Notes", "req-2")
    service.add_canonical_control(
        author, ver.id, "A.5.1", "Policies", "Desc", "Gov", "Guidance", 10, "req-3"
    )
    service.submit_version_for_review(author, ver.id, "req-4")

    # Author conducts legal review
    service.record_legal_review(author, ver.id, "Legal review passed", "req-5")

    # Self-approval attempt must fail
    with pytest.raises(
        IndependentApprovalRequiredError, match="version creator cannot perform independent"
    ):
        service.approve_version(author, ver.id, "Attempting self-approval", "req-6")


def test_independent_approval_enforces_legal_reviewer_and_approver_separation(
    session: Session,
) -> None:
    """Legal reviewer cannot also act as the independent second-person approver."""
    service = FrameworkService(session)
    author_id = uuid4()
    legal_id = uuid4()

    author = Principal(user_id=author_id, is_platform_admin=True, mfa_verified=True)
    legal = Principal(user_id=legal_id, is_platform_admin=True, mfa_verified=True)

    fw = service.create_framework(author, "NIST CSF", "test-nist", "Test NIST", "req-10")
    ver = service.create_version_draft(author, fw.id, "2.0", "Notes", "req-11")
    service.add_canonical_control(
        author, ver.id, "GV.OC-01", "Context", "Desc", "Gov", "Guidance", 10, "req-12"
    )
    service.submit_version_for_review(author, ver.id, "req-13")

    # Legal reviewer conducts review
    service.record_legal_review(legal, ver.id, "Legal check complete", "req-14")

    # Legal reviewer attempting to act as approver must fail
    with pytest.raises(
        IndependentApprovalRequiredError, match="legal reviewer cannot perform final"
    ):
        service.approve_version(legal, ver.id, "Legal reviewer approving", "req-15")


def test_import_framework_pack_creates_draft_only(session: Session) -> None:
    """Normal import creates unapproved DRAFT versions only without auto-approval or fake reviews."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)
    mvsp_pack = next(p for p in TIER_A_FRAMEWORK_PACKS if p.slug == "mvsp")

    ver = import_framework_pack_draft(service, mvsp_pack, author, "req-import-1")

    assert ver.release_state == ReleaseState.DRAFT
    assert ver.legal_reviewed_by_user_id is None
    assert ver.legal_reviewed_at is None
    assert ver.approved_by_user_id is None
    assert ver.approved_at is None
    assert ver.released_at is None
    assert len(ver.controls) > 0

    # Tenant cannot adopt an unreleased draft
    tenant = Tenant(name="Test Corp", slug="test-corp", status=TenantStatus.ACTIVE)
    user = User(
        email="admin@testcorp.com",
        display_name="Admin",
        oidc_issuer="test",
        oidc_subject="sub1",
        status=UserStatus.ACTIVE,
    )
    session.add_all([tenant, user])
    session.flush()

    user_principal = Principal(user_id=user.id)
    tenant_ctx = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.OWNER)

    with pytest.raises((ValueError, FrameworkVersionNotFoundError)):
        service.adopt_framework_version(user_principal, tenant_ctx, ver.id, True, "req-adopt-1")


def test_content_edits_invalidate_pending_approvals_and_reject_stale_digests(
    session: Session,
) -> None:
    """Modifying controls in a draft clears pending reviews/approvals and rejects stale content digests."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)
    legal = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)
    fw = service.create_framework(author, "CIS Controls", "test-cis", "Test CIS", "req-cis-1")
    ver = service.create_version_draft(author, fw.id, "8.0", "Notes", "req-cis-2")
    service.add_canonical_control(
        author, ver.id, "1.1", "Inventory", "Desc", "Assets", "Guidance", 10, "req-cis-3"
    )

    digest_before = compute_version_content_digest(ver)
    service.submit_version_for_review(author, ver.id, "req-cis-4")
    service.record_legal_review(
        legal, ver.id, "Legal approved v1", "req-cis-5", content_digest=digest_before
    )

    # Attempting to edit content while in review MUST fail fail-closed!
    with pytest.raises(
        ImmutableCanonicalVersionError, match="cannot add controls to version in in_review state"
    ):
        service.add_canonical_control(
            author,
            ver.id,
            "1.2",
            "Unauthorized Assets",
            "Desc 2",
            "Assets",
            "Guidance",
            20,
            "req-cis-fail",
        )

    # Revert to draft explicitly via audited service method
    service.return_version_to_draft(
        author, ver.id, "Revising controls after legal review", "req-cis-revert"
    )

    # Pending legal review must have been invalidated!
    assert ver.legal_reviewed_by_user_id is None
    assert ver.legal_reviewed_at is None
    assert ver.release_state == ReleaseState.DRAFT

    # Author adds an additional control in draft
    service.add_canonical_control(
        author,
        ver.id,
        "1.2",
        "Unauthorized Assets",
        "Desc 2",
        "Assets",
        "Guidance",
        20,
        "req-cis-6",
    )

    # Re-submit for review
    service.submit_version_for_review(author, ver.id, "req-cis-7")

    # Stale review with old digest must be rejected!
    with pytest.raises(StaleReviewError, match="content has been modified"):
        service.record_legal_review(
            legal, ver.id, "Trying with stale digest", "req-cis-8", content_digest=digest_before
        )


def test_lifecycle_immutability_and_return_to_draft_workflow(session: Session) -> None:
    """Rigorous verification of fail-closed immutability during review/approval and explicit return-to-draft."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)
    legal = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)
    approver = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)
    non_admin = Principal(user_id=uuid4(), is_platform_admin=False, mfa_verified=True)
    no_mfa = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=False)

    fw = service.create_framework(author, "NIST Privacy", "nist-priv", "NIST Privacy", "req-np-1")
    ver = service.create_version_draft(author, fw.id, "1.0", "Initial", "req-np-2")
    ctrl = service.add_canonical_control(
        author, ver.id, "PR.PO-P1", "Privacy Policies", "Desc", "Governance", None, 1, "req-np-3"
    )

    # 1. Submit for review -> IN_REVIEW
    service.submit_version_for_review(author, ver.id, "req-np-4")
    assert ver.release_state == ReleaseState.IN_REVIEW

    # All mutations must be blocked in IN_REVIEW
    with pytest.raises(ImmutableCanonicalVersionError):
        service.add_canonical_control(
            author, ver.id, "PR.PO-P2", "Roles", "Desc", "Gov", None, 2, "req-fail-add"
        )
    with pytest.raises(ImmutableCanonicalVersionError):
        service.update_canonical_control(
            author, ctrl.id, "New Title", "New Desc", "Gov", None, 1, "req-fail-upd"
        )
    with pytest.raises(ImmutableCanonicalVersionError):
        service.delete_canonical_control(author, ctrl.id, "req-fail-del")

    # 2. Legal review & Approval -> APPROVED
    service.record_legal_review(legal, ver.id, "Legal sign-off", "req-np-5")
    service.approve_version(approver, ver.id, "Independent sign-off", "req-np-6")
    assert ver.release_state == ReleaseState.APPROVED

    # All mutations must be blocked in APPROVED
    with pytest.raises(ImmutableCanonicalVersionError):
        service.add_canonical_control(
            author, ver.id, "PR.PO-P2", "Roles", "Desc", "Gov", None, 2, "req-fail-appr-add"
        )
    with pytest.raises(ImmutableCanonicalVersionError):
        service.update_canonical_control(
            author, ctrl.id, "Updated Title", "Desc", "Gov", None, 1, "req-fail-appr-upd"
        )
    with pytest.raises(ImmutableCanonicalVersionError):
        service.delete_canonical_control(author, ctrl.id, "req-fail-appr-del")

    # 3. Authorization checks on return_version_to_draft
    with pytest.raises(PermissionError, match="only platform administrators"):
        service.return_version_to_draft(non_admin, ver.id, "Revert", "req-auth-1")
    with pytest.raises(PermissionError, match="multi-factor authentication required"):
        service.return_version_to_draft(no_mfa, ver.id, "Revert", "req-auth-2")
    with pytest.raises(ValueError, match="at least 3 characters"):
        service.return_version_to_draft(author, ver.id, "no", "req-auth-3")

    # 4. Successfully return APPROVED version to DRAFT
    returned = service.return_version_to_draft(
        author, ver.id, "Need to add missing control before release", "req-return-appr"
    )
    assert returned.release_state == ReleaseState.DRAFT
    assert returned.legal_reviewed_by_user_id is None
    assert returned.approved_by_user_id is None
    assert returned.approval_notes is None

    # Now mutation is permitted in DRAFT
    service.update_canonical_control(
        author,
        ctrl.id,
        "Refined Policy Control",
        "New Description",
        "Gov",
        None,
        1,
        "req-upd-draft",
    )

    # 5. Released versions CANNOT be returned to draft (must be superseded by a new version draft)
    service.submit_version_for_review(author, ver.id, "req-re-sub")
    service.record_legal_review(legal, ver.id, "Legal sign-off 2", "req-re-leg")
    service.approve_version(approver, ver.id, "Sign-off 2", "req-re-appr")
    service.release_version(approver, ver.id, "req-rel")
    assert ver.release_state == ReleaseState.RELEASED

    with pytest.raises(
        InvalidStateTransitionError, match="cannot return version in released state to draft"
    ):
        service.return_version_to_draft(
            author, ver.id, "Cannot revert released version", "req-rel-fail"
        )


def test_unauthorized_direct_calls_fail_security_checks(session: Session) -> None:
    """Non-admin principals or principals without verified MFA cannot review, approve, or release."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)
    non_admin = Principal(user_id=uuid4(), is_platform_admin=False, mfa_verified=True)
    no_mfa_admin = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=False)

    fw = service.create_framework(author, "GDPR", "test-gdpr", "Test GDPR", "req-g-1")
    ver = service.create_version_draft(author, fw.id, "2024", "Notes", "req-g-2")
    service.add_canonical_control(
        author, ver.id, "Art 5", "Principles", "Desc", "Law", "Guidance", 10, "req-g-3"
    )
    service.submit_version_for_review(author, ver.id, "req-g-4")

    # Non-admin rejected
    with pytest.raises(PermissionError, match="only platform administrators"):
        service.record_legal_review(non_admin, ver.id, "Notes", "req-g-5")

    # Admin without MFA rejected
    with pytest.raises(PermissionError, match="multi-factor authentication required"):
        service.record_legal_review(no_mfa_admin, ver.id, "Notes", "req-g-6")


def test_version_quarantine_and_retirement_preserves_historical_records(session: Session) -> None:
    """Retiring or quarantining a version blocks new adoptions while preserving existing tenant data."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)
    legal = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)
    approver = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)

    fw = service.create_framework(author, "Legacy Pack", "legacy-pack", "Legacy", "req-leg-1")
    ver = service.create_version_draft(author, fw.id, "1.0", "Notes", "req-leg-2")
    service.add_canonical_control(
        author, ver.id, "L.1", "Legacy Control", "Desc", "Legacy", "Guidance", 10, "req-leg-3"
    )
    service.submit_version_for_review(author, ver.id, "req-leg-4")
    service.record_legal_review(legal, ver.id, "Passed", "req-leg-5")
    service.approve_version(approver, ver.id, "Approved", "req-leg-6")
    service.release_version(approver, ver.id, "req-leg-7")

    # Tenant adopts released version
    tenant = Tenant(name="Active Customer", slug="active-customer", status=TenantStatus.ACTIVE)
    user = User(
        email="lead@activecustomer.com",
        display_name="Lead",
        oidc_issuer="test",
        oidc_subject="sub2",
        status=UserStatus.ACTIVE,
    )
    session.add_all([tenant, user])
    session.flush()

    user_principal = Principal(user_id=user.id)
    tenant_ctx = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.OWNER)
    adoption = service.adopt_framework_version(
        user_principal, tenant_ctx, ver.id, True, "req-adopt-leg"
    )
    assert adoption.status == AdoptionStatus.ACTIVE

    # Platform administrator quarantines the version due to an audit discrepancy
    quarantined = service.quarantine_version(
        approver, ver.id, reason="Audit revealed unverified source mapping", request_id="req-quar-1"
    )
    assert quarantined.release_state == ReleaseState.RETIRED
    assert quarantined.retired_at is not None

    # New tenant attempting to adopt quarantined version must be blocked!
    tenant2 = Tenant(name="New Customer", slug="new-customer", status=TenantStatus.ACTIVE)
    session.add(tenant2)
    session.flush()
    tenant2_ctx = TenantContext(tenant_id=tenant2.id, user_id=user.id, role=Role.OWNER)

    with pytest.raises(ValueError, match="cannot adopt version in non-released state: retired"):
        service.adopt_framework_version(user_principal, tenant2_ctx, ver.id, True, "req-adopt-fail")

    # Active adoptions under quarantined version are surfaced for human disposition
    affected = service.list_adoptions_for_retired_version(approver, ver.id)
    assert len(affected) == 1
    assert affected[0].tenant_id == tenant.id
    # Historical adoption remains intact and readable
    assert affected[0].status == AdoptionStatus.ACTIVE
