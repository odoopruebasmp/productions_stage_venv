# -*- coding: utf-8 -*-

from openerp import models, fields, api



class ManagmentControlSftp(models.Model):
	_name = 'managment.control.sftp'
	_description = 'Administracion de acceso SFTP'
	_inherit = ['mail.thread']
	_order = 'name desc'

	name = fields.Char(string='',size=64,required=False,readonly=False)
	type_test = fields.Selection([
		('test', 'Pruebas'),
		('production', 'Produccion'),
	], required=True, string="Ambiente")
	host = fields.Char('Hostname',required=True,)
	port = fields.Char('Puerto',required=True,)
	user = fields.Char('Usuario',required=True,)
	password = fields.Char('Password',required=True,)
	key_required = fields.Boolean("Llave SSH")
	key_password = fields.Char('Contraseña key RSA')
	key_bin = fields.Binary('Llave RSA de acceso')
	path_access = fields.Char('Directorio')
	path_access_read = fields.Char('Directorio de Lectura')
	path_access_process = fields.Char('Directorio Procesados')
	path_access_temp = fields.Char('Directorio Local Temp')
	path_access_error = fields.Char('Directorio Error')
	id_warehouse_inventory = fields.Many2one('stock.warehouse',string='Nombre Almacen',required=True,)
	id_ubicacion_inventory = fields.Many2one('stock.location',string='Nombre Ubicacion',required=True,)
	id_price_list = fields.Many2one('product.pricelist',string='Lista de Precios')
	id_price_list_version = fields.Many2one('product.pricelist.version',string='Version Lista de Precios')
	bln_price_pricelist = fields.Boolean("Precios por Lista de Precios",default=False,help="Si marca esta opcion el sistema tomara el precio segun la lista definida")
	id_ml_mk = fields.Char(string='Id Prefijo Mercado Libre')
	id_linio_mk = fields.Char(string='Id Prefijo Linio')
	id_sale_default = fields.Many2one('res.users',string='Vendedor por Defecto',required=False,)

	#Integrated Sales Odoo
	id_managment_sales_stock_ids = fields.One2many('managment.control.sales.stock','id_managment_control_sftp',string='Control Pedidos Add')

	#Inventario
	id_transactions_stock = fields.Char('Id de Ubicaciones Stock',required=True,)	
	#cliente
	id_property_paymet_term  = fields.Many2one('account.payment.term',string='Plazo de Pago cliente',)
	id_position_fiscal_customer  = fields.Many2one('account.fiscal.position',string='Posicion Fiscal cliente',)
	id_position_fiscal_vendors  = fields.Many2one('account.fiscal.position',string='Posicion Fiscal Provedores',)
	id_property_account_payable = fields.Many2one('account.account',string='Cuentas por pagar',)	
	id_property_account_receivable = fields.Many2one('account.account',string='Cuentas por Cobrar',)
	tributary_obligations_ids = fields.Many2many('tributary.obligations',string='Obligaciones de Facturacion Electronica',)
	active = fields.Boolean(string='Activo',)
	#Producto
	bln_active_create_product = fields.Boolean("Permite Creacion Productos",default=False)
	bln_active_update_product = fields.Boolean("Permite Actualizacion Productos",default=False)
	#Pagos
	id_journal_payment_default  = fields.Many2one('account.journal',string='Metodo de pago Mercado Libre',)
	id_payment_customer_ids = fields.One2many('managment.control.payment.config','id_payment_customer',string='Item Recibos')

	#control 
	bln_validate_sales_orders = fields.Boolean("Confirmar Automaticamente Ventas",default=False)



#update 10022021
class ManagmentControlSalesStock(models.Model):
	_name = 'managment.control.sales.stock'
	_description = 'Control Pedidos de Ventas Stock'

	id_prefix_integracion = fields.Char(string='Id Prefijo de Integracion',required=True,)
	name_prefix = fields.Char(string='Nombre Prefijo de Integracion',required=True,)
	sales_full = fields.Boolean(string='Is Full',default=False)
	id_ubicacion_inventory = fields.Many2one('stock.location',string='Nombre Ubicacion',required=True,)
	labels_team_sales = fields.Many2many('crm.case.categ',string='Etiquetas',)
	team_sales = fields.Many2one('crm.case.section',string='Equipo de Ventas',required=False,)


	id_managment_control_sftp  = fields.Many2one('managment.control.sftp',string='Managment Control',)

		

class ManagmentControlPaymentConfug(models.Model):
	_name = 'managment.control.payment.config'
	_description = 'Control de Lineas en recibos de pagos de clientes'

	id_account_advance  = fields.Many2one('account.account',string='Cuenta',required=True,)
	txt_account_advance = fields.Char('Comentario',required=True,)
	id_account_analytic  = fields.Many2one('account.analytic.account',string='Centro de Costo',)
	id_payment_customer  = fields.Many2one('managment.control.sftp',string='de Pago cliente',)