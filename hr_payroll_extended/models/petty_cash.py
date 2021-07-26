# -*- coding: utf-8 -*-
from openerp import models, fields, api
import openerp.addons.decimal_precision as dp
from datetime import datetime
from openerp.exceptions import Warning


class OpenPettyCash(models.TransientModel):
    _name = 'open.petty.cash'

    employee_id = fields.Many2one('hr.employee', 'Responsable', domain="[('responsable_caja', '=', True)]")
    type = fields.Selection([('abrir', 'Abrir'), ('aumentar', 'Aumentar'), ('disminuir', 'Disminuir'),
                             ('cerrar', 'Cerrar')], 'Tipo operacion')
    ammount = fields.Float('Monto de apertura')

    @api.multi
    def open_cash(self):
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']
        journal = self.employee_id.journal_id2
        seq_obj = self.pool.get('ir.sequence')
        name = seq_obj.next_by_id(self._cr, self._uid, journal.sequence_id.id, context=self._context)

        period_obj = self.env['account.period']

        # Validacion del periodo
        period_id = period_obj.search([('state', '=', 'draft'), ('date_start', '<=', datetime.now()),
                                                ('date_stop', '>=', datetime.now())], limit=1)
        if period_id:
            period_id = period_id[0]
        else:
            raise Warning(
                "El sistema debe contar con un periodo contable abierto para este tipo de transferencia para la fecha")
        if self.type in ['abrir', 'aumentar']:
            if self.type == 'abrir':
                narration = 'Apertura de caja menor'
            else:
                narration = 'Aumento de fondo de caja menor'
            debit_account = journal.default_debit_account_id.id
            credit_account = journal.petty_payable_account_id.id
            journal.fondo = journal.fondo + self.ammount
        elif self.type in ['disminuir', 'cerrar']:
            if self.type == 'disminuir':
                narration = 'Reduccion de caja menor'
            else:
                narration = 'Cierre de fondo de caja menor'
            debit_account = journal.petty_payable_account_id.id
            credit_account = journal.default_debit_account_id.id
            journal.fondo = journal.fondo - self.ammount

        move = {
            'narration': narration,
            'date': datetime.now(),
            'ref': name,
            'journal_id': journal.id,
            'period_id': period_id.id,
            'partner_id': self.employee_id.partner_id.id,
            'state': 'draft',
            'name': name,
        }
        move_id = move_obj.create(move)
        credit_line = {
            'name': name,
            'date': datetime.now(),
            'partner_id': self.employee_id.partner_id.id,
            'account_id': credit_account,
            'journal_id': journal.id,
            'period_id': period_id.id,
            'debit': 0.0,
            'credit': self.ammount,
            'analytic_account_id': False,
            'move_id': move_id.id,
            'ref': move_id.ref,
        }
        move_line_obj.create(credit_line)

        debit_line = {
            'name': name,
            'date': datetime.now(),
            'partner_id': self.employee_id.partner_id.id,
            'account_id': debit_account,
            'journal_id': journal.id,
            'period_id': period_id.id,
            'debit': self.ammount,
            'credit': 0.0,
            'analytic_account_id': False,
            'move_id': move_id.id,
            'ref': move_id.ref,
        }
        move_line_obj.create(debit_line)
        journal.update_petty_moves()
        return


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    petty_payable_account_id = fields.Many2one('account.account', 'Cuenta por pagar caja')
    move_ids = fields.One2many('move.petty.cash', 'journal_id', string='Movimientos')

    fondo = fields.Float('Fondo', help="Fondo de la caja menor")

    total_debit = fields.Float('Total debito', compute="_get_totals")
    total_credit = fields.Float('Total credito', compute='_get_totals')

    petty_cash = fields.Boolean('Caja menor', help="Marcar para gestionar como caja menor")

    @api.depends('move_ids')
    def _get_totals(self):
        for s in self:
            total_debit, total_credit = 0, 0
            for line in s.move_ids:
                total_credit += line.credit
                total_debit += line.debit
            s.total_debit = total_debit
            s.total_credit = total_credit

    @api.multi
    def update_petty_moves(self):
        self._cr.execute("DELETE FROM move_petty_cash WHERE journal_id = {id}".format(id=self.id))
        sql = '''
            SELECT id FROM account_move_line
            WHERE journal_id = {journal_id} AND account_id = {account_id}
        '''.format(journal_id=self.id, account_id=self.default_debit_account_id.id)
        self._cr.execute(sql)
        move_ids = self._cr.fetchall()
        orm2sql = self.env['avancys.orm2sql']
        datalist = []
        fondo = 0
        for move_id in move_ids:
            data = {
                'journal_id': self.id,
                'move_id': move_id[0]
            }
            move = self.env['account.move.line'].browse(move_id[0])
            fondo += move.debit - move.credit
            datalist.append(data)
        self.fondo = fondo
        orm2sql.sqlcreate(self.env.uid, self.env.cr, 'move_petty_cash', datalist, progress=True)
        return


class MovePettyCash(models.Model):
    _name = 'move.petty.cash'

    detail = fields.Text('Detalle', related="move_id.narration")
    journal_id = fields.Many2one('account.journal', 'Comprobante')
    account_id = fields.Many2one('account.account', 'Cuenta', related="move_id.account_id")
    move_id = fields.Many2one('account.move.line', 'Movimiento')
    debit = fields.Float('Debito', related="move_id.debit")
    credit = fields.Float('Credito', related="move_id.credit")
    date = fields.Date('Fecha', related="move_id.date")
    partner_id = fields.Many2one('res.partner', related="move_id.partner_id")


class HrExpenseExpense(models.Model):
    _inherit = 'hr.expense.expense'

    fondo_caja = fields.Float('Fondo Caja Menor', related="employee_id.journal_id2.fondo",
                              digits=dp.get_precision('Sale Price'))
    saldo_caja = fields.Float('Saldo Caja', compute="_get_saldo_caja", digits=dp.get_precision('Sale Price'))

    @api.depends('amount_total2')
    def _get_saldo_caja(self):
        self.saldo_caja = self.fondo_caja - self.amount_total2

    def write(self, cr, uid, ids, vals, context=None):
        print "Guardando"

        result = super(HrExpenseExpense, self).write(cr, uid, ids, vals, context=context)
        for rec in self.browse(cr, uid, ids, context=context):
            total = 0
            for line in rec.line_ids:
                total += line.total_base
            if rec.employee_id.journal_id2.petty_cash:
                if total > rec.fondo_caja and rec.type == 'rembolso_caja_menor':
                    raise Warning("No se pueden legalizar gastos superiores al fondo de la caja")
        return result
