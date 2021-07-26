# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 AVANCYS SAS
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
    'name': 'Stock Extended',
    'version': '0.1',
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'category': 'Warehouse',
    'depends': ['account_analytic_avancys','stock_account','delivery','product_expiry'],
    'description': '''
        Features:
        New "In Transit" & "Delivered" state in Delivery order 
    ''',
    'init_xml': [],
    'data': [
        'security/stock_security.xml', 
        "stock_extended_view.xml",
        'wizard/stock_move_view.xml',
        'security/ir.model.access.csv',               
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}
