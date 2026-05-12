"""
Facility Management – Whitelisted API
========================================
All methods here are accessible via /api/method/facility_management.api.*
The frontend calls these instead of raw frappe.get_list to get
permission-aware, role-scoped data in a single request.
"""

import frappe
from frappe import _
from facility_management.permissions import (
    get_highest_facility_role,
    get_user_branch,
    get_employee_record,
    get_supervised_employees,
    ROLE_SUPER_ADMIN, ROLE_ADMIN,
    ROLE_BRANCH_MANAGER, ROLE_SUPERVISOR, ROLE_TECHNICIAN,
)


# ─── Session / Auth ───────────────────────────────────────────────────────────

@frappe.whitelist()
def get_session_permissions():
    """
    Called on login. Returns the current user's role, branch, and a
    capability map consumed by the frontend permission system.
    """
    user = frappe.session.user
    role = get_highest_facility_role(user)
    emp  = get_employee_record(user)
    branch = emp.branch if emp else None

    capabilities = build_capability_map(role)

    return {
        "user": user,
        "role": role,
        "branch": branch,
        "employee": emp,
        "capabilities": capabilities,
        "is_super_admin": role == ROLE_SUPER_ADMIN,
        "is_admin":       role in (ROLE_SUPER_ADMIN, ROLE_ADMIN),
        "is_manager":     role in (ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_BRANCH_MANAGER),
        "is_supervisor":  role in (ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_BRANCH_MANAGER, ROLE_SUPERVISOR),
        "is_technician":  role == ROLE_TECHNICIAN,
    }


def build_capability_map(role: str) -> dict:
    """
    Returns a flat boolean map of what the current role can do.
    The frontend uses this to show/hide nav items and action buttons.
    """
    base = {
        # Navigation visibility
        "nav.dashboard":         False,
        "nav.work_orders":       False,
        "nav.service_requests":  False,
        "nav.assets":            False,
        "nav.reservations":      False,
        "nav.contracts":         False,
        "nav.locations":         False,
        "nav.reports":           False,
        "nav.scheduler":         False,
        "nav.technicians":       False,
        "nav.user_setup":        False,
        "nav.iot_dashboard":     False,
        "nav.calendar":          False,
        # Actions
        "action.create_work_order":     False,
        "action.create_service_request":False,
        "action.assign_work_order":     False,
        "action.approve_work_order":    False,
        "action.close_work_order":      False,
        "action.manage_users":          False,
        "action.manage_branches":       False,
        "action.view_all_branches":     False,
        "action.export_reports":        False,
        "action.manage_contracts":      False,
        "action.manage_assets":         False,
        "action.delete_records":        False,
    }

    if role == ROLE_SUPER_ADMIN:
        return {k: True for k in base}

    if role == ROLE_ADMIN:
        return {**base,
            "nav.dashboard": True, "nav.work_orders": True,
            "nav.service_requests": True, "nav.assets": True,
            "nav.reservations": True, "nav.contracts": True,
            "nav.locations": True, "nav.reports": True,
            "nav.scheduler": True, "nav.technicians": True,
            "nav.user_setup": True, "nav.iot_dashboard": True,
            "nav.calendar": True,
            "action.create_work_order": True, "action.create_service_request": True,
            "action.assign_work_order": True, "action.approve_work_order": True,
            "action.close_work_order": True, "action.manage_users": True,
            "action.manage_assets": True, "action.export_reports": True,
            "action.manage_contracts": True, "action.delete_records": True,
        }

    if role == ROLE_BRANCH_MANAGER:
        return {**base,
            "nav.dashboard": True, "nav.work_orders": True,
            "nav.service_requests": True, "nav.assets": True,
            "nav.reservations": True, "nav.contracts": True,
            "nav.locations": True, "nav.reports": True,
            "nav.scheduler": True, "nav.technicians": True,
            "nav.calendar": True,
            "action.create_work_order": True, "action.create_service_request": True,
            "action.assign_work_order": True, "action.approve_work_order": True,
            "action.close_work_order": True, "action.manage_assets": True,
            "action.export_reports": True,
        }

    if role == ROLE_SUPERVISOR:
        return {**base,
            "nav.dashboard": True, "nav.work_orders": True,
            "nav.service_requests": True, "nav.assets": True,
            "nav.scheduler": True, "nav.technicians": True,
            "nav.calendar": True,
            "action.create_work_order": True, "action.create_service_request": True,
            "action.assign_work_order": True, "action.close_work_order": True,
        }

    if role == ROLE_TECHNICIAN:
        return {**base,
            "nav.dashboard": True, "nav.work_orders": True,
            "nav.service_requests": True, "nav.calendar": True,
            "action.create_service_request": True, "action.close_work_order": True,
        }

    return base


# ─── Dashboard ────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_dashboard_stats():
    """
    Returns KPI counts scoped to what the current user can see.
    Because each get_list call will apply permission_query_conditions,
    the counts are automatically filtered.
    """
    user  = frappe.session.user
    role  = get_highest_facility_role(user)
    emp   = get_employee_record(user)

    filters = {}
    if role == ROLE_BRANCH_MANAGER:
        filters["branch"] = emp.branch
    elif role == ROLE_SUPERVISOR:
        team = get_supervised_employees(user)
        filters = {"assigned_to": ["in", team], "branch": emp.branch}
    elif role == ROLE_TECHNICIAN:
        filters["assigned_to"] = emp.name if emp else frappe.session.user

    open_wo = frappe.db.count("Work Order",    {**filters, "status": ["in", ["Open","In Progress"]]})
    open_sr = frappe.db.count("Service Request",{**filters, "status": ["in", ["Open","Pending"]]})
    overdue = frappe.db.count("Work Order",    {**filters, "status": "Open",
                                                "due_date": ["<", frappe.utils.today()]})
    completed_today = frappe.db.count("Work Order", {**filters, "status": "Completed",
                                                     "modified": [">=", frappe.utils.today()]})

    result = {
        "open_work_orders":    open_wo,
        "open_service_requests": open_sr,
        "overdue_work_orders": overdue,
        "completed_today":     completed_today,
    }

    # Branch managers and above get multi-branch breakdown
    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        branches = frappe.get_all("Branch", pluck="name")
        result["by_branch"] = []
        for b in branches:
            result["by_branch"].append({
                "branch": b,
                "open_work_orders": frappe.db.count("Work Order",
                    {"branch": b, "status": ["in", ["Open","In Progress"]]}),
                "open_service_requests": frappe.db.count("Service Request",
                    {"branch": b, "status": ["in", ["Open","Pending"]]}),
            })

    return result


# ─── Work Orders ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_work_orders(
    status: str = None,
    priority: str = None,
    page: int = 1,
    page_length: int = 20,
):
    """
    Returns work orders visible to the current user.
    permission_query_conditions automatically scopes results.
    """
    filters = {}
    if status:
        filters["status"] = status
    if priority:
        filters["priority"] = priority

    orders = frappe.get_list(
        "Work Order",
        filters=filters,
        fields=[
            "name", "title", "status", "priority", "branch",
            "assigned_to", "assigned_to_name", "due_date",
            "asset", "location", "description", "creation",
        ],
        order_by="priority ASC, due_date ASC",
        start=(page - 1) * page_length,
        page_length=page_length,
    )
    total = frappe.db.count("Work Order", filters)
    return {"data": orders, "total": total, "page": page, "page_length": page_length}


# ─── Service Requests ─────────────────────────────────────────────────────────

@frappe.whitelist()
def get_service_requests(
    status: str = None,
    category: str = None,
    page: int = 1,
    page_length: int = 20,
):
    filters = {}
    if status:
        filters["status"] = status
    if category:
        filters["category"] = category

    requests = frappe.get_list(
        "Service Request",
        filters=filters,
        fields=[
            "name", "title", "status", "category", "priority",
            "branch", "assigned_to", "requester", "creation", "due_date",
        ],
        order_by="creation DESC",
        start=(page - 1) * page_length,
        page_length=page_length,
    )
    total = frappe.db.count("Service Request", filters)
    return {"data": requests, "total": total, "page": page, "page_length": page_length}


# ─── User Management ──────────────────────────────────────────────────────────

@frappe.whitelist()
def get_facility_employees(branch: str = None):
    """Returns employees visible to the current user (branch-scoped for managers)."""
    user = frappe.session.user
    role = get_highest_facility_role(user)

    filters = {"enabled": 1}

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        if branch:
            filters["branch"] = branch
    elif role == ROLE_BRANCH_MANAGER:
        filters["branch"] = get_user_branch(user)
    elif role == ROLE_SUPERVISOR:
        # Supervisors only see their own team
        emp = get_employee_record(user)
        filters["supervisor"] = emp.name if emp else "__none__"
    else:
        frappe.throw(_("Insufficient permissions"), frappe.PermissionError)

    employees = frappe.get_all(
        "Facility Employee",
        filters=filters,
        fields=["name", "full_name", "employee_type", "branch",
                "supervisor", "phone", "current_workload"],
    )
    return employees


@frappe.whitelist()
def create_facility_user(
    email: str,
    full_name: str,
    employee_type: str,
    branch: str,
    supervisor: str = None,
    phone: str = None,
):
    """Create a Frappe User + Facility Employee record in one call."""
    user = frappe.session.user
    role = get_highest_facility_role(user)

    # Only Admin+ can create any user; Branch Manager can create within their branch
    if role not in (ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_BRANCH_MANAGER):
        frappe.throw(_("Insufficient permissions to create users"), frappe.PermissionError)

    if role == ROLE_BRANCH_MANAGER:
        allowed_branch = get_user_branch(user)
        if branch != allowed_branch:
            frappe.throw(_("You can only create users in your own branch"), frappe.PermissionError)

    # Map employee_type → Role Profile
    role_profile_map = {
        "Super Admin":     "Facility Super Admin Profile",
        "Admin":           "Facility Admin Profile",
        "Branch Manager":  "Facility Branch Manager Profile",
        "Supervisor":      "Facility Supervisor Profile",
        "Technician":      "Facility Technician Profile",
    }
    role_profile = role_profile_map.get(employee_type)
    if not role_profile:
        frappe.throw(_(f"Unknown employee type: {employee_type}"))

    # Create Frappe User
    if not frappe.db.exists("User", email):
        new_user = frappe.new_doc("User")
        new_user.email      = email
        new_user.first_name = full_name.split()[0]
        new_user.last_name  = " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else ""
        new_user.role_profile_name = role_profile
        new_user.send_welcome_email = 1
        new_user.insert(ignore_permissions=True)

    # Create Facility Employee
    emp = frappe.new_doc("Facility Employee")
    emp.user          = email
    emp.employee_type = employee_type
    emp.branch        = branch
    emp.supervisor    = supervisor
    emp.phone         = phone
    emp.role_profile  = role_profile
    emp.enabled       = 1
    emp.insert(ignore_permissions=True)

    frappe.db.commit()
    return {"message": "User created successfully", "employee": emp.name}
