# -*- coding: utf-8 -*-
{
    'name': "Avancys - Consultor funcional",

    'summary': """
       Este módulo es una prueba para optar al cargo de Consultor Funcional""",

    'description': """
        Por Avancys, C.A.
    """,

    'author': "Avancys",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Conocimiento',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        #'templates.xml',
        'views/groupIdea.xml',
        'views/idea.xml',
        'views/votes.xml',
        'views/group.xml',
        'views/users.xml',
        'views/menu.xml',
        'security/groupRule.xml',
        'security/ir.model.access.csv'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}