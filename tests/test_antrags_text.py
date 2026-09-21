from app.llm.client import Antragstexte, LLMAufrufFehler


def _create_case_with_measure(client, auth_headers) -> tuple[str, str]:
    prop = client.post(
        "/property",
        json={
            "person": {"name": "Testperson", "kontakt": "test@example.com"},
            "building": {"adresse": "Teststrasse 1", "baujahr": 1998, "wohneinheiten": 3},
            "ownership": {"von": "2020-01-01"},
        },
        headers=auth_headers,
    ).json()
    case = client.post(
        "/cases",
        json={"building_id": prop["building_id"], "ownership_id": prop["ownership_id"]},
        headers=auth_headers,
    ).json()
    measure = client.post(
        f"/cases/{case['id']}/measures",
        json={"typ": "daemmung"},
        headers=auth_headers,
    ).json()
    return case["id"], measure["id"]


def _mock_generate(monkeypatch, massnahmenbeschreibung="Entwurf Beschreibung", energetischer_mehrwert="Entwurf Mehrwert"):
    monkeypatch.setattr(
        "app.modules.documents.antrags_text_service.generate_antragstexte",
        lambda fall: Antragstexte(
            massnahmenbeschreibung=massnahmenbeschreibung, energetischer_mehrwert=energetischer_mehrwert
        ),
    )


def test_generate_erzeugt_entwurf_mit_freigegeben_false(client, auth_headers, monkeypatch):
    _mock_generate(monkeypatch)
    case_id, measure_id = _create_case_with_measure(client, auth_headers)

    response = client.post(
        f"/cases/{case_id}/texts/generate", json={"measure_id": measure_id}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["massnahmenbeschreibung_entwurf"] == "Entwurf Beschreibung"
    assert body["energetischer_mehrwert_entwurf"] == "Entwurf Mehrwert"
    assert body["freigegeben"] is False


def test_review_ohne_vorherigen_entwurf_gibt_404(client, auth_headers):
    case_id, measure_id = _create_case_with_measure(client, auth_headers)

    response = client.post(
        f"/cases/{case_id}/texts/review",
        json={
            "measure_id": measure_id,
            "massnahmenbeschreibung": "x",
            "energetischer_mehrwert": "y",
        },
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_review_setzt_bearbeitete_endfassung_und_freigabe(client, auth_headers, monkeypatch):
    _mock_generate(monkeypatch)
    case_id, measure_id = _create_case_with_measure(client, auth_headers)
    client.post(f"/cases/{case_id}/texts/generate", json={"measure_id": measure_id}, headers=auth_headers)

    response = client.post(
        f"/cases/{case_id}/texts/review",
        json={
            "measure_id": measure_id,
            "massnahmenbeschreibung": "Vom Berater bearbeitete Beschreibung",
            "energetischer_mehrwert": "Entwurf Mehrwert",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["massnahmenbeschreibung_final"] == "Vom Berater bearbeitete Beschreibung"
    assert body["freigegeben"] is True
    assert body["reviewed_by_id"] is not None
    assert body["reviewed_at"] is not None


def test_export_vor_freigabe_gibt_409(client, auth_headers, monkeypatch):
    _mock_generate(monkeypatch)
    case_id, measure_id = _create_case_with_measure(client, auth_headers)
    client.post(f"/cases/{case_id}/texts/generate", json={"measure_id": measure_id}, headers=auth_headers)

    response = client.get(f"/cases/{case_id}/texts/export?measure_id={measure_id}", headers=auth_headers)
    assert response.status_code == 409


def test_export_nach_freigabe_gibt_finalen_text(client, auth_headers, monkeypatch):
    _mock_generate(monkeypatch)
    case_id, measure_id = _create_case_with_measure(client, auth_headers)
    client.post(f"/cases/{case_id}/texts/generate", json={"measure_id": measure_id}, headers=auth_headers)
    client.post(
        f"/cases/{case_id}/texts/review",
        json={
            "measure_id": measure_id,
            "massnahmenbeschreibung": "Finale Beschreibung",
            "energetischer_mehrwert": "Finaler Mehrwert",
        },
        headers=auth_headers,
    )

    response = client.get(f"/cases/{case_id}/texts/export?measure_id={measure_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["massnahmenbeschreibung_final"] == "Finale Beschreibung"
    assert body["freigegeben"] is True


def test_erneute_generierung_setzt_freigabe_zurueck(client, auth_headers, monkeypatch):
    _mock_generate(monkeypatch)
    case_id, measure_id = _create_case_with_measure(client, auth_headers)
    client.post(f"/cases/{case_id}/texts/generate", json={"measure_id": measure_id}, headers=auth_headers)
    client.post(
        f"/cases/{case_id}/texts/review",
        json={
            "measure_id": measure_id,
            "massnahmenbeschreibung": "Finale Beschreibung",
            "energetischer_mehrwert": "Finaler Mehrwert",
        },
        headers=auth_headers,
    )

    # Neuer Entwurf entwertet die vorherige Freigabe.
    _mock_generate(monkeypatch, massnahmenbeschreibung="Neuer Entwurf")
    response = client.post(
        f"/cases/{case_id}/texts/generate", json={"measure_id": measure_id}, headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["freigegeben"] is False

    export_response = client.get(
        f"/cases/{case_id}/texts/export?measure_id={measure_id}", headers=auth_headers
    )
    assert export_response.status_code == 409


def test_generate_bei_llm_fehler_gibt_502(client, auth_headers, monkeypatch):
    def _fehlschlag(fall):
        raise LLMAufrufFehler("OpenAI nicht erreichbar")

    monkeypatch.setattr("app.modules.documents.antrags_text_service.generate_antragstexte", _fehlschlag)
    case_id, measure_id = _create_case_with_measure(client, auth_headers)

    response = client.post(
        f"/cases/{case_id}/texts/generate", json={"measure_id": measure_id}, headers=auth_headers
    )
    assert response.status_code == 502


def test_export_pdf_gibt_gueltiges_pdf_zurueck(client, auth_headers, monkeypatch):
    _mock_generate(monkeypatch)
    case_id, measure_id = _create_case_with_measure(client, auth_headers)
    client.post(f"/cases/{case_id}/texts/generate", json={"measure_id": measure_id}, headers=auth_headers)
    client.post(
        f"/cases/{case_id}/texts/review",
        json={
            "measure_id": measure_id,
            "massnahmenbeschreibung": "Finale Beschreibung für den PDF-Beleg",
            "energetischer_mehrwert": "Finaler Mehrwert für den PDF-Beleg",
        },
        headers=auth_headers,
    )

    response = client.get(
        f"/cases/{case_id}/texts/export/pdf?measure_id={measure_id}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 500


def test_export_pdf_vor_freigabe_gibt_409(client, auth_headers, monkeypatch):
    _mock_generate(monkeypatch)
    case_id, measure_id = _create_case_with_measure(client, auth_headers)
    client.post(f"/cases/{case_id}/texts/generate", json={"measure_id": measure_id}, headers=auth_headers)

    response = client.get(
        f"/cases/{case_id}/texts/export/pdf?measure_id={measure_id}", headers=auth_headers
    )
    assert response.status_code == 409
