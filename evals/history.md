# Historical evaluation notes

Results are tied to the runs described below. Earlier runs do not validate later cases or revisions.

## Prompt simplification and Sonnet 5.5 comparison — October 8, 2026

Created checkpoint `df4b6d4` before simplifying conversation instructions. Common rules, grounding,
phase responsibilities, and per-action guidance now have less repetition. The extraction prompt,
schemas, fixtures, and workflow logic are unchanged. Representative conversation system prompts
are 28.5–45.4% shorter by word count; this excludes history, context, and output schemas.

Initial Sonnet 4.6 experiments exposed misleading full-ID, consent, and DOB wording; those reductions
were rejected and explicit boundary instructions retained. After the user switched to Sonnet 5.5,
both checkpoint prompts and the simplified prompts were evaluated on all 31 cases / 95 events.
An intermediate candidate misread `offer_human=false` as prohibiting human support. Its meaning is
now explicit: true requires an offer, while false does not prohibit one. Processing estimates also
stay in discussion references rather than being recorded as action steps.

The final Sonnet 5.5 run and the same-model checkpoint baseline each passed all 95 state checks.
87 offline tests and lint/format/diff checks pass. The implementing agent reviewed every turn and
all eight email drafts in each comparison run. No material semantic regression was observed in the
final run, but smaller concerns remain: an unsupported inference about whether an upload happened,
a conditional support offer, and unnecessary search clues for an empty account. This is not full
semantic acceptance or a statistical reliability claim. Detailed verdicts, raw reports, source
manifests, and trace links are in `outputs/prompt-simplification/review.md`; the earlier model's
results remain separately recorded in `review-sonnet-4-6.md`.

## Multi-topic evidence routing

The extractor now selects multiple bounded guidance topics. Pending requests append and deduplicate
through verification/consent/case selection; after a successful claim reply they join that claim's
topic history. Retrieval uses pending requests rather than all prior subjects. Explicit switches
clear pending topics and keep each prior claim's discussion in its own outcome for the summary.

87 offline tests passed, including early-topic preservation, deduplication, receipt-only retrieval,
case-switch history, deadline suppression, and the next-step reference boundary. Lint, formatting,
diff checks, and skill validation passed. The first full live run exposed three reference-validation
failures: actionable service guidance was excluded from the next-step schema, and a general claim
overview lacked its ordinary request-documents step. The contract was corrected to allow authorized
guidance as a source for next steps while still rejecting claim facts and unknown IDs.

The final full run passed state checks for all 31 cases / 95 events with
`anthropic/claude-sonnet-4.6`. The receipt question now has 6 evidence entries instead of 24; the
compound scan/submission/review request has 12, alternatives plus receipt has 15, and early scan/review
questions have 10. Their answers retained the relevant guidance and conditions. The receipt reply no
longer claims instant confirmation does not exist, and all eight summary drafts retain their discussed
claims despite narrower current evidence.

Semantic acceptance is still incomplete: one reply calls March 18 seven days after March 15, despite
the correct date in evidence. Other concerns include unsupported human-follow-up capabilities and
an inaccurate explanation of identity revocation. These are recorded separately from the passing
routing and state checks. The implementing-agent review, per-case verdicts, source manifests, raw
first/final runs, and trace links are in `outputs/multi-topic-routing/`. No independent review or
statistical recall/reliability measurement was performed.

## Optional clarification metadata and visible caller values — October 7, 2026

Added optional per-turn extraction clarifications (default `[]`) so the conversation agent receives
the ambiguous field, caller value, and reason. Two existing DOB cases now check that metadata and
its absence after a clear answer. Removed `[provided]` masking from response context and the demo
inspector; identity access boundaries and separate telemetry export pseudonymization remain.

84 offline tests passed, as did lint/format/diff checks. A targeted live run of five cases / 13 events
with `anthropic/claude-sonnet-4.6` passed all state checks. Both ambiguous-date replies presented both
interpretations and accepted later written-month answers; the correction reply offered valid PII
alternatives. Semantic review still found a wrong-year typo (`2985`) in one clarification example,
an omitted original-document qualification in a claim answer, and other grounding concerns.
This is not full semantic acceptance or a full-suite rerun. The implementing-agent review and
trace links are in `outputs/clarification-metadata/review.md`, with raw `live.json` and source hashes.

## Assignment-aligned workflow and review — October 7, 2026

Preserved the original assignment in `docs/assignment/original.txt` and updated cases before changing
the implementation. Five new scenarios exercise compound questions, early requests, optional claim
hints, discrepancies with recorded claim facts, and changed email preferences. The suite now has
31 scenarios / 95 events. Semantic review starts from the original assignment and authorized
fixtures; it accepts equivalent wording and does not require the removed topic/intent fields.
The review skill guides the invoking agent and does not automatically launch a subagent.

The implementation separates identity from optional claim hints, uses conversation history for
requests, supplies applicable grounded guidance without a single-topic classifier, and stores one
email choice separately from offer/delivery progress. Conversation summaries now include separately
attributed outcomes for all discussed claims. Identity changes clear protected history and outcomes;
claim-hint changes do not themselves require identity verification again.

Offline validation passed: 83 tests, lint, formatting, and skill validation. A full live run of all
31 scenarios / 95 events and a final targeted rerun of 12 scenarios / 43 events passed state checks
with `anthropic/claude-sonnet-4.6`. The final small prompt/date-evidence revision was tested only in
that targeted rerun. Source manifests accompany the artifacts.

**Semantic acceptance remains incomplete.** The implementing Codex agent reviewed the transcripts,
not an independent reviewer. One reply guessed an ambiguous DOB and offered policy number as a
PII alternative, although extraction and the access gate correctly rejected the ambiguous date.
Another claimed instant upload confirmation does not exist when the fixture only leaves it
unspecified. Additional grounding and consent-wording concerns remain in the report. Langfuse
traces distinguish these response-model failures from correct workflow state; they do not establish
a single causal explanation or reliability rate.

Evidence: `outputs/assignment-refactor/review.md`, `final-*.json`, `recheck-*.json`, and their source
manifests (ignored by Git). The report identifies each case, dimension, finding, and relevant trace.

## DOB clarification only for genuine ambiguity

The user clarified that YYYY-MM-DD is a recommendation, not a mandatory input format. The current
prompts accept written months, explicitly stated numeric orders, and dates with a single valid
interpretation without retyping or confirmation. Clarification is reserved for multiple plausible
dates. The UI note and README now describe the format as recommended. An ambiguous correction
still retracts a previous DOB and revokes access until clarified.

The first revised prompt still guessed some slash dates. A focused revision distinguishes an
explicitly stated order from a merely familiar-looking date. All 27 rechecked probes passed,
including written months, both explicit numeric orders, year-first slashes, equal month/day values,
and genuinely ambiguous inputs. Earlier strict-format results below are historical and do not
define the current acceptance contract. Current artifacts are in
`outputs/extractor-tuning/flexible-dob-review.md` and its linked raw reports.

## User-facing DOB format convention

The user chose a format request and visible reminder instead of deterministic date parsing.
The extractor now accepts DOB supplied as `YYYY-MM-DD`; other representations are left unset for
the caller to restate. An explicit correction in another format also retracts the old DOB so prior
access cannot silently survive. The verification prompt requests typed input, offers alternate
fields, and avoids converting a date then asking for yes/no confirmation. The UI note explains
year-month-day with an example. No schema or workflow architecture changed.

Under this input convention, all date probes passed in a 53-probe run. Two pre-existing preferred
classifier-label mismatches remain workflow-equivalent, as explained in the earlier review. The
targeted live run covered four cases / ten events with zero state failures. After tightening the
clarification wording, both date workflows passed again across six events; semantic review confirms
the caller is asked to type the format, no DOB is counted early, corrected identity revokes access,
and the original claim hint is reused after verification. The named-month example now intentionally
requires restatement too; earlier tests of automatic date conversion are historical evidence.

Offline checks: 75 tests passed, lint and formatting passed, and Streamlit AppTest rendered the
format note without exceptions. Evidence and remaining unrelated response issues are recorded in
`outputs/extractor-tuning/format-policy-review.md`. This targeted check does not revalidate all
conversational behavior or claim deterministic enforcement of arbitrary free-text inputs.

## Extractor prompt iterations

Baseline `f918169` was committed before editing. Five main prompt candidates and one additional
date-focused candidate were tested with `anthropic/claude-sonnet-4.6`. The prompt now separates facts
from conversational signals and explicitly preserves factual corrections alongside bypass requests.
The original name-correction failure no longer occurred in the tested candidates. No schema,
context-builder, response-prompt, state-machine, or model-setting changes were made.

Three cases were added for identity retraction, ambiguous DOB, and full-ID handling. Both the fifth
and sixth candidates passed all 25 workflows (74 events), including access revocation and retention
of the original claim hint. Offline tests: 74 passed; lint and formatting passed.

However, isolated and repeated probes still exposed guessed numeric DOBs; one earlier candidate
also reversed an explicit date format. Thus the extractor is not fully accepted. The user was asked
whether deterministic DOB handling at the extraction boundary is acceptable; no such change has
been made. Known response-only grounding and workflow-communication failures also remain.

Local evidence: `outputs/extractor-tuning/` contains frozen probe inputs, per-candidate prompt
snapshots and hashes, raw results, full workflow reports, and Langfuse links. `review.md` documents
the iterations; `workflow-review.md` grades all current-candidate conversations. Two preferred-label
mismatches were judged workflow-equivalent (email skip and scan guidance), rather than forcing
exact model classifications. Date errors remain recorded as failures.

## Langfuse diagnosis on October 7, 2026

Connected the configured US-cloud project and verified exported traces by fetching them back.
Re-ran the five previously failing scenarios with `anthropic/claude-sonnet-4.6`: 22 events total.
Four scenarios passed all state checks; identity revocation still failed five assertions. Semantic
review found four failing scenarios and one concern. The original representative-name repeat did
not recur, but consent turns 2 and 5 falsely claimed approval while recorded access stayed pending.
The earlier invented payment range did not recur; a future-payment inference remains a concern.

Nine isolated diagnostic calls compared unchanged inputs, reduced context, and explicit prompt
rules. Identity correction and pending-consent wording improved with either reduced assistant
history or a focused instruction. Removing unrelated context eliminated the invented adjuster
contact route in one replay; another grounding instruction alone did not. These are single-run
observations, not validated production fixes. Business prompts and SOP behavior remain unchanged.

Local evidence: `outputs/langfuse-identity.json`, `outputs/langfuse-failures.json`, the
`outputs/langfuse-*-ablation.json` reports, fetched observation exports, and
`outputs/langfuse-diagnosis.md`. Reports include direct Langfuse trace links. Offline checks:
71 tests passed, lint and formatting passed. This targeted run does not revalidate all 22 scenarios.

## Expanded suite review

One run of all 22 scenarios (68 events) with `anthropic/claude-sonnet-4.6` completed. State checks
passed for 21 scenarios. `identity_revocation` failed five assertions on its second turn: the
extractor omitted the caller's explicit name correction, retained Margaret's verified access, and
the reply repeated her claim details. Keep this as a failing regression target.

The Codex rubric review rated 14 scenarios pass, five fail, and three concern. Other failures were
an invented payment range, an unsupported adjuster/callback route, claiming an email send preference
while the choice remained pending, and asking again for a representative name already supplied.
The workflow therefore did not pass overall acceptance. Application code/prompts and business
fixtures were unchanged. Offline checks passed: 69 tests, lint, formatting, and skill validation.

Local evidence: `outputs/sop-expanded.json` and `outputs/sop-review.md` (ignored by Git). These are
single-run findings, not a reliability estimate or proof that a later revision behaves the same.

## Earlier v0 review on October 7, 2026

- 33 offline tests passed, including the history-window contract and 60 consecutive follow-ups.
- All seven live scenarios passed state assertions across 19 events (18 caller turns and one clock
  event) using the configured OpenRouter model. Emotion labels and refusal were inspected separately
  from the generated wording. This is one run per scenario, not a reliability estimate.
- The first live review found an unsupported reconsideration assurance and an unverified policy
  number described as "on file". Response instructions were tightened; those specific statements
  did not recur in the second run.
- The second run still had qualitative issues: anxiety acknowledgment appeared after the field
  explanation; a human-support offer implied a later follow-up; and a consent explanation described
  representative identity verification even though the demo only matched policyholder details.
  Actual access remained blocked until simulated consent. These wording issues mean the bonus and
  semantic-grounding requirements are **partially validated**, not fully satisfied by state checks.

Local transcripts with evidence are in `outputs/live-conversations.json` (first run) and
`outputs/live-conversations-recheck.json` (second run). Outputs are ignored by Git. Future evaluations
should use these failure modes as review criteria; prompt changes alone are not a guarantee.

## Simplified extractor and streaming console

At that point the collection had eight scenarios. `followup` checks the new single conversation-action
field: thanks plus a question must stay in processing, and a question alongside email consent must
be answered before renewing the summary offer. Other cases retain their identity and phase
assertions; emotion-label assertions were removed because the response model now owns empathy.

Seven existing cases passed again after the schema change, across 19 events. The browser test
confirmed real provider usage for both calls and a live output stream. Offline streaming tests cover
per-call accounting, skipped response calls, partial-output errors, and diagnostic retention without
committing failed turns. Response wording still needs qualitative review; these results do not
establish that every paraphrase is empathetic or grounded.

The new `followup` scenario initially hit the next-step reference guard. The response schema now
constrains reference choices to authorized IDs and eligible next-step IDs. Its five-event rerun
passed, as did an additional unverified `anxiety` run with empty evidence arrays. All eight scenarios
have passed state checks with the smaller extractor; 36 offline tests pass. Prompt wording remains
subject to the qualitative rubric above.
