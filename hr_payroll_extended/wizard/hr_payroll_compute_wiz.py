# -*- coding: utf-8 -*-

# from openerp.osv import osv
from openerp.osv import osv

class hr_payroll_compute(osv.osv_memory):
    _name = 'hr.payroll.compute'
    
    def compute_sheet(self, cr, uid, ids, context=None):
        if context is None:
            context={}
        payroll_obj = self.pool.get('hr.payslip')
        worked_days_obj = self.pool.get('hr.payslip.worked_days')
        payroll_recs = payroll_obj.browse(cr, uid, context.get('active_ids', []), context=context)
        payroll_ids = [payroll.id for payroll in payroll_recs if payroll.state == 'draft']
        for payslip in payroll_recs:
            worked_days_line_ids = payroll_obj.get_worked_day_lines(cr, uid, payslip, context=context)
            worked_days_obj.unlink(cr, uid, [line.id for line in payslip.worked_days_line_ids], context=None)
            payroll_obj.write(cr, uid, payslip.id , {'worked_days_line_ids':[(0, 0, x) for x in worked_days_line_ids]})
            payroll_obj.compute_sheet2(cr, uid, [payslip.id], context=context)
        return {'type': 'ir.actions.act_window_close'}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
