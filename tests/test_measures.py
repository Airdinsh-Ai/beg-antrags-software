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


def test_catalog_listet_sieben_massnahmentypen(client, auth_headers):
    response = client.get("/measures/catalog", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 7
    typen_mit_pruefung = [e["typ"] for e in body if e["machbarkeitspruefung_automatisiert"]]
    assert set(typen_mit_pruefung) == {"waermepumpe_luft", "waermepumpe_erdwaerme"}


def test_waermepumpe_mit_ausreichender_jaz_ist_machbar(client, auth_headers):
    case = _create_case(client, auth_headers)
    response = client.post(
        f"/cases/{case['id']}/measures",
        json={"typ": "waermepumpe_luft", "jaz": "3.5"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["machbar"] is True
    assert "erfuellt" in body["hinweis"]


def test_waermepumpe_mit_zu_niedriger_jaz_ist_nicht_machbar(client, auth_headers):
    case = _create_case(client, auth_headers)
    response = client.post(
        f"/cases/{case['id']}/measures",
        json={"typ": "waermepumpe_erdwaerme", "jaz": "2.7"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["machbar"] is False
    assert "unterschreitet" in body["hinweis"]


def test_waermepumpe_ohne_jaz_gibt_422(client, auth_headers):
    case = _create_case(client, auth_headers)
    response = client.post(
        f"/cases/{case['id']}/measures",
        json={"typ": "waermepumpe_luft"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_daemmung_wird_ohne_automatisierte_pruefung_gespeichert(client, auth_headers):
    case = _create_case(client, auth_headers)
    response = client.post(
        f"/cases/{case['id']}/measures",
        json={"typ": "daemmung"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["machbar"] is None
    assert "nicht automatisiert" in body["hinweis"]
