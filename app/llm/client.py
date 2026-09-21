"""Einziger LLM-Client im Projekt (Systemarchitektur Abschnitt 4.1/4.2) - keine
andere Datei importiert eine Anbieter-Bibliothek. Fachliche Signaturen statt
durchgereichter chat.completions-Aufrufe; Pydantic-Modelle als Ergebnisvertrag.
Anbieter ist Phase 0 fest auf OpenAI verdrahtet (Abschnitt 4.3) - kein
Umschaltmechanismus, wird beim Anbieterwechsel ersetzt, nicht konfiguriert.
"""

import base64
import time
from typing import TypeVar

from openai import APIError, OpenAI
from pydantic import BaseModel

from app.core.config import settings

MODEL = "gpt-4o-mini"
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 0.5

T = TypeVar("T", bound=BaseModel)


class LLMAufrufFehler(Exception):
    """API-Aufruf ist nach Wiederholungen weiterhin fehlgeschlagen (Netz,
    Rate Limit, Ausfall) - Systemarchitektur Abschnitt 4.4."""


class LLMValidierungsFehler(Exception):
    """Antwort entspricht nicht dem erwarteten Schema - wird gemeldet, aber
    nicht gespeichert (Systemarchitektur Abschnitt 4.4)."""


class UnlesbaresPDFFehler(Exception):
    """PDF ist leer oder kein gueltiges PDF - eigener Fehlerfall VOR dem
    LLM-Aufruf, spart Kosten (Systemarchitektur Abschnitt 4.4)."""


class EnergieausweisDaten(BaseModel):
    baujahr: int | None
    wohneinheiten: int | None
    energieverbrauch_kwh_pro_m2a: float | None
    energieeffizienzklasse: str | None


class FallDatenFuerAntragstext(BaseModel):
    """Vom Service aus Modul 1-3-Daten zusammengestellt (Gesamtkonzept Modul 4)
    - der Client bekommt strukturierte Fakten, keinen freien Nutzer-Text."""

    adresse: str
    baujahr: int | None
    wohneinheiten: int | None
    massnahme_typ: str
    foerderprogramm: str | None
    jaz: float | None = None


class Antragstexte(BaseModel):
    massnahmenbeschreibung: str
    energetischer_mehrwert: str


def _get_client() -> OpenAI:
    # Lazy statt Modul-Ebene: verhindert einen Fehler beim Import, falls der
    # Key (noch) nicht gesetzt ist - z.B. in Tests, die diese Funktion nie
    # aufrufen.
    return OpenAI(api_key=settings.openai_api_key)


def _call_with_retry(messages: list, response_format: type[T]) -> T:
    """Gemeinsame Retry-mit-Backoff-Logik fuer alle Structured-Output-Aufrufe
    (Systemarchitektur Abschnitt 4.4, Fall 1)."""
    client = _get_client()
    response = None
    for versuch in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.parse(
                model=MODEL, messages=messages, response_format=response_format
            )
            break
        except APIError as exc:
            if versuch == MAX_RETRIES:
                raise LLMAufrufFehler(
                    f"OpenAI-Aufruf nach {MAX_RETRIES + 1} Versuchen fehlgeschlagen: {exc}"
                ) from exc
            time.sleep(RETRY_BACKOFF_SECONDS * (2**versuch))

    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise LLMValidierungsFehler(
            "Die Antwort entspricht nicht dem erwarteten Schema und wurde nicht gespeichert."
        )
    return parsed


def extract_energieausweis(pdf: bytes) -> EnergieausweisDaten:
    """Extrahiert Baujahr, Wohneinheiten und Verbrauchswerte aus einem
    Energieausweis-PDF (Gesamtkonzept Modul 1)."""
    if not pdf or not pdf.startswith(b"%PDF-"):
        raise UnlesbaresPDFFehler("Die Datei ist leer oder kein gueltiges PDF.")

    pdf_base64 = base64.b64encode(pdf).decode("ascii")
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Extrahiere aus diesem Energieausweis das Baujahr, die Anzahl "
                        "Wohneinheiten und die Verbrauchswerte (Energieverbrauchskennwert "
                        "in kWh/(m²a) und Energieeffizienzklasse, falls angegeben). Felder, "
                        "die nicht im Dokument stehen, bleiben leer statt geraten zu werden."
                    ),
                },
                {
                    "type": "file",
                    "file": {
                        "filename": "energieausweis.pdf",
                        "file_data": f"data:application/pdf;base64,{pdf_base64}",
                    },
                },
            ],
        }
    ]
    return _call_with_retry(messages, EnergieausweisDaten)


def generate_antragstexte(fall: FallDatenFuerAntragstext) -> Antragstexte:
    """Erzeugt die beiden Freitextfelder des BEG-Antrags (Gesamtkonzept
    Modul 4) - Maßnahmenbeschreibung und energetischer Mehrwert. Kein
    Formular-Ausfüller: alle strukturierten Felder traegt der Antragsteller
    weiterhin selbst ein (Produktdefinition, Kernentscheidung 10).

    Ergebnis ist ein ENTWURF - Pflicht-Review vor Freigabe (Abschnitt 4,
    DSGVO Art. 22), siehe modules/documents/service.py.
    """
    fakten = [f"Adresse: {fall.adresse}", f"Maßnahme: {fall.massnahme_typ}"]
    if fall.baujahr is not None:
        fakten.append(f"Baujahr: {fall.baujahr}")
    if fall.wohneinheiten is not None:
        fakten.append(f"Wohneinheiten: {fall.wohneinheiten}")
    if fall.foerderprogramm is not None:
        fakten.append(f"Förderprogramm: {fall.foerderprogramm}")
    if fall.jaz is not None:
        fakten.append(f"Jahresarbeitszahl (JAZ): {fall.jaz}")

    messages = [
        {
            "role": "user",
            "content": (
                "Erzeuge fuer einen BEG-Förderantrag (energetische Sanierung) genau zwei "
                "Freitexte auf Basis dieser Fakten:\n"
                + "\n".join(f"- {f}" for f in fakten)
                + "\n\n1. Maßnahmenbeschreibung: sachlich-technische Beschreibung der "
                "Maßnahme, Bauteile/Anlagen, technische Spezifikationen, Ausführung durch "
                "Fachbetrieb nach BEG-Mindestanforderungen.\n"
                "2. Energetischer Mehrwert: Reduzierung des Primärenergiebedarfs, Minderung "
                "der CO₂-Emissionen, Steigerung der Effizienz, Zukunftssicherheit der "
                "Immobilie.\n\n"
                "Nur die gegebenen Fakten verwenden, nichts erfinden. Deutsch, sachlich, "
                "amtssprachlich angemessen."
            ),
        }
    ]
    return _call_with_retry(messages, Antragstexte)
