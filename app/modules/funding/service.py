import uuid
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models.case import Case
from app.models.funding import CaseFunding, FundingHistory, ProgrammTyp
from app.models.user import User
from app.modules.funding import ruleset
from app.modules.property.service import get_case

# Gesamtkonzept Modul 3: Obergrenze der Gesamtfoerderquote aus allen
# oeffentlichen Quellen fuer dieselben Kosten. Greift nur zwischen mehreren
# PROGRAMMEN auf derselben Massnahme - ein einzelnes Programm darf seinen
# eigenen, hoeheren offiziellen Satz (z.B. KfW 458 bis 80 %) ausschoepfen,
# das ist kein Kumulierungsfall.
KUMULIERUNG_OBERGRENZE = Decimal("0.60")


def _einkommensbonus(regeln: ruleset.Kfw458Regeln, haushaltsjahreseinkommen: int) -> Decimal:
    for stufe in regeln.einkommensbonus_stufen:
        if haushaltsjahreseinkommen <= stufe.bis_einkommen:
            return stufe.bonus
    return Decimal("0")


def calculate_kfw458(
    foerderfaehige_kosten: Decimal,
    haushaltsjahreseinkommen: int,
    ist_selbstnutzer: bool,
    stichtag: date | None = None,
) -> dict:
    """Reine Berechnung, kein DB-Zugriff - Regelsatz nach Stichtag gewaehlt
    (Systemarchitektur Abschnitt 6, Regel 1), ohne Stichtag gilt heute.
    Wirft ruleset.KeinRegelsatzFehler, wenn am Stichtag keiner gilt.

    Kappt zuerst die foerderfaehigen Kosten am Deckel fuer die erste Wohneinheit,
    dann die Foerderquote an der jeweils geltenden Obergrenze (Modul 3).
    """
    stichtag = stichtag or utcnow().date()
    regelsatz = ruleset.waehle_regelsatz(ProgrammTyp.KFW_458, stichtag)
    regeln: ruleset.Kfw458Regeln = regelsatz.regeln

    quote = regeln.grundfoerderung + regeln.klimabonus + _einkommensbonus(
        regeln, haushaltsjahreseinkommen
    )

    max_quote = regeln.max_quote_standard
    if (
        ist_selbstnutzer
        and haushaltsjahreseinkommen <= regeln.max_quote_selbstnutzer_einkommensgrenze
    ):
        max_quote = regeln.max_quote_selbstnutzer_niedriges_einkommen
    quote = min(quote, max_quote)

    kosten_gedeckelt = min(foerderfaehige_kosten, regeln.foerderfaehige_kosten_deckel_erste_wohneinheit)
    foerderbetrag = (kosten_gedeckelt * quote).quantize(Decimal("0.01"))

    return {
        "foerderquote": quote,
        "foerderfaehige_kosten_gedeckelt": kosten_gedeckelt,
        "foerderbetrag": foerderbetrag,
        "stichtag": stichtag,
        "regelversion": regelsatz.kopf.version,
        "regel_hash": regelsatz.regel_hash,
    }


def calculate_beg_em(
    foerderfaehige_kosten: Decimal,
    hat_isfp: bool,
    fachplanung_kosten: Decimal | None = None,
    energieberatung_kosten: Decimal | None = None,
    ist_mfh: bool = False,
    stichtag: date | None = None,
) -> dict:
    """Reine Berechnung, kein DB-Zugriff - Regelsatz nach Stichtag gewaehlt wie
    bei calculate_kfw458 (ohne Stichtag gilt heute).

    Strukturell anders als calculate_kfw458 (Systemarchitektur Abschnitt 2.7):
    der iSFP-Bonus ist eine Marginalrechnung nur auf den Kostenanteil ueber
    30.000 Euro, und Fachplanung/Baubegleitung sowie Energieberatung sind zwei
    eigene Nebenrechnungen statt Teil derselben Foerderquote.
    """
    stichtag = stichtag or utcnow().date()
    regelsatz = ruleset.waehle_regelsatz(ProgrammTyp.BEG_EM, stichtag)
    regeln: ruleset.BegEmRegeln = regelsatz.regeln

    deckel = (
        regeln.foerderfaehige_kosten_deckel_mit_isfp
        if hat_isfp
        else regeln.foerderfaehige_kosten_deckel_erste_wohneinheit
    )
    kosten_gedeckelt = min(foerderfaehige_kosten, deckel)

    grundfoerderung_betrag = Decimal("0.00")
    isfp_bonus_betrag = Decimal("0.00")
    if kosten_gedeckelt >= regeln.mindestinvestitionsvolumen:
        grundfoerderung_betrag = (kosten_gedeckelt * regeln.grundfoerderung).quantize(
            Decimal("0.01")
        )
        if hat_isfp:
            marginal_basis = max(Decimal("0"), kosten_gedeckelt - regeln.isfp_schwelle)
            isfp_bonus_betrag = (marginal_basis * regeln.isfp_bonus).quantize(Decimal("0.01"))

    hauptmassnahme_foerderbetrag = grundfoerderung_betrag + isfp_bonus_betrag

    fachplanung_foerderbetrag = None
    if fachplanung_kosten is not None:
        fachplanung_foerderbetrag = min(
            (fachplanung_kosten * regeln.fachplanung_satz).quantize(Decimal("0.01")),
            regeln.fachplanung_deckel,
        )

    energieberatung_foerderbetrag = None
    if energieberatung_kosten is not None:
        energieberatung_deckel = (
            regeln.energieberatung_deckel_mfh
            if ist_mfh
            else regeln.energieberatung_deckel_efh_zfh
        )
        energieberatung_foerderbetrag = min(
            (energieberatung_kosten * regeln.energieberatung_satz).quantize(Decimal("0.01")),
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
        "stichtag": stichtag,
        "regelversion": regelsatz.kopf.version,
        "regel_hash": regelsatz.regel_hash,
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


def _stichtag_fuer(case: Case, stichtag: date | None) -> date:
    """Massgebliches Datum fuer die Regelsatz-Auswahl: explizit uebergeben,
    sonst das Anlagedatum des Falls. Ein eigenes Antragsdatum am Fall gibt es
    in Phase 0 bewusst nicht (keine Migration dafuer)."""
    return stichtag or case.created_at.date()


@contextmanager
def _kein_regelsatz_als_422():
    try:
        yield
    except ruleset.KeinRegelsatzFehler as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


def calculate_case_kfw458(
    db: Session,
    case_id: uuid.UUID,
    current_user: User,
    foerderfaehige_kosten: Decimal,
    haushaltsjahreseinkommen: int,
    ist_selbstnutzer: bool,
    measure_id: uuid.UUID | None = None,
    stichtag: date | None = None,
) -> dict:
    case = get_case(db, case_id, current_user)
    with _kein_regelsatz_als_422():
        result = calculate_kfw458(
            foerderfaehige_kosten,
            haushaltsjahreseinkommen,
            ist_selbstnutzer,
            stichtag=_stichtag_fuer(case, stichtag),
        )
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
    stichtag: date | None = None,
) -> dict:
    case = get_case(db, case_id, current_user)
    with _kein_regelsatz_als_422():
        result = calculate_beg_em(
            foerderfaehige_kosten,
            hat_isfp,
            fachplanung_kosten,
            energieberatung_kosten,
            ist_mfh,
            stichtag=_stichtag_fuer(case, stichtag),
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
