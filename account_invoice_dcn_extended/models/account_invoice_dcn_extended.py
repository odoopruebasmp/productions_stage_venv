# -*- coding: utf-8 -*-
from openerp import models, fields, api
from openerp.exceptions import Warning
from lxml import etree


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.model
    def _prepare_refund(self, invoice, date=None, period_id=None, description=None, journal_id=None):
        # noinspection PyProtectedMember
        res = super(AccountInvoice, self)._prepare_refund(invoice, date=date, period_id=period_id,
                                                          description=description, journal_id=journal_id)
        res['invoice_out_refund_id'] = invoice.id
        res['partner_shipping_id'] = invoice.partner_id.id
        return res

    invoice_in_refund_id = fields.Many2one('account.invoice', 'Factura a Rectificar IN', readonly=True,
                                           states={'draft': [('readonly', False)]}, domain=[('type', '=',
                                           'in_invoice'), ('state', '=', 'open')])  # Domain in sale_extended.py
    invoice_out_refund_id = fields.Many2one('account.invoice', 'Factura a Rectificar OUT', readonly=True,
                                            states={'draft': [('readonly', False)]}, domain=[('type', '=',
                                            'out_invoice'), ('state', '=', 'open')])  # Domain in sale_extended.py
    invoice_out_add_id = fields.Many2one('account.invoice', 'Factura a Adicionar OUT', readonly=True,
                                         states={'draft': [('readonly', False)]}, domain=[('type', '=',
                                         'out_invoice'), ('state', '=', 'open')])  # Domain in sale_extended.py
    invoice_refund_id = fields.Many2one('account.invoice', 'Nota Credito Origen', readonly=True)
    journal_type = fields.Selection(string='Tipo Comprobante', related='journal_id.type', readonly=True)
    residual_in = fields.Float(related='invoice_in_refund_id.residual', string='Saldo pendiente factura original in',
                               readonly=True)
    residual_out = fields.Float(related='invoice_out_refund_id.residual', string='Saldo pendiente factura original out',
                                readonly=True)

    @api.multi
    def action_cancel(self):
        for refund_inv in self:
            if refund_inv.move_id and (refund_inv.invoice_in_refund_id or refund_inv.invoice_out_refund_id):
                invoice = False
                if refund_inv.type == 'in_refund':
                    invoice = refund_inv.invoice_in_refund_id
                elif refund_inv.type == 'out_refund':
                    invoice = refund_inv.invoice_out_refund_id
                if invoice:
                    recs = []
                    for line in refund_inv.move_id.line_id:
                        if line.reconcile_id:
                            recs += [line.reconcile_id.id]
                        if line.reconcile_partial_id:
                            recs += [line.reconcile_partial_id.id]
                    self.env['account.move.reconcile'].browse(recs).unlink()
        res = super(AccountInvoice, self).action_cancel()
        return res

    @api.multi
    def action_move_create(self):
        res = super(AccountInvoice, self).action_move_create()
        move_line_obj = self.env['account.move.line']

        for refund_inv in self:
            if (refund_inv.invoice_in_refund_id or refund_inv.invoice_out_refund_id) and not \
                    refund_inv.invoice_refund_id:
                invoice = False
                if refund_inv.type == 'in_refund':
                    invoice = refund_inv.invoice_in_refund_id
                elif refund_inv.type == 'out_refund':
                    invoice = refund_inv.invoice_out_refund_id

                #validaciones
                if refund_inv.residual > invoice.residual:
                    raise Warning('El valor que se quiere rectificar es mayor al facturado')
                if invoice.payment_term.id != refund_inv.payment_term.id:
                    raise Warning('El plazo de pago para la factura tiene que ser el mismo que el de la factura a '
                                  'rectificar!')
                if invoice.move_id and refund_inv.move_id:
                    refund_inv.move_id.state = 'draft'
                    #ordenar por fecha de vencimiento
                    invoice_recon = move_line_obj.search([('move_id', '=', invoice.move_id.id),
                                                          ('date_maturity', '!=', False)], order='date_maturity asc')
                    refund_recon = move_line_obj.search([('move_id', '=', refund_inv.move_id.id),
                                                         ('date_maturity', '!=', False)], order='date_maturity asc')
                    aux = {}
                    for i, invoice in enumerate(invoice_recon):
                        if invoice.reconcile_id:
                            aux[i] = 0
                        elif invoice.reconcile_partial_id:
                            total = reduce(lambda y,t: (t.debit or 0.0) - (t.credit or 0.0) + y,
                                           invoice.reconcile_partial_id.line_partial_ids, 0.0)
                            aux[i] = abs(total)
                        else:
                            aux[i] = invoice.debit and invoice.debit or invoice.credit

                    for i, refund in enumerate(refund_recon):
                        credit = refund.credit
                        debit = refund.debit

                        if credit:
                            # Se agrega redondeo para no dejar saldos insignificantes por conciliar
                            if credit <= round(aux[i], 4):
                                (refund_recon[i] + invoice_recon[i]).reconcile_partial(writeoff_acc_id=False,
                                                                    writeoff_period_id=invoice.move_id.period_id.id,
                                                                    writeoff_journal_id=refund_inv.journal_id.id)
                            else:
                                j = i+1
                                refund2 = refund_recon[j]
                                credit2 = refund2.credit
                                refund_recon[i].credit = aux[i]
                                credit = credit - aux[i]
                                refund_recon[j].credit = credit2 + credit
                                (refund_recon[i] + invoice_recon[i]).reconcile_partial(writeoff_acc_id=False,
                                                                writeoff_period_id=invoice.move_id.period_id.id,
                                                                writeoff_journal_id=refund_inv.journal_id.id)
                        elif debit:
                            if debit <= aux[i]:
                                (refund_recon[i] + invoice_recon[i]).reconcile_partial(writeoff_acc_id=False,
                                                                writeoff_period_id=invoice.move_id.period_id.id,
                                                                writeoff_journal_id=refund_inv.journal_id.id)
                            else:
                                j = i+1
                                refund2 = refund_recon[j]
                                debit2 = refund2.debit
                                refund_recon[i].debit = aux[i]
                                debit = debit-aux[i]
                                refund_recon[j].debit = debit2+debit
                                (refund_recon[i] + invoice_recon[i]).reconcile_partial(writeoff_acc_id=False,
                                                                writeoff_period_id=invoice.move_id.period_id.id,
                                                                writeoff_journal_id=refund_inv.journal_id.id)
                    refund_inv.move_id.post()
        return res

    @api.multi
    def pull_invoice_lines(self):
        for refund_inv in self:
            invoice = None
            if refund_inv.type == 'in_refund':
                invoice = refund_inv.invoice_in_refund_id
            elif refund_inv.type == 'out_refund':
                invoice = refund_inv.invoice_out_refund_id
            elif refund_inv.type == 'out_invoice' and refund_inv.journal_type == 'sale_add':
                invoice = refund_inv.invoice_out_add_id
            if invoice:
                refund_inv.invoice_line.unlink()
                for line in invoice.invoice_line:
                    line.copy(default={'invoice_id': refund_inv.id, 'invoice_line_refund_id': line.id})
                data = {'account_id': invoice.account_id.id,
                        'currency_id': invoice.currency_id.id,
                        'partner_shipping_id': invoice.partner_shipping_id.id,
                        'fiscal_position': invoice.fiscal_position.id,
                        'tasa_manual': invoice.tasa_manual,
                        'currency_id2': invoice.currency_id2.id,
                        'tasa_cambio_conversion': invoice.tasa_cambio_conversion,
                        'fue_convertida': invoice.fue_convertida,
                        'es_multidivisa': invoice.es_multidivisa,
                        'payment_term': invoice.payment_term.id
                        }
                refund_inv.write(data)
                refund_inv.button_reset_taxes()
        return True


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    invoice_line_refund_id = fields.Many2one('account.invoice.line', 'Linea de Factura', readonly=True)
