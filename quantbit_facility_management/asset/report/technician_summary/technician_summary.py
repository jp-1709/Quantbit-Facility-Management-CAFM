# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"label": "Technician",
			"fieldname": "resource_name",
			"fieldtype": "Data",
			"width": 150
		},
				{
			"label": "Jobs Assigned",
			"fieldname": "jobs_assigned",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Jobs Closed",
			"fieldname": "jobs_closed",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Open Jobs",
			"fieldname": "open_jobs",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Avg Response Time",
			"fieldname": "avg_response_time",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": "Attendance Days",
			"fieldname": "attendance_days",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Productivity Score",
			"fieldname": "productivity_score",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": "Client Rating",
			"fieldname": "client_rating",
			"fieldtype": "Float",
			"width": 100
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	# Main query to get technicians
	query = """
		SELECT 
			r.name,
			r.staff_code,
			r.resource_name,
			r.primary_area_group
		FROM `tabResource` r
		WHERE 1=1
		{conditions}
		GROUP BY r.name, r.staff_code, r.resource_name, r.primary_area_group
		ORDER BY r.resource_name
	""".format(conditions=conditions)
	
	technicians = frappe.db.sql(query, as_dict=True)
	data = []
	
	# For each technician, calculate metrics
	for tech in technicians:
		row = {
			'resource_name': tech['resource_name'],
			'jobs_assigned': get_jobs_assigned(tech['name'], filters),
			'jobs_closed': get_jobs_closed(tech['name'], filters),
			'open_jobs': get_open_jobs(tech['name'], filters),
			'avg_response_time': get_avg_response_time(tech['name'], filters),
			'attendance_days': get_attendance_days(tech['name'], filters),
			'productivity_score': get_productivity_score(tech['name'], filters),
			'client_rating': get_client_rating(tech['name'], filters)
		}
		data.append(row)
	
	return data


def get_jobs_assigned(resource_name, filters):
	conditions = get_date_conditions(filters)
	
	query = """
		SELECT COUNT(*) as count
		FROM `tabWork Orders`
		WHERE assigned_to = %s 
			AND docstatus = 1
		{conditions}
	""".format(conditions=conditions)
	
	# Debug: Log the actual query
	frappe.errprint(f"DEBUG - Jobs Assigned Query: {query}")
	frappe.errprint(f"DEBUG - Jobs Assigned Resource: {resource_name}")
	
	result = frappe.db.sql(query, resource_name, as_dict=True)
	return result[0]['count'] if result else 0


def get_jobs_closed(resource_name, filters):
	conditions = get_date_conditions(filters)
	
	query = """
		SELECT COUNT(*) as count
		FROM `tabWork Orders`
		WHERE assigned_to = %s 
			AND status IN ('Completed', 'Closed')
			AND docstatus = 1
		{conditions}
	""".format(conditions=conditions)
	
	result = frappe.db.sql(query, resource_name, as_dict=True)
	return result[0]['count'] if result else 0


def get_open_jobs(resource_name, filters):
	conditions = get_date_conditions(filters)
	
	query = """
		SELECT COUNT(*) as count
		FROM `tabWork Orders`
		WHERE assigned_to = %s 
			AND status IN ('Open', 'Assigned', 'In Progress')
			AND docstatus = 1
		{conditions}
	""".format(conditions=conditions)
	
	result = frappe.db.sql(query, resource_name, as_dict=True)
	return result[0]['count'] if result else 0


def get_avg_response_time(resource_name, filters):
	conditions = get_date_conditions_for_joins(filters)
	
	query = """
		SELECT AVG(TIMESTAMPDIFF(HOUR, sr.raised_date, sr.response_sla_actual)) as avg_hours
		FROM `tabWork Orders` wo
		INNER JOIN `tabService Request` sr ON wo.sr_number = sr.name
		WHERE wo.assigned_to = %s 
			AND wo.docstatus != 2
			AND sr.raised_date IS NOT NULL 
			AND sr.response_sla_actual IS NOT NULL
		{conditions}
	""".format(conditions=conditions)
	
	result = frappe.db.sql(query, resource_name, as_dict=True)
	
	if result and result[0]['avg_hours']:
		return round(result[0]['avg_hours'], 2)
	else:
		return 0


def get_attendance_days(resource_name, filters):
	conditions = get_date_conditions(filters)
	
	query = """
		SELECT COUNT(DISTINCT DATE(schedule_start_date)) as attendance_days
		FROM `tabWork Orders`
		WHERE assigned_to = %s 
			AND docstatus = 1
			AND schedule_start_date IS NOT NULL
		{conditions}
	""".format(conditions=conditions)
	
	result = frappe.db.sql(query, resource_name, as_dict=True)
	return result[0]['attendance_days'] if result else 0


def get_productivity_score(resource_name, filters):
	# Calculate productivity score based on completion rate and satisfaction
	conditions = get_date_conditions(filters)
	join_conditions = get_date_conditions_for_joins(filters)
	
	# Get completion rate
	completion_query = """
		SELECT 
			COUNT(*) as total_jobs,
			SUM(CASE WHEN status IN ('Completed', 'Closed') THEN 1 ELSE 0 END) as completed_jobs
		FROM `tabWork Orders`
		WHERE assigned_to = %s 
			AND docstatus = 1
		{conditions}
	""".format(conditions=conditions)
	
	completion_result = frappe.db.sql(completion_query, resource_name, as_dict=True)
	
	if completion_result and completion_result[0]['total_jobs'] > 0:
		completion_rate = (completion_result[0]['completed_jobs'] / completion_result[0]['total_jobs']) * 100
	else:
		completion_rate = 0
	
	# Get satisfaction score from service requests
	satisfaction_query = """
		SELECT 
			COUNT(*) as total_rated,
			SUM(CASE 
				WHEN sr.customer_rating = '1 - Very Unsatisfied' THEN 1
				WHEN sr.customer_rating = '2 - Unsatisfied' THEN 2
				WHEN sr.customer_rating = '3 - Neutral' THEN 3
				WHEN sr.customer_rating = '4 - Satisfied' THEN 4
				WHEN sr.customer_rating = '5 - Very Satisfied' THEN 5
				ELSE 0
			END) as total_rating_points
		FROM `tabWork Orders` wo
		INNER JOIN `tabService Request` sr ON wo.sr_number = sr.name
		WHERE wo.assigned_to = %s 
			AND wo.docstatus != 2
			AND sr.customer_rating IS NOT NULL 
			AND sr.customer_rating != ''
		{conditions}
	""".format(conditions=join_conditions)
	
	satisfaction_result = frappe.db.sql(satisfaction_query, resource_name, as_dict=True)
	
	if satisfaction_result and satisfaction_result[0]['total_rated'] > 0:
		max_rating = 5
		satisfaction_score = (satisfaction_result[0]['total_rating_points'] / (satisfaction_result[0]['total_rated'] * max_rating)) * 100
	else:
		satisfaction_score = 0
	
	# Productivity score = 70% completion rate + 30% satisfaction score
	productivity_score = (completion_rate * 0.7) + (satisfaction_score * 0.3)
	return round(productivity_score, 2)


def get_client_rating(resource_name, filters):
	conditions = get_date_conditions_for_joins(filters)
	
	query = """
		SELECT 
			COUNT(*) as total_rated,
			SUM(CASE 
				WHEN sr.customer_rating = '1 - Very Unsatisfied' THEN 1
				WHEN sr.customer_rating = '2 - Unsatisfied' THEN 2
				WHEN sr.customer_rating = '3 - Neutral' THEN 3
				WHEN sr.customer_rating = '4 - Satisfied' THEN 4
				WHEN sr.customer_rating = '5 - Very Satisfied' THEN 5
				ELSE 0
			END) as total_rating_points
		FROM `tabWork Orders` wo
		INNER JOIN `tabService Request` sr ON wo.sr_number = sr.name
		WHERE wo.assigned_to = %s 
			AND wo.docstatus != 2
			AND sr.customer_rating IS NOT NULL 
			AND sr.customer_rating != ''
		{conditions}
	""".format(conditions=conditions)
	
	result = frappe.db.sql(query, resource_name, as_dict=True)
	
	if result and result[0]['total_rated'] > 0:
		max_rating = 5
		avg_rating = result[0]['total_rating_points'] / result[0]['total_rated']
		return round(avg_rating, 2)
	else:
		return 0


def get_date_conditions(filters):
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("DATE(creation) >= '{0}'".format(filters.get("from_date")))
	
	if filters.get("to_date"):
		conditions.append("DATE(creation) <= '{0}'".format(filters.get("to_date")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""


def get_date_conditions_for_joins(filters):
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("DATE(wo.creation) >= '{0}'".format(filters.get("from_date")))
	
	if filters.get("to_date"):
		conditions.append("DATE(wo.creation) <= '{0}'".format(filters.get("to_date")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""


def get_conditions(filters):
	conditions = []
	
	if filters.get("staff_code"):
		conditions.append("staff_code = '{0}'".format(filters.get("staff_code")))
	
	if filters.get("primary_area_group"):
		conditions.append("primary_area_group = '{0}'".format(filters.get("primary_area_group")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""
