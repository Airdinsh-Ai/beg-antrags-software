import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.funding import rules
from app.modules.property.service import get_case
from app.models.user import User


def _einkommensbonus(haushaltsjahreseinkommen: int) -> Decimal:
    for grenze, bonus in rules.EINKOMMENSBONUS_STUFEN:
        if haushaltsjahreseinkommen <= grenze:
            return bonus
    return Decimal("0")


def calculate_kfw458(
    foerderfaehige_kosten: Decimal,
    haushaltsjahreseinkommen: int,
    ist_selbstnutzer: bool,
) -> dict:
    """Reine Berechnung, kein DB-Zugriff - Regelsatz Stand rules.REGELVERSION.

    Kappt zuerst die foerderfaehigen Kosten am Deckel fuer die erste Wohneinheit,
    dann die Foerderquote an der jeweils geltenden Obergrenze (Systemarchitektur
    Abschnitt 6, Modul 3).
    """
    quote = rules.GRUNDFOERDERUNG + rules.KLIMABONUS + _einkommensbonus(haushaltsjahreseinkommen)

    max_quote = rules.MAX_QUOTE_STANDARD
    if (
        ist_selbstnutzer
        and haushaltsjahreseinkommen <= rules.MAX_QUOTE_SELBSTNUTZER_EINKOMMENSGRENZE
    ):
        max_quote = rules.MAX_QUOTE_SELBSTNUTZER_NIEDRIGES_EINKOMMEN
    quote = min(quote, max_quote)

    kosten_gedeckelt = min(
        foerderfaehige_kosten, rules.FOERDERFAEHIGE_KOSTEN_DECKEL_ERSTE_WOHNEINHEIT
    )
    foerderbetrag = (kosten_gedeckelt * quote).quantize(Decimal("0.01"))

    return {
        "foerderquote": quote,
        "foerderfaehige_kosten_gedeckelt": kosten_gedeckelt,
        "foerderbetrag": foerderbetrag,
        "regelversion": rules.REGELVERSION,
        "regel_hash": rules.REGEL_HASH,
    }


def calculate_case_funding(
    db: Session,
    case_id: uuid.UUID,
    current_user: User,
    foerderfaehige_kosten: Decimal,
    haushaltsjahreseinkommen: int,
    ist_selbstnutzer: bool,
) -> dict:
    """Holt den Fall (inkl. Zugriffspruefung), berechnet und speichert
    regelversion/regel_hash am Case - fuer spaetere Nachvollziehbarkeit."""
    case = get_case(db, case_id, current_user)
    result = calculate_kfw458(foerderfaehige_kosten, haushaltsjahreseinkommen, ist_selbstnutzer)

    case.regelversion = result["regelversion"]
    case.regel_hash = result["regel_hash"]
    db.commit()

    return result
