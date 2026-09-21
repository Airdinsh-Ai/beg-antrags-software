import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.db import get_db
from app.models.document import DocumentTyp, RetentionClass
from app.models.user import User, UserRole
from app.modules.documents import antrags_text_service, service
from app.schemas.antrags_text import (
    AntragsTextOut,
    TextGenerateRequest,
    TextGenerateResponse,
    TextReviewRequest,
)
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


@router.post("/cases/{case_id}/texts/generate", response_model=TextGenerateResponse, status_code=201)
def generate_texts_endpoint(
    case_id: uuid.UUID,
    payload: TextGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> TextGenerateResponse:
    eintrag = antrags_text_service.generate_text_for_measure(
        db, case_id, payload.measure_id, current_user
    )
    return TextGenerateResponse.model_validate(eintrag)


@router.post("/cases/{case_id}/texts/review", response_model=AntragsTextOut)
def review_texts_endpoint(
    case_id: uuid.UUID,
    payload: TextReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> AntragsTextOut:
    eintrag = antrags_text_service.review_text_for_measure(
        db,
        case_id,
        payload.measure_id,
        current_user,
        massnahmenbeschreibung=payload.massnahmenbeschreibung,
        energetischer_mehrwert=payload.energetischer_mehrwert,
    )
    return AntragsTextOut.model_validate(eintrag)


@router.get("/cases/{case_id}/texts/export", response_model=AntragsTextOut)
def export_texts_endpoint(
    case_id: uuid.UUID,
    measure_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> AntragsTextOut:
    eintrag = antrags_text_service.export_text_for_measure(db, case_id, measure_id, current_user)
    return AntragsTextOut.model_validate(eintrag)


@router.get("/cases/{case_id}/texts/export/pdf")
def export_texts_pdf_endpoint(
    case_id: uuid.UUID,
    measure_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> Response:
    pdf_bytes = antrags_text_service.export_text_pdf_for_measure(db, case_id, measure_id, current_user)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="antragstext_{measure_id}.pdf"'},
    )
