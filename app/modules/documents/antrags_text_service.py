import io
import uuid
from xml.sax.saxutils import escape

from fastapi import HTTPException, status
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
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


def export_text_pdf_for_measure(
    db: Session, case_id: uuid.UUID, measure_id: uuid.UUID, current_user: User
) -> bytes:
    """PDF-Beleg fuer die eigene Akte (Gesamtkonzept Modul 4: "Ausgabe als
    Copy-Paste-Text plus PDF-Beleg") - nur fuer bereits freigegebene Texte,
    dieselbe 404/409-Pruefung wie beim JSON-Export."""
    measure = _get_measure(db, case_id, measure_id, current_user)
    eintrag = export_text_for_measure(db, case_id, measure_id, current_user)

    styles = getSampleStyleSheet()
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"], fontSize=9, textColor="#555555")

    reviewed_by = f" von {eintrag.reviewed_by.email}" if eintrag.reviewed_by else ""
    reviewed_at = eintrag.reviewed_at.strftime("%d.%m.%Y %H:%M") if eintrag.reviewed_at else "-"

    story = [
        Paragraph("BEG-Antrag &ndash; Freitextfelder", styles["Heading1"]),
        Paragraph(f"Gebäude: {escape(measure.case.building.adresse)}", meta_style),
        Paragraph(f"Maßnahme: {escape(measure.typ.value)}", meta_style),
        Paragraph(f"Freigegeben am {reviewed_at} Uhr{escape(reviewed_by)}", meta_style),
        Spacer(1, 1 * cm),
        Paragraph("Maßnahmenbeschreibung", styles["Heading2"]),
        Paragraph(escape(eintrag.massnahmenbeschreibung_final or ""), styles["BodyText"]),
        Spacer(1, 0.6 * cm),
        Paragraph("Energetischer Mehrwert", styles["Heading2"]),
        Paragraph(escape(eintrag.energetischer_mehrwert_final or ""), styles["BodyText"]),
    ]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm
    )
    doc.build(story)
    return buffer.getvalue()
