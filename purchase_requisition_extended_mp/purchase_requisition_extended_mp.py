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
   

class purchase_requisition(models.Model):
    _inherit = "purchase.requisition"
    
    location_id = fields.Many2one('stock.location', string='Lugar de Entrega', required=True, readonly=False, states={'draft':[('readonly',False)]}, domain=[('usage', '=', 'internal'),('purchase_ok', '=', True)], help="Ubicacion para la cual se realiza la requisicion")
    tipo_compra = fields.Selection([('product', 'Almacenable'), ('consu', 'Consumible'), ('service', 'Servicio')], string='Tipo de Compra', required=True, states={'draft':[('readonly',False)]}, help="Indica el tipo de productos que podran ser seleccionados en la requisicion, Almacenables - Consumibles - Servicios")
    fabricante_id = fields.Many2one('res.partner', string='Fabricante', required=True)
    
    @api.multi
    def aprobar_todos(self):
        for line in self.line_ids:
            line.set_approve()
        return True
    
    @api.multi
    def write(self, vals):
        if self.location_id:
            warehouse_id = self.env['stock.warehouse'].search([('view_location_id.parent_left', '<=', self.location_id.parent_left), 
                                ('view_location_id.parent_right', '>=', self.location_id.parent_left)])
            if warehouse_id:
                self._cr.execute(''' UPDATE purchase_requisition SET picking_type_id=%s WHERE id=%s ''',(warehouse_id.in_type_id.id,self.id))   
        res = super(purchase_requisition, self).write(vals)
        return res


class purchase_requisition_line(models.Model):
    _inherit = "purchase.requisition.line"
    
    tipo_compra = fields.Selection([('product', 'Almacenable'), ('consu', 'Consumible'), ('service', 'Servicio')], string='Tipo de Compra', related="requisition_id.tipo_compra", store=True)

class stock_location(models.Model):
    _inherit = "stock.location"    
    
    purchase_ok = fields.Boolean(string='Compra')
    sale_ok = fields.Boolean(string='Venta')
    
class purchase_quotation_supplier_line(models.Model):
    _inherit = "purchase.quotation.supplier.line"
    
    lugar_entrega = fields.Char(string='Lugar de Entrega', states={'sent':[('readonly',False)]})
    description = fields.Char(string='Descripcion', states={'sent':[('readonly',False)]})
    fecha_entrega = fields.Date(string='Fecha Pago', states={'sent':[('readonly',False)]})
    tipo_compra = fields.Selection([('product', 'Almacenable'), ('consu', 'Consumible'), ('service', 'Servicio')], string='Tipo de Compra', related="requisition_line_id.tipo_compra", store=True)
    

class purchase_order(models.Model):
    _inherit = "purchase.order"
    
    @api.onchange('fabricante_id')
    def check_change_cantidad(self):
        if self.fabricante_id:
            self.payment_term_id = self.fabricante_id.property_supplier_payment_term.id
    
    tipo_compra = fields.Selection([('product', 'Almacenable'), ('consu', 'Consumible'), ('service', 'Servicio')], string='Tipo de Compra', related="requisition_id.tipo_compra", store=True)
    fabricante_id = fields.Many2one('res.partner', string='Fabricante')
    country_fabricante_id = fields.Many2one('res.country', string='Pais Fabricante', related='fabricante_id.country_id', store=True, readonly=True)
    
    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self,vals):
        res = super(purchase_order, self).create(vals)  
        if res.requisition_id:
            res.location_id = res.requisition_id.location_id.id
        return res
        
        
class purchase_order_line(models.Model):
    _inherit = "purchase.order.line"
    
    fabricante_id = fields.Many2one('res.partner', related="order_id.fabricante_id", string='Fabricante', store=True)
    country_fabricante_id = fields.Many2one('res.country', string='Pais Fabricante', related='fabricante_id.country_id', store=True)
    

#