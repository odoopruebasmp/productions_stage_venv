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

from openerp.osv import osv, fields

class sale_order_imported_file(osv.Model):
    '''Imported sale order File'''
    _name = 'sale.order.imported.file'
    _description = __doc__
    _rec_name = 'date'
    _columns = {
        'company_id': fields.many2one('res.company', 'Company',
                                      select=True, readonly=True
                                     ),
        'date': fields.datetime('Import Date', readonly=True, select=True,
                                states={'draft': [('readonly', False)]}
                               ),
        'format': fields.char('File Format', size=20, readonly=True,
                              states={'draft': [('readonly', False)]}
                             ),
        'file': fields.binary('Raw Data', readonly=True,
                              states={'draft': [('readonly', False)]}
                             ),
        'log': fields.text('Import Log', readonly=True,
                           states={'draft': [('readonly', False)]}
                          ),
        'user_id': fields.many2one('res.users', 'Responsible User',
                                   readonly=True, select=True,
                                   states={'draft': [('readonly', False)]}
                                  ),
        'state': fields.selection(
            [('unfinished', 'Unfinished'),
             ('error', 'Error'),
             ('review', 'Review'),
             ('ready', 'Finished'),
            ], 'State', select=True, readonly=True
        ),
    }
    _defaults = {
        'date': fields.date.context_today,
        'user_id': lambda self, cr, uid, context: uid,
    }
sale_order_imported_file()