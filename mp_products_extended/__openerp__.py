# -*- coding: utf-8 -*-
{
    'name': "Extension de caracteristicas de Productos",
    'summary': """
        Extension de caracteristicas de Productos
       """,
    'description': """
        Extension de Variantes en Productos
        Agregar caracteristicas de productos
        Medidas de Productos
        Medidas de empaque
        Inner Box
        Master Box
    """,
    'author': "Technology Management by More Products S.A.",
    'website': "http://www.moreproducts.com",
    'category': 'sale',
    'version': '0.1',
    'depends': ['base','product','product_mp'],
    'data': [
        'views/mp_products_extended.xml',
    ],
    'demo': [
    ],
}