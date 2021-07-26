# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 AVANCYS SAS
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
from openerp import fields as fields2
from openerp.tools.translate import _
import time
from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp import netsvc
import openerp.addons.decimal_precision as dp
import logging
from openerp import SUPERUSER_ID
from openerp.tools.float_utils import float_compare, float_round
from openerp import models, api
_logger = logging.getLogger(__name__)

class stock_kardex(osv.Model):
    _name = 'stock.kardex'
    
    _columns= {
        'name': fields.char(string='Nombre', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'partner_id': fields.many2one('res.partner', string='Cliente', readonly=True, states={'draft':[('readonly',False)]}),
        'date_start': fields.datetime(string='Fecha Inicial', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'date_end': fields.datetime(string='Fecha Final', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'product_id': fields.many2one('product.product', 'Producto', required=True, select=True, readonly=True, states={'draft':[('readonly',False)]}),
        'location_id': fields.many2one('stock.location', 'Ubicacion', required=True, select=True, readonly=True, states={'draft':[('readonly',False)]}),
        'state': fields.selection([('draft', 'Nuevo'),
                                   ('confirmed', 'Confirmado'),
                                   ('done', 'Realizado'),
                                   ], 'Status', readonly=True, select=True),
        'move_ids': fields.many2many('stock.move', 'kardex_moves_ids', 'kardex_id', 'move_id', 'Movimientos', readonly=True),
    }
    
    _defaults = {
        'state': 'draft',
    }
    
    def confirmar(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'confirmed'}, context=context)        
        return True

    def borrador(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'draft'}, context=context)        
        return True


    def calcular_kardex(self, cr, uid, ids, context=None):
        kardex_moves_ids = self.pool.get('stock.move')
        for kardex in self.browse(cr, uid, ids, context=context):
            move_ids = kardex_moves_ids.search(cr, uid, [('product_id','=',kardex.product_id.id),('location_id','=',kardex.location_id.id),('date','>=',kardex.date_start),('date','<=',kardex.date_end),('state','=','done')],context=context)

            move_ids += kardex_moves_ids.search(cr, uid, [('product_id','=',kardex.product_id.id),('location_dest_id','=',kardex.location_id.id),('date','>=',kardex.date_start),('date','<=',kardex.date_end),('state','=','done')],context=context)

            move_lines = self.pool.get('stock.move').browse(cr, uid, move_ids, context=context)

            sorted_lines=sorted(move_lines, key=lambda x: x.date)
            self.write(cr, uid, ids , {'move_ids':[(6, 0,[x.id for x in sorted_lines])]}, context=context)
        return True


class res_company(models.Model):
    _inherit = 'res.company'

    block_sale_warehouse=fields2.Boolean(string='Bloqueo venta por almacen', help="No deja confirmar ventas que no tengan disponibilidad en la bodega seleccionada")
    zero_cost_moves_incomes=fields2.Boolean(string='Permitir Entradas con Costo Cero ', help="Permitir que se efectuen entradas al inventario con un costo igual a cero (recordar que esto afecta directamente el costo promedio del producto involucrado")

class sale_order(models.Model):
    _inherit = 'sale.order'

    def action_button_confirm(self, cr, uid, ids, context=None):
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        for sale in self.browse(cr, uid, ids, context=context):
            if sale.company_id.block_sale_warehouse:
                products = {}
                for line in sale.order_line:
                    # context.update({'warehouse':sale.warehouse_id.id})
                    product = line.product_id
                    if product.type == 'product':
                        if product.id not in products:
                            product_qty = uom_obj._compute_qty_obj(cr, uid, line.product_uom, line.product_uom_qty, line.product_id.uom_id, context=context)
                            # virtual = product.virtual_available
                            # entrante = product.incoming_qty
                            cr.execute("SELECT sum(qty) from stock_quant WHERE product_id={p} and location_id = {l} and reservation_id is Null".format(p=line.product_id.id, l=sale.warehouse_id.out_type_id.default_location_src_id.id))
                            available = cr.fetchone()[0]
                            products[product.id] = {'name':product.name,'available':available,'product_qty':product_qty}
                        else:
                            product_qty = uom_obj._compute_qty_obj(cr, uid, line.product_uom, line.product_uom_qty,
                                                                   line.product_id.uom_id, context=context)
                            cr.execute(
                                "SELECT sum(qty) from stock_quant WHERE product_id={p} and location_id = {l} and reservation_id is Null".format(
                                    p=line.product_id.id, l=sale.warehouse_id.out_type_id.default_location_src_id.id))
                            available = cr.fetchone()[0]
                            products[product.id]['product_qty'] += product_qty
                for t in products.values():
                    if t['available'] < t['product_qty']:
                        raise osv.except_osv(_('Error!'), _('Solo hay disponible "%s" del producto "%s" en el almacen "%s"')%(t['available'],t['name'],sale.warehouse_id.name))
                        
        super(sale_order, self).action_button_confirm(cr, uid, ids, context=context)
        return True
    
    def action_ship_create(self, cr, uid, ids, context=None):
        super(sale_order, self).action_ship_create(cr, uid, ids, context=context)
        picking_obj=self.pool.get('stock.picking')
        for sale in self.browse(cr, uid, ids, context=context):
            if sale.company_id.block_sale_warehouse:
                stock_picking_ids = picking_obj.search(cr, uid, [('group_id', '=', sale.procurement_group_id.id),('state', '!=', 'cancel')], context=context)
                picking_obj.action_assign(cr, uid, stock_picking_ids, context=context)
                cr.execute(''' UPDATE stock_picking SET  note = %s WHERE id in %s''',(sale.note, tuple(stock_picking_ids)))
        return True
    
class product_template(osv.Model):
    _inherit = 'product.template'
    
    _columns= {
        'lot_sequence_id': fields.many2one('ir.sequence', string='Secuencia del lote', copy=False),
    }

class stock_production_lot(osv.Model):
    _inherit = "stock.production.lot"
    _order = 'create_date desc, name desc'
    
    def _get_stock_avancys(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        uom_obj = self.pool.get('product.uom')
        for lot in self.browse(cr, uid, ids, context=context):
            cant = 0
            if lot.quant_ids:
                for quant in lot.quant_ids:
                    if quant.location_id.usage == 'internal':
                        cant += quant.qty
            res[lot.id] = cant
        return res
    
    def _get_prodlots_from_quant(self, cr, uid, ids, context=None):
        list = []
        quant_obj = self.pool.get('stock.quant')
        for quant in quant_obj.browse(cr, uid, ids, context=context):
            if quant.lot_id:
                list.append(quant.lot_id.id)
        return list
    
    _columns = {
        'quant_ids': fields.one2many('stock.quant', 'lot_id', 'Quants', readonly=False),
        'stock_available': fields.function(_get_stock_avancys, readonly=True, fnct_search=None, digits_compute=dp.get_precision('Product Unit of Measure'), 
                                            store={
                                                'stock.production.lot': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                                'stock.quant': (_get_prodlots_from_quant, None, 10),
                                            },
                                            type='float', string='Available'),
    }
    
    _defaults = {
        'name': '',
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name,product_id)', 'El serial debe ser unico por producto,')
    ]
    
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if not vals.get('name'):
            sequence_id = self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context=context).lot_sequence_id
            if sequence_id:
                vals.update({'name': self.pool.get('ir.sequence').next_by_id(cr, uid, sequence_id.id, context=context)})
        
        result = super(stock_production_lot, self).create(cr, uid, vals, context=context)
        return result
    
    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'name':'',
        })
        return super(stock_production_lot, self).copy(cr, uid, id, default, context)
       
class stock_transaction_type(osv.Model):
    _name = 'stock.transaction.type'
    
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'debit_account': fields.many2one('account.account', 'Debit Account', required=True), 
        'credit_account': fields.many2one('account.account', 'Credit Account', required=True),
        'cost_update':fields.boolean('Update product cost?'),
    }
    
class stock_picking(models.Model):
    _inherit = 'stock.picking'

    warehouse_id=fields2.Many2one('stock.warehouse', 'Warehouse', readonly=False, states={'done':[('readonly',True)]})
    source_location=fields2.Many2one('stock.location', 'Ubicacion Origen')
    dest_location=fields2.Many2one('stock.location', 'Ubicacion Destino')
    transaction=fields2.Boolean('Is Transaction')
    carrier_cedula=fields2.Char('Cedula Transportista', readonly=False, states={'done':[('readonly',True)]})
    carrier_placa=fields2.Char('Placa Transportista', readonly=False, states={'done':[('readonly',True)]})
    carrier_coment=fields2.Text('Observaciones', readonly=False, states={'done':[('readonly',True)]})    
    transaction_type=fields2.Many2one('stock.transaction.type', 'Transaction Type')
    picking_invoice_id=fields2.Many2one('account.invoice', 'Factura', copy=False)
    move_lines=fields2.One2many('stock.move', readonly=True, states={'draft':[('readonly',False)]})
    
    #para evitar los casos extranos donde se duplica el picking
    _sql_constraints = [('dont_repeat', 'unique(backorder_id,origin,state)', 'No se pueden tener 2 ordenes de despacho para el mismo pedido! Verificar si ya se ha creado una orden!,')]

class procurement_order(osv.osv):
    _inherit = "procurement.order"

    def _run_move_create(self, cr, uid, procurement, context=None):
        vals = super(procurement_order, self)._run_move_create(cr, uid, procurement, context=context)
        vals.update({'sale_line_id':procurement.sale_line_id.id,'price_unit':procurement.sale_line_id.price_unit})  
        return vals

class stock_move(osv.osv):
    _name = "stock.move"
    _inherit = ['stock.move','mail.thread']
    _order = 'date asc, id'
    
    def _get_string_qty_information(self, cr, uid, ids, field_name, args, context=None):
        settings_obj = self.pool.get('stock.config.settings')
        uom_obj = self.pool.get('product.uom')
        res = dict.fromkeys(ids, '')
        for move in self.browse(cr, uid, ids, context=context):
            info = ''
            if move.state in ('draft', 'done', 'cancel') or move.location_id.usage != 'internal':
                res[move.id] = info  # 'not applicable' or 'n/a' could work too
                continue
            group = {}
            for quant in move.reserved_quant_ids:
                lote = quant.lot_id or False
                quantity = uom_obj._compute_qty_obj(cr, uid, move.product_id.uom_id, quant.qty, move.product_uom, context=context)
                if lote:
                    if lote.id in group:
                        group[lote.id]['quantity'] += quantity
                    else:
                        group[lote.id] = {'quantity':quantity,'lot_name':lote.name}
                else:
                    if 0 in group:
                        group[0]['quantity'] += quantity
                    else:
                        group[0] = {'quantity':quantity,'lot_name':False}
            for value in group.values():
                if value['lot_name']:
                    info += '['+value['lot_name']+']'
                info += _('(%s)') % (str(value['quantity']))
                info += '\n'
                    
            res[move.id] = info
        return res
    
    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, lazy=True):
        if 'cost' not in fields:
            fields.append('total_cost')
            fields.append('product_uom_qty')
        result = super(stock_move, self).read_group(cr, uid, domain, fields, groupby, offset=offset, limit=limit, context=context, orderby=orderby, lazy=lazy)  
        for res in result:
            if 'cost' in res and 'total_cost' in res and 'product_uom_qty' in res:
                if res['product_uom_qty'] > 0.0:
                    res.update({'cost':abs(res['total_cost']/res['product_uom_qty'])})
                else:
                    res.update({'cost':0.0})
        return result
    
    def _total_cost(self, cr, uid, ids, name, args, context=None):
        res = {}
        currency_obj = self.pool.get('res.currency')
        for move in self.browse(cr, uid, ids, context=context):
            # amount = currency_obj.round(cr, uid, move.local_currency_id, move.cost*move.product_qty)
            amount = move.cost*move.product_qty
            res[move.id] =  amount
        return res
    
    def _get_remaining_reseved_qty(self, cr, uid, ids, field_name, args, context=None):
        uom_obj = self.pool.get('product.uom')
        res = {}
        for move in self.browse(cr, uid, ids, context=context):
            remaining = move.product_qty
            for quant in move.reserved_quant_ids:
                remaining -= quant.qty
            res[move.id] = remaining
        return res
    
    def _cantidad(self, cr, uid, ids, name, args, context=None):
        res = {}
        for move in self.browse(cr, uid, ids, context=context):
            # if move.product_uos:
            #     res[move.id] = move.product_id.uos_coeff * move.product_uom_qty
            if move.product_uos:
                if move.product_id.uom_id.uom_type == 'bigger':
                    factor=move.product_id.uom_id.factor_inv
                    res[move.id] = move.product_uom_qty / factor
                elif move.product_id.uom_id.uom_type == 'smaller':
                    factor=1/move.product_id.uom_id.factor
                    res[move.id] = move.product_uom_qty * factor

        return res
        
    def _get_total(self, cr, uid, ids, name, args, context=None):
        res = {}
        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = move.price_unit * move.product_qty
        return res
    
    _columns = dict(
        remaining_reserved_qty=fields.function(_get_remaining_reseved_qty, type='float', string='Cantidad Restante',
                                               digits_compute=dp.get_precision('Product Unit of Measure'),
                                               states={'done': [('readonly', True)]}, store=True),
        product_uom=fields.many2one('product.uom', 'Unit of Measure', required=True, readonly=True,
                                    states={'draft': [('readonly', False)]}),
        product_uom_qty=fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),
                                     required=True, readonly=True, states={'draft': [('readonly', False)]},
                                     help="This is the quantity of products from an inventory "
                                          "point of view. For moves in the state 'done', this is the "
                                          "quantity of products that were actually moved. For other "
                                          "moves, this is the quantity of product that is planned to "
                                          "be moved. Lowering this quantity does not generate a "
                                          "backorder. Changing this quantity on assigned moves affects "
                                          "the product reservation, and should be done with care."
                                     ),
        product_id=fields.many2one('product.product', 'Product', required=True, select=True,
                                   domain=[('type', '<>', 'service')], readonly=True,
                                   states={'draft': [('readonly', False)]}), state=fields.selection([('draft', 'New'),
                                                                                                     ('cancel',
                                                                                                      'Cancelled'),
                                                                                                     ('waiting',
                                                                                                      'Waiting Another Move'),
                                                                                                     ('confirmed',
                                                                                                      'Waiting Availability'),
                                                                                                     ('assigned',
                                                                                                      'Available'),
                                                                                                     ('done', 'Done'),
                                                                                                     ], 'Status',
                                                                                                    readonly=True,
                                                                                                    select=True,
                                                                                                    help="* New: When the stock move is created and not yet confirmed.\n" \
                                                                                                         "* Waiting Another Move: This state can be seen when a move is waiting for another one, for example in a chained flow.\n" \
                                                                                                         "* Waiting Availability: This state is reached when the procurement resolution is not straight forward. It may need the scheduler to run, a component to me manufactured...\n" \
                                                                                                         "* Available: When products are reserved, it is set to \'Available\'.\n" \
                                                                                                         "* Done: When the shipment is processed, the state is \'Done\'.",
                                                                                                    track_visibility='onchange'),
        sale_line_id=fields.many2one('sale.order.line', 'Linea de Venta', readonly=True),
        purchase_line_id=fields.many2one('purchase.order.line', 'Linea de Compra', readonly=True),
        cost=fields.float('Costo Unitario', readonly=True

                          , digits_compute=dp.get_precision('Account')),
        total_cost=fields.function(_total_cost, digits_compute=dp.get_precision('Account'),
                                   string='Costo Total Movimiento', type='float', readonly=True, store=True),
        move_kardex_ids=fields.many2many('stock.kardex', 'kardex_moves_ids', 'move_id', 'kardex_id', 'Kardex'),
        costo_promedio=fields.float('Costo promedio unitario',
                                    help="Costo promedio unitario en el momento de realizar el movimiento",
                                    digits_compute=dp.get_precision('Account'), readonly=True),
        string_availability_info=fields.function(_get_string_qty_information, type='text', string='Availability',
                                                 readonly=True,
                                                 help='Show various information on stock availability for this move'),
        price_unit_total=fields.function(_get_total, type='float', digits_compute=dp.get_precision('Account'),
                                         string='Valor Productos', store=False),
        local_currency_id=fields.related('company_id', 'currency_id', type="many2one", relation="res.currency",
                                         string="Moneda Local", readonly=True),
        product_uos=fields.related('product_id', 'uos_id', type='many2one', relation='product.uom',
                                   string='Unidad Equivalente', readonly=True, store=True),
        product_uos_qty=fields.function(_cantidad, string='Cantidad Equivalente',
                                        digits_compute=dp.get_precision('Product Unit of Measure'), type='float',
                                        readonly=True, store=True))
    
    def get_price_unit(self, cr, uid, move, context=None):
        return move.cost
    
    def force_assign(self, cr, uid, ids, context=None):
        #TODO implementar grupo
        for move in self.browse(cr, uid, ids, context=context):
            if move.location_id.usage == 'internal' and move.product_id.type == 'product':
                raise osv.except_osv(_('Error!'), _('No es posible forzar disponibilidad en ubicaciones internas.'))
        return super(stock_move, self).force_assign(cr, uid, ids, context=context)
    
    def action_scrap(self, cr, uid, ids, quantity, location_id, restrict_lot_id=False, restrict_partner_id=False, context=None):
        result = super(stock_move, self).action_scrap(cr, uid, ids, quantity, location_id, restrict_lot_id=restrict_lot_id, restrict_partner_id=restrict_partner_id, context=context)
        for move in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, [move.id], {'product_uom_qty':move.product_uom_qty-quantity}, context=context)
        return result
    
    def write(self, cr, uid, ids, vals, context=None):
        if context is None: context = {}    
        state_new = vals.get('state',False) 
        res_user_obj = self.pool.get('res.users')
                
        result = super(stock_move, self).write(cr, uid, ids, vals, context=context)
        if state_new and state_new in ['done']:  
            for move in self.browse(cr, uid, ids, context=context):                
                if move.location_dest_id and len(move.location_dest_id.user_owners_ids) >= 1:
                    current_user = res_user_obj.browse(cr, uid, uid, context=context)
                    if current_user not in move.location_dest_id.user_owners_ids:
                        raise osv.except_osv(_('Error!'), _("No tiene autorizacion para realizar este movimiento. Usted no es responsable de las entradas de para la ubicacion '%s'") % (move.location_dest_id.name))
        
        return result
    
    
    def create(self, cr, uid, vals, context=None):
        sale = False
        if vals.get('picking_type_id'):
            cr.execute("SELECT code FROM stock_picking_type WHERE id=%s" % vals.get('picking_type_id'))
            pick_type_code = cr.fetchall()[0][0]
            if pick_type_code == 'outgoing':
                cr.execute("SELECT value_float FROM ir_property WHERE res_id = (SELECT 'product.template,' || "
                           "(SELECT product_tmpl_id FROM product_product WHERE id=%s)) AND NAME="
                           "'standard_price'" % vals.get('product_id'))
                standard_price = cr.fetchall()
                standard_price = standard_price[0][0] if standard_price and standard_price[0] else 0
                vals.update({'cost': standard_price})
                sale = True
                sale_line_id = vals.get('sale_line_id', False)
                restrict_lot_id = vals.get('restrict_lot_id', False)
                if sale_line_id and not restrict_lot_id:                    
                    sale_line_id = self.pool.get('sale.order.line').browse(cr, uid, sale_line_id, context=context)
                    if 'lot_id' in sale_line_id._fields:
                        if sale_line_id.lot_id:
                            vals.update({'restrict_lot_id': sale_line_id.lot_id.id})
        if not sale:
            if vals.get('cost') and not vals.get('price_unit'):
                vals.update({'price_unit': vals.get('cost')})
            elif vals.get('price_unit') and not vals.get('cost'):
                vals.update({'cost': vals.get('price_unit')})
            elif not vals.get('price_unit') and not vals.get('cost'):
                zero_cost_moves_incomes = self.pool.get('res.company').browse(cr, uid, vals.get('company_id'),
                                                                              context=context).zero_cost_moves_incomes
                if zero_cost_moves_incomes:
                    vals.update({'cost': vals.get('price_unit')})
                    vals.update({'price_unit': vals.get('cost')})
                else:
                    cr.execute("SELECT value_float FROM ir_property WHERE res_id = (SELECT 'product.template,' || "
                               "(SELECT product_tmpl_id FROM product_product WHERE id=%s)) AND NAME="
                               "'standard_price'" % vals.get('product_id'))
                    standard_price = cr.fetchall()
                    standard_price = standard_price[0][0] if standard_price and standard_price[0] else 0
                    vals.update({'price_unit': standard_price})
                    vals.update({'cost': standard_price})
            if vals.get('purchase_line_id'):
                purchase_line_obj = self.pool.get('purchase.order.line')
                purchase_line_id = purchase_line_obj.browse(cr, uid, vals.get('purchase_line_id'), context=context)
                costo_adicional = purchase_line_obj.mayor_valor(cr, uid, purchase_line_id, context=context)
                cost = vals.get('cost')
                if purchase_line_id.product_id.uom_id.id != purchase_line_id.product_uom.id:
                    factor=1
                    if purchase_line_id.product_id.uom_id.category_id != purchase_line_id.product_uom.category_id:
                        raise osv.except_osv(_('Error !'), _("No es posible transferir un movimiento donde la categoria de unidad del producto '%s' no corresponde a la del movimiento '%s', por favor validar esta informacion. \n\n %s ") % (purchase_line_id.product_id.display_name, purchase_line_id.id, purchase_line_id.order_id.name))
                    else:
                        if purchase_line_id.product_id.uom_id.uom_type == 'bigger':
                            # factor=1/purchase_line_id.product_uom.factor_inv
                            cost=cost*purchase_line_id.product_id.uom_id.factor_inv
                        elif purchase_line_id.product_id.uom_id.uom_type == 'smaller':
                            cost=cost/purchase_line_id.product_id.uom_id.factor
                discount = purchase_line_id.discount
                vals.update({'cost': (cost*(1-discount/100))+costo_adicional, 'price_unit': cost})
        res = super(stock_move, self).create(cr, uid, vals, context=context)
        return res
    
    def default_get(self, cr, uid, fields, context=None):
        if context is None: context = {}
        res = super(stock_move, self).default_get(cr, uid, fields, context=context)
        if context.get('s_loc'):
            res.update({'location_id':context.get('s_loc')})
        if context.get('d_loc'):
            res.update({'location_dest_id':context.get('d_loc')})
        return res
    
    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False,
                            loc_dest_id=False, partner_id=False, context=None):
        product_obj = self.pool.get('product.product')
        vals = super(stock_move, self).onchange_product_id(cr, uid, ids, prod_id=prod_id, loc_id=loc_id,
                            loc_dest_id=loc_dest_id, partner_id=partner_id, context=context)
        if prod_id:
            product_rec = product_obj.browse(cr, uid, prod_id, context=context)
            if product_rec.standard_price:
                vals['value'].update({'cost':product_rec.standard_price})
        return vals

class account_journal(models.Model):
    _inherit = 'account.journal'
   
    stock_journal = fields2.Boolean(string='Stock Journal')
    no_agrupar=fields2.Boolean(string="No Agrupar")   

account_journal()

class stock_location(models.Model):
    _inherit = 'stock.location'
    
    user_owners_ids = fields2.Many2many('res.users', 'responsable_location_user_rel', 'location_id', 'user_id', string='Responsables', help="Personas que tienen permisos para recibir en ese almacen")

    ''''@api.multi
    def write(self, vals):
        for a in self:
            if (vals.get('usage',False) or vals.get('parent_id',False) or 'active' in vals) and len(a.env['stock.move'].search(['|',('location_id','=',a.id),('location_dest_id','=',a.id)])) >= 1:
                raise osv.except_osv(_('Error!'), _('No es posible realizar modificaciones de una ubicacion con movimientos relacionados'))
            res = super(stock_location, a).write(vals)
        return res'''


class stock_quant(osv.Model):
    _inherit = "stock.quant"
    
    def _get_quants_from_lot(self, cr, uid, ids, context=None):
        list = []
        lot_obj = self.pool.get('stock.production.lot')
        for lot in lot_obj.browse(cr, uid, ids, context=context):
            if lot.quant_ids:
                list+=[x.id for x in lot.quant_ids]
        return list
    
    def _check_lot_product(self, cr, uid, ids, context=None):
        for quant in self.browse(cr, uid, ids, context):
            if quant.lot_id and quant.lot_id.product_id != quant.product_id:
                return False
        return True
    
    def _get_total_cost(self, cr, uid, ids, name, args, context=None):
        res={}
        for ops in self.browse(cr, uid, ids, context=context):
                res[ops.id] = ops.cost*ops.qty
        return res
    
    _columns= {
        'life_date': fields.related('lot_id', 'life_date', type='datetime', string='Fecha de Caducidad', readonly=True, 
                                            store={
                                                'stock.production.lot': (_get_quants_from_lot, ['life_date'], 10),
                                                'stock.quant': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                            },),
        'product_id': fields.many2one('product.product', 'Product', required=True, ondelete="restrict", readonly=False, select=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True, ondelete="restrict", readonly=False, select=True),
        'qty': fields.float('Quantity', required=True, help="Quantity of products in this quant, in the default unit of measure of the product", readonly=False, select=True),
        'lot_id': fields.many2one('stock.production.lot', 'Lot', readonly=False, select=True),
        'cost_update': fields.float('Promedio Actualizar'),
        'cost_total': fields.function(_get_total_cost, type='float', digits=0, string="Costo Total"),
    }
    
    _constraints = [
        (_check_lot_product, 'El producto del lote y del quant, deben ser el mismo', ['lot_id']),
    ]
    
    #TODO implementar con metodo padre
    def apply_removal_strategy(self, cr, uid, location, product, quantity, domain, removal_strategy, context=None):
        if removal_strategy == 'fifo':
            order = 'in_date, id'
        elif removal_strategy == 'lifo':
            order = 'in_date desc, id desc'
        elif removal_strategy == 'fefo':
            order = 'life_date, id'
            domain += [('life_date', '!=', False),('lot_id','!=', False)]
        else:
            raise osv.except_osv(_('Error!'), _('Removal strategy %s not implemented.' % (removal_strategy,)))
        return self._quants_get_order(cr, uid, location, product, quantity, domain, order, context=context)
        
    def write(self, cr, uid, ids, vals, context=None):
        for quant in self.browse(cr, uid, ids, context=context):
            if quant.location_id.usage == 'internal' and quant.qty < 0 and quant.product_id.type == 'product':
                user = self.pool.get('res.users').browse(cr, uid, uid)
                if 'bypass' not in context and not user.company_id.negative_qty:
                    if quant.lot_id:
                        raise osv.except_osv(_('Error!'), _("No hay disponibilidad para el producto '%s' en la ubicacion '%s' con el lote '%'!")%(quant.product_id.name,quant.location_id.name,quant.lot_id.name ))
                    else:
                        raise osv.except_osv(_('Error!'), _("No hay disponibilidad para el producto '%s' en la ubicacion '%s'!")%(quant.product_id.name,quant.location_id.name ))
        res = super(stock_quant, self).write(cr, uid, ids, vals, context=context)
        return res

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        cost_update = vals.get('cost_update',False)
        product_obj = self.pool.get('product.product')
        if vals.get('cost_update',False) and uid == SUPERUSER_ID:
            product_id = vals.get('product_id',False)
            product_obj.write(cr, uid, product_id, {'standard_price':cost_update}, context=context)
            vals.update({'cost': cost_update})
        result = super(stock_quant, self).create(cr, uid, vals, context=context)
        quant = self.browse(cr, uid, result, context=context)
        user = self.pool.get('res.users').browse(cr, uid, uid)
        if quant.location_id.usage == 'internal' and quant.qty < 0 and quant.product_id.type == 'product':
            if 'bypass' not in context and not user.company_id.negative_qty:
                if quant.lot_id:
                    raise osv.except_osv(_('Error!'), _("No hay disponibilidad para el producto '%s' en la ubicacion "
                                                        "'%s' con el lote '%s'!") %
                                         (quant.product_id.name, quant.location_id.name, quant.lot_id.name ))
                else:
                    raise osv.except_osv(_('Error!'), _("No hay disponibilidad para el producto '%s' en la ubicacion "
                                                        "'%s'!") % (quant.product_id.name, quant.location_id.name))
        return result