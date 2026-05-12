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
			"label": "Contract",
			"fieldname": "contract_title",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Total Assets",
			"fieldname": "total_assets",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Active Assets",
			"fieldname": "active_assets",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "Critical Assets",
			"fieldname": "critical_assets",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "PM Due",
			"fieldname": "pm_due",
			"fieldtype": "Int",
			"width": 80
		},
		{
			"label": "Breakdown This Month",
			"fieldname": "breakdown_this_month",
			"fieldtype": "Int",
			"width": 120
		},
		{
			"label": "Active",
			"fieldname": "active_assets_percentage",
			"fieldtype": "Data",
			"width": 100
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)

	query = """
		SELECT 
			COALESCE(
				(SELECT c.client_name 
				 FROM `tabClient` c 
				 WHERE c.name = a.client_code 
				 LIMIT 1), ''
			) as client_name,

			COALESCE(
				(SELECT p.property_name 
				 FROM `tabProperty` p 
				 WHERE p.name = a.property_code 
				 LIMIT 1), ''
			) as property_name,

			'' as contract_title,

			COUNT(*) as total_assets,

			SUM(
				CASE 
					WHEN a.asset_status = 'Active' 
					THEN 1 
					ELSE 0 
				END
			) as active_assets,

			SUM(
				CASE 
					WHEN a.criticality = 'Critical' 
					THEN 1 
					ELSE 0 
				END
			) as critical_assets,

			0 as pm_due,

			SUM(
				CASE 
					WHEN MONTH(a.warranty_expiry) = MONTH(CURDATE()) 
						AND YEAR(a.warranty_expiry) = YEAR(CURDATE()) 
						AND a.asset_status = 'Active'
					THEN 1 
					ELSE 0 
				END
			) as breakdown_this_month,

			CASE 
				WHEN COUNT(*) > 0 
				THEN ROUND(
					(
						SUM(
							CASE 
								WHEN a.asset_status = 'Active' 
								THEN 1 
								ELSE 0 
							END
						) * 100
					) / COUNT(*), 0
				)
				ELSE 0 
			END as active_assets_percentage

		FROM `tabCFAM Asset` a

		WHERE 1=1
		{conditions}

		GROUP BY a.client_code, a.property_code

		ORDER BY a.client_code, a.property_code
	""".format(conditions=conditions)

	data = frappe.db.sql(query, as_dict=True)

	return data


def get_conditions(filters):
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("DATE(a.creation) >= '{0}'".format(filters.get("from_date")))
	
	if filters.get("to_date"):
		conditions.append("DATE(a.creation) <= '{0}'".format(filters.get("to_date")))
	
	if filters.get("client_code"):
		conditions.append("a.client_code = '{0}'".format(filters.get("client_code")))
	
	if filters.get("property_code"):
		conditions.append("a.property_code = '{0}'".format(filters.get("property_code")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""
