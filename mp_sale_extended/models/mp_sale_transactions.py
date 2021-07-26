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


class ProductCategory(models.Model):
	_inherit = "product.category"

	id_category_yuju = fields.Char(string='Id Categoria Yuju',size=5)
	name_category_yuju = fields.Char(string='Nombre Categoria Yuju',size=64)


class SaleTransactionsExtended(models.Model):
	_name = 'sale.transactions.extended'
	_description = 'Transacciones realizadas integracion Ventas E-commerce'
	_inherit = ['mail.thread']
	_order = 'date_transaccion desc'

	name = fields.Char(string='Orden de Venta',size=64)
	status_transaction = fields.Selection([
		('integrated', 'Integrado'),
		('process', 'Procesando'),
		('partial_integrated', 'Parcialmente Integrado'),
		('error', 'Error No integrado'),
	], required=True, string="Estatus de Transaccion")
	sales_channel = fields.Char(string='Canal Origen de Venta',size=64,readonly=False,)# Mercado libre o Linio
	sale_odoo = fields.Many2one('sale.order',string='Pedido Venta Odoo',required=False,)
	number_sale = fields.Char(string='Order de Venta Marketplace',size=64,readonly=False,)# Mercado libre o Linio
	number_sale_yuju = fields.Char(string='Numero de Order Yuju',)#Alfanumercio
	name_file_server = fields.Char(string='Nombre del Archivo',)#Nombre del archivo
	date_transaccion = fields.Datetime(string='Fecha de Integracion')#Generacion de la transaccion odoo
	date_created_tr = fields.Date(string='Fecha de Creacion Order')
	#cliente
	customer = fields.Many2one('res.partner',string='Cliente',required=False,)
	#Pago de Cliente
	id_transactions_payment = fields.Many2one('transactions.customer.receipts',string='Pago Integrado',)
	#Excepciones de Pedido
	tranctions_sales_ids = fields.One2many('sale.transactions.extended.exceptions','id_transactions_sale',string='Excepciones Ventas',)




	@api.multi
	def read_sftp_sales_e_commerce_1(self):
		conex_sftp = self.env['managment.control.sftp'].search_read([('active','=',True)])
		for rec_cx in conex_sftp:
			cx_type_test = rec_cx['type_test']
			cx_host = rec_cx['host']
			cx_port = int(rec_cx['port'])
			cx_user = rec_cx['user']
			cx_password = rec_cx['password']
			cx_path_access = rec_cx['path_access']
			cx_path_access_temp = rec_cx['path_access_temp']
			cx_path_access_read = rec_cx['path_access_read']
			cx_path_access_process = rec_cx['path_access_process'][0]           
			id_warehouse_inventory = rec_cx['id_warehouse_inventory'][0]
			id_ubicacion_inventory = rec_cx['id_ubicacion_inventory'][0]
			id_price_list = rec_cx['id_price_list'][0]
			id_price_list_version = rec_cx['id_price_list_version'][0]
			bln_price_pricelist = rec_cx['bln_price_pricelist']			
			id_ml_mk = int(rec_cx['id_ml_mk'])
			id_linio_mk = int(rec_cx['id_linio_mk'])
			bln_validate_sales_orders = rec_cx['bln_validate_sales_orders']
			
			#CLIENTE
			id_position_fiscal_customer = rec_cx['id_position_fiscal_customer'][0]
			id_position_fiscal_vendors = rec_cx['id_position_fiscal_vendors'][0]
			id_property_account_payable = rec_cx['id_property_account_payable'][0]#CUENTA POR PAGAR
			id_property_account_receivable = rec_cx['id_property_account_receivable'][0]#CUENTA POR COBRAR
			id_property_paymet_term = rec_cx['id_property_paymet_term'][0]
			id_sale_default = rec_cx['id_sale_default'][0]
			tributary_obligations_ids = rec_cx['tributary_obligations_ids']

		os.chdir(cx_path_access_temp)       
		
		try:
			client = paramiko.SSHClient()
			client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			client.connect(cx_host, port=cx_port, username=cx_user, password=cx_password)
			sftpclient = client.open_sftp()
		except Exception as e:
			raise Warning('No se ha conectado al servidor SFTP, contactar con administrador '+str(e))

		read_folder_path = str(cx_path_access+'/venta/in')
		try:
			sftpclient.chdir(read_folder_path)
		except IOError:
			raise Warning(u"Error Ruta de lectura en carpeta , '%s'" % read_folder_path)

		dirlist = sftpclient.listdir(cx_path_access+'/venta/in')

		os.chdir(cx_path_access_temp)       
		dirlist = sftpclient.listdir()
		processpath = str(cx_path_access+'/venta/procesado')
		dict_sale = {}
		for rec_f in dirlist:
			sftpclient.chdir()
			sftpclient.chdir(read_folder_path)
			sale_order_crt = False
			sale_order_line_crt = False
			sale_order_customer = False
			id_client_res = ''
			order_id = ''
			order_txt = ''
			orden_yuju = ''
			res_created = ''
			val_name =  str(rec_f[0:5])

			if str('ORDER') in (val_name.upper()):#solo lee de nombre order
				sftpclient.get(rec_f,rec_f)

				with open(rec_f, 'rb') as myfile:
					data=myfile.read()
					obj = json.loads(data)

					#UPDATE 10022021
					cntl_sales = self.env['managment.control.sales.stock'].search_read([('id_prefix_integracion','=',int(obj['marketplace_pk']))])
					for rc_sales in cntl_sales:
						name_prefix = rc_sales['name_prefix']
						sales_full = rc_sales['sales_full']
						id_ubicacion_inventory2 = rc_sales['id_ubicacion_inventory'][0]
						team_sales = rc_sales['team_sales'][0]
						labels_team_sales = rc_sales['labels_team_sales']

					date_created_at = datetime.strptime(obj['created_at'], "%Y-%m-%dT%H:%M:%S")


					if(not id_ubicacion_inventory2):
						id_ubicacion_inventory2 = id_ubicacion_inventory

					rs_sale_venta = self.env['sale.transactions.extended'].search(['&',('number_sale_yuju','=',obj['pk']),('status_transaction','not in',['integrated'])])#Validar no crear el mismo numero venta yuju si esta 
					#Falta validar en sale.order

					if(not rs_sale_venta):
						#crear transaccion de venta
						dict_transaction_sale = {
									'name':'VENTA ' + obj['pk'],
									'sales_channel': name_prefix,
									'number_sale':obj['reference'],
									'status_transaction':'process',
									'date_transaccion': str(time.strftime('%Y-%m-%d %H:%M:%S')),
									'date_created_tr': str(date_created_at.strftime('%Y-%m-%d')),
									'number_sale_yuju':obj['pk'],
									'name_file_server': str(rec_f),
									}
						res_cr_sale_transaction = self.env['sale.transactions.extended'].sudo().create(dict_transaction_sale)
						id_transaction_loc = res_cr_sale_transaction.id
				
						dt_type = 'contact'

						if(not obj['customer']['doc_type']):
							dt_number_identification = obj['billing_address']['taxid']
							dt_type_identification = self._get_type_identificacion('CC')#IDS PENDIENTE
						else:
							dt_number_identification = obj['customer']['doc_number']
							dt_type_identification = self._get_type_identificacion(obj['customer']['doc_type'])#IDS PENDIENTE


						dt_first_name = obj['customer']['first_name']
						dt_last_name = obj['customer']['last_name']
						dt_email = obj['customer']['email']
						dt_phone = obj['customer']['phone']
						dt_email = obj['customer']['email']
						dt_country= self._get_country('colombia')#por default

					
						if not obj['shipping_address']['region']:
							obj['shipping_address']['region'] = 'BOGOTA'
						dt_state = self._get_state_id(obj['shipping_address']['region'])#Buscar id estado
						if not dt_state:
							dt_state = self._get_state_id('BOGOTA')#Buscar id estado

						if not obj['shipping_address']['city']:
							obj['shipping_address']['city'] = 'BOGOTA, D.C.'
						dt_city = self._get_city_id(obj['shipping_address']['city'])#Buscar id ciudad
						if not dt_city:
							dt_city = self._get_city_id('BOGOTA, D.C.')#Buscar id estado

						if obj['shipping_address']['reference']:
							dt_street =  obj['shipping_address']['address']+' '+obj['shipping_address']['reference']+ ' ,'+obj['shipping_address']['region']+','+obj['shipping_address']['city']
						else:
							dt_street =  obj['shipping_address']['address']+' ,'+obj['shipping_address']['region']+','+obj['shipping_address']['city']
						#Verificar el numero posiblemnte exista

						if not dt_number_identification:
							descrition_log_txt = 'No ha sido posible crear el cliente, por favor contactar con administrador'
							res_validate1= self._generate_exception_integration('ERROR INTEGRANDO CLIENTE', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
							continue

						#buscar cliente existe
						rs_partner = self.env['res.partner'].sudo().search([('ref','=',dt_number_identification)])

						if not (rs_partner):
							dict_rec = {
										'type':dt_type,
										'ref_type':dt_type_identification,
										'ref':dt_number_identification,
										'name':dt_first_name +' '+ dt_last_name,
										'primer_nombre':dt_first_name,
										'primer_apellido':dt_last_name,
										'street':dt_street[0:50],
										'main_street':dt_street[0:50],                                
										'phone':dt_phone,
										'email':dt_email,
										'country_id':dt_country,
										'state_id':dt_state,
										'city_id':dt_city,
										'property_account_position':id_position_fiscal_customer,
										'property_payment_term':id_property_paymet_term,
										'property_account_payable': id_property_account_payable,
										'property_account_receivable': id_property_account_receivable,
										'electronic_invoice':True,
										'tributary_obligations_ids': [(6,0,tributary_obligations_ids)],
										}
							res_created = self.env['res.partner'].sudo().create(dict_rec)
							id_client_res = res_created.id
							sale_order_customer = True
						else:
							for rec_info in rs_partner:
								if(rec_info):
									id_client_res = rec_info[0].id#obtener el id de usuario ya registrado
									sale_order_customer = True

						if not sale_order_customer:
							descrition_log_txt = 'No ha sido posible crear el cliente, por favor contactar con administrador'
							res_validate1= self._generate_exception_integration('ERROR INTEGRANDO CLIENTE', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
							continue

						if (date_created_at.hour > 12):
							max_ship_date1 = date_created_at +timedelta(days=1)
							max_ship_date = max_ship_date1.strftime('%Y-%m-%d')
						else:
							max_ship_date = date_created_at.strftime('%Y-%m-%d')

						rs_sodoo = self.env['sale.order'].search([('n_oc','ilike',obj['pk'])])#Validar no crear el mismo numero venta odoo si esta 
						if (rs_sodoo):
							descrition_log_txt = 'No ha sido posible crear la orden de Venta, por favor contactar con administrador'
							res_validate1= self._generate_exception_integration('ERROR NUMERO DE ORDEN DE VENTA YA EXISTE EN SISTEMA', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
							continue
							
						dict_sale = {
									'partner_id': id_client_res,
									'partner_invoice_id': id_client_res,
									'partner_shipping_id': id_client_res,                           
									'deli_addres': dt_street,
									'n_oc': str(name_prefix)+'/'+str(obj['reference']),
									'date_order': str(date_created_at.strftime('%Y-%m-%d %H:%M:%S')),
									'fecha_malla': str(date_created_at.strftime('%Y-%m-%d')),
									'warehouse_id': id_warehouse_inventory,
									'pricelist_id': id_price_list,
									'location_id': id_ubicacion_inventory2,                              
									'order_type': 'ORDEN DE COMPRA ESTANDAR',
									'type_cross': 'factura',
									'order_policy':'picking',
									'picking_policy':'direct',
									'min_ship_date': str(date_created_at.strftime('%Y-%m-%d')),#fecha minima
									'max_ship_date': str(max_ship_date),#fecha maxima
									'user_id':id_sale_default,#Vendedor por defecto
									'categ_ids': [(6,0,labels_team_sales)],
									'section_id': team_sales,
									}

						res_cr_sale = self.env['sale.order'].create(dict_sale)



						if not sale_order_customer:
							descrition_log_txt = 'No ha sido posible crear la orden de Venta, por favor contactar con administrador'
							res_validate1= self._generate_exception_integration('ERROR INTEGRANDO CLIENTE', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
							res_cr_sale.unlink()
							continue

						sale_order_crt = True
						order_id = res_cr_sale
						res_cr_sale_order_line = ''

						if(sale_order_crt):
							for rec_item in obj['items']:
								res_product = self.env['product.product'].search(['&',('ean_codigo','=',str(rec_item['product']['ean'])),('active','=',True)])
								rec_prdt = ''

								if(res_product):
									for rec_prodyct_c in res_product:
										rec_prdt = rec_prodyct_c[0].id

								if(not res_product):
									descrition_log_txt = 'No ha sido posible encontrar el producto, por favor contactar con administrador'
									res_validate2= self._generate_exception_integration('ERROR INTEGRANDO PRODUCTO', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
									res_cr_sale.unlink()									
									continue

								price_pricelist = ''
								price_unit = ''
								#get price by price list
								if (bln_price_pricelist == True):
									res_price = self.env['product.pricelist.item'].search_read(['&',('price_version_id','=',id_price_list_version),('product_id','=',rec_prdt)],['price_surcharge'])
									for rec_prc in res_price:
										price_pricelist = rec_prc['price_surcharge']

									if(price_pricelist):
										price_unit = price_pricelist
									else:
										price_unit = (rec_item['price'] / 1.19)

								else:
									price_unit = (rec_item['price'] / 1.19)

								dict_sale_line = {
											'product_id': rec_prdt,
											'product_uom_qty': rec_item['quantity'],
											'price_unit': price_unit,
											'order_id': order_id.id             
											}

								res_cr_sale_order_line = self.env['sale.order.line'].create(dict_sale_line)

								if(not res_cr_sale_order_line):
									descrition_log_txt = 'No ha sido posible encontrar el producto, por favor contactar con administrador'
									res_validate2= self._generate_exception_integration('ERROR INTEGRANDO PRODUCTO', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
									res_cr_sale.unlink()
									res_cr_sale_order_line.unlink()
									continue

								sale_order_line_crt = True

							#Confirmar Venta
							#Generar informacion de Pago
							if(sale_order_crt  and sale_order_line_crt and res_product):
								if (bln_validate_sales_orders == True):
									res_cr_sale.signal_workflow('order_confirm')


								descrition_log_txt = 'Ha sido Integrado correctamente'
								vals_payment = {
										'name': 'PAGO DE CLIENTE',
										'sale_number_transaction': id_transaction_loc,
										'date_transaction': str(time.strftime('%Y-%m-%d %H:%M:%S')),
										'date_payment_tr': datetime.strptime(obj['payment_accredited_at'], "%Y-%m-%dT%H:%M:%S"),
										'shipping_cost': obj['shipping_cost'],
										'method_paid': obj['payment_method'],
										'payment_references': obj['payment_references'],
										'paid_total': obj['paid_total'],
										'total': obj['total'],
										'marketplace_fee': obj['marketplace_fee'],
										'seller_shipping_cost': obj['seller_shipping_cost'],
								}
								res_cr_payment_transaction = self.env['transactions.customer.receipts'].create(vals_payment)

								self._generate_exception_integration('INTEGRADO', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'integrated',order_id.id,id_client_res,res_cr_payment_transaction.id)

							if(sale_order_crt and res_product and sale_order_line_crt):
								sftpclient.remove(rec_f)
								sftpclient.chdir()
								sftpclient.chdir(processpath)
								sftpclient.put(rec_f, rec_f)
								os.remove(rec_f)

			else:
				print "No se procesa"
			

		client.close()
		sftpclient.close()

		return True


	@api.multi
	def integrated_sftp_sale_2(self):
		conex_sftp = self.env['managment.control.sftp'].search_read([('active','=',True)])
		for rec_cx in conex_sftp:
			cx_type_test = rec_cx['type_test']
			cx_host = rec_cx['host']
			cx_port = int(rec_cx['port'])
			cx_user = rec_cx['user']
			cx_password = rec_cx['password']
			cx_path_access = rec_cx['path_access']
			cx_path_access_temp = rec_cx['path_access_temp']
			cx_path_access_read = rec_cx['path_access_read']
			cx_path_access_process = rec_cx['path_access_process'][0]           
			id_warehouse_inventory = rec_cx['id_warehouse_inventory'][0]
			id_ubicacion_inventory = rec_cx['id_ubicacion_inventory'][0]
			id_price_list = rec_cx['id_price_list'][0]
			id_price_list_version = rec_cx['id_price_list_version'][0]
			bln_price_pricelist = rec_cx['bln_price_pricelist']			
			id_ml_mk = int(rec_cx['id_ml_mk'])
			id_linio_mk = int(rec_cx['id_linio_mk'])
			bln_validate_sales_orders = rec_cx['bln_validate_sales_orders']
			
			#CLIENTE
			id_position_fiscal_customer = rec_cx['id_position_fiscal_customer'][0]
			id_position_fiscal_vendors = rec_cx['id_position_fiscal_vendors'][0]
			id_property_account_payable = rec_cx['id_property_account_payable'][0]#CUENTA POR PAGAR
			id_property_account_receivable = rec_cx['id_property_account_receivable'][0]#CUENTA POR COBRAR
			id_property_paymet_term = rec_cx['id_property_paymet_term'][0]
			id_sale_default = rec_cx['id_sale_default'][0]
			tributary_obligations_ids = rec_cx['tributary_obligations_ids']

		os.chdir(cx_path_access_temp)       
		
		try:
			client = paramiko.SSHClient()
			client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			client.connect(cx_host, port=cx_port, username=cx_user, password=cx_password)
			sftpclient = client.open_sftp()
		except Exception as e:
			raise Warning('No se ha conectado al servidor SFTP, contactar con administrador '+str(e))

		read_folder_path = str(cx_path_access+'/venta/in')
		try:
			sftpclient.chdir(read_folder_path)
		except IOError:
			raise Warning(u"Error Ruta de lectura en carpeta , '%s'" % read_folder_path)

		dirlist = sftpclient.listdir(cx_path_access+'/venta/in')

		os.chdir(cx_path_access_temp)       
		dirlist = sftpclient.listdir()
		processpath = str(cx_path_access+'/venta/procesado')
		dict_sale = {}
		for rec_f in dirlist:
			sftpclient.chdir()
			sftpclient.chdir(read_folder_path)
			sale_order_crt = False
			sale_order_line_crt = False
			sale_order_customer = False
			id_client_res = ''
			order_id = ''
			order_txt = ''
			orden_yuju = ''
			res_created = ''
			val_name =  str(rec_f[0:5])

			if (rec_f == self.name_file_server):
				if str('ORDER') in (val_name.upper()):#solo lee de nombre order
					sftpclient.get(rec_f,rec_f)

					with open(rec_f, 'rb') as myfile:
						data=myfile.read()
						obj = json.loads(data)
					
						cntl_sales = self.env['managment.control.sales.stock'].search_read([('id_prefix_integracion','=',int(obj['marketplace_pk']))])
						for rc_sales in cntl_sales:
							name_prefix = rc_sales['name_prefix']
							sales_full = rc_sales['sales_full']
							id_ubicacion_inventory2 = rc_sales['id_ubicacion_inventory'][0]
							team_sales = rc_sales['team_sales'][0]
							labels_team_sales = rc_sales['labels_team_sales']


						if(not id_ubicacion_inventory2):
							id_ubicacion_inventory2 = id_ubicacion_inventory

						date_created_at = datetime.strptime(obj['created_at'], "%Y-%m-%dT%H:%M:%S")
						id_transaction_loc = self.id
				
						dt_type = 'contact'

						if(not obj['customer']['doc_type']):
							dt_number_identification = obj['billing_address']['taxid']
							dt_type_identification = self._get_type_identificacion('CC')#IDS PENDIENTE
						else:
							dt_number_identification = obj['customer']['doc_number']
							dt_type_identification = self._get_type_identificacion(obj['customer']['doc_type'])#IDS PENDIENTE


						dt_first_name = obj['customer']['first_name']
						dt_last_name = obj['customer']['last_name']
						dt_email = obj['customer']['email']
						dt_phone = obj['customer']['phone']
						dt_email = obj['customer']['email']
						dt_country= self._get_country('colombia')#por default

					
						if not obj['shipping_address']['region']:
							obj['shipping_address']['region'] = 'BOGOTA'
						dt_state = self._get_state_id(obj['shipping_address']['region'])#Buscar id estado
						if not dt_state:
							dt_state = self._get_state_id('BOGOTA')#Buscar id estado

						if not obj['shipping_address']['city']:
							obj['shipping_address']['city'] = 'BOGOTA, D.C.'
						dt_city = self._get_city_id(obj['shipping_address']['city'])#Buscar id ciudad
						if not dt_city:
							dt_city = self._get_city_id('BOGOTA, D.C.')#Buscar id estado

						if obj['shipping_address']['reference']:
							dt_street =  obj['shipping_address']['address']+' '+obj['shipping_address']['reference']+ ' ,'+obj['shipping_address']['region']+','+obj['shipping_address']['city']
						else:
							dt_street =  obj['shipping_address']['address']+' ,'+obj['shipping_address']['region']+','+obj['shipping_address']['city']
						#Verificar el numero posiblemnte exista

						if not dt_number_identification:
							descrition_log_txt = 'No ha sido posible crear el cliente, por favor contactar con administrador'
							res_validate1= self._generate_exception_integration('ERROR INTEGRANDO CLIENTE', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
							continue

						#buscar cliente existe
						rs_partner = self.env['res.partner'].sudo().search([('ref','=',dt_number_identification)])

						if not (rs_partner):
							dict_rec = {
										'type':dt_type,
										'ref_type':dt_type_identification,
										'ref':dt_number_identification,
										'name':dt_first_name +' '+ dt_last_name,
										'primer_nombre':dt_first_name,
										'primer_apellido':dt_last_name,
										'street':dt_street[0:50],
										'main_street':dt_street[0:50],                                
										'phone':dt_phone,
										'email':dt_email,
										'country_id':dt_country,
										'state_id':dt_state,
										'city_id':dt_city,
										'property_account_position':id_position_fiscal_customer,
										'property_payment_term':id_property_paymet_term,
										'property_account_payable': id_property_account_payable,
										'property_account_receivable': id_property_account_receivable,
										'electronic_invoice':True,
										'tributary_obligations_ids': [(6,0,tributary_obligations_ids)],
										}
							res_created = self.env['res.partner'].sudo().create(dict_rec)
							id_client_res = res_created.id
							sale_order_customer = True
						else:
							for rec_info in rs_partner:
								if(rec_info):
									id_client_res = rec_info[0].id#obtener el id de usuario ya registrado
									sale_order_customer = True

						if not sale_order_customer:
							descrition_log_txt = 'No ha sido posible crear el cliente, por favor contactar con administrador'
							res_validate1= self._generate_exception_integration('ERROR INTEGRANDO CLIENTE', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
							continue

						if (date_created_at.hour > 12):
							max_ship_date1 = date_created_at +timedelta(days=1)
							max_ship_date = max_ship_date1.strftime('%Y-%m-%d')
						else:
							max_ship_date = date_created_at.strftime('%Y-%m-%d')

						rs_sodoo = self.env['sale.order'].search([('n_oc','ilike',obj['pk'])])#Validar no crear el mismo numero venta odoo si esta 
						if (rs_sodoo):
							descrition_log_txt = 'No ha sido posible crear la orden de Venta, por favor contactar con administrador'
							res_validate1= self._generate_exception_integration('ERROR NUMERO DE ORDEN DE VENTA YA EXISTE EN SISTEMA', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
							continue

						dict_sale = {
									'partner_id': id_client_res,
									'partner_invoice_id': id_client_res,
									'partner_shipping_id': id_client_res,                           
									'deli_addres': dt_street,
									'n_oc': str(name_prefix)+'/'+str(obj['reference']),
									'date_order': str(date_created_at.strftime('%Y-%m-%d %H:%M:%S')),
									'fecha_malla': str(date_created_at.strftime('%Y-%m-%d')),
									'warehouse_id': id_warehouse_inventory,
									'pricelist_id': id_price_list,
									'location_id': id_ubicacion_inventory2,                              
									'order_type': 'ORDEN DE COMPRA ESTANDAR',
									'type_cross': 'factura',
									'order_policy':'picking',
									'picking_policy':'direct',
									'min_ship_date': str(date_created_at.strftime('%Y-%m-%d')),#fecha minima
									'max_ship_date': str(max_ship_date),#fecha maxima
									'user_id':id_sale_default,#Vendedor por defecto
									'categ_ids': [(6,0,labels_team_sales)],
									'section_id': team_sales,
									}

						res_cr_sale = self.env['sale.order'].create(dict_sale)


						if not sale_order_customer:
							descrition_log_txt = 'No ha sido posible crear la orden de Venta, por favor contactar con administrador'
							res_validate1= self._generate_exception_integration('ERROR INTEGRANDO CLIENTE', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
							res_cr_sale.unlink()
							continue

						sale_order_crt = True
						order_id = res_cr_sale
						res_cr_sale_order_line = ''

						if(sale_order_crt):
							for rec_item in obj['items']:
								res_product = self.env['product.product'].search(['&',('ean_codigo','=',str(rec_item['product']['ean'])),('active','=',True)])
								rec_prdt = ''

								if(res_product):
									for rec_prodyct_c in res_product:
										rec_prdt = rec_prodyct_c[0].id

								if(not res_product):
									descrition_log_txt = 'No ha sido posible encontrar el producto, por favor contactar con administrador'
									res_validate2= self._generate_exception_integration('ERROR INTEGRANDO PRODUCTO', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
									res_cr_sale.unlink()									
									continue

								price_pricelist = ''
								price_unit = ''
								#get price by price list
								if (bln_price_pricelist == True):
									res_price = self.env['product.pricelist.item'].search_read(['&',('price_version_id','=',id_price_list_version),('product_id','=',rec_prdt)],['price_surcharge'])
									for rec_prc in res_price:
										price_pricelist = rec_prc['price_surcharge']

									if(price_pricelist):
										price_unit = price_pricelist
									else:
										price_unit = (rec_item['price'] / 1.19)

								else:
									price_unit = (rec_item['price'] / 1.19)

								dict_sale_line = {
											'product_id': rec_prdt,
											'product_uom_qty': rec_item['quantity'],
											'price_unit': price_unit,
											'order_id': order_id.id             
											}

								res_cr_sale_order_line = self.env['sale.order.line'].create(dict_sale_line)

								if(not res_cr_sale_order_line):
									descrition_log_txt = 'No ha sido posible encontrar el producto, por favor contactar con administrador'
									res_validate2= self._generate_exception_integration('ERROR INTEGRANDO PRODUCTO', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'error',False,False,False)
									res_cr_sale.unlink()
									res_cr_sale_order_line.unlink()
									continue

								sale_order_line_crt = True

							#Confirmar Venta
							#Generar informacion de Pago
							if(sale_order_crt  and sale_order_line_crt and res_product):
								if (bln_validate_sales_orders == True):
									res_cr_sale.signal_workflow('order_confirm')


								descrition_log_txt = 'Ha sido Integrado correctamente'
								vals_payment = {
										'name': 'PAGO DE CLIENTE',
										'sale_number_transaction': id_transaction_loc,
										'date_transaction': str(time.strftime('%Y-%m-%d %H:%M:%S')),
										'date_payment_tr': datetime.strptime(obj['payment_accredited_at'], "%Y-%m-%dT%H:%M:%S"),
										'shipping_cost': obj['shipping_cost'],
										'method_paid': obj['payment_method'],
										'payment_references': obj['payment_references'],
										'paid_total': obj['paid_total'],
										'total': obj['total'],
										'marketplace_fee': obj['marketplace_fee'],
										'seller_shipping_cost': obj['seller_shipping_cost'],
								}
								res_cr_payment_transaction = self.env['transactions.customer.receipts'].create(vals_payment)

								self._generate_exception_integration('INTEGRADO', descrition_log_txt,str(time.strftime('%Y-%m-%d %H:%M:%S')),id_transaction_loc,'integrated',order_id.id,id_client_res,res_cr_payment_transaction.id)

							if(sale_order_crt and res_product and sale_order_line_crt):
								sftpclient.remove(rec_f)
								sftpclient.chdir()
								sftpclient.chdir(processpath)
								sftpclient.put(rec_f, rec_f)
								os.remove(rec_f)

				else:
					print "No se procesa"

			else:
				print "No conincide"
			

		client.close()
		sftpclient.close()

		return True



	def todayAt(hr, min=0, sec=0, micros=0):
		now = datetime.now()
		return now.replace(hour=hr, minute=min, second=sec, microsecond=micros)

	def normalize_data(self,str2):
		string_d = str2.encode('utf8')
		replacements = (
			("á", "a"),
			("é", "e"),
			("í", "i"),
			("ó", "o"),
			("ú", "u"),
			("ñ", "#"),
		)
		for a, b in replacements:
			string_d = string_d.replace(a, b).replace(a.upper(), b.upper())
			
		return string_d

	def _generate_exception_integration(self,name_transactions,description_transaction,date_transaction,id_transaction_loc,status_transaction,order_id,customer_id,payment_id):
		res_transacciones = self.env['sale.transactions.extended'].search([('id','=',id_transaction_loc)])
		for rec_upt in res_transacciones:
			res_transacciones.write({'status_transaction':status_transaction,'sale_odoo':order_id,'customer':customer_id,'id_transactions_payment':payment_id})

		dict_vals = {
			'name': name_transactions, 
			'date_transaction': date_transaction,
			'description_transaction': description_transaction,
			'id_transactions_sale': id_transaction_loc,
			}
		res_transaction_exceptions = self.env['sale.transactions.extended.exceptions'].sudo().create(dict_vals)

		return res_transaction_exceptions



	def _get_type_identificacion(self,name_type_identification):
		if((name_type_identification == 'CC') or (name_type_identification == 'C.C.')):
			name_type_i = 'Cédula de ciudadanía'
		elif ((name_type_identification == 'CE') or (name_type_identification == 'C.E.')):
			name_type_i = 'Cédula de extranjería'
		elif ((name_type_identification == 'NI') or (name_type_identification == 'N.I.')):
			name_type_i = 'Numero de identificación tributaria'
		else:
			name_type_i = False

		res_type_identificacion = self.env['res.document.type'].search([('name','ilike',str(name_type_i))])
		rec_type_id = ''
		if(res_type_identificacion):
			for rec_type_c in res_type_identificacion:
				rec_type_id = rec_type_c[0].id

		return rec_type_id


	def _get_country(self,name_country):
		res_country = self.env['res.country'].search([('name','ilike',str(name_country))])
		country_id = ''
		if(res_country):
			for rec_c in res_country:
				country_id = rec_c[0].id

		return country_id


	def _get_state_id(self,name_state):
		name_state2 = self.normalize_data(name_state.strip())
		res_country_state = self.env['res.country.state'].search([('name','ilike',str(name_state2.encode('utf-8')))])
		state_id = ''
		if(res_country_state):
			for rec_c in res_country_state:
				state_id = rec_c[0].id

		return state_id

	def _get_city_id(self,name_city):
		name_city2 = self.normalize_data(name_city.strip())
		res_city = self.env['res.city'].search([('name','ilike',str(name_city2.encode('utf-8')))])
		city_id = ''
		if(res_city):
			for rec_c in res_city:
				city_id = rec_c[0].id

		return city_id


	def _get_id_product(self,id_sku):
		res_product = self.env['product.product'].search(['&',('ean_codigo','=',str(id_sku)),('active','=',True)])
		rec_prdt = ''
		if(res_product):
			for rec_prodyct_c in res_product:
				rec_prdt = {'id':rec_prodyct_c[0].id, 'validate': True}
		else:
			rec_prdt = rec_prdt = {'validate': False}


		return rec_prdt

#Trasnacciones de log integracion Pedidos de Ventas
class SaleTransactionsExtendedExceptions(models.Model):
	_name = 'sale.transactions.extended.exceptions'
	_description = 'Transacciones realizadas Excepciones de Ventas'

	name = fields.Char(string='Transaccion',size=64)
	date_transaction = fields.Datetime(string='Fecha de Transaccion',)
	description_transaction = fields.Char(string='Descripcion')

	id_transactions_sale = fields.Many2one('sale.transactions.extended',string='Excepciones de Venta')


#Integracion de Pagos Recibos de Cliente
class TransactionsCustomerReceipts(models.Model):
	_name = 'transactions.customer.receipts'
	_description = 'Transacciones realizadas integracion Recibos de Cliente'
	_inherit = ['mail.thread']
	_order = 'name desc'

	name = fields.Char(string='Transaccion',size=64,readonly=True, )
	date_transaction = fields.Datetime(string='Fecha de Transaccion',readonly=True, )
	date_payment_tr = fields.Datetime(string='Fecha de Pago', )
	sale_number_transaction = fields.Many2one('sale.transactions.extended',string='Pedido Venta Integrado',required=False, readonly=True, )
	#info
	method_paid = fields.Char(string='Metodo de Pago',)
	payment_references = fields.Char(string='Numero de Referencia',)
	shipping_cost = fields.Char(string='Costo de envío del cliente',)
	total = fields.Char(string='Total',)
	paid_total = fields.Char(string='Pago Total',)
	marketplace_fee = fields.Char(string='Comisión del Marketplace',)
	seller_shipping_cost = fields.Char(string='Costo de envío del vendedor',)
	amount_invoice = fields.Float(string='Monto de factura',)





#Integracion de Stock por ubicacion Ventas
class StockTransactionsLocationE(models.Model):
	_name = 'stock.transactions.location.sales.days'
	_description = 'Transacciones realizadas Ventas E-commerce'
	_order = 'name desc'

	name = fields.Char(string='Transaccion',size=64)
	sale_order_name = fields.Char(string='Pedido de Venta',)
	id_product = fields.Many2one('product.product',string='Producto',required=True, readonly=True, )
	qty_sale = fields.Integer(string='Cantidad Pedido',)
	date_created_transaction = fields.Date(string='Fecha de Creacion' )
	date_transaction_sale = fields.Datetime(string='Fecha de Transaccion',readonly=True, )
	qty_stock = fields.Integer(string='Cantida Stock',)
	sum_unit = fields.Boolean(string='Suma productos unitarios',default=False)
	generated_file = fields.Selection([
		('not_generated', 'No generado'),
		('generated', 'Generado'),
	], required=True, string="Achivo Generado",default="not_generated")




#Integracion de Stock por ubicacion
class StockTransactionsLocationE(models.Model):
	_name = 'stock.transactions.location.e'
	_description = 'Transacciones realizadas integracion Ubicacion E-commerce'
	_inherit = ['mail.thread']
	_order = 'name desc'

	name = fields.Char(string='Transaccion',size=64)
	date_transaction = fields.Datetime(string='Fecha de Transaccion',)
	type_transaction = fields.Selection([
		('by_incoming_location', 'Ingreso a Ubicacion'),
		('by_transaction_sales', 'Ventas de dia'),
	], required=True, string="Estatus de Transaccion")

	
	products_t_ids = fields.One2many('stock.transactions.location.e.products','stock_transaction_id',string='Productos')



	@api.multi
	def generate_sftp_transactions_location_e(self):
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


		os.chdir(cx_path_access_temp)    
		txt_file = '' 
		
		try:
			client = paramiko.SSHClient()
			client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			client.connect(cx_host, port=cx_port, username=cx_user, password=cx_password)
			sftpclient = client.open_sftp()
		except Exception as e:
			raise Warning('No se ha conectado al servidor SFTP, contactar con administrador '+str(e))
			

		read_folder_path = str(cx_path_access+'/producto/out')
		try:
			sftpclient.chdir(read_folder_path)
		except IOError:
			raise Warning(u"Error Ruta de lectura en carpeta , '%s'" % read_folder_path)


		#Realizar bsuqeuda de ventas en integracion
		date_ref = datetime.now().strftime('%Y-%m-%d 00:00:01')
		date_ref2 = datetime.now().strftime('%Y-%m-%d 23:59:00')
		date_created_tr= datetime.now().strftime('%Y-%m-%d')
		date_created_tr_timne= datetime.now().strftime('%Y%m%d%H%m%s')
		res_sales_integrated = self.env['sale.transactions.extended'].search_read(['&','&','&',('status_transaction','=','integrated'),('sale_odoo','!=',False),('date_transaccion','>=',date_ref),('date_transaccion','<=',date_ref2)],['id','sale_odoo'])

		for rec_salinteg in res_sales_integrated:
			id_sale_odoo = rec_salinteg['sale_odoo'][0]

			rs_order_line = self.env['sale.order.line'].search_read(['&',('order_id','=',id_sale_odoo),('state','in',['confirmed','done'])],['id','product_id','product_uom_qty'])
			for rec_ in rs_order_line:
				rec_salinteg['sale_odoo'][1]
				search_sale = self.env['stock.transactions.location.sales.days'].search_count([('sale_order_name','=',rec_salinteg['sale_odoo'][1])])

				if(search_sale == 0):
					dict_order_line = {
								"name": 'Transaccion_'+str(date_created_tr_timne),
								"sale_order_name":rec_salinteg['sale_odoo'][1],
								"id_product":rec_['product_id'][0],
								"qty_sale":rec_['product_uom_qty'],
								"date_created_transaction": date_created_tr,
								"generated_file": 'not_generated',
								"sum_unit" : False,
					}
					res_created = self.env['stock.transactions.location.sales.days'].sudo().create(dict_order_line)
					id_transaction_location_days = res_created.id

		#Buscar informacion segun dia de productos
		res_location_integrated = self.env['stock.transactions.location.sales.days'].search_read(['&','&',('date_created_transaction','>=',date_ref),('date_created_transaction','<=',date_ref2),('generated_file','=','not_generated')],['id','id_product','qty_sale','generated_file','sum_unit'])
		qty_all = 0


		dirlist = sftpclient.listdir()
		processpath = str(cx_path_access+'/venta/procesado')
		#Buscar segun ubicacion
		list_p = cx_id_transactions_stock.split(',')
		domain_search = []
		tmp_file = ''

		
		for rec_2 in res_location_integrated:
			if(rec_2['generated_file'] == 'not_generated'):
				if(rec_2['sum_unit'] == False):
					date_object = str(time.strftime('%Y%m%d%H%M%S'))
					os.chdir(cx_path_access_temp)
					stock_file = 'STOCK_'+date_object+'.txt'
					txt_file = open(stock_file, 'w')
					txt_file.write("sku|stock\n".decode())
					##Cantidad registrada en transacciones de  un producto
					qty_unit_prd = self._get_total_product_qty(rec_2['id_product'][0],rec_2['id'])
					#cantidad stock
					res_product = self.env['product.product'].search([('id','=',rec_2['id_product'][0]),('active','=',True)])
					for rec_prd in res_product:
						available_qty = rec_prd.with_context({'location' : id_ubicacion_inventory}).qty_available

					total_file =  available_qty - qty_unit_prd
					os.chdir(cx_path_access_temp)
					ean_codigo = self._get_ref_product(rec_2['id_product'][0])
					rec_qty = total_file
					txt_file.write(str(ean_codigo)+"|"+str(rec_qty)+"\n".decode())
					#dict

					txt_file.close()
					archivo_temp_open = open(stock_file, 'rb')
					data_upload = archivo_temp_open.read()
					sftpclient.put(stock_file, stock_file)

					res_write_days= self.env['stock.transactions.location.sales.days'].search([('id_product','=',rec_2['id_product'][0])])
					for rec_write in res_write_days:
						write = rec_write.write({'sum_unit': True,'generated_file': 'generated'})

					#registrar Movimiento
					dict_registros = {'name':str(stock_file),'date_transaction': time.strftime('%Y-%m-%d %H:%M:%S'),'type_transaction':'by_transaction_sales'}
					res_ = self.create(dict_registros)
					list_add = {'product_id': rec_2['id_product'][0],'codigo_barras': ean_codigo, 'stock_qty_disponible': qty_unit_prd, 'stock_qty_report': total_file,'stock_transaction_id': res_.id ,'stock_location_id': id_ubicacion_inventory}
					res_prd = self.env['stock.transactions.location.e.products'].create(list_add)

					os.remove(stock_file)
			else:
				print "No genera nada"

		#client.close()
		sftpclient.close()

		return True


	def _get_total_product_qty(self,id_product,id_trans_days):
		res_qty_product = self.env['stock.transactions.location.sales.days'].search_read([('id_product','=',id_product)],['qty_sale'])
		sum_all = 0
		if(res_qty_product):
			for rec_prodyct_c in res_qty_product:
				sum_all = + rec_prodyct_c['qty_sale']

		return sum_all


	def _get_codigo_barras(self,id_product):
		res_product = self.env['product.product'].search_read(['&',('id','=',id_product),('active','=',True)],['ean_codigo'])
		rec_prdt = ''
		if(res_product):
			for rec_prodyct_c in res_product:
				ean_codigo = rec_prodyct_c['ean_codigo']

		return ean_codigo


	def _get_ref_product(self,id_product):
		res_product = self.env['product.product'].search_read(['&',('id','=',id_product),('active','=',True)],['ean_codigo','default_code'])
		rec_prdt = ''
		if(res_product):
			for rec_prodyct_c in res_product:
				default_code = rec_prodyct_c['default_code']

		return default_code




#Integracion de Stock por ubicacion productos
class StockTransactionsLocationEProducts(models.Model):
	_name = 'stock.transactions.location.e.products'
	_description = 'Transacciones realizadas integracion Ubicacion E-commerce'
	_inherit = ['mail.thread']
	_order = 'name desc'

	name = fields.Char(string='Transaccion',size=64)
	product_id = fields.Many2one('product.product', string='Producto')
	codigo_barras = fields.Char(string='Codigo de Barras',)
	stock_qty_disponible = fields.Integer(string='Cantidad Disponible',)
	stock_qty_report = fields.Integer(string='Cantidad Reportada',)
	stock_location_id = fields.Many2one('stock.location',string='id Ubicacion',)    

	stock_transaction_id = fields.Many2one('stock.transactions.location.e',string='Transactions',)



class ProducTemplate(models.Model):
	_inherit = 'product.template'

	integrated_e_commerce = fields.Boolean(string='Disponible Integracion E-commerce',default=False)


class ProducProduct(models.Model):
	_inherit = 'product.product'

	@api.model
	def create(self, vals):
		res_c = super(ProducProduct, self).create(vals)
		#Generate function txt file product
		self.generate_transaction_products(vals,res_c.id)

		return res_c

	@api.multi
	def write(self, vals):
		res_w = super(ProducProduct, self).write(vals)
		#Generate function txt file product
		self._generate_write_transaction_products(vals,self.id)

		return res_w

	def generate_transaction_products(self,vals_info,idProduct):
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
			active_create_product = rec_cx['bln_active_create_product']

		if(active_create_product == True):
			if(vals_info['type'] == 'product'):
				os.chdir(cx_path_access_temp)
				try:
					client = paramiko.SSHClient()
					client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
					client.connect(cx_host, port=cx_port, username=cx_user, password=cx_password)
					sftpclient = client.open_sftp()
				except Exception as e:
					raise Warning('No se ha conectado al servidor SFTP, contactar con administrador '+str(e))

				#print sftpclient

				read_folder_path = str(cx_path_access+'/producto/out')
				try:
					sftpclient.chdir(read_folder_path)
				except IOError:
					raise Warning(u"Error Ruta de lectura en carpeta , '%s'" % read_folder_path)

				dirlist = sftpclient.listdir(cx_path_access+'/producto/out')

				dirlist = sftpclient.listdir()
				processpath = str(cx_path_access+'/producto/procesado')

				os.chdir(cx_path_access_temp)
				date_object = str(time.strftime('%Y%m%d%H%M%S'))
				product_file = 'PRODUCT_'+date_object+'.txt'
				txt_file = open(product_file, 'w')
				sep = '|'
				#Data
				condition_product = 'new'
				txt_data = ''
				data = ''
				str_for = "client_id|parent_id|name|description|stock|sku_simple|sku|price|special_price|brand|shipping|shipping_price|discount|discount_from|discount_to|availability|condition|category|color|secondary_color|gender|size|width|height|depth|dimensions_unit|weight|weight_unit|link|mpn|material|tax|listing_type|shipping_width|shipping_height|shipping_depth|short_description|model|description_html|asin|ean|upc|isbn_10|isbn_13|template_html|gtin|jan|product_weight|official_store|part_number|scent|delivery_time|imagen_1|imagen_2|imagen_3|imagen_4|imagen_5|imagen_6|imagen_7|imagen_8|imagen_9|imagen_10|binding|author|editor|edition|publisher|book_title|publication_date|number_of_pages|language|special_price_amz|special_price_linio|warranty|warranty_months"

				for rc in str_for.split("|"):
					data = rc.replace("client_id",vals_info['default_code']) if rc == 'client_id' else data
					data = rc.replace("parent_id",vals_info['default_code']) if rc == 'parent_id' else data
					data = rc.replace("name",vals_info['name']) if rc == 'name' else data
					data = rc.replace("description",vals_info['name']) if rc == 'description' else data
					data = rc.replace("sku_simple",vals_info['default_code']) if rc == 'sku_simple' else data
					data = rc.replace("sku",vals_info['default_code']) if rc == 'sku' else data
					data = rc.replace("ean",vals_info['ean_codigo']) if rc == 'ean' else data
					data = rc.replace("brand",str(self._get_name_brand(vals_info['marca_id']))) if rc == 'brand' else data
					data = rc.replace("color",vals_info['color']) if rc == 'color' else data
					data = rc.replace("material",str(vals_info['material'])) if rc == 'material' else data
					data = rc.replace("shipping",str('-1')) if rc == 'shipping' else data
					#size product
					data = rc.replace("width",str(vals_info['prod_width'])) if rc == 'width' else data
					data = rc.replace("height",str(vals_info['prod_high'])) if rc == 'height' else data
					data = rc.replace("depth",str(vals_info['prod_large'])) if rc == 'depth' else data
					data = rc.replace("dimensions_unit",str('cm')) if rc == 'dimensions_unit' else data
					data = rc.replace("weight",str(vals_info['prod_weight'])) if rc == 'weight' else data
					data = rc.replace("weight_unit",str('kg')) if rc == 'weight_unit' else data

					data = rc.replace("shipping_width",str(vals_info['emp_width'])) if rc == 'shipping_width' else data
					data = rc.replace("shipping_height",str(vals_info['emp_width'])) if rc == 'shipping_height' else data
					data = rc.replace("shipping_depth",str(vals_info['emp_width'])) if rc == 'shipping_depth' else data
					#more 
					data = rc.replace("category",str(self._get_id_categoty_yuju(vals_info['category_id'])))  if rc == 'category' else data
					data = rc.replace("condition",'new') if rc == 'condition' else data

					txt_data = txt_data+data+'|'
					data = ''


				txt_file.write(txt_data[:-1].decode())
				txt_file.close()
				archivo_temp_open = open(product_file, 'rb')
				data_upload = archivo_temp_open.read()
				sftpclient.put(product_file, product_file)

				#Generate log de integracion
				vals_cr = {
						'name': 'Creacion de '+str(vals_info['default_code']),
						'id_product':(idProduct),
						'date_transaction': datetime.now(),
						'type_transaction': 'new',
						'name_file_transaction': product_file,
						'state_transaction': 'Integrado',
						'observacion_transaction': 'Sin observaciones',
						}
				res_prd = self.env['transactions.products'].create(vals_cr)


	def _generate_write_transaction_products(self,vals_info,idProduct):
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
			active_update_product = rec_cx['bln_active_update_product']

		if(active_update_product == True):
			os.chdir(cx_path_access_temp)	
			try:
				client = paramiko.SSHClient()
				client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
				client.connect(cx_host, port=cx_port, username=cx_user, password=cx_password)
				sftpclient = client.open_sftp()
			except Exception as e:
				raise Warning('No se ha conectado al servidor SFTP, contactar con administrador '+str(e))
				
			#print sftpclient

			read_folder_path = str(cx_path_access+'/producto/out')
			try:
				sftpclient.chdir(read_folder_path)
			except IOError:
				raise Warning(u"Error Ruta de lectura en carpeta , '%s'" % read_folder_path)

			dirlist = sftpclient.listdir(cx_path_access+'/producto/out')

			dirlist = sftpclient.listdir()
			processpath = str(cx_path_access+'/producto/procesado')

			os.chdir(cx_path_access_temp)
			date_object = str(time.strftime('%Y%m%d%H%M%S'))
			product_file = 'PRODUCT_'+date_object+'.txt'
			txt_file = open(product_file, 'w')
			sep = '|'
			#Data       
			txt_data = ''
			data = ''
			str_for = "client_id|parent_id|name|description|stock|sku_simple|sku|price|special_price|brand|shipping|shipping_price|discount|discount_from|discount_to|availability|condition|category|color|secondary_color|gender|size|width|height|depth|dimensions_unit|weight|weight_unit|link|mpn|material|tax|listing_type|shipping_width|shipping_height|shipping_depth|short_description|model|description_html|asin|ean|upc|isbn_10|isbn_13|template_html|gtin|jan|product_weight|official_store|part_number|scent|delivery_time|imagen_1|imagen_2|imagen_3|imagen_4|imagen_5|imagen_6|imagen_7|imagen_8|imagen_9|imagen_10|binding|author|editor|edition|publisher|book_title|publication_date|number_of_pages|language|special_price_amz|special_price_linio|warranty|warranty_months"

			res_product = self.env['product.product'].search_read(['&',('id','=',idProduct),('active','=',True)],['ean_codigo','default_code'])
			rec_prdt = ''

			if(res_product):
				for rec_prodyct_c in res_product:
					ean_codigo = rec_prodyct_c['ean_codigo']
					default_code = rec_prodyct_c['default_code']


			marca = ''
			clean = ''
			marca = self._get_name_brand(vals_info['marca_id']) if 'marca_id' in vals_info else clean
			color = vals_info['color'] if 'color' in vals_info else clean
			material = vals_info['material'] if 'material' in vals_info else clean
			name = vals_info['name'] if 'name' in vals_info else clean
			description = vals_info['name'] if 'name' in vals_info else clean
			prod_width = vals_info['prod_width'] if 'prod_width' in vals_info else clean
			prod_high = vals_info['prod_high'] if 'prod_high' in vals_info else clean
			prod_large = vals_info['prod_large'] if 'prod_large' in vals_info else clean
			prod_weight = vals_info['prod_weight'] if 'prod_weight' in vals_info else clean
			shipping_width = vals_info['emp_width'] if 'emp_width' in vals_info else clean
			shipping_height = vals_info['emp_width'] if 'emp_width' in vals_info else clean
			shipping_depth = vals_info['emp_width'] if 'emp_width' in vals_info else clean
			category_id = self._get_id_categoty_yuju(vals_info['category_id']) if 'category_id' in vals_info else clean
			

			for rc in str_for.split("|"):
				data = rc.replace("client_id",str(default_code)) if rc == 'client_id' else data
				data = rc.replace("parent_id",str(default_code)) if rc == 'parent_id' else data
				data = rc.replace("name",str(name)) if rc == 'name' else data
				data = rc.replace("description",str(description)) if rc == 'description' else data
				data = rc.replace("sku_simple",str(default_code)) if rc == 'sku_simple' else data
				data = rc.replace("sku",str(default_code)) if rc == 'sku' else data
				data = rc.replace("ean",str(ean_codigo)) if rc == 'ean' else data
				data = rc.replace("color",color) if rc == 'color' else data
				data = rc.replace("material",material) if rc == 'material' else data
				data = rc.replace("brand",str(marca)) if rc == 'brand' else data
				data = rc.replace("width",str(prod_width)) if rc == 'width' else data
				data = rc.replace("height",str(prod_high)) if rc == 'height' else data
				data = rc.replace("depth",str(prod_large)) if rc == 'depth' else data
				data = rc.replace("dimensions_unit",str('cm')) if rc == 'dimensions_unit' else data
				data = rc.replace("weight",str(prod_weight)) if rc == 'weight' else data
				data = rc.replace("weight_unit",str('kg')) if rc == 'weight_unit' else data
				data = rc.replace("shipping_width",str(shipping_width)) if rc == 'shipping_width' else data
				data = rc.replace("shipping_height",str(shipping_width)) if rc == 'shipping_height' else data
				data = rc.replace("shipping_depth",str(shipping_width)) if rc == 'shipping_depth' else data
				data = rc.replace("category",str(category_id))  if rc == 'category' else data

				txt_data = txt_data+data+'|'
				data = ''

			txt_file.write(txt_data[:-1].decode())
			txt_file.close()
			archivo_temp_open = open(product_file, 'rb')
			data_upload = archivo_temp_open.read()
			sftpclient.put(product_file, product_file)

			#Generate log de integracion
			vals_cr = {
					'name': 'Actualizacion de '+str(default_code),
					'id_product':(idProduct),
					'date_transaction': datetime.now(),
					'type_transaction': 'update',
					'name_file_transaction': product_file,
					'state_transaction': 'Integrado',
					'observacion_transaction': 'Sin observaciones',
					}
			res_prd = self.env['transactions.products'].create(vals_cr)



	def _get_name_brand(self,id):
		res_product_brand = self.env['product.marca'].search_read([('id','=',id)],['name'])
		rec_brd = ''
		if(res_product_brand):
			for rec_brand in res_product_brand:
				rec_brd =  rec_brand['name']

		return rec_brd



	def _get_id_categoty_yuju(self,id):
		res_cat_id = self.env['product.category'].search_read([('id','=',id)],['id_category_yuju'])
		rec_cat = ''
		if(res_cat_id):
			for rec_cat_prd in res_cat_id:
				rec_cat =  rec_cat_prd['id_category_yuju']

		return rec_cat


#Integracion de Productos Con YUJU
class TransactionsProducts(models.Model):
	_name = 'transactions.products'
	_description = 'Transacciones realizadas integracion Productos'
	_inherit = ['mail.thread']
	_order = 'name desc'

	name = fields.Char(string='Transaccion Producto',size=64, readonly=True, )
	id_product = fields.Many2one('product.product',string='Producto', readonly=True, )
	date_transaction = fields.Datetime(string='Fecha de Transaccion',readonly=True, )
	type_transaction = fields.Selection([
		('new', 'Nuevo'),
		('update', 'Actualizacion'),
	], string="Tipo de Transaccion",readonly=True,)
	name_file_transaction= fields.Char(string='Nombre Archivo',size=64,readonly=True,)
	state_transaction= fields.Char(string='Estado de Integracion',size=64,readonly=True,)
	observacion_transaction= fields.Char(string='Observacion de Integracion',size=64,readonly=True,)
	#related
	#default_code = fields.Char(related='id_product.default_code',string="Referencia Interna", store=False, readonly=True)
	#ean_codigo = fields.Char(related='id_product.ean_codigo', string="Codigo de Barras", store=False, readonly=True)
