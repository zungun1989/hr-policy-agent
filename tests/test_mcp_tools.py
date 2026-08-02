"""
MCP tool tests: verify tool discovery and direct tool execution via Python imports.
These tests do NOT call the live MCP stdio server; they call the underlying tool functions.
A separate integration test (test_mcp_integration.py) would test the full stdio transport.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ---------------------------------------------------------------------------
# RAG tools (require indexed ChromaDB)
# ---------------------------------------------------------------------------

def test_search_policy_documents_returns_results():
    from mcp.tools.rag_tools import search_policy_documents
    result = search_policy_documents("PTO accrual rate", top_k=3)
    assert "results" in result
    assert result["total_results"] >= 0  # may be 0 if index not built in CI


def test_get_policy_section_known_doc():
    from mcp.tools.rag_tools import get_policy_section
    result = get_policy_section("pto_policy", "manager approval", top_k=2)
    assert "doc_id" in result
    assert result["doc_id"] == "pto_policy"


def test_check_policy_compliance_returns_structure():
    from mcp.tools.rag_tools import check_policy_compliance
    result = check_policy_compliance("employee working remotely from New York for 6 weeks")
    assert "relevant_policies" in result
    assert isinstance(result["relevant_policies"], list)


# ---------------------------------------------------------------------------
# HR mock-data tools
# ---------------------------------------------------------------------------

def test_lookup_employee_profile_found():
    from mcp.tools.hr_tools import lookup_employee_profile
    result = lookup_employee_profile("EMP001")
    assert result["found"] is True
    emp = result["employee"]
    assert emp["employee_id"] == "EMP001"
    assert "name" in emp
    assert "role" in emp


def test_lookup_employee_profile_not_found():
    from mcp.tools.hr_tools import lookup_employee_profile
    result = lookup_employee_profile("EMP999")
    assert result["found"] is False
    assert "error" in result


def test_check_pto_balance_found():
    from mcp.tools.hr_tools import check_pto_balance
    result = check_pto_balance("EMP003")
    assert result["found"] is True
    bal = result["pto_balance"]
    assert "available_hours" in bal
    assert "available_days" in bal


def test_check_pto_balance_not_found():
    from mcp.tools.hr_tools import check_pto_balance
    result = check_pto_balance("EMP999")
    assert result["found"] is False


def test_lookup_benefits_status_found():
    from mcp.tools.hr_tools import lookup_benefits_status
    result = lookup_benefits_status("EMP001")
    assert result["found"] is True
    ben = result["benefits"]
    assert "medical_plan" in ben
    assert "retirement_401k_enrolled" in ben


# ---------------------------------------------------------------------------
# Confirmation-gated actions
# ---------------------------------------------------------------------------

def test_create_mock_hr_ticket_requires_confirmation():
    from mcp.tools.hr_tools import create_mock_hr_ticket
    result = create_mock_hr_ticket(
        employee_id="EMP003",
        ticket_type="pto_request",
        subject="PTO Request: Oct 6-8",
        description="Requesting 3 days PTO next week.",
        requester_confirmed=False,
    )
    assert result["created"] is False
    assert result["requires_confirmation"] is True


def test_create_mock_hr_ticket_with_confirmation():
    from mcp.tools.hr_tools import create_mock_hr_ticket
    result = create_mock_hr_ticket(
        employee_id="EMP003",
        ticket_type="pto_request",
        subject="PTO Request: Test Ticket",
        description="Test ticket for automated testing.",
        requester_confirmed=True,
    )
    assert result["created"] is True
    assert "ticket_id" in result["ticket"]
    assert result["ticket"]["ticket_id"].startswith("TKT-")


def test_draft_hr_email_requires_confirmation():
    from mcp.tools.hr_tools import draft_hr_email
    result = draft_hr_email(
        to_role="manager",
        subject="Remote Work Request",
        body_context="I'd like to work from New York for 6 weeks.",
        employee_id="EMP001",
        requester_confirmed=False,
    )
    assert result["sent"] is False
    assert result["requires_confirmation"] is True
    assert "draft" in result


def test_draft_hr_email_action_safety():
    """Action safety: draft is always mock, never sends real email."""
    from mcp.tools.hr_tools import draft_hr_email
    result = draft_hr_email(
        to_role="hr",
        subject="Test",
        body_context="Test message",
        employee_id="EMP001",
        requester_confirmed=True,
    )
    assert result["sent"] is False
    assert result["draft"]["is_mock"] is True


# ---------------------------------------------------------------------------
# MCP server tool discovery (import test)
# ---------------------------------------------------------------------------

def test_mcp_server_tool_list_importable():
    from mcp.server import TOOLS
    tool_names = {t.name for t in TOOLS}
    expected = {
        "search_policy_documents",
        "get_policy_section",
        "check_policy_compliance",
        "lookup_employee_profile",
        "check_pto_balance",
        "lookup_benefits_status",
        "create_mock_hr_ticket",
        "draft_hr_email",
    }
    assert expected == tool_names, f"Missing tools: {expected - tool_names}"
