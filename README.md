# Prof-AI for BEMS

**Prof-AI for BEMS** is an AI-powered troubleshooting assistant built for TAC and on-call engineers working with Building Energy Management Systems (BEMS). It uses a **Retrieval-Augmented Generation (RAG)** architecture to combine fast semantic search over historical support data with LLM-driven diagnostic summaries, helping engineers resolve issues faster and reduce mean time to resolution.

## How It Works

Engineers describe a BEMS problem in plain language. The system searches a vector database of past tickets, service requests, and Webex conversations to find semantically similar issues. It then feeds those matches to an LLM, which generates a structured troubleshooting summary with root-cause analysis, diagnostic steps, and proven fixes drawn from historical data.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Prof-AI Web UI (Browser)                            │
│ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────┐ ┌──────┐ ┌─────┐│
│ │ Diagnose │ │ Search   │ │ Ingest │ │ Ticket │ │ RCA  │ │ Jira │ │Fine ││
│ │  Issue   │ │ Tickets  │ │  Data  │ │  Sync  │ │      │ │Ticket│ │Tune ││
│ └────┬─────┘ └────┬─────┘ └───┬────┘ └───┬────┘ └──┬───┘ └──┬───┘ └──┬──┘│
└──────┼────────────┼───────────┼──────────┼─────────┼────────┼────────┼───┘
       │            │           │          │         │        │        │
       ▼            ▼           ▼          ▼         ▼        ▼        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend (app.py)                             │
│  /api/query  /api/search  /api/ingest  /api/sync/*  /api/rca  /api/jira-*  │
└───────┬──────────┬──────────┬──────────┬───────────┬──────────┬─────────────┘
        │          │          │          │           │          │
        ▼          ▼          ▼          ▼           ▼          ▼
┌──────────────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐
│     RAG Engine       │ │  Ingest  │ │  Ticket  │ │ Cisco CX AI          │
│ 1. Embed query       │ │(ingest.py│ │   Sync   │ │ Playground (LLM)     │
│ 2. Retrieve ChromaDB │ │)         │ │(sync_    │ │ (remote API)         │
│ 3. Summarize via LLM │ └──────────┘ │tickets.py│ └──────────────────────┘
└─────────┬────────────┘              └──────────┘
          ▼
┌─────────────────┐
│ ChromaDB Vector │
│    Database     │
│  (local disk)   │
└─────────────────┘
```

## Features

### Core RAG Pipeline
- **Diagnose Issue** — Describe a problem in natural language, retrieve the most relevant past tickets via vector similarity, and receive an LLM-generated troubleshooting summary with root-cause rankings, diagnostic steps, and recommended fixes.
- **Search Tickets** — Fast semantic search across the knowledge base without LLM analysis. Returns ranked results by cosine similarity.
- **Resolution Playbook** — Click any retrieved ticket to view its structured resolution details in the sidebar: step-by-step procedures, reference documents, and CLI commands used during the original fix.

### Knowledge Base Management
- **Data Ingestion** — Bulk-load tickets from JSON into ChromaDB. Embeddings are generated locally using `all-MiniLM-L6-v2` (no external API needed).
- **Real-Time Ticket Sync** — Add new tickets on the fly via JSON upload, CSV import, or webhook. Duplicates are automatically detected and skipped. All synced tickets are immediately searchable.

### Root Cause Analysis
- **Root Cause Analyser** — LLM-powered deep root-cause analysis that retrieves historical tickets, identifies failure patterns and contributing factors, assesses impact, and recommends prioritised corrective actions (immediate, short-term, long-term).
- **Pattern Statistics** — Automated detection of recurring components, severity distribution, and data sources across similar historical incidents.
- **Email Template** — Auto-generated professional RCA email template ready to copy and send to stakeholders.

### Jira Ticket Generation
- **Raise Jira Ticket** — LLM-based severity classification (P1-Critical through P4-Low) that analyses issue sentiment and impact, then generates a complete structured Jira ticket with summary, description, component, labels, and acceptance criteria.
- **Copy-Ready Output** — Generated tickets are formatted for direct copy-paste into Jira with all required fields populated.
- **RCA Integration** — Optionally feed RCA report context into the Jira generator for more accurate severity classification.

### Embedding Fine-Tuning
- **Fine-Tune Model** — Fine-tune the sentence-transformer embedding model on BEMS ticket data using contrastive learning (CosineSimilarityLoss). Generates positive pairs (description-resolution from the same ticket) and negative pairs (cross-component mismatches) to produce better domain-specific embeddings.

### Additional
- **45 Sample Tickets** — Pre-built dataset covering HVAC (VAV, AHU, FCU), chillers, boilers, cooling towers, BACnet/Modbus, VRF systems, IAQ sensors, lighting controls, fire/smoke dampers, and more. Each ticket includes resolution steps, reference documents, and commands used.

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/pramod018/Prof_AI.git
cd Prof_AI

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and set your Cisco CX AI Playground JWT token:

```
CXAI_PLAYGROUND_ACCESS_TOKEN=your-jwt-token-here
```

This token is required for LLM-based features (Diagnose Issue, Root Cause Analyser, Jira Ticket Generator). Semantic search, data ingestion, ticket sync, and fine-tuning work without it.

### 3. Ingest Sample Data

```bash
python ingest.py
```

Loads 45 sample BEMS tickets into ChromaDB and generates embeddings locally using `all-MiniLM-L6-v2`. No external API call is needed for this step.

### 4. Run

```bash
python app.py
```

Open **http://localhost:8000** in your browser.

## Usage Guide

| Tab | What It Does |
|-----|-------------|
| **Diagnose Issue** | Full RAG pipeline — enter a problem description, get matched tickets + AI-generated troubleshooting summary. Click any ticket card to open the Resolution Playbook in the sidebar. |
| **Search Tickets** | Semantic search only — enter keywords or a description, browse ranked results. Click a ticket to see its playbook. |
| **Ingest Data** | Load a JSON file of tickets into ChromaDB (or re-ingest the default sample data). |
| **Ticket Sync** | Paste JSON or CSV ticket data to add new entries to the knowledge base in real time. View sync history at the bottom. |
| **Root Cause Analyser** | Enter a symptom to run LLM-powered RCA. View pattern statistics, the full RCA report, a copy-ready email template, and evidence tickets. |
| **Raise Jira Ticket** | Describe an issue to get AI-classified severity and a complete Jira ticket. Optionally paste RCA context for better classification. Copy-ready output included. |
| **Fine-Tune Model** | Train the embedding model on BEMS data to improve retrieval accuracy. Configure epochs and batch size. |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CXAI_PLAYGROUND_ACCESS_TOKEN` | Cisco CX AI Playground JWT token | — (required for LLM) |
| `OPENAI_BASE_URL` | LLM API base URL | `https://cxai-playground.cisco.com` |
| `EMBEDDING_MODEL` | Sentence-transformer model for embeddings | `all-MiniLM-L6-v2` |
| `LLM_MODEL` | LLM model name for summarization | `gpt-4o-mini` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage directory | `./chroma_db` |
| `CHROMA_COLLECTION` | ChromaDB collection name | `bems_tickets` |
| `TOP_K` | Default number of results to retrieve | `5` |
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8000` |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/api/query` | Full RAG: retrieve + LLM summarize |
| `GET` | `/api/search?q=...&top_k=5` | Semantic search (retrieval only) |
| `POST` | `/api/ingest` | Bulk data ingestion into ChromaDB |
| `POST` | `/api/sync/json` | Sync tickets from JSON array |
| `POST` | `/api/sync/csv` | Sync tickets from CSV content |
| `POST` | `/api/sync/webhook` | Add a single ticket via webhook |
| `GET` | `/api/sync/history` | Sync activity log |
| `POST` | `/api/rca` | Root cause analysis (RAG + LLM) |
| `POST` | `/api/jira-ticket` | Generate Jira ticket with severity classification |
| `POST` | `/api/finetune` | Fine-tune the embedding model |
| `GET` | `/api/health` | Health check |

### Example

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"problem_description": "AHU supply fan VFD throwing overcurrent fault after startup", "top_k": 5}'
```

## Ticket Data Format

Each ticket in the knowledge base has this structure:

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

Supported `source` values: `BEMS Ticket`, `Service Request`, `Webex Conversation`

## Project Structure

```
Prof_AI/
├── app.py                  # FastAPI application — routes, middleware, API endpoints
├── rag_engine.py           # RAG pipeline — embedding, retrieval, LLM summarization
├── rca.py                  # Root Cause Analyser — pattern detection + LLM-driven RCA
├── jira_ticket.py          # Jira ticket generator — severity classification + formatting
├── ingest.py               # Bulk data ingestion — JSON → embeddings → ChromaDB
├── sync_tickets.py         # Real-time ticket sync — JSON/CSV/webhook with dedup
├── analytics.py            # Analytics computation — metrics, counters, query logs
├── finetune.py             # Embedding fine-tuning with contrastive learning
├── config.py               # Pydantic-based configuration from .env
├── db.py                   # Shared singletons — SentenceTransformer + ChromaDB client
├── ticket_utils.py         # Shared utilities — document building, metadata, playbook parsing
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── sample_data/
│   └── bems_tickets.json   # 45 sample BEMS support tickets with resolution playbooks
├── templates/
│   └── index.html          # Single-page web UI (Jinja2 template)
├── static/
│   ├── css/style.css       # Dark-themed Cisco-branded UI styles
│   └── js/app.js           # Frontend logic — forms, rendering, clipboard, playbook panel
├── chroma_db/              # ChromaDB persistence (auto-created on ingestion)
└── finetuned_model/        # Fine-tuned model output (created when fine-tuning runs)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, Uvicorn |
| Vector Database | ChromaDB (local, persistent) |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`, runs locally) |
| LLM | Cisco CX AI Playground (`gpt-4o-mini`, via OpenAI SDK) |
| Frontend | HTML, CSS, JavaScript (no framework) |
| Templating | Jinja2 |
| Configuration | pydantic-settings, python-dotenv |
