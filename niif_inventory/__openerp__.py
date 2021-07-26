{
    'name': 'NIIF INVENTORY',
    'version': '1.11',
    'category': 'Products',
    'complexity': "normal",
    'description': """
        Este modulo permite calcular el deterioro del inventario de la compañia.
    """,
    'author':'Avancys',
    'website':'www.avancys.com',
    'depends': ['niif_account', 'inventory_account'],

    'data': [
       'product_category_niff.xml',
       'wizard/deterioro_producto.xml',
    ],
    'demo_xml': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
