import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.db import get_db
from app.models.user import User, UserRole
from app.modules.measures import service
from app.schemas.measures import MeasureCatalogEntry, MeasureCreateRequest, MeasureOut

router = APIRouter(tags=["measures"])


@router.get("/measures/catalog", response_model=list[MeasureCatalogEntry])
def get_catalog_endpoint(
    current_user: User = Depends(get_current_user),
) -> list[MeasureCatalogEntry]:
    return list(service.CATALOG)


@router.post("/cases/{case_id}/measures", response_model=MeasureOut, status_code=201)
def create_measure_endpoint(
    case_id: uuid.UUID,
    payload: MeasureCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> MeasureOut:
    measure = service.create_measure(db, case_id, current_user, payload)
    return MeasureOut.model_validate(measure)
