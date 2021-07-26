# -*- coding: utf-8 -*-
# import openerp.netsvc
import openerp.netsvc
# from openerp.osv import osv, fields
from openerp.osv import osv, fields

class hr_payslip_mass_notification(osv.osv_memory):
    
    _name = 'hr.payslip.mass.notification'
    
    def notification_mass_leave(self, cr, uid, ids, context=None):
        payslip_ids = context.get('active_ids', [])
        for pay_slip_id in payslip_ids:
            self.pool.get('hr.payslip').action_notification_mass_send(cr, uid, [pay_slip_id], context=None)
        return {'type': 'ir.actions.act_window_close'}

hr_payslip_mass_notification()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:



