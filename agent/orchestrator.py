"""
Agent orchestrator: connects to the MCP server (stdio), calls Claude with MCP tools,
handles multi-step HR workflows, and returns cited, traced responses.
"""
import asyncio
import json
import os
import sys
from typing import Any

import anthropic
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from agent.prompts import SYSTEM_PROMPT

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 2048

MCP_SERVER_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "mcp", "server.py"
)


def _tool_to_anthropic(tool) -> dict:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.inputSchema,
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


async def _run_agent(user_message: str) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    tool_trace: list[dict] = []
    error_message: str | None = None

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[MCP_SERVER_SCRIPT],
        env={
            **os.environ,
            "PYTHONPATH": os.path.join(os.path.dirname(__file__), ".."),
        },
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Discover tools from MCP server
                tools_response = await session.list_tools()
                anthropic_tools = [_tool_to_anthropic(t) for t in tools_response.tools]

                messages = [{"role": "user", "content": user_message}]

                # Agentic loop: Claude decides which tools to call
                for _iteration in range(8):  # max 8 tool-call rounds
                    response = client.messages.create(
                        model=MODEL,
                        max_tokens=MAX_TOKENS,
                        system=SYSTEM_PROMPT,
                        tools=anthropic_tools,
                        messages=messages,
                    )

                    # Collect text and tool_use blocks
                    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                    text_blocks = [b for b in response.content if b.type == "text"]

                    if not tool_use_blocks:
                        # No more tool calls → final response
                        final_text = " ".join(b.text for b in text_blocks)
                        break

                    # Execute each tool call via MCP
                    tool_results_for_message = []
                    for block in tool_use_blocks:
                        tool_name = block.name
                        tool_input = block.input

                        try:
                            mcp_result = await session.call_tool(tool_name, tool_input)
                            raw_result = json.loads(mcp_result.content[0].text) if mcp_result.content else {}
                            is_error = False
                        except Exception as exc:
                            raw_result = {"error": str(exc)}
                            is_error = True

                        trace_entry = {
                            "tool": tool_name,
                            "arguments": tool_input,
                            "result_summary": _summarize_result(raw_result),
                            "raw_result": raw_result,
                            "is_error": is_error,
                        }
                        tool_trace.append(trace_entry)

                        tool_results_for_message.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(raw_result),
                        })

                    # Add assistant turn and tool results to conversation
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results_for_message})

                else:
                    # Safety: if we hit max iterations, take last text output
                    final_text = " ".join(
                        b.text for b in response.content if hasattr(b, "text")
                    ) or "I was unable to complete this request within the allowed steps."

    except Exception as e:
        error_message = str(e)
        final_text = (
            "I encountered an error connecting to the HR tools. "
            "Please contact HR directly at hr@acmecorp.com. "
            f"(Technical detail: {error_message})"
        )

    citations = _build_citations(tool_trace)
    # Strip raw_result from public trace (keep structured summary only)
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


def run_agent(user_message: str) -> dict:
    """Synchronous entry point for the FastAPI app."""
    return asyncio.run(_run_agent(user_message))
