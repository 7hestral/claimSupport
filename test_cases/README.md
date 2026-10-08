# Conversation test cases

Offline tests exercise the real graph, policy, repository, memory, and UI with scripted model
outputs. They prove application behavior given an observation; they do not test whether a real LLM
extracts that observation or writes an empathetic reply.

`test_cases/conversations.json` contains reusable caller messages, expected state/observation
values, and a qualitative review rubric. Run `uv run python -m scripts.live_smoke --case all` to use
the configured OpenRouter model. Default execution runs only `recovery`; `--case upfront` runs the
original Margaret example. Each case gets a separate conversation. Results and authorized evidence
are saved to ignored `outputs/live-conversations.json`. Real calls incur model usage.

## Coverage map

| Requirement | Offline contract | Live scenario / remaining review |
| --- | --- | --- |
| Three distinct PII matches, all volunteered upfront | `test_full_conversation_requires_wrapup_and_explicit_email_choice`, `test_identity_gate_rejects_incomplete_or_conflicting_data` | `upfront`: actual extraction and immediate case selection |
| No protected access before verification | `test_early_case_hint_survives_partial_identity_without_claim_access`, foreign-case and consent tests | All unverified live turns check absent evidence/candidates and selected leak terms; inspect prose for other disclosures |
| Remember denied / healthcare / January across phases | `test_early_case_hint_survives_partial_identity_without_claim_access` | `recovery`: name + hint, complaint, then DOB + email; resolves CL-2048 without repeating the hint |
| Grounded case answers and allowed actions | Invalid evidence references, ownership, deadlines, case-switching tests | `upfront`, `recovery`, `consent`: compare every factual sentence to saved evidence; no automatic semantic proof |
| Phase ordering, close readiness, explicit email choice | Full conversation and premature-close / early-email tests | `upfront` sends, `recovery` skips; both simulated |
| Emotional support | Raw dialogue reaches the speaker; emotion alone does not increment refusal counters | Review `anxiety`, `confusion`, `anger`, and `recovery` replies directly; no extracted emotion label |
| Empathy before requesting more info | Prompt requirement, not proven offline | Review emotional replies for specific acknowledgment first, appropriate tone, no blame or pressure |
| Explain verification and consent | Gate tests verify access restrictions | `confusion`, `consent`: review privacy explanation and why identity details alone cannot grant representative access |
| Encourage progress and offer alternate fields | Partial-identity and refusal tests | `recovery`, `anxiety`: review optional DOB/phone/email alternatives without requiring SSN |
| Stop persuading and honor human request | `test_repeated_refusal_offers_human_without_bypassing_gate` | `refusal`: review offer after stalled recovery, then assert terminal handoff request |
| No fixed number of follow-ups | `test_many_followups_do_not_force_completion` (60 follow-ups) | No arbitrary cap; terminal user choices still close a conversation |
| Context window retains memory | `test_long_chat_windows_model_input_without_losing_memory` | Input-budget test, not a real-model long-chat quality evaluation |

Additional offline cases cover national ID, aliases, ambiguous January matches, identity corrections,
session isolation, model failures without partial state updates, scope retries, consent approval and
expiry, open/closed claims, and UI reset/clock controls.

## Qualitative acceptance

For each emotional reply, check: (1) acknowledgment before the next request, (2) brief explanation
of the required gate, (3) a feasible next option, (4) no disclosure or bypass, and (5) no repeated
persuasion once human support is appropriate. Natural wording is intentionally not asserted with
exact-text snapshots. A state-check pass is not an empathy pass.

The interpreter extracts explicit verification refusal and workflow choices. The main speaker reads
caller wording and recent dialogue directly for tone and empathy. No emotion label is extracted and
no dedicated comforting agent is routed in. Emotion cannot authorize a claim read or phase
transition. A separate comfort model, if introduced, would need the same restricted context and
would still have to obey the application-selected action.

These are representative scenarios, not exhaustive paraphrase, prompt-injection, or hallucination
evaluations. The history window preserves structured facts but not every old utterance or emotional
detail; it does not provide unbounded semantic memory.

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

The current collection has eight scenarios. `followup` checks the new single conversation-action
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
