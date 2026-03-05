"""
FastAPI backend for the BEMS Troubleshooting Assistant.

Provides REST API endpoints for querying the RAG pipeline and
serves the web-based user interface.
"""

from __future__ import annotations

import os
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config import settings
from rag_engine import query_assistant, retrieve
from ingest import ingest
from analytics import save_query_log_entry
from rca import analyse_root_cause
from ticket_utils import format_ticket_result
from sync_tickets import (
    sync_from_list,
    sync_from_csv,
    sync_single_ticket,
    get_sync_history,
)

from finetune import finetune as run_finetune
from jira_ticket import generate_jira_ticket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Prof-AI for BEMS",
    description="AI-powered support tool for diagnosing BEMS issues using RAG",
    version="1.0.0",
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(_BASE_DIR, "static")), name="static")
_templates = Jinja2Templates(directory=os.path.join(_BASE_DIR, "templates"))


# ---- Request Models ----

class QueryRequest(BaseModel):
    problem_description: str = Field(..., min_length=10, max_length=5000)
    top_k: int = Field(default=5, ge=1, le=20)


class IngestRequest(BaseModel):
    data_path: str | None = None


class SyncJsonRequest(BaseModel):
    tickets: list[dict] = Field(..., min_length=1)


class SyncCsvRequest(BaseModel):
    csv_content: str = Field(..., min_length=10)


# ---- UI ----

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return _templates.TemplateResponse("index.html", {"request": request})


# ---- RAG Endpoints ----

@app.post("/api/query")
async def query_endpoint(req: QueryRequest):
    """Full RAG pipeline: retrieve + LLM summarize."""
    try:
        result = query_assistant(
            problem_description=req.problem_description,
            top_k=req.top_k,
        )
        save_query_log_entry(req.problem_description, len(result.get("retrieved_tickets", [])))
        return JSONResponse(content=result)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized. Run POST /api/ingest first.")
    except Exception as e:
        logger.exception("Error processing query")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_endpoint(q: str, top_k: int = 5):
    """Semantic search only (no LLM summary)."""
    if not q or len(q) < 5:
        raise HTTPException(status_code=400, detail="Query must be at least 5 characters")
    try:
        tickets = retrieve(q, top_k=top_k)
        results = []
        for t in tickets:
            entry = format_ticket_result(t)
            entry["document"] = t.get("document", "")
            results.append(entry)
        return JSONResponse(content={"query": q, "results": results})
    except Exception as e:
        logger.exception("Error during search")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Ingestion ----

@app.post("/api/ingest")
async def ingest_endpoint(req: IngestRequest):
    try:
        result = ingest(data_path=req.data_path)
        return JSONResponse(content=result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Data file not found: {e}")
    except Exception as e:
        logger.exception("Error during ingestion")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Ticket Sync ----

@app.post("/api/sync/json")
async def sync_json_endpoint(req: SyncJsonRequest):
    try:
        return JSONResponse(content=sync_from_list(req.tickets))
    except Exception as e:
        logger.exception("Error during JSON sync")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/csv")
async def sync_csv_endpoint(req: SyncCsvRequest):
    try:
        return JSONResponse(content=sync_from_csv(req.csv_content))
    except Exception as e:
        logger.exception("Error during CSV sync")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/webhook")
async def sync_webhook_endpoint(ticket: dict):
    try:
        return JSONResponse(content=sync_single_ticket(ticket))
    except Exception as e:
        logger.exception("Error during webhook sync")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sync/history")
async def sync_history_endpoint():
    return JSONResponse(content=get_sync_history())


# ---- Root Cause Analysis ----

class RcaRequest(BaseModel):
    symptom: str = Field(..., min_length=10, max_length=5000)
    top_k: int = Field(default=10, ge=1, le=20)


@app.post("/api/rca")
async def rca_endpoint(req: RcaRequest):
    """Perform root-cause analysis using RAG + LLM."""
    try:
        result = analyse_root_cause(symptom=req.symptom, top_k=req.top_k)
        return JSONResponse(content=result)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized. Run POST /api/ingest first.")
    except Exception as e:
        logger.exception("Error during root cause analysis")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Health ----

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "database_initialized": os.path.exists(settings.chroma_persist_dir),
        "embedding_model": settings.embedding_model,
        "llm_model": settings.llm_model,
    }


# ---- Jira Ticket Generator ----

class JiraTicketRequest(BaseModel):
    issue_description: str = Field(..., min_length=10, max_length=5000)
    rca_report: str | None = None
    override_severity: int | None = Field(default=None, ge=1, le=4)


@app.post("/api/jira-ticket")
async def jira_ticket_endpoint(req: JiraTicketRequest):
    """Generate a Jira ticket with LLM-based severity classification."""
    try:
        result = generate_jira_ticket(
            issue_description=req.issue_description,
            rca_report=req.rca_report,
            override_severity=req.override_severity,
        )
        return JSONResponse(content=result)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized. Run POST /api/ingest first.")
    except Exception as e:
        logger.exception("Error generating Jira ticket")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Fine-tune ----

class FinetuneRequest(BaseModel):
    data_path: str | None = None
    epochs: int = Field(default=3, ge=1, le=20)
    batch_size: int = Field(default=16, ge=1, le=128)


@app.post("/api/finetune")
async def finetune_endpoint(req: FinetuneRequest):
    """Fine-tune the embedding model on BEMS ticket data."""
    try:
        result = run_finetune(data_path=req.data_path, epochs=req.epochs, batch_size=req.batch_size)
        return JSONResponse(content=result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Data file not found: {e}")
    except Exception as e:
        logger.exception("Error during fine-tuning")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=settings.host, port=settings.port, reload=True)
