"""BEG-EM-Regelsatz (BAFA-Anteil: Gebaeudehuelle, Anlagentechnik), Stand ab
21.07.2026.

Quelle (Primaerquelle, laut Recherche in Basics/Documente Projekt/
Unterlagen_Bafa_KfW/, geprueft gegen bafa.de, Richtlinie BEG EM vom
17.08.2026, Recherchestand 21.09.2026 - siehe Sitzungslog
2026-09-21-modul-2-und-beg-em-recherche.md).

Bewusst nur die erste Wohneinheit abgebildet, wie bei rules_kfw458.py -
die gestaffelten Deckel fuer weitere Wohneinheiten (2.-6. WE: 15.000 Euro,
ab 7. WE: 8.000 Euro) sind Phase 2 (Systemarchitektur Abschnitt 12).

Aenderungen an diesen Werten IMMER hier zentral vornehmen, nie in
service.py - sonst verliert REGEL_HASH seinen Sinn.
"""

import hashlib
from datetime import date
from decimal import Decimal

REGELVERSION = "beg-em-2026-07-21"
GUELTIG_AB = date(2026, 7, 21)
QUELLE = "bafa.de, Richtlinie BEG EM vom 17.08.2026"
GEPRUEFT_AM = date(2026, 9, 21)

GRUNDFOERDERUNG = Decimal("0.15")
# Marginalrechnung: nur auf den Kostenanteil UEBER dieser Schwelle, kein
# Flat-Rate-Prozentsatz auf die Gesamtkosten (strukturell anders als KfW 458).
ISFP_BONUS = Decimal("0.05")
ISFP_SCHWELLE = Decimal("30000")

FOERDERFAEHIGE_KOSTEN_DECKEL_ERSTE_WOHNEINHEIT = Decimal("30000")
FOERDERFAEHIGE_KOSTEN_DECKEL_MIT_ISFP = Decimal("60000")

MINDESTINVESTITIONSVOLUMEN = Decimal("300")

# Zwei eigene Nebenrechnungen, nicht Teil der Grundfoerderungs-Quote.
FACHPLANUNG_SATZ = Decimal("0.50")
FACHPLANUNG_DECKEL = Decimal("2500")

ENERGIEBERATUNG_SATZ = Decimal("0.50")
ENERGIEBERATUNG_DECKEL_EFH_ZFH = Decimal("650")
ENERGIEBERATUNG_DECKEL_MFH = Decimal("1300")


def _regel_hash() -> str:
    content = "|".join(
        str(v)
        for v in (
            GRUNDFOERDERUNG,
            ISFP_BONUS,
            ISFP_SCHWELLE,
            FOERDERFAEHIGE_KOSTEN_DECKEL_ERSTE_WOHNEINHEIT,
            FOERDERFAEHIGE_KOSTEN_DECKEL_MIT_ISFP,
            MINDESTINVESTITIONSVOLUMEN,
            FACHPLANUNG_SATZ,
            FACHPLANUNG_DECKEL,
            ENERGIEBERATUNG_SATZ,
            ENERGIEBERATUNG_DECKEL_EFH_ZFH,
            ENERGIEBERATUNG_DECKEL_MFH,
        )
    )
    return hashlib.sha256(content.encode()).hexdigest()


REGEL_HASH = _regel_hash()
