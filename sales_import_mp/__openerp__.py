# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2013 Avancys SAS
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
    'name': 'Sale Import MP',
    'version': '0.1',
    'author' : 'Serpent Consulting Services Pvt. Ltd.',
    'website': 'http://www.serpentcs.com',
    'category': 'Sales Management',
    'depends': ['sale', 'product_mp', 'procesos_mp', 'inventory_account'],
    'description': '''
        It will import xlsx the Based on a xlsx file it will import sales order in OpenERP.
    ''',
    'init_xml': [],
    'update_xml': [
        'security/ir.model.access.csv',
        "wizard/sales_import_mp_wiz_view.xml",
        "sales_import_mp_view.xml",
        "imported_sale_order_log_view.xml",
        "control_despachos_view.xml",
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}

