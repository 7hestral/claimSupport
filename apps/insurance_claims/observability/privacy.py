"""Pseudonymize the demo identities in exported telemetry, without changing model inputs."""

import hashlib
import json
import re

from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult, OtelSpanPatch

from ..data import FIXTURES

IDENTITY_KEYS = (
    "name",
    "rep_name",
    "buyer_name",
    "dob",
    "phone",
    "email",
    "id_last4",
    "policy_number",
)


def fixture_replacements() -> dict[str, str]:
    replacements = {}
    for filename in ("policyholders.json", "representatives.json"):
        for record in json.loads((FIXTURES / filename).read_text()):
            for key in IDENTITY_KEYS:
                for value in ([record[key]] if key in record else []) + record.get(
                    f"{key}_aliases", []
                ):
                    token = hashlib.sha256(value.casefold().encode()).hexdigest()[:8]
                    replacements[value] = f"[identity:{token}]"
                    if key == "phone":
                        digits = re.sub(r"\D", "", value)[-10:]
                        replacements[digits] = f"[identity:{token}]"
    return replacements


class TraceMasker:
    def __init__(self):
        replacements = fixture_replacements()
        self.replacements = {key.casefold(): value for key, value in replacements.items()}
        self.pattern = re.compile(
            r"(?<![A-Za-z0-9])(?:"
            + "|".join(re.escape(value) for value in sorted(replacements, key=len, reverse=True))
            + r")(?![A-Za-z0-9])",
            re.IGNORECASE,
        )

    def text(self, value: str) -> str:
        value = self.pattern.sub(lambda match: self.replacements[match[0].casefold()], value)
        value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email]", value)
        return re.sub(
            r"(?<!\d)(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)", "[phone]", value
        )

    def __call__(self, *, params: MaskOtelSpansParams) -> MaskOtelSpansResult:
        patches = {}
        for identifier, span in params.spans.items():
            updates = {}
            for key, value in span.attributes.items():
                if isinstance(value, str):
                    updates[key] = self.text(value)
                elif isinstance(value, (tuple, list)) and all(isinstance(v, str) for v in value):
                    updates[key] = [self.text(v) for v in value]
            patches[identifier] = OtelSpanPatch(set_attributes=updates)
        return MaskOtelSpansResult(span_patches=patches)
