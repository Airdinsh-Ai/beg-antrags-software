"""KfW-458-Regelsatz (Heizungsfoerderung), Stand ab 21.07.2026.

Quelle (Primaerquelle, per WebFetch geprueft am 18.09.2026):
https://www.kfw.de/inlandsfoerderung/Bundesfoerderung-fuer-effiziente-Gebaeude/Anpassungen-2026/

BEG-EM (BAFA-Anteil: Gebaeudehuelle, Anlagentechnik) ist noch NICHT in diesem Regelsatz
enthalten - die amtlichen Prozentsaetze dafuer liegen bisher nur als nicht auslesbare
PDFs vor (siehe Sitzungslog 2026-09-18). Folgt als eigener Regelsatz, sobald verifiziert.

Aenderungen an diesen Werten IMMER hier zentral vornehmen, nie in service.py - sonst
verliert REGEL_HASH seinen Sinn (Nachvollziehbarkeit, Systemarchitektur Abschnitt 6).
"""

import hashlib
from datetime import date
from decimal import Decimal

REGELVERSION = "kfw458-2026-07-21"
GUELTIG_AB = date(2026, 7, 21)
QUELLE = "https://www.kfw.de/inlandsfoerderung/Bundesfoerderung-fuer-effiziente-Gebaeude/Anpassungen-2026/"
GEPRUEFT_AM = date(2026, 9, 18)

GRUNDFOERDERUNG = Decimal("0.30")
KLIMABONUS = Decimal("0.16")

# (Haushaltsjahreseinkommen bis einschliesslich X Euro, Bonus) - erster Treffer gewinnt.
EINKOMMENSBONUS_STUFEN: tuple[tuple[int, Decimal], ...] = (
    (30_000, Decimal("0.40")),
    (40_000, Decimal("0.30")),
    (50_000, Decimal("0.10")),
)

MAX_QUOTE_STANDARD = Decimal("0.70")
MAX_QUOTE_SELBSTNUTZER_NIEDRIGES_EINKOMMEN = Decimal("0.80")
MAX_QUOTE_SELBSTNUTZER_EINKOMMENSGRENZE = 40_000

# Deckelt die foerderfaehigen KOSTEN (nicht den Foerderbetrag) fuer die erste
# Wohneinheit. Weitere Wohneinheiten pro Gebaeude sind Phase 2 (Systemarchitektur
# Abschnitt 12) - hier bewusst nicht abgebildet.
FOERDERFAEHIGE_KOSTEN_DECKEL_ERSTE_WOHNEINHEIT = Decimal("28000")


def _regel_hash() -> str:
    content = "|".join(
        str(v)
        for v in (
            GRUNDFOERDERUNG,
            KLIMABONUS,
            EINKOMMENSBONUS_STUFEN,
            MAX_QUOTE_STANDARD,
            MAX_QUOTE_SELBSTNUTZER_NIEDRIGES_EINKOMMEN,
            MAX_QUOTE_SELBSTNUTZER_EINKOMMENSGRENZE,
            FOERDERFAEHIGE_KOSTEN_DECKEL_ERSTE_WOHNEINHEIT,
        )
    )
    return hashlib.sha256(content.encode()).hexdigest()


REGEL_HASH = _regel_hash()
