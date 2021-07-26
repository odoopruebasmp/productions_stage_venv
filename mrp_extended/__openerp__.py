# -*- coding: utf-8 -*-
{
    'name': 'MRP Extended',
    'version': '1.0',
    'category': 'mrp',
    'complexity': "normal",
    'description': """
    """,
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'depends': ['mrp','mrp_operations','stock_extended'],
    'data': [
            'mrp_extended.xml',
            'wizard/mrp_product_produce_view.xml',
            'security/security.xml',
            'security/ir.model.access.csv',
             ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: