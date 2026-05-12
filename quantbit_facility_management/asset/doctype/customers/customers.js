frappe.ui.form.on('Customers', {
	refresh: function(frm) {
		// Add custom buttons or UI elements if needed
		if (frm.doc.customer_code) {
			frm.add_custom_button(__('View Hierarchy'), function() {
				frappe.call({
					method: 'quantbit_facility_management.quantbit_facility_management.asset.doctype.customers.customers.get_customer_hierarchy',
					args: {
						customer_code: frm.doc.customer_code
					},
					callback: function(r) {
						if (r.message) {
							show_hierarchy_dialog(r.message);
						}
					}
				});
			}, __('Actions'));
		}
	},
	
	customer_name: function(frm) {
		// Auto-generate customer code when name is entered
		if (!frm.doc.customer_code && frm.doc.customer_name) {
			frm.set_value('customer_code', generate_customer_code(frm.doc.customer_name));
		}
	},
	
	is_active: function(frm) {
		// Show warning when deactivating a customer
		if (!frm.doc.is_active && frm.doc.__islocal) {
			frappe.msgprint(__('Deactivating this customer will not affect existing records, but it will not be available for new selections.'));
		}
	}
});

function generate_customer_code(name) {
	// Generate a customer code from the name
	var base_code = name.toUpperCase().replace(/[^A-Z0-9]/g, '_').substring(0, 8);
	return base_code;
}

function show_hierarchy_dialog(data) {
	var dialog = new frappe.ui.Dialog({
		title: __('Customer Hierarchy'),
		fields: [
			{
				fieldname: 'customer_info',
				fieldtype: 'Section Break',
				label: __('Customer Information')
			},
			{
				fieldname: 'customer_name',
				fieldtype: 'Data',
				label: __('Customer Name'),
				read_only: 1,
				default: data.customer[1]
			},
			{
				fieldname: 'contact_person',
				fieldtype: 'Data',
				label: __('Contact Person'),
				read_only: 1,
				default: data.customer[2]
			},
			{
				fieldname: 'phone',
				fieldtype: 'Data',
				label: __('Phone'),
				read_only: 1,
				default: data.customer[3]
			},
			{
				fieldname: 'email',
				fieldtype: 'Data',
				label: __('Email'),
				read_only: 1,
				default: data.customer[4]
			}
		]
	});
	
	// Add hierarchy counts
	var hierarchy_break = dialog.add_field({
		fieldname: 'hierarchy_break',
		fieldtype: 'Section Break',
		label: __('Location Hierarchy')
	});
	
	var hierarchy_types = [
		{ label: __('Cities'), data: data.cities, icon: '🌆' },
		{ label: __('Branches'), data: data.branches, icon: '🏢' },
		{ label: __('Area Groups'), data: data.area_groups, icon: '📋' },
		{ label: __('Areas'), data: data.areas, icon: '📍' },
		{ label: __('Properties'), data: data.properties, icon: '🏠' },
		{ label: __('Zones'), data: data.zones, icon: '🗂️' },
		{ label: __('Sub Zones'), data: data.sub_zones, icon: '🏘️' },
		{ label: __('Base Units'), data: data.base_units, icon: '🏗️' }
	];
	
	hierarchy_types.forEach(function(type) {
		if (type.data && type.data.length > 0) {
			dialog.add_field({
				fieldname: type.label.toLowerCase().replace(' ', '_'),
				fieldtype: 'HTML',
				options: `
					<div style="padding: 10px; margin: 5px 0; border: 1px solid #d1d1d1; border-radius: 4px; background-color: #f8f8f8;">
						<div style="display: flex; align-items: center; margin-bottom: 8px;">
							<span style="font-size: 16px; margin-right: 8px;">${type.icon}</span>
							<strong>${type.label} (${type.data.length})</strong>
						</div>
						<div style="font-size: 12px; color: #666;">
							${type.data.slice(0, 5).map(function(item) { 
								return '• ' + (item[1] || item[0]); 
							}).join('<br>')}
							${type.data.length > 5 ? '<br>... and ' + (type.data.length - 5) + ' more' : ''}
						</div>
					</div>
				`
			});
		}
	});
	
	dialog.show();
}
