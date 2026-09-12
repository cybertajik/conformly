from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.db.session import get_db
from conformly.exports.models import (
    ExportJob,
    ExportJobStatus,
    ExportManifest,
    ExportScope,
)
from conformly.exports.service import (
    ExportExpiredError,
    ExportNotFoundError,
    ExportProcessingError,
    ExportService,
)
from conformly.retention.models import (
    DeletionProof,
)
from conformly.retention.service import (
    CancellationError,
    DeletionJobNotFoundError,
    LegalHoldActiveError,
    RetentionService,
)
from conformly.storage.service import StorageService, get_storage_service

lifecycle_router = APIRouter(
    prefix="/v1/tenants/{tenant_id}",
    tags=["lifecycle"],
)


def get_export_service(
    database: Annotated[Session, Depends(get_db)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
) -> ExportService:
    return ExportService(database, storage_service)


def get_retention_service(
    database: Annotated[Session, Depends(get_db)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    export_service: Annotated[ExportService, Depends(get_export_service)],
) -> RetentionService:
    return RetentionService(database, storage_service, export_service)


# ── Pydantic Request & Response Schemas ─────────────────────────────────────


class CreateExportRequest(BaseModel):
    scope: ExportScope = ExportScope.FULL


class ExportManifestResponse(BaseModel):
    id: UUID
    export_job_id: UUID
    tenant_id: UUID
    dataset_versions: dict[str, Any]
    file_hashes: dict[str, Any]
    record_counts: dict[str, Any]
    audit_references: dict[str, Any]
    manifest_sha256: str
    created_at: datetime


class ExportJobResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    requested_by_user_id: UUID
    scope: ExportScope
    status: ExportJobStatus
    stored_file_id: UUID | None = None
    records_count: int
    files_count: int
    size_bytes: int
    sha256_hash: str | None = None
    error_message: str | None = None
    expires_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ExportJobDetailResponse(ExportJobResponse):
    manifest: ExportManifestResponse | None = None


class CancellationRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    confirm_slug: str = Field(min_length=1, max_length=100)


class LegalHoldRequest(BaseModel):
    enabled: bool
    reason: str = Field(min_length=3, max_length=500)


class TenantCancellationResponse(BaseModel):
    status: str
    cancellation_requested_at: datetime | None = None
    export_until: datetime | None = None
    deletion_due_at: datetime | None = None
    days_remaining_in_export_window: int | None = None
    is_export_window_active: bool
    legal_hold: bool


class DeletionProofResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    deletion_job_id: UUID
    deleted_at: datetime
    tables_purged: dict[str, Any]
    storage_objects_purged: int
    proof_manifest_sha256: str
    created_at: datetime


def _to_manifest_response(manifest: ExportManifest) -> ExportManifestResponse:
    return ExportManifestResponse(
        id=manifest.id,
        export_job_id=manifest.export_job_id,
        tenant_id=manifest.tenant_id,
        dataset_versions=manifest.dataset_versions,
        file_hashes=manifest.file_hashes,
        record_counts=manifest.record_counts,
        audit_references=manifest.audit_references,
        manifest_sha256=manifest.manifest_sha256,
        created_at=manifest.created_at,
    )


def _to_job_response(job: ExportJob) -> ExportJobResponse:
    return ExportJobResponse(
        id=job.id,
        tenant_id=job.tenant_id,
        requested_by_user_id=job.requested_by_user_id,
        scope=job.scope,
        status=job.status,
        stored_file_id=job.stored_file_id,
        records_count=job.records_count,
        files_count=job.files_count,
        size_bytes=job.size_bytes,
        sha256_hash=job.sha256_hash,
        error_message=job.error_message,
        expires_at=job.expires_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _to_job_detail_response(job: ExportJob) -> ExportJobDetailResponse:
    manifest_resp = _to_manifest_response(job.manifest) if job.manifest else None
    return ExportJobDetailResponse(
        id=job.id,
        tenant_id=job.tenant_id,
        requested_by_user_id=job.requested_by_user_id,
        scope=job.scope,
        status=job.status,
        stored_file_id=job.stored_file_id,
        records_count=job.records_count,
        files_count=job.files_count,
        size_bytes=job.size_bytes,
        sha256_hash=job.sha256_hash,
        error_message=job.error_message,
        expires_at=job.expires_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        manifest=manifest_resp,
    )


def _to_proof_response(proof: DeletionProof) -> DeletionProofResponse:
    return DeletionProofResponse(
        id=proof.id,
        tenant_id=proof.tenant_id,
        deletion_job_id=proof.deletion_job_id,
        deleted_at=proof.deleted_at,
        tables_purged=proof.tables_purged,
        storage_objects_purged=proof.storage_objects_purged,
        proof_manifest_sha256=proof.proof_manifest_sha256,
        created_at=proof.created_at,
    )


# ── Export Routes ───────────────────────────────────────────────────────────


@lifecycle_router.post(
    "/exports",
    response_model=ExportJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_export(
    tenant_id: UUID,
    payload: CreateExportRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    export_service: Annotated[ExportService, Depends(get_export_service)],
) -> ExportJobResponse:
    if tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied"
        )

    request_id = request.state.request_id
    try:
        job = export_service.create_export_job(
            principal=principal,
            tenant_context=tenant_context,
            scope=payload.scope,
            request_id=request_id,
        )
        return _to_job_response(job)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ExportProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@lifecycle_router.get(
    "/exports",
    response_model=list[ExportJobResponse],
)
def list_exports(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    export_service: Annotated[ExportService, Depends(get_export_service)],
) -> list[ExportJobResponse]:
    if tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied"
        )

    try:
        jobs = export_service.list_export_jobs(principal, tenant_context)
        return [_to_job_response(j) for j in jobs]
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@lifecycle_router.get(
    "/exports/{export_id}",
    response_model=ExportJobDetailResponse,
)
def get_export(
    tenant_id: UUID,
    export_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    export_service: Annotated[ExportService, Depends(get_export_service)],
) -> ExportJobDetailResponse:
    if tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied"
        )

    try:
        job = export_service.get_export_job(principal, tenant_context, export_id=export_id)
        return _to_job_detail_response(job)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ExportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@lifecycle_router.get(
    "/exports/{export_id}/download",
)
def download_export(
    tenant_id: UUID,
    export_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    export_service: Annotated[ExportService, Depends(get_export_service)],
) -> Response:
    if tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied"
        )

    request_id = request.state.request_id
    try:
        job, zip_bytes = export_service.download_export_archive(
            principal=principal,
            tenant_context=tenant_context,
            export_id=export_id,
            request_id=request_id,
        )
        filename = f"conformly-export-{export_id.hex[:8]}.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(zip_bytes)),
                "ETag": f'"{job.sha256_hash or export_id.hex}"',
            },
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ExportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExportExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except ExportProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ── Cancellation & Retention Routes ─────────────────────────────────────────


@lifecycle_router.get(
    "/cancellation",
    response_model=TenantCancellationResponse,
)
def get_cancellation(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    retention_service: Annotated[RetentionService, Depends(get_retention_service)],
) -> TenantCancellationResponse:
    if tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied"
        )

    try:
        status_dict = retention_service.get_cancellation_status(principal, tenant_context)
        return TenantCancellationResponse(
            status=status_dict["status"],
            cancellation_requested_at=datetime.fromisoformat(
                status_dict["cancellation_requested_at"]
            )
            if status_dict["cancellation_requested_at"]
            else None,
            export_until=datetime.fromisoformat(status_dict["export_until"])
            if status_dict["export_until"]
            else None,
            deletion_due_at=datetime.fromisoformat(status_dict["deletion_due_at"])
            if status_dict["deletion_due_at"]
            else None,
            days_remaining_in_export_window=status_dict["days_remaining_in_export_window"],
            is_export_window_active=status_dict["is_export_window_active"],
            legal_hold=status_dict["legal_hold"],
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except CancellationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@lifecycle_router.post(
    "/cancellation",
    response_model=TenantCancellationResponse,
)
def request_cancellation(
    tenant_id: UUID,
    payload: CancellationRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    retention_service: Annotated[RetentionService, Depends(get_retention_service)],
) -> TenantCancellationResponse:
    if tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied"
        )

    request_id = request.state.request_id
    try:
        tenant = retention_service.request_cancellation(
            principal=principal,
            tenant_context=tenant_context,
            reason=payload.reason,
            confirm_slug=payload.confirm_slug,
            request_id=request_id,
        )
        return TenantCancellationResponse(
            status=str(tenant.status),
            cancellation_requested_at=tenant.cancellation_requested_at,
            export_until=tenant.export_until,
            deletion_due_at=tenant.deletion_due_at,
            days_remaining_in_export_window=30,
            is_export_window_active=True,
            legal_hold=tenant.legal_hold,
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LegalHoldActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CancellationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@lifecycle_router.post(
    "/legal-hold",
    response_model=TenantCancellationResponse,
)
def set_legal_hold(
    tenant_id: UUID,
    payload: LegalHoldRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    retention_service: Annotated[RetentionService, Depends(get_retention_service)],
) -> TenantCancellationResponse:
    if tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied"
        )

    request_id = request.state.request_id
    try:
        retention_service.set_legal_hold(
            principal=principal,
            tenant_context=tenant_context,
            enabled=payload.enabled,
            reason=payload.reason,
            request_id=request_id,
        )
        current_status = retention_service.get_cancellation_status(principal, tenant_context)
        return TenantCancellationResponse.model_validate(current_status)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except CancellationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@lifecycle_router.get(
    "/deletion-proofs",
    response_model=list[DeletionProofResponse],
)
def list_deletion_proofs(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    retention_service: Annotated[RetentionService, Depends(get_retention_service)],
) -> list[DeletionProofResponse]:
    if tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied"
        )

    try:
        proofs = retention_service.list_deletion_proofs(principal, tenant_context)
        return [_to_proof_response(p) for p in proofs]
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@lifecycle_router.post(
    "/deletion-jobs/{job_id}/execute",
    response_model=DeletionProofResponse,
)
def execute_deletion_job(
    tenant_id: UUID,
    job_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    retention_service: Annotated[RetentionService, Depends(get_retention_service)],
) -> DeletionProofResponse:
    if tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied"
        )

    request_id = request.state.request_id
    try:
        proof = retention_service.execute_deletion_job(
            job_id=job_id,
            operator_principal=principal,
            tenant_context=tenant_context,
            request_id=request_id,
        )
        return _to_proof_response(proof)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LegalHoldActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (CancellationError, DeletionJobNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
