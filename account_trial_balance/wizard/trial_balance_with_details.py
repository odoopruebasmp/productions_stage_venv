from openerp.osv import osv, fields

class account_balance_with_details_report(osv.osv_memory):
    _inherit = "account.common.account.report"
    _name = 'account.balance.with.details.report'
    _description = 'Balance de Prueba Terceros'

    _columns = {
        'journal_ids': fields.many2many('account.journal', 'account_balance_report_journal_rel', 'account_id', 'journal_id', 'Journals', required=True),
    }

    _defaults = {
        'journal_ids': [],
    }

    def _print_report(self, cr, uid, ids, data, context=None):
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        return {'type': 'ir.actions.report.xml', 'report_name': 'account.account.balance.with.details', 'datas': data}

account_balance_with_details_report()
