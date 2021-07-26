# -*- coding: utf-8 -*-
{
    'name': 'Purchase Requisition Extended MP',
    'version': '1.0816',
    'category': 'purchase',
    'complexity': "normal",
    'description': """Module to manage purchase requisition.
    """,
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'depends': ['purchase_requisition_extended','stock_return'],
    'update_xml' : ['purchase_requisition_extended_mp.xml'],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: