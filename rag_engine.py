"""
RAG engine for the BEMS Troubleshooting Assistant.

Performs semantic similarity search against ChromaDB and uses an LLM
to summarize retrieved tickets into actionable troubleshooting guidance.
"""

from __future__ import annotations

import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI

from config import settings

_model: SentenceTransformer | None = None
_chroma_client: chromadb.PersistentClient | None = None
_openai_client: OpenAI | None = None


def _get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def _get_chroma_collection() -> chromadb.Collection:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _chroma_client.get_collection(name=settings.chroma_collection)


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=settings.cxai_access_token,
            base_url=settings.openai_base_url,
        )
    return _openai_client


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """
    Perform semantic similarity search and return the top-k matching tickets.
    """
    if top_k is None:
        top_k = settings.top_k

    model = _get_embedding_model()
    query_embedding = model.encode([query]).tolist()

    collection = _get_chroma_collection()
    results = collection.query(
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


SYSTEM_PROMPT = """You are the BEMS Troubleshooting Assistant — an expert AI support tool \
for Building Energy Management Systems. Your role is to help TAC and on-call engineers \
diagnose and resolve issues faster.

You will be given:
1. A problem description from the engineer.
2. A set of related past tickets retrieved from the knowledge base.

Your task:
- Analyze the retrieved tickets for patterns, root causes, and proven resolutions.
- Provide a clear, structured troubleshooting summary.
- Highlight the most relevant past ticket(s) and explain why they are relevant.
- Suggest concrete diagnostic steps and potential fixes based on historical data.
- If multiple root causes are possible, rank them by likelihood.
- Note any recurring patterns or systemic issues.

Keep your response concise, actionable, and technically precise. \
Use bullet points and clear section headers."""


def build_context(tickets: list[dict]) -> str:
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


def summarize(query: str, tickets: list[dict]) -> str:
    """
    Use the LLM to generate a troubleshooting summary from query + retrieved tickets.
    """
    context = build_context(tickets)

    user_message = (
        f"## Engineer's Problem Description\n{query}\n\n"
        f"## Related Past Tickets from Knowledge Base\n{context}"
    )

    client = _get_openai_client()
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=2048,
    )

    return response.choices[0].message.content


def query_assistant(problem_description: str, top_k: int | None = None) -> dict:
    """
    End-to-end RAG pipeline: retrieve relevant tickets and generate a summary.
    """
    tickets = retrieve(problem_description, top_k=top_k)
    summary = summarize(problem_description, tickets)

    return {
        "query": problem_description,
        "retrieved_tickets": [
            {
                "ticket_id": t["metadata"].get("ticket_id", "N/A"),
                "title": t["metadata"].get("title", "N/A"),
                "source": t["metadata"].get("source", "N/A"),
                "severity": t["metadata"].get("severity", "N/A"),
                "component": t["metadata"].get("component", "N/A"),
                "similarity_score": t.get("similarity_score"),
            }
            for t in tickets
        ],
        "summary": summary,
    }
