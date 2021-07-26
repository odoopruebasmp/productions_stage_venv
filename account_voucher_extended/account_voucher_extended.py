# -*- coding: utf-8 -*-
from openerp import models, fields
import pytz
import re
import time
import openerp
import openerp.service.report
import uuid
import collections
import babel.dates
from werkzeug.exceptions import BadRequest
from datetime import datetime, timedelta
from dateutil import parser
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from openerp import api
from openerp import tools, SUPERUSER_ID
from openerp.osv import fields as fields2, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _
from openerp.http import request
from operator import itemgetter
import openerp.addons.decimal_precision as dp
from openerp.addons.avancys_tools import report_tools
from openerp.exceptions import Warning

class res_company(models.Model):
    _inherit = "res.company"
    
    limit_ajuste_peso = fields.Float("Limite Ajuste al Peso", digits_compute=dp.get_precision('Account'), help="Esta es una politica de compañia, el sistema dentra en cuenta este valor, como valor maximo en la diferencia en la conciliacion de dos cuentas. Aplica para el proceso de conciliacion masiva y cruce de cuentas.")
    journal_ajustes_id = fields.Many2one('account.journal', string="Diario Ajuste al Peso", digits_compute=dp.get_precision('Account'), help="Diario para los movimientos de ajustes al peso")
    account_ajuste_id = fields.Many2one('account.account', string="Ganancia Ajuste al Peso", required=True, help="Cuenta para los movimientos de ajustes al peso")
    account_ajuste_id2 = fields.Many2one('account.account', string="Perdida Ajuste al Peso", required=True, help="Cuenta para los movimientos de ajustes al peso")

class payment_mode(models.Model):
    _inherit = "payment.mode"
    
    journal=fields.Many2one('account.journal', string='Diario', required=True, domain=[('type', 'in', ('bank','cash')),('recaudo','=',False)], help='Bank or Cash Journal for the Payment Mode')
    
    
class account_distribution_amount(models.Model):
    _name = "account.distribution.amount"

    account_id = fields.Many2one('account.account', string='Cuenta', required=True, domain=[('type','<>','view')])
    account_analytic_id = fields.Many2one('account.analytic.account', string='Centro de Costo')
    amount = fields.Float(string='Cantidad', digits= dp.get_precision('Account'), required=True)
    account_move_line_id = fields.Many2one('account.move.line', string='Distribucion de Cuentas')
    voucher_id = fields.Many2one('account.voucher', string='Voucher')
    name = fields.Char(string='Comentario', required=True)

class account_voucher_line(models.Model):
    _inherit = 'account.voucher.line'
    
    move_line_id = fields.Many2one('account.move.line', string='Journal Item', copy=False, required=True, ondelete='cascade')
    

class account_voucher(models.Model):
    _inherit = 'account.voucher'

    @api.model
    def copy(self, default=None):
        raise Warning("Por integridad de informacion este documento no puede ser duplicado.")



    @api.multi
    def _compute_text(self):
        for s in self:
            if s.id:
                numero = s.id
                voucher = s.env['account.voucher'].search([('id', '=', numero)])
                num2text = report_tools.avancys_amount_to_text_decimal(voucher.amount)
                s.num2text = num2text
                voucher.write({'num2text': num2text})

    account_amount_ids = fields.One2many('account.distribution.amount', 'voucher_id', string='Account Distributions')
    diferencia = fields.Float(string='Diferencia', digits= dp.get_precision('Account'), readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Cuenta Analitica')
    num2text = fields.Char(compute=_compute_text,string='Valor en Letras')

    @api.multi
    def borrar_seleccionados(self):
        self._cr.execute(''' UPDATE account_voucher_line set reconcile=False,amount=0.0 WHERE voucher_id = %s''',(self.id,))
        return True
       
    def onchange_date(self, cr, uid, ids, date, currency_id, payment_rate_currency_id, amount, company_id, context=None):
        datetime = date +' '+ '12:00:00'        
        
        res = super(account_voucher, self).onchange_date(cr, uid, ids, date=datetime, currency_id=currency_id, payment_rate_currency_id=payment_rate_currency_id, amount=amount, company_id=company_id, context=context)
        
        payment_rate_currency_id = self.pool.get('res.currency').browse(cr, uid, payment_rate_currency_id, context=context)
        company_id = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
        company_currency = company_id.currency_id
        
        if company_currency != payment_rate_currency_id:
            tasa_dia = self.pool.get('res.currency').tasa_dia(cr, uid, date, company_id, payment_rate_currency_id, context=context)
            res['value'].update({'payment_rate': tasa_dia,'payment_rate_currency_id':company_currency.id})        
        return res
    
    
    def onchange_account_amount_ids(self, cr, uid, ids, account_amount_ids, writeoff_amount, context=None):
        total_amount = 0
        if account_amount_ids:
            values = self.resolve_2many_commands(cr, uid, 'account_amount_ids', account_amount_ids, ['amount','account_id','account_analytic_id','name'], context=context)
            for val in values:
                total_amount += val['amount']
                    
        diferencia = writeoff_amount - total_amount
        res = {'value' :{'diferencia': diferencia}}
        return res
    

    def writeoff_move_line_get(self, cr, uid, voucher_id, line_total, move_id, name, company_currency, current_currency, context=None):
        currency_obj = self.pool.get('res.currency')
        move_line = {}
        move_line_obj = self.pool.get('account.move.line')
        voucher_brw = self.pool.get('account.voucher').browse(cr,uid,voucher_id,context)
        company_id = voucher_brw.company_id
        line_total2=0.0
        if voucher_brw.payment_option == 'with_writeoff':
            line_total2 = voucher_brw.writeoff_amount
        else:
            if abs(line_total) <= company_id.limit_ajuste_peso:
                line_total2 = line_total
                
        current_currency_obj = voucher_brw.currency_id or voucher_brw.journal_id.company_id.currency_id
        if not currency_obj.is_zero(cr, uid, current_currency_obj, line_total2):
            diff = line_total2
            account_id = False
            account_analytic_id = False
            write_off_name = ''
            write_off_flag = True
            if voucher_brw.payment_option == 'with_writeoff':
                total_amount = 0.0
                for line2 in voucher_brw.account_amount_ids:
                    total_amount += line2.amount
                total_amount = currency_obj.round(cr, uid, current_currency_obj, total_amount)
                if abs(total_amount) != currency_obj.round(cr, uid, current_currency_obj, abs(line_total2)):
                    raise osv.except_osv(_('Configuration !'),
                                         _("la cantidad distribuida en las cuentas es %s y la diferencia es %s. ambas tienen que ser igual !") % (total_amount, line_total2))
                cont = 0
                diff2 = -line_total

                for line2 in voucher_brw.account_amount_ids:
                    cont += 1                
                    multicurrency = company_currency != current_currency and current_currency or False
                    amount = line2.amount
                    
                    if voucher_brw.type == 'receipt':
                        diff2 += voucher_brw.payment_rate*amount
                    else:
                        diff2 -= voucher_brw.payment_rate*amount
                        
                    if voucher_brw.type == 'receipt':
                        credit= line2.amount > 0 and amount or 0.0
                        debit= line2.amount < 0 and amount or 0.0
                    else:
                        credit= line2.amount < 0 and amount or 0.0
                        debit= line2.amount > 0 and amount or 0.0
                        
                    
                    if multicurrency:
                        debit = voucher_brw.payment_rate*debit
                        credit= voucher_brw.payment_rate*credit
                        currency_amount = line2.amount
                        if credit > 0:
                            currency_amount = abs(currency_amount)*-1
                    
                    if voucher_brw.type == 'receipt':
                        if len(voucher_brw.account_amount_ids) == cont:
                            if not currency_obj.is_zero(cr, uid, current_currency_obj, diff2):
                                if line2.amount > 0:
                                    credit += diff2
                                else:
                                    debit += diff2
                    else:
                        if len(voucher_brw.account_amount_ids) == cont:
                            if not currency_obj.is_zero(cr, uid, current_currency_obj, diff2):
                                if line2.amount < 0:
                                    credit += diff2
                                else:
                                    debit += diff2           
                                
                    vals = {
                        'name': line2.name,
                        'account_id': line2.account_id.id,
                        'analytic_account_id': line2.account_analytic_id and line2.account_analytic_id.id or False,
                        'move_id': move_id,
                        'partner_id': voucher_brw.partner_id.id,
                        'date': voucher_brw.date,
                        'credit': abs(credit),
                        'debit': abs(debit),
                        'amount_currency': multicurrency and currency_amount,
                        'currency_id': multicurrency,
                        'period_id': line2.voucher_id.period_id.id,
                    }
                    move_line_obj.create(cr, uid, vals)
                    write_off_flag = False

            elif voucher_brw.type in ('sale', 'receipt'):
                if line_total2 > 0.0:
                    account_id = company_id.account_ajuste_id.id
                else:
                    account_id = company_id.account_ajuste_id2.id
            elif voucher_brw.type in ('purchase', 'payment'):
                if line_total2 < 0.0:
                    account_id = company_id.account_ajuste_id.id
                else:
                    account_id = company_id.account_ajuste_id2.id
                
            if write_off_flag:
                move_line = {
                    'name': write_off_name or name,
                    'account_id': account_id,
                    'move_id': move_id,
                    'partner_id': voucher_brw.partner_id.id,
                    'date': voucher_brw.date,
                    'credit': diff > 0 and diff or 0.0,
                    'debit': diff < 0 and -diff or 0.0,
                    'amount_currency': company_currency <> current_currency and voucher_brw.writeoff_amount or False,
                    'currency_id': company_currency <> current_currency and current_currency or False,
                    'analytic_account_id': voucher_brw.analytic_id and voucher_brw.analytic_id.id or False,
                }
        return move_line
    
    def _make_journal_search(self, cr, uid, ttype, context=None):
        return False

    # Se sobreescribe funcion del account_voucher para restriccion en lineas con valor 0 de las ordenes de pago
    def recompute_voucher_lines(self, cr, uid, ids, partner_id, journal_id, price, currency_id, ttype, date, context=None):
        """
        Returns a dict that contains new values and context

        @param partner_id: latest value from user input for field partner_id
        @param args: other arguments
        @param context: context arguments, like lang, time zone

        @return: Returns a dict which contains new values, and context
        """
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

        if context is None:
            context = {}
        context_multi_currency = context.copy()

        currency_pool = self.pool.get('res.currency')
        move_line_pool = self.pool.get('account.move.line')
        partner_pool = self.pool.get('res.partner')
        journal_pool = self.pool.get('account.journal')
        line_pool = self.pool.get('account.voucher.line')

        #set default values
        default = {
            'value': {'line_dr_ids': [], 'line_cr_ids': [], 'pre_line': False},
        }

        # drop existing lines
        line_ids = ids and line_pool.search(cr, uid, [('voucher_id', '=', ids[0])])
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            if line.type == 'cr':
                default['value']['line_cr_ids'].append((2, line.id))
            else:
                default['value']['line_dr_ids'].append((2, line.id))

        if not partner_id or not journal_id:
            return default

        journal = journal_pool.browse(cr, uid, journal_id, context=context)
        partner = partner_pool.browse(cr, uid, partner_id, context=context)
        currency_id = currency_id or journal.company_id.currency_id.id

        total_credit = 0.0
        total_debit = 0.0
        account_type = None
        if context.get('account_id'):
            account_type = self.pool['account.account'].browse(cr, uid, context['account_id'], context=context).type
        if ttype == 'payment':
            if not account_type:
                account_type = 'payable'
            total_debit = price or 0.0
        else:
            total_credit = price or 0.0
            if not account_type:
                account_type = 'receivable'

        if not context.get('move_line_ids', False):
            ids = move_line_pool.search(cr, uid, [('state','=','valid'), ('account_id.type', '=', account_type), ('reconcile_id', '=', False), ('partner_id', '=', partner_id)], context=context)
        else:
            ids = context['move_line_ids']
        invoice_id = context.get('invoice_id', False)
        company_currency = journal.company_id.currency_id.id
        move_lines_found = []

        #order the lines by most old first
        ids.reverse()
        account_move_lines = move_line_pool.browse(cr, uid, ids, context=context)

        #compute the total debit/credit and look for a matching open amount or invoice
        for line in account_move_lines:
            if _remove_noise_in_o2m():
                continue

            if invoice_id:
                if line.invoice.id == invoice_id:
                    #if the invoice linked to the voucher line is equal to the invoice_id in context
                    #then we assign the amount on that line, whatever the other voucher lines
                    move_lines_found.append(line.id)
            elif currency_id == company_currency:
                #otherwise treatments is the same but with other field names
                if line.amount_residual == price:
                    #if the amount residual is equal the amount voucher, we assign it to that voucher
                    #line, whatever the other voucher lines
                    move_lines_found.append(line.id)
                    break
                #otherwise we will split the voucher amount on each line (by most old first)
                total_credit += line.credit or 0.0
                total_debit += line.debit or 0.0
            elif currency_id == line.currency_id.id:
                if line.amount_residual_currency == price:
                    move_lines_found.append(line.id)
                    break
                total_credit += line.credit and line.amount_currency or 0.0
                total_debit += line.debit and line.amount_currency or 0.0

        remaining_amount = price
        #voucher line creation
        for line in account_move_lines:

            if _remove_noise_in_o2m():
                continue

            if line.currency_id and currency_id == line.currency_id.id:
                amount_original = abs(line.amount_currency)
                amount_unreconciled = abs(line.amount_residual_currency)
            else:
                #always use the amount booked in the company currency as the basis of the conversion into the voucher currency
                amount_original = currency_pool.compute(cr, uid, company_currency, currency_id, line.credit or line.debit or 0.0, context=context_multi_currency)
                amount_unreconciled = currency_pool.compute(cr, uid, company_currency, currency_id, abs(line.amount_residual), context=context_multi_currency)
            if amount_original == 0 and amount_unreconciled == 0:
                continue
            line_currency_id = line.currency_id and line.currency_id.id or company_currency
            rs = {
                'name':line.move_id.name,
                'type': line.credit and 'dr' or 'cr',
                'move_line_id':line.id,
                'account_id':line.account_id.id,
                'amount_original': amount_original,
                'amount': (line.id in move_lines_found) and min(abs(remaining_amount), amount_unreconciled) or 0.0,
                'date_original':line.date,
                'date_due':line.date_maturity,
                'amount_unreconciled': amount_unreconciled,
                'currency_id': line_currency_id,
            }
            remaining_amount -= rs['amount']
            #in case a corresponding move_line hasn't been found, we now try to assign the voucher amount
            #on existing invoices: we split voucher amount by most old first, but only for lines in the same currency
            if not move_lines_found:
                if currency_id == line_currency_id:
                    if line.credit:
                        amount = min(amount_unreconciled, abs(total_debit))
                        rs['amount'] = amount
                        total_debit -= amount
                    else:
                        amount = min(amount_unreconciled, abs(total_credit))
                        rs['amount'] = amount
                        total_credit -= amount

            if rs['amount_unreconciled'] == rs['amount']:
                rs['reconcile'] = True

            if rs['type'] == 'cr':
                default['value']['line_cr_ids'].append(rs)
            else:
                default['value']['line_dr_ids'].append(rs)

            if len(default['value']['line_cr_ids']) > 0:
                default['value']['pre_line'] = 1
            elif len(default['value']['line_dr_ids']) > 0:
                default['value']['pre_line'] = 1
            default['value']['writeoff_amount'] = self._compute_writeoff_amount(cr, uid, default['value']['line_dr_ids'], default['value']['line_cr_ids'], price, ttype)
        return default