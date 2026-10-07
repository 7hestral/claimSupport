---
name: workflow
description: Session ownership, phase gates, and the two-call conversation pipeline.
meta:
  type: code
---

# Workflow

`build_workflow(reasoner, repository)` compiles four LangGraph nodes:
`interpret -> decide -> compose -> record`. Invoke it with a validated `Session` and `Event`, and
retain the returned session. Streamlit holds it in browser-session state. The graph deep-copies the
input session, so failures cannot commit partial memory, authorization, or conversation changes.
LangGraph END ends one turn, not the business conversation.

## Model boundaries

The interpreter receives message history and caller memory. It emits an `Observation`: a fact patch,
scope, emotion, a bounded question topic, and conversational choices. It has no customer registry,
claim tools, or phase-setting fields. Extraction runs in every phase; clock events skip extraction.
Omitted/null patch values preserve memory; explicit clear fields remove retracted facts. Corrections
to identity invalidate access, consent, selected case, and outcome before any further claim read.

The response model receives masked memory, the current phase prompt, a code-selected action, and
authorized evidence. It emits a `DraftReply` with conversational text and evidence references.
Outcome facts and next steps are copied from those references, not accepted as arbitrary model data.
Invalid references fail the turn. Scope rejections, email-choice confirmations, and terminal
handoff/exit replies are deterministic.
Normal turns use two calls to the same OpenRouter model; clock events use at most the response call.

## Gates

| Phase | Exit condition |
| --- | --- |
| VERIFY_ID | Three matching PII fields, one customer, no supplied conflicts; representative consent if needed |
| RESOLVE_INTENT | A remembered intent and exactly one authorized matching case |
| PROCESS_CASE | A discussed outcome and caller readiness without another follow-up question |
| POST_PROCESS | Explicit send or skip after the offer |

An identity correction restarts verification. An explicit case change restarts case resolution.
Follow-up questions during the summary offer remain in POST_PROCESS and are answered before renewing
the offer. Human requests and explicit conversation exits are terminal dispositions outside normal
phase progression. Neither path grants access or claims that an external action succeeded.

## Data and time

`FixtureRepository.claims_for` and `claim_for` enforce access and customer ownership. Claim status is
read-only. Document requirements use canonical identifiers shared with guideline keys; display labels
are separate. Guidance is selected by topic and only supplies document-specific instructions for
documents actually requested on that claim. Monetary values are decimal USD strings in fixtures.

Representative identity is limited to the supplied relationship fixture plus matching policyholder
PII and simulated consent. The default sequence is pending then approved; timeout stays pending.
The fake clock starts at March 10, 2026, and moves only on an Advance time event. Consent expires after
120 seconds. Status checks are eligible every 10 seconds; expiry takes precedence over approval.
Claim appeal deadlines affect guidance, not the phase. There is no real timer or notification worker.

## Limits and extension points

The state is ephemeral and scoped to one browser session. Real persistence would replace that owner
with a server session store or a LangGraph checkpointer, retaining isolation and failed-turn behavior.
Real verification, consent, email, and transfer require service implementations and their own access
contracts. No model output is a substitute for those service results.

Evidence-reference validation protects the structured outcome. Free-form phrasing and semantic
classification still depend on the model and require scenario evaluation. The offline tests exercise
business gates with scripted model outputs; live runs exercise extraction and response quality.
