"""FastAPI routes for pre-audit readiness assessments.

All endpoints are tenant-scoped and capability-guarded.
Wording deliberately uses 'readiness assessment' / 'pre-audit readiness' —
never accredited-certification language.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.compliance.models import FindingSeverity, RemediationStatus
from conformly.db.session import get_db
from conformly.entitlements.dependencies import require_module
from conformly.preaudit.service import (
    CertificateIssuanceBlockedError,
    CertificateNotFoundError,
    InvalidAdoptionReferenceError,
    InvalidPreAuditTransitionError,
    PreAuditFindingNotFoundError,
    PreAuditNotFoundError,
    PreAuditOptimisticLockError,
    PreAuditService,
    ReviewerConflictError,
)

preaudit_router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/pre-audits",
    tags=["pre_audit"],
    dependencies=[Depends(require_module("preaudit"))],
)


def get_preaudit_service(
    database: Annotated[Session, Depends(get_db)],
) -> PreAuditService:
    return PreAuditService(database)


# ── Pydantic schemas ──────────────────────────────────────────────────────


class PreAuditScopeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    pre_audit_id: UUID
    framework_version_id: UUID
    control_count: int
    checked_count: int
    created_at: datetime


class PreAuditCheckResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    scope_id: UUID
    control_type: str
    control_id: UUID
    result: str
    rule_version: str
    evidence_count: int
    policy_count: int
    open_findings_count: int
    implementation_status: str | None = None
    score: float
    evaluated_at: datetime | None = None
    created_at: datetime


class PreAuditFindingResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    pre_audit_id: UUID
    check_id: UUID | None = None
    title: str
    description: str
    severity: str
    recommendation: str | None = None
    remediation_status: str
    version: int
    created_at: datetime
    updated_at: datetime


class PreAuditReportResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    pre_audit_id: UUID
    file_id: UUID
    report_type: str
    rule_version: str
    generated_at: datetime
    created_at: datetime


class PreAuditManifestResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    pre_audit_id: UUID
    file_id: UUID
    manifest_hash_sha256: str
    record_count: int
    rule_version: str
    generated_at: datetime
    created_at: datetime


class PreAuditCertificateResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    pre_audit_id: UUID
    certificate_number: str
    status: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    revoked_reason: str | None = None
    created_at: datetime


class ReadinessScoreResponse(BaseModel):
    overall_score: float
    total_checks: int
    passed_checks: int
    failed_checks: int
    not_applicable_checks: int
    pending_checks: int
    open_findings: int


class PreAuditResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    description: str
    status: str
    framework_adoption_id: UUID
    lead_user_id: UUID
    reviewer_user_id: UUID | None = None
    reviewed_at: datetime | None = None
    rule_version: str
    overall_score: float | None = None
    version: int
    scopes: list[PreAuditScopeResponse] | None = None
    checks: list[PreAuditCheckResponse] | None = None
    findings: list[PreAuditFindingResponse] | None = None
    reports: list[PreAuditReportResponse] | None = None
    certificates: list[PreAuditCertificateResponse] | None = None
    score_summary: ReadinessScoreResponse | None = None
    created_at: datetime
    updated_at: datetime


class CreatePreAuditRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)
    framework_adoption_id: UUID
    lead_user_id: UUID


class AddFindingRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=4000)
    severity: FindingSeverity = FindingSeverity.MEDIUM
    recommendation: str | None = Field(default=None, max_length=4000)
    check_id: UUID | None = None


class UpdateFindingRequest(BaseModel):
    expected_version: int
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    severity: FindingSeverity | None = None
    recommendation: str | None = Field(default=None, max_length=4000)
    remediation_status: RemediationStatus | None = None


class SubmitReviewRequest(BaseModel):
    reviewer_user_id: UUID
    expected_version: int


class CompleteReviewRequest(BaseModel):
    expected_version: int


class CancelRequest(BaseModel):
    expected_version: int


class GenerateReportRequest(BaseModel):
    file_id: UUID
    report_type: str = Field(default="readiness_summary", max_length=50)


class GenerateManifestRequest(BaseModel):
    file_id: UUID
    manifest_content: str


class IssueCertificateRequest(BaseModel):
    validity_days: int = Field(default=365, ge=1, le=1825)


class RevokeCertificateRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


# ── Serialisers ───────────────────────────────────────────────────────────


def _scope_response(s: object) -> PreAuditScopeResponse:
    return PreAuditScopeResponse(
        id=s.id,  # type: ignore[attr-defined]
        tenant_id=s.tenant_id,  # type: ignore[attr-defined]
        pre_audit_id=s.pre_audit_id,  # type: ignore[attr-defined]
        framework_version_id=s.framework_version_id,  # type: ignore[attr-defined]
        control_count=s.control_count,  # type: ignore[attr-defined]
        checked_count=s.checked_count,  # type: ignore[attr-defined]
        created_at=s.created_at,  # type: ignore[attr-defined]
    )


def _check_response(c: object) -> PreAuditCheckResponse:
    impl = c.implementation_status  # type: ignore[attr-defined]
    return PreAuditCheckResponse(
        id=c.id,  # type: ignore[attr-defined]
        tenant_id=c.tenant_id,  # type: ignore[attr-defined]
        scope_id=c.scope_id,  # type: ignore[attr-defined]
        control_type=str(c.control_type),  # type: ignore[attr-defined]
        control_id=c.control_id,  # type: ignore[attr-defined]
        result=str(c.result),  # type: ignore[attr-defined]
        rule_version=c.rule_version,  # type: ignore[attr-defined]
        evidence_count=c.evidence_count,  # type: ignore[attr-defined]
        policy_count=c.policy_count,  # type: ignore[attr-defined]
        open_findings_count=c.open_findings_count,  # type: ignore[attr-defined]
        implementation_status=str(impl) if impl else None,
        score=c.score,  # type: ignore[attr-defined]
        evaluated_at=c.evaluated_at,  # type: ignore[attr-defined]
        created_at=c.created_at,  # type: ignore[attr-defined]
    )


def _finding_response(f: object) -> PreAuditFindingResponse:
    return PreAuditFindingResponse(
        id=f.id,  # type: ignore[attr-defined]
        tenant_id=f.tenant_id,  # type: ignore[attr-defined]
        pre_audit_id=f.pre_audit_id,  # type: ignore[attr-defined]
        check_id=f.check_id,  # type: ignore[attr-defined]
        title=f.title,  # type: ignore[attr-defined]
        description=f.description,  # type: ignore[attr-defined]
        severity=str(f.severity),  # type: ignore[attr-defined]
        recommendation=f.recommendation,  # type: ignore[attr-defined]
        remediation_status=str(f.remediation_status),  # type: ignore[attr-defined]
        version=f.version,  # type: ignore[attr-defined]
        created_at=f.created_at,  # type: ignore[attr-defined]
        updated_at=f.updated_at,  # type: ignore[attr-defined]
    )


def _report_response(r: object) -> PreAuditReportResponse:
    return PreAuditReportResponse(
        id=r.id,  # type: ignore[attr-defined]
        tenant_id=r.tenant_id,  # type: ignore[attr-defined]
        pre_audit_id=r.pre_audit_id,  # type: ignore[attr-defined]
        file_id=r.file_id,  # type: ignore[attr-defined]
        report_type=r.report_type,  # type: ignore[attr-defined]
        rule_version=r.rule_version,  # type: ignore[attr-defined]
        generated_at=r.generated_at,  # type: ignore[attr-defined]
        created_at=r.created_at,  # type: ignore[attr-defined]
    )


def _manifest_response(m: object) -> PreAuditManifestResponse:
    return PreAuditManifestResponse(
        id=m.id,  # type: ignore[attr-defined]
        tenant_id=m.tenant_id,  # type: ignore[attr-defined]
        pre_audit_id=m.pre_audit_id,  # type: ignore[attr-defined]
        file_id=m.file_id,  # type: ignore[attr-defined]
        manifest_hash_sha256=m.manifest_hash_sha256,  # type: ignore[attr-defined]
        record_count=m.record_count,  # type: ignore[attr-defined]
        rule_version=m.rule_version,  # type: ignore[attr-defined]
        generated_at=m.generated_at,  # type: ignore[attr-defined]
        created_at=m.created_at,  # type: ignore[attr-defined]
    )


def _cert_response(c: object) -> PreAuditCertificateResponse:
    return PreAuditCertificateResponse(
        id=c.id,  # type: ignore[attr-defined]
        tenant_id=c.tenant_id,  # type: ignore[attr-defined]
        pre_audit_id=c.pre_audit_id,  # type: ignore[attr-defined]
        certificate_number=c.certificate_number,  # type: ignore[attr-defined]
        status=str(c.status),  # type: ignore[attr-defined]
        issued_at=c.issued_at,  # type: ignore[attr-defined]
        expires_at=c.expires_at,  # type: ignore[attr-defined]
        revoked_at=c.revoked_at,  # type: ignore[attr-defined]
        revoked_reason=c.revoked_reason,  # type: ignore[attr-defined]
        created_at=c.created_at,  # type: ignore[attr-defined]
    )


def _pa_response(pa: object, *, detail: bool = False) -> PreAuditResponse:
    from conformly.preaudit.service import PreAuditService

    scopes = None
    checks_all = None
    findings = None
    reports = None
    certs = None
    score_summary = None

    if detail:
        scopes_list = getattr(pa, "scopes", []) or []
        scopes = [_scope_response(s) for s in scopes_list]
        checks_all = []
        for s in scopes_list:
            for c in getattr(s, "checks", []) or []:
                checks_all.append(_check_response(c))
        findings = [_finding_response(f) for f in (getattr(pa, "findings", []) or [])]
        reports = [_report_response(r) for r in (getattr(pa, "reports", []) or [])]
        certs = [_cert_response(c) for c in (getattr(pa, "certificates", []) or [])]
        # Inline score summary
        svc = PreAuditService.__new__(PreAuditService)
        score_summary_dict = svc.compute_score_summary(pa)  # type: ignore[arg-type]
        score_summary = ReadinessScoreResponse(**score_summary_dict)

    return PreAuditResponse(
        id=pa.id,  # type: ignore[attr-defined]
        tenant_id=pa.tenant_id,  # type: ignore[attr-defined]
        title=pa.title,  # type: ignore[attr-defined]
        description=pa.description,  # type: ignore[attr-defined]
        status=str(pa.status),  # type: ignore[attr-defined]
        framework_adoption_id=pa.framework_adoption_id,  # type: ignore[attr-defined]
        lead_user_id=pa.lead_user_id,  # type: ignore[attr-defined]
        reviewer_user_id=pa.reviewer_user_id,  # type: ignore[attr-defined]
        reviewed_at=pa.reviewed_at,  # type: ignore[attr-defined]
        rule_version=pa.rule_version,  # type: ignore[attr-defined]
        overall_score=pa.overall_score,  # type: ignore[attr-defined]
        version=pa.version,  # type: ignore[attr-defined]
        scopes=scopes,
        checks=checks_all,
        findings=findings,
        reports=reports,
        certificates=certs,
        score_summary=score_summary,
        created_at=pa.created_at,  # type: ignore[attr-defined]
        updated_at=pa.updated_at,  # type: ignore[attr-defined]
    )


# ── Route handlers ────────────────────────────────────────────────────────


@preaudit_router.post(
    "/",
    response_model=PreAuditResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pre_audit(
    body: CreatePreAuditRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditResponse:
    try:
        pa = svc.create_pre_audit(
            principal,
            tenant_ctx,
            title=body.title,
            description=body.description,
            framework_adoption_id=body.framework_adoption_id,
            lead_user_id=body.lead_user_id,
        )
        return _pa_response(pa)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except InvalidAdoptionReferenceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@preaudit_router.get("/", response_model=list[PreAuditResponse])
def list_pre_audits(
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> list[PreAuditResponse]:
    try:
        items = svc.list_pre_audits(principal, tenant_ctx)
        return [_pa_response(pa) for pa in items]
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc


@preaudit_router.get("/{pre_audit_id}", response_model=PreAuditResponse)
def get_pre_audit(
    pre_audit_id: UUID,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditResponse:
    try:
        pa = svc.get_pre_audit(principal, tenant_ctx, pre_audit_id)
        return _pa_response(pa, detail=True)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except PreAuditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@preaudit_router.post("/{pre_audit_id}/run-checks", response_model=PreAuditResponse)
def run_checks(
    pre_audit_id: UUID,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditResponse:
    try:
        pa = svc.run_checks(principal, tenant_ctx, pre_audit_id)
        return _pa_response(pa, detail=True)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except PreAuditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except InvalidPreAuditTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@preaudit_router.post(
    "/{pre_audit_id}/findings",
    response_model=PreAuditFindingResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_finding(
    pre_audit_id: UUID,
    body: AddFindingRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditFindingResponse:
    try:
        f = svc.add_finding(
            principal,
            tenant_ctx,
            pre_audit_id,
            title=body.title,
            description=body.description,
            severity=body.severity,
            recommendation=body.recommendation,
            check_id=body.check_id,
        )
        return _finding_response(f)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except PreAuditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except InvalidPreAuditTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@preaudit_router.patch(
    "/{pre_audit_id}/findings/{finding_id}",
    response_model=PreAuditFindingResponse,
)
def update_finding(
    pre_audit_id: UUID,
    finding_id: UUID,
    body: UpdateFindingRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditFindingResponse:
    try:
        f = svc.update_finding(
            principal,
            tenant_ctx,
            pre_audit_id,
            finding_id,
            expected_version=body.expected_version,
            title=body.title,
            description=body.description,
            severity=body.severity,
            recommendation=body.recommendation,
            remediation_status=body.remediation_status,
        )
        return _finding_response(f)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except PreAuditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except PreAuditFindingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except PreAuditOptimisticLockError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@preaudit_router.post("/{pre_audit_id}/submit-review", response_model=PreAuditResponse)
def submit_review(
    pre_audit_id: UUID,
    body: SubmitReviewRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditResponse:
    try:
        pa = svc.submit_for_review(
            principal,
            tenant_ctx,
            pre_audit_id,
            reviewer_user_id=body.reviewer_user_id,
            expected_version=body.expected_version,
        )
        return _pa_response(pa)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except PreAuditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (
        InvalidPreAuditTransitionError,
        PreAuditOptimisticLockError,
        ReviewerConflictError,
    ) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except InvalidAdoptionReferenceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@preaudit_router.post("/{pre_audit_id}/complete-review", response_model=PreAuditResponse)
def complete_review(
    pre_audit_id: UUID,
    body: CompleteReviewRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditResponse:
    try:
        pa = svc.complete_review(
            principal,
            tenant_ctx,
            pre_audit_id,
            expected_version=body.expected_version,
        )
        return _pa_response(pa)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except PreAuditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (
        InvalidPreAuditTransitionError,
        PreAuditOptimisticLockError,
    ) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@preaudit_router.post("/{pre_audit_id}/cancel", response_model=PreAuditResponse)
def cancel_pre_audit(
    pre_audit_id: UUID,
    body: CancelRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditResponse:
    try:
        pa = svc.cancel_pre_audit(
            principal,
            tenant_ctx,
            pre_audit_id,
            expected_version=body.expected_version,
        )
        return _pa_response(pa)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except PreAuditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (
        InvalidPreAuditTransitionError,
        PreAuditOptimisticLockError,
    ) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@preaudit_router.post(
    "/{pre_audit_id}/generate-report",
    response_model=PreAuditReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_report(
    pre_audit_id: UUID,
    body: GenerateReportRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditReportResponse:
    try:
        r = svc.generate_report(
            principal,
            tenant_ctx,
            pre_audit_id,
            file_id=body.file_id,
            report_type=body.report_type,
        )
        return _report_response(r)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except PreAuditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@preaudit_router.post(
    "/{pre_audit_id}/generate-manifest",
    response_model=PreAuditManifestResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_manifest(
    pre_audit_id: UUID,
    body: GenerateManifestRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditManifestResponse:
    try:
        m = svc.generate_manifest(
            principal,
            tenant_ctx,
            pre_audit_id,
            file_id=body.file_id,
            manifest_content=body.manifest_content,
        )
        return _manifest_response(m)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except PreAuditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@preaudit_router.post(
    "/{pre_audit_id}/issue-certificate",
    response_model=PreAuditCertificateResponse,
    status_code=status.HTTP_201_CREATED,
)
def issue_certificate(
    pre_audit_id: UUID,
    body: IssueCertificateRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditCertificateResponse:
    try:
        cert = svc.issue_certificate(
            principal,
            tenant_ctx,
            pre_audit_id,
            validity_days=body.validity_days,
        )
        return _cert_response(cert)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except PreAuditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except CertificateIssuanceBlockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@preaudit_router.post(
    "/{pre_audit_id}/certificates/{certificate_id}/revoke",
    response_model=PreAuditCertificateResponse,
)
def revoke_certificate(
    pre_audit_id: UUID,
    certificate_id: UUID,
    body: RevokeCertificateRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[PreAuditService, Depends(get_preaudit_service)],
) -> PreAuditCertificateResponse:
    try:
        cert = svc.revoke_certificate(
            principal,
            tenant_ctx,
            pre_audit_id,
            certificate_id,
            reason=body.reason,
        )
        return _cert_response(cert)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except (PreAuditNotFoundError, CertificateNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except InvalidPreAuditTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
