"""
Facility Management - Installation Setup
==========================================
Runs once on `bench install-app facility_management`.
Creates roles, role profiles, and the custom fields that link
Work Orders / Service Requests / Assets to a branch.
"""

import frappe
from frappe import _


FACILITY_ROLES = [
    {
        "role_name": "Facility Super Admin",
        "desk_access": 1,
        "is_custom": 1,
        "description": "Full access to all branches, users, configuration and reports.",
    },
    {
        "role_name": "Facility Admin",
        "desk_access": 1,
        "is_custom": 1,
        "description": "Full access. Manages users and settings.",
    },
    {
        "role_name": "Facility Branch Manager",
        "desk_access": 1,
        "is_custom": 1,
        "description": "Access limited to their assigned branch.",
    },
    {
        "role_name": "Facility Supervisor",
        "desk_access": 1,
        "is_custom": 1,
        "description": "Manages their team's work orders and service requests.",
    },
    {
        "role_name": "Facility Technician",
        "desk_access": 1,
        "is_custom": 1,
        "description": "Can only view and act on records assigned to them.",
    },
]

# Role Profile → list of roles assigned to that profile
ROLE_PROFILES = {
    "Facility Super Admin Profile": [
        "Facility Super Admin",
        "Facility Admin",
        "Facility Branch Manager",
        "Facility Supervisor",
        "Facility Technician",
    ],
    "Facility Admin Profile": [
        "Facility Admin",
        "Facility Branch Manager",
        "Facility Supervisor",
        "Facility Technician",
    ],
    "Facility Branch Manager Profile": [
        "Facility Branch Manager",
        "Facility Supervisor",
        "Facility Technician",
    ],
    "Facility Supervisor Profile": [
        "Facility Supervisor",
        "Facility Technician",
    ],
    "Facility Technician Profile": [
        "Facility Technician",
    ],
}

# Custom fields to add to existing DocTypes
CUSTOM_FIELDS = [
    # branch field on Work Order
    {
        "dt": "Work Order",
        "fieldname": "branch",
        "fieldtype": "Link",
        "options": "Branch",
        "label": "Branch",
        "insert_after": "company",
        "reqd": 1,
        "in_list_view": 1,
        "in_filter": 1,
        "search_index": 1,
    },
    # branch field on Service Request
    {
        "dt": "Service Request",
        "fieldname": "branch",
        "fieldtype": "Link",
        "options": "Branch",
        "label": "Branch",
        "insert_after": "company",
        "reqd": 1,
        "in_list_view": 1,
        "in_filter": 1,
        "search_index": 1,
    },
    # branch field on Asset
    {
        "dt": "Asset",
        "fieldname": "branch",
        "fieldtype": "Link",
        "options": "Branch",
        "label": "Branch",
        "insert_after": "company",
        "reqd": 0,
        "in_list_view": 1,
        "in_filter": 1,
    },
    # branch field on Contract
    {
        "dt": "Contract",
        "fieldname": "branch",
        "fieldtype": "Link",
        "options": "Branch",
        "label": "Branch",
        "insert_after": "company",
    },
    # branch field on Reservation
    {
        "dt": "Reservation",
        "fieldname": "branch",
        "fieldtype": "Link",
        "options": "Branch",
        "label": "Branch",
        "insert_after": "company",
    },
]


def after_install():
    create_roles()
    create_role_profiles()
    add_custom_fields()
    create_facility_employee_doctype()
    frappe.db.commit()
    print("✅ Facility Management permission scaffolding installed.")


def create_roles():
    for role_def in FACILITY_ROLES:
        if not frappe.db.exists("Role", role_def["role_name"]):
            role = frappe.new_doc("Role")
            role.role_name = role_def["role_name"]
            role.desk_access = role_def.get("desk_access", 1)
            role.is_custom = role_def.get("is_custom", 1)
            role.description = role_def.get("description", "")
            role.insert(ignore_permissions=True)
            print(f"  ✓ Created role: {role_def['role_name']}")
        else:
            print(f"  · Role exists: {role_def['role_name']}")


def create_role_profiles():
    for profile_name, roles in ROLE_PROFILES.items():
        if frappe.db.exists("Role Profile", profile_name):
            print(f"  · Role Profile exists: {profile_name}")
            continue
        profile = frappe.new_doc("Role Profile")
        profile.role_profile = profile_name
        for role_name in roles:
            profile.append("roles", {"role": role_name})
        profile.insert(ignore_permissions=True)
        print(f"  ✓ Created Role Profile: {profile_name}")


def add_custom_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    field_map = {}
    for cf in CUSTOM_FIELDS:
        dt = cf.pop("dt")
        field_map.setdefault(dt, []).append(cf)
    create_custom_fields(field_map, ignore_validate=True)
    print("  ✓ Custom fields added")


def create_facility_employee_doctype():
    """
    Creates the Facility Employee DocType if it doesn't exist.
    This is the bridge between a Frappe User and a facility branch/team.
    """
    if frappe.db.exists("DocType", "Facility Employee"):
        print("  · Facility Employee DocType exists")
        return

    doc = frappe.new_doc("DocType")
    doc.name = "Facility Employee"
    doc.module = "Facility Management"
    doc.autoname = "FM-EMP-.####"
    doc.is_submittable = 0
    doc.track_changes = 1
    doc.fields = [
        {"fieldname": "user",          "fieldtype": "Link",    "options": "User",              "label": "User",         "reqd": 1, "in_list_view": 1},
        {"fieldname": "full_name",     "fieldtype": "Data",    "label": "Full Name",           "fetch_from": "user.full_name", "read_only": 1, "in_list_view": 1},
        {"fieldname": "employee_type", "fieldtype": "Select",  "options": "Technician\nSupervisor\nBranch Manager\nAdmin\nSuper Admin", "label": "Employee Type", "reqd": 1, "in_list_view": 1},
        {"fieldname": "branch",        "fieldtype": "Link",    "options": "Branch",            "label": "Branch",       "reqd": 1, "in_list_view": 1, "search_index": 1},
        {"fieldname": "supervisor",    "fieldtype": "Link",    "options": "Facility Employee", "label": "Supervisor"},
        {"fieldname": "enabled",       "fieldtype": "Check",   "label": "Enabled",             "default": "1"},
        {"fieldname": "role_profile",  "fieldtype": "Link",    "options": "Role Profile",      "label": "Role Profile"},
        {"fieldname": "current_workload","fieldtype": "Int",   "label": "Current Workload",    "read_only": 1, "default": "0"},
        {"fieldname": "phone",         "fieldtype": "Data",    "label": "Phone"},
        {"fieldname": "skills_section","fieldtype": "Section Break", "label": "Skills"},
        {"fieldname": "skills",        "fieldtype": "Table MultiSelect", "options": "Facility Skill", "label": "Skills"},
        {"fieldname": "specializations","fieldtype": "Table MultiSelect","options": "Facility Specialization","label": "Specializations"},
    ]
    doc.permissions = [
        {"role": "Facility Super Admin", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"role": "Facility Admin",       "read": 1, "write": 1, "create": 1, "delete": 1},
        {"role": "Facility Branch Manager","read": 1, "write": 1, "create": 1, "delete": 0},
        {"role": "Facility Supervisor",  "read": 1, "write": 0, "create": 0, "delete": 0},
        {"role": "Facility Technician",  "read": 1, "write": 0, "create": 0, "delete": 0},
    ]
    doc.insert(ignore_permissions=True)
    print("  ✓ Facility Employee DocType created")
