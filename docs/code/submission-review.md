# Submission review — October 9, 2026

The repository implements the assignment's four-phase demo. Docker and the hosted UI both ran
real OpenRouter conversations successfully. The review found three defects and corrected them
locally. The original revision is tagged **v0**; the reviewed corrections are included in **v1**.
The hosted app tested in this review used v0; its deployment must be checked again after updating.

## Reference and scope

The acceptance reference was `/Users/rayz/Downloads/apps/instruction.txt`, which is byte-identical
to [the preserved assignment](../assignment/original.txt). The original starter fixtures were also
compared. Claim facts are unchanged; document keys were normalized and display labels added.

GitHub's default HEAD and local HEAD were both `b61d500fa23046546eca5de638e2992804185028` before
the review. The subsequent v1 release packages these corrections; hosted verification below predates
that release. Review and corrections were made by the
same agent, using the [SOP rubric](../../evals/rubric.md); this is self-review, not independent review.

## Requirement coverage

| Requirement | Evidence and result |
| --- | --- |
| Runnable delivery and clear setup | Locked installation, Docker builds, HTTP health checks, and UI startup passed. |
| Accept a model API token | Entered the `.env` OpenRouter key through both browser UIs; real model calls completed. No credential value is included in this report. |
| Natural-language test UI | Hosted and Docker browser conversations reached completed outcomes. |
| Fixed four-phase workflow | Both browser inspectors recorded VERIFY_ID → RESOLVE_INTENT → PROCESS_CASE → POST_PROCESS. |
| Three PII fields and protected claim access | Hosted partial-name input stayed in verification; name, DOB, and SSN last four then selected CL-2048. Offline and live revocation/consent checks passed. |
| Remember early intent and requests | January denial hint and early scan/review-time questions survived verification in live cases. |
| Grounded claim answers | Original model replies inferred an unsupported submission route. Corrected prompts passed the selected fresh semantic review. |
| Optional summary, send or skip | Hosted send produced a draft and simulated delivery; Docker skip completed without delivery. Live summary drafts retained status, discussion, and next steps. |
| Reject unrelated questions and escalate retries | Live unrelated and mixed-topic cases passed; the third unrelated retry offered human support. |
| Bonus empathy and recovery | Live frustration, anxiety, refusal, alternate-ID, and representative-consent scenarios passed after correcting refusal progress. |

## Findings and corrections

1. **Repeated identity could reset refusal recovery.** In baseline `refusal`, turn 3, the extractor
   repeated the stored name during “I still refuse.” The counter reset to zero and the deterministic
   human-offer flag was false. Memory merging now compares normalized old/new identity fields;
   repeating a name is not progress. A regression failed before the fix and passes afterward,
   including recovery when the caller supplies a genuinely new field.
2. **Unsupported routes and callback promises.** Baseline `upfront`, turn 1, prescribed documents
   “as part of any appeal or resubmission,” although that turn's evidence only supported obtaining
   copies. Baseline `refusal`, turns 1–3, promised a team member would follow up through another
   channel. Response instructions now explicitly bound recommended routes to supplied evidence
   and explain simulated human requests and email drafts. The hosted original also reproduced the
   unsupported appeal wording, so its successful workflow is not a clean semantic acceptance result.
3. **Premature timeout wording.** In the first boundary run, `email_timeout`, turn 5, the model said
   “The demo clock has now run out” with one second remaining; state checks still passed. Clock-only
   email reminders now come directly from workflow state without a model call. Regression checks
   failed before this correction. The fresh live run says “1 second left,” keeps the choice pending,
   and skips only after the final second.

## Verification

- `uv sync --locked`: passed.
- `uv run pytest -q`: **113 passed** after all code changes.
- `uv run ruff check .`, `uv run ruff format --check .`, `git diff --check`: passed.
- Original and corrected Docker images built. The original, first corrected, and final images
  passed Docker health checks. They run as UID 10001, load the fixtures, and exclude `.env`.
- A three-turn real-model workflow inside the corrected container verified Margaret, selected
  CL-2048, offered the summary, and completed with skip. This ran before the isolated clock-reminder
  correction; the final image was rebuilt afterward.
- The hosted URL accepted a session key, preserved the identity gate, reused the claim hint, offered
  send/skip, and reached `completed` with `simulated_only` delivery. Docker's UI completed with skip.
- A Git archive contained the required source, prompts, fixtures, lockfile, Dockerfile, setup guide,
  and `.env.example`. Local Markdown links resolved. No tracked file contained a configured `.env`
  credential; `.env` and local evaluation outputs are excluded from Git.

All fresh evaluations used `anthropic/claude-sonnet-4.6`, the documented default, with optional
Langfuse export disabled. The initial eight-case run had two deterministic failures in one refusal
turn. The corrected eight-case run had **28 turns, zero deterministic failures**. The boundary run
had **24 turns, zero deterministic failures**, but the timeout prose failure above. Its six-turn
timeout case was rerun after correction and passed state and semantic review.

The table below grades the latest reviewed result for each case. `P` means pass; `—` means not
applicable/not exercised. Every saved turn and distinct summary draft in these selected runs was
reviewed. These are case-level judgments, not statistical guarantees.

| Case | Privacy | Grounding | Memory | Scope | Empathy | Workflow | Summary | Readability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| early_requests | P | P | P | — | P | P | — | P |
| upfront | P | P | P | — | — | P | P | P |
| recovery | P | P | P | P | P | P | P | P |
| anxiety | P | P | P | — | P | P | — | P |
| refusal | P | P | P | — | P | P | — | P |
| followup | P | P | P | — | — | P | P | P |
| scope_retries | P | P | P | P | — | P | — | P |
| mixed_scope | P | P | P | P | — | P | — | P |
| payment_switch | P | P | P | — | — | P | P | P |
| consent | P | P | P | — | P | P | — | P |
| consent_timeout | P | P | P | — | P | P | — | P |
| identity_revocation | P | P | P | — | — | P | — | P |
| inactivity_timeout | P | P | P | — | — | P | — | P |
| email_timeout (rerun) | P | P | P | — | — | P | P | P |

Local evidence, intentionally excluded from a GitHub ZIP:

- `outputs/submission-2026-10-09.json`: baseline failures and original replies.
- `outputs/submission-fixed-2026-10-09.json`: corrected eight-case run.
- `outputs/submission-boundaries-2026-10-09.json`: six boundary cases, including the original timer prose failure.
- `outputs/submission-timer-fixed-2026-10-09.json`: corrected timer case.
- `outputs/submission-fixed-container.json`: live corrected-container workflow.
- `outputs/submission-hosted-browser.json` and `outputs/submission-docker-browser.json`: completed browser transcripts/state.
- `outputs/submission-hosted-completed.png`: hosted workflow screenshot.

## Submission boundaries and remaining work

- **GitHub ZIP:** use the v1 tag to include the reviewed fixes and this report. Wait for the hosted
  update and repeat its sample conversation before submitting that URL.
- **Email and human support are simulated.** Send creates a draft and records a choice; no real
  email, transfer, or callback occurs. The assignment requires the offer and choice and does not
  explicitly require an email provider integration. Real delivery would be additional work if
  the reviewer interprets “send” literally.
- **Timeouts use a manual demo clock.** This is documented behavior, not a requirement in the
  original assignment. Waiting in real time does not trigger it.
- **Coverage is bounded.** Fourteen live cases were reviewed, not the full scenario collection.
  Other models, exhaustive paraphrases/injections, real external services, remote Langfuse export,
  cross-platform container builds, and long-running hosted availability were not validated.
- Generated replies can still vary. Passing selected state checks and semantic reviews does not
  prove every future response is grounded.
