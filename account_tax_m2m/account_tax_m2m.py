from openerp import models, api, _, fields


class AccountTax(models.Model):
    _inherit = 'account.tax'
    _name = 'account.tax'

    child_ids = fields.Many2many('account.tax', 'account_tax_tax_rel', 'account_tax_id', 'account_tax_id_child', string="Child Tax Accounts")

