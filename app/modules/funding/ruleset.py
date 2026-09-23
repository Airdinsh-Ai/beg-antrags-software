"""Regelwerk-Verwaltung der Foerdersatz-Engine (Systemarchitektur Abschnitt 6).

Jeder Regelsatz ist eine YAML-Datei unter app/rules/ mit Gueltigkeitszeitraum als
Daten (gueltig_ab, gueltig_bis = letzter gueltiger Tag, null = aktuell gueltig).
Umgesetzt sind die vier Regeln aus Abschnitt 6:

1. Auswahl ueber den Stichtag des Falls, nicht ueber "neueste Datei"
   (waehle_regelsatz).
2. Regelsaetze werden nie ueberschrieben, nur abgeloest - beim Vorgaenger
   gueltig_bis setzen, neue Datei anlegen.
3. Ueberlappungs- und Lueckenpruefung beim Laden; main.py laedt beim Start,
   ein Fehler bricht den Start ab (Phase 0: laut und frueh).
4. Regel-Hash ueber den Dateiinhalt - belegt, dass die Datei seit der
   Berechnung unveraendert ist.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from app.models.funding import ProgrammTyp

# app/rules/ - Regelsaetze liegen bewusst neben, nicht im Modulcode (Abschnitt 3).
RULES_DIR = Path(__file__).parents[2] / "rules"


class RegelwerkFehler(Exception):
    """Regelwerk ist inkonsistent: Datei fehlerhaft, Zeitraeume ueberlappen
    oder lassen Luecken, oder fuer ein Programm fehlt jeder Regelsatz."""


class KeinRegelsatzFehler(Exception):
    """Fuer Programm und Stichtag gibt es keinen gueltigen Regelsatz - lieber
    ein klarer Fehler als eine stille Berechnung nach falschem Rechtsstand."""


class _Strikt(BaseModel):
    # extra="forbid": ein vertippter Schluessel faellt beim Laden auf, statt
    # still ignoriert zu werden.
    model_config = ConfigDict(extra="forbid", frozen=True)


class RegelwerkKopf(_Strikt):
    programm: ProgrammTyp
    version: str
    gueltig_ab: date
    gueltig_bis: date | None  # Pflichtschluessel, null = aktuell gueltig
    quelle: str
    geprueft_am: date


class EinkommensbonusStufe(_Strikt):
    bis_einkommen: int
    bonus: Decimal


class Kfw458Regeln(_Strikt):
    grundfoerderung: Decimal
    klimabonus: Decimal
    einkommensbonus_stufen: tuple[EinkommensbonusStufe, ...]
    max_quote_standard: Decimal
    max_quote_selbstnutzer_niedriges_einkommen: Decimal
    max_quote_selbstnutzer_einkommensgrenze: int
    foerderfaehige_kosten_deckel_erste_wohneinheit: Decimal


class BegEmRegeln(_Strikt):
    grundfoerderung: Decimal
    isfp_bonus: Decimal
    isfp_schwelle: Decimal
    foerderfaehige_kosten_deckel_erste_wohneinheit: Decimal
    foerderfaehige_kosten_deckel_mit_isfp: Decimal
    mindestinvestitionsvolumen: Decimal
    fachplanung_satz: Decimal
    fachplanung_deckel: Decimal
    energieberatung_satz: Decimal
    energieberatung_deckel_efh_zfh: Decimal
    energieberatung_deckel_mfh: Decimal


# Getrennte Modelle je Programm, keine gemeinsame Abstraktion (Abschnitt 2.7).
# Jedes Programm hier MUSS mindestens einen Regelsatz haben.
_REGELN_MODELLE: dict[ProgrammTyp, type[_Strikt]] = {
    ProgrammTyp.KFW_458: Kfw458Regeln,
    ProgrammTyp.BEG_EM: BegEmRegeln,
}


@dataclass(frozen=True)
class Regelsatz:
    kopf: RegelwerkKopf
    regeln: Kfw458Regeln | BegEmRegeln
    regel_hash: str

    def gilt_am(self, stichtag: date) -> bool:
        bis = self.kopf.gueltig_bis
        return self.kopf.gueltig_ab <= stichtag and (bis is None or stichtag <= bis)


def _lade_datei(pfad: Path) -> Regelsatz:
    # Zeilenenden normalisieren: git macht unter Windows aus LF ein CRLF - der
    # Hash soll den Inhalt belegen, nicht das Betriebssystem des Checkouts.
    inhalt = pfad.read_bytes().replace(b"\r\n", b"\n")
    try:
        daten = yaml.safe_load(inhalt)
        kopf = RegelwerkKopf.model_validate(daten["regelwerk"])
        regeln = _REGELN_MODELLE[kopf.programm].model_validate(daten["regeln"])
    except (yaml.YAMLError, KeyError, TypeError, ValidationError) as exc:
        raise RegelwerkFehler(f"{pfad.name}: {exc}") from exc
    return Regelsatz(kopf=kopf, regeln=regeln, regel_hash=hashlib.sha256(inhalt).hexdigest())


def _pruefe_zeitraeume(saetze: list[Regelsatz]) -> None:
    """Erwartet die Regelsaetze EINES Programms, sortiert nach gueltig_ab."""
    for satz in saetze:
        if satz.kopf.gueltig_bis is not None and satz.kopf.gueltig_bis < satz.kopf.gueltig_ab:
            raise RegelwerkFehler(f"{satz.kopf.version}: gueltig_bis liegt vor gueltig_ab.")

    for vorher, nachher in zip(saetze, saetze[1:]):
        bis = vorher.kopf.gueltig_bis
        if bis is None or nachher.kopf.gueltig_ab <= bis:
            raise RegelwerkFehler(
                f"Ueberlappung: {vorher.kopf.version} und {nachher.kopf.version} "
                "gelten gleichzeitig."
            )
        if nachher.kopf.gueltig_ab != bis + timedelta(days=1):
            raise RegelwerkFehler(
                f"Luecke zwischen {vorher.kopf.version} (bis {bis}) und "
                f"{nachher.kopf.version} (ab {nachher.kopf.gueltig_ab})."
            )


def lade_regelwerk(rules_dir: Path = RULES_DIR) -> dict[ProgrammTyp, list[Regelsatz]]:
    """Laedt und prueft alle Regelsaetze. Wirft RegelwerkFehler bei jedem
    Problem - nie ein teilweise geladenes Regelwerk."""
    regelwerk: dict[ProgrammTyp, list[Regelsatz]] = {}
    for pfad in sorted(rules_dir.glob("*.yaml")):
        satz = _lade_datei(pfad)
        regelwerk.setdefault(satz.kopf.programm, []).append(satz)

    for programm in _REGELN_MODELLE:
        if programm not in regelwerk:
            raise RegelwerkFehler(f"Kein Regelsatz fuer {programm.value} vorhanden.")

    for saetze in regelwerk.values():
        saetze.sort(key=lambda satz: satz.kopf.gueltig_ab)
        _pruefe_zeitraeume(saetze)
    return regelwerk


@cache
def aktuelles_regelwerk() -> dict[ProgrammTyp, list[Regelsatz]]:
    """Das produktive Regelwerk, einmal pro Prozess geladen. main.py ruft das
    beim Start auf, damit ein Fehler den Start abbricht statt die erste
    Berechnung."""
    return lade_regelwerk()


def waehle_regelsatz(
    programm: ProgrammTyp,
    stichtag: date,
    regelwerk: dict[ProgrammTyp, list[Regelsatz]] | None = None,
) -> Regelsatz:
    """Abschnitt 6, Regel 1: der Regelsatz, dessen Gueltigkeitszeitraum den
    Stichtag enthaelt - nicht der neueste."""
    if regelwerk is None:
        regelwerk = aktuelles_regelwerk()
    for satz in regelwerk.get(programm, []):
        if satz.gilt_am(stichtag):
            return satz
    raise KeinRegelsatzFehler(
        f"Kein gueltiger Regelsatz fuer {programm.value} am {stichtag:%d.%m.%Y}."
    )
