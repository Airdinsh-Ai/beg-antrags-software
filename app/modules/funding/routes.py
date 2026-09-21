import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.db import get_db
from app.models.user import User, UserRole
from app.modules.funding import rules_beg_em, rules_kfw458, service
from app.schemas.funding import (
    BegEmCalculateRequest,
    BegEmCalculateResponse,
    FundingRulesetOut,
    Kfw458CalculateRequest,
    Kfw458CalculateResponse,
)

router = APIRouter(tags=["funding"])


@router.post("/cases/{case_id}/funding/kfw-458", response_model=Kfw458CalculateResponse)
def calculate_kfw458_endpoint(
    case_id: uuid.UUID,
    payload: Kfw458CalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> Kfw458CalculateResponse:
    result = service.calculate_case_kfw458(
        db,
        case_id,
        current_user,
        foerderfaehige_kosten=payload.foerderfaehige_kosten,
        haushaltsjahreseinkommen=payload.haushaltsjahreseinkommen,
        ist_selbstnutzer=payload.ist_selbstnutzer,
        measure_id=payload.measure_id,
    )
    return Kfw458CalculateResponse(**result)


@router.post("/cases/{case_id}/funding/beg-em", response_model=BegEmCalculateResponse)
def calculate_beg_em_endpoint(
    case_id: uuid.UUID,
    payload: BegEmCalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> BegEmCalculateResponse:
    result = service.calculate_case_beg_em(
        db,
        case_id,
        current_user,
        foerderfaehige_kosten=payload.foerderfaehige_kosten,
        hat_isfp=payload.hat_isfp,
        fachplanung_kosten=payload.fachplanung_kosten,
        energieberatung_kosten=payload.energieberatung_kosten,
        ist_mfh=payload.ist_mfh,
        measure_id=payload.measure_id,
    )
    return BegEmCalculateResponse(**result)


@router.get("/funding/rulesets", response_model=list[FundingRulesetOut])
def list_rulesets_endpoint(
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> list[FundingRulesetOut]:
    return [
        FundingRulesetOut(
            regelversion=rules_kfw458.REGELVERSION,
            gueltig_ab=rules_kfw458.GUELTIG_AB,
            quelle=rules_kfw458.QUELLE,
            regel_hash=rules_kfw458.REGEL_HASH,
        ),
        FundingRulesetOut(
            regelversion=rules_beg_em.REGELVERSION,
            gueltig_ab=rules_beg_em.GUELTIG_AB,
            quelle=rules_beg_em.QUELLE,
            regel_hash=rules_beg_em.REGEL_HASH,
        ),
    ]
