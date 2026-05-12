
frappe.ui.form.on("Service Request", {
	initiator_type(frm) {
		frm.set_value("requested_by", "");
		frm.set_value("initiator_client", "");

		if (frm.doc.initiator_type === "Helpdesk" || frm.doc.initiator_type === "Inspection") {
			const role = frm.doc.initiator_type;
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Has Role",
					filters: { role: role },
					fields: ["parent"]
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						const userIds = [...new Set(r.message.map(u => u.parent))];
                        
                        // Fetch full names for these users
                        frappe.call({
                            method: "frappe.client.get_list",
                            args: {
                                doctype: "User",
                                filters: { name: ["in", userIds] },
                                fields: ["name", "full_name"]
                            },
                            callback: function(res) {
                                if (res.message && res.message.length > 0) {
                                    const options = res.message.map(u => ({ value: u.full_name || u.name, label: u.full_name || u.name }));
                                    
                                    if (options.length === 1) {
                                        frm.set_value("requested_by", options[0].value);
                                    } else {
                                        frappe.prompt([
                                            {
                                                label: "Select Requested By",
                                                fieldname: "user",
                                                fieldtype: "Select",
                                                options: options,
                                                reqd: 1
                                            }
                                        ], (values) => {
                                            frm.set_value("requested_by", values.user);
                                        }, "Select User");
                                    }
                                }
                            }
                        });
					}
				}
			});
		} else if (frm.doc.initiator_type === "System") {
			frm.set_value("requested_by", frappe.session.user_fullname || frappe.session.user);
		} else if (frm.doc.initiator_type === "Technician") {
			// Try to find if current user is a technician
			frappe.db.get_value("Resource", { user_id: frappe.session.user }, "resource_name", (r) => {
				if (r && r.resource_name) {
					frm.set_value("requested_by", r.resource_name);
				}
				
				// Always allow selection if they want to change it
				frappe.call({
					method: "frappe.client.get_list",
					args: {
						doctype: "Resource",
						fields: ["name", "resource_name"],
						limit: 1000
					},
					callback: function(res) {
						if (res.message && res.message.length > 0) {
							const technicians = res.message.map(t => t.resource_name || t.name);
							frappe.prompt([
								{
									label: "Select Technician",
									fieldname: "tech",
									fieldtype: "Select",
									options: technicians,
									reqd: 1
								}
							], (values) => {
								frm.set_value("requested_by", values.tech);
							}, "Select Technician");
						}
					}
				});
			});
		}
	},
	initiator_client(frm) {
		if (frm.doc.initiator_client) {
            frappe.db.get_value("Client", frm.doc.initiator_client, "client_name", (r) => {
                if (r && r.client_name) {
                    frm.set_value("requested_by", r.client_name);
                } else {
                    frm.set_value("requested_by", frm.doc.initiator_client);
                }
            });
		}
	}
});
