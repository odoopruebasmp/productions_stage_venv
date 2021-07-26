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
from openerp.addons.edi import EDIMixin
import math



class purchase_order(models.Model):
    _inherit = "purchase.order"
    
    invoiced_import = fields.Boolean(string='Facturado Importacion')
    
    @api.multi
    def create_invoice_import(self):
        if self.import_id and not self.invoiced_import:
            self.write({'invoice_method': 'order', 'invoiced_import': True})
            picking_id=self.env['stock.picking'].search([('state','!=','cancel'),('origin','=',self.name)], limit=1)
            if not picking_id:
                raise osv.except_osv(_('Error !'), _("No se logra encontrar un picking con docuemnto de origen %s "  % self.name))
            invoice_id = self.action_invoice_create()            
            invoice_id=self.env['account.invoice'].browse(invoice_id)   
            journal_id=self.env['account.journal'].search([('type','=','purchase'),('currency','=',self.import_id.currency_id.id)], limit=1)
            if not journal_id:
                raise osv.except_osv(_('Error !'), _("No se logra encontrar un diario de compra parala moneda %s "  % self.import_id.currency_id.name))
                        
            invoice_id.write({'es_multidivisa':True, 'journal_id': journal_id.id, 'currency_id': self.import_id.currency_id.id, 'tasa_manual': self.import_id.currency_rate > 0 and self.import_id.currency_rate or 1, 'stock_picking_id':picking_id.id})
            for line in invoice_id.invoice_line:
                if line.product_id and line.product_id.type == 'product':
                    account_id=invoice_id.partner_id.accrued_account_payable_id and invoice_id.partner_id.accrued_account_payable_id.id or False
                    if not account_id:
                        raise osv.except_osv(_('Configuration !'), _("La cuenta puente de recepcion no esta configurada en el proveedor %s "  % invoice_id.partner_id.name))
                    line.write({'account_id': account_id})            
            invoice_id.button_reset_taxes()
        return True
  
    
class purchase_advance_supplier(models.Model):
    _inherit = "purchase.advance.supplier"
    
    @api.one
    @api.depends('purchase_order_id')
    def _imp(self):
        if self.env['ir.module.module'].search([('name','=','purchase_requisition_extended_mp'),('state','=','installed')]):
            if self.purchase_order_id and self.purchase_order_id.fabricante_id:
                self.imp=True
                self.fabricante_id = self.purchase_order_id.fabricante_id.id
            
    @api.one
    @api.constrains('planned_date')
    def _check_planned_date(self):
        if self.planned_date:
            today = datetime.now().date()
            date = datetime.strptime(self.planned_date, DEFAULT_SERVER_DATE_FORMAT).date()
            if  date < today:
                raise Warning(_('Debe configurar una fecha mayor o igual a ("%s")') % (today))
            
    fabricante_id = fields.Many2one('res.partner', compute="_imp", string='Fabricante')
    imp = fields.Boolean(string='Tipo Importacion', compute="_imp")
    
            
class purchase_import(models.Model, EDIMixin):
    _inherit = "purchase.import"
    
    @api.one
    @api.depends('advance_supplier_ids', 'amount_total_products', 'pagada', 'state')
    def _amount(self):
        var = 0
        if self.advance_supplier_ids:            
            for advance in self.advance_supplier_ids:
                var += advance.total_local
        self.amount_balance = self.amount_total_products - var        
        self.amount_total = self.amount_total_products
        if self.pagada == 'pagada':
            self.amount_balance = 0
        else:
            self.amount_advance = var
            
    @api.one
    @api.depends('purchase_order_ids')
    def _import(self):
        res = []
        if self.purchase_order_ids:
            for order in self.purchase_order_ids:
                if order.advance_payment_id:
                    for advance in order.advance_payment_id:
                        if advance.state != "cancelled":
                            res.append(advance.id)
        if res:
            self.advance_supplier_ids = [(6, 0,res)]
            self.advance_count = len(res)
    
        
    @api.one
    @api.depends('purchase_order_ids','invoices_ids','invoices_arancel_ids')
    def _invoice(self):
        res = []
        res1 = []
        if self.purchase_order_ids:
            self.purchase_count = len(self.purchase_order_ids)
            for order in self.purchase_order_ids:
                if order.invoice_ids:
                    for invoice in order.invoice_ids:
                        res.append(invoice.id)
                if order.picking_ids:
                    for picking in order.picking_ids:
                        res1.append(picking.id)
        if res1:
            self.picking_ids = [(6, 0,res1)]
            self.picking_count = len(res1)
        if res:
            self.invoice_fob_ids = [(6, 0,res)]
            self.invoice_count_fob = len(res)
        if self.invoices_ids:
            self.invoice_count = len(self.invoices_ids.filtered(lambda x: x.state != 'cancel')) + len(self.invoices_arancel_ids.filtered(lambda x: x.state != 'cancel'))
        
    
    @api.one
    @api.depends('picking_ids','invoices_ids', 'invoices_arancel_ids')
    def _contable(self):
        contable_count = self.env['account.move.line'].search([('import_id','=',self.id)])
        if contable_count:
            self.contable_count=len(contable_count)
    
    
    invoice_fob_ids = fields.One2many('account.invoice',  compute='_invoice', string="Factura FOB")
    invoice_count_fob=fields.Integer(string='Facturas FOB', compute="_invoice")
    contable_count=fields.Integer(string='Registros Contables', compute="_contable")
    purchase_count=fields.Integer(string='Pedidos de Compra', compute="_invoice")
    invoice_count=fields.Integer(string='Facturas Costos', compute="_invoice")
    picking_count=fields.Integer(string='Recepciones', compute="_invoice")
    advance_count=fields.Integer(string='Anticipos', compute="_import")
    picking_ids=fields.One2many('stock.picking',  compute='_invoice', string="Factura FOB")
    advance_supplier_ids = fields.One2many('purchase.advance.supplier',  compute='_import', string="Anticipos de Proveedores")
    amount_balance = fields.Float(string='Balance', compute='_amount', digits=dp.get_precision('Account'), store=True, readonly=True)
    amount_advance = fields.Float(string='Anticipos', compute='_amount', digits=dp.get_precision('Account'), store=True, readonly=True)
    amount_total = fields.Float(string='Total', compute='_amount', digits=dp.get_precision('Account'), store=True, readonly=True)
    date_balance = fields.Date(string='Fecha Proximo Pago')
    pagada=fields.Selection([('pagada','Pagada'),('no_pagada','No Pagada')], string='Estado', default='no_pagada')
    
    
    def view_contable(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for import_id in self.browse(cr, uid, ids, context=context):
            moves = self.pool.get('account.move.line').search(cr,uid,[('import_id','=',import_id.id)], context=context)
            print ""
            print moves
            print ""
            if moves:
                for move in moves:
                    inv.append(move)
        
        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Liquidacion Importacion',
                'view_type': 'form',
                'view_mode': 'graph,tree,form',
                'view_id': False,
                'res_model': 'account.move.line',
                'type': 'ir.actions.act_window'
            }
    
    def view_purchase(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for purchase in self.browse(cr, uid, ids, context=context).purchase_order_ids:
            inv.append(purchase.id)
        
        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Pedidos de Compra',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'purchase.order',
                'type': 'ir.actions.act_window'
            }
        
    def view_picking(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for picking in self.browse(cr, uid, ids, context=context).picking_ids:
            inv.append(picking.id)
        
        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Recepciones',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'stock.picking',
                'type': 'ir.actions.act_window'
            }
        
    def view_advance(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for advance in self.browse(cr, uid, ids, context=context).advance_supplier_ids:
            inv.append(advance.id)
        
        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Anticipos',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'purchase.advance.supplier',
                'type': 'ir.actions.act_window'
            }
    
    def view_invoice_fob(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for invoice in self.browse(cr, uid, ids, context=context).invoice_fob_ids:
            inv.append(invoice.id)
        
        
        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Invoice FOB',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.invoice',
                'type': 'ir.actions.act_window'
            }
    
    def view_invoice(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for invoice in self.browse(cr, uid, ids, context=context).invoices_ids:
            inv.append(invoice.id)
        for invoice in self.browse(cr, uid, ids, context=context).invoices_arancel_ids:
            inv.append(invoice.id)
        
        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Cost Invoice',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.invoice',
                'type': 'ir.actions.act_window'
            }
#
