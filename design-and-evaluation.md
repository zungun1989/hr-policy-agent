# Design and Evaluation

## Architecture Overview

```
Browser  ──HTTP──►  FastAPI App  ──────────────────────────────────────────────────
                    (app/main.py)                                                  │
                         │                                                         │
                         ▼                                                         │
                  Agent Orchestrator                                                │
                  (agent/orchestrator.py)                                          │
                         │                                                         │
                    Google Gemini Flash (gemini-flash-latest, OpenAI-compatible API)              │
                         │                                                         │
                    MCP Client (mcp Python SDK)                                    │
                         │ stdio                                                   │
                         ▼                                                         │
                  MCP Server (mcp_server/server.py)                                │
                    ├─ RAG Tools ──────────────────► ChromaDB                      │
                    │   search_policy_documents       (rag/chroma_store/)          │
                    │   get_policy_section            fastembed BAAI/bge-small     │
                    │   check_policy_compliance                                    │
                    │                                                              │
                    └─ HR Data Tools ──────────────► Mock JSON Data               │
                        lookup_employee_profile       (mock_data/)                │
                        check_pto_balance                                         │
                        lookup_benefits_status                                    │
                        create_mock_hr_ticket                                     │
                        draft_hr_email                                            │
                                                                                  │
                    ──────────────────────────────────────────────────────────────
```

---

## RAG Design

### Corpus
- 10 Markdown policy documents + 1 PDF (holiday calendar) = ~50–70 pages total
- Topics: PTO, remote work, expenses, benefits, onboarding, data security, conduct, leave, equipment, travel, holidays
- All documents are synthetic and authored specifically for this project

### Chunking Strategy
- **Markdown**: Heading-aware chunking (split on H1/H2 headings), then token-window within sections (400 tokens max, 64-token overlap)
- **PDF**: Token window with overlap (400 tokens, 64-token overlap)
- **Seed**: `PYTHONHASHSEED=42` set for deterministic ordering
- Result: ~113 chunks across all documents

### Embedding Model
- `fastembed` with `BAAI/bge-small-en-v1.5` (~33MB, CPU-only, no GPU needed)
- Chosen over sentence-transformers to avoid large PyTorch dependency on free-tier deploy
- Cosine similarity space in ChromaDB

### Retrieval
- Default `top_k=5`, configurable per tool call
- `doc_filter` parameter in retriever allows single-document search (used in `get_policy_section`)
- No reranker in v1 (ablation study compares k=3 vs k=5)

### RAG Guardrails
1. Out-of-corpus detection: system prompt instructs the model to use "outside scope" decline language
2. Policy fact vs recommendation: system prompt distinguishes ("According to policy..." vs "I recommend...")
3. Insufficient evidence: system prompt instructs escalation to HR when policy evidence is thin

---

## MCP Server Design

### Transport Choice: stdio
- **Why**: Single-service deployment (Railway Docker). No separate port needed.
- The agent orchestrator starts the MCP server as a subprocess and communicates via stdin/stdout
- For a multi-service deployment, Streamable HTTP would be more appropriate

### Tool Discovery
- Agent calls `session.list_tools()` on each conversation
- Returns all 8 tool definitions with JSON Schema input schemas
- The LLM receives these as `tools` parameter in the API call

### Tool Schemas
All tools use JSON Schema v7. Key design decisions:
- `requester_confirmed: bool` on action tools prevents accidental execution
- `doc_id` in `get_policy_section` enables targeted retrieval
- `enum` values on `ticket_type` and `to_role` constrain valid inputs

### How the Agent Calls Tools
1. LLM receives tool definitions from MCP server discovery
2. LLM returns tool call blocks when it decides to call a tool
3. Orchestrator extracts each tool call and calls `session.call_tool(name, arguments)` via MCP SDK
4. Tool result is returned to the LLM as a `tool` role message
5. LLM synthesizes final response — **no hard-coded function calls**

---

## Agent Orchestration

### Flow
```
User message
  → Prepend employee context (if employee_id provided)
  → LLM + 8 MCP tools
  → Agentic loop (max 8 rounds):
      IF tool_calls in response:
        execute each via MCP client
        append tool result to conversation
        continue loop
      ELSE:
        extract final text response → break
  → Build citations from tool results
  → Return {answer, citations, tool_trace}
```

### Two Demo Agentic Tasks

**Task 1: PTO Request Guidance (EMP003 — Carol)**
> "I'd like to take 3 days of PTO next week. Can you check my balance?"

Expected MCP call sequence:
1. `lookup_employee_profile(employee_id="EMP003")` → Carol Lee, Product Manager, hybrid-eligible
2. `check_pto_balance(employee_id="EMP003")` → 8.1 days available
3. `search_policy_documents(query="PTO request approval process advance notice")` → POL-001 sections
4. `get_policy_section(doc_id="pto_policy", section_query="manager approval")` → approval rules
5. `create_mock_hr_ticket(...)` with `requester_confirmed=False` → preview shown to user

**Task 2: Remote Work Eligibility (EMP001 — Alice, 6 weeks NY)**
> "Can I work from New York for 6 weeks?"

Expected MCP call sequence:
1. `lookup_employee_profile(employee_id="EMP001")` → Alice Johnson, fully_remote_eligible, CA
2. `search_policy_documents(query="remote work out of state approval requirements")` → POL-002
3. `search_policy_documents(query="data security VPN remote work requirements")` → POL-006
4. `check_policy_compliance(situation="employee working remotely from NY for 6 weeks")` → compliance check
5. `draft_hr_email(...)` with `requester_confirmed=False` → draft shown for confirmation

### Failure Handling
- MCP server unavailable: catches exception, returns "HR tools temporarily unavailable" message
- Employee ID not found: tool returns `found: false` with error message → LLM relays to user
- Insufficient policy evidence: LLM guided by system prompt to escalate to HR

---

## Safety Guardrails

| Guardrail | Implementation |
|---|---|
| Irreversible action gate | `requester_confirmed` parameter; `False` by default → shows preview only |
| Out-of-scope decline | System prompt: explicit instruction to decline non-HR questions |
| Policy fact vs recommendation | System prompt: distinguish language required |
| No hidden chain-of-thought | `tool_trace` in response is operational (tool names + args + result summary only) |
| Action safety | `draft_hr_email` always sets `is_mock: true` and `sent: false` |

---

## Deployment Architecture

| Component | Technology | Location |
|---|---|---|
| Web app + API | FastAPI + uvicorn | Railway Docker (port 7860) |
| Agent orchestrator | Python + httpx | Same process |
| MCP client | mcp Python SDK (stdio) | Same process |
| MCP server | mcp Python SDK (subprocess) | Same process (spawned) |
| RAG index | ChromaDB + fastembed | Built into Docker image (RUN python rag/ingest.py) |
| Mock data | JSON files | In Docker image |
| LLM | gemini-flash-latest via Google AI API | Google cloud |
| Embedding | BAAI/bge-small-en-v1.5 via fastembed | Downloaded at Docker build time |

**Cold-start behavior**: Railway containers stay warm as long as the service is active. First request after a fresh deploy may take 10–30 seconds for ChromaDB and fastembed model loading.

---

## Evaluation

### Question Set (25 questions)
| Category | Count |
|---|---|
| Simple policy Q&A | 8 |
| Multi-document questions | 4 |
| Tool-requiring tasks | 5 |
| Ambiguous requests | 4 |
| Out-of-scope | 4 |

### Metrics Reported
| Metric | Definition |
|---|---|
| Groundedness rate | % of policy questions with citations in response |
| Citation accuracy | % where cited document matches expected source |
| Avg partial match | Token overlap between answer and gold answer |
| Tool selection accuracy | % of tool tasks where expected tools were called |
| Workflow completion rate | % of tool tasks completed end-to-end |
| Escalation accuracy | % of ambiguous/OOS questions handled correctly |
| Action safety rate | % of responses where irreversible actions were gated |
| Latency p50/p95 | Measured over all 25 questions (warm Railway deployment) |

### Ablation Study
Run with `python evaluation/run_eval.py --k 5 --k-ablation 3`.
Compares retrieval k=5 vs k=3 on groundedness and citation accuracy.

### Results (k=5, run 2026-08-03)

| Metric | Score |
|---|---|
| Groundedness rate | **92%** (23/25) |
| Citation accuracy | **92%** (23/25) |
| Avg partial match | **46%** |
| Tool selection accuracy | **80%** (4/5 tool tasks) |
| Workflow completion rate | **60%** (3/5 tool tasks end-to-end) |
| Escalation accuracy | **75%** (6/8 ambiguous + out-of-scope) |
| Action safety rate | **100%** |
| Latency p50 / p95 | **6 229 ms / 13 415 ms** (warm Railway deploy) |

**Notes on missed questions:**
- Q11 (new hire PTO): grounded=False — answer came primarily from a tool call rather than a retrieved policy chunk, which the grader treated as ungrounded; answer content was factually correct.
- Q15 (benefits lookup): grounded=False — same pattern: benefits data came from the `lookup_benefits_status` mock tool; no RAG citation was expected for a structured-data query.
- Q17 (ticket creation): tool_ok=False — model provided the ticket preview but did not call `create_mock_hr_ticket`; it returned a draft description instead and asked for confirmation.
- Q18, Q20 (ambiguous): grounded=False — model jumped directly to policy guidance rather than asking a clarifying question first; escalation_accuracy penalized.

### Ablation Study (k=3 vs k=5)

| Metric | k=5 | k=3 | Delta |
|---|---|---|---|
| Groundedness | 92% | 75% | −17 pp |
| Citation accuracy | 92% | 83% | −9 pp |
| Avg partial match | 46% | 37% | −9 pp |
| Action safety | 100% | 100% | 0 |

**Interpretation:** k=5 consistently outperforms k=3, especially on groundedness (−17 pp). Retrieving fewer chunks means the model more frequently lacks the policy evidence it needs to ground its answer, causing it to either hallucinate or hedge without citation.

**Note on k=3 run reliability:** The ablation ran immediately after the k=5 run. Multiple questions (Q07, Q10, Q12, Q13, Q16, Q24) received HTTP 503 responses from the Gemini API during this second run — not code failures, but Gemini rate-limit/capacity errors. These caused the k=3 workflow completion and escalation metrics to be artificially low (0% workflow completion). The groundedness and citation accuracy figures above reflect only the questions that received valid responses.

---

## Design Decision Justifications

| Decision | Rationale |
|---|---|
| **fastembed** over sentence-transformers | No PyTorch dependency; 33MB vs ~1GB; free-tier compatible |
| **ChromaDB** over FAISS | Persistent, metadata-rich, built-in query filtering |
| **stdio MCP transport** | Simplest for single-service deployment; no extra port |
| **Gemini Flash (gemini-flash-latest)** | OpenAI-compatible API endpoint; routes to newest Flash model; httpx used directly to preserve `thought_signature` round-trip required by Gemini thinking models |
| **Railway** over HF Spaces | Docker SDK on HF Spaces requires paid plan; Railway offers free starter credit |
| **heading-aware chunking** | Policy documents have strong heading structure; reduces cross-section noise |
| **Confirmation gate** | Required by project spec; prevents accidental irreversible actions |
