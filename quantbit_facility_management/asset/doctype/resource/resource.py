# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Resource(Document):
	def validate(self):
		self.auto_fill_supervised_technicians()
	
	@frappe.whitelist()
	def auto_fill_supervised_technicians(self):
		"""Auto-fill supervised technicians child table when designation is Supervisor"""
		if self.designation == "Supervisor" and self.get("staff_code"):
			# Clear existing technicians to avoid duplicates
			self.set("technicians", [])
			
			# Fetch all technicians who have this supervisor as their supervisor_code
			technicians = frappe.db.get_all("Resource", 
				filters={
					"supervisor_code": self.staff_code,
					"designation": ["!=", "Supervisor"],
					"is_active": 1
				},
				fields=["staff_code", "resource_name", "designation", "is_active"]
			)
			
			# Add technicians to child table
			for tech in technicians:
				self.append("technicians", {
					"staff_code": tech.staff_code,
					"resource_name": tech.resource_name
				})
			
			return self.technicians
	
	@frappe.whitelist()
	def get_supervised_technicians(self):
		"""Get list of supervised technicians for this supervisor"""
		if self.designation != "Supervisor":
			return []
			
		return frappe.db.get_all("Resource",
			filters={
				"supervisor_code": self.staff_code,
				"designation": ["!=", "Supervisor"]
			},
			fields=["staff_code", "resource_name", "designation", "department", 
					"phone", "email", "is_active", "branch_code"]
		)


