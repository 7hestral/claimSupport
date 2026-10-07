"""Build a bounded evidence set from an authorized claim and applicable guidance."""

from datetime import date, timedelta

from .repository import FixtureRepository
from .schemas.records import Claim
from .schemas.state import Evidence

TOPIC_GUIDANCE = {
    "alternatives": "missing_required_material_alternatives",
    "processing_time": "processing_time_after_submission",
    "submission": "submission_method",
    "format": "file_format_requirements",
    "receipt": "receipt_confirmation",
}


def claim_evidence(
    claim: Claim, repository: FixtureRepository, today: date, topic: str
) -> list[Evidence]:
    rules = repository.guidelines
    labels = rules["document_labels"]
    documents = ", ".join(labels[document] for document in claim.documents_needed)
    evidence = [
        Evidence(id="claim.status", text=f"Claim {claim.case_id}: {claim.status}. {claim.summary}"),
        Evidence(id="claim.created", text=f"Claim created on {claim.created_at}."),
    ]
    if claim.denial_reason:
        evidence.append(
            Evidence(id="claim.denial", text=f"Recorded denial reason: {claim.denial_reason}.")
        )
    if topic == "payment" or claim.status in {"open", "closed"}:
        for field in ("expected_reimbursement_amount", "allowed_max_amount", "net_pay", "net_fee"):
            description = repository.field_descriptions[field]["description"]
            evidence.append(
                Evidence(
                    id=f"claim.{field}",
                    text=f"{field}: USD {getattr(claim, field):.2f}. {description}",
                )
            )
    expired = claim.appeal_deadline is not None and today > claim.appeal_deadline
    if claim.appeal_deadline:
        evidence.append(
            Evidence(
                id="claim.deadline", text=f"Recorded appeal deadline: {claim.appeal_deadline}."
            )
        )
    if expired:
        evidence.append(
            Evidence(
                id="step.expired",
                kind="next_step",
                text="The recorded appeal deadline has passed. Ask a human claims representative to review available options; this record does not establish an extension or eligibility for a late appeal.",
            )
        )
    if claim.documents_needed:
        evidence.append(Evidence(id="claim.documents", text=f"Requested documents: {documents}."))
        evidence.append(
            Evidence(
                id="step.documents",
                kind="next_step",
                text=f"Request complete copies of {documents} from the issuing provider or facility.",
            )
        )
        evidence.append(
            Evidence(
                id="guidance.submission", kind="guidance", text=rules["default_guidance"]["en"]
            )
        )
        if claim.case_type in rules["case_type_guidance"]:
            evidence.append(
                Evidence(
                    id="guidance.case_type",
                    kind="guidance",
                    text=rules["case_type_guidance"][claim.case_type]["en"],
                )
            )
        category = (
            "document_alternative_guidance" if topic == "alternatives" else "document_guidance"
        )
        for document in claim.documents_needed:
            if document in rules[category]:
                evidence.append(
                    Evidence(
                        id=f"guidance.{category}.{document}",
                        kind="guidance",
                        text=rules[category][document]["en"],
                    )
                )
        if topic == "alternatives":
            evidence.extend(
                [
                    Evidence(
                        id="guidance.alternatives",
                        kind="guidance",
                        text=rules["document_alternative_guidance"]["default"]["en"],
                    ),
                    Evidence(
                        id="step.manual_review",
                        kind="next_step",
                        text=rules["claim_followup_settings"][
                            "human_review_after_document_alternatives_exhausted"
                        ]["en"],
                    ),
                ]
            )
        if topic == "submission_timing" and not expired:
            target = today + timedelta(days=7)
            if claim.appeal_deadline:
                target = min(target, claim.appeal_deadline)
            evidence.append(
                Evidence(
                    id="guidance.submission_timing",
                    kind="guidance",
                    text=f"The general guidance is to submit within a week, bounded by the recorded appeal deadline: target {target}. This is not an extension.",
                )
            )
        for rule in rules["claim_followup_guidance"]:
            if rule["topic"] == TOPIC_GUIDANCE.get(topic) and not (
                expired and topic == "processing_time"
            ):
                text = rule["en"].format(
                    case_id=claim.case_id,
                    documents=documents,
                    average_processing_time_after_submission=rules["claim_followup_settings"][
                        "average_processing_time_after_submission"
                    ]["en"],
                )
                evidence.append(
                    Evidence(id=f"guidance.{rule['topic']}", kind="guidance", text=text)
                )
    return evidence
