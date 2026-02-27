"""
FastAPI backend for the BEMS Troubleshooting Assistant.

Provides REST API endpoints for querying the RAG pipeline and
serves the web-based user interface.
"""

import os
import json
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config import settings
from rag_engine import query_assistant, retrieve
from ingest import ingest

# --- Fine-tune module (DISABLED) ---
# To enable: uncomment the import and the /api/finetune endpoint below
# from finetune import finetune as run_finetune

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BEMS Troubleshooting Assistant",
    description="AI-powered support tool for diagnosing BEMS issues using RAG",
    version="1.0.0",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


class QueryRequest(BaseModel):
    problem_description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Description of the BEMS issue to troubleshoot",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of similar tickets to retrieve",
    )


class IngestRequest(BaseModel):
    data_path: str | None = Field(
        default=None,
        description="Path to JSON data file (uses default sample data if not provided)",
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main web UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/query")
async def query_endpoint(req: QueryRequest):
    """
    Submit a problem description and get RAG-based troubleshooting guidance.
    Returns retrieved tickets and an LLM-generated summary.
    """
    try:
        result = query_assistant(
            problem_description=req.problem_description,
            top_k=req.top_k,
        )
        return JSONResponse(content=result)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Knowledge base not initialized. Please run data ingestion first via POST /api/ingest.",
        )
    except Exception as e:
        logger.exception("Error processing query")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest")
async def ingest_endpoint(req: IngestRequest):
    """Trigger data ingestion into the vector database."""
    try:
        result = ingest(data_path=req.data_path)
        return JSONResponse(content=result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Data file not found: {e}")
    except Exception as e:
        logger.exception("Error during ingestion")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_endpoint(q: str, top_k: int = 5):
    """
    Lightweight semantic search endpoint (retrieval only, no LLM summary).
    Useful for quick lookups without waiting for LLM generation.
    """
    if not q or len(q) < 5:
        raise HTTPException(status_code=400, detail="Query must be at least 5 characters")
    try:
        tickets = retrieve(q, top_k=top_k)
        return JSONResponse(content={
            "query": q,
            "results": [
                {
                    "ticket_id": t["metadata"].get("ticket_id", "N/A"),
                    "title": t["metadata"].get("title", "N/A"),
                    "source": t["metadata"].get("source", "N/A"),
                    "severity": t["metadata"].get("severity", "N/A"),
                    "component": t["metadata"].get("component", "N/A"),
                    "date": t["metadata"].get("date", "N/A"),
                    "similarity_score": t.get("similarity_score"),
                    "document": t.get("document", ""),
                }
                for t in tickets
            ],
        })
    except Exception as e:
        logger.exception("Error during search")
        raise HTTPException(status_code=500, detail=str(e))


# --- Fine-tune endpoint (DISABLED) ---
# Uncomment to enable fine-tuning via the API.
# When enabled, POST /api/finetune triggers embedding model fine-tuning
# on BEMS ticket data to improve domain-specific retrieval accuracy.
#
# class FinetuneRequest(BaseModel):
#     data_path: str | None = Field(
#         default=None,
#         description="Path to training data JSON (uses default sample data if not provided)",
#     )
#     epochs: int = Field(default=3, ge=1, le=20, description="Number of training epochs")
#     batch_size: int = Field(default=16, ge=1, le=128, description="Training batch size")
#
#
# @app.post("/api/finetune")
# async def finetune_endpoint(req: FinetuneRequest):
#     """
#     Fine-tune the embedding model on BEMS ticket data.
#     Improves retrieval accuracy for domain-specific terminology.
#     After fine-tuning, update EMBEDDING_MODEL in .env to point to the
#     fine-tuned model directory and restart the application.
#     """
#     try:
#         result = run_finetune(
#             data_path=req.data_path,
#             epochs=req.epochs,
#             batch_size=req.batch_size,
#         )
#         return JSONResponse(content=result)
#     except FileNotFoundError as e:
#         raise HTTPException(status_code=404, detail=f"Data file not found: {e}")
#     except Exception as e:
#         logger.exception("Error during fine-tuning")
#         raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    db_exists = os.path.exists(settings.chroma_persist_dir)
    return {
        "status": "healthy",
        "database_initialized": db_exists,
        "embedding_model": settings.embedding_model,
        "llm_model": settings.llm_model,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
