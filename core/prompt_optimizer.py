"""
core/prompt_optimizer.py
━━━━━━━━━━━━━━━━━━━━━━━
Iterative prompt refinement system with A/B testing support.
Records prompt performance, compares variants, and auto-suggests
improvements based on quality scores.

PROMPT ENGINEERING: Iterative Prompt Refinement
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Optional
import anthropic

logger = logging.getLogger(__name__)


@dataclass
class PromptVariant:
    variant_id: str
    prompt_text: str
    description: str
    scores: list[float] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @property
    def avg_score(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def sample_count(self) -> int:
        return len(self.scores)

    @property
    def is_statistically_significant(self) -> bool:
        """Require at least 5 samples before declaring a winner."""
        return self.sample_count >= 5

    def record_score(self, score: float):
        self.scores.append(score)

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "description": self.description,
            "avg_score": round(self.avg_score, 1),
            "sample_count": self.sample_count,
            "is_significant": self.is_statistically_significant,
        }


class PromptABTest:
    """Manages an A/B test between two prompt variants."""

    def __init__(self, name: str, variant_a: PromptVariant, variant_b: PromptVariant):
        self.name = name
        self.variant_a = variant_a
        self.variant_b = variant_b
        self._assignment_log: list[str] = []

    def assign(self) -> PromptVariant:
        """Randomly assign a variant (50/50 split)."""
        chosen = random.choice([self.variant_a, self.variant_b])
        self._assignment_log.append(chosen.variant_id)
        return chosen

    def record_result(self, variant_id: str, score: float):
        if variant_id == self.variant_a.variant_id:
            self.variant_a.record_score(score)
        elif variant_id == self.variant_b.variant_id:
            self.variant_b.record_score(score)

    @property
    def winner(self) -> Optional[PromptVariant]:
        """Returns winner only when both variants have enough samples."""
        if not (self.variant_a.is_statistically_significant and
                self.variant_b.is_statistically_significant):
            return None
        return (
            self.variant_a
            if self.variant_a.avg_score >= self.variant_b.avg_score
            else self.variant_b
        )

    def status(self) -> dict:
        return {
            "test_name": self.name,
            "variant_a": self.variant_a.to_dict(),
            "variant_b": self.variant_b.to_dict(),
            "winner": self.winner.variant_id if self.winner else "undecided (insufficient samples)",
            "total_assignments": len(self._assignment_log),
        }


class PromptOptimizer:
    """
    Tracks prompt performance and generates improvement suggestions
    using an LLM to analyze patterns in failures.

    Implements the iterative refinement cycle:
    Observe → Diagnose failure mode → Hypothesize fix → Test → Measure → Repeat
    """

    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self._performance_log: list[dict] = []
        self._active_tests: dict[str, PromptABTest] = {}
        self._refinement_history: list[dict] = []

    def log_performance(
        self,
        prompt_id: str,
        department: str,
        quality_score: float,
        issues: list[str],
        shot_technique: str,
        ticket_summary: str,
    ):
        """Record a response's performance for later analysis."""
        self._performance_log.append({
            "prompt_id": prompt_id,
            "department": department,
            "quality_score": quality_score,
            "issues": issues,
            "shot_technique": shot_technique,
            "ticket_summary": ticket_summary,
            "timestamp": time.time(),
        })

        # Also update any active A/B test for this department
        test_key = f"ab_{department}"
        if test_key in self._active_tests:
            self._active_tests[test_key].record_result(prompt_id, quality_score)

    def create_ab_test(
        self,
        department: str,
        variant_a_text: str,
        variant_a_desc: str,
        variant_b_text: str,
        variant_b_desc: str,
    ) -> PromptABTest:
        """Create a new A/B test for a department's prompt."""
        test = PromptABTest(
            name=f"{department}_prompt_test",
            variant_a=PromptVariant(f"{department}_A", variant_a_text, variant_a_desc),
            variant_b=PromptVariant(f"{department}_B", variant_b_text, variant_b_desc),
        )
        self._active_tests[f"ab_{department}"] = test
        logger.info(f"[Optimizer] A/B test created for {department}")
        return test

    def get_ab_status(self, department: str) -> Optional[dict]:
        """Get current A/B test status for a department."""
        test = self._active_tests.get(f"ab_{department}")
        return test.status() if test else None

    def analyze_failures_and_suggest_refinement(
        self,
        department: str,
        current_prompt_excerpt: str,
        n_samples: int = 10,
    ) -> dict:
        """
        Analyze recent failures for a department and suggest prompt refinements.
        This is the core of the iterative refinement loop.

        PROMPT ENGINEERING: Iterative Refinement via LLM-assisted diagnosis
        """
        # Get recent low-scoring responses for this department
        dept_logs = [
            l for l in self._performance_log
            if l["department"] == department and l["quality_score"] < 75
        ][-n_samples:]

        if not dept_logs:
            return {"message": f"No failures recorded for {department} yet."}

        # Aggregate failure patterns
        all_issues = []
        for log in dept_logs:
            all_issues.extend(log.get("issues", []))

        issue_text = "\n".join(f"- {issue}" for issue in all_issues) if all_issues else "No specific issues logged"
        avg_score = sum(l["quality_score"] for l in dept_logs) / len(dept_logs)

        refinement_prompt = f"""You are a prompt engineering expert. Analyze these customer support prompt failures
and suggest a targeted improvement.

<failure_analysis>
  <department>{department}</department>
  <sample_count>{len(dept_logs)}</sample_count>
  <average_score>{avg_score:.1f}/100</average_score>
  <recurring_issues>
{issue_text}
  </recurring_issues>
</failure_analysis>

<current_prompt_excerpt>
{current_prompt_excerpt}
</current_prompt_excerpt>

Diagnose the root cause of these failures and suggest ONE specific prompt change.
Think step by step: What failure mode is this? What in the prompt causes it?
What minimal change would fix it?

<output_format>
<refinement>
  <winning_variant>A or B (which current prompt is working better)</winning_variant>
  <win_reason>One sentence</win_reason>
  <root_cause>Specific diagnosis of why failures are occurring</root_cause>
  <refined_prompt>The specific addition or replacement to make in the prompt</refined_prompt>
  <expected_improvement>What metric should improve and by how much</expected_improvement>
</refinement>
</output_format>"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=800,
                messages=[{"role": "user", "content": refinement_prompt}]
            )

            raw = response.content[0].text

            # Parse the refinement suggestion
            import re
            def extract(tag: str) -> str:
                m = re.search(rf"<{tag}>(.*?)</{tag}>", raw, re.DOTALL)
                return m.group(1).strip() if m else ""

            result = {
                "department": department,
                "failures_analyzed": len(dept_logs),
                "avg_failure_score": round(avg_score, 1),
                "root_cause": extract("root_cause"),
                "refined_prompt": extract("refined_prompt"),
                "expected_improvement": extract("expected_improvement"),
                "raw_suggestion": raw,
            }

            self._refinement_history.append(result)
            logger.info(f"[Optimizer] Refinement suggestion generated for {department}")
            return result

        except Exception as e:
            logger.error(f"[Optimizer] Refinement analysis failed: {e}")
            return {"error": str(e)}

    def full_report(self) -> dict:
        """Comprehensive performance report across all departments."""
        if not self._performance_log:
            return {"message": "No performance data yet."}

        by_dept: dict[str, list[float]] = {}
        by_technique: dict[str, list[float]] = {}

        for log in self._performance_log:
            dept = log["department"]
            tech = log["shot_technique"]
            score = log["quality_score"]

            by_dept.setdefault(dept, []).append(score)
            by_technique.setdefault(tech, []).append(score)

        dept_summary = {
            dept: {
                "avg_score": round(sum(scores) / len(scores), 1),
                "count": len(scores),
                "min": min(scores),
                "max": max(scores),
            }
            for dept, scores in by_dept.items()
        }

        tech_summary = {
            tech: round(sum(scores) / len(scores), 1)
            for tech, scores in by_technique.items()
        }

        return {
            "total_responses_tracked": len(self._performance_log),
            "by_department": dept_summary,
            "by_shot_technique": tech_summary,
            "active_ab_tests": {
                k: v.status() for k, v in self._active_tests.items()
            },
            "refinements_suggested": len(self._refinement_history),
        }
