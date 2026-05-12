# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"label": "WO No",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Work Orders",
			"width": 120
		},
		{
			"label": "WO Date",
			"fieldname": "schedule_start_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": "Client",
			"fieldname": "client_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Contract",
			"fieldname": "contract_title",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Branch",
			"fieldname": "branch",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": "Site",
			"fieldname": "property_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Category",
			"fieldname": "fault_category",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Asset Name",
			"fieldname": "asset_code",
			"fieldtype": "Link",
			"options": "CFAM Asset",
			"width": 120
		},
		{
			"label": "Priority",
			"fieldname": "default_priority",
			"fieldtype": "Data",
			"width": 80
		},
		{
			"label": "Assigned Technician",
			"fieldname": "assigned_to",
			"fieldtype": "Link",
			"options": "Resource",
			"width": 140
		},
		{
			"label": "Work Done Notes",
			"fieldname": "work_done_notes",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": "Status",
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": "Open Time",
			"fieldname": "schedule_start_time",
			"fieldtype": "Time",
			"width": 100
		},
		{
			"label": "Completion Time",
			"fieldname": "schedule_end_time",
			"fieldtype": "Time",
			"width": 100
		},
		{
			"label": "Resolution Hours",
			"fieldname": "resolution_hours",
			"fieldtype": "Float",
			"width": 100
		},
		{
			"label": "SLA Target Date",
			"fieldname": "resolution_sla_target",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": "SLA Met",
			"fieldname": "sla_met",
			"fieldtype": "Data",
			"width": 80
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	query = """
		SELECT 
			wo.wo_number as name,
			wo.wo_title,
			COALESCE(fc.contract_title, '') as contract_title,
			COALESCE(c.client_name, '') as client_name,
			wo.branch_code,
			COALESCE(wo.branch_name, '') as branch,
			COALESCE(p.property_name, '') as property_name,
			wo.fault_category,
			wo.asset_code,
			wo.default_priority,
			wo.assigned_to,
			wo.schedule_start_date,
			wo.schedule_start_time,
			wo.schedule_end_time,
			wo.resolution_sla_target,
			wo.resolution_sla_actual,
			wo.actual_start,
			wo.actual_end,
			CASE 
				WHEN DATE(wo.resolution_sla_actual) IS NOT NULL 
					AND DATE(wo.resolution_sla_target) IS NOT NULL
					AND DATE(wo.resolution_sla_actual) <= DATE(wo.resolution_sla_target) 
				THEN 'Fulfilled' 
				WHEN DATE(wo.resolution_sla_actual) IS NOT NULL 
					AND DATE(wo.resolution_sla_target) IS NOT NULL
					AND DATE(wo.resolution_sla_actual) > DATE(wo.resolution_sla_target) 
				THEN 'Failed' 
				ELSE '' 
			END as sla_met,
			wo.status,
			wo.work_done_notes
		FROM `tabWork Orders` wo
		LEFT JOIN `tabProperty` p ON wo.property_code = p.name
		LEFT JOIN `tabClient` c ON wo.client_code = c.name
		LEFT JOIN `tabFM Contract` fc ON wo.contract_code = fc.name
		WHERE wo.docstatus = 1
		{conditions}
		ORDER BY wo.wo_number DESC
	""".format(conditions=conditions)
	
	# Debug: Log the actual query
	frappe.errprint(f"DEBUG - Work Orders Register Query: {query}")
	
	data = frappe.db.sql(query, as_dict=True)
	return data


def get_conditions(filters):
	conditions = []
	
	if filters.get("wo_no"):
		conditions.append("wo.name = '{0}'".format(filters.get("wo_no")))
	
	if filters.get("client_code"):
		conditions.append("wo.client_code = '{0}'".format(filters.get("client_code")))
	
	if filters.get("contract_code"):
		conditions.append("wo.contract_code = '{0}'".format(filters.get("contract_code")))
	
	if filters.get("branch_code"):
		conditions.append("wo.branch_code = '{0}'".format(filters.get("branch_code")))
	
	if filters.get("property_code"):
		conditions.append("wo.property_code = '{0}'".format(filters.get("property_code")))
	
	if filters.get("fault_category"):
		conditions.append("wo.fault_category = '{0}'".format(filters.get("fault_category")))
	
	if filters.get("asset_code"):
		conditions.append("wo.asset_code = '{0}'".format(filters.get("asset_code")))
	
	if filters.get("default_priority"):
		conditions.append("wo.default_priority = '{0}'".format(filters.get("default_priority")))
	
	if filters.get("assigned_to"):
		conditions.append("wo.assigned_to = '{0}'".format(filters.get("assigned_to")))
	
	if filters.get("status"):
		conditions.append("wo.status = '{0}'".format(filters.get("status")))
	
	if filters.get("from_date"):
		conditions.append("DATE(wo.creation) >= '{0}'".format(filters.get("from_date")))
	
	if filters.get("to_date"):
		conditions.append("DATE(wo.creation) <= '{0}'".format(filters.get("to_date")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""
