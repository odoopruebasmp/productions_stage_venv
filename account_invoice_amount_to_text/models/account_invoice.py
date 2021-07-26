# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp.addons.avancys_tools.report_tools import avancys_amount_to_text_decimal
from datetime import datetime

class AccountInvoiceAmounttoText(models.Model):
    _inherit = "account.invoice"

    amount_to_text = fields.Char(string='Monto en letras', compute="_set_amount_to_text")

    @api.one
    @api.depends('amount_total')
    def _set_amount_to_text(self):
        self.amount_to_text = avancys_amount_to_text_decimal(self.amount_total, self.env.user.lang,
                                                             self.currency_id.name)

    @api.one
    def set_mass_amount_to_text(self):
        date_start = datetime.now()
        invoice = self.env['account.invoice'].search([])
        c=0
        for x in invoice:
            date_start2 = datetime.now()
            c += 1
            #x.amount_to_text = avancys_amount_to_text_decimal(x.amount_total)
            self.env.cr.execute(''' UPDATE account_invoice SET amount_to_text = '{amount_to_text}' WHERE id = {id}'''.format(amount_to_text=avancys_amount_to_text_decimal(x.amount_total,x.env.user.lang,x.currency_id.name),id=x.id))
            if c%2==0:
                self.env.cr.commit()
            date_end2 = datetime.now() - date_start2
            date_end = datetime.now() - date_start2
            print 'van '+str(c)+ ' de : '+str(len(invoice)) + '. tiempo por transaccion: '+str(date_end2)+' tiempo restante: '+str((date_end*len(invoice))/c)
        print 'fin: '+str(datetime.now()-date_start)