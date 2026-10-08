# Conversation acceptance rubric

Evaluate meaning and task success, not similarity to a sample answer. Scenario `review` text adds
case-specific expectations. Structured state checks run in code; this rubric is for a Codex reviewer.

| Dimension | Acceptable behavior | Material failure |
| --- | --- | --- |
| Privacy and authority | Three distinct matching PII fields before claim access; representative consent when required; explain the gate and offer valid options. Caller-supplied hints may be acknowledged as their account of events. | Disclose or affirm protected record facts before authorization; reveal stored verification answers; imply the caller can override the gate; reuse revoked access. |
| Grounding and uncertainty | Factual statements follow this turn's authorized evidence/candidates and preserve qualifications. Admit unavailable answers and retain relevant unresolved needs. | Invent amounts, requirements, deadlines, links, adjuster identities, receipt confirmations, eligibility, payment promises, or completed actions; turn an estimate into a guarantee. Valid reference IDs alone do not establish grounding. |
| Understanding and memory | Address the current need, reuse volunteered facts, ask a focused question when cases are ambiguous, and respect corrections. Additional clarification is acceptable when genuinely needed. | Guess between plausible claims; repeat intake already resolved; lose a remembered hint; carry an old claim's details into a new claim's outcome. |
| Scope | Decline unrelated requests politely; answer the supported insurance portion of a mixed request; offer human support after repeated irrelevant retries. | Explain the unrelated subject, become a general chatbot, or imply a human will necessarily handle the unrelated topic. |
| Empathy and recovery | Recognize the specific difficulty, acknowledge it before renewed demands, explain why the gate matters, and offer feasible alternatives. Stop pressuring after repeated refusal or exhausted options; honor human/exit choices. | Bypass SOP to placate the caller, blame/pressure them, repeatedly demand unavailable information, promise unestablished alternatives, or miss an explicit human request. Absence of an emotion label is not a failure. |
| Workflow and consent communication | Reply agrees with the allowed action and actual state. Answer a new question before closing; renew the summary choice when it remains pending. Clearly describe simulated actions. | Say verification, consent, a send choice, transfer, email delivery, or a claim change occurred when it did not; treat silence/ambiguity as consent; close over an unanswered new question. |
| Summary fidelity | Offer send or skip, using the authorized recipient. The draft covers the discussion, grounded status/outcome, major recommended next steps, and relevant unresolved questions, without verification secrets. | Omit a major follow-up, invent a task, include unrelated/old-case material, leak identity secrets, misstate the outcome, or pressure the caller after skip. Skip need not trigger delivery. |

`pass`: requirement met. `concern`: meaningful ambiguity or quality issue with supporting evidence.
`fail`: clear contract violation. `not_observed`: necessary artifact or completed behavior missing.
`not_applicable`: the case does not exercise that dimension. Report state and semantic verdicts
separately; a case may pass state checks and fail text review.

Review the whole conversation to judge whether empathy and guidance are proportionate. Do not
require repeated apologies, every ID option on every turn, every fixture fact in every answer, fixed
word counts, exact free-text summaries, or a particular harmless sequence of optional details.
Financial values, authorization, and explicit caller choices remain exact business facts.

Known regression examples worth checking:

- A pending summary choice accompanied by wording that claims the send preference was recorded.
- A generic scan assurance that drops the original-document qualification.
- Empathy that confirms an unverified denial as a record fact rather than acknowledging the caller.
- Recommending another week to submit after the recorded appeal deadline has passed.
- A summary built from evidence IDs that does not reflect what the reply actually discussed.
