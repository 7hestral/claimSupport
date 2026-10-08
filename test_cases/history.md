# Historical evaluation notes

Results are tied to the runs described below. Earlier runs do not validate later cases or revisions.

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
