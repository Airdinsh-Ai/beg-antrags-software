import uuid
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models.case import Case
from app.models.funding import CaseFunding, FundingHistory, ProgrammTyp
from app.models.measure import AltheizungArt, Measure
from app.models.user import User
from app.modules.funding import ruleset
from app.modules.property.service import get_case


class FehlendeAngabeFehler(Exception):
    """Eine fuer die Berechnung noetige Angabe fehlt - z.B. Einkommen oder
    Altheizung bei Selbstnutzern (KfW-Merkblatt 458, 07/2026). Wird im Service
    zu 422, analog zur fehlenden JAZ in Modul 2."""


def _jahre_vor(stichtag: date, jahre: int) -> date:
    """Derselbe Kalendertag `jahre` Jahre vor dem Stichtag - echte
    Kalenderarithmetik statt Tage/365. Faellt der Stichtag auf den 29.02. und
    das Zieljahr ist kein Schaltjahr, gilt der 28.02.: eine an diesem Tag
    begonnene Jahresfrist ist am 29.02. des Stichtagsjahres bereits vollendet."""
    try:
        return stichtag.replace(year=stichtag.year - jahre)
    except ValueError:
        return stichtag.replace(year=stichtag.year - jahre, day=28)


def _klimabonus_berechtigt(
    regeln: ruleset.Kfw458Regeln,
    art: AltheizungArt,
    inbetriebnahme: date,
    funktionstuechtig: bool,
    stichtag: date,
) -> bool:
    """Klimageschwindigkeitsbonus-Voraussetzung an der Altheizung (Merkblatt
    S. 3) - die Selbstnutzung prueft der Aufrufer. "Mindestens N Jahre
    zurueckliegend" heisst: Inbetriebnahme spaetestens am N-ten Jahrestag vor dem
    Stichtag. Beispiel: 29.02.2004 -> am 28.02.2024 nein, ab 29.02.2024 ja."""
    if not funktionstuechtig:
        return False
    if art in regeln.klimabonus_heizarten_ohne_altersgrenze:
        return True
    if art in regeln.klimabonus_heizarten_mit_altersgrenze:
        return inbetriebnahme <= _jahre_vor(stichtag, regeln.klimabonus_mindestalter_jahre)
    return False


def _einkommensbonus(regeln: ruleset.Kfw458Regeln, bemessungseinkommen: Decimal) -> Decimal:
    for stufe in regeln.einkommensbonus_stufen:
        if bemessungseinkommen <= stufe.bis_einkommen:
            return stufe.bonus
    return Decimal("0")


def calculate_kfw458(
    foerderfaehige_kosten: Decimal,
    haushaltsjahreseinkommen: int | None,
    ist_selbstnutzer: bool,
    kind_im_haushalt: bool = False,
    alte_heizung_art: AltheizungArt | None = None,
    alte_heizung_inbetriebnahme: date | None = None,
    alte_heizung_funktionstuechtig: bool | None = None,
    stichtag: date | None = None,
) -> dict:
    """Reine Berechnung, kein DB-Zugriff - Regelsatz nach Stichtag gewaehlt
    (Systemarchitektur Abschnitt 6, Regel 1), ohne Stichtag gilt heute.
    Wirft ruleset.KeinRegelsatzFehler, wenn am Stichtag keiner gilt, und
    FehlendeAngabeFehler, wenn einem Selbstnutzer Einkommen oder Altheizung fehlt.

    Nach KfW-Merkblatt 458, Stand 07/2026: Klima- und Einkommensbonus nur fuer
    Selbstnutzer; der Familienzuschlag senkt das Bemessungseinkommen und
    verschiebt damit Bonusstufen UND 80-%-Grenze. Danach Quote kappen, Kosten am
    Deckel der ersten Wohneinheit kappen, unter der Mindestinvestition 0 Euro.
    Nicht-Selbstnutzer: Einkommen, Kind und Altheizung werden ignoriert.
    """
    stichtag = stichtag or utcnow().date()
    regelsatz = ruleset.waehle_regelsatz(ProgrammTyp.KFW_458, stichtag)
    regeln: ruleset.Kfw458Regeln = regelsatz.regeln

    einkommensbonus = Decimal("0")
    klimabonus_angewendet = False
    max_quote = regeln.max_quote_standard

    if ist_selbstnutzer:
        fehlend = [
            name
            for name, wert in (
                ("haushaltsjahreseinkommen", haushaltsjahreseinkommen),
                ("alte_heizung_art", alte_heizung_art),
                ("alte_heizung_inbetriebnahme", alte_heizung_inbetriebnahme),
                ("alte_heizung_funktionstuechtig", alte_heizung_funktionstuechtig),
            )
            if wert is None
        ]
        if fehlend:
            raise FehlendeAngabeFehler(
                "Fuer Selbstnutzer erforderlich (Klima-/Einkommensbonus, KfW-Merkblatt 458): "
                + ", ".join(fehlend)
                + ". Die alte_heizung_* werden an der Massnahme hinterlegt."
            )

        bemessungseinkommen = Decimal(haushaltsjahreseinkommen)
        if kind_im_haushalt:
            bemessungseinkommen -= regeln.familienzuschlag

        einkommensbonus = _einkommensbonus(regeln, bemessungseinkommen)
        klimabonus_angewendet = _klimabonus_berechtigt(
            regeln,
            alte_heizung_art,
            alte_heizung_inbetriebnahme,
            alte_heizung_funktionstuechtig,
            stichtag,
        )
        if bemessungseinkommen <= regeln.max_quote_selbstnutzer_einkommensgrenze:
            max_quote = regeln.max_quote_selbstnutzer_niedriges_einkommen

    quote = regeln.grundfoerderung + einkommensbonus
    if klimabonus_angewendet:
        quote += regeln.klimabonus
    quote = min(quote, max_quote)

    kosten_gedeckelt = min(foerderfaehige_kosten, regeln.foerderfaehige_kosten_deckel_erste_wohneinheit)
    foerderbetrag = Decimal("0.00")
    if foerderfaehige_kosten >= regeln.mindestinvestitionsvolumen:
        foerderbetrag = (kosten_gedeckelt * quote).quantize(Decimal("0.01"))

    return {
        "foerderquote": quote,
        "foerderfaehige_kosten_gedeckelt": kosten_gedeckelt,
        "foerderbetrag": foerderbetrag,
        "klimabonus_angewendet": klimabonus_angewendet,
        "einkommensbonus": einkommensbonus,
        "max_quote": max_quote,
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


def check_ein_programm_pro_massnahme(
    db: Session, measure_id: uuid.UUID, programm: ProgrammTyp
) -> None:
    """Fuer dieselben foerderfaehigen Kosten nur ein Antrag, KfW ODER BAFA
    (KfW-Merkblatt 458, 07/2026, S. 9) - unabhaengig von der Hoehe. Solange die
    zulaessigen Massnahmentypen beider Regelsaetze disjunkt sind, faengt schon die
    Typpruefung das ab; dieser Schutz greift, falls sie sich kuenftig ueberschneiden.
    Dasselbe Programm erneut zu berechnen ist kein Konflikt (Upsert).

    Ersetzt die fruehere 60-%-Kumulierungspruefung: die 60 % gelten laut Merkblatt
    nur fuer die Kombination mit ANDEREN oeffentlichen Mitteln (Kredite, Zulagen,
    Landeszuschuesse), die Phase 0 nicht abbildet - BACKLOG B28.
    """
    anderes = (
        db.query(CaseFunding)
        .filter(CaseFunding.measure_id == measure_id, CaseFunding.programm != programm)
        .first()
    )
    if anderes is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Fuer diese Massnahme ist bereits {anderes.programm.value} berechnet - fuer "
                "dieselben foerderfaehigen Kosten ist nur ein Antrag zulaessig, KfW oder "
                "BAFA (KfW-Merkblatt 458, S. 9)."
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
def _berechnungsfehler_als_422():
    try:
        yield
    except (ruleset.KeinRegelsatzFehler, FehlendeAngabeFehler) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


def _get_measure_im_fall(db: Session, case: Case, measure_id: uuid.UUID) -> Measure:
    measure = (
        db.query(Measure).filter(Measure.id == measure_id, Measure.case_id == case.id).one_or_none()
    )
    if measure is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Massnahme nicht in diesem Fall gefunden."
        )
    return measure


def _check_massnahmentyp(regelsatz: ruleset.Regelsatz, measure: Measure) -> None:
    """Welche Massnahmentypen ein Programm foerdert, steht im Regelsatz
    (zulaessige_massnahmen), nicht im Code."""
    zulaessig = regelsatz.regeln.zulaessige_massnahmen
    if measure.typ not in zulaessig:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Massnahmentyp '{measure.typ.value}' ist fuer {regelsatz.kopf.programm.value} "
                f"nicht zulaessig (Regelsatz {regelsatz.kopf.version}: "
                f"{', '.join(t.value for t in zulaessig)})."
            ),
        )


def calculate_case_kfw458(
    db: Session,
    case_id: uuid.UUID,
    current_user: User,
    foerderfaehige_kosten: Decimal,
    ist_selbstnutzer: bool,
    haushaltsjahreseinkommen: int | None,
    kind_im_haushalt: bool,
    measure_id: uuid.UUID,
    stichtag: date | None = None,
) -> dict:
    case = get_case(db, case_id, current_user)
    measure = _get_measure_im_fall(db, case, measure_id)
    stichtag = _stichtag_fuer(case, stichtag)
    with _berechnungsfehler_als_422():
        _check_massnahmentyp(ruleset.waehle_regelsatz(ProgrammTyp.KFW_458, stichtag), measure)
        result = calculate_kfw458(
            foerderfaehige_kosten,
            haushaltsjahreseinkommen,
            ist_selbstnutzer,
            kind_im_haushalt=kind_im_haushalt,
            alte_heizung_art=measure.alte_heizung_art,
            alte_heizung_inbetriebnahme=measure.alte_heizung_inbetriebnahme,
            alte_heizung_funktionstuechtig=measure.alte_heizung_funktionstuechtig,
            stichtag=stichtag,
        )
    check_ein_programm_pro_massnahme(db, measure.id, ProgrammTyp.KFW_458)
    _upsert_case_funding(
        db,
        case,
        ProgrammTyp.KFW_458,
        result["foerderbetrag"],
        result["regelversion"],
        result["regel_hash"],
        measure_id=measure.id,
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
    measure_id: uuid.UUID,
    stichtag: date | None = None,
) -> dict:
    case = get_case(db, case_id, current_user)
    measure = _get_measure_im_fall(db, case, measure_id)
    stichtag = _stichtag_fuer(case, stichtag)
    with _berechnungsfehler_als_422():
        _check_massnahmentyp(ruleset.waehle_regelsatz(ProgrammTyp.BEG_EM, stichtag), measure)
        result = calculate_beg_em(
            foerderfaehige_kosten,
            hat_isfp,
            fachplanung_kosten,
            energieberatung_kosten,
            ist_mfh,
            stichtag=stichtag,
        )
    check_ein_programm_pro_massnahme(db, measure.id, ProgrammTyp.BEG_EM)
    _upsert_case_funding(
        db,
        case,
        ProgrammTyp.BEG_EM,
        result["foerderbetrag"],
        result["regelversion"],
        result["regel_hash"],
        measure_id=measure.id,
        foerderfaehige_kosten=foerderfaehige_kosten,
    )
    return result
