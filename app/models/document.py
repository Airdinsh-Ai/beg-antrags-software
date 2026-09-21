import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow

if TYPE_CHECKING:
    from app.models.case import Case


class DocumentTyp(str, enum.Enum):
    ENERGIEAUSWEIS = "energieausweis"
    ANGEBOT = "angebot"
    RECHNUNG = "rechnung"
    FOTO = "foto"
    FACHUNTERNEHMERERKLAERUNG = "fachunternehmererklaerung"
    BZA = "bza"
    TPB = "tpb"
    BESTAETIGUNG_NACH_DURCHFUEHRUNG = "bestaetigung_nach_durchfuehrung"
    ZAHLUNGSNACHWEIS = "zahlungsnachweis"
    SONSTIGES = "sonstiges"


class RetentionClass(str, enum.Enum):
    """Entscheidet, ob ein Dokument steuerlich, foerderrechtlich oder frei
    loeschbar ist (Systemarchitektur Abschnitt 7.3)."""

    STEUERLICH = "steuerlich"
    FOERDERRECHTLICH = "foerderrechtlich"
    FREI_LOESCHBAR = "frei_loeschbar"


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case.id"), nullable=False)
    typ: Mapped[DocumentTyp] = mapped_column(
        Enum(DocumentTyp, native_enum=False, validate_strings=True), nullable=False
    )
    retention_class: Mapped[RetentionClass] = mapped_column(
        Enum(RetentionClass, native_enum=False, validate_strings=True), nullable=False
    )
    dateiname: Mapped[str | None] = mapped_column(String(255))
    # Ablageort auf dem lokalen Dateisystem (Phase 0 - kein Objektspeicher).
    speicherpfad: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    case: Mapped["Case"] = relationship(back_populates="documents")
