import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow

if TYPE_CHECKING:
    from app.models.measure import Measure
    from app.models.user import User


class AntragsText(Base):
    """Modul 4 - Antragstext-Generator. Ein Massnahme bekommt genau einen
    (upsertbaren) Textsatz: LLM-Entwurf + nach Pflicht-Review die finale,
    ggf. bearbeitete Fassung (Gesamtkonzept Modul 4, DSGVO Art. 22 - der
    Review muss inhaltlich sein, kein formales Abnicken)."""

    __tablename__ = "antrags_text"
    __table_args__ = (UniqueConstraint("measure_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    measure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measure.id"), nullable=False)

    massnahmenbeschreibung_entwurf: Mapped[str] = mapped_column(Text, nullable=False)
    energetischer_mehrwert_entwurf: Mapped[str] = mapped_column(Text, nullable=False)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    # Erst nach dem Pflicht-Review befuellt - freigegeben bleibt False, bis
    # eine reviewende Person die (ggf. bearbeitete) Endfassung einreicht.
    massnahmenbeschreibung_final: Mapped[str | None] = mapped_column(Text)
    energetischer_mehrwert_final: Mapped[str | None] = mapped_column(Text)
    freigegeben: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)

    measure: Mapped["Measure"] = relationship(back_populates="antrags_text")
    reviewed_by: Mapped["User | None"] = relationship()
