import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Uuid
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


class AltheizungArt(str, enum.Enum):
    """Art der Heizung, die ein Waermeerzeuger ersetzt - entscheidet ueber den
    Klimageschwindigkeitsbonus (KfW 458, Merkblatt 07/2026). Welche Arten
    bonusberechtigt sind, steht im Regelsatz, nicht hier."""

    OEL = "oel"
    KOHLE = "kohle"
    GAS_ETAGE = "gas_etage"
    NACHTSPEICHER = "nachtspeicher"
    GAS = "gas"
    BIOMASSE = "biomasse"
    SONSTIGE = "sonstige"


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
    # Die Heizung, die diese Massnahme ersetzt - nur bei Waermeerzeugern. Gehoert
    # zur Massnahme, nicht zum Gebaeude: nach dem Tausch stimmt sie dort nicht mehr.
    # Pflicht erst bei der KfW-458-Berechnung fuer Selbstnutzer (Klimabonus).
    alte_heizung_art: Mapped[AltheizungArt | None] = mapped_column(
        Enum(AltheizungArt, native_enum=False, validate_strings=True)
    )
    alte_heizung_inbetriebnahme: Mapped[date | None] = mapped_column(Date)
    alte_heizung_funktionstuechtig: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    case: Mapped["Case"] = relationship(back_populates="measures")
    antrags_text: Mapped["AntragsText | None"] = relationship(back_populates="measure")
