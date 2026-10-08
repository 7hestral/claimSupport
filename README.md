# Insurance SOP demo

A local text-chat demo using LangGraph, OpenRouter, Pydantic, and Streamlit. It verifies identity,
resolves a claim from remembered hints, answers from fixtures, and records an optional email-summary
choice. Email, representative consent, and human handoff are simulated; no external actions occur.

## Run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```shell
uv sync --locked
cp .env.example .env  # Fresh checkout only; keep your existing .env.
```

Set `OPENROUTER_API_KEY` in `.env`. `OPENROUTER_MODEL` selects a model supporting structured output;
the default is `anthropic/claude-sonnet-4.6`. Environment variables override `.env`.

```shell
uv run streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open [the local demo](http://127.0.0.1:8501). The left panel is chat; the right panel shows masked
memory, phase history, verification, consent status, and follow-up choices. The outcome develops
below the chat and can be downloaded when the conversation ends.

Each browser session has independent in-memory conversation state. New conversation clears it;
refreshing or restarting may lose it. API failures leave the previous session unchanged and display
an error. No database, background worker, or cross-conversation memory is used.

## Try it

Paste this into the chat:

```text
I'm the policyholder. My name is Margaret Chen, policy POL-9921. I'm calling about my denied
healthcare claim from January. DOB is 1985-03-15, SSN last four is 4472.
```

The application verifies three matching PII fields, resolves CL-2048 from the early hint, and
explains the missing pathology report and office note. Follow up with "Can I send a scan?", then
"That answers my question, that's all." Choose send or skip when offered the summary. Send records
the choice and prepares a draft; the application explicitly states that nothing was sent.

Other scenarios:

- Provide only name and policy number with the January hint, then provide DOB and phone later.
- Ask "What is RL?" repeatedly: the third out-of-scope turn offers human support.
- Say "I already told you who I am. Just tell me why it was denied." before verification.
- For national ID, use Ma Tian, DOB 1964-09-10, national ID last four 6688, and the March claim.
- For representative consent, use "I'm David Chen, Margaret Chen's son, calling for her about her
  denied January healthcare claim. Her DOB is 1985-03-15 and her SSN last four is 4472."
  The first simulated check is pending. Advance time by 10 seconds to approve the default scenario.
  For timeout, select timeout, start a new conversation, provide the same details, then advance 120
  seconds. No actual consent request or transfer is sent.
- Start a conversation after March 18, 2026 to exercise Margaret's expired appeal deadline.

The default demo clock is March 10, 2026, 10:00 UTC. Only Advance time moves it. Consent checks are
eligible every 10 seconds, one check per event; the request expires at 120 seconds. Expiry is checked
before polling, so advancing directly to expiry cannot grant late approval.

## Business boundaries

- Code requires three distinct PII matches on one customer, with no contradictory supplied fields.
  Policy number locates a record but does not count. SSN or national-ID last four counts as one field;
  an explicitly supplied ID type must match. Fixture aliases and US phone formatting are supported.
- The representative fixture plus simulated policyholder consent supplies the demo authorization
  scenario. It is not a real representative-authentication service.
- Claim retrieval checks verified customer ownership. Corrections to identity revoke access and
  clear the selected case and outcome. Claim records are never given to the extraction model.
- The shared response model gets phase instructions, masked memory, an application-selected action,
  and authorized evidence. It cannot set the phase, authorize access, or mutate claim records.
- Three distinct failed verification submissions offer human support. Clarifications do not count.
  Two refusal turns without identity progress offer human support. Emotion alone does not count.
  Explicit handoff requests exit.
- A filled outcome does not end processing. The caller must indicate readiness to wrap up without a
  new question. Email choice is accepted only after the summary offer; silence is not consent.
- Outcomes retain fixture-backed facts and suggested steps separately from unchanged claim status.
  Document IDs are normalized across fixtures. Expired deadlines override generic submission timing.

Structured output validates shape and evidence references; it does not prove every generated sentence
is semantically grounded. Scope and intent classification are also model interpretations. Use the
fixture scenarios to evaluate those behaviors. The demo is not a production identity service.

## Code

```text
app.py                         Streamlit entry point
apps/insurance_claims/
  prompts/                     extraction, shared response, and phase instructions
  schemas/                     memory, model outputs, records, and session state
  workflow.py                  interpret -> decide -> compose -> record
  policy.py                    phase gates and bounded case selection
  identity.py                  verification and simulated consent timing
  repository.py                validated fixtures and guarded claim reads
  guidance.py                  applicable claim and document evidence
  memory.py                    fact merging and access invalidation
  presentation.py              model context, outcome, email draft, and inspector
  reasoner.py                   two structured calls to the same model
  llm_calls.py                  streaming, output validation, token usage, and call events
  monitoring.py                 Langfuse turn, generation, and decision observations
  trace_privacy.py              fixture identity masking at telemetry export
  context.py                    bounded dialogue windows
  debug_ui.py                   local model traces and token totals
  model.py                     OpenRouter configuration
  ui.py                        chat and demo controls
  fixtures/                    sample customers, claims, and guidance
```

See [workflow design](docs/code/workflow.md) for state ownership and extension boundaries.

## Checks

```shell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Tests substitute the model boundary while exercising the actual graph and fixtures. They require no
API key. Model interpretation and phrasing should additionally be checked through the live UI.

An optional live acceptance check makes OpenRouter calls using `.env` and incurs model usage:

```shell
uv run python -m scripts.live_smoke
uv run python -m scripts.live_smoke --case all
```

See [test coverage and review criteria](test_cases/README.md) and the reusable natural-language
[original scenarios](test_cases/conversations.json). The runner also loads the identity, claim
resolution, document recovery, and scope/consent collections in `test_cases/`; use `--list` to see
all cases or `--case <id> <id>` to select a group. Live checks save before/after state, replies,
authorized evidence, and the actual email draft to `outputs/live-conversations.json`.
Use the repository's [SOP review skill](.agents/skills/sop-eval-review/SKILL.md) and
[behavioral rubric](test_cases/rubric.md) to grade those artifacts. Deterministic checks enforce
business gates and field population; text review judges meaning without exact-wording snapshots.

There is no turn-count limit. Model history uses a sliding window of up to 24,000 JSON characters;
the latest message and structured caller memory are always included. The full transcript remains
visible in the UI. A completed, ended, or handed-off conversation requires starting a new one.

The **LLM debug** tab shows input/output token totals separately for extraction and response. Each
call exposes its prompts, output schema, raw output, parsed result, latency, and provider token
metadata. During a turn, a live debug panel streams raw JSON; the customer reply appears only after
validation. Failed-call diagnostics survive a failed turn. Missing token metadata is shown as
unavailable. Raw debug inputs contain supplied identity details; this is a local tester console.
New conversation clears the traces. No API key or transport headers are recorded.

## Langfuse monitoring

Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` in the project `.env`.
Tracing starts automatically for UI turns and live evaluation runs. Environment variables override
the file; `LANGFUSE_TRACING_ENABLED=false` explicitly disables export. Missing keys leave monitoring
off, while a partially configured setup is rejected. Restart the app after changing credentials.

Each conversation is a Langfuse session. Each turn has a `support-turn` trace containing
`extract-facts` and `compose-reply` generations and an `apply-sop` decision span. Fixed replies skip
the response generation. Generations contain the actual prompts, context, output schema, prompt
hash, model, usage, and latency; the decision span records interpreted facts, authorization, and
allowed evidence. Root metadata includes before/after state and the final summary draft. Filter by
`insurance-sop`, `evaluation`/`ui`, and scenario `case_id`. Live reports include direct trace links
and flush the exporter before exiting. Langfuse cost totals depend on its model-pricing match.

Export masking pseudonymizes known fixture identity values and common email/phone forms while
preserving differences between identities. Model inputs and SOP state are never changed by masking.
This is a fixture-data demo, not a general PII detector: arbitrary names and unrecognized identity
formats in free text are not guaranteed to be removed. Use the provided synthetic callers.
Offline tests disable remote export; the instrumentation test uses an in-memory SDK exporter.
