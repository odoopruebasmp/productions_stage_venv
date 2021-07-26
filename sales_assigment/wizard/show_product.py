# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2014 Avancys SAS
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

class wiz_show_lines(osv.TransientModel):
    
    _name = 'wiz.show.lines'
    
    def show_lines(self, cr, uid, ids, context=None):
        '''
        will show the line which has product has less qty on the other sale order
        '''
        if not context: context = {}
        line_obj = self.pool.get('sale.order.line')
        order_obj = self.pool.get('sale.order')
        product_dict = {}
        quote_ids = order_obj.search(cr, uid, [('state', '=', 'draft')])
        for quote_id in quote_ids:
            line_ids = line_obj.search(cr, uid, [('order_id', '=', quote_id)])
            for line in line_obj.browse(cr, uid, line_ids, context=context):
                if product_dict.get(line.product_id.id):
                    product_dict.update({line.product_id.id: product_dict.get(line.product_id.id) + line.product_uom_qty})
                else:
                    product_dict[line.product_id.id] = line.product_uom_qty
        line_list = []
        for quote_id in quote_ids:
            line_ids = line_obj.search(cr, uid, [('order_id', '=', quote_id)])
            for line in line_obj.browse(cr, uid, line_ids, context=context):
                if line.product_id.qty_available <= product_dict.get(line.product_id.id):
                    line_list.append(line.id)
        model_data =self.pool.get('ir.model.data')
        tree_view = model_data.get_object_reference(cr, uid, 'sales_assigment', 'sale_assignment_view_order_line_tree')
        search_view = model_data.get_object_reference(cr, uid, 'sales_assigment', 'sale_assignment_view_order_line_search')
        domain = [('id', 'in', line_list)]
        
        for line in line_obj.browse(cr, uid, line_list, context):
            temp_qty = line.proposed_qty
            temp_write = line_obj.write(cr, uid, [line.id], {'proposed_qty': 1}, context)
            if temp_write:
                line_obj.write(cr, uid, [line.id], {'proposed_qty': temp_qty}, context)
        
        return {
              'name': _('Analytic Entries by line'),
              'view_type': 'form',
              "view_mode": 'tree,form',
              'res_model': 'sale.order.line',
              'type': 'ir.actions.act_window',
              'views': [(tree_view and tree_view[1] or False, 'tree')],
              'search_view_id': search_view and search_view[1] or False,
              'domain': domain,
              'context': context,
        }
    
wiz_show_lines()