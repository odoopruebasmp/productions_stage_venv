# -*- coding: utf-8 -*-
{
    'name': 'Avisos de Recibo',
    'version': '1.0',
    'author': 'Avancys SAS',
    'website': 'www.avancys.com',
    'category': 'Inventory Control',
    'depends': ['electronic_invoice'],
    'summary': 'Control proceso gestión de Avisos de Recibo',
    'description': '''
    - Lectura de avisos de recibo  de cantidas de productos enviadas a clientes
    - Control de registros para las operaciones de Avisos de Recibo
    - Control de novedades en los avisos de recibo, gestión en todo el proceso de Novedades
    ''',
    'init_xml': [],
    'data': [
        'data/rn_cron.xml',
        'security/rn_security.xml',
        'data/stock_picking_type.xml',
        'wizard/create_refund_picking.xml',
        'wizard/novelty_movement_solution.xml',
        'wizard/novelty_picking_creation.xml',
        'views/receipt_notice.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
