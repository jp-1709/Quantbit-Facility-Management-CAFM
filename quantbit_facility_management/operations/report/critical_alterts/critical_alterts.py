# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "name",
			"label": "WO Number",
			"fieldtype": "Link",
			"options": "Work Orders",
			"width": 120
		},
		{
			"fieldname": "wo_title",
			"label": "WO Title",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "client_name",
			"label": "Client",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "property_name",
			"label": "Property",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "asset_name",
			"label": "Asset",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "fault_category",
			"label": "Fault Category",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "actual_priority",
			"label": "Priority",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "assigned_technician",
			"label": "Assigned Technician",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "schedule_start_date",
			"label": "Scheduled Start",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"fieldname": "response_sla_target",
			"label": "Response SLA Target",
			"fieldtype": "Datetime",
			"width": 150
		},
		{
			"fieldname": "response_sla_breach",
			"label": "Response SLA Breached",
			"fieldtype": "Check",
			"width": 100
		}
	]


def get_data(filters):
	conditions = get_conditions(filters)
	
	# Debug: Check if any work orders exist at all (both draft and submitted)
	all_wo_count = frappe.db.count("Work Orders")
	open_wo_count = frappe.db.count("Work Orders", {"status": "Open"})
	critical_wo_count = frappe.db.count("Work Orders", {"status": "Open", "actual_priority": "P1 - Critical"})
	
	frappe.errprint(f"DEBUG - All WOs (draft + submitted): {all_wo_count}")
	frappe.errprint(f"DEBUG - Open WOs (draft + submitted): {open_wo_count}")
	frappe.errprint(f"DEBUG - Open Critical WOs (draft + submitted): {critical_wo_count}")
	
	data = frappe.db.sql("""
		SELECT 
			wo.name,
			wo.wo_title,
			COALESCE(c.client_name, '') as client_name,
			COALESCE(p.property_name, '') as property_name,
			COALESCE(wo.asset_name, '') as asset_name,
			wo.fault_category,
			wo.actual_priority,
			COALESCE(wo.assigned_technician, '') as assigned_technician,
			wo.schedule_start_date,
			wo.response_sla_target,
			wo.response_sla_breach
		FROM `tabWork Orders` wo
		LEFT JOIN `tabProperty` p ON wo.property_code = p.name
		LEFT JOIN `tabClient` c ON wo.client_code = c.name
		WHERE wo.status = 'Open' 
		AND wo.actual_priority = 'P1 - Critical'
		{conditions}
		ORDER BY wo.response_sla_target ASC, wo.creation DESC
	""".format(conditions=conditions), as_dict=True)
	
	# Debug: Log the actual query and result count
	frappe.errprint(f"DEBUG - Critical Alerts Query executed")
	frappe.errprint(f"DEBUG - Result count: {len(data) if data else 0}")
	
	return data


def get_conditions(filters):
	conditions = ""
	
	if filters.get("client_code"):
		conditions += " AND wo.client_code = %(client_code)s"
	
	if filters.get("property_code"):
		conditions += " AND wo.property_code = %(property_code)s"
	
	if filters.get("assigned_to"):
		conditions += " AND wo.assigned_to = %(assigned_to)s"
	
	if filters.get("from_date"):
		conditions += " AND wo.schedule_start_date >= %(from_date)s"
	
	if filters.get("to_date"):
		conditions += " AND wo.schedule_start_date <= %(to_date)s"
	
	return conditions
