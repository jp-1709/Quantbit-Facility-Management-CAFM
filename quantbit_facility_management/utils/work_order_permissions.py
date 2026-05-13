import frappe
from frappe import _

def get_user_branches(user):
    """Returns list of branch codes linked to the user via Branch doctype"""
    return frappe.get_all("Branch", filters={"user_id": user, "is_active": 1}, pluck="name")

def get_supervised_resources(user):
    """Returns list of resource names reporting to the current user's resource record"""
    # Get current resource
    current_resource = frappe.db.get_value("Resource", {"user_id": user, "is_active": 1}, "name")
    if not current_resource:
        return []
    
    # Get technicians reporting to this resource
    supervised = frappe.get_all("Resource", filters={"supervisor_code": current_resource, "is_active": 1}, pluck="name")
    
    # Include the current resource itself
    return supervised + [current_resource]

def is_unrestricted_user(user):
    """Check if user has roles that bypass all restrictions"""
    if not user:
        return False
    
    user_roles = frappe.get_roles(user)
    unrestricted_roles = [
        "System Manager", 
        "Super Admin", 
        "Head Operations",
        "Management Director",
        "Asset Manager"
    ]
    return any(role in user_roles for role in unrestricted_roles)

@frappe.whitelist()
def work_order_query(user=None):
    if not user: user = frappe.session.user
    if is_unrestricted_user(user): return ""

    roles = frappe.get_roles(user)
    conditions = []

    # Branch Manager logic
    if "Branch Manager" in roles:
        branches = get_user_branches(user)
        if branches:
            branch_list = ", ".join([f"'{b}'" for b in branches])
            conditions.append(f"`tabWork Orders`.branch_code IN ({branch_list})")

    # Supervisor / Technician logic
    if "Supervisor" in roles or "Technician" in roles:
        resources = get_supervised_resources(user)
        if resources:
            res_list = ", ".join([f"'{r}'" for r in resources])
            conditions.append(f"(`tabWork Orders`.assigned_to IN ({res_list}) OR `tabWork Orders`.secondary_tech IN ({res_list}))")

    if not conditions:
        # If user has roles but no branch/resource links, they shouldn't see anything
        # unless they have other roles. But here we restrict to what's defined.
        return "1=0"

    return " OR ".join(conditions)

@frappe.whitelist()
def service_request_query(user=None):
    if not user: user = frappe.session.user
    if is_unrestricted_user(user): return ""

    roles = frappe.get_roles(user)
    conditions = []
    
    if "Branch Manager" in roles or "Supervisor" in roles:
        branches = get_user_branches(user)
        if branches:
            branch_list = ", ".join([f"'{b}'" for b in branches])
            conditions.append(f"`tabService Request`.branch_code IN ({branch_list})")
            
    if "Technician" in roles:
        # Technicians see all except converted ones (existing logic)
        conditions.append("(`tabService Request`.converted_to_wo = 0 AND `tabService Request`.status != 'Converted')")

    if not conditions:
        return "1=0"
        
    return " OR ".join(conditions)

@frappe.whitelist()
def asset_query(user=None):
    if not user: user = frappe.session.user
    if is_unrestricted_user(user): return ""

    roles = frappe.get_roles(user)
    if "Branch Manager" in roles or "Supervisor" in roles:
        branches = get_user_branches(user)
        if branches:
            branch_list = ", ".join([f"'{b}'" for b in branches])
            return f"`tabCFAM Asset`.branch_code IN ({branch_list})"
            
    return ""

@frappe.whitelist()
def property_query(user=None):
    if not user: user = frappe.session.user
    if is_unrestricted_user(user): return ""

    roles = frappe.get_roles(user)
    if "Branch Manager" in roles or "Supervisor" in roles:
        branches = get_user_branches(user)
        if branches:
            branch_list = ", ".join([f"'{b}'" for b in branches])
            return f"`tabProperty`.branch_code IN ({branch_list})"
            
    return ""

@frappe.whitelist()
def ppm_schedule_query(user=None):
    if not user: user = frappe.session.user
    if is_unrestricted_user(user): return ""

    roles = frappe.get_roles(user)
    conditions = []

    if "Branch Manager" in roles or "Supervisor" in roles:
        branches = get_user_branches(user)
        if branches:
            branch_list = ", ".join([f"'{b}'" for b in branches])
            # Filter by Property's branch
            conditions.append(f"""
                `tabPPM Schedule`.property_code IN (
                    SELECT name FROM `tabProperty` WHERE branch_code IN ({branch_list})
                )
            """)

    if "Supervisor" in roles or "Technician" in roles:
        resources = get_supervised_resources(user)
        if resources:
            res_list = ", ".join([f"'{r}'" for r in resources])
            conditions.append(f"`tabPPM Schedule`.assigned_to IN ({res_list})")

    if not conditions:
        return "1=0"

    return " OR ".join(conditions)

@frappe.whitelist()
def resource_query(user=None):
    if not user: user = frappe.session.user
    if is_unrestricted_user(user): return ""
    
    roles = frappe.get_roles(user)
    
    # Branch Manager: show resources in their branch
    if "Branch Manager" in roles:
        branches = get_user_branches(user)
        if branches:
            branch_list = ", ".join([f"'{b}'" for b in branches])
            return f"`tabResource`.branch_code IN ({branch_list})"
            
    # Supervisor: show their technicians
    if "Supervisor" in roles:
        resources = get_supervised_resources(user)
        if resources:
            res_list = ", ".join([f"'{r}'" for r in resources])
            return f"`tabResource`.name IN ({res_list})"
            
    # Fallback for technicians or others
    return "`tabResource`.is_active = 1"

def resource_has_permission(doc, ptype, user, verbose=False):
    """
    Grant read permission for Resource to Technicians
    """
    if ptype == "read" and "Technician" in frappe.get_roles(user):
        return True
    return False

def is_admin_or_manager_user(user):
    """DEPRECATED: Use is_unrestricted_user for bypass logic. 
    Keeping for compatibility if called elsewhere."""
    return is_unrestricted_user(user)
