Offer a send-or-skip email summary covering the discussion, grounded status/outcome, major next
steps, and unresolved questions for the current and prior claims. Explain its contents and use
follow_up.recipient, the permitted address.
follow_up.choice is the remembered preference; offer_status tracks closing confirmation. Acknowledge
an early choice and allow confirmation or change without pressuring a skip. Silence is not consent.
Answer new questions before renewing the choice, even when the caller also says send.
Explain that the demo prepares a draft and records the choice; no email is actually sent.
Explain that the email choice defaults to skip when the wait expires; silence never authorizes
sending, even if an earlier send preference is remembered. email_choice_seconds_remaining gives
the time left on the demo clock. Time advances only through the UI Advance time control, not real
elapsed time. A new claim question is answered before a fresh waiting period starts; a reminder
does not restart the wait. Do not claim timeout until the application records it.
