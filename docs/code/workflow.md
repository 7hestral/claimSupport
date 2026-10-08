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
scope, a bounded question topic, and conversational choices. It has no customer registry,
claim tools, or phase-setting fields. Extraction runs in every phase; clock events skip extraction.
Omitted/null patch values preserve memory; explicit clear fields remove retracted facts. Corrections
to identity invalidate access, consent, selected case, and outcome before any further claim read.
This is automatic structured extraction on every user turn, not optional form-filling tool calls.

There is no conversation turn cap. The interpreter receives the latest user message in full plus a
contiguous suffix of whole prior messages capped at 24,000 JSON characters. This is a conservative
history budget, not model-specific token counting. Memory, phase, and last action are always included.
The full transcript stays in session state for the UI. Old unstructured details outside the window
are not summarized; unresolved references require clarification. Memory is a schema of useful caller
facts, not a complete semantic summary. Extremely long fact values can still grow model input.
The speaker also receives the latest caller wording and bounded recent dialogue. Identity/case
changes that invalidate prior claim context reset the speaker's dialogue boundary. Its memory omits
identity values; known values in dialogue are redacted by case-insensitive literal matching. This is
best-effort masking, not a general PII detector (alternate date/phone spellings can remain).

The response model receives masked memory, the current phase prompt, a code-selected action, and
authorized evidence. It emits a `DraftReply` with conversational text and evidence references.
Outcome facts and next steps are copied from those references, not accepted as arbitrary model data.
Invalid references fail the turn. Scope rejections, email-choice confirmations, and terminal
handoff/exit replies are deterministic.
Normal turns use two calls to the same OpenRouter model; clock events use at most the response call.

### Extractor contract

`Observation` has nine top-level fields, down from fourteen. `facts` holds fifteen nullable caller
fields (identity, representative role, intent, and case selectors). Omitted facts preserve memory.

| Field | Why code needs it |
| --- | --- |
| facts | Verify identity and resolve the authorized case |
| clear_fields | Explicitly retract previously supplied values |
| scope | Reject unrelated requests and count retries |
| topic | Select applicable fixture guidance |
| refuses_verification | Count explicit refusal, never anxiety/confusion alone |
| conversation_action | One of continue, ask_followup, finish_case, request_human, end_conversation |
| alternatives_exhausted | Offer human review when required documents and substitutes are unavailable |
| email_choice | Explicit send/skip consent, subject to phase checks |
| new_case | Reset case selectors when the caller explicitly switches claims |

The speaker infers tone directly from dialogue. There is no extracted emotion, rewritten question,
or duplicate prose case hint. A single action replaces conflicting finish/follow-up/handoff/exit
booleans; the extractor prioritizes new questions over finishing. The speaker receives phase/action,
non-identity memory, dialogue, scope, verification field availability, consent status, the human
offer flag, authorized candidates/evidence, accumulated outcome, email choice/recipient, and demo date.

### Streaming and diagnostics

`llm_calls.py` binds the JSON schema, streams raw response chunks, collects provider usage metadata,
and validates the completed JSON with Pydantic. Response schemas restrict evidence-reference arrays
to the IDs authorized for that call (and next steps to next-step IDs); no available IDs means an
empty array. Application validation independently enforces those restrictions before saving.
The call emits start/delta/finish diagnostics through
[LangGraph custom streaming](https://reference.langchain.com/python/langgraph/types/StreamWriter).
The UI consumes custom events alongside graph updates. Only the final record-node result commits a
conversation turn; partial stream output is confined to the tester console.

Diagnostics live separately in Streamlit session state so failed calls remain inspectable without
committing partial business state. Each call has a model name, input messages, requested schema,
raw output, validated output, status/error type, elapsed time, and provider-reported token usage.
SDK error messages, API keys, and request headers are not captured. Raw prompts contain caller data
and are explicitly labeled in the local debug console. New conversation clears both state stores.
Usage totals include failed calls when the provider reported usage; absent usage is unknown, not
zero or an estimate. Fixed replies do not generate a response-call trace.

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
