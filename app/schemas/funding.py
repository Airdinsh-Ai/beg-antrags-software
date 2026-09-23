import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Kfw458CalculateRequest(BaseModel):
    foerderfaehige_kosten: Decimal = Field(gt=0)
    haushaltsjahreseinkommen: int = Field(ge=0)
    ist_selbstnutzer: bool = True
    # Optional: verknuepft die Berechnung mit einer konkreten Massnahme -
    # Voraussetzung fuer die 60%-Kumulierungspruefung (siehe check_kumulierung()).
    measure_id: uuid.UUID | None = None
    # Optional: massgebliches Datum fuer die Regelsatz-Auswahl (Systemarchitektur
    # Abschnitt 6, Regel 1). Fehlt es, gilt das Anlagedatum des Falls.
    stichtag: date | None = None


class Kfw458CalculateResponse(BaseModel):
    foerderquote: Decimal
    foerderfaehige_kosten_gedeckelt: Decimal
    foerderbetrag: Decimal
    stichtag: date
    regelversion: str
    regel_hash: str


class BegEmCalculateRequest(BaseModel):
    foerderfaehige_kosten: Decimal = Field(gt=0)
    hat_isfp: bool = False
    fachplanung_kosten: Decimal | None = Field(default=None, gt=0)
    energieberatung_kosten: Decimal | None = Field(default=None, gt=0)
    ist_mfh: bool = False
    measure_id: uuid.UUID | None = None
    # Optional: massgebliches Datum fuer die Regelsatz-Auswahl (Systemarchitektur
    # Abschnitt 6, Regel 1). Fehlt es, gilt das Anlagedatum des Falls.
    stichtag: date | None = None


class BegEmCalculateResponse(BaseModel):
    foerderfaehige_kosten_gedeckelt: Decimal
    grundfoerderung_betrag: Decimal
    isfp_bonus_betrag: Decimal
    hauptmassnahme_foerderbetrag: Decimal
    fachplanung_foerderbetrag: Decimal | None
    energieberatung_foerderbetrag: Decimal | None
    foerderbetrag: Decimal
    stichtag: date
    regelversion: str
    regel_hash: str


class FundingRulesetOut(BaseModel):
    programm: str
    regelversion: str
    gueltig_ab: date
    gueltig_bis: date | None
    quelle: str
    regel_hash: str
