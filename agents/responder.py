"""
agents/responder.py
━━━━━━━━━━━━━━━━━━
Response generation agent. Combines role prompting, few-shot examples,
XML output structure, system prompt design, and negative constraints
to produce consistent, high-quality support responses.

PROMPT ENGINEERING: Role Prompting + Few-shot + XML + System Prompt + Constraints
"""

import logging
import anthropic
from prompts.system_prompts import build_response_system_prompt
from prompts.shot_templates import get_shot_count_label
from core.parser import parse_agent_response

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """
    Generates customer support responses using the appropriate department persona,
    few-shot examples, and structured XML output.

    Each department uses a different persona (role prompting) and different
    few-shot examples. The system prompt layers all components together.
    """

    MODEL = "claude-sonnet-4-6"  # Better model for customer-facing responses
    MAX_TOKENS = 1024

    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self._response_log: list[dict] = []

    def generate(
        self,
        sanitized_ticket: str,
        analysis: dict,
        customer_context: dict,
        n_shots: int = 2,
    ) -> dict:
        """
        Generate a response for the analyzed ticket.

        Args:
            sanitized_ticket: XML-isolated ticket from InjectionGuard
            analysis: Output from TicketAnalyzer
            customer_context: Dict with name, tier, order_id, etc.
            n_shots: Number of few-shot examples to include (0=zero-shot)

        Returns:
            Parsed response dict with plain_text and structured fields
        """
        department = analysis.get("category", "general")
        priority = analysis.get("priority", "medium")
        shot_label = get_shot_count_label(department)

        system_prompt = build_response_system_prompt(
            department=department,
            customer_context=customer_context,
            n_shots=n_shots,
        )

        # Build the user-facing prompt with analysis context
        user_prompt = f"""Generate a response for the following customer ticket.

<ticket_analysis>
  <category>{department}</category>
  <priority>{priority}</priority>
  <sentiment>{analysis.get('sentiment', 'neutral')}</sentiment>
  <summary>{analysis.get('summary', '')}</summary>
  <suggested_actions>{''.join(f'<action>{a}</action>' for a in analysis.get('suggested_actions', []))}</suggested_actions>
  <repeat_contact>{str(analysis.get('repeat_contact', False)).lower()}</repeat_contact>
</ticket_analysis>

{sanitized_ticket}

Respond in the exact XML format specified. Use the analysis above to inform your response."""

        try:
            logger.info(
                f"[Responder] Generating {department} response "
                f"({shot_label}, priority={priority})"
            )

            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            raw = response.content[0].text
            result = parse_agent_response(raw)
            result["department"] = department
            result["shot_technique"] = shot_label
            result["persona"] = department
            result["model"] = self.MODEL
            result["input_tokens"] = response.usage.input_tokens
            result["output_tokens"] = response.usage.output_tokens

            # Log for optimization tracking
            self._response_log.append({
                "department": department,
                "priority": priority,
                "shot_technique": shot_label,
                "output_length": len(result.get("plain_text", "")),
                "has_all_fields": all([
                    result.get("greeting"),
                    result.get("acknowledgment"),
                    result.get("resolution_steps"),
                    result.get("timeline"),
                ])
            })

            return result

        except Exception as e:
            logger.error(f"[Responder] Response generation failed: {e}")
            return {
                "plain_text": (
                    "We've received your message and a support agent will follow up shortly. "
                    "We apologize for any inconvenience."
                ),
                "department": department,
                "error": str(e),
                "shot_technique": shot_label,
            }

    def get_response_stats(self) -> dict:
        """Returns response quality statistics across all generated responses."""
        if not self._response_log:
            return {}

        complete = sum(1 for r in self._response_log if r.get("has_all_fields"))
        by_dept = {}
        for r in self._response_log:
            dept = r["department"]
            by_dept[dept] = by_dept.get(dept, 0) + 1

        return {
            "total_responses": len(self._response_log),
            "complete_structure_rate": f"{(complete / len(self._response_log)) * 100:.1f}%",
            "by_department": by_dept,
            "avg_length": sum(r["output_length"] for r in self._response_log) // len(self._response_log),
        }
