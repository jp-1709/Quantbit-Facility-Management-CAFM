// Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Orders", {
	fault_code: function(frm) {
		if (frm.doc.fault_code) {
			// Auto-fill service_group and fault_category from fault_code
			frappe.db.get_value("Fault Code", frm.doc.fault_code, ["service_group", "fault_category", "default_priority"])
				.then(response => {
					if (response.message) {
						let values = {};
						if (response.message.service_group && !frm.doc.service_group) {
							values.service_group = response.message.service_group;
						}
						if (response.message.fault_category && !frm.doc.fault_category) {
							values.fault_category = response.message.fault_category;
						}
						if (response.message.default_priority && !frm.doc.default_priority) {
							values.default_priority = response.message.default_priority;
						}
						
						if (Object.keys(values).length > 0) {
							frm.set_value(values);
						}
					}
				});
		}
	},
	
	sr_number: function(frm) {
		if (frm.doc.sr_number) {
			// Auto-fill fields from service request
			frappe.db.get_value("Service Request", frm.doc.sr_number, [
				"client_code", "client_name", "contract_code", "contract_group",
				"property_code", "property_name", "branch_code", "branch_name",
				"zone_code", "sub_zone_code", "base_unit_code", "business_type",
				"asset_code", "asset_name", "asset_category", "asset_master_category",
				"service_group", "fault_category", "fault_code", "default_priority",
				"actual_priority", "priority_change_reason", "approval_criticality",
				"wo_source", "initiator_type", "requested_by", "sr_title"
			]).then(response => {
				if (response.message) {
					frm.set_value(response.message);
					
					// Set WO title from SR title
					if (response.message.sr_title && !frm.doc.wo_title) {
						frm.set_value("wo_title", response.message.sr_title);
					}
					
					// Set WO source
					if (response.message.wo_source) {
						frm.set_value("wo_source", "Service Request");
					}
				}
			});
		}
	},
	
	refresh: function(frm) {
		// Add custom button to update service request if converted
		if (frm.doc.docstatus === 1 && frm.doc.sr_number) {
			frm.add_custom_button(__("Update Service Request"), function() {
				frappe.call({
					method: "quantbit_facility_management.operations.doctype.work_orders.work_orders.update_service_request",
					args: {
						sr_number: frm.doc.sr_number,
						wo_number: frm.doc.wo_number,
						status: frm.doc.status
					},
					callback: function(r) {
						if (!r.exc) {
							frappe.show_alert({ message: __("Service Request updated successfully"), indicator: "green" });
							frm.refresh_fields();
						}
					}
				});
			}, __("Actions"));
		}
	},
	
	on_submit: function(frm) {
		// Auto-update service request when work order is submitted
		if (frm.doc.sr_number) {
			frappe.call({
				method: "quantbit_facility_management.operations.doctype.work_orders.work_orders.update_service_request",
				args: {
					sr_number: frm.doc.sr_number,
					wo_number: frm.doc.wo_number,
					status: frm.doc.status
				},
				callback: function(r) {
					if (!r.exc) {
						console.log("Service Request updated automatically");
					}
				}
			});
		}
	}
});
