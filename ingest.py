"""
Data ingestion module for the BEMS Troubleshooting Assistant.

Reads support data (BEMS tickets, Service Requests, Webex conversations),
generates embeddings using a local sentence-transformer model, and
stores them in a ChromaDB vector database for semantic retrieval.
"""

from __future__ import annotations

import json
import logging
import os
import sys

from config import settings
from db import get_embedding_model, get_chroma_client, reset_chroma_client
from ticket_utils import build_document_text, build_metadata

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


def _load_tickets(data_path: str) -> list[dict]:
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ingest(data_path: str | None = None) -> dict:
    """Ingest ticket data into ChromaDB. Returns a summary dict."""
    if data_path is None:
        data_path = os.path.join("sample_data", "bems_tickets.json")

    tickets = _load_tickets(data_path)
    if not tickets:
        return {"status": "error", "message": "No tickets found in data file"}

    logger.info("Loaded %d tickets from %s", len(tickets), data_path)

    documents = []
    metadatas = []
    ids = []

    for ticket in tickets:
        documents.append(build_document_text(ticket))
        metadatas.append(build_metadata(ticket))
        ids.append(ticket.get("ticket_id", f"doc-{len(ids)}"))

    logger.info("Generating embeddings with %s ...", settings.embedding_model)
    embeddings = get_embedding_model().encode(documents, show_progress_bar=True).tolist()

    logger.info("Storing in ChromaDB at %s ...", settings.chroma_persist_dir)
    client = get_chroma_client()

    existing_collections = [c.name for c in client.list_collections()]
    if settings.chroma_collection in existing_collections:
        client.delete_collection(settings.chroma_collection)
        logger.info("Cleared existing collection: %s", settings.chroma_collection)

    reset_chroma_client()
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )

    for i in range(0, len(documents), _BATCH_SIZE):
        end = min(i + _BATCH_SIZE, len(documents))
        collection.add(
            documents=documents[i:end],
            embeddings=embeddings[i:end],
            metadatas=metadatas[i:end],
            ids=ids[i:end],
        )

    count = collection.count()
    logger.info("Ingestion complete. %d documents stored.", count)

    return {
        "status": "success",
        "documents_ingested": count,
        "collection": settings.chroma_collection,
        "persist_dir": settings.chroma_persist_dir,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data_file = sys.argv[1] if len(sys.argv) > 1 else None
    result = ingest(data_file)
    print(json.dumps(result, indent=2))
