import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.measure import MeasureTyp

# Nur diese beiden Typen haben in Phase 0 eine automatisierte Machbarkeitspruefung
# (JAZ >= 3,0). Alle anderen Katalog-Typen sind waehlbar, werden aber ohne
# automatisierte Pruefung gespeichert (siehe app/models/measure.py).
TYPEN_MIT_JAZ_PRUEFUNG = (MeasureTyp.WAERMEPUMPE_LUFT, MeasureTyp.WAERMEPUMPE_ERDWAERME)


class MeasureCatalogEntry(BaseModel):
    typ: MeasureTyp
    bezeichnung: str
    machbarkeitspruefung_automatisiert: bool


class MeasureCreateRequest(BaseModel):
    typ: MeasureTyp
    jaz: Decimal | None = None


class MeasureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    typ: MeasureTyp
    jaz: Decimal | None
    machbar: bool | None
    hinweis: str | None
    created_at: datetime
