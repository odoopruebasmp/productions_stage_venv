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
    'name': 'Stock Import Extended',
    'version': '0.2',
    'author' : 'Avancys',
    'website': 'http://www.avancys.com',
    'category': 'Warehouse',
    'depends': ['stock'],
    'description': '''
        Features:
        It will import csv file and do stock movement
        A wizard can update the average cost of the product via csv file with ref and price.
    ''',
    'data': [
             'wizard/stock_import_wiz_view.xml',
             'wizard/update_product_cost_view.xml',
             'stock_extended_view.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}