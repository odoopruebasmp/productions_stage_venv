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
    'name': 'Stock Return More Products',
    'version': '0.1',
    'author': 'Avancys',
    'website': 'www.odoo.com.co',
    'category': 'Warehouse',
    'depends': ['stock_return'],
    'description': '''
        Modulo para la gestion de devoluciones especial para More Products
    ''',
    'init_xml': [],
    'data': [
        'stock_return_view.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}