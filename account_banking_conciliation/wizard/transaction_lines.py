# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 Serpent Consulting services
#                  All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import osv, fields
from openerp.tools.translate import _
from openerp.addons.avancys_orm import avancys_orm

class bank_transaction_wiz(osv.TransientModel):
    _name = "bank.transaction.wiz"

    _columns = {
        'journal_id' : fields.many2one('account.journal', 'Diario'),
        'debit_account_id' : fields.many2one('account.account', 'Account'),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'transaction_ids': fields.many2many('account.bank.statement.line', string="Selected Transaction",
                                            domain=[('state','=','draft')]),
        'analytic_account_id': fields.many2one('account.analytic.account', 'Cuenta analitica'),
        'date': fields.date('Fecha movimiento'),
    }
    
    def create_journal_entries(self, cr, uid, ids, context=None):
        if not context: context = {}
        account_move_obj = self.pool.get('account.move')
        account_move_line_obj = self.pool.get('account.move.line')
        transaction_obj = self.pool.get('account.bank.statement.line')
        parent_rec = self.pool.get('account.bank.statement').browse(cr, uid, context['active_id'])
        rec = self.browse(cr, uid, ids[0], context=context)
        debit, credit = 0, 0
        period_id = parent_rec.period_id.id
        journal_id = rec.journal_id.id

        name = self.pool.get('ir.sequence').next_by_id(cr, uid, rec.journal_id.sequence_id.id)
        move_vals = {
            'name': name,
            'date': rec.date,
            'journal_id': journal_id,
            'ref': parent_rec.name,
            'period_id': period_id,
            'statement_id': parent_rec.id,
            'state': 'posted',
        }
        move_id = account_move_obj.create(cr, uid, move_vals, context=context)
        
        for transaction in rec.transaction_ids:
            move_line_vals = {
                'date': transaction.date,
                'name': name,
                'journal_id': journal_id,
                'account_id' : transaction.account_id.id,
                'partner_id': rec.partner_id.id,
                'statement_line_id': transaction.id,
                'move_id': move_id,
                'period_id': period_id,
                'state': 'valid',
            }
            if transaction.amount > 0:
                move_line_vals.update({'credit': 0.0, 'debit': round(abs(transaction.amount), 0)})
                debit += round(transaction.amount, 0)
            else:
                move_line_vals.update({'credit': round(abs(transaction.amount), 0), 'debit': 0.0})
                credit += round(abs(transaction.amount),0)
            move_line_id = avancys_orm.direct_create(cr, uid, 'account_move_line',
                                                     [move_line_vals], company=True)[0][0]
            # move_line_id = account_move_line_obj.create(cr, uid, move_line_vals, context=context)
            # line_vals = {
            #     'state': 'confirmed',
            #     'account_move_line_ids': [(6, 0, [move_line_id])],
            # }
            cr.execute("""
                        INSERT INTO statement_lines_move_lines_rel 
                        (statement_line_id, account_move_line_id)
                        VALUES ({tid}, {amid})
                        """.format(tid=transaction.id, amid=move_line_id))
            avancys_orm.direct_update(
                cr, 'account_bank_statement_line', {'state': 'confirmed'}, ('id', transaction.id))
            # transaction_obj.write(cr, uid, [transaction.id], line_vals, context=context)

        if debit > credit:
            amount_diff = debit - credit
            move_line_vals = {
                'date': rec.date,
                'name': name,
                'journal_id': journal_id,
                'account_id': rec.debit_account_id.id,
                'partner_id': rec.partner_id.id,
                'analytic_account_id': rec.analytic_account_id.id,
                'credit': amount_diff,
                'debit': 0.0,
                'period_id': period_id,
                'move_id': move_id,
                'state': 'valid',
            }
            counter_line = avancys_orm.direct_create(cr, uid, 'account_move_line', [move_line_vals], company=True)[0][0]
        else:
            amount_diff = credit - debit
            move_line_vals = {
                'date': rec.date,
                'name': name,
                'journal_id': journal_id,
                'account_id': rec.debit_account_id.id,
                'partner_id': rec.partner_id.id,
                'analytic_account_id': rec.analytic_account_id.id,
                'credit': 0.0,
                'debit': amount_diff,
                'period_id': period_id,
                'move_id': move_id,
                'state': 'valid',
            }
            counter_line = avancys_orm.direct_create(cr, uid, 'account_move_line', [move_line_vals], company=True)[0][0]
        line = self.pool.get('account.move.line').browse(cr, uid, counter_line)
        if line.analytic_account_id:
            analytic_line = {
                'account_id': line.analytic_account_id.id,
                'date': line.date,
                'name': line.name,
                'ref': name,
                'move_id': counter_line,
                'journal_id': rec.journal_id.analytic_journal_id.id,
                'general_account_id': line.account_id.id,
                'amount': line.credit - line.debit,
            }
            avancys_orm.direct_create(cr, uid, 'account_analytic_line',
                                      [analytic_line], company=True)
        return move_id


bank_transaction_wiz()
