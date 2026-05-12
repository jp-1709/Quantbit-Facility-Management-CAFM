#!/usr/bin/env python3
"""
Frappe Migration Script for Facility Management Permissions
================================================================
This script sets up the permission system within the Frappe environment.
Run this with: bench execute quantbit_facility_management.permission_ref.migrate
"""

import frappe
from frappe import _

def migrate():
    """Main migration function"""
    print("🚀 Starting Facility Management Permission System Setup...")
    
    try:
        # Step 1: Create roles
        create_facility_roles()
        
        # Step 2: Create role profiles  
        create_role_profiles()
        
        # Step 3: Add custom fields
        add_custom_fields()
        
        # Step 4: Create sample data
        create_sample_resources()
        
        # Step 5: Update permissions
        update_doctype_permissions()
        
        frappe.db.commit()
        print("✅ Facility Management Permission System setup completed successfully!")
        
    except Exception as e:
        frappe.db.rollback()
        print(f"❌ Setup failed: {str(e)}")
        raise

def create_facility_roles():
    """Create facility management roles"""
    print("\n📋 Creating facility roles...")
    
    roles = [
        {
            "role_name": "Facility Super Admin",
            "desk_access": 1,
            "is_custom": 1,
            "description": "Full access to all branches, users, configuration and reports."
        },
        {
            "role_name": "Facility Admin", 
            "desk_access": 1,
            "is_custom": 1,
            "description": "Full access. Manages users and settings."
        },
        {
            "role_name": "Facility Branch Manager",
            "desk_access": 1,
            "is_custom": 1,
            "description": "Access limited to their assigned branch."
        },
        {
            "role_name": "Facility Supervisor",
            "desk_access": 1,
            "is_custom": 1,
            "description": "Manages their team's work orders and service requests."
        },
        {
            "role_name": "Facility Technician",
            "desk_access": 1,
            "is_custom": 1,
            "description": "Can only view and act on records assigned to them."
        }
    ]
    
    for role_data in roles:
        if not frappe.db.exists("Role", role_data["role_name"]):
            role = frappe.new_doc("Role")
            role.update(role_data)
            role.insert(ignore_permissions=True)
            print(f"  ✓ Created role: {role_data['role_name']}")
        else:
            print(f"  · Role exists: {role_data['role_name']}")

def create_role_profiles():
    """Create role profiles"""
    print("\n👥 Creating role profiles...")
    
    role_profiles = {
        "Facility Super Admin Profile": [
            "Facility Super Admin", "Facility Admin", "Facility Branch Manager",
            "Facility Supervisor", "Facility Technician"
        ],
        "Facility Admin Profile": [
            "Facility Admin", "Facility Branch Manager", 
            "Facility Supervisor", "Facility Technician"
        ],
        "Facility Branch Manager Profile": [
            "Facility Branch Manager", "Facility Supervisor", "Facility Technician"
        ],
        "Facility Supervisor Profile": [
            "Facility Supervisor", "Facility Technician"
        ],
        "Facility Technician Profile": [
            "Facility Technician"
        ]
    }
    
    for profile_name, roles in role_profiles.items():
        if not frappe.db.exists("Role Profile", profile_name):
            profile = frappe.new_doc("Role Profile")
            profile.role_profile = profile_name
            for role_name in roles:
                profile.append("roles", {"role": role_name})
            profile.insert(ignore_permissions=True)
            print(f"  ✓ Created role profile: {profile_name}")
        else:
            print(f"  · Role profile exists: {profile_name}")

def add_custom_fields():
    """Add custom fields for branch and assignment tracking"""
    print("\n🔧 Adding custom fields...")
    
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    
    custom_fields = {
        "Work Order": [
            {
                "fieldname": "branch",
                "fieldtype": "Link",
                "options": "Branch",
                "label": "Branch",
                "insert_after": "company",
                "reqd": 1,
                "in_list_view": 1,
                "in_filter": 1,
                "search_index": 1,
            }
        ],
        "Service Request": [
            {
                "fieldname": "branch", 
                "fieldtype": "Link",
                "options": "Branch",
                "label": "Branch",
                "insert_after": "company",
                "reqd": 1,
                "in_list_view": 1,
                "in_filter": 1,
                "search_index": 1,
            }
        ],
        "Asset": [
            {
                "fieldname": "branch",
                "fieldtype": "Link", 
                "options": "Branch",
                "label": "Branch",
                "insert_after": "company",
                "reqd": 0,
                "in_list_view": 1,
                "in_filter": 1,
            }
        ]
    }
    
    create_custom_fields(custom_fields, ignore_validate=True)
    print("  ✓ Custom fields added")

def create_sample_resources():
    """Create sample Resource records for testing"""
    print("\n👤 Creating sample resources...")
    
    # Check if we have branches
    if not frappe.db.exists("Branch", {"name": ["!=", ""]]):
        print("  ⚠️ No branches found. Creating sample branch...")
        create_sample_branch()
    
    sample_resources = [
        {
            "staff_code": "TECH001",
            "resource_name": "Raj Kumar", 
            "branch_code": "Main Branch",
            "designation": "Senior Technician",
            "department": "Technical",
            "employment_type": "Staff",
            "user_id": get_or_create_user("raj@example.com", "Raj Kumar"),
            "is_active": 1
        },
        {
            "staff_code": "SUP001", 
            "resource_name": "Amit Sharma",
            "branch_code": "Main Branch", 
            "designation": "Supervisor",
            "department": "Operations",
            "employment_type": "Staff",
            "user_id": get_or_create_user("amit@example.com", "Amit Sharma"),
            "is_active": 1
        },
        {
            "staff_code": "MGR001",
            "resource_name": "Priya Singh",
            "branch_code": "Main Branch",
            "designation": "Branch Manager", 
            "department": "Management",
            "employment_type": "Staff",
            "user_id": get_or_create_user("priya@example.com", "Priya Singh"),
            "is_active": 1
        }
    ]
    
    for resource_data in sample_resources:
        if not frappe.db.exists("Resource", {"staff_code": resource_data["staff_code"]}):
            resource = frappe.new_doc("Resource")
            resource.update(resource_data)
            resource.insert(ignore_permissions=True)
            print(f"  ✓ Created resource: {resource_data['resource_name']}")
            
            # Assign appropriate role to user
            assign_role_to_user(resource_data["user_id"], get_role_for_designation(resource_data["designation"]))
        else:
            print(f"  · Resource exists: {resource_data['resource_name']}")

def create_sample_branch():
    """Create a sample branch for testing"""
    branch = frappe.new_doc("Branch")
    branch.branch_name = "Main Branch"
    branch.branch_code = "Main Branch"
    branch.insert(ignore_permissions=True)
    print("  ✓ Created sample branch: Main Branch")

def get_or_create_user(email, full_name):
    """Get or create a user"""
    if frappe.db.exists("User", email):
        return email
    
    user = frappe.new_doc("User")
    user.email = email
    user.first_name = full_name.split()[0]
    user.last_name = " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else ""
    user.enabled = 1
    user.insert(ignore_permissions=True)
    print(f"    ✓ Created user: {email}")
    return email

def get_role_for_designation(designation):
    """Map designation to facility role"""
    role_mapping = {
        "Senior Technician": "Facility Technician",
        "Technician": "Facility Technician", 
        "Supervisor": "Facility Supervisor",
        "Branch Manager": "Facility Branch Manager",
        "Manager": "Facility Admin"
    }
    return role_mapping.get(designation, "Facility Technician")

def assign_role_to_user(user_email, role_name):
    """Assign facility role to user"""
    user = frappe.get_doc("User", user_email)
    if role_name not in [d.role for d in user.roles]:
        user.append("roles", {"role": role_name})
        user.save(ignore_permissions=True)
        print(f"    ✓ Assigned role {role_name} to {user_email}")

def update_doctype_permissions():
    """Update DocType permissions for facility roles"""
    print("\n🔒 Updating DocType permissions...")
    
    # Update Work Order permissions
    update_work_order_permissions()
    
    # Update Service Request permissions  
    update_service_request_permissions()
    
    print("  ✓ DocType permissions updated")

def update_work_order_permissions():
    """Update Work Order permissions"""
    if frappe.db.exists("DocType", "Work Order"):
        doc = frappe.get_doc("DocType", "Work Order")
        
        # Add facility role permissions
        facility_permissions = [
            {"role": "Facility Super Admin", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1},
            {"role": "Facility Admin", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1},
            {"role": "Facility Branch Manager", "read": 1, "write": 1, "create": 1, "delete": 0, "submit": 1, "cancel": 1, "amend": 0},
            {"role": "Facility Supervisor", "read": 1, "write": 1, "create": 1, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
            {"role": "Facility Technician", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0}
        ]
        
        for perm in facility_permissions:
            existing = [p for p in doc.permissions if p.role == perm["role"]]
            if not existing:
                doc.append("permissions", perm)
        
        doc.save(ignore_permissions=True)
        print("    ✓ Work Order permissions updated")

def update_service_request_permissions():
    """Update Service Request permissions"""
    if frappe.db.exists("DocType", "Service Request"):
        doc = frappe.get_doc("DocType", "Service Request")
        
        facility_permissions = [
            {"role": "Facility Super Admin", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1},
            {"role": "Facility Admin", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1},
            {"role": "Facility Branch Manager", "read": 1, "write": 1, "create": 1, "delete": 0, "submit": 1, "cancel": 1, "amend": 0},
            {"role": "Facility Supervisor", "read": 1, "write": 1, "create": 1, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
            {"role": "Facility Technician", "read": 1, "write": 0, "create": 1, "delete": 0, "submit": 0, "cancel": 0, "amend": 0}
        ]
        
        for perm in facility_permissions:
            existing = [p for p in doc.permissions if p.role == perm["role"]]
            if not existing:
                doc.append("permissions", perm)
                
        doc.save(ignore_permissions=True)
        print("    ✓ Service Request permissions updated")

if __name__ == "__main__":
    migrate()
