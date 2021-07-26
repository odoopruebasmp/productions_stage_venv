# -*- coding: utf-8 -*-
{
    'name': 'reportes_comprobantes',
    'version': '1.0',
    'category': 'reports',
    'complexity': "normal",
    'description': """
    """,
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'depends': ['account_voucher_extended','currency_tarifa_manual','account_analytic_avancys','report'],
    'data': [
            'reportes_comprobantes.xml',
            'report/voucher_report.xml',
            'report/reporte_ingreso.xml',
            'report/comprobante_contable.xml',
            'report/cheque_avvillas.xml',
            'report/cheque_bancolombia.xml',
            'report/cheque_bogota.xml'
            ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
