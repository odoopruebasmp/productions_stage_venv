# -*- coding: utf-8 -*-
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
from openerp import SUPERUSER_ID
from openerp import models, fields, api, _
from openerp.osv import osv
import openerp.addons.decimal_precision as dp
import time
from openerp.addons.avancys_orm import avancys_orm
from openerp.exceptions import Warning


class account_voucher(models.Model):
    _inherit = "account.voucher"
        
    #SE MODIFICA ESTA FUNCION PARA QUE NO LLEVE CUENTAS DE DIFERENCIA EN CAMBIO PARCIALES
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
            ids = move_line_pool.search(cr, uid, [('state','=','valid'), ('account_id.type', '=', account_type), ('reconcile_id', '=', False), ('partner_id', '=', partner_id),('not_voucher', '!=', True),('move_change_id', '=', False)], context=context)
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

            #AGREGA POR DEFAULT EL CHECK RECONCILE A LOS VALORES EN CERO
            if rs['amount_unreconciled'] == rs['amount'] and rs['amount'] > 0.0:
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
            
        # CRUCE DE CUENTAS
        if context.get('type') == 'crossing':
            values_2 = super(account_voucher, self).recompute_voucher_lines(cr, uid, ids, partner_id, journal_id, price, currency_id, 'payment', date, context={})
            default['value']['line_cr_ids'] += values_2['value']['line_cr_ids']
            default['value']['line_dr_ids'] += values_2['value']['line_dr_ids']
        return default
    
    #SE SOBRE-ESCRIBE LA FUNCTION DEL /ODOO/ADDONS/ACCOUNT_VOUCHER/ACCOUNT_VOUCHER.PY POR EFICIENCIA
    def action_move_line_create(self, cr, uid, ids, context=None):
        '''
        Confirm the vouchers given in ids and create the journal entries for each of them
        '''
        if context is None:
            context = {}
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        seq_obj = self.pool.get('ir.sequence')
        currency_obj = self.pool.get('res.currency')
        for voucher in self.browse(cr, uid, ids, context=context):
            local_context = dict(context, force_company=voucher.journal_id.company_id.id)
            if voucher.move_id:
                continue
            company_currency = self._get_company_currency(cr, uid, voucher.id, context)
            current_currency = self._get_current_currency(cr, uid, voucher.id, context)
            currency_id = currency_obj.browse(cr, uid, company_currency, context=context)
            # we select the context to use accordingly if it's a multicurrency case or not
            context = self._sel_context(cr, uid, voucher.id, context)
            # But for the operations made by _convert_amount, we always need to give the date in the context
            ctx = context.copy()
            ctx.update({'date': voucher.date})
            # Create the account move record.
            move_id = move_pool.create(cr, uid, self.account_move_get(cr, uid, voucher.id, context=context), context=context)
            # Get the name of the account_move just created
            name = move_pool.browse(cr, uid, move_id, context=context).name
            # Create the first line of the voucher
            move_line_id = move_line_pool.create(cr, uid, self.first_move_line_get(cr,uid,voucher.id, move_id, company_currency, current_currency, local_context), local_context)  
            move_line_brw = move_line_pool.browse(cr, uid, move_line_id, context=context)            
            line_total = move_line_brw.debit - move_line_brw.credit
            rec_list_ids = []
            if voucher.type == 'sale':
                line_total = line_total - self._convert_amount(cr, uid, voucher.tax_amount, voucher.id, context=ctx)
            elif voucher.type == 'purchase':
                line_total = line_total + self._convert_amount(cr, uid, voucher.tax_amount, voucher.id, context=ctx)
            # Create one move line per voucher line where amount is not 0.0
            line_total, rec_list_ids = self.voucher_move_line_create(cr, uid, voucher.id, line_total, move_id, company_currency, current_currency, context)

            # Create the writeoff line if needed
            ml_writeoff = self.writeoff_move_line_get(cr, uid, voucher.id, line_total, move_id, name, company_currency, current_currency, local_context)
            if ml_writeoff:
                move_line_pool.create(cr, uid, ml_writeoff, local_context)
            # We post the voucher.
            self.write(cr, uid, [voucher.id], {
                'move_id': move_id,
                'state': 'posted',
                'number': name,
            })
            if voucher.journal_id.entry_posted:
                move_pool.post(cr, uid, [move_id], context={})
            # We automatically reconcile the account move lines.
            reconcile = False
            cont = 1
            
            for rec_ids in rec_list_ids:
                cont+=1
                if len(rec_ids) >= 2:                     
                    new_ids_dc = self.pool.get('account.move.line').browse(cr, uid, rec_ids, context=context)
                    n_debit = 0
                    n_credit = 0                    
                    for i in new_ids_dc:
                        n_debit += i.debit > 0.0 and i.debit
                        n_credit += i.credit > 0.0 and i.credit
                        if i.reconcile_partial_id:
                            for line in i.reconcile_partial_id.line_partial_ids:
                                if line.id != i.id:
                                    n_debit += line.debit > 0.0 and line.debit
                                    n_credit += line.credit > 0.0 and line.credit
                                    rec_ids.append(line.id)
                    
                    is_zero = currency_id.is_zero(n_credit - n_debit)
                    if n_credit > 0 and n_debit > 0 and not is_zero:
                        print "conciliacion Parcial"
                        type = 'Parcial'
                        seq = seq_obj.search(cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                        name = seq_obj.next_by_id(cr, SUPERUSER_ID, seq[0], context=context)
                        cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES 
                                (%s,%s,%s) RETURNING id''' ,
                                (time.strftime('%Y-%m-%d'),name,type))
                        r_id = cr.fetchone()[0]
                        move_line_pool.write(cr, SUPERUSER_ID, rec_ids, {'reconcile_partial_id': r_id, 'reconcile_ref':name})
                            
                    elif n_credit > 0 and n_debit > 0 and is_zero:
                        print "conciliacion Total"
                        type = 'Total'
                        seq = seq_obj.search(cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                        name = seq_obj.next_by_id(cr, SUPERUSER_ID, seq[0], context=context)
                        cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES 
                                (%s,%s,%s) RETURNING id''' ,
                                (time.strftime('%Y-%m-%d'),name,type))
                        r_id = cr.fetchone()[0]
                        cr.execute(''' UPDATE account_move_line SET reconcile_partial_id=%s, reconcile_id=%s, reconcile_ref=%s WHERE id in %s''',(None, r_id,name,tuple(rec_ids)))
                        move_line_pool.write(cr, SUPERUSER_ID, rec_ids, {'reconcile_id': r_id,'reconcile_ref':name})

        if voucher.line_dr_ids:
            for v_ln in voucher.line_dr_ids:
                if v_ln.state == 'posted':
                    expense_name = v_ln.move_line_id.name
                    state = ['paid']
                    cr.execute('''UPDATE hr_expense_expense SET state = %s WHERE name = %s''', (state[0],expense_name))

        return True
    
    
    # def _get_exchange_lines(self, cr, uid, line, move_id, amount_residual, company_currency, current_currency, context=None):
        # print "wwwwwwwwwwwww"
        # print line.voucher_id.type
        # print amount_residual
        # print line.move_line_id.amount_change
        # print ""
        # if line.voucher_id.type == 'payment':
            # amount_residual = amount_residual +  line.move_line_id.amount_change*(line.amount/line.amount_unreconciled)
        # elif line.voucher_id.type == 'receipt':
            # amount_residual = amount_residual -  line.move_line_id.amount_change*(line.amount/line.amount_unreconciled)
        # elif line.voucher_id.type == 'crossing':
            # amount_residual = amount_residual -  line.move_line_id.amount_change*(line.amount/line.amount_unreconciled)
        # res = super(account_voucher, self)._get_exchange_lines(cr, uid, line=line, move_id=move_id, amount_residual=amount_residual, company_currency= company_currency, current_currency=current_currency, context=context)        
        # return res
         
        
    
    def voucher_move_line_create(self, cr, uid, voucher_id, line_total, move_id, company_currency, current_currency, context=None):
        '''
        Create one account move line, on the given account move, per voucher line where amount is not 0.0.
        It returns Tuple with tot_line what is total of difference between debit and credit and
        a list of lists with ids to be reconciled with this format (total_deb_cred,list_of_lists).

        :param voucher_id: Voucher id what we are working with
        :param line_total: Amount of the first line, which correspond to the amount we should totally split among all voucher lines.
        :param move_id: Account move wher those lines will be joined.
        :param company_currency: id of currency of the company to which the voucher belong
        :param current_currency: id of currency of the voucher
        :return: Tuple build as (remaining amount not allocated on voucher lines, list of account_move_line created in this method)
        :rtype: tuple(float, list of int)
        '''
        if context is None:
            context = {}
        move_line_obj = self.pool.get('account.move.line')
        currency_obj = self.pool.get('res.currency')
        tax_obj = self.pool.get('account.tax')
        tot_line = line_total
        rec_lst_ids = []

        date = self.read(cr, uid, [voucher_id], ['date'], context=context)[0]['date']
        ctx = context.copy()
        ctx.update({'date': date})
        voucher = self.pool.get('account.voucher').browse(cr, uid, voucher_id, context=ctx)
        voucher_currency = voucher.journal_id.currency or voucher.company_id.currency_id
        ctx.update({
            'voucher_special_currency_rate': voucher_currency.rate * voucher.payment_rate ,
            'voucher_special_currency': voucher.payment_rate_currency_id and voucher.payment_rate_currency_id.id or False,})
        prec = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
        
        for line in voucher.line_ids.filtered(lambda x: x.amount > 0.0 or x.reconcile == True):
            #create one move line per voucher line where amount is not 0.0
            # AND (second part of the clause) only if the original move line was not having debit = credit = 0 (which is a legal value)
            if not line.amount and not (line.move_line_id and not float_compare(line.move_line_id.debit, line.move_line_id.credit, precision_digits=prec) and not float_compare(line.move_line_id.debit, 0.0, precision_digits=prec)):
                continue
            # convert the amount set on the voucher line into the currency of the voucher's company
            # this calls res_curreny.compute() with the right context, so that it will take either the rate on the voucher if it is relevant or will use the default behaviour
            amount = self._convert_amount(cr, uid, line.untax_amount or line.amount, voucher.id, context=ctx)
            # if the amount encoded in voucher is equal to the amount unreconciled, we need to compute the
            # currency rate difference
            
            if line.amount == line.amount_unreconciled:
                if not line.move_line_id:
                    raise osv.except_osv(_('Wrong voucher line'),_("The invoice you are willing to pay is not valid anymore."))
                sign = line.type =='dr' and -1 or 1
                currency_rate_difference = sign * (line.move_line_id.amount_residual - amount)
            elif voucher.journal_id.currency  and voucher.journal_id.currency != voucher.company_id.currency_id:                
                amount_residual = line.move_line_id.amount_residual                
                sign = line.type =='dr' and -1 or 1            
                currency_rate_difference = sign*(line.amount*(amount_residual/line.move_line_id.amount_residual_currency)-amount)
            else:
                currency_rate_difference = 0.0
            
            move_line = {
                'journal_id': voucher.journal_id.id,
                'period_id': voucher.period_id.id,
                'name': line.name or '/',
                'account_id': line.account_id.id,
                'move_id': move_id,
                'partner_id': voucher.partner_id.id,
                'currency_id': line.move_line_id and (company_currency <> line.move_line_id.currency_id.id and line.move_line_id.currency_id.id) or False,
                'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
                'quantity': 1,
                'credit': 0.0,
                'debit': 0.0,
                'date': voucher.date
            }
            if amount < 0:
                amount = -amount
                if line.type == 'dr':
                    line.type = 'cr'
                else:
                    line.type = 'dr'

            if (line.type=='dr'):
                tot_line += amount
                move_line['debit'] = amount
            else:
                tot_line -= amount
                move_line['credit'] = amount

            if voucher.tax_id and voucher.type in ('sale', 'purchase'):
                move_line.update({
                    'account_tax_id': voucher.tax_id.id,
                })

            # compute the amount in foreign currency
            foreign_currency_diff = 0.0
            amount_currency = False
            if line.move_line_id:
                # We want to set it on the account move line as soon as the original line had a foreign currency
                if line.move_line_id.currency_id and line.move_line_id.currency_id.id != company_currency:
                    # we compute the amount in that foreign currency.
                    if line.move_line_id.currency_id.id == current_currency:
                        # if the voucher and the voucher line share the same currency, there is no computation to do
                        sign = (move_line['debit'] - move_line['credit']) < 0 and -1 or 1
                        amount_currency = sign * (line.amount)
                    else:
                        # if the rate is specified on the voucher, it will be used thanks to the special keys in the context
                        # otherwise we use the rates of the system
                        amount_currency = currency_obj.compute(cr, uid, company_currency, line.move_line_id.currency_id.id, move_line['debit']-move_line['credit'], context=ctx)
                if line.amount == line.amount_unreconciled:
                    foreign_currency_diff = line.move_line_id.amount_residual_currency - abs(amount_currency)

            move_line['amount_currency'] = amount_currency
            voucher_line = move_line_obj.create(cr, uid, move_line)
            rec_ids = [voucher_line, line.move_line_id.id]

            if not currency_obj.is_zero(cr, uid, voucher.company_id.currency_id, currency_rate_difference):
                # Change difference entry in company currency
                exch_lines = self._get_exchange_lines(cr, uid, line, move_id, currency_rate_difference, company_currency, current_currency, context=context)
                exch_lines[0].update({'not_voucher': True})
                exch_lines[1].update({'not_voucher': True})
                new_id = move_line_obj.create(cr, uid, exch_lines[0],context)
                move_line_obj.create(cr, uid, exch_lines[1], context)
                rec_ids.append(new_id)
            if line.move_line_id and line.move_line_id.currency_id and not currency_obj.is_zero(cr, uid, line.move_line_id.currency_id, foreign_currency_diff):
                # Change difference entry in voucher currency
                move_line_foreign_currency = {
                    'journal_id': line.voucher_id.journal_id.id,
                    'period_id': line.voucher_id.period_id.id,
                    'name': _('change')+': '+(line.name or '/'),
                    'account_id': line.account_id.id,
                    'move_id': move_id,
                    'partner_id': line.voucher_id.partner_id.id,
                    'currency_id': line.move_line_id.currency_id.id,
                    'amount_currency': (-1 if line.type == 'cr' else 1) * foreign_currency_diff,
                    'quantity': 1,
                    'credit': 0.0,
                    'debit': 0.0,
                    'date': line.voucher_id.date,
                }
                new_id = move_line_obj.create(cr, uid, move_line_foreign_currency, context=context)
                rec_ids.append(new_id)
            if line.move_line_id.id:
                rec_lst_ids.append(rec_ids)
            
            #AGREGA LAS LINEAS DE DIFERENCIA EN CAMBIO       
            cont = 0
            if not line.amount and line.reconcile and line.move_line_id and not (line.move_line_id.id in rec_lst_ids[0]):
                for m in rec_lst_ids:
                    if line.move_line_id.move_change_id.id in m:
                        rec_lst_ids[cont].append(line.move_line_id.id)   
                    cont +=1    
                        
        return (tot_line, rec_lst_ids)
    
    
class account_period(models.Model):
    _inherit = "account.period"
    
    change_id = fields.Many2one('change.difference', string='Generador de Diferencia en Cambio')
    
    
class account_account(models.Model):
    _inherit = "account.account"
    
    @api.one
    @api.depends('account_change_ids', 'account_change_ids.state', 'diff', 'diff_process', 'diff_partner_id', 'account_diff_niif_id')       
    def _amount_divisa(self):
        account_id = self._context.get('id', False) or self.id or False
        account_diff_niif_id = self.account_diff_niif_id and self.account_diff_niif_id.id or False
        if account_id and account_diff_niif_id and self.currency_id and self.diff == "cuenta":
            amount_change = 0.0
            if self.account_change_ids:
                
                self._cr.execute('''SELECT
                                        SUM(debit - credit)
                                    FROM
                                        account_move_line
                                    WHERE  
                                        account_id = %s 
                                        AND account_change_id = %s
                                        AND state = 'valid' ''',
                                (account_diff_niif_id,account_id)) 
                result = self._cr.fetchall()
                if result:
                    amount_change = result[0]
                    if isinstance(amount_change, (list, tuple)):
                        amount_change = float(amount_change[0] or 0.0)
                    else:
                        amount_change = float(amount_change or 0.0)
                        
                
            
            diff_amount_local = 0.0
            diff_amount_divisa = 0.0
            diff_amount_trm = 0.0
            self._cr.execute('''SELECT
                                    SUM(debit-credit),
                                    SUM(amount_currency)
                                FROM
                                    account_move_line
                                WHERE  
                                    account_id=%s
                                    AND currency_id=%s
                                    AND state = 'valid' ''',
                            (account_id,self.currency_id.id)) 
            result = self._cr.fetchall()[0] or 0.0
            if result:
                diff_amount_local = result[0]
                if isinstance(diff_amount_local, (list, tuple)):
                    diff_amount_local = diff_amount_local[0]
                else:
                    diff_amount_local = diff_amount_local
                
                diff_amount_divisa = result[1]
                if isinstance(diff_amount_divisa, (list, tuple)):
                    diff_amount_divisa = diff_amount_divisa[0]
                else:
                    diff_amount_divisa = diff_amount_divisa
            
            self.diff_amount_local = diff_amount_local
            self.diff_amount_divisa = diff_amount_divisa
            if diff_amount_divisa:
                diff_amount_trm = (diff_amount_local+amount_change)/diff_amount_divisa
            self.diff_amount_trm = diff_amount_trm
            self.amount_change = amount_change
                            
            
    
    
    diff = fields.Selection([('cuenta', 'Cuenta'),('movimiento', 'Movimiento')], string='Diferencia en Cambio ', help="Si este campo es seleccionado, el sistema tendra en cuenta esta cuenta para el proceso de diferencia en cambio, donde se calculara en base a los registros en moneda igual a la modena secundaria configurada")
    naturaleza = fields.Selection([('debito', 'Debito'),('credito', 'Credito')], string='Naturaleza', help="Este campo indica al sistema la naturaleza de la cuenta, criterio que sera tenido en cuenta para enviar al ingreso o gasto la diferencia en cmabio optenida en cada proceso")
    amount_change = fields.Float(string='Diferencia Acumulada', digits=dp.get_precision('Account'), readonly=True, compute="_amount_divisa", store=True, help="Diferencia en cambio acumulada, es el resultado de todos los procesos ejecutados para esta cuenta, donde podremos conocer el balance de diferencia en cambio para esta cuenta. Su significado dependera de la naturaleza de la cuenta, Positivo + Naturaleza(Debito) => Ganancia, Negativo + Naturaleza(Debito) => Perdida, Positivo + Naturaleza(Credito) => Perdida, Negativo + Naturaleza(Credito) => Ganancia")
    diff_amount_local = fields.Float(string='Saldo Local', digits=dp.get_precision('Account'), readonly=True, compute="_amount_divisa", store=True, help="Debitos menos creditos de los movimientos con divisa igual a la Divisa secundaria configurada")
    diff_amount_divisa = fields.Float(string='Saldo divisa', digits=dp.get_precision('Account'), readonly=True, compute="_amount_divisa", store=True, help="Sumatoria del balance de los registros con divisa igual a la divisa secundaria configurada")
    diff_amount_trm = fields.Float(string='TRM', digits=dp.get_precision('Account'), readonly=True, compute="_amount_divisa", store=True, help="Esta es la TRM de la moneda secundaria configurada, es igual a:  'Saldo Local' / 'Saldo Divisa' ")
    account_diff_niif_id = fields.Many2one('account.account', string='Cuenta Consolidada NIIF', help="Esta cuenta es la que el sistema tendra en cuenta para calcular el valor acumulado y afectar el plan contable.", domain="[('niif','=',True),('type','!=','view')]")
    account_change_ids = fields.One2many('account.move.line', 'account_change_id', string='Movimientos de Diferencia en Cambio', readonly=True, help="Estos son los movimientos de diferencia en cambio de la presente cuenta")
    account_analytic_change_id = fields.Many2one('account.analytic.account', string='Cuenta Analitica', help="Si se ingresa, los registros de diferencia en cambio quedaran asociados a esta cuenta analitica, de lo contrario sera Vacio")
    diff_partner_id = fields.Many2one('res.partner', string='Tercero', help="Si se ingresa, los registros de diferencia en cambio quedaran asociados a este tercero, de lo contrario queda asociado al tercero de la compañia")
    account_income_niif_id = fields.Many2one('account.account', string='Cuenta Ingresos NIIF', help="Esta cuenta es la que el sistema utiliza cuando es un mayor valor para la compania", domain="[('niif','=',True),('type','!=','view')]")
    account_expense_niif_id = fields.Many2one('account.account', string='Cuenta Gasto NIIF', help="Esta cuenta es la que el sistema utiliza cuando es un menor valor para la compania", domain="[('niif','=',True),('type','!=','view')]")
    diff_process = fields.Char(string="Ultimo Proceso", readonly=True)
    change_ids = fields.Many2many('change.difference', string="Cuentas")
    

class account_move_line(models.Model):
    _inherit = "account.move.line"        
    
    @api.one
    @api.depends('move_change_ids', 'move_change_ids.state', 'ref', 'ref1', 'ref2', 'diff_process','state')       
    def _amount_divisa(self):
        move_line_pool = self.pool.get('account.move.line')
        move_id = self._context.get('move_id', False) or self.id or False
        rec_ids=[]
        if move_id and self.currency_id:
            diff_amount_trm = 0.0
            diff_amount_local1 = 0.0
            diff_amount_divisa1 = 0.0
            amount_change = 0.0
            amount_change1= 0.0
            diff_amount_local = self.debit - self.credit
            diff_amount_divisa = self.amount_currency
            if self.reconcile_partial_id:
                diff_amount_divisa
                if (self.account_id.naturaleza == 'debito' and diff_amount_divisa > 0.0) or (self.account_id.naturaleza == 'credito' and diff_amount_divisa < 0.0):                     
                    for move_reconcile in self.reconcile_partial_id.line_partial_ids:
                        if move_reconcile.id != self.id:
                            diff_amount_local += move_reconcile.debit - move_reconcile.credit
                            diff_amount_divisa += move_reconcile.amount_currency
            
            #if self.move_change_ids:
                #self._cr.execute('''SELECT
                                        #SUM(debit-credit),
                                        #SUM(amount_currency)
                                    #FROM
                                        #account_move_line
                                    #WHERE  
                                        #account_id = %s
                                        #AND move_change_id = %s
                                        #AND state = 'valid' ''',
                            #(self.account_id.id,move_id)) 
                #result = self._cr.fetchall()[0]
                #if result:
                    #amount_change = result[0]
                    #if isinstance(amount_change, (list, tuple)):
                        #amount_change = float(amount_change[0] or 0.0)
                    #else:
                        #amount_change = float(amount_change or 0.0)
                    
                    #diff_amount_divisa1 = result[1]
                    #if isinstance(diff_amount_divisa1, (list, tuple)):
                        #diff_amount_divisa = diff_amount_divisa + float(diff_amount_divisa1[0] or 0.0)
                    #else:
                        #diff_amount_divisa = diff_amount_divisa + float(diff_amount_divisa1 or 0.0)
            
            #diff_amount_local = diff_amount_local + amount_change
            
            
            self.diff_amount_local = diff_amount_local
            self.diff_amount_divisa = diff_amount_divisa
            if diff_amount_divisa:
                diff_amount_trm = diff_amount_local/diff_amount_divisa
            self.diff_amount_trm = diff_amount_trm
            self.amount_change = amount_change
    
    
    change_id = fields.Many2one('change.difference', string='Generador de Diferencia en Cambio')
    move_change_id = fields.Many2one('account.move.line', string='Movimiento Relacionado')
    account_change_id = fields.Many2one('account.account', string='Cuenta Relacionado')
    move_change_ids = fields.One2many('account.move.line', 'move_change_id', string='Movimientos de Diferencia en Cambio')
    amount_change = fields.Float(string='Diferencia Acumulada', digits=dp.get_precision('Account'), readonly=True, compute="_amount_divisa", store=True)
    diff_amount_local = fields.Float(string='Saldo Local', digits=dp.get_precision('Account'), readonly=True, compute="_amount_divisa", store=True)
    diff_amount_divisa = fields.Float(string='Saldo Divisa', digits=dp.get_precision('Account'), readonly=True, compute="_amount_divisa" , store=True)
    diff_amount_trm = fields.Float(string='TRM', digits=dp.get_precision('Account'), readonly=True, compute="_amount_divisa", store=True)
    diff_process = fields.Char(string="Ultimo Proceso", readonly=True)
    change_ids = fields.Many2many('change.difference', string="Cuentas")
    change_not = fields.Boolean(string='No Diff', help="Este campo permite realizar una excepcion, y aunque el registro cumpla con las condiciones del proceso de diferencia en cambio, no ejecutara el procedimiento.")
    not_voucher = fields.Boolean(string="No aplica para pagos y recaudos")

    
class account_analytic_line(models.Model):
    _inherit = "account.analytic.line"
    
    change_id = fields.Many2one('change.difference', string='Generador de Diferencia en Cambio')


class account_move(models.Model):
    _inherit = "account.move"
    
    diff_process = fields.Many2one('change.difference', string='Generador de Diferencia en Cambio')

        
class change_difference(models.Model):
    _name = 'change.difference'
    _inherit = ['mail.thread']
        
    @api.one
    @api.depends('date')       
    def _period(self):
        if self.date:
            period_id = self.env['account.period'].search([('date_start','<=', self.date),('date_stop','>=', self.date),('state','=', 'draft')])
            if not period_id:
                raise osv.except_osv(_('Error !'), _("No existe un periodo Abierto parala fecha '%s'") % (self.date))
            self.period_id = period_id.id
            
    @api.onchange('date', 'currency_id')
    def _rate(self):
        if self.date and self.currency_id:
            rate = 0.0
            rate = self.env['res.currency.rate'].search([('date_sin_hora','=',self.date),('currency_id','=',self.currency_id.id)]).rate_inv
            if rate == 0.0:
                raise osv.except_osv(_('Error !'), _("No existe un una tasa configurada para la fecha '%s' en la divisa '%s'") % (self.date,self.currency_id.name))
            self.rate = rate
            
    name = fields.Char(string='Name', readonly=True)
    state = fields.Selection([('draft', 'Nuevo'),('confirmed', 'Confirmado'),('done', 'Realizado')], 'Estado', readonly=True, select=True, default="draft", track_visibility='onchange')
    period_id = fields.Many2one('account.period', compute="_period", string='Periodo', store=True)
    date = fields.Date(string='Fecha', default=fields.datetime.now(), readonly=True, required=True, states={'draft':[('readonly',False)]})
    rate=fields.Float(string='Tasa', digits=dp.get_precision('Exchange Precision'), readonly=True, default=1, required=True, states={'draft':[('readonly',False)]})
    line_ids = fields.One2many('account.move.line', 'change_id', string='Movimientos', readonly=True)
    line_analytic_ids = fields.One2many('account.analytic.line', 'change_id', string='Lineas Analiticas', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, readonly=True, states={'draft':[('readonly',False)]})
    journal_id = fields.Many2one('account.journal', string='Diario', required=True, readonly=True, states={'draft':[('readonly',False)]}, domain="[('niif','=',True)]")
    move_ids = fields.Many2many('account.move.line', string="Movimiento")
    account_ids = fields.Many2many('account.account', string="Cuentas")
    
    
    @api.multi
    def confirmar(self):
        sequence_obj = self.env['ir.sequence']
        number_seq = sequence_obj.get('difference.change')
        return self.write({'state': 'confirmed','name':number_seq})

    @api.multi
    def unlink(self):
        for dif in self:
            if dif.state == 'done':
                raise Warning("No se pueden eliminar procesos en estado realizado")
    
    @api.multi
    def borrador(self):
        self.write({'state':'draft'})        
        return True
    
    @api.multi
    def recalcular(self):
        move_diff_ids=[]
        period_id = self.env['account.period'].search([('date_start','<=', self.date),('date_stop','>=', self.date),('state','=', 'draft')])
        if not period_id:
            raise osv.except_osv(_('Error !'), _("No puede recalcular una diferencia en cambio de un periodo que este ya cerrrado, por favor consulte con el area responsable"))
        
        if self.id:
            self._cr.execute("DELETE FROM account_move WHERE diff_process=%s", (self.id,))
            
        self._cr.commit()
        
        # Esta funcion permitia conocer y actualizar el balance del movimiento respecto a la diferencia en cambio, sin embargo afecta desempeño y restriccion de modificacion de movimientos en periodos cerrados #TODO Sedeberia poder hacer un informe para mejorar esta funcionalidad y poderse generar desde el mismo account.move.line, esto se realizara para la version 11
        #if self.move_ids:
            #for move in self.move_ids:
                #move.write({'diff_process': 'RECALCULO'+'-'+self.name+'-'+str(fields.datetime.now())})
        if self.account_ids:
            for account in self.account_ids:
                account.write({'diff_process':'RECALCULO'+'-'+self.name+'-'+str(fields.datetime.now())})                
        return self.write({'state': 'confirmed'})
    
    
    @api.multi
    def calcular(self):
        # Actualiza movimientos contables con equivalente niif
        self._cr.execute("UPDATE account_move_line aml "
                         "SET write_uid = {uid}, write_date = now(), account_niif_id = child_id "
                         "FROM account_account_consol_rel aacr, "
                         "account_period ap "
                         "WHERE aml.account_id = aacr.parent_id "
                         "AND account_id IS NOT NULL "
                         "AND ap.id = aml.period_id "
                         "AND ap.state = 'draft'".format(uid=self.env.user.id))

        # Actualiza movimientos contables con cuenta niif en campo cuenta
        self._cr.execute("UPDATE account_move_line aml "
                         "SET write_uid = {uid}, write_date = now(), account_niif_id = account_id "
                         "FROM account_account aa, "
                         "account_period ap "
                         "WHERE aml.account_id = aa.id "
                         "AND ap.id = aml.period_id "
                         "AND ap.state = 'draft' "
                         "AND aa.niif IS TRUE ".format(uid=self.env.user.id))
        
        move_obj = self.env['account.move.line']
        account_obj = self.env['account.account']
        seq_obj = self.pool.get('ir.sequence')
        move_line_pool = self.pool.get('account.move.line')
        cont = 0 
        cont2 = 0
        move_diff_ids=[]
        # CUENTAS QUE SE LES CORRERA DIFERENCIA EN CAMBIO A NIVEL DE CUENTA
        account_ids = account_obj.search([('currency_id','=',self.currency_id.id),('diff','=','cuenta')])        
                
        # CUENTAS QUE SE LES CORRERA DIFERENCIA EN CAMBIO A NIVEL DE MOVIMIENTO
        account_ids2 = [x.id for x in account_obj.search([('currency_id','=',self.currency_id.id),('diff','=','movimiento')])]

        # MOVIMEINTOS QUE SE LES CORRERA DIFERENCIA EN CAMBIO
        move_ids = move_obj.search([('currency_id','=',self.currency_id.id),('reconcile_id','=',False),('date','<=',self.date),('account_id','in',account_ids2),('change_not','=',False)])
        
        # MOVIMIENTOS QUE SE LES DEBE REVERTIR EL PROCESO DE DIFERENCIA EN CAMBIO BAJO NIIF
        if self.search([('state','=','done'),('date','>=',self.date)]):
            raise osv.except_osv(_('Error !'), _("No es posible ejecutar un proceso de diferencia en cambio con una fecha anterior a un proceso ya existente en el sistema."))
        
        diferencia_id = self.search([('state','=','done')], limit=1, order='date desc')
        if diferencia_id:
            move_diff_ids = move_obj.search([('move_change_ids','!=', False),('currency_id','=',self.currency_id.id),('reconcile_id.create_date','>=',diferencia_id.date),('account_id','in',account_ids2),('change_not','=',False)])
        
        
        company = self.period_id.company_id
        if not company:
            raise osv.except_osv(_('Error !'), _("ERROR EL PERIODO DEBE ESTAR ASOCIADO A LA COMPANIA"))
        
        # CUENTA DE GANANCIA Y PERDIDA A NIVEL DE COMPANIA
        self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (company.income_currency_exchange_account_id.id,))
        income_currency_exchange_account_id = self._cr.fetchall()
        
        self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (company.expense_currency_exchange_account_id.id,))
        expense_currency_exchange_account_id = self._cr.fetchall()
                    
        
        move = {
            'name': self.name,
            'ref': self.name,
            'journal_id': self.journal_id.id,
            'date': self.date,
            'period_id': self.period_id.id,
            'company': company.id,
            'diff_process': self.id,
            }
        move_id = self.env['account.move'].create(move)
        
        
        if move_diff_ids:
            for move_diff in move_diff_ids:
                for move in move_diff.move_change_ids:
                    db=move.debit
                    cr=move.credit
                    #print "wwwwwwww  MOVIMIENTO wwwwwwwwwww"
                    self._cr.execute('''INSERT INTO account_move_line (account_niif_id,account_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,change_id,move_change_id,journal_id,period_id,company_id,state,currency_id) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                    (move.account_niif_id.id,move.account_id.id,self.date,move.name,move.ref,self.date,move.partner_id.id,db,cr,move.analytic_account_id and move.analytic_account_id.id or None,move_id.id,self.id,move_diff.id,self.journal_id.id, self.period_id.id, company.id, 'valid',self.currency_id.id))
            
        if move_ids:
            for move in move_ids:
                cont += 1
                
                diff_amount_trm = 0.0
                amount_change = 0.0
                diff_amount_local = move.debit - move.credit
                diff_amount_divisa = move.amount_currency
                                    
                rec_ids = [move.id]
                if move.reconcile_partial_id:
                    if (move.account_id.naturaleza == 'debito' and diff_amount_divisa > 0.0) or (move.account_id.naturaleza == 'credito' and diff_amount_divisa < 0.0):
                        for move_reconcile in move.reconcile_partial_id.line_partial_ids:
                            if move_reconcile.id != move.id:
                                diff_amount_local += move_reconcile.debit - move_reconcile.credit
                                diff_amount_divisa += move_reconcile.amount_currency
                                rec_ids.append(move_reconcile.id)
                    else:
                        continue
                if move.move_change_ids:
                    self._cr.execute('''SELECT
                                            SUM(debit-credit),
                                            SUM(amount_currency)
                                        FROM
                                            account_move_line
                                        WHERE  
                                            account_id = %s
                                            AND move_change_id = %s
                                            AND state = 'valid' ''',
                                (move.account_niif_id.id,move.id)) 
                    result = self._cr.fetchall()[0]
                    if result:
                        amount_change = result[0]
                        if isinstance(amount_change, (list, tuple)):
                            amount_change = float(amount_change[0] or 0.0)
                        else:
                            amount_change = float(amount_change or 0.0)
                        
                        diff_amount_divisa1 = result[1]
                        if isinstance(diff_amount_divisa1, (list, tuple)):
                            diff_amount_divisa = diff_amount_divisa + float(diff_amount_divisa1[0] or 0.0)
                        else:
                            diff_amount_divisa = diff_amount_divisa + float(diff_amount_divisa1 or 0.0)
                
                diff_amount_local+= amount_change
                
                if diff_amount_divisa:
                    diff_amount_trm = diff_amount_local/diff_amount_divisa
                
                
                if diff_amount_trm == 0.0:
                    continue
                
                amount = (abs(diff_amount_trm) - self.rate)*abs(diff_amount_divisa)
                cont2 += 1
                
                if abs(amount) <= 0.1:
                    continue
                
                if amount > 0.0 and move.account_id.type == 'receivable':
                    if move.account_id.account_expense_niif_id:
                        debit_account = move.account_id.account_expense_niif_id.id
                    else:
                        debit_account = expense_currency_exchange_account_id
                    
                    self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (move.account_id.id,))
                    credit_account = self._cr.fetchall()
                    #m=True
                
                elif amount > 0.0 and move.account_id.type == 'payable':
                    if move.account_id.account_income_niif_id:
                        credit_account = move.account_id.account_income_niif_id.id
                    else:
                        credit_account = income_currency_exchange_account_id
                    
                    self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (move.account_id.id,))
                    debit_account = self._cr.fetchall()
                    
                elif amount < 0.0 and move.account_id.type == 'receivable':
                    if move.account_id.account_income_niif_id:
                        credit_account = move.account_id.account_income_niif_id.id
                    else:
                        credit_account = income_currency_exchange_account_id
                    
                    self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (move.account_id.id,))
                    debit_account = self._cr.fetchall()
                    
                elif amount < 0.0 and move.account_id.type == 'payable':                    
                    if move.account_id.account_expense_niif_id:
                        debit_account = move.account_id.account_expense_niif_id.id
                    else:
                        debit_account = expense_currency_exchange_account_id
                    
                    self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (move.account_id.id,))
                    credit_account = self._cr.fetchall()
                
                if isinstance(debit_account, (list, tuple)):
                    debit_account = debit_account[0]
                else:
                    debit_account = debit_account
                    
                if isinstance(credit_account, (list, tuple)):
                    credit_account = credit_account[0]
                else:
                    credit_account = credit_account
                
                #print "wwwwwwww  DEBITO wwwwwwwwwww"
                #print ""
                self._cr.execute('''INSERT INTO account_move_line (account_niif_id,account_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,change_id,move_change_id,journal_id,period_id,company_id,state,currency_id) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                (debit_account,debit_account,self.date,move.move_id.name,move.ref,self.date,move.partner_id.id,0.0,abs(amount),move.analytic_account_id and move.analytic_account_id.id or None,move_id.id,self.id,move.id,self.journal_id.id, self.period_id.id, company.id, 'valid',self.currency_id.id))
                ac_id = self._cr.fetchone()[0]

                #print "wwwwwwww  CREDITO  wwwwwwwwwww"
                self._cr.execute('''INSERT INTO account_move_line (account_niif_id,account_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,change_id,move_change_id,journal_id,period_id,company_id,state,currency_id) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                (credit_account,credit_account,self.date,move.move_id.name,move.ref,self.date,move.partner_id.id,abs(amount),0.0,move.analytic_account_id and move.analytic_account_id.id or None,move_id.id,self.id,move.id,self.journal_id.id, self.period_id.id, company.id,'valid',self.currency_id.id))
                ad_id = self._cr.fetchone()[0]

                for aid in [ac_id, ad_id]:
                    if aid == ac_id:
                        acc = debit_account
                        b = 1
                    else:
                        acc = credit_account
                        b = -1
                    for ana in move.analytic_lines:
                        pi = amount/(move.credit-move.debit)
                        danaly = {
                            'account_id': ana.account_id.id,
                            'date': self.date,
                            'name': move.name,
                            'ref': move.ref,
                            'move_id': aid,
                            'user_id': self._uid,
                            'journal_id': move.journal_id.analytic_journal_id.id,
                            'general_account_id': acc[0] if type(acc).__name__ == 'tuple' else acc,
                            'amount': b*abs(ana.amount*pi)
                        }
                        avancys_orm.direct_create(self._cr, self._uid, 'account_analytic_line', [danaly], company=True)
                
                #move.write({'amount_change':  abs(move.amount_residual) - abs(move.amount_residual_currency*self.rate)})
                self._cr.execute(''' update account_move_line set amount_change=%s where id=%s''', (abs(move.amount_residual) - abs(move.amount_residual_currency*self.rate), move.id))
                #if m:
                    #rec_ids.append(ad_id)
                #else:
                    #rec_ids.append(ac_id)
                    
                #type = 'Parcial'
                #seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                #name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                #self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES 
                        #(%s,%s,%s) RETURNING id''' ,
                        #(time.strftime('%Y-%m-%d'),name,type))
                #r_id = self._cr.fetchone()[0]
                
                #move_line_pool.write(self._cr, SUPERUSER_ID, rec_ids, {'reconcile_partial_id': r_id, 'reconcile_ref':name})

                #if abs(amount) <= 0.1:
                    #continue
                
                #cont2 += 1
                #if amount > 0.0 and move.account_id.naturaleza == 'debito':
                    #debit_account = company.expense_currency_exchange_account_id
                    #credit_account = move.account_id
                
                #elif amount > 0.0 and move.account_id.naturaleza == 'credito':
                    #debit_account = move.account_id
                    #credit_account = company.income_currency_exchange_account_id
                    
                #elif amount < 0.0 and move.account_id.naturaleza == 'debito':
                    #debit_account = move.account_id
                    #credit_account = company.income_currency_exchange_account_id
                    
                #elif amount < 0.0 and move.account_id.naturaleza == 'credito':                    
                    #debit_account = company.expense_currency_exchange_account_id
                    #credit_account = move.account_id
                
                
                ##"wwwwwwww  DEBITO wwwwwwwwwww"
                #self._cr.execute('''INSERT INTO account_move_line (account_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,change_id,move_change_id,journal_id,period_id,company_id,state,currency_id) VALUES 
                #(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                #(debit_account.id,self.date,move.move_id.name,move.ref,self.date,move.partner_id.id,0.0,abs(amount),move.analytic_account_id and move.analytic_account_id.id or None,move_id.id,self.id,move.id,self.journal_id.id,self.period_id.id,company.id,'valid',self.currency_id.id))
                
                ##"wwwwwwww  CREDITO wwwwwwwwwww"
                #self._cr.execute('''INSERT INTO account_move_line (account_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,change_id,move_change_id,journal_id,period_id,company_id,state,currency_id) VALUES 
                #(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                #(credit_account.id,self.date,move.move_id.name,move.ref,self.date,move.partner_id.id,abs(amount),0.0,move.analytic_account_id and move.analytic_account_id.id or None,move_id.id,self.id,move.id,self.journal_id.id, self.period_id.id,company.id,'valid',self.currency_id.id))
                    
        
        if account_ids:
            for account in account_ids:                
                self._cr.execute('''SELECT
                                        SUM(amount_currency),
                                        SUM(debit - credit)
                                    FROM
                                        account_move_line
                                    WHERE  
                                        account_id = %s
                                        AND date <= %s
                                        AND currency_id = %s
                                        ''',
                                (account.id,self.date,self.currency_id.id))        
                dict={}
                result = self._cr.fetchall()
                for res in result:
                    amount_currency = res[0] or 0.0
                    amount_local = res[1] or 0.0
                
                amount = abs(amount_local) - abs(amount_currency*self.rate)
                
                
                
                if account.account_change_ids:
                    amount_change=0.0
                    self._cr.execute('''SELECT
                                            SUM(debit-credit)
                                        FROM
                                            account_move_line
                                        WHERE  
                                            account_id = %s
                                            AND account_change_id = %s
                                            AND state = 'valid' ''',
                                (account.account_diff_niif_id.id,account.id)) 
                    result = self._cr.fetchall()[0]
                    
                    if result:
                        amount_change = result[0]
                        if isinstance(amount_change, (list, tuple)):
                            amount_change = float(amount_change[0] or 0.0)
                        else:
                            amount_change = float(amount_change or 0.0)
                        
                    amount+= amount_change                
                
                
                if abs(amount) <= 0.1:
                    continue
                    
                if amount > 0.0 and account.naturaleza == 'debito':
                    if amount_local < 0.0:
                        # sobregiros, cuando la cuenta esta volteada                        
                        if account.account_expense_niif_id:
                            credit_account = account.account_expense_niif_id.id
                        else:
                            credit_account = expense_currency_exchange_account_id
                        
                        self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (account.id,))
                        debit_account = self._cr.fetchall()                        
                    else:
                        if account.account_expense_niif_id:
                            debit_account = account.account_expense_niif_id.id
                        else:
                            debit_account = expense_currency_exchange_account_id
                        
                        self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (account.id,))
                        credit_account = self._cr.fetchall() 
                        
                elif amount > 0.0 and account.naturaleza == 'credito':
                    if account.account_income_niif_id:
                        credit_account = account.account_income_niif_id.id
                    else:
                        credit_account = income_currency_exchange_account_id
                    
                    self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (account.id,))
                    debit_account = self._cr.fetchall()
                    
                elif amount < 0.0 and account.naturaleza == 'debito':
                    
                    if account.account_income_niif_id:
                        credit_account = account.account_income_niif_id.id
                    else:
                        credit_account = income_currency_exchange_account_id
                    
                    self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (account.id,))
                    debit_account = self._cr.fetchall()
                                        
                elif amount < 0.0 and account.naturaleza == 'credito':                     
                    if account.account_expense_niif_id:
                        debit_account = account.account_expense_niif_id.id
                    else:
                        debit_account = expense_currency_exchange_account_id
                    
                    self._cr.execute('''SELECT child_id from account_account_consol_rel WHERE parent_id=%s''', (account.id,))
                    credit_account = self._cr.fetchall() 
                                    
                
                diff_partner_id = account.diff_partner_id and account.diff_partner_id.id or company.partner_id.id
                
                if isinstance(debit_account, (list, tuple)):
                    debit_account = debit_account[0]
                else:
                    debit_account = debit_account
                    
                if isinstance(credit_account, (list, tuple)):
                    credit_account = credit_account[0]
                else:
                    credit_account = credit_account
                    
                self._cr.execute('''INSERT INTO account_move_line (account_niif_id,account_id,date,name,ref,date_created,partner_id,credit,debit,analytic_account_id,move_id,change_id,account_change_id,journal_id,period_id,company_id,state,currency_id) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (debit_account,debit_account, self.date, account.name + ' '+ self.name, account.code, self.date, diff_partner_id, 0.0, abs(amount), account.account_analytic_change_id and account.account_analytic_change_id.id or None, move_id.id, self.id, account.id, self.journal_id.id, self.period_id.id, company.id, 'valid', self.currency_id.id))
                
                #"wwwwwwww  CREDITO ANALITICO PARA CUENTA wwwwwwwwwww"
                self._cr.execute('''INSERT INTO account_move_line (account_niif_id,account_id,date,name,ref,date_created,partner_id,credit,debit,analytic_account_id,move_id,change_id,account_change_id,journal_id,period_id,company_id,state,currency_id) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (credit_account,credit_account, self.date, account.name +' '+ self.name, account.code, self.date, diff_partner_id, abs(amount), 0.0, account.account_analytic_change_id and account.account_analytic_change_id.id or None, move_id.id, self.id, account.id, self.journal_id.id, self.period_id.id, company.id, 'valid', self.currency_id.id))
                
                
        move_id.post()
        self._cr.commit()
        
        # Esta funcion permitia conocer y actualizar el balance del movimiento respecto a la diferencia en cambio, sin embargo afecta desempeño y restriccion de modificacion de movimientos en periodos cerrados #TODO Sedeberia poder hacer un informe para mejorar esta funcionalidad y poderse generar desde el mismo account.move.line, esto se realizara para la version 11        
        #if move_ids:            
            #for move in move_ids:
                #move.write({'diff_process': self.name+'-'+str(fields.datetime.now())})
        if account_ids:
            for account in account_ids:
                account.write({'diff_process':self.name+'-'+str(fields.datetime.now())})            
        return self.write({'state':'done', 'move_ids': [(6, 0, [x.id for x in move_ids])], 'account_ids': [(6, 0, [x.id for x in account_ids])]})
#
