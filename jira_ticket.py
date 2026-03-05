"""
Jira Ticket Generator for the BEMS Troubleshooting Assistant.

Uses LLM-based sentiment analysis of the issue description to
auto-classify severity, then generates a structured Jira ticket
ready for submission.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from openai import APIConnectionError, APITimeoutError, AuthenticationError

from config import settings
from db import get_embedding_model, get_collection
from rag_engine import get_openai_client

logger = logging.getLogger(__name__)


SEVERITY_PROMPT = """\
You are a BEMS (Building Energy Management System) issue severity classifier.

Analyse the issue description below and determine the Jira ticket severity.
Also produce a structured Jira ticket.

SEVERITY CRITERIA:
- **1 - Critical**: Complete system outage, safety hazard, building uninhabitable, \
data loss, all occupants affected. Requires immediate 24/7 response.
- **2 - High**: Major component failure, significant comfort impact across multiple \
zones/floors, partial system outage, security risk. Response within 4 hours.
- **3 - Medium**: Single component degradation, one zone affected, intermittent \
faults, performance below spec but operational. Response within 1 business day.
- **4 - Low**: Minor cosmetic issue, documentation update, enhancement request, \
scheduled maintenance item, no occupant impact. Response within 1 week.

Respond ONLY with valid JSON (no markdown fences) in this exact structure:
{
  "severity": <1|2|3|4>,
  "severity_label": "<Critical|High|Medium|Low>",
  "confidence": "<High|Medium|Low>",
  "reasoning": "<1-2 sentence justification for the severity choice>",
  "title": "<concise Jira ticket title, max 120 chars>",
  "description": "<detailed Jira description in plain text with sections: \
Problem Statement, Impact, Affected Systems, Steps to Reproduce (if applicable)>",
  "component": "<BEMS component affected>",
  "labels": ["<label1>", "<label2>"],
  "acceptance_criteria": "<what 'done' looks like for this ticket>"
}
"""


def _classify_and_generate(issue_text: str, rca_context: str | None) -> dict:
    """Use the LLM to classify severity and generate Jira ticket fields."""
    if not settings.cxai_access_token:
        return _fallback_ticket(issue_text, "No API token configured")

    user_message = f"## Issue Description\n{issue_text}"
    if rca_context:
        user_message += f"\n\n## Root Cause Analysis Context\n{rca_context}"

    try:
        response = get_openai_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SEVERITY_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1500,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(content)
    except (APIConnectionError, APITimeoutError, AuthenticationError) as e:
        logger.warning("LLM unavailable for Jira classification: %s", type(e).__name__)
        return _fallback_ticket(issue_text, f"LLM unavailable: {type(e).__name__}")
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse LLM severity response: %s", e)
        return _fallback_ticket(issue_text, "LLM returned invalid format")
    except Exception as e:
        logger.exception("Unexpected error during Jira ticket generation")
        return _fallback_ticket(issue_text, str(e))


def _fallback_ticket(issue_text: str, reason: str) -> dict:
    """Generate a basic ticket when the LLM is unavailable."""
    return {
        "severity": 3,
        "severity_label": "Medium",
        "confidence": "Low",
        "reasoning": f"Auto-assigned Medium severity (LLM classification unavailable: {reason}). Please review and adjust.",
        "title": issue_text[:120],
        "description": issue_text,
        "component": "BEMS - General",
        "labels": ["auto-generated", "needs-review"],
        "acceptance_criteria": "Issue resolved and verified in production.",
    }


def _get_similar_context(issue_text: str) -> tuple[list[dict], str | None]:
    """Retrieve similar tickets to enrich the Jira ticket context."""
    try:
        query_embedding = get_embedding_model().encode([issue_text]).tolist()
        results = get_collection().query(
            query_embeddings=query_embedding,
            n_results=3,
            include=["metadatas", "distances"],
        )

        related: list[dict] = []
        if results and results["metadatas"]:
            for i, meta in enumerate(results["metadatas"][0]):
                distance = results["distances"][0][i] if results["distances"] else None
                similarity = round(1 - distance, 4) if distance is not None else None
                related.append({
                    "ticket_id": meta.get("ticket_id", ""),
                    "title": meta.get("title", ""),
                    "severity": meta.get("severity", ""),
                    "component": meta.get("component", ""),
                    "similarity": similarity,
                })

        context_lines = []
        for r in related:
            context_lines.append(
                f"- {r['ticket_id']}: {r['title']} "
                f"(Severity: {r['severity']}, Component: {r['component']}, "
                f"Similarity: {r['similarity']})"
            )
        context_str = "\n".join(context_lines) if context_lines else None
        return related, context_str
    except Exception:
        logger.debug("Could not retrieve similar tickets for Jira context")
        return [], None


def generate_jira_ticket(
    issue_description: str,
    rca_report: str | None = None,
    override_severity: int | None = None,
) -> dict:
    """Generate a complete Jira ticket with LLM-based severity classification.

    Args:
        issue_description: The problem description
        rca_report: Optional RCA report text to provide extra context
        override_severity: Optional manual severity override (1-4)
    """
    related_tickets, similar_context = _get_similar_context(issue_description)

    rca_context = rca_report
    if similar_context and not rca_context:
        rca_context = f"Similar historical tickets:\n{similar_context}"
    elif similar_context and rca_context:
        rca_context += f"\n\nSimilar historical tickets:\n{similar_context}"

    ticket = _classify_and_generate(issue_description, rca_context)

    if override_severity and 1 <= override_severity <= 4:
        severity_labels = {1: "Critical", 2: "High", 3: "Medium", 4: "Low"}
        ticket["severity"] = override_severity
        ticket["severity_label"] = severity_labels[override_severity]
        ticket["reasoning"] = f"Manually set to Severity {override_severity}. " + ticket.get("reasoning", "")

    ticket["generated_at"] = datetime.now().isoformat()
    ticket["related_tickets"] = related_tickets

    ticket["jira_text"] = _format_jira_text(ticket)

    return ticket


def _format_jira_text(ticket: dict) -> str:
    """Format the ticket as copy-paste-ready Jira text."""
    sev = ticket.get("severity", 3)
    sev_label = ticket.get("severity_label", "Medium")
    priority_map = {1: "Blocker", 2: "Critical", 3: "Major", 4: "Minor"}
    priority = priority_map.get(sev, "Major")

    lines = [
        "Project: BEMS",
        "Issue Type: Bug",
        f"Priority: {priority} (Severity {sev} - {sev_label})",
        f"Summary: {ticket.get('title', '')}",
        f"Component: {ticket.get('component', 'BEMS - General')}",
        f"Labels: {', '.join(ticket.get('labels', []))}",
        "",
        "=" * 50,
        "DESCRIPTION",
        "=" * 50,
        ticket.get("description", ""),
        "",
        "=" * 50,
        "SEVERITY JUSTIFICATION",
        "=" * 50,
        f"AI Confidence: {ticket.get('confidence', 'N/A')}",
        ticket.get("reasoning", ""),
        "",
        "=" * 50,
        "ACCEPTANCE CRITERIA",
        "=" * 50,
        ticket.get("acceptance_criteria", ""),
    ]

    related = ticket.get("related_tickets", [])
    if related:
        lines.extend([
            "",
            "=" * 50,
            "RELATED TICKETS",
            "=" * 50,
        ])
        for r in related:
            lines.append(f"- {r.get('ticket_id', '')}: {r.get('title', '')} ({r.get('severity', '')})")

    lines.extend([
        "",
        f"Generated by Prof-AI for BEMS — {ticket.get('generated_at', '')}",
    ])

    return "\n".join(lines)
