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

## Code organization

`app.py` starts `apps.insurance_claims.ui.app.main`. Application files are grouped under
`apps/insurance_claims/` by the responsibility they own:

| Package | Responsibility |
| --- | --- |
| `workflow/` | `graph.py` coordinates turns; policy, identity, memory, guidance, context, and presentation modules implement the SOP |
| `llm/` | OpenRouter configuration, the reasoner, structured streaming calls, and their `prompts/` resources |
| `data/` | Authorized fixture access in `repository.py` and the synthetic records in `fixtures/` |
| `ui/` | Chat in `app.py`, credential controls in `connection.py`, and diagnostics in `debug.py` |
| `observability/` | Optional Langfuse integration and masking of exported identities |
| `schemas/` | Shared contracts for caller observations, stored records, events, and session state |

The UI owns browser-session state and creates the graph. The graph coordinates the reasoner and
repository; deterministic SOP code owns access and phase changes. Model output is validated at
the LLM boundary. Observability records execution without deciding business state. Shared schemas
have no dependency on UI, model clients, or telemetry.

Keep resources next to their loader. `data.FIXTURES` is the shared fixture location for record
access and telemetry masking. `llm/reasoner.py` loads its adjacent `prompts/`. The application
package defines `PROJECT_ROOT` once for project configuration and entry-point lookup.

`evals/` owns the command-line runner, scenario contracts, `cases/`, rubric, and review history.
Run it with `uv run python -m evals`; `--list` requires no model call. `tests/` groups offline tests
by the subsystem exercised and keeps shared fixtures in `conftest.py`.

### Design references

The layout applies the following patterns to this Streamlit application:

- [BCG X's AgentKit article](https://www.langchain.com/blog/bcg-x-releases-agentkit-a-full-stack-starter-kit-for-building-constrained-agents)
  describes a constrained agent with a separate chat UI and backend. Its
  [backend layout](https://github.com/BCG-X-Official/agentkit/tree/80f4a0bb192b0a49269113d57cfdde87903316a0/backend/app/app)
  groups services, data access, and schemas by responsibility. AgentKit is archived; it is an
  architectural reference here.
- [Vercel's AI SDK 4.0 article](https://vercel.com/blog/ai-sdk-4-0#updated-chatbot-template)
  links a working chatbot product. The inspected
  [repository](https://github.com/vercel/ai-chatbot/tree/c2f8235e1f3ea903ad8b7f61447c4f74164b5c58)
  separates chat components, `lib/ai`, `lib/db`, and test groups. This informs the UI, LLM, data,
  and test boundaries above.
- [LangGraph's application structure guide](https://docs.langchain.com/oss/python/langgraph/application-structure)
  keeps graph construction in a clear module with supporting code in packages. Here,
  `workflow/graph.py` is that module, and package names identify their responsibilities.

## Connection ownership

`llm.model.load_model_settings` resolves a UI key override before environment variables and the project
`.env` file. The default model is `anthropic/claude-sonnet-4.6`. `create_model` rejects an empty key
before constructing the OpenRouter client. Configuration loading makes no API call.

`ui/connection.py` owns the masked key-entry form. The override lives in Streamlit session state,
separate from the business `Session`, prompts, traces, and downloaded outcomes. It never mutates
environment variables or writes `.env`. Server credentials are not sent to the password widget.
Replacing or clearing the key discards the cached workflow client while preserving conversation
state. A new conversation clears the graph and traces but retains the key override. With no key,
chat and clock submissions are disabled. Clearing an override restores the configured server key,
if present. OpenRouter validates the credential on the first model request.

See the [delivery guide](delivery-guide.md) for setup, credential lifetime, and the demo
walkthrough.

## Model boundaries

The interpreter receives dialogue, identity memory, optional caller case hints, current selected
case ID, phase, and last action. It emits an `Observation` containing identity and case-hint
patches,
explicit retractions, optional identity clarifications, multiple guidance topics, scope, and bounded
conversational choices. It has no customer registry,
authoritative claim object, or phase-setting fields. Extraction runs in every phase; clock events
skip extraction. Null patch values preserve memory. An identity correction invalidates access,
consent, selected case, and outcome; normalized casing/phone-format changes preserve access.

Both models receive the full conversation within the current identity boundary. This preserves
requests volunteered before verification and multi-part questions without an extracted `intent_hint`
or single `topic`. An identity change after claim access excludes previous protected dialogue.
Claim switches retain dialogue for conversational continuity, but only current authorized evidence
establishes facts about the newly selected claim. Caller values remain visible in dialogue and the
inspector; no `[provided]` substitution is applied. Telemetry export pseudonymization is separate.

`clarifications` defaults to an empty list. An entry contains the identity `field`, the ambiguous
`provided_value`, and a bounded `reason` (`ambiguous_date_order` or `ambiguous_value`). It explains
the extractor's uncertainty to the speaker without granting access or changing workflow actions.
Entries are per-turn, not stored preferences; a clear answer removes the need for an entry.
An ambiguous correction still retracts the old value through `clear_fields`. As with the other
structured-output fields, the model's wire schema includes the key, using `[]` when not applicable.

There is no silent history window or turn cap. Extremely long chats can hit the model context limit;
production use would need explicit summarization of unresolved needs/corrections before discarding
old turns. A failed model call remains an atomic failed turn, not a silent loss of memory.

The response model knows the whole four-stage journey and receives the current phase prompt,
code-selected action, only that action's instructions, topic-selected authorized evidence, optional
case hints, and follow-up state. `llm/prompts/actions.json` supplies the current instruction; unrelated
actions are not included in the response prompt.
It selects relevant guidance and may answer multiple questions in one response. It emits
`DraftReply`
with text and evidence references. Outcome facts and next steps are copied from referenced evidence.
Invalid references fail the turn. Scope rejections, final email confirmations, and handoff/exit
replies
are deterministic. Normal turns use two calls; clock events use at most the response call.

### Guidance selection and topic reduction

`Observation.topics` contains zero or more bounded subjects requested in the current turn. It is
not an intent summary or a replacement for conversation history. `Session.pending_topics` appends
and deduplicates these in first-seen order, including before verification or while consent/case
selection is pending. A successful claim response appends/deduplicates them into `Outcome.topics`
and clears the pending list. This records which subjects reached the speaker, not proof that its
answers were correct; unresolved questions and semantic review remain separate.

Retrieval includes core authorized claim facts, then only the union of guidance needed by pending
topics. Document acceptance qualifications accompany format/alternative guidance. Receipt alone
does not load past document-format or processing-time rules. Unknown/general topics do not expand
to the whole fixture. Expired deadlines remain an unconditional safety constraint; payment fields
are included for payment requests or open/closed claim overviews. Follow-up text is indexed by its
fixture key at repository load time; unrelated fixture rules are not added to response evidence.

An explicit claim switch clears pending topics, while the old claim's handled topics stay with its
archived outcome. Same-claim refinements retain that history. Identity changes after claim access
clear pending topics and all outcomes; initial partial verification preserves early requests.
Closing summaries use recorded outcomes, so reducing current evidence does not erase prior answers.

### Extractor contract

| Field | Why code needs it |
| --- | --- |
| facts | Caller-provided identity and representative fields for verification |
| clear_fields | Retract identity values |
| clarifications | Optional per-turn identity ambiguity metadata for the conversation agent; defaults to [] |
| topics | Multiple requested guidance subjects; appended/deduplicated into pending_topics |
| case_hints | Optional type/status/month/year/ID clues for authorized claim selection |
| clear_case_fields | Retract case search clues without changing the database |
| scope | Reject unrelated requests and count retries |
| refuses_verification | Count explicit refusal, not emotion alone |
| conversation_action | continue, ask_followup, finish_case, request_human, or end_conversation |
| alternatives_exhausted | Offer human review when documents and substitutes are unavailable |
| email_choice | A per-turn send/skip signal, merged into the one stored follow_up.choice |
| new_case | Clear old search clues for an explicit switch |

Conversation history carries intent and tone. Case hints are never mandatory verification fields.
Questioning the recorded status is not a case-hint correction. Changes to optional hints trigger
case resolution without identity verification; resolving to the same claim preserves its outcome.
Selecting a different claim archives the active outcome by claim ID and starts or resumes the
selected claim's outcome. The final email includes both prior and current discussed claims, clearly
attributed. Identity changes clear both. Case switches renew email confirmation while retaining
this customer's preference. `follow_up.offer_status` tracks whether the final choice is pending or
confirmed; `delivery` separately records the simulated action. A choice with a new question never
closes before the question is answered.

### Streaming and diagnostics

`llm/calls.py` binds the JSON schema, streams raw response chunks, collects provider usage metadata,
and validates the completed JSON with Pydantic. Response schemas restrict evidence-reference arrays
to the IDs authorized for that call (and next steps to guidance/next-step IDs, excluding claim
facts); no available IDs means an
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
| RESOLVE_INTENT | Exactly one authorized matching case; the speaker uses dialogue to understand or clarify the need |
| PROCESS_CASE | A discussed outcome and caller readiness without another follow-up question |
| POST_PROCESS | Explicit send/skip after the offer, or timeout with automatic skip |

An identity correction restarts verification. An explicit case change restarts case resolution.
Follow-up questions during the summary offer remain in POST_PROCESS and are answered before renewing
the offer. Human requests and explicit conversation exits are terminal dispositions outside normal
phase progression. Neither path grants access or claims that an external action succeeded.

The email choice starts a 120-second wait on the demo clock when first offered.
`follow_up.expires_at` records its deadline. At or after that deadline, code sets `choice=skip`,
`offer_status=timed_out`, `delivery=not_requested`, and `disposition=completed`. This overrides an
unconfirmed early send preference and uses a fixed reply without a model call. Timeout is not
caller confirmation. The existing draft and support outcome remain available.

A new claim question is answered before renewing the offer with a fresh 120 seconds. Clock
reminders preserve the deadline. Identity changes clear the offer; case resolution cancels the
old wait, including when updated hints resolve to the same case. Failed turns commit neither the
answer nor a renewed deadline. Expiry uses **Advance time**, with no background wall-clock timer.

All phases also have a 180-second inactivity deadline, `inactivity_expires_at`, initialized from
the session's demo time. A caller-message turn renews it; clock events and UI reruns do not. At
expiry, code sets `disposition=timed_out`, defaults email to skip, and returns a fixed closing
reply without model generation. Later turns are rejected until a new conversation starts.
Failed turns retain the previous deadline along with the previous business state.

Policy checks expiry before business routing. An earlier pending email or representative-consent
deadline takes precedence when one clock step crosses multiple deadlines. The remaining time is
visible in the sidebar. There is no real-time inactivity timer.

## Data and time

`FixtureRepository.claims_for` and `claim_for` enforce access and customer ownership. Claim status
is
read-only. Document requirements use canonical identifiers shared with guideline keys; display
labels
are separate. All applicable guidance is supplied together, with document-specific instructions only
for
documents actually requested on that claim. Fixture topic labels are evidence identifiers, not a
required classifier. Monetary values are decimal USD strings in fixtures.

Representative identity is limited to the supplied relationship fixture plus matching policyholder
PII and simulated consent. The default sequence is pending then approved; timeout stays pending.
The fake clock starts at March 10, 2026, and moves only on an Advance time event. Consent expires
after
120 seconds. Status checks are eligible every 10 seconds; expiry takes precedence over approval.
Claim appeal deadlines affect guidance, not the phase. There is no real timer or notification
worker.

## Limits and extension points

The state is ephemeral and scoped to one browser session. Real persistence would replace that owner
with a server session store or a LangGraph checkpointer, retaining isolation and failed-turn
behavior.
Real verification, consent, email, and transfer require service implementations and their own access
contracts. No model output is a substitute for those service results.

Evidence-reference validation protects the structured outcome. Free-form phrasing and semantic
classification still depend on the model and require scenario evaluation. The offline tests exercise
business gates with scripted model outputs; live runs exercise extraction and response quality.
