# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Avancys SAS http://www.avancys.com
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
    'name': 'Notificacion de Pagos',
    'version': '1.0',
    'depends': ['account_voucher_extended','avancys_tools','account_payment_order_extended'],
    'author' : 'Avancys SAS',
    'website': 'http://www.avancys.com',
    'description': """
        Este modulo permite notificar el pago a proveedores y clientes
    """,
    'category': 'Accounting & Finance',
    'init_xml': [],
    'data': [
        'account_voucher_view.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
