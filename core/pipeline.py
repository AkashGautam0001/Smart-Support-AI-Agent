"""
core/pipeline.py
━━━━━━━━━━━━━━━
Main orchestration pipeline. Connects all agents and components
in the correct order: Guard → Analyze → Respond → QA → Optimize.

This is the single entry point for processing any support ticket.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
import anthropic

from security.injection_guard import InjectionGuard
from agents.analyzer import TicketAnalyzer
from agents.responder import ResponseGenerator
from agents.quality_checker import QualityChecker
from core.prompt_optimizer import PromptOptimizer

logger = logging.getLogger(__name__)


@dataclass
class TicketRequest:
    message: str
    customer_name: str = "Customer"
    customer_tier: str = "standard"          # standard | premium | enterprise
    order_id: Optional[str] = None
    prior_contacts: int = 0
    account_age_months: int = 0
    ticket_id: str = field(default_factory=lambda: f"TKT-{uuid.uuid4().hex[:6].upper()}")


@dataclass
class TicketResponse:
    ticket_id: str
    final_response: str
    department: str
    priority: str
    sentiment: str
    quality_score: int
    quality_passed: bool
    shot_technique: str
    processing_time_ms: float
    injection_blocked: bool = False
    analysis: dict = field(default_factory=dict)
    quality_issues: list = field(default_factory=list)
    tokens_used: dict = field(default_factory=dict)


class SupportPipeline:
    """
    End-to-end customer support ticket processing pipeline.

    Flow:
    1. InjectionGuard   — sanitize & block malicious input
    2. TicketAnalyzer   — CoT classification + priority + sentiment
    3. ResponseGenerator — persona + few-shot + XML structured response
    4. QualityChecker   — validate + auto-correct if below threshold
    5. PromptOptimizer  — log performance for A/B tracking + refinement
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

        self.guard = InjectionGuard(self.client, enable_semantic_check=True)
        self.analyzer = TicketAnalyzer(self.client)
        self.responder = ResponseGenerator(self.client)
        self.qa = QualityChecker(self.client, threshold=72)
        self.optimizer = PromptOptimizer(self.client)

        self._processed: list[TicketResponse] = []
        logger.info("[Pipeline] SmartSupport pipeline initialized ✓")

    def process(self, request: TicketRequest) -> TicketResponse:
        """
        Process a single support ticket through the full pipeline.
        Returns a TicketResponse with the final customer-ready message.
        """
        start_time = time.time()
        ticket_id = request.ticket_id
        logger.info(f"\n{'='*60}")
        logger.info(f"[Pipeline] Processing {ticket_id} from {request.customer_name}")

        # ── Step 1: Injection Guard ──────────────────────────────────────────
        logger.info(f"[Pipeline] Step 1: Injection Guard")
        guard_result = self.guard.inspect(request.message, context=ticket_id)

        if not guard_result.is_safe:
            logger.warning(f"[Pipeline] {ticket_id} BLOCKED by injection guard")
            elapsed = (time.time() - start_time) * 1000
            return TicketResponse(
                ticket_id=ticket_id,
                final_response=(
                    "Your message could not be processed as it contains content that "
                    "violates our security policy. If this is an error, please contact "
                    "support via phone at 1800-XXX-XXXX."
                ),
                department="security",
                priority="high",
                sentiment="unknown",
                quality_score=0,
                quality_passed=False,
                shot_technique="blocked",
                processing_time_ms=round(elapsed, 1),
                injection_blocked=True,
            )

        sanitized = guard_result.sanitized_input

        # ── Step 2: Ticket Analysis (CoT) ─────────────────────────────────────
        logger.info(f"[Pipeline] Step 2: CoT Analysis")
        analysis = self.analyzer.analyze(sanitized, ticket_id=ticket_id)

        # Escalate if repeat contact + high priority
        if request.prior_contacts >= 2 and analysis["priority"] in ("high", "critical"):
            logger.info(f"[Pipeline] Auto-escalating {ticket_id} (repeat={request.prior_contacts} contacts)")
            analysis["category"] = "escalation"
            analysis["priority"] = "critical"

        # ── Step 3: Response Generation ───────────────────────────────────────
        logger.info(f"[Pipeline] Step 3: Generating {analysis['category']} response")

        customer_context = {
            "name": request.customer_name,
            "tier": request.customer_tier,
            "order_id": request.order_id,
            "prior_contacts": request.prior_contacts,
            "account_age_months": request.account_age_months,
        }

        # Premium customers get fewer shots (faster) since they get priority routing
        n_shots = 1 if request.customer_tier == "enterprise" else 2
        response_data = self.responder.generate(
            sanitized_ticket=sanitized,
            analysis=analysis,
            customer_context=customer_context,
            n_shots=n_shots,
        )

        draft_response = response_data.get("plain_text", "")
        shot_technique = response_data.get("shot_technique", "unknown")

        # ── Step 4: Quality Check ─────────────────────────────────────────────
        logger.info(f"[Pipeline] Step 4: Quality Check")
        qa_result = self.qa.check(
            response_text=draft_response,
            ticket_summary=analysis.get("summary", ""),
            department=analysis["category"],
        )

        final_response = qa_result.get("approved_response") or draft_response
        quality_score = qa_result.get("score", 70)
        quality_passed = qa_result.get("passed", True)
        quality_issues = qa_result.get("issues", [])

        # ── Step 5: Log for Optimization ─────────────────────────────────────
        self.optimizer.log_performance(
            prompt_id=f"{analysis['category']}_default",
            department=analysis["category"],
            quality_score=quality_score,
            issues=quality_issues,
            shot_technique=shot_technique,
            ticket_summary=analysis.get("summary", ""),
        )

        # ── Build final result ────────────────────────────────────────────────
        elapsed = (time.time() - start_time) * 1000

        result = TicketResponse(
            ticket_id=ticket_id,
            final_response=final_response,
            department=analysis["category"],
            priority=analysis["priority"],
            sentiment=analysis["sentiment"],
            quality_score=quality_score,
            quality_passed=quality_passed,
            shot_technique=shot_technique,
            processing_time_ms=round(elapsed, 1),
            injection_blocked=False,
            analysis=analysis,
            quality_issues=quality_issues,
            tokens_used={
                "analysis": {
                    "input": analysis.get("input_tokens", 0),
                    "output": analysis.get("output_tokens", 0),
                },
                "response": {
                    "input": response_data.get("input_tokens", 0),
                    "output": response_data.get("output_tokens", 0),
                },
            },
        )

        self._processed.append(result)
        logger.info(
            f"[Pipeline] {ticket_id} done in {elapsed:.0f}ms | "
            f"dept={result.department} priority={result.priority} "
            f"QA={quality_score}/100 ({'✓' if quality_passed else '⚠'})"
        )
        return result

    def batch_process(self, requests: list[TicketRequest]) -> list[TicketResponse]:
        """Process multiple tickets sequentially."""
        return [self.process(req) for req in requests]

    def full_report(self) -> dict:
        """Aggregate stats across all processed tickets."""
        if not self._processed:
            return {"message": "No tickets processed yet."}

        depts = {}
        priorities = {}
        for r in self._processed:
            depts[r.department] = depts.get(r.department, 0) + 1
            priorities[r.priority] = priorities.get(r.priority, 0) + 1

        scores = [r.quality_score for r in self._processed]
        times = [r.processing_time_ms for r in self._processed]
        blocked = sum(1 for r in self._processed if r.injection_blocked)

        return {
            "tickets_processed": len(self._processed),
            "injection_blocked": blocked,
            "avg_quality_score": round(sum(scores) / len(scores), 1),
            "avg_processing_ms": round(sum(times) / len(times), 1),
            "by_department": depts,
            "by_priority": priorities,
            "qa_stats": self.qa.qa_summary(),
            "analyzer_stats": self.analyzer.stats,
            "responder_stats": self.responder.get_response_stats(),
            "optimizer_report": self.optimizer.full_report(),
            "threat_summary": self.guard.threat_summary(),
        }
