# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
import openerp.netsvc
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil import relativedelta, parser
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval
from openerp.addons.edi import EDIMixin
from calendar import monthrange
from openerp import models, api, _, fields as fields2

class hr_contract(models.Model):
    _inherit = "hr.contract"

    distancia_trabajo=fields2.Selection([('menos','Menos de un (1) kilometro'),('ruta','Beneficiario de ruta')], string='Distancia al Trabajo')
    beneficio_dependiente=fields2.Boolean('Beneficio dependientes')

#