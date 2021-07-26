# -*- coding: utf-8 -*-
import openerp.netsvc
from openerp.osv import osv, fields
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from datetime import date, datetime, timedelta


class hr_payslip_mass_approve(osv.osv_memory):
    _name = 'hr.payslip.mass.approve'
    
    def approve_mass_leave(self, cr, uid, ids, context=None):
        payslip_ids = context.get('active_ids', [])
        self.pool.get('hr.payslip').close_slip(cr, uid, payslip_ids, context=None)
        return {'type': 'ir.actions.act_window_close'}

hr_payslip_mass_approve()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:



