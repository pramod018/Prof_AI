"""
Shared database and model singletons for the BEMS Troubleshooting Assistant.

All modules should import from here instead of creating their own
ChromaDB clients or SentenceTransformer instances.
"""

from __future__ import annotations

import chromadb
from sentence_transformers import SentenceTransformer

from config import settings

_embedding_model: SentenceTransformer | None = None
_chroma_client: chromadb.PersistentClient | None = None


def get_embedding_model() -> SentenceTransformer:
    """Return the cached embedding model, loading it on first call."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def get_chroma_client() -> chromadb.PersistentClient:
    """Return the cached ChromaDB persistent client."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _chroma_client


def get_collection() -> chromadb.Collection:
    """Return the BEMS ticket collection."""
    return get_chroma_client().get_collection(name=settings.chroma_collection)


def get_or_create_collection() -> chromadb.Collection:
    """Return the BEMS ticket collection, creating it if it doesn't exist."""
    return get_chroma_client().get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )


def reset_chroma_client() -> None:
    """Force re-creation of the ChromaDB client on next access.

    Useful after operations that delete/recreate collections.
    """
    global _chroma_client
    _chroma_client = None
