import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Kfw458CalculateRequest(BaseModel):
    foerderfaehige_kosten: Decimal = Field(gt=0)
    # Pflicht ohne Standardwert: entscheidet ueber Klima- und Einkommensbonus
    # (KfW-Merkblatt 458, 07/2026) - ein stiller Default wuerde Boni unterstellen.
    ist_selbstnutzer: bool
    # Nur fuer Selbstnutzer relevant und dort Pflicht (Pruefung in der Engine, 422).
    haushaltsjahreseinkommen: int | None = Field(default=None, ge=0)
    # Familienzuschlag: mind. ein minderjaehriges, kindergeldberechtigtes Kind im Haushalt.
    kind_im_haushalt: bool = False
    # Pflicht: Typpruefung (KfW 458 nur fuer Waermeerzeuger) und "ein Programm pro
    # Massnahme" brauchen die Massnahme; die Altheizung haengt ebenfalls an ihr.
    measure_id: uuid.UUID
    # Optional: massgebliches Datum fuer die Regelsatz-Auswahl (Systemarchitektur
    # Abschnitt 6, Regel 1). Fehlt es, gilt das Anlagedatum des Falls.
    stichtag: date | None = None


class Kfw458CalculateResponse(BaseModel):
    foerderquote: Decimal
    foerderfaehige_kosten_gedeckelt: Decimal
    foerderbetrag: Decimal
    # Aufschluesselung, damit die Quote nachvollziehbar ist - nicht nur die Endzahl.
    klimabonus_angewendet: bool
    einkommensbonus: Decimal
    max_quote: Decimal
    stichtag: date
    regelversion: str
    regel_hash: str


class BegEmCalculateRequest(BaseModel):
    foerderfaehige_kosten: Decimal = Field(gt=0)
    hat_isfp: bool = False
    fachplanung_kosten: Decimal | None = Field(default=None, gt=0)
    energieberatung_kosten: Decimal | None = Field(default=None, gt=0)
    ist_mfh: bool = False
    # Pflicht: Typpruefung (keine Waermeerzeuger ueber BEG EM) und "ein Programm
    # pro Massnahme".
    measure_id: uuid.UUID
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
