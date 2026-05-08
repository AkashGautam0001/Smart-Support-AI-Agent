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
    customer_tier: str = "standard"
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