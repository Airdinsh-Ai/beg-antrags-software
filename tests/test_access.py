import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.core.access import check_building_access
from app.models.building import Building
from app.models.ownership import Ownership
from app.models.person import Person
from app.models.user import User, UserRole


@pytest.fixture()
def building_with_owner(db_session) -> tuple[Building, Person]:
    person = Person(name="Testperson Eigentuemer")
    building = Building(adresse="Teststrasse 1")
    db_session.add_all([person, building])
    db_session.flush()
    db_session.add(Ownership(person_id=person.id, building_id=building.id, von=date(2020, 1, 1)))
    db_session.commit()
    db_session.refresh(building)
    return building, person


def test_admin_always_has_access(building_with_owner):
    building, _ = building_with_owner
    admin = User(email="a@test.example", password_hash="x", role=UserRole.ADMIN)
    check_building_access(admin, building)  # wirft nicht


def test_berater_always_has_access(building_with_owner):
    building, _ = building_with_owner
    berater = User(email="b@test.example", password_hash="x", role=UserRole.BERATER)
    check_building_access(berater, building)  # wirft nicht


def test_owner_has_access_to_own_building(building_with_owner):
    building, person = building_with_owner
    owner = User(
        email="o@test.example", password_hash="x", role=UserRole.IMMOBILIENBESITZER, person_id=person.id
    )
    check_building_access(owner, building)  # wirft nicht


def test_other_owner_has_no_access(building_with_owner):
    building, _ = building_with_owner
    other = User(
        email="c@test.example",
        password_hash="x",
        role=UserRole.IMMOBILIENBESITZER,
        person_id=uuid.uuid4(),
    )
    with pytest.raises(HTTPException) as exc_info:
        check_building_access(other, building)
    assert exc_info.value.status_code == 403


def test_fachpartner_has_no_access_in_phase_0(building_with_owner):
    building, _ = building_with_owner
    partner = User(email="f@test.example", password_hash="x", role=UserRole.FACHPARTNER)
    with pytest.raises(HTTPException) as exc_info:
        check_building_access(partner, building)
    assert exc_info.value.status_code == 403
