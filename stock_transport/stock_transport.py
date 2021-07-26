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
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from datetime import datetime,timedelta
from openerp import netsvc
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

class stock_move(osv.osv):
    _inherit = "stock.move"
    
    def _get_transport(self, cr, uid, ids, name, args, context=None):
        res = {}
        for move in self.browse(cr, uid, ids, context=context):
            if len(move.transport_order_ids) > 0:
                res[move.id] = move.transport_order_ids[0]
        return res
    
    _columns = {
        'transport_id': fields.function(_get_transport, relation='purchase.order', type="many2one", string='Transporte',readonly=True),
        'transport_cost': fields.float('Costo Transporte', digits_compute=dp.get_precision('Account')),
        'transport_order_ids': fields.many2many('purchase.order','transport_stockmove_rel','stock_move_id','transport_id','Transporte Relacionado', readonly=True),
    }

class stock_picking(osv.osv):
    _inherit = "stock.picking"
    
    _columns = {
        'transport_order_id' : fields.many2one('purchase.order', 'Orden Transporte', readonly=True),
    }
    
class stock_picking(osv.osv):
    _inherit = "stock.picking"
    
    _columns = {
        'transport_order_id' : fields.many2one('purchase.order', 'Orden Transporte', readonly=True),
    }

class sale_order(osv.Model):
    _inherit = "sale.order"   
    
    def _get_all_pickings(self, cr, uid, ids, name, args, context=None):
        res = {}
        for po in self.browse(cr, uid, ids, context=context):
            picks = []
            for line in po.order_line:
                for move in line.move_ids:
                    picks.append(move.picking_id.id)
            res[po.id] = picks
        return res
    
    _columns = {
        'stock_picking_ids': fields.function(_get_all_pickings, relation='stock.picking', type="one2many", string='Remisiones relacionadas',readonly=True),
    }
    
class purchase_order(osv.Model):
    _inherit = "purchase.order"
    
    def _get_transport_lines(self, cr, uid, ids, name, args, context=None):
        res = {}
        for transport in self.browse(cr, uid, ids, context=context):
            list = []
            list += [x.id for x in transport.order_line if (x.product_id.type == 'service' and x.product_id.landed_cost_ok)]
            res[transport.id] = list
        return res
    
    def _get_local_subtotal_transport(self, cr, uid, ids, name, arg, context=None):
        res={}
        for record in self.browse(cr, uid, ids, context=context):
            total = 0
            for line in record.transport_order_line_ids:
                total += line.price_subtotal*record.rate_pactada
            res[record.id] = total
        return res
    
    def _get_all_pickings(self, cr, uid, ids, name, args, context=None):
        res = {}
        for po in self.browse(cr, uid, ids, context=context):
            picks = []
            for line in po.order_line:
                for move in line.move_ids:
                    picks.append(move.picking_id.id)
            res[po.id] = picks
        return res
    
    def _amount_transport(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {
                    'total_product_price':0.0,
                    'total_product_weight':0.0,
            }
            total_product_price = 0.0
            total_product_weight = 0.0
            
            for move in order.transport_stock_move_ids:
                total_product_price += move.price_unit_total
                total_product_weight += move.weight
            
            res[order.id]['total_product_price'] = total_product_price
            res[order.id]['total_product_weight'] = total_product_weight
            
        return res
    
    _columns = {    
        'transport_order_line_ids': fields.function(_get_transport_lines, relation='purchase.order.line', type="one2many", string='Transportes',readonly=True),
        'local_subtotal_transport': fields.function(_get_local_subtotal_transport, type='float', digits_compute=dp.get_precision('Account'), string='Total Servicios de Transporte en moneda local', store=True),
        'transport' : fields.boolean('Servicio Transporte', readonly=True),
        'transport_stock_move_ids': fields.many2many('stock.move','transport_stockmove_rel','transport_id','stock_move_id','Movimientos de Stock', readonly=True, states={'draft': [('readonly', False)],'confirmed': [('readonly', False)],'approved': [('readonly', False)],'sent': [('readonly', False)]}),
        
        'stock_picking_ids': fields.function(_get_all_pickings, relation='stock.picking', type="one2many", string='Remisiones relacionadas',readonly=True),
        'stock_picking_transport_ids': fields.one2many('stock.picking', 'transport_order_id', 'Remisiones de Transporte', readonly=True),
        
        'origin_id' : fields.many2one('stock.location', 'Origen', states={'draft': [('readonly', False)]}, required=True),
        'volume': fields.float('Volumen Reportado', help="The volume in m3."),
        'weight': fields.float('Peso Reportado', digits_compute=dp.get_precision('Stock Weight'), help="The gross weight in Kg."),
        'products_value': fields.float('Precio Productos Transportados', digits_compute=dp.get_precision('Account')),
        'calculate_method': fields.selection((('price','Por Precio'), ('weight','Por Peso')),'Metodo Prorateo', help="""El metodo con el cual se calculara el costo del producto
        'Por Linea': El precio unitario de cada linea se divide por el precio total, este porcentaje se multiplica por el valor del transporte; este sera el costo de transporte para la linea.
        'Por Peso: El peso de cada linea se divide por el peso total, este porcentaje se multiplica por el valor del transporte; este sera el costo de transporte para la linea'
        """),
        'total_product_price': fields.function(_amount_transport, method=True, digits_compute=dp.get_precision('Account'), 
                                          store={
                                          'purchase.order': (lambda self, cr, uid, ids, c={}: ids, None, 10)},
                                           type='float', string='Total Valor Transportado',
                                           multi='trans_sums',),
        'total_product_weight': fields.function(_amount_transport, method=True, digits_compute=dp.get_precision('Stock Weight'), 
                                          store={
                                          'purchase.order': (lambda self, cr, uid, ids, c={}: ids, None, 10)},
                                           type='float', string='Total Peso Transportado',
                                           multi='trans_sums',),
    }
    
    _defaults = { 
        'calculate_method': 'price',
    }
    
    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default['transport_stock_move_ids'] = []
        return super(purchase_order, self).copy(cr, uid, id, default, context)
    
    def _prepare_order_line_move(self, cr, uid, order, order_line, picking_id, group_id, context=None):
        res = super(purchase_order, self)._prepare_order_line_move(cr, uid, order, order_line, picking_id, group_id, context=context)
        if res and res[0] and res[0]['location_id']:
            res[0]['location_id'] = order.origin_id and order.origin_id.id or False
        return res
    
    def onchange_partner_id(self, cr, uid, ids, partner_id, context=None):
        res = super(purchase_order, self).onchange_partner_id(cr, uid, ids, partner_id, context=context)
        partner = self.pool.get('res.partner')
        if partner_id:
            supplier = partner.browse(cr, uid, partner_id)
            res['value']['origin_id'] = supplier.property_stock_supplier and supplier.property_stock_supplier.id or False
        return res
    
    def _create_pickings(self, cr, uid, order, order_lines, picking_id=False, context=None):
        if not picking_id:
            picking_id = self.pool.get('stock.picking').create(cr, uid, self._prepare_order_picking(cr, uid, order, context=context))
        todo_moves = []
        stock_move = self.pool.get('stock.move')
        wf_service = openerp.netsvc.LocalService("workflow")
        move_order_lines = []
        transport = False
        for order_line in order_lines:
            if not order_line.product_id:
                continue
            if True:
                move = stock_move.create(cr, uid, self._prepare_order_line_move(cr, uid, order, order_line, picking_id, context=context))
                if order_line.move_dest_id:
                    order_line.move_dest_id.write({'location_id': order.location_id.id})
            if (order_line.product_id.type == 'service' and order_line.product_id.landed_cost_ok):
                transport = True
            else:
                todo_moves.append(move)
        
        if transport:
            for line_id in todo_moves:
                self.write(cr, uid, order.id, {'transport_stock_move_ids':[(4, line_id)]}, context=context)
                self.prorate_cost(cr, uid, [order.id], context=context)
                
        stock_move.action_confirm(cr, uid, todo_moves)
        stock_move.force_assign(cr, uid, todo_moves)
        wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
        
        return [picking_id]
    
    def prorate_cost(self, cr, uid, ids, context=None):
        if not context: context = {}
        vals={}
        stock_move_obj = self.pool.get('stock.move')
        stock_picking_obj = self.pool.get('stock.picking')
        for po in self.browse(cr, uid, ids, context=context):
            for move in po.transport_stock_move_ids:
                if po.calculate_method == 'price':
                    if po.total_product_price <= 0:
                        raise osv.except_osv(_('Error!'), _('La suma del costo de los movimientos seleccionados da cero "%s".') % po.name)
                    prorate = (move.price_unit_total/po.total_product_price)
                elif po.calculate_method == 'weight':
                    if po.total_product_weight <= 0:
                        raise osv.except_osv(_('Error!'), _('La suma del peso de los movimientos seleccionados da cero "%s".') % po.name)
                    prorate = (move.weight/po.total_product_weight)
                else:
                    raise osv.except_osv(_('Error!'), _('No selecciono un metodo de prorateo de transporte para la orden "%s".') % po.name)
                    
                cost = prorate*po.local_subtotal_transport
                stock_move_obj.write(cr, uid, move.id, {'transport_cost':cost, 'cost':(move.price_unit_total+cost)/move.product_qty}, context=context)
                stock_picking_obj.write(cr, uid, [x.id for x in po.picking_ids], {'transport_order_id':po.id}, context=context)
                    
        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
