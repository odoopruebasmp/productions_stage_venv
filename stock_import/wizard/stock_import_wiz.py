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

class import_stock_wiz(osv.TransientModel):
    
    _name = 'import.stock.wiz'
    
    _columns = {
        'file': fields.binary('CSV File'),
    }
    
    def check_data(self, cr, uid, line, count,context=None):
        if len(line) < 4:
            raise osv.except_osv(_('Error !'), _('Selected CSV File Does have columns < 4!'))
        if not line[0] or not line[1] or not line[2] or not line[3]:
            raise osv.except_osv(_('Error !'), _('value is not proper, Please check CSV line %d,'%(count+1)))
    
    def update_product_price(self, cr, uid, product_id, qty, cost_price, old_qty,old_price ,context=None):
        if not context: context = {}
        product_obj = self.pool.get('product.product')
        product_rec = product_obj.browse(cr, uid, product_id, context=context)
        if product_rec.cost_method == 'average':
            if product_rec.qty_available <= 0:
                new_price =  cost_price
            else:
                new_price = ((old_qty * old_price) + ((qty or 1) * cost_price) ) / (old_qty + qty)
            product_obj.write(cr, uid, product_rec.id, {'standard_price': new_price})
        return True
    
    def import_stock(self, cr, uid, ids, context=None):
        if not context: context = {}
        product_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('stock.move')
        rec = self.browse(cr, uid, ids[0], context)
        file_path = tempfile.gettempdir()+'/stock_import.csv'
        f = open(file_path,'wb')
        f.write(rec.file.decode('base64'))
        f.close()
        line_count = 0
        move_list ,partner_dict, account_dict = [], {}, {}
        data_reader = csv.reader(open(file_path))
        for line in data_reader:
            data_dict = {}
            if line_count == 0:
                line_count += 1
                continue
            self.check_data(cr, uid, line, line_count, context)
            product_ids = product_obj.search(cr, uid, [('default_code', '=', line[0])])
            if product_ids:
                data_dict['product_id'] = product_ids[0]
            else:
                raise osv.except_osv(_('Error!'), "product with ref %s not found."%(str(line[0])))
            product_rec = product_obj.browse(cr, uid, data_dict.get('product_id'), context)
            
            if not product_rec.property_stock_procurement.id:
                raise osv.except_osv(_('Error!'), "Procurement Location product not defined in %s."%(str(product_rec.name)))
            data_dict['product_qty'] = float(line[1])
            data_dict['cost_price'] = float(line[2])
            location_ids = location_obj.search(cr, uid, [('name','=',line[3])])
            if location_ids:
                data_dict['location_id'] = location_ids[0]
            else:
                raise osv.except_osv(_('Error!'), "Location %s not found."%(str(line[3])))
            old_qty_avai = product_rec.qty_available
            old_price =  product_rec.standard_price
            if data_dict:
                vals = {}
                move_vals = move_obj.onchange_product_id(cr, uid, [], prod_id = data_dict.get('product_id'), loc_dest_id=data_dict.get('location_id'))
                vals = move_vals.get('value')
                context.update({'picking_type': 'internal'})
                vals.update({
                    'product_id': data_dict.get('product_id'),
                    'location_id': product_rec.property_stock_procurement and product_rec.property_stock_procurement.id or False,
                    'location_dest_id':data_dict.get('location_id'),
                    'type': 'internal',
                    'product_qty': data_dict.get('product_qty'), 
                })
                if data_dict['product_qty'] > 0:
                    move_ids = move_obj.create(cr, uid, vals, context=context)
                    move_obj.action_done( cr, uid, [move_ids], context=context)
                    move_list.append(move_ids)
                self.update_product_price(cr, uid, data_dict.get('product_id'), data_dict.get('product_qty'), data_dict.get('cost_price'), old_qty_avai, old_price ,context=context)
            line_count += 1
        domain = [('id','in',move_list)]
       
        return {
            'domain': domain,
            'name': 'Imported Stock Moves',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'stock.move',
            'type': 'ir.actions.act_window', 
        }
        
import_stock_wiz()
