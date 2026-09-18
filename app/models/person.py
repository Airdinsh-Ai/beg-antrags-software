import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.ownership import Ownership


class Person(Base):
    __tablename__ = "person"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(String(200))
    kontakt: Mapped[str | None] = mapped_column(String(200))
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime)

    ownerships: Mapped[list["Ownership"]] = relationship(back_populates="person")
