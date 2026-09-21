"""Einziger LLM-Client im Projekt (Systemarchitektur Abschnitt 4.1/4.2) - keine
andere Datei importiert eine Anbieter-Bibliothek. Fachliche Signaturen statt
durchgereichter chat.completions-Aufrufe; Pydantic-Modelle als Ergebnisvertrag.
Anbieter ist Phase 0 fest auf OpenAI verdrahtet (Abschnitt 4.3) - kein
Umschaltmechanismus, wird beim Anbieterwechsel ersetzt, nicht konfiguriert.
"""

import base64
import time

from openai import APIError, OpenAI
from pydantic import BaseModel

from app.core.config import settings

MODEL = "gpt-4o-mini"
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 0.5


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


def _get_client() -> OpenAI:
    # Lazy statt Modul-Ebene: verhindert einen Fehler beim Import, falls der
    # Key (noch) nicht gesetzt ist - z.B. in Tests, die diese Funktion nie
    # aufrufen.
    return OpenAI(api_key=settings.openai_api_key)


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

    client = _get_client()
    response = None
    for versuch in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.parse(
                model=MODEL, messages=messages, response_format=EnergieausweisDaten
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
