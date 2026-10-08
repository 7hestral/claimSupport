"""Build a bounded evidence set from an authorized claim and applicable guidance."""

from datetime import date, timedelta

from ..data.repository import FixtureRepository
from ..schemas.facts import Topic
from ..schemas.records import Claim
from ..schemas.state import Evidence

FOLLOWUP_TOPICS = {
    "processing_time": "processing_time_after_submission",
    "submission": "submission_method",
    "receipt": "receipt_confirmation",
}


def claim_evidence(
    claim: Claim, repository: FixtureRepository, today: date, topics: list[Topic]
) -> list[Evidence]:
    requested = set(topics)
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
    if "payment" in requested or claim.status in {"open", "closed"}:
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
        if not requested or requested & {
            "denial",
            "documents",
            "alternatives",
            "submission",
            "general",
        }:
            evidence.append(
                Evidence(
                    id="step.documents",
                    kind="next_step",
                    text=f"Request complete copies of {documents} from the issuing provider or facility.",
                )
            )
        document_details = bool(requested & {"documents", "format", "alternatives"})
        if document_details:
            evidence.append(
                Evidence(
                    id="guidance.submission", kind="guidance", text=rules["default_guidance"]["en"]
                )
            )
        if document_details and claim.case_type in rules["case_type_guidance"]:
            evidence.append(
                Evidence(
                    id="guidance.case_type",
                    kind="guidance",
                    text=rules["case_type_guidance"][claim.case_type]["en"],
                )
            )
        categories = ["document_guidance"] if document_details else []
        if "alternatives" in requested:
            categories.append("document_alternative_guidance")
        for category in categories:
            for document in claim.documents_needed:
                if document in rules[category]:
                    evidence.append(
                        Evidence(
                            id=f"guidance.{category}.{document}",
                            kind="guidance",
                            text=rules[category][document]["en"],
                        )
                    )
        if "alternatives" in requested:
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
        if "submission_timing" in requested and not expired:
            target = today + timedelta(days=7)
            if claim.appeal_deadline:
                target = min(target, claim.appeal_deadline)
            evidence.append(
                Evidence(
                    id="guidance.submission_timing",
                    kind="guidance",
                    text=f"Suggested submission target: {target}. It is the earlier of seven days from today's date ({today}) and the recorded appeal deadline. This is a suggested target, not a new deadline, an intake buffer, or an extension.",
                )
            )
        for topic, rule_id in FOLLOWUP_TOPICS.items():
            if topic not in requested or (expired and topic == "processing_time"):
                continue
            text = repository.followup_guidance[rule_id].format(
                case_id=claim.case_id,
                documents=documents,
                average_processing_time_after_submission=rules["claim_followup_settings"][
                    "average_processing_time_after_submission"
                ]["en"],
            )
            evidence.append(Evidence(id=f"guidance.{rule_id}", kind="guidance", text=text))
    return evidence
