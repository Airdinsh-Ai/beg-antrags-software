from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class FundingCalculateRequest(BaseModel):
    foerderfaehige_kosten: Decimal = Field(gt=0)
    haushaltsjahreseinkommen: int = Field(ge=0)
    ist_selbstnutzer: bool = True


class FundingCalculateResponse(BaseModel):
    foerderquote: Decimal
    foerderfaehige_kosten_gedeckelt: Decimal
    foerderbetrag: Decimal
    regelversion: str
    regel_hash: str


class FundingRulesetOut(BaseModel):
    regelversion: str
    gueltig_ab: date
    quelle: str
    regel_hash: str
