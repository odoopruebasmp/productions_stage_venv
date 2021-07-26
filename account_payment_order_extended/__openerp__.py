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
    'name': 'Suppliers Payment Management extended',
    'version': '1.0',
    'category': 'Accounting & Finance',
    'description': """

Manage Customer Claims.
=======================
Module to manage the payment of your supplier invoices.
=======================================================

This module allows you to create and manage your payment orders, with purposes to
--------------------------------------------------------------------------------- 
    * serve as base for an easy plug-in of various automated payment mechanisms.
    * provide a more efficient way to manage invoice payment.

The confirmation of a payment order will create accounting entries  and also 
records the fact that you gave your payment order to your bank.

    """,
    
    'author': 'Avancys SAS',
    'website': 'www.avancys.com',
    'depends': ['avancys_tools','account_analytic_avancys','account_payment','advance_supplier'],
    'data': [ 
        'account_payment_order_extended_view.xml',
        'account_payment_order_workflow_extended_view.xml',
        'report/Forma-continua.xml',
        'wizard/account_supplier_payment_wizard_view.xml'
    ],
    'installable': True,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
