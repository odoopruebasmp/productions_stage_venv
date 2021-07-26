# -*- coding: utf-8 -*-
from openerp import models, fields, api
from openerp.addons import decimal_precision as dp
from openerp.exceptions import Warning
from datetime import datetime, date
from datetime import timedelta
from lxml import etree
import time
import re
import os



class ProductTemplate(models.Model):
	_inherit = "product.template"

	#inherit
	prod_weight = fields.Float(string='Peso (g)',digits=(8,3))
	emp_weight = fields.Float(string='Peso (g)',digits=(8,3))

	innerbox_large = fields.Float(string='Largo cm',digits=(8,2))
	innerbox_width = fields.Float(string='Ancho cm',digits=(8,2))
	innerbox_high = fields.Float(string='Alto cm',digits=(8,2))
	innerbox_weight = fields.Float(string='Peso (g)',digits=(8,3))
	innerbox_qty = fields.Float(string='Cant contenida',digits=(8,2))
	masterbox_large = fields.Float(string='Largo cm',digits=(8,2))
	masterbox_width = fields.Float(string='Ancho cm',digits=(8,2))
	masterbox_high = fields.Float(string='Alto cm',digits=(8,2))
	masterbox_weight = fields.Float(string='Peso (g)',digits=(8,3))
	masterbox_qty = fields.Float(string='Cant contenida',digits=(8,2))


class ProductProduct(models.Model):
	_inherit = "product.product"

	#inherit
	prod_weight = fields.Float(string='Peso (g)',digits=(8,3))
	emp_weight = fields.Float(string='Peso (g)',digits=(8,3))

	innerbox_large = fields.Float(string='Largo cm',digits=(8,2))
	innerbox_width = fields.Float(string='Ancho cm',digits=(8,2))
	innerbox_high = fields.Float(string='Alto cm',digits=(8,2))
	innerbox_weight = fields.Float(string='Peso (g)',digits=(8,3))
	innerbox_qty = fields.Float(string='Cant contenida',digits=(8,2))
	masterbox_large = fields.Float(string='Largo cm',digits=(8,2))
	masterbox_width = fields.Float(string='Ancho cm',digits=(8,2))
	masterbox_high = fields.Float(string='Alto cm',digits=(8,2))
	masterbox_weight = fields.Float(string='Peso (g)',digits=(8,3))
	masterbox_qty = fields.Float(string='Cant contenida',digits=(8,2))
