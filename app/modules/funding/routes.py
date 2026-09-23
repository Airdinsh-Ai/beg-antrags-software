import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.db import get_db
from app.models.user import User, UserRole
from app.modules.funding import ruleset, service
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
        ist_selbstnutzer=payload.ist_selbstnutzer,
        haushaltsjahreseinkommen=payload.haushaltsjahreseinkommen,
        kind_im_haushalt=payload.kind_im_haushalt,
        measure_id=payload.measure_id,
        stichtag=payload.stichtag,
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
        stichtag=payload.stichtag,
    )
    return BegEmCalculateResponse(**result)


@router.get("/funding/rulesets", response_model=list[FundingRulesetOut])
def list_rulesets_endpoint(
    current_user: User = Depends(require_role(UserRole.BERATER, UserRole.ADMIN)),
) -> list[FundingRulesetOut]:
    # Alle Regelsaetze inkl. abgeloester - alte Berechnungen bleiben so
    # nachvollziehbar (Systemarchitektur Abschnitt 6, Regel 2).
    return [
        FundingRulesetOut(
            programm=satz.kopf.programm.value,
            regelversion=satz.kopf.version,
            gueltig_ab=satz.kopf.gueltig_ab,
            gueltig_bis=satz.kopf.gueltig_bis,
            quelle=satz.kopf.quelle,
            regel_hash=satz.regel_hash,
        )
        for saetze in ruleset.aktuelles_regelwerk().values()
        for satz in saetze
    ]
