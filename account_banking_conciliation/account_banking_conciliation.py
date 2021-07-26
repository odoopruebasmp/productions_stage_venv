# -*- coding: utf-8 -*-
import re
import datetime as dt
from openerp.osv import osv, fields
from openerp import fields as fields2
from openerp import models, api
from openerp.tools.translate import _
from collections import defaultdict
import openerp.addons.decimal_precision as dp
from openerp.addons.avancys_orm import avancys_orm
from openerp.addons.edi import EDIMixin

class account_move(osv.Model):
    _inherit = "account.move"
    _rec_name = 'name'
    _columns = {
        'statement_id': fields.many2one('account.bank.statement', 'Extracto Bancario', readonly=True, select=True),
    }

class account_move_line(osv.Model):
    _inherit = "account.move.line"
    _rec_name = 'name'
    _columns = {
        'statement_line_id': fields.many2one('account.bank.statement.line', 'Transaction Line', readonly=True, select=True),
    }

class account_bank_statement_line(osv.Model):
    _inherit = "account.bank.statement.line"
    _columns = {
        'account_move_line_ids': fields.many2many('account.move.line', 'statement_lines_move_lines_rel','statement_line_id','account_move_line_id',string="Registros Relacionados", readonly=True, states={'manual': [('readonly', False)]}),
        'select': fields.boolean("Select", readonly=True, states={'draft': [('readonly', False)]}),
        'state': fields.selection([('draft', 'No Encontrado'), ('pending', 'Pendiente'), ('manual', 'Manual'), ('multiple', 'Multiples Coincidencias'), ('confirmed', 'Confirmado')], 'Estado', required=True, readonly=True),
        'balance': fields.float("Balance", digits_compute= dp.get_precision('Account'), readonly=True),
        'new_active_id': fields.integer("new_active_id"),
        'statement_id': fields.many2one('account.bank.statement', 'Statement', select=True, required=False, ondelete='cascade'),
        'statement_origin_id': fields.many2one('account.bank.statement', 'Origen', select=True, required=False, ondelete='cascade'),
    }
    
    _defaults = {
        'state': 'draft',
    }
    
    def confirm(self, cr, uid, ids, context=None):
        move_line_object = self.pool.get('account.move.line')
        for transaction in self.browse(cr, uid, ids, context=context):
            suma = 0
            for move_line in transaction.account_move_line_ids:
                suma+=move_line.debit-move_line.credit
                move_line_object.write(cr, uid, [move_line.id], {"statement_line_id": transaction.id})
                
            if suma != transaction.amount:
                raise osv.except_osv(_('Error!'), _('El valor de la transaccion "%s" es diferente al de los registros "%s"' %(suma,transaction.amount) ))
            transaction.statement_id.update_unfind()
        self.write(cr, uid, ids, {"state": 'confirmed'})
        return True
        
    def cancel(self, cr, uid, ids, context=None):
        orm2sql = self.pool.get('avancys.orm2sql')
        move_line_object = self.pool.get('account.move.line')
        for transaction in self.browse(cr, uid, ids, context=context):
            if transaction.statement_id.state == 'confirm':
                raise osv.except_osv(_('Error!'), _('No se puede cancelar una transaccion de un extracto cerrado'))
            for move_line in transaction.account_move_line_ids:
                cr.execute("UPDATE account_move_line SET statement_line_id = Null where id = {mid}".format(
                    mid=move_line.id))
                # move_line_object.write(cr, uid, [move_line.id], {"statement_line_id": False})
            cr.execute("""
                DELETE FROM statement_lines_move_lines_rel WHERE statement_line_id ={sid}
            """.format(sid=transaction.id))
            orm2sql.sqlupdate(cr, 'account_bank_statement_line', {'state': 'draft'}, ('id', transaction.id))

        return True
        
    def manual(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {"state": 'manual'})
        return True
        
    def pending(self, cr, uid, ids, context=None):
        self.cancel(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {"state": 'pending','statement_id': False})
        return True
    
    def attach(self, cr, uid, ids, context=None):
        transaction_pool = self.pool.get('account.bank.statement.line')
        for transaction in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, ids, {"state": 'draft', 'statement_id': transaction.new_active_id})
            self.find(cr, uid, ids, context=context)
        return True
    
    def find(self, cr, uid, ids, context=None):
        move_line_object = self.pool.get('account.move.line')
        orm2sql = self.pool.get('avancys.orm2sql')
        for transaction in self.browse(cr, uid, ids, context=context):
            match_dom = []
            tmatch = transaction.statement_id.match_dom
            if tmatch:
                c = re.findall(r'<(.*?)>', tmatch)
                for f in c:
                    cond = ()
                    condicionales = f.split(',')
                    if len(condicionales) == 3:
                        cond3 = str(getattr(transaction, str(condicionales[2])))
                        cond = (str(condicionales[0]), str(condicionales[1]), cond3)
                        print cond
                    match_dom.append(cond)
            if transaction.state == 'confirmed':
                continue
            match_dom += [('state', '=', 'valid'), ('account_id', '=', transaction.account_id.id),
                          ('date', '=', transaction.date), ('statement_line_id', '=', False)]
            if transaction.amount < 0:
                match_dom += [('credit', '=', transaction.amount * -1)]
            else:
                match_dom += [('debit', '=', transaction.amount)]
            move_line_ids = move_line_object.search(cr, uid, match_dom)

            if len(move_line_ids) == 1:
                self.cancel(cr, uid, [transaction.id], context=context)
                # Se asocia la transaccion al movimiento contable
                orm2sql.sqlupdate(
                    cr, 'account_move_line', {'statement_line_id': transaction.id}, ('id', move_line_ids[0]))
                # orm many2many create
                cr.execute("""
                    INSERT INTO statement_lines_move_lines_rel 
                    (statement_line_id, account_move_line_id)
                    VALUES ({tid}, {amid})
                    """.format(tid=transaction.id, amid=move_line_ids[0]))
                # Estado confirmado en transaccion
                orm2sql.sqlupdate(
                    cr, 'account_bank_statement_line', {'state': 'confirmed'}, ('id', transaction.id))
            elif len(move_line_ids) > 1:
                self.cancel(cr, uid, [transaction.id], context=context)
                # orm many2many create
                for move_line_id in move_line_ids:
                    cr.execute("""
                                INSERT INTO statement_lines_move_lines_rel 
                                (statement_line_id, account_move_line_id)
                                VALUES ({tid}, {amid})
                                """.format(tid=transaction.id, amid=move_line_id))
                orm2sql.sqlupdate(
                    cr, 'account_bank_statement_line', {'state': 'multiple'}, ('id', transaction.id))
            else:
                self.cancel(cr, uid, [transaction.id], context=context)

        t = False
        for transaction in self.browse(cr, uid, ids, context=context):
            if t is False:
                t = transaction
            else:
                break
        if t is not False:
            t.statement_id.update_unfind()
            
        return True


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    @api.multi
    def find2(self):
        crit, op, val = [], [], []
        tmatch = self[0].statement_id.match_dom
        match_cheque = self[0].statement_id.match_cheque
        simple_ref = self[0].statement_id.simple_ref

        # Dominio especial ej: <ref2,=,ref>
        # donde ref2 es campo del account_move_line y ref es campo de la linea de extracto
        if tmatch:
            c = re.findall(r'<(.*?)>', tmatch)
            for f in c:

                condicionales = f.split(',')

                if len(condicionales) == 3:
                    crit.append(str(condicionales[0]))
                    op.append(str(condicionales[1]))
                    val.append(str(condicionales[2]))
            print crit, op, val

        i, j = 0, len(self)
        bar = avancys_orm.progress_bar(i, j)

        # noinspection PyTypeChecker
        for transaction in self:
            # limpieza
            if transaction.state != 'confirmed':
                for move_line in transaction.account_move_line_ids:
                    self._cr.execute("UPDATE account_move_line SET statement_line_id = Null where id = {mid}".format(
                        mid=move_line.id))
                self._cr.execute("""
                    DELETE FROM statement_lines_move_lines_rel WHERE statement_line_id ={sid}
                """.format(sid=transaction.id))
                avancys_orm.direct_update(self._cr, 'account_bank_statement_line', {'state': 'draft'},
                                          ('id', transaction.id))
                self._cr.commit()
                # Fin limpieza
                matchdom = ''
                for idx in range(len(crit)):
                    matchdom += " AND {criterio} {operador} '{valor}'".format(
                        criterio=crit[idx],
                        operador=op[idx],
                        valor=str(getattr(transaction, str(val[idx])))
                    )
                if transaction.amount < 0:
                    debcred = 'AND credit = {amount}'.format(amount=transaction.amount * -1)
                else:
                    debcred = 'AND debit = {amount}'.format(amount=transaction.amount)

                if match_cheque and transaction.ref != simple_ref:
                    # VALIDACION POR CHEQUE
                    vlook = """
                        SELECT id FROM account_move_line 
                        WHERE 
                                (state = 'valid' 
                                AND account_id = {account} 
                                AND date = '{date}' 
                                AND statement_id is Null
                                {debcred}
                                {matchdom}) 
                            OR 
                                (state = 'valid' 
                                AND account_id = {account} 
                                AND statement_id is Null
                                AND ref2 = '{cheque}'
                                {debcred})
                    """.format(account=transaction.account_id.id, date=transaction.date, debcred=debcred,
                               matchdom=matchdom, cheque=transaction.ref)

                else:
                    vlook = """
                        SELECT id FROM account_move_line 
                        WHERE 
                            state = 'valid' 
                            AND account_id = {account} 
                            AND date = '{date}' 
                            AND statement_id is Null
                            {debcred}
                            {matchdom}
                    """.format(account=transaction.account_id.id, date=transaction.date, debcred=debcred,
                               matchdom=matchdom)

                self._cr.execute(vlook)
                moves = self._cr.fetchall()

                if moves:
                    if len(moves) == 1:
                        # Se asocia la transaccion al movimiento contable
                        avancys_orm.direct_update(
                            self._cr, 'account_move_line', {'statement_line_id': transaction.id}, ('id', moves[0][0]))
                        # orm many2many create
                        self._cr.execute("""
                            INSERT INTO statement_lines_move_lines_rel 
                            (statement_line_id, account_move_line_id)
                            VALUES ({tid}, {amid})
                            """.format(tid=transaction.id, amid=moves[0][0]))
                        # Estado confirmado en transaccion
                        avancys_orm.direct_update(
                            self._cr, 'account_bank_statement_line', {'state': 'confirmed'}, ('id', transaction.id))
                    elif len(moves) > 1:
                        # orm many2many create
                        for move_line in moves:
                            self._cr.execute("""
                                        INSERT INTO statement_lines_move_lines_rel 
                                        (statement_line_id, account_move_line_id)
                                        VALUES ({tid}, {amid})
                                        """.format(tid=transaction.id, amid=move_line[0]))
                        avancys_orm.direct_update(
                            self._cr, 'account_bank_statement_line', {'state': 'multiple'}, ('id', transaction.id))
            i += 1
            bar = avancys_orm.progress_bar(i, j, bar, transaction.id)

        return True


class account_bank_statement(osv.Model):
    _name = 'account.bank.statement'
    _inherit = ['account.bank.statement', 'mail.thread', 'ir.needaction_mixin']
    
    def _get_pendings(self, cr, uid, ids, name, args, context=None):
        res = {}
        transaction_pool = self.pool.get('account.bank.statement.line')
        statement = self.browse(cr, uid, ids, context=context)
        for transaction in statement:
            lists = transaction_pool.search(
                cr, uid, [('statement_id', '=', False),
                          ('account_id', '=', statement.journal_id.default_debit_account_id.id)], context=context)
            #workaround because parent.active_id/parent.id was not accesible from the view for some reason
            #TODO make it work with the active_id
            transaction_pool.write(cr, uid, lists, {'new_active_id': transaction.id}, context=context)
            res[transaction.id] = lists
        return res
    
    _columns = {
        'pending_transaction': fields.function(_get_pendings, relation='account.bank.statement.line', type="one2many", string='Detalle de Dias', readonly=True),
        'file': fields.binary('Archivo', readonly=True),
        'file_name': fields.char(size=64, string='Archivo'),
        'match_dom': fields.char('Dominio adicional'),
        'match_cheque': fields.boolean('Concilar cheques', help="Marcar para buscar movimientos con coincidencias en"
                                                                "cuenta y ref2"),
        'simple_ref': fields.char('Referencia omision cheque', help="Caracteres definidos por los bancos para hacer"
                                                                    "alusion a movimientos que no corresponden a "
                                                                    "cheque"),
        'line_ids': fields.one2many('account.bank.statement.line','statement_id', 'Statement lines',
                                    states={'confirm':[('readonly', True)]}, list_options='{"limit":20}'),
        'line_origin_ids': fields.one2many('account.bank.statement.line','statement_origin_id','Original Statement lines',readonly=True),
        'move_ids': fields.one2many('account.move', 'statement_id','Comprobantes Generados',readonly=True),
        'unfind_move_ids': fields.many2many('account.move.line', 'unfind_move_lines_rel',
                                            'statement_line_id','account_move_line_id',
                                            string="Movimiento contables no encontrados", readonly=True)
    }
    
    def button_cancel(self, cr, uid, ids, context=None):
        statement = self.browse(cr, uid, ids, context=None)
        for trans_line in statement.line_ids:
            for move in trans_line.account_move_line_ids:
                move.statement_id = False
        return self.write(cr, uid, ids, {'state':'draft'}, context=context)
    
    def button_confirm_bank(self, cr, uid, ids, context=None):
        for st in self.browse(cr, uid, ids, context=context):
        
            if not ((abs((st.balance_end or 0.0) - st.balance_end_real) < 0.0001) or (abs((st.balance_end or 0.0) - st.balance_end_real) < 0.0001)):
                raise osv.except_osv(_('Error!'),
                    _('The statement balance is incorrect !\nThe expected balance (%.2f) is different than the computed one. (%.2f)') % (st.balance_end_real, st.balance_end))
        
            for transaction in st.line_ids:
                if transaction.state != 'confirmed':
                    raise osv.except_osv(_('Error!'), _('Todas las transacciones tienen que estar confirmadas "%s"!' %(transaction.name) ))
                for move in transaction.account_move_line_ids:
                    if move.move_id.state != 'posted':
                        raise osv.except_osv(_('Error!'), _('Todos los registros relacionados tienen que estar Asentados "%s"!' %(transaction.name) ))
            self.write(cr, uid, [st.id], {'state':'confirm'}, context=context)
        return True

    def update_unfind(self, cr, uid, ids, context=None):
        move_line_object = self.pool.get('account.move.line')
        for statement_id in self.browse(cr, uid, ids, context=context):
            cr.execute("DELETE FROM unfind_move_lines_rel WHERE statement_line_id ={sid}".format(sid=statement_id.id))
            dom = [('account_id', 'in', [statement_id.journal_id.default_debit_account_id.id,
                                         statement_id.journal_id.default_credit_account_id.id]),
                   ('date', '>=', statement_id.period_id.date_start),
                   ('date', '<=', statement_id.period_id.date_stop),
                   ('statement_line_id', '=', False)
                   ]
            unfind_move_line_ids = move_line_object.search(cr, uid, dom)
            for move_line_id in unfind_move_line_ids:
                cr.execute("""
                    INSERT INTO unfind_move_lines_rel
                    (statement_line_id, account_move_line_id)
                    VALUES ({sid}, {mid})
                """.format(sid=statement_id.id, mid=move_line_id))
        return
        
    def open_journal_wizard(self, cr, uid, ids, context=None):
        if not context: context = {}
        records= []
        for transaction in self.browse(cr, uid, ids[0], context=context).line_ids:
            if transaction.select:
                records.append(transaction.id)
        context.update({'default_transaction_ids': records})
        return {
                'name': _('Journal Entries'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'bank.transaction.wiz',
                'view_id': False,
                'context': context,
                'type': 'ir.actions.act_window',
                'target': 'new',
        }
    
    def reconcile_invoice(self,cr, uid, ids, context=None):
        '''
            It will find the open invoices and do the reconciliation for it.
        '''
        if not context: context = {}
        invoice_obj = self.pool.get('account.invoice')
        voucher_obj = self.pool.get('account.voucher')
        journal_obj = self.pool.get('account.journal')
        statement_line_object = self.pool.get('account.bank.statement.line')
        for rec in self.browse(cr, uid, ids, context=context):
            journal_ids = journal_obj.search(cr, uid, [('default_debit_account_id', '=', rec.account_id.id)])
            out_journal, in_journal = False, False
            for journal in journal_obj.browse(cr, uid, journal_ids, context):
                if journal.recaudo:
                    in_journal = journal.id
                else:
                    out_journal = journal.id
            for transaction in rec.line_ids:
                search_domain_invoice = [('amount_total', '=', transaction.amount), ('state', '=', 'open'), ('type', '=', 'out_invoice')]
                context.update({"type": 'receipt', "default_type": 'receipt', "invoice_type": "out_invoice", "journal_type": 'sale', })
                ttype = 'sale'
                if transaction.amount < 0:
                    search_domain_invoice = [('amount_total', '=', abs(transaction.amount)), ('state', '=', 'open'), ('type', '=', 'in_invoice')]
                    context.update({"type": 'payment', "default_type": 'payment', "invoice_type": "in_invoice", "journal_type": 'purchase', })
                    ttype = 'payment'
                invoice_ids = invoice_obj.search(cr, uid, search_domain_invoice)
                if len(invoice_ids) == 1:
                    inv_rec = invoice_obj.browse(cr, uid, invoice_ids[0], context=context)
                    context.update({
                        "default_amount": abs(transaction.amount),
                        "invoice_id": invoice_ids[0],
                        'default_partner_id': inv_rec.partner_id.id,
                        "active_ids": invoice_ids,
                    })
                    fields_list = ['comment', 'line_cr_ids', 'is_multi_currency', 'reference', 'line_dr_ids', 'company_id', 'currency_id', 'narration', 'partner_id', 'payment_rate_currency_id', 'paid_amount_in_company_currency', 'writeoff_acc_id', 'state', 'pre_line', 'type', 'payment_option', 'account_id', 'period_id', 'date', 'payment_rate', 'name', 'writeoff_amount', 'analytic_id', 'journal_id', 'amount']
                    voucher_vals = voucher_obj.default_get(cr, uid, fields_list, context=context)
                    tax_id = inv_rec.account_id.tax_ids and inv_rec.account_id.tax_ids[0].id or False
                    partner_id = inv_rec.partner_id.id
                    date = voucher_vals.get('request_date') or voucher_vals.get('date')
                    amount = abs(transaction.amount)
                    company_id = inv_rec.company_id.id
                    onchange_vals = voucher_obj.onchange_journal(cr, uid, ids, rec.journal_id.id, [], tax_id, partner_id, date, amount, ttype, company_id, context=None)
                    voucher_vals.update(onchange_vals.get('value'))
                    if onchange_vals.get('value').get('line_cr_ids'):
                        voucher_vals['line_cr_ids'] = [(0, 0, x) for x in onchange_vals.get('value').get('line_cr_ids')]
                        voucher_vals['line_dr_ids'] = [] 
                    if onchange_vals.get('value').get('line_dr_ids'):
                        voucher_vals['line_dr_ids'] = [(0, 0, x) for x in onchange_vals.get('value').get('line_dr_ids')]
                        voucher_vals['line_cr_ids'] = []
                    if voucher_vals.get('type') in ['receipt']:
                        voucher_vals.update({
                        'journal_id':in_journal,
                        })
                    elif voucher_vals.get('type') in ['payment']:
                        voucher_vals.update({
                        'journal_id':out_journal,
                        })
                    if not in_journal:
                        raise osv.except_osv(_('Error!'), _('No account journal found for %s with Recaudo(si),Pago(no)!' %(rec.account_id.name) ))
                    voucher_id = voucher_obj.create(cr, uid, voucher_vals , context)
                    voucher_obj.button_proforma_voucher(cr, uid, [voucher_id], context=context)
                    voucher_rec = voucher_obj.browse(cr, uid, voucher_id, context)
                    reconcile_id = [x.reconcile_id for x in voucher_rec.move_ids]
                    line_vals = {
                        'amount':transaction.amount,
                        'state': 'confirm',
                        "reconcile_id": reconcile_id[0].id,
                        'voucher_id': voucher_id,
                    }
                    statement_line_object.write(cr, uid, [transaction.id], line_vals, context)
        return True
    
    def button_dummy(self, cr, uid, ids, context=None):
        vals = super(account_bank_statement, self).button_dummy(cr, uid, ids, context=context)
        statement_line_object = self.pool.get('account.bank.statement.line')
        for rec in self.browse(cr, uid, ids, context=context):
            statement_line_object.find2(cr, uid, [x.state != 'manual' and x.id for x in rec.line_ids], context=context)
        # self.update_unfind(cr, uid, ids, context)
        return vals


# new api declaration
class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    multi_trans_ids = fields2.One2many('account.bank.multi.transaction', 'statement_id', string="Transacciones")
    multi_move_line_ids = fields2.One2many('account.bank.multi.move', 'statement_id', string="Movimientos")
    multi_trans_amount = fields2.Float('Total transacciones seleccionadas')
    multi_move_amount = fields2.Float('Total movimientos seleccionados')
    date_multi_get = fields2.Date('Filtro fecha')
    value_multi_get = fields2.Float('Filtro valor')
    bank_account_id = fields2.Many2one('res.partner.bank', 'Cuenta bancaria')
    trans_balance = fields2.Float('Saldo calculado', digits_compute=dp.get_precision('Account'))
    balance_account = fields2.Float('Saldo Cuenta', digits_compute=dp.get_precision('Account'),
                                    help='Saldo Cuenta Efectivo General Libro Mayor, al día interior de la fecha de inicio '
                                         'del periodo')
    pending_consing = fields2.Float('Consignaciones Pendientes', digits_compute=dp.get_precision('Account'),
                                    help='Consignaciones pendientes de contabilizar')
    rotated_check = fields2.Float('Cheques Pendientes', digits_compute=dp.get_precision('Account'),
                                  help='Cheques girados y no cobrados')
    payment_pending = fields2.Float('Pagos Pendientes', digits_compute=dp.get_precision('Account'),
                                    help='Pagos pendientes de contabilizar')
    nd_not_account = fields2.Float('N/D no contabilizadas', digits_compute=dp.get_precision('Account'),
                                    help='Notas Débito no Contabilizadas')
    nc_not_account = fields2.Float('N/C no contabilizadas', digits_compute=dp.get_precision('Account'),
                                    help='Notas Crédito no Contabilizadas')

    @api.onchange('journal_id')
    def onchange_journal(self):
        if self.journal_id:
            journal = self.pool.get('account.journal').browse(self._cr, self._uid, self.journal_id.id)
            if journal.with_last_closing_balance:
                self._cr.execute('SELECT balance_end_real \
                              FROM account_bank_statement \
                              WHERE journal_id = %s AND NOT state = %s \
                              ORDER BY date DESC,id DESC LIMIT 1', (self.journal_id.id, 'draft'))
                res = self._cr.fetchone()
                if res:
                    self.balance_start = res[0]
                else:
                    self.balance_start = 0
            else:
                self.balance_start = 0
        else:
            self.balance_start = 0


    @api.multi
    def calculate_balance_end(self):
        total = """SELECT SUM(amount) from account_bank_statement_line
                        WHERE statement_id = {sid} and state='confirmed'
                """.format(sid=self.id)
        self._cr.execute(total)
        delta = self._cr.fetchall()
        if delta:
            self.trans_balance = self.balance_start + delta[0][0]
        else:
            self.trans_balance = self.balance_start
        return True

    @api.multi
    def close_statement(self):

        self.calculate_balance_end()
        self._cr.commit()

        if not ((abs((self.trans_balance or 0.0) - self.balance_end_real) < 0.0001) or (
                abs((self.trans_balance or 0.0) - self.balance_end_real) < 0.0001)):
            raise osv.except_osv(_('Error!'),
                                 _(
                                     'The statement balance is incorrect !\nThe expected balance (%.2f) is different than the computed one. (%.2f)') % (
                                 self.balance_end_real, self.trans_balance))

        for transaction in self.line_ids:
            if transaction.state != 'confirmed':
                raise osv.except_osv(_('Error!'), _(
                    'Todas las transacciones tienen que estar confirmadas "%s"!' % (transaction.name)))
            for move in transaction.account_move_line_ids:
                if move.move_id.state != 'posted':
                    raise osv.except_osv(_('Error!'), _(
                        'Todos los registros relacionados tienen que estar Asentados "%s"!' % (transaction.name)))
        for trans_line in self.line_ids:
            for move in trans_line.account_move_line_ids:
                move.statement_id = self
        self.write({'state': 'confirm'})
        return True

    @api.multi
    def print_concil(self):
        aci = self.line_ids[0].account_id.id
        self._cr.execute("UPDATE account_bank_statement SET balance_account = (SELECT sum(debit-credit) FROM "
                         "account_move_line WHERE account_id = {aci} AND date <= '{dt}') WHERE id = {sti}"
                         .format(aci=aci, dt=self.date, sti=self.id))
        # TODO remover restricción, se coloca tmp mientras se desarrolla req en transacciones pendientes fuera de perido
        self._cr.execute("UPDATE account_bank_statement SET pending_consing = (SELECT sum(amount) FROM "
                         "account_bank_statement_line WHERE (statement_id = {sti} OR statement_id IS Null) "
                         "AND state != 'confirmed' AND amount > 0 AND date BETWEEN '{dts}' AND '{dtt}') WHERE id = "
                         "{sti}".format(dts=self.period_id.date_start, dtt=self.period_id.date_stop, sti=self.id))
        self._cr.execute("UPDATE account_bank_statement SET rotated_check = (SELECT sum(credit) FROM account_move_line aml "
                         "WHERE id IN (SELECT account_move_line_id FROM unfind_move_lines_rel WHERE statement_line_id = "
                         "{sti}) AND aml.ref2 IS NOT Null AND aml.ref2 NOT IN ('ref2','') AND aml.debit = 0) WHERE "
                         "id = {sti}".format(sti=self.id))
        self._cr.execute("UPDATE account_bank_statement SET payment_pending = (SELECT -1*sum(amount) FROM "
                         "account_bank_statement_line WHERE (statement_id = {sti} OR statement_id IS Null) "
                         "AND state != 'confirmed' AND amount < 0) WHERE id = {sti}".format(sti=self.id))
        self._cr.execute("UPDATE account_bank_statement SET nd_not_account = (SELECT sum(debit) FROM account_move_line aml "
                         "WHERE id IN (SELECT account_move_line_id FROM unfind_move_lines_rel WHERE statement_line_id = "
                         "{sti}) AND (aml.ref2 IS Null OR aml.ref2 IN ('ref2','')) AND debit > 0) WHERE id = {sti}".
                         format(sti=self.id))
        self._cr.execute("UPDATE account_bank_statement SET nc_not_account = (SELECT sum(credit) FROM account_move_line aml "
                         "WHERE id IN (SELECT account_move_line_id FROM unfind_move_lines_rel WHERE statement_line_id = "
                         "{sti}) AND (aml.ref2 IS Null OR aml.ref2 IN ('ref2','')) AND credit > 0) WHERE id = {sti}".
                         format(sti=self.id))
        self._cr.commit()
        dat = {'ids': [self.id], 'model': u'account.bank.statement'}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': u'account_banking_conciliation.banking_conciliation_report',
            'datas': dat,
        }

    @api.multi
    def find2(self):
        self.line_ids.find2()

    @api.multi
    def write(self, vals):
        if 'active_model' in self._context and 'pos.session.opening' in self._context['active_model'] or \
                'pos_session_id' in vals:
            return super(AccountBankStatement, self).write(vals)
        return avancys_orm.direct_write(self, vals)

    @api.multi
    def view_transactions(self):
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.bank.statement.line',
            'domain': [('statement_id', '=', self.id),
                       ('state', '!=', 'pending')],
            'context': {'default_statement_id': self.id,
                        'default_account_id': self.journal_id.default_debit_account_id.id,
                        'default_bank_account_id': self.bank_account_id.id}
        }

    @api.multi
    def view_unfind_move_ids(self):
        view = self.env['ir.model.data']._get_id('account_banking_conciliation',
                                                 'account_banking_conciliation_unfind_moves')
        view_id = self.env['ir.model.data'].browse(view).res_id
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'res_model': 'account.bank.statement',
            'view_id': [view_id]
        }

    @api.multi
    def view_multi_match(self):
        view = self.env['ir.model.data']._get_id('account_banking_conciliation',
                                                 'account_banking_conciliation_multi_form')
        view_id = self.env['ir.model.data'].browse(view).res_id
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.bank.statement',
            'res_id': self.id,
            'view_id': [view_id]
        }

    @api.multi
    def view_undone_match(self):
        view = self.env['ir.model.data']._get_id('account_banking_conciliation',
                                                 'account_banking_conciliation_multi_form')
        view_id = self.env['ir.model.data'].browse(view).res_id
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.bank.statement',
            'res_id': self.id,
            'view_id': [view_id]
        }

    @api.multi
    def view_back(self):
        view = self.env['ir.model.data']._get_id('account_banking_conciliation',
                                                 'account_banking_conciliation_statement_form')
        view_id = self.env['ir.model.data'].browse(view).res_id
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.bank.statement',
            'res_id': self.id,
            'view_id': [view_id]
        }

    @api.multi
    def view_move_ids(self):
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'domain': [('statement_id', '=', self.id)],
        }

    @api.multi
    def get_multi_dif(self):
        sql_trans = """SELECT sum(amount) FROM account_bank_multi_transaction 
        WHERE statement_id = {s} AND selected = 't'""".format(s=self.id)
        sql_moves = """SELECT((SELECT sum(debit) FROM account_bank_multi_move WHERE statement_id = {s} AND selected = 't')
                - (SELECT sum(credit) FROM account_bank_multi_move WHERE statement_id = {s} AND selected = 't'))
        """.format(s=self.id)
        self._cr.execute(sql_trans)
        total_trans = self._cr.fetchall()[0][0]
        self._cr.execute(sql_moves)
        total_moves = self._cr.fetchall()[0][0]
        self.multi_trans_amount = total_trans
        self.multi_move_amount = total_moves
        return True

    @api.multi
    def get_multi(self):
        orm2sql = self.env['avancys.orm2sql']
        self._cr.execute(
            "DELETE FROM account_bank_multi_transaction where statement_id = {statement}".format(statement=self.id))
        self._cr.execute(
            "DELETE FROM account_bank_multi_move where statement_id = {statement}".format(statement=self.id))

        # Transacciones
        aditional = ''
        if self.value_multi_get:
            aditional += ' AND amount = {amount}'.format(amount=self.value_multi_get)
        if self.date_multi_get:
            aditional += " AND date = '{date}'".format(date=self.date_multi_get)
        self._cr.execute("""
            SELECT id FROM account_bank_statement_line
            WHERE state = 'multiple' and statement_id = {statement}
                {aditional}
        """.format(statement=self.id, aditional=aditional))
        stat_lines = self._cr.fetchall()
        stats = []
        for s in stat_lines:
            self._cr.execute("""
                SELECT amount, date from account_bank_statement_line where id = {s}
            """.format(s=s[0]))
            values = self._cr.fetchall()
            svalue = {
                'statement_id': self.id,
                'transaction_id': s[0],
                'amount': values[0][0],
                'date': values[0][1]
            }
            if self.value_multi_get or self.date_multi_get:
                svalue['selected'] = True
            stats.append(svalue)
        orm2sql.sqlcreate(self._uid, self._cr, 'account_bank_multi_transaction', stats, progress=True)

        # Movimientos
        self._cr.execute("""
            SELECT DISTINCT account_move_line_id FROM statement_lines_move_lines_rel
            WHERE statement_line_id IN 
                (SELECT id FROM account_bank_statement_line 
                WHERE state = 'multiple' and statement_id = {statement} {aditional})
        """.format(statement=self.id, aditional=aditional))
        move_lines = self._cr.fetchall()
        moves = []
        for m in move_lines:
            self._cr.execute("""
                SELECT debit, credit, date from account_move_line where id = {m}
            """.format(m=m[0]))
            values = self._cr.fetchall()
            mvalue = {
                'statement_id': self.id,
                'move_line_id': m[0],
                'debit': values[0][0],
                'credit': values[0][1],
                'date': values[0][2]
            }
            if self.value_multi_get or self.date_multi_get:
                mvalue['selected'] = True
            moves.append(mvalue)
        orm2sql.sqlcreate(self._uid, self._cr, 'account_bank_multi_move', moves, progress=True)
        self.get_multi_dif()
        return True

    @api.multi
    def get_undone(self):
        orm2sql = self.env['avancys.orm2sql']
        self._cr.execute(
            "DELETE FROM account_bank_multi_transaction where statement_id = {statement}".format(statement=self.id))
        self._cr.execute(
            "DELETE FROM account_bank_multi_move where statement_id = {statement}".format(statement=self.id))

        # Transacciones
        aditional = ''
        adtmove = ''
        if self.value_multi_get:
            aditional += ' AND amount = {amount}'.format(amount=self.value_multi_get)
            if self.value_multi_get > 0:
                adtmove += ' AND debit = {amount}'.format(amount=abs(self.value_multi_get))
            else:
                adtmove += ' AND credit = {amount}'.format(amount=abs(self.value_multi_get))
        if self.date_multi_get:
            aditional += " AND date = '{date}'".format(date=self.date_multi_get)
            adtmove += " AND date = '{date}'".format(date=self.date_multi_get)
        self._cr.execute("""
            SELECT id FROM account_bank_statement_line
            WHERE state = 'draft' and statement_id = {statement}
                {aditional}
        """.format(statement=self.id, aditional=aditional))
        stat_lines = self._cr.fetchall()
        stats = []
        for s in stat_lines:
            self._cr.execute("""
                SELECT amount, date from account_bank_statement_line where id = {s}
            """.format(s=s[0]))
            values = self._cr.fetchall()
            svalue = {
                'statement_id': self.id,
                'transaction_id': s[0],
                'amount': values[0][0],
                'date': values[0][1]
            }
            if self.value_multi_get or self.date_multi_get:
                svalue['selected'] = True
            stats.append(svalue)
        orm2sql.sqlcreate(self._uid, self._cr, 'account_bank_multi_transaction', stats, progress=True)

        # Movimientos

        self._cr.execute("""
            SELECT id FROM account_move_line
            WHERE account_id IN ({deb}, {cred})
            AND date >= '{date_start}' AND date <= '{date_stop}'
            AND statement_line_id is Null
            {aditional}
        """.format(deb=self.journal_id.default_debit_account_id.id, cred=self.journal_id.default_credit_account_id.id,
                   date_start=self.period_id.date_start, date_stop=self.period_id.date_stop, aditional=adtmove))
        move_lines = self._cr.fetchall()
        moves = []
        for m in move_lines:
            self._cr.execute("""
                SELECT debit, credit, date from account_move_line where id = {m}
            """.format(m=m[0]))
            values = self._cr.fetchall()
            mvalue = {
                'statement_id': self.id,
                'move_line_id': m[0],
                'debit': values[0][0],
                'credit': values[0][1],
                'date': values[0][2]
            }
            if self.value_multi_get or self.date_multi_get:
                mvalue['selected'] = True
            moves.append(mvalue)
        orm2sql.sqlcreate(self._uid, self._cr, 'account_bank_multi_move', moves, progress=True)
        self.get_multi_dif()
        return True

    @api.multi
    def conciliate(self):
        orm2sql = self.env['avancys.orm2sql']

        self.get_multi_dif()

        # Validacion de totales seleccionados
        if self.multi_trans_amount != self.multi_move_amount:
            raise Warning("Las transacciones seleccionadas no están correctamente correspondidas")
        self._cr.execute("""SELECT count(amount), amount  FROM account_bank_multi_transaction 
            WHERE statement_id = {s} AND selected = 't' group by amount order by amount asc
        """.format(s=self.id))
        trans_comp = self._cr.fetchall()

        self._cr.execute("""select count(debit - credit), (debit - credit) as dif from account_bank_multi_move 
            WHERE statement_id = {s} AND selected = 't' group by dif order by dif asc
        """.format(s=self.id))
        moves_comp = self._cr.fetchall()

        # Validacion de integridad
        if trans_comp and (trans_comp != moves_comp):
            raise Warning("La estructura de las transacciones seleccionadas no son correctas")

        self._cr.execute("""SELECT transaction_id from account_bank_multi_transaction 
            WHERE statement_id = {s} AND selected = 't' order by amount asc
        """.format(s=self.id))
        trans = self._cr.fetchall()
        transaction = self.env['account.bank.statement.line'].browse(x[0] for x in trans)
        # Limpieza
        for tr in transaction:
            for move_line in tr.account_move_line_ids:
                self._cr.execute("UPDATE account_move_line SET statement_line_id = Null where id = {mid}".format(
                    mid=move_line.id))

        self._cr.execute("""SELECT move_line_id from account_bank_multi_move 
            WHERE statement_id = {s} AND selected = 't' order by (debit-credit)
        """.format(s=self.id))
        moves = self._cr.fetchall()
        idxm = 0
        for idx in trans:
            transaction = self.env['account.bank.statement.line'].browse(idx[0])
            self._cr.execute("""
                DELETE FROM statement_lines_move_lines_rel WHERE statement_line_id ={sid}
            """.format(sid=transaction.id))
            orm2sql.sqlupdate('account_bank_statement_line', {'state': 'draft'}, ('id', transaction.id))
            # Fin limpieza
            print "Conciliando", transaction.id, "con", moves[idxm][0]
            self._cr.execute("UPDATE account_move_line set statement_line_id = {trans} WHERE id = {move}".format(
                trans=transaction.id, move=moves[idxm][0]
            ))
            # orm2sql.sqlupdate(
            #     'account_move_line', {'statement_line_id': transaction.id}, ('id', moves[idxm][0]))
            # orm many2many create
            self._cr.execute("""
                INSERT INTO statement_lines_move_lines_rel 
                (statement_line_id, account_move_line_id)
                VALUES ({tid}, {amid})
                """.format(tid=transaction.id, amid=moves[idxm][0]))
            # Estado confirmado en transaccion
            orm2sql.sqlupdate(
                'account_bank_statement_line', {'state': 'confirmed'}, ('id', transaction.id))
            idxm += 1
        self.get_multi()
        self.multi_trans_amount = 0
        self.multi_move_amount = 0

        return True


class AccountBankMultiTransaction(models.Model):
    _name = 'account.bank.multi.transaction'

    selected = fields2.Boolean('Seleccionado', default=False)
    transaction_id = fields2.Many2one('account.bank.statement.line', 'Transaccion bancaria')
    date = fields2.Date('Fecha')
    amount = fields2.Float('Valor')
    statement_id = fields2.Many2one('account.bank.statement', 'Extracto')


class AccountBankMultiMove(models.Model):
    _name = 'account.bank.multi.move'

    selected = fields2.Boolean('Seleccionado', default=False)
    move_line_id = fields2.Many2one('account.move.line', 'Movimiento contable')
    date = fields2.Date('Fecha')
    debit = fields2.Float('Debito')
    credit = fields2.Float('Credito')
    statement_id = fields2.Many2one('account.bank.statement', 'Extracto')

