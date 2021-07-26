# -*- coding: utf-8 -*-
{
    "name": "Trial Balance",
    "version": "1.0",
    "depends": ["account"],
    "author": "Avancys SAS",
    "website": 'http://www.avancys.com',
    "category": "Trial Balance Report",
    "description": """
        This module customizes Trial Balance
    """,
    "init_xml": [],
    'data': [ "wizard/account_report_account_balance_view.xml","trial_balance_report_view.xml"],
    'installable': True,
    'auto_install':False,
    'application':True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: