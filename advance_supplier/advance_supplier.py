# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
from openerp import netsvc
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

class account_payment_term(osv.Model):
    _inherit = 'account.payment.term'
    
    def compute_advance(self, cr, uid, id, value, date_ref=False, context=None):
        if not date_ref:
            date_ref = datetime.now().strftime('%Y-%m-%d')
        pt = self.browse(cr, uid, id, context=context)
        amount = value
        result = []
        obj_precision = self.pool.get('decimal.precision')
        prec = obj_precision.precision_get(cr, uid, 'Account')
        for line in pt.line_ids:
            if not line.advance:
                continue
            if line.value == 'fixed':
                amt = round(line.value_amount, prec)
            elif line.value == 'procent':
                amt = round(value * line.value_amount, prec)
            elif line.value == 'balance':
                amt = round(amount, prec)
            if amt:
                next_date = (datetime.strptime(date_ref, DEFAULT_SERVER_DATETIME_FORMAT) + relativedelta(days=line.days))
                if line.days2 < 0:
                    next_first_date = next_date + relativedelta(day=1,months=1) #Getting 1st of next month
                    next_date = next_first_date + relativedelta(days=line.days2)
                if line.days2 > 0:
                    next_date += relativedelta(day=line.days2, months=1)
                result.append( (next_date.strftime('%Y-%m-%d'), amt) )
                amount -= amt

        amount = reduce(lambda x,y: x+y[1], result, 0.0)
        return result

class account_payment_term_line(osv.Model):
    _inherit = 'account.payment.term.line'
    
    _columns = {
        'advance':fields.boolean('Anticipo'),
    }

class purchase_order(osv.Model):
    _inherit = 'purchase.order'
    
    def wkf_confirm_order(self, cr, uid, ids, context=None):
        term_pool = self.pool.get('account.payment.term')
        advance_pool = self.pool.get('purchase.advance.supplier')
        wf_service = openerp.netsvc.LocalService("workflow")
        super(purchase_order, self).wkf_confirm_order(cr, uid, ids, context=context)
        for po in self.browse(cr, uid, ids, context=context):
            if po.payment_term_id:
                result = term_pool.compute_advance(cr, uid, po.payment_term_id.id, po.amount_total, date_ref=po.date_order, context=context)
                if result:
                    for line in result:
                        data = {
                            'partner_id': po.partner_id.id,
                            'user_id': uid,
                            'currency_id': po.pricelist_id.currency_id.id,
                            'company_id': po.company_id.id,
                            'amount': line[1],
                            'planned_date': line[0],
                            'description': 'anticipo generado automaticamente por orden de compra '+po.name,
                            'purchase_order_id': po.id,
                            'request_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                            'multicurrency': po.multi_currency,
                            'tasa_cambio': po.rate_pactada,
                        }
                        ad_id = advance_pool.create(cr, uid, data, context=context)
                        advance_pool.write(cr, uid, [ad_id],{'tasa_cambio':po.rate_pactada}, context=context)
                        wf_service.trg_validate(uid, 'purchase.advance.supplier', ad_id, 'draft_send_for_approval', cr)
                        wf_service.trg_validate(uid, 'purchase.advance.supplier', ad_id, 'approval_accept', cr)
        return True
    
    _columns = {
        'advance_payment_id' : fields.one2many('purchase.advance.supplier', 'purchase_order_id', 'Anticipos', readonly=False, states={'done':[('readonly',True)]}),
    }

class res_partner(osv.osv):
    _inherit = 'res.partner'
    
    _columns = {
        'property_account_receivable_advance': fields.property(
                    type='many2one',
                    relation='account.account',
                    string="Cuenta Anticipo Proveedor",
                     
                    domain="[('type', '=', 'receivable')]"),
    }

class account_voucher(osv.osv):
    _inherit = 'account.voucher'
    
    def recompute_voucher_lines(self, cr, uid, ids, partner_id, journal_id, price, currency_id, ttype, date, context=None):
        values = super(account_voucher, self).recompute_voucher_lines(cr, uid, ids, partner_id, journal_id, price, currency_id, ttype, date, context=context)
        
        #private function from the same original parent method
        def _remove_noise_in_o2m():
            """if the line is partially reconciled, then we must pay attention to display it only once and
                in the good o2m.
                This function returns True if the line is considered as noise and should not be displayed
            """
            if line.reconcile_partial_id:
                if currency_id == line.currency_id.id:
                    if line.amount_residual_currency <= 0:
                        return True
                else:
                    if line.amount_residual <= 0:
                        return True
            return False
        
        move_line_pool = self.pool.get('account.move.line')
        currency_pool = self.pool.get('res.currency')
        journal_pool = self.pool.get('account.journal')
        account_id = False
        parter = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)
        journal = journal_pool.browse(cr, uid, journal_id, context=context)
        company_currency = journal.company_id.currency_id.id
        
        if ttype == 'payment':
            account_id = parter.property_account_receivable_advance and parter.property_account_receivable_advance.id or False
        if account_id:
            ids = move_line_pool.search(cr, uid, [('state','=','valid'), ('account_id', '=', account_id), ('reconcile_id', '=', False), ('partner_id', '=', partner_id)], context=context)
            ids.reverse()
            account_move_lines = move_line_pool.browse(cr, uid, ids, context=context)
            for line in account_move_lines:
                if _remove_noise_in_o2m():
                    continue
                if line.currency_id and currency_id==line.currency_id.id:
                    amount_original = abs(line.amount_currency)
                    amount_unreconciled = abs(line.amount_residual_currency)
                else:
                    amount_original = currency_pool.compute(cr, uid, company_currency, currency_id, line.credit or line.debit or 0.0)
                    amount_unreconciled = currency_pool.compute(cr, uid, company_currency, currency_id, abs(line.amount_residual))
                line_currency_id = line.currency_id and line.currency_id.id or company_currency
                rs = {
                    'name':line.move_id.name,
                    'type': line.credit and 'dr' or 'cr',
                    'move_line_id':line.id,
                    'account_id':line.account_id.id,
                    'amount_original': amount_original,
                    'amount': 0.0,
                    'date_original':line.date,
                    'date_due':line.date_maturity,
                    'amount_unreconciled': amount_unreconciled,
                    'currency_id': line_currency_id,
                }
                values['value']['line_cr_ids'].append(rs)
                values['value']['pre_line'] = True
        return values

class advance_supplier(osv.osv, EDIMixin):
    _name = "purchase.advance.supplier"
    _description = "Anticipo Proveedor"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _order = 'name desc'
    
    def _no_amount(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context=context):
            if advance.amount <= 0.00:
                return False
        return True
        
    def _check_currency(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context=context):
            if advance.tasa_cambio < 0 and advance.state != 'draft':
                return False
        return True
    
    def _get_local_currency_total(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for advance in self.browse(cr, uid, ids, context):
            res[advance.id] = advance.amount*advance.tasa_cambio
        return res
    
    def _amount_residual_value(self, cr, uid, advance, context=None):
        remaining = False
        if advance.move_id:
            remaining = advance.account_move_line_id.amount_residual
        return remaining
    
    def _amount_residual(self, cr, uid, ids, name, args, context=None):
        result = {}
        wf_service = openerp.netsvc.LocalService("workflow")
        period_obj = self.pool.get('account.period')
        for advance in self.browse(cr, uid, ids, context=context):
            if advance.move_id:
                
                remaining = self._amount_residual_value(cr, uid, advance, context)
                result[advance.id] = remaining
                
                #no usar el campo .residual en las funciones de workflow que desencadenan de estas signals, usar la funcion _amount_residual_value
                if remaining > 0 and advance.state == 'done':
                    wf_service.trg_validate(uid, 'purchase.advance.supplier', advance.id, 'done_back', cr)
                elif remaining == 0 and advance.state == 'progress':
                    wf_service.trg_validate(uid, 'purchase.advance.supplier', advance.id, 'done', cr)
        
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
            advance_ids = self.pool.get('purchase.advance.supplier').search(cr, uid, [('move_id','in',move.keys())], context=context)
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
            advance_ids = self.pool.get('purchase.advance.supplier').search(cr, uid, [('move_id','in',move.keys())], context=context)
        return advance_ids
    
    
    _columns = {
        'name': fields.char('Codigo',size=64,readonly=True),
        'move_name': fields.char('Nombre Comprobante', size=64, readonly=True, copy=False),
        'moneda_local': fields.related('company_id','currency_id',type="many2one",relation="res.currency",string="Moneda Local",readonly=True, store=True),
        'description': fields.text('Descripcion', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'user_id': fields.many2one('res.users', 'Usuario', required=True, readonly=True, states={'draft': [('readonly', False),('required', True)]}),
        'partner_id': fields.many2one('res.partner', 'Proveedor', readonly=True, required=True, domain=[('supplier','=',True)], states={'draft': [('readonly', False),('required', True)]}),
        'purchase_order_id' : fields.many2one('purchase.order','Orden de Compra', readonly=True, ondelete='cascade', states={'draft': [('readonly', False)]}),
        'currency_id': fields.many2one('res.currency', 'Moneda', required=True, readonly=True, states={'draft': [('readonly', False),('required', True)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True, readonly=True, states={'draft': [('readonly', False),('required', True)]}),
        'tasa_cambio' : fields.float("Tasa Cambio", digits_compute=dp.get_precision('Exchange Precision'),required=True, readonly=False, states={'done': [('readonly', True)]}),
        'amount': fields.float('Valor', digits_compute=dp.get_precision('Account'), required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'request_date': fields.date('Fecha Solicitud', readonly=True, required=True, states={'draft': [('readonly', False),('required', True)]}),
        'planned_date': fields.date('Fecha Planificada', readonly=True, required=True, states={'draft': [('readonly', False)]}),
        'pay_date': fields.date('Fecha de Pago', readonly=True, states={'validated': [('readonly', False)]}),
        'journal_bank_id': fields.many2one('account.journal', 'Diario Banco', readonly=True, states={'validated': [('readonly', False)]}, domain=[('type','in',['bank', 'cash']),('recaudo','=',False)]),
        'account_analytic_id': fields.many2one('account.analytic.account', 'Centro de Costo', readonly=True, states={'draft': [('readonly', False)]}),
        'multicurrency': fields.boolean('Multimoneda'),
        'move_id': fields.many2one('account.move', 'Comprobante', readonly=True, copy=False),
        'total_local': fields.function(_get_local_currency_total, type="float", string="En Moneda Local", digits_compute=dp.get_precision('Account'), readonly=True, store=True),
        'account_move_line_id': fields.many2one('account.move.line', 'Linea a reconciliar', readonly=True),
        'reconcile_id': fields.related('account_move_line_id','reconcile_id',type="many2one",relation="account.move.reconcile",string="Reconciliacion",readonly=True,store=True),
        'reconcile_partial_id': fields.related('account_move_line_id','reconcile_partial_id',type="many2one",relation="account.move.reconcile",string="Reconciliacion Parcial",readonly=True,store=True),
        'state':fields.selection([('draft', 'Borrador'),
                                  ('waiting_approval', 'Pendiente Aprobacion'), 
                                  ('refused', 'Rechazado'),
                                  ('validated', 'Aprobado'), 
                                  ('cancelled', 'Cancelado'),
                                  ('progress', 'Contabilizado'), 
                                  ('done', 'Realizado'), 
                                  ], 'Estado', select=True, readonly=True, track_visibility='onchange'),
                                  
        'remaining': fields.function(_amount_residual, digits_compute=dp.get_precision('Account'), string='Balance',
            store={
                'purchase.advance.supplier': (lambda self, cr, uid, ids, c={}: ids, None,50),
                'account.move.line': (_get_advance_from_line, None, 50),
                'account.move.reconcile': (_get_advance_from_reconcile, None, 50),
            }, track_visibility='onchange'),
    }
    
    _defaults = {
        'request_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state': 'draft',
        'currency_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'company_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.id,
        'user_id': lambda self, cr, uid, c: uid,
        'tasa_cambio': 1,
    }
    
    _track = {
        'state': {
            'advance_supplier.mt_advance_new': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'draft',
            'advance_supplier.mt_advance_waiting_approval': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'waiting_approval',
            'advance_supplier.mt_advance_refused': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'refused',
            'advance_supplier.mt_advance_validated': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'validated',
            'advance_supplier.mt_advance_cancelled': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelled',
            'advance_supplier.mt_advance_progress': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'progress',
            'advance_supplier.mt_advance_done': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'done',
        },
    }
    
    _constraints = [
        (_no_amount, 'No se pueden ingresar valores menores o iguales a 0!', ['amount']),
        (_check_currency, 'No existe una tasa con la cual se pueda evaluar', ['tasa_cambio']),
    ]
    
    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'name':False,
        })
        return super(advance_supplier, self).copy(cr, uid, id, default=default, context=context)
    
    def onchange_currency_id(self, cr, uid, ids, currency_id, company_id, date, date_pay, state, context=None):
        val = {}
        warning = {}
        if currency_id:
            var= 0.0      
            
            if not company_id:
                company  = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            else:
                company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
            
            if company.currency_id.id != currency_id:
                date = date
                if date_pay:
                    date = date_pay
                currency_obj = self.pool.get('res.currency')
                currency_id = currency_obj.browse(cr, uid, currency_id, context=context)
                var = currency_obj.tasa_dia(cr, uid, date, company, currency_id, context=context)                
                if var == 0.0:
                    warning = {
                        'title': _('Advertencia!'),
                        'message' : _("No existe la tasa de cambio para la fecha '%s' ") % (date)
                    }
                    rate = -1
                else:
                    rate = var
                multi = True
            else:
                rate = 1
                multi = False
                
            val['currency_id'] = currency_id
            val['tasa_cambio'] = rate
            val['multicurrency'] = multi
        return {'value': val,'warning': warning}
    
    
    def wf_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'draft'})
        return True
        
    def wf_waiting_approval(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'waiting_approval'})
        return True
        
    def wf_refused(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'refused'})
        return True
        
    def wf_validated(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'validated'})
        return True
        
    def wf_cancelled(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'cancelled'})
        return True
        
    def wf_progress(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        for advance in self.browse(cr, uid, ids, context):
            if advance.move_id:
                self.write(cr, uid, [advance.id] ,{'state':'progress'})
                continue
            date = advance.pay_date
            period_ids = period_obj.find(cr, uid, date)
            period_id = period_ids and period_ids[0] or False
            if not period_id:
                raise osv.except_osv(_('Error !'), _('No hay un periodo definido para esta fecha'))
            
            moneda = (advance.currency_id != advance.moneda_local) and advance.currency_id or False
            cantidad_moneda = moneda and advance.amount or False
            amount = moneda and advance.amount*advance.tasa_cambio or advance.amount
            
            if not advance.partner_id.property_account_receivable_advance:
                raise osv.except_osv(_('Error !'), _('El Tercero no tiene cuenta de cobro para anticipos configurada'))
            account_recivable_id = advance.partner_id.property_account_receivable_advance.id
            partner_id = advance.partner_id.id
            
            if not date:
                raise osv.except_osv(_('Error !'), _('Debe haber una fecha de pago'))
            if not advance.journal_bank_id or not advance.mode:
                raise osv.except_osv(_('Error !'), _('Debe haber un metodo de pago'))
            
            vals = { 'partner_id': partner_id,
                     'journal_id': advance.journal_bank_id.id,
                     'date': date,
                     'ref': advance.name,
                     'period_id': period_id,
                    }
            
            if advance.move_name:
                vals['name'] = advance.move_name
            
            move_id = move_obj.create(cr, uid, vals, context)
            vals = { 'partner_id': partner_id,
                     'currency_id': moneda and moneda.id or False,
                     'amount_currency': cantidad_moneda,
                     'journal_id': advance.journal_bank_id.id,
                     'date': date,
                     'name': advance.name,
                     'debit': amount,
                     'credit': 0,
                     'account_id': account_recivable_id,
                     'analytic_account_id': advance.account_analytic_id and advance.account_analytic_id.id or False,
                     'period_id': period_id,
                     'move_id': move_id,
                    }
            move_line_id1 = move_line_obj.create(cr, uid, vals, context)
            vals = { 'partner_id': partner_id,
                     'currency_id': moneda and moneda.id or False,
                     'amount_currency': cantidad_moneda*-1,
                     'journal_id': advance.journal_bank_id.id,
                     'date': date,
                     'name': advance.name,
                     'credit': amount,
                     'debit': 0,
                     'account_id': advance.journal_bank_id.default_credit_account_id.id,
                     'analytic_account_id': advance.account_analytic_id and advance.account_analytic_id.id or False,
                     'period_id': period_id,
                     'move_id': move_id,
                    }
            move_line_id2 = move_line_obj.create(cr, uid, vals, context)
            new_move_name = move_obj.browse(cr, uid, move_id, context=context).name
            self.write(cr, uid, [advance.id] ,{'move_name': new_move_name,'move_id': move_id,'account_move_line_id': move_line_id1, 'state':'progress'})
            
        return True
        
    def wf_done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'done'})
        return True
    
    def write(self, cr, uid, ids, vals, context=None):
        for advance in self.browse(cr, uid, ids, context):
            #verificacion para la tasa de cambio
            if vals.get('currency_id') and  (vals.get('pay_date',False) or not vals.get('tasa_cambio',False)):
                company = advance.company_id
                currency_id = vals.get('currency_id',False)
                rate = 1
                if company.currency_id.id != currency_id:
                    date = advance.request_date
                    if advance.state == 'validated':
                        date = vals.get('pay_date',False)                        
                    currency_obj = self.pool.get('res.currency.rate')
                    currency_date_id = currency_obj.search(cr, uid, [('date_sin_hora','=',date),('currency_id','=',currency_id)])
                    if not currency_date_id:
                        rate = -1
                    else:
                        rate = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv
                vals.update({'tasa_cambio': rate})
        #llama al metodo padre
        result = super(advance_supplier, self).write(cr, uid, ids, vals, context=context)
        return result
    
    def create(self, cr, uid, vals, context={}):
        if (not 'name' in vals) or (vals['name'] == False):
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'purchase.advance.number') or '/'
            
        return super(advance_supplier, self).create(cr, uid, vals, context)
    