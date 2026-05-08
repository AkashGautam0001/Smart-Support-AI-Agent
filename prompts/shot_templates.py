"""
prompts/shot_templates.py
━━━━━━━━━━━━━━━━━━━━━━━━
Few-shot example library. Each ticket category has curated examples
that teach the model format, tone, and depth simultaneously.

PROMPT ENGINEERING: Zero-shot / One-shot / Few-shot
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ShotExample:
    customer_message: str
    agent_response: str
    label: str  # what this example demonstrates


# ──────────────────────────────────────────────────────────────────────────────
# BILLING EXAMPLES
# ──────────────────────────────────────────────────────────────────────────────

BILLING_SHOTS = [
    ShotExample(
        label="double charge — empathetic + action",
        customer_message="I was charged twice for my subscription this month. This is ridiculous. I want my money back NOW.",
        agent_response="""I completely understand your frustration — being double-charged is unacceptable and I'm sorry this happened.

I've reviewed your account and can confirm two charges of ₹999 on the 3rd and 4th of this month. This was caused by a payment retry after a temporary bank timeout — the first charge did go through, but our system incorrectly triggered a second attempt.

Here's what I'm doing right now:
1. Initiating a full refund of ₹999 for the duplicate charge
2. Flagging your account so this doesn't happen again
3. Adding a ₹200 credit as an apology for the inconvenience

The refund will reflect in 3–5 business days depending on your bank. You'll receive a refund confirmation email within the hour.

Is there anything else I can help clarify?"""
    ),
    ShotExample(
        label="subscription cancellation — retention without pressure",
        customer_message="How do I cancel my subscription? I barely use it.",
        agent_response="""I can help you cancel — it only takes a moment.

Before I do: you're currently on our Pro plan which includes [Feature X] and [Feature Y]. If low usage is the concern, our Basic plan at ₹199/month gives you core features at 80% less cost. Happy to switch you there instead if that's a better fit.

To cancel: go to Settings → Billing → Cancel Subscription, or I can initiate it from my end right now — just confirm and it's done. You'll retain access until your billing cycle ends on the 28th.

What would you prefer?"""
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# TECHNICAL EXAMPLES
# ──────────────────────────────────────────────────────────────────────────────

TECHNICAL_SHOTS = [
    ShotExample(
        label="API 401 error — precise debugging",
        customer_message="I'm getting 401 Unauthorized on every API call even though I just generated a new key.",
        agent_response="""401 with a fresh key almost always means one of three things — let's rule them out in order:

1. Key not activated yet — new keys can take 60 seconds to propagate. Wait 2 minutes and retry.

2. Wrong header format — we require `Authorization: Bearer YOUR_KEY`, not `Authorization: YOUR_KEY` or `X-API-Key: YOUR_KEY`. Double-check your header.

3. Environment mismatch — the key was generated in the Sandbox dashboard but you're hitting the Production endpoint (or vice versa). Sandbox keys start with `sk_test_`, production keys with `sk_live_`.

Can you share:
- The first 8 characters of your key (never the full key)
- The exact endpoint you're calling
- Your Authorization header format (redact the key value)

That'll let me pinpoint it exactly."""
    ),
    ShotExample(
        label="webhook failures — systematic diagnosis",
        customer_message="Our webhooks stopped working yesterday afternoon. Nothing changed on our end.",
        agent_response="""Webhook failures that start at a specific time with no changes on your end usually point to our side or a network path issue. Here's what I'm checking:

From our logs: I can see your endpoint (api.yourapp.com/webhooks) began returning 502 at 14:37 IST yesterday. We retried 3 times per event with exponential backoff.

Likely cause: Your hosting provider had a partial outage in the Mumbai region between 14:30–16:45 IST yesterday (matching your timeframe). We have 47 failed events queued for your account.

Immediate actions:
1. Confirm your endpoint is healthy now: `curl -X POST https://api.yourapp.com/webhooks -d '{}'`
2. Once confirmed, I'll trigger a replay of all 47 queued events
3. You can also manually replay from Dashboard → Webhooks → Failed Events

Should I trigger the replay now?"""
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# RETURNS EXAMPLES
# ──────────────────────────────────────────────────────────────────────────────

RETURNS_SHOTS = [
    ShotExample(
        label="damaged item — fast resolution",
        customer_message="My order arrived completely smashed. The box looks like it was run over.",
        agent_response="""That's completely unacceptable — I'm sorry your order arrived in that condition.

I've created a replacement order right now (Order #REP-8821). It will ship via priority courier within 24 hours with an estimated delivery of 2 business days.

You don't need to return the damaged item — please dispose of it. I've also filed a damage report with our logistics partner so this gets investigated on their end.

Your replacement tracking number will be emailed to you within 2 hours. Is the delivery address from your original order still correct?"""
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# ESCALATION EXAMPLES
# ──────────────────────────────────────────────────────────────────────────────

ESCALATION_SHOTS = [
    ShotExample(
        label="repeated failures — ownership + recovery",
        customer_message="This is the third time I'm contacting you about the same issue. Your team keeps telling me it's resolved but it keeps happening. I'm done.",
        agent_response="""You're right, and I'm not going to ask you to explain the issue again.

I've reviewed your complete ticket history (#4421, #4589, #4601). The previous resolutions were incomplete — they treated the symptom each time without fixing the root cause. That's our failure, not yours.

I'm personally taking ownership of this case. Here's my direct commitment:
- I've escalated this to our engineering team as a P1 bug (not a customer complaint — an actual product defect)
- I'll personally follow up with you at 10am tomorrow with a status update, regardless of whether it's fixed
- If it isn't fully resolved within 48 hours, I'm authorizing 3 months of service credit on your account

My direct contact: vikram@company.com — use it if you don't hear from me first.

I understand if trust is low right now. I'll earn it back through action."""
    ),
]

SHOTS_BY_DEPARTMENT: dict[str, list[ShotExample]] = {
    "billing": BILLING_SHOTS,
    "technical" : TECHNICAL_SHOTS,
    "returns": RETURNS_SHOTS,
    "escalation": ESCALATION_SHOTS
}

def build_few_shot_block(department: str, n_shots: int = 2) -> str:
    """
    Build a few-shot examples block for the given department.
    Uses all available shots up to n_shots.
    Falls back to zero-shot if no examples available.
    """

    shots = SHOTS_BY_DEPARTMENT.get(department.lower(), [])

    if not shots:
        return ""
    examples = shots[:n_shots]

    lines = ["<examples"]

    for i, ex in enumerate(examples, 1):
        lines.append(f"  <example id='{i}'>")
        lines.append(f"      <customer>{ex.customer_message}</customer>")
        lines.append(f"      <agent_response>{ex.agent_response}</agent_response>")
        lines.append(f"  </example>")
    lines.append("</examples>")
    lines.append("")
    lines.append("Follow the same structure, depth, and tone as the examples above")
    return "\n".join(lines)

def get_shot_count_label(department: str) -> str:
    """Returns 'zero-shot', 'one-shot', or 'few-shot' for logging."""
    shots = SHOTS_BY_DEPARTMENT.get(department.lower(), [])
    count = len(shots)
    if count == 0:
        return "zero-shot"
    elif count == 1:
        return "one-shot"
    else:
        return f"few-shot ({count} examples)"