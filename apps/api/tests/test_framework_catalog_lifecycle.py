from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal
from conformly.frameworks.models import (
    CanonicalControl,
    ReleaseState,
)
from conformly.frameworks.service import (
    FrameworkService,
    ImmutableCanonicalVersionError,
    IndependentApprovalRequiredError,
    InvalidStateTransitionError,
    UnapprovedReleaseError,
)
from conformly.identity.models import User, UserStatus


def make_user(session: Session, is_admin: bool = False) -> tuple[User, Principal]:
    user_id = uuid4()
    user = User(
        id=user_id,
        oidc_issuer="https://issuer.example.com",
        oidc_subject=f"sub-{user_id.hex[:8]}",
        email=f"user-{user_id.hex[:8]}@example.com",
        display_name=f"User {user_id.hex[:6]}",
        status=UserStatus.ACTIVE,
        is_platform_admin=is_admin,
    )
    session.add(user)
    session.flush()
    return user, Principal(user_id=user.id, is_platform_admin=is_admin)


def test_platform_admin_can_create_framework_and_version(session: Session) -> None:
    _, admin_principal = make_user(session, is_admin=True)
    service = FrameworkService(session)

    fw = service.create_framework(
        admin_principal,
        name="ISO/IEC 27001",
        slug="iso-27001",
        description="Information security management systems",
        request_id="req-1",
    )
    assert fw.id is not None
    assert fw.slug == "iso-27001"

    v = service.create_version_draft(
        admin_principal,
        framework_id=fw.id,
        version_str="2022",
        release_notes="Updated controls taxonomy",
        request_id="req-2",
    )
    assert v.id is not None
    assert v.release_state == ReleaseState.DRAFT
    assert v.version == "2022"


def test_non_platform_admin_denied_canonical_mutations(session: Session) -> None:
    _, normal_principal = make_user(session, is_admin=False)
    _, admin_principal = make_user(session, is_admin=True)
    service = FrameworkService(session)

    fw = service.create_framework(
        admin_principal,
        name="SOC 2",
        slug="soc-2",
        description="Trust Services Criteria",
        request_id="req-1",
    )

    with pytest.raises(PermissionError, match="platform administrator"):
        service.create_framework(
            normal_principal,
            name="HIPAA",
            slug="hipaa",
            description="Health Insurance Portability and Accountability Act",
            request_id="req-2",
        )

    with pytest.raises(PermissionError, match="platform administrator"):
        service.create_version_draft(
            normal_principal,
            framework_id=fw.id,
            version_str="2017",
            release_notes=None,
            request_id="req-3",
        )


def test_canonical_controls_lifecycle_and_immutability(session: Session) -> None:
    _, admin_principal = make_user(session, is_admin=True)
    service = FrameworkService(session)

    fw = service.create_framework(
        admin_principal, name="NIST CSF", slug="nist-csf", description=None, request_id="req-1"
    )
    v = service.create_version_draft(
        admin_principal, fw.id, "2.0", "Draft version", request_id="req-2"
    )

    ctrl = service.add_canonical_control(
        admin_principal,
        version_id=v.id,
        identifier="GV.OC-01",
        title="Organizational Context",
        description="The mission, goals, and organizational context are understood",
        category="Govern",
        guidance="Identify and communicate organizational context",
        sort_order=1,
        request_id="req-3",
    )
    assert ctrl.id is not None
    assert ctrl.identifier == "GV.OC-01"

    updated = service.update_canonical_control(
        admin_principal,
        control_id=ctrl.id,
        title="Organizational Context (Updated)",
        description="Updated description",
        category="Govern",
        guidance=None,
        sort_order=2,
        request_id="req-4",
    )
    assert updated.title == "Organizational Context (Updated)"

    ctrl2 = service.add_canonical_control(
        admin_principal,
        version_id=v.id,
        identifier="GV.OC-02",
        title="Risk Tolerances",
        description="Risk tolerances are determined and clearly expressed",
        category="Govern",
        guidance=None,
        sort_order=2,
        request_id="req-5",
    )
    service.delete_canonical_control(admin_principal, ctrl2.id, request_id="req-6")
    assert session.get(CanonicalControl, ctrl2.id) is None


def test_independent_second_person_approval_rule(session: Session) -> None:
    _, creator_principal = make_user(session, is_admin=True)
    _, reviewer_principal = make_user(session, is_admin=True)
    _, second_admin_principal = make_user(session, is_admin=True)
    service = FrameworkService(session)

    fw = service.create_framework(
        creator_principal, name="PCI-DSS", slug="pci-dss", description=None, request_id="req-1"
    )
    v = service.create_version_draft(
        creator_principal, fw.id, "4.0", "Draft version", request_id="req-2"
    )
    service.add_canonical_control(
        creator_principal,
        version_id=v.id,
        identifier="Req-1",
        title="Firewall Configuration",
        description="Install and maintain network security controls",
        category="Network Security",
        guidance=None,
        sort_order=1,
        request_id="req-3",
    )

    # Submit for review
    v = service.submit_version_for_review(creator_principal, v.id, request_id="req-4")
    assert v.release_state == ReleaseState.IN_REVIEW

    # Cannot mutate controls while in review
    with pytest.raises(ImmutableCanonicalVersionError):
        service.add_canonical_control(
            creator_principal,
            version_id=v.id,
            identifier="Req-2",
            title="System Passwords",
            description="Do not use vendor defaults",
            category="System Security",
            guidance=None,
            sort_order=2,
            request_id="req-5",
        )

    # Approval before legal review is rejected
    with pytest.raises(InvalidStateTransitionError, match="legal and compliance review"):
        service.approve_version(second_admin_principal, v.id, "Looks good", request_id="req-6")

    # Record legal review
    service.record_legal_review(
        reviewer_principal, v.id, "Legal and compliance checks passed.", request_id="req-7"
    )

    # Independent second-person approval rule: creator CANNOT approve their own draft!
    with pytest.raises(IndependentApprovalRequiredError, match="creator cannot perform"):
        service.approve_version(creator_principal, v.id, "Self-approval", request_id="req-8")

    # Independent second person approves
    v = service.approve_version(
        second_admin_principal, v.id, "Independent sign-off", request_id="req-9"
    )
    assert v.release_state == ReleaseState.APPROVED
    assert v.approved_by_user_id == second_admin_principal.user_id


def test_unapproved_release_denial_and_immutability_post_release(session: Session) -> None:
    _, creator = make_user(session, is_admin=True)
    _, approver = make_user(session, is_admin=True)
    service = FrameworkService(session)

    fw = service.create_framework(
        creator, name="CIS Controls", slug="cis", description=None, request_id="req-1"
    )
    v = service.create_version_draft(creator, fw.id, "v8", None, request_id="req-2")
    service.add_canonical_control(
        creator,
        v.id,
        "CIS-1",
        "Inventory of Assets",
        "Manage devices",
        "Asset Management",
        None,
        1,
        "req-3",
    )

    # Releasing while still draft fails
    with pytest.raises(UnapprovedReleaseError):
        service.release_version(creator, v.id, request_id="req-4")

    # Move to in_review
    service.submit_version_for_review(creator, v.id, request_id="req-5")

    # Releasing while still in_review fails
    with pytest.raises(UnapprovedReleaseError):
        service.release_version(creator, v.id, request_id="req-6")

    # Legal review & approval
    service.record_legal_review(creator, v.id, "Legal ok", request_id="req-7")
    service.approve_version(approver, v.id, "Approved", request_id="req-8")

    # Now release succeeds
    v = service.release_version(creator, v.id, request_id="req-9")
    assert v.release_state == ReleaseState.RELEASED
    assert v.released_at is not None

    # Post-release immutability: attempting to mutate controls fails
    with pytest.raises(ImmutableCanonicalVersionError):
        service.add_canonical_control(
            creator,
            v.id,
            "CIS-2",
            "Inventory of Software",
            "Manage apps",
            "Software",
            None,
            2,
            "req-10",
        )

    # Retiring version
    v = service.retire_version(creator, v.id, request_id="req-11")
    assert v.release_state == ReleaseState.RETIRED
    assert v.retired_at is not None
