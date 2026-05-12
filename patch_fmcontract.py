import json

path = '/home/erpnext/frappe-bench/apps/quantbit_facility_management/quantbit_facility_management/contracts_&_finance/doctype/fm_contract/fm_contract.json'

with open(path) as f:
    doc = json.load(f)

fo = doc['field_order']
if 'branch_code' not in fo:
    idx = fo.index('client_name') + 1
    fo.insert(idx, 'branch_code')
    fo.insert(idx+1, 'branch_name')

fields = doc['fields']
if not any(f.get('fieldname')=='branch_code' for f in fields):
    cname_idx = next(i for i,f in enumerate(fields) if f.get('fieldname')=='client_name')
    fields.insert(cname_idx+1, {
        'fieldname': 'branch_code',
        'fieldtype': 'Link',
        'in_list_view': 1,
        'in_standard_filter': 1,
        'label': 'Branch',
        'options': 'Branch'
    })
    fields.insert(cname_idx+2, {
        'fetch_from': 'branch_code.branch_name',
        'fieldname': 'branch_name',
        'fieldtype': 'Data',
        'label': 'Branch Name',
        'read_only': 1
    })

doc['modified'] = '2026-04-24 00:00:00.000000'
with open(path, 'w') as f:
    json.dump(doc, f, indent=1)

print('FM Contract: Done')
