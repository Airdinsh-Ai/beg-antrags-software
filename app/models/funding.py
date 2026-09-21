import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.case import Case
    from app.models.measure import Measure


class ProgrammTyp(str, enum.Enum):
    """Geteiltes Vokabular zwischen case_funding und funding_history - keine
    geteilte Rechenlogik (Systemarchitektur Abschnitt 2.7/7.5). KfW 270 taucht
    hier bewusst nicht auf: dafuer entsteht nie ein Berechnungsergebnis, das
    gespeichert werden muesste (Gesamtkonzept Modul 3 - Kredit, kein Zuschuss)."""

    KFW_458 = "kfw_458"
    BEG_EM = "beg_em"
    # spaeter: PARAGRAPH_35C (Phase 2, siehe BACKLOG B25)


class FundingHistory(Base):
    """Modulspezifisch (Modul 3) -> Tabellenname praefigiert, im Unterschied zu
    den unpraefigierten Kernentitaeten (Systemarchitektur Abschnitt 2.4).

    Wird aus der aktuellen Summe aller case_funding-Zeilen je Gebaeude/Jahr/
    Programm neu berechnet (Upsert), nicht additiv fortgeschrieben - siehe
    _upsert_case_funding() in modules/funding/service.py."""

    __tablename__ = "funding_history"
    __table_args__ = (UniqueConstraint("building_id", "jahr", "programm"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    building_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("building.id"), nullable=False)
    jahr: Mapped[int] = mapped_column(Integer, nullable=False)
    programm: Mapped[ProgrammTyp] = mapped_column(
        Enum(ProgrammTyp, native_enum=False, validate_strings=True), nullable=False
    )
    betrag: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    building: Mapped["Building"] = relationship(back_populates="funding_history")


class CaseFunding(Base):
    """Fallbezogene 1:n-Tabelle, ersetzt die frueheren case.regelversion/
    case.regel_hash-Skalarfelder (Systemarchitektur Abschnitt 7.5) - ein Fall
    kann mehrere Foerderprogramme gleichzeitig haben (z.B. Daemmung ueber BAFA,
    Heizung ueber KfW 458). Upsert je (case_id, programm), kein Anhaengen.

    measure_id + foerderfaehige_kosten sind optional: nur gesetzt, wenn die
    Berechnung einer konkreten Massnahme zugeordnet wird. Das ist die
    Voraussetzung fuer die 60%-Kumulierungspruefung (Gesamtkonzept Modul 3) -
    ohne diesen Bezug kann nicht unterschieden werden, ob zwei Programme
    dieselben Kosten doppelt foerdern oder (erlaubt) getrennte Gewerke."""

    __tablename__ = "case_funding"
    __table_args__ = (UniqueConstraint("case_id", "programm"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case.id"), nullable=False)
    measure_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("measure.id"))
    programm: Mapped[ProgrammTyp] = mapped_column(
        Enum(ProgrammTyp, native_enum=False, validate_strings=True), nullable=False
    )
    foerderfaehige_kosten: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    foerderbetrag: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    regelversion: Mapped[str] = mapped_column(String(30), nullable=False)
    regel_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    berechnet_am: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    case: Mapped["Case"] = relationship(back_populates="funding_entries")
    measure: Mapped["Measure | None"] = relationship()
