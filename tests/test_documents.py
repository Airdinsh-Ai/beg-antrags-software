from pathlib import Path

import pytest

from app.llm.client import EnergieausweisDaten, LLMAufrufFehler

MINI_PDF = b"%PDF-1.4\n%%EOF"


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


def _upload_energieausweis(client, auth_headers, case_id: str):
    return client.post(
        f"/cases/{case_id}/documents",
        files={"datei": ("energieausweis.pdf", MINI_PDF, "application/pdf")},
        data={"typ": "energieausweis", "retention_class": "frei_loeschbar"},
        headers=auth_headers,
    )


def test_upload_speichert_datei_und_erzeugt_eintrag(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.upload_verzeichnis", str(tmp_path))
    case = _create_case(client, auth_headers)

    response = _upload_energieausweis(client, auth_headers, case["id"])
    assert response.status_code == 201
    body = response.json()
    assert body["typ"] == "energieausweis"
    assert body["dateiname"] == "energieausweis.pdf"

    gespeicherte_dateien = list(Path(tmp_path).rglob("*energieausweis.pdf"))
    assert len(gespeicherte_dateien) == 1
    assert gespeicherte_dateien[0].read_bytes() == MINI_PDF


def test_extract_ohne_dokument_gibt_404(client, auth_headers):
    case = _create_case(client, auth_headers)
    response = client.post(f"/cases/{case['id']}/extract", headers=auth_headers)
    assert response.status_code == 404


def test_extract_bei_unlesbarem_pdf_gibt_422(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.upload_verzeichnis", str(tmp_path))
    case = _create_case(client, auth_headers)
    client.post(
        f"/cases/{case['id']}/documents",
        files={"datei": ("kaputt.pdf", b"das ist kein PDF", "application/pdf")},
        data={"typ": "energieausweis", "retention_class": "frei_loeschbar"},
        headers=auth_headers,
    )

    response = client.post(f"/cases/{case['id']}/extract", headers=auth_headers)
    assert response.status_code == 422


def test_extract_aktualisiert_building_und_gibt_werte_zurueck(
    client, auth_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr("app.core.config.settings.upload_verzeichnis", str(tmp_path))
    monkeypatch.setattr(
        "app.modules.documents.service.extract_energieausweis",
        lambda pdf: EnergieausweisDaten(
            baujahr=1998,
            wohneinheiten=4,
            energieverbrauch_kwh_pro_m2a=120.5,
            energieeffizienzklasse="C",
        ),
    )
    case = _create_case(client, auth_headers)
    _upload_energieausweis(client, auth_headers, case["id"])

    response = client.post(f"/cases/{case['id']}/extract", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["baujahr"] == 1998
    assert body["wohneinheiten"] == 4
    assert body["energieeffizienzklasse"] == "C"

    # Baujahr/Wohneinheiten wurden ins Building geschrieben.
    building_response = client.get(f"/cases/{case['id']}", headers=auth_headers)
    assert building_response.status_code == 200


def test_extract_bei_llm_fehler_gibt_502(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.upload_verzeichnis", str(tmp_path))

    def _fehlschlag(pdf):
        raise LLMAufrufFehler("OpenAI nicht erreichbar")

    monkeypatch.setattr("app.modules.documents.service.extract_energieausweis", _fehlschlag)
    case = _create_case(client, auth_headers)
    _upload_energieausweis(client, auth_headers, case["id"])

    response = client.post(f"/cases/{case['id']}/extract", headers=auth_headers)
    assert response.status_code == 502
