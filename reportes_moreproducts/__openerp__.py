# -*- coding: utf-8 -*-
{
    'name': 'Moreproducts Reports',
    'version': '1.0',
    'category': 'reports',
    'complexity': "normal",
    'description': """
    """,
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'depends': ['inventory_account','account_invoice_amount_to_text'],
    'data': [
        'report/nomina.xml',
        'report/report.xml',
        'report/stock_picking_mp.xml',
        'report/stock_picking_puertas_mp.xml',
        'report/stock_picking_cross_mp.xml',
        'views/reportes_moreproducts_view.xml',
      ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
