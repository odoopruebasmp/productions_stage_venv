# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
import openerp.netsvc
from dateutil.rrule import rrule, DAILY
import time
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval
from openerp.addons.edi import EDIMixin
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp.report import report_sxw
from openerp.exceptions import Warning


class hr_employee(osv.osv):
    _inherit = "hr.employee"
    
    
    def _get_partner(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for empleado in self.browse(cr, uid, ids, context):
            res[empleado.id] = empleado.partner_id.id
        return res

    _columns = {
        'address_home_id': fields.function(_get_partner, type="many2one", string="Home Address", readonly=True),
    }

class res_company(osv.osv):
    _inherit = 'res.company'
    
    _columns = {
        'vencimiento_anticipo': fields.float('Dias vencimiento anticipo', help="Los dias sumados a la fecha fin de un anticipo para calcular la fecha de vencimiento", digits_compute=dp.get_precision('Account')),
        'giro_anticipo': fields.float('Dias pago anticipo', help="Los dias restados a la fecha inicio de un anticipo para calcular la fecha de giro", digits_compute=dp.get_precision('Account')),
    }
    
class res_partner(osv.osv):
    
    _inherit = 'res.partner'
    
    _columns = {
        'property_advance_account_receivable': fields.property(type='many2one',relation='account.account',string="Advance Account Receivable",),
        'property_advance_account_payable': fields.property(type='many2one',relation='account.account',string="Advance Account Payabl",),
    }
    
class hr_expense_expense(osv.osv):
    _inherit = 'hr.expense.expense'
    
    def _check_advance(self, cr, uid, ids, context=None):
        for lega in self.browse(cr, uid, ids, context):
            if (lega.type == 'anticipo' and lega.state not in ['draft','cancelled'] and lega.advance_id) and (lega.employee_id != lega.advance_id.employee_id or (lega.advance_id.partner_id != lega.employee_id.partner_id)):
                return False
        return True
        
    def _check_advance_state(self, cr, uid, ids, context=None):
        for lega in self.browse(cr, uid, ids, context):
            if lega.type == 'anticipo' and lega.state not in ['draft','cancelled'] and lega.advance_id.state not in ['to_pay','to_refund'] :
                return False
                
        return True
        
    def _currency_advance(self, cr, uid, ids, context=None):
        for lega in self.browse(cr, uid, ids, context):
            if lega.type == 'anticipo' and lega.advance_id and lega.currency_id != lega.advance_id.currency_id and lega.currency_id != lega.advance_id.company_id.currency_id:
                return False
        return True
        
    def _get_advance_difference(self, cr, uid, ids, name, args, context=None):
        res = {}
        for expense in self.browse(cr, uid, ids, context=context):
            if expense.advance_id and expense.state != 'done':
                res[expense.id] = expense.advance_id.remaining - expense.total_local
        return res
    
    _columns = {
        'advance_id': fields.many2one('hr.payroll.advance', 'Avance', readonly=True, domain=['|','|',('state','=','to_pay'),('state','=','expired'),('state','=','paid')], states={'draft': [('readonly', False)]}),
        'advance_difference': fields.function(_get_advance_difference, type="float", string="Diferencia con anticipo", digits_compute=dp.get_precision('Account'), readonly=True, store=True),
    }
    
    _constraints = [
        (_check_advance, '[Legalizacion] El empleado o tercero es diferente al empleado o tercero del avance', ['advance_id']),
        (_currency_advance, 'La moneda es diferente a la del anticipo o la local', ['advance_id']),
        (_check_advance_state, "[Legalizacion] Este anticipo ya no se encuentra en estado 'Por Legalizar'", ['advance_id']),
    ]
    
    def expense_regret(self, cr, uid, expense, context=None):
        res = True
        if expense.advance_id and expense.advance_id.account_move_line_refund_id and expense.advance_id.account_move_line_refund_id.reconcile_id:
            raise osv.except_osv(_('Error !'), _("Debe romper primero la conciliacion del reembolso"))
        else:
            res = super(hr_expense_expense, self).expense_regret(cr, uid, expense, context)
        return res

    def how_to_reconcile(self, cr, uid, expense, expense_move_line, move_lines, context=None):

        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        advance_obj = self.pool.get('hr.payroll.advance')

        move_id = expense_move_line.move_id
        period_id = move_id.period_id.id
        journal_id = expense.journal_id.id
        advance = expense.advance_id
        remaining = advance.remaining
        diff = expense.amount_total2 - remaining
        reconcile = move_line_obj.reconcile_partial(cr, uid, move_lines, writeoff_acc_id=False,
                                                    writeoff_period_id=period_id, writeoff_journal_id=journal_id)
        if diff > 0 and not advance.account_move_line_id.reconcile_id:
            if not advance.employee_id.partner_id.property_account_payable:
                raise osv.except_osv(_('Error !'), _('El Tercero del empleado no tiene cuenta de pago configurada'))
            date = expense.date
            name = advance.name + '[-R]'
            line2 = expense_move_line.id
            cr.execute("UPDATE account_move_line SET credit=%s WHERE id=%s" %
                       (expense_move_line.credit - diff, expense_move_line.id))

            line1 = move_line_obj.create(cr, uid, {
                'date_created': date,
                'partner_id': advance.partner_id.id,
                'name': name,
                'date': date,
                'credit': diff,
                'debit': 0,
                'account_id': advance.employee_id.partner_id.property_account_payable.id,
                'move_id': move_id.id,
            }, context=context)

            move_obj.post(cr, uid, [move_id.id])

            to_reconcile = [line2, advance.account_move_line_id.id]
            reconcile = move_line_obj.reconcile_partial(cr, uid, to_reconcile, writeoff_acc_id=False,
                                                        writeoff_period_id=period_id, writeoff_journal_id=journal_id)
            advance_obj.write(cr, uid, [advance.id],
                              {'move_refund_id': move_id.id, 'account_move_line_refund_id': line1})

        return reconcile

    def action_move_create(self, cr, uid, ids, context=None):
        res = super(hr_expense_expense, self).action_move_create(cr, uid, ids, context)
        for expense in self.browse(cr, uid, ids, context=context):
            if expense.advance_id and not expense.type == 'anticipo':
                raise osv.except_osv(_('Error !'), _(
                    "El documento no es de tipo anticipo pero tiene asociado uno. por favor desvinculelo."))
            if expense.advance_id:
                if not expense.advance_id:
                    # si se llega a este error es por que hubo una manipulacion inesperada en el sistema (cambios por base de datos o por hacks de python o javascript)
                    raise osv.except_osv(_('Error !'), _("Debe seleccionar un anticipo"))

                expense_move_line = False
                move_lines = [expense.advance_id.account_move_line_id.id]
                for move_line in expense.account_move_id.line_id:
                    if move_line.account_id == expense.advance_id.account_recivable_id:  # expense.employee_id.partner_id.property_account_receivable.id:
                        expense_move_line = move_line
                        move_lines += [move_line.id]

                if not expense_move_line:
                    raise osv.except_osv(_('Error !'), _(
                        "La cuenta utilizada en el anticipo no concuerda con la usada en la legalizacion"))
                self.how_to_reconcile(cr, uid, expense, expense_move_line, move_lines, context=context)
        return res

    
class hr_payslip_advance(osv.osv):
    _name = "hr.payslip.advance"
    _description = "Anticipo Empleado"
    
    def _check_amounts(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context):
            if advance.amount_discount < 0 or  advance.amount_discount > advance.amount_total:
                return False
        return True
    
    _columns = {
        'advance_id': fields.many2one('hr.payroll.advance', 'Anticipo', required=True, readonly=True, ondelete='cascade'),
        'payslip_id': fields.many2one('hr.payslip', 'Nomina', required=True, readonly=True, ondelete='cascade'),
        'amount_total': fields.float('Valor', digits_compute=dp.get_precision('Account'), required=True, readonly=True),
        'amount_discount': fields.float('Valor Descontado', digits_compute=dp.get_precision('Account'), required=True),
        'manual': fields.boolean('Manual'),
        # 'journal_id': fields.related('journal_id','payslip_id',type="many2one",relation="account.journal",string="Journal", readonly=True, store=True),
        'period_id': fields.related('payslip_id','payslip_period_id',type="many2one",relation="payslip.period", string="Periodo", readonly=True, store=True),
        'state': fields.related('payslip_id', 'state', type="char", string="Estado", readonly=True, store=True),
        'account_id': fields.many2one('account.account', 'Account', readonly=True),
    }
    
    _defaults = {
        'manual': False,
    }
    
    _constraints = [
        (_check_amounts, 'El valor a descontar no puede ser menor a 0 ni mayor al valor total', ['amount_discount']),
    ]


class hr_payroll_advance(osv.osv, EDIMixin):
    _name = "hr.payroll.advance"
    _description = "Anticipo Empleado"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _order = 'name desc'
    
    def _get_local_currency_total(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for prestamo in self.browse(cr, uid, ids, context):
            res[prestamo.id] = prestamo.amount*prestamo.tasa_cambio
        return res
    
    def _get_contract(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for prestamo in self.browse(cr, uid, ids, context):
            res[prestamo.id] = self.pool.get('hr.employee').get_contract(cr, SUPERUSER_ID, prestamo.employee_id, prestamo.request_date, context)
        return res
        
    def _employee_get(obj, cr, uid, context=None):
        if context is None:
            context = {}
        ids = obj.pool.get('hr.employee').search(cr, uid, [('user_id', '=', uid)], context=context)
        if ids:
            return ids[0]
        else:
            raise osv.except_osv(_('Error !'),_("Su usuario no esta vinculado a ningun empleado"))
        return False
        
    def _check_advances(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context):
            advance_ids = self.search(cr, uid, [('state', '<>', 'cancelled'),
                                                ('state', '<>', 'paid'),
                                                ('state', '<>', 'refused'),
                                                ('employee_id', '=', advance.employee_id.id)])
            if advance_ids and len(advance_ids) > 1:
                return False
        return True
        
    def _check_dates(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context):
            if advance.start_date > advance.end_date:
                return False
        return True
        
    def _no_amount(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context=context):
            if advance.amount == 0.00:
                return False
        return True
    
    def _expire_date(self, cr, uid, ids, name, args, context=None):  # TODO
        if context is None:
            context = {}
        res = {}
        for prestamo in self.browse(cr, uid, ids, context):
            end_date = datetime.strptime(prestamo.end_date, DEFAULT_SERVER_DATE_FORMAT).date()
            contract = self._get_contract(cr, uid, ids, name, args, context=context)[prestamo.id]
            contract = self.pool.get('hr.contract').browse(cr, uid, contract, context)
            expire_date = str(end_date + timedelta(days=contract.company_id.vencimiento_anticipo))
            res[prestamo.id] = expire_date
        return res
        
    def _amount_residual_value(self, cr, uid, advance, context=None):
        remaining = False
        if advance.move_egress_id:
            remaining = advance.account_move_line_id.amount_residual
            if remaining==0 and advance.account_move_line_refund_id:
                remaining -= advance.account_move_line_refund_id.amount_residual
                
                
        return remaining
        
    def _amount_residual(self, cr, uid, ids, name, args, context=None):
        result = {}
        wf_service = openerp.netsvc.LocalService("workflow")
        period_obj = self.pool.get('account.period')
        for advance in self.browse(cr, uid, ids, context=context):
            if advance.move_egress_id:
                
                remaining = self._amount_residual_value(cr, uid, advance, context)
                result[advance.id] = remaining
                
                #no usar el campo .residual en las funciones de workflow que desencadenan de estas signals, usar la funcion _amount_residual_value
                if remaining > 0 and advance.state in ['paid','to_refund','to_discount']:
                    wf_service.trg_validate(uid, 'hr.payroll.advance', advance.id, 'remaining_positive', cr)
                elif remaining == 0 and advance.state in ['to_pay','to_refund','to_discount']:
                    wf_service.trg_validate(uid, 'hr.payroll.advance', advance.id, 'remaining_cero', cr)
                elif remaining < 0 and advance.state != 'to_refund':
                    wf_service.trg_validate(uid, 'hr.payroll.advance', advance.id, 'remaining_negative', cr)
        
        return result
        
    def _get_advance_from_line(self, cr, uid, ids, context=None):
        move = {}
        for line in self.pool.get('account.move.line').browse(cr, uid, ids, context=context):
            if line.reconcile_partial_id:
                for line2 in line.reconcile_partial_id.line_partial_ids:
                    move[line2.move_id.id] = True
            if line.reconcile_id:
                for line2 in line.reconcile_id.line_id:
                    move[line2.move_id.id] = True
        advance_ids = []
        if move:
            advance_ids = self.pool.get('hr.payroll.advance').search(cr, uid, [('move_egress_id','in',move.keys())], context=context)
            advance_ids += self.pool.get('hr.payroll.advance').search(cr, uid, [('move_refund_id','in',move.keys())], context=context)
        return advance_ids

    def _get_advance_from_reconcile(self, cr, uid, ids, context=None):
        move = {}
        for r in self.pool.get('account.move.reconcile').browse(cr, uid, ids, context=context):
            for line in r.line_partial_ids:
                move[line.move_id.id] = True
            for line in r.line_id:
                move[line.move_id.id] = True

        advance_ids = []
        if move:
            advance_ids = self.pool.get('hr.payroll.advance').search(cr, uid, [('move_egress_id','in',move.keys())], context=context)
            advance_ids += self.pool.get('hr.payroll.advance').search(cr, uid, [('move_refund_id','in',move.keys())], context=context)
        return advance_ids
    
    def _check_currency(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context=context):
            if advance.tasa_cambio < 0 and advance.state != 'draft':
                return False
        return True
    
    _columns = {
        
        'move_name': fields.char('Nombre Comprobante', size=64, readonly=True),
        'expense_ids':fields.one2many('hr.expense.expense','advance_id','Legalizaciones', readonly=True, states={'to_pay': [('readonly', False)]}),
        'advance_payslip_ids':fields.one2many('hr.payslip.advance','advance_id','Nominas', readonly=True, ondelete='cascade'),
        'moneda_local': fields.related('company_id','currency_id',type="many2one",relation="res.currency",string="Moneda Local",readonly=True, store=True),
        'parent_id': fields.related('employee_id','parent_id',type="many2one",relation="hr.employee",string="Director", readonly=True ,store=True),
        'currency_id': fields.many2one('res.currency', 'Moneda', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'multicurrency': fields.boolean('Multimoneda'),
        'automaticly_expired': fields.boolean('Expiracion Automatica'),
        'total_local': fields.function(_get_local_currency_total, type="float", string="En Moneda Local", digits_compute=dp.get_precision('Account'), readonly=True, store=True),
        'ref': fields.char('Reference Payment'),         
        'remaining': fields.function(_amount_residual, digits_compute=dp.get_precision('Account'), string='Balance',
            store={
                'hr.payroll.advance': (lambda self, cr, uid, ids, c={}: ids, None,50),
                'account.move.line': (_get_advance_from_line, None, 50),
                'account.move.reconcile': (_get_advance_from_reconcile, None, 50),
            },
            help="Remaining amount due.", track_visibility='onchange'),
            
        # , groups='account.group_account_invoice'
            
        'tasa_cambio' : fields.float("Tasa Cambio", digits_compute=dp.get_precision('Exchange Precision'),required=True, readonly=True, states={'validated': [('readonly', False)]}),
        'name': fields.char('Codigo',size=64,readonly=True),
        'description': fields.text('Descripcion', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'amount': fields.float('Valor', digits_compute=dp.get_precision('Account'), required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'employee_id': fields.many2one('hr.employee', 'Empleado', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'account_recivable_id': fields.many2one('account.account', 'Cuenta Cobro', readonly=True),
        'account_payable_id': fields.many2one('account.account', 'Cuenta Pago', readonly=True),
        'contract_id': fields.function(_get_contract, type="many2one", relation='hr.contract', string="Contrato",
                                       store=True),
        'request_date': fields.date('Fecha solicitud', readonly=True, required=True, states={'draft': [('readonly', False),('required', True)]}),
        'approve_date': fields.date('Fecha de aprobacion', readonly=True, states={'waiting_financial_approval': [('readonly', False),('required', True)]}),
        'start_date': fields.date('Fecha de inicio', readonly=True, required=True, states={'draft': [('readonly', False),('required', True)]}),
        'end_date': fields.date('Fecha de fin', required=True, track_visibility='onchange'),
        'expire_date': fields.function(_expire_date, type="date", string="Fecha de vencimiento", readonly=True,
                                       store=True),
        'pay_date': fields.date('Fecha de Pago', readonly=True, states={'validated': [('readonly', False),('required', True)]}),
        'company_id': fields.related('contract_id','company_id',type="many2one",relation="res.company",string="Compania",readonly=True,store=True),
        'journal_bank_id': fields.many2one('account.journal', 'Diario Anticipo', readonly=True, states={'waiting_signature': [('readonly', False), ('required', True)]}, domain=[('type','in',['bank', 'cash']),('recaudo','=',False)]),
        'journal_advance_id': fields.many2one('account.journal', 'Diario Anticipo', readonly=True),
        'accounting_date': fields.date('Fecha Causacion', readonly=True, states={'waiting_signature': [('readonly', False),('required', True)]}),
        'move_validate_id': fields.many2one('account.move', 'Comprobante Validacion', readonly=True),
        'move_egress_id': fields.many2one('account.move', 'Comprobante Egreso', readonly=True),
        'move_refund_id': fields.many2one('account.move', 'Comprobante Para Reembolso', readonly=True),
        'partner_id': fields.many2one('res.partner', 'Tercero', readonly=True),
        'massive': fields.boolean('Masivo'),
        'analytic_account_id': fields.many2one('account.analytic.account', 'Centro de Costo', required=True, readonly=True, states={'draft': [('readonly', False)],'waiting_approval': [('readonly', False)],'waiting_financial_approval': [('readonly', False)]}),
        'payslip_ids': fields.many2many('hr.payslip', 'payslip_advance_rel', 'payslip_id', 'advance_id', 'Nominas'),
        'account_move_line_id': fields.many2one('account.move.line', 'Linea a reconciliar', readonly=True),
        'account_move_line_refund_id': fields.many2one('account.move.line', 'Linea a reconciliar reembolso', readonly=True),
        'reconcile_id': fields.related('account_move_line_id','reconcile_id',type="many2one",relation="account.move.reconcile",string="Reconciliacion",readonly=True,store=True),
        'reconcile_refund_id': fields.related('account_move_line_refund_id','reconcile_id',type="many2one",relation="account.move.reconcile",string="Reconciliacion Reembolso",readonly=True,store=True),
        'reconcile_partial_id': fields.related('account_move_line_id','reconcile_partial_id',type="many2one",relation="account.move.reconcile",string="Reconciliacion Parcial",readonly=True,store=True),
        'reconcile_partial_refund_id': fields.related('account_move_line_refund_id','reconcile_partial_id',type="many2one",relation="account.move.reconcile",string="Reconciliacion Parcial Reembolso",readonly=True,store=True),
        'state':fields.selection([('draft', 'Borrador'),
                                  ('waiting_approval', 'Pendiente Aprobacion'), 
                                  ('refused', 'Rechazado'),
                                  ('waiting_financial_approval', 'Pendiente Aprobacion Financiera'), 
                                  ('waiting_signature', 'Proceso Firmas'), 
                                  ('validated', 'Aprobado'), 
                                  ('cancelled', 'Cancelado'),
                                  ('to_pay', 'Por Legalizar'), 
                                  ('paid', 'Realizado'), 
                                  ('expired', 'Vencido'), 
                                  ('to_discount', 'Para Descontar Nomina'), 
                                  ('to_refund', 'Por Reembolsar'),
                                  ], 'Estado', select=True, readonly=True),# track_visibility='onchange'),
        'payslip_id': fields.many2one('hr.payslip', 'Nomina'),
    }
    
    _defaults = {
        'request_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state': 'draft',
        'employee_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).employee_id and self.pool.get('res.users').browse(cr, uid, uid, c).employee_id.id or False,
        'currency_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'tasa_cambio': 1,
    }
    
    _track = {
        'state': {
            'hr_payroll_extended.mt_advance_new': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'draft',
            'hr_payroll_extended.mt_advance_waiting_approval': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'waiting_approval',
            'hr_payroll_extended.mt_advance_waiting_financial_approval': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'waiting_financial_approval',
            'hr_payroll_extended.mt_advance_validated': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'validated',
            'hr_payroll_extended.mt_to_pay_validated': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'to_pay',
            'hr_payroll_extended.mt_advance_refused': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'refused',
            'hr_payroll_extended.mt_advance_paid': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'paid',
            'hr_payroll_extended.mt_advance_expired': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'expired',
            'hr_payroll_extended.mt_advance_to_discount': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'to_discount',
            'hr_payroll_extended.mt_advance_to_discount': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'to_refund',
            'hr_payroll_extended.mt_waiting_signature_discount': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'waiting_signature',
            'hr_payroll_extended.mt_waiting_signature_discount': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelled',
        },
    }
    
    _constraints = [
        # (_check_advances, 'El empleado tiene ya un anticipo en proceso', ['employee_id']),
        (_no_amount, 'No se puede ingresar un anticipo con valor cero!', ['amount']),
        (_check_dates, 'La fecha de inicio es mayor a la de fin!', ['start_date','end_date']),
        (_check_currency, 'No existe una tasa con la cual se pueda evaluar el anticipo', ['tasa_cambio']),
    ]
    
    def cancel_refund_move(self, cr, uid, advance, context=None):
        moveobj = self.pool.get('account.move')
        reconcile_pool = self.pool.get('account.move.reconcile')
        
        if advance.move_refund_id:
            
            #si la reconciliacion se cancelo en el proceso de cancelar la legalizacion dara error al tratar de leerla ya que este proceso fue echo en el mismo hilo
            try:
                if not advance.move_refund_id.reconcile_id:
                    moveobj.button_cancel(cr, uid, [advance.move_refund_id.id], context=context)
                    moveobj.unlink(cr, uid, [advance.move_refund_id.id], context=context)
            except:
                pass
            
        return True
    
    def test_expiration(self, cr, uid, ids, *args):
        # just for 1 record
        context = {}
        advance =  self.browse(cr, uid, ids, context)[0]
        fecha_hoy = datetime.now()
        fecha_hoy_str = fecha_hoy.strftime(DEFAULT_SERVER_DATE_FORMAT)
        if advance.expire_date < fecha_hoy_str:
            return True
        return False
    
    def name_get(self, cr, user, ids, context=None):
        parse = report_sxw.rml_parse(cr, user, 'advance_parser', context=context)
        
        if context is None:
            context = {}
        if type(ids) == int:
            ids = [ids]
        if not len(ids):
            return []
        def _name_get(d):
            name = d.get('name','')
            total_local = d.get('total_local',False)
            if total_local:
                name = '%s [%s]' % (name,total_local)
            return (d['id'], name)

        result = []
        for advance in self.browse(cr, user, ids, context=context):
        
            total_local = parse.formatLang(advance.total_local, monetary=True, currency_obj=advance.company_id.currency_id)
            mydict = {
                      'id': advance.id,
                      'name': advance.name,
                      'total_local': total_local,
                      }
            result.append(_name_get(mydict))
        return result
    
    def expire_cronjob(self, cr, uid, expired_ids, context=None):
        # no actualizan el workflow, ninguna de estas funciones
        # wf_service = openerp.netsvc.LocalService("workflow")
        # for id in expired_ids:
            # wf_service.trg_trigger(uid, 'account.move.line', id, cr)
            # wf_service.trg_write(uid, 'account.move.line', id, cr)
        
        #workaround
        self.write(cr, uid, expired_ids , {'automaticly_expired':False})   
        self.write(cr, uid, expired_ids , {'automaticly_expired':True})
        
        return True
    
    def anticipo_vencido_cron(self, cr, uid, dias_aviso=5, mensaje=False, subject=False, context=None):
        wf_service = openerp.netsvc.LocalService("workflow")
        fecha_hoy = datetime.now()
        fecha_hoy_str = fecha_hoy.strftime(DEFAULT_SERVER_DATE_FORMAT)
        fecha_now_str = fecha_hoy.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        fecha_aviso = fecha_hoy+relativedelta(days=dias_aviso)
        fecha_aviso_str = fecha_aviso.strftime(DEFAULT_SERVER_DATE_FORMAT)
        if not subject:
            subject = 'Anticipo Vencido'
        
        expired_ids = self.search(cr, uid, ['|',('state', '=', 'expired'),('state', '=', 'to_pay'), ('expire_date', '<', fecha_hoy_str)], context=context)
        
        self.expire_cronjob(cr, uid, expired_ids, context=context)
        
        
        advance_ids = self.search(cr, uid, [('state', '=', 'to_pay'), ('expire_date', '=', fecha_aviso_str)], context=context)
        
        if advance_ids:
            message_obj= self.pool.get('mail.message')
            
            super_user = self.pool.get('res.users').browse(cr, uid, SUPERUSER_ID, context).partner_id.id#opcional
            
            for advance in self.browse(cr, uid, advance_ids, context):
                partner = False
                if advance.employee_id.user_id:
                    partner = advance.employee_id.user_id.partner_id.id
                if not mensaje:
                    mensaje = 'Este anticipo se vencera en '+str(dias_aviso)+' dias ('+advance.expire_date+') y sera descontado en la proxima nomina del empleado '+advance.employee_id.name
                
                parent = False
                for message in advance.message_ids:
                    if not message.parent_id:
                        if not parent:
                            parent = message.id
                        elif parent and parent > message.id:
                            parent = message.id
                
                vals = {
                    'author_id': advance.company_id.partner_id.id,
                    'model' : 'hr.payroll.advance',
                    'res_id' : advance.id,
                    'date' : fecha_now_str,
                    'subject' : subject,
                    'body' : mensaje,
                    'type' : 'email',
                    # 'subtype_id' : subtype,
                    'parent_id' : parent,
                    'partner_ids': [(6, 0,[x.id for x in advance.message_follower_ids])],
                    'notified_partner_ids': [(6, 0,[x.id for x in advance.message_follower_ids])],
                }
                messaje_id = message_obj.create(cr, uid, vals, context)
                
        return True
    
    def onchange_currency_id(self, cr, uid, ids, currency_id, company_id, date, state, context=None):
        val = {}
        warning = {}
        if currency_id:
        
            if not company_id:
                company  = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            else:
                company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
            
            if company.currency_id.id != currency_id:
                
                date = time.strftime('%Y-%m-%d')
                if state == 'validated':
                    date = date or time.strftime('%Y-%m-%d')
                
                currency_obj = self.pool.get('res.currency.rate')
                cr.execute("select id from res_currency_rate where currency_id = {c} and "
                           "name::varchar like '{d}%'".format(c=currency_id, d=date))
                currency_date_id = cr.fetchall()
                if currency_date_id:
                    currency_date_id = currency_date_id[0][0]
                # currency_date_id = currency_obj.search(cr, uid, [('name','=',date),('currency_id','=',currency_id)])
                if not currency_date_id:
                    warning = {
                        'title': _('Advertencia!'),
                        'message' : _("No existe la tasa de cambio para la fecha '%s' ") % (date,)
                    }
                    rate = -1
                else:
                    rate = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv
                multi = True
            else:
                rate = 1
                multi = False
                
            val['currency_id'] = currency_id
            val['tasa_cambio'] = rate
            val['multicurrency'] = multi
        return {'value': val,'warning': warning}
        
    def verificacionDirector(self, cr, uid, ids, context=None):
        director = False
        for advance in self.browse(cr, uid, ids, context=context):
            if not advance.employee_id.parent_id:
                raise osv.except_osv(_('Error de Configuracion'), _('El Empleado no tiene configurado un Director'))
            if not advance.employee_id.parent_id.user_id:
                raise osv.except_osv(_('Error de Configuracion'), _('El Director no tiene un Usuario asignado'))
            if advance.employee_id.parent_id.user_id.id != uid:
                raise osv.except_osv(_('Error de Permisos'), _('Usted no es el director del empleado'))
            else:
                director = True
        return director

    def cancel_seats(self, cr, uid, ids, context=None):
        for antic in self.browse(cr, uid, ids, context):
            mi = antic.move_egress_id.id
            self.pool.get('account.move').button_cancel(cr, uid, [mi], context)
            antic.move_egress_id.unlink()
        return True
        
    def wf_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'draft'})
        return True
    
    def wf_waiting_approval(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context):
            if advance.state != 'draft':
                raise Warning("No se puede enviar a aprobar un anticipo que no esté en Borrador")
        self.write(cr, uid, ids , {'state': 'waiting_approval'})
        return True
    
    def wf_refused(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state': 'refused'})
        return True
    
    def wf_waiting_financial_approval(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state': 'waiting_financial_approval'})
        return True
    
    def wf_waiting_signature(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'waiting_signature'})
        return True
      
    def wf_validated(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'validated'})
        return True
    
    def wf_cancelled(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'cancelled'})
        return True
    
    def wf_to_pay(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        for advance in self.browse(cr, uid, ids, context):
            # if advance.state not in ['draft']:
            #     raise Warning("No se puede enviar a aprobar un anticipo que no esté en por legalizar")
            self.cancel_refund_move(cr, uid, advance, context)
            if not advance.move_egress_id:
                date = advance.accounting_date and advance.accounting_date or advance.pay_date
                period_ids = period_obj.find(cr, uid, date)
                period_id = period_ids and period_ids[0] or False
                if not period_id:
                    raise osv.except_osv(_('Error !'), _('No hay un periodo definido para esta fecha'))
                if not advance.employee_id.partner_id:
                    raise osv.except_osv(_('Error !'), _('El Tercero del empleado no esta asignado'))
                if not advance.employee_id.partner_id.property_account_payable:
                    raise osv.except_osv(_('Error !'), _('El Tercero del empleado no tiene cuenta de pago configurada'))
                if not advance.employee_id.partner_id.property_account_receivable:
                    raise osv.except_osv(_('Error !'), _('El Tercero del empleado no tiene cuenta de cobro configurada'))
                
                moneda = (advance.currency_id != advance.moneda_local) and advance.currency_id or False
                cantidad_moneda = moneda and advance.amount or False
                amount = moneda and advance.amount*advance.tasa_cambio or advance.amount

                # ID cuenta Debito
                account_recivable_id = advance.employee_id.partner_id.property_account_receivable.id
                # Codigo cuenta Debito
                account_recivable_code = advance.employee_id.partner_id.property_account_receivable.code
                # ID cuenta Credito
                account_payable_id = advance.employee_id.partner_id.property_account_payable.id
                # Codigo cuenta Credito
                account_payable_code = advance.employee_id.partner_id.property_account_payable.code

                partner_id = advance.employee_id.partner_id.id

                vals = {'partner_id': partner_id,
                        'journal_id': advance.journal_bank_id.id,
                        'date': date,
                        'ref': advance.name,
                        'period_id': period_id,
                        }
                if advance.move_name:
                    vals['name'] = advance.move_name

                cta_analitica_credito = False
                num_cuentas = ['4', '5', '6', '7']

                # Si el primer numero del codigo de la cta esta en num_cuentas, le asiganara la cuenta analitica
                if account_payable_code[0:1] in num_cuentas:
                    cta_analitica_credito = advance.analytic_account_id.id

                move_id = move_obj.create(cr, uid, vals, context)
                vals = {'partner_id': partner_id,
                        'currency_id': moneda and moneda.id or False,
                        'amount_currency': cantidad_moneda,
                        'journal_id': advance.journal_bank_id.id,
                        'date': date,
                        'name': advance.name,
                        'debit': amount,
                        'credit': 0,
                        'account_id': account_recivable_id,
                        'analytic_account_id': cta_analitica_credito,  # Asignacion de cuenta analitica
                        'period_id': period_id,
                        'move_id': move_id,
                        }

                cta_analitica_debito = False

                # Si el primer numero del codigo de la cta esta en num_cuentas, le asiganara la cuenta analitica
                if account_recivable_code[0:1] in num_cuentas:
                    cta_analitica_debito = advance.analytic_account_id.id

                move_line_id1 = move_line_obj.create(cr, uid, vals, context)
                vals = {'partner_id': partner_id,
                        'currency_id': moneda and moneda.id or False,
                        'amount_currency': cantidad_moneda * -1,
                        'journal_id': advance.journal_bank_id.id,
                        'date': date,
                        'name': advance.name,
                        'credit': amount,
                        'debit': 0,
                        'account_id': advance.journal_bank_id.default_credit_account_id.id,
                        'analytic_account_id': cta_analitica_debito,  # Asignacion de cuenta analitica
                        'period_id': period_id,
                        'move_id': move_id,
                        }

                move_line_id2 = move_line_obj.create(cr, uid, vals, context)
                new_move_name = move_obj.browse(cr, uid, move_id, context=context).name
                self.write(cr, uid, [advance.id] , {'move_name': new_move_name,'partner_id': partner_id, 'move_egress_id': move_id,'account_recivable_id': account_recivable_id,'account_payable_id': account_payable_id,'account_move_line_id': move_line_id1})
                
        self.write(cr, uid, ids , {'state':'to_pay'})
        return True
        
    def wf_paid(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'paid'})
        return True
        
    def wf_expired(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'expired'})
        return True
    
    def wf_to_discount(self, cr, uid, ids, context=None):
        # for advance in self.browse(cr, uid, ids, context):
        #     if advance.state not in ['to_pay']:
        #         raise Warning("No se puede enviar a aprobar un anticipo que no esté en por legalizar")
        self.write(cr, uid, ids, {'state': 'to_discount'})
        return True
    
    def wf_to_refund(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        expense_obj = self.pool.get('hr.expense.expense')
        
        for advance in self.browse(cr, uid, ids, context):
            
            if not advance.account_move_line_id.reconcile_id:
                
                journal_id = expense_obj.get_journal_expenses(cr, uid, advance.company_id, advance.currency_id, context=context)
                # remaining =  advance.remaining 
                remaining = self._amount_residual_value(cr, uid, advance, context)*-1
                
                #fecha correcta?
                date = False
                for expense in advance.expense_ids:
                    if not date or expense.date > date:
                        date = expense.date
                period_ids = period_obj.find(cr, uid, date)
                period_id = period_ids and period_ids[0] or False
                if not period_id:
                        raise osv.except_osv(_('Warning !'), _('No hay un periodo definido para esta fecha'))
                
                name = advance.name+'[-R]'
                
                vals = { 'partner_id': advance.partner_id.id,
                         'journal_id': journal_id,
                         'date': date,
                         'ref': name,
                         'period_id': period_id,
                        }
                move_id = move_obj.create(cr, uid, vals, context)                
                line1 = move_line_obj.create(cr, uid,{
                        'date_created': date,
                        'partner_id': advance.partner_id.id,
                        'name': name,
                        'date': date,
                        'credit': remaining,
                        'debit': 0,
                        'account_id': advance.account_payable_id.id,
                        'move_id' : move_id,
                        'analytic_account_id': advance.analytic_account_id and advance.analytic_account_id.id or False,
                    }, context=context)
                line2 = move_line_obj.create(cr, uid,{
                        'date_created': date,
                        'partner_id': advance.partner_id.id,
                        'name': name,
                        'date': date,
                        'credit': 0,
                        'debit': remaining,
                        'account_id': advance.account_recivable_id.id,
                        'move_id' : move_id,
                        'analytic_account_id': advance.analytic_account_id and advance.analytic_account_id.id or False,
                    }, context=context)
                move_obj.post(cr, uid, [move_id])
                to_reconcile = [line2, advance.account_move_line_id.id]
                
                reconcile = move_line_obj.reconcile_partial(cr, uid, to_reconcile, writeoff_acc_id=False, writeoff_period_id=period_id, writeoff_journal_id=journal_id)
                self.write(cr, uid, [advance.id] , {'move_refund_id': move_id,'account_move_line_refund_id': line1})
                
            self.write(cr, uid, [advance.id] , {'state': 'to_refund'})
                
        return True
        
    def write(self, cr, uid, ids, vals, context=None):
        for advance in self.browse(cr, uid, ids, context):
            #asigna la fecha de pago
            if advance.state == 'draft':
                start_date = datetime.strptime(advance.start_date, DEFAULT_SERVER_DATE_FORMAT).date()
                contract = self._get_contract(cr, uid, ids, vals, vals, context=context)[advance.id]
                contract = self.pool.get('hr.contract').browse(cr, uid, contract, context)
                pay_date = str(start_date - timedelta(days=contract.company_id.giro_anticipo))
                request_date = vals.get('request_date',False) or advance.request_date
                if pay_date < request_date:
                    pay_date = request_date
                vals.update({'pay_date': pay_date})
            
            #verificacion para la tasa de cambio
            if vals.get('currency_id',False) and not vals.get('tasa_cambio',False):
                company = advance.company_id
                currency_id = vals.get('currency_id',False)
                rate = 1
                if company.currency_id.id != currency_id:
                    date = time.strftime('%Y-%m-%d')
                    if advance.state == 'validated':
                        date = advance.pay_date or time.strftime('%Y-%m-%d')
                        
                    currency_obj = self.pool.get('res.currency.rate')
                    currency_date_id = currency_obj.search(cr, uid, [('name','=',date),('currency_id','=',currency_id)])
                    if not currency_date_id:
                        rate = -1
                    else:
                        rate = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv
                
                vals.update({'tasa_cambio': rate})
        
               
        #agrega los followers por defecto
        if 'employee_id' in vals:
            for req in self.browse(cr, uid, ids, context=context):
                empleado = self.pool.get('hr.employee').browse(cr, uid, vals.get('employee_id'), context=context)
                if empleado.partner_id not in req.message_follower_ids:
                    message_follower_ids = []
                    message_follower_ids += req.message_follower_ids
                    message_follower_ids.append(empleado.partner_id)
                    vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
                    if empleado.parent_id.partner_id not in req.message_follower_ids:
                        message_follower_ids += req.message_follower_ids
                        message_follower_ids.append(empleado.partner_id)
                        vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
        
        #llama al metodo padre
        result = super(hr_payroll_advance, self).write(cr, uid, ids, vals, context=context)
        return result

    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'journal_advance_id': False,
            'journal_bank_id': False,
            'pay_date': False,
            'accounting_date': False,
            'account_recivable_id': False,
            'move_validate_id': False,
            'move_egress_id': False,
            'ref': False,
            'approve_date': False,
            'expire_date': False,
            'reconcile_id': False,
            'move_name': False
            })
        return super(hr_payroll_advance, self).copy(cr, uid, id, default, context=context)


    
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        
        vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'payroll.advance.number') or '/'
        
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        currency_id = vals.get('currency_id')
        rate = 1
        if company.currency_id.id != currency_id:
            date = time.strftime('%Y-%m-%d')
            currency_obj = self.pool.get('res.currency.rate')
            currency_date_id = currency_obj.search(cr, uid, [('name','=',date),('currency_id','=',currency_id)])
            if not currency_date_id:
                rate = -1
            else:
                rate = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv
        vals.update({'tasa_cambio': rate})
        
        result = super(hr_payroll_advance, self).create(cr, uid, vals, context=context)
        
        #agrega al empleado como follower
        if 'employee_id' in vals:
            for req in self.browse(cr, uid, [result], context=context):
                empleado = self.pool.get('hr.employee').browse(cr, uid, vals.get('employee_id'), context=context)
                if empleado.partner_id not in req.message_follower_ids:
                    message_follower_ids = []
                    message_follower_ids += req.message_follower_ids
                    message_follower_ids.append(empleado.partner_id)
                    vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
                    if empleado.parent_id and empleado.parent_id.partner_id not in req.message_follower_ids:
                        message_follower_ids += req.message_follower_ids
                        message_follower_ids.append(empleado.partner_id)
                        vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
                self.write(cr, uid, result, vals, context=context)   
        
               
        return result
        
    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        advances = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for t in advances:
            if t['state'] not in ('draft'):
                raise openerp.exceptions.Warning(_('No puede borrar un avance que no este en estado borrador'))
            else:
                unlink_ids.append(t['id'])
        osv.osv.unlink(self, cr, uid, unlink_ids, context=context)
        return True
    
    
