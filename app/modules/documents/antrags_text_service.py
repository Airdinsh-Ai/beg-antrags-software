import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.llm.client import (
    FallDatenFuerAntragstext,
    LLMAufrufFehler,
    LLMValidierungsFehler,
    generate_antragstexte,
)
from app.models.antrags_text import AntragsText
from app.models.funding import CaseFunding
from app.models.measure import Measure
from app.models.user import User
from app.modules.property.service import get_case


def _get_measure(db: Session, case_id: uuid.UUID, measure_id: uuid.UUID, current_user: User) -> Measure:
    case = get_case(db, case_id, current_user)
    measure = (
        db.query(Measure).filter(Measure.id == measure_id, Measure.case_id == case.id).one_or_none()
    )
    if measure is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Maßnahme nicht in diesem Fall gefunden."
        )
    return measure


def generate_text_for_measure(
    db: Session, case_id: uuid.UUID, measure_id: uuid.UUID, current_user: User
) -> AntragsText:
    """Erzeugt einen neuen LLM-Entwurf (Gesamtkonzept Modul 4) - upsertbar wie
    case_funding: eine Neugenerierung ersetzt den bisherigen Entwurf und setzt
    eine vorherige Freigabe zurueck, da der Text sich geaendert hat."""
    measure = _get_measure(db, case_id, measure_id, current_user)

    foerderprogramm = (
        db.query(CaseFunding.programm)
        .filter(CaseFunding.measure_id == measure.id)
        .order_by(CaseFunding.berechnet_am.desc())
        .limit(1)
        .scalar()
    )

    fall = FallDatenFuerAntragstext(
        adresse=measure.case.building.adresse,
        baujahr=measure.case.building.baujahr,
        wohneinheiten=measure.case.building.wohneinheiten,
        massnahme_typ=measure.typ.value,
        foerderprogramm=foerderprogramm.value if foerderprogramm else None,
        jaz=float(measure.jaz) if measure.jaz is not None else None,
    )

    try:
        texte = generate_antragstexte(fall)
    except LLMValidierungsFehler as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except LLMAufrufFehler as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    eintrag = db.query(AntragsText).filter(AntragsText.measure_id == measure.id).one_or_none()
    if eintrag is None:
        eintrag = AntragsText(measure_id=measure.id)
        db.add(eintrag)

    eintrag.massnahmenbeschreibung_entwurf = texte.massnahmenbeschreibung
    eintrag.energetischer_mehrwert_entwurf = texte.energetischer_mehrwert
    eintrag.erstellt_am = utcnow()
    # Neuer Entwurf entwertet eine vorherige Freigabe - Pflicht-Review gilt
    # fuer die aktuelle Fassung, nicht rueckwirkend fuer eine alte.
    eintrag.freigegeben = False
    eintrag.massnahmenbeschreibung_final = None
    eintrag.energetischer_mehrwert_final = None
    eintrag.reviewed_by_id = None
    eintrag.reviewed_at = None

    db.commit()
    db.refresh(eintrag)
    return eintrag


def review_text_for_measure(
    db: Session,
    case_id: uuid.UUID,
    measure_id: uuid.UUID,
    current_user: User,
    massnahmenbeschreibung: str,
    energetischer_mehrwert: str,
) -> AntragsText:
    """Pflicht-Review vor Freigabe (Gesamtkonzept Modul 4, DSGVO Art. 22) -
    die reviewende Person reicht die (ggf. bearbeitete) Endfassung aktiv ein,
    kein formales Abnicken eines bestehenden Entwurfs ohne Textpruefung."""
    _get_measure(db, case_id, measure_id, current_user)

    eintrag = db.query(AntragsText).filter(AntragsText.measure_id == measure_id).one_or_none()
    if eintrag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noch kein Textentwurf fuer diese Maßnahme - zuerst generieren.",
        )

    eintrag.massnahmenbeschreibung_final = massnahmenbeschreibung
    eintrag.energetischer_mehrwert_final = energetischer_mehrwert
    eintrag.freigegeben = True
    eintrag.reviewed_by_id = current_user.id
    eintrag.reviewed_at = utcnow()

    db.commit()
    db.refresh(eintrag)
    return eintrag


def export_text_for_measure(
    db: Session, case_id: uuid.UUID, measure_id: uuid.UUID, current_user: User
) -> AntragsText:
    _get_measure(db, case_id, measure_id, current_user)

    eintrag = db.query(AntragsText).filter(AntragsText.measure_id == measure_id).one_or_none()
    if eintrag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kein Textentwurf vorhanden.")
    if not eintrag.freigegeben:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Text ist noch nicht freigegeben - Pflicht-Review steht aus.",
        )
    return eintrag
