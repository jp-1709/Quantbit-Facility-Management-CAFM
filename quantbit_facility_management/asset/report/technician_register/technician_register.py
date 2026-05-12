# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"label": "Employee ID",
			"fieldname": "staff_code",
			"fieldtype": "Link",
			"options": "Resource",
			"width": 120
		},
		{
			"label": "Technician Name",
			"fieldname": "resource_name",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": "Site",
			"fieldname": "primary_area_group",
			"fieldtype": "Link",
			"options": "Area Group",
			"width": 120
		},
		{
			"label": "Contract",
			"fieldname": "contract_title",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Skill Type",
			"fieldname": "designation",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Shift",
			"fieldname": "shift",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": "Status",
			"fieldname": "is_active",
			"fieldtype": "Data",
			"width": 80
		},
		{
			"label": "Availability",
			"fieldname": "availability",
			"fieldtype": "Data",
			"width": 100
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	# Main query to get technicians
	query = """
		SELECT 
			r.staff_code,
			r.resource_name,
			r.primary_area_group,
			r.designation,
			r.shift,
			r.is_active,
			COALESCE(fc.contract_title, '') as contract_title,
			'' as availability
		FROM `tabResource` r
		LEFT JOIN `tabWork Orders` wo ON r.name = wo.assigned_to
		LEFT JOIN `tabFM Contract` fc ON wo.contract_code = fc.name
		WHERE 1=1
		{conditions}
		GROUP BY r.staff_code, r.resource_name, r.primary_area_group, r.designation, r.shift, r.is_active, fc.contract_title
		ORDER BY r.staff_code
	""".format(conditions=conditions)
	
	data = frappe.db.sql(query, as_dict=True)
	
	# For each technician, check availability in the selected period
	for row in data:
		availability = check_technician_availability(row['staff_code'], filters)
		row['availability'] = availability
		
		# Convert is_active to readable format
		row['is_active'] = 'Active' if row['is_active'] == 1 else 'Inactive'
	
	return data


def check_technician_availability(staff_code, filters):
	# Check if technician is assigned to any active work order
	wo_query = """
		SELECT COUNT(*) as assigned_count
		FROM `tabWork Orders`
		WHERE assigned_to = (
			SELECT name FROM `tabResource` WHERE staff_code = %s
		)
		AND docstatus = 1
		AND status NOT IN ('Completed', 'Cancelled')
	"""
	
	result = frappe.db.sql(wo_query, staff_code, as_dict=True)
	
	if result and result[0]['assigned_count'] > 0:
		return "No"  # Not available (assigned to active work orders)
	else:
		return "Yes"  # Available


def get_conditions(filters):
	conditions = []
	
	if filters.get("staff_code"):
		conditions.append("staff_code = '{0}'".format(filters.get("staff_code")))
	
	if filters.get("primary_area_group"):
		conditions.append("primary_area_group = '{0}'".format(filters.get("primary_area_group")))
	
	if filters.get("designation"):
		conditions.append("designation = '{0}'".format(filters.get("designation")))
	
	if filters.get("shift"):
		conditions.append("shift = '{0}'".format(filters.get("shift")))
	
		
	return "AND " + " AND ".join(conditions) if conditions else ""
