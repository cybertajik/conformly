"""Unmounted report download router; integrate only with customer demo admission."""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.customer_demo.api import CustomerDemoRoute
from conformly.customer_demo.assessment_report import (
    CustomerAssessmentReportService,
    ReportSnapshotError,
)
from conformly.customer_demo.assessment_report_archive import ReportArchiveError, package_report
from conformly.db.session import get_db

report_router = APIRouter(
    prefix="/v2/tenants/{tenant_id}/customer-demo/assessment-reports",
    tags=["customer-demo-assessment-reports"],
    route_class=CustomerDemoRoute,
)


class ReportDownloadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adoption_id: UUID
    expected_answer_revision: int = Field(gt=0, strict=True)
    expected_selection_revision: int = Field(gt=0, strict=True)


@report_router.post("/download", response_class=Response)
def download_assessment_report(
    tenant_id: UUID,
    body: ReportDownloadRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Prepare a private operational ZIP and commit its audit before releasing bytes.

    Requires the existing customer-demo error handlers when mounted. This module
    does not register itself in the application or grant any new capabilities.
    """
    if tenant_id != tenant_context.tenant_id:
        raise HTTPException(status_code=403, detail="Customer demo access denied")
    request_id = getattr(request.state, "request_id", None)
    if not isinstance(request_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", request_id):
        request_id = str(uuid4())
    try:
        bundle = CustomerAssessmentReportService(db).generate(
            principal=principal,
            tenant_context=tenant_context,
            adoption_id=body.adoption_id,
        )
        archive = package_report(bundle, tenant_id=tenant_id, adoption_id=body.adoption_id)
        if (
            archive.answer_revision != body.expected_answer_revision
            or archive.selection_revision != body.expected_selection_revision
        ):
            raise ReportSnapshotError("Report revision changed")
        record_audit_event(
            db,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_assessment.report_download_prepared",
            resource_type="customer_assessment_report",
            resource_id=str(body.adoption_id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "adoption_id": str(body.adoption_id),
                "report_type": "synthetic_operational_snapshot",
                "sha256": archive.sha256,
                "manifest_hash": archive.manifest_sha256,
                "size_bytes": len(archive.content),
                "files_count": 3,
            },
        )
        # Do not rely on request dependency teardown: it may execute after the
        # response is sent. A failed audit commit must not release report bytes.
        db.commit()
    except ReportSnapshotError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflict: Report scope changed or is unavailable; refresh before retry",
        ) from exc
    except AuthorizationDeniedError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail="Customer demo access denied") from exc
    except (ReportArchiveError, SQLAlchemyError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Report download unavailable") from exc
    except Exception:
        db.rollback()
        raise
    return Response(
        archive.content,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="conformly-assessment-report.zip"',
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; sandbox",
            "Referrer-Policy": "no-referrer",
            "X-Report-Tenant-ID": str(tenant_id),
            "X-Report-Adoption-ID": str(body.adoption_id),
            "X-Report-Answer-Revision": str(archive.answer_revision),
            "X-Report-Selection-Revision": str(archive.selection_revision),
            "X-Report-SHA256": archive.sha256,
            "X-Correlation-ID": request_id,
        },
    )
