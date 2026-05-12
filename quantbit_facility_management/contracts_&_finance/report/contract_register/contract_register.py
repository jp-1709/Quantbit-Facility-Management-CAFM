# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"label": "Contract No",
			"fieldname": "contract_code",
			"fieldtype": "Link",
			"options": "FM Contract",
			"width": 120
		},
		{
			"label": "Client",
			"fieldname": "client_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Site",
			"fieldname": "property_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Contract Name",
			"fieldname": "contract_title",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": "Start Date",
			"fieldname": "start_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": "End Date",
			"fieldname": "end_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": "Billing Cycle",
			"fieldname": "billing_model",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Contract Value",
			"fieldname": "annual_value",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "Status",
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	query = """
		SELECT 
			fc.contract_code,
			fc.contract_title,
			COALESCE((SELECT client_name FROM `tabClient` WHERE name = fc.client_code LIMIT 1), '') as client_name,
			fc.start_date,
			fc.end_date,
			fc.billing_model,
			fc.annual_value,
			fc.status
		FROM `tabFM Contract` fc
		WHERE fc.docstatus = 1
		{conditions}
		ORDER BY fc.contract_code
	""".format(conditions=conditions)
	
	data = frappe.db.sql(query, as_dict=True)
	return data


def get_conditions(filters):
	conditions = []
	
	if filters.get("contract_code"):
		conditions.append("fc.contract_code = '{0}'".format(filters.get("contract_code")))
	
	if filters.get("client_code"):
		conditions.append("fc.client_code = '{0}'".format(filters.get("client_code")))
	
	if filters.get("status"):
		conditions.append("fc.status = '{0}'".format(filters.get("status")))
	
	if filters.get("from_date"):
		conditions.append("DATE(fc.creation) >= '{0}'".format(filters.get("from_date")))
	
	if filters.get("to_date"):
		conditions.append("DATE(fc.creation) <= '{0}'".format(filters.get("to_date")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""
