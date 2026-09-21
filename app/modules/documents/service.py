import uuid
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.client import (
    LLMAufrufFehler,
    LLMValidierungsFehler,
    UnlesbaresPDFFehler,
    extract_energieausweis,
)
from app.models.document import Document, DocumentTyp, RetentionClass
from app.models.user import User
from app.modules.property.service import get_case


def upload_document(
    db: Session,
    case_id: uuid.UUID,
    current_user: User,
    typ: DocumentTyp,
    retention_class: RetentionClass,
    dateiname: str,
    inhalt: bytes,
) -> Document:
    """Speichert die Datei lokal (Phase 0 - kein Objektspeicher) und legt den
    Document-Datensatz an."""
    case = get_case(db, case_id, current_user)

    document_id = uuid.uuid4()
    zielordner = Path(settings.upload_verzeichnis) / str(case.id)
    zielordner.mkdir(parents=True, exist_ok=True)
    zielpfad = zielordner / f"{document_id}_{dateiname}"
    zielpfad.write_bytes(inhalt)

    document = Document(
        id=document_id,
        case_id=case.id,
        typ=typ,
        retention_class=retention_class,
        dateiname=dateiname,
        speicherpfad=str(zielpfad),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def extract_energieausweis_for_case(db: Session, case_id: uuid.UUID, current_user: User) -> dict:
    """Sucht das zuletzt hochgeladene Energieausweis-Dokument des Falls,
    extrahiert Baujahr/Wohneinheiten/Verbrauchswerte und schreibt Baujahr und
    Wohneinheiten in das zugehoerige Building (Gesamtkonzept Modul 1).

    Verbrauchswerte werden zurueckgegeben, aber (noch) nicht persistiert -
    dafuer gibt es im Datenmodell (Systemarchitektur Abschnitt 7) bisher kein
    Feld auf Building.
    """
    case = get_case(db, case_id, current_user)

    dokument = (
        db.query(Document)
        .filter(Document.case_id == case.id, Document.typ == DocumentTyp.ENERGIEAUSWEIS)
        .order_by(Document.created_at.desc())
        .first()
    )
    if dokument is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kein Energieausweis-Dokument fuer diesen Fall hochgeladen.",
        )

    pdf_bytes = Path(dokument.speicherpfad).read_bytes()

    try:
        daten = extract_energieausweis(pdf_bytes)
    except UnlesbaresPDFFehler as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except LLMValidierungsFehler as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except LLMAufrufFehler as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if daten.baujahr is not None:
        case.building.baujahr = daten.baujahr
    if daten.wohneinheiten is not None:
        case.building.wohneinheiten = daten.wohneinheiten
    db.commit()

    return {
        "baujahr": daten.baujahr,
        "wohneinheiten": daten.wohneinheiten,
        "energieverbrauch_kwh_pro_m2a": daten.energieverbrauch_kwh_pro_m2a,
        "energieeffizienzklasse": daten.energieeffizienzklasse,
    }
