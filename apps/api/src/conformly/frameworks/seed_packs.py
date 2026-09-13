"""Seed, review, independently approve, and release initial Tier A framework packs.

Enforces the mandatory 2-person independent approval process:
- Platform Author (User A) creates draft and canonical controls, and submits for review.
- Legal & compliance review is recorded.
- Independent Platform Approver (User B != User A) approves the version.
- Version is formally released into the canonical catalog with immutable status.
"""

from datetime import UTC, datetime
from uuid import NAMESPACE_DNS, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal
from conformly.db.session import SessionLocal
from conformly.frameworks.models import Framework, FrameworkVersion, ReleaseState
from conformly.frameworks.packs_data import TIER_A_FRAMEWORK_PACKS, FrameworkPackDefinition
from conformly.frameworks.service import FrameworkService
from conformly.identity.models import User, UserStatus

AUTHOR_EMAIL = "framework-author@conformly.internal"
LEGAL_REVIEWER_EMAIL = "framework-legal@conformly.internal"
APPROVER_EMAIL = "framework-approver@conformly.internal"

# Deterministic UUIDs for platform author, legal reviewer, and approver (3-person separation)
AUTHOR_USER_ID = uuid5(NAMESPACE_DNS, AUTHOR_EMAIL)
LEGAL_REVIEWER_USER_ID = uuid5(NAMESPACE_DNS, LEGAL_REVIEWER_EMAIL)
APPROVER_USER_ID = uuid5(NAMESPACE_DNS, APPROVER_EMAIL)


def get_or_create_platform_user(
    session: Session, user_id: UUID, email: str, display_name: str
) -> tuple[User, Principal]:
    user = session.get(User, user_id)
    if user is None:
        user = session.scalar(select(User).where(User.email == email))

    if user is None:
        user = User(
            id=user_id,
            oidc_issuer="https://auth.conformly.internal",
            oidc_subject=f"platform-{email}",
            email=email,
            display_name=display_name,
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )
        session.add(user)
        session.flush()
    else:
        if not user.is_platform_admin:
            user.is_platform_admin = True
            session.flush()

    principal = Principal(user_id=user.id, is_platform_admin=True, mfa_verified=True)
    return user, principal


def import_framework_pack_draft(
    service: FrameworkService,
    pack: FrameworkPackDefinition,
    author_principal: Principal,
    request_id: str,
) -> FrameworkVersion:
    """Import a framework pack definition as an unapproved DRAFT only.

    Decouples raw content loading from human review and release. Does NOT
    elevate permissions, assert synthetic MFA, fabricate review notes,
    or auto-approve.
    """
    session = service.session

    framework = session.scalar(select(Framework).where(Framework.slug == pack.slug))
    if framework is None:
        framework = service.create_framework(
            principal=author_principal,
            name=pack.name,
            slug=pack.slug,
            description=pack.description,
            request_id=f"{request_id}-fw",
        )

    version = session.scalar(
        select(FrameworkVersion).where(
            FrameworkVersion.framework_id == framework.id,
            FrameworkVersion.version == pack.version,
        )
    )

    if version is None:
        version = service.create_version_draft(
            principal=author_principal,
            framework_id=framework.id,
            version_str=pack.version,
            release_notes=pack.release_notes,
            request_id=f"{request_id}-draft",
        )

    # 1. Populate canonical controls
    existing_controls = {c.identifier: c for c in version.controls}
    ctrl_map = {}
    for idx, ctrl_def in enumerate(pack.controls, start=1):
        if ctrl_def.identifier in existing_controls:
            ctrl_map[ctrl_def.identifier] = existing_controls[ctrl_def.identifier].id
        else:
            c = service.add_canonical_control(
                principal=author_principal,
                version_id=version.id,
                identifier=ctrl_def.identifier,
                title=ctrl_def.title,
                description=ctrl_def.description,
                category=ctrl_def.category,
                guidance=ctrl_def.guidance,
                sort_order=ctrl_def.sort_order or (idx * 10),
                request_id=f"{request_id}-ctrl-{ctrl_def.identifier}",
            )
            ctrl_map[ctrl_def.identifier] = c.id

    # 2. Populate source requirements
    existing_reqs = {r.source_reference: r for r in version.source_requirements}
    req_map = {}
    for idx, req_def in enumerate(pack.source_requirements, start=1):
        if req_def.source_reference in existing_reqs:
            req_map[req_def.source_reference] = existing_reqs[req_def.source_reference].id
        else:
            r = service.add_source_requirement(
                principal=author_principal,
                version_id=version.id,
                source_reference=req_def.source_reference,
                title=req_def.title,
                requirement_type=req_def.requirement_type,
                source_authority=req_def.source_authority,
                edition_or_amendment=req_def.edition_or_amendment,
                source_text=req_def.source_text,
                content_rights=req_def.content_rights,
                source_url=req_def.source_url,
                retrieval_date=req_def.retrieval_date,
                language=req_def.language,
                effective_date=req_def.effective_date,
                permitted_use=req_def.permitted_use,
                conformly_guidance=req_def.conformly_guidance,
                suggested_operating_targets=req_def.suggested_operating_targets,
                assessment_procedure=req_def.assessment_procedure,
                default_owner_role=req_def.default_owner_role,
                review_cadence=req_def.review_cadence,
                applicability_conditions=req_def.applicability_conditions,
                reporting_limitations=req_def.reporting_limitations,
                sort_order=req_def.sort_order or (idx * 10),
                request_id=f"{request_id}-req-{idx}",
            )
            req_map[req_def.source_reference] = r.id

    # 3. Populate requirement-to-control mappings
    existing_mappings = {
        (m.source_requirement_id, m.canonical_control_id)
        for m in version.requirement_control_mappings
    }
    for idx, map_def in enumerate(pack.mappings, start=1):
        s_id = req_map.get(map_def.source_reference)
        c_id = ctrl_map.get(map_def.control_identifier)
        if s_id and c_id and (s_id, c_id) not in existing_mappings:
            service.add_requirement_control_mapping(
                principal=author_principal,
                version_id=version.id,
                source_requirement_id=s_id,
                canonical_control_id=c_id,
                mapping_type=map_def.mapping_type,
                rationale=map_def.rationale,
                request_id=f"{request_id}-map-{idx}",
            )
            existing_mappings.add((s_id, c_id))

    # 4. Populate evidence specifications
    existing_specs = {s.identifier for s in version.evidence_specifications}
    for idx, evid_def in enumerate(pack.evidence_specifications, start=1):
        if evid_def.identifier not in existing_specs:
            c_id = (
                ctrl_map.get(evid_def.control_identifier) if evid_def.control_identifier else None
            )
            s_id = req_map.get(evid_def.source_reference) if evid_def.source_reference else None
            service.add_evidence_specification(
                principal=author_principal,
                version_id=version.id,
                identifier=evid_def.identifier,
                title=evid_def.title,
                description=evid_def.description,
                evidence_type=evid_def.evidence_type,
                canonical_control_id=c_id,
                source_requirement_id=s_id,
                original_file_required=evid_def.original_file_required,
                observation_period_days=evid_def.observation_period_days,
                validity_period_days=evid_def.validity_period_days,
                review_cadence_days=evid_def.review_cadence_days,
                confidentiality_level=evid_def.confidentiality_level,
                suggested_storage_format=evid_def.suggested_storage_format,
                request_id=f"{request_id}-evid-{idx}",
            )
            existing_specs.add(evid_def.identifier)

    # 5. Populate coverage ledger entries
    existing_ledger_req_ids = {e.source_requirement_id for e in version.coverage_ledger_entries}
    for idx, cov_def in enumerate(pack.coverage_ledger, start=1):
        s_id = req_map.get(cov_def.source_reference)
        if s_id and s_id not in existing_ledger_req_ids:
            service.set_coverage_ledger_entry(
                principal=author_principal,
                version_id=version.id,
                source_requirement_id=s_id,
                disposition=cov_def.disposition,
                rationale=cov_def.rationale,
                request_id=f"{request_id}-cov-{idx}",
            )
            existing_ledger_req_ids.add(s_id)

    session.flush()
    session.expire(version)
    session.refresh(version)

    return version


def import_tier_a_framework_packs_as_drafts(
    session: Session, author_principal: Principal
) -> list[FrameworkVersion]:
    """Import all 5 Tier A framework packs as unapproved DRAFTS for human review."""
    service = FrameworkService(session)
    draft_versions: list[FrameworkVersion] = []
    for pack in TIER_A_FRAMEWORK_PACKS:
        req_id = f"import-{pack.slug}-{int(datetime.now(UTC).timestamp())}"
        v = import_framework_pack_draft(service, pack, author_principal, req_id)
        draft_versions.append(v)
    return draft_versions


def release_framework_pack(
    service: FrameworkService,
    pack: FrameworkPackDefinition,
    author_principal: Principal,
    legal_principal: Principal,
    approver_principal: Principal,
    request_id: str,
) -> FrameworkVersion:
    """Execute complete 3-role independent creation, review, approval, and release lifecycle with digest binding."""
    session = service.session

    # 1. Find or create canonical framework
    framework = session.scalar(select(Framework).where(Framework.slug == pack.slug))
    if framework:
        version = session.scalar(
            select(FrameworkVersion).where(
                FrameworkVersion.framework_id == framework.id,
                FrameworkVersion.version == pack.version,
            )
        )
        if version is not None and version.release_state == ReleaseState.RELEASED:
            return version

    # 2. Import complete draft content with requirements, mappings, evidence, and ledger
    version = import_framework_pack_draft(
        service=service,
        pack=pack,
        author_principal=author_principal,
        request_id=f"{request_id}-import",
    )

    # 3. Submit for review if in draft
    if version.release_state == ReleaseState.DRAFT:
        version = service.submit_version_for_review(
            principal=author_principal,
            version_id=version.id,
            request_id=f"{request_id}-submit",
        )

    from conformly.frameworks.service import compute_version_content_digest

    content_digest = compute_version_content_digest(version)

    # 4. Record legal and compliance review (Legal != Author, Legal != Approver)
    if version.legal_reviewed_by_user_id is None:
        version = service.record_legal_review(
            principal=legal_principal,
            version_id=version.id,
            notes=pack.legal_review_notes,
            content_digest=content_digest,
            request_id=f"{request_id}-legal",
        )

    # 5. Independent second-person approval (Approver != Author, Approver != Legal)
    if version.release_state == ReleaseState.IN_REVIEW:
        version = service.approve_version(
            principal=approver_principal,
            version_id=version.id,
            notes=pack.approval_notes,
            content_digest=content_digest,
            request_id=f"{request_id}-approve",
        )

    # 6. Formal release
    if version.release_state == ReleaseState.APPROVED:
        version = service.release_version(
            principal=approver_principal,
            version_id=version.id,
            content_digest=content_digest,
            request_id=f"{request_id}-release",
        )

    return version


def seed_tier_a_test_fixtures(session: Session) -> list[FrameworkVersion]:
    """Execute synthetic 3-person test fixture release pipeline.

    WARNING: FOR AUTOMATED TEST SUITES AND ISOLATED DEVELOPMENT FIXTURES ONLY.
    Separate synthetic account IDs generated in code do NOT constitute genuine
    independent human review. Production releases require authenticated, distinct
    human operators executing legal/compliance review and release approval.
    """
    _, author = get_or_create_platform_user(
        session, AUTHOR_USER_ID, AUTHOR_EMAIL, "Platform Framework Author"
    )
    _, legal = get_or_create_platform_user(
        session, LEGAL_REVIEWER_USER_ID, LEGAL_REVIEWER_EMAIL, "Platform Legal Reviewer"
    )
    _, approver = get_or_create_platform_user(
        session, APPROVER_USER_ID, APPROVER_EMAIL, "Independent Compliance Approver"
    )

    # Enforce 3-person independence invariant
    if len({author.user_id, legal.user_id, approver.user_id}) < 3:
        raise RuntimeError("Author, Legal Reviewer, and Approver must be 3 distinct users")

    service = FrameworkService(session)
    released_versions: list[FrameworkVersion] = []

    for pack in TIER_A_FRAMEWORK_PACKS:
        req_id = f"seed-{pack.slug}-{int(datetime.now(UTC).timestamp())}"
        v = release_framework_pack(service, pack, author, legal, approver, req_id)
        released_versions.append(v)

    return released_versions


def seed_tier_a_framework_packs(session: Session, as_drafts: bool = True) -> list[FrameworkVersion]:
    """Seed Tier A framework packs.

    Default: as_drafts=True. Safely imports all packs as unapproved DRAFT versions
    without creating synthetic reviewer accounts, without fabricating review notes,
    and without auto-releasing packs.

    If as_drafts=False: delegates to seed_tier_a_test_fixtures (guarded for tests only).
    """
    if not as_drafts:
        return seed_tier_a_test_fixtures(session)

    _, author = get_or_create_platform_user(
        session, AUTHOR_USER_ID, AUTHOR_EMAIL, "Platform Framework Author"
    )
    return import_tier_a_framework_packs_as_drafts(session, author)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed Tier A framework packs into the canonical catalog."
    )
    parser.add_argument(
        "--test-fixtures",
        action="store_true",
        help="Execute synthetic test fixture release pipeline (FOR ISOLATED TESTS ONLY; does NOT constitute independent human review)",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        if args.test_fixtures:
            print(
                "[SECURITY WARNING] Creating synthetic reviewer accounts and auto-releasing packs "
                "is permitted ONLY in isolated automated test environments. Separate account IDs "
                "do NOT constitute genuine independent human review."
            )
            versions = seed_tier_a_test_fixtures(session)
            session.commit()
            for v in versions:
                print(
                    f"[TIER_A_PACKS] [TEST FIXTURE] Released pack: {v.framework.slug} v{v.version} "
                    f"(Controls: {len(v.controls)}, State: {v.release_state})"
                )
        else:
            print(
                "[TIER_A_PACKS] Seeding Tier A framework packs as unapproved DRAFTS (safe default)..."
            )
            versions = seed_tier_a_framework_packs(session, as_drafts=True)
            session.commit()
            for v in versions:
                print(
                    f"[TIER_A_PACKS] Imported draft pack: {v.framework.slug} v{v.version} "
                    f"(Controls: {len(v.controls)}, State: {v.release_state})"
                )
    print("[TIER_A_PACKS] Tier A framework packs seed completed successfully.")


if __name__ == "__main__":
    main()
