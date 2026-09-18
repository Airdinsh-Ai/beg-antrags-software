import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.db import get_db
from app.models.user import User, UserRole
from app.modules.funding import rules, service
from app.schemas.funding import (
    FundingCalculateRequest,
    FundingCalculateResponse,
    FundingRulesetOut,
)

router = APIRouter(tags=["funding"])


@router.post("/cases/{case_id}/funding/calculate", response_model=FundingCalculateResponse)
def calculate_funding_endpoint(
    case_id: uuid.UUID,
    payload: FundingCalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> FundingCalculateResponse:
    result = service.calculate_case_funding(
        db,
        case_id,
        current_user,
        foerderfaehige_kosten=payload.foerderfaehige_kosten,
        haushaltsjahreseinkommen=payload.haushaltsjahreseinkommen,
        ist_selbstnutzer=payload.ist_selbstnutzer,
    )
    return FundingCalculateResponse(**result)


@router.get("/funding/rulesets", response_model=list[FundingRulesetOut])
def list_rulesets_endpoint(
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> list[FundingRulesetOut]:
    # Phase 0: genau ein Programm (KfW 458). Weitere Regelsaetze (BEG EM, KfW 270,
    # Steuerbonus) werden hier ergaenzt, sobald sie existieren.
    return [
        FundingRulesetOut(
            regelversion=rules.REGELVERSION,
            gueltig_ab=rules.GUELTIG_AB,
            quelle=rules.QUELLE,
            regel_hash=rules.REGEL_HASH,
        )
    ]
