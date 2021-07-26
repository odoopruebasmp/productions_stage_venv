# -*- coding: utf-8 -*-
{
    'name': 'PRODUCTOS COMPLEMENTARIOS Y SUSTITUTOS',
    'version': '2.0',
    'author' : 'AVANCYS S.A.S.',
    'website': 'http://www.avancys.com.co',
    'category': 'Wharehouse',
    'depends': ['stock_extended'],
    'description': '''
        Permite relacionar a un producto, uno o mas productos sustitutos, para conocer la disponibilidad, de igual forma permite agregar productos complementarios.
    ''',
    'init_xml': [],
    'update_xml': [
         "product_substitutes_view.xml",
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}

