# Insurance claims SOP demo

A text-chat demo that combines a fixed insurance support workflow with natural-language responses.
LangGraph controls identity verification, claim access, phase changes, and follow-up choices.
An OpenRouter model interprets the caller's messages and answers from authorized fixture data.

```text
VERIFY_ID -> RESOLVE_INTENT -> PROCESS_CASE -> POST_PROCESS
```

Email delivery, representative consent, and human transfer are simulated. Claim records are
read-only.

- [Delivery guide](docs/code/delivery-guide.md): demo walkthrough, configuration, and assignment
  coverage.
- [Workflow design](docs/code/workflow.md): state ownership, model contracts, and access controls.
- [Evaluation guide](evals/README.md): scenarios, deterministic checks, and response review.
- [Original assignment](docs/assignment/original.txt): the acceptance reference.

## Repository layout

The application is grouped by responsibility. Prompts and fixtures live with the code that loads
them; evaluation scenarios live with their runner and review guidance.

```text
app.py                       Streamlit entry point
apps/insurance_claims/
  workflow/                  Graph, SOP rules, identity, memory, and outcomes
  llm/                       OpenRouter client, structured calls, and prompts/
  data/                      Authorized repository and synthetic fixtures/
  ui/                        Chat, API key form, and diagnostic views
  observability/             Langfuse tracing and export privacy
  schemas/                   Shared input, record, and session contracts
evals/                       Live runner, rubric, review history, and cases/
tests/                       workflow/, llm/, ui/, observability/, and evals/
docs/                        assignment/, code/, and assets/
```

See [code organization](docs/code/workflow.md#code-organization) for package ownership and the
agentic chatbot projects used as references. Add code to the package that owns its responsibility.

## Before you begin

Use the provided synthetic callers. You need an
[OpenRouter API key](https://openrouter.ai/settings/keys) with access and credits for the selected
model. Model calls incur usage charges. The default model is `anthropic/claude-sonnet-4.6`.

For a local installation, install Python 3.12 or later and [uv](https://docs.astral.sh/uv/).
For a container installation, install and start Docker.

## Run locally

1. In the repository directory, install the locked dependencies:

   ```shell
   uv sync --locked
   ```

2. Start the app:

   ```shell
   uv run streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
   ```

3. Open [the local demo](http://127.0.0.1:8501).
4. In **Connect to OpenRouter**, enter your **OpenRouter API key**, then click **Use API key**.
   Chat becomes available. OpenRouter checks the key when you send your first message.

You can start the UI without a `.env` file. A key entered in the UI is held in server memory for
that browser session. It is not written to disk or included in conversation exports. To remove it,
click **Clear session key**. A configured server key then applies, if available.

## Run with Docker

1. In the repository directory, build the image:

   ```shell
   docker build -t insurance-sop .
   ```

2. Start the container:

   ```shell
   docker run --rm --name insurance-sop -p 127.0.0.1:8501:8501 insurance-sop
   ```

3. Open [the local demo](http://127.0.0.1:8501) and enter your key in **Connect to OpenRouter**.

The image includes the app, prompts, fixtures, and locked runtime dependencies. It runs as a
non-root user and excludes `.env`, local outputs, and development tools. Stop it with
`docker stop insurance-sop` in another terminal. Conversation state is not persisted.

## Try the assignment example

1. In the chat, send:

   ```text
   I'm the policyholder. My name is Margaret Chen, policy POL-9921. I'm calling about my denied
   healthcare claim from January. DOB is 1985-03-15, SSN last four is 4472.
   ```

   The expected result is three matching identity fields, selection of `CL-2048`, and an explanation
   of the missing pathology report and office note. **Workflow state** shows the phase history.

2. Ask `Can I send a scan?` to exercise a grounded follow-up.
3. Send `That answers my question, that's all.` to request closing.
4. When offered a summary, choose send or skip. Send creates an email draft and records simulated
   delivery. No email is sent. **Download outcome** exports the completed support result.

The email choice defaults to skip after 120 seconds on the demo clock. To test it, leave the choice
pending, select **120 seconds** under **Advance by**, and click **Advance time**. This completes
the conversation without sending email. Real elapsed time does not advance this demo clock.

In every phase, the conversation also times out after **180 seconds without a caller message**
on the same step clock. Each caller message restarts that wait. Use **Advance time → 180 seconds**
to test it. When a step crosses multiple deadlines, the earlier email or consent timeout applies
first. The demo displays the rule and remaining conversation time.

For a demo that pauses at verification and checks early memory, follow the
[full walkthrough](docs/code/delivery-guide.md#walk-through-the-four-phases).

## Configure the model

The UI key takes precedence over `OPENROUTER_API_KEY` in the environment, which takes precedence
over the project `.env` file. Server keys are never prefilled into the password field.
`OPENROUTER_MODEL` selects a model with
[structured output support](https://openrouter.ai/docs/guides/features/structured-outputs).
If unset or blank, it uses the default model.

Only an OpenRouter API key and a model are needed for chat; the model has the default above.
Langfuse is optional. Missing, partial, or blank Langfuse connection settings disable tracing
without blocking the app.

For command-line live evaluations or optional monitoring, create a `.env` file from `.env.example`
only if you do not already have one. Set `OPENROUTER_API_KEY` there. Keep it out of version control.
See [configuration and monitoring](docs/code/delivery-guide.md#configure-server-settings) for
details.

## Run checks

```shell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

These checks run without model credentials. Tests substitute the model boundary while exercising
real workflow code, fixtures, streaming, and UI state.

To run selected scenarios against OpenRouter, configure a server key, then run:

```shell
uv run python -m evals --case upfront recovery scope_retries \
  --output outputs/review.json
```

This command incurs model usage. It saves transcripts, authorized evidence, before/after state,
and email drafts. Review the output using the [behavioral rubric](evals/rubric.md).
A deterministic state pass does not establish response quality. Use `--list` to list cases offline
or `--case all` to run the full collection.

## Understand the demo boundaries

Each browser session owns its conversation and key override. **New conversation** clears dialogue,
workflow state, and local traces while retaining the key. Reloading or restarting can lose the
session.
Failed turns leave the previous conversation unchanged and display an error.

Identity checks compare supplied details with synthetic records; they are not production identity
proofing. The full dialogue within the current identity boundary goes to the model. The inspector
and **LLM debug** tab display caller data. Optional Langfuse export masks known fixture identities,
but it is not a general personal-data detector.

The delivery is a runnable repository with a Docker build definition. See the
[delivery verification record](docs/code/delivery-guide.md#delivery-verification) for completed
checks and remaining evaluation limits.
