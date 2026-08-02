"""
Acme Corp HR Policy MCP Server
Transport: stdio (called as subprocess by the agent orchestrator)

Exposes 8 tools:
  RAG-based: search_policy_documents, get_policy_section, check_policy_compliance
  Mock data: lookup_employee_profile, check_pto_balance, lookup_benefits_status
  Mock actions: create_mock_hr_ticket, draft_hr_email
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent

from mcp.tools.rag_tools import (
    search_policy_documents,
    get_policy_section,
    check_policy_compliance,
)
from mcp.tools.hr_tools import (
    lookup_employee_profile,
    check_pto_balance,
    lookup_benefits_status,
    create_mock_hr_ticket,
    draft_hr_email,
)

app = Server("acme-hr-policy-server")

TOOLS: list[Tool] = [
    Tool(
        name="search_policy_documents",
        description=(
            "Search Acme Corp's internal policy corpus for relevant policy information. "
            "Use this for any question about company policies, procedures, or guidelines. "
            "Returns top-k chunks with citations (document title, section, source snippet)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query describing what policy information is needed.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 10).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_policy_section",
        description=(
            "Retrieve specific sections from a named policy document. "
            "Use when you know the document and need targeted information. "
            "doc_id examples: pto_policy, remote_work_policy, expense_policy, "
            "benefits_policy, onboarding_policy, data_security_policy, "
            "workplace_conduct, leave_policy, equipment_policy, travel_policy."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "The policy document ID (e.g. 'pto_policy', 'remote_work_policy').",
                },
                "section_query": {
                    "type": "string",
                    "description": "Description of the section to retrieve (e.g. 'manager approval process').",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of section chunks to return (default 3).",
                    "default": 3,
                },
            },
            "required": ["doc_id", "section_query"],
        },
    ),
    Tool(
        name="check_policy_compliance",
        description=(
            "Check whether a described employee situation is compliant with Acme Corp policies. "
            "Retrieves relevant policy sections and returns them for compliance determination. "
            "Use for multi-policy compliance checks (e.g., remote work + security requirements)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "situation": {
                    "type": "string",
                    "description": "Description of the situation to check for policy compliance.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of policy chunks to retrieve (default 5).",
                    "default": 5,
                },
            },
            "required": ["situation"],
        },
    ),
    Tool(
        name="lookup_employee_profile",
        description=(
            "Look up an employee's profile from the mock HR database. "
            "Returns role, department, employment type, remote classification, "
            "primary state, office location, manager, and hire date. "
            "Required before any employee-specific workflow."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "Employee ID (e.g. 'EMP001', 'EMP005'). Case-insensitive.",
                },
            },
            "required": ["employee_id"],
        },
    ),
    Tool(
        name="check_pto_balance",
        description=(
            "Check an employee's current PTO balance including available hours and days, "
            "YTD accrual, YTD usage, and carryover. "
            "Use to determine if an employee has sufficient PTO for a requested leave."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "Employee ID (e.g. 'EMP001'). Case-insensitive.",
                },
            },
            "required": ["employee_id"],
        },
    ),
    Tool(
        name="lookup_benefits_status",
        description=(
            "Look up an employee's current benefits elections including medical plan, "
            "dental, vision, 401(k) enrollment and contribution rate, HSA/FSA status, "
            "and wellness stipend balance."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "Employee ID (e.g. 'EMP001'). Case-insensitive.",
                },
            },
            "required": ["employee_id"],
        },
    ),
    Tool(
        name="create_mock_hr_ticket",
        description=(
            "Create a mock HR ticket for an employee. "
            "IMPORTANT: requester_confirmed MUST be True for the ticket to be created. "
            "If False, returns a preview for user confirmation. "
            "ticket_type options: pto_request, remote_work_request, hr_case, benefits_inquiry, general."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID."},
                "ticket_type": {
                    "type": "string",
                    "enum": ["pto_request", "remote_work_request", "hr_case", "benefits_inquiry", "general"],
                    "description": "Type of HR ticket.",
                },
                "subject": {"type": "string", "description": "Brief ticket subject line."},
                "description": {"type": "string", "description": "Full description of the request."},
                "requester_confirmed": {
                    "type": "boolean",
                    "description": "Set to true only after explicit user confirmation to proceed.",
                    "default": False,
                },
            },
            "required": ["employee_id", "ticket_type", "subject", "description"],
        },
    ),
    Tool(
        name="draft_hr_email",
        description=(
            "Draft a mock HR-related email (to manager, HR, Finance, or VP). "
            "IMPORTANT: requester_confirmed MUST be True to finalize the draft. "
            "If False, shows preview only. No real email is ever sent — this is always a mock action."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "to_role": {
                    "type": "string",
                    "enum": ["manager", "hr", "finance", "vp"],
                    "description": "Recipient role.",
                },
                "subject": {"type": "string", "description": "Email subject line."},
                "body_context": {
                    "type": "string",
                    "description": "The main body content of the email (will be formatted).",
                },
                "employee_id": {"type": "string", "description": "Employee ID of the sender."},
                "requester_confirmed": {
                    "type": "boolean",
                    "description": "Set to true only after explicit user confirmation.",
                    "default": False,
                },
            },
            "required": ["to_role", "subject", "body_context", "employee_id"],
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    import json as _json

    dispatch = {
        "search_policy_documents": lambda a: search_policy_documents(**a),
        "get_policy_section": lambda a: get_policy_section(**a),
        "check_policy_compliance": lambda a: check_policy_compliance(**a),
        "lookup_employee_profile": lambda a: lookup_employee_profile(**a),
        "check_pto_balance": lambda a: check_pto_balance(**a),
        "lookup_benefits_status": lambda a: lookup_benefits_status(**a),
        "create_mock_hr_ticket": lambda a: create_mock_hr_ticket(**a),
        "draft_hr_email": lambda a: draft_hr_email(**a),
    }

    handler = dispatch.get(name)
    if not handler:
        result = {"error": f"Unknown tool: {name}"}
    else:
        try:
            result = handler(arguments)
        except Exception as e:
            result = {"error": f"Tool execution error: {e}"}

    return [TextContent(type="text", text=_json.dumps(result, indent=2))]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
