# Acme Corp HR Policy Agent

An agentic AI system that helps employees with HR policy questions and workflows. Built with **RAG** (Retrieval-Augmented Generation) over company policy documents, **MCP** (Model Context Protocol) for tool integration, and **Groq Llama-3.3-70b** as the reasoning backbone.

**Quantic MSAIE Capstone Project** — Zeliha Ungun & Fahrettin Ungun

**Live Demo**: https://hr-policy-agent-production.up.railway.app

---

## Features

- **Policy RAG**: Answers questions grounded in 10+ company policy documents with cited sources
- **Agentic Workflows**: Multi-step HR tasks (PTO requests, remote work eligibility, benefits checks)
- **MCP Integration**: 8 tools exposed via MCP stdio server for employee data, policy search, and mock HR actions
- **Safety Guardrails**: Irreversible actions (ticket creation, email drafts) require explicit user confirmation
- **Trace Visibility**: Every tool call, argument, and result is shown in the UI

---

## Architecture

```
Browser (Chat UI)
       │
       ▼
FastAPI Web App  (/chat, /health, /demo/task1, /demo/task2)
       │
       ▼
Agent Orchestrator  (agent/orchestrator.py)
  └─ Groq llama-3.3-70b-versatile via Groq Python SDK
       │
       ├─ MCP Client (mcp Python SDK, stdio transport)
       │       │
       │       ▼
       │  MCP Server (mcp_server/server.py — subprocess)
       │    ├─ search_policy_documents   → ChromaDB (RAG)
       │    ├─ get_policy_section        → ChromaDB (RAG)
       │    ├─ check_policy_compliance   → ChromaDB (RAG)
       │    ├─ lookup_employee_profile   → mock_data/employees.json
       │    ├─ check_pto_balance         → mock_data/pto_balances.json
       │    ├─ lookup_benefits_status    → mock_data/benefits.json
       │    ├─ create_mock_hr_ticket     → mock_data/hr_tickets.json (with confirmation)
       │    └─ draft_hr_email            → mock only, never sends (with confirmation)
       │
       └─ RAG Index: ChromaDB + fastembed (BAAI/bge-small-en-v1.5)
                     built from corpus/ at Docker build time
```

---

## Quick Start (Local)

### Prerequisites
- Python 3.12+
- A Groq API key (free at https://console.groq.com)

### Setup

```bash
git clone https://github.com/zungun1989/hr-policy-agent.git
cd hr-policy-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.\.venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add: GROQ_API_KEY=gsk_...

# Build RAG index (downloads ~33MB embedding model first run)
python rag/ingest.py

# Start the app
uvicorn app.main:app --reload
```

Open http://localhost:8000 in your browser.

### Verify System Health

```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status": "ok", "rag_index": "loaded", "rag_chunk_count": 113, "mcp": "available", "model": "groq/llama-3.3-70b-versatile"}
```

---

## Running the Two Demo Tasks

### Via UI
Click **"Task 1 — PTO Request"** or **"Task 2 — Remote Work Eligibility"** in the sidebar.

### Via API

```bash
# Task 1: PTO request guidance (EMP003, Carol)
curl -X POST http://localhost:8000/demo/task1 | python -m json.tool

# Task 2: Remote work eligibility (EMP001, Alice, 6 weeks NY)
curl -X POST http://localhost:8000/demo/task2 | python -m json.tool
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests cover:
- `/health` smoke test (app starts successfully)
- `/` HTML response
- Empty message rejection
- All 8 MCP tool functions (direct unit tests)
- MCP tool discovery (server TOOLS list)
- Action safety (confirmation gates)

---

## Evaluation

```bash
# Run full eval set (k=5) with ablation (k=3)
python evaluation/run_eval.py --k 5 --k-ablation 3 --output evaluation/results.json
```

See [evaluation/](evaluation/) for the 25-question set and results.

---

## Deployment (Railway)

The app is deployed to Railway using Docker. The RAG index is built during the Docker image build phase (`RUN python rag/ingest.py` in Dockerfile), so no cold-start indexing delay occurs.

**Deployed URL**: https://hr-policy-agent-production.up.railway.app

See [deployed.md](deployed.md) for full deployment details and environment variable configuration.

---

## Project Structure

```
hr-policy-agent/
├── corpus/           # 10 markdown + 1 PDF policy documents
├── mock_data/        # Synthetic employee, PTO, benefits, ticket data (JSON)
├── rag/              # Ingestion pipeline + ChromaDB retriever
├── mcp_server/       # MCP server + 8 tools (stdio transport)
├── agent/            # Agent orchestrator + prompts
├── app/              # FastAPI app + HTML chat UI
├── evaluation/       # 25-question eval set + run_eval.py
├── tests/            # Pytest smoke + MCP unit tests
└── .github/workflows/ci.yml  # GitHub Actions CI
```

---

## AI Tooling

See [ai-tooling.md](ai-tooling.md) for details on how Claude Code was used throughout this project.

## Design Documentation

See [design-and-evaluation.md](design-and-evaluation.md) for architecture details, RAG design, MCP schema, and evaluation results.
