"""
HR mock-data MCP tools: employee lookup, PTO balance, benefits, ticket creation, email drafting.
"""
import json
import os
import uuid
from datetime import datetime

MOCK_DATA_PATH = os.environ.get("MOCK_DATA_PATH", "./mock_data")


def _load(filename: str) -> dict:
    path = os.path.join(MOCK_DATA_PATH, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(filename: str, data: dict) -> None:
    path = os.path.join(MOCK_DATA_PATH, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def lookup_employee_profile(employee_id: str) -> dict:
    """
    Retrieve an employee's profile from mock HR data.
    employee_id format: EMP001, EMP002, ... EMP010
    """
    try:
        data = _load("employees.json")
        employees = {e["employee_id"]: e for e in data["employees"]}
        emp = employees.get(employee_id.upper())
        if not emp:
            return {
                "found": False,
                "employee_id": employee_id,
                "error": f"Employee {employee_id} not found in the system.",
            }
        # Look up manager name
        if emp.get("manager_id") and emp["manager_id"] in employees:
            emp = dict(emp)
            emp["manager_name"] = employees[emp["manager_id"]]["name"]
        return {"found": True, "employee": emp}
    except Exception as e:
        return {"found": False, "error": str(e)}


def check_pto_balance(employee_id: str) -> dict:
    """
    Check an employee's current PTO balance (available hours and days).
    employee_id format: EMP001, EMP002, ... EMP010
    """
    try:
        data = _load("pto_balances.json")
        balances = {b["employee_id"]: b for b in data["pto_balances"]}
        bal = balances.get(employee_id.upper())
        if not bal:
            return {
                "found": False,
                "employee_id": employee_id,
                "error": f"PTO balance for {employee_id} not found.",
            }
        return {"found": True, "pto_balance": bal}
    except Exception as e:
        return {"found": False, "error": str(e)}


def lookup_benefits_status(employee_id: str) -> dict:
    """
    Look up an employee's current benefits elections and enrollment status.
    employee_id format: EMP001, EMP002, ... EMP010
    """
    try:
        data = _load("benefits.json")
        benefits = {b["employee_id"]: b for b in data["benefits_elections"]}
        ben = benefits.get(employee_id.upper())
        if not ben:
            return {
                "found": False,
                "employee_id": employee_id,
                "error": f"Benefits record for {employee_id} not found.",
            }
        return {"found": True, "benefits": ben}
    except Exception as e:
        return {"found": False, "error": str(e)}


def create_mock_hr_ticket(
    employee_id: str,
    ticket_type: str,
    subject: str,
    description: str,
    requester_confirmed: bool = False,
) -> dict:
    """
    Create a mock HR ticket after explicit user confirmation.
    ticket_type: 'pto_request', 'remote_work_request', 'hr_case', 'benefits_inquiry', 'general'
    requester_confirmed: MUST be True; if False, ticket is not created.
    """
    if not requester_confirmed:
        return {
            "created": False,
            "requires_confirmation": True,
            "message": (
                "This action will create an HR ticket. "
                "Please confirm you want to proceed before this ticket is submitted."
            ),
            "preview": {
                "employee_id": employee_id,
                "ticket_type": ticket_type,
                "subject": subject,
                "description": description,
            },
        }

    try:
        data = _load("hr_tickets.json")
        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        ticket = {
            "ticket_id": ticket_id,
            "employee_id": employee_id.upper(),
            "ticket_type": ticket_type,
            "subject": subject,
            "description": description,
            "status": "open",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        data["hr_tickets"].append(ticket)
        _save("hr_tickets.json", data)
        return {
            "created": True,
            "ticket": ticket,
            "message": f"HR ticket {ticket_id} created successfully.",
        }
    except Exception as e:
        return {"created": False, "error": str(e)}


def draft_hr_email(
    to_role: str,
    subject: str,
    body_context: str,
    employee_id: str,
    requester_confirmed: bool = False,
) -> dict:
    """
    Draft a mock HR-related email (e.g., to manager for PTO, remote work request).
    to_role: 'manager', 'hr', 'finance', 'vp'
    requester_confirmed: MUST be True to finalize the draft; if False, shows preview only.
    """
    role_emails = {
        "manager": "[manager's email — look up via employee profile]",
        "hr": "hr@acmecorp.com",
        "finance": "finance@acmecorp.com",
        "vp": "[VP's email — look up via org chart]",
    }
    to_email = role_emails.get(to_role.lower(), f"{to_role}@acmecorp.com")

    draft = {
        "to": to_email,
        "subject": subject,
        "body": (
            f"Dear {to_role.title()},\n\n"
            f"{body_context}\n\n"
            f"Employee ID: {employee_id}\n\n"
            "Please review and let me know if you need any additional information.\n\n"
            "Best regards,\n[Employee Name]"
        ),
        "is_mock": True,
        "note": "This is a MOCK draft. No email has been sent.",
    }

    if not requester_confirmed:
        return {
            "sent": False,
            "requires_confirmation": True,
            "message": "Please review the draft below and confirm to finalize.",
            "draft": draft,
        }

    return {
        "sent": False,
        "finalized": True,
        "message": (
            "Draft finalized (MOCK — no real email sent). "
            "Copy and send manually via your email client."
        ),
        "draft": draft,
    }
