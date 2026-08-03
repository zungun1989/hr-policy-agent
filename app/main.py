"""
Acme Corp HR Policy Agent — FastAPI application
Endpoints: GET /, GET /health, POST /chat, POST /demo/task1, POST /demo/task2
"""
import os
import sys
import time
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from agent.orchestrator import run_agent, startup_mcp, shutdown_mcp
from rag.retriever import is_index_loaded, get_collection_count


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_mcp()
    yield
    await shutdown_mcp()


app = FastAPI(
    title="Acme Corp HR Policy Agent",
    description="Agentic HR assistant with RAG + MCP tool integration",
    version="1.0.0",
    lifespan=lifespan,
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    employee_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict]
    tool_trace: list[dict]
    latency_ms: int
    error: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>Acme Corp HR Policy Agent</h1><p>Chat UI not found.</p>")


@app.get("/health")
async def health():
    try:
        index_ok = is_index_loaded()
        chunk_count = get_collection_count() if index_ok else 0
    except Exception as e:
        index_ok = False
        chunk_count = 0

    from agent.orchestrator import _session
    mcp_status = "connected" if _session is not None else "not_connected"

    return {
        "status": "ok",
        "rag_index": "loaded" if index_ok else "not_loaded",
        "rag_chunk_count": chunk_count,
        "mcp": mcp_status,
        "model": "gemini/gemini-2.0-flash",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Optionally prepend employee context
    user_message = req.message
    if req.employee_id:
        user_message = f"[My employee ID is {req.employee_id}]\n\n{req.message}"

    t0 = time.perf_counter()
    try:
        result = await run_agent(user_message)
    except Exception as e:
        result = {
            "answer": f"An unexpected error occurred: {e}",
            "citations": [],
            "tool_trace": [],
            "error": str(e),
        }
    latency_ms = int((time.perf_counter() - t0) * 1000)

    return ChatResponse(
        answer=result.get("answer", ""),
        citations=result.get("citations", []),
        tool_trace=result.get("tool_trace", []),
        latency_ms=latency_ms,
        error=result.get("error"),
    )


@app.post("/demo/task1", response_model=ChatResponse)
async def demo_task1():
    """
    Demo Task 1: PTO Request Guidance
    Employee EMP003 (Carol Lee) asks about taking 3 days PTO next week.
    Expected tool calls: lookup_employee_profile → check_pto_balance →
      search_policy_documents (PTO approval) → get_policy_section → create_mock_hr_ticket (preview)
    """
    req = ChatRequest(
        message=(
            "Hi! I'm Carol and my employee ID is EMP003. "
            "I'd like to take 3 days of PTO next week (Monday to Wednesday). "
            "Can you check if I have enough PTO balance and walk me through what I need to do to request it?"
        ),
        employee_id="EMP003",
    )
    return await chat(req)


@app.post("/demo/task2", response_model=ChatResponse)
async def demo_task2():
    """
    Demo Task 2: Remote Work Eligibility (Out-of-State, 6 weeks)
    Employee EMP001 (Alice Johnson) asks about working from New York for 6 weeks.
    Expected tool calls: lookup_employee_profile → search_policy_documents (remote work out-of-state) →
      search_policy_documents (security requirements) → check_policy_compliance → draft_hr_email (preview)
    """
    req = ChatRequest(
        message=(
            "Hello, I'm Alice Johnson, employee ID EMP001. "
            "I'd like to work remotely from New York for 6 weeks this summer "
            "(July 7 to August 15). My primary work state is California. "
            "Am I eligible to do this? What approvals do I need, and are there any security requirements?"
        ),
        employee_id="EMP001",
    )
    return await chat(req)
