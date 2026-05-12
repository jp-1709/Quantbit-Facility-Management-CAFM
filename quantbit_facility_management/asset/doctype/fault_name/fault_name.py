import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname

class FaultName(Document):
    def validate(self):
        validate(self, "validate")

def validate(doc, method):
    """Validate fault name"""
    # Check if fault category exists and is active
    if doc.fault_category:
        category_doc = frappe.db.get_value("Fault Category", doc.fault_category, ["is_active", "service_group"], as_dict=True)
        if not category_doc or not category_doc.is_active:
            frappe.throw("Selected Fault Category is not active or does not exist")
        
        # Auto-set service group from fault category
        if category_doc.service_group and category_doc.service_group != doc.service_group:
            doc.service_group = category_doc.service_group
    
    # Check for duplicate fault name under same fault category
    existing = frappe.db.exists("Fault Name", {
        "fault_name_title": doc.fault_name_title,
        "fault_category": doc.fault_category,
        "name": ("!=", doc.name) if doc.name else ("!=", "")
    })
    if existing:
        frappe.throw(f"Fault Name '{doc.fault_name_title}' already exists under Fault Category '{doc.fault_category}'")

def on_update(self, method):
    """Update related fault codes when fault category changes"""
    if self.has_value_changed("fault_category") and self.fault_category:
        # Get service group from fault category
        service_group = frappe.db.get_value("Fault Category", self.fault_category, "service_group")
        if service_group:
            self.service_group = service_group
        
        # Update service_group and fault_category in related fault codes
        frappe.db.sql("""
            UPDATE `tabFault Code`
            SET service_group = %s, fault_category = %s
            WHERE fault_name = %s
        """, (service_group, self.fault_category, self.name))

def get_fault_names(fault_category):
    """Get fault names for a given fault category"""
    if not fault_category:
        return []
    
    return frappe.db.get_all("Fault Name",
        filters={"fault_category": fault_category, "is_active": 1},
        fields=["name", "fault_name_title", "service_group"],
        order_by="fault_name_title"
    )
