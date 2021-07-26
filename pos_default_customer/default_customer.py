# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import logging

import openerp

from openerp import tools
from openerp.osv import fields, osv
from openerp.tools.translate import _

class pos_config(osv.osv):
    _inherit = 'pos.config' 
    _columns = {
        'default_customer_id': fields.many2one('res.partner','Default Customer', domain=[('customer','=',True)]),
    }


class res_partner(osv.osv):
    _inherit = 'res.partner'
    
    def get_default_partner(self, cr, uid, query, context=None):
        if context is None:
            context = {}
        cr.execute('''SELECT id,name,street,city,state_id,country_id,vat,phone,zip,mobile,email,ean13,write_date FROM res_partner WHERE customer=True and id=%d'''% (query,))
        result = cr.dictfetchall()
#         return self.search_read(cr, uid, [('name','ilike',query),('customer','=',True)], ['id','name','street','city','state_id','country_id','vat','phone','zip','mobile','email','ean13','write_date'], order='id asc', context=context)
        return result

    def get_new_partner(self, cr, uid, query, context=None):
        if context is None:
            context = {}
        cr.execute("SELECT id,name,street,city,state_id,country_id,vat,phone,zip,mobile,email,ean13,write_date FROM res_partner WHERE customer=True and name ilike %s", (query+'%',))
        result = cr.dictfetchall()
#         return self.search_read(cr, uid, [('name','ilike',query),('customer','=',True)], ['id','name','street','city','state_id','country_id','vat','phone','zip','mobile','email','ean13','write_date'], order='id asc', context=context)
        return result
#        return self.search_read(cr, uid, [('name','ilike',query),('customer','=',True)], ['id','name','street','city','state_id','country_id','vat','phone','zip','mobile','email','ean13','write_date'], order='id asc', context=context)
