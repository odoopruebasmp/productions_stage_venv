# -*- coding: utf-8 -*-
# import openerp.netsvc
import openerp.netsvc
# from openerp.osv import osv, fields
from openerp.osv import osv, fields

class hr_leave_mass_approve(osv.osv_memory):
    _name = 'hr.leave.mass.approve'
    
    def confirm_mass_leave(self, cr, uid, ids, context=None):
        leaves_ids = context.get('active_ids', [])
        wf_service = openerp.netsvc.LocalService("workflow")
        for leave_id in leaves_ids:
            wf_service.trg_validate(uid, context['active_model'], leave_id, 'confirm', cr)
        return {'type': 'ir.actions.act_window_close'}

    def validate_mass_leave(self, cr, uid, ids, context=None):
        leaves_ids = context.get('active_ids', [])
        wf_service = openerp.netsvc.LocalService("workflow")
        for leave_id in leaves_ids:
            wf_service.trg_validate(uid, context['active_model'], leave_id, 'validate', cr)
        return {'type': 'ir.actions.act_window_close'}
        
    def cancel_mass_leave(self, cr, uid, ids, context=None):
        leaves_ids = context.get('active_ids', [])
        wf_service = openerp.netsvc.LocalService("workflow")
        for leave_id in leaves_ids:
            wf_service.trg_validate(uid, context['active_model'], leave_id, 'cancel', cr)
        return {'type': 'ir.actions.act_window_close'}
        

hr_leave_mass_approve()

class hr_extra_mass_compute(osv.osv_memory):
    _name = 'hr.extra.mass.compute'
    
    def compute_mass_extra_hours(self, cr, uid, ids, context=None):
        active_ids = context.get('active_ids', [])
        self.pool.get('hr.payroll.extrahours').compute_value(cr, uid, active_ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
