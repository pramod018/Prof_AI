"""
Query logging for the BEMS Troubleshooting Assistant.

Tracks user queries with timestamps for usage analytics.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

_QUERY_LOG_FILE = os.path.join("sample_data", "query_log.json")


def _load_query_log() -> list[dict]:
    if os.path.exists(_QUERY_LOG_FILE):
        with open(_QUERY_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_query_log_entry(query: str, num_results: int) -> None:
    """Log a user query for analytics tracking."""
    log = _load_query_log()
    log.append({
        "timestamp": datetime.now().isoformat(),
        "query": query[:200],
        "num_results": num_results,
    })
    os.makedirs(os.path.dirname(_QUERY_LOG_FILE), exist_ok=True)
    with open(_QUERY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
