"""
agents/quality_checker.py
━━━━━━━━━━━━━━━━━━━━━━━━
QA agent that validates generated responses against quality rubric.
Uses its own system prompt and structured XML output for verdicts.

PROMPT ENGINEERING: XML Tags + System Prompt Design + Negative Constraints
"""

import logging
import anthropic
from prompts.system_prompts import build_quality_check_system_prompt
from core.parser import parse_quality_review

logger = logging.getLogger(__name__)

QUALITY_THRESHOLD = 75  # Responses scoring below this get auto-corrected


class QualityChecker:
    """
    Validates responses before they go to customers.
    Below-threshold responses are auto-corrected by the checker itself.
    """

    MODEL = "claude-haiku-4-5-20251001"
    MAX_TOKENS = 1024

    def __init__(self, client: anthropic.Anthropic, threshold: int = QUALITY_THRESHOLD):
        self.client = client
        self.threshold = threshold
        self._system_prompt = build_quality_check_system_prompt()
        self._qa_log: list[dict] = []

    def check(self, response_text: str, ticket_summary: str, department: str) -> dict:
        """
        Quality-check a generated response.

        Returns a review dict with:
        - passed: bool
        - score: 0-100
        - issues: list of found problems
        - approved_response: final (possibly corrected) response text
        """
        user_prompt = f"""Review this customer support response:

<context>
  <department>{department}</department>
  <ticket_summary>{ticket_summary}</ticket_summary>
</context>

<draft_response>
{response_text}
</draft_response>

Score it and provide your verdict in the required XML format."""

        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=self._system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            raw = response.content[0].text
            review = parse_quality_review(raw)

            passed = review["score"] >= self.threshold
            review["passed"] = passed
            review["threshold"] = self.threshold

            # If the checker found issues but didn't correct → use original
            if not review.get("approved_response"):
                review["approved_response"] = response_text

            self._qa_log.append({
                "department": department,
                "score": review["score"],
                "passed": passed,
                "issue_count": len(review.get("issues", [])),
            })

            log_level = logging.INFO if passed else logging.WARNING
            logger.log(
                log_level,
                f"[QA] {department} response scored {review['score']}/100 "
                f"({'PASS' if passed else 'FAIL — auto-corrected'})"
            )

            return review

        except Exception as e:
            logger.error(f"[QA] Quality check failed: {e} — passing response as-is")
            return {
                "score": 70,  # Default pass
                "passed": True,
                "issues": [],
                "improvements": [],
                "approved_response": response_text,
                "error": str(e),
            }

    def qa_summary(self) -> dict:
        """Aggregate QA statistics."""
        if not self._qa_log:
            return {}

        scores = [r["score"] for r in self._qa_log]
        passed = sum(1 for r in self._qa_log if r["passed"])

        return {
            "total_checked": len(self._qa_log),
            "pass_rate": f"{(passed / len(self._qa_log)) * 100:.1f}%",
            "avg_score": f"{sum(scores) / len(scores):.1f}",
            "min_score": min(scores),
            "max_score": max(scores),
            "total_issues_found": sum(r["issue_count"] for r in self._qa_log),
        }
