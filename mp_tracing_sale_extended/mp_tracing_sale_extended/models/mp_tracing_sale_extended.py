# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

class AccountInvoiceLine(models.Model):
	_inherit = "account.invoice.line"
	
	@api.multi
	@api.depends('price_unit', 'discount', 'invoice_line_tax_id', 'quantity','product_id', 'invoice_id.partner_id', 'invoice_id.currency_id')
	def _tracing_product(self):

		self.product_low_turnover= self.product_id.product_low_turnover
		self.qty_initial_prd= self.product_id.qty_initial_prd



	product_low_turnover = fields.Boolean(string='Baja Rotación',default=False,compute='_tracing_product',store=True)
	qty_initial_prd = fields.Integer(string='Cantidad Inicial',default=0,compute='_tracing_product',store=True)



class ProductTemplate(models.Model):
	_inherit = "product.template"

	product_low_turnover = fields.Boolean(string='Baja Rotación',default=False)
	qty_initial_prd = fields.Integer(string='Cantidad Inicial',default=0)



class ProductProduct(models.Model):
	_inherit = "product.product"

	product_low_turnover = fields.Boolean(string='Baja Rotación',default=False)
	qty_initial_prd = fields.Integer(string='Cantidad Inicial',default=0)
