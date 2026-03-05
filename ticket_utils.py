"""
Shared ticket utilities for the BEMS Troubleshooting Assistant.

Centralizes ticket document building, metadata construction, and
playbook field parsing to avoid duplication across modules.
"""

from __future__ import annotations

import json

_PLAYBOOK_FIELDS = ("resolution_steps", "documents_used", "commands_used")


def build_document_text(ticket: dict) -> str:
    """Combine ticket fields into a single searchable document for embedding."""
    parts = [
        f"Ticket ID: {ticket.get('ticket_id', 'N/A')}",
        f"Source: {ticket.get('source', 'N/A')}",
        f"Title: {ticket.get('title', '')}",
        f"Severity: {ticket.get('severity', 'N/A')}",
        f"Component: {ticket.get('component', 'N/A')}",
        f"Description: {ticket.get('description', '')}",
        f"Resolution: {ticket.get('resolution', '')}",
    ]
    for field, label in (
        ("resolution_steps", "Resolution Steps"),
        ("documents_used", "Documents Used"),
        ("commands_used", "Commands Used"),
    ):
        values = ticket.get(field)
        if values:
            parts.append(f"{label}: " + " | ".join(values))
    return "\n".join(parts)


def build_metadata(ticket: dict) -> dict:
    """Build a ChromaDB-compatible metadata dict from a ticket.

    Playbook list fields are JSON-serialized since ChromaDB metadata
    only supports scalar values.
    """
    return {
        "ticket_id": ticket.get("ticket_id", ""),
        "source": ticket.get("source", ""),
        "title": ticket.get("title", ""),
        "severity": ticket.get("severity", ""),
        "component": ticket.get("component", ""),
        "date": ticket.get("date", ""),
        "engineer": ticket.get("engineer", ""),
        "resolution_steps": json.dumps(ticket.get("resolution_steps", [])),
        "documents_used": json.dumps(ticket.get("documents_used", [])),
        "commands_used": json.dumps(ticket.get("commands_used", [])),
    }


def parse_playbook_fields(meta: dict) -> dict:
    """Parse JSON-encoded playbook fields from ChromaDB metadata back into lists."""
    parsed: dict = {}
    for field in _PLAYBOOK_FIELDS:
        raw = meta.get(field, "[]")
        try:
            parsed[field] = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            parsed[field] = []
    return parsed


def format_ticket_result(ticket_raw: dict) -> dict:
    """Convert a raw ChromaDB retrieval result into a clean API response entry."""
    meta = ticket_raw.get("metadata", {})
    entry = {
        "ticket_id": meta.get("ticket_id", "N/A"),
        "title": meta.get("title", "N/A"),
        "source": meta.get("source", "N/A"),
        "severity": meta.get("severity", "N/A"),
        "component": meta.get("component", "N/A"),
        "date": meta.get("date", "N/A"),
        "similarity_score": ticket_raw.get("similarity_score"),
    }
    entry.update(parse_playbook_fields(meta))
    return entry
