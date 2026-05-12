import frappe
from frappe.model.document import Document

class Customers(Document):
	def validate(self):
		"""Validate customer data before saving"""
		if self.customer_code and self.customer_name:
			# Check for duplicate customer code
			duplicate = frappe.db.exists("Customers", {
				"customer_code": self.customer_code,
				"name": ["!=", self.name] if self.name else ["!=", ""]
			})
			if duplicate:
				frappe.throw(f"Customer Code '{self.customer_code}' already exists")
		
		# Validate email format if provided
		if self.email:
			import re
			email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
			if not re.match(email_pattern, self.email):
				frappe.throw("Please enter a valid email address")
	
	def before_save(self):
		"""Auto-generate customer code if not provided"""
		if not self.customer_code and self.customer_name:
			# Generate customer code from name
			base_code = self.customer_name.upper().replace(" ", "_")[:8]
			counter = 1
			customer_code = base_code
			
			# Ensure uniqueness
			while frappe.db.exists("Customers", {"customer_code": customer_code}):
				customer_code = f"{base_code}_{counter}"
				counter += 1
			
			self.customer_code = customer_code
	
	def on_update(self):
		"""Handle post-update operations"""
		pass
	
	def on_trash(self):
		"""Handle deletion cleanup"""
		# Check if customer is referenced in other documents
		references = frappe.db.count("Property", {"customer_code": self.name})
		if references > 0:
			frappe.throw(f"Cannot delete customer. Referenced in {references} properties")
		
		references = frappe.db.count("Branch", {"customer_code": self.name})
		if references > 0:
			frappe.throw(f"Cannot delete customer. Referenced in {references} branches")
		
		references = frappe.db.count("City", {"customer_code": self.name})
		if references > 0:
			frappe.throw(f"Cannot delete customer. Referenced in {references} cities")
		
		# Add checks for other doctypes as needed
		for doctype in ["Area Group", "Area", "Zone", "Sub Zone", "Base Unit"]:
			references = frappe.db.count(doctype, {"customer_code": self.name})
			if references > 0:
				frappe.throw(f"Cannot delete customer. Referenced in {references} {doctype.lower()}(s)")

@frappe.whitelist()
def get_customer_options(doctype=None, txt="", searchfield="customer_name"):
	"""Get customer options for autocomplete"""
	filters = {"is_active": 1}
	if txt:
		filters["customer_name"] = ["like", f"%{txt}%"]
	
	return frappe.db.get_all("Customers", 
		filters=filters,
		fields=["name", "customer_code", "customer_name"],
		limit=20
	)

@frappe.whitelist()
def get_customer_hierarchy(customer_code):
	"""Get complete hierarchy for a customer"""
	result = {
		"customer": frappe.db.get_value("Customers", customer_code, ["customer_name", "contact_person", "phone", "email"]),
		"cities": frappe.db.get_all("City", {"customer_code": customer_code}, ["name", "city_name", "city_code"]),
		"branches": frappe.db.get_all("Branch", {"customer_code": customer_code}, ["name", "branch_name", "branch_code"]),
		"area_groups": frappe.db.get_all("Area Group", {"customer_code": customer_code}, ["name", "area_group_name", "area_group_code"]),
		"areas": frappe.db.get_all("Area", {"customer_code": customer_code}, ["name", "area_name", "area_code"]),
		"properties": frappe.db.get_all("Property", {"customer_code": customer_code}, ["name", "property_name", "property_code"]),
		"zones": frappe.db.get_all("Zone", {"customer_code": customer_code}, ["name", "zone_name", "zone_code"]),
		"sub_zones": frappe.db.get_all("Sub Zone", {"customer_code": customer_code}, ["name", "sub_zone_name", "sub_zone_code"]),
		"base_units": frappe.db.get_all("Base Unit", {"customer_code": customer_code}, ["name", "base_unit_name", "base_unit_code"])
	}
	return result
