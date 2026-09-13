import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.db.session import get_db
from conformly.entitlements.dependencies import require_module
from conformly.frameworks.applicability import (
    TenantProfileContext,
    evaluate_and_apply_adoption_applicability,
)
from conformly.frameworks.impact import ControlModification, ControlSummaryItem, TenantImpactWarning
from conformly.frameworks.manifest import get_pack_manifest_by_id
from conformly.frameworks.models import (
    ControlEntityType,
    CustomControlStatus,
    MappingType,
    OverlayApplicability,
    ReleaseState,
)
from conformly.frameworks.service import (
    AdoptionNotFoundError,
    CanonicalControlNotFoundError,
    ControlMappingNotFoundError,
    ControlOverlayNotFoundError,
    CustomControlNotFoundError,
    FrameworkNotFoundError,
    FrameworkService,
    FrameworkVersionNotFoundError,
    ImmutableCanonicalVersionError,
    IndependentApprovalRequiredError,
    InvalidStateTransitionError,
    UnapprovedReleaseError,
)

canonical_router = APIRouter(prefix="/v1/frameworks", tags=["canonical_frameworks"])
tenant_router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/frameworks",
    tags=["tenant_frameworks"],
    dependencies=[Depends(require_module("frameworks"))],
)
tenant_custom_controls_router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/custom-controls",
    tags=["custom_controls"],
    dependencies=[Depends(require_module("frameworks"))],
)
tenant_mappings_router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/control-mappings",
    tags=["control_mappings"],
    dependencies=[Depends(require_module("frameworks"))],
)


# -----------------------------------------------------------------------------
# Canonical Pydantic Schemas
# -----------------------------------------------------------------------------


class CreateFrameworkRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class CanonicalControlResponse(BaseModel):
    id: UUID
    framework_version_id: UUID
    identifier: str
    title: str
    description: str
    category: str
    guidance: str | None = None
    sort_order: int
    created_at: datetime
    source_reference: str | None = None
    why_evidence_requested: str | None = None
    coverage_disposition: str | None = None
    coverage_rationale: str | None = None


class FrameworkVersionSummaryResponse(BaseModel):
    id: UUID
    framework_id: UUID
    version: str
    release_state: str
    release_notes: str | None
    created_by_user_id: UUID
    legal_reviewed_by_user_id: UUID | None
    legal_reviewed_at: datetime | None
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    released_at: datetime | None
    retired_at: datetime | None
    created_at: datetime
    source_edition: str | None = None
    content_revision: str | None = None
    jurisdiction: str | None = None
    declared_scope: str | None = None
    profile: str | None = None
    limitations: list[str] = []
    is_blocked: bool = False
    required_for_beta_status: str | None = None


class FrameworkVersionDetailResponse(FrameworkVersionSummaryResponse):
    controls: list[CanonicalControlResponse] = []


class FrameworkResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    versions: list[FrameworkVersionSummaryResponse] = []
    source_edition: str | None = None
    content_revision: str | None = None
    jurisdiction: str | None = None
    declared_scope: str | None = None
    profile: str | None = None
    limitations: list[str] = []
    is_blocked: bool = False
    required_for_beta_status: str | None = None


class CreateVersionRequest(BaseModel):
    version: str = Field(..., min_length=1, max_length=50)
    release_notes: str | None = None


class CreateCanonicalControlRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1, max_length=120)
    guidance: str | None = None
    sort_order: int = 0


class UpdateCanonicalControlRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1, max_length=120)
    guidance: str | None = None
    sort_order: int = 0


class ReviewVersionRequest(BaseModel):
    notes: str = Field(..., min_length=1, max_length=2000)


class ApproveVersionRequest(BaseModel):
    notes: str | None = Field(None, max_length=2000)


class ReturnVersionToDraftRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class ImpactReportResponse(BaseModel):
    framework_id: UUID
    source_version_id: UUID
    source_version_string: str
    target_version_id: UUID
    target_version_string: str
    total_source_controls: int
    total_target_controls: int
    added_controls: list[ControlSummaryItem]
    removed_controls: list[ControlSummaryItem]
    modified_controls: list[ControlModification]
    unchanged_count: int
    tenant_warnings: list[TenantImpactWarning]
    overall_impact_level: str


# -----------------------------------------------------------------------------
# Tenant Pydantic Schemas
# -----------------------------------------------------------------------------


class AdoptFrameworkRequest(BaseModel):
    framework_version_id: UUID
    acknowledge_impact: bool = True


class TenantFrameworkAdoptionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    framework_id: UUID
    framework_version_id: UUID
    status: str
    adopted_at: datetime
    adopted_by_user_id: UUID
    impact_analysis_acknowledged_at: datetime | None
    impact_summary: dict[str, Any] | None = None


class ManageOverlayRequest(BaseModel):
    canonical_control_id: UUID
    applicability: OverlayApplicability = OverlayApplicability.APPLICABLE
    justification: str | None = None
    internal_notes: str | None = None
    custom_guidance: str | None = None


class TenantControlOverlayResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    adoption_id: UUID
    canonical_control_id: UUID
    applicability: str
    justification: str | None
    internal_notes: str | None
    custom_guidance: str | None
    created_at: datetime


class CreateCustomControlRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1, max_length=120)
    guidance: str | None = None


class UpdateCustomControlRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1, max_length=120)
    guidance: str | None = None
    status: CustomControlStatus = CustomControlStatus.ACTIVE


class CustomControlResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    identifier: str
    title: str
    description: str
    category: str
    guidance: str | None
    status: str
    created_at: datetime


class CreateControlMappingRequest(BaseModel):
    source_type: ControlEntityType
    source_control_id: UUID
    target_type: ControlEntityType
    target_control_id: UUID
    mapping_type: MappingType = MappingType.SATISFIES
    rationale: str | None = None


class ControlMappingResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    source_type: str
    source_control_id: UUID
    target_type: str
    target_control_id: UUID
    mapping_type: str
    rationale: str | None
    created_at: datetime


# -----------------------------------------------------------------------------
# Dependency helper
# -----------------------------------------------------------------------------


def _svc(database: Annotated[Session, Depends(get_db)]) -> FrameworkService:
    return FrameworkService(session=database)


# -----------------------------------------------------------------------------
# Canonical Framework Endpoints
# -----------------------------------------------------------------------------


@canonical_router.get("", response_model=list[FrameworkResponse])
def list_frameworks(
    principal: CurrentPrincipal,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> list[FrameworkResponse]:
    frameworks = service.list_frameworks(is_platform_admin=principal.is_platform_admin)
    result: list[FrameworkResponse] = []
    for fw in frameworks:
        pack_meta = get_pack_manifest_by_id(fw.slug) or {}
        req_status = pack_meta.get("required_for_beta_status")
        fw_blocked = req_status == "OWNER_DECISION_REQUIRED"
        versions = [
            FrameworkVersionSummaryResponse(
                id=v.id,
                framework_id=v.framework_id,
                version=v.version,
                release_state=v.release_state,
                release_notes=v.release_notes,
                created_by_user_id=v.created_by_user_id,
                legal_reviewed_by_user_id=v.legal_reviewed_by_user_id,
                legal_reviewed_at=v.legal_reviewed_at,
                approved_by_user_id=v.approved_by_user_id,
                approved_at=v.approved_at,
                released_at=v.released_at,
                retired_at=v.retired_at,
                created_at=v.created_at,
                source_edition=pack_meta.get("source_edition"),
                content_revision=pack_meta.get("conformly_content_revision"),
                jurisdiction=pack_meta.get("jurisdiction"),
                declared_scope=pack_meta.get("declared_scope"),
                profile=pack_meta.get("profile"),
                limitations=list(pack_meta.get("blockers") or []),
                is_blocked=fw_blocked or (v.release_state != ReleaseState.RELEASED),
                required_for_beta_status=req_status,
            )
            for v in fw.versions
            if principal.is_platform_admin
            or v.release_state in (ReleaseState.RELEASED, ReleaseState.RETIRED)
        ]
        result.append(
            FrameworkResponse(
                id=fw.id,
                name=fw.name,
                slug=fw.slug,
                description=fw.description,
                created_at=fw.created_at,
                updated_at=fw.updated_at,
                versions=versions,
                source_edition=pack_meta.get("source_edition"),
                content_revision=pack_meta.get("conformly_content_revision"),
                jurisdiction=pack_meta.get("jurisdiction"),
                declared_scope=pack_meta.get("declared_scope"),
                profile=pack_meta.get("profile"),
                limitations=list(pack_meta.get("blockers") or []),
                is_blocked=fw_blocked,
                required_for_beta_status=req_status,
            )
        )
    return result


@canonical_router.post("", response_model=FrameworkResponse, status_code=status.HTTP_201_CREATED)
def create_framework(
    principal: CurrentPrincipal,
    body: CreateFrameworkRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> FrameworkResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        fw = service.create_framework(
            principal=principal,
            name=body.name,
            slug=body.slug,
            description=body.description,
            request_id=request_id,
        )
        return FrameworkResponse(
            id=fw.id,
            name=fw.name,
            slug=fw.slug,
            description=fw.description,
            created_at=fw.created_at,
            updated_at=fw.updated_at,
            versions=[],
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@canonical_router.get("/{framework_id}", response_model=FrameworkResponse)
def get_framework(
    framework_id: UUID,
    principal: CurrentPrincipal,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> FrameworkResponse:
    try:
        fw = service.get_framework(
            framework_id=framework_id, is_platform_admin=principal.is_platform_admin
        )
        pack_meta = get_pack_manifest_by_id(fw.slug) or {}
        req_status = pack_meta.get("required_for_beta_status")
        fw_blocked = req_status == "OWNER_DECISION_REQUIRED"
        versions = [
            FrameworkVersionSummaryResponse(
                id=v.id,
                framework_id=v.framework_id,
                version=v.version,
                release_state=v.release_state,
                release_notes=v.release_notes,
                created_by_user_id=v.created_by_user_id,
                legal_reviewed_by_user_id=v.legal_reviewed_by_user_id,
                legal_reviewed_at=v.legal_reviewed_at,
                approved_by_user_id=v.approved_by_user_id,
                approved_at=v.approved_at,
                released_at=v.released_at,
                retired_at=v.retired_at,
                created_at=v.created_at,
                source_edition=pack_meta.get("source_edition"),
                content_revision=pack_meta.get("conformly_content_revision"),
                jurisdiction=pack_meta.get("jurisdiction"),
                declared_scope=pack_meta.get("declared_scope"),
                profile=pack_meta.get("profile"),
                limitations=list(pack_meta.get("blockers") or []),
                is_blocked=fw_blocked or (v.release_state != ReleaseState.RELEASED),
                required_for_beta_status=req_status,
            )
            for v in fw.versions
            if principal.is_platform_admin
            or v.release_state in (ReleaseState.RELEASED, ReleaseState.RETIRED)
        ]
        return FrameworkResponse(
            id=fw.id,
            name=fw.name,
            slug=fw.slug,
            description=fw.description,
            created_at=fw.created_at,
            updated_at=fw.updated_at,
            versions=versions,
            source_edition=pack_meta.get("source_edition"),
            content_revision=pack_meta.get("conformly_content_revision"),
            jurisdiction=pack_meta.get("jurisdiction"),
            declared_scope=pack_meta.get("declared_scope"),
            profile=pack_meta.get("profile"),
            limitations=list(pack_meta.get("blockers") or []),
            is_blocked=fw_blocked,
            required_for_beta_status=req_status,
        )
    except FrameworkNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@canonical_router.post(
    "/{framework_id}/versions",
    response_model=FrameworkVersionSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_version_draft(
    framework_id: UUID,
    principal: CurrentPrincipal,
    body: CreateVersionRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> FrameworkVersionSummaryResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        v = service.create_version_draft(
            principal=principal,
            framework_id=framework_id,
            version_str=body.version,
            release_notes=body.release_notes,
            request_id=request_id,
        )
        return FrameworkVersionSummaryResponse(
            id=v.id,
            framework_id=v.framework_id,
            version=v.version,
            release_state=v.release_state,
            release_notes=v.release_notes,
            created_by_user_id=v.created_by_user_id,
            legal_reviewed_by_user_id=v.legal_reviewed_by_user_id,
            legal_reviewed_at=v.legal_reviewed_at,
            approved_by_user_id=v.approved_by_user_id,
            approved_at=v.approved_at,
            released_at=v.released_at,
            retired_at=v.retired_at,
            created_at=v.created_at,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except FrameworkNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@canonical_router.get(
    "/{framework_id}/versions/{version_id}", response_model=FrameworkVersionDetailResponse
)
def get_version_details(
    framework_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> FrameworkVersionDetailResponse:
    try:
        v = service.get_version(version_id, is_platform_admin=principal.is_platform_admin)
        if v.framework_id != framework_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="version does not belong to framework"
            )

        mappings_by_ctrl = {
            m.canonical_control_id: m for m in getattr(v, "requirement_control_mappings", [])
        }
        specs_by_ctrl = {
            s.canonical_control_id: s
            for s in getattr(v, "evidence_specifications", [])
            if s.canonical_control_id
        }
        reqs_by_id = {r.id: r for r in getattr(v, "source_requirements", [])}
        coverage_by_req = {
            c.source_requirement_id: c for c in getattr(v, "coverage_ledger_entries", [])
        }

        controls = []
        for c in v.controls:
            m = mappings_by_ctrl.get(c.id)
            source_req = reqs_by_id.get(m.source_requirement_id) if m else None
            spec = specs_by_ctrl.get(c.id)
            cov = coverage_by_req.get(source_req.id) if source_req else None

            controls.append(
                CanonicalControlResponse(
                    id=c.id,
                    framework_version_id=c.framework_version_id,
                    identifier=c.identifier,
                    title=c.title,
                    description=c.description,
                    category=c.category,
                    guidance=c.guidance,
                    sort_order=c.sort_order,
                    created_at=c.created_at,
                    source_reference=source_req.source_reference if source_req else None,
                    why_evidence_requested=spec.description if spec else None,
                    coverage_disposition=str(cov.disposition) if cov else None,
                    coverage_rationale=cov.rationale if cov else None,
                )
            )

        fw = service.get_framework(framework_id, is_platform_admin=principal.is_platform_admin)
        pack_meta = get_pack_manifest_by_id(fw.slug) or {}
        req_status = pack_meta.get("required_for_beta_status")
        is_blocked = (req_status == "OWNER_DECISION_REQUIRED") or (
            v.release_state != ReleaseState.RELEASED
        )

        return FrameworkVersionDetailResponse(
            id=v.id,
            framework_id=v.framework_id,
            version=v.version,
            release_state=v.release_state,
            release_notes=v.release_notes,
            created_by_user_id=v.created_by_user_id,
            legal_reviewed_by_user_id=v.legal_reviewed_by_user_id,
            legal_reviewed_at=v.legal_reviewed_at,
            approved_by_user_id=v.approved_by_user_id,
            approved_at=v.approved_at,
            released_at=v.released_at,
            retired_at=v.retired_at,
            created_at=v.created_at,
            controls=controls,
            source_edition=pack_meta.get("source_edition"),
            content_revision=pack_meta.get("conformly_content_revision"),
            jurisdiction=pack_meta.get("jurisdiction"),
            declared_scope=pack_meta.get("declared_scope"),
            profile=pack_meta.get("profile"),
            limitations=list(pack_meta.get("blockers") or []),
            is_blocked=is_blocked,
            required_for_beta_status=req_status,
        )
    except FrameworkVersionNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@canonical_router.post(
    "/{framework_id}/versions/{version_id}/controls",
    response_model=CanonicalControlResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_canonical_control(
    framework_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    body: CreateCanonicalControlRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> CanonicalControlResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        c = service.add_canonical_control(
            principal=principal,
            version_id=version_id,
            identifier=body.identifier,
            title=body.title,
            description=body.description,
            category=body.category,
            guidance=body.guidance,
            sort_order=body.sort_order,
            request_id=request_id,
        )
        return CanonicalControlResponse(
            id=c.id,
            framework_version_id=c.framework_version_id,
            identifier=c.identifier,
            title=c.title,
            description=c.description,
            category=c.category,
            guidance=c.guidance,
            sort_order=c.sort_order,
            created_at=c.created_at,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except (ImmutableCanonicalVersionError, FrameworkVersionNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@canonical_router.put(
    "/{framework_id}/versions/{version_id}/controls/{control_id}",
    response_model=CanonicalControlResponse,
)
def update_canonical_control(
    framework_id: UUID,
    version_id: UUID,
    control_id: UUID,
    principal: CurrentPrincipal,
    body: UpdateCanonicalControlRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> CanonicalControlResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        c = service.update_canonical_control(
            principal=principal,
            control_id=control_id,
            title=body.title,
            description=body.description,
            category=body.category,
            guidance=body.guidance,
            sort_order=body.sort_order,
            request_id=request_id,
        )
        return CanonicalControlResponse(
            id=c.id,
            framework_version_id=c.framework_version_id,
            identifier=c.identifier,
            title=c.title,
            description=c.description,
            category=c.category,
            guidance=c.guidance,
            sort_order=c.sort_order,
            created_at=c.created_at,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except CanonicalControlNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ImmutableCanonicalVersionError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@canonical_router.delete(
    "/{framework_id}/versions/{version_id}/controls/{control_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_canonical_control(
    framework_id: UUID,
    version_id: UUID,
    control_id: UUID,
    principal: CurrentPrincipal,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> None:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        service.delete_canonical_control(principal, control_id, request_id)
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except CanonicalControlNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ImmutableCanonicalVersionError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@canonical_router.post(
    "/{framework_id}/versions/{version_id}/submit-review",
    response_model=FrameworkVersionSummaryResponse,
)
def submit_version_for_review(
    framework_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> FrameworkVersionSummaryResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        v = service.submit_version_for_review(principal, version_id, request_id)
        return FrameworkVersionSummaryResponse(
            id=v.id,
            framework_id=v.framework_id,
            version=v.version,
            release_state=v.release_state,
            release_notes=v.release_notes,
            created_by_user_id=v.created_by_user_id,
            legal_reviewed_by_user_id=v.legal_reviewed_by_user_id,
            legal_reviewed_at=v.legal_reviewed_at,
            approved_by_user_id=v.approved_by_user_id,
            approved_at=v.approved_at,
            released_at=v.released_at,
            retired_at=v.retired_at,
            created_at=v.created_at,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except (InvalidStateTransitionError, FrameworkVersionNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@canonical_router.post(
    "/{framework_id}/versions/{version_id}/return-draft",
    response_model=FrameworkVersionSummaryResponse,
)
def return_version_to_draft(
    framework_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    body: ReturnVersionToDraftRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> FrameworkVersionSummaryResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        v = service.return_version_to_draft(principal, version_id, body.reason, request_id)
        return FrameworkVersionSummaryResponse(
            id=v.id,
            framework_id=v.framework_id,
            version=v.version,
            release_state=v.release_state,
            release_notes=v.release_notes,
            created_by_user_id=v.created_by_user_id,
            legal_reviewed_by_user_id=v.legal_reviewed_by_user_id,
            legal_reviewed_at=v.legal_reviewed_at,
            approved_by_user_id=v.approved_by_user_id,
            approved_at=v.approved_at,
            released_at=v.released_at,
            retired_at=v.retired_at,
            created_at=v.created_at,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except (InvalidStateTransitionError, FrameworkVersionNotFoundError, ValueError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@canonical_router.post(
    "/{framework_id}/versions/{version_id}/legal-review",
    response_model=FrameworkVersionSummaryResponse,
)
def record_legal_review(
    framework_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    body: ReviewVersionRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> FrameworkVersionSummaryResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        v = service.record_legal_review(principal, version_id, body.notes, request_id)
        return FrameworkVersionSummaryResponse(
            id=v.id,
            framework_id=v.framework_id,
            version=v.version,
            release_state=v.release_state,
            release_notes=v.release_notes,
            created_by_user_id=v.created_by_user_id,
            legal_reviewed_by_user_id=v.legal_reviewed_by_user_id,
            legal_reviewed_at=v.legal_reviewed_at,
            approved_by_user_id=v.approved_by_user_id,
            approved_at=v.approved_at,
            released_at=v.released_at,
            retired_at=v.retired_at,
            created_at=v.created_at,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except (InvalidStateTransitionError, FrameworkVersionNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@canonical_router.post(
    "/{framework_id}/versions/{version_id}/approve",
    response_model=FrameworkVersionSummaryResponse,
)
def approve_version(
    framework_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    body: ApproveVersionRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> FrameworkVersionSummaryResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        v = service.approve_version(principal, version_id, body.notes, request_id)
        return FrameworkVersionSummaryResponse(
            id=v.id,
            framework_id=v.framework_id,
            version=v.version,
            release_state=v.release_state,
            release_notes=v.release_notes,
            created_by_user_id=v.created_by_user_id,
            legal_reviewed_by_user_id=v.legal_reviewed_by_user_id,
            legal_reviewed_at=v.legal_reviewed_at,
            approved_by_user_id=v.approved_by_user_id,
            approved_at=v.approved_at,
            released_at=v.released_at,
            retired_at=v.retired_at,
            created_at=v.created_at,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except IndependentApprovalRequiredError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except (InvalidStateTransitionError, FrameworkVersionNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@canonical_router.post(
    "/{framework_id}/versions/{version_id}/release",
    response_model=FrameworkVersionSummaryResponse,
)
def release_version(
    framework_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> FrameworkVersionSummaryResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        v = service.release_version(principal, version_id, request_id)
        return FrameworkVersionSummaryResponse(
            id=v.id,
            framework_id=v.framework_id,
            version=v.version,
            release_state=v.release_state,
            release_notes=v.release_notes,
            created_by_user_id=v.created_by_user_id,
            legal_reviewed_by_user_id=v.legal_reviewed_by_user_id,
            legal_reviewed_at=v.legal_reviewed_at,
            approved_by_user_id=v.approved_by_user_id,
            approved_at=v.approved_at,
            released_at=v.released_at,
            retired_at=v.retired_at,
            created_at=v.created_at,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except (UnapprovedReleaseError, FrameworkVersionNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@canonical_router.post(
    "/{framework_id}/versions/{version_id}/retire",
    response_model=FrameworkVersionSummaryResponse,
)
def retire_version(
    framework_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> FrameworkVersionSummaryResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        v = service.retire_version(principal, version_id, request_id)
        return FrameworkVersionSummaryResponse(
            id=v.id,
            framework_id=v.framework_id,
            version=v.version,
            release_state=v.release_state,
            release_notes=v.release_notes,
            created_by_user_id=v.created_by_user_id,
            legal_reviewed_by_user_id=v.legal_reviewed_by_user_id,
            legal_reviewed_at=v.legal_reviewed_at,
            approved_by_user_id=v.approved_by_user_id,
            approved_at=v.approved_at,
            released_at=v.released_at,
            retired_at=v.retired_at,
            created_at=v.created_at,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except (InvalidStateTransitionError, FrameworkVersionNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@canonical_router.get(
    "/{framework_id}/compare",
    response_model=ImpactReportResponse,
)
def compare_versions(
    framework_id: UUID,
    principal: CurrentPrincipal,
    source_version_id: Annotated[UUID, Query(...)],
    target_version_id: Annotated[UUID, Query(...)],
    service: Annotated[FrameworkService, Depends(_svc)],
) -> ImpactReportResponse:
    try:
        report = service.compare_versions(
            framework_id,
            source_version_id,
            target_version_id,
            is_platform_admin=principal.is_platform_admin,
        )
        return ImpactReportResponse(
            framework_id=report.framework_id,
            source_version_id=report.source_version_id,
            source_version_string=report.source_version_string,
            target_version_id=report.target_version_id,
            target_version_string=report.target_version_string,
            total_source_controls=report.total_source_controls,
            total_target_controls=report.total_target_controls,
            added_controls=list(report.added_controls),
            removed_controls=list(report.removed_controls),
            modified_controls=list(report.modified_controls),
            unchanged_count=report.unchanged_count,
            tenant_warnings=list(report.tenant_warnings),
            overall_impact_level=report.overall_impact_level,
        )
    except (ValueError, FrameworkVersionNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@canonical_router.get("/applicability-rules")
def get_applicability_rules() -> dict[str, Any]:
    """Return catalog schema and parameter descriptions for deterministic applicability rules."""
    return {
        "parameters": [
            {
                "field": "entity_role",
                "type": "string",
                "options": ["controller", "processor", "both"],
                "description": "Role under GDPR/privacy regulations (Controller, Processor, or Both).",
            },
            {
                "field": "deployment_model",
                "type": "string",
                "options": ["cloud_saas", "hybrid", "on_premise"],
                "description": "Architecture and deployment model.",
            },
            {
                "field": "employee_count",
                "type": "integer",
                "description": "Total employee headcount (triggers German § 38 BDSG DPO threshold if >= 20).",
            },
            {
                "field": "processes_personal_data",
                "type": "boolean",
                "description": "Whether tenant systems collect or process personal data.",
            },
            {
                "field": "processes_special_category_data",
                "type": "boolean",
                "description": "Whether special categories (health/biometric) are processed (§ 22 BDSG / Art 9 GDPR).",
            },
            {
                "field": "has_physical_offices",
                "type": "boolean",
                "description": "Whether the organization operates physical offices vs. 100% remote operations.",
            },
            {
                "field": "operates_own_datacenter",
                "type": "boolean",
                "description": "Whether organization operates its own server rooms/datacenters vs. public cloud hosting.",
            },
            {
                "field": "involves_international_transfers",
                "type": "boolean",
                "description": "Whether personal data is transferred or accessible outside the EEA/EU.",
            },
            {
                "field": "uses_subprocessors",
                "type": "boolean",
                "description": "Whether third-party sub-processors or external data vendors are engaged.",
            },
        ],
        "evaluations": ["applicable", "not_applicable", "scoped_out"],
    }


# -----------------------------------------------------------------------------
# Tenant Framework Endpoints
# -----------------------------------------------------------------------------


@tenant_router.get("/adoptions", response_model=list[TenantFrameworkAdoptionResponse])
def list_tenant_adoptions(
    tenant_id: UUID,
    tenant_context: CurrentTenant,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> list[TenantFrameworkAdoptionResponse]:
    adoptions = service.list_tenant_adoptions(tenant_context)
    return [
        TenantFrameworkAdoptionResponse(
            id=a.id,
            tenant_id=a.tenant_id,
            framework_id=a.framework_id,
            framework_version_id=a.framework_version_id,
            status=a.status,
            adopted_at=a.adopted_at,
            adopted_by_user_id=a.adopted_by_user_id,
            impact_analysis_acknowledged_at=a.impact_analysis_acknowledged_at,
            impact_summary=json.loads(a.impact_summary_json) if a.impact_summary_json else None,
        )
        for a in adoptions
    ]


@tenant_router.get("/{framework_id}/impact", response_model=ImpactReportResponse)
def get_tenant_impact_analysis(
    tenant_id: UUID,
    framework_id: UUID,
    target_version_id: Annotated[UUID, Query(...)],
    tenant_context: CurrentTenant,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> ImpactReportResponse:

    try:
        report = service.get_tenant_impact_analysis(tenant_context, framework_id, target_version_id)
        return ImpactReportResponse(
            framework_id=report.framework_id,
            source_version_id=report.source_version_id,
            source_version_string=report.source_version_string,
            target_version_id=report.target_version_id,
            target_version_string=report.target_version_string,
            total_source_controls=report.total_source_controls,
            total_target_controls=report.total_target_controls,
            added_controls=list(report.added_controls),
            removed_controls=list(report.removed_controls),
            modified_controls=list(report.modified_controls),
            unchanged_count=report.unchanged_count,
            tenant_warnings=list(report.tenant_warnings),
            overall_impact_level=report.overall_impact_level,
        )
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err
    except (ValueError, FrameworkVersionNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@tenant_router.post(
    "/adopt", response_model=TenantFrameworkAdoptionResponse, status_code=status.HTTP_201_CREATED
)
def adopt_framework_version(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    body: AdoptFrameworkRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> TenantFrameworkAdoptionResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    version = service.get_version(
        body.framework_version_id, is_platform_admin=principal.is_platform_admin
    )
    framework = service.get_framework(
        version.framework_id, is_platform_admin=principal.is_platform_admin
    )
    pack_meta = get_pack_manifest_by_id(framework.slug)
    if pack_meta and pack_meta.get("required_for_beta_status") == "OWNER_DECISION_REQUIRED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Adoption blocked: Framework pack '{framework.slug}' is pending Product Owner confirmation",
        )
    if version.release_state != ReleaseState.RELEASED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"cannot adopt version in non-released state: {version.release_state}",
        )
    try:
        a = service.adopt_framework_version(
            principal=principal,
            tenant_context=tenant_context,
            framework_version_id=body.framework_version_id,
            acknowledge_impact=body.acknowledge_impact,
            request_id=request_id,
        )
        return TenantFrameworkAdoptionResponse(
            id=a.id,
            tenant_id=a.tenant_id,
            framework_id=a.framework_id,
            framework_version_id=a.framework_version_id,
            status=a.status,
            adopted_at=a.adopted_at,
            adopted_by_user_id=a.adopted_by_user_id,
            impact_analysis_acknowledged_at=a.impact_analysis_acknowledged_at,
            impact_summary=json.loads(a.impact_summary_json) if a.impact_summary_json else None,
        )
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err
    except Exception as err:
        from conformly.entitlements.service import FrameworkPackNotEntitledError

        if isinstance(err, FrameworkPackNotEntitledError):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
        if isinstance(err, (ValueError, FrameworkVersionNotFoundError)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
        raise


@tenant_router.get(
    "/adoptions/{adoption_id}/overlays", response_model=list[TenantControlOverlayResponse]
)
def list_overlays(
    tenant_id: UUID,
    adoption_id: UUID,
    tenant_context: CurrentTenant,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> list[TenantControlOverlayResponse]:
    try:
        overlays = service.list_overlays(tenant_context, adoption_id)
        return [
            TenantControlOverlayResponse(
                id=o.id,
                tenant_id=o.tenant_id,
                adoption_id=o.adoption_id,
                canonical_control_id=o.canonical_control_id,
                applicability=o.applicability,
                justification=o.justification,
                internal_notes=o.internal_notes,
                custom_guidance=o.custom_guidance,
                created_at=o.created_at,
            )
            for o in overlays
        ]
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err


@tenant_router.post(
    "/adoptions/{adoption_id}/overlays",
    response_model=TenantControlOverlayResponse,
    status_code=status.HTTP_201_CREATED,
)
def manage_overlay(
    tenant_id: UUID,
    adoption_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    body: ManageOverlayRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> TenantControlOverlayResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        o = service.manage_overlay(
            principal=principal,
            tenant_context=tenant_context,
            adoption_id=adoption_id,
            canonical_control_id=body.canonical_control_id,
            applicability=body.applicability,
            justification=body.justification,
            internal_notes=body.internal_notes,
            custom_guidance=body.custom_guidance,
            request_id=request_id,
        )
        return TenantControlOverlayResponse(
            id=o.id,
            tenant_id=o.tenant_id,
            adoption_id=o.adoption_id,
            canonical_control_id=o.canonical_control_id,
            applicability=o.applicability,
            justification=o.justification,
            internal_notes=o.internal_notes,
            custom_guidance=o.custom_guidance,
            created_at=o.created_at,
        )
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err
    except (AdoptionNotFoundError, CanonicalControlNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@tenant_router.delete(
    "/adoptions/{adoption_id}/overlays/{overlay_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_overlay(
    tenant_id: UUID,
    adoption_id: UUID,
    overlay_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> None:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        service.delete_overlay(principal, tenant_context, overlay_id, request_id)
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err
    except ControlOverlayNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@tenant_router.post(
    "/adoptions/{adoption_id}/evaluate-applicability",
    response_model=list[TenantControlOverlayResponse],
)
def evaluate_adoption_applicability(
    tenant_id: UUID,
    adoption_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    body: TenantProfileContext,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> list[TenantControlOverlayResponse]:
    """Deterministically evaluate profile parameters against framework controls and apply overlays."""
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        from conformly.authz.policy import authorize
        from conformly.authz.roles import Capability

        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        overlays = evaluate_and_apply_adoption_applicability(
            db,
            tenant_id=tenant_id,
            adoption_id=adoption_id,
            profile=body,
            principal=principal,
            request_id=request_id,
            tenant_context=tenant_context,
        )
        return [
            TenantControlOverlayResponse(
                id=o.id,
                tenant_id=o.tenant_id,
                adoption_id=o.adoption_id,
                canonical_control_id=o.canonical_control_id,
                applicability=o.applicability,
                justification=o.justification,
                internal_notes=o.internal_notes,
                custom_guidance=o.custom_guidance,
                created_at=o.created_at,
            )
            for o in overlays
        ]
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


# -----------------------------------------------------------------------------
# Tenant Custom Controls Endpoints
# -----------------------------------------------------------------------------


@tenant_custom_controls_router.get("", response_model=list[CustomControlResponse])
def list_custom_controls(
    tenant_id: UUID,
    tenant_context: CurrentTenant,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> list[CustomControlResponse]:
    try:
        controls = service.list_custom_controls(tenant_context)
        return [
            CustomControlResponse(
                id=c.id,
                tenant_id=c.tenant_id,
                identifier=c.identifier,
                title=c.title,
                description=c.description,
                category=c.category,
                guidance=c.guidance,
                status=c.status,
                created_at=c.created_at,
            )
            for c in controls
        ]
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err


@tenant_custom_controls_router.post(
    "", response_model=CustomControlResponse, status_code=status.HTTP_201_CREATED
)
def create_custom_control(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    body: CreateCustomControlRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> CustomControlResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        c = service.create_custom_control(
            principal=principal,
            tenant_context=tenant_context,
            identifier=body.identifier,
            title=body.title,
            description=body.description,
            category=body.category,
            guidance=body.guidance,
            request_id=request_id,
        )
        return CustomControlResponse(
            id=c.id,
            tenant_id=c.tenant_id,
            identifier=c.identifier,
            title=c.title,
            description=c.description,
            category=c.category,
            guidance=c.guidance,
            status=c.status,
            created_at=c.created_at,
        )
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@tenant_custom_controls_router.put("/{control_id}", response_model=CustomControlResponse)
def update_custom_control(
    tenant_id: UUID,
    control_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    body: UpdateCustomControlRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> CustomControlResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        c = service.update_custom_control(
            principal=principal,
            tenant_context=tenant_context,
            control_id=control_id,
            title=body.title,
            description=body.description,
            category=body.category,
            guidance=body.guidance,
            status=body.status,
            request_id=request_id,
        )
        return CustomControlResponse(
            id=c.id,
            tenant_id=c.tenant_id,
            identifier=c.identifier,
            title=c.title,
            description=c.description,
            category=c.category,
            guidance=c.guidance,
            status=c.status,
            created_at=c.created_at,
        )
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err
    except CustomControlNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


# -----------------------------------------------------------------------------
# Tenant Control Mappings Endpoints
# -----------------------------------------------------------------------------


@tenant_mappings_router.get("", response_model=list[ControlMappingResponse])
def list_control_mappings(
    tenant_id: UUID,
    tenant_context: CurrentTenant,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> list[ControlMappingResponse]:
    try:
        mappings = service.list_control_mappings(tenant_context)
        return [
            ControlMappingResponse(
                id=m.id,
                tenant_id=m.tenant_id,
                source_type=m.source_type,
                source_control_id=m.source_control_id,
                target_type=m.target_type,
                target_control_id=m.target_control_id,
                mapping_type=m.mapping_type,
                rationale=m.rationale,
                created_at=m.created_at,
            )
            for m in mappings
        ]
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err


@tenant_mappings_router.post(
    "", response_model=ControlMappingResponse, status_code=status.HTTP_201_CREATED
)
def create_control_mapping(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    body: CreateControlMappingRequest,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> ControlMappingResponse:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        m = service.create_control_mapping(
            principal=principal,
            tenant_context=tenant_context,
            source_type=body.source_type,
            source_control_id=body.source_control_id,
            target_type=body.target_type,
            target_control_id=body.target_control_id,
            mapping_type=body.mapping_type,
            rationale=body.rationale,
            request_id=request_id,
        )
        return ControlMappingResponse(
            id=m.id,
            tenant_id=m.tenant_id,
            source_type=m.source_type,
            source_control_id=m.source_control_id,
            target_type=m.target_type,
            target_control_id=m.target_control_id,
            mapping_type=m.mapping_type,
            rationale=m.rationale,
            created_at=m.created_at,
        )
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err


@tenant_mappings_router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_control_mapping(
    tenant_id: UUID,
    mapping_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    service: Annotated[FrameworkService, Depends(_svc)],
) -> None:
    request_id = request.headers.get("x-request-id", "req-unknown")
    try:
        service.delete_control_mapping(principal, tenant_context, mapping_id, request_id)
    except AuthorizationDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from err
    except ControlMappingNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
