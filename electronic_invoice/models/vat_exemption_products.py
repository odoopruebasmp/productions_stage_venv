# -*- coding: utf-8 -*-
from openerp import models, fields, api
from datetime import datetime

class VatExcemptionProductsConfig(models.Model):
    _name = 'vat.excemption.products.config'
    _description = 'Configuracion para dias sin IVA'
    name = fields.Char(string='Descripcion')
    products_ids = fields.Many2many(
        comodel_name='product.product',
        string='Productos Excluidos')
    excempted_days_ids = fields.One2many('vat.excemption.day',
                                         'excemption_config_id',
                                         string='Dias de exención')


class VatExcemptionDay(models.Model):
    _name = 'vat.excemption.day'
    _description = 'Configuracion para dias sin IVA'

    name = fields.Date(string='Fecha')
    excemption_config_id = fields.Many2one('vat.excemption.products.config')


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def button_reset_taxes(self):
        today = datetime.today().strftime('%Y-%m-%d')
        for line in self.invoice_line:
            vat_excemption_config = self.env['vat.excemption.products.config'].search(
                [('products_ids', '=', line.product_id.id)]
            ).filtered(
                lambda vat_conf: (self.date_invoice or today) in [
                    conf.name for conf in vat_conf.excempted_days_ids]
            )
            if vat_excemption_config:
                line.invoice_line_tax_id = (
                    line.invoice_line_tax_id.filtered(
                        lambda tax: not (0.19 == tax.amount and 'iva' in tax.name.lower())
                    )
                ) 
        return super(AccountInvoice, self).button_reset_taxes()
