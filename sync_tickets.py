"""
Real-Time Ticket Sync module for the BEMS Troubleshooting Assistant.

Supports:
  - JSON array upload
  - CSV file upload
  - Single-ticket webhook

Synced tickets are deduplicated and immediately ingested into ChromaDB.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import datetime

from config import settings
from db import get_embedding_model, get_collection, get_or_create_collection
from ticket_utils import build_document_text, build_metadata

logger = logging.getLogger(__name__)

_SYNC_LOG_FILE = os.path.join("sample_data", "sync_log.json")


def _load_sync_log() -> list[dict]:
    if os.path.exists(_SYNC_LOG_FILE):
        with open(_SYNC_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_sync_log(log: list[dict]) -> None:
    os.makedirs(os.path.dirname(_SYNC_LOG_FILE), exist_ok=True)
    with open(_SYNC_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)


def _append_sync_entry(entry: dict) -> None:
    log = _load_sync_log()
    log.append({"timestamp": datetime.now().isoformat(), **entry})
    _save_sync_log(log)


def _get_existing_ids() -> set[str]:
    try:
        result = get_collection().get(include=[])
        return set(result["ids"]) if result["ids"] else set()
    except Exception:
        return set()


def _ingest_tickets(tickets: list[dict]) -> dict:
    """Embed and add new tickets into ChromaDB, skipping duplicates."""
    if not tickets:
        return {"added": 0, "skipped": 0}

    existing_ids = _get_existing_ids()
    new_tickets = [t for t in tickets if t.get("ticket_id") not in existing_ids]
    skipped = len(tickets) - len(new_tickets)

    if not new_tickets:
        return {"added": 0, "skipped": skipped}

    documents = [build_document_text(t) for t in new_tickets]
    metadatas = [build_metadata(t) for t in new_tickets]
    ids = [t.get("ticket_id", f"sync-{i}") for i, t in enumerate(new_tickets)]

    embeddings = get_embedding_model().encode(documents, show_progress_bar=False).tolist()

    get_or_create_collection().add(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )
    return {"added": len(new_tickets), "skipped": skipped}


def _current_total() -> int:
    try:
        return get_collection().count()
    except Exception:
        return 0


def sync_from_list(tickets: list[dict]) -> dict:
    """Sync tickets from a Python list (avoids JSON roundtrip)."""
    if not isinstance(tickets, list) or not tickets:
        return {"status": "error", "message": "Expected a non-empty array of ticket objects"}

    result = _ingest_tickets(tickets)

    _append_sync_entry({
        "source_type": "json_upload",
        "tickets_received": len(tickets),
        "tickets_added": result["added"],
        "tickets_skipped": result["skipped"],
    })

    return {
        "status": "success",
        "tickets_received": len(tickets),
        "tickets_added": result["added"],
        "tickets_skipped_duplicate": result["skipped"],
        "total_in_knowledge_base": _current_total(),
    }


def sync_from_json(json_content: str) -> dict:
    """Sync tickets from a JSON string."""
    try:
        tickets = json.loads(json_content)
        if not isinstance(tickets, list):
            return {"status": "error", "message": "JSON must be an array of ticket objects"}
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid JSON: {e}"}

    return sync_from_list(tickets)


def sync_from_csv(csv_content: str) -> dict:
    """Sync tickets from CSV content.

    Expected columns: ticket_id, source, title, description, resolution,
    severity, component, date, engineer
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        tickets = []
        for row in reader:
            ticket = {
                "ticket_id": row.get("ticket_id", "").strip(),
                "source": row.get("source", "BEMS Ticket").strip(),
                "title": row.get("title", "").strip(),
                "description": row.get("description", "").strip(),
                "resolution": row.get("resolution", "").strip(),
                "severity": row.get("severity", "P3").strip(),
                "component": row.get("component", "").strip(),
                "date": row.get("date", "").strip(),
                "engineer": row.get("engineer", "").strip(),
            }
            if ticket["ticket_id"] and ticket["description"]:
                tickets.append(ticket)
    except Exception as e:
        return {"status": "error", "message": f"CSV parsing error: {e}"}

    if not tickets:
        return {"status": "error", "message": "No valid tickets found in CSV"}

    result = _ingest_tickets(tickets)

    _append_sync_entry({
        "source_type": "csv_upload",
        "tickets_received": len(tickets),
        "tickets_added": result["added"],
        "tickets_skipped": result["skipped"],
    })

    return {
        "status": "success",
        "tickets_received": len(tickets),
        "tickets_added": result["added"],
        "tickets_skipped_duplicate": result["skipped"],
        "total_in_knowledge_base": _current_total(),
    }


def sync_single_ticket(ticket: dict) -> dict:
    """Sync a single ticket (webhook / real-time push)."""
    for field in ("ticket_id", "description"):
        if not ticket.get(field):
            return {"status": "error", "message": f"Missing required field: {field}"}

    ticket.setdefault("source", "BEMS Ticket")
    ticket.setdefault("severity", "P3")
    ticket.setdefault("date", datetime.now().strftime("%Y-%m-%d"))

    result = _ingest_tickets([ticket])

    _append_sync_entry({
        "source_type": "webhook",
        "ticket_id": ticket["ticket_id"],
        "tickets_added": result["added"],
        "tickets_skipped": result["skipped"],
    })

    if result["added"] > 0:
        return {"status": "success", "message": f"Ticket {ticket['ticket_id']} added to knowledge base"}
    return {"status": "skipped", "message": f"Ticket {ticket['ticket_id']} already exists"}


def get_sync_history() -> list[dict]:
    return _load_sync_log()
