# -*- coding: utf-8 -*-
import time
from collections import OrderedDict

import openerp.tools
from openerp import fields as fields2
from openerp import models, api
from openerp.addons.avancys_tools import report_tools
from openerp.addons.edi import EDIMixin
from openerp.osv import fields, osv
from openerp.tools.translate import _


class payment_order(osv.osv, EDIMixin):
    _name = "payment.order"
    _inherit = ['payment.order', 'mail.thread', 'ir.needaction_mixin']

    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        ctx = dict(context, account_period_prefer_normal=True)
        periods = self.pool.get('account.period').find(cr, uid, context=ctx)
        return periods and periods[0] or False

    def _get_narration(self, cr, uid, context=None):
        if context is None: context = {}
        return context.get('narration', False)

    def _get_type(self, cr, uid, context=None):
        if context is None:
            context = {}
        return context.get('type', False)

    def print_check(self, cr, uid, ids, context=None):
        if not ids:
            raise osv.except_osv(_('Printing error'), _('No check selected '))

        data = {
            'id': ids and ids[0],
            'ids': ids,
        }

        return self.pool['report'].get_action(
            cr, uid, [], 'account_payment.report_paymentorder', data=data, context=context
        )

    _columns = {
        'period_id': fields.many2one('account.period', 'Period', required=True, readonly=True,
                                     states={'draft': [('readonly', False)]}),
        'move_id': fields.many2one('account.move', 'Comprobante Contable', readonly=True),
        'move_name': fields.char('Nombre Comprobante', size=64, readonly=True),
        'narration': fields.text('Notes', readonly=True, states={'draft': [('readonly', False)]}),
        'type': fields.selection([
            ('sale', 'Sale'),
            ('purchase', 'Purchase'),
            ('payment', 'Payment'),
            ('receipt', 'Receipt'),
        ], 'Default Type', readonly=True, states={'draft': [('readonly', False)]}),
        'payment_order_date': fields.date('Fecha de Pago', required=True, readonly=True,
                                          states={'draft': [('readonly', False)]}),
        'time_of_process': fields.datetime('Fecha Transmision', readonly=True),
        'file_text': fields.binary(string="Archivo Pago Banco", readonly=True),
        'file_name': fields.char(size=64, string='Archivo Pago Banco', track_visibility='onchange', readonly=True),
        'type_payment': fields.selection([('Pago Nomina', 'Pago Nomina'), ('Pago Proveedores', 'Pago Proveedores'),
                                          ('Transferencias', 'Transferencias'), ('Otros', 'Otros')],
                                         'Tipo de Transaccion', states={'draft': [('readonly', False)]}),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('cancel', 'Cancelled'),
            ('open', 'Confirmed'),
            ('done', 'Done')], 'Status', select=True, copy=False, track_visibility='onchange')
    }

    _defaults = {
        'period_id': _get_period,
        'narration': _get_narration,
        'type': _get_type,
    }

    def set_done(self, cr, uid, ids, context=None):
        wf_service = openerp.netsvc.LocalService("workflow")
        self.write(cr, uid, ids, {'date_done': time.strftime('%Y-%m-%d')}, context=context)
        wf_service.trg_validate(uid, 'payment.order', ids[0], 'done', cr)
        payment = self.browse(cr, uid, ids, context=context)
        if payment.cheque:
            payment.cheque = self.pool.get('ir.sequence').next_by_id(
                cr, uid, payment.mode.journal.cheque_seq.id, context=context)
        self.action_move_line_create(cr, uid, ids, context=context)
        return True

    def _prepare_move_line_debit(self, cr, uid, payment_id, lines_id, move_id, journal_id, date, company_id,
                                 context=None):
        if move_id:
            return {
                'name': payment_id.reference,
                'move_id': move_id,
                'company_id': company_id,
                'journal_id': journal_id,
                'period_id': payment_id.period_id.id,
                'account_id': lines_id.move_line_id.account_id.id,
                'partner_id': lines_id.partner_id.id,
                'credit': lines_id.move_line_id.debit and lines_id.amount_currency or 0,
                'debit': lines_id.move_line_id.credit and lines_id.amount_currency or 0,
                'date': date,
                'amount_currency': 0.0,
                'currency_id': False,
                'tax_code_id': False,
                'tax_amount': False,
                'analytic_account_id': False,
                'ref1': 'ref1',
                'ref2': payment_id.cheque or lines_id.numero_cheque or 'ref2',
                'state': 'valid',
            }

    def _prepare_move_line_credit(self, cr, uid, payment_id, lines_id, move_id, journal_id, date, company_id,
                                  credit_value, context=None):
        if move_id:
            return {
                'name': '/',
                'ref': payment_id.reference,
                'move_id': move_id,
                'company_id': company_id,
                'journal_id': journal_id,
                'period_id': payment_id.period_id.id,
                'account_id': payment_id.mode.journal.default_credit_account_id.id,
                'partner_id': lines_id.other_partner_id.id,
                'credit': credit_value,
                'debit': lines_id.move_line_id.debit,
                'date': date,
                'amount_currency': 0.0,
                'currency_id': False,
                'tax_code_id': False,
                'tax_amount': False,
                'analytic_account_id': False,
                'ref1': 'ref1',
                'ref2': payment_id.cheque or lines_id.numero_cheque or 'ref2',
                'state': 'valid',
            }

    def action_move_line_create(self, cr, uid, ids, context=None):

        if context is None:
            context = {}
        orm2sql = self.pool.get('avancys.orm2sql')
        account_move_obj = self.pool.get('account.move')
        account_move_line_obj = self.pool.get('account.move.line')
        seq_obj = self.pool.get('ir.sequence')
        dclines = OrderedDict()  # dict credit lines
        ddlines = OrderedDict()

        for payment in self.browse(cr, uid, ids, context=context):
            if payment.line_ids:
                journal_id = payment.mode.journal.id
                summarized_payment = payment.mode.journal.summarized_payment
                date = payment.payment_order_date
                company_id = payment.company_id.id

                if payment.mode.journal.allow_date:
                    if not time.strptime(payment.payment_order_date[:10], '%Y-%m-%d') >= time.strptime(
                            payment.period_id.date_start, '%Y-%m-%d') or not time.strptime(
                            payment.payment_order_date[:10], '%Y-%m-%d') <= time.strptime(payment.period_id.date_stop,
                                                                                          '%Y-%m-%d'):
                        raise osv.except_osv(_('Error!'), _(
                            """The date of your Journal Entry is not in the defined period! You should change the date or remove this constraint from the journal"""))

                if payment.mode.journal.sequence_id:
                    if not payment.mode.journal.sequence_id.active:
                        raise osv.except_osv(_('Configuration Error !'),
                                             _('Please activate the sequence of selected journal !'))
                    c = dict(context)
                    c.update({'fiscalyear_id': payment.period_id.fiscalyear_id.id})
                    if payment.move_name:
                        name = payment.move_name
                    else:
                        name = seq_obj.next_by_id(cr, uid, payment.mode.journal.sequence_id.id, context=c)
                else:
                    raise osv.except_osv(_('Error!'),
                                         _('Please define a sequence on the journal.'))
                move = {
                    'name': name,
                    'ref': payment.reference,
                    'line_id': [],
                    'journal_id': journal_id,
                    'date': date,
                    'period_id': payment.period_id.id,
                    'narration': payment.narration,
                    'company_id': company_id,
                }
                move_id = account_move_obj.create(cr, uid, move, context=context)
                self.write(cr, uid, [payment.id], {'move_name': name, 'move_id': move_id}, context=context)
                if payment.mode.journal.entry_posted:
                    account_move_obj.button_validate(cr, uid, [move_id], context=context)

                if summarized_payment:
                    credit_value = payment.total
                    rec_list_ids = []
                    move_line_data_credit = []
                    for summarized_lines in payment.line_ids:
                        move_line_data_credit = self._prepare_move_line_credit(cr, uid, payment, summarized_lines,
                                                                               move_id, journal_id, date, company_id,
                                                                               credit_value, context=context)
                    move_line_credit_id = account_move_line_obj.create(cr, uid, move_line_data_credit, context=context)
                    for debit_lines in payment.line_ids:
                        rec_ids = [debit_lines.move_line_id.id]
                        move_line_data_debit = self._prepare_move_line_debit(cr, uid, payment, debit_lines, move_id,
                                                                             journal_id, date, company_id,
                                                                             context=context)
                        move_line_debit_id = account_move_line_obj.create(cr, uid, move_line_data_debit,
                                                                          context=context)
                        rec_ids.append(move_line_debit_id)
                        if debit_lines.move_line_id.id:
                            rec_list_ids.append(rec_ids)
                    for rec_ids in rec_list_ids:
                        if len(rec_ids) >= 2:
                            account_move_line_obj.reconcile_partial(cr, uid, rec_ids, writeoff_acc_id=False,
                                                                    writeoff_period_id=False, writeoff_journal_id=False)
                else:
                    aag = self.pool.get('ir.module.module').search(cr, uid, [('name', '=', 'account_analytic_general'),
                                                                             ('state', '=', 'installed')],
                                                                   context=context)
                    ddmids = {}  # dict debit move ids
                    dcmids = {}  # dict credit move ids
                    dconcil = {}  # dict conciliations
                    dlineas = {}  # dict lineas credito a emparejar con lineas debito creadas
                    ban = 0
                    for lines in payment.line_ids:
                        credit_value = lines.amount_currency
                        rec_ids = lines.move_line_id.id

                        move_line_data_credit = self._prepare_move_line_credit(cr, uid, payment, lines, move_id,
                                                                               journal_id, date, company_id,
                                                                               credit_value, context=context)
                        move_line_data_debit = self._prepare_move_line_debit(cr, uid, payment, lines, move_id,
                                                                             journal_id, date, company_id,
                                                                             context=context)

                        ckey = (lines.bank_id.id, lines.other_partner_id.id)
                        dkey = (lines.bank_id.id, move_line_data_debit['partner_id'],
                                move_line_data_debit['account_id'])

                        if ckey not in dclines:
                            dclines[ckey] = move_line_data_credit
                            dclines[ckey] = move_line_data_credit
                            dlineas[dkey] = [rec_ids]
                            dclines[ckey]['lineas'] = dlineas
                            dclines[ckey]['ids'] = [lines.id]
                        else:
                            ncredit = dclines[ckey]['credit'] + move_line_data_credit['credit']
                            ndebit = dclines[ckey]['debit'] + move_line_data_credit['debit']
                            dclines[ckey].update({'credit': ncredit})
                            dclines[ckey].update({'debit': ndebit})
                            dclines[ckey]['ids'].append(lines.id)
                            if dkey not in dlineas:
                                dlineas[dkey] = [rec_ids]
                                dclines[ckey]['lineas'] = dlineas
                            else:
                                dclines[ckey]['lineas'][dkey].append(rec_ids)

                        if dkey not in ddlines:
                            ddlines[dkey] = move_line_data_debit
                            ddlines[dkey]['ids'] = [lines.id]
                            ddlines[dkey]['key'] = dkey
                            ddlines[dkey]['ckey'] = ckey
                        else:
                            ndebit = ddlines[dkey]['debit'] + move_line_data_debit['debit']
                            ncredit = ddlines[dkey]['credit'] + move_line_data_debit['credit']
                            ddlines[dkey].update({'debit': ndebit})
                            ddlines[dkey].update({'credit': ncredit})
                            ddlines[dkey]['ids'].append(lines.id)

                    for i in range(len(ddlines) - len(dclines)):
                        dclines[i] = 0

                    for mldc, mldd in zip(dclines.values(), ddlines.values()):
                        if mldc == 0:
                            mldc = dclines.get(mldd['ckey'])
                            ban = 1
                        line_seats = mldc['lineas']
                        line_c_ids = mldc['ids']
                        line_d_ids = mldd['ids']
                        debit_key = mldd['key']
                        cpmldc = mldc.copy()
                        map(cpmldc.pop, ['lineas', 'ids'])
                        cpmldd = mldd.copy()
                        map(cpmldd.pop, ['ids', 'key', 'ckey'])

                        move_line_credit_id = \
                        orm2sql.sqlcreate(uid, cr, 'account_move_line', [cpmldc], company=True, commit=False)[0][
                            0] if not ban else 0
                        move_line_debit_id = \
                        orm2sql.sqlcreate(uid, cr, 'account_move_line', [cpmldd], company=True, commit=False)[0][0]

                        lineas_credito = line_seats.get(debit_key)
                        dconcil[debit_key] = lineas_credito
                        dconcil[debit_key].append(move_line_debit_id)

                        ddmids[move_line_credit_id] = line_d_ids
                        dcmids[move_line_debit_id] = line_c_ids

                        ban = 0

                    for concil in dconcil.values():
                        if len(concil) >= 2:
                            account_move_line_obj.reconcile_partial(cr, uid, concil, writeoff_acc_id=False,
                                                                    writeoff_period_id=False, writeoff_journal_id=False)

                    if aag:
                        for lines in payment.line_ids:
                            credit_value = lines.amount_currency
                            move_line_data_credit = self._prepare_move_line_credit(cr, uid, payment, lines, move_id,
                                                                                   journal_id, date, company_id,
                                                                                   credit_value, context=context)
                            move_line_data_debit = self._prepare_move_line_debit(cr, uid, payment, lines, move_id,
                                                                                 journal_id, date, company_id,
                                                                                 context=context)

                            md_id = next((move for move, line in ddmids.items() if lines.id in line), None)
                            mc_id = next((move for move, line in dcmids.items() if lines.id in line), None)

                            if lines.move_line_id.analytic_lines:
                                for l in lines.move_line_id.analytic_lines:
                                    amount = abs(l.amount / (l.move_id.debit + l.move_id.credit))
                                    amount1 = amount * (
                                                move_line_data_debit.get('credit', False) - move_line_data_debit.get(
                                            'debit', False))
                                    analytic_lines1 = {
                                        'account_id': l.account_id.id,
                                        'date': move['date'],
                                        'name': lines.move_line_id.name,
                                        'ref': lines.move_line_id.ref,
                                        'move_id': md_id,
                                        'user_id': uid,
                                        'journal_id': lines.move_line_id.journal_id.analytic_journal_id.id,
                                        'general_account_id': move_line_data_credit.get('account_id', False),
                                        'amount': amount1,
                                    }
                                    self.pool.get('account.analytic.line').create(cr, uid, analytic_lines1,
                                                                                  context=context)

                                    amount2 = amount * (
                                                move_line_data_credit.get('credit', False) - move_line_data_credit.get(
                                            'debit', False))
                                    analytic_lines2 = {
                                        'account_id': l.account_id.id,
                                        'date': move['date'],
                                        'name': lines.move_line_id.name,
                                        'ref': lines.move_line_id.ref,
                                        'move_id': mc_id,
                                        'user_id': uid,
                                        'journal_id': lines.move_line_id.journal_id.analytic_journal_id.id,
                                        'general_account_id': move_line_data_debit.get('account_id', False),
                                        'amount': amount2,
                                    }
                                    self.pool.get('account.analytic.line').create(cr, uid, analytic_lines2,
                                                                                  context=context)
            else:
                raise osv.except_osv(_('Error!'), _('No hay lineas en la orden de pago.'))
        return True

    def wf_cancel(self, cr, uid, ids, context=None):
        moveobj = self.pool.get('account.move')
        for payment in self.browse(cr, uid, ids, context=context):
            if payment.move_id:
                moveobj.button_cancel(cr, uid, [payment.move_id.id], context=context)
                moveobj.unlink(cr, uid, [payment.move_id.id], context=context)
            linv = [(x.ml_inv_ref.id, x.ml_inv_ref.amount_total) for x in payment.line_ids if x.ml_inv_ref.id]
            if len(linv) > 1:
                for i in linv:
                    cr.execute("UPDATE account_invoice SET residual=%s WHERE id=%s" % (i[1], i[0]))
        self.write(cr, uid, ids, {'state': 'cancel'})
        return True


class PaymentOrder(models.Model):
    _inherit = 'payment.order'

    cheque = fields2.Char('Cheque', track_visibility='onchange')

    @api.multi
    def unlink(self):
        if self.state != 'draft':
            raise Warning("No se puede eliminar una orden de pago que no se encuentre en estado borrador")
        return super(PaymentOrder, self).unlink()

    @api.onchange('mode')
    def onchange_mode(self):
        if self.mode and self.mode.journal.cheque:
            self.cheque = self.mode.journal.cheque_seq.number_next_actual


class res_partner_bank(osv.Model):
    _inherit = "res.partner.bank"

    _columns = {
        'city_code': fields.char(string="Codigo Ciudad Banco Bogota"),
    }


class account_move_line(osv.osv):
    _inherit = "account.move.line"

    _columns = {
        'default_bank_id': fields.related('partner_id', 'default_bank_id', type="many2one", relation="res.partner.bank",
                                          string="Cuenta Banco"),
        'bank': fields.related('default_bank_id', 'bank', type="many2one", relation="res.bank", string="Banco"),
    }

    def reconcile_without_writeoff(self, cr, uid, ids, type='auto', context=None):
        account_obj = self.pool.get('account.account')
        move_obj = self.pool.get('account.move')
        move_rec_obj = self.pool.get('account.move.reconcile')
        partner_obj = self.pool.get('res.partner')
        currency_obj = self.pool.get('res.currency')
        lines = self.browse(cr, uid, ids, context=context)
        unrec_lines = filter(lambda x: not x['reconcile_id'], lines)
        credit = debit = 0.0
        currency = 0.0
        account_id = False
        partner_id = False
        if context is None:
            context = {}
        company_list = []
        for line in self.browse(cr, uid, ids, context=context):
            if company_list and not line.company_id.id in company_list:
                raise osv.except_osv(_('Warning!'),
                                     _('To reconcile the entries company should be the same for all entries.'))
            company_list.append(line.company_id.id)
        for line in unrec_lines:
            credit += line['credit']
            debit += line['debit']
            currency += line['amount_currency'] or 0.0
            account_id = line['account_id']['id']
            partner_id = (line['partner_id'] and line['partner_id']['id']) or False
        writeoff = debit - credit

        # Ifdate_p in context => take this date
        if context.has_key('date_p') and context['date_p']:
            date = context['date_p']
        else:
            date = time.strftime('%Y-%m-%d')

        cr.execute('SELECT account_id, reconcile_id ' \
                   'FROM account_move_line ' \
                   'WHERE id IN %s ' \
                   'GROUP BY account_id,reconcile_id',
                   (tuple(ids),))
        r = cr.fetchall()
        # TODO: move this check to a constraint in the account_move_reconcile object
        if not unrec_lines:
            raise osv.except_osv(_('Error!'), _('Entry is already reconciled.'))
        account = account_obj.browse(cr, uid, account_id, context=context)
        if r[0][1] != None:
            raise osv.except_osv(_('Error!'), _('Some entries are already reconciled.'))

        if context.get('fy_closing'):
            # We don't want to generate any write-off when being called from the
            # wizard used to close a fiscal year (and it doesn't give us any
            # writeoff_acc_id).
            pass
        r_id = move_rec_obj.create(cr, uid, {
            'type': type,
            'line_id': map(lambda x: (4, x, False), ids),
            'line_partial_ids': map(lambda x: (3, x, False), ids)
        })
        wf_service = openerp.netsvc.LocalService("workflow")
        # the id of the move.reconcile is written in the move.line (self) by the create method above
        # because of the way the line_id are defined: (4, x, False)
        for id in ids:
            wf_service.trg_trigger(uid, 'account.move.line', id, cr)

        if lines and lines[0]:
            partner_id = lines[0].partner_id and lines[0].partner_id.id or False
            if partner_id and not partner_obj.has_something_to_reconcile(cr, uid, partner_id, context=context):
                partner_obj.mark_as_reconciled(cr, uid, [partner_id], context=context)
        return r_id

    def reconcile(self, cr, uid, ids, type='auto', writeoff_acc_id=False, writeoff_period_id=False,
                  writeoff_journal_id=False, context=None):
        res = super(account_move_line, self).reconcile(cr, uid, ids, type='auto', writeoff_acc_id=writeoff_acc_id,
                                                       writeoff_period_id=writeoff_period_id,
                                                       writeoff_journal_id=writeoff_journal_id, context=context)
        lines = self.browse(cr, uid, ids, context=context)
        unrec_lines = filter(lambda x: not x['reconcile_id'], lines)

        for line in unrec_lines:
            if line.state <> 'valid':
                raise osv.except_osv(_('¡Error!'),
                                     _('La linea de valor "%s", tiene el asiento "%s" en estado no asentado') % (
                                         line.amount_to_pay, line.name))

        return res
    #
    # def reconcile(self, cr, uid, ids, type='auto', writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False, context=None):
    #     lines = self.browse(cr, uid, ids, context=context)
    #     unrec_lines = filter(lambda x: not x['reconcile_id'], lines)
    #     sta=0
    #     debit=0
    #     credit=0
    #     for line in unrec_lines:
    #         if line.state == 'draft':
    #             line.state = 'valid'
    #             sta=sta+1
    #         if sta == 2:
    #             raise osv.except_osv(_('¡Error!'),
    #                                  _('La linea de valor "%s", tiene el asiento "%s" en estado no asentado') % (line.amount_to_pay, line.name))
    #         if (line.credit > 0):
    #             credit=round(line.credit)
    #         if (line.debit > 0):
    #             debit=round(line.debit)
    #         if (credit > 0.0 and debit > 0.0):
    #             if (debit != credit):
    #                 raise osv.except_osv(_('¡Error!'),
    #                                      _('Existe una diferencia en el debito "%s" y el Credito "%s"') % (debit, credit))
    #
    #     res = super(account_move_line, self).reconcile(cr, uid, ids, type='auto', writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False, context=None)
    #     return res


class account_journal(osv.osv):
    _inherit = "account.journal"
    _columns = {
        'summarized_payment': fields.boolean('Pago Agrupado',
                                             help="Indica si un pago masivo debe ser agrupado en una linea credito"),
        'efectivo': fields.boolean('Tipo Efectivo', help="Indica si el diario es para pagos en Efectivo"),
        'cheque': fields.boolean('Tipo Cheque', help="Indica si el diario es para pagos con Cheque"),
        'cheque_seq': fields.many2one('ir.sequence', 'Secuencia cheque'),
        'transacciones': fields.boolean('Tipo Transaccion', help="Indica si el diario es para Transacciones"),
    }

    _defaults = {
        'summarized_payment': False,
    }


class payment_line(models.Model):
    _inherit = "payment.line"

    amount_to_text = fields2.Char(string='Monto en letras', compute="_set_amount_to_text")
    other_partner_id = fields2.Many2one('res.partner', string='Beneficiario', required=True)
    bank = fields2.Many2one("res.bank", related="bank_id.bank", string="Banco")
    numero_cheque = fields2.Char(string='Numero de Cheque', help="Numero de Cheque")

    def onchange_other_partner_id(self, cr, uid, ids, other_partner_id, context):
        res = {}
        if other_partner_id:
            other_partner = self.pool.get('res.partner').browse(cr, uid, other_partner_id, context=context)
            if other_partner.default_bank_id:
                res = {'value': {'bank_id': other_partner.default_bank_id.id}}
            else:
                res = {'value': {'bank_id': False}}
        return res

    def onchange_partner(self, cr, uid, ids, partner_id, mode, context=None):
        res = super(payment_line, self).onchange_partner(cr, uid, ids, partner_id, mode, context=context)
        res['value'].update({'other_partner_id': partner_id})
        return res

    @api.multi
    def _set_amount_to_text(self):
        for a in self:
            a.amount_to_text = report_tools.avancys_amount_to_text_decimal(a.amount_currency, a.env.user.lang,
                                                                           a.currency.name)


class account_voucher(models.Model):
    _inherit = "account.voucher"

    other_partner_id = fields2.Many2one('res.partner', string='Beneficiario', readonly=True,
                                        states={'draft': [('readonly', False)]})
    time_of_process = fields2.Datetime(string='Fecha Transmision', readonly=True)
    mode = fields2.Many2one('payment.mode', string='Payment Mode', select=True, readonly=True,
                            help='seleccione el metodo de pago.', states={'draft': [('readonly', False)]})
    bank_account_id = fields2.Many2one('res.partner.bank', string='Cuenta Banco Beneficiario', readonly=True,
                                       required=False, states={'draft': [('readonly', False)]})
    file_text = fields2.Binary(string="Archivo Pago Banco", readonly=True)
    file_name = fields2.Char(size=64, string='Archivo Pago Banco', track_visibility='onchange', readonly=True)
    efectivo = fields2.Boolean(string='Tipo Efectivo', help="Indica si el diario es para pagos en Efectivo")
    cheque = fields2.Boolean(string='Tipo Cheque')
    transacciones = fields2.Boolean(string='Tipo Transaccion', help="Indica si el diario es para Transacciones")
    numero_cheque = fields2.Char(string='Numero de Cheque', help="Numero de Cheque")
    type_payment = fields2.Selection([('payment', 'Pago'), ('receipt', 'Recaudo')], string='Tipo')

    def del_blank_lines(self, cr, uid, ids, context=None):
        vou_obj = self.browse(cr, uid, ids, context=context)
        for line in vou_obj.line_cr_ids:
            if line.amount == 0:
                line.unlink()
        for line in vou_obj.line_dr_ids:
            if line.amount == 0:
                line.unlink()
        return True

    def onchange_mode(self, cr, uid, ids, mode, context=None):
        res = {'value': {'type_payment': context.get('type', False)}}
        if mode:
            journal = self.pool.get('payment.mode').browse(cr, uid, mode, context=context).journal
            res = {'value': {'journal_id': journal.id, 'efectivo': journal.efectivo, 'cheque': journal.cheque,
                             'transacciones': journal.transacciones}}
        return res

    def proforma_voucher(self, cr, uid, ids, context=None):
        self.del_blank_lines(cr, uid, ids, context=None)
        res = super(account_voucher, self).proforma_voucher(cr, uid, ids, context=context)
        for voucher in self.browse(cr, uid, ids, context=context):
            if voucher.numero_cheque and voucher.move_id:
                cr.execute(''' UPDATE account_move_line set ref2=%s WHERE move_id = %s''',
                           (voucher.numero_cheque, voucher.move_id.id))
        return True

    def cancel_voucher(self, cr, uid, ids, context=None):
        self.del_blank_lines(cr, uid, ids, context=None)
        res = super(account_voucher, self).cancel_voucher(cr, uid, ids, context=context)
        return True


class purchase_advance_supplier(osv.osv):
    _inherit = "purchase.advance.supplier"
    _columns = {
        'other_partner_id': fields.many2one('res.partner', 'Beneficiario', required=True, readonly=True,
                                            states={'draft': [('readonly', False)]}),
        'time_of_process': fields.datetime('Fecha Transmision', readonly=True),
        'mode': fields.many2one('payment.mode', 'Payment Mode', select=True, help='Seleccione el metodo de pago.',
                                readonly=True, states={'validated': [('readonly', False)]}),
        'bank_account_id': fields.many2one('res.partner.bank', 'Cuenta Banco Beneficiario', readonly=True,
                                           required=False, states={'draft': [('readonly', False)]}),
        'reference': fields.char(size=64, string='Reference Payment'),
        'file_text': fields.binary(string="Archivo Pago Banco", readonly=True),
        'file_name': fields.char(size=64, string='Archivo Pago Banco', track_visibility='onchange', readonly=True),
    }

    def onchange_other_partner_id(self, cr, uid, ids, other_partner_id, context):
        res = {}
        if other_partner_id:
            other_partner = self.pool.get('res.partner').browse(cr, uid, other_partner_id, context=context)
            if other_partner.default_bank_id:
                res = {'value': {'bank_account_id': other_partner.default_bank_id.id}}
            else:
                res = {'value': {'bank_account_id': False}}
        return res

    def onchange_partner_id(self, cr, uid, ids, partner_id, context=None):
        res = {'value': {'other_partner_id': partner_id}}
        return res

    def onchange_mode(self, cr, uid, ids, mode, context=None):
        res = {}
        if mode:
            res = {'value': {
                'journal_bank_id': self.pool.get('payment.mode').browse(cr, uid, mode, context=context).journal.id}}
        return res


class FilePaymentConfig(models.Model):
    _name = 'account.payment.file.config'

    bank_id = fields2.Many2one('res.bank', 'Banco')
    state = fields2.Selection([('inactive', 'Inactiva'), ('active', 'Activa')], default='inactive')
    header_line_ids = fields2.One2many('acocunt.payment.config.line', 'header_config_id', 'Lineas')
    detail_line_ids = fields2.One2many('acocunt.payment.config.line', 'payment_config_id', 'Lineas')
    footer = fields2.Boolean('Footer instead header')

    _sql_constraints = [
        ('unique_bank_id', 'unique(bank_id)', 'No pueden existir mas de dos configuraciones del mismo banco'),
    ]


class FilePaymentConfigLine(models.Model):
    _name = 'acocunt.payment.config.line'

    payment_config_id = fields2.Many2one('account.payment.file.config', 'Configuracion detalle')
    header_config_id = fields2.Many2one('account.payment.file.config', 'Configuracion encabezado')
    content = fields2.Text('Contenido')
    advance_content = fields2.Text('Contenido - Anticipos')
    content_type = fields2.Selection([('plain', 'Contenido plano'), ('context', 'Contexto'), ('python', 'Python')])
    name = fields2.Char('Nombre')
    size = fields2.Integer('Tamaño')
    adjust = fields2.Boolean('Ajuste a tamaño',
                             help='Marque esta opción si requiere que se ajuste el resultado al tamaño indicado anteriormente.')
    align = fields2.Selection([('right', 'Derecha'), ('left', 'Izquierda')], 'Alineacion')
    fill = fields2.Char('Caracter de relleno')
    sequence = fields2.Integer('Secuencia')
