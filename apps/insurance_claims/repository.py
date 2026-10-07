"""Fixture storage with an authorization boundary for all claim reads."""

import json
from pathlib import Path

from pydantic import TypeAdapter

from .schemas.records import Claim, Policyholder, Representative
from .schemas.state import Session

FIXTURES = Path(__file__).parent / "fixtures"


class FixtureRepository:
    def __init__(self, directory: Path = FIXTURES):
        self.policyholders = TypeAdapter(list[Policyholder]).validate_json(
            (directory / "policyholders.json").read_text()
        )
        self.representatives = TypeAdapter(list[Representative]).validate_json(
            (directory / "representatives.json").read_text()
        )
        self._claims = TypeAdapter(list[Claim]).validate_json(
            (directory / "claims.json").read_text()
        )
        self.guidelines = json.loads((directory / "required_document_guideline.json").read_text())
        self.field_descriptions = json.loads((directory / "claim_schema.json").read_text())[
            "field_descriptions"
        ]
        self.consent_scenarios = json.loads((directory / "consent_scenarios.json").read_text())

    def customer(self, party_id: str) -> Policyholder:
        return next(p for p in self.policyholders if p.party_id == party_id)

    def claims_for(self, session: Session) -> list[Claim]:
        party_id = session.verification.verified_party_id
        if party_id is None or session.authorization.status not in {"not_required", "approved"}:
            raise PermissionError("Identity and representative authorization are required.")
        return [claim for claim in self._claims if claim.party_id == party_id]

    def claim_for(self, session: Session, case_id: str) -> Claim:
        for claim in self.claims_for(session):
            if claim.case_id == case_id:
                return claim
        raise PermissionError("This case is not available to the verified customer.")
