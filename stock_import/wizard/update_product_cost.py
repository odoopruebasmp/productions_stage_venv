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

from openerp.osv import osv, fields
from openerp.tools.translate import _
import csv
import tempfile

class update_product_cost(osv.TransientModel):
    
    _name = 'update.product.cost'
    
    _columns = {
        'file': fields.binary('CSV File'),
    }
    
    def check_data(self, cr, uid, line, count,context=None):
        if len(line) < 2:
            raise osv.except_osv(_('Error !'), _('Selected CSV File Does have columns < 2!'))
        if not line[0] or not line[1]:
            raise osv.except_osv(_('Error !'), _('value is not proper, Please check CSV line %d,'%(count+1)))
    
    
    def update_cost(self, cr, uid, ids, context=None):
        if not context: context = {}
        product_obj = self.pool.get('product.product')
        rec = self.browse(cr, uid, ids[0], context)
        file_path = tempfile.gettempdir()+'/stock_import.csv'
        f = open(file_path,'wb')
        f.write(rec.file.decode('base64'))
        f.close()
        line_count = 0
        product_list = []
        data_reader = csv.reader(open(file_path))
        for line in data_reader:
            product_id = False
            if line_count == 0:
                line_count += 1
                continue
            self.check_data(cr, uid, line, line_count, context)
            product_ids = product_obj.search(cr, uid, [('default_code', '=', line[0])])
            if product_ids:
                product_id = product_ids[0]
            cost_price = float(line[1])
            product_rec = product_obj.browse(cr, uid, product_id, context=context)
            if product_rec.cost_method == 'average':
                product_obj.write(cr, uid, product_rec.id, {'standard_price': cost_price})
                product_list.append(product_rec.id)
        domain = [('id','in',product_list)]
        return {
            'domain': domain,
            'name': 'Updated Product',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'product.product',
            'type': 'ir.actions.act_window',
        }
        
update_product_cost()
