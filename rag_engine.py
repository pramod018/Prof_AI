"""
RAG engine for the BEMS Troubleshooting Assistant.

Performs semantic similarity search against ChromaDB and uses an LLM
to summarize retrieved tickets into actionable troubleshooting guidance.
"""

from __future__ import annotations

import logging

from openai import OpenAI, APIConnectionError, APITimeoutError, AuthenticationError

from config import settings
from db import get_embedding_model, get_collection
from ticket_utils import format_ticket_result

logger = logging.getLogger(__name__)

_openai_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    """Return the cached OpenAI client singleton.

    Shared across rag_engine, rca, and jira_ticket modules.
    """
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=settings.cxai_access_token,
            base_url=settings.openai_base_url,
            timeout=30.0,
        )
    return _openai_client


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """Perform semantic similarity search and return the top-k matching tickets."""
    if top_k is None:
        top_k = settings.top_k

    query_embedding = get_embedding_model().encode([query]).tolist()

    results = get_collection().query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    tickets = []
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
    return tickets


SYSTEM_PROMPT = (
    "You are the BEMS Troubleshooting Assistant — an expert AI support tool "
    "for Building Energy Management Systems. Your role is to help TAC and on-call engineers "
    "diagnose and resolve issues faster.\n\n"
    "You will be given:\n"
    "1. A problem description from the engineer.\n"
    "2. A set of related past tickets retrieved from the knowledge base.\n\n"
    "Your task:\n"
    "- Analyze the retrieved tickets for patterns, root causes, and proven resolutions.\n"
    "- Provide a clear, structured troubleshooting summary.\n"
    "- Highlight the most relevant past ticket(s) and explain why they are relevant.\n"
    "- Suggest concrete diagnostic steps and potential fixes based on historical data.\n"
    "- If multiple root causes are possible, rank them by likelihood.\n"
    "- Note any recurring patterns or systemic issues.\n\n"
    "Keep your response concise, actionable, and technically precise. "
    "Use bullet points and clear section headers."
)


def _build_context(tickets: list[dict]) -> str:
    """Format retrieved tickets into context for the LLM prompt."""
    if not tickets:
        return "No related tickets found in the knowledge base."

    parts = []
    for i, ticket in enumerate(tickets, 1):
        meta = ticket.get("metadata", {})
        score = ticket.get("similarity_score", "N/A")
        parts.append(
            f"--- Retrieved Ticket {i} (Similarity: {score}) ---\n"
            f"Ticket ID: {meta.get('ticket_id', 'N/A')}\n"
            f"Source: {meta.get('source', 'N/A')}\n"
            f"Severity: {meta.get('severity', 'N/A')}\n"
            f"Component: {meta.get('component', 'N/A')}\n"
            f"Date: {meta.get('date', 'N/A')}\n"
            f"\n{ticket.get('document', '')}\n"
        )
    return "\n".join(parts)


def _summarize(query: str, tickets: list[dict]) -> str:
    """Use the LLM to generate a troubleshooting summary.

    Returns a fallback message if the LLM is unreachable.
    """
    if not settings.cxai_access_token:
        return (
            "**LLM summarization unavailable** — no API token configured.\n\n"
            "Set `CXAI_PLAYGROUND_ACCESS_TOKEN` in your `.env` file. "
            "The retrieved tickets below are still available for manual review."
        )

    user_message = (
        f"## Engineer's Problem Description\n{query}\n\n"
        f"## Related Past Tickets from Knowledge Base\n{_build_context(tickets)}"
    )

    try:
        response = get_openai_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except APIConnectionError:
        logger.warning("Cannot reach LLM API at %s", settings.openai_base_url)
        return (
            "**LLM summarization unavailable** — cannot connect to "
            f"`{settings.openai_base_url}`.\n\n"
            "Make sure you are connected to the **Cisco VPN** or corporate network.\n\n"
            "The retrieved tickets below are still available for manual review."
        )
    except APITimeoutError:
        logger.warning("LLM API request timed out")
        return (
            "**LLM summarization timed out** — the API did not respond in time.\n\n"
            "Please try again. The retrieved tickets below are still available for manual review."
        )
    except AuthenticationError:
        logger.warning("LLM API authentication failed")
        return (
            "**LLM summarization failed** — authentication error.\n\n"
            "Your `CXAI_PLAYGROUND_ACCESS_TOKEN` may be expired or invalid. "
            "Please update it in your `.env` file.\n\n"
            "The retrieved tickets below are still available for manual review."
        )
    except Exception as e:
        logger.exception("Unexpected error during LLM summarization")
        return (
            f"**LLM summarization failed** — {type(e).__name__}: {e}\n\n"
            "The retrieved tickets below are still available for manual review."
        )


def query_assistant(problem_description: str, top_k: int | None = None) -> dict:
    """End-to-end RAG pipeline: retrieve relevant tickets and generate a summary."""
    tickets = retrieve(problem_description, top_k=top_k)
    summary = _summarize(problem_description, tickets)

    return {
        "query": problem_description,
        "retrieved_tickets": [format_ticket_result(t) for t in tickets],
        "summary": summary,
    }
