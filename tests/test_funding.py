import uuid
from decimal import Decimal

from app.models.funding import FundingHistory
from app.modules.funding.service import calculate_beg_em, calculate_kfw458


def test_niedriges_einkommen_selbstnutzer_erreicht_maximalquote_80():
    result = calculate_kfw458(
        foerderfaehige_kosten=Decimal("10000"),
        haushaltsjahreseinkommen=25_000,
        ist_selbstnutzer=True,
    )
    # 30 + 16 + 40 = 86 %, gekappt bei 80 % (Selbstnutzer, Einkommen <= 40.000)
    assert result["foerderquote"] == Decimal("0.80")
    assert result["foerderbetrag"] == Decimal("8000.00")


def test_hohes_einkommen_kein_einkommensbonus_kappung_bei_70():
    result = calculate_kfw458(
        foerderfaehige_kosten=Decimal("10000"),
        haushaltsjahreseinkommen=100_000,
        ist_selbstnutzer=True,
    )
    # 30 + 16 + 0 = 46 %, unter beiden Obergrenzen -> keine Kappung noetig
    assert result["foerderquote"] == Decimal("0.46")
    assert result["foerderbetrag"] == Decimal("4600.00")


def test_nicht_selbstnutzer_kappung_bei_70_trotz_niedrigem_einkommen():
    result = calculate_kfw458(
        foerderfaehige_kosten=Decimal("10000"),
        haushaltsjahreseinkommen=25_000,
        ist_selbstnutzer=False,
    )
    # 30 + 16 + 40 = 86 %, aber kein Selbstnutzer -> nur 70 %-Obergrenze gilt
    assert result["foerderquote"] == Decimal("0.70")
    assert result["foerderbetrag"] == Decimal("7000.00")


def test_kosten_ueber_deckel_werden_bei_28000_gekappt():
    result = calculate_kfw458(
        foerderfaehige_kosten=Decimal("50000"),
        haushaltsjahreseinkommen=100_000,
        ist_selbstnutzer=True,
    )
    assert result["foerderfaehige_kosten_gedeckelt"] == Decimal("28000")
    assert result["foerderbetrag"] == Decimal("12880.00")  # 28000 * 0.46


def test_regelversion_und_hash_sind_gesetzt():
    result = calculate_kfw458(
        foerderfaehige_kosten=Decimal("1000"),
        haushaltsjahreseinkommen=100_000,
        ist_selbstnutzer=True,
    )
    assert result["regelversion"] == "kfw458-2026-07-21"
    assert len(result["regel_hash"]) == 64  # sha256 hex


def test_kfw458_endpoint_speichert_case_funding_eintrag(client, auth_headers):
    prop = client.post(
        "/property",
        json={
            "person": {"name": "Testperson", "kontakt": "test@example.com"},
            "building": {"adresse": "Teststrasse 1"},
            "ownership": {"von": "2020-01-01"},
        },
        headers=auth_headers,
    ).json()
    case = client.post(
        "/cases",
        json={"building_id": prop["building_id"], "ownership_id": prop["ownership_id"]},
        headers=auth_headers,
    ).json()

    response = client.post(
        f"/cases/{case['id']}/funding/kfw-458",
        json={
            "foerderfaehige_kosten": "10000",
            "haushaltsjahreseinkommen": 25000,
            "ist_selbstnutzer": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["foerderquote"] == "0.80"
    assert body["regelversion"] == "kfw458-2026-07-21"

    updated_case = client.get(f"/cases/{case['id']}", headers=auth_headers).json()
    assert len(updated_case["funding_entries"]) == 1
    entry = updated_case["funding_entries"][0]
    assert entry["programm"] == "kfw_458"
    assert entry["regelversion"] == "kfw458-2026-07-21"
    assert entry["regel_hash"] == body["regel_hash"]


def test_kfw458_neuberechnung_ersetzt_statt_anzuhaengen(client, auth_headers):
    prop = client.post(
        "/property",
        json={
            "person": {"name": "Testperson", "kontakt": "test@example.com"},
            "building": {"adresse": "Teststrasse 1"},
            "ownership": {"von": "2020-01-01"},
        },
        headers=auth_headers,
    ).json()
    case = client.post(
        "/cases",
        json={"building_id": prop["building_id"], "ownership_id": prop["ownership_id"]},
        headers=auth_headers,
    ).json()

    for kosten in ("10000", "20000"):
        client.post(
            f"/cases/{case['id']}/funding/kfw-458",
            json={
                "foerderfaehige_kosten": kosten,
                "haushaltsjahreseinkommen": 25000,
                "ist_selbstnutzer": True,
            },
            headers=auth_headers,
        )

    updated_case = client.get(f"/cases/{case['id']}", headers=auth_headers).json()
    assert len(updated_case["funding_entries"]) == 1
    assert updated_case["funding_entries"][0]["foerderbetrag"] == "16000.00"  # 20000 * 0.80


def test_rulesets_endpoint_listet_kfw458(client, auth_headers):
    response = client.get("/funding/rulesets", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert any(r["regelversion"] == "kfw458-2026-07-21" for r in body)


def _create_case(client, auth_headers) -> dict:
    prop = client.post(
        "/property",
        json={
            "person": {"name": "Testperson", "kontakt": "test@example.com"},
            "building": {"adresse": "Teststrasse 1"},
            "ownership": {"von": "2020-01-01"},
        },
        headers=auth_headers,
    ).json()
    return client.post(
        "/cases",
        json={"building_id": prop["building_id"], "ownership_id": prop["ownership_id"]},
        headers=auth_headers,
    ).json()


def test_beg_em_ohne_isfp_grundfoerderung_15_prozent():
    result = calculate_beg_em(foerderfaehige_kosten=Decimal("10000"), hat_isfp=False)
    assert result["grundfoerderung_betrag"] == Decimal("1500.00")
    assert result["isfp_bonus_betrag"] == Decimal("0.00")
    assert result["foerderbetrag"] == Decimal("1500.00")


def test_beg_em_isfp_bonus_nur_auf_marginalen_anteil_ueber_30000():
    result = calculate_beg_em(foerderfaehige_kosten=Decimal("40000"), hat_isfp=True)
    # Grundfoerderung auf volle 40000, iSFP-Bonus nur auf (40000 - 30000)
    assert result["grundfoerderung_betrag"] == Decimal("6000.00")
    assert result["isfp_bonus_betrag"] == Decimal("500.00")  # 10000 * 5 %
    assert result["foerderbetrag"] == Decimal("6500.00")


def test_beg_em_ohne_isfp_deckel_bei_30000():
    result = calculate_beg_em(foerderfaehige_kosten=Decimal("50000"), hat_isfp=False)
    assert result["foerderfaehige_kosten_gedeckelt"] == Decimal("30000")
    assert result["foerderbetrag"] == Decimal("4500.00")


def test_beg_em_mit_isfp_deckel_bei_60000():
    result = calculate_beg_em(foerderfaehige_kosten=Decimal("70000"), hat_isfp=True)
    assert result["foerderfaehige_kosten_gedeckelt"] == Decimal("60000")
    assert result["grundfoerderung_betrag"] == Decimal("9000.00")
    assert result["isfp_bonus_betrag"] == Decimal("1500.00")  # 30000 * 5 %
    assert result["foerderbetrag"] == Decimal("10500.00")


def test_beg_em_unter_mindestinvestition_keine_foerderung():
    result = calculate_beg_em(foerderfaehige_kosten=Decimal("200"), hat_isfp=False)
    assert result["foerderbetrag"] == Decimal("0.00")


def test_beg_em_fachplanung_wird_bei_2500_gedeckelt():
    result = calculate_beg_em(
        foerderfaehige_kosten=Decimal("10000"), hat_isfp=False, fachplanung_kosten=Decimal("10000")
    )
    assert result["fachplanung_foerderbetrag"] == Decimal("2500")


def test_beg_em_energieberatung_deckel_efh_vs_mfh():
    efh = calculate_beg_em(
        foerderfaehige_kosten=Decimal("10000"),
        hat_isfp=False,
        energieberatung_kosten=Decimal("3000"),
        ist_mfh=False,
    )
    mfh = calculate_beg_em(
        foerderfaehige_kosten=Decimal("10000"),
        hat_isfp=False,
        energieberatung_kosten=Decimal("3000"),
        ist_mfh=True,
    )
    assert efh["energieberatung_foerderbetrag"] == Decimal("650")
    assert mfh["energieberatung_foerderbetrag"] == Decimal("1300")


def test_beg_em_gesamtfoerderbetrag_summiert_alle_positionen():
    result = calculate_beg_em(
        foerderfaehige_kosten=Decimal("10000"),
        hat_isfp=False,
        fachplanung_kosten=Decimal("1000"),
        energieberatung_kosten=Decimal("1000"),
    )
    # Hauptmassnahme 1500.00 + Fachplanung 500.00 + Energieberatung 500.00
    assert result["foerderbetrag"] == Decimal("2500.00")


def test_beg_em_endpoint_speichert_case_funding_eintrag(client, auth_headers):
    case = _create_case(client, auth_headers)

    response = client.post(
        f"/cases/{case['id']}/funding/beg-em",
        json={"foerderfaehige_kosten": "10000", "hat_isfp": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["foerderbetrag"] == "1500.00"

    updated_case = client.get(f"/cases/{case['id']}", headers=auth_headers).json()
    assert len(updated_case["funding_entries"]) == 1
    assert updated_case["funding_entries"][0]["programm"] == "beg_em"


def test_case_kann_kfw458_und_beg_em_gleichzeitig_haben(client, auth_headers):
    case = _create_case(client, auth_headers)

    client.post(
        f"/cases/{case['id']}/funding/kfw-458",
        json={"foerderfaehige_kosten": "10000", "haushaltsjahreseinkommen": 25000, "ist_selbstnutzer": True},
        headers=auth_headers,
    )
    client.post(
        f"/cases/{case['id']}/funding/beg-em",
        json={"foerderfaehige_kosten": "10000", "hat_isfp": False},
        headers=auth_headers,
    )

    updated_case = client.get(f"/cases/{case['id']}", headers=auth_headers).json()
    programme = {entry["programm"] for entry in updated_case["funding_entries"]}
    assert programme == {"kfw_458", "beg_em"}


def test_funding_history_wird_aus_aktueller_summe_neu_berechnet(client, auth_headers, db_session):
    prop = client.post(
        "/property",
        json={
            "person": {"name": "Testperson", "kontakt": "test@example.com"},
            "building": {"adresse": "Teststrasse 1"},
            "ownership": {"von": "2020-01-01"},
        },
        headers=auth_headers,
    ).json()
    case = client.post(
        "/cases",
        json={"building_id": prop["building_id"], "ownership_id": prop["ownership_id"]},
        headers=auth_headers,
    ).json()

    client.post(
        f"/cases/{case['id']}/funding/kfw-458",
        json={"foerderfaehige_kosten": "10000", "haushaltsjahreseinkommen": 25000, "ist_selbstnutzer": True},
        headers=auth_headers,
    )
    history = (
        db_session.query(FundingHistory)
        .filter(FundingHistory.building_id == uuid.UUID(prop["building_id"]))
        .one()
    )
    assert history.betrag == Decimal("8000.00")

    # Neuberechnung mit anderen Kosten ersetzt den Betrag, statt ihn aufzuaddieren
    client.post(
        f"/cases/{case['id']}/funding/kfw-458",
        json={"foerderfaehige_kosten": "20000", "haushaltsjahreseinkommen": 25000, "ist_selbstnutzer": True},
        headers=auth_headers,
    )
    db_session.refresh(history)
    assert history.betrag == Decimal("16000.00")
