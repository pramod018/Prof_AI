"""
Root Cause Analyser for the BEMS Troubleshooting Assistant.

Performs deep root-cause analysis by retrieving similar past tickets
and using the LLM to identify the most probable root causes,
contributing factors, and recommended corrective actions.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from openai import APIConnectionError, APITimeoutError, AuthenticationError

from config import settings
from db import get_embedding_model, get_collection
from rag_engine import get_openai_client
from ticket_utils import format_ticket_result, parse_playbook_fields

logger = logging.getLogger(__name__)


RCA_SYSTEM_PROMPT = (
    "You are an expert Root Cause Analyst for Building Energy Management Systems (BEMS). "
    "Your role is to perform structured root-cause analysis on reported BEMS issues.\n\n"
    "You will receive:\n"
    "1. A symptom/problem description from the engineer.\n"
    "2. Similar historical tickets with their resolutions and playbook data.\n\n"
    "Produce a structured Root Cause Analysis report with these sections:\n\n"
    "## Root Cause Determination\n"
    "Identify the most probable root cause(s), ranked by likelihood. For each:\n"
    "- State the root cause clearly\n"
    "- Assign a confidence level (High / Medium / Low)\n"
    "- Cite supporting evidence from the historical tickets\n\n"
    "## Contributing Factors\n"
    "List environmental, operational, or systemic factors that contributed.\n\n"
    "## Impact Assessment\n"
    "Describe the downstream effects — what systems, zones, or operations are affected.\n\n"
    "## Corrective Actions\n"
    "Provide concrete, prioritised fix steps:\n"
    "- **Immediate**: Steps to restore service now\n"
    "- **Short-term**: Fixes to prevent recurrence within days\n"
    "- **Long-term**: Systemic improvements or upgrades\n\n"
    "## Pattern Analysis\n"
    "Note recurring failure patterns, common components, or seasonal trends "
    "visible in the historical data.\n\n"
    "Be technically precise. Reference specific ticket IDs, component names, "
    "and data points. Use bullet points and clear headers."
)


def _build_rca_context(tickets: list[dict]) -> str:
    """Format retrieved tickets with full playbook data for RCA analysis."""
    if not tickets:
        return "No related tickets found in the knowledge base."

    parts: list[str] = []
    for i, ticket in enumerate(tickets, 1):
        meta = ticket.get("metadata", {})
        score = ticket.get("similarity_score", "N/A")
        playbook = parse_playbook_fields(meta)

        section = (
            f"--- Historical Ticket {i} (Similarity: {score}) ---\n"
            f"Ticket ID: {meta.get('ticket_id', 'N/A')}\n"
            f"Source: {meta.get('source', 'N/A')}\n"
            f"Severity: {meta.get('severity', 'N/A')}\n"
            f"Component: {meta.get('component', 'N/A')}\n"
            f"Date: {meta.get('date', 'N/A')}\n"
            f"Engineer: {meta.get('engineer', 'N/A')}\n"
            f"\nFull Record:\n{ticket.get('document', '')}\n"
        )

        steps = playbook.get("resolution_steps", [])
        if steps:
            section += "\nResolution Steps:\n" + "\n".join(f"  {j}. {s}" for j, s in enumerate(steps, 1))

        docs = playbook.get("documents_used", [])
        if docs:
            section += "\nDocuments Used:\n" + "\n".join(f"  - {d}" for d in docs)

        cmds = playbook.get("commands_used", [])
        if cmds:
            section += "\nCommands Used:\n" + "\n".join(f"  $ {c}" for c in cmds)

        parts.append(section)

    return "\n\n".join(parts)


def _compute_pattern_stats(tickets: list[dict]) -> dict:
    """Extract statistical patterns from retrieved tickets."""
    components: Counter[str] = Counter()
    severities: Counter[str] = Counter()
    sources: Counter[str] = Counter()

    for t in tickets:
        meta = t.get("metadata", {})
        comp = meta.get("component", "")
        if comp:
            components[comp] += 1
            family = comp.split(" - ")[0].strip()
            if family != comp:
                components[family] += 1
        sev = meta.get("severity", "")
        if sev:
            severities[sev] += 1
        src = meta.get("source", "")
        if src:
            sources[src] += 1

    return {
        "top_components": dict(components.most_common(5)),
        "severity_distribution": dict(severities),
        "source_distribution": dict(sources),
        "total_similar_tickets": len(tickets),
    }


def _run_rca_llm(symptom: str, tickets: list[dict]) -> str:
    """Call the LLM to produce a root-cause analysis report."""
    if not settings.cxai_access_token:
        return (
            "**Root Cause Analysis unavailable** — no API token configured.\n\n"
            "Set `CXAI_PLAYGROUND_ACCESS_TOKEN` in your `.env` file. "
            "The retrieved tickets and pattern statistics below are still available."
        )

    user_message = (
        f"## Reported Symptom / Problem\n{symptom}\n\n"
        f"## Historical Ticket Data\n{_build_rca_context(tickets)}"
    )

    try:
        response = get_openai_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": RCA_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=3000,
        )
        return response.choices[0].message.content
    except APIConnectionError:
        logger.warning("Cannot reach LLM API at %s", settings.openai_base_url)
        return (
            "**RCA unavailable** — cannot connect to "
            f"`{settings.openai_base_url}`.\n\n"
            "Ensure you are connected to the **Cisco VPN** or corporate network.\n\n"
            "Pattern statistics and retrieved tickets are still available below."
        )
    except APITimeoutError:
        logger.warning("LLM API request timed out during RCA")
        return (
            "**RCA timed out** — the API did not respond in time.\n\n"
            "Please try again. Pattern statistics and tickets are available below."
        )
    except AuthenticationError:
        logger.warning("LLM API authentication failed during RCA")
        return (
            "**RCA failed** — authentication error.\n\n"
            "Your `CXAI_PLAYGROUND_ACCESS_TOKEN` may be expired. "
            "Update it in your `.env` file."
        )
    except Exception as e:
        logger.exception("Unexpected error during RCA")
        return f"**RCA failed** — {type(e).__name__}: {e}"


def analyse_root_cause(
    symptom: str,
    top_k: int = 10,
) -> dict:
    """Run the full root-cause analysis pipeline.

    1. Retrieve more tickets (default 10) for broader pattern detection
    2. Compute pattern statistics
    3. Call LLM with full context for structured RCA report
    """
    query_embedding = get_embedding_model().encode([symptom]).tolist()
    results = get_collection().query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    tickets: list[dict] = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else None
            similarity = round(1 - distance, 4) if distance is not None else None
            tickets.append({
                "document": doc,
                "metadata": meta,
                "similarity_score": similarity,
            })

    pattern_stats = _compute_pattern_stats(tickets)
    rca_report = _run_rca_llm(symptom, tickets)
    email_template = _build_email_template(symptom, rca_report, pattern_stats, tickets)

    return {
        "symptom": symptom,
        "rca_report": rca_report,
        "pattern_stats": pattern_stats,
        "evidence_tickets": [format_ticket_result(t) for t in tickets],
        "email_template": email_template,
    }


def _build_email_template(
    symptom: str,
    rca_report: str,
    stats: dict,
    tickets: list[dict],
) -> str:
    """Build a professional email template from the RCA results."""
    ticket_ids = []
    for t in tickets[:5]:
        tid = t.get("metadata", {}).get("ticket_id", "")
        if tid:
            ticket_ids.append(tid)

    top_comp = ""
    top_components = stats.get("top_components", {})
    if top_components:
        top_comp = next(iter(top_components))

    subject = f"RCA Report: {top_comp + ' — ' if top_comp else ''}{symptom[:80]}"

    body_lines = [
        f"Subject: {subject}",
        "",
        "Hi Team,",
        "",
        "Please find below the Root Cause Analysis for the reported BEMS issue.",
        "",
        "=" * 60,
        "REPORTED SYMPTOM",
        "=" * 60,
        symptom,
        "",
        "=" * 60,
        "ROOT CAUSE ANALYSIS",
        "=" * 60,
        _strip_markdown(rca_report),
        "",
        "=" * 60,
        "EVIDENCE SUMMARY",
        "=" * 60,
        f"Similar historical tickets analysed: {stats.get('total_similar_tickets', 0)}",
    ]

    if top_comp:
        body_lines.append(f"Primary component affected: {top_comp}")

    sev_dist = stats.get("severity_distribution", {})
    if sev_dist:
        sev_str = ", ".join(f"{k}: {v}" for k, v in sorted(sev_dist.items()))
        body_lines.append(f"Severity distribution: {sev_str}")

    if ticket_ids:
        body_lines.append(f"Related ticket IDs: {', '.join(ticket_ids)}")

    body_lines.extend([
        "",
        "=" * 60,
        "",
        "This analysis was generated by Prof-AI for BEMS — Troubleshooting Assistant.",
        "Please review and validate before taking action.",
        "",
        "Best regards,",
        "BEMS Support Team",
    ])

    return "\n".join(body_lines)


def _strip_markdown(text: str) -> str:
    """Remove common markdown formatting for plain-text email."""
    text = re.sub(r"^#{1,4}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text
