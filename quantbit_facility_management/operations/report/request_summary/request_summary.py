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
			"label": "Total Requests",
			"fieldname": "total_requests",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Closed",
			"fieldname": "closed_requests",
			"fieldtype": "Int",
			"width": 80
		},
		{
			"label": "Pending",
			"fieldname": "pending_requests",
			"fieldtype": "Int",
			"width": 80
		},
		{
			"label": "Avg Response Time",
			"fieldname": "avg_response_time",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": "Escalated Count",
			"fieldname": "escalated_count",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Satisfaction Score",
			"fieldname": "satisfaction_score",
			"fieldtype": "Float",
			"width": 120
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	# Main query to get grouped data
	query = """
		SELECT 
			sr.client_code,
			COALESCE(c.client_name, '') as client_name,
			COUNT(*) as total_requests,
			SUM(CASE WHEN sr.status IN ('Completed', 'Closed') THEN 1 ELSE 0 END) as closed_requests,
			SUM(CASE WHEN sr.status IN ('Open', 'In Progress', 'Pending') THEN 1 ELSE 0 END) as pending_requests,
			0 as avg_response_time,
			SUM(CASE WHEN sr.response_sla_status = 'Breached' THEN 1 ELSE 0 END) as escalated_count,
			0 as satisfaction_score
		FROM `tabService Request` sr
		LEFT JOIN `tabClient` c ON sr.client_code = c.name
		WHERE sr.docstatus IN (0, 1) 
			{conditions}
		GROUP BY sr.client_code, c.client_name
		ORDER BY sr.client_code
	""".format(conditions=conditions)
	
	data = frappe.db.sql(query, as_dict=True)
	
	# Calculate average response time and satisfaction score for each client
	for row in data:
		# Calculate Average Response Time (in hours)
		response_query = """
			SELECT AVG(TIMESTAMPDIFF(HOUR, raised_date, response_sla_actual)) as avg_response_hours
			FROM `tabService Request`
			WHERE client_code = %s AND docstatus IN (0, 1)
				AND raised_date IS NOT NULL 
				AND response_sla_actual IS NOT NULL
				{conditions}
		""".format(conditions=conditions.replace("sr.client_code =", "client_code =").replace("DATE(sr.creation)", "DATE(creation)"))
		
		response_result = frappe.db.sql(response_query, row['client_code'], as_dict=True)
		
		if response_result and response_result[0]['avg_response_hours']:
			row['avg_response_time'] = round(response_result[0]['avg_response_hours'], 2)
		else:
			row['avg_response_time'] = 0
		
		# Calculate Satisfaction Score
		rating_query = """
			SELECT 
				COUNT(*) as total_rated,
				SUM(CASE 
					WHEN customer_rating = '1 - Very Unsatisfied' THEN 1
					WHEN customer_rating = '2 - Unsatisfied' THEN 2
					WHEN customer_rating = '3 - Neutral' THEN 3
					WHEN customer_rating = '4 - Satisfied' THEN 4
					WHEN customer_rating = '5 - Very Satisfied' THEN 5
					ELSE 0
				END) as total_rating_points
			FROM `tabService Request`
			WHERE client_code = %s AND docstatus IN (0, 1)
				AND customer_rating IS NOT NULL 
				AND customer_rating != ''
				{conditions}
		""".format(conditions=conditions.replace("sr.client_code =", "client_code =").replace("DATE(sr.creation)", "DATE(creation)"))
		
		rating_result = frappe.db.sql(rating_query, row['client_code'], as_dict=True)
		
		if rating_result and rating_result[0]['total_rated'] > 0:
			# Satisfaction Score = (Total Rating Points / (Total Rated * Max Rating)) × 100
			max_rating = 5
			row['satisfaction_score'] = round((rating_result[0]['total_rating_points'] / (rating_result[0]['total_rated'] * max_rating)) * 100, 2)
		else:
			row['satisfaction_score'] = 0
	
	return data


def get_conditions(filters):
	conditions = []
	
	if filters.get("client_code"):
		conditions.append("client_code = '{0}'".format(filters.get("client_code")))
	
	if filters.get("from_date"):
		conditions.append("DATE(sr.creation) >= '{0}'".format(filters.get("from_date")))
	
	if filters.get("to_date"):
		conditions.append("DATE(sr.creation) <= '{0}'".format(filters.get("to_date")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""
