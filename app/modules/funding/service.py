import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models.case import Case
from app.models.funding import CaseFunding, FundingHistory, ProgrammTyp
from app.models.user import User
from app.modules.funding import rules_beg_em, rules_kfw458
from app.modules.property.service import get_case

# Gesamtkonzept Modul 3: Obergrenze der Gesamtfoerderquote aus allen
# oeffentlichen Quellen fuer dieselben Kosten. Greift nur zwischen mehreren
# PROGRAMMEN auf derselben Massnahme - ein einzelnes Programm darf seinen
# eigenen, hoeheren offiziellen Satz (z.B. KfW 458 bis 80 %) ausschoepfen,
# das ist kein Kumulierungsfall.
KUMULIERUNG_OBERGRENZE = Decimal("0.60")


def _einkommensbonus(haushaltsjahreseinkommen: int) -> Decimal:
    for grenze, bonus in rules_kfw458.EINKOMMENSBONUS_STUFEN:
        if haushaltsjahreseinkommen <= grenze:
            return bonus
    return Decimal("0")


def calculate_kfw458(
    foerderfaehige_kosten: Decimal,
    haushaltsjahreseinkommen: int,
    ist_selbstnutzer: bool,
) -> dict:
    """Reine Berechnung, kein DB-Zugriff - Regelsatz Stand rules_kfw458.REGELVERSION.

    Kappt zuerst die foerderfaehigen Kosten am Deckel fuer die erste Wohneinheit,
    dann die Foerderquote an der jeweils geltenden Obergrenze (Systemarchitektur
    Abschnitt 6, Modul 3).
    """
    quote = rules_kfw458.GRUNDFOERDERUNG + rules_kfw458.KLIMABONUS + _einkommensbonus(
        haushaltsjahreseinkommen
    )

    max_quote = rules_kfw458.MAX_QUOTE_STANDARD
    if (
        ist_selbstnutzer
        and haushaltsjahreseinkommen <= rules_kfw458.MAX_QUOTE_SELBSTNUTZER_EINKOMMENSGRENZE
    ):
        max_quote = rules_kfw458.MAX_QUOTE_SELBSTNUTZER_NIEDRIGES_EINKOMMEN
    quote = min(quote, max_quote)

    kosten_gedeckelt = min(
        foerderfaehige_kosten, rules_kfw458.FOERDERFAEHIGE_KOSTEN_DECKEL_ERSTE_WOHNEINHEIT
    )
    foerderbetrag = (kosten_gedeckelt * quote).quantize(Decimal("0.01"))

    return {
        "foerderquote": quote,
        "foerderfaehige_kosten_gedeckelt": kosten_gedeckelt,
        "foerderbetrag": foerderbetrag,
        "regelversion": rules_kfw458.REGELVERSION,
        "regel_hash": rules_kfw458.REGEL_HASH,
    }


def calculate_beg_em(
    foerderfaehige_kosten: Decimal,
    hat_isfp: bool,
    fachplanung_kosten: Decimal | None = None,
    energieberatung_kosten: Decimal | None = None,
    ist_mfh: bool = False,
) -> dict:
    """Reine Berechnung, kein DB-Zugriff - Regelsatz Stand rules_beg_em.REGELVERSION.

    Strukturell anders als calculate_kfw458 (Systemarchitektur Abschnitt 2.7):
    der iSFP-Bonus ist eine Marginalrechnung nur auf den Kostenanteil ueber
    30.000 Euro, und Fachplanung/Baubegleitung sowie Energieberatung sind zwei
    eigene Nebenrechnungen statt Teil derselben Foerderquote.
    """
    deckel = (
        rules_beg_em.FOERDERFAEHIGE_KOSTEN_DECKEL_MIT_ISFP
        if hat_isfp
        else rules_beg_em.FOERDERFAEHIGE_KOSTEN_DECKEL_ERSTE_WOHNEINHEIT
    )
    kosten_gedeckelt = min(foerderfaehige_kosten, deckel)

    grundfoerderung_betrag = Decimal("0.00")
    isfp_bonus_betrag = Decimal("0.00")
    if kosten_gedeckelt >= rules_beg_em.MINDESTINVESTITIONSVOLUMEN:
        grundfoerderung_betrag = (kosten_gedeckelt * rules_beg_em.GRUNDFOERDERUNG).quantize(
            Decimal("0.01")
        )
        if hat_isfp:
            marginal_basis = max(Decimal("0"), kosten_gedeckelt - rules_beg_em.ISFP_SCHWELLE)
            isfp_bonus_betrag = (marginal_basis * rules_beg_em.ISFP_BONUS).quantize(Decimal("0.01"))

    hauptmassnahme_foerderbetrag = grundfoerderung_betrag + isfp_bonus_betrag

    fachplanung_foerderbetrag = None
    if fachplanung_kosten is not None:
        fachplanung_foerderbetrag = min(
            (fachplanung_kosten * rules_beg_em.FACHPLANUNG_SATZ).quantize(Decimal("0.01")),
            rules_beg_em.FACHPLANUNG_DECKEL,
        )

    energieberatung_foerderbetrag = None
    if energieberatung_kosten is not None:
        energieberatung_deckel = (
            rules_beg_em.ENERGIEBERATUNG_DECKEL_MFH
            if ist_mfh
            else rules_beg_em.ENERGIEBERATUNG_DECKEL_EFH_ZFH
        )
        energieberatung_foerderbetrag = min(
            (energieberatung_kosten * rules_beg_em.ENERGIEBERATUNG_SATZ).quantize(Decimal("0.01")),
            energieberatung_deckel,
        )

    gesamtfoerderbetrag = (
        hauptmassnahme_foerderbetrag
        + (fachplanung_foerderbetrag or Decimal("0.00"))
        + (energieberatung_foerderbetrag or Decimal("0.00"))
    )

    return {
        "foerderfaehige_kosten_gedeckelt": kosten_gedeckelt,
        "grundfoerderung_betrag": grundfoerderung_betrag,
        "isfp_bonus_betrag": isfp_bonus_betrag,
        "hauptmassnahme_foerderbetrag": hauptmassnahme_foerderbetrag,
        "fachplanung_foerderbetrag": fachplanung_foerderbetrag,
        "energieberatung_foerderbetrag": energieberatung_foerderbetrag,
        "foerderbetrag": gesamtfoerderbetrag,
        "regelversion": rules_beg_em.REGELVERSION,
        "regel_hash": rules_beg_em.REGEL_HASH,
    }


def check_kumulierung(
    db: Session,
    measure_id: uuid.UUID | None,
    programm: ProgrammTyp,
    foerderfaehige_kosten: Decimal,
    neuer_foerderbetrag: Decimal,
) -> None:
    """60%-Kumulierungsobergrenze (Gesamtkonzept Modul 3): Summe aus MEHREREN
    Programmen fuer dieselbe Massnahme darf 60 % ihrer foerderfaehigen Kosten
    nicht uebersteigen. Ein einzelnes Programm ohne zweites auf derselben
    Massnahme ist davon ausgenommen - es darf seinen eigenen, ggf. hoeheren
    offiziellen Satz ausschoepfen (z.B. KfW 458 bis 80 %); das ist keine
    Kumulierung, sondern die normale Foerderquote dieses einen Programms.

    Ohne measure_id keine Pruefung - das deckt den ausdruecklich erlaubten
    Fall ab, dass unterschiedliche Gewerke (z.B. Daemmung ueber BAFA, Heizung
    ueber KfW 458) getrennt gefoerdert werden, ohne dass hier ein Bezug
    zwischen ihnen besteht.
    """
    if measure_id is None:
        return

    andere_eintraege = (
        db.query(CaseFunding)
        .filter(CaseFunding.measure_id == measure_id, CaseFunding.programm != programm)
        .all()
    )
    if not andere_eintraege:
        # Kein zweites Programm auf dieser Massnahme - keine Kumulierung im Spiel.
        return

    bisherige_summe = sum((eintrag.foerderbetrag for eintrag in andere_eintraege), Decimal("0"))
    gesamt = bisherige_summe + neuer_foerderbetrag
    obergrenze = (foerderfaehige_kosten * KUMULIERUNG_OBERGRENZE).quantize(Decimal("0.01"))

    if gesamt > obergrenze:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Kumulierungsobergrenze ueberschritten: {gesamt} Euro Gesamtfoerderung "
                f"aus mehreren Programmen fuer diese Massnahme uebersteigen 60 % von "
                f"{foerderfaehige_kosten} Euro foerderfaehigen Kosten ({obergrenze} Euro) "
                "(Gesamtkonzept Modul 3)."
            ),
        )


def _upsert_case_funding(
    db: Session,
    case: Case,
    programm: ProgrammTyp,
    foerderbetrag: Decimal,
    regelversion: str,
    regel_hash: str,
    measure_id: uuid.UUID | None = None,
    foerderfaehige_kosten: Decimal | None = None,
) -> CaseFunding:
    """Upsert je (case_id, programm) - eine Neuberechnung ersetzt die bestehende
    Zeile, statt eine zweite anzuhaengen (Systemarchitektur Abschnitt 7.5).

    Schreibt danach funding_history als komplette Neuberechnung aus der
    aktuellen Summe aller case_funding-Zeilen dieses Gebaeudes/Jahres/Programms
    - nicht additiv. Damit ist es unerheblich, wie oft ein Fall neu berechnet
    wird: funding_history bleibt konsistent, ohne Verworfenes mitzuzaehlen.
    """
    entry = (
        db.query(CaseFunding)
        .filter(CaseFunding.case_id == case.id, CaseFunding.programm == programm)
        .one_or_none()
    )
    now = utcnow()
    if entry is None:
        entry = CaseFunding(case_id=case.id, programm=programm)
        db.add(entry)

    entry.foerderbetrag = foerderbetrag
    entry.regelversion = regelversion
    entry.regel_hash = regel_hash
    entry.berechnet_am = now
    entry.measure_id = measure_id
    entry.foerderfaehige_kosten = foerderfaehige_kosten
    db.flush()

    jahr = now.year
    zeilen = (
        db.query(CaseFunding)
        .join(Case, Case.id == CaseFunding.case_id)
        .filter(Case.building_id == case.building_id, CaseFunding.programm == programm)
        .all()
    )
    summe = sum(
        (zeile.foerderbetrag for zeile in zeilen if zeile.berechnet_am.year == jahr),
        Decimal("0.00"),
    )

    history = (
        db.query(FundingHistory)
        .filter(
            FundingHistory.building_id == case.building_id,
            FundingHistory.jahr == jahr,
            FundingHistory.programm == programm,
        )
        .one_or_none()
    )
    if history is None:
        db.add(FundingHistory(building_id=case.building_id, jahr=jahr, programm=programm, betrag=summe))
    else:
        history.betrag = summe

    db.commit()
    db.refresh(entry)
    return entry


def calculate_case_kfw458(
    db: Session,
    case_id: uuid.UUID,
    current_user: User,
    foerderfaehige_kosten: Decimal,
    haushaltsjahreseinkommen: int,
    ist_selbstnutzer: bool,
    measure_id: uuid.UUID | None = None,
) -> dict:
    case = get_case(db, case_id, current_user)
    result = calculate_kfw458(foerderfaehige_kosten, haushaltsjahreseinkommen, ist_selbstnutzer)
    check_kumulierung(db, measure_id, ProgrammTyp.KFW_458, foerderfaehige_kosten, result["foerderbetrag"])
    _upsert_case_funding(
        db,
        case,
        ProgrammTyp.KFW_458,
        result["foerderbetrag"],
        result["regelversion"],
        result["regel_hash"],
        measure_id=measure_id,
        foerderfaehige_kosten=foerderfaehige_kosten,
    )
    return result


def calculate_case_beg_em(
    db: Session,
    case_id: uuid.UUID,
    current_user: User,
    foerderfaehige_kosten: Decimal,
    hat_isfp: bool,
    fachplanung_kosten: Decimal | None,
    energieberatung_kosten: Decimal | None,
    ist_mfh: bool,
    measure_id: uuid.UUID | None = None,
) -> dict:
    case = get_case(db, case_id, current_user)
    result = calculate_beg_em(
        foerderfaehige_kosten, hat_isfp, fachplanung_kosten, energieberatung_kosten, ist_mfh
    )
    check_kumulierung(db, measure_id, ProgrammTyp.BEG_EM, foerderfaehige_kosten, result["foerderbetrag"])
    _upsert_case_funding(
        db,
        case,
        ProgrammTyp.BEG_EM,
        result["foerderbetrag"],
        result["regelversion"],
        result["regel_hash"],
        measure_id=measure_id,
        foerderfaehige_kosten=foerderfaehige_kosten,
    )
    return result
