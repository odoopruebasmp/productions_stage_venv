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


class res_company(models.Model):
    _inherit = "res.company"
    
    logo_service = fields.Binary(string='Firma Digitalizada')
    

class service_contact(models.Model):
    _name = "service.contact"
    
    name=fields.Char(string='Nombre', required=True)
    ref=fields.Char(string='Numero de Identificacion', required=True)
    email=fields.Char(string='Email')
    phone=fields.Char(string='Telefono')
    street=fields.Char(string='Direccion')
    
    _sql_constraints = [('name_uniq', 'unique(ref)', 'El numero de Identificacion no puede ser duplicado, por favor verifique nuevamente o valide si el tercero aun no se encuentra creado en el sistema'),
                        ]
    

class service_prioridad(models.Model):
    _name = "service.prioridad"
    
    name=fields.Char(string='Nombre', required=True)
    
    
#class service_category(models.Model):
    #_name = "service.category"
    
    #name=fields.Char(string='Nombre', required=True)
    
    
class service_costumer(models.Model):
    _name = "service.costumer"
    _order = 'name desc'
    
    @api.one
    @api.depends('date_purchase','date_reclamacion')
    def _garantia(self):        
        if self.date_purchase and self.date_reclamacion:
            date_purchase = datetime.strptime(self.date_purchase, DEFAULT_SERVER_DATETIME_FORMAT)
            date_reclamacion = datetime.strptime(self.date_reclamacion, DEFAULT_SERVER_DATETIME_FORMAT)
            if (date_reclamacion - date_purchase).days <= self.product_id.warranty*30:
                self.garantia = 'Aplica'
            else:
                self.garantia = 'No Aplica'
    
    
    @api.onchange('product_id')
    def _cantidad(self):
        if self.product_id:
            self.plu = self.product_id.plu
            
    @api.onchange('plu')
    def _cantidad2(self):
        if self.plu:
            self.product_id = self.env['product.product'].search([('plu','=',self.plu)], limit=1) or False
            
    
    # INFORMACION GENERAL
    name=fields.Char(string='Secuencia', readonly=True, default='Draft')
    summary=fields.Char(string='Objeto Reclamacion', required=True, readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)]})
    code=fields.Char(string='Numero de Reclamacion', readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)]}, copy=False)
    plu=fields.Char(string='PLU', required=True, readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)]})
    product_id=fields.Many2one('product.product', string='Producto', required=True, readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)]})
    product_ref=fields.Char(string='Referencia Interna', related='product_id.default_code', store=True, readonly=True)
    product_description=fields.Text(string='Descripcion', related='product_id.description', store=True, readonly=True)
    product_qty = fields.Float(string='Cantidad', digits=dp.get_precision('Product UoM'), required=True, readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)]})
    product_serial = fields.Many2one('stock.production.lot', string='Serial', readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)]})
    importacion=fields.Char(string='Importacion', readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)]})
    guia=fields.Char(string='Numero Guia Entrada', readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)]})
    guia_end=fields.Char(string='Numero Guia Salida', readonly=True, states={'diagnostico':[('required',True)]})
    date_purchase=fields.Datetime(string='Fecha de Compra', readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)]})
    date_reclamacion=fields.Datetime(string='Fecha de Reclamacion', required=True, readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)]})
    date_recepcion=fields.Datetime(string='Fecha de Recepcion', readonly=True, states={'confirm':[('readonly',False)]})
    responsable_id=fields.Many2one('res.partner', string='Responsable', readonly=True, states={'confirm':[('readonly',False)]})    
    prioridad_id=fields.Many2one('service.prioridad', string='Prioridad', readonly=True, states={'confirm':[('readonly',False)]})
    categ_id=fields.Many2one(string='Categoria', related='product_id.categ_id', store=True, readonly=True)
    user_recepcion_id=fields.Many2one('res.users', string='Recepcionado por:', readonly=True, states={'draft':[('invisible',True)]})
    #category_id=fields.Many2one('service.category', string='Categoria', required=True, readonly=True, states={'draft':[('readonly',False)]})
    date_limit_open=fields.Datetime(string='Fecha Limite Respuesta', readonly=True, states={'confirm':[('readonly',False)]})
    date_limit_close=fields.Datetime(string='Fecha Cierre', readonly=True, states={'diagnostico':[('readonly',False)]})
    observaciones=fields.Text(string='Observaciones', readonly=True, states={'draft':[('readonly',False)]}, required=True)
    observaciones_recepcion=fields.Text(string='Estado Recepcion', readonly=True, states={'confirm':[('readonly',False)]})
    # INFORMACION DEL RECLAMANTE
    partner_id=fields.Many2one('res.partner',string='Cliente', required=True, select=True, domain="[('type','=', 'default')]", readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]})
    partner_phone=fields.Char(string='Telefono', related='partner_id.phone', store=True, readonly=True)
    partner_email=fields.Char(string='Email', related='partner_id.email', store=True, readonly=True)
    partner_sucursal_id=fields.Many2one('res.partner',string='Sucursal', required=True, select=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]})
    partner_sucursal_phone=fields.Char(string='Telefono', related='partner_sucursal_id.phone', store=True, readonly=True)
    partner_sucursal_email=fields.Char(string='Email', related='partner_sucursal_id.email', store=True, readonly=True)
    contact_id=fields.Many2one('service.contact',string='Contacto', required=True,readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]})
    contact_phone=fields.Char(string='Telefono', related='contact_id.phone', store=True, readonly=True)
    contact_email=fields.Char(string='Email', related='contact_id.email', store=True, readonly=True)
    state=fields.Selection([('draft', 'Borrador'),('confirm', 'Confirmado'),('recept', 'Recepcionado'),('open', 'En Revision'),('diagnostico', 'Diagnostico'),('despachado', 'Despachado'),('close', 'Cerrado')], string='Estado', select=True, default='draft')
    garantia=fields.Char(string='Garantia', compute='_garantia', readonly=True, default='Indefinido', store=True)
    # OTROS
    tecnico_id2=fields.Many2one('res.partner', string='Tecnico', readonly=True, states={'recept':[('readonly',False)]})
    resultado_tecnico=fields.Selection([('cambio', 'Cambio'),
                                        ('cambio_interno', 'Cambio Interno'),
                                        ('no_aplica', 'No Aplica Garantia'),
                                        ('no_corresponde', 'No Corresponde'),
                                        ('no_falla', 'No Fallas'),
                                        ('no_falla1', 'No Fallas 1'),
                                        ('notacredito', 'Requiere Nota'),
                                        ('reparado', 'Reparado'),
                                        ('sin_empaque', 'Funcional Sin Empaque'),
                                        ], string='Resultado', readonly=True, states={'open':[('readonly',False)]})
    referencia=fields.Char(string='Albaran', readonly=True, states={'despachado':[('readonly',False)]})
    trabajos_tecnico=fields.Text(string='Trabajos Realizados', readonly=True, states={'open':[('readonly',False)]})
    observaciones_tecnico=fields.Text(string='Observaciones', readonly=True, states={'open':[('readonly',False)]})
    
    _sql_constraints = [('code_uniq', 'unique(code)', 'El Numero de Reclamacion no puede ser duplicado, por favor verifique nuevamente o valide si el Numero de Reclamacion ya se encuentra creado en el sistema'),
                        ]
    
    _track = {
        'state': {
            'service_costumer.mt_draft': lambda self, obj: obj['state'] == 'draft',
            'service_costumer.mt_confirm': lambda self, obj: obj['state'] == 'confirm',
            'service_costumer.mt_recept': lambda self, obj: obj['state'] == 'recept',
            'service_costumer.mt_open': lambda self, obj: obj['state'] == 'open',
            'service_costumer.mt_diagnostico': lambda self, obj: obj['state'] == 'diagnostico',
            'service_costumer.mt_despachado': lambda self, obj: obj['state'] == 'despachado',
            'service_costumer.mt_close': lambda self, obj: obj['state'] == 'close',
        }        
    }
        
    @api.multi
    def confirmar(self):
        sequence_obj = self.env['ir.sequence']
        number_seq = sequence_obj.get('service.costumer.number')
        return self.write({'state': 'confirm','name':number_seq})
    
    @api.multi
    def recepcionar(self):  
        return self.write({'user_recepcion_id': self._uid, 'state': 'recept'})
        
    @api.multi
    def abrir(self):  
        return self.write({'state': 'open'})
    
    @api.multi
    def diagnosticar(self):  
        return self.write({'state': 'diagnostico'})
    
    @api.multi
    def despachar(self):  
        return self.write({'state': 'despachado'})
        
    @api.multi
    def cerrar(self):
        return self.write({'state': 'close'})
        
    
#
