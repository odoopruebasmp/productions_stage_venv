# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 Serpent Consulting services
#                  All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Imporation of Bank Statements Import: Davivienda,Helm,Bancolombia',
    'version': '0.2',
    'author' : 'Avancys',
    'website': 'http://www.avancys.com',
    'category': 'Banking addons',
    'depends': ['account_analytic_avancys','account_payment', 'avancys_help'],
    'description': '''
        Module to import Helm Format bank statement files. Based
        on the Banking addons framework.
    ''',
    'data': [
        'security/banking_security.xml',
        "wizard/transaction_line_view.xml",
        "account_banking_view.xml",
        "wizard/bank_import_view.xml",
        "account_banking_conciliation_tour.xml",
        "views/account_banking_conciliation.xml",
        "report/banking_conciliation.xml",
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}

