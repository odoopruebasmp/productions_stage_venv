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
    @api.depends('partner_shipping_id', 'invoice_id.ref2')
    def _compute_cliente(self):
        if self.partner_shipping_id:
            self.type_cliente = self.partner_shipping_id.category_id2 and self.partner_shipping_id.category_id2.name or False
            self.zona = self.partner_shipping_id.zona_id and self.partner_shipping_id.zona_id.name or False
    
    @api.one
    @api.depends('product_id', 'invoice_id.ref2')
    def _compute_otros(self):
        if self.product_id:
            self.tipologia = self.product_id.tipologia_inv or False
            self.type_product = self.product_id.type
            self.categ_cadenas = self.product_id.customer_categ_id and self.product_id.customer_categ_id.id or False
            self.categ_proveedor = self.product_id.supplier_categ_id and self.product_id.supplier_categ_id.id or False
            self.suppler_id = self.product_id.partner_purchase and self.product_id.partner_purchase.id or False
            self.type_compra = self.product_id.type_compra or False
            self.fabricante_id = self.product_id.fabricante_id and self.product_id.fabricante_id.id or False
            self.evento = self.product_id.product_event or False
            self.country_fabricante_id = self.product_id.fabricante_id and self.product_id.fabricante_id.country_id and self.product_id.fabricante_id.country_id.id or False
    
    type_product = fields.Char(string='Tipo Producto', compute='_compute_otros', store=True)
    categ_cadenas = fields.Char(string='Categoria Cadenas', compute='_compute_otros', store=True)
    tipologia = fields.Char(string='Tipologia', compute='_compute_otros', store=True)
    suppler_id = fields.Many2one('res.partner', string='Proveedor', compute='_compute_otros', store=True)
    categ_proveedor = fields.Char(string='Categoria Proveedor', compute='_compute_otros', store=True)
    type_cliente = fields.Char(string='Tipo Cliente', compute='_compute_cliente', store=True)
    zona = fields.Char(string='Zona', compute='_compute_cliente', store=True)
    type_compra = fields.Selection([('nacional', 'Nacional'),('importado', 'Importado')], compute='_compute_otros', string='Tipo Compra')
    fabricante_id = fields.Many2one('res.partner', string='Fabricante', compute='_compute_otros', store=True)
    evento = fields.Char(string='Evento', compute='_compute_otros', store=True)
    country_fabricante_id = fields.Many2one('res.country', string='Pais Fabricante', compute='_compute_otros', store=True)
    evento = fields.Char(string='Evento', compute='_compute_otros', store=True)


class account_invoice(models.Model):
    _inherit = "account.invoice"

    @api.one
    @api.depends('invoice_line', 'invoice_line.fabricante_id')
    def _compute_otros(self):
        if self.invoice_line:
            self.fabricante_id = self.invoice_line[0].fabricante_id and self.invoice_line[0].fabricante_id.id or False

    fabricante_id = fields.Many2one('res.partner', string='Fabricante', compute='_compute_otros', store=True)
    country_fabricante_id = fields.Many2one('res.country', string='Pais Fabricante', related='fabricante_id.country_id',
                                            store=True, readonly=True)

    @api.multi
    def compute_cost(self):
        if self.company_id and self.company_id.sale_cost_invoice and self.type == "out_invoice" and self._uid == 1:
            self.ref2 = self.origin
            for line in self.invoice_line:
                if line.product_id and line.product_id.type == "product":
                    debit_id = line.product_id.categ_id.cogs_account_id.id
                    credit_id = line.product_id.categ_id.property_stock_account_output_categ.id
                    amount = line.cost_t
                    self._cr.execute(
                        ''' UPDATE account_move_line SET debit=%s WHERE move_id=%s and name=%s and account_id=%s''',
                        (amount, self.move_id.id, line.product_id.default_code, debit_id))
                    self._cr.execute(
                        ''' UPDATE account_move_line SET credit=%s WHERE move_id=%s and name=%s and account_id=%s''',
                        (amount, self.move_id.id, line.product_id.default_code, credit_id))
        elif self.company_id and self.company_id.sale_cost_invoice and self.type == "out_refund" and self._uid == 1:
            self.ref2 = self.origin
            for line in self.invoice_line:
                if line.product_id and line.product_id.type == "product":
                    debit_id = line.product_id.categ_id.property_stock_account_output_categ.id
                    credit_id = line.product_id.categ_id.cogs_account_id.id
                    amount = abs(line.cost_t)
                    self._cr.execute(
                        ''' UPDATE account_move_line SET debit=%s WHERE move_id=%s and name=%s and account_id=%s''',
                        (amount, self.move_id.id, line.product_id.default_code, debit_id))
                    self._cr.execute(
                        ''' UPDATE account_move_line SET credit=%s WHERE move_id=%s and name=%s and account_id=%s''',
                        (amount, self.move_id.id, line.product_id.default_code, credit_id))
        return True


class stock_move(models.Model):
    _inherit = "stock.move"
        
    fabricante_id = fields.Many2one('res.partner', related="purchase_line_id.fabricante_id", string='Fabricante', store=True)
    country_fabricante_id = fields.Many2one('res.country', string='Pais Fabricante', related='fabricante_id.country_id', store=True, readonly=True)
