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
    'name': 'Purchase Import',
    'version': '1.0',
    'depends': ['advance_supplier','stock_transport','event','inventory_account'],
    'author' : 'Avancys',
    'website': 'http://www.avancys.com',
    'description': """
         Purchase Import
         control importation of product and add additional cost to importation product.
    """,
    'category': 'Purchases',
    'data': [
        "security/security.xml",
        "purchase_import_view.xml",
        "purchase_import_data.xml",
        "purchase_import_workflow.xml",
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
