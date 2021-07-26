# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
# from openerp.tools.translate import _
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

class account_invoice_line(models.Model):
    _inherit = "account.invoice.line"
    
    
    @api.one
    @api.depends('stock_move_ids', 'discount', 'price_unit', 'invoice_id.partner_shipping_id', 'invoice_id.state', 'invoice_id.ref2', 'cost_file','date_recalcular')
    def _cost(self):
        if self.invoice_id.state in ['draft','cancel']:
            self.state=self.invoice_id.state
        else:
            print "ENTRO"
            cost = 0.0
            margin_p = 100
            margin_unitario = 0.0
            cantidad = 1.0            
            precio_unitario = abs(self.price_unit)
            if self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
                precio_unitario = self.price_unit*self.invoice_id.tasa_manual
            discount = abs(self.discount/100)        
            type = 1
            type_state = 'Facturas'
            
            # Cantidad
            if self.quantity != 0.0:
                cantidad = self.quantity            
            # Venta o Devolucion
            if self.invoice_id.type == 'out_refund':
                type = -1
                type_state = 'Devoluciones'
            elif self.invoice_id.type == 'in_refund':
                type = -1
                type_state = 'Devoluciones Proveedor'
            elif self.invoice_id.type == 'in_invoice':
                type_state = 'Facturas Proveedor'
            # costo
            if self.stock_move_ids:
                cost = self.stock_move_ids[0].cost
            else:
                cost = abs(self.cost_file)
            # precio unitario y margen unitario
            price_neto_unitario = precio_unitario - precio_unitario*discount
            margin_unitario = price_neto_unitario - cost       
                    
            if price_neto_unitario > 0.0:
                margin_p = (margin_unitario/price_neto_unitario)*100
            
            # Costo
            self.cost = cost*type
            self.cost_t = cost*cantidad*type        
            # Precio neto
            self.price_neto = price_neto_unitario*type
            self.price_neto_t = price_neto_unitario*cantidad*type        
            
            # Margen bruto
            self.margin = margin_unitario*type
            self.margin_t = margin_unitario*cantidad*type        
            # Margen porcentual
            self.margin_p = margin_p*type        
            # Cantidad        
            self.cantidad = cantidad*type        
            # Descuento
            self.discount_line = discount*cantidad*precio_unitario
            # Tipo
            self.type = type_state
            # Terceros
            self.partner_shipping_id = self.invoice_id.partner_shipping_id and self.invoice_id.partner_shipping_id.id or False
            self.country_id = self.invoice_id.partner_shipping_id.country_id and self.invoice_id.partner_shipping_id.country_id.id or False
            self.state_id = self.invoice_id.partner_shipping_id.state_id and self.invoice_id.partner_shipping_id.state_id.id or False
            self.city_id = self.invoice_id.partner_shipping_id.city_id and self.invoice_id.partner_shipping_id.city_id.id or False
            self.partner_id2 = self.invoice_id.partner_id and self.invoice_id.partner_id.id or False
            # Estado - Periodo - Fecha de factura - Comercial - Equipo de ventas
            self.state = self.invoice_id.state
            self.period_id = self.invoice_id.period_id.id
            self.date = self.invoice_id.date_invoice
            self.user_id = self.invoice_id.user_id.id
            self.default_section_id = self.invoice_id.user_id.default_section_id and self.invoice_id.user_id.default_section_id or False
            # Division - Categoria - Subcategoria
            if self.product_id:
                self.type_product=self.product_id.type
                self.ref = self.product_id.default_code or False
                self.subcategory_id = self.product_id.categ_id.id
            if self.product_id.categ_id.parent_id:
                self.category_id = self.product_id.categ_id.parent_id.id
                if self.product_id.categ_id.parent_id.parent_id:
                    self.division_id = self.product_id.categ_id.parent_id.parent_id.id
                    
    
    margin = fields.Float(string='Margen Unitario', compute='_cost', digits= dp.get_precision('Account'), store=True, readonly=True)
    ref = fields.Char(string='Referencia', compute='_cost', store=True)
    cost = fields.Float(string='Costo Unitario', compute='_cost', digits= dp.get_precision('Account'), store=True, readonly=True, help="prueba")
    cost_file = fields.Float(string='Costo file', digits= dp.get_precision('Account'))
    price_neto = fields.Float(string='Precio Neto Unitario', compute='_cost', digits= dp.get_precision('Account'), store=True)
    type = fields.Char(string='Type', compute='_cost', store=True)
    cantidad = fields.Float(string='Cantidad QTY', compute='_cost', digits= dp.get_precision('Account'), store=True, readonly=True, help="prueba")
    discount_line = fields.Float(string='Descuento', compute='_cost', digits= dp.get_precision('Account'), readonly=True)
    state = fields.Char(string='State', compute='_cost', store=True)
    period_id = fields.Many2one('account.period', compute='_cost', string='Periodo', store=True)
    date = fields.Date(string='Date', compute='_cost', store=True)
    margin_p = fields.Float(string='Margen %', compute='_cost', digits= dp.get_precision('Discount'), store=True)
    margin_t = fields.Float(string='Margen Total', compute='_cost', digits= dp.get_precision('Account'), store=True)
    cost_t = fields.Float(string='Costo Total', compute='_cost', digits= dp.get_precision('Account'), store=True)
    price_neto_t = fields.Float(string='Precio Neto Total', compute='_cost', digits= dp.get_precision('Account'), store=True)
    partner_shipping_id = fields.Many2one('res.partner', compute='_cost', string='Sucursal', store=True)
    country_id = fields.Many2one('res.country', compute='_cost', string='Pais', store=True)
    state_id = fields.Many2one('res.country.state', compute='_cost', string='Departamento', store=True)
    city_id = fields.Many2one('res.city', compute='_cost', string='Ciudad', store=True)    
    partner_id2 = fields.Many2one('res.partner', compute='_cost', string='Empresa', store=True)
    division_id = fields.Many2one('product.category', compute='_cost', string='Division', store=True)
    category_id = fields.Many2one('product.category', compute='_cost', string='Categoria', store=True)
    subcategory_id = fields.Many2one('product.category', compute='_cost', string='Subcategoria', store=True)
    user_id = fields.Many2one('res.users', compute='_cost', string='Comercial', store=True)
    default_section_id = fields.Many2one('crm.case.section', compute='_cost', string='Equipo de Ventas', store=True)
    type_product = fields.Selection([('product', 'Almacenable'), ('consu', 'Consumible'), ('service', 'Servicio')], string='Tipo de Compra', compute="_cost", store=True)
    date_recalcular = fields.Datetime(string='Fecha Recalcular')
    
    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, lazy=True):
        #if 'margin_t' not in fields:
            #fields.append('margin_t')
        result = super(account_invoice_line, self).read_group(cr, uid, domain=domain, fields=fields, groupby=groupby, offset=offset, limit=limit, context=context, orderby=orderby, lazy=lazy)        
        margin_unitario = 0.0
        
        for res in result:
            
            if 'margin_p' in res or 'margin_t' in res:
                if res['price_neto_t'] and res['price_neto_t'] != 0.0:
                    res.update({'margin_p':abs(res['price_neto_t']-res['cost_t'])*100/res['price_neto_t'], 'margin_t':res['price_neto_t']-res['cost_t']})
            if 'cost' in res:
                if not 'quantity' in res:
                    raise osv.except_osv(_('Warning!'),_('Para agregar el Costo Unitario, debes primero seleccionar la medida Cantidad'))
                if not 'cost_t' in res:
                    raise osv.except_osv(_('Warning!'),_('Para agregar el Costo Unitario, debes primero seleccionar la medida Costo Total'))
                if res['quantity'] == 0.0:
                   res['quantity'] = 1
                res.update({'cost':abs(res['cost_t']/res['quantity'])})
            if 'price_neto' in res:
                if not 'quantity' in res:
                    raise osv.except_osv(_('Warning!'),_('Para agregar el Precio Neto Unitario, debes primero seleccionar la medida Cantidad'))
                if not 'price_neto_t' in res:
                    raise osv.except_osv(_('Warning!'),_('Para agregar el Precio Neto Unitario, debes primero seleccionar la medida Precio Neto Total'))
                if res['quantity'] == 0.0:
                   res['quantity'] = 1
                res.update({'price_neto':abs(res['price_neto_t']/res['quantity'])})
        return result
#
