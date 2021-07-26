# -*- coding: utf-8 -*-

{
    'name': 'Notas débito y crédito de Facturación',
    'version': '1.0',
    'depends': ['account_analytic_avancys'],
    'author' : 'Avancys SAS',
    'website': 'http://www.avancys.com',
    'summary': 'Notas débito - Notas crédito',
    'description': '''
    - Notas débito de cliente
    - Notas crédito de cliente
    - Notas débito de proveedor
    ''',
    'category': 'Accounting & Finance',
    'init_xml': [],
    'data': [
        'views/account_invoice_dcn_extended.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
    }
