import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.db import get_db
from app.models.document import DocumentTyp, RetentionClass
from app.models.user import User, UserRole
from app.modules.documents import service
from app.schemas.documents import DocumentOut, EnergieausweisExtraktResponse

router = APIRouter(tags=["documents"])


@router.post("/cases/{case_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document_endpoint(
    case_id: uuid.UUID,
    typ: DocumentTyp = Form(...),
    retention_class: RetentionClass = Form(...),
    datei: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> DocumentOut:
    inhalt = await datei.read()
    document = service.upload_document(
        db,
        case_id,
        current_user,
        typ=typ,
        retention_class=retention_class,
        dateiname=datei.filename or "unbenannt",
        inhalt=inhalt,
    )
    return DocumentOut.model_validate(document)


@router.post("/cases/{case_id}/extract", response_model=EnergieausweisExtraktResponse)
def extract_energieausweis_endpoint(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> EnergieausweisExtraktResponse:
    result = service.extract_energieausweis_for_case(db, case_id, current_user)
    return EnergieausweisExtraktResponse(**result)
