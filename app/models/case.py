import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.document import Document
    from app.models.measure import Measure
    from app.models.ownership import Ownership


class CaseStatus(str, enum.Enum):
    """Phase 0: einziger Status. Die Fall-Zustandsmaschine (Fristen, Wiedervorlage)
    gehoert zu Modul 6 und kommt erst in Phase 2 (Systemarchitektur Abschnitt 11)."""

    ANGELEGT = "angelegt"


class Case(Base):
    __tablename__ = "case"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    building_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("building.id"), nullable=False)
    ownership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ownership.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=CaseStatus.ANGELEGT.value)
    regelversion: Mapped[str | None] = mapped_column(String(30))
    regel_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    building: Mapped["Building"] = relationship(back_populates="cases")
    ownership: Mapped["Ownership"] = relationship(back_populates="cases")
    documents: Mapped[list["Document"]] = relationship(back_populates="case")
    measures: Mapped[list["Measure"]] = relationship(back_populates="case")
