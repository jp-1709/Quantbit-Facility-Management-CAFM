import frappe

@frappe.whitelist()
def test_work_order_permissions():
    """Test function to verify work order permissions"""
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    # Get Resource records linked to this user
    resource_list = frappe.db.get_all("Resource", 
        filters={"user_id": user, "is_active": 1}, 
        pluck="name"
    )
    
    # Test work order query directly
    from .utils.work_order_permissions import work_order_query
    condition = work_order_query(user)
    
    return {
        "user": user,
        "roles": user_roles,
        "resources": resource_list,
        "permission_condition": condition
    }
