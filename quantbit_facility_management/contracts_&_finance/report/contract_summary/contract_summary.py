# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"label": "Client",
			"fieldname": "client_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Active Contracts",
			"fieldname": "active_contracts",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Monthly Revenue",
			"fieldname": "monthly_revenue",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "Annual Revenue",
			"fieldname": "annual_revenue",
			"fieldtype": "Currency",
			"width": 120
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	# Main query to get grouped data
	query = """
		SELECT 
			COALESCE((SELECT client_name FROM `tabClient` WHERE name = fc.client_code LIMIT 1), '') as client_name,
			COUNT(*) as active_contracts,
			SUM(fc.annual_value) as total_annual_value,
			SUM(fc.annual_value/12) as monthly_revenue
		FROM `tabFM Contract` fc
		WHERE fc.docstatus = 1 
			AND fc.status = 'Active'
			{conditions}
		GROUP BY fc.client_code
		ORDER BY fc.client_code
	""".format(conditions=conditions)
	
	data = frappe.db.sql(query, as_dict=True)
	return data


def get_conditions(filters):
	conditions = []
	
	if filters.get("client_code"):
		conditions.append("fc.client_code = '{0}'".format(filters.get("client_code")))
	
	if filters.get("from_date"):
		conditions.append("DATE(fc.creation) >= '{0}'".format(filters.get("from_date")))
	
	if filters.get("to_date"):
		conditions.append("DATE(fc.creation) <= '{0}'".format(filters.get("to_date")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""
