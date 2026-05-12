# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"label": "Scheduled PPM",
			"fieldname": "scheduled_ppm",
			"fieldtype": "Int",
			"width": 120
		},
		{
			"label": "Completed PPM",
			"fieldname": "completed_ppm",
			"fieldtype": "Int",
			"width": 120
		},
		{
			"label": "Percentage of Completed PPM",
			"fieldname": "percentage_completed",
			"fieldtype": "Percent",
			"width": 150
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	query = """
		SELECT 
			COUNT(*) as scheduled_ppm,
			COUNT(CASE WHEN status = 'Completed' THEN 1 END) as completed_ppm
		FROM `tabPPM Schedule`
		WHERE docstatus IN (0, 1)
		{conditions}
	""".format(conditions=conditions)
	
	data = frappe.db.sql(query, as_dict=True)
	
	# Calculate percentage
	result = []
	for row in data:
		scheduled = row.scheduled_ppm or 0
		completed = row.completed_ppm or 0
		percentage = int((completed / scheduled * 100)) if scheduled > 0 else 0
		
		result.append({
			"scheduled_ppm": scheduled,
			"completed_ppm": completed,
			"percentage_completed": percentage
		})
	
	return result


def get_conditions(filters):
	conditions = []
	
	if filters.get("property_code"):
		conditions.append("property_code = '{0}'".format(filters.get("property_code")))
	
	if filters.get("client_code"):
		conditions.append("client_code = '{0}'".format(filters.get("client_code")))
	
	if filters.get("contract_code"):
		conditions.append("contract_code = '{0}'".format(filters.get("contract_code")))
	
	if filters.get("asset_code"):
		conditions.append("asset_code = '{0}'".format(filters.get("asset_code")))
	
	if filters.get("from_date"):
		conditions.append("DATE(next_due_date) >= '{0}'".format(filters.get("from_date")))
	
	if filters.get("to_date"):
		conditions.append("DATE(next_due_date) <= '{0}'".format(filters.get("to_date")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""
