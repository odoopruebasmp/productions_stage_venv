# -*- coding: utf-8 -*-
{
    'name': 'Analytic Account Extended Avancys',
    'version': '1.13',
    'category': 'Accounts',
    'complexity': "normal",
    'description': """
    """,
    'author':'Avancys',
    'website':'www.avancys.com',
    'depends': ['hr_expense','product_category_taxes', 'avancys_orm2sql', 'avancys_notification',],
    'data': [
       'security/security.xml',
       'security/ir.model.access.csv',
       'account_analytic_avancys_view.xml',
       'hr_expenses_workflow.xml',
    ],
    'demo_xml': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
