import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.building import Building


class FundingHistory(Base):
    """Modulspezifisch (Modul 3) -> Tabellenname praefigiert, im Unterschied zu
    den unpraefigierten Kernentitaeten (Systemarchitektur Abschnitt 2.4)."""

    __tablename__ = "funding_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    building_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("building.id"), nullable=False)
    jahr: Mapped[int] = mapped_column(Integer, nullable=False)
    programm: Mapped[str] = mapped_column(String(50), nullable=False)
    betrag: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    building: Mapped["Building"] = relationship(back_populates="funding_history")
