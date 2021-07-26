# -*- coding: utf-8 -*-
{
    'name': "SFTP More",

    'summary': """
        Access your documents via SFTP""",

    'description': """
        Access your documents via SFTP
    """,

    'author': "Avancys",
    'website': "http://www.avancys.com",
    'contributor': 'Juan Arcos parcos@avancys.com.co',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Knowledge Management',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['stock_extended'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'templates/ir_cron_view.xml',
        'templates/stock_picking_wizard_view.xml',
        'templates/stock_picking_view.xml',
        'templates/sftp_more_view.xml',
        'templates/stock_location_view.xml',
        'templates/sftp_quant_view.xml',
        'templates/sftp_quant_wizard_view.xml',
        'templates/product_template.xml',
        'wizard/sftp_multi_send.xml',
        'wizard/picking_multi_assign.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'external_dependencies': {
        'python': ['paramiko',
                   'xlsxwriter'],
    },
}