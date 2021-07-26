from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
import openerp.netsvc
from operator import itemgetter
from itertools import groupby
from openerp.osv import fields, osv, orm
from openerp.tools.translate import _
from openerp import workflow
from openerp import tools
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import openerp.addons.decimal_precision as dp
from openerp import pooler, tools, SUPERUSER_ID
from openerp.addons.edi import EDIMixin
import numpy

class account_loan(osv.osv, EDIMixin):
    _name = 'account.loan'
    _description = "Obligacion Financiera"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _rec_name = 'loan_no'
    _order = 'payment_date desc'
    
    def _check_loan_no(self, cr, uid, ids, context=None):
        '''
        Check if the UoM has the same category as the product standard UoM
        '''
        if not context:
            context = {}
        for loan in self.browse(cr, uid, ids, context=context):
            rec_ids = self.search(cr, uid, [("loan_no", '=', loan.loan_no), ("id", "!=", loan.id)])
            if rec_ids:
                return False
        return True
    
    def _period_remain(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for rec in self.browse(cr, uid, ids, context=context):
            val = 0
            for line in rec.loan_move_line_ids:
                if line.state != 'confirm' and not line.payment > 0:
                 val += 1
            res[rec.id] = val
        return res
    
    def _get_balance_debt(self, cr, uid, ids, name, arg, context=None):
        res = {}
        
        for rec in self.browse(cr, uid, ids, context=context):
            val = -rec.final_payment
            for line in rec.loan_move_line_ids:
                if line.state == 'confirm':
                    val -= line.capital_payment+line.val_to_capital-line.payment
            if val <= 0:
                val += rec.balance
            res[rec.id] = val
        return res
    
    def _get_balance_debt_lines(self, cr, uid, ids, context=None):
        cuota_obj = self.pool.get('loan.move.line')
        return [line.loan_id.id for line in cuota_obj.browse(cr, uid, ids, context=context)]
    
    def check_analytic_sum(self, cr, uid, ids, context=None):
        currency_obj = self.pool.get('res.currency')
        for asset in self.browse(cr, uid, ids, context):
            sum = 0
            for analytic in asset.analytic_account_ids:
                sum += analytic.rate
            if sum != 100:
                return False
        return True
    
    _columns = {
            'partner_bank_id': fields.many2one('res.partner.bank', 'Cuenta de banco'),
            'analytic_account_ids': fields.one2many('account.loan.distribution', 'loan_id', 'Centros de Costo', track_visibility='onchange'),
            'company_id':fields.many2one('res.company', 'Company', required=True),
            'loan_no':fields.char('Numero de Obligacion', size=64, required=True),
            'loan_var_type':fields.selection([('fixed', 'Plazo Fijo'), ('intcom', 'Intercompania'), ('shareholder', 'Accionistas'), ('leasing', 'Leasing'), ('rotary', 'Rotativo'), ], "Modalidad de Obligacion", required=True),
            'dec_type':fields.selection([('cuoto_fija', 'Cuota Fija'), ('capital_fijo', 'Capital Fijo')], 'Tipo de Amortizacion', required=True),
            'partner_id':fields.many2one('res.partner', 'Tercero', required=True),
            'loan_type':fields.selection([('por_cobrar', 'Por Cobrar'), ('por_pagar', 'Por Pagar')], 'Tipo de Obligacion', required=True),
            'currency_id':fields.many2one('res.currency', 'Moneda', required=True),
            'intrest_per_period':fields.float('Interes', digits_compute= dp.get_precision('Account'),track_visibility="onchange", required=True),
            'period_no':fields.integer('Meses Entre Periodos', required=True),
            'periods_to_pay':fields.integer('Plazo Inicial', required=True),
            'remain_period':fields.function(_period_remain, type="integer", string="Periodos por pagar"),
            'final_payment':fields.float('Pago final', digits_compute= dp.get_precision('Account'),track_visibility="onchange"),
            'start_period':fields.integer('Periodos de Gracia'),
            'balance':fields.float('Valor inicial de obligacion', digits_compute= dp.get_precision('Account'), required=True),
            'payment_date':fields.date('Fecha de desembolso', required=True),
            'first_payment':fields.float('Primer desembolso'),
            'balance_debt':fields.function(_get_balance_debt, digits_compute= dp.get_precision('Account'), type="float", string="Saldo por amortizar", readonly=True, 
                    store={
                    'loan.move.line': (_get_balance_debt_lines, ['cote', 'capital_payment', 'state'], 10),
                    'account.loan': (lambda self, cr, uid, ids, c={}: ids, ['final_payment'], 10),
                   }),
            'state':fields.selection([
                                    ('new', 'Borrador'),
                                    ('in_progress', 'En Ejecucion'),
                                    ('done', 'Terminada'),
                                    ('cancel', 'Anulada')], 'Status', readonly=True, track_visibility='onchange'),
            'loan_move_line_ids':fields.one2many('loan.move.line', 'loan_id', 'Loan Depriciation Line'),
            'capital_id':fields.many2one('account.account', 'Capital', required=True),
            'intereses_id':fields.many2one('account.account', 'Intereses', required=True),
            'inter_de_mora_id':fields.many2one('account.account', 'Intereses de Mora'),
            'gastos_bancarios_id':fields.many2one('account.account', 'Gastos Bancarios'),
            'tes_oreria_id':fields.many2one('account.account', 'Tesoreria', required=True),
            'bank_journal_id':fields.many2one("account.journal", "Diario de Banco", domain=[('type','=','bank')], required=True),
            'loan_journal_id':fields.many2one("account.journal", "Diario de Obligacion", required=True),
            'tir':fields.float(string='TIR Fiscal', digits_compute= dp.get_precision('Exchange Precision')),
            'tir_contable':fields.float(string='TIR Contable', digits_compute= dp.get_precision('Exchange Precision')),
            }
    
    _constraints = [
        (_check_loan_no, 'Numero de obligacion should be unique', ['loan_no']),
        (check_analytic_sum, 'La distribucion tiene que dar 100%!', ['analytic_account_ids']),
    ]
    
    _defaults = {
        'period_no': 1,
        'state':'new',
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'account.loan', context=c),
    }
               
    def action_button_new(self, cr, uid, ids, context=None):
        cur_obj = self.browse(cr , uid , ids[0])
        self.write(cr, uid, cur_obj.id, {'state':'new'})
        return True
        
    def action_button_cancel(self, cr, uid, ids, context=None):
        cur_obj = self.browse(cr , uid , ids[0])
        self.write(cr, uid, cur_obj.id, {'state':'cancel'})
        return True
    
    def action_button_confirm(self, cr, uid, ids, context=None):
        cur_obj = self.browse(cr , uid , ids[0])
        self.write(cr, uid, cur_obj.id, {'state':'in_progress'})
        return True
    
    def action_button_done(self, cr, uid, ids, context=None):
        cur_obj = self.browse(cr , uid , ids[0])
        self.write(cr, uid, cur_obj.id, {'state':'done'})
        return True
    
    
    def compute_tir(self, cr, uid, ids, context=None):        
        loan_move_line_obj = self.pool.get('loan.move.line')
        num = openerp.registry(cr.dbname).get('decimal.precision').precision_get(cr, SUPERUSER_ID, 'Account')
        
        array=[]
        for loan in self.browse(cr, uid, ids, context=context):
            for line in loan.loan_move_line_ids:
                if line.period == 0:                
                    if loan.loan_type == 'por_pagar':
                        array=[line.total_payment]
                    else:
                        array=[-line.total_payment]
                else:
                    if loan.loan_type == 'por_pagar':
                        array.append(-line.total_payment)
                    else:
                        array.append(line.total_payment)
                    
            print "1111111111111"
            print array
            print ""
            print ""
            tir_contable = numpy.irr(array)
            print "222222222222"
            print tir_contable
            print ""
            print ""
            self.write(cr, uid, ids, {'tir_contable':tir_contable})
        return True  
    
    def compute_loan_board(self, cr, uid, ids, context=None):
        loan_move_line_obj = self.pool.get('loan.move.line')
        num = openerp.registry(cr.dbname).get('decimal.precision').precision_get(cr, SUPERUSER_ID, 'Account')
        
        for loan in self.browse(cr, uid, ids, context=context):
            cuotas_pagadas = 0
            n=0
            cuotas_gracia_pagadas = 0
            desembolso = False
            cuota_extra = 0
            if loan.loan_type == 'por_pagar':
                array=[loan.balance_debt]
            else:
                array=[-loan.balance_debt]
                
            if loan.loan_move_line_ids:
                for cuota in loan.loan_move_line_ids:
                    if cuota.val_to_capital:
                        cuota_extra += cuota.val_to_capital
                    elif cuota.state == 'new':
                        loan_move_line_obj.unlink(cr, SUPERUSER_ID, cuota.id, context)
                    elif not cuota.payment:
                        if cuota.capital_payment:
                            cuotas_pagadas+=1
                        elif cuota.interest:
                            cuotas_gracia_pagadas+=1
                    elif cuota.payment:
                        desembolso = True
            
            remain_period = loan.periods_to_pay - cuotas_pagadas
            final_payment = loan.final_payment
            balance_debt = loan.balance_debt
            initial_value = loan.balance_debt+final_payment
            
            tasa_interes = loan.intrest_per_period/100

                                
            period = cuotas_pagadas+cuotas_gracia_pagadas
            final_period = cuotas_pagadas+cuotas_gracia_pagadas
            incre = loan.period_no*period
            date = datetime.strptime((datetime.strptime(loan.payment_date, '%Y-%m-%d') + relativedelta(months=0)).strftime('%Y-%m-%d'), '%Y-%m-%d')
            if not desembolso:
                loan_move_line_obj.create(cr, SUPERUSER_ID, {"period":0,
                                                    'date':date,
                                                    'payment':loan.balance,
                                                    'loan_id':loan.id, 'state':'new'})
            
            if loan.start_period:
                for period in range(cuotas_gracia_pagadas, loan.start_period):                    
                    interest = round(initial_value*tasa_interes, num)
                    incre += loan.period_no
                    array.append(0.0)
                    date = datetime.strptime((datetime.strptime(loan.payment_date, '%Y-%m-%d') + relativedelta(months=incre)).strftime('%Y-%m-%d'), '%Y-%m-%d')
                    loan_move_line_obj.create(cr, SUPERUSER_ID, {"period":period + 1,
                                                        'date':date,
                                                        'initial_value':initial_value,
                                                        'interest':interest,
                                                        'cote':interest ,
                                                        'loan_id':loan.id,
                                                        'state':'new'})
                    final_period = period + 1
            total=0
            tir = 0.0
            amount_final = 0.0
            for period in range(cuotas_pagadas, loan.periods_to_pay):
                incre += loan.period_no
                interest = round(initial_value*tasa_interes, num)
                if loan.dec_type == 'cuoto_fija':
                    capital_payment = ((tasa_interes*((1+tasa_interes)**(remain_period))/(((1+tasa_interes)**(remain_period))-1))*(balance_debt))-((initial_value-final_payment)*tasa_interes)
                elif loan.dec_type == 'capital_fijo':
                    capital_payment = (balance_debt-final_payment)/remain_period
                else:
                    print "xxxxxxxxx"
                    print period
                    if period == loan.periods_to_pay:
                        capital_payment = loan.periods_to_pay
                    else:
                        capital_payment = 0.0
                
                
                date = datetime.strptime((datetime.strptime(loan.payment_date, '%Y-%m-%d') + relativedelta(months=incre)).strftime('%Y-%m-%d'), '%Y-%m-%d')
                if period == loan.periods_to_pay-1:
                    capital_payment = balance_debt-total
                capital_payment = round(capital_payment, num)
                
                if loan.loan_type == 'por_pagar':
                    array.append(-(interest + capital_payment))
                else:
                    array.append((interest + capital_payment))
                
                amount_final+=(interest + capital_payment)
                
                loan_move_line_obj.create(cr, SUPERUSER_ID, {"period":period + 1 + final_period,
                                                    'date':date,
                                                    'initial_value':initial_value,
                                                    'capital_payment':capital_payment,
                                                    'interest':interest,
                                                    'cote':interest + capital_payment,
                                                    'loan_id':loan.id, 
                                                    'state':'new'})
                initial_value -= capital_payment
                total+=capital_payment
            
            #if loan.loan_type == 'por_pagar':
                #array.append(-amount_final)
            #else:
                #array.append(amount_final)
            
            print "1111111111111"
            print array
            print ""
            print ""
            tir = numpy.irr(array)
            print "222222222222"
            print tir
            print ""
            print ""
            self.write(cr, uid, ids, {'tir':tir})
        return True  
    
    def unlink(self, cr, uid, ids, context=None):
        for obligacion in self.browse(cr, uid, ids, context=context):
            if obligacion.state not in  ['new','cancel']:
                raise osv.except_osv(_('Error!'),_('No puede borrar una obligacion que no esta en borrador o cancelado!'))
        return super(account_loan, self).unlink(cr, uid, ids, context)
    
    def borrador(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'new'}, context=context)
        return True
        
    def in_progress(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'in_progress'})
        return True
        
    def cancel(self, cr, uid, ids, context=None):
        for obligacion in self.browse(cr, uid, ids, context=context):
            for line in obligacion.loan_move_line_ids:
                if line.state != 'new':
                    raise osv.except_osv(_('Error!'),_('Solo puede cancelar obligaciones que no tengan lineas contabilizadas!'))
        self.write(cr, uid, ids , {'state':'cancel'})
        return True
        
    def done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'done'})
        return True
    
class loan_move_line(osv.osv):
    _name = "loan.move.line"
    _description = "Linea de Obligacion Financiera"
    _order = 'date asc, period desc, prepaid_id desc'
    
    def _get_move_check(self, cr, uid, ids, name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = bool(line.loan_id)
        return res
        
    def _get_total_payment(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for rec in self.browse(cr, uid, ids, context=context):
            res[rec.id] = abs(rec.payment - rec.val_to_capital - rec.capital_payment - rec.interest - rec.penality_interest - rec.bank_charges)
            if rec.loan_id.loan_type == 'por_cobrar' and res[rec.id] > 0:
                res[rec.id] -= rec.bank_charges*2
        return res
        
    def _get_cote(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for rec in self.browse(cr, uid, ids, context=context):
            res[rec.id] = abs(rec.capital_payment + rec.interest)
        return res
        
    def _get_final_bal(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for rec in self.browse(cr, uid, ids, context=context):
            res[rec.id] = rec.initial_value + rec.payment - rec.capital_payment - rec.val_to_capital
        return res
    
    def _get_advance_from_line(self, cr, uid, ids, context=None):
        move = {}
        for line in self.pool.get('account.move.line').browse(cr, uid, ids, context=context):
            if line.reconcile_id:
                for line2 in line.reconcile_id.line_id:
                    move[line2.move_id.id] = True
                    
        loan_line_ids = []
        if move:
            loan_line_ids = self.pool.get('loan.move.line').search(cr, uid, [('move_id','in',move.keys())], context=context)
        return loan_line_ids
        
    def _get_advance_from_reconcile(self, cr, uid, ids, context=None):
        move = {}
        for r in self.pool.get('account.move.reconcile').browse(cr, uid, ids, context=context):
            for line in r.line_partial_ids:
                move[line.move_id.id] = True
            for line in r.line_id:
                move[line.move_id.id] = True
                
        loan_line_ids = []
        if move:
            loan_line_ids = self.pool.get('loan.move.line').search(cr, uid, [('move_id','in',move.keys())], context=context)
        return loan_line_ids
        
    
    def _is_paid(self, cr, uid, ids, name, args, context=None):
        result = {}
        num = 0
        for obl_line in self.browse(cr, uid, ids, context=context):
            result[obl_line.id] = False
            if obl_line.move_id:
                for line_move in obl_line.move_id.line_id:
                    if line_move.reconcile_id:
                        result[obl_line.id] = True
                        break
        return result
    
    _columns = {
                'paid': fields.function(_is_paid, type="boolean", string='Pagado'),
                'move_name': fields.char('Nombre Comprobante', size=64, readonly=True),
                'prepaid_id':fields.many2one('account.loan.prepaid', 'Prepago/Desembolso', readonly=True),
                'loan_id':fields.many2one('account.loan', 'Loan', ondelete='cascade'),
                'period':fields.integer('Periodo', readonly=True, states={'new': [('readonly', False)]}),
                'date':fields.date('Fecha', required=True, readonly=True, states={'new': [('readonly', False)]}),
                'initial_value':fields.float('Saldo inicial', digits_compute= dp.get_precision('Account'), readonly=True),
                'core_adjust':fields.float('Ajuste de cuotas', digits_compute= dp.get_precision('Account'), readonly=True),
                'val_to_capital':fields.float('Abono extra a capital', digits_compute= dp.get_precision('Account'), readonly=True),
                'payment':fields.float('Desembolso', digits_compute= dp.get_precision('Account'), readonly=True),
                'capital_payment':fields.float('Pago a capital', digits_compute= dp.get_precision('Account'), readonly=True, states={'new': [('readonly', False)]}),
                'interest':fields.float('Intereses corrientes', digits_compute= dp.get_precision('Account'), readonly=True, states={'new': [('readonly', False)]}),
                'final_bal':fields.function(_get_final_bal, type="float", string="Saldo final", digits_compute= dp.get_precision('Account'), readonly=True),
                'penality_interest':fields.float('Interes de mora', digits_compute= dp.get_precision('Account'), readonly=True, states={'new': [('readonly', False)]}),
                'bank_charges':fields.float('Gastos bancarios', digits_compute= dp.get_precision('Account'), readonly=True, states={'new': [('readonly', False)]}),
                'state':fields.selection([('new', "New"),("confirm", "Confirm") ,('close', "Close")], readonly=True),
                'move_id': fields.many2one('account.move', 'Comprobante Contable', readonly=True),
                'total_payment':fields.function(_get_total_payment, type="float", string="Pago Total", digits_compute= dp.get_precision('Account'), readonly=True),
                'cote':fields.function(_get_cote, type="float", string="Cuota", digits_compute= dp.get_precision('Account'), readonly=True),
            }
    
    _defaults = {
        'state': 'new',
    }
    
    def create_move(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        asset_obj = self.pool.get('account.asset.asset')
        period_obj = self.pool.get('account.period')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        currency_obj = self.pool.get('res.currency')
        obj_seq = self.pool.get('ir.sequence')
        user_rec = self.pool.get("res.users").browse(cr, uid, uid, context = context)
        created_move_ids = []
        currency_rate = 1
        currency_id = False
        leasing_agrupar = False
        for line in self.browse(cr, uid, ids, context=context):
            loan_id = line.loan_id
            
            if loan_id.state != 'in_progress':
                raise osv.except_osv(_('Error!'), _('Solo se puede contabilizar cuando la obligacion esta en estado "En Ejecucion"!'))
                
            if loan_id.currency_id.id != loan_id.company_id.currency_id.id:
                currency_id = loan_id.currency_id.id
                currency_rate = currency_obj.tasa_dia(cr, uid, line.date, loan_id.company_id, loan_id.currency_id, context=context)
                if not currency_rate:
                    raise osv.except_osv(_('Error!'), _('No hay una tasa de cambio para la fecha "%s"!')% (line.date))
            
            line_ids = self.search(cr, uid, [("loan_id", "=", loan_id.id),("period", "<", line.period), ("state", "not in", ['close', 'confirm'])], context = context)
            
            if line_ids:
                error = False
                if loan_id.loan_var_type == 'leasing':
                    
                    if loan_id.capital_id == loan_id.intereses_id:
                        leasing_agrupar = True
                    
                    for line2 in self.browse(cr, uid, line_ids, context=context):
                        if not line2.payment:
                            error = True
                else:
                    error = True
                if error:
                    raise osv.except_osv(_('Error!'), _('Una linea anterior no esta confirmada!'))
            
            if not line.prepaid_id and loan_id.loan_var_type == 'leasing' and line.payment:
                raise osv.except_osv(_('Error!'), _('No se puede contabilizar el pago en un Leasing!'))
            
            depreciation_date = line.date or time.strftime('%Y-%m-%d')
            ctx = dict(context, account_period_prefer_normal=True)
            period_ids = period_obj.find(cr, uid, depreciation_date, context=ctx)
            ctx.update({'date': depreciation_date})
            loan_name = loan_id.loan_no
            reference = loan_id.loan_no
            partner_id = loan_id.partner_id.id
            credit_amount_currency = 0.0
            debit_amount_currency = 0.0
            
            journal_id = loan_id.loan_journal_id.id
            if line.payment or line.prepaid_id:
                journal_id = loan_id.bank_journal_id.id
            
            if line.prepaid_id:
                reference += str(line.prepaid_id.name)
            else:
                reference += ' No.'+str(line.period)
            
            move_vals = {
                'date': depreciation_date,
                'ref': reference+' No.'+str(line.period),
                'period_id': period_ids and period_ids[0] or False,
                'journal_id': journal_id,
                }
            
            if line.move_name:
                move_vals['name'] = line.move_name
                
            move_id = move_obj.create(cr, uid, move_vals, context=ctx)
            
            if line.penality_interest and not loan_id.inter_de_mora_id:
                raise osv.except_osv(_('Error!'), _('No a configurado una cuenta de interesses de mora!'))
            if line.bank_charges and not loan_id.gastos_bancarios_id:
                raise osv.except_osv(_('Error!'), _('No a configurado una cuenta de gastos bancarios!'))
            
            pago_capital_acc = loan_id.capital_id.id
            intereses_acc = loan_id.intereses_id.id
            tesoreria_acc = loan_id.tes_oreria_id.id
            intereses_mora_acc = loan_id.inter_de_mora_id and line.loan_id.inter_de_mora_id.id or False
            gastos_bancarios_acc = loan_id.gastos_bancarios_id and loan_id.gastos_bancarios_id.id or False
            
            por_cobrar = loan_id.loan_type == 'por_cobrar'
            por_pagar = loan_id.loan_type == 'por_pagar'
            if por_cobrar:
                if line.payment or line.val_to_capital:
                    if not loan_id.bank_journal_id.default_credit_account_id:
                        raise osv.except_osv(_('Error!'), _('El diario de banco no tiene configurado cuenta acreedora!'))
                if line.payment:
                    payment_credit = loan_id.bank_journal_id.default_credit_account_id.id
                    payment_debit = loan_id.capital_id.id
                elif line.val_to_capital:
                    payment_credit = loan_id.capital_id.id
                    payment_debit = loan_id.bank_journal_id.default_debit_account_id.id
                        
            elif por_pagar:
                if line.payment or line.val_to_capital:
                    if not loan_id.bank_journal_id.default_credit_account_id:
                        raise osv.except_osv(_('Error!'), _('El diario de banco no tiene configurado cuenta deudora!'))
                if line.payment:
                    payment_credit = loan_id.capital_id.id
                    payment_debit = loan_id.bank_journal_id.default_debit_account_id.id
                elif line.val_to_capital:
                    payment_credit = loan_id.bank_journal_id.default_credit_account_id.id
                    payment_debit = loan_id.capital_id.id
            
            total_debit = 0
            total_credit = 0
            max_centros = len(loan_id.analytic_account_ids)
            x = 0
            for centro_costo_obj in loan_id.analytic_account_ids:
                x+=1
                ultimo = False
                if x == max_centros:
                    ultimo = True
                rate = centro_costo_obj.rate/100
                centro_costo = centro_costo_obj.account_analytic_id.id
                
                if line.penality_interest:
                    penality_interest = line.penality_interest*rate*currency_rate
                    currency_amount = currency_id and line.penality_interest*rate or False
                    if por_cobrar:
                        currency_amount = currency_amount*-1
                    move_line_obj.create(cr, uid, {
                            'name': 'Intereses de Mora',
                            'ref': loan_name,
                            'move_id': move_id,
                            'account_id': intereses_mora_acc,
                            'debit': (por_cobrar==False and penality_interest or 0),
                            'credit': (por_cobrar==True and penality_interest or 0),
                            'amount_currency':currency_amount,
                            'currency_id':currency_id,
                            'period_id': period_ids and period_ids[0] or False,
                            'journal_id': journal_id,
                            'partner_id': partner_id,
                            'date': depreciation_date,
                            'analytic_account_id': centro_costo,
                        })
                    total_debit += (por_cobrar==False and penality_interest or 0)
                    total_credit += (por_cobrar==True and penality_interest or 0)
                
                if line.interest and not leasing_agrupar:
                    interes = line.interest*rate*currency_rate
                    currency_amount = currency_id and line.interest*rate or False
                    if por_cobrar:
                        currency_amount = currency_amount*-1
                    move_line_obj.create(cr, uid, {
                            'name': 'Intereses',
                            'ref': loan_name,
                            'move_id': move_id,
                            'account_id': intereses_acc,
                            'debit': (por_cobrar==False and interes or 0),
                            'credit': (por_cobrar==True and interes or 0),
                            'amount_currency':currency_amount,
                            'currency_id':currency_id,
                            'period_id': period_ids and period_ids[0] or False,
                            'journal_id': journal_id,
                            'partner_id': partner_id,
                            'date': depreciation_date,
                            'analytic_account_id': centro_costo,
                        })
                    total_debit += (por_cobrar==False and interes or 0)
                    total_credit += (por_cobrar==True and interes or 0)
                
                if line.capital_payment and not leasing_agrupar:
                    capital_payment = line.capital_payment*rate*currency_rate
                    currency_amount = currency_id and line.capital_payment*rate or False
                    if por_cobrar:
                        currency_amount = currency_amount*-1
                    move_line_obj.create(cr, uid, {
                            'name': 'Pago Capital',
                            'ref': loan_name,
                            'move_id': move_id,
                            'account_id': pago_capital_acc,
                            'debit': (por_cobrar==False and capital_payment or 0),
                            'credit': (por_cobrar==True and capital_payment or 0),
                            'amount_currency':currency_amount,
                            'currency_id':currency_id,
                            'period_id': period_ids and period_ids[0] or False,
                            'journal_id': journal_id,
                            'partner_id': partner_id,
                            'date': depreciation_date,
                            'analytic_account_id': centro_costo,
                        })
                    total_debit += (por_cobrar==False and capital_payment or 0)
                    total_credit += (por_cobrar==True and capital_payment or 0)
                
                if line.bank_charges:
                    bank_charges = line.bank_charges*rate*currency_rate
                    currency_amount = currency_id and line.bank_charges*rate or False
                    if por_cobrar:
                        currency_amount = currency_amount*-1
                    move_line_obj.create(cr, uid, {
                            'name': 'Gastos Bancarios',
                            'ref': loan_name,
                            'move_id': move_id,
                            'account_id': gastos_bancarios_acc,
                            'debit': bank_charges,
                            'credit': 0,
                            'amount_currency':currency_amount,
                            'currency_id':currency_id,
                            'period_id': period_ids and period_ids[0] or False,
                            'journal_id': journal_id,
                            'partner_id': partner_id,
                            'date': depreciation_date,
                            'analytic_account_id': centro_costo,
                        })
                    total_debit += bank_charges
                
                if leasing_agrupar:
                    cuota = (line.capital_payment+line.interest)*rate*currency_rate
                    currency_amount = currency_id and (line.capital_payment+line.interest)*rate or False
                    if por_cobrar:
                        currency_amount = currency_amount*-1
                    move_line_obj.create(cr, uid, {
                            'name': 'Pago Capital',
                            'ref': loan_name,
                            'move_id': move_id,
                            'account_id': pago_capital_acc,
                            'debit': (por_cobrar==False and cuota or 0),
                            'credit': (por_cobrar==True and cuota or 0),
                            'amount_currency':currency_amount,
                            'currency_id':currency_id,
                            'period_id': period_ids and period_ids[0] or False,
                            'journal_id': journal_id,
                            'partner_id': partner_id,
                            'date': depreciation_date,
                            'analytic_account_id': centro_costo,
                        })
                    total_debit += (por_cobrar==False and cuota or 0)
                    total_credit += (por_cobrar==True and cuota or 0)
                
                total_payment = (line.total_payment-line.payment)*rate
                total_debit += (por_pagar==False and total_payment*currency_rate or 0)
                total_credit += (por_pagar==True and total_payment*currency_rate or 0)
                if ultimo:
                    total_payment += abs(total_debit-total_credit)
                if total_payment > 0 and not line.val_to_capital:
                    currency_amount = currency_id and line.total_payment-line.payment or False
                    if por_pagar:
                        currency_amount = currency_amount*-1
                    move_line_obj.create(cr, uid, {
                            'name': 'Pago Total',
                            'ref': loan_name,
                            'move_id': move_id,
                            'account_id': tesoreria_acc,
                            'debit': (por_pagar==False and total_payment*currency_rate or 0),
                            'credit': (por_pagar==True and total_payment*currency_rate or 0),
                            'amount_currency':currency_amount,
                            'currency_id':currency_id,
                            'period_id': period_ids and period_ids[0] or False,
                            'journal_id': journal_id,
                            'partner_id': partner_id,
                            'date': depreciation_date,
                            'analytic_account_id': centro_costo,
                        })
                
                if line.payment or line.val_to_capital:
                    if line.payment:
                        payment = line.payment*rate*currency_rate
                        currency_amount = currency_id and line.payment*rate or False
                        ref_name = 'Desembolso'
                    elif line.val_to_capital:
                        payment = line.val_to_capital*rate*currency_rate
                        currency_amount = currency_id and line.val_to_capital*rate or False
                        ref_name = 'Abono a Capital'
                    move_line_obj.create(cr, uid, {
                            'name': ref_name+' Credito',
                            'ref': loan_name,
                            'move_id': move_id,
                            'account_id': payment_credit,
                            'debit': 0,
                            'credit': payment,
                            'amount_currency':currency_amount*-1,
                            'currency_id':currency_id,
                            'period_id': period_ids and period_ids[0] or False,
                            'journal_id': journal_id,
                            'partner_id': partner_id,
                            'date': depreciation_date,
                            'analytic_account_id': centro_costo,
                        })
                    move_line_obj.create(cr, uid, {
                            'name': ref_name+' Debito',
                            'ref': loan_name,
                            'move_id': move_id,
                            'account_id': payment_debit,
                            'debit': payment,
                            'credit': 0,
                            'amount_currency':currency_amount,
                            'currency_id':currency_id,
                            'period_id': period_ids and period_ids[0] or False,
                            'journal_id': journal_id,
                            'partner_id': partner_id,
                            'date': depreciation_date,
                            'analytic_account_id': centro_costo,
                        })
                        
            new_move_name = move_obj.browse(cr, uid, move_id, context=ctx).name
            self.write(cr, uid, line.id, {'move_name': new_move_name, 'move_id': move_id, 'state':'confirm'}, context=ctx)
        return created_move_ids
        
    def cancel_move(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        move_obj = self.pool.get('account.move')
        for line in self.browse(cr, uid, ids, context=context):
            
            for cuota in line.loan_id.loan_move_line_ids:
                if cuota.date > line.date and cuota.state != 'new':
                    raise osv.except_osv(_('Error !'),_("Solo se puede cancelar la ultima cuota contabilizada"))
        
            if line.paid:
                raise osv.except_osv(_('Error!'), _('No se puede cancelar lineas pagadas!'))
            if line.move_id:
                move_obj.button_cancel(cr, uid, [line.move_id.id], context = context)
                move_obj.unlink(cr, uid, [line.move_id.id], context=context)
            
            self.write(cr, uid, line.id, {'state':'new'}, context=context)
            
        return True
 
class account_loan_prepaid(osv.osv, EDIMixin):
    _name = "account.loan.prepaid"
    _description = "Prepago Desembolso Obligacion Financiera"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _order = 'name desc'
    
    _columns = {
        'type':fields.selection([('prepago', 'Prepago'), ('desembolso', 'Desembolso')], 'Tipo', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'company_id': fields.related('loan_id','company_id',type="many2one",relation="res.company",string="Compania",readonly=True,store=True),
        'loan_id': fields.many2one('account.loan', 'Obligacion Financiera', domain=[('state','=','in_progress')],readonly=True, states={'draft': [('readonly', False)]}),
        'value': fields.float("Valor", digits_compute= dp.get_precision('Account'), required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'numero_cuotas': fields.integer("Cuotas a Modificar", readonly=True, help="Negativo restar, Positivo para sumar", states={'draft': [('readonly', False)]}),
        'name': fields.char('Codigo',size=64,readonly=True),
        'date': fields.date('Fecha de Pago', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'description': fields.text('Descripcion'),
        'approve_date': fields.date('Fecha de Aprobacion', help="Fecha en la que se aprobo el prepago, dejela vacia para que se llene automaticamente", readonly=True, states={'confirmed': [('readonly', False)], 'draft': [('readonly', False)]}),
        'state':fields.selection([('draft', 'Borrador'), 
                                  ('confirmed', 'Confirmada'), 
                                  ('validated', 'Validada'), 
                                  ('refused', 'Rechazada'), 
                                  ('cancelled', 'Cancelada'), 
                                  ('done', 'Pagado'), 
                                  ], 'State', select=True, readonly=True),
    }
    
    _defaults = {
        'date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state': 'draft',
    }
    
    def check_no_amount(self, cr, uid, ids, context=None):
        for prepago in self.browse(cr, uid, ids, context=context):
            if prepago.numero_cuotas < 0:
                numero = 0
                cuotas_restar = prepago.numero_cuotas*-1
                if cuotas_restar:
                    monto_cuotas = 0
                    for cuota in prepago.loan_id.loan_move_line_ids:
                        if not cuota.paid and not cuota.prepaid_id:
                            monto_cuotas += cuota.capital_payment
                            numero+=1
                            if numero == cuotas_restar:
                                break;
                    
                    if numero < cuotas_restar:
                        raise osv.except_osv(_('Error !'),_("El numero de cuotas no puede ser mayor al numero de cuotas restantes"))
                            
                    if monto_cuotas > prepago.value:
                        raise osv.except_osv(_('Error!'),_('No se puede ingresar un numero de cuotas cuyo monto sea mayor al valor prepagado!'))
        return True
    
    _track = {
        'state': {
            'account_loan.mt_prepaid_account_loan_new': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'draft',
            'account_loan.mt_prepaid_account_loan_confirmado': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'confirmed',
            'account_loan.mt_prepaid_account_loan_validado': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'validated',
            'account_loan.mt_prepaid_account_loan_rechazado': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'refused',
            'account_loan.mt_prepaid_account_loan_cancelado': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelled',
            'account_loan.mt_prepaid_account_loan_pagado': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'done',
        },
    }
    
    def draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'draft'})
        return True
    
    def confirm(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'confirmed'})
        return True
        
    def validate(self, cr, uid, ids, context=None):
        cuotas_obj = self.pool.get('loan.move.line')
        prestamo_obj = self.pool.get('account.loan')
        for prepago in self.browse(cr, uid, ids, context=context):
            for cuota in prepago.loan_id.loan_move_line_ids:
                if cuota.prepaid_id.id == prepago.id:
                    cuotas_obj.unlink(cr, uid, [cuota.id], context=context)
                    prestamo_obj.compute_loan_board(cr, uid, [prepago.loan_id.id], context=context)
            if not prepago.approve_date:
                self.write(cr, uid, ids, {'approve_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)})
        self.write(cr, uid, ids, {'state': 'validated'})
        self.check_no_amount(cr, uid, ids, context=context)
        return True
    
    def refuse(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'refused'})
        return True
    
    def done(self, cr, uid, ids, context=None):
        self.check_no_amount(cr, uid, ids, context=context)
        cuotas_obj = self.pool.get('loan.move.line')
        prestamo_obj = self.pool.get('account.loan')
        for prepago in self.browse(cr, uid, ids, context=context):
            saldo_inicial = 0
            for cuota in prepago.loan_id.loan_move_line_ids:
                if cuota.date < prepago.date or (cuota.date == prepago.date and cuota.prepaid_id):
                    saldo_inicial = cuota.final_bal
                    if cuota.state == 'new':
                        if not (prepago.loan_id.loan_var_type == 'leasing' and cuota.period == 0):
                            raise osv.except_osv(_('Error !'),_("no puede haber prepagos/desembolsos posteriores a cuotas que no se han contabilizado"))
                        # loan_id.loan_var_type != 'leasing':
                if cuota.date > prepago.date and cuota.state != 'new':
                        raise osv.except_osv(_('Error !'),_("esta tratando de contabilizar un prepago/desembolso en una fecha anterior a una cuota ya contabilizada"))
            
            if prepago.type == 'prepago':
                cuota_id = cuotas_obj.create(cr, uid, {'initial_value': saldo_inicial,'state': 'confirm','loan_id': prepago.loan_id.id,'val_to_capital': prepago.value, 'date': prepago.date, 'prepaid_id': prepago.id, 'core_adjust': prepago.numero_cuotas}, context=context)
                if prepago.value > saldo_inicial:
                    raise osv.except_osv(_('Error !'),_("El prepago no puede ser mayor al saldo"))
                
            elif prepago.type == 'desembolso':
                cuota_id = cuotas_obj.create(cr, uid, {'initial_value': saldo_inicial,'state': 'confirm','loan_id': prepago.loan_id.id,'payment': prepago.value, 'date': prepago.date, 'prepaid_id': prepago.id, 'core_adjust': prepago.numero_cuotas}, context=context)
            cuotas_obj.create_move(cr, uid, [cuota_id], context=context)
            prestamo_obj.write(cr, uid, [prepago.loan_id.id], {'periods_to_pay': prepago.loan_id.periods_to_pay+prepago.numero_cuotas}, context=context)
            prestamo_obj.compute_loan_board(cr, uid, [prepago.loan_id.id], context=context)
        self.write(cr, uid, ids, {'state':'done'})
        return True
        
    def cancel(self, cr, uid, ids, context=None):
        cuotas_obj = self.pool.get('loan.move.line')
        prestamo_obj = self.pool.get('account.loan')
        for prepago in self.browse(cr, uid, ids, context=context):
            for cuota in prepago.loan_id.loan_move_line_ids:
                if cuota.prepaid_id.id == prepago.id:
                    cuotas_obj.cancel_move(cr, uid, [cuota.id], context=context)
                    cuotas_obj.unlink(cr, uid, [cuota.id], context=context)
                    prestamo_obj.write(cr, uid, [prepago.loan_id.id], {'periods_to_pay': prepago.loan_id.periods_to_pay-prepago.numero_cuotas}, context=context)
                    prestamo_obj.compute_loan_board(cr, uid, [prepago.loan_id.id], context=context)
        self.write(cr, uid, ids, {'state':'cancelled'})
        return True
    
    def unlink(self, cr, uid, ids, context=None):
        for prepago in self.browse(cr, uid, ids, context=context):
            if prepago.state not in ['draft']:
                raise osv.except_osv(_('Error !'),_("solo es posible borrar prepagos/desembolsos en estado borrador"))
        return super(account_loan_prepaid, self).unlink(cr, uid, ids, context=context)
        
    def create(self, cr, uid, vals, context=None):
        #agrega numero de secuencia
        vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'account.loan.prepaid.seq') or '/'
        result = super(account_loan_prepaid, self).create(cr, uid, vals, context=context)
        return result

class account_loan_distribution(osv.osv):
    _name = "account.loan.distribution"
    _description = "Distribucion Obligacion Financiera"
    
    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        res = [(r.id, '%s [%s %s]'%(r.account_analytic_id.name, r.rate, '%')) for r in self.browse(cr, uid, ids, context=context) ]
        return res
    
    def get_precision_rate():
        def change_digit_rate(cr):
            res = openerp.registry(cr.dbname).get('decimal.precision').precision_get(cr, SUPERUSER_ID, 'Account')
            return (16, res+2)
        return change_digit_rate
    
    _columns = {
        'account_analytic_id': fields.many2one('account.analytic.account', 'Centro de Costo', required=True),
        'loan_id': fields.many2one('account.loan', 'Obligacion Financiera', required=True, ondelete='cascade'),
        'name': fields.char('Comentario', size=256),
        'rate': fields.float('(%)', digits_compute=get_precision_rate(), required=True),
    }
    
    _defaults = {
        'rate': 100,
    }

class res_partner_bank(osv.osv):
    _inherit = "res.partner.bank" 
    
    _columns = {
        'oficina_nombre': fields.char('Nombre de la oficina', size=256),
        'director_id': fields.many2one('res.partner', 'Director de cuenta del banco'),
        'currency_id': fields.many2one('res.currency', 'Moneda'),
        'date_renovacion': fields.date('Fecha de renovacion de cupo'),
        'cupo_endeudamiento':fields.float('Cupo de endeudamiento', digits_compute= dp.get_precision('Account')),
        'obligaciones_financieras_ids': fields.one2many('account.loan', 'partner_bank_id', 'Obligaciones Financieras', readonly=True),
    }
    
#
