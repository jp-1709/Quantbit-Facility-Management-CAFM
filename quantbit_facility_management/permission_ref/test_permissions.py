#!/usr/bin/env python3
"""
Test script to verify permission system configuration
"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_permissions_config():
    """Test the permissions configuration"""
    print("🔍 Testing Facility Management Permission System")
    print("=" * 50)
    
    # Test 1: Check if permissions.py exists and has required functions
    try:
        import permissions
        print("✅ permissions.py loaded successfully")
        
        required_functions = [
            'get_highest_facility_role',
            'get_resource_record', 
            'get_user_branch',
            'work_order_query_conditions',
            'service_request_query_conditions',
            'has_work_order_permission',
            'has_service_request_permission'
        ]
        
        for func_name in required_functions:
            if hasattr(permissions, func_name):
                print(f"✅ Function {func_name} found")
            else:
                print(f"❌ Function {func_name} missing")
                
    except ImportError as e:
        print(f"❌ Failed to import permissions.py: {e}")
        return False
    
    # Test 2: Check role constants
    try:
        roles = [
            permissions.ROLE_SUPER_ADMIN,
            permissions.ROLE_ADMIN,
            permissions.ROLE_BRANCH_MANAGER,
            permissions.ROLE_SUPERVISOR,
            permissions.ROLE_TECHNICIAN
        ]
        print(f"✅ Role constants defined: {roles}")
    except AttributeError as e:
        print(f"❌ Role constants missing: {e}")
    
    # Test 3: Check hooks.py configuration
    try:
        import hooks
        print("✅ hooks.py loaded successfully")
        
        if hasattr(hooks, 'permission_query_conditions'):
            conditions = hooks.permission_query_conditions
            print(f"✅ Permission query conditions configured for: {list(conditions.keys())}")
        else:
            print("❌ permission_query_conditions not found in hooks.py")
            
    except ImportError as e:
        print(f"❌ Failed to import hooks.py: {e}")
    
    # Test 4: Check install.py configuration
    try:
        import install
        print("✅ install.py loaded successfully")
        
        if hasattr(install, 'FACILITY_ROLES'):
            print(f"✅ Facility roles defined: {[r['role_name'] for r in install.FACILITY_ROLES]}")
        else:
            print("❌ FACILITY_ROLES not found in install.py")
            
    except ImportError as e:
        print(f"❌ Failed to import install.py: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 Permission system test completed")
    return True

if __name__ == "__main__":
    test_permissions_config()
