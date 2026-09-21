import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow

if TYPE_CHECKING:
    from app.models.antrags_text import AntragsText
    from app.models.case import Case


class MeasureTyp(str, enum.Enum):
    """Katalog aus Modul 2 (Gesamtkonzept). Automatisierte Machbarkeitspruefung
    in Phase 0 nur fuer die beiden Waermepumpen-Typen (JAZ >= 3,0, VDI 4650) -
    fuer alle anderen Typen sind die technischen Mindeststandards laut Doku noch
    nicht einzeln verifiziert (siehe Sitzungslog 2026-09-18)."""

    DAEMMUNG = "daemmung"
    FENSTER = "fenster"
    WAERMEPUMPE_LUFT = "waermepumpe_luft"
    WAERMEPUMPE_ERDWAERME = "waermepumpe_erdwaerme"
    PV_SPEICHER = "pv_speicher"
    LUEFTUNG = "lueftung"
    BAUBEGLEITUNG = "baubegleitung"


class Measure(Base):
    __tablename__ = "measure"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case.id"), nullable=False)
    typ: Mapped[MeasureTyp] = mapped_column(
        Enum(MeasureTyp, native_enum=False, validate_strings=True), nullable=False
    )
    # Nur bei Waermepumpen-Typen befuellt (Jahresarbeitszahl fuer die JAZ-Pruefung).
    jaz: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    # None = in Phase 0 fuer diesen Typ noch nicht automatisiert geprueft.
    machbar: Mapped[bool | None] = mapped_column(Boolean)
    hinweis: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    case: Mapped["Case"] = relationship(back_populates="measures")
    antrags_text: Mapped["AntragsText | None"] = relationship(back_populates="measure")
