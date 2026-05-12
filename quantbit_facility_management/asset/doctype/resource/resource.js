// Copyright (c) 2026, Quantbit Technologies Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Resource", {
	refresh(frm) {
		// Set queries for fields
		frm.set_query("staff_code", "technicians", function() {
			return {
				filters: {
					"designation": ["!=", "Supervisor"]
				}
			};
		});

		frm.set_query("supervisor_code", function() {
			return {
				filters: {
					"designation": "Supervisor",
					"is_active": 1
				}
			};
		});

		// Add custom button to manually refresh supervised technicians
		if (frm.doc.designation === "Supervisor") {
			frm.add_custom_button(__("Refresh Supervised Technicians"), function() {
				frm.call({
					method: "quantbit_facility_management.quantbit_facility_management.asset.doctype.resource.resource.auto_fill_supervised_technicians_for_resource",
					doc: frm.doc,
					callback: function(r) {
						if (!r.exc) {
							frm.refresh_field("technicians");
							frappe.show_alert({
								message: __("Supervised Technicians refreshed successfully"),
								indicator: "green"
							});
						}
					}
				});
			}, __("Actions"));
		}

		frm.trigger("designation");
	},

	designation(frm) {
		if (frm.doc.designation) {
			// user_id is mandatory for all resources once designation is set
			frm.set_df_property("user_id", "reqd", 1);
			
			// supervisor_code is mandatory if designation is not Supervisor
			if (frm.doc.designation !== "Supervisor") {
				frm.set_df_property("supervisor_code", "reqd", 1);
			} else {
				frm.set_df_property("supervisor_code", "reqd", 0);
				// Clear supervisor if the resource itself is a supervisor
				frm.set_value("supervisor_code", "");
				// Auto-fill supervised technicians when designation changes to Supervisor
				frm.trigger("staff_code");
			}
		} else {
			frm.set_df_property("user_id", "reqd", 0);
			frm.set_df_property("supervisor_code", "reqd", 0);
		}
	},

	staff_code(frm) {
		// Auto-fill supervised technicians when staff_code is set and designation is Supervisor
		if (frm.doc.designation === "Supervisor" && frm.doc.staff_code) {
			frm.call({
				method: "quantbit_facility_management.quantbit_facility_management.asset.doctype.resource.resource.auto_fill_supervised_technicians_for_resource",
				doc: frm.doc,
				callback: function(r) {
					if (!r.exc) {
						frm.refresh_field("technicians");
						// Show success message
						frappe.show_alert({
							message: __("Supervised Technicians auto-populated successfully"),
							indicator: "green"
						});
					}
				}
			});
		}
	}
});
