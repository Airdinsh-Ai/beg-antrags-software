"""Zentrales Datenmodell (Systemarchitektur Abschnitt 7), vollstaendig ab Phase 0.

Der Import aller Modelle hier ist Voraussetzung dafuer, dass Base.metadata
vollstaendig ist - fuer Alembic-Autogenerate und fuer die Aufloesung der
relationship()-Strings zwischen den Dateien.
"""

from app.models.building import Building
from app.models.case import Case, CaseStatus
from app.models.document import Document, DocumentTyp, RetentionClass
from app.models.funding import CaseFunding, FundingHistory, ProgrammTyp
from app.models.measure import Measure, MeasureTyp
from app.models.ownership import Ownership
from app.models.person import Person
from app.models.user import AuditLog, User, UserRole

__all__ = [
    "AuditLog",
    "Building",
    "Case",
    "CaseFunding",
    "CaseStatus",
    "Document",
    "DocumentTyp",
    "FundingHistory",
    "Measure",
    "MeasureTyp",
    "Ownership",
    "Person",
    "ProgrammTyp",
    "RetentionClass",
    "User",
    "UserRole",
]
