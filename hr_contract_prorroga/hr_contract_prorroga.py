#-*- coding:utf-8 -*-

import time
from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from openerp import netsvc
from openerp.osv import fields, osv
from openerp import tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare

class hr_contract(osv.osv):
    _inherit = "hr.contract"
    def _periodo_prueba(self, cr, uid, ids, field_name, arg, context=None):
	    res = {}
	    for i in self.browse(cr, uid, ids, context=context):
	      res[i.id] = {
		'trial_date_start':False,
		'trial_date_end':False,
	    }
	      start_dt = datetime.strptime(i.date_start, DEFAULT_SERVER_DATE_FORMAT).date()
	      date = start_dt - relativedelta(days=1) + relativedelta(months=2)
	      date_date = date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
	      res[i.id]['trial_date_start'] = i.date_start
	      res[i.id]['trial_date_end'] = date_date
	    return res

    def onchange_type(self, cr, uid, ids, type_id, context=None):
        res = {}
        if type_id:
	    type = self.pool.get('hr.contract.type').browse(cr, uid, type_id, context=context)
            res={'value':{'type_fijo': type.type_fijo}}
        return res
    
    _columns = {
	    'proroga_1_date': fields.date("Proroga 1 Date"),
	    'proroga_2_date': fields.date("Proroga 2 Date"),
	    'proroga_3_date': fields.date("Proroga 3 Date"),
	    'trial_date_start': fields.function(_periodo_prueba, method=True, store=True, type='date', string='Inicio Periodo de Prueba',
					      multi='Periodo_de_Prueba'),
	    'trial_date_end': fields.function(_periodo_prueba, method=True, store=True, type='date', string='Fin Periodo de Prueba',
					      multi='Periodo_de_Prueba'),
	    'type_fijo': fields.boolean("Tipo Fijo"),
    }

hr_contract()

class hr_contract_type(osv.osv):

    _inherit = "hr.contract.type"
    _columns = {
	'type_fijo': fields.boolean("Tipo Fijo"),
    }

hr_contract_type()

