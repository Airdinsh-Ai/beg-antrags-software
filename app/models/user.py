import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow


class UserRole(str, enum.Enum):
    """Die vier Rollen aus Systemarchitektur Abschnitt 8. Rollen-Management
    (mehrere aktive Rollen je Nutzer, Einladungsflows) ist bewusst nicht Phase 0."""

    BERATER = "beraterfirma_mitarbeiter"
    ADMIN = "admin"
    IMMOBILIENBESITZER = "immobilienbesitzer"
    FACHPARTNER = "eee_fachpartner"


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, validate_strings=True), nullable=False
    )
    # Nicht im urspruenglichen Diagramm (Abschnitt 7), mit Airdinsh abgestimmt:
    # ohne diese Zuordnung kann core/access.py fuer die Rolle Immobilienbesitzer
    # nie pruefen, ob ein Fall/Gebaeude "ihm gehoert".
    person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("person.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    # Nicht im urspruenglichen Diagramm, mit Airdinsh abgestimmt: ohne Zielangabe
    # weiss das Audit-Log nie, WAS protokolliert wurde.
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    zeit: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
