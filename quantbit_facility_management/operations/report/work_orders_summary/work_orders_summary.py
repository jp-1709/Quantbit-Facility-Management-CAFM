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
			"label": "Site",
			"fieldname": "property_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Branch",
			"fieldname": "branch_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Total Work Order",
			"fieldname": "total_wo",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Closed WO",
			"fieldname": "closed_wo",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Overdue WO",
			"fieldname": "overdue_wo",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Emergency WO",
			"fieldname": "emergency_wo",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "SLA %",
			"fieldname": "sla_percentage",
			"fieldtype": "Float",
			"width": 80
		},
		{
			"label": "Avg TAT",
			"fieldname": "avg_tat",
			"fieldtype": "Float",
			"width": 80
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	# Main query to get grouped data
	query = """
		SELECT 
			COALESCE(c.client_name, '') as client_name,
			wo.branch_code,
			COALESCE(wo.branch_name, '') as branch_name,
			wo.property_code,
			COALESCE(p.property_name, '') as property_name,
			COUNT(*) as total_wo,
			SUM(CASE WHEN wo.status IN ('Completed', 'Closed') THEN 1 ELSE 0 END) as closed_wo,
			SUM(CASE 
				WHEN wo.status NOT IN ('Completed', 'Closed') 
					AND wo.schedule_start_date < CURDATE() 
				THEN 1 ELSE 0 END) as overdue_wo,
			SUM(CASE WHEN wo.default_priority = 'P1 - Critical' THEN 1 ELSE 0 END) as emergency_wo,
			0 as sla_percentage,
			0 as avg_tat
		FROM `tabWork Orders` wo
		LEFT JOIN `tabClient` c ON wo.client_code = c.name
		LEFT JOIN `tabProperty` p ON wo.property_code = p.name
		WHERE wo.docstatus = 1
			{conditions}
		GROUP BY c.client_name, wo.branch_code, wo.branch_name, wo.property_code, p.property_name
		ORDER BY c.client_name, wo.branch_code, wo.property_code
	""".format(conditions=conditions)
	
	data = frappe.db.sql(query, as_dict=True)
	
	# Calculate SLA percentage and Avg TAT for each group
	for row in data:
		# Skip if essential fields are missing
		if not row.get('client_name') or not row.get('property_code'):
			continue
			
		# Calculate SLA percentage: (No. of Work Orders within SLA / Total Work Orders) × 100
		sla_query = """
			SELECT 
				COUNT(*) as total_count,
				SUM(CASE WHEN DATE(wo.resolution_sla_actual) <= DATE(wo.resolution_sla_target) THEN 1 ELSE 0 END) as within_sla_count
			FROM `tabWork Orders` wo
			LEFT JOIN `tabClient` c ON wo.client_code = c.name
			WHERE c.client_name = %s 
				AND wo.property_code = %s
				AND wo.docstatus = 1
				AND wo.resolution_sla_target IS NOT NULL 
				AND wo.resolution_sla_actual IS NOT NULL
				{conditions}
		""".format(conditions=conditions.replace("c.client_name =", "client_name =").replace("wo.property_code =", "property_code ="))
		
		sla_result = frappe.db.sql(sla_query, (row.get('client_name'), row.get('property_code')), as_dict=True)
		
		if sla_result and sla_result[0]['total_count'] > 0:
			row['sla_percentage'] = round((sla_result[0]['within_sla_count'] / sla_result[0]['total_count']) * 100, 2)
		else:
			row['sla_percentage'] = 0
		
		# Calculate Average TAT: actual start – actual end
		tat_query = """
			SELECT AVG(TIMESTAMPDIFF(HOUR, wo.actual_start, wo.actual_end)) as avg_tat_hours
			FROM `tabWork Orders` wo
			LEFT JOIN `tabClient` c ON wo.client_code = c.name
			WHERE c.client_name = %s 
				AND wo.property_code = %s
				AND wo.docstatus = 1
				AND wo.actual_start IS NOT NULL 
				AND wo.actual_end IS NOT NULL
				{conditions}
		""".format(conditions=conditions.replace("c.client_name =", "client_name =").replace("wo.property_code =", "property_code ="))
		
		tat_result = frappe.db.sql(tat_query, (row.get('client_name'), row.get('property_code')), as_dict=True)
		
		if tat_result and tat_result[0]['avg_tat_hours']:
			row['avg_tat'] = round(tat_result[0]['avg_tat_hours'], 2)
		else:
			row['avg_tat'] = 0
	
	return data


def get_conditions(filters):
	conditions = []
	
	# Ensure filters is a dictionary
	filters = filters or {}
	
	try:
		if filters.get("client_name"):
			conditions.append("c.client_name = '{}'".format(filters.get("client_name")))
		
		if filters.get("property_code"):
			conditions.append("wo.property_code = '{}'".format(filters.get("property_code")))
		
		if filters.get("branch_code"):
			conditions.append("wo.branch_code = '{}'".format(filters.get("branch_code")))
		
		if filters.get("from_date"):
			conditions.append("DATE(wo.creation) >= '{}'".format(filters.get("from_date")))
		
		if filters.get("to_date"):
			conditions.append("DATE(wo.creation) <= '{}'".format(filters.get("to_date")))
	except Exception as e:
		frappe.errprint(f"Error in get_conditions: {e}")
	
	return "AND " + " AND ".join(conditions) if conditions else ""