import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentTyp, RetentionClass


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    typ: DocumentTyp
    retention_class: RetentionClass
    dateiname: str | None
    created_at: datetime


class EnergieausweisExtraktResponse(BaseModel):
    baujahr: int | None
    wohneinheiten: int | None
    energieverbrauch_kwh_pro_m2a: float | None
    energieeffizienzklasse: str | None
