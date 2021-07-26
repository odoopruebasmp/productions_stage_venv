# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2014 Avancys SAS
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
    'name': 'Sales Assignment',
    'version': '0.1',
    'author':'Avancys',
    'website':'www.avancys.com',
    'category': 'Sales Management',
    'depends': ['sale','sales_import_mp'],
    'description': '''
        user can update the sale line qty based on qty available.
    ''',
    'init_xml': [],
    'update_xml': [
        'sales_assigment_view.xml',
        'wizard/assign_proposed_qty_view.xml',
        'wizard/show_product_view.xml',
        'wizard/confirm_quote_view.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}