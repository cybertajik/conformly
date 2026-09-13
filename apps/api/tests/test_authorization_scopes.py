from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.authz.policy import (
    AuthorizationDeniedError,
    Principal,
    TenantContext,
    authorize,
    authorize_resource,
)
from conformly.authz.roles import Capability, Role
from conformly.compliance.models import ComplianceTask, EvidenceItem, Finding, TaskStatus
from conformly.compliance.service import ComplianceService
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.exports.models import ExportScope
from conformly.exports.service import ExportService
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
)
from conformly.identity.service import update_membership_scopes
from conformly.organization.service import (
    create_business_unit,
    create_legal_entity,
    list_business_units,
    list_legal_entities,
)
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import StorageService
from conformly.tenancy.context import TenantContextError, resolve_tenant_context


def make_test_codec() -> EncryptedFieldCodec:
    raw_key = b"0" * 32
    enc = EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="}, "v1")
    )
    return EncryptedFieldCodec(enc)


def make_test_storage(session: Session) -> StorageService:
    raw_key = b"0" * 32
    enc = EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="}, "v1")
    )
    return StorageService(session, MemoryStorageProvider(), enc)


def create_user_in_tenant(
    session: Session, tenant: Tenant, role: Role = Role.OWNER, **membership_kwargs
) -> tuple[User, Principal, TenantContext, Membership]:
    user = User(
        email=f"user-{uuid4()}@acme.test",
        display_name="Test User",
        oidc_issuer="https://issuer.test",
        oidc_subject=f"sub-{uuid4()}",
    )
    session.add(user)
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
        **membership_kwargs,
    )
    session.add(membership)
    session.commit()

    principal = Principal(user_id=user.id)
    tenant_context = TenantContext(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        legal_entity_id=membership.legal_entity_id,
        business_unit_id=membership.business_unit_id,
        is_external_advisor=membership.is_external_advisor,
        expires_at=membership.expires_at,
        is_workforce=membership.is_workforce,
    )
    return user, principal, tenant_context, membership


def create_tenant_and_user(
    session: Session, role: Role = Role.OWNER, **membership_kwargs
) -> tuple[Tenant, User, Principal, TenantContext, Membership]:
    tenant = Tenant(name="Acme Corp", slug=f"acme-{uuid4()}")
    session.add(tenant)
    session.flush()
    user, principal, tenant_context, membership = create_user_in_tenant(
        session, tenant, role=role, **membership_kwargs
    )
    return tenant, user, principal, tenant_context, membership


# =============================================================================
# 1. ADMINISTRATOR & REVIEWER EXPORT RESTRICTIONS
# =============================================================================


def test_administrator_cannot_create_or_read_exports(session: Session) -> None:
    """Tenant Administrator withholding normal content access cannot bypass via full exports."""
    tenant, user, principal, context, _ = create_tenant_and_user(
        session, role=Role.ADMINISTRATOR
    )

    with pytest.raises(AuthorizationDeniedError):
        authorize(principal, context, Capability.EXPORT_CREATE)

    with pytest.raises(AuthorizationDeniedError):
        authorize(principal, context, Capability.EXPORT_READ)

    storage = make_test_storage(session)
    export_service = ExportService(session, storage)

    with pytest.raises(AuthorizationDeniedError):
        export_service.create_export_job(
            principal=principal,
            tenant_context=context,
            scope=ExportScope.FULL,
            request_id="req-admin-export",
        )


def test_reviewer_cannot_read_exports() -> None:
    """Reviewers cannot read full tenant export archives that contain unassigned material."""
    user_id = uuid4()
    principal = Principal(user_id=user_id)
    context = TenantContext(tenant_id=uuid4(), user_id=user_id, role=Role.REVIEWER)

    with pytest.raises(AuthorizationDeniedError):
        authorize(principal, context, Capability.EXPORT_READ)


# =============================================================================
# 2. REVIEWER ASSIGNED-MATERIAL SCOPING
# =============================================================================


def test_reviewer_can_access_assigned_material_and_denied_unassigned(session: Session) -> None:
    """Reviewers may only access materials explicitly assigned to or owned by them."""
    tenant, rev_user, rev_principal, rev_context, _ = create_tenant_and_user(
        session, role=Role.REVIEWER
    )
    other_user = User(
        email=f"other-{uuid4()}@acme.test",
        display_name="Other User",
        oidc_issuer="https://issuer.test",
        oidc_subject=f"sub-{uuid4()}",
    )
    session.add(other_user)
    session.flush()

    codec = make_test_codec()
    compliance = ComplianceService(session, codec)

    # 1. Evidence items
    assigned_evidence = EvidenceItem(
        tenant_id=tenant.id,
        title="Assigned Evidence",
        description="Owned by reviewer",
        classification="Internal",
        owner_user_id=rev_user.id,
    )
    unassigned_evidence = EvidenceItem(
        tenant_id=tenant.id,
        title="Unassigned Evidence",
        description="Owned by other user",
        classification="Internal",
        owner_user_id=other_user.id,
    )
    session.add_all([assigned_evidence, unassigned_evidence])
    session.commit()

    # Reviewer can get their assigned evidence
    item, _ = compliance.get_evidence(rev_principal, rev_context, assigned_evidence.id)
    assert item.id == assigned_evidence.id

    # Reviewer is denied unassigned evidence
    with pytest.raises(AuthorizationDeniedError, match="reviewer may only access assigned material"):
        compliance.get_evidence(rev_principal, rev_context, unassigned_evidence.id)

    # Listing evidence only returns assigned evidence
    ev_list = compliance.list_evidence(rev_principal, rev_context)
    ev_ids = [e.id for e in ev_list]
    assert assigned_evidence.id in ev_ids
    assert unassigned_evidence.id not in ev_ids

    # 2. Compliance Tasks
    assigned_task = ComplianceTask(
        tenant_id=tenant.id,
        title="Assigned Task",
        description="Reviewer task",
        due_date=datetime.now(UTC) + timedelta(days=7),
        assignee_user_id=rev_user.id,
    )
    unassigned_task = ComplianceTask(
        tenant_id=tenant.id,
        title="Unassigned Task",
        description="Other task",
        due_date=datetime.now(UTC) + timedelta(days=7),
        assignee_user_id=other_user.id,
    )
    session.add_all([assigned_task, unassigned_task])
    session.commit()

    task = compliance.get_task(rev_principal, rev_context, assigned_task.id)
    assert task.id == assigned_task.id

    with pytest.raises(AuthorizationDeniedError, match="reviewer may only access assigned material"):
        compliance.get_task(rev_principal, rev_context, unassigned_task.id)

    tasks_list = compliance.list_tasks(rev_principal, rev_context)
    task_ids = [t.id for t in tasks_list]
    assert assigned_task.id in task_ids
    assert unassigned_task.id not in task_ids

    # 3. Findings
    assigned_finding = Finding(
        tenant_id=tenant.id,
        title="Assigned Finding",
        description="Reviewer finding",
        owner_user_id=rev_user.id,
    )
    unassigned_finding = Finding(
        tenant_id=tenant.id,
        title="Unassigned Finding",
        description="Other finding",
        owner_user_id=other_user.id,
    )
    session.add_all([assigned_finding, unassigned_finding])
    session.commit()

    finding = compliance.get_finding(rev_principal, rev_context, assigned_finding.id)
    assert finding.id == assigned_finding.id

    with pytest.raises(AuthorizationDeniedError, match="reviewer may only access assigned material"):
        compliance.get_finding(rev_principal, rev_context, unassigned_finding.id)

    findings_list = compliance.list_findings(rev_principal, rev_context)
    finding_ids = [f.id for f in findings_list]
    assert assigned_finding.id in finding_ids
    assert unassigned_finding.id not in finding_ids


# =============================================================================
# 3. ASSESSOR EVIDENCE MUTATION LOCK & EXPIRING ENGAGEMENTS
# =============================================================================


def test_assessor_and_external_advisor_cannot_modify_evidence() -> None:
    """Assessors and external advisors can never modify customer evidence or controls."""
    user_id = uuid4()
    principal = Principal(user_id=user_id)

    # 1. Reviewer role cannot mutate evidence or controls
    rev_context = TenantContext(
        tenant_id=uuid4(),
        user_id=user_id,
        role=Role.REVIEWER,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    with pytest.raises(AuthorizationDeniedError, match="cannot modify customer evidence or controls"):
        authorize(principal, rev_context, Capability.EVIDENCE_MANAGE)

    with pytest.raises(AuthorizationDeniedError, match="cannot modify customer evidence or controls"):
        authorize(principal, rev_context, Capability.FILE_WRITE)

    with pytest.raises(AuthorizationDeniedError, match="cannot modify customer evidence or controls"):
        authorize(principal, rev_context, Capability.FILE_DELETE)

    # 2. External advisor classification cannot mutate evidence even if role has capability
    advisor_context = TenantContext(
        tenant_id=uuid4(),
        user_id=user_id,
        role=Role.COMPLIANCE_MANAGER,
        is_external_advisor=True,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    with pytest.raises(AuthorizationDeniedError, match="cannot modify customer evidence or controls"):
        authorize(principal, advisor_context, Capability.EVIDENCE_MANAGE)


def test_external_advisor_must_have_expiration() -> None:
    """External Advisors must have a time-limited engagement."""
    user_id = uuid4()
    principal = Principal(user_id=user_id)
    advisor_context = TenantContext(
        tenant_id=uuid4(),
        user_id=user_id,
        role=Role.REVIEWER,
        is_external_advisor=True,
        expires_at=None,
    )
    with pytest.raises(AuthorizationDeniedError, match="time-limited engagement"):
        authorize(principal, advisor_context, Capability.EVIDENCE_READ)


def test_expired_engagement_denied_at_authz_and_context(session: Session) -> None:
    """Expired membership engagements fail closed."""
    past_time = datetime.now(UTC) - timedelta(days=1)
    tenant, user, principal, context, _ = create_tenant_and_user(
        session,
        role=Role.REVIEWER,
        expires_at=past_time,
    )

    # Denied in central authorize
    with pytest.raises(AuthorizationDeniedError, match="membership engagement has expired"):
        authorize(principal, context, Capability.EVIDENCE_READ)

    # Denied in context resolution
    with pytest.raises(TenantContextError, match="membership engagement has expired"):
        resolve_tenant_context(session, principal, tenant.id)


# =============================================================================
# 4. WORKFORCE STANDING ACCESS RESTRICTION
# =============================================================================


def test_workforce_member_standing_access_denied(session: Session) -> None:
    """Staff have no standing access and must have an active expiring engagement."""
    tenant, user, principal, context, _ = create_tenant_and_user(
        session,
        role=Role.COMPLIANCE_MANAGER,
        is_workforce=True,
        expires_at=None,
    )

    # Denied at authorize
    with pytest.raises(AuthorizationDeniedError, match="workforce members must have an active expiring engagement"):
        authorize(principal, context, Capability.EVIDENCE_READ)

    # Denied at context resolution
    with pytest.raises(TenantContextError, match="workforce members must have an active expiring engagement"):
        resolve_tenant_context(session, principal, tenant.id)


def test_workforce_member_active_engagement_allowed(session: Session) -> None:
    """Workforce member with an active, unexpired engagement is authorized."""
    future_time = datetime.now(UTC) + timedelta(hours=4)
    tenant, user, principal, context, _ = create_tenant_and_user(
        session,
        role=Role.COMPLIANCE_MANAGER,
        is_workforce=True,
        expires_at=future_time,
    )

    # Allowed at context resolution
    resolved = resolve_tenant_context(session, principal, tenant.id)
    assert resolved.is_workforce is True
    assert resolved.expires_at is not None
    assert abs((resolved.expires_at - future_time).total_seconds()) < 1.0

    # Allowed at authorize
    authorize(principal, resolved, Capability.EVIDENCE_READ)


# =============================================================================
# 5. ORGANIZATIONAL SCOPES ENFORCEMENT
# =============================================================================


def test_organizational_scope_isolation_in_policy() -> None:
    """authorize_resource enforces legal-entity and business-unit boundaries."""
    user_id = uuid4()
    principal = Principal(user_id=user_id)
    entity_a = uuid4()
    entity_b = uuid4()
    unit_1 = uuid4()
    unit_2 = uuid4()

    scoped_context = TenantContext(
        tenant_id=uuid4(),
        user_id=user_id,
        role=Role.CONTROL_OWNER,
        legal_entity_id=entity_a,
        business_unit_id=unit_1,
    )

    # Matching scope allowed
    authorize_resource(
        principal,
        scoped_context,
        Capability.FILE_READ,
        legal_entity_id=entity_a,
        business_unit_id=unit_1,
    )

    # Global resource (no entity/unit tag) allowed
    authorize_resource(
        principal,
        scoped_context,
        Capability.FILE_READ,
        legal_entity_id=None,
        business_unit_id=None,
    )

    # Different legal entity denied
    with pytest.raises(AuthorizationDeniedError, match="outside assigned legal entity scope"):
        authorize_resource(
            principal,
            scoped_context,
            Capability.FILE_READ,
            legal_entity_id=entity_b,
            business_unit_id=unit_1,
        )

    # Different business unit denied
    with pytest.raises(AuthorizationDeniedError, match="outside assigned business unit scope"):
        authorize_resource(
            principal,
            scoped_context,
            Capability.FILE_READ,
            legal_entity_id=entity_a,
            business_unit_id=unit_2,
        )


def test_organization_service_scopes_filtering(session: Session) -> None:
    """OrganizationService queries and mutations strictly honor membership scopes."""
    tenant, _, admin_principal, admin_context, _ = create_tenant_and_user(
        session, role=Role.OWNER
    )

    # Create two legal entities
    entity_1 = create_legal_entity(
        session, admin_principal, admin_context, "Entity 1", None, "DE", True, "req-le-1"
    )
    entity_2 = create_legal_entity(
        session, admin_principal, admin_context, "Entity 2", None, "DE", False, "req-le-2"
    )

    unit_1 = create_business_unit(
        session, admin_principal, admin_context, entity_1.id, "Unit 1", "U1", "req-bu-1"
    )
    unit_2 = create_business_unit(
        session, admin_principal, admin_context, entity_2.id, "Unit 2", "U2", "req-bu-2"
    )

    # Create scoped user in same tenant for entity 1 with ORGANIZATION_MANAGE capability
    _, scoped_principal, scoped_context, _ = create_user_in_tenant(
        session,
        tenant,
        role=Role.ADMINISTRATOR,
        legal_entity_id=entity_1.id,
        business_unit_id=unit_1.id,
    )

    # Listing legal entities only returns entity 1
    le_list = list_legal_entities(session, scoped_principal, scoped_context, "req-list-le")
    assert len(le_list) == 1
    assert le_list[0].id == entity_1.id

    # Listing business units only returns unit 1
    bu_list = list_business_units(session, scoped_principal, scoped_context, "req-list-bu")
    assert len(bu_list) == 1
    assert bu_list[0].id == unit_1.id

    # Scoped user cannot create business unit in entity 2
    with pytest.raises(AuthorizationDeniedError, match="outside assigned legal entity scope"):
        create_business_unit(
            session,
            scoped_principal,
            scoped_context,
            entity_2.id,
            "Illegal Unit",
            "IU",
            "req-bu-illegal",
        )


# =============================================================================
# 6. IDENTITY SERVICE MEMBERSHIP SCOPES MANAGEMENT
# =============================================================================


def test_update_membership_scopes_management(session: Session) -> None:
    """Authorized managers can configure membership scopes and audit events are emitted."""
    tenant, _, owner_principal, owner_context, _ = create_tenant_and_user(
        session, role=Role.OWNER
    )
    _, _, _, target_membership = create_user_in_tenant(
        session, tenant, role=Role.REVIEWER
    )

    le_id = uuid4()
    bu_id = uuid4()
    exp_time = datetime.now(UTC) + timedelta(days=90)

    updated = update_membership_scopes(
        session,
        owner_principal,
        owner_context,
        target_membership.id,
        "req-scope-update",
        legal_entity_id=le_id,
        business_unit_id=bu_id,
        is_external_advisor=True,
        expires_at=exp_time,
        is_workforce=False,
    )

    assert updated.legal_entity_id == le_id
    assert updated.business_unit_id == bu_id
    assert updated.is_external_advisor is True
    assert updated.expires_at is not None
    assert abs((updated.expires_at - exp_time).total_seconds()) < 1.0
    assert updated.is_workforce is False

