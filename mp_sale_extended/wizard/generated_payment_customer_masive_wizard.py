# -*- coding: utf-8 -*-
from openerp import models, fields, api
from openerp.addons import decimal_precision as dp
from openerp.exceptions import Warning
from datetime import datetime, date
from datetime import timedelta
from openerp import netsvc
from lxml import etree
import time
import paramiko
from ftplib import FTP
import re
import os
import json
import sys
import logging


class GeneratePaymentPaymentMasive(models.TransientModel):
	_name = 'generated.payment.customer.masive'
	_description = 'Modelo de Creacion de Pagos De Cliente'


	@api.model
	def _count(self):
		return len(self._context.get('active_ids', []))

	name = fields.Char(string='Transaccion de Pago')
	count =fields.Integer(default=_count, string='Order Count')
	journal_id = fields.Many2one('account.journal',string='Comprobante',required=True,)
	period_id = fields.Many2one('account.period',string='Periodo', required=True,)
	required_lines_default = fields.Boolean(string='Diferencias por Defecto', default=False)

	search_t_ids = fields.One2many('generated.payment.customer.masive.searchs','search_transaction_id',string='Facturas')


	@api.onchange('search_t_ids')
	def _onchange_search_t_ids(self):
		conex_sftp = self.env['managment.control.sftp'].search_read([('active','=',True)])
		for rec_cx in conex_sftp:
			id_journal_payment_default = rec_cx['id_journal_payment_default'][0]

		vals_list_ep = []
		searchs_res = self.env['account.invoice'].search_read([('id','in',self._context.get('active_ids', []))],['partner_id','date_invoice','state','name','number','amount_untaxed','amount_total','internal_number','id'])

		for rec_ in searchs_res:
			invoice_id = rec_['id']
			partner_id = rec_['partner_id']
			date_invoice = rec_['date_invoice']
			state = rec_['state']
			name = rec_['name']
			number = rec_['number']
			amount_untaxed = rec_['amount_untaxed']
			amount_total = rec_['amount_total']
			internal_number = rec_['internal_number']

			vals_list_ep.append({
								'name': 'Historial de ',
								'customer_id': partner_id,
								'picking_order_id': '1',
								'invoice_id': invoice_id,
								'amount_untaxed':amount_untaxed,
								'amount_total':amount_total,
								})

		res = self.update({'journal_id':id_journal_payment_default,'search_t_ids': vals_list_ep})

		return res
	    

	@api.multi
	def generate_data(self):
		searchs_res = self.env['account.invoice'].search_read([('id','in',self._context.get('active_ids', []))],['partner_id','date_invoice','state','name','number','amount_untaxed','amount_total','internal_number','account_id','id'])

		company_id = self.env.user.company_id

		for rec_ in searchs_res:
			invoice_id = rec_['id']
			partner_id = rec_['partner_id'][0]
			account_invoice_l_id = rec_['account_id'][0]
			date_invoice = rec_['date_invoice']
			state = rec_['state']
			name = rec_['name']
			number = rec_['number']
			amount_untaxed = rec_['amount_untaxed']
			internal_number = rec_['internal_number']
			amount_total = rec_['amount_total']

			#Get accoun move line
			res_account_mvl = self.env['account.move.line'].search_read(['&',('ref','=',str(number)),('account_id','=',account_invoice_l_id)],['id'])
			for rec_5 in res_account_mvl:
				id_move_line_by =rec_5['id']

			res_account = self.env['account.journal'].search_read([('id','=',self.journal_id.id)],['default_debit_account_id','default_credit_account_id'])
			for rec_1 in res_account:
				account_debit_by =rec_1['default_debit_account_id'][0]
				account_credit_by =rec_1['default_credit_account_id'][0] 
			#Generar inser en modelo de recibos de clientes
			#account_voucher
			vals_payment = {
							'partner_id':partner_id,
							'amount':amount_untaxed,
							'account_id': account_debit_by,
							'journal_id': self.journal_id.id,
							'date': str(time.strftime('%Y-%m-%d')),
							'period_id': self.period_id.id,
							'type': 'receipt',
							'payment_option': 'with_writeoff',
							'company_id': company_id.id,

			}
			res_cr = self.env['account.voucher'].create(vals_payment)
			id_transaction_loc = res_cr.id

			#account_move_line
			vals_payment_line = {
							'move_line_id' : id_move_line_by,
							'voucher_id': id_transaction_loc,
							'account_id': account_invoice_l_id,
							#'amount_original':amount_total,
							#'amount_unreconciled':amount_total,
							'type':'cr',
							'reconcile': True,
							'amount':amount_total,
							'company_id': company_id.id,
			}

			res_cr2 = self.env['account.voucher.line'].create(vals_payment_line)
			#Valores adicionales por defecto
			res_search_1 = self.env['managment.control.payment.config'].search_read()
			id_account_analytic = ''
			for rec_reg in res_search_1:
				if (rec_reg['id_account_analytic']):
					id_account_analytic = rec_reg['id_account_analytic'][0]
				else:
					id_account_analytic = False

				vals_distribution_amount = {
							'voucher_id' : id_transaction_loc,
							'amount': '1',
							'name': rec_reg['txt_account_advance'],
							'account_id':rec_reg['id_account_advance'][0],
							'account_analytic_id': id_account_analytic,
					}
				res_cr2 = self.env['account.distribution.amount'].create(vals_distribution_amount)





class GeneratePaymentPaymentMasiveSearch(models.TransientModel):
	_name = 'generated.payment.customer.masive.searchs'

	name = fields.Char(string='Transaccion',size=64)
	customer_id = fields.Many2one('res.partner', string='Cliente')
	picking_order_id = fields.Many2one('stock.picking', string='Orden de Entrega')
	invoice_id = fields.Many2one('account.invoice',string='Factura',)
	amount_untaxed = fields.Float(string='Monto SUB_TOTAL')
	amount_total = fields.Float(string='Monto TOTAL')

	search_transaction_id = fields.Many2one('generated.payment.customer.masive',string='Facturas',)
