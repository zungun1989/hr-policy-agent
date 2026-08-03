"""
Agent orchestrator: connects to the MCP server (stdio), calls Gemini via httpx,
handles multi-step HR workflows, and returns cited, traced responses.
"""
import asyncio
import json
import os
import re
import sys

import httpx
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from agent.prompts import SYSTEM_PROMPT

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-flash-latest"
MAX_TOKENS = 1024
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

_session: ClientSession | None = None
_groq_tools: list[dict] = []
_stdio_cm = None


def _tool_to_openai(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema,
        },
    }


def _build_citations(tool_results: list[dict]) -> list[dict]:
    citations = []
    seen = set()
    for r in tool_results:
        raw = r.get("raw_result", {})
        for key in ("results", "relevant_policies", "sections"):
            for item in raw.get(key, []):
                cit_key = (item.get("doc_id", ""), item.get("section", ""))
                if cit_key not in seen:
                    seen.add(cit_key)
                    citations.append({
                        "doc_id": item.get("doc_id", ""),
                        "title": item.get("title", ""),
                        "section": item.get("section", ""),
                        "source_snippet": item.get("source_snippet", "")[:300],
                    })
    return citations


async def startup_mcp() -> None:
    global _session, _groq_tools, _stdio_cm
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(os.path.dirname(__file__), "..", "mcp_server", "server.py")],
        env={**os.environ},
    )
    try:
        _stdio_cm = stdio_client(server_params)
        read, write = await _stdio_cm.__aenter__()
        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()
        tools_response = await session.list_tools()
        _session = session
        _groq_tools = [_tool_to_openai(t) for t in tools_response.tools]
        print(f"[MCP] Started — {len(_groq_tools)} tools available", file=sys.stderr, flush=True)
    except Exception as e:
        err = e.exceptions[0] if hasattr(e, "exceptions") else e
        print(f"[MCP] Startup failed: {type(err).__name__}: {err}", file=sys.stderr, flush=True)
        _session = None
        _groq_tools = []


async def shutdown_mcp() -> None:
    global _session, _stdio_cm
    if _session:
        try:
            await _session.__aexit__(None, None, None)
        except Exception:
            pass
        _session = None
    if _stdio_cm:
        try:
            await _stdio_cm.__aexit__(None, None, None)
        except Exception:
            pass
        _stdio_cm = None


async def _call_llm(messages: list[dict]) -> dict:
    """POST directly to Gemini OpenAI-compat endpoint via httpx (preserves all fields)."""
    async with httpx.AsyncClient(timeout=120) as http:
        resp = await http.post(
            _GEMINI_URL,
            headers={"Authorization": f"Bearer {GEMINI_API_KEY}"},
            json={
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "tools": _groq_tools,
                "messages": messages,
            },
        )
        if resp.status_code == 429:
            raise httpx.HTTPStatusError("429", request=resp.request, response=resp)
        resp.raise_for_status()
        return resp.json()


async def _run_agent(user_message: str) -> dict:
    global _session, _groq_tools

    if _session is None:
        return {
            "answer": "The HR tools are temporarily unavailable. Please contact HR directly at hr@acmecorp.com.",
            "citations": [],
            "tool_trace": [],
            "error": "MCP session not initialized",
        }

    tool_trace: list[dict] = []
    error_message: str | None = None
    final_text = ""

    try:
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        for _iteration in range(8):
            for _retry in range(6):
                try:
                    response_json = await _call_llm(messages)
                    break
                except Exception as _re:
                    _re_err = _re.exceptions[0] if hasattr(_re, "exceptions") else _re
                    _err_str = str(_re_err)
                    if "429" not in _err_str and "RESOURCE_EXHAUSTED" not in _err_str:
                        raise
                    _match = re.search(r"retry in (\d+(?:\.\d+)?)s", _err_str)
                    _wait = float(_match.group(1)) if _match else min(13 * (2 ** _retry), 13)
                    if _retry < 5:
                        print(f"[LLM] 429 — waiting {_wait:.0f}s", file=sys.stderr, flush=True)
                        await asyncio.sleep(_wait)
                    else:
                        raise

            msg = response_json["choices"][0]["message"]
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                final_text = msg.get("content") or ""
                break

            # Build assistant message preserving thought_signature from raw response.
            # httpx returns Gemini's raw JSON, so extra_content.google.thought_signature
            # is present. We re-emit it as a flat "thought_signature" field which is
            # what the Gemini API expects on the next request.
            assistant_tool_calls = []
            for tc in tool_calls:
                ec = tc.get("extra_content", {}) or {}
                sig = ec.get("google", {}).get("thought_signature", "skip_thought_signature_validator")
                assistant_tool_calls.append({
                    "id": tc["id"],
                    "type": tc["type"],
                    "function": tc["function"],
                    "thought_signature": sig,
                })

            messages.append({
                "role": "assistant",
                "content": msg.get("content"),
                "tool_calls": assistant_tool_calls,
            })

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    tool_input = json.loads(tc["function"]["arguments"])
                except Exception:
                    tool_input = {}

                try:
                    mcp_result = await _session.call_tool(tool_name, tool_input)
                    raw_result = (
                        json.loads(mcp_result.content[0].text)
                        if mcp_result.content
                        else {}
                    )
                    is_error = False
                except Exception as exc:
                    raw_result = {"error": str(exc)}
                    is_error = True

                tool_trace.append({
                    "tool": tool_name,
                    "arguments": tool_input,
                    "result_summary": _summarize_result(raw_result),
                    "raw_result": raw_result,
                    "is_error": is_error,
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(raw_result),
                })

        else:
            final_text = msg.get("content") or "Unable to complete this request within the allowed steps."

    except Exception as e:
        err = e.exceptions[0] if hasattr(e, "exceptions") else e
        error_message = f"{type(err).__name__}: {err}"
        final_text = (
            "I encountered an error connecting to the HR tools. "
            "Please contact HR directly at hr@acmecorp.com. "
            f"(Technical detail: {error_message})"
        )

    citations = _build_citations(tool_trace)
    public_trace = [{k: v for k, v in t.items() if k != "raw_result"} for t in tool_trace]

    return {
        "answer": final_text,
        "citations": citations,
        "tool_trace": public_trace,
        "error": error_message,
    }


def _summarize_result(result: dict) -> str:
    if "error" in result:
        return f"ERROR: {result['error']}"
    if result.get("found") is False:
        return result.get("error", "Not found")
    if "total_results" in result:
        return f"{result['total_results']} policy chunks retrieved"
    if "employee" in result:
        e = result["employee"]
        return f"Employee: {e.get('name')} ({e.get('role')}, {e.get('department')})"
    if "pto_balance" in result:
        b = result["pto_balance"]
        return f"PTO: {b.get('available_days', 0):.1f} days available"
    if "benefits" in result:
        b = result["benefits"]
        return f"Benefits: {b.get('medical_plan')} plan, 401k={'yes' if b.get('retirement_401k_enrolled') else 'no'}"
    if "ticket" in result:
        return f"Ticket created: {result['ticket']['ticket_id']}"
    if "draft" in result:
        return f"Email draft prepared to {result['draft']['to']}"
    if result.get("requires_confirmation"):
        return "Awaiting user confirmation"
    if "sections" in result:
        return f"{len(result['sections'])} sections retrieved"
    return "OK"


async def run_agent(user_message: str) -> dict:
    return await _run_agent(user_message)
