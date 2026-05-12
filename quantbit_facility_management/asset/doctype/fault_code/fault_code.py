# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FaultCode(Document):
    def validate(self):
        """Validate fault code"""
        # Check if service group exists and is active
        if self.service_group:
            if not frappe.db.exists("Service Group", {"name": self.service_group, "is_active": 1}):
                frappe.throw("Selected Service Group is not active or does not exist")
        
        # Check if fault category exists and is active
        if self.fault_category:
            category_doc = frappe.db.get_value("Fault Category", self.fault_category, ["is_active", "service_group"], as_dict=True)
            if not category_doc or not category_doc.is_active:
                frappe.throw("Selected Fault Category is not active or does not exist")
            
            # Validate service group consistency
            if category_doc.service_group and category_doc.service_group != self.service_group:
                frappe.throw(f"Service Group mismatch. Fault Category '{self.fault_category}' belongs to Service Group '{category_doc.service_group}'")
        
        # Check if fault name exists and is active
        if self.fault_name:
            name_doc = frappe.db.get_value("Fault Name", self.fault_name, ["is_active", "fault_category", "service_group"], as_dict=True)
            if not name_doc or not name_doc.is_active:
                frappe.throw("Selected Fault Name is not active or does not exist")
            
            # Validate fault category consistency
            if name_doc.fault_category and name_doc.fault_category != self.fault_category:
                frappe.throw(f"Fault Category mismatch. Fault Name '{self.fault_name}' belongs to Fault Category '{name_doc.fault_category}'")
            
            # Validate service group consistency
            if name_doc.service_group and name_doc.service_group != self.service_group:
                frappe.throw(f"Service Group mismatch. Fault Name '{self.fault_name}' belongs to Service Group '{name_doc.service_group}'")
        
        # Check for duplicate fault code
        existing = frappe.db.exists("Fault Code", {
            "fault_code": self.fault_code,
            "name": ("!=", self.name) if self.name else ("!=", "")
        })
        if existing:
            frappe.throw(f"Fault Code '{self.fault_code}' already exists")

    def on_update(self):
        """Update cascading fields"""
        # Auto-set service group and fault category from fault name if not set
        if self.fault_name and (not self.service_group or not self.fault_category):
            name_doc = frappe.db.get_value("Fault Name", self.fault_name, ["fault_category", "service_group"], as_dict=True)
            if name_doc:
                if name_doc.service_group and not self.service_group:
                    self.service_group = name_doc.service_group
                if name_doc.fault_category and not self.fault_category:
                    self.fault_category = name_doc.fault_category
                self.db_update()


@frappe.whitelist()
def get_fault_codes(service_group=None, fault_category=None, fault_name=None):
    """Get fault codes based on filters"""
    filters = {"is_active": 1}
    
    if service_group:
        filters["service_group"] = service_group
    if fault_category:
        filters["fault_category"] = fault_category
    if fault_name:
        filters["fault_name"] = fault_name
    
    return frappe.db.get_all("Fault Code",
        filters=filters,
        fields=["name", "fault_code", "fault_description", "service_group", "fault_category", "fault_name", "default_priority"],
        order_by="fault_code"
    )
