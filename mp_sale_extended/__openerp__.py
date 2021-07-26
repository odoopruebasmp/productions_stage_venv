# -*- coding: utf-8 -*-
{
    'name': "Integracion Ventas E-commerce",

    'summary': """
        Integracion de Pedidos de Ventas con e-commerce SFTP
       """,

    'description': """
        Integracion de Pedidos de Ventas con e-commerce SFTP
    """,
    'author': "Technology Management by More Products S.A.",
    'website': "http://www.moreproducts.com",
    'category': 'sale',
    'version': '0.1',
    'depends': ['base','sale','contacts','stock','crm'],
    'data': [
        'data/sale_e_cron.xml',
        'security/mp_sale_extended_security.xml',
        'security/ir.model.access.csv',
        'wizard/generated_payment_customer_masive_wizard.xml',
        'views/mp_managment_sftp_view.xml',
        'views/mp_sale_transactions_view.xml',

    ],
    'demo': [
    ],
}