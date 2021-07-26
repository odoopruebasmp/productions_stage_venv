# -*- coding: utf-8 -*-
{
    'name': 'Purchase Requisition Extended',
    'version': '1.0816',
    'category': 'purchase',
    'complexity': "normal",
    'description': """Module to manage purchase requisition.
    """,
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'depends': ['purchase_extended','project', 'inventory_account', 'purchase_requisition'],
    'data' : [
        'wizard/requisition_line_quotation.xml',
        'wizard/quotation_line_wizard.xml',
        'purchase_requisition_extended.xml',
        'edi/purchase_requisition_edi.xml',        
        'security/purchase_security.xml',
        'report/quotation_report.xml',
        'security/ir.model.access.csv',
        ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: