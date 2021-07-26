# -*- coding: utf-8 -*-

{
    'name': 'Payroll Extended',
    'version': '3',
    'category': 'Human Resources',
    'complexity': "normal",
    'description': """This module will compute automated payslips and compute Leaves,Extra Hours and novelties of employees.
    """,
    'author':'Avancys',
    'website':'www.avancys.com',
    'depends': [
        'hr_payroll_account', 'hr_payroll', 'account_analytic_avancys','hr_attendance','variables_economicas_co', 'base', 'avancys_orm'
    ],
    'init_xml': [
    ],
    'css': ['static/src/css/hr_payroll_extended.css'],
    'data': [
        'views/hr_payroll_extended_view.xml',
        'wizard/hr_payroll_compute_view.xml',
        'wizard/leave_allocation_compute_view.xml',
        'wizard/import_pay_slip_view.xml',
        'wizard/open_petty_cash_wiz.xml',
        'hr_payroll_extended_data.xml',
        'views/hr_payroll_policies.xml',
        'wizard/hr_payslip_mass_approve_view.xml',
        'wizard/hr_leave_mass_approve_view.xml',
        'wizard/hr_payslip_mass_notification.xml',
        'edi/hr_payroll_action_data.xml',
        'views/hr_payroll_hours_view.xml',
        'views/hr_payroll_novedades_view.xml',
        'views/hr_payroll_prestamos_view.xml',
        'views/hr_payroll_holidays.xml',
        'views/hr_contribution_form_view.xml',
        'security/security.xml',
        'advance_workflow.xml',
        'security/ir.model.access.csv',
        'views/hr_payroll_obligacion_tributaria_view.xml',
        'views/hr_payroll_anticipo_view.xml',
        'data/hr_concept_data.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
