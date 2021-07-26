# -*- coding: utf-8 -*-
from openerp import models, fields, api


class XmlMassiveGeneration(models.TransientModel):
    _name = 'xml.massive.generation'

    @api.onchange('invoices')
    def populate_invoices(self):
        txt = ''
        for inv in self.env['account.invoice'].browse(self._context['active_ids'])\
                .filtered(lambda x: x.type != 'in_invoice' and x.state in ['open', 'paid'] and x.ei_state == 'pending'):
            inv_s = 'Abierta' if inv.state == 'open' else 'Pagada'
            txt += u'- {n}  -  {p}  -  {s} \n'.format(n=inv.number, p=inv.partner_id.name, s=inv_s)
        self.invoices = txt

    invoices = fields.Text('Facturas a procesar', readonly=True, help="Facturas con Estado XML 'No Transferido'")

    @api.multi
    def massive_ei_generation(self):
        for inv in self.env['account.invoice'].browse(self._context['active_ids'])\
                .filtered(lambda x: x.type != 'in_invoice' and x.state in ['open', 'paid'] and x.ei_state == 'pending'):
            inv._gen_xml_invoice()
