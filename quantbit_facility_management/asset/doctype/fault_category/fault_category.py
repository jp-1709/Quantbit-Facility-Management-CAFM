import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname

class FaultCategory(Document):
    def validate(self):
        validate(self, "validate")

def validate(doc, method):
    """Validate fault category"""
    # Check if service group exists and is active
    if doc.service_group:
        if not frappe.db.exists("Service Group", {"name": doc.service_group, "is_active": 1}):
            frappe.throw("Selected Service Group is not active or does not exist")
    
    # Check for duplicate fault category under same service group
    existing = frappe.db.exists("Fault Category", {
        "fault_category_name": doc.fault_category_name,
        "service_group": doc.service_group,
        "name": ("!=", doc.name) if doc.name else ("!=", "")
    })
    if existing:
        frappe.throw(f"Fault Category '{doc.fault_category_name}' already exists under Service Group '{doc.service_group}'")

def on_update(self, method):
    """Update related fault names when service group changes"""
    if self.has_value_changed("service_group") and self.service_group:
        # Update service_group in related fault names
        frappe.db.sql("""
            UPDATE `tabFault Name`
            SET service_group = %s
            WHERE fault_category = %s
        """, (self.service_group, self.name))
        
        # Update service_group in related fault codes
        frappe.db.sql("""
            UPDATE `tabFault Code`
            SET service_group = %s
            WHERE fault_category = %s
        """, (self.service_group, self.name))

def get_fault_categories(service_group):
    """Get fault categories for a given service group"""
    if not service_group:
        return []
    
    return frappe.db.get_all("Fault Category",
        filters={"service_group": service_group, "is_active": 1},
        fields=["name", "fault_category_name"],
        order_by="fault_category_name"
    )
