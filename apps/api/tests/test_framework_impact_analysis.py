from uuid import uuid4

from sqlalchemy.orm import Session

from conformly.authz.policy import Principal
from conformly.frameworks.impact import compute_framework_impact
from conformly.frameworks.models import (
    ControlEntityType,
    ControlMapping,
    MappingType,
    OverlayApplicability,
    TenantControlOverlay,
    TenantFrameworkAdoption,
)
from conformly.frameworks.service import FrameworkService
from conformly.identity.models import Tenant, TenantStatus, User, UserStatus


def make_test_setup(
    session: Session,
) -> tuple[User, Principal, Tenant, FrameworkService]:
    user_id = uuid4()
    tenant_id = uuid4()

    user = User(
        id=user_id,
        oidc_issuer="https://issuer.example.com",
        oidc_subject=f"sub-{user_id.hex[:8]}",
        email=f"admin-{user_id.hex[:8]}@example.com",
        display_name="Admin User",
        status=UserStatus.ACTIVE,
        is_platform_admin=True,
    )
    tenant = Tenant(
        id=tenant_id,
        name="Acme Corp",
        slug=f"acme-{tenant_id.hex[:8]}",
        status=TenantStatus.ACTIVE,
    )
    session.add(user)
    session.add(tenant)
    session.flush()

    return (
        user,
        Principal(user_id=user.id, is_platform_admin=True),
        tenant,
        FrameworkService(session),
    )


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


def test_deterministic_diff_between_versions(session: Session) -> None:
    _, admin, _, service = make_test_setup(session)

    fw = service.create_framework(admin, "SOC 2", "soc-2", None, "req-1")

    # Version 2017 (Source)
    v1 = service.create_version_draft(admin, fw.id, "2017", None, "req-2")
    service.add_canonical_control(
        admin,
        v1.id,
        "CC1.1",
        "Integrity & Ethics",
        "Tone at the top",
        "Common Criteria",
        None,
        1,
        "req-3",
    )
    service.add_canonical_control(
        admin,
        v1.id,
        "CC1.2",
        "Board Independence",
        "Oversight by board",
        "Common Criteria",
        None,
        2,
        "req-4",
    )
    service.add_canonical_control(
        admin,
        v1.id,
        "CC1.3",
        "Management Structure",
        "Establish structure",
        "Common Criteria",
        None,
        3,
        "req-5",
    )

    # Version 2022 (Target): CC1.1 unchanged, CC1.2 modified, CC1.3 removed, CC2.1 added
    v2 = service.create_version_draft(admin, fw.id, "2022", None, "req-6")
    service.add_canonical_control(
        admin,
        v2.id,
        "CC1.1",
        "Integrity & Ethics",
        "Tone at the top",
        "Common Criteria",
        None,
        1,
        "req-7",
    )
    service.add_canonical_control(
        admin,
        v2.id,
        "CC1.2",
        "Board Oversight & Independence",  # Modified title
        "Expanded board oversight requirements",  # Modified description
        "Common Criteria",
        "Annual review recommended",  # Added guidance
        2,
        "req-8",
    )
    service.add_canonical_control(
        admin,
        v2.id,
        "CC2.1",
        "Communication",
        "Internal and external communication",
        "Communication",
        None,
        4,
        "req-9",
    )

    report = compute_framework_impact(v1, v2)

    assert report.source_version_string == "2017"
    assert report.target_version_string == "2022"
    assert report.unchanged_count == 1  # CC1.1

    # Added: CC2.1
    assert len(report.added_controls) == 1
    assert report.added_controls[0].identifier == "CC2.1"

    # Removed: CC1.3
    assert len(report.removed_controls) == 1
    assert report.removed_controls[0].identifier == "CC1.3"

    # Modified: CC1.2
    assert len(report.modified_controls) == 1
    mod = report.modified_controls[0]
    assert mod.identifier == "CC1.2"
    assert "title" in mod.changed_fields
    assert "description" in mod.changed_fields
    assert "guidance" in mod.changed_fields


def test_tenant_overlay_and_mapping_impact_warnings(session: Session) -> None:
    user, admin, tenant, service = make_test_setup(session)

    fw = service.create_framework(admin, "ISO 27001", "iso-27001", None, "req-1")

    # Version 2013
    v1 = service.create_version_draft(admin, fw.id, "2013", None, "req-2")
    c1 = service.add_canonical_control(
        admin, v1.id, "A.5.1", "Policies", "Security policies", "Org", None, 1, "req-3"
    )
    c2 = service.add_canonical_control(
        admin, v1.id, "A.8.1", "Asset Responsibility", "Inventory", "Asset", None, 2, "req-4"
    )

    # Release v1
    service.submit_version_for_review(admin, v1.id, "req-5")
    service.record_legal_review(admin, v1.id, "ok", "req-6")
    _, approver_p = make_user(session, is_admin=True)
    service.approve_version(approver_p, v1.id, "ok", "req-7")
    service.release_version(admin, v1.id, "req-8")

    # Version 2022: A.5.1 is modified; A.8.1 is removed
    v2 = service.create_version_draft(admin, fw.id, "2022", None, "req-9")
    service.add_canonical_control(
        admin,
        v2.id,
        "A.5.1",
        "Policies (Updated)",
        "Security policies updated",
        "Org",
        None,
        1,
        "req-10",
    )

    # Release v2
    service.submit_version_for_review(admin, v2.id, "req-11")
    service.record_legal_review(admin, v2.id, "ok", "req-12")
    service.approve_version(approver_p, v2.id, "ok", "req-13")
    service.release_version(admin, v2.id, "req-14")

    # Tenant adopts v1 and creates overlays on A.8.1 and A.5.1
    adoption = TenantFrameworkAdoption(
        tenant_id=tenant.id,
        framework_id=fw.id,
        framework_version_id=v1.id,
        adopted_at=v1.created_at,
        adopted_by_user_id=user.id,
    )
    session.add(adoption)
    session.flush()

    overlay_removed = TenantControlOverlay(
        tenant_id=tenant.id,
        adoption_id=adoption.id,
        canonical_control_id=c2.id,  # A.8.1
        applicability=OverlayApplicability.APPLICABLE,
        internal_notes="Our hardware asset management procedure",
        created_by_user_id=user.id,
    )
    overlay_modified = TenantControlOverlay(
        tenant_id=tenant.id,
        adoption_id=adoption.id,
        canonical_control_id=c1.id,  # A.5.1
        applicability=OverlayApplicability.APPLICABLE,
        internal_notes="Reviewed policy",
        created_by_user_id=user.id,
    )
    mapping_removed = ControlMapping(
        tenant_id=tenant.id,
        source_type=ControlEntityType.CANONICAL,
        source_control_id=c2.id,  # A.8.1
        target_type=ControlEntityType.CUSTOM,
        target_control_id=uuid4(),
        mapping_type=MappingType.SATISFIES,
        rationale="Hardware policy",
        created_by_user_id=user.id,
    )
    session.add_all([overlay_removed, overlay_modified, mapping_removed])
    session.flush()

    # Analyze impact with tenant context
    report = compute_framework_impact(
        v1, v2, [overlay_removed, overlay_modified], [mapping_removed]
    )

    assert report.overall_impact_level == "high"  # High due to breaking changes on active overlays

    severities = [w.severity for w in report.tenant_warnings]
    assert "breaking" in severities
    assert "review_required" in severities

    warning_idents = [w.control_identifier for w in report.tenant_warnings]
    assert "A.8.1" in warning_idents
    assert "A.5.1" in warning_idents
