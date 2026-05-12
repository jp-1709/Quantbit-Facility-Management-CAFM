# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WorkOrders(Document):
    def validate(self):
        """Validate work order with fault cascading"""
        # Validate fault hierarchy consistency
        if self.fault_code:
            fault_doc = frappe.db.get_value("Fault Code", self.fault_code, 
                ["service_group", "fault_category", "fault_name", "default_priority"], as_dict=True)
            if not fault_doc:
                frappe.throw(f"Fault Code '{self.fault_code}' does not exist")
            
            # Validate service group consistency
            if fault_doc.service_group and self.service_group and fault_doc.service_group != self.service_group:
                frappe.throw(f"Service Group mismatch. Fault Code '{self.fault_code}' belongs to Service Group '{fault_doc.service_group}'")
            
            # Validate fault category consistency
            if fault_doc.fault_category and self.fault_category and fault_doc.fault_category != self.fault_category:
                frappe.throw(f"Fault Category mismatch. Fault Code '{self.fault_code}' belongs to Fault Category '{fault_doc.fault_category}'")
            
            # Validate fault name consistency
            if fault_doc.fault_name and self.fault_name and fault_doc.fault_name != self.fault_name:
                frappe.throw(f"Fault Name mismatch. Fault Code '{self.fault_code}' belongs to Fault Name '{fault_doc.fault_name}'")
            
            # Auto-set default priority if not set
            if fault_doc.default_priority and not self.default_priority:
                self.default_priority = fault_doc.default_priority
        
        # Validate fault category if set
        if self.fault_category:
            category_doc = frappe.db.get_value("Fault Category", self.fault_category, ["service_group"], as_dict=True)
            if not category_doc:
                frappe.throw(f"Fault Category '{self.fault_category}' does not exist")
            
            # Validate service group consistency
            if category_doc.service_group and self.service_group and category_doc.service_group != self.service_group:
                frappe.throw(f"Service Group mismatch. Fault Category '{self.fault_category}' belongs to Service Group '{category_doc.service_group}'")
        
        # Validate fault name if set
        if self.fault_name:
            name_doc = frappe.db.get_value("Fault Name", self.fault_name, 
                ["fault_category", "service_group"], as_dict=True)
            if not name_doc:
                frappe.throw(f"Fault Name '{self.fault_name}' does not exist")
            
            # Validate fault category consistency
            if name_doc.fault_category and self.fault_category and name_doc.fault_category != self.fault_category:
                frappe.throw(f"Fault Category mismatch. Fault Name '{self.fault_name}' belongs to Fault Category '{name_doc.fault_category}'")
            
            # Validate service group consistency
            if name_doc.service_group and self.service_group and name_doc.service_group != self.service_group:
                frappe.throw(f"Service Group mismatch. Fault Name '{self.fault_name}' belongs to Service Group '{name_doc.service_group}'")
        
        # Auto-cascade fault hierarchy from fault code if other fields are not set
        if self.fault_code and (not self.service_group or not self.fault_category or not self.fault_name):
            fault_doc = frappe.db.get_value("Fault Code", self.fault_code, 
                ["service_group", "fault_category", "fault_name"], as_dict=True)
            if fault_doc:
                if fault_doc.service_group and not self.service_group:
                    self.service_group = fault_doc.service_group
                if fault_doc.fault_category and not self.fault_category:
                    self.fault_category = fault_doc.fault_category
                if fault_doc.fault_name and not self.fault_name:
                    self.fault_name = fault_doc.fault_name


@frappe.whitelist()
def update_service_request(sr_number, wo_number, status):
    """
    Update Service Request when converted to Work Order
    """
    try:
        # Validate service request exists
        if not frappe.db.exists("Service Request", sr_number):
            frappe.throw(f"Service Request {sr_number} not found")
        
        # Update service request
        frappe.db.set_value("Service Request", sr_number, {
            "converted_to_wo": 1,
            "status": "Converted" if status in ["Open", "Assigned", "In Progress"] else status
        })
        
        # Add comment to service request
        sr_doc = frappe.get_doc("Service Request", sr_number)
        sr_doc.add_comment("Comment", f"Converted to Work Order: {wo_number}")
        
        return {"status": "success", "message": "Service Request updated successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error updating Service Request {sr_number}: {str(e)}", "Service Request Update Error")
        frappe.throw(f"Failed to update Service Request: {str(e)}")
