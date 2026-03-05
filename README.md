<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/ChromaDB-FF6F00?style=for-the-badge&logo=databricks&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI_SDK-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/Cisco_BEMS-049FD9?style=for-the-badge&logo=cisco&logoColor=white" />
</p>

<h1 align="center">Prof-AI for BEMS</h1>
<p align="center"><strong>AI-Powered Troubleshooting Assistant for Building Energy Management Systems</strong></p>
<p align="center"><em>Built for the AI Hackathon 2026</em></p>

---

## The Problem

TAC and on-call engineers supporting BEMS environments spend significant time manually searching through past tickets, service requests, and Webex conversations to diagnose recurring issues. This leads to **high mean time to resolution (MTTR)**, inconsistent troubleshooting, and knowledge loss when experienced engineers rotate off-shift.

## Our Solution

**Prof-AI** uses a **Retrieval-Augmented Generation (RAG)** architecture to turn historical support data into instant, AI-powered troubleshooting guidance. Engineers describe a problem in plain language and receive:

- Semantically matched past tickets ranked by relevance
- An LLM-generated diagnostic summary with root-cause rankings and proven fixes
- Structured resolution playbooks with step-by-step procedures and CLI commands

> Think of it as having your most experienced BEMS engineer available 24/7, with perfect recall of every ticket ever resolved.

---

## How It Works

```
  Engineer describes problem
           │
           ▼
  ┌─────────────────────┐
  │   Embed query with   │
  │  SentenceTransformer │
  └─────────┬───────────┘
            │
            ▼
  ┌─────────────────────┐       ┌─────────────────────┐
  │   ChromaDB Vector   │──────▶│  Top-K similar       │
  │     Database        │       │  tickets retrieved    │
  └─────────────────────┘       └─────────┬───────────┘
                                          │
                                          ▼
                                ┌─────────────────────┐
                                │  Cisco CX AI         │
                                │  Playground (LLM)    │
                                │  generates summary   │
                                └─────────┬───────────┘
                                          │
                                          ▼
                                ┌─────────────────────┐
                                │  Structured output:  │
                                │  • Diagnosis         │
                                │  • Root causes       │
                                │  • Fix steps         │
                                │  • Playbook          │
                                └─────────────────────┘
```

---

## Features at a Glance

| Feature | Description |
|---------|-------------|
| **Diagnose Issue** | Full RAG pipeline — describe a problem, get matched tickets + AI troubleshooting summary |
| **Search Tickets** | Fast semantic search across the knowledge base, ranked by cosine similarity |
| **Resolution Playbook** | Click any ticket to see step-by-step fix procedures, reference docs, and CLI commands |
| **Data Ingestion** | Bulk-load tickets from JSON into ChromaDB with locally generated embeddings |
| **Real-Time Ticket Sync** | Add new tickets via JSON, CSV, or webhook — duplicates auto-detected and skipped |
| **Root Cause Analyser** | LLM-powered deep RCA with pattern statistics, impact assessment, and corrective actions |
| **Email Template** | Auto-generated professional RCA email ready to send to stakeholders |
| **Jira Ticket Generator** | AI classifies severity (P1–P4), generates complete Jira ticket with all fields |
| **Fine-Tune Model** | Improve retrieval accuracy by training the embedding model on your own BEMS data |

---

## Screenshots

### Diagnose Issue (RAG Pipeline)
> Engineer enters a problem description → AI retrieves similar past tickets and generates a structured troubleshooting summary with root-cause analysis.

### Root Cause Analyser
> Deep analysis of BEMS symptoms → Pattern statistics, LLM-driven RCA report, email template, and evidence tickets.

### Jira Ticket Generator
> AI classifies issue severity and produces a complete, copy-ready Jira ticket with all required fields.

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/pramod018/Prof_AI.git
cd Prof_AI

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Open `.env` and add your Cisco CX AI Playground JWT token:

```env
CXAI_PLAYGROUND_ACCESS_TOKEN=your-jwt-token-here
```

> **Note:** The token is needed for LLM features (Diagnose, RCA, Jira). Semantic search, ingestion, sync, and fine-tuning all work without it.

### 3. Load Sample Data

```bash
python ingest.py
```

This loads 45 pre-built BEMS tickets into ChromaDB and generates embeddings locally — no API call needed.

### 4. Launch

```bash
python app.py
```

Open **http://localhost:8000** in your browser. That's it!

---

## What Each Tab Does

| Tab | Purpose |
|-----|---------|
| **Diagnose Issue** | Enter a problem → get matched tickets + AI summary. Click any ticket for its Resolution Playbook. |
| **Search Tickets** | Semantic search — type keywords, browse ranked results. Click for playbook details. |
| **Ingest Data** | Load a JSON file of tickets into the vector database. |
| **Ticket Sync** | Paste JSON or CSV to add new tickets on the fly. View sync history below. |
| **Root Cause Analyser** | Enter symptoms → get pattern stats, full RCA report, email template, and evidence. |
| **Raise Jira Ticket** | Describe an issue → AI classifies severity and generates a complete Jira ticket. |
| **Fine-Tune Model** | Train the embedding model on BEMS data. Configure epochs and batch size. |

---

## Sample Ticket Format

```json
{
  "ticket_id": "BEMS-1001",
  "source": "BEMS Ticket",
  "title": "HVAC Zone 3 temperature oscillation",
  "description": "Zone 3 experiencing temperature oscillations of +/- 4°F around setpoint...",
  "resolution": "Retuned PID parameters: reduced proportional gain from 8 to 4...",
  "severity": "P2",
  "component": "HVAC - VAV Controller",
  "date": "2025-11-15",
  "engineer": "jsmith",
  "resolution_steps": [
    "Checked PID loop parameters on VAV controller",
    "Reduced proportional gain from 8 to 4",
    "Monitored zone temp for 30 minutes to confirm stability"
  ],
  "documents_used": [
    "Honeywell VAV Controller Programming Guide v3.2",
    "ASHRAE Guideline 36 — PID Loop Tuning"
  ],
  "commands_used": [
    "bacnet read AV:101 present-value",
    "bacnet write AV:101 present-value 4.0"
  ]
}
```

The dataset includes **45 sample tickets** covering HVAC (VAV, AHU, FCU), chillers, boilers, cooling towers, BACnet/Modbus, VRF systems, IAQ sensors, lighting controls, fire/smoke dampers, and more.

---

## API Reference

| Method | Endpoint | What It Does |
|--------|----------|--------------|
| `GET` | `/` | Serves the web UI |
| `POST` | `/api/query` | Full RAG — retrieve + LLM summarize |
| `GET` | `/api/search?q=...&top_k=5` | Semantic search (no LLM) |
| `POST` | `/api/ingest` | Bulk data ingestion |
| `POST` | `/api/sync/json` | Sync tickets from JSON array |
| `POST` | `/api/sync/csv` | Sync tickets from CSV |
| `POST` | `/api/sync/webhook` | Add single ticket via webhook |
| `GET` | `/api/sync/history` | View sync activity log |
| `POST` | `/api/rca` | Root cause analysis |
| `POST` | `/api/jira-ticket` | Generate Jira ticket |
| `POST` | `/api/finetune` | Fine-tune embedding model |
| `GET` | `/api/health` | Health check |

**Example:**

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"problem_description": "AHU supply fan VFD throwing overcurrent fault after startup", "top_k": 5}'
```

---

## Project Structure

```
Prof_AI/
├── app.py                  # FastAPI app — routes and API endpoints
├── rag_engine.py           # RAG pipeline — embed, retrieve, summarize
├── rca.py                  # Root Cause Analyser — patterns + LLM RCA
├── jira_ticket.py          # Jira generator — severity classification
├── ingest.py               # Data ingestion — JSON → ChromaDB
├── sync_tickets.py         # Real-time sync — JSON/CSV/webhook
├── analytics.py            # Query logging for usage tracking
├── finetune.py             # Embedding fine-tuning module
├── config.py               # Configuration from .env
├── db.py                   # Shared singletons (model + DB client)
├── ticket_utils.py         # Ticket formatting utilities
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
│
├── sample_data/
│   └── bems_tickets.json   # 45 sample tickets with playbooks
│
├── templates/
│   └── index.html          # Web UI (Jinja2 template)
│
├── static/
│   ├── css/style.css       # Dark-themed Cisco-branded styles
│   └── js/app.js           # Frontend logic and interactions
│
├── chroma_db/              # Vector DB storage (auto-created)
└── finetuned_model/        # Fine-tuned model output (auto-created)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, FastAPI, Uvicorn |
| **Vector Database** | ChromaDB (local, persistent) |
| **Embeddings** | sentence-transformers (`all-MiniLM-L6-v2`, runs locally) |
| **LLM** | Cisco CX AI Playground (`gpt-4o-mini` via OpenAI SDK) |
| **Frontend** | HTML, CSS, JavaScript (no framework) |
| **Templating** | Jinja2 |
| **Configuration** | pydantic-settings, python-dotenv |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CXAI_PLAYGROUND_ACCESS_TOKEN` | Cisco CX AI Playground JWT | *(required for LLM)* |
| `OPENAI_BASE_URL` | LLM API base URL | `https://cxai-playground.cisco.com` |
| `EMBEDDING_MODEL` | Embedding model name | `all-MiniLM-L6-v2` |
| `LLM_MODEL` | LLM model name | `gpt-4o-mini` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `./chroma_db` |
| `CHROMA_COLLECTION` | Collection name | `bems_tickets` |
| `TOP_K` | Default results per query | `5` |
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8000` |

---

## Team

Built with care for the **AI Hackathon 2026** by the Prof-AI team.

---

<p align="center"><sub>Prof-AI for BEMS — Reducing MTTR, one ticket at a time.</sub></p>
