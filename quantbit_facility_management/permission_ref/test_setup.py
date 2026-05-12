#!/usr/bin/env python3
"""
Test script to verify the permission system setup
Run with: bench execute quantbit_facility_management.permission_ref.test_setup
"""

import frappe
from frappe import _

def test_permission_setup():
    """Test the complete permission system setup"""
    print("🧪 Testing Facility Management Permission System Setup")
    print("=" * 60)
    
    success = True
    
    # Test 1: Check Roles
    print("\n📋 Testing Roles...")
    required_roles = [
        "Facility Super Admin",
        "Facility Admin", 
        "Facility Branch Manager",
        "Facility Supervisor",
        "Facility Technician"
    ]
    
    for role in required_roles:
        if frappe.db.exists("Role", role):
            print(f"  ✅ Role exists: {role}")
        else:
            print(f"  ❌ Role missing: {role}")
            success = False
    
    # Test 2: Check Resources
    print("\n👤 Testing Resources...")
    sample_resources = ["TECH001", "SUP001", "MGR001"]
    
    for staff_code in sample_resources:
        if frappe.db.exists("Resource", {"staff_code": staff_code}):
            resource = frappe.get_doc("Resource", {"staff_code": staff_code})
            print(f"  ✅ Resource exists: {resource.resource_name} ({staff_code})")
            
            # Check if user is linked
            if resource.user_id:
                print(f"    📧 Linked to user: {resource.user_id}")
            else:
                print(f"    ⚠️ No user linked")
        else:
            print(f"  ❌ Resource missing: {staff_code}")
            success = False
    
    # Test 3: Check Users and Roles
    print("\n🔐 Testing User Role Assignments...")
    test_users = [
        {"email": "raj@example.com", "role": "Facility Technician"},
        {"email": "amit@example.com", "role": "Facility Supervisor"}, 
        {"email": "priya@example.com", "role": "Facility Branch Manager"}
    ]
    
    for user_data in test_users:
        if frappe.db.exists("User", user_data["email"]):
            user = frappe.get_doc("User", user_data["email"])
            user_roles = [d.role for d in user.roles]
            
            if user_data["role"] in user_roles:
                print(f"  ✅ {user.email} has role: {user_data['role']}")
            else:
                print(f"  ❌ {user.email} missing role: {user_data['role']}")
                print(f"    Current roles: {', '.join(user_roles)}")
                success = False
        else:
            print(f"  ❌ User missing: {user_data['email']}")
            success = False
    
    # Test 4: Check Custom Fields
    print("\n🔧 Testing Custom Fields...")
    
    # Check Work Order branch field
    if frappe.db.exists("Custom Field", {"dt": "Work Order", "fieldname": "branch"}):
        print("  ✅ Work Order 'branch' field exists")
    else:
        print("  ❌ Work Order 'branch' field missing")
        success = False
    
    # Check Service Request branch field
    if frappe.db.exists("Custom Field", {"dt": "Service Request", "fieldname": "branch"}):
        print("  ✅ Service Request 'branch' field exists")
    else:
        print("  ❌ Service Request 'branch' field missing")
        success = False
    
    # Test 5: Test Permission Functions
    print("\n🔒 Testing Permission Functions...")
    try:
        # Import permissions module
        from quantbit_facility_management.permission_ref.permissions import (
            get_highest_facility_role,
            get_user_branch,
            work_order_query_conditions,
            service_request_query_conditions
        )
        
        # Test with sample user
        test_user = "raj@example.com"
        if frappe.db.exists("User", test_user):
            role = get_highest_facility_role(test_user)
            branch = get_user_branch(test_user)
            
            print(f"  ✅ get_highest_facility_role('{test_user}'): {role}")
            print(f"  ✅ get_user_branch('{test_user}'): {branch}")
            
            # Test query conditions
            wo_conditions = work_order_query_conditions(test_user)
            sr_conditions = service_request_query_conditions(test_user)
            
            print(f"  ✅ work_order_query_conditions: {wo_conditions}")
            print(f"  ✅ service_request_query_conditions: {sr_conditions}")
        else:
            print(f"  ⚠️ Test user {test_user} not found, skipping function tests")
            
    except ImportError as e:
        print(f"  ❌ Could not import permission functions: {e}")
        success = False
    except Exception as e:
        print(f"  ❌ Error testing permission functions: {e}")
        success = False
    
    # Test 6: Check Hooks Registration
    print("\n🪝 Testing Hooks Registration...")
    try:
        hooks = frappe.get_hooks("permission_query_conditions")
        
        expected_doctypes = ["Work Order", "Service Request", "Asset"]
        for doctype in expected_doctypes:
            if doctype in hooks:
                print(f"  ✅ {doctype} permission query conditions registered")
            else:
                print(f"  ❌ {doctype} permission query conditions not registered")
                success = False
                
    except Exception as e:
        print(f"  ❌ Error checking hooks: {e}")
        success = False
    
    # Final Result
    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL TESTS PASSED! Permission system is ready to use.")
        print("\n📝 Next Steps:")
        print("1. Login as test users to verify UI filtering")
        print("2. Create work orders and service requests")
        print("3. Test role-based access in the frontend")
        print("4. Create additional resources as needed")
    else:
        print("❌ SOME TESTS FAILED! Please check the issues above.")
        print("\n🔧 Troubleshooting:")
        print("1. Run the migration script again")
        print("2. Check Frappe logs for errors")
        print("3. Verify all prerequisites are met")
    
    return success

def create_test_data():
    """Create sample work orders and service requests for testing"""
    print("\n📝 Creating test data...")
    
    # Get sample resources
    technician = frappe.get_doc("Resource", {"staff_code": "TECH001"})
    supervisor = frappe.get_doc("Resource", {"staff_code": "SUP001"})
    
    # Create sample work order
    if not frappe.db.exists("Work Order", {"wo_title": "Test Permission WO"}):
        wo = frappe.new_doc("Work Order")
        wo.update({
            "wo_title": "Test Permission WO",
            "wo_type": "Reactive Maintenance", 
            "status": "Open",
            "actual_priority": "P2 - High",
            "branch": technician.branch_code,
            "assigned_to": technician.name,
            "property_name": "Test Property",
            "asset_name": "Test Asset"
        })
        wo.insert(ignore_permissions=True)
        print(f"  ✅ Created test Work Order: {wo.name}")
    
    # Create sample service request
    if not frappe.db.exists("Service Request", {"sr_title": "Test Permission SR"}):
        sr = frappe.new_doc("Service Request")
        sr.update({
            "sr_title": "Test Permission SR", 
            "status": "Open",
            "priority_actual": "P2 - High",
            "branch": technician.branch_code,
            "assigned_to": technician.name,
            "property_name": "Test Property",
            "client_name": "Test Client"
        })
        sr.insert(ignore_permissions=True)
        print(f"  ✅ Created test Service Request: {sr.name}")

if __name__ == "__main__":
    success = test_permission_setup()
    
    if success:
        # Create test data for manual testing
        try:
            create_test_data()
        except Exception as e:
            print(f"⚠️ Could not create test data: {e}")
    
    print("\n🏁 Test completed")
