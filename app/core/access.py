from fastapi import HTTPException, status

from app.models.building import Building
from app.models.case import Case
from app.models.user import User, UserRole


def check_building_access(user: User, building: Building) -> None:
    """Row-Level-Zugriffspruefung, zentral aufgerufen aus service.py (Systemarchitektur
    Abschnitt 8) - nicht aus routes.py und nicht als verstreute if-Abfragen."""
    if user.role in (UserRole.ADMIN, UserRole.BERATER):
        return
    if user.role == UserRole.IMMOBILIENBESITZER and user.person_id is not None:
        if any(o.person_id == user.person_id for o in building.ownerships):
            return
    # UserRole.FACHPARTNER: in Phase 0 ohne Zuordnungstabelle (Modul 5 kommt
    # erst Phase 2), daher hier immer abgelehnt.
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kein Zugriff auf dieses Gebaeude")


def check_case_access(user: User, case: Case) -> None:
    check_building_access(user, case.building)
