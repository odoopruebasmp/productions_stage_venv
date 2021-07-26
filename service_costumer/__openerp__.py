# -*- coding: utf-8 -*-
{
    'name': 'Servicio al Cliente',
    'version': '1.0',
    'category': 'Tools',
    'description': """
Modulo de Servicio al Cliente.
""",
    'author': 'Avancys',
    'website': 'http://avancys.com',
    'sequence': 9,
    'depends': ['sale_extended'],
    'data': [
        'security/security.xml',
        #'security/ir.model.access.csv',
        'servicio_workflow.xml',
        'servicio_view.xml',
        'servicio_report_mp.xml',
        ],
    'demo': [],
    'test': [],
    'css': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
