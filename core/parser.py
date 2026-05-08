"""
core/parser.py
━━━━━━━━━━━━━
Robust XML parser for structured LLM output.
Handles partial XML, malformed tags, and missing fields gracefully.

PROMPT ENGINEERING: XML Tags for Output Structure
"""

import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def extract_xml_tag(text: str, tag: str, default: str = "") -> str:
    """
    Extract content from an XML tag. Handles nested content and whitespace.
    Returns default if tag not found.
    """
    # Try direct match first
    pattern = rf"<{tag}[^>]*>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try self-closing tag fallback
    sc_pattern = rf"<{tag}[^/]*/>"
    if re.search(sc_pattern, text, re.IGNORECASE):
        return default

    return default


def extract_all_xml_tags(text: str, tag: str) -> list[str]:
    """Extract all occurrences of a tag (for repeated tags like <action>, <step>)."""
    pattern = rf"<{tag}[^>]*>(.*?)</{tag}>"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    return [m.strip() for m in matches]


def parse_analysis(raw: str) -> dict:
    """
    Parse the ticket analyzer's XML output into a Python dict.
    Tolerant of minor formatting issues.
    """
    analysis_block = extract_xml_tag(raw, "analysis", raw)

    result = {
        "thinking": extract_xml_tag(analysis_block, "thinking"),
        "category": extract_xml_tag(analysis_block, "category", "general").lower(),
        "sentiment": extract_xml_tag(analysis_block, "sentiment", "neutral").lower(),
        "priority": extract_xml_tag(analysis_block, "priority", "medium").lower(),
        "priority_reason": extract_xml_tag(analysis_block, "priority_reason"),
        "summary": extract_xml_tag(analysis_block, "summary"),
        "repeat_contact": extract_xml_tag(analysis_block, "repeat_contact", "false").lower() == "true",
        "estimated_resolution_time": extract_xml_tag(analysis_block, "estimated_resolution_time", "unknown"),
        "suggested_actions": extract_all_xml_tags(analysis_block, "action"),
    }

    # Validate category
    valid_categories = {"billing", "technical", "returns", "general", "escalation"}
    if result["category"] not in valid_categories:
        logger.warning(f"Unknown category '{result['category']}' — defaulting to general")
        result["category"] = "general"

    # Validate priority
    valid_priorities = {"low", "medium", "high", "critical"}
    if result["priority"] not in valid_priorities:
        result["priority"] = "medium"

    return result


def parse_agent_response(raw: str) -> dict:
    """
    Parse the response agent's XML output.
    Also extracts the plain-text version for sending to customer.
    """
    response_block = extract_xml_tag(raw, "response", raw)

    steps = extract_all_xml_tags(response_block, "step")

    result = {
        "greeting": extract_xml_tag(response_block, "greeting"),
        "acknowledgment": extract_xml_tag(response_block, "acknowledgment"),
        "resolution_steps": steps,
        "timeline": extract_xml_tag(response_block, "timeline"),
        "next_action": extract_xml_tag(response_block, "next_action"),
        "closing": extract_xml_tag(response_block, "closing"),
        "raw_xml": raw,
    }

    # Build plain-text version for display/sending
    parts = []
    if result["greeting"]:
        parts.append(result["greeting"])
    if result["acknowledgment"]:
        parts.append(result["acknowledgment"])
    if steps:
        parts.append("\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)))
    if result["timeline"]:
        parts.append(result["timeline"])
    if result["next_action"]:
        parts.append(f"Next step: {result['next_action']}")
    if result["closing"]:
        parts.append(result["closing"])

    result["plain_text"] = "\n\n".join(p for p in parts if p)
    return result


def parse_quality_review(raw: str) -> dict:
    """Parse quality checker output."""
    review_block = extract_xml_tag(raw, "quality_review", raw)

    score_str = extract_xml_tag(review_block, "score", "0")
    try:
        score = int(score_str)
    except ValueError:
        score = 0

    return {
        "score": score,
        "passed": extract_xml_tag(review_block, "passed", "false").lower() == "true",
        "issues": extract_all_xml_tags(review_block, "issue"),
        "improvements": extract_all_xml_tags(review_block, "improvement"),
        "approved_response": extract_xml_tag(review_block, "approved_response"),
    }


def parse_optimization_result(raw: str) -> dict:
    """Parse prompt optimizer output."""
    return {
        "winning_variant": extract_xml_tag(raw, "winning_variant"),
        "win_reason": extract_xml_tag(raw, "win_reason"),
        "refined_prompt": extract_xml_tag(raw, "refined_prompt"),
        "expected_improvement": extract_xml_tag(raw, "expected_improvement"),
    }
