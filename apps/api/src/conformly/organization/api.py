from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.db.session import get_db
from conformly.organization import service

router = APIRouter(prefix="/v1/tenants/{tenant_id}/organization", tags=["organization"])


class LegalEntityCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    registration_number: str | None = Field(default=None, max_length=100)
    country: str = Field(default="DE", min_length=2, max_length=2)
    is_primary: bool = Field(default=False)


class LegalEntityResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    registration_number: str | None
    country: str
    is_primary: bool


class BusinessUnitCreateRequest(BaseModel):
    legal_entity_id: UUID
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)


class BusinessUnitResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    legal_entity_id: UUID
    name: str
    code: str | None


class LocationCreateRequest(BaseModel):
    legal_entity_id: UUID
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(default="DE", min_length=2, max_length=2)
    city: str = Field(min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=300)


class LocationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    legal_entity_id: UUID
    name: str
    country: str
    city: str
    address: str | None


@router.get("/legal-entities", response_model=list[LegalEntityResponse])
def list_legal_entities_endpoint(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> list[LegalEntityResponse]:
    request_id = getattr(request.state, "request_id", "req-org-list")
    try:
        entities = service.list_legal_entities(database, principal, tenant_context, request_id)
        return [
            LegalEntityResponse(
                id=e.id,
                tenant_id=e.tenant_id,
                name=e.name,
                registration_number=e.registration_number,
                country=e.country,
                is_primary=e.is_primary,
            )
            for e in entities
        ]
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing organization:read capability"
        )


@router.post("/legal-entities", response_model=LegalEntityResponse, status_code=status.HTTP_201_CREATED)
def create_legal_entity_endpoint(
    payload: LegalEntityCreateRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> LegalEntityResponse:
    request_id = getattr(request.state, "request_id", "req-org-create")
    try:
        entity = service.create_legal_entity(
            database,
            principal,
            tenant_context,
            name=payload.name,
            registration_number=payload.registration_number,
            country=payload.country,
            is_primary=payload.is_primary,
            request_id=request_id,
        )
        database.commit()
        return LegalEntityResponse(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            registration_number=entity.registration_number,
            country=entity.country,
            is_primary=entity.is_primary,
        )
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing organization:manage capability"
        )


@router.get("/business-units", response_model=list[BusinessUnitResponse])
def list_business_units_endpoint(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    legal_entity_id: UUID | None = None,
) -> list[BusinessUnitResponse]:
    request_id = getattr(request.state, "request_id", "req-bu-list")
    try:
        units = service.list_business_units(
            database, principal, tenant_context, request_id, legal_entity_id=legal_entity_id
        )
        return [
            BusinessUnitResponse(
                id=u.id,
                tenant_id=u.tenant_id,
                legal_entity_id=u.legal_entity_id,
                name=u.name,
                code=u.code,
            )
            for u in units
        ]
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing organization:read capability"
        )


@router.post("/business-units", response_model=BusinessUnitResponse, status_code=status.HTTP_201_CREATED)
def create_business_unit_endpoint(
    payload: BusinessUnitCreateRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> BusinessUnitResponse:
    request_id = getattr(request.state, "request_id", "req-bu-create")
    try:
        unit = service.create_business_unit(
            database,
            principal,
            tenant_context,
            legal_entity_id=payload.legal_entity_id,
            name=payload.name,
            code=payload.code,
            request_id=request_id,
        )
        database.commit()
        return BusinessUnitResponse(
            id=unit.id,
            tenant_id=unit.tenant_id,
            legal_entity_id=unit.legal_entity_id,
            name=unit.name,
            code=unit.code,
        )
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing organization:manage capability"
        )
    except service.OrganizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/locations", response_model=list[LocationResponse])
def list_locations_endpoint(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    legal_entity_id: UUID | None = None,
) -> list[LocationResponse]:
    request_id = getattr(request.state, "request_id", "req-loc-list")
    try:
        locations = service.list_locations(
            database, principal, tenant_context, request_id, legal_entity_id=legal_entity_id
        )
        return [
            LocationResponse(
                id=loc.id,
                tenant_id=loc.tenant_id,
                legal_entity_id=loc.legal_entity_id,
                name=loc.name,
                country=loc.country,
                city=loc.city,
                address=loc.address,
            )
            for loc in locations
        ]
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing organization:read capability"
        )


@router.post("/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
def create_location_endpoint(
    payload: LocationCreateRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> LocationResponse:
    request_id = getattr(request.state, "request_id", "req-loc-create")
    try:
        location = service.create_location(
            database,
            principal,
            tenant_context,
            legal_entity_id=payload.legal_entity_id,
            name=payload.name,
            country=payload.country,
            city=payload.city,
            address=payload.address,
            request_id=request_id,
        )
        database.commit()
        return LocationResponse(
            id=location.id,
            tenant_id=location.tenant_id,
            legal_entity_id=location.legal_entity_id,
            name=location.name,
            country=location.country,
            city=location.city,
            address=location.address,
        )
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing organization:manage capability"
        )
    except service.OrganizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
