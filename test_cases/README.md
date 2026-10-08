# Conversation evaluations

Deterministic code checks workflow state and populated structured fields. A Codex agent reviews
natural-language replies and summary drafts with the [rubric](rubric.md) using the repository's
[sop-eval-review skill](../.agents/skills/sop-eval-review/SKILL.md). A state pass is not a text pass.

Read the preserved [original assignment](../docs/assignment/original.txt) before reviewing. The
review skill is an instruction for the invoking Codex agent, not an automatic subagent launcher.
A separately authorized reviewer should receive that assignment, the rubric, fixtures, cases, and
the exact run artifact. Review reports identify self-review versus independent review.

## Run and review

```shell
uv run pytest -q
uv run python -m scripts.live_smoke --list
uv run python -m scripts.live_smoke --case identity_correction mixed_scope --output outputs/targeted.json
uv run python -m scripts.live_smoke --case all --output outputs/sop-evaluation.json
```

`--list` and pytest are offline. Live cases use the configured OpenRouter model and incur model
usage. Default execution runs `recovery`. Each case starts a fresh session; optional `setup` changes
only the demo date or consent scenario. Deterministic failures are retained and produce a nonzero
exit status. Workflow exceptions stop that case and are recorded; other cases still run.

Ask Codex to use `sop-eval-review` on the resulting artifact. Reports include the model, case rubric,
events, before/after state, observations, allowed evidence/candidates, draft references, actual
summary draft, and deterministic failures. Text review remains pending until a reviewer performs
it. Local artifacts contain volunteered identity details and are kept in ignored `outputs/`.

## Case format

All top-level `test_cases/*.json` files are loaded and validated. IDs must be unique.

- `expect`: exact dotted-path equality for business facts and workflow state.
- `present`: field exists and is neither null nor an empty string/list/object. Free-text phrasing
  is unrestricted. Zero and false are valid populated values.
- `includes`: unordered list membership; additional items are allowed.
- `review`: behavior to grade semantically, using the shared rubric.

Paths start with `session`, `observation`, `plan`, or `draft`. Do not use text substring assertions
as a substitute for grounding, empathy, or consent review. Every unverified turn also checks that
protected evidence and candidates are absent. The reviewer checks disclosures in prose, including
whether the agent merely acknowledges a caller's statement or asserts an actual record fact.

## Coverage

| Cases | Distinct behavior exercised |
| --- | --- |
| `compound_followup`, `early_requests` | Multiple current/early questions, full dialogue memory across verification, and reassurance about the optional closing summary |
| `optional_claim_hints`, `claim_discrepancy` | Claim fields are optional hints, record facts are authoritative, same-claim corrections and explicit switches preserve identity |
| `early_email_change` | One early email preference survives verification and can change at the closing offer |
| `upfront`, `recovery` | Three-field identity, original sample, partial answers, remembered January hint, optional email send/skip |
| `identity_correction`, `identity_revocation` | Policy number excluded from PII count, contradictory field, correction, revoked access and injection attempt |
| `identity_retraction`, `identity_ambiguous_date`, `identity_dob_format_correction`, `identity_full_id` | Retracted PII revokes access; only ambiguous DOBs need clarification; an ambiguous DOB correction revokes prior access; a full ID is not silently truncated; clarification resumes the remembered case |
| `alias_no_claims`, `no_claims` | Name/email aliases, formatted phone, verification without SSN/DOB, two accounts with no claims, human request |
| `ambiguous_january` | Competing January claims, year clarification, CL-2011 settled payment and summary |
| `national_id_claim` | Ma Tian national ID, CL-3001, diagnosis report and absent document-specific details |
| `payment_switch` | Open auto versus settled dental amounts; case switch with separate active outcomes and a complete multi-claim conversation summary |
| `unknown_answer` | Unavailable adjuster/callback information, recorded uncertainty and summary fidelity |
| `document_alternatives` | Replacement/substitute records, exhausted alternatives, empathy and human review |
| `timing_before_deadline`, `expired_deadline` | Submission date versus processing estimate, deadline clamping, expiry and human review |
| `scope_retries`, `mixed_scope` | Repeated unrelated questions, escalation, partial refusal alongside a grounded claim answer |
| `anxiety`, `confusion`, `anger`, `refusal` | Emotional acknowledgment, explanations, alternate PII, stopping persuasion |
| `consent`, `consent_timeout` | Representative consent, multiple pending polls, attempted bypass, approval/expiry |
| `followup` | Thanks plus a question, email choice plus a question, renewed choice |

Offline tests additionally cover cross-customer claim isolation, three failed identity attempts,
early email preferences, model errors/atomic updates, long conversations, streaming, and UI state.
They substitute observations/replies, so real extraction and conversational quality need live review.

## Fixture boundaries

The scenarios now exercise all four policyholder records and all five claim records. This is
scenario coverage, not a claim that all runs have passed or every fixture value is asserted.
Financial facts and distinctions are graded against saved evidence; summary completeness is
reviewed against the actual conversation. Exact deterministic payment checks also guard evidence
construction offline.

Some fixture data is intentionally not operative: representative relationship/buyer-name metadata,
claim-schema type/example/notes, and guidance matching hints are not consumed by runtime routing.
The extractor selects multiple bounded guidance subjects. Code retrieves their applicable union,
bounds submission timing, and preserves document-specific qualifications. Fixture topic labels index
follow-up rules; their wording need not match the extractor labels. Overlapping generic wrappers
and the generic fixture fallback are unused when more specific guidance already covers the subject.
Do not wire unused metadata into the product merely to make a coverage count look complete.

The auto claim has no requested documents. Auto-document rules therefore remain unreachable with
this sample data; testing them end-to-end would require a separate realistic claim fixture. Existing
claim requirements must not be changed just to exercise a rule. The phone alias duplicates the
canonical number, so it cannot independently demonstrate alias matching.

See [historical evaluations](history.md) for earlier observations. Those runs used the earlier suite;
new cases need their own live results and semantic review. Neither one run per case nor the limited
paraphrases establish statistical reliability or exhaustive injection coverage.

## Assignment-aligned refactor

Assertions on the old `intent_hint` field were removed: remembering a need is graded from the actual
reply and transcript. Case-hint checks now use `session.case_hints`, distinct from database records.
Email checks distinguish `follow_up.choice` from `offer_status` and actual delivery. A new question
can retain a send preference while the closing offer remains pending. No assertion requires an
exact reply, one topic per turn, or the caller to provide every claim selector.
