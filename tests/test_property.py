import uuid

from app.models.person import Person
from app.models.user import User, UserRole


def _create_property(client, auth_headers) -> dict:
    payload = {
        "person": {"name": "Testperson 1", "kontakt": "test@example.com"},
        "building": {"adresse": "Musterstrasse 1, 12345 Musterstadt", "baujahr": 1998, "wohneinheiten": 3},
        "ownership": {"von": "2020-01-01"},
    }
    response = client.post("/property", json=payload, headers=auth_headers)
    assert response.status_code == 201
    return response.json()


def test_create_property_returns_three_ids(client, auth_headers):
    body = _create_property(client, auth_headers)
    assert uuid.UUID(body["person_id"])
    assert uuid.UUID(body["building_id"])
    assert uuid.UUID(body["ownership_id"])


def test_create_case_for_existing_property(client, auth_headers):
    prop = _create_property(client, auth_headers)
    response = client.post(
        "/cases",
        json={"building_id": prop["building_id"], "ownership_id": prop["ownership_id"]},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "angelegt"
    assert body["building_id"] == prop["building_id"]


def test_create_case_with_unknown_building_returns_404(client, auth_headers):
    response = client.post(
        "/cases",
        json={"building_id": str(uuid.uuid4()), "ownership_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_get_case_returns_it(client, auth_headers):
    prop = _create_property(client, auth_headers)
    created = client.post(
        "/cases",
        json={"building_id": prop["building_id"], "ownership_id": prop["ownership_id"]},
        headers=auth_headers,
    ).json()

    response = client.get(f"/cases/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_case_unknown_id_returns_404(client, auth_headers):
    response = client.get(f"/cases/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404


def test_get_case_as_unrelated_owner_returns_403(client, auth_headers, db_session):
    prop = _create_property(client, auth_headers)
    case = client.post(
        "/cases",
        json={"building_id": prop["building_id"], "ownership_id": prop["ownership_id"]},
        headers=auth_headers,
    ).json()

    other_person = Person(name="Fremde Person")
    db_session.add(other_person)
    db_session.flush()
    other_owner = User(
        email="fremd@test.example",
        password_hash="x",
        role=UserRole.IMMOBILIENBESITZER,
        person_id=other_person.id,
    )
    db_session.add(other_owner)
    db_session.commit()

    from app.core.security import create_access_token

    token = create_access_token(subject=str(other_owner.id))
    response = client.get(
        f"/cases/{case['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
