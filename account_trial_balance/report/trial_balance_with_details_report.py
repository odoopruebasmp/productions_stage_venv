# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp import pooler

class trial_balance_with_details_report(report_sxw.rml_parse):
    
    def __init__(self,cr,uid,name,context):
        super(trial_balance_with_details_report,self).__init__(cr,uid,name,context=context)
        self.sum_debit = 0.00
        self.sum_credit = 0.00
        self.date_lst = []
        self.date_lst_string = ''
        self.result_acc = []
        self.result_acc1 = []
        self.result_acc2 = []
        self.localcontext.update({
            'time': time,
            'lines': self.lines,
            'account15': self.account15,
            'account2349': self.account2349,
            'account15_total': self.account15_total,
            'account2349_total': self.account2349_total,
            'sum_debit': self._sum_debit,
            'sum_credit': self._sum_credit,
            'get_fiscalyear':self._get_fiscalyear,
            'get_filter': self._get_filter,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period ,
            'get_account': self._get_account,
            'get_journal': self._get_journal,
            'get_start_date':self._get_start_date,
            'get_end_date':self._get_end_date,
            'get_target_move': self._get_target_move,
        })
        self.context = context

    def _sum_debit(self, period_id=False, journal_id=False):
        if journal_id and isinstance(journal_id, int):
            journal_id = [journal_id]
        if period_id and isinstance(period_id, int):
            period_id = [period_id]
        if not journal_id:
            journal_id = self.journal_ids
        if not period_id:
            period_id = self.period_ids
        if not (period_id and journal_id):
            return 0.0
        self.cr.execute('SELECT SUM(debit) FROM account_move_line l '
                        'WHERE period_id IN %s AND journal_id IN %s ' + self.query_get_clause + ' ',
                        (tuple(period_id), tuple(journal_id)))
        return self.cr.fetchone()[0] or 0.0

    def _sum_credit(self, period_id=False, journal_id=False):
        if journal_id and isinstance(journal_id, int):
            journal_id = [journal_id]
        if period_id and isinstance(period_id, int):
            period_id = [period_id]
        if not journal_id:
            journal_id = self.journal_ids
        if not period_id:
            period_id = self.period_ids
        if not (period_id and journal_id):
            return 0.0
        self.cr.execute('SELECT SUM(credit) FROM account_move_line l '
                        'WHERE period_id IN %s AND journal_id IN %s '+ self.query_get_clause+'',
                        (tuple(period_id), tuple(journal_id)))
        return self.cr.fetchone()[0] or 0.0

    def _get_start_date(self, data):
        if data.get('form', False) and data['form'].get('date_from', False):
            return data['form']['date_from']
        return ''

    def _get_target_move(self, data):
        if data.get('form', False) and data['form'].get('target_move', False):
            if data['form']['target_move'] == 'all':
                return _('All Entries')
            return _('All Posted Entries')
        return ''

    def _get_end_date(self, data):
        if data.get('form', False) and data['form'].get('date_to', False):
            return data['form']['date_to']
        return ''

    def get_start_period(self, data):
        if data.get('form', False) and data['form'].get('period_from', False):
            return openerp.registry(self.cr.dbname).get('account.period').browse(self.cr,self.uid,data['form']['period_from']).name
        return ''

    def get_end_period(self, data):
        if data.get('form', False) and data['form'].get('period_to', False):
            return openerp.registry(self.cr.dbname).get('account.period').browse(self.cr, self.uid, data['form']['period_to']).name
        return ''

    def _get_account(self, data):
        if data.get('form', False) and data['form'].get('chart_account_id', False):
            return openerp.registry(self.cr.dbname).get('account.account').browse(self.cr, self.uid, data['form']['chart_account_id']).name
        return ''

    def _get_sortby(self, data):
        raise (_('Error'), _('Not implemented'))

    def _get_filter(self, data):
        if data.get('form', False) and data['form'].get('filter', False):
            if data['form']['filter'] == 'filter_date':
                return 'Date'
            elif data['form']['filter'] == 'filter_period':
                return 'Periods'
        return 'No Filter'

    def _sum_debit_period(self, period_id, journal_id=None):
        journals = journal_id or self.journal_ids
        if not journals:
            return 0.0
        self.cr.execute('SELECT SUM(debit) FROM account_move_line l '
                        'WHERE period_id=%s AND journal_id IN %s '+ self.query_get_clause +'',
                        (period_id, tuple(journals)))

        return self.cr.fetchone()[0] or 0.0

    def _sum_credit_period(self, period_id, journal_id=None):
        journals = journal_id or self.journal_ids
        if not journals:
            return 0.0
        self.cr.execute('SELECT SUM(credit) FROM account_move_line l '
                        'WHERE period_id=%s AND journal_id IN %s ' + self.query_get_clause +' ',
                        (period_id, tuple(journals)))
        return self.cr.fetchone()[0] or 0.0

    def _get_fiscalyear(self, data):
        if data.get('form', False) and data['form'].get('fiscalyear_id', False):
            return openerp.registry(self.cr.dbname).get('account.fiscalyear').browse(self.cr, self.uid, data['form']['fiscalyear_id']).name
        return ''

    def _get_company(self, data):
        if data.get('form', False) and data['form'].get('chart_account_id', False):
            return openerp.registry(self.cr.dbname).get('account.account').browse(self.cr, self.uid, data['form']['chart_account_id']).company_id.name
        return ''

    def _get_journal(self, data):
        codes = []
        if data.get('form', False) and data['form'].get('journal_ids', False):
            self.cr.execute('select code from account_journal where id IN %s',(tuple(data['form']['journal_ids']),))
            codes = [x for x, in self.cr.fetchall()]
        return codes

    def _get_currency(self, data):
        if data.get('form', False) and data['form'].get('chart_account_id', False):
            return openerp.registry(self.cr.dbname).get('account.account').browse(self.cr, self.uid, data['form']['chart_account_id']).company_id.currency_id.symbol
        return ''

    def set_context(self, objects, data, ids, report_type=None):
        new_ids = ids
        if (data['model'] == 'ir.ui.menu'):
            new_ids = 'chart_account_id' in data['form'] and [data['form']['chart_account_id']] or []
            objects = self.pool.get('account.account').browse(self.cr, self.uid, new_ids)
        return super(trial_balance_with_details_report, self).set_context(objects, data, new_ids, report_type=report_type)

    #def _add_header(self, node, header=1):
    #    if header == 0:
    #        self.rml_header = ""
    #    return True

    def _get_account(self, data):
        if data['model']=='account.account':
            return self.pool.get('account.account').browse(self.cr, self.uid, data['form']['id']).company_id.name
        return super(trial_balance_with_details_report ,self)._get_account(data)

    def lines(self, form, ids=[], done=None):#, level=1):
        move_line_obj = self.pool.get('account.move.line')
        fiscal_year_obj = self.pool.get('account.fiscalyear')
        partner_obj = self.pool.get('res.partner')
        def _process_child(accounts, disp_acc, parent):
                account_rec = [acct for acct in accounts if acct['id']==parent][0]
                currency_obj = self.pool.get('res.currency')
                acc_id = self.pool.get('account.account').browse(self.cr, self.uid, account_rec['id'])
                
                currency = acc_id.currency_id and acc_id.currency_id or acc_id.company_id.currency_id
                res = {
                    'id': account_rec['id'],
                    'type': account_rec['type'],
                    'code': account_rec['code'],
                    'name': account_rec['name'],
                    'opening_balance': account_rec['opening_balance'],
                    'level': account_rec['level'],
                    'debit': account_rec['debit'],
                    'credit': account_rec['credit'],
                    'balance': account_rec['balance'],
                    'parent_id': account_rec['parent_id'],
                    'bal_type': '',
                }
                self.sum_debit += account_rec['debit']
                self.sum_credit += account_rec['credit']
                if disp_acc == 'movement':
                    if not currency_obj.is_zero(self.cr, self.uid, currency, res['credit']) or not currency_obj.is_zero(self.cr, self.uid, currency, res['debit']) or not currency_obj.is_zero(self.cr, self.uid, currency, res['balance']):
                        res.get('id')
                        self.result_acc.append(res)
                elif disp_acc == 'not_zero':
                    if not currency_obj.is_zero(self.cr, self.uid, currency, res['balance']):
                        self.result_acc.append(res)
                else:
                    self.result_acc.append(res)
                if res.get('id') and res.get('type') != 'view':
                    self.cr.execute("select partner_id, sum(credit), sum(debit) from account_move_line where account_id=%s and date >='%s'  and date <='%s' group by partner_id" % (str(res.get('id')), str(self.opening_start_date), str(self.opening_end_date)))
                    results = self.cr.fetchall()

                    self.cr.execute("select partner_id, sum(credit), sum(debit) from account_move_line where account_id=%s and date >='%s' and date <='%s' group by partner_id" % (str(res.get('id')), str(self.ending_start_date),  str(self.ending_end_date)))
                    end_results = self.cr.fetchall()

                    for result in results:
                        if result:
                            end_balance = 0.0
                            partner_name = partner_obj.browse(self.cr, self.uid, result[0]).name
                            opening_balance = result[2] - result[1]
                            for end_result in end_results:
                                if end_result[0] == result[0]:
                                    end_balance = end_result[2] - end_result[1]

                            new_res = {
                                'id': res.get('id'),
                                'type': res.get('type'),
                                'code': '',
                                'name': partner_name,
                                'opening_balance': opening_balance,
                                'level': res.get('level',0) + 1,
                                'debit': result[2],
                                'credit': result[1],
                                'balance': end_balance,
                                'parent_id': '',
                                'bal_type': '',
                            }
                            self.result_acc.append(new_res)
                if account_rec['code'] in ['1','5']:
                    self.result_acc1.append(res)
                
                if account_rec['code'] in ['2','3','4','9']:
                    self.result_acc2.append(res)
                
                if account_rec['child_id']:
                    for child in account_rec['child_id']:
                        _process_child(accounts,disp_acc,child)

        obj_account = self.pool.get('account.account')
        if not ids:
            ids = self.ids
        if not ids:
            return []
        if not done:
            done={}

        ctx = self.context.copy()
        fiscal_year_data = fiscal_year_obj.browse(self.cr, self.uid, form['fiscalyear_id'])
        ctx['fiscalyear'] = form['fiscalyear_id']
        self.ending_start_date = False
        self.ending_end_date = False
        if form['filter'] == 'filter_period':
            ctx['period_from'] = form['period_from']
            ctx['period_to'] = form['period_to']
            self.ending_start_date = form['period_from']
            self.ending_end_date = form['period_to']
        elif form['filter'] == 'filter_date':
            ctx['date_from'] = form['date_from']
            ctx['date_to'] =  form['date_to']
            self.ending_start_date = form['date_from']
            self.ending_end_date = form['date_to']
        else:
            self.ending_start_date = fiscal_year_data.date_start
            self.ending_end_date = fiscal_year_data.date_stop


        ctx['state'] = form['target_move']
        parents = ids
        child_ids = obj_account._get_children_and_consol(self.cr, self.uid, ids, ctx)
        if child_ids:
            ids = child_ids
        accounts = obj_account.read(self.cr, self.uid, ids, ['type','code','name','debit','credit','balance','parent_id','level','child_id'], ctx)

        ctxt = self.context.copy()
        ctxt['fiscalyear'] = form['fiscalyear_id']
        self.opening_start_date = False
        self.opening_end_date = False
        if form['filter'] == 'filter_period':
            ctxt['period_from'] = fiscal_year_data.date_start
            ctxt['period_to'] = form['period_from']
            self.opening_start_date = fiscal_year_data.date_start
            self.opening_end_date = form['period_from']
        elif form['filter'] == 'filter_date':
            ctxt['date_from'] = fiscal_year_data.date_start
            ctxt['date_to'] =  form['date_from']
            self.opening_start_date = fiscal_year_data.date_start
            self.opening_end_date = form['date_from']
        else:
            ctxt['date_from'] = fiscal_year_data.date_start
            ctxt['date_to'] =  fiscal_year_data.date_stop
            self.opening_start_date = fiscal_year_data.date_start
            self.opening_end_date = fiscal_year_data.date_stop

        opening_balance = obj_account.read(self.cr, self.uid, ids, ['type','code','name', 'debit','credit','balance','parent_id','level','child_id'], ctxt)

        for account in accounts:
            for open_balance in opening_balance:
                if account.get('id') == open_balance.get('id'):
                    accounts[accounts.index(account)].update({'opening_balance': open_balance.get('balance')})

        for parent in parents:
                if parent in done:
                    continue
                done[parent] = 1
                _process_child(accounts,form['display_account'],parent)
        return self.result_acc
    
    def account15(self):
        return self.result_acc1
    
    def account15_total(self):
        tot_dict = {'name' : 'TOTAL DEBITOS'}
        o_b = credit = debit = balance = 0.0
        for rec in self.result_acc1:
            o_b += rec['opening_balance']
            credit += rec['credit']
            debit += rec['debit']
            balance += rec['balance']
        tot_dict.update({
                         'opening_balance' : o_b,
                         'debit' : debit,
                         'credit':credit,
                         'balance':balance,
                    })
        
        return [tot_dict]
    
    def account2349(self):
        return self.result_acc2
    
    def account2349_total(self):
        tot_dict = {'name' : 'TOTAL CREDITOS'}
        o_b = credit = debit = balance = 0.0
        for rec in self.result_acc2:
            o_b += rec['opening_balance']
            credit += rec['credit']
            debit += rec['debit']
            balance += rec['balance']
        tot_dict.update({
                         'opening_balance' : o_b,
                         'debit' : debit,
                         'credit':credit,
                         'balance':balance,
                    })
        return [tot_dict]
    
report_sxw.report_sxw('report.account.account.balance.with.details','account.account','addons/account_trial_balance/report/trial_balance_with_details_report.rml',parser=trial_balance_with_details_report, header="internal")
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
