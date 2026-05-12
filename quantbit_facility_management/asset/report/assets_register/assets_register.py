# Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"label": "Asset Code",
			"fieldname": "asset_code",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Asset Name",
			"fieldname": "asset_name",
			"fieldtype": "Data",
			"width": 200
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
			"label": "Category",
			"fieldname": "asset_master_category",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Make",
			"fieldname": "make_brand",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Model",
			"fieldname": "model",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Install Date",
			"fieldname": "installation_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": "Warranty Expire",
			"fieldname": "warranty_expiry",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": "Current Status",
			"fieldname": "asset_status",
			"fieldtype": "Data",
			"width": 120
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	# Main query to get asset data with client and site information
	query = """
		SELECT 
			a.asset_code,
			a.asset_name,
			COALESCE((SELECT c.client_name FROM `tabClient` c WHERE c.name = a.client_code LIMIT 1), '') as client_name,
			COALESCE((SELECT p.property_name FROM `tabProperty` p WHERE p.name = a.property_code LIMIT 1), a.property_name) as property_name,
			a.asset_master_category,
			a.make_brand,
			a.model,
			a.installation_date,
			a.warranty_expiry,
			a.asset_status
		FROM `tabCFAM Asset` a
		WHERE 1=1
			{conditions}
		ORDER BY a.asset_code
	""".format(conditions=conditions)
	
	# Debug: Check what's happening
	try:
		data = frappe.db.sql(query, as_dict=True)
		frappe.errprint(f"DEBUG - Query executed, returned {len(data)} rows")
		if not data:
			# Try a simpler query to see if table exists
			simple_query = "SELECT COUNT(*) as count FROM `tabCFAM Asset`"
			count_result = frappe.db.sql(simple_query, as_dict=True)
			frappe.errprint(f"DEBUG - Asset count: {count_result[0]['count'] if count_result else 'No result'}")
			
			# Show sample data if any
			if count_result and count_result[0]['count'] > 0:
				sample_query = "SELECT asset_code, asset_name, asset_status FROM `tabCFAM Asset` LIMIT 3"
				sample_data = frappe.db.sql(sample_query, as_dict=True)
				frappe.errprint(f"DEBUG - Sample data: {sample_data}")
		# If no data, add debug info as a row
		if not data:
			debug_info = [{
				'asset_code': f'DEBUG: Query returned {len(data)} rows',
				'asset_name': f'Check Frappe logs for DEBUG messages',
				'client_name': 'Run report and check error logs',
				'property_name': 'Look for "DEBUG -" messages',
				'asset_master_category': '',
				'make_brand': '',
				'model': '',
				'installation_date': '',
				'warranty_expiry': '',
				'asset_status': 'Debug Info'
			}]
			return debug_info
		
		return data
	except Exception as e:
		frappe.errprint(f"DEBUG - Error: {e}")
		return []


def get_conditions(filters):
	conditions = []
	
	# Default: show only active assets unless status is explicitly filtered
	if not filters.get("asset_status"):
		conditions.append("a.asset_status = 'Active'")
	
	if filters.get("from_date"):
		conditions.append("DATE(a.creation) >= '{}'".format(filters.get("from_date")))
	
	if filters.get("to_date"):
		conditions.append("DATE(a.creation) <= '{}'".format(filters.get("to_date")))
	
	if filters.get("asset_code"):
		conditions.append("a.asset_code = '{}'".format(filters.get("asset_code")))
	
	if filters.get("client_code"):
		conditions.append("a.client_code = '{}'".format(filters.get("client_code")))
	
	if filters.get("property_code"):
		conditions.append("a.property_code = '{}'".format(filters.get("property_code")))
	
	if filters.get("asset_master_category"):
		conditions.append("a.asset_master_category = '{}'".format(filters.get("asset_master_category")))
	
	if filters.get("asset_status"):
		conditions.append("a.asset_status = '{}'".format(filters.get("asset_status")))
	
	return "AND " + " AND ".join(conditions) if conditions else ""

