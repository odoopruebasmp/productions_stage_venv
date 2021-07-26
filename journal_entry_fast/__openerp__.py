# -*- encoding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2012 Serpent Consulting services
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
    'name': 'Journal Entry import fast',
    'version': '0.1',
    'category': 'CSV Import',
    'description': """
        Module will import Journal entrie with lines from csv data.
    """,
    'author': 'Serpent Consulting Services',
    'website': 'http://www.serpentcs.com',
    'depends': ['account'],
    'data': [
           'wizard/journal_entry_import_view.xml',
           'journal_import_view.xml',
    ],
    'installable': True,
    'active': False,
}