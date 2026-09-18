import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.db import get_db
from app.models.user import User, UserRole
from app.modules.property import service
from app.schemas.property import (
    CaseCreateRequest,
    CaseOut,
    PropertyCreateRequest,
    PropertyCreateResponse,
)

router = APIRouter(tags=["property"])


@router.post("/property", response_model=PropertyCreateResponse, status_code=201)
def create_property_endpoint(
    payload: PropertyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> PropertyCreateResponse:
    person, building, ownership = service.create_property(db, payload)
    return PropertyCreateResponse(
        person_id=person.id, building_id=building.id, ownership_id=ownership.id
    )


@router.post("/cases", response_model=CaseOut, status_code=201)
def create_case_endpoint(
    payload: CaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> CaseOut:
    case = service.create_case(db, payload, current_user)
    return CaseOut.model_validate(case)


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_case_endpoint(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseOut:
    case = service.get_case(db, case_id, current_user)
    return CaseOut.model_validate(case)
