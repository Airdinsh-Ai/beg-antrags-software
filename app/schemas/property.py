import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.funding import ProgrammTyp


class PersonIn(BaseModel):
    name: str
    kontakt: str | None = None


class BuildingIn(BaseModel):
    adresse: str
    baujahr: int | None = None
    wohneinheiten: int | None = None


class OwnershipIn(BaseModel):
    von: date
    bis: date | None = None


class PropertyCreateRequest(BaseModel):
    person: PersonIn
    building: BuildingIn
    ownership: OwnershipIn


class PropertyCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    person_id: uuid.UUID
    building_id: uuid.UUID
    ownership_id: uuid.UUID


class CaseCreateRequest(BaseModel):
    building_id: uuid.UUID
    ownership_id: uuid.UUID


class CaseFundingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    programm: ProgrammTyp
    foerderbetrag: Decimal
    regelversion: str
    regel_hash: str
    berechnet_am: datetime


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    building_id: uuid.UUID
    ownership_id: uuid.UUID
    status: str
    funding_entries: list[CaseFundingOut] = []
    created_at: datetime
