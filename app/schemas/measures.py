import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.measure import AltheizungArt, MeasureTyp

# Nur diese beiden Typen haben in Phase 0 eine automatisierte Machbarkeitspruefung
# (JAZ >= 3,0). Alle anderen Katalog-Typen sind waehlbar, werden aber ohne
# automatisierte Pruefung gespeichert (siehe app/models/measure.py).
TYPEN_MIT_JAZ_PRUEFUNG = (MeasureTyp.WAERMEPUMPE_LUFT, MeasureTyp.WAERMEPUMPE_ERDWAERME)

# Technische Eigenschaft des Katalogtyps (erzeugt Waerme, ersetzt eine Altheizung) -
# nur diese Typen duerfen Angaben zur Altheizung tragen. Welches FOERDERPROGRAMM
# einen Typ foerdert, ist Regelwerk und steht in app/rules/*.yaml
# (zulaessige_massnahmen), nicht hier.
WAERMEERZEUGER_TYPEN = (MeasureTyp.WAERMEPUMPE_LUFT, MeasureTyp.WAERMEPUMPE_ERDWAERME)


class MeasureCatalogEntry(BaseModel):
    typ: MeasureTyp
    bezeichnung: str
    machbarkeitspruefung_automatisiert: bool


class MeasureCreateRequest(BaseModel):
    typ: MeasureTyp
    jaz: Decimal | None = None
    alte_heizung_art: AltheizungArt | None = None
    alte_heizung_inbetriebnahme: date | None = None
    alte_heizung_funktionstuechtig: bool | None = None


class MeasureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    typ: MeasureTyp
    jaz: Decimal | None
    machbar: bool | None
    hinweis: str | None
    alte_heizung_art: AltheizungArt | None
    alte_heizung_inbetriebnahme: date | None
    alte_heizung_funktionstuechtig: bool | None
    created_at: datetime
