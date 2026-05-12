// Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Work Orders Register"] = {
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
			"fieldname": "wo_no",
			"label": "WO No",
			"fieldtype": "Link",
			"options": "Work Orders",
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
			"fieldname": "contract_code",
			"label": "Contract",
			"fieldtype": "Link",
			"options": "FM Contract",
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
			"fieldname": "fault_category",
			"label": "Category",
			"fieldtype": "Select",
			"options": "\nElectrical\nMechanical\nPlumbing\nHVAC\nCivil\nFire Safety\nElevator\nGenerator\nWater Treatment\nLandscaping\nCleaning\nPest Control\nSecurity",
			"width": 120
		},
		{
			"fieldname": "asset_code",
			"label": "Asset",
			"fieldtype": "Link",
			"options": "CFAM Asset",
			"width": 120
		},
		{
			"fieldname": "default_priority",
			"label": "Priority",
			"fieldtype": "Select",
			"options": "\nP1 - Critical\nP2 - High\nP3 - Medium\nP4 - Low",
			"width": 80
		},
		{
			"fieldname": "assigned_to",
			"label": "Assigned Technician",
			"fieldtype": "Link",
			"options": "Resource",
			"width": 140
		},
		{
			"fieldname": "status",
			"label": "Status",
			"fieldtype": "Select",
			"options": "\nDraft\nOpen\nAssigned\nOn Hold\nIn Progress\nPending Parts\nNot Dispatched\nPending Approval\nCompleted\nClosed\nCancelled",
			"width": 100
		}
	]
};
