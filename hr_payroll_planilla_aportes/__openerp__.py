# -*- coding: utf-8 -*-
{
    'name': 'Planilla integrada de liquidación de aportes (PILA)',
    'version': '2.0',
    'category': 'Payroll',
    'complexity': "normal",
    'description': """Este módulo permite generar la planilla integrada de liquidación de aportes de las nóminas, en un periodo mensual determinado. 
        Además permite notificar a los usuarios configurados tres días antes del vencimiento de este pago.
        - Observaciones: Para generar las notificaciones, es necesario verificar la fecha de ejecución del cron, el día de pago y los usuarios a notificar.
    """,
    'author': 'Avancys SAS',
    'website': 'http://www.avancys.com',
    'depends': ['hr_payroll_extended_co', 'hr_attendance'],
    'data': [
        'security/security.xml',
        'data/sequence.xml',
        'data/cron_data.xml',
        'data/hr_payroll_planilla_aportes_data.xml',
        'data/hr_salary_rule_category.xml',
        'data/hr_salary_rule.xml',
        'views/hr_payroll_planilla_aportes_view.xml',
        'views/hr_payroll_pila_views.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
