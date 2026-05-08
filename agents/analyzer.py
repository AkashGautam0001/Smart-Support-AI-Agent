"""
agents/analyzer.py
━━━━━━━━━━━━━━━━━
Ticket analyzer agent. Uses Chain-of-Thought reasoning to classify
tickets before routing. The <thinking> block forces step-by-step
reasoning, dramatically reducing misclassification on ambiguous tickets.

PROMPT ENGINEERING: Chain-of-Thought (CoT)
"""

import logging
import anthropic
from prompts.system_prompts import build_analyzer_system_prompt
from core.parser import parse_analysis

logger = logging.getLogger(__name__)


class TicketAnalyzer:
    """
    Analyzes customer support tickets using CoT reasoning.
    Produces: category, sentiment, priority, summary, suggested actions.

    The CoT approach here is critical — without it, ambiguous tickets
    like "My account is locked" get misrouted (billing? technical? security?).
    With CoT, the model reasons through context clues before deciding.
    """

    MODEL = "claude-haiku-4-5-20251001"  # Fast + cheap for analysis pass
    MAX_TOKENS = 1024

    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self._system_prompt = build_analyzer_system_prompt()
        self._call_count = 0
        self._error_count = 0

    def analyze(self, sanitized_ticket: str, ticket_id: str = "") -> dict:
        """
        Analyze a sanitized ticket (post-injection-guard) using CoT.

        Args:
            sanitized_ticket: The XML-isolated ticket content from InjectionGuard
            ticket_id: Optional ID for logging

        Returns:
            Parsed analysis dict with category, sentiment, priority, etc.
        """
        self._call_count += 1
        prefix = f"[Ticket {ticket_id}]" if ticket_id else "[Analyzer]"

        user_prompt = f"""Analyze the following customer support ticket using the step-by-step
reasoning process described in your instructions.

{sanitized_ticket}

Think through your reasoning carefully in the <thinking> block before
producing the final structured output."""

        try:
            logger.debug(f"{prefix} Sending to analyzer model...")
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=self._system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            raw = response.content[0].text
            logger.debug(f"{prefix} Raw analyzer output:\n{raw[:300]}...")

            result = parse_analysis(raw)
            result["ticket_id"] = ticket_id
            result["model"] = self.MODEL
            result["input_tokens"] = response.usage.input_tokens
            result["output_tokens"] = response.usage.output_tokens

            logger.info(
                f"{prefix} Analyzed → category={result['category']}, "
                f"priority={result['priority']}, sentiment={result['sentiment']}"
            )
            return result

        except Exception as e:
            self._error_count += 1
            logger.error(f"{prefix} Analysis failed: {e}")
            # Return safe defaults on failure
            return {
                "thinking": f"Analysis failed: {str(e)}",
                "category": "general",
                "sentiment": "neutral",
                "priority": "medium",
                "priority_reason": "Analysis unavailable — default routing applied",
                "summary": "Unable to analyze ticket",
                "repeat_contact": False,
                "estimated_resolution_time": "unknown",
                "suggested_actions": ["Manual review required"],
                "ticket_id": ticket_id,
                "error": str(e),
            }

    @property
    def stats(self) -> dict:
        return {
            "total_calls": self._call_count,
            "errors": self._error_count,
            "success_rate": f"{((self._call_count - self._error_count) / max(self._call_count, 1)) * 100:.1f}%"
        }
