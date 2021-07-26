# -*- coding: utf-8 -*-
{
    'name': 'Ocultar Debitos Creditos Account',
    'version': '1.0',
    'depends': ['account_analytic_avancys'],
    'author' : 'Avancys',
    'website': 'http://www.odoo.com.co',
    'description': """
         Modulo que permite mejorar el desempeño en la gestion contable, eliminando el compute del debit, credit, balance.
    """,
    'category': 'Account',
    'data': [
        "account_extended_view.xml",
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
