import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.funding import FundingHistory
    from app.models.ownership import Ownership


class Building(Base):
    __tablename__ = "building"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    adresse: Mapped[str] = mapped_column(String(300), nullable=False)
    baujahr: Mapped[int | None] = mapped_column(Integer)
    wohneinheiten: Mapped[int | None] = mapped_column(Integer)

    ownerships: Mapped[list["Ownership"]] = relationship(back_populates="building")
    cases: Mapped[list["Case"]] = relationship(back_populates="building")
    funding_history: Mapped[list["FundingHistory"]] = relationship(back_populates="building")
