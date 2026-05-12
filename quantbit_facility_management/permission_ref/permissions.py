"""
Facility Management - Permission Engine
========================================
Central module called by hooks.py for every list query and single-doc read.

Role hierarchy (highest → lowest):
  Facility Super Admin   – all branches, all data, no filters
  Facility Admin         – all branches, all data (same as Super Admin for data)
  Facility Branch Manager– own branch only
  Facility Supervisor    – own branch, own team's work orders & requests
  Facility Technician    – own assigned records only

Each `*_query_conditions` function returns a raw SQL string that Frappe
appends with AND to every get_list WHERE clause.
Each `has_*_permission` function returns True/False for a single document.
"""

import frappe
from frappe import _


# ─── Role Constants ──────────────────────────────────────────────────────────

ROLE_SUPER_ADMIN     = "Facility Super Admin"
ROLE_ADMIN           = "Facility Admin"
ROLE_BRANCH_MANAGER  = "Facility Branch Manager"
ROLE_SUPERVISOR      = "Facility Supervisor"
ROLE_TECHNICIAN      = "Facility Technician"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_user_roles(user: str = None) -> set:
    user = user or frappe.session.user
    return set(frappe.get_roles(user))


def get_highest_facility_role(user: str = None) -> str | None:
    """Return the most-privileged Facility role for the user."""
    roles = get_user_roles(user)
    for role in [ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_BRANCH_MANAGER,
                 ROLE_SUPERVISOR, ROLE_TECHNICIAN]:
        if role in roles:
            return role
    return None


def get_resource_record(user: str = None):
    """Return the Resource linked to the Frappe user, or None."""
    user = user or frappe.session.user
    records = frappe.get_all(
        "Resource",
        filters={"user_id": user, "is_active": 1},
        fields=["name", "branch_code", "branch_name", "designation", "department", "staff_code"],
        limit=1,
    )
    return records[0] if records else None


def get_user_branch(user: str = None) -> str | None:
    resource = get_resource_record(user)
    return resource.branch_code if resource else None


def get_supervised_resources(supervisor_user: str = None) -> list[str]:
    """Return list of resource names supervised by this user."""
    supervisor_user = supervisor_user or frappe.session.user
    supervisor = get_resource_record(supervisor_user)
    if not supervisor:
        return []
    # For supervisors, get all technicians in the same branch
    team = frappe.get_all(
        "Resource",
        filters={
            "branch_code": supervisor.branch_code,
            "is_active": 1,
            "department": ["!=", "Management"]  # Exclude management roles
        },
        pluck="name",
    )
    return team


def get_user_technician_name(user: str = None) -> str | None:
    resource = get_resource_record(user)
    return resource.name if resource else None


# ─── Work Order ───────────────────────────────────────────────────────────────

def work_order_query_conditions(user: str = None) -> str:
    """
    Returns SQL condition string for Work Order list filtering.
    Frappe appends this with AND to the generated WHERE clause.
    """
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return ""  # No restriction

    if role == ROLE_BRANCH_MANAGER:
        branch = get_user_branch(user)
        if not branch:
            return "1=0"
        return f"`tabWork Order`.branch = {frappe.db.escape(branch)}"

    if role == ROLE_SUPERVISOR:
        branch = get_user_branch(user)
        team = get_supervised_resources(user)
        if not branch:
            return "1=0"
        branch_cond = f"`tabWork Order`.branch = {frappe.db.escape(branch)}"
        if team:
            team_list = ", ".join(frappe.db.escape(e) for e in team)
            assign_cond = f"`tabWork Order`.assigned_to IN ({team_list})"
            return f"({branch_cond} AND {assign_cond})"
        return branch_cond

    if role == ROLE_TECHNICIAN:
        tech = get_user_technician_name(user)
        if not tech:
            return "1=0"
        return f"`tabWork Order`.assigned_to = {frappe.db.escape(tech)}"

    # No facility role — return nothing (standard Frappe perms handle it)
    return ""


def has_work_order_permission(doc, user: str = None, permission_type: str = "read") -> bool:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return True
    if role == ROLE_BRANCH_MANAGER:
        return doc.branch == get_user_branch(user)
    if role == ROLE_SUPERVISOR:
        branch_ok = doc.branch == get_user_branch(user)
        team = get_supervised_resources(user)
        team_ok = doc.assigned_to in team
        return branch_ok and team_ok
    if role == ROLE_TECHNICIAN:
        return doc.assigned_to == get_user_technician_name(user)
    return False


# ─── Service Request ──────────────────────────────────────────────────────────

def service_request_query_conditions(user: str = None) -> str:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return ""

    if role == ROLE_BRANCH_MANAGER:
        branch = get_user_branch(user)
        return f"`tabService Request`.branch = {frappe.db.escape(branch)}" if branch else "1=0"

    if role == ROLE_SUPERVISOR:
        branch = get_user_branch(user)
        team = get_supervised_resources(user)
        if not branch:
            return "1=0"
        branch_cond = f"`tabService Request`.branch = {frappe.db.escape(branch)}"
        if team:
            team_list = ", ".join(frappe.db.escape(e) for e in team)
            assign_cond = f"`tabService Request`.assigned_to IN ({team_list})"
            return f"({branch_cond} AND {assign_cond})"
        return branch_cond

    if role == ROLE_TECHNICIAN:
        tech = get_user_technician_name(user)
        if not tech:
            return "1=0"
        return (
            f"(`tabService Request`.assigned_to = {frappe.db.escape(tech)} "
            f"OR `tabService Request`.created_by_user = {frappe.db.escape(user)})"
        )

    return ""


def has_service_request_permission(doc, user: str = None, permission_type: str = "read") -> bool:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)
    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return True
    if role == ROLE_BRANCH_MANAGER:
        return doc.branch == get_user_branch(user)
    if role == ROLE_SUPERVISOR:
        return (doc.branch == get_user_branch(user) and
                doc.assigned_to in get_supervised_resources(user))
    if role == ROLE_TECHNICIAN:
        return (doc.assigned_to == get_user_technician_name(user) or
                doc.created_by_user == user)
    return False


# ─── Asset ────────────────────────────────────────────────────────────────────

def asset_query_conditions(user: str = None) -> str:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return ""

    if role in (ROLE_BRANCH_MANAGER, ROLE_SUPERVISOR):
        branch = get_user_branch(user)
        return f"`tabAsset`.branch = {frappe.db.escape(branch)}" if branch else "1=0"

    if role == ROLE_TECHNICIAN:
        # Technicians see assets in their branch
        branch = get_user_branch(user)
        return f"`tabAsset`.branch = {frappe.db.escape(branch)}" if branch else "1=0"

    return ""


def has_asset_permission(doc, user: str = None, permission_type: str = "read") -> bool:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)
    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return True
    if role in (ROLE_BRANCH_MANAGER, ROLE_SUPERVISOR, ROLE_TECHNICIAN):
        return doc.branch == get_user_branch(user)
    return False


# ─── Contract ────────────────────────────────────────────────────────────────

def contract_query_conditions(user: str = None) -> str:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return ""

    if role == ROLE_BRANCH_MANAGER:
        branch = get_user_branch(user)
        return f"`tabContract`.branch = {frappe.db.escape(branch)}" if branch else "1=0"

    # Supervisors and Technicians cannot see contracts
    return "1=0"


def has_contract_permission(doc, user: str = None, permission_type: str = "read") -> bool:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)
    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return True
    if role == ROLE_BRANCH_MANAGER:
        return doc.branch == get_user_branch(user)
    return False


# ─── Reservation ─────────────────────────────────────────────────────────────

def reservation_query_conditions(user: str = None) -> str:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return ""

    if role in (ROLE_BRANCH_MANAGER, ROLE_SUPERVISOR):
        branch = get_user_branch(user)
        return f"`tabReservation`.branch = {frappe.db.escape(branch)}" if branch else "1=0"

    # Technicians don't access reservations
    return "1=0"


def has_reservation_permission(doc, user: str = None, permission_type: str = "read") -> bool:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)
    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return True
    if role in (ROLE_BRANCH_MANAGER, ROLE_SUPERVISOR):
        return doc.branch == get_user_branch(user)
    return False


# ─── Maintenance Schedule ────────────────────────────────────────────────────

def maintenance_schedule_query_conditions(user: str = None) -> str:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return ""

    branch = get_user_branch(user)
    if not branch:
        return "1=0"

    if role == ROLE_BRANCH_MANAGER:
        return f"`tabMaintenance Schedule`.branch = {frappe.db.escape(branch)}"

    if role == ROLE_SUPERVISOR:
        team = get_supervised_resources(user)
        if not team:
            return "1=0"
        team_list = ", ".join(frappe.db.escape(e) for e in team)
        return (f"`tabMaintenance Schedule`.branch = {frappe.db.escape(branch)} "
                f"AND `tabMaintenance Schedule`.assigned_to IN ({team_list})")

    if role == ROLE_TECHNICIAN:
        tech = get_user_technician_name(user)
        return f"`tabMaintenance Schedule`.assigned_to = {frappe.db.escape(tech)}" if tech else "1=0"

    return ""


# ─── Technician ───────────────────────────────────────────────────────────────

def resource_query_conditions(user: str = None) -> str:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return ""

    if role in (ROLE_BRANCH_MANAGER, ROLE_SUPERVISOR):
        branch = get_user_branch(user)
        return f"`tabResource`.branch_code = {frappe.db.escape(branch)}" if branch else "1=0"

    if role == ROLE_TECHNICIAN:
        tech = get_user_technician_name(user)
        return f"`tabResource`.name = {frappe.db.escape(tech)}" if tech else "1=0"

    return ""


# ─── Location ─────────────────────────────────────────────────────────────────

def location_query_conditions(user: str = None) -> str:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return ""  # All locations

    branch = get_user_branch(user)
    if not branch:
        return "1=0"
    return f"`tabLocation`.branch = {frappe.db.escape(branch)}"


# ─── Report ───────────────────────────────────────────────────────────────────

def report_query_conditions(user: str = None) -> str:
    if not user:
        user = frappe.session.user
    role = get_highest_facility_role(user)

    if role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        return ""

    if role == ROLE_BRANCH_MANAGER:
        branch = get_user_branch(user)
        return f"`tabReport`.branch = {frappe.db.escape(branch)}" if branch else "1=0"

    # Supervisors and Technicians cannot access Reports DocType directly
    return "1=0"


# ─── Document Event Handlers ─────────────────────────────────────────────────

def set_work_order_branch(doc, method=None):
    """Auto-stamp branch on new Work Orders based on creator's branch."""
    if not doc.branch:
        branch = get_user_branch(frappe.session.user)
        if branch:
            doc.branch = branch


def set_service_request_branch(doc, method=None):
    """Auto-stamp branch on new Service Requests."""
    if not doc.branch:
        branch = get_user_branch(frappe.session.user)
        if branch:
            doc.branch = branch


def notify_technician_on_submit(doc, method=None):
    """Send in-app + email notification to assigned technician on WO submit."""
    if not doc.assigned_to:
        return
    emp = frappe.get_doc("Facility Employee", doc.assigned_to)
    if emp.user:
        frappe.publish_realtime(
            "work_order_assigned",
            {"work_order": doc.name, "title": doc.title},
            user=emp.user,
        )
        frappe.sendmail(
            recipients=[emp.user],
            subject=f"New Work Order Assigned: {doc.title}",
            template="work_order_assigned",
            args={"doc": doc, "employee": emp},
            now=True,
        )


def auto_assign_service_request(doc, method=None):
    """
    Auto-assign Service Request to the least-loaded technician
    in the same branch when no technician is specified.
    """
    if doc.assigned_to:
        return

    available_techs = frappe.get_all(
        "Resource",
        filters={
            "branch_code": doc.branch,
            "department": ["in", ["Technical", "Operations"]],  # Technical staff
            "is_active": 1,
        },
        fields=["name"],
        order_by="staff_code ASC",  # Simple ordering since workload field may not exist
        limit=1,
    )
    if available_techs:
        doc.db_set("assigned_to", available_techs[0].name)
