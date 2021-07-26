# -*- coding: utf-8 -*-

{
    'name': 'Payroll Extended CO',
    'version': '2.01',
    'category': 'Human Resources',
    'complexity': "normal",
    'description': """
    """,
    'author':'Avancys',
    'website':'www.avancys.com',
    'depends': [
        'hr_payroll_extended','variables_economicas_co'
    ],
    'init_xml': [
    ],
    'data': [
       'hr_payroll_extended_co_data.xml',
       'hr_payroll_extended_co.xml',
       'security/security.xml',
       'security/ir.model.access.csv',
    ],
    'demo_xml': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
