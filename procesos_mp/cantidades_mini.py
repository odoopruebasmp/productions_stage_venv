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
from openerp.osv import fields,osv


class product_product(osv.Model):
    _inherit = 'product.product'
    
    _columns = {
                'min_qty' : fields.integer('Minimum Quantity')
    }
    
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        if not context: context = {}
        
        res = super(product_product, self).search(cr, user, args, offset, limit, order, context, count)
        if context.get('product_candidades'):
            vals = []
            for rec in self.read(cr, user, res, ['qty_available', 'min_qty'], context):
                if rec.get('qty_available') < rec.get('min_qty'):
                    vals.append(rec.get('id'))
            return vals
        return res 

product_product()