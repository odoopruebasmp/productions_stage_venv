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

class control_office(models.Model):
    _name = 'control.office'
    
    @api.one
    @api.depends('invoice_id')
    def _invoiced(self):
        if self.invoice_id:
            val = 0.0
            val_total = 0.0
            for invoice in self.invoice_id:
                val += invoice.amount_untaxed
                val_total += invoice.amount_total
            self.valor_neto_fact = val
            self.valor_total_fact = val_total
        else:
            self.valor_neto_fact = 0.0
            self.valor_total_fact = 0.0
    
    @api.one
    @api.depends('sale_id.picking_ids', 'sale_id.invoice_ids')
    def _picking(self):
        if self.sale_id.picking_ids:
            self.picking_id = self.sale_id.picking_ids[0].id
            self.picking_state = self.sale_id.picking_ids[0].state
            self.picking_date = self.sale_id.picking_ids[0].date
            self.picking_guia = self.sale_id.picking_ids[0].carrier_tracking_ref
        if self.sale_id.invoice_ids:
            self.invoice = self.sale_id.invoice_ids[0].id
            self.invoice_state = self.sale_id.invoice_ids[0].state
            self.invoice_date = self.sale_id.invoice_ids[0].date_invoice
            
    @api.one
    @api.depends('valor_neto_fact', 'value')
    def _diff(self):
        self.diff_neto = self.value - self.valor_neto_fact
        
            
    sale_id = fields.Many2one('sale.order', string='N RADICACION')
    create_date = fields.Datetime(string='FECHA RADICACION')
    cust_ref = fields.Char(string='N O.C.', related="sale_id.n_oc", readonly=True, store=True)
    min_ship_date = fields.Date(string='FECHA MINIMA DE ENTREGA')
    max_ship_date = fields.Date(string='FECHA MAXIMA ENTREGA')
    date_malla = fields.Date(string='FECHA MALLA', related="sale_id.fecha_malla")
    value = fields.Float(related="sale_id.amount_untaxed", string='VALOR NETO O.C.')
    value_total = fields.Float(related="sale_id.amount_total", string='VALOR TOTAL O.C.')
    partner_type = fields.Many2one('res.partner.category', related="partner_id.category_id2", string='TIPO DE CLIENTE', store=True) 
    partner_id = fields.Many2one('res.partner', string='CLIENTE')
    branch_name = fields.Many2one('res.partner', string='SUCURSAL')
    city_branch = fields.Many2one('res.city', related="branch_name.city_id", string='CIUDAD SUCURSAL', store=True)
    zona_branch = fields.Many2one('zona.zona', related="branch_name.zona_id", string='ZONA SUCURSAL', store=True)
    event_id = fields.Many2one('event.event', related="sale_id.event_id", string='EVENTO', readonly=True, store=True)
    picking_ids = fields.One2many('stock.picking', 'sale_id', related="sale_id.picking_ids", string='REMISIONES')
    picking_id = fields.Many2one('stock.picking', compute="_picking", string='REMISION')
    invoice = fields.Many2one('account.invoice', compute="_picking", string='FACTURA')
    picking_state = fields.Char(string='ESTADO REMISION', compute="_picking", readonly=True)
    invoice_state = fields.Char(string='ESTADO FACTURA', compute="_picking", readonly=True)
    picking_guia = fields.Char(string='GUIA', compute="_picking", readonly=True)
    picking_date = fields.Datetime(string='FECHA REMISION', compute="_picking", readonly=True)
    invoice_date = fields.Date(string='FECHA FACTURA', compute="_picking", readonly=True)
    invoice_id = fields.Many2many('account.invoice', related="sale_id.invoice_ids", string='FACTURAS')    
    valor_neto_fact = fields.Float(compute='_invoiced', string='VALOR NETO FACT.')
    diff_neto = fields.Float(compute='_diff', string='DIFERENCIA NETO')
    valor_total_fact = fields.Float(compute='_invoiced', string='VALOR TOTAL FACT.')
    state_guia = fields.Selection(related="picking_id.state_guia", string='ESTADO GUIA')
    
    
class res_partner(models.Model):
    _inherit = 'res.partner'
    
    category_id2 = fields.Many2one('res.partner.category', string='Tipo de Cliente')


class stock_picking(models.Model):
    _inherit = 'stock.picking'
    
    n_oc = fields.Char(string='N O.C.')
    type_code = fields.Selection(related="picking_type_id.code", string='Code Picking Type', readonly=True)
    state_guia = fields.Selection([('Despachado', 'Despachado'),('En_Bodega_Destino', 'En Bodega Destino'),('En_Distribucion', 'En Distribucion'),('Entregado', 'Entregado'),('Con_Novedad', 'Con Novedad')], string='Estado Guia', default="Despachado")
    
    
class account_invoice(models.Model):
    _inherit = 'account.invoice'
    
    n_oc = fields.Char(related="stock_picking_id.n_oc", string='N O.C.', readonly=True)
    
    
class event_event(models.Model):    
    _inherit = 'event.event'
    
    sale_ids = fields.One2many('sale.order', 'event_id', string='Pedidos DE Venta')
    
    
class sale_order(models.Model):    
    _inherit = 'sale.order'
        
    event_id = fields.Many2one('event.event', string='EVENTO')
    
    def action_wait(self, cr, uid, ids, context=None):
        self.check_limit(cr, uid, ids, context=context)
        vals_con_office = {}
        contro_de_obj = self.pool.get('control.office')
        for sale_id in self.browse(cr, uid, ids, context=context):
            vals_con_office.update({'sale_id': sale_id.id,                                   
                                    'partner_id' : sale_id.partner_id.id,
                                    'branch_name' : sale_id.partner_shipping_id.id,  
                                    'min_ship_date' :sale_id.min_ship_date,
                                    'max_ship_date' : sale_id.max_ship_date,
                                    'value' : sale_id.amount_untaxed,
                                    'fecha_malla' : sale_id.fecha_malla,
                                    'zona' : sale_id.partner_id.zona_id.id,
                                    'date' : datetime.now(),
                                    })
            contro_de_obj.create(cr, uid, vals_con_office, context=context)
        res = super(sale_order, self).action_wait(cr, uid, ids, context=context)       
        return True
