"""WP-06D Final Shared Assurance Foundation Compatibility & V1 Invariance Test Suite.

Proves:
1. Frozen V1 OpenAPI route/method/security surface canonical projection matches WP-05 fixture.
2. Complete absence of Catalog V2 or assurance HTTP routers, routes, endpoints, or schemas.
3. conformly.main does not import or register anything from conformly.catalog_v2.
4. OpenAPI schemas contain zero Catalog V2 or assurance entities.
5. Representative synthetic Catalog V2 core and assurance workflows leave V1 tenant data (Tenant,
   User, Membership, Asset, Risk, Vendor, PublicProfile, WhistleblowerPortal, WhistleblowerCase)
   100% byte-for-byte identical before and after execution.
6. Pre-existing tenant framework adoptions are unmutated, and no new tenant adoption or authorization
   relationship for Catalog V2 entities is created.
7. Tenant actors (unprivileged actor contexts with is_platform_admin=False and no catalog capabilities)
   are denied access to Catalog V2 assurance and import services with CatalogSecurityError.
8. Catalog assurance tables contain zero foreign keys referencing tenant-scoped tables.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

import conformly.main as conformly_main
from conformly.assets.models import Asset, AssetType
from conformly.authz.roles import Role
from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogSecurityError,
)
from conformly.catalog_v2.import_adapter import load_fixture
from conformly.catalog_v2.models import (
    CatalogSourcePermissionProposal,
    CatalogSourceProvenance,
)
from conformly.catalog_v2.service import CatalogDraftService
from conformly.catalog_v2.service_assurance import CatalogAssuranceDraftService
from conformly.catalog_v2.services_import import ConservativeImportService
from conformly.db.base import Base
from conformly.frameworks.models import (
    AdoptionStatus,
    Framework,
    FrameworkVersion,
    ReleaseState,
    TenantFrameworkAdoption,
)
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.profiles.models import PublicProfile
from conformly.risks.models import Risk, RiskStatus
from conformly.vendors.models import Vendor, VendorStatus
from conformly.whistleblower.models import (
    WhistleblowerCase,
    WhistleblowerCaseStatus,
    WhistleblowerPortal,
)

HTTP_METHODS: tuple[str, ...] = (
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
    "trace",
)

FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "catalog_v2_integration"
    / "v1_openapi_contract.json"
)

ASSURANCE_TABLES = (
    "catalog_evidence_requirement_versions",
    "catalog_evidence_requirement_artifact_types",
    "catalog_evidence_requirement_metadata_keys",
    "catalog_assessment_procedure_versions",
    "catalog_assessment_procedure_steps",
    "catalog_assessment_procedure_evidence_requirements",
)

TENANT_TABLE_NAMES = {
    "tenants",
    "users",
    "memberships",
    "assets",
    "risks",
    "vendors",
    "public_profiles",
    "whistleblower_portals",
    "whistleblower_cases",
    "tenant_framework_adoptions",
}


@lru_cache(maxsize=1)
def get_pristine_conformly_app() -> FastAPI:
    """Return an app rebuilt after test-module collection, without route injection."""
    return importlib.reload(conformly_main).app


def build_canonical_v1_openapi_contract(app: FastAPI) -> dict[str, Any]:
    """Reconstruct the canonical deterministic V1 OpenAPI contract representation from app."""
    openapi = app.openapi()
    paths: dict[str, dict[str, Any]] = {}
    for path, methods in sorted(openapi.get("paths", {}).items()):
        method_ops: dict[str, Any] = {}
        for method in sorted(methods.keys()):
            if method.lower() in HTTP_METHODS:
                op = methods[method]
                method_ops[method.lower()] = op.get("operationId")
        paths[path] = method_ops

    return {
        "components": {"securitySchemes": openapi.get("components", {}).get("securitySchemes", {})},
        "paths": paths,
        "title": openapi.get("info", {}).get("title"),
        "version": openapi.get("info", {}).get("version"),
    }


def compute_canonical_contract_digest(payload: dict[str, Any]) -> str:
    """Compute sha256 hex digest of the canonical JSON representation of contract payload."""
    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def extract_all_runtime_routes(routes: list[Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Recursively extract all route objects and full path prefixes from FastAPI/Starlette router tree."""
    extracted: list[tuple[str, Any]] = []
    for r in routes:
        if type(r).__name__ == "_IncludedRouter":
            sub_prefix = prefix + (getattr(r.include_context, "prefix", "") or "")
            extracted.extend(extract_all_runtime_routes(r.original_router.routes, sub_prefix))
        elif hasattr(r, "routes"):
            sub_prefix = prefix + (getattr(r, "prefix", "") or "")
            extracted.extend(extract_all_runtime_routes(r.routes, sub_prefix))
        elif hasattr(r, "path"):
            extracted.append((prefix + r.path, r))
    return extracted


def serialize_entity_row(obj: Any) -> dict[str, Any]:
    """Serialize model row columns to a JSON-safe dictionary with normalized string formats."""
    serialized: dict[str, Any] = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, UUID):
            val = str(val)
        elif isinstance(val, datetime):
            val = val.isoformat()
        elif hasattr(val, "value"):
            val = val.value
        serialized[col.name] = val
    return serialized


def snapshot_targeted_v1_tenant_state(session: Session, tenant_id: UUID) -> bytes:
    """Return deterministic canonical JSON bytes of targeted tenant-owned V1 entities."""
    tenants = [
        serialize_entity_row(r)
        for r in session.scalars(select(Tenant).where(Tenant.id == tenant_id)).all()
    ]
    memberships = [
        serialize_entity_row(r)
        for r in session.scalars(select(Membership).where(Membership.tenant_id == tenant_id)).all()
    ]
    user_ids = {UUID(str(row["user_id"])) for row in memberships}
    users = (
        [
            serialize_entity_row(r)
            for r in session.scalars(select(User).where(User.id.in_(user_ids))).all()
        ]
        if user_ids
        else []
    )
    assets = [
        serialize_entity_row(r)
        for r in session.scalars(select(Asset).where(Asset.tenant_id == tenant_id)).all()
    ]
    risks = [
        serialize_entity_row(r)
        for r in session.scalars(select(Risk).where(Risk.tenant_id == tenant_id)).all()
    ]
    vendors = [
        serialize_entity_row(r)
        for r in session.scalars(select(Vendor).where(Vendor.tenant_id == tenant_id)).all()
    ]
    profiles = [
        serialize_entity_row(r)
        for r in session.scalars(
            select(PublicProfile).where(PublicProfile.tenant_id == tenant_id)
        ).all()
    ]
    portals = [
        serialize_entity_row(r)
        for r in session.scalars(
            select(WhistleblowerPortal).where(WhistleblowerPortal.tenant_id == tenant_id)
        ).all()
    ]
    portal_ids = {UUID(str(p["id"])) for p in portals}
    cases = (
        [
            serialize_entity_row(r)
            for r in session.scalars(
                select(WhistleblowerCase).where(WhistleblowerCase.portal_id.in_(portal_ids))
            ).all()
        ]
        if portal_ids
        else []
    )
    state = {
        "assets": sorted(assets, key=lambda x: str(x["id"])),
        "cases": sorted(cases, key=lambda x: str(x["id"])),
        "memberships": sorted(memberships, key=lambda x: str(x["id"])),
        "portals": sorted(portals, key=lambda x: str(x["id"])),
        "profiles": sorted(profiles, key=lambda x: str(x["id"])),
        "risks": sorted(risks, key=lambda x: str(x["id"])),
        "tenants": sorted(tenants, key=lambda x: str(x["id"])),
        "users": sorted(users, key=lambda x: str(x["id"])),
        "vendors": sorted(vendors, key=lambda x: str(x["id"])),
    }
    return json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_v1_openapi_contract_canonical_projection_unaltered() -> None:
    """The runtime application OpenAPI canonical projection matches the frozen V1 fixture payload and digest."""
    assert FIXTURE_PATH.is_file(), f"OpenAPI fixture not found at {FIXTURE_PATH}"

    raw_bytes = FIXTURE_PATH.read_bytes()
    assert raw_bytes.endswith(b"\n"), "Fixture file must end with a single newline"

    fixture_data = json.loads(raw_bytes.decode("utf-8"))
    assert "sha256" in fixture_data, "Fixture missing 'sha256' digest key"
    fixture_digest = fixture_data["sha256"]
    fixture_payload = {k: v for k, v in fixture_data.items() if k != "sha256"}

    reconstructed = build_canonical_v1_openapi_contract(get_pristine_conformly_app())
    reconstructed_digest = compute_canonical_contract_digest(reconstructed)

    assert reconstructed == fixture_payload, (
        "Runtime OpenAPI canonical projection differs from frozen V1 contract"
    )
    assert reconstructed_digest == fixture_digest, (
        "Runtime OpenAPI canonical digest differs from frozen V1 contract"
    )


def test_zero_v2_or_assurance_routes_in_router_tree() -> None:
    """No runtime route path, router, or endpoint exposes Catalog V2 or assurance content."""
    all_routes = extract_all_runtime_routes(get_pristine_conformly_app().routes)
    assert len(all_routes) > 0, "No routes extracted from runtime application"

    forbidden_keywords = (
        "catalog-v2",
        "catalog_v2",
        "evidence-requirement",
        "evidence_requirement",
        "assessment-procedure",
        "assessment_procedure",
        "assurance",
    )

    for path, route in all_routes:
        name = getattr(route, "name", "")
        endpoint = getattr(route, "endpoint", None)
        endpoint_module = getattr(endpoint, "__module__", "")

        assert not path.startswith("/api/v2"), f"Forbidden /api/v2 route registered: {path}"
        for kw in forbidden_keywords:
            assert kw not in path.lower(), f"Forbidden keyword '{kw}' in route path: {path}"
            assert kw not in name.lower(), f"Forbidden keyword '{kw}' in route name: {name}"

        assert not endpoint_module.startswith("conformly.catalog_v2"), (
            f"Route {path} uses endpoint from conformly.catalog_v2: {endpoint_module}"
        )


FORBIDDEN_SCHEMA_NAMES = (
    "catalog",
    "evidencerequirement",
    "evidence_requirement",
    "assessmentprocedure",
    "assessment_procedure",
    "assurance",
    "importbatch",
    "import_batch",
    "reuseledger",
    "reuse_ledger",
    "sourceversion",
    "source_version",
    "controlversion",
    "control_version",
)

FORBIDDEN_PROPERTY_TERMS = (
    "catalog",
    "assurance",
    "evidencerequirement",
    "evidence_requirement",
    "assessmentprocedure",
    "assessment_procedure",
    "importbatch",
    "import_batch",
    "reuseledger",
    "reuse_ledger",
    "sourceversion",
    "source_version",
    "controlversion",
    "control_version",
)

FORBIDDEN_TEXT_TERMS = (
    "catalog",
    "assurance",
    "evidence requirement",
    "assessment procedure",
    "sourceversion",
    "source_version",
    "source version",
    "controlversion",
    "control_version",
    "control version",
    "import batch",
    "reuse ledger",
)

V1_FRAMEWORK_DIFF_PROPERTIES = frozenset({"source_version_id", "source_version_string"})
V1_FRAMEWORK_DIFF_PATHS = frozenset(
    {
        "ImpactReportResponse.properties.source_version_id",
        "ImpactReportResponse.properties.source_version_string",
    }
)


def assert_no_catalog_v2_schema_content(node: Any, path: str = "root") -> None:
    """Recursively traverse schema definitions rejecting Catalog V2 / assurance entities in properties, titles, descriptions, and $refs."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str):
                ref_target = v.split("/")[-1].lower()
                for term in FORBIDDEN_SCHEMA_NAMES:
                    assert term not in ref_target, (
                        f"OpenAPI schema {path} contains forbidden $ref target '{v}' (matched '{term}')"
                    )
            # Property/key checks
            if not (
                path == "ImpactReportResponse.properties" and k in V1_FRAMEWORK_DIFF_PROPERTIES
            ):
                for term in FORBIDDEN_PROPERTY_TERMS:
                    assert term not in k.lower(), (
                        f"OpenAPI schema {path} contains forbidden property/key '{k}' (matched '{term}')"
                    )
            # Title/description string checks
            if k in ("title", "description") and isinstance(v, str):
                if path not in V1_FRAMEWORK_DIFF_PATHS:
                    for term in FORBIDDEN_TEXT_TERMS:
                        assert term not in v.lower(), (
                            f"OpenAPI schema {path}.{k} contains forbidden reference '{v}' (matched '{term}')"
                        )
            assert_no_catalog_v2_schema_content(v, f"{path}.{k}")
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            assert_no_catalog_v2_schema_content(item, f"{path}[{idx}]")


def test_zero_v2_or_assurance_schemas_in_openapi_components() -> None:
    """OpenAPI components.schemas contains zero Catalog V2 or assurance entities in names, definitions, or references."""
    openapi = get_pristine_conformly_app().openapi()
    schemas = openapi.get("components", {}).get("schemas", {})

    for schema_name, schema_def in schemas.items():
        for term in FORBIDDEN_SCHEMA_NAMES:
            assert term not in schema_name.lower(), (
                f"OpenAPI components.schemas contains forbidden V2 entity schema: {schema_name}"
            )
        assert_no_catalog_v2_schema_content(schema_def, schema_name)


def test_schema_content_assertion_catches_source_and_control_version_negatives() -> None:
    """Negative unit tests: assert_no_catalog_v2_schema_content rejects SourceVersion and ControlVersion under innocuous schema names."""
    # 1. Innocuous schema with a forbidden property name 'control_version'
    innocuous_with_ctrl_prop = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "control_version": {"type": "string"},
        },
    }
    with pytest.raises(AssertionError, match="forbidden property/key 'control_version'"):
        assert_no_catalog_v2_schema_content(innocuous_with_ctrl_prop, "UserResponse")

    # 2. Innocuous schema with a forbidden property name 'source_version'
    innocuous_with_src_prop = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "source_version": {"type": "string"},
        },
    }
    with pytest.raises(AssertionError, match="forbidden property/key 'source_version'"):
        assert_no_catalog_v2_schema_content(innocuous_with_src_prop, "ProfileResponse")

    # 3. Innocuous schema with a forbidden title containing 'SourceVersion'
    innocuous_with_src_title = {
        "type": "object",
        "properties": {
            "config": {"type": "string", "title": "Current SourceVersion Setting"},
        },
    }
    with pytest.raises(AssertionError, match="forbidden reference 'Current SourceVersion Setting'"):
        assert_no_catalog_v2_schema_content(innocuous_with_src_title, "SystemMetadata")

    # 4. Innocuous schema with a forbidden description containing 'ControlVersion'
    innocuous_with_ctrl_desc = {
        "type": "object",
        "properties": {
            "details": {"type": "string", "description": "Associated ControlVersion snapshot"},
        },
    }
    with pytest.raises(
        AssertionError, match="forbidden reference 'Associated ControlVersion snapshot'"
    ):
        assert_no_catalog_v2_schema_content(innocuous_with_ctrl_desc, "AuditLogItem")

    # 5. Innocuous schema with a forbidden $ref to 'ControlVersion'
    innocuous_with_ref = {
        "type": "object",
        "properties": {
            "ref_item": {"$ref": "#/components/schemas/ControlVersion"},
        },
    }
    with pytest.raises(
        AssertionError, match=r"forbidden \$ref target '#/components/schemas/ControlVersion'"
    ):
        assert_no_catalog_v2_schema_content(innocuous_with_ref, "AccountSettings")


def test_conformly_main_zero_catalog_imports() -> None:
    """conformly.main does not import or register anything from conformly.catalog_v2."""
    main_py_path = Path(conformly_main.__file__)
    source_code = main_py_path.read_text(encoding="utf-8")
    tree = ast.parse(source_code, filename=str(main_py_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "catalog_v2" not in alias.name, (
                    f"conformly.main has forbidden import: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "catalog_v2" not in mod, f"conformly.main has forbidden import from: {mod}"
            for alias in node.names:
                assert "catalog_v2" not in alias.name, (
                    f"conformly.main has forbidden import: {alias.name} from {mod}"
                )


def test_targeted_v1_tenant_state_preserved_byte_for_byte_across_full_assurance_workflow(
    session: Session,
) -> None:
    """Executing full Catalog V2 core service, assurance service, and synthetic import leaves V1 tenant data untouched."""
    # 1. Seed representative targeted V1 tenant entities using real model fields
    tenant = Tenant(
        id=uuid4(),
        name="Targeted Tenant Alpha",
        slug=f"targeted-tenant-{uuid4()}",
        status=TenantStatus.ACTIVE,
        legal_hold=False,
    )
    user = User(
        id=uuid4(),
        email=f"admin-{uuid4()}@example.com",
        oidc_issuer="https://auth.example.com",
        oidc_subject=f"sub-{uuid4()}",
        display_name="Admin",
        status="ACTIVE",
        is_platform_admin=False,
    )
    membership = Membership(
        id=uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        role=Role.ADMINISTRATOR,
        status=MembershipStatus.ACTIVE,
    )
    asset = Asset(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Targeted Production Host",
        asset_type=AssetType.HARDWARE,
        status="active",
    )
    risk = Risk(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Access Risk",
        description="Targeted risk",
        category="security",
        likelihood=3,
        impact=4,
        inherent_score=12,
        residual_score=6,
        status=RiskStatus.IDENTIFIED,
    )
    vendor = Vendor(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Cloud Provider Inc.",
        service_description="Virtual hosting",
        criticality="high",
        status=VendorStatus.ACTIVE,
    )
    profile = PublicProfile(
        id=uuid4(),
        tenant_id=tenant.id,
        slug=f"profile-{uuid4()}",
        display_name="Targeted Profile Alpha",
        is_published=False,
    )
    portal = WhistleblowerPortal(
        id=uuid4(),
        tenant_id=tenant.id,
        slug=f"portal-{uuid4()}",
        title="Targeted Portal Alpha",
        welcome_text="Report concerns anonymously.",
        is_active=True,
        version=1,
    )
    case = WhistleblowerCase(
        id=uuid4(),
        tenant_id=tenant.id,
        portal_id=portal.id,
        public_case_id="CASE-SYN-001",
        return_secret_salt="0" * 32,
        return_secret_hash="1" * 64,
        status=WhistleblowerCaseStatus.SUBMITTED,
        category=None,
        title=None,
        encrypted_category=None,
        encrypted_title=None,
        encrypted_summary=None,
    )
    session.add_all([tenant, user, membership, asset, risk, vendor, profile, portal, case])
    session.commit()

    # 2. Capture pre-workflow deterministic snapshot
    snapshot_before = snapshot_targeted_v1_tenant_state(session, tenant.id)

    # 3. Setup privileged Catalog actor contexts
    admin_actor_id = uuid4()
    dec_actor_id = uuid4()
    admin_ctx = CatalogActorContext(
        actor_id=admin_actor_id,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset(
            {
                CatalogCapability.DRAFT_READ,
                CatalogCapability.DRAFT_WRITE,
                CatalogCapability.PERMISSION_DECIDE,
            }
        ),
    )
    dec_ctx = CatalogActorContext(
        actor_id=dec_actor_id,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset(
            {
                CatalogCapability.DRAFT_READ,
                CatalogCapability.DRAFT_WRITE,
                CatalogCapability.PERMISSION_DECIDE,
            }
        ),
    )

    # 4. Execute Core Catalog Draft Service
    cat_service = CatalogDraftService(session=session)
    pub = cat_service.create_publisher(
        admin_ctx, "compat-req-pub-01", "compat-pub-01", "Compatibility Publisher"
    )
    src = cat_service.create_source(
        admin_ctx, "compat-req-src-01", pub.id, "compat-framework", "Compatibility Framework"
    )
    sv = cat_service.create_source_version(admin_ctx, "compat-req-sv-01", src.id, "1.0.0")
    prov = CatalogSourceProvenance(
        id=uuid4(),
        source_version_id=sv.id,
        source_revision=1,
        content_sha256=sv.content_digest,
        content_size=1024,
        mime_type="text/plain",
        locator="https://standards.invalid/compat",
        retrieved_at=datetime.now(UTC),
        recorded_by_actor_id=admin_actor_id,
    )
    session.add(prov)
    session.flush()

    prop_ref = CatalogSourcePermissionProposal(
        id=uuid4(),
        provenance_id=prov.id,
        source_version_id=sv.id,
        use_case="reference",
        scope_key="global",
        sequence=1,
        proposed_outcome="Allowed",
        review_state="Draft",
        conditions_state="None",
        recorded_by_actor_id=admin_actor_id,
    )
    prop_map = CatalogSourcePermissionProposal(
        id=uuid4(),
        provenance_id=prov.id,
        source_version_id=sv.id,
        use_case="map",
        scope_key="global",
        sequence=1,
        proposed_outcome="Allowed",
        review_state="Draft",
        conditions_state="None",
        recorded_by_actor_id=admin_actor_id,
    )
    session.add_all([prop_ref, prop_map])
    session.flush()

    cat_service.create_permission_decision(
        dec_ctx,
        "compat-req-spd-01",
        src.id,
        sv.id,
        prop_ref.id,
        use_case="reference",
        scope_key="global",
        decision_type="Allowed",
        valid_from=datetime.now(UTC) - timedelta(hours=1),
        valid_until=None,
        evidence_reference="EVID-COMPAT-01",
    )
    cat_service.create_permission_decision(
        dec_ctx,
        "compat-req-spd-02",
        src.id,
        sv.id,
        prop_map.id,
        use_case="map",
        scope_key="global",
        decision_type="Allowed",
        valid_from=datetime.now(UTC) - timedelta(hours=1),
        valid_until=None,
        evidence_reference="EVID-COMPAT-02",
    )

    req = cat_service.create_requirement(admin_ctx, "compat-req-01", src.id, "REQ-SEC-V2-01")
    rv = cat_service.create_requirement_version(
        admin_ctx,
        "compat-rv-01",
        req.id,
        sv.id,
        "1.0.0",
        "Mandatory requirement description",
        "mandatory",
        "controller",
        "conformly_paraphrase",
        source_references=[
            {
                "source_version_id": sv.id,
                "locator_kind": "clause",
                "locator_value": "1.1",
                "sequence": 1,
            }
        ],
    )
    ctrl = cat_service.create_common_control(
        admin_ctx, "compat-ctrl-01", "CC-SEC-001", "Access Management"
    )
    cv = cat_service.create_control_version(
        admin_ctx,
        "compat-cv-01",
        ctrl.id,
        "1.0.0",
        "Control statement",
        "Control purpose",
        control_type="preventive",
        frequency="continuous",
        automation_level="automated",
        suggested_owner_role="Security Lead",
        assurance_level="foundational",
    )
    mapping = cat_service.create_mapping(
        admin_ctx, "compat-map-01", req.id, ctrl.id, "MAP-IAM-V2-01"
    )
    cat_service.create_mapping_version(
        admin_ctx,
        "compat-mv-01",
        mapping.id,
        rv.id,
        cv.id,
        expected_req_revision=rv.revision,
        expected_req_digest=rv.content_digest,
        expected_ctrl_revision=cv.revision,
        expected_ctrl_digest=cv.content_digest,
        version_label="1.0.0",
        mapping_type="Full",
        rationale="Synthetic mapping verification",
        source_basis="direct_text",
        confidence="high",
    )
    pack = cat_service.create_pack(
        admin_ctx, "compat-pack-01", "PACK-IAM-01", "Compatibility Pack", "regulatory", "EU"
    )
    pv = cat_service.create_pack_version(admin_ctx, "compat-pv-01", pack.id, "1.0.0")
    cat_service.append_pack_membership(
        admin_ctx,
        "compat-pm-01",
        pv.id,
        rv.id,
        expected_req_revision=rv.revision,
        expected_req_digest=rv.content_digest,
    )

    # 5. Execute WP-06B Assurance Draft Service
    assurance_service = CatalogAssuranceDraftService(session=session)
    er_version = assurance_service.create_evidence_requirement_version(
        context=admin_ctx,
        request_key="compat-req-er-01",
        control_version_id=cv.id,
        expected_control_digest=cv.content_digest,
        requirement_key="ER-COMPAT-001",
        title="Compat Evidence Requirement",
        frequency="monthly",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="operating_effectiveness",
        validity_rule="period_coverage",
        max_age_days=None,
        guidance="Guidance",
        artifact_types=["record"],
        required_metadata=[],
    )
    assert er_version is not None

    ap_version = assurance_service.create_assessment_procedure_version(
        context=admin_ctx,
        request_key="compat-req-ap-01",
        control_version_id=cv.id,
        expected_control_digest=cv.content_digest,
        procedure_key="AP-COMPAT-001",
        title="Compat Assessment Procedure",
        objective="Objective",
        sample_guidance=None,
        scope_guidance=None,
        decision_guidance="Decision guidance",
        assessor_qualifications=None,
        steps=[{"step_kind": "inspect", "instruction": "Inspect", "expected_output": None}],
        evidence_requirements=[{"id": er_version.id, "content_digest": er_version.content_digest}],
    )
    assert ap_version is not None

    # Read aggregates
    read_er = assurance_service.get_evidence_requirement_version(admin_ctx, er_version.id)
    assert read_er is not None
    read_ap = assurance_service.get_assessment_procedure_version(admin_ctx, ap_version.id)
    assert read_ap is not None

    # 6. Execute WP-06C Conservative Synthetic Import
    import_service = ConservativeImportService(session=session)
    items = load_fixture("synthetic_assurance_fixture.json")
    adm = import_service.admit_batch(admin_ctx, "batch-compat-01", items)
    manifest = import_service.execute_batch(admin_ctx, adm.batch.id, items)
    assert manifest is not None

    # Replay for exact reuse
    replay_adm = import_service.admit_batch(admin_ctx, "batch-compat-replay-01", items)
    replay_manifest = import_service.execute_batch(admin_ctx, replay_adm.batch.id, items)
    assert replay_manifest is not None

    # 7. Capture post-workflow snapshot and assert 100% byte-for-byte identical state
    snapshot_after = snapshot_targeted_v1_tenant_state(session, tenant.id)
    assert snapshot_after == snapshot_before, (
        "Targeted V1 tenant state was mutated by Catalog V2 / assurance service workflow"
    )


def test_v1_tenant_framework_adoption_unaltered_by_assurance_workflow(session: Session) -> None:
    """Pre-existing V1 tenant framework adoptions are unaltered by Catalog V2 workflows, and no new adoptions are created."""
    tenant = Tenant(
        id=uuid4(),
        name="Adoption Tenant Alpha",
        slug=f"adoption-tenant-{uuid4()}",
        status=TenantStatus.ACTIVE,
        legal_hold=False,
    )
    user = User(
        id=uuid4(),
        email=f"adopter-{uuid4()}@example.com",
        oidc_issuer="https://auth.example.com",
        oidc_subject=f"sub-{uuid4()}",
        display_name="Adopter",
        status="ACTIVE",
        is_platform_admin=False,
    )
    framework = Framework(
        id=uuid4(),
        slug=f"v1-framework-{uuid4()}",
        name="V1 Test Framework",
    )
    framework_version = FrameworkVersion(
        id=uuid4(),
        framework_id=framework.id,
        version="1.0.0",
        release_state=ReleaseState.RELEASED,
        created_by_user_id=user.id,
    )
    pre_existing_adoption = TenantFrameworkAdoption(
        id=uuid4(),
        tenant_id=tenant.id,
        framework_id=framework.id,
        framework_version_id=framework_version.id,
        status=AdoptionStatus.ACTIVE,
        adopted_at=datetime.now(UTC),
        adopted_by_user_id=user.id,
    )
    session.add_all([tenant, user, framework, framework_version, pre_existing_adoption])
    session.commit()

    # Pre-workflow adoption snapshot
    adoptions_pre = [
        serialize_entity_row(r)
        for r in session.scalars(
            select(TenantFrameworkAdoption).where(TenantFrameworkAdoption.tenant_id == tenant.id)
        ).all()
    ]
    assert len(adoptions_pre) == 1

    # Run Catalog V2 core and assurance operations
    admin_ctx = CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset(
            {
                CatalogCapability.DRAFT_READ,
                CatalogCapability.DRAFT_WRITE,
                CatalogCapability.PERMISSION_DECIDE,
            }
        ),
    )
    cat_service = CatalogDraftService(session=session)
    pub = cat_service.create_publisher(
        admin_ctx, "adopt-req-pub-01", "adopt-pub-01", "Adoption Publisher"
    )
    src = cat_service.create_source(
        admin_ctx, "adopt-req-src-01", pub.id, "adopt-framework", "Adoption Framework"
    )
    cat_service.create_source_version(admin_ctx, "adopt-req-sv-01", src.id, "1.0.0")
    ctrl = cat_service.create_common_control(admin_ctx, "adopt-req-cc-01", "CC-IAM-001", "Access")
    cv = cat_service.create_control_version(
        admin_ctx,
        "adopt-req-cv-01",
        ctrl.id,
        "1.0.0",
        "Control statement",
        "Control purpose",
        control_type="preventive",
        frequency="continuous",
        automation_level="automated",
        suggested_owner_role="Lead",
        assurance_level="foundational",
    )

    assurance_service = CatalogAssuranceDraftService(session=session)
    assurance_service.create_evidence_requirement_version(
        context=admin_ctx,
        request_key="adopt-req-er-01",
        control_version_id=cv.id,
        expected_control_digest=cv.content_digest,
        requirement_key="ER-ADOPT-001",
        title="Adoption ER",
        frequency="continuous",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="operating_effectiveness",
        validity_rule="period_coverage",
        max_age_days=None,
        guidance=None,
        artifact_types=["record"],
        required_metadata=[],
    )

    # Post-workflow adoption inspection
    adoptions_post = [
        serialize_entity_row(r)
        for r in session.scalars(
            select(TenantFrameworkAdoption).where(TenantFrameworkAdoption.tenant_id == tenant.id)
        ).all()
    ]

    # Pre-existing adoption row is 100% unmutated
    assert adoptions_post == adoptions_pre, (
        "Pre-existing tenant adoption was mutated by Catalog V2 workflow"
    )

    # Zero adoptions or tenant authorization relationships for Catalog V2 entities exist
    all_adoptions = session.scalars(select(TenantFrameworkAdoption)).all()
    assert len(all_adoptions) == 1
    assert all_adoptions[0].id == pre_existing_adoption.id
    assert all_adoptions[0].framework_id == framework.id


def test_tenant_actors_unauthorized_for_assurance_services(session: Session) -> None:
    """Tenant actors with unprivileged actor contexts are denied access to Catalog V2 assurance and import services."""
    tenant_actor = CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=False,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset(),
    )

    assurance_service = CatalogAssuranceDraftService(session=session)
    fake_cv_id = uuid4()

    with pytest.raises(CatalogSecurityError):
        assurance_service.create_evidence_requirement_version(
            context=tenant_actor,
            request_key="denied-req-er-01",
            control_version_id=fake_cv_id,
            expected_control_digest=b"dummy",
            requirement_key="ER-DENIED-001",
            title="Denied ER",
            frequency="continuous",
            custom_frequency=None,
            scope_state="All",
            scope_guidance=None,
            assurance_purpose="operating_effectiveness",
            validity_rule="period_coverage",
            max_age_days=None,
            guidance=None,
            artifact_types=["record"],
            required_metadata=[],
        )

    with pytest.raises(CatalogSecurityError):
        assurance_service.create_assessment_procedure_version(
            context=tenant_actor,
            request_key="denied-req-ap-01",
            control_version_id=fake_cv_id,
            expected_control_digest=b"dummy",
            procedure_key="AP-DENIED-001",
            title="Denied AP",
            objective="Objective",
            sample_guidance=None,
            scope_guidance=None,
            decision_guidance="Decision guidance",
            assessor_qualifications=None,
            steps=[{"step_kind": "inspect", "instruction": "Inspect", "expected_output": None}],
            evidence_requirements=[],
        )

    import_service = ConservativeImportService(session=session)
    items = load_fixture("synthetic_assurance_fixture.json")

    with pytest.raises(CatalogSecurityError):
        import_service.admit_batch(tenant_actor, "denied-batch-01", items)

    with pytest.raises(CatalogSecurityError):
        import_service.execute_batch(tenant_actor, uuid4(), items)


ALLOWED_ASSURANCE_FK_TARGETS = frozenset(
    {
        "catalog_control_versions",
        "catalog_evidence_requirement_versions",
        "catalog_assessment_procedure_versions",
    }
)


def test_assurance_tables_zero_tenant_foreign_keys() -> None:
    """All foreign keys on WP-06 assurance tables point strictly to the exact 3 allowed Catalog V2 targets, zero to tenant tables."""
    for tbl_name in ASSURANCE_TABLES:
        table = Base.metadata.tables.get(tbl_name)
        assert table is not None, (
            f"Assurance table {tbl_name} missing from SQLAlchemy Base.metadata"
        )

        for fk in table.foreign_keys:
            target_table = fk.column.table.name
            assert target_table not in TENANT_TABLE_NAMES, (
                f"Assurance table {tbl_name} has forbidden foreign key to tenant table: {target_table}"
            )
            assert target_table in ALLOWED_ASSURANCE_FK_TARGETS, (
                f"Assurance table {tbl_name} foreign key points to unauthorized target table: {target_table}"
            )
