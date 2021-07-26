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

class TransactionsCustomerReceipts(models.Model):
	_inherit = 'transactions.customer.receipts'

	
	@api.multi
	def generate_payment_customer_default(self):
		conex_sftp = self.env['managment.control.sftp'].search_read([('active','=',True)])
		for rec_cx in conex_sftp:
			cx_type_test = rec_cx['type_test']
			cx_host = rec_cx['host']
			cx_port = int(rec_cx['port'])
			cx_user = rec_cx['user']
			cx_password = rec_cx['password']
			cx_path_access = rec_cx['path_access']
			cx_id_transactions_stock = str(rec_cx['id_transactions_stock'])
			cx_path_access_temp = rec_cx['path_access_temp']
			id_ubicacion_inventory = rec_cx['id_ubicacion_inventory'][0]


		return True



class GeneratePaymentPaymentMasive(models.Model):
    _name = 'generated.payment.customer.masive'
    _description = 'Modelo de Creacion de Pagos De Cliente'

    name = fields.Char(string='Transaccion de Pago')