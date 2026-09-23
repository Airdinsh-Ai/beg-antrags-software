import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.measure import Measure, MeasureTyp
from app.models.user import User
from app.modules.property.service import get_case
from app.schemas.measures import (
    TYPEN_MIT_JAZ_PRUEFUNG,
    WAERMEERZEUGER_TYPEN,
    MeasureCatalogEntry,
    MeasureCreateRequest,
)

JAZ_MINDESTWERT = Decimal("3.0")

CATALOG: tuple[MeasureCatalogEntry, ...] = (
    MeasureCatalogEntry(typ=MeasureTyp.DAEMMUNG, bezeichnung="Dämmung", machbarkeitspruefung_automatisiert=False),
    MeasureCatalogEntry(typ=MeasureTyp.FENSTER, bezeichnung="Fenster", machbarkeitspruefung_automatisiert=False),
    MeasureCatalogEntry(
        typ=MeasureTyp.WAERMEPUMPE_LUFT,
        bezeichnung="Wärmepumpe (Luft)",
        machbarkeitspruefung_automatisiert=True,
    ),
    MeasureCatalogEntry(
        typ=MeasureTyp.WAERMEPUMPE_ERDWAERME,
        bezeichnung="Wärmepumpe (Erdwärme)",
        machbarkeitspruefung_automatisiert=True,
    ),
    MeasureCatalogEntry(
        typ=MeasureTyp.PV_SPEICHER, bezeichnung="PV + Speicher", machbarkeitspruefung_automatisiert=False
    ),
    MeasureCatalogEntry(typ=MeasureTyp.LUEFTUNG, bezeichnung="Lüftung", machbarkeitspruefung_automatisiert=False),
    MeasureCatalogEntry(
        typ=MeasureTyp.BAUBEGLEITUNG, bezeichnung="Baubegleitung", machbarkeitspruefung_automatisiert=False
    ),
)


def _check_feasibility(typ: MeasureTyp, jaz: Decimal | None) -> tuple[bool | None, str]:
    """Technische Mindeststandard-Pruefung (Gesamtkonzept, Modul 2). Nur fuer
    Waermepumpen automatisiert - JAZ >= 3,0 nach VDI 4650, Stand 09/2026 belegt.
    Alle anderen Typen: Grenzwerte laut eigener Doku noch nicht einzeln
    verifiziert, daher bewusst kein automatisiertes Ergebnis (None statt
    geraten)."""
    if typ not in TYPEN_MIT_JAZ_PRUEFUNG:
        return None, "Machbarkeitspruefung fuer diesen Maßnahmentyp ist in Phase 0 noch nicht automatisiert."

    if jaz is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Fuer Waermepumpen ist die Jahresarbeitszahl (jaz) fuer die Machbarkeitspruefung erforderlich.",
        )

    machbar = jaz >= JAZ_MINDESTWERT
    hinweis = (
        f"JAZ {jaz} erfuellt die Mindestanforderung von {JAZ_MINDESTWERT} (VDI 4650)."
        if machbar
        else f"JAZ {jaz} unterschreitet die Mindestanforderung von {JAZ_MINDESTWERT} (VDI 4650) - Foerderverlust droht."
    )
    return machbar, hinweis


def _check_altheizung_nur_bei_waermeerzeugern(payload: MeasureCreateRequest) -> None:
    angaben = (
        payload.alte_heizung_art,
        payload.alte_heizung_inbetriebnahme,
        payload.alte_heizung_funktionstuechtig,
    )
    if payload.typ not in WAERMEERZEUGER_TYPEN and any(a is not None for a in angaben):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Angaben zur Altheizung (alte_heizung_*) sind nur bei Waermeerzeugern "
                f"zulaessig, nicht bei '{payload.typ.value}'."
            ),
        )


def create_measure(
    db: Session,
    case_id: uuid.UUID,
    current_user: User,
    payload: MeasureCreateRequest,
) -> Measure:
    case = get_case(db, case_id, current_user)
    _check_altheizung_nur_bei_waermeerzeugern(payload)
    machbar, hinweis = _check_feasibility(payload.typ, payload.jaz)

    measure = Measure(
        case_id=case.id,
        typ=payload.typ,
        jaz=payload.jaz,
        machbar=machbar,
        hinweis=hinweis,
        alte_heizung_art=payload.alte_heizung_art,
        alte_heizung_inbetriebnahme=payload.alte_heizung_inbetriebnahme,
        alte_heizung_funktionstuechtig=payload.alte_heizung_funktionstuechtig,
    )
    db.add(measure)
    db.commit()
    db.refresh(measure)
    return measure
