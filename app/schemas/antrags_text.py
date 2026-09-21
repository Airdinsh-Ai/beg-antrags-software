import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TextGenerateRequest(BaseModel):
    measure_id: uuid.UUID


class TextGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    measure_id: uuid.UUID
    massnahmenbeschreibung_entwurf: str
    energetischer_mehrwert_entwurf: str
    freigegeben: bool


class TextReviewRequest(BaseModel):
    measure_id: uuid.UUID
    # Reviewer reicht die (ggf. bearbeitete) Endfassung ein - kein separates
    # "approve"-Flag ohne Text, damit kein formales Abnicken moeglich ist
    # (DSGVO Art. 22, Gesamtkonzept Modul 4).
    massnahmenbeschreibung: str
    energetischer_mehrwert: str


class AntragsTextOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    measure_id: uuid.UUID
    massnahmenbeschreibung_final: str | None
    energetischer_mehrwert_final: str | None
    freigegeben: bool
    reviewed_by_id: uuid.UUID | None
    reviewed_at: datetime | None
