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

class product_product(models.Model):
    _inherit = 'product.product'
    
    product_substitutes_ids = fields.One2many('product.substitutes', 'product_id_2', string='Productos Sustitutos')
    product_complementary_ids = fields.One2many('product.complementary', 'product_id1', string='Productos Complementarios')
    

class product_complementary(models.Model):
    _name = 'product.complementary'
    
    @api.one
    @api.depends('line_ids', 'coheficiente')
    def _get_qty(self):
        if self.line_ids:
            cant = 0.0
            cant_in = 0.0
            for location in self.line_ids:
               cant +=  location.qty
               cant_in +=  location.qty_in
            self.qty_complementary = cant
            self.qty = cant*self.coheficiente
            self.qty_complementary_in = cant_in
            self.qty_in = cant_in*self.coheficiente
    
    line_ids = fields.One2many('product.complementary.location', 'complementary_id', string='Lineas', required=True, select=True)
    qty_complementary = fields.Float(compute="_get_qty", string="Cantidad Disponible Complementarios", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    qty = fields.Float(compute="_get_qty", string="Cantidad Disponible", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    qty_complementary_in = fields.Float(compute="_get_qty", string="Cantidad Disponible Complementarios Entrante", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    qty_in = fields.Float(compute="_get_qty", string="Cantidad Entrante", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    coheficiente = fields.Float(string="Coeficiente", digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default=1)
    product_id = fields.Many2one('product.product', string='Producto Complementario', required=True, domain="[('type','=','product')]")
    product_id1 = fields.Many2one('product.product', string='Producto Complementario')
    

class product_complementary_location(models.Model):
    _name = 'product.complementary.location'
    
    @api.one
    @api.depends('location_id', 'complementary_id')
    def _get_qty(self):
        if self.complementary_id and self.location_id:
            cxt = self._context.copy()
            cxt.update({'location': self.location_id.id})
            res = self.with_context(cxt).complementary_id.product_id._product_available()
            if res:            
                qty_available = res.values()[0].get('qty_available')
                outgoing_qty = res.values()[0].get('outgoing_qty')
                virtual_available = res.values()[0].get('virtual_available')
                incoming_qty = res.values()[0].get('incoming_qty')
                self.qty = qty_available
                self.qty_in = incoming_qty
            
    complementary_id = fields.Many2one('product.complementary', string='Parent')
    location_id = fields.Many2one('stock.location', 'Ubicacion', required=True, select=True, domain="[('usage','=','internal')]")
    qty = fields.Float(compute="_get_qty", string="Cantidad Disponible", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    qty_in = fields.Float(compute="_get_qty", string="Cantidad Entrante", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    
    

class product_substitutes(models.Model):
    _name = 'product.substitutes'
    
    @api.one
    @api.depends('location_ids', 'coheficiente', 'product_id')
    def _get_qty(self):
        if self.location_ids:
            cant = 0.0
            cant_in = 0.0
            for location in self.location_ids:
               cant +=  location.qty
               cant_in +=  location.qty_in
            self.qty_substitutes = cant
            self.qty = cant*self.coheficiente
            self.qty_substitutes_in = cant_in
            self.qty_in = cant_in*self.coheficiente
    
    location_ids = fields.One2many('product.substitutes.location', 'product_substitutes_id', string='Ubicaciones', required=True, select=True)
    qty_substitutes = fields.Float(compute="_get_qty", string="Cantidad Disponible Sustituto", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    qty = fields.Float(compute="_get_qty", string="Cantidad Disponible", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    qty_substitutes_in = fields.Float(compute="_get_qty", string="Cantidad Disponible Sustituto Entrante", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    qty_in = fields.Float(compute="_get_qty", string="Cantidad Entrante", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    coheficiente = fields.Float(string="Coeficiente", digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default=1)
    product_id = fields.Many2one('product.product', string='Producto Sustituto', required=True, domain="[('type','=','product')]")
    product_id_2 = fields.Many2one('product.product', string='Producto', required=True)

class product_substitutes_location(models.Model):
    _name = 'product.substitutes.location'
    
    @api.one
    @api.depends('location_id', 'product_substitutes_id')
    def _get_qty(self):
        if self.product_substitutes_id and self.location_id:
            cxt = self._context.copy()
            cxt.update({'location': self.location_id.id})
            res = self.with_context(cxt).product_substitutes_id.product_id._product_available()
            if res:            
                qty_available = res.values()[0].get('qty_available')
                outgoing_qty = res.values()[0].get('outgoing_qty')
                virtual_available = res.values()[0].get('virtual_available')
                incoming_qty = res.values()[0].get('incoming_qty')
                self.qty = qty_available
                self.qty_in = incoming_qty
            
    product_substitutes_id = fields.Many2one('product.substitutes', string='Ubicacion')
    location_id = fields.Many2one('stock.location', 'Ubicacion', required=True, select=True, domain="[('usage','=','internal')]")
    qty = fields.Float(compute="_get_qty", string="Cantidad Disponible", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
    qty_in = fields.Float(compute="_get_qty", string="Cantidad Entrante", digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True)
       
#