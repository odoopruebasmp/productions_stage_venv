# -*- coding: utf-8 -*-

{
    'name': 'PROCUREMENT MP',
    'version': '1.0',
    'author' : 'AVANCYS S.A.S.',
    'website': 'http://www.avancys.com.co',
    'category': 'Wharehouse',
    'depends': ['product_mp', 'procurement'],
    'description': '''
        Permite gestionar un informe de stock minimo real y virtual.
    ''',
    'init_xml': [],
    'update_xml': [
         "procurement_mp_view.xml",
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}

