# BEMS Troubleshooting Assistant

An AI-powered support tool that helps TAC and on-call engineers diagnose and resolve Building Energy Management System (BEMS) issues faster using Retrieval-Augmented Generation (RAG).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Web UI (Browser)                         │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Diagnose │  │Search Tickets│  │    Ingest Data        │ │
│  └────┬─────┘  └──────┬───────┘  └───────────┬───────────┘ │
└───────┼────────────────┼──────────────────────┼─────────────┘
        │                │                      │
        ▼                ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (app.py)                    │
│  POST /api/query    GET /api/search    POST /api/ingest     │
└────────┬────────────────┬──────────────────────┬────────────┘
         │                │                      │
         ▼                ▼                      ▼
┌──────────────────────────────────────┐  ┌───────────────────┐
│       RAG Engine (rag_engine.py)     │  │ Ingest (ingest.py)│
│  ┌────────────┐ ┌──────────────────┐ │  │ Load JSON → Embed │
│  │  Retrieve   │ │    Summarize     │ │  │ → Store in Chroma │
│  │ (ChromaDB)  │ │ (Cisco CX AI)   │ │  └───────────────────┘
│  └──────┬──────┘ └──────┬──────────┘ │
└─────────┼───────────────┼────────────┘
          ▼               ▼
┌─────────────────┐ ┌──────────────────────┐
│ ChromaDB Vector │ │ Cisco CX AI          │
│    Database     │ │ Playground           │
│                 │ │ (gpt-4o-mini)        │
└─────────────────┘ └──────────────────────┘
```

## Features

- **Semantic Search**: Find similar past tickets using vector similarity (sentence-transformers)
- **AI Summarization**: LLM-generated troubleshooting guidance via Cisco CX AI Playground
- **Multi-Source Data**: Supports BEMS tickets, Service Requests, and Webex conversations
- **45 Sample Tickets**: Rich dataset covering HVAC, chillers, boilers, BACnet, VRF, IAQ, and more
- **Modern Web UI**: Dark-themed, responsive interface with three modes
- **REST API**: Full API for programmatic integration

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

Edit `.env` and add your Cisco CX AI Playground JWT token:

```
CXAI_PLAYGROUND_ACCESS_TOKEN=your-jwt-token-here
```

The application uses the Cisco CX AI Playground API (`https://cxai-playground.cisco.com`) via the OpenAI SDK. The base URL is pre-configured in `.env.example` — you only need to provide your JWT token.

### 3. Ingest Sample Data

```bash
python ingest.py
```

This loads 45 sample BEMS tickets into ChromaDB and generates embeddings locally using `all-MiniLM-L6-v2` (no API key needed for embeddings).

### 4. Run the Application

```bash
python app.py
```

Open http://localhost:8000 in your browser.

## Usage

### Diagnose Issue (Full RAG Pipeline)
1. Click **Diagnose Issue** in the sidebar
2. Describe the BEMS problem in detail
3. Click **Analyze & Diagnose**
4. Review the AI-generated troubleshooting summary and matched tickets

### Search Tickets (Semantic Search Only)
1. Click **Search Tickets**
2. Enter keywords or a short description
3. Browse matching tickets (click to expand details)

### Ingest Data
1. Click **Ingest Data**
2. Optionally specify a custom JSON file path
3. Click **Start Ingestion**

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CXAI_PLAYGROUND_ACCESS_TOKEN` | Cisco CX AI Playground JWT token (required) | — |
| `OPENAI_BASE_URL` | LLM API base URL | `https://cxai-playground.cisco.com` |
| `EMBEDDING_MODEL` | Local sentence-transformer model | `all-MiniLM-L6-v2` |
| `LLM_MODEL` | LLM model for summarization | `gpt-4o-mini` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage directory | `./chroma_db` |
| `CHROMA_COLLECTION` | ChromaDB collection name | `bems_tickets` |
| `TOP_K` | Default number of results to retrieve | `5` |
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8000` |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/api/query` | Full RAG query (retrieve + summarize) |
| `GET` | `/api/search?q=...&top_k=5` | Semantic search only |
| `POST` | `/api/ingest` | Trigger data ingestion |
| `GET` | `/api/health` | Health check |

### Example API Call

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"problem_description": "AHU supply fan VFD throwing overcurrent fault", "top_k": 5}'
```

## Data Format

The ingestion module expects a JSON array of ticket objects:

```json
[
  {
    "ticket_id": "BEMS-1001",
    "source": "BEMS Ticket",
    "title": "HVAC Zone 3 temperature oscillation",
    "description": "Zone 3 experiencing temperature oscillations...",
    "resolution": "Retuned PID parameters...",
    "severity": "P2",
    "component": "HVAC - VAV Controller",
    "date": "2025-11-15",
    "engineer": "jsmith"
  }
]
```

Supported `source` values: `BEMS Ticket`, `Service Request`, `Webex Conversation`

## Fine-Tuning (Optional, Currently Disabled)

The project includes a fine-tuning module (`finetune.py`) that can improve retrieval accuracy by training the embedding model on BEMS-specific terminology. It is fully implemented but **commented out** by default.

### What It Does

- Generates **contrastive training pairs** from ticket data:
  - **Positive pairs**: description <-> resolution (same ticket)
  - **Negative pairs**: description <-> resolution (different component families)
- Fine-tunes the `all-MiniLM-L6-v2` model using `CosineSimilarityLoss`
- Splits data 80/20 for training/evaluation
- Saves the fine-tuned model to `./finetuned_model/`

### How to Enable

1. **`finetune.py`** — Uncomment the entire module body (everything inside the file)
2. **`app.py`** — Uncomment the `from finetune import ...` line and the `/api/finetune` endpoint
3. **`templates/index.html`** — Uncomment the Fine-Tune sidebar button and tab panel
4. **`static/js/app.js`** — Uncomment the fine-tune form handler

### Standalone Usage

```bash
python finetune.py
```

After fine-tuning, update your `.env`:

```
EMBEDDING_MODEL=./finetuned_model/bems_ft_YYYYMMDD_HHMMSS
```

Then re-run `python ingest.py` to re-embed tickets with the fine-tuned model.

## Project Structure

```
Prof_AI/
├── app.py                  # FastAPI application and API endpoints
├── rag_engine.py           # RAG retrieval and LLM summarization
├── ingest.py               # Data ingestion and embedding pipeline
├── finetune.py             # Embedding model fine-tuning (disabled)
├── config.py               # Configuration management
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── sample_data/
│   └── bems_tickets.json   # 45 sample BEMS support tickets
├── templates/
│   └── index.html          # Web UI template
├── static/
│   ├── css/style.css       # UI styles
│   └── js/app.js           # Frontend logic
├── chroma_db/              # ChromaDB persistence (created at runtime)
└── finetuned_model/        # Fine-tuned models (created when fine-tuning runs)
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Uvicorn |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| LLM | Cisco CX AI Playground (gpt-4o-mini) |
| Frontend | Vanilla HTML/CSS/JS |
| Templating | Jinja2 |
