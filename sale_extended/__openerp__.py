# -*- coding: utf-8 -*-
{
    'name': 'Sale Extended',
    'version': '1.115',
    'category': 'sale extended',
    'complexity': "normal",
    'description': """Module to manage purchase requisition.
    """,
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'depends': ['sale_stock','partner_extended','sales_team'],
    'data' : ['sale_extended.xml',
    'sale_extended_data.xml',
    'security/ir.model.access.csv',
    'security/security.xml'],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: