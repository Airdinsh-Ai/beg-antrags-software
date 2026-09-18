from datetime import date

from app.models.building import Building
from app.models.ownership import Ownership
from app.models.person import Person


def test_person_name_is_nullable_for_anonymization(db_session):
    person = Person(name="Testperson 1", kontakt="test@example.com")
    db_session.add(person)
    db_session.commit()

    person.name = None
    db_session.commit()
    db_session.refresh(person)

    assert person.name is None
    assert person.kontakt == "test@example.com"


def test_ownership_links_person_and_building(db_session):
    person = Person(name="Testperson 2")
    building = Building(adresse="Musterstrasse 1, 12345 Musterstadt")
    db_session.add_all([person, building])
    db_session.flush()

    ownership = Ownership(person_id=person.id, building_id=building.id, von=date(2020, 1, 1))
    db_session.add(ownership)
    db_session.commit()

    assert ownership in person.ownerships
    assert ownership in building.ownerships
