"""Validated fixture input contracts."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field

from .facts import StrictModel


class Policyholder(StrictModel):
    party_id: str
    name: str
    policy_number: str
    dob: date
    id_type: Literal["ssn_last4", "national_id_last4"]
    id_last4: str
    phone: str
    email: str
    name_aliases: list[str] = Field(default_factory=list)
    phone_aliases: list[str] = Field(default_factory=list)
    email_aliases: list[str] = Field(default_factory=list)


class Representative(StrictModel):
    rep_name: str
    relationship: str
    buyer_name: str
    buyer_party_id: str


class Claim(StrictModel):
    case_id: str
    party_id: str
    case_type: Literal["healthcare", "dental", "auto"]
    created_at: date
    status: Literal["denied", "open", "closed"]
    summary: str
    denial_reason: str | None = None
    documents_needed: list[str] = Field(default_factory=list)
    appeal_deadline: date | None = None
    expected_reimbursement_amount: Decimal
    allowed_max_amount: Decimal
    net_pay: Decimal
    net_fee: Decimal
