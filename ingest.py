"""
Data ingestion module for the BEMS Troubleshooting Assistant.

Reads support data (BEMS tickets, Service Requests, Webex conversations),
generates embeddings using a local sentence-transformer model, and
stores them in a ChromaDB vector database for semantic retrieval.
"""

import json
import os
import sys

import chromadb
from sentence_transformers import SentenceTransformer

from config import settings


def load_tickets(data_path: str) -> list[dict]:
    """Load ticket data from a JSON file."""
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_document_text(ticket: dict) -> str:
    """Combine ticket fields into a single searchable document."""
    parts = [
        f"Ticket ID: {ticket.get('ticket_id', 'N/A')}",
        f"Source: {ticket.get('source', 'N/A')}",
        f"Title: {ticket.get('title', '')}",
        f"Severity: {ticket.get('severity', 'N/A')}",
        f"Component: {ticket.get('component', 'N/A')}",
        f"Description: {ticket.get('description', '')}",
        f"Resolution: {ticket.get('resolution', '')}",
    ]
    return "\n".join(parts)


def ingest(data_path: str | None = None) -> dict:
    """
    Ingest ticket data into ChromaDB.

    Returns a summary dict with counts and status.
    """
    if data_path is None:
        data_path = os.path.join("sample_data", "bems_tickets.json")

    tickets = load_tickets(data_path)
    if not tickets:
        return {"status": "error", "message": "No tickets found in data file"}

    print(f"Loaded {len(tickets)} tickets from {data_path}")

    print(f"Loading embedding model: {settings.embedding_model} ...")
    model = SentenceTransformer(settings.embedding_model)

    documents = []
    metadatas = []
    ids = []

    for ticket in tickets:
        doc_text = build_document_text(ticket)
        documents.append(doc_text)
        metadatas.append({
            "ticket_id": ticket.get("ticket_id", ""),
            "source": ticket.get("source", ""),
            "title": ticket.get("title", ""),
            "severity": ticket.get("severity", ""),
            "component": ticket.get("component", ""),
            "date": ticket.get("date", ""),
            "engineer": ticket.get("engineer", ""),
        })
        ids.append(ticket.get("ticket_id", f"doc-{len(ids)}"))

    print("Generating embeddings ...")
    embeddings = model.encode(documents, show_progress_bar=True).tolist()

    print(f"Storing in ChromaDB at {settings.chroma_persist_dir} ...")
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    existing_collections = [c.name for c in client.list_collections()]
    if settings.chroma_collection in existing_collections:
        client.delete_collection(settings.chroma_collection)
        print(f"Cleared existing collection: {settings.chroma_collection}")

    collection = client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )

    batch_size = 100
    for i in range(0, len(documents), batch_size):
        end = min(i + batch_size, len(documents))
        collection.add(
            documents=documents[i:end],
            embeddings=embeddings[i:end],
            metadatas=metadatas[i:end],
            ids=ids[i:end],
        )

    count = collection.count()
    print(f"Ingestion complete. {count} documents stored in '{settings.chroma_collection}'.")

    return {
        "status": "success",
        "documents_ingested": count,
        "collection": settings.chroma_collection,
        "persist_dir": settings.chroma_persist_dir,
    }


if __name__ == "__main__":
    data_file = sys.argv[1] if len(sys.argv) > 1 else None
    result = ingest(data_file)
    print(json.dumps(result, indent=2))
