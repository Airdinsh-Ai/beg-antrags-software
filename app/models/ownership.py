import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.case import Case
    from app.models.person import Person


class Ownership(Base):
    __tablename__ = "ownership"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id"), nullable=False)
    building_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("building.id"), nullable=False)
    von: Mapped[date] = mapped_column(Date, nullable=False)
    bis: Mapped[date | None] = mapped_column(Date)

    person: Mapped["Person"] = relationship(back_populates="ownerships")
    building: Mapped["Building"] = relationship(back_populates="ownerships")
    cases: Mapped[list["Case"]] = relationship(back_populates="ownership")
