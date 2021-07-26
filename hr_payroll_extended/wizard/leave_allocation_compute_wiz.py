# -*- coding: utf-8 -*-

# from openerp.osv import osv,fields
from openerp.osv import osv,fields
# from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
# from openerp.tools.translate import _
from openerp.tools.translate import _
# import openerp.netsvc
import openerp.netsvc

from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil import relativedelta, parser
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval

class leave_allocation_compute(osv.osv_memory):
    _name = 'leave.allocation.compute'
    
    _columns = {
        'date': fields.date('Fecha Hasta'), #FR
        'date_from': fields.date('Fecha Desde'), #FR
        
    }
    _defaults = {
        'date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT), #FR
    }
    
    def compute_sheet(self, cr, uid, ids, context=None):
        if context is None:
            context={}
        leave_obj = self.pool.get('hr.holidays.allocation.rule')
        for leave_allocation_compute_obj in self.browse(cr, uid, ids, context=context):
            
            date = datetime.strptime(leave_allocation_compute_obj.date, DEFAULT_SERVER_DATE_FORMAT)
            if leave_allocation_compute_obj.date_from:
                date_from = datetime.strptime(leave_allocation_compute_obj.date_from, DEFAULT_SERVER_DATE_FORMAT)
                def daterange(date_from,date):
                    for n in range(int ((date - date_from).days)):
                        yield date_from + timedelta(n)
                for single_date in daterange(date_from, date):
                    leave_obj.compute_allocation_leave(cr, uid, single_date, context=context)
            else:
                leave_obj.compute_allocation_leave(cr, uid, date, context=context)

            
        return {'type': 'ir.actions.act_window_close'}

leave_allocation_compute()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: