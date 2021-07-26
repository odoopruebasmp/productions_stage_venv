# -*- coding: utf-8 -*-
{
    'name': 'Variables Economicas Colombia',
    'version': '1.0',
    'category': 'localization',
    'complexity': "normal",
    'description': """Variables economicas aplicables en Colombia
    """,
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'depends': ['base'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',        
        'variables_economicas_co.xml',
        'data/2013/variables.economicas.retefuente.csv',
        'data/2013/variables.economicas.retefuente.line.csv',
        'data/2013/variables.economicas.retefuente.marginal.line.csv',        
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
