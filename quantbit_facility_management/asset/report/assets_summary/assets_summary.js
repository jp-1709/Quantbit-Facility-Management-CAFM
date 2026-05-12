// Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Assets Summary"] = {
	"filters": [
		{
			"fieldname": "client_code",
			"label": "Client",
			"fieldtype": "Link",
			"options": "Client",
			"width": 120
		},
		{
			"fieldname": "property_code",
			"label": "Site",
			"fieldtype": "Link",
			"options": "Property",
			"width": 120
		}
	]
};
