# -*- coding: utf-8 -*-
{
    'name': 'NIIF ASSETS',
    'version': '1.115',
    'category': 'Activos account',
    'complexity': "normal",
    'description': """
        Este modulo permite gestionar una segunda tabla de depreciacion para activos, con politicas independientes.
        Adicionalmente permite realizar un proceso masivo de depreciacion para COLGAP, NIIF O COLGAP & NIIF.
    """,
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'depends': ['account_asset_extended','niif_inventory'],
    'data' : [
        'security/ir.model.access.csv',
        'account_asset_extended_niif.xml',
        ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
