// Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Request Register"] = {
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
			"fieldname": "sr_number",
			"label": "Request No",
			"fieldtype": "Link",
			"options": "Service Request",
			"width": 120
		},
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
		},
		{
			"fieldname": "service_group",
			"label": "Department",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "initiator_type",
			"label": "Request Type",
			"fieldtype": "Select",
			"options": "\nHelpdesk\nClient\nTechnician\nSystem\nInspection",
			"width": 120
		},
		{
			"fieldname": "priority_actual",
			"label": "Priority",
			"fieldtype": "Select",
			"options": "\nP1 - Critical\nP2 - High\nP3 - Medium\nP4 - Low",
			"width": 80
		},
		{
			"fieldname": "status",
			"label": "Status",
			"fieldtype": "Select",
			"options": "\nOpen\nIn Progress\nPending\nCompleted\nClosed\nCancelled",
			"width": 100
		}
	]
};
