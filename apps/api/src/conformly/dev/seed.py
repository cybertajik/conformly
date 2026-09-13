from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.authz.roles import Role
from conformly.compliance.models import (
    ComplianceTask,
    EvidenceItem,
    EvidenceStatus,
    Policy,
    PolicyStatus,
    TaskPriority,
    TaskStatus,
)
from conformly.config import get_settings
from conformly.db.session import SessionLocal
from conformly.frameworks.models import (
    AdoptionStatus,
    Framework,
    FrameworkVersion,
    ReleaseState,
    TenantFrameworkAdoption,
)
from conformly.frameworks.seed_packs import seed_tier_a_test_fixtures
from conformly.identity.models import Membership, MembershipStatus, Tenant, User, UserStatus
from conformly.risks.models import (
    Risk,
    RiskCategory,
    RiskStatus,
    RiskTreatment,
    RiskTreatmentStrategy,
)
from conformly.tenancy.rls import set_rls_context
from conformly.vendors.models import Vendor, VendorCriticality, VendorStatus

DEVELOPMENT_ENVIRONMENTS = frozenset({"development", "local", "test"})


class UnsafeSeedEnvironmentError(RuntimeError):
    """Raised before fixture data can be written outside a development environment."""


def seed_development_fixtures(database: Session, *, environment: str) -> None:
    if environment.casefold() not in DEVELOPMENT_ENVIRONMENTS:
        raise UnsafeSeedEnvironmentError("development fixtures are disabled in this environment")

    now = datetime.now(UTC)

    # 1. Release canonical framework packs (six Tier A packs including ISO 9001 and ISO 27001)
    seed_tier_a_test_fixtures(database)

    # 2. Get or create Tenant
    tenant = database.scalar(select(Tenant).where(Tenant.slug == "example-organization"))
    if tenant is None:
        tenant = Tenant(name="Acme Global Compliance GmbH", slug="example-organization")
        database.add(tenant)
        database.flush()

    # 3. Create synthetic users (Owner, Compliance Manager, Independent Reviewer, and Legacy)
    demo_accounts = [
        {
            "oidc_subject": "example-user",
            "email": "example-user@development.invalid",
            "display_name": "Example User",
            "role": Role.OWNER,
        },
        {
            "oidc_subject": "demo-owner",
            "email": "owner@example.test",
            "display_name": "Elena Rostova (Tenant Owner)",
            "role": Role.OWNER,
        },
        {
            "oidc_subject": "demo-compliance",
            "email": "compliance@example.test",
            "display_name": "Marcus Vance (Compliance Lead)",
            "role": Role.COMPLIANCE_MANAGER,
        },
        {
            "oidc_subject": "demo-reviewer",
            "email": "auditor@example.test",
            "display_name": "David Ross (Independent Reviewer)",
            "role": Role.REVIEWER,
        },
    ]

    user_map: dict[str, User] = {}
    for acc in demo_accounts:
        user = database.scalar(
            select(User).where(
                User.oidc_issuer == "https://development.invalid",
                User.oidc_subject == acc["oidc_subject"],
            )
        )
        if user is None:
            user = User(
                oidc_issuer="https://development.invalid",
                oidc_subject=acc["oidc_subject"],
                email=acc["email"],
                display_name=acc["display_name"],
                status=UserStatus.ACTIVE,
            )
            database.add(user)
            database.flush()
        user_map[acc["oidc_subject"]] = user

        # Set or verify active membership
        membership = database.scalar(
            select(Membership).where(
                Membership.tenant_id == tenant.id,
                Membership.user_id == user.id,
            )
        )
        if membership is None:
            database.add(
                Membership(
                    tenant_id=tenant.id,
                    user_id=user.id,
                    role=acc["role"],
                    status=MembershipStatus.ACTIVE,
                )
            )
            database.flush()

    primary_owner = user_map["demo-owner"]
    compliance_mgr = user_map["demo-compliance"]

    # Set tenant RLS context for remaining operations
    set_rls_context(
        database,
        user_id=primary_owner.id,
        tenant_id=tenant.id,
        tenant_verified=True,
    )

    # 4. Adopt ISO 27001 and ISO 9001 frameworks
    for slug in ("iso-27001", "iso-9001"):
        fw = database.scalar(select(Framework).where(Framework.slug == slug))
        if fw is not None:
            released_ver = database.scalar(
                select(FrameworkVersion).where(
                    FrameworkVersion.framework_id == fw.id,
                    FrameworkVersion.release_state == ReleaseState.RELEASED,
                )
            )
            if released_ver is not None:
                existing_adoption = database.scalar(
                    select(TenantFrameworkAdoption).where(
                        TenantFrameworkAdoption.tenant_id == tenant.id,
                        TenantFrameworkAdoption.framework_id == fw.id,
                    )
                )
                if existing_adoption is None:
                    database.add(
                        TenantFrameworkAdoption(
                            tenant_id=tenant.id,
                            framework_id=fw.id,
                            framework_version_id=released_ver.id,
                            status=AdoptionStatus.ACTIVE,
                            adopted_by_user_id=primary_owner.id,
                            adopted_at=now - timedelta(days=60),
                        )
                    )
                    database.flush()

    # 5. Seed Policies (Valid / Published & In-Review)
    existing_pol = database.scalar(select(Policy).where(Policy.tenant_id == tenant.id))
    if existing_pol is None:
        p1 = Policy(
            tenant_id=tenant.id,
            title="Information Security Management Policy",
            description="High-level governance, cryptographic standards, and access control mandates across all production systems.",
            version_string="1.0.0",
            version=1,
            status=PolicyStatus.PUBLISHED,
            classification="Internal",
            owner_user_id=compliance_mgr.id,
            approved_by_user_id=primary_owner.id,
            approved_at=now - timedelta(days=45),
            next_review_due=now + timedelta(days=320),
        )
        p2 = Policy(
            tenant_id=tenant.id,
            title="Third-Party Supplier & Subprocessor Governance Policy",
            description="Outlines vendor due diligence, minimum security guarantees, DPAs, and incident response requirements.",
            version_string="1.0.0",
            version=1,
            status=PolicyStatus.IN_REVIEW,
            classification="Confidential",
            owner_user_id=compliance_mgr.id,
            next_review_due=now + timedelta(days=90),
        )
        database.add_all([p1, p2])
        database.flush()

    # 6. Seed Evidence (Valid and Expired)
    existing_ev = database.scalar(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id))
    if existing_ev is None:
        ev_valid = EvidenceItem(
            tenant_id=tenant.id,
            title="Annual Penetration Testing & Vulnerability Assessment Report",
            description="Third-party black-box and grey-box security penetration test conducted by certified auditors.",
            owner_user_id=compliance_mgr.id,
            status=EvidenceStatus.VALID,
            version=1,
            classification="Confidential",
            valid_from=now - timedelta(days=60),
            valid_until=now + timedelta(days=305),
        )
        ev_expired = EvidenceItem(
            tenant_id=tenant.id,
            title="Historical SOC 2 Type II Independent Audit Attestation (Prior Period)",
            description="Previous fiscal year SOC 2 Type II attestation report. Requires renewal for current assessment window.",
            owner_user_id=compliance_mgr.id,
            status=EvidenceStatus.EXPIRED,
            version=1,
            classification="Internal",
            valid_from=now - timedelta(days=395),
            valid_until=now - timedelta(days=30),
        )
        database.add_all([ev_valid, ev_expired])
        database.flush()

    # 7. Seed Operational Risks
    existing_risk = database.scalar(select(Risk).where(Risk.tenant_id == tenant.id))
    if existing_risk is None:
        r1 = Risk(
            tenant_id=tenant.id,
            title="Unencrypted Internal Traffic Across Legacy Subnets",
            description="Legacy monitoring endpoints transmit telemetry without mTLS transport encryption.",
            category=RiskCategory.SECURITY,
            likelihood=3,
            impact=4,
            inherent_score=12,
            residual_score=4,
            status=RiskStatus.TREATING,
            owner_user_id=compliance_mgr.id,
        )
        r2 = Risk(
            tenant_id=tenant.id,
            title="Key Person Dependency in Cryptographic Key Ceremony Procedures",
            description="Sole custodian dependency for emergency KMS master key rotation.",
            category=RiskCategory.OPERATIONAL,
            likelihood=2,
            impact=3,
            inherent_score=6,
            residual_score=3,
            status=RiskStatus.MONITORED,
            owner_user_id=primary_owner.id,
        )
        database.add_all([r1, r2])
        database.flush()
        database.add(
            RiskTreatment(
                tenant_id=tenant.id,
                risk_id=r1.id,
                strategy=RiskTreatmentStrategy.MITIGATE,
                treatment_plan="Enforce mutual TLS (mTLS) with automated certificate rotation across all service mesh nodes.",
                owner_user_id=compliance_mgr.id,
                status="in_progress",
            )
        )
        database.add(
            RiskTreatment(
                tenant_id=tenant.id,
                risk_id=r2.id,
                strategy=RiskTreatmentStrategy.MITIGATE,
                treatment_plan="Implement multi-person threshold quorum recovery protocol.",
                owner_user_id=primary_owner.id,
                status="planned",
            )
        )
        database.flush()

    # 8. Seed Third-Party Vendors
    existing_vendor = database.scalar(select(Vendor).where(Vendor.tenant_id == tenant.id))
    if existing_vendor is None:
        v1 = Vendor(
            tenant_id=tenant.id,
            name="AWS Cloud Infrastructure (Frankfurt eu-central-1)",
            service_description="Dedicated virtual private cloud hosting core multi-tenant backend and encrypted object storage.",
            criticality=VendorCriticality.CRITICAL,
            data_classification_accessed="Restricted",
            country_residency="DE",
            dpa_signed=True,
            status=VendorStatus.ACTIVE,
            security_reviewed_at=now - timedelta(days=90),
            next_review_due_at=now + timedelta(days=275),
            owner_user_id=compliance_mgr.id,
        )
        v2 = Vendor(
            tenant_id=tenant.id,
            name="SecureMail Transactional Relay Services",
            service_description="Encrypted SMTP delivery infrastructure for operational system notifications.",
            criticality=VendorCriticality.MEDIUM,
            data_classification_accessed="Internal",
            country_residency="DE",
            dpa_signed=True,
            status=VendorStatus.ACTIVE,
            security_reviewed_at=now - timedelta(days=120),
            next_review_due_at=now + timedelta(days=245),
            owner_user_id=compliance_mgr.id,
        )
        database.add_all([v1, v2])
        database.flush()

    # 9. Seed Compliance Tasks
    existing_task = database.scalar(
        select(ComplianceTask).where(ComplianceTask.tenant_id == tenant.id)
    )
    if existing_task is None:
        t1 = ComplianceTask(
            tenant_id=tenant.id,
            title="Execute Annual Disaster Recovery Failover Simulation",
            description="Perform cross-region backup restoration drill and record recovery time objective (RTO) metrics.",
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            due_date=now + timedelta(days=14),
            assignee_user_id=compliance_mgr.id,
        )
        t2 = ComplianceTask(
            tenant_id=tenant.id,
            title="Review and Re-certify Production Privileged IAM Roles",
            description="Perform quarterly segregation-of-duties review for all administrative credentials and API keys.",
            priority=TaskPriority.CRITICAL,
            status=TaskStatus.IN_PROGRESS,
            due_date=now + timedelta(days=7),
            assignee_user_id=primary_owner.id,
        )
        database.add_all([t1, t2])
        database.flush()


def main() -> None:
    settings = get_settings()
    with SessionLocal() as database:
        seed_development_fixtures(database, environment=settings.environment)
        database.commit()


if __name__ == "__main__":
    main()
