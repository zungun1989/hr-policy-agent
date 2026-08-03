"""
Agent orchestrator: connects to the MCP server (stdio), calls Gemini LLM with MCP tools,
handles multi-step HR workflows, and returns cited, traced responses.

The MCP subprocess is started ONCE at app startup via startup_mcp() and kept alive
for the lifetime of the container, avoiding per-request subprocess overhead.
"""
import asyncio
import json
import os
import sys

from google import genai
from google.genai import types
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from agent.prompts import SYSTEM_PROMPT

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-flash-latest"
MAX_TOKENS = 1024

MCP_SERVER_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "mcp_server", "server.py"
)

# Persistent MCP connection — initialized at startup, reused for every request
_session: ClientSession | None = None
_mcp_tools: list = []
_stdio_cm = None


def _tool_to_fn_decl(tool) -> types.FunctionDeclaration:
    schema = {k: v for k, v in tool.inputSchema.items() if k != "additionalProperties"}
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=schema,
    )


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
    """Start the MCP subprocess once at app startup. Called by FastAPI lifespan."""
    global _session, _mcp_tools, _stdio_cm

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[MCP_SERVER_SCRIPT],
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
        _mcp_tools = tools_response.tools
        print(
            f"[MCP] Started — {len(_mcp_tools)} tools available",
            file=sys.stderr, flush=True,
        )
    except Exception as e:
        err = e.exceptions[0] if hasattr(e, "exceptions") else e
        print(f"[MCP] Startup failed: {type(err).__name__}: {err}", file=sys.stderr, flush=True)
        _session = None
        _mcp_tools = []


async def shutdown_mcp() -> None:
    """Tear down the MCP subprocess. Called by FastAPI lifespan on shutdown."""
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


async def _run_agent(user_message: str) -> dict:
    global _session, _mcp_tools

    if _session is None:
        return {
            "answer": (
                "The HR tools are temporarily unavailable. "
                "Please contact HR directly at hr@acmecorp.com."
            ),
            "citations": [],
            "tool_trace": [],
            "error": "MCP session not initialized",
        }

    client = genai.Client(api_key=GEMINI_API_KEY)
    tool_trace: list[dict] = []
    error_message: str | None = None
    final_text = ""

    try:
        fn_decls = [_tool_to_fn_decl(t) for t in _mcp_tools]
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(function_declarations=fn_decls)],
            max_output_tokens=MAX_TOKENS,
        )

        contents: list = [
            types.Content(role="user", parts=[types.Part(text=user_message)])
        ]

        for _iteration in range(8):
            for _retry in range(6):
                try:
                    _snap = list(contents)
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=MODEL,
                            contents=_snap,
                            config=config,
                        ),
                    )
                    break
                except Exception as _re:
                    import re as _re_mod
                    _re_err = _re.exceptions[0] if hasattr(_re, "exceptions") else _re
                    _err_str = str(_re_err)
                    if "429" not in _err_str and "RESOURCE_EXHAUSTED" not in _err_str:
                        raise
                    _match = _re_mod.search(r"retry in (\d+(?:\.\d+)?)s", _err_str)
                    _wait = float(_match.group(1)) if _match else (13 * (2 ** _retry))
                    _wait = min(_wait, 13)
                    if _retry < 5:
                        print(f"[LLM] 429 — waiting {_wait:.0f}s before retry", file=sys.stderr, flush=True)
                        await asyncio.sleep(_wait)
                    else:
                        raise

            model_content = response.candidates[0].content

            function_call_parts = [
                p for p in (model_content.parts or [])
                if p.function_call is not None
            ]

            if not function_call_parts:
                text_parts = [p for p in (model_content.parts or []) if p.text]
                final_text = "".join(p.text for p in text_parts)
                break

            # Append the model's full Content object — the SDK carries thought_signatures
            # automatically so the next request passes validation without any manual handling.
            contents.append(model_content)

            function_response_parts = []
            for part in function_call_parts:
                fc = part.function_call
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                try:
                    mcp_result = await _session.call_tool(tool_name, tool_args)
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
                    "arguments": tool_args,
                    "result_summary": _summarize_result(raw_result),
                    "raw_result": raw_result,
                    "is_error": is_error,
                })

                function_response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response=raw_result,
                        )
                    )
                )

            contents.append(
                types.Content(role="user", parts=function_response_parts)
            )

        else:
            final_text = (
                "I was unable to complete this request within the allowed steps."
            )

    except Exception as e:
        err = e.exceptions[0] if hasattr(e, "exceptions") else e
        error_message = f"{type(err).__name__}: {err}"
        final_text = (
            "I encountered an error connecting to the HR tools. "
            "Please contact HR directly at hr@acmecorp.com. "
            f"(Technical detail: {error_message})"
        )

    citations = _build_citations(tool_trace)
    public_trace = [
        {k: v for k, v in t.items() if k != "raw_result"}
        for t in tool_trace
    ]

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
    """Async entry point for the FastAPI app."""
    return await _run_agent(user_message)
