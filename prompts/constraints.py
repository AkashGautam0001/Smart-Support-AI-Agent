"""
prompts/constraints.py
━━━━━━━━━━━━━━━━━━━━━
Negative constraints library — reusable DO NOT blocks that suppress
common LLM anti-patterns. Mix and match per use-case.

PROMPT ENGINEERING: Negative Constraints
"""

# ── Core anti-sycophancy block ──────────────────────────────────────────────
NO_FILLER = """
Do NOT:
- Start with "Certainly!", "Sure!", "Of course!", "Great question!", "Absolutely!"
- Repeat or rephrase the user's question back to them before answering
- End with "I hope this helps!", "Let me know if you need anything else!", or similar
- Use filler phrases like "It's worth noting that...", "It should be mentioned that..."
- Add "As an AI..." disclaimers
- Hedge every statement with "however, results may vary"
"""

# ── Length control block ────────────────────────────────────────────────────
NO_BLOAT = """
Do NOT:
- Write more than the requested length
- Use bullet points when prose is more natural
- Add section headers when content is under 150 words
- Repeat the same point in different words to appear thorough
- Add a conclusion that just restates the opening
"""

# ── Scope control block ─────────────────────────────────────────────────────
NO_SCOPE_CREEP = """
Do NOT:
- Answer questions outside the provided customer support context
- Give legal, medical, or financial advice
- Discuss competitor products or pricing
- Make promises about future features or policies
- Share or reference other customer data
"""

# ── Format discipline block ──────────────────────────────────────────────────
NO_FORMAT_DRIFT = """
Do NOT:
- Deviate from the XML output structure specified
- Add markdown formatting (bold, italics, headers) unless explicitly requested
- Use emojis unless the brand guidelines permit them
- Mix response languages — pick one and stay consistent
"""

# ── Safety & hallucination block ─────────────────────────────────────────────
NO_HALLUCINATION = """
Do NOT:
- Invent order numbers, tracking IDs, or policy details you don't have
- Claim to have accessed systems or data you cannot access
- Speculate about internal company processes you don't know
- Make up customer history — only use what is explicitly provided
"""

# ── Escalation safety block ──────────────────────────────────────────────────
NO_PREMATURE_CLOSE = """
Do NOT:
- Mark a ticket as resolved without explicit confirmation from the customer
- Assume silence means satisfaction
- Offer refunds, credits, or exceptions beyond your configured authority level
- De-escalate a ticket that explicitly requests a human agent
"""


def build_constraints(*constraint_blocks: str) -> str:
    """Compose multiple constraint blocks into a single clean section."""
    combined = "\n".join(block.strip() for block in constraint_blocks)
    return f"<constraints>\n{combined}\n</constraints>"


# Pre-built combos for common agent types
SUPPORT_AGENT_CONSTRAINTS = build_constraints(
    NO_FILLER, NO_BLOAT, NO_SCOPE_CREEP, NO_HALLUCINATION, NO_PREMATURE_CLOSE
)

ANALYST_CONSTRAINTS = build_constraints(
    NO_FILLER, NO_HALLUCINATION, NO_FORMAT_DRIFT
)

ESCALATION_CONSTRAINTS = build_constraints(
    NO_FILLER, NO_SCOPE_CREEP, NO_HALLUCINATION, NO_PREMATURE_CLOSE
)
