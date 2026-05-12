"""
Facility Management - Frappe Hooks
===================================
Registers permission query conditions, document events, and API overrides
for role-based data filtering across all facility DocTypes.
"""

app_name = "facility_management"
app_title = "Facility Management"
app_publisher = "Your Company"
app_description = "Role-based Facility Management System"
app_version = "1.0.0"

# ─── Permission Query Conditions ────────────────────────────────────────────
# These hooks inject WHERE-clause conditions into every frappe.get_list() call
# for the respective DocType, ensuring row-level security at the DB layer.

permission_query_conditions = {
    "Work Order":          "facility_management.permissions.work_order_query_conditions",
    "Service Request":     "facility_management.permissions.service_request_query_conditions",
    "Asset":               "facility_management.permissions.asset_query_conditions",
    "Reservation":         "facility_management.permissions.reservation_query_conditions",
    "Maintenance Schedule":"facility_management.permissions.maintenance_schedule_query_conditions",
    "Resource":            "facility_management.permissions.resource_query_conditions",
    "Location":            "facility_management.permissions.location_query_conditions",
    "Contract":            "facility_management.permissions.contract_query_conditions",
    "Report":              "facility_management.permissions.report_query_conditions",
}

# ─── Has Permission (single-doc read gate) ──────────────────────────────────
has_permission = {
    "Work Order":          "facility_management.permissions.has_work_order_permission",
    "Service Request":     "facility_management.permissions.has_service_request_permission",
    "Asset":               "facility_management.permissions.has_asset_permission",
    "Contract":            "facility_management.permissions.has_contract_permission",
    "Reservation":         "facility_management.permissions.has_reservation_permission",
}

# ─── Document Events ─────────────────────────────────────────────────────────
doc_events = {
    "Work Order": {
        "before_insert": "facility_management.permissions.set_work_order_branch",
        "on_submit":     "facility_management.permissions.notify_technician_on_submit",
    },
    "Service Request": {
        "before_insert": "facility_management.permissions.set_service_request_branch",
        "on_submit":     "facility_management.permissions.auto_assign_service_request",
    },
    "User": {
        "after_insert":  "facility_management.setup.user_setup.create_facility_employee",
        "on_update":     "facility_management.setup.user_setup.sync_employee_branch",
    },
}

# ─── Fixtures (exported with bench export-fixtures) ─────────────────────────
fixtures = [
    # Role definitions
    {"dt": "Role", "filters": [["name", "in", [
        "Facility Super Admin",
        "Facility Admin",
        "Facility Branch Manager",
        "Facility Supervisor",
        "Facility Technician",
    ]]]},
    # Role Profiles
    {"dt": "Role Profile", "filters": [["name", "like", "Facility%"]]},
    # Custom fields that store branch / technician linkages
    {"dt": "Custom Field", "filters": [["module", "=", "Facility Management"]]},
    # DocType permissions
    {"dt": "DocPerm", "filters": [["parent", "in", [
        "Work Order", "Service Request", "Asset",
        "Reservation", "Contract", "Maintenance Schedule",
    ]]]},
]

# ─── On App Install ───────────────────────────────────────────────────────────
after_install = "facility_management.setup.install.after_install"

# ─── Scheduled Jobs ──────────────────────────────────────────────────────────
scheduler_events = {
    "daily": [
        "facility_management.tasks.send_daily_technician_digest",
        "facility_management.tasks.escalate_overdue_work_orders",
    ],
    "hourly": [
        "facility_management.tasks.sync_iot_sensor_readings",
    ],
}

# ─── Override Whitelisted Methods ────────────────────────────────────────────
override_whitelisted_methods = {
    "frappe.desk.reportview.get":       "facility_management.api.report_view.get",
    "frappe.desk.reportview.get_count": "facility_management.api.report_view.get_count",
}
