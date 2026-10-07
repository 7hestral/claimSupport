"""Deterministic identity checks and simulated representative authorization."""

import hashlib
import json
from datetime import timedelta

from .repository import FixtureRepository
from .schemas.facts import CallerFacts, IdentityField
from .schemas.records import Policyholder
from .schemas.state import Authorization, Session

IDENTITY_FIELDS: tuple[IdentityField, ...] = ("full_name", "dob", "phone", "email", "id_last4")
AUTH_FIELDS = (*IDENTITY_FIELDS, "id_type", "policy_number", "caller_role", "representative_name")
CONSENT_TIMEOUT_SECONDS = 120
CONSENT_CHECK_SECONDS = 10


def normalize(value: object) -> str:
    return " ".join(str(value).casefold().split())


def phone_digits(value: str) -> str:
    digits = "".join(c for c in value if c.isdecimal())
    # The demo fixtures use US phone numbers; local ten-digit input is accepted.
    return "1" + digits if len(digits) == 10 else digits


def matches(facts: CallerFacts, customer: Policyholder) -> tuple[list[IdentityField], bool]:
    values = {
        "full_name": [customer.name, *customer.name_aliases],
        "dob": [customer.dob],
        "phone": [customer.phone, *customer.phone_aliases],
        "email": [customer.email, *customer.email_aliases],
        "id_last4": [customer.id_last4],
    }
    matched = []
    supplied = []
    for field in IDENTITY_FIELDS:
        value = getattr(facts, field)
        if value is None:
            continue
        supplied.append(field)
        normalizer = phone_digits if field == "phone" else normalize
        if normalizer(value) in [normalizer(v) for v in values[field]] and (
            field != "id_last4" or facts.id_type in {None, customer.id_type}
        ):
            matched.append(field)
    return matched, len(matched) == len(supplied)


def verify(session: Session, repository: FixtureRepository) -> Policyholder | None:
    facts = session.memory
    if sum(getattr(facts, key) is not None for key in IDENTITY_FIELDS) < 3:
        return None
    payload = {key: getattr(facts, key) for key in AUTH_FIELDS}
    fingerprint = hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True).encode()
    ).hexdigest()
    candidates = []
    for customer in repository.policyholders:
        if facts.policy_number and normalize(facts.policy_number) != normalize(
            customer.policy_number
        ):
            continue
        matched, consistent = matches(facts, customer)
        if len(matched) >= 3 and consistent:
            candidates.append((customer, matched))
    if len(candidates) != 1:
        if fingerprint != session.verification.last_attempt:
            session.verification.failed_attempts += 1
            session.verification.last_attempt = fingerprint
        return None
    customer, matched = candidates[0]
    session.verification.matched_fields = matched
    session.verification.last_attempt = fingerprint
    return customer


def authorize_representative(
    session: Session, customer: Policyholder, repository: FixtureRepository
) -> str:
    """Return an action; only the fixture service can approve, never the caller or LLM."""
    if session.memory.representative_name is None:
        return "collect_representative"
    registered = any(
        rep.buyer_party_id == customer.party_id
        and normalize(rep.rep_name) == normalize(session.memory.representative_name)
        for rep in repository.representatives
    )
    if not registered:
        return "representative_unavailable"
    authorization = session.authorization
    if authorization.status == "not_required":
        authorization = Authorization(
            status="pending",
            requested_at=session.now,
            expires_at=session.now + timedelta(seconds=CONSENT_TIMEOUT_SECONDS),
            next_check_at=session.now,
        )
        session.authorization = authorization
    if authorization.status == "pending":
        if session.now >= authorization.expires_at:
            authorization.status = "timed_out"
            return "consent_timeout"
        if session.now >= authorization.next_check_at:
            sequence = repository.consent_scenarios[session.consent_scenario]["status_sequence"]
            index = min(authorization.check_index, len(sequence) - 1)
            authorization.status = sequence[index]
            authorization.check_index += 1
            authorization.next_check_at = session.now + timedelta(seconds=CONSENT_CHECK_SECONDS)
    return "authorized" if authorization.status == "approved" else "wait_consent"
