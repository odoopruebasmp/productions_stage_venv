# -*- coding: utf-8 -*-
{
    'name': 'reportes_empleados',
    'version': '1.0',
    'category': 'reports',
    'complexity': "normal",
    'description': """
    """,
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'depends': ['hr_payroll_account','hr_payroll_extended_co','hr_payroll_extended'],
    'data': ['report/voucher_report.xml'
             ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: