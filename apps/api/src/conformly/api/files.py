from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.db.session import get_db
from conformly.storage.models import StoredFile
from conformly.storage.providers import StorageError
from conformly.storage.service import (
    FileQuarantinedError,
    StorageFileNotFoundError,
    StorageIntegrityError,
    StorageService,
    get_storage_service,
)
from conformly.storage.validation import FileValidationError

router = APIRouter(prefix="/v1/tenants/{tenant_id}/files", tags=["files"])


class StoredFileResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    created_by_user_id: UUID
    original_filename: str
    content_type: str
    classification: str
    plaintext_size_bytes: int
    plaintext_sha256: str
    created_at: datetime


def _to_response(file: StoredFile) -> StoredFileResponse:
    return StoredFileResponse(
        id=file.id,
        tenant_id=file.tenant_id,
        created_by_user_id=file.created_by_user_id,
        original_filename=file.original_filename,
        content_type=file.content_type,
        classification=file.classification,
        plaintext_size_bytes=file.plaintext_size_bytes,
        plaintext_sha256=file.plaintext_sha256,
        created_at=file.created_at,
    )


@router.post("", response_model=StoredFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    database: Annotated[Session, Depends(get_db)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    file: Annotated[UploadFile, File(...)],
    classification: Annotated[str, Form()] = "Restricted",
) -> StoredFileResponse:
    if tenant_context.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant mismatch")

    content = await file.read(storage_service.max_file_size + 1)
    if len(content) > storage_service.max_file_size:
        raise HTTPException(status_code=413, detail="File exceeds upload limit")
    request_id = getattr(request.state, "request_id", "unknown")

    try:
        stored = storage_service.upload_file(
            principal,
            tenant_context,
            filename=file.filename or "upload.bin",
            content=content,
            classification=classification,
            content_type=file.content_type,
            request_id=request_id,
        )
        database.commit()
        return _to_response(stored)
    except AuthorizationDeniedError as err:
        database.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="file write capability denied"
        ) from err
    except FileQuarantinedError as err:
        database.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malware detected; file quarantined: {err}",
        ) from err
    except FileValidationError as err:
        database.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except Exception as err:
        from conformly.entitlements.service import StorageQuotaExceededError

        if isinstance(err, StorageQuotaExceededError):
            database.rollback()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
        raise


@router.get("", response_model=list[StoredFileResponse])
def list_files(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
) -> list[StoredFileResponse]:
    if tenant_context.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant mismatch")

    try:
        files = storage_service.list_files(principal, tenant_context)
        return [_to_response(f) for f in files]
    except AuthorizationDeniedError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="file read capability denied"
        ) from err


@router.get("/{file_id}", response_model=StoredFileResponse)
def get_file_metadata(
    tenant_id: UUID,
    file_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
) -> StoredFileResponse:
    if tenant_context.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant mismatch")

    try:
        file = storage_service.get_file_metadata(principal, tenant_context, file_id=file_id)
        return _to_response(file)
    except AuthorizationDeniedError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="file read capability denied"
        ) from err
    except StorageFileNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found") from err


@router.get("/{file_id}/download")
def download_file(
    tenant_id: UUID,
    file_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    database: Annotated[Session, Depends(get_db)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
) -> Response:
    if tenant_context.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant mismatch")

    request_id = getattr(request.state, "request_id", "unknown")

    try:
        file, plaintext = storage_service.download_file(
            principal, tenant_context, file_id=file_id, request_id=request_id
        )
        database.commit()
        safe_filename = (
            file.original_filename.replace("\\", "_")
            .replace('"', "_")
            .replace("\r", "")
            .replace("\n", "")
        )
        return Response(
            content=plaintext,
            media_type=file.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )
    except AuthorizationDeniedError as err:
        database.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="file read capability denied"
        ) from err
    except StorageFileNotFoundError as err:
        database.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found") from err
    except StorageIntegrityError as err:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stored file integrity check failed",
        ) from err


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    tenant_id: UUID,
    file_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    database: Annotated[Session, Depends(get_db)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
) -> Response:
    if tenant_context.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant mismatch")

    request_id = getattr(request.state, "request_id", "unknown")

    try:
        storage_service.delete_file(
            principal, tenant_context, file_id=file_id, request_id=request_id
        )
        database.commit()
        try:
            storage_service.finalize_pending_deletions(
                principal, tenant_context, file_id=file_id, request_id=request_id
            )
            database.commit()
        except (OSError, StorageError):
            database.rollback()
            return Response(status_code=status.HTTP_202_ACCEPTED)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AuthorizationDeniedError as err:
        database.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="file delete capability denied"
        ) from err
    except StorageFileNotFoundError as err:
        database.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found") from err
