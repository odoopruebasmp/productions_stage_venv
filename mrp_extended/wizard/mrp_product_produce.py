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

from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _

class mrp_product_produce_line(osv.osv_memory):
    _inherit="mrp.product.produce.line"

    _columns = {
        'move_id': fields.many2one('stock.move', 'Movimiento Asociado'),
        'string_availability_info': fields.char('Reserva', readonly=True),
    }
    
class mrp_product_produce(osv.osv_memory):
    _inherit="mrp.product.produce"
    
    def _get_product_qty(self, cr, uid, context=None):
        if context is None:
            context = {}
        prod = self.pool.get('mrp.production').browse(cr, uid, context['active_id'], context=context)
        quantity = 0.0
        for move in prod.move_created_ids:
            if move.product_id == prod.product_id and move.state != 'draft':
                quantity += move.product_uom_qty
        return quantity
    
    def on_change_qty(self, cr, uid, ids, product_qty, consume_lines, context=None):
        # res = super(mrp_product_produce, self).on_change_qty(cr, uid, ids, product_qty, consume_lines, context=context)
        
        prod_obj = self.pool.get("mrp.production")
        uom_obj = self.pool.get("product.uom")
        move_obj = self.pool.get("stock.move")
        lot_obj = self.pool.get("stock.production.lot")
        production = prod_obj.browse(cr, uid, context['active_id'], context=context)
        consume_lines = []
        new_consume_lines = []
        if product_qty > 0.0:
            product_uom_qty = uom_obj._compute_qty(cr, uid, production.product_uom.id, product_qty, production.product_id.uom_id.id)
            consume_lines = prod_obj._calculate_qty(cr, uid, production, product_qty=product_uom_qty, context=context)
            sorted_lines=sorted(production.move_lines, key=lambda x: x.create_date)
            for line in consume_lines:
                if line['lot_id']:
                    lot = lot_obj.browse(cr, uid, line['lot_id'], context=context)
                    line.update({'string_availability_info':'['+lot.name+']'+'('+str(line['product_qty'])+')'})
                    # line.update({'string_availability_info':'['+lot.name+']'+'('+str(line['product_qty'])+')', 'move_id': move.id})
        
        for consume in consume_lines:
            new_consume_lines.append([0, False, consume])
        return {'value': {'consume_lines': new_consume_lines}}
    
    _defaults = {
         'product_qty': _get_product_qty,
    }
    
    def do_produce(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        prod = self.pool.get('mrp.production').browse(cr, uid, context['active_id'], context=context)
        for data in self.browse(cr, uid, ids, context=context):
            if data.mode == 'consume_produce':
                for workcenter in prod.workcenter_lines:
                    if workcenter.state != 'done':
                        raise osv.except_osv(_('Error !'),_("Primero debe terminar la orden de  trabajo '%s'")%(workcenter.name))
                quantity = 0
                for move in prod.move_created_ids:
                    if move.product_id == prod.product_id and move.state != 'draft':
                        quantity += move.product_uom_qty
                if data.product_qty > quantity:
                    raise osv.except_osv(_('Error !'),_("La cantidad producida no puede ser mayor a la pendiente"))
            if data.product_qty <= 0:
                raise osv.except_osv(_('Error !'),_("La cantidad producida no puede ser menor o igual a 0"))
            
        res = super(mrp_product_produce, self).do_produce(cr, uid, ids, context=context)
        return res
    
#