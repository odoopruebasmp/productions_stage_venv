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


class account_invoice_line(models.Model):
    _inherit = 'account.invoice.line'
    
    @api.one
    @api.depends('invoice_line_tax_id', 'product_id', 'invoice_id.state')
    def _iva(self):
        if self.invoice_line_tax_id:
            iva=''
            for imp in self.invoice_line_tax_id:
                if imp.account_collected_id and imp.account_collected_id.code == '24080502':
                    iva='IVA 19%'
                elif imp.account_collected_id and imp.account_collected_id.code == '24080503':
                    iva='IVA 5%'
                elif imp.account_collected_id and imp.account_collected_id.code == '24080502':
                    iva='IVA 16%'
            self.iva = iva
    
    iva=fields.Char(string='Iva', compute="_iva")
    

class pos_extra(models.Model):
    _name = 'pos.extra'
  
    ean_punto_de_venta = fields.Char(string='EAN Punto de Venta')
    nombre_punto_de_venta = fields.Char(string='Nombre Punto de Venta')
    cantidad_pto_vta = fields.Float(string='Cantidad Pto Vta')
    precio_bruto = fields.Float(string='Precio Bruto')
    precio_neto = fields.Float(string='Precio Neto')
    sale_line_id = fields.Many2one('sale.order.line', string='Sale Order Line')
    

class return_reason(models.Model):
    _name='return.reason'
    
    name = fields.Char(string='Reason')
    
    
class stock_move(models.Model):
    _inherit = 'stock.move'

    return_reason_id = fields.Many2one('return.reason', string='Motivo de devolucion')
    return_incoming = fields.Boolean(string='Return', readonly=True)
    nombre_punto_de_venta = fields.Char(string='Nombre Punto de Venta')
    cliente_final = fields.Char(string='cliente final')
    note_pedido = fields.Char(string='Note pedido')
    
    
class stock_picking(models.Model):
    _inherit = 'stock.picking'
    
    numero_dap = fields.Char(string='Numero DAP')
    guia_retorno = fields.Char(string='Guia Retorno')
    mpp = fields.Char(string='MPP')
    news = fields.Boolean(string='Novedades')
    reason = fields.Char(string='Motivo', size=128)
    return_incoming = fields.Boolean(string='Return', readonly=True)
    nombre_punto_de_venta = fields.Char(string='Nombre Punto de Venta')
    cust_ref = fields.Char(related="partner_id.ref", string='Customer Ref', store=True, readonly=True)
    sale_id_extra = fields.One2many('pos.extra', 'sale_line_id', string='POS Extra')
    

class stock_return_picking(models.Model):
    _inherit = 'stock.return.picking'
    
    return_reason_id = fields.Many2one('return.reason', string='Motivo de devolucion')
 

class stock_return_picking(models.Model):
    _inherit = 'stock.return.picking'

    numero_dap = fields.Char(string='Numero DAP')
    guia_retorno = fields.Char(string='Guia Retorno')
    mpp = fields.Char(string='MPP')
    
    
    #def create_returns(self, cr, uid, ids, context=None):
        #line_list=[]
        #temp_dict={}
        #if not context : context={}
        #res=super(stock_return_picking,self).create_returns(cr, uid, ids, context=context)
        #data = self.browse(cr, uid, ids[0], context=context)
        #for line in data.product_return_moves:
            #temp_dict[line.product_id.id] = line.return_reason_id.id
        
        #pick_in_obj = self.pool.get('stock.picking')
        #move_obj = self.pool.get('stock.move')
        
        #pick_ids = eval(res.get('domain'))[0][-1]
        #for pick in pick_in_obj.browse(cr, uid, pick_ids, context):
            #for move in pick.move_lines:
                #reason = temp_dict.get(move.product_id.id)
                #move_obj.write(cr, uid, move.id, {'return_incoming':True,'return_reason_id': reason})
        #pick_in_obj.write(cr, uid, pick_ids, {'return_incoming':True,'numero_dap':data.numero_dap,'guia_retorno':data.guia_retorno,'mpp': data.mpp})
        #return res


class zona_zona(models.Model):
    _name = 'zona.zona'
    
    name = fields.Char(string='Nombre')


class res_partner(models.Model):
    _inherit = "res.partner"    
    
    zona_id = fields.Many2one('zona.zona', string='Zona')
    
#    