# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"label": "Request No",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Service Request",
			"width": 120
		},
		{
			"label": "Date",
			"fieldname": "raised_date",
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
			"label": "Site",
			"fieldname": "property_name",
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
			"label": "Department",
			"fieldname": "service_group",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Raised By",
			"fieldname": "reported_by",
			"fieldtype": "Data",
			"width": 140
		},
		{
			"label": "Request Type",
			"fieldname": "initiator_type",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Priority",
			"fieldname": "priority_actual",
			"fieldtype": "Data",
			"width": 80
		},
		{
			"label": "Assigned To",
			"fieldname": "assigned_to",
			"fieldtype": "Data",
			"width": 140
		},
		{
			"label": "Status",
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": "Closure Time",
			"fieldname": "closure_time",
			"fieldtype": "Time",
			"width": 100
		},
		{
			"label": "Feedback",
			"fieldname": "remarks",
			"fieldtype": "Data",
			"width": 200
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	# Main query to get service requests
	query = """
		SELECT 
			sr.name,
			sr.raised_date,
			COALESCE(c.client_name, '') as client_name,
			COALESCE(p.property_name, '') as property_name,
			COALESCE(fc.contract_title, '') as contract_title,
			sr.service_group,
			sr.reported_by,
			sr.initiator_type,
			sr.priority_actual,
			sr.status,
			sr.remarks,
			'' as assigned_to,
			'' as closure_time
		FROM `tabService Request` sr
		LEFT JOIN `tabProperty` p ON sr.property_code = p.name
		LEFT JOIN `tabClient` c ON sr.client_code = c.name
		LEFT JOIN `tabWork Orders` wo ON sr.name = wo.sr_number
		LEFT JOIN `tabFM Contract` fc ON wo.contract_code = fc.name
		WHERE sr.docstatus IN (0, 1)
		{conditions}
		ORDER BY sr.raised_date DESC
	""".format(conditions=conditions)
	
	data = frappe.db.sql(query, as_dict=True)
	
	# For each service request, get assigned technicians from work orders
	for row in data:
		# Get assigned technicians from work orders
		wo_query = """
			SELECT DISTINCT assigned_to, schedule_start_time, schedule_end_time
			FROM `tabWork Orders`
			WHERE sr_number = %s AND docstatus IN (0, 1)
				AND assigned_to IS NOT NULL
		"""
		
		wo_results = frappe.db.sql(wo_query, row['name'], as_dict=True)
		
		if wo_results:
			# If multiple work orders, concatenate assigned technicians
			assigned_techs = []
			closure_times = []
			
			for wo in wo_results:
				if wo.assigned_to:
					# Get resource name
					resource_name = frappe.db.get_value("Resource", wo.assigned_to, "resource_name")
					if resource_name:
						assigned_techs.append(resource_name)
				
				# Use schedule_end_time as closure time
				if wo.schedule_end_time:
					closure_times.append(str(wo.schedule_end_time))
			
			row['assigned_to'] = ", ".join(assigned_techs) if assigned_techs else ""
			row['closure_time'] = ", ".join(closure_times) if closure_times else ""
		else:
			# If no work orders, leave closure time empty
			row['assigned_to'] = ""
			row['closure_time'] = ""
	
	return data


def get_conditions(filters):
	conditions = []
	
	if filters.get("sr_number"):
		conditions.append("sr.name = '{0}'".format(filters.get("sr_number")))
	
	if filters.get("client_code"):
		conditions.append("sr.client_code = '{0}'".format(filters.get("client_code")))
	
	if filters.get("property_code"):
		conditions.append("sr.property_code = '{0}'".format(filters.get("property_code")))
	
	if filters.get("service_group"):
		conditions.append("sr.service_group = '{0}'".format(filters.get("service_group")))
	
	if filters.get("initiator_type"):
		conditions.append("sr.initiator_type = '{0}'".format(filters.get("initiator_type")))
	
	if filters.get("priority_actual"):
		conditions.append("sr.priority_actual = '{0}'".format(filters.get("priority_actual")))
	
	if filters.get("status"):
		conditions.append("sr.status = '{0}'".format(filters.get("status")))
	
	if filters.get("from_date"):
		conditions.append("DATE(sr.creation) >= '{0}'".format(filters.get("from_date")))
	
	if filters.get("to_date"):
		conditions.append("DATE(sr.creation) <= '{0}'".format(filters.get("to_date")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""
