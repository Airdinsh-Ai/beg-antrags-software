import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.access import check_building_access, check_case_access
from app.models.building import Building
from app.models.case import Case
from app.models.ownership import Ownership
from app.models.person import Person
from app.models.user import User
from app.schemas.property import CaseCreateRequest, PropertyCreateRequest


def create_property(db: Session, data: PropertyCreateRequest) -> tuple[Person, Building, Ownership]:
    person = Person(name=data.person.name, kontakt=data.person.kontakt)
    building = Building(
        adresse=data.building.adresse,
        baujahr=data.building.baujahr,
        wohneinheiten=data.building.wohneinheiten,
    )
    db.add_all([person, building])
    db.flush()

    ownership = Ownership(
        person_id=person.id,
        building_id=building.id,
        von=data.ownership.von,
        bis=data.ownership.bis,
    )
    db.add(ownership)
    db.commit()
    db.refresh(person)
    db.refresh(building)
    db.refresh(ownership)
    return person, building, ownership


def create_case(db: Session, data: CaseCreateRequest, current_user: User) -> Case:
    building = db.get(Building, data.building_id)
    if building is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gebaeude nicht gefunden")
    check_building_access(current_user, building)

    ownership = db.get(Ownership, data.ownership_id)
    if ownership is None or ownership.building_id != data.building_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eigentuemerschaft nicht gefunden")

    case = Case(building_id=data.building_id, ownership_id=data.ownership_id)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def get_case(db: Session, case_id: uuid.UUID, current_user: User) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fall nicht gefunden")
    check_case_access(current_user, case)
    return case
