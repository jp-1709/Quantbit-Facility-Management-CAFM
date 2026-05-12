import frappe
from frappe import _
from frappe.utils.password import update_password

@frappe.whitelist()
def fm_create_user_with_roles(user_data, roles=None):
    """
    Create a new user with roles in a single operation
    
    Args:
        user_data (dict): User data including email, first_name, last_name, etc.
        roles (list): List of role names to assign to the user
        
    Returns:
        dict: Success/failure message with user details
    """
    try:
        # Validate required fields
        if not user_data.get('email'):
            return {
                'success': False,
                'message': 'Email is required'
            }
        
        if not user_data.get('first_name'):
            return {
                'success': False,
                'message': 'First name is required'
            }
        
        # Check if user already exists
        if frappe.db.exists('User', user_data['email']):
            return {
                'success': False,
                'message': f'User with email {user_data["email"]} already exists'
            }
        
        # Prepare user document
        user_doc = frappe.new_doc('User')
        
        # Set user fields
        user_doc.email = user_data['email']
        user_doc.first_name = user_data['first_name']
        user_doc.last_name = user_data.get('last_name', '')
        user_doc.full_name = user_data.get('full_name') or f"{user_data['first_name']} {user_data.get('last_name', '')}".strip()
        user_doc.enabled = user_data.get('enabled', 1)
        user_doc.user_type = user_data.get('user_type', 'System User')
        user_doc.send_welcome_email = user_data.get('send_welcome_email', 1)
        
        # Set optional fields only if they have values
        if user_data.get('phone'):
            user_doc.phone = user_data['phone']
        if user_data.get('mobile_no'):
            user_doc.mobile_no = user_data['mobile_no']
        
        # Insert user
        user_doc.insert(ignore_permissions=True)
        user_name = user_doc.name
        
        # Set password if provided
        if user_data.get('new_password'):
            update_password(user_name, user_data['new_password'])
        
        # Assign roles if provided
        if roles and isinstance(roles, list):
            for role_name in roles:
                # Check if role exists
                if frappe.db.exists('Role', role_name):
                    # Create role assignment
                    role_doc = frappe.new_doc('Has Role')
                    role_doc.role = role_name
                    role_doc.parent = user_name
                    role_doc.parentfield = 'roles'
                    role_doc.parenttype = 'User'
                    role_doc.insert(ignore_permissions=True)
                else:
                    frappe.logger().warning(f"Role '{role_name}' does not exist, skipping")
        
        # Commit changes
        frappe.db.commit()
        
        return {
            'success': True,
            'message': f'User {user_name} created successfully with {len(roles) if roles else 0} roles',
            'user_name': user_name,
            'user_email': user_data['email'],
            'roles_assigned': len(roles) if roles else 0
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.logger().error(f"Error creating user: {str(e)}")
        return {
            'success': False,
            'message': f'Error creating user: {str(e)}'
        }

@frappe.whitelist()
def fm_assign_user_roles(user_id, roles):
    """
    Assign roles to a user by removing existing roles and adding new ones
    
    Args:
        user_id (str): User ID or email
        roles (list): List of role names to assign
    
    Returns:
        dict: Success/failure message with details
    """
    try:
        # Validate user exists
        if not frappe.db.exists("User", user_id):
            return {
                "success": False,
                "message": f"User {user_id} does not exist"
            }
        
        # Get user's email if user_id is name
        user_email = frappe.db.get_value("User", user_id, "email")
        if not user_email:
            user_email = user_id
        
        # Delete all existing roles for this user
        frappe.db.delete("Has Role", {
            "parent": user_id
        })
        
        # Add new roles
        success_count = 0
        failed_roles = []
        
        for role in roles:
            if frappe.db.exists("Role", role):
                # Create Has Role document
                role_doc = frappe.get_doc({
                    "doctype": "Has Role",
                    "role": role,
                    "parent": user_id,
                    "parentfield": "roles",
                    "parenttype": "User"
                })
                role_doc.insert(ignore_permissions=True)
                success_count += 1
            else:
                failed_roles.append(role)
        
        # Commit changes
        frappe.db.commit()
        
        message = f"Successfully assigned {success_count} roles to {user_email}"
        if failed_roles:
            message += f". Failed to assign roles: {', '.join(failed_roles)} (roles do not exist)"
        
        return {
            "success": True,
            "message": message,
            "success_count": success_count,
            "failed_roles": failed_roles
        }
        
    except Exception as e:
        frappe.db.rollback()
        return {
            "success": False,
            "message": f"Error assigning roles: {str(e)}"
        }

@frappe.whitelist()
def fm_get_user_roles(user_id):
    """
    Get all roles assigned to a user
    
    Args:
        user_id (str): User ID or email
    
    Returns:
        list: List of role names
    """
    try:
        roles = frappe.db.get_all("Has Role", 
            filters={"parent": user_id}, 
            fields=["role"]
        )
        return [role.role for role in roles]
    except Exception as e:
        frappe.log_error(f"Error getting user roles: {str(e)}")
        return []

@frappe.whitelist()
def fm_remove_user_role(user_id, role):
    """
    Remove a specific role from a user
    
    Args:
        user_id (str): User ID or email
        role (str): Role name to remove
    
    Returns:
        dict: Success/failure message
    """
    try:
        # Find the Has Role document
        has_role = frappe.db.get_value("Has Role", 
            {"parent": user_id, "role": role}, 
            "name"
        )
        
        if has_role:
            frappe.delete_doc("Has Role", has_role)
            frappe.db.commit()
            return {
                "success": True,
                "message": f"Successfully removed role '{role}' from user {user_id}"
            }
        else:
            return {
                "success": False,
                "message": f"Role '{role}' not found for user {user_id}"
            }
            
    except Exception as e:
        frappe.db.rollback()
        return {
            "success": False,
            "message": f"Error removing role: {str(e)}"
        }

@frappe.whitelist()
def fm_update_user_password(user_id, new_password):
    """
    Update user password
    
    Args:
        user_id (str): User ID or email
        new_password (str): New password to set
        
    Returns:
        dict: Success/failure message
    """
    try:
        # Validate user exists
        if not frappe.db.exists("User", user_id):
            return {
                "success": False,
                "message": f"User {user_id} does not exist"
            }
        
        # Validate password is provided
        if not new_password or new_password.strip() == "":
            return {
                "success": False,
                "message": "Password cannot be empty"
            }
        
        # Update password
        update_password(user_id, new_password)
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Password updated successfully for user {user_id}"
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.logger().error(f"Error updating password: {str(e)}")
        return {
            "success": False,
            "message": f"Error updating password: {str(e)}"
        }

@frappe.whitelist()
def fm_create_role(role_data):
    """
    Create a new role
    
    Args:
        role_data (dict): Role data including role_name, desk_access, etc.
        
    Returns:
        dict: Success/failure message with role details
    """
    try:
        # Validate required fields
        if not role_data.get('role_name'):
            return {
                'success': False,
                'message': 'Role name is required'
            }
        
        # Check if role already exists
        if frappe.db.exists('Role', role_data['role_name']):
            return {
                'success': False,
                'message': f'Role {role_data["role_name"]} already exists'
            }
        
        # Prepare role document
        role_doc = frappe.new_doc('Role')
        
        # Set role fields
        role_doc.role_name = role_data['role_name']
        role_doc.desk_access = role_data.get('desk_access', 1)
        role_doc.is_custom = role_data.get('is_custom', 0)
        role_doc.disabled = role_data.get('disabled', 0)
        role_doc.two_factor_auth = role_data.get('two_factor_auth', 0)
        
        # Insert role
        role_doc.insert(ignore_permissions=True)
        role_name = role_doc.name
        
        # Commit changes
        frappe.db.commit()
        
        return {
            'success': True,
            'message': f'Role {role_name} created successfully',
            'role_name': role_name,
            'role_data': {
                'name': role_name,
                'role_name': role_doc.role_name,
                'desk_access': role_doc.desk_access,
                'is_custom': role_doc.is_custom,
                'disabled': role_doc.disabled,
                'two_factor_auth': role_doc.two_factor_auth
            }
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.logger().error(f"Error creating role: {str(e)}")
        return {
            'success': False,
            'message': f'Error creating role: {str(e)}'
        }
