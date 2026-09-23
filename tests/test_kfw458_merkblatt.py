"""KfW 458 gegen das Merkblatt Zuschuss 458, Stand 07/2026 (gueltig ab 21.07.2026).

Sollwerte aus dem Merkblatt, nicht aus dem Code abgeleitet:
- Klima- und Einkommensbonus nur fuer Selbstnutzer (S. 3)
- Klimabonus nur beim Tausch einer funktionstuechtigen Oel-/Kohle-/Gas-Etagen-/
  Nachtspeicherheizung (Alter egal) oder Gas-/Biomasseheizung >= 20 Jahre (S. 3)
- 80-%-Obergrenze nur bis 30.000 EUR, mit Familienzuschlag bis 40.000 EUR;
  Familienzuschlag verschiebt auch die Einkommensbonus-Grenzen um 10.000 EUR (S. 3/4)
- Mindestinvestition 300 EUR (S. 2)
- fuer dieselben Kosten nur ein Antrag, KfW ODER BAFA (S. 9)
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.funding import ProgrammTyp
from app.models.measure import AltheizungArt
from app.modules.funding import ruleset
from app.modules.funding.service import _klimabonus_berechtigt, check_ein_programm_pro_massnahme
from tests.test_funding import (
    OEL_JSON,
    _beg_em,
    _create_case,
    _create_case_with_measure,
    _create_measure,
    _kfw,
)

# Gasheizung, 15 Jahre vor dem Test-Stichtag 01.09.2026 in Betrieb genommen -> kein Klimabonus
GAS_15_JAHRE = {
    "alte_heizung_art": "gas",
    "alte_heizung_inbetriebnahme": "2011-09-01",
    "alte_heizung_funktionstuechtig": True,
}


def _berechne(client, auth_headers, altheizung=OEL_JSON, **felder):
    case, measure_id = _create_case_with_measure(client, auth_headers, altheizung=altheizung)
    return _kfw(client, auth_headers, case["id"], measure_id, **felder)


def _ok(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()


# --- T1-T5: Sollwerte aus dem Auftrag ------------------------------------------


def test_t1_selbstnutzer_25000_klimabonus_kappung_80(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers,
        foerderfaehige_kosten="35000", haushaltsjahreseinkommen=25000, ist_selbstnutzer=True,
    ))
    assert body["foerderquote"] == "0.80"  # 30 + 16 + 40 = 86 -> 80
    assert body["foerderfaehige_kosten_gedeckelt"] == "28000"
    assert body["foerderbetrag"] == "22400.00"
    assert body["klimabonus_angewendet"] is True
    assert body["einkommensbonus"] == "0.40"
    assert body["max_quote"] == "0.80"


def test_t2_selbstnutzer_35000_ohne_kind_kappung_70(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers,
        foerderfaehige_kosten="28000", haushaltsjahreseinkommen=35000, ist_selbstnutzer=True,
    ))
    assert body["foerderquote"] == "0.70"  # 30 + 16 + 30 = 76 -> 70
    assert body["foerderbetrag"] == "19601.00"  # ABSICHTLICH FALSCH: CI-Rot-Nachweis, wird revertiert
    assert body["einkommensbonus"] == "0.30"
    assert body["max_quote"] == "0.70"


def test_t3_nicht_selbstnutzer_nur_grundfoerderung(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers, altheizung=None,
        foerderfaehige_kosten="28000", ist_selbstnutzer=False,
    ))
    assert body["foerderquote"] == "0.30"
    assert body["foerderbetrag"] == "8400.00"
    assert body["klimabonus_angewendet"] is False
    assert body["einkommensbonus"] == "0"


def test_t4_gasheizung_15_jahre_kein_klimabonus(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers, altheizung=GAS_15_JAHRE,
        foerderfaehige_kosten="28000", haushaltsjahreseinkommen=80000, ist_selbstnutzer=True,
    ))
    assert body["foerderquote"] == "0.30"
    assert body["foerderbetrag"] == "8400.00"
    assert body["klimabonus_angewendet"] is False


def test_t5_selbstnutzer_45000_klimabonus(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers,
        foerderfaehige_kosten="20000", haushaltsjahreseinkommen=45000, ist_selbstnutzer=True,
    ))
    assert body["foerderquote"] == "0.56"  # 30 + 16 + 10
    assert body["foerderbetrag"] == "11200.00"


# --- T6: Degression ab 01.02.2027 -> Regelsatz endet am 31.01.2027 --------------


def test_t6_stichtag_ab_degression_hat_keinen_regelsatz(client, auth_headers):
    response = _berechne(
        client, auth_headers,
        foerderfaehige_kosten="28000", ist_selbstnutzer=False, stichtag="2027-02-01",
    )
    assert response.status_code == 422
    assert "Kein gueltiger Regelsatz" in response.json()["detail"]


def test_t6b_letzter_gueltiger_tag_31_01_2027(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers,
        foerderfaehige_kosten="28000", ist_selbstnutzer=False, stichtag="2027-01-31",
    ))
    assert body["foerderbetrag"] == "8400.00"


# --- T7: ein Antrag pro Kosten (KfW ODER BAFA) ----------------------------------


def test_t7_zweites_programm_auf_derselben_massnahme_wird_abgelehnt(client, auth_headers):
    case, measure_id = _create_case_with_measure(client, auth_headers)
    kfw = _kfw(
        client, auth_headers, case["id"], measure_id,
        foerderfaehige_kosten="10000", ist_selbstnutzer=False,
    )
    assert kfw.status_code == 200

    # Unabhaengig von der Summe: BEG EM auf derselben Waermepumpe scheitert
    # schon an der Typpruefung (Waermeerzeuger nur KfW 458).
    beg_em = _beg_em(client, auth_headers, case["id"], measure_id, foerderfaehige_kosten="1000")
    assert beg_em.status_code == 422


def test_t7b_schutz_ein_programm_pro_massnahme_gibt_409(client, auth_headers, db_session):
    # Per API nicht erreichbar, solange die Typlisten disjunkt sind - der Schutz
    # greift, falls sich die Listen in einem kuenftigen Regelsatz ueberschneiden.
    case, measure_id = _create_case_with_measure(client, auth_headers)
    _ok(_kfw(
        client, auth_headers, case["id"], measure_id,
        foerderfaehige_kosten="10000", ist_selbstnutzer=False,
    ))

    with pytest.raises(HTTPException) as exc:
        check_ein_programm_pro_massnahme(db_session, uuid.UUID(measure_id), ProgrammTyp.BEG_EM)
    assert exc.value.status_code == 409


def test_t7c_gleiches_programm_erneut_berechnen_ist_upsert(client, auth_headers):
    case, measure_id = _create_case_with_measure(client, auth_headers)
    for kosten in ("10000", "12000"):
        _ok(_kfw(
            client, auth_headers, case["id"], measure_id,
            foerderfaehige_kosten=kosten, ist_selbstnutzer=False,
        ))

    entries = client.get(f"/cases/{case['id']}", headers=auth_headers).json()["funding_entries"]
    assert len(entries) == 1
    assert entries[0]["foerderbetrag"] == "3600.00"  # 12000 * 30 %


# --- T8: Typpruefung in beide Richtungen ----------------------------------------


def test_t8_beg_em_auf_waermepumpe_wird_abgelehnt(client, auth_headers):
    case, measure_id = _create_case_with_measure(client, auth_headers)
    response = _beg_em(client, auth_headers, case["id"], measure_id, foerderfaehige_kosten="10000")
    assert response.status_code == 422


def test_t8b_kfw458_auf_daemmung_wird_abgelehnt(client, auth_headers):
    case, measure_id = _create_case_with_measure(client, auth_headers, typ="daemmung")
    response = _kfw(
        client, auth_headers, case["id"], measure_id,
        foerderfaehige_kosten="10000", haushaltsjahreseinkommen=25000, ist_selbstnutzer=False,
    )
    assert response.status_code == 422
    assert "daemmung" in response.text


@pytest.mark.parametrize("typ", ["pv_speicher", "baubegleitung"])
def test_t8c_typen_ohne_programm_werden_von_beiden_abgelehnt(client, auth_headers, typ):
    # D4: aus der Foerderlandschaft abgeleitet, nicht gegen die Richtlinie geprueft.
    case, measure_id = _create_case_with_measure(client, auth_headers, typ=typ)
    kfw = _kfw(
        client, auth_headers, case["id"], measure_id,
        foerderfaehige_kosten="10000", ist_selbstnutzer=False,
    )
    beg_em = _beg_em(client, auth_headers, case["id"], measure_id, foerderfaehige_kosten="10000")
    assert kfw.status_code == 422
    assert beg_em.status_code == 422


# --- T9: Familienzuschlag (+10.000 EUR auf alle Einkommensgrenzen) --------------


def test_t9a_mit_kind_35000_wie_25000(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers,
        foerderfaehige_kosten="28000", haushaltsjahreseinkommen=35000,
        ist_selbstnutzer=True, kind_im_haushalt=True,
    ))
    assert body["einkommensbonus"] == "0.40"
    assert body["max_quote"] == "0.80"
    assert body["foerderquote"] == "0.80"  # 30 + 16 + 40 = 86 -> 80
    assert body["foerderbetrag"] == "22400.00"


def test_t9b_mit_kind_45000_bleibt_bei_70(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers,
        foerderfaehige_kosten="28000", haushaltsjahreseinkommen=45000,
        ist_selbstnutzer=True, kind_im_haushalt=True,
    ))
    assert body["einkommensbonus"] == "0.30"  # Bemessung 35.000
    assert body["max_quote"] == "0.70"  # 45.000 > 40.000
    assert body["foerderquote"] == "0.70"  # 76 -> 70
    assert body["foerderbetrag"] == "19600.00"


def test_t9c_kind_verschiebt_einkommensbonus_stufe(client, auth_headers):
    mit_kind = _ok(_berechne(
        client, auth_headers, altheizung=GAS_15_JAHRE,
        foerderfaehige_kosten="20000", haushaltsjahreseinkommen=55000,
        ist_selbstnutzer=True, kind_im_haushalt=True,
    ))
    ohne_kind = _ok(_berechne(
        client, auth_headers, altheizung=GAS_15_JAHRE,
        foerderfaehige_kosten="20000", haushaltsjahreseinkommen=55000,
        ist_selbstnutzer=True, kind_im_haushalt=False,
    ))
    assert mit_kind["foerderquote"] == "0.40"  # 30 + 10 (Bemessung 45.000)
    assert mit_kind["foerderbetrag"] == "8000.00"
    assert ohne_kind["foerderquote"] == "0.30"
    assert ohne_kind["foerderbetrag"] == "6000.00"


# --- T10: Mindestinvestition 300 EUR --------------------------------------------


@pytest.mark.parametrize(("kosten", "betrag"), [("299", "0.00"), ("300", "90.00")])
def test_t10_mindestinvestition_300(client, auth_headers, kosten, betrag):
    body = _ok(_berechne(
        client, auth_headers, foerderfaehige_kosten=kosten, ist_selbstnutzer=False,
    ))
    assert body["foerderbetrag"] == betrag


# --- T11/T12/T19: Pflichtangaben ------------------------------------------------


def test_t11_selbstnutzer_ohne_einkommen_gibt_422(client, auth_headers):
    response = _berechne(client, auth_headers, foerderfaehige_kosten="10000", ist_selbstnutzer=True)
    assert response.status_code == 422
    assert "haushaltsjahreseinkommen" in response.text


def test_t12_selbstnutzer_ohne_altheizung_gibt_422(client, auth_headers):
    response = _berechne(
        client, auth_headers, altheizung=None,
        foerderfaehige_kosten="10000", haushaltsjahreseinkommen=25000, ist_selbstnutzer=True,
    )
    assert response.status_code == 422
    assert "alte_heizung" in response.text


def test_t19_ohne_ist_selbstnutzer_gibt_422(client, auth_headers):
    response = _berechne(
        client, auth_headers, foerderfaehige_kosten="10000", haushaltsjahreseinkommen=25000,
    )
    assert response.status_code == 422


# --- T13-T15: Klimabonus-Voraussetzungen ----------------------------------------


def test_t13_nicht_funktionstuechtige_oelheizung_kein_klimabonus(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers, altheizung={**OEL_JSON, "alte_heizung_funktionstuechtig": False},
        foerderfaehige_kosten="28000", haushaltsjahreseinkommen=80000, ist_selbstnutzer=True,
    ))
    assert body["foerderquote"] == "0.30"
    assert body["foerderbetrag"] == "8400.00"


@pytest.mark.parametrize(
    ("stichtag", "klimabonus", "betrag"),
    [("2026-08-01", True, "12880.00"), ("2026-07-31", False, "8400.00")],
)
def test_t14_gasheizung_genau_20_jahre(client, auth_headers, stichtag, klimabonus, betrag):
    gas = {**GAS_15_JAHRE, "alte_heizung_inbetriebnahme": "2006-08-01"}
    body = _ok(_berechne(
        client, auth_headers, altheizung=gas,
        foerderfaehige_kosten="28000", haushaltsjahreseinkommen=80000,
        ist_selbstnutzer=True, stichtag=stichtag,
    ))
    assert body["klimabonus_angewendet"] is klimabonus
    assert body["foerderbetrag"] == betrag


@pytest.mark.parametrize(
    ("stichtag", "erwartet"),
    [(date(2024, 2, 28), False), (date(2024, 2, 29), True), (date(2024, 3, 1), True)],
)
def test_t14b_inbetriebnahme_am_29_februar(stichtag, erwartet):
    # 2024 ist ein Schaltjahr: der 20. Jahrestag des 29.02.2004 ist der 29.02.2024.
    # Am 28.02.2024 liegen erst 19 Jahre und 364 Tage zurueck -> nein; ab dem
    # Jahrestag sind es "mindestens 20 Jahre" -> ja. Direkt an der Hilfsfunktion
    # getestet, weil fuer 2024 kein Regelsatz existiert.
    regeln = ruleset.waehle_regelsatz(ProgrammTyp.KFW_458, date(2026, 9, 1)).regeln
    assert _klimabonus_berechtigt(
        regeln, AltheizungArt.GAS, date(2004, 2, 29), True, stichtag
    ) is erwartet


def test_t14c_29_februar_im_nicht_schaltjahr():
    # Jahrestag faellt auf ein Nicht-Schaltjahr: 21 Jahre sind erst mit Ablauf des
    # 28.02.2025 vollendet (BGB § 188 Abs. 3), also ab 01.03.2025 -> dort ja.
    regeln = ruleset.waehle_regelsatz(ProgrammTyp.KFW_458, date(2026, 9, 1)).regeln
    regeln = regeln.model_copy(update={"klimabonus_mindestalter_jahre": 21})
    assert _klimabonus_berechtigt(regeln, AltheizungArt.GAS, date(2004, 2, 29), True, date(2025, 2, 28)) is False
    assert _klimabonus_berechtigt(regeln, AltheizungArt.GAS, date(2004, 2, 29), True, date(2025, 3, 1)) is True


def test_t15_sonstige_heizart_kein_klimabonus(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers, altheizung={**OEL_JSON, "alte_heizung_art": "sonstige"},
        foerderfaehige_kosten="28000", haushaltsjahreseinkommen=80000, ist_selbstnutzer=True,
    ))
    assert body["foerderquote"] == "0.30"
    assert body["foerderbetrag"] == "8400.00"


# --- Nicht-Selbstnutzer brauchen weder Einkommen noch Altheizung -----------------


def test_nicht_selbstnutzer_ignoriert_einkommen_und_kind(client, auth_headers):
    body = _ok(_berechne(
        client, auth_headers,
        foerderfaehige_kosten="28000", haushaltsjahreseinkommen=10000,
        ist_selbstnutzer=False, kind_im_haushalt=True,
    ))
    assert body["foerderquote"] == "0.30"
    assert body["einkommensbonus"] == "0"
    assert body["max_quote"] == "0.70"


def test_zweite_massnahme_im_fall_mit_eigener_altheizung(client, auth_headers):
    # Altheizung haengt an der Massnahme, nicht am Fall.
    case = _create_case(client, auth_headers)
    measure_id = _create_measure(client, auth_headers, case["id"], altheizung=GAS_15_JAHRE)
    body = _ok(_kfw(
        client, auth_headers, case["id"], measure_id,
        foerderfaehige_kosten="28000", haushaltsjahreseinkommen=80000, ist_selbstnutzer=True,
    ))
    assert body["klimabonus_angewendet"] is False


def test_t14d_stichtag_29_februar_zieljahr_ohne_schaltjahr():
    # Stichtag 29.02.2024, 21 Jahre zurueck: 2003 hat keinen 29.02. -> Grenze 28.02.2003.
    # Eine am 28.02.2003 begonnene 21-Jahres-Frist ist am 28.02.2024 vollendet (ja),
    # eine am 01.03.2003 begonnene erst am 01.03.2024 (nein).
    regeln = ruleset.waehle_regelsatz(ProgrammTyp.KFW_458, date(2026, 9, 1)).regeln
    regeln = regeln.model_copy(update={"klimabonus_mindestalter_jahre": 21})
    stichtag = date(2024, 2, 29)
    assert _klimabonus_berechtigt(regeln, AltheizungArt.GAS, date(2003, 2, 28), True, stichtag) is True
    assert _klimabonus_berechtigt(regeln, AltheizungArt.GAS, date(2003, 3, 1), True, stichtag) is False


def test_massnahme_aus_anderem_fall_gibt_404(client, auth_headers):
    _, fremde_measure_id = _create_case_with_measure(client, auth_headers)
    case = _create_case(client, auth_headers)
    response = _kfw(
        client, auth_headers, case["id"], fremde_measure_id,
        foerderfaehige_kosten="10000", ist_selbstnutzer=False,
    )
    assert response.status_code == 404
