# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from datetime import datetime, timedelta, date
from openerp import SUPERUSER_ID
from dateutil.relativedelta import relativedelta

class AccountInvoiceLine(models.Model):
	_inherit = "account.invoice.line"
	

	@api.multi
	@api.depends('price_unit', 'discount', 'invoice_line_tax_id', 'quantity',
		'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id')
	def _get_number_sale(self):

		for rec in self:
			#Pedido de Venta
			rec.n_sale_order= rec.invoice_id.stock_picking_id.origin
			#Orden de compra
			rec.n_oc= rec.invoice_id.n_oc
			#orden movimiento
			rec.n_picking_order= rec.invoice_id.stock_picking_id.name


	n_sale_order = fields.Char(string='Pedido de Venta',compute='_get_number_sale',store=True)
	n_oc = fields.Char(string='N O.C.', compute='_get_number_sale', store=True)
	n_picking_order = fields.Char(string='Nro Picking',compute='_get_number_sale',store=True)
