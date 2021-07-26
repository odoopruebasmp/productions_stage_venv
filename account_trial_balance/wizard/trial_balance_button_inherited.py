from openerp.osv import osv, fields

class trial_balance_button_inherited(osv.osv_memory):
    
    _inherit = "account.balance.report"

    _columns = {
        'journal_ids': fields.many2many('account.journal', 'account_balance_report_journal_rel', 'account_id', 'journal_id', 'Journals', readonly=True),
        'level': fields.integer('Level'),
        'selected_account_ids' : fields.many2many('account.account','account_trial_balance_ids','selected_account_ids','account_id','Accounts')
    }

    _defaults = {
        'selected_account_ids' : [],
        'journal_ids': [],
    }

    def default_get(self, cr, uid, fields, context=None):
        
        res = super(trial_balance_button_inherited, self).default_get(cr, uid, fields, context=context)
        if context.get('active_model','') == 'account.account' and context.get('active_ids',False):
            res['selected_account_ids'] = context.get('active_ids',[])
        return res
        
    
    def _print_report(self, cr, uid, ids, data, context=None):
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        for record in self.browse(cr, uid, ids, context):
            data.get('form',{}).update({'level': record.level})
            acc_ids = [x.id for x in record.selected_account_ids]
            data.get('form',{}).update({'account_ids':acc_ids})
        return {'type': 'ir.actions.report.xml', 'report_name': 'account.account.balance.inherit', 'datas': data}


trial_balance_button_inherited()
