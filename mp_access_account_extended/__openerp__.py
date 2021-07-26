# -*- coding: utf-8 -*-
{
    'name': "Complementa permisos Contables en Sistema",

    'summary': """
        Complementa permisos Contables en Sistema
       """,

    'description': """
        Complementa permisos Contables en Sistema
    """,
    'author': "Technology Management by More Products S.A.",
    'website': "http://www.moreproducts.com",
    'category': 'sale',
    'version': '0.1',
    'depends': ['base','account','base_setup', 'product', 'analytic', 'board', 'edi', 'report','sale','contacts','stock','crm','purchase'],
    'data': [
        'security/mp_access_account_extended_security.xml',
        'security/ir.model.access.csv',
    ],
}