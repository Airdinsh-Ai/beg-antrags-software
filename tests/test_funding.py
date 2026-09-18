from decimal import Decimal

from app.modules.funding.service import calculate_kfw458


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


def test_calculate_endpoint_speichert_regelversion_am_case(client, auth_headers):
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
        f"/cases/{case['id']}/funding/calculate",
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
    assert updated_case["regelversion"] == "kfw458-2026-07-21"
    assert updated_case["regel_hash"] == body["regel_hash"]


def test_rulesets_endpoint_listet_kfw458(client, auth_headers):
    response = client.get("/funding/rulesets", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert any(r["regelversion"] == "kfw458-2026-07-21" for r in body)
