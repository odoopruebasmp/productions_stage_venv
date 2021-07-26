# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
from openerp import addons
from openerp import SUPERUSER_ID
import itertools
from dateutil.relativedelta import relativedelta
from lxml import etree
from openerp import models, fields, api, _
from openerp.osv import osv, fields as fields2
from openerp.exceptions import except_orm, Warning, RedirectWarning
import openerp.addons.decimal_precision as dp
import math


class pos_extra(models.Model):
    _name = 'pos.extra'
    
    ean_punto_de_venta = fields.Char(string='EAN Punto de Venta')
    nombre_punto_de_venta = fields.Char(string='Nombre Punto de Venta')
    cantidad_pto_vta = fields.Float(string='Cantidad Pto Vta')
    precio_bruto = fields.Float(string='CEN Precio Bruto')
    precio_neto = fields.Float(string='CEN Precio Neto')
    sale_line_id = fields.Many2one('sale.order.line', string='Sale Order Line')
    sale_id = fields.Many2one('sale.order', string='Sale Order')
    move_id = fields.Many2one('stock.move', string='Stock Move')


class sale_shop(models.Model):
    _name = "sale.shop"
    
    name = fields.Char(string='Shop Name', size=64, required=True)
    payment_default_id = fields.Many2one('account.payment.term', string='Default Payment Term', required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    project_id = fields.Many2one('account.analytic.account', string='Analytic Account', domain=[('parent_id', '!=', False)])
    shop_ean = fields.Char(string='EAN of shop', size=32)
    company_id = fields.Many2one('res.company', string='Company', required=False, defaults=1)   

    
    
class sale_order(models.Model):    
    _inherit = 'sale.order'

    @api.multi
    def show_red_lines(self):
        red_line_ids = []
        for sale in self:
            for line in sale.order_line:
                if line.neto_price - line.sale_neto == 0.0:
                    red_line_ids.append(line.id)
        self.env['sale.order.line'].browse(red_line_ids).write({'active': False})
        return True
    
    @api.multi
    def show_all_lines(self):
        for sale in self:
            sale_order_ids = self.env['sale.order.line'].search([('order_id','=',sale.id),('active','=',False)]).write({'active': True})
        return True

    order_type = fields.Char(string='Tipo de Orden', readonly=True, states={'draft':[('readonly',False)], 'send':[('readonly',False)]})
    min_ship_date = fields.Date(string='Fecha Minima Entrega', readonly=True, states={'draft':[('readonly',False)], 'send':[('readonly',False)]})
    max_ship_date = fields.Date(string='Fecha Maxima Entrega', readonly=True, states={'draft':[('readonly',False)], 'send':[('readonly',False)]})
    #agreement = fields.Text(string='Promotional Agreement')
    net_price = fields.Float(strign='Net price')
    qty_pto_vta = fields.Float(string='Cantidad Pto Vta')
    pos_extra_ids = fields.One2many('pos.extra','sale_line_id', string='POS Extra')
    type_cross = fields.Selection([('remision', 'Remisionar'),('factura', 'Facturar')], string='Tipo de Remision', required=True, defaults='remision', readonly=True, states={'draft':[('readonly',False)], 'send':[('readonly',False)]})
    picking_type_cross = fields.Many2one('stock.picking.type', string='Tipo de Albaran', domain=[('cross_docking','=', True)], readonly=True, states={'draft':[('readonly',False)], 'send':[('readonly',False)]})
    location_id = fields.Many2one('stock.location', string='Origen', readonly=True, states={'draft':[('readonly',False)], 'send':[('readonly',False)]}, domain=[('usage','=', 'internal'),('sale_ok','=', True),('active','=', True)])
    

    def _prepare_order_line_move(self, cr, uid, order, line, picking_id, date_planned, context=None):
        if not context:context ={}
        res = super(sale_order, self)._prepare_order_line_move(cr, uid, order, line, picking_id, date_planned, context)
        if line.qty_pto_vta:
            res.update({'qty_pto_vta': line.qty_pto_vta})
        if line.pos_extra_ids:
            pos_ids_list = []
            for pos_ids in line.pos_extra_ids:
                pos_ids_list.append((4,pos_ids.id))
            res.update({'pos_extra_ids': pos_ids_list})
        return res


class res_partner(models.Model):
    _inherit = 'res.partner'
    
    partner_ean = fields.Char('Partner EAN')
    category_id2 = fields.Many2one('res.partner.category', string='Tipo de Cliente')
    
    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        vals = super(res_partner, self).name_search(cr, user, name, args=args, operator=operator, context=context, limit=limit)
        if not vals:
            ids = []
            if name:
                ids = self.search(cr, user, [('partner_ean','=',name)]+ args, limit=limit, context=context)
            if ids:
                vals = self.name_get(cr, user, ids, context)        
        return vals
    

class stock_picking_type(models.Model):    
    _inherit = 'stock.picking.type'
    
    cross_docking = fields.Boolean(string='Tipo Cross Docking')    
        

class stock_location(models.Model):    
    _inherit = 'stock.location'
    
    stock_ean = fields.Char(string='Stock EAN')
        
    
class sale_order_line(models.Model):
    _inherit = 'sale.order.line'
    
    @api.one
    @api.depends('product_id.qty_available', 'order_id.warehouse_id')
    def _get_available(self):
        cxt = self._context.copy()
        cxt.update({'location': self.order_id.warehouse_id.wh_input_stock_loc_id.id})
        res = self.with_context(cxt).product_id._product_available()
        if res:            
            qty_available = res.values()[0].get('qty_available')
            self.qty_availble = qty_available
                
    @api.one
    @api.depends('sale_neto', 'neto_price')
    def _sale_net_price_diff(self):
        self.sale_net_price_diff = self.sale_neto - self.neto_price
    
    @api.onchange('product_uom_qty')
    def _qty(self):
        self.proposed_qty = self.product_uom_qty
    
    @api.one
    @api.depends('price_unit', 'discount')
    def _sale_neto(self):
        if self.discount != 0.0:
            self.sale_neto = self.price_unit - (self.price_unit*(self.discount/100))
        else:
            self.sale_neto = self.price_unit

    pos_extra_ids = fields.One2many('pos.extra','sale_line_id', string='POS Extra')
    qty_pto_vta = fields.Float(string='Cantidad Pto Vta')
    sale_net_price_diff = fields.Float(compute='_sale_net_price_diff', string='Price Differences.', store=True)
    sale_neto = fields.Float(compute='_sale_neto', string='MP Precio Neto')
    total_discount = fields.Float(string='Total Discount')
    neto_price = fields.Float(string='Neto Price')
    active = fields.Boolean(string='Active', default=True)
    #ean_punto_de_venta = fields.Char(string='EAN Punto de Venta')
    ean_del_tem = fields.Char(string='EAN Item')
    plu_lineas = fields.Char(string='MP PLU')
    precio_neto = fields.Float(string='CEN Precio Neto')
    precio_bruto = fields.Float(string='CEN Precio Bruto')
    proposed_qty = fields.Float(string='MP Aprobado')
    qty_availble = fields.Float(compute="_get_available", type='float', string='MP Disponible')
    order_state = fields.Selection(related='order_id.state', string='Order state', readonly=True, store=True)
    
    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self,vals):
        if vals.get('product_uom_qty', False) and not vals.get('proposed_qty', False):
            vals.update({'proposed_qty': float(vals.get('product_uom_qty'))})
        res = super(sale_order_line, self).create(vals)
        return res
    
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False, context=None):
        product_obj = self.pool.get('product.product')
        res = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty=qty,
            uom=uom, qty_uos=qty_uos, uos=uos, name=name, partner_id=partner_id,
            lang=lang, update_tax=update_tax, date_order=date_order, packaging=packaging, fiscal_position=fiscal_position, flag=flag, context=context)
        if product:
            product_rec = product_obj.browse(cr, uid, product, context)
            res.get('value').update({'qty_availble': product_rec.qty_available})
        return res


class stock_picking(models.Model):    
    _inherit = 'stock.picking'
    
    type_cross = fields.Selection(related="sale_id.type_cross")
    fecha_malla = fields.Date(string='Fecha malla')
    min_ship_date = fields.Date(string='Fecha Minima Entrega', readonly=True)
    max_ship_date = fields.Date(string='Fecha Maxima Entrega', readonly=True)
    cliente_id = fields.Many2one('res.partner',string="Cliente")
    
    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self,vals):
        if vals.get('origin'):
            sale_line = self.env['sale.order'].search([('name','=',vals.get('origin'))])
            if sale_line:
                vals.update({'state_guia':'Despachado', 'n_oc': sale_line.n_oc, 'cliente_id': sale_line.partner_id.id,'min_ship_date': sale_line.min_ship_date, 'max_ship_date': sale_line.max_ship_date, 'carrier_coment': sale_line.note or ' ', 'fecha_malla': sale_line.fecha_malla})
                if sale_line.type_cross == 'remision':
                    vals.update({'picking_type_id': sale_line.picking_type_cross.id})                    
                else:
                    vals.update({'picking_type_id': sale_line.warehouse_id.out_type_id.id})
                    if sale_line.location_id:
                        vals.update({'source_location': sale_line.location_id.id})
        if vals.get('picking_invoice_id', False):
            vals.update({'picking_invoice_id': False})
        res = super(stock_picking, self).create(vals)        
        return res
        

class stock_move(models.Model):    
    _inherit = 'stock.move'
    
    sale_line_id = fields.Many2one('sale.order.line', string='Sale Order Line')
    qty_pto_vta = fields.Float(string='Cantidad Pto Vta')
    pos_extra_ids = fields.One2many(related="sale_line_id.pos_extra_ids", string='REMISIONES')    
       
    
    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self,vals):
        if vals.get('sale_line_id', False) and not vals.get('origin_returned_move_id', False):
            sale_line = self.env['sale.order.line'].browse(vals.get('sale_line_id'))
            if sale_line:
                vals.update({'sale_line_id': sale_line.id})
                if sale_line.product_uom_qty != sale_line.proposed_qty:
                    vals.update({'product_uom_qty': sale_line.proposed_qty})
                if sale_line.order_id.type_cross == 'remision':
                    vals.update({'picking_type_id': sale_line.order_id.picking_type_cross.id, 'invoice_state': 'none', 'location_dest_id': sale_line.order_id.picking_type_cross.default_location_dest_id.id})                    
                else:
                    vals.update({'picking_type_id': sale_line.order_id.warehouse_id.out_type_id.id, 'invoice_state': '2binvoiced', 'location_id': sale_line.order_id.warehouse_id.out_type_id.default_location_src_id.id})
                    if sale_line.order_id.location_id:
                        vals.update({'location_id': sale_line.order_id.location_id.id})        
        res = super(stock_move, self).create(vals)
        return res


class procurement_order(models.Model):
    _inherit = "procurement.order"
    
    @api.multi
    def action_confirm(self):
        move_obj = self.env['stock.move']
        for procurement in self:
            if procurement.product_id.type in ('product', 'consu'):
                if not procurement.move_id:
                    source = procurement.location_id.id
                    if procurement.procure_method == 'make_to_order':
                        source = procurement.product_id.property_stock_procurement.id
                    obj = move_obj.create({'name': procurement.name,
                        'location_id': source,
                        'location_dest_id': procurement.location_id.id,
                        'product_id': procurement.product_id.id,
                        'product_qty': procurement.product_qty,
                        'product_uom': procurement.product_uom.id,
                        'date_expected': procurement.date_planned,
                        'state': 'draft',
                        'company_id': procurement.company_id.id,
                        'auto_validate': True,
                    })
                    move_obj.action_confirm([obj.id])
                    procurement.write({'move_id': obj.id, 'close_move': 1})
        self.write({'state': 'confirmed', 'message': ''})
        return True


class product_pricelist_item(models.Model):
    _inherit = "product.pricelist.item"

    discount = fields.Float(string='Discount %')
#
