# -*- coding: utf-8 -*-
{
    'name': 'Reportes Odoo Avancys',
    'version': '0.1',
    'author' : 'Avancys',
    'website': 'http://www.avancys.com.co',
    'category': 'Accounting',
    'depends': ['account_analytic_avancys','report_aeroo','stock_account','avancys_tools'],
    'description': '''
        Agrega reportes
    ''',
    'init_xml': [],
    'data': [
        "security/security.xml",
        "report_menus_view.xml",
        "report_analitico_view.xml",
        "report_certificado_view.xml",
        "report_balance_sql_view.xml",
        "report_balance_sql_report.xml",
        "report_mayor_report.xml",
        "report_mayor_view.xml",
        "report_diario_report.xml",
        "report_diario_view.xml",
        "report_auxiliar_sql_view.xml",
        "report_auxiliar_sql_report.xml",
        "report_stock_sql_view.xml",
        "report_stock_lot_sql_view.xml",
        "report_kardex_view.xml",
        "report_quants_view.xml",
        "reporte_cartera_tercero_view.xml",
        "security/ir.model.access.csv",
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}

