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

class product_marca(models.Model):
    _name = "product.marca"
    
    name = fields.Char(string='Marca', size=64)

class product_product(models.Model):
    _inherit = "product.product"

    siigo_code = fields.Char(string='Siigo Code') 
    ean_14 = fields.Char(string='EAN 14')
    plu = fields.Char(string='PLU Sodimac')
    plu_14 = fields.Char(string='PLU La 14')
    material = fields.Char(string='Material')
    color = fields.Char(string='Color')
    ean_codigo = fields.Char(string='Codigo de barras')
    required_certificate = fields.Boolean(string='Requiere certificado?')
    product_register = fields.Char(string='Certificado', size=250)
    emp_large = fields.Float(string='Largo cm',size=128,digits=(16,2))
    emp_width = fields.Float(string='Ancho cm',size=128,digits=(16,2))
    emp_high = fields.Float(string='Alto cm',size=128,digits=(16,2))
    emp_weight = fields.Float(string='Peso kg',size=128,digits=(16,2))
    emp_qty = fields.Float(string='Cant contenida',size=128,digits=(16,2))
    subemp_large = fields.Float(string='Largo cm',size=128,digits=(16,2))
    subemp_width = fields.Float(string='Ancho cm',size=128,digits=(16,2))
    subemp_high = fields.Float(string='Alto cm',size=128,digits=(16,2))
    subemp_weight = fields.Float(string='Peso kg',size=128,digits=(16,2))
    subemp_qty = fields.Float(string='Cant contenida',size=128,digits=(16,2))
    prod_large = fields.Float(string='Largo cm',size=128,digits=(16,2))
    prod_width = fields.Float(string='Ancho cm',size=128,digits=(16,2))
    prod_high = fields.Float(string='Alto cm',size=128,digits=(16,2))
    prod_weight = fields.Float(string='Peso kg',size=128,digits=(16,2))
    product_event =  fields.Char(string='Eventos')
    division_id = fields.Many2one('product.category', string='Division', change_default=True, domain="[('type','=','normal')]")
    category_id = fields.Many2one('product.category', string='Categoria',  change_default=True, domain="[('type','=','normal')]")
    marca_id = fields.Many2one('product.marca', string='Marca',)
    customer_categ_id = fields.Many2one('customer.category', string='Categoria Cadenas')
    supplier_categ_id = fields.Many2one('supplier.category', string='Categoria Proveedor')
    tariff_head = fields.Char("Partida Arancelaria", size=10, required=False)
    
    
    @api.onchange('parent_categ_id','categ_id')
    def _onchange_categ_id(self):
        product_obj =  self.env['product.product']
        template_obj =  self.env['product.template']
        category_obj =  self.env['product.category']
        if self.categ_id:
            parent_categ_id = self.categ_id.parent_id
            if parent_categ_id:
                category_id = parent_categ_id.id
                parent_category_id = parent_categ_id.parent_id.id
                if parent_category_id:
                    division_id = parent_category_id
                else:
                    division_id = ''
            else:
                category_id = ''
                division_id = ''
                
            self.category_id =category_id
            self.division_id =division_id
            
#TODO BORRAR TODO LO DEL TEMPLATE
class product_template(models.Model):
    _inherit = "product.template"

    siigo_code = fields.Char(string='Siigo Code') 
    ean_14 = fields.Char(string='EAN 14')
    plu = fields.Char(string='PLU')
    material = fields.Char(string='Material')
    color = fields.Char(string='Color')
    ean_codigo = fields.Char(string='Codigo de barras')
    required_certificate = fields.Boolean(string='Requiere certificado?')
    warranty_time = fields.Char(string='Tiempo de garantia')
    product_register = fields.Char(string='Certificado', size=250)
    emp_large = fields.Float(string='Largo cm',size=128,digits=(16,2))
    emp_width = fields.Float(string='Ancho cm',size=128,digits=(16,2))
    emp_high = fields.Float(string='Alto cm',size=128,digits=(16,2))
    emp_weight = fields.Float(string='Peso kg',size=128,digits=(16,2))
    emp_qty = fields.Float(string='Cant contenida',size=128,digits=(16,2))
    subemp_large = fields.Float(string='Largo cm',size=128,digits=(16,2))
    subemp_width = fields.Float(string='Ancho cm',size=128,digits=(16,2))
    subemp_high = fields.Float(string='Alto cm',size=128,digits=(16,2))
    subemp_weight = fields.Float(string='Peso kg',size=128,digits=(16,2))
    subemp_qty = fields.Float(string='Cant contenida',size=128,digits=(16,2))
    prod_large = fields.Float(string='Largo cm',size=128,digits=(16,2))
    prod_width = fields.Float(string='Ancho cm',size=128,digits=(16,2))
    prod_high = fields.Float(string='Alto cm',size=128,digits=(16,2))
    prod_weight = fields.Float(string='Peso kg',size=128,digits=(16,2))
    product_event =  fields.Char(string='Eventos')
    division_id = fields.Many2one('product.category', string='Division', change_default=True, domain="[('type','=','normal')]")
    category_id = fields.Many2one('product.category', string='Categoria',  change_default=True, domain="[('type','=','normal')]")
    marca_id = fields.Many2one('product.marca', string='Marca',)
    categ_id = fields.Many2one('product.category', string='Subcategoria', required=True, change_default=True, domain="[('type','=','normal')]" ,help="Selecciones la subcategoria para el producto")
    type_negocio = fields.Selection([('linea', 'Linea'),('nuevos', 'Nuevos Negocios'),('eventos', 'Eventos')], string='Tipo de Compra')
    type_compra = fields.Selection([('nacional', 'Nacional'),('importado', 'Importado')], string='Origen')
                
    @api.onchange('parent_categ_id','categ_id')
    def _onchange_categ_id(self):
        product_obj =  self.env['product.product']
        template_obj =  self.env['product.template']
        category_obj =  self.env['product.category']
        if self.categ_id:
            parent_categ_id = category_obj.browse(self.categ_id.id).parent_id.id
            if parent_categ_id:
                category_id = parent_categ_id
                parent_category_id = category_obj.browse(parent_categ_id).parent_id.id
                if parent_category_id:
                    division_id = parent_category_id
                else:
                    division_id = ''
            else:
                category_id = ''
                division_id = ''
                
            self.category_id =category_id
            self.division_id =division_id
               
    
class customer_category(models.Model):
    _name = "customer.category"
    
    name = fields.Char(string='Nombre', size=250)
                
    
class supplier_category(models.Model):
    _name = "supplier.category"
    
    name = fields.Char(string='Nombre', size=250)  
  

class res_partner(models.Model):
    _inherit = "res.partner"
    
    no_tienda = fields.Char(string='No. Tienda')
    ean_localizacion = fields.Char(string='EAN Localizacion Padre')
    cedi_padre = fields.Char(string='Nombre Cedi Padre')
    
#