from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.frameworks.models import (
    AdoptionStatus,
    CanonicalControl,
    ControlEntityType,
    MappingType,
    OverlayApplicability,
    TenantFrameworkAdoption,
)
from conformly.frameworks.service import (
    AdoptionNotFoundError,
    ControlOverlayNotFoundError,
    FrameworkService,
)
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
)


def make_tenant(session: Session, name: str) -> tuple[Tenant, User, TenantContext, Principal]:
    tenant_id = uuid4()
    user_id = uuid4()

    tenant = Tenant(
        id=tenant_id,
        name=name,
        slug=f"tenant-{tenant_id.hex[:8]}",
        status=TenantStatus.ACTIVE,
    )
    user = User(
        id=user_id,
        oidc_issuer="https://issuer.example.com",
        oidc_subject=f"sub-{user_id.hex[:8]}",
        email=f"user-{user_id.hex[:8]}@example.com",
        display_name=f"User {name}",
        status=UserStatus.ACTIVE,
        is_platform_admin=False,
    )
    membership = Membership(
        tenant_id=tenant_id,
        user_id=user_id,
        role=Role.COMPLIANCE_MANAGER,
        status=MembershipStatus.ACTIVE,
    )
    session.add_all([tenant, user, membership])
    session.flush()

    return (
        tenant,
        user,
        TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.COMPLIANCE_MANAGER),
        Principal(user_id=user_id, is_platform_admin=False),
    )


def setup_released_framework(
    session: Session,
) -> tuple[FrameworkService, UUID, UUID, UUID, CanonicalControl, CanonicalControl]:
    admin_id = uuid4()
    approver_id = uuid4()

    admin = User(
        id=admin_id,
        oidc_issuer="https://issuer.example.com",
        oidc_subject=f"sub-{admin_id.hex[:8]}",
        email="admin@example.com",
        display_name="Admin",
        status=UserStatus.ACTIVE,
        is_platform_admin=True,
    )
    approver = User(
        id=approver_id,
        oidc_issuer="https://issuer.example.com",
        oidc_subject=f"sub-{approver_id.hex[:8]}",
        email="approver@example.com",
        display_name="Approver",
        status=UserStatus.ACTIVE,
        is_platform_admin=True,
    )
    session.add_all([admin, approver])
    session.flush()

    admin_p = Principal(user_id=admin.id, is_platform_admin=True)
    approver_p = Principal(user_id=approver.id, is_platform_admin=True)

    service = FrameworkService(session)
    fw = service.create_framework(admin_p, "ISO 27001", "iso-27001", None, "req-1")

    # v1
    v1 = service.create_version_draft(admin_p, fw.id, "2013", None, "req-2")
    c1 = service.add_canonical_control(
        admin_p,
        v1.id,
        "A.5.1",
        "Policies",
        "Information security policies",
        "Org",
        None,
        1,
        "req-3",
    )
    service.submit_version_for_review(admin_p, v1.id, "req-4")
    service.record_legal_review(admin_p, v1.id, "ok", "req-5")
    service.approve_version(approver_p, v1.id, "ok", "req-6")
    service.release_version(admin_p, v1.id, "req-7")

    # v2
    v2 = service.create_version_draft(admin_p, fw.id, "2022", None, "req-8")
    c2 = service.add_canonical_control(
        admin_p,
        v2.id,
        "A.5.1",
        "Policies (2022)",
        "Updated security policies",
        "Org",
        None,
        1,
        "req-9",
    )
    service.submit_version_for_review(admin_p, v2.id, "req-10")
    service.record_legal_review(admin_p, v2.id, "ok", "req-11")
    service.approve_version(approver_p, v2.id, "ok", "req-12")
    service.release_version(admin_p, v2.id, "req-13")

    return service, fw.id, v1.id, v2.id, c1, c2


def test_tenant_adoption_and_upgrade(session: Session) -> None:
    service, fw_id, v1_id, v2_id, c1, c2 = setup_released_framework(session)
    tenant, user, t_ctx, principal = make_tenant(session, "Tenant Alpha")

    # 1. Adopt Version 1
    adoption = service.adopt_framework_version(
        principal=principal,
        tenant_context=t_ctx,
        framework_version_id=v1_id,
        acknowledge_impact=True,
        request_id="req-adopt-1",
    )
    assert adoption.status == AdoptionStatus.ACTIVE
    assert adoption.framework_version_id == v1_id
    assert adoption.tenant_id == tenant.id

    # 2. Add Overlay to A.5.1 on Adoption 1
    overlay = service.manage_overlay(
        principal=principal,
        tenant_context=t_ctx,
        adoption_id=adoption.id,
        canonical_control_id=c1.id,
        applicability=OverlayApplicability.APPLICABLE,
        justification="Applicable to cloud operations",
        internal_notes="Reviewed quarterly",
        custom_guidance="Follow Confluence policy link",
        request_id="req-overlay-1",
    )
    assert overlay.id is not None
    assert overlay.applicability == OverlayApplicability.APPLICABLE

    # 3. Upgrade to Version 2: old adoption superseded, new adoption active, overlay migrated
    new_adoption = service.adopt_framework_version(
        principal=principal,
        tenant_context=t_ctx,
        framework_version_id=v2_id,
        acknowledge_impact=True,
        request_id="req-adopt-2",
    )
    assert new_adoption.status == AdoptionStatus.ACTIVE
    assert new_adoption.framework_version_id == v2_id
    assert new_adoption.impact_summary_json is not None

    # Verify old adoption is superseded
    old_adp = session.get(TenantFrameworkAdoption, adoption.id)
    assert old_adp is not None
    assert old_adp.status == AdoptionStatus.SUPERSEDED

    # Verify overlays migrated to new adoption for A.5.1
    new_overlays = service.list_overlays(t_ctx, new_adoption.id)
    assert len(new_overlays) == 1
    assert new_overlays[0].canonical_control_id == c2.id
    assert new_overlays[0].justification == "Applicable to cloud operations"


def test_tenant_overlay_isolation(session: Session) -> None:
    service, fw_id, v1_id, v2_id, c1, _ = setup_released_framework(session)
    t_a, u_a, ctx_a, p_a = make_tenant(session, "Tenant A")
    t_b, u_b, ctx_b, p_b = make_tenant(session, "Tenant B")

    # Tenant A adopts v1
    adp_a = service.adopt_framework_version(p_a, ctx_a, v1_id, True, "req-a1")
    ov_a = service.manage_overlay(
        p_a,
        ctx_a,
        adp_a.id,
        c1.id,
        OverlayApplicability.APPLICABLE,
        None,
        "Tenant A secret",
        None,
        "req-a2",
    )

    # Tenant B adopts v1
    adp_b = service.adopt_framework_version(p_b, ctx_b, v1_id, True, "req-b1")

    # Tenant B cannot access Tenant A's overlays
    overlays_b = service.list_overlays(ctx_b, adp_b.id)
    assert len(overlays_b) == 0

    # Tenant B attempting to delete Tenant A's overlay fails
    with pytest.raises(ControlOverlayNotFoundError):
        service.delete_overlay(p_b, ctx_b, ov_a.id, "req-b2")

    # Tenant B attempting to add overlay to Tenant A's adoption fails
    with pytest.raises(AdoptionNotFoundError):
        service.manage_overlay(
            p_b, ctx_b, adp_a.id, c1.id, OverlayApplicability.APPLICABLE, None, None, None, "req-b3"
        )


def test_custom_controls_and_mappings(session: Session) -> None:
    service, fw_id, v1_id, _, c1, _ = setup_released_framework(session)
    tenant, user, t_ctx, principal = make_tenant(session, "Custom Tenant")

    # Create custom control
    cc = service.create_custom_control(
        principal=principal,
        tenant_context=t_ctx,
        identifier="CUST-001",
        title="Zero Trust Network Access",
        description="All internal endpoints require mutual TLS and continuous posture check",
        category="Network",
        guidance="Deploy Cloudflare Access",
        request_id="req-cc-1",
    )
    assert cc.id is not None
    assert cc.identifier == "CUST-001"

    # Duplicate identifier in same tenant fails
    with pytest.raises(ValueError, match="already exists"):
        service.create_custom_control(
            principal, t_ctx, "CUST-001", "Duplicate", "Desc", "Cat", None, "req-cc-2"
        )

    # Map custom control to canonical control A.5.1
    mapping = service.create_control_mapping(
        principal=principal,
        tenant_context=t_ctx,
        source_type=ControlEntityType.CUSTOM,
        source_control_id=cc.id,
        target_type=ControlEntityType.CANONICAL,
        target_control_id=c1.id,
        mapping_type=MappingType.SATISFIES,
        rationale="ZTNA satisfies remote access policy",
        request_id="req-map-1",
    )
    assert mapping.id is not None
    assert mapping.mapping_type == MappingType.SATISFIES

    # List mappings
    maps = service.list_control_mappings(t_ctx)
    assert len(maps) == 1

    # Delete mapping
    service.delete_control_mapping(principal, t_ctx, mapping.id, "req-map-2")
    assert len(service.list_control_mappings(t_ctx)) == 0
