import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    building_id: uuid.UUID
    ownership_id: uuid.UUID
    status: str
    regelversion: str | None
    regel_hash: str | None
    created_at: datetime
