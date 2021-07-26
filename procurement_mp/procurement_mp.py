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

    
class stock_warehouse_orderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'
    
    @api.one
    @api.depends('product_min_qty', 'product_max_qty', 'qty_multiple')
    def _get_qty(self):
        if self.location_id:
            cxt = self._context.copy()
            cxt.update({'location': self.location_id.id})
            res = self.with_context(cxt).product_id._product_available()
            if res:
                qty_available = res.values()[0].get('qty_available')
                outgoing_qty = res.values()[0].get('outgoing_qty')
                virtual_available = res.values()[0].get('virtual_available')
                incoming_qty = res.values()[0].get('incoming_qty')
                self.qty = qty_available
                self.qty_virtual = virtual_available
                self.qty_in = incoming_qty
                self.qty_out = outgoing_qty
                self.qty_disponible = qty_available - outgoing_qty
                self.qty_futura = qty_available - outgoing_qty + incoming_qty
            
    
    @api.one
    @api.depends('qty', 'qty_virtual', 'qty_in', 'qty_out', 'qty_disponible', 'qty_futura')
    def _get_state(self):        
        state = 'normal'        
        for order in  self:
            if order.qty_disponible > order.product_min_qty and order.qty_futura > order.reorder_qty:
                state = 'normal'
            elif order.qty_disponible > order.product_min_qty and order.qty_futura <= order.reorder_qty:
                state = 'abastecimiento'
            elif order.qty_disponible <= order.product_min_qty and order.qty_futura > order.reorder_qty:
                state = 'agotado'
            elif order.qty_disponible <= order.product_min_qty and order.qty_futura <= order.reorder_qty:
                state = 'critico'
            else:
                raise osv.except_osv(_('Error !'),_("Estado de abastecimiento no definido para el producto '%s', consultar con el administrador") % (order.product_id.name))
        self.state_procurement = state


    reorder_qty = fields.Float(string='Cantidad Reorden')
    qty = fields.Float(compute="_get_qty", string="QTY DISPONIBLE", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True, multi='orderpoint')
    qty_virtual = fields.Float(compute="_get_qty", string="QTY VIRTUAL", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True, multi='orderpoint')
    qty_in = fields.Float(compute="_get_qty", string="QTY ENTRANTE", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True, multi='orderpoint')
    qty_out = fields.Float(compute="_get_qty", string="QTY SALIENTE", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True, multi='orderpoint')
    qty_disponible = fields.Float(compute="_get_qty", string="QTY REAL DISPONIBLE", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True, multi='orderpoint')
    qty_futura = fields.Float(compute="_get_qty", string="QTY FUTURA", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True, multi='orderpoint')
    state_procurement = fields.Selection([('normal','Normal'),('abastecimiento','Abastecimiento'),('agotado','Agotado'),('critico','Critico')], string="ESTADO ABASTECIMIENTO", compute="_get_state", readonly=True)
   
    
    
class product_product(models.Model):
    _inherit = 'product.product'
    
    @api.one
    @api.depends('orderpoint_ids.qty', 'orderpoint_ids.qty_in', 'orderpoint_ids.qty_out', 'tipologia_inv', 'qty_available', 'incoming_qty', 'virtual_available')
    def _get_state(self):
        state = 'normal'
        if self.orderpoint_ids:
            for order in  self.orderpoint_ids:
                if order.state_procurement == 'critico':
                    state = 'critico'
                    continue
                if order.state_procurement == 'agotado':
                    state = 'agotado'
                    continue
                if order.state_procurement == 'abastecimiento':
                    state = 'abastecimiento'
                    continue
        self.state_procurement = state
       
    state_procurement = fields.Selection([('normal','Normal'),('abastecimiento','Abastecimiento'),('agotado','Agotado'),('critico','Critico')], string="ESTADO ABASTECIMIENTO", compute="_get_state", readonly=True, store=True, default='normal')
    tipologia_inv = fields.Char(string="Tipologia de Inventario")
    
#