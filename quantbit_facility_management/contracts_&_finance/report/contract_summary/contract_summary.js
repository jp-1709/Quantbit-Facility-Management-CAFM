// Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Contract Summary"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"default": frappe.datetime.add_days(frappe.datetime.now_date(), -30),
			"width": 120
		},
		{
			"fieldname": "to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": frappe.datetime.now_date(),
			"width": 120
		},
		{
			"fieldname": "client_code",
			"label": "Client",
			"fieldtype": "Link",
			"options": "Client",
			"width": 120
		}
	]
};
