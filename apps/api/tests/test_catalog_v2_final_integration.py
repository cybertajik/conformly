"""WP-05 Service-Only Final Integration & V1 Compatibility Test Suite.

Proves:
1. Frozen V1 OpenAPI route/method/security surface compatibility against deterministic fixture.
2. Complete absence of Catalog V2 HTTP routers, routes, endpoints, operations, or schemas.
3. conformly.main does not import or register anything from conformly.catalog_v2.
4. All runtime V1 routes and security schemes match the frozen fixture exactly.
5. Representative synthetic Catalog V2 service operations leave V1 tenant data untouched byte-for-byte.
6. Synthetic Catalog V2 operations create no tenant adoption or authorization relationship.
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

from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import conformly.main as conformly_main
from conformly.assets.models import Asset, AssetType
from conformly.authz.roles import Role
from conformly.catalog_v2.actor import CatalogActorContext, CatalogCapability
from conformly.catalog_v2.models import (
    CatalogSourcePermissionProposal,
    CatalogSourceProvenance,
)
from conformly.catalog_v2.service import CatalogDraftService
from conformly.frameworks.models import TenantFrameworkAdoption
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.risks.models import Risk, RiskStatus
from conformly.vendors.models import Vendor, VendorStatus

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


def snapshot_v1_tenant_state(session: Session, tenant_id: UUID) -> bytes:
    """Return deterministic canonical JSON bytes of all tenant-owned V1 entities for comparison."""
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
    state = {
        "assets": sorted(assets, key=lambda x: str(x["id"])),
        "memberships": sorted(memberships, key=lambda x: str(x["id"])),
        "risks": sorted(risks, key=lambda x: str(x["id"])),
        "tenants": sorted(tenants, key=lambda x: str(x["id"])),
        "users": sorted(users, key=lambda x: str(x["id"])),
        "vendors": sorted(vendors, key=lambda x: str(x["id"])),
    }
    return json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_v1_openapi_fixture_self_digest_and_canonical_formatting() -> None:
    """The compatibility fixture exists, has a valid self-digest, and is canonically formatted."""
    assert FIXTURE_PATH.is_file(), f"OpenAPI fixture not found at {FIXTURE_PATH}"

    raw_bytes = FIXTURE_PATH.read_bytes()
    assert raw_bytes.endswith(b"\n"), "Fixture file must end with a single newline"

    data = json.loads(raw_bytes.decode("utf-8"))
    assert "sha256" in data, "Fixture missing 'sha256' digest key"
    stored_digest = data["sha256"]

    payload = {k: v for k, v in data.items() if k != "sha256"}
    expected_digest = compute_canonical_contract_digest(payload)
    assert stored_digest == expected_digest, "Fixture self-digest mismatch"

    expected_canonical_bytes = (
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    )
    assert raw_bytes == expected_canonical_bytes, "Fixture file is not formatted as canonical JSON"

    assert payload["title"] == "Conformly API"
    assert payload["version"] == "0.1.0"
    assert len(payload["paths"]) == 144
    total_operations = sum(len(methods) for methods in payload["paths"].values())
    assert total_operations == 191


def test_runtime_openapi_matches_frozen_v1_contract_exactly() -> None:
    """The runtime application OpenAPI matches the frozen V1 contract payload and digest."""
    fixture_data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fixture_payload = {k: v for k, v in fixture_data.items() if k != "sha256"}
    fixture_digest = fixture_data["sha256"]

    reconstructed = build_canonical_v1_openapi_contract(get_pristine_conformly_app())
    reconstructed_digest = compute_canonical_contract_digest(reconstructed)

    assert reconstructed == fixture_payload, (
        "Runtime OpenAPI payload differs from frozen V1 contract"
    )
    assert reconstructed_digest == fixture_digest, (
        "Runtime OpenAPI digest differs from frozen V1 contract"
    )


def test_no_v2_or_catalog_v2_routes_registered_at_runtime() -> None:
    """No runtime route path, router, or endpoint exposes V2 or Catalog V2."""
    all_routes = extract_all_runtime_routes(get_pristine_conformly_app().routes)
    assert len(all_routes) > 0, "No routes extracted from runtime application"

    for path, route in all_routes:
        name = getattr(route, "name", "")
        endpoint = getattr(route, "endpoint", None)
        endpoint_module = getattr(endpoint, "__module__", "")

        assert not path.startswith("/api/v2"), f"Forbidden /api/v2 route registered: {path}"
        assert "catalog-v2" not in path.lower(), f"Forbidden catalog-v2 in route path: {path}"
        assert "catalog_v2" not in path.lower(), f"Forbidden catalog_v2 in route path: {path}"

        assert "catalog_v2" not in name.lower(), f"Forbidden catalog_v2 in route name: {name}"
        assert "catalog-v2" not in name.lower(), f"Forbidden catalog-v2 in route name: {name}"

        assert not endpoint_module.startswith("conformly.catalog_v2"), (
            f"Route {path} uses endpoint from conformly.catalog_v2: {endpoint_module}"
        )


def test_no_v2_or_catalog_v2_elements_in_runtime_openapi_document() -> None:
    """OpenAPI paths, operations, tags, and schemas contain zero Catalog V2 references."""
    openapi = get_pristine_conformly_app().openapi()

    # 1. Path inspection
    for path in openapi.get("paths", {}):
        assert not path.startswith("/api/v2"), f"OpenAPI exposes /api/v2 path: {path}"
        assert "catalog_v2" not in path.lower(), f"OpenAPI path references catalog_v2: {path}"
        assert "catalog-v2" not in path.lower(), f"OpenAPI path references catalog-v2: {path}"

    # 2. Operations, tags, and operation IDs inspection
    for path, methods in openapi.get("paths", {}).items():
        for method, op in methods.items():
            if method.lower() not in HTTP_METHODS:
                continue
            op_id = op.get("operationId", "")
            tags = op.get("tags", [])
            summary = op.get("summary", "")
            description = op.get("description", "")

            assert "catalog_v2" not in op_id.lower(), f"Forbidden operationId in {path}: {op_id}"
            assert "catalog-v2" not in op_id.lower(), f"Forbidden operationId in {path}: {op_id}"
            assert "catalogv2" not in op_id.lower(), f"Forbidden operationId in {path}: {op_id}"

            for tag in tags:
                assert "catalog_v2" not in tag.lower(), f"Forbidden tag in {path}: {tag}"
                assert "catalog-v2" not in tag.lower(), f"Forbidden tag in {path}: {tag}"

            assert "catalog_v2" not in summary.lower(), f"Forbidden summary in {path}: {summary}"
            assert "catalog-v2" not in summary.lower(), f"Forbidden summary in {path}: {summary}"
            assert "catalog_v2" not in description.lower(), (
                f"Forbidden description in {path}: {description}"
            )

    # 3. Component schemas inspection
    schemas = openapi.get("components", {}).get("schemas", {})
    for schema_name in schemas:
        assert "catalog_v2" not in schema_name.lower(), f"Catalog V2 schema found: {schema_name}"
        assert "catalog-v2" not in schema_name.lower(), f"Catalog V2 schema found: {schema_name}"
        assert "catalogv2" not in schema_name.lower(), f"Catalog V2 schema found: {schema_name}"


def test_conformly_main_does_not_import_or_register_catalog_v2() -> None:
    """conformly.main AST contains no imports from conformly.catalog_v2."""
    import conformly.main

    main_source_file = Path(conformly.main.__file__).resolve()
    assert main_source_file.is_file()

    tree = ast.parse(main_source_file.read_text(encoding="utf-8"), filename=str(main_source_file))
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


def test_v1_route_methods_and_security_schemes_verified_against_fixture() -> None:
    """Verify all runtime V1 routes, methods, and security schemes against the frozen fixture."""
    fixture_data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fixture_paths = fixture_data["paths"]
    fixture_security = fixture_data["components"]["securitySchemes"]

    # Assert exact security schemes
    assert fixture_security == {"HTTPBearer": {"scheme": "bearer", "type": "http"}}
    assert (
        get_pristine_conformly_app().openapi().get("components", {}).get("securitySchemes", {})
        == fixture_security
    )

    # Build runtime route-method mapping from extracted router tree
    all_extracted = extract_all_runtime_routes(get_pristine_conformly_app().routes)
    api_routes = [
        (path, r)
        for path, r in all_extracted
        if not path.startswith(("/docs", "/redoc", "/openapi.json"))
    ]

    runtime_paths_methods: dict[str, set[str]] = {}
    for path, route in api_routes:
        methods_raw: Any = getattr(route, "methods", set())
        methods_set: set[str] = set(methods_raw) if methods_raw else set()
        valid_methods = {m.lower() for m in methods_set if m.lower() in HTTP_METHODS}
        runtime_paths_methods.setdefault(path, set()).update(valid_methods)

    # Compare against fixture paths
    assert set(runtime_paths_methods.keys()) == set(fixture_paths.keys()), (
        f"Path mismatch between runtime and fixture: diff = {set(runtime_paths_methods.keys()) ^ set(fixture_paths.keys())}"
    )

    for path, expected_methods in fixture_paths.items():
        assert runtime_paths_methods[path] == set(expected_methods.keys()), (
            f"Method mismatch for path {path}: runtime={runtime_paths_methods[path]}, expected={set(expected_methods.keys())}"
        )


def test_synthetic_catalog_v2_service_flow_preserves_v1_tenant_data_byte_for_byte(
    session: Session,
) -> None:
    """Representative synthetic Catalog V2 service workflow leaves V1 tenant data byte-for-byte unchanged."""
    # 1. Seed representative V1 tenant entities
    tenant = Tenant(
        id=uuid4(),
        name="V1 Compliance Tenant",
        slug=f"v1-compliance-{uuid4()}",
        status=TenantStatus.ACTIVE,
        legal_hold=False,
    )
    user = User(
        id=uuid4(),
        email=f"compliance-admin-{uuid4()}@example.com",
        oidc_issuer="https://auth.example.com",
        oidc_subject=f"sub-{uuid4()}",
        display_name="Compliance Admin",
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
        name="Core Production Server",
        asset_type=AssetType.HARDWARE,
        status="active",
    )
    risk = Risk(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Unauthorized Data Access",
        description="Risk of unauthorized credential exposure",
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
        name="Secure Cloud Infrastructure Inc.",
        service_description="Managed Virtual Cloud Services",
        criticality="high",
        status=VendorStatus.ACTIVE,
    )
    session.add_all([tenant, user, membership, asset, risk, vendor])
    session.commit()

    # 2. Capture pre-flow deterministic snapshot
    snapshot_before = snapshot_v1_tenant_state(session, tenant.id)

    # 3. Execute supported Catalog V2 draft service workflow (isolated platform catalog operations)
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

    cat_service = CatalogDraftService(session=session)
    pub = cat_service.create_publisher(
        admin_ctx, "req-pub-v2", "pub-iso-v2", "ISO Catalog Publisher"
    )
    src = cat_service.create_source(
        admin_ctx, "req-src-v2", pub.id, "src-iso-27001-v2", "ISO 27001 V2 Source"
    )
    sv = cat_service.create_source_version(admin_ctx, "req-sv-v2", src.id, edition="2026-v2")

    prov = CatalogSourceProvenance(
        id=uuid4(),
        source_version_id=sv.id,
        source_revision=1,
        content_sha256=sv.content_digest,
        content_size=1024,
        mime_type="text/plain",
        locator="https://standards.invalid/iso27001",
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
        "req-dec-ref-v2",
        src.id,
        sv.id,
        prop_ref.id,
        use_case="reference",
        scope_key="global",
        decision_type="Allowed",
        valid_from=datetime.now(UTC) - timedelta(hours=1),
        valid_until=None,
        evidence_reference="EVID-REF-V2",
    )
    cat_service.create_permission_decision(
        dec_ctx,
        "req-dec-map-v2",
        src.id,
        sv.id,
        prop_map.id,
        use_case="map",
        scope_key="global",
        decision_type="Allowed",
        valid_from=datetime.now(UTC) - timedelta(hours=1),
        valid_until=None,
        evidence_reference="EVID-MAP-V2",
    )

    req = cat_service.create_requirement(admin_ctx, "req-r-v2", src.id, "REQ-SEC-V2-01")
    rv = cat_service.create_requirement_version(
        admin_ctx,
        "req-rv-v2",
        req.id,
        sv.id,
        "1.0.0",
        "Mandatory multi-factor authentication for administrative accounts",
        "mandatory",
        "controller",
        "conformly_paraphrase",
        source_references=[
            {
                "source_version_id": sv.id,
                "locator_kind": "clause",
                "locator_value": "A.9.4.2",
                "sequence": 1,
            }
        ],
    )

    ctrl = cat_service.create_common_control(
        admin_ctx, "req-cc-v2", "CC-IAM-001", "Identity & Access"
    )
    cv = cat_service.create_control_version(
        admin_ctx,
        "req-cv-v2",
        ctrl.id,
        "1.0.0",
        "Require FIDO2 or TOTP second factor for privileged consoles",
        "Mitigate credential theft and brute force attacks",
        control_type="preventive",
        frequency="continuous",
        automation_level="automated",
        suggested_owner_role="IAM Lead",
        assurance_level="foundational",
    )

    mapping = cat_service.create_mapping(admin_ctx, "req-map-v2", req.id, ctrl.id, "MAP-IAM-V2-01")
    cat_service.create_mapping_version(
        admin_ctx,
        "req-mv-v2",
        mapping.id,
        rv.id,
        cv.id,
        expected_req_revision=rv.revision,
        expected_req_digest=rv.content_digest,
        expected_ctrl_revision=cv.revision,
        expected_ctrl_digest=cv.content_digest,
        version_label="1.0.0",
        mapping_type="Full",
        rationale="Privileged MFA control satisfies administrative access requirement",
        source_basis="direct_text",
        confidence="high",
    )

    pack = cat_service.create_pack(
        admin_ctx, "req-pk-v2", "PACK-SEC-V2", "Security Core Pack V2", "regulatory", "EU"
    )
    pv = cat_service.create_pack_version(admin_ctx, "req-pkv-v2", pack.id, "1.0.0")
    cat_service.append_pack_membership(
        admin_ctx,
        "req-pkm-v2",
        pv.id,
        rv.id,
        expected_req_revision=rv.revision,
        expected_req_digest=rv.content_digest,
    )
    session.commit()

    # 4. Capture post-flow snapshot and assert byte-for-byte equivalence
    snapshot_after = snapshot_v1_tenant_state(session, tenant.id)
    assert snapshot_after == snapshot_before, (
        "V1 tenant data was modified by Catalog V2 service workflow"
    )

    # 5. Assert no tenant framework adoptions exist
    adoption_count = session.scalar(select(func.count()).select_from(TenantFrameworkAdoption))
    assert adoption_count == 0, f"Expected 0 tenant adoptions, found {adoption_count}"

    # 6. Assert no tenant authorization or adoption relationship was created
    adoptions_for_tenant = session.scalars(
        select(TenantFrameworkAdoption).where(TenantFrameworkAdoption.tenant_id == tenant.id)
    ).all()
    assert len(adoptions_for_tenant) == 0

    # 7. Assert no V2 route is exposed at runtime
    assert not any(
        getattr(r, "path", "").startswith("/api/v2") for r in get_pristine_conformly_app().routes
    )
