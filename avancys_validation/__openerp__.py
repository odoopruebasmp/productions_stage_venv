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
    'name': 'Validation Avancys',
    'version': '1.0',
    'author' : 'Avancys',
    'website': 'http://www.avancys.com.co',
    'category': 'Contabilidad',
    'depends': ['inventory_account'],
    'description': '''
        Este modulo permite realizar o ejecturar procesos que ajustan errores del sistema y validan las diferencias
    ''',
    'init_xml': [],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'validation_view.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}

