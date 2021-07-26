# -*- coding: utf-8 -*-
import time
import sys
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
from openerp import addons
from openerp import SUPERUSER_ID
import itertools
from dateutil.relativedelta import relativedelta
from lxml import etree
from openerp.osv import osv,fields
from openerp import api,models
from openerp import fields as fields2
from openerp.tools.translate import _
from openerp.exceptions import except_orm, Warning, RedirectWarning
import openerp.addons.decimal_precision as dp
import math
import progressbar
from collections import OrderedDict, defaultdict

class res_company(osv.osv):
    _inherit = "res.company"

    _columns = {
        'limit_ajuste_peso':fields.float("Limite Ajuste al Peso", digits_compute=dp.get_precision('Account'), help="Esta es una politica de compañia, el sistema dentra en cuenta este valor, como valor maximo en la diferencia en la conciliacion de dos cuentas. Aplica para el proceso de conciliacion masiva y cruce de cuentas."),
        'journal_ajustes_id':fields.many2one('account.journal', string="Diario Ajuste al Peso", digits_compute=dp.get_precision('Account'), help="Diario para los movimientos de ajustes al peso"),
        'account_ajuste_id':fields.many2one('account.account', string="Ganancia Ajuste al Peso", help="Cuenta para los movimientos de ajustes al peso"),
        'account_ajuste_id2':fields.many2one('account.account', string="Perdida Ajuste al Peso", help="Cuenta para los movimientos de ajustes al peso"),
    }

    _defaults = {
        'limit_ajuste_peso': 0.0,
    }


class account_config_settings_cartera(osv.osv_memory):
    _name = 'account.config.settings.cartera'
    _inherit = 'res.config.settings'


    def _set_default_limit_cartera(self, cr, uid, context=None):
        return self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.limit_ajuste_peso or 0.0

    def _set_default_journal_cartera(self, cr, uid, context=None):
        return self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.journal_ajustes_id.id

    def _set_default_account_cartera(self, cr, uid, context=None):
        return self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.account_ajuste_id.id

    def _set_default_account_cartera2(self, cr, uid, context=None):
        return self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.account_ajuste_id2.id

    _columns = {
        'limit_ajuste_peso':fields.float("Limite Ajuste al Peso", digits_compute=dp.get_precision('Account'), help="Esta es una politica de compañia, el sistema dentra en cuenta este valor, como valor maximo en la diferencia en la conciliacion de dos cuentas. Aplica para el proceso de conciliacion masiva y cruce de cuentas."),
        'account_ajuste_id':fields.many2one('account.account', string="Ganancia Ajuste al Peso", required=True, help="Cuenta para los movimientos de ajustes al peso", domain="[('type','!=','view')]"),
        'account_ajuste_id2':fields.many2one('account.account', string="Perdida Ajuste al Peso", required=True, help="Cuenta para los movimientos de ajustes al peso", domain="[('type','!=','view')]"),
        'journal_ajustes_id':fields.many2one('account.journal', string="Diario Ajuste al Peso", required=True, help="Diario para los movimientos de ajustes al peso", domain="[('type','=','general')]"),
    }

    _defaults = {
        'limit_ajuste_peso': _set_default_limit_cartera,
        'journal_ajustes_id': _set_default_journal_cartera,
        'account_ajuste_id': _set_default_account_cartera,
        'account_ajuste_id2': _set_default_account_cartera2,
    }

    def execute_cartera(self, cr, uid, ids, context=None):
        if uid == 1:
            for res in self.browse(cr, uid, ids, context=context):
                company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
                cr.execute(''' UPDATE res_company SET  limit_ajuste_peso=%s, journal_ajustes_id=%s, account_ajuste_id=%s, account_ajuste_id2=%s WHERE id = %s''',(res.limit_ajuste_peso, res.journal_ajustes_id.id, res.account_ajuste_id.id, res.account_ajuste_id2.id, company_id))
        return True


class account_move_line_reconcile_avancys(models.TransientModel):
    _name = 'account.move.line.reconcile.avancys'

    def _default_company(self):
        user = self.pool.get('res.users').browse(self._cr, self._uid, self.ids, context=self.env.context)
        if user.company_id:
            return user.company_id.id
        return self.pool.get('res.company').search(self._cr, self._uid, [('parent_id', '=', False)])[0]

    partners = fields2.Boolean(string='Varios Terceros')
    move_ids = fields2.Many2many('account.move.line', 'ref_account_move_line_reconcile', 'move_id', string='reconcile_id')
    partner_id = fields2.Many2one('res.partner', string="Tercero")
    partner_ids = fields2.Many2many('res.partner', string="Terceros")
    company_id = fields2.Many2one('res.company', string="Compania", required=True, default=_default_company)


    @api.multi
    def invoice_reconcile(self):
        move_line_obj = self.env['account.move.line']
        move_rec_obj = self.env['account.move.reconcile']
        seq_obj = self.pool.get('ir.sequence')
        currency_obj = self.pool.get('res.currency')
        period_obj = self.env['account.period']
        account_move_obj = self.env['account.move']
        move_line_obj_old = self.pool.get('account.move.line')
        orm2sql = self.env['avancys.orm2sql']

        company_id = self.company_id
        currency_id = company_id.currency_id
        limit_ajuste_peso = company_id.limit_ajuste_peso
        account_ajuste_id = company_id.account_ajuste_id
        account_ajuste_id2 = company_id.account_ajuste_id2
        journal_id = company_id.journal_ajustes_id
        dict={}
        cont = 1
        cont2 = 1
        l_ids = []
        new_active_ids = []
        date = datetime.now().date()

        if self.company_id.name == 'Colombiana De Vigilancia Y Seguridad Ltda Colviseg Ltda':
            raise osv.except_osv(_('Error !'), _('No es posible conciliar facturas en su compañia; comuniquese con su administrador.'))

        for rec in self:
            if not account_ajuste_id or not account_ajuste_id2:
                raise osv.except_osv(_('Configuration !'), _("Por favor configure una cuenta de ajustes al peso en la parametrizacion de la compañia."))
            if not journal_id:
                raise osv.except_osv(_('Configuration !'), _("Por favor configure un diario de ajuste al peso en la configuracion de la compañia. Actualmente tiene configurado un valor de tolerancia de '%s'."  % limit_ajuste_peso))
            period_id = period_obj.search([('date_start','<=',date),('date_stop','>=',date)], limit=1)
            if not period_id:
                raise osv.except_osv(_('Configuration !'), _("No existe un periodo para la fecha '%s'."  % date))
            if rec.partners:
                if rec.partner_ids:
                    partner_list = rec.partner_ids
                else:
                    partner_list = self.env['res.partner'].search([])
                i, bar = 0, progressbar.ProgressBar(max_value=len(partner_list), redirect_stdout=True,
                                                    redirect_stderr=True, widgets=orm2sql.widgets()).start()
                for partner in partner_list:
                    active_ids = move_line_obj.search([('partner_id','=',partner.id),('ref1','!=',False),('reconcile_id','=',False), ('account_id.reconcile','=',True),('move_id.state','=','posted'),('state','=','valid')])
                    if active_ids:
                        for p_rec in active_ids:
                            key = (p_rec.ref1 ,p_rec.account_id.id)
                            if key not in dict:
                                dict[key]=[p_rec.id]
                                if p_rec.reconcile_partial_id:
                                    for l in p_rec.reconcile_partial_id.line_partial_ids:
                                        if l.id != p_rec.id:
                                            dict[key].append(l.id)
                            else:
                                if p_rec.reconcile_partial_id:
                                    for l in p_rec.reconcile_partial_id.line_partial_ids:
                                        dict[key].append(l.id)
                                else:
                                    dict[key].append(p_rec.id)
                        for new_ids in dict.values():
                            cont2 += 1
                            if len(new_ids)>1:
                                self._cr.execute(''' SELECT SUM(debit), SUM(credit), account_id FROM account_move_line WHERE id in %s GROUP BY account_id''',(tuple(new_ids),))
                                result = self._cr.fetchall()
                                for res in result:
                                    n_debit = float(res[0] or 0.0),
                                    n_credit= float(res[1] or 0.0),
                                    account_id= res[2],

                                if isinstance(n_debit, (list, tuple)):
                                    n_debit = n_debit[0]
                                else:
                                    n_debit = n_debit

                                if isinstance(n_credit, (list, tuple)):
                                    n_credit = n_credit[0]
                                else:
                                    n_credit = n_credit

                                diff = float(n_debit-n_credit)
                                dif = currency_obj.is_zero(self._cr, SUPERUSER_ID, currency_id, diff)
                                if n_credit > 0 and n_debit > 0 and not dif:
                                    if abs(diff) < limit_ajuste_peso:
                                        ref = str(new_ids)
                                        move = {
                                            'journal_id': journal_id.id,
                                            'date': date,
                                            'period_id': period_id.id,
                                            'ref': ref,
                                            'state': 'posted',
                                        }
                                        move_id = account_move_obj.create(move)
                                        move_id.post()

                                        account_debit_id = account_id[0]
                                        account_credit_id = account_id[0]


                                        if diff > 0.0:
                                            account_debit_id = account_ajuste_id2.id
                                        else:
                                            account_credit_id = account_ajuste_id.id

                                        self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_debit_id, partner.id, abs(diff), 0.0, date, 'valid'))
                                        move_line_id1 = self._cr.fetchone()[0]

                                        self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_credit_id, partner.id, 0.0, abs(diff), date, 'valid'))
                                        move_line_id2 = self._cr.fetchone()[0]

                                        if diff > 0.0:
                                            new_ids.append(move_line_id2)
                                        else:
                                            new_ids.append(move_line_id1)

                                        dif= True
                                    else:
                                        cont += 1
                                        type = 'Masivo Parcial'
                                        seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                                        name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                                        self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES 
                                                (%s,%s,%s) RETURNING id''' ,
                                                (time.strftime('%Y-%m-%d'),name,type))
                                        r_id = self._cr.fetchone()[0]
                                        move_line_obj_old.write(self._cr, SUPERUSER_ID, new_ids, {'reconcile_partial_id': r_id}, context=self._context)
                                        for new_id in new_ids:
                                            l_ids.append(new_id)
                                if dif:
                                    cont += 1
                                    type = 'Masivo Total'
                                    seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                                    name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                                    self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES 
                                            (%s,%s,%s) RETURNING id''' ,
                                            (time.strftime('%Y-%m-%d'),name,type))
                                    r_id = self._cr.fetchone()[0]
                                    move_line_obj_old.write(self._cr, SUPERUSER_ID, new_ids, {'reconcile_id': r_id}, context=self._context)
                                    for new_id in new_ids:
                                        l_ids.append(new_id)
                    self._cr.commit()
                    i += 1
                    bar.update(i, bar.widgets[7].update_mapping(item=partner.id))
            else:
                partner = rec.partner_id
                active_ids = move_line_obj.search([('partner_id','=',partner.id),('ref1','!=',False),('reconcile_id','=',False), ('account_id.reconcile','=',True),('move_id.state','=','posted'),('state','=','valid')])
                if active_ids:
                    for p_rec in active_ids:
                        key = (p_rec.ref1 ,p_rec.account_id.id)
                        if key not in dict:
                            dict[key]=[p_rec.id]
                            if p_rec.reconcile_partial_id:
                                for l in p_rec.reconcile_partial_id.line_partial_ids:
                                    if l.id != p_rec.id:
                                        dict[key].append(l.id)
                        else:
                            if p_rec.reconcile_partial_id:
                                for l in p_rec.reconcile_partial_id.line_partial_ids:
                                    dict[key].append(l.id)
                            else:
                                dict[key].append(p_rec.id)

                    for new_ids in dict.values():
                        cont2 += 1
                        if len(new_ids)>1:
                            self._cr.execute(''' SELECT SUM(debit), SUM(credit), account_id FROM account_move_line WHERE id in %s GROUP BY account_id''',(tuple(new_ids),))
                            result = self._cr.fetchall()
                            for res in result:
                                n_debit = float(res[0] or 0.0),
                                n_credit= float(res[1] or 0.0),
                                account_id= res[2],

                            if isinstance(n_debit, (list, tuple)):
                                n_debit = n_debit[0]
                            else:
                                n_debit = n_debit

                            if isinstance(n_credit, (list, tuple)):
                                n_credit = n_credit[0]
                            else:
                                n_credit = n_credit

                            diff = float(n_debit-n_credit)
                            dif = currency_obj.is_zero(self._cr, SUPERUSER_ID, currency_id, diff)
                            if n_credit > 0 and n_debit > 0 and not dif:
                                if abs(diff) < limit_ajuste_peso:
                                    ref = str(new_ids)
                                    move = {
                                        'journal_id': journal_id.id,
                                        'date': date,
                                        'period_id': period_id.id,
                                        'ref': ref,
                                        'state': 'posted',
                                    }
                                    move_id = account_move_obj.create(move)
                                    move_id.post()

                                    account_debit_id = account_id[0]
                                    account_credit_id = account_id[0]


                                    if diff > 0.0:
                                        account_debit_id = account_ajuste_id2.id
                                    else:
                                        account_credit_id = account_ajuste_id.id

                                    self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_debit_id, partner.id, abs(diff), 0.0, date, 'valid'))
                                    move_line_id1 = self._cr.fetchone()[0]

                                    self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_credit_id, partner.id, 0.0, abs(diff), date, 'valid'))
                                    move_line_id2 = self._cr.fetchone()[0]

                                    if diff > 0.0:
                                        new_ids.append(move_line_id2)
                                    else:
                                        new_ids.append(move_line_id1)

                                    dif= True
                                else:
                                    cont += 1
                                    type = 'Masivo Parcial'
                                    seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                                    name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                                    self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES 
                                            (%s,%s,%s) RETURNING id''' ,
                                            (time.strftime('%Y-%m-%d'),name,type))
                                    r_id = self._cr.fetchone()[0]
                                    move_line_obj_old.write(self._cr, SUPERUSER_ID, new_ids, {'reconcile_partial_id': r_id}, context=self._context)
                                    for new_id in new_ids:
                                        l_ids.append(new_id)
                            if dif:
                                cont += 1
                                type = 'Masivo Total'
                                seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                                name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                                self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES 
                                        (%s,%s,%s) RETURNING id''' ,
                                        (time.strftime('%Y-%m-%d'),name,type))
                                r_id = self._cr.fetchone()[0]
                                move_line_obj_old.write(self._cr, SUPERUSER_ID, new_ids, {'reconcile_id': r_id}, context=self._context)
                                for new_id in new_ids:
                                    l_ids.append(new_id)

        domain = [('id','in',l_ids)]
        contx = {'group_by': ['partner_id','reconcile_ref']}
        return {
            'domain': domain,
            'name': 'Movimientos Conciliados',
            'view_type': 'form',
            'view_mode': 'tree,graph',
            'view_id': False,
            'res_model': 'account.move.line',
            'type': 'ir.actions.act_window',
            'context': contx,
        }

    @api.multi
    def account_reconcile(self):
        seq_obj = self.pool.get('ir.sequence')
        currency_obj = self.pool.get('res.currency')
        period_obj = self.env['account.period']
        account_move_obj = self.env['account.move']
        move_line_obj_old = self.pool.get('account.move.line')
        orm2sql = self.env['avancys.orm2sql']

        company_id = self.company_id
        currency_id = company_id.currency_id
        limit_ajuste_peso = company_id.limit_ajuste_peso
        account_ajuste_id = company_id.account_ajuste_id
        account_ajuste_id2 = company_id.account_ajuste_id2
        journal_id = company_id.journal_ajustes_id
        dict={}
        cont, cont2 = 1, 1
        l_ids = []
        date = datetime.now().date()

        states = ['','f','posted','valid']
        n_debit, n_credit = 0,0

        if not account_ajuste_id or not account_ajuste_id2:
            raise osv.except_osv(_('Configuration !'), _("Por favor configure una cuenta de ajustes al peso en la parametrizacion de la compañia."))
        if not journal_id:
            raise osv.except_osv(_('Configuration !'), _("Por favor configure un diario de ajuste al peso en la configuracion de la compañia. Actualmente tiene configurado un valor de tolerancia de '%s'."  % limit_ajuste_peso))
        period_id = period_obj.search([('date_start','<=',date),('date_stop','>=',date)], limit=1)
        if not period_id:
            raise osv.except_osv(_('Configuration !'), _("No existe un periodo para la fecha '%s'."  % date))
        if self.partners:
            if self.partner_ids:
                partner_list = self.partner_ids
            else:
                partner_list = self.env['res.partner'].search([])
            i, bar = 0, progressbar.ProgressBar(max_value=len(partner_list), redirect_stdout=True,
                                                redirect_stderr=True, widgets=orm2sql.widgets()).start()
            for partner in partner_list:
                dict={}
                cont, cont2 = 1,1
                n_debit, n_credit = 0,0
                self._cr.execute('''SELECT aml.id,aml.partner_id,aml.ref1,aml.reconcile_id,aml.account_id,aml.move_id,aml.state, aml.reconcile_partial_id FROM 
                                account_move_line AS aml WHERE (partner_id = %s and ref1 != %s AND reconcile_id is null AND 
                                (SELECT aa.reconcile FROM account_account AS aa WHERE aa.id = aml.account_id) != %s
                                AND (SELECT am.state FROM account_move AS am WHERE id = aml.move_id) = %s AND state = %s)''',(partner.id,states[0],states[1],states[2],states[3]))
                active_ids = self._cr.dictfetchall()
                if active_ids:
                    for p_rec in active_ids:
                        key = (p_rec['ref1'] ,p_rec['account_id'])
                        if key not in dict:
                            dict[key]=[p_rec['id']]
                            if p_rec['reconcile_partial_id']:
                                self._cr.execute('''SELECT aml.id FROM account_move_line aml WHERE aml.reconcile_partial_id = %s and ref1 = %s and partner_id = %s
                                                    and account_id = %s''',(p_rec['reconcile_partial_id'],p_rec['ref1'],partner.id,p_rec['account_id']))
                                lp_ids = self._cr.fetchall()
                                for l in lp_ids:
                                    if l[0] != p_rec['id']:
                                        dict[key].append(l[0])
                        else:
                            if p_rec['reconcile_partial_id']:
                                self._cr.execute('''SELECT aml.id FROM account_move_line aml WHERE aml.reconcile_partial_id = %s and ref1 = %s and partner_id = %s
                                                    and account_id = %s''',(p_rec['reconcile_partial_id'],p_rec['ref1'],partner.id,p_rec['account_id']))
                                lp_ids = self._cr.fetchall()
                                for l in lp_ids:
                                    dict[key].append(l[0])
                            else:
                                dict[key].append(p_rec['id'])
                    for new_ids in dict.values():
                        cont2 += 1
                        if len(new_ids)>1:
                            self._cr.execute(''' SELECT SUM(debit), SUM(credit), account_id FROM account_move_line WHERE id in %s GROUP BY account_id''',(tuple(new_ids),))
                            result = self._cr.fetchall()
                            for res in result:
                                n_debit = float(res[0] or 0.0),
                                n_credit= float(res[1] or 0.0),
                                account_id= res[2],

                            if isinstance(n_debit, (list, tuple)):
                                n_debit = n_debit[0]
                            else:
                                n_debit = n_debit

                            if isinstance(n_credit, (list, tuple)):
                                n_credit = n_credit[0]
                            else:
                                n_credit = n_credit

                            diff = float(n_debit-n_credit)
                            dif = currency_obj.is_zero(self._cr, SUPERUSER_ID, currency_id, diff)
                            if n_credit > 0 and n_debit > 0 and not dif:
                                if abs(diff) < limit_ajuste_peso:
                                    ref = str(new_ids)
                                    move = {
                                        'journal_id': journal_id.id,
                                        'date': date,
                                        'period_id': period_id.id,
                                        'ref': ref,
                                        'state': 'posted',
                                    }
                                    move_id = account_move_obj.create(move)
                                    move_id.post()

                                    account_debit_id = account_id[0]
                                    account_credit_id = account_id[0]


                                    if diff > 0.0:
                                        account_debit_id = account_ajuste_id2.id
                                    else:
                                        account_credit_id = account_ajuste_id.id

                                    self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_debit_id, partner.id, abs(diff), 0.0, date, 'valid'))
                                    move_line_id1 = self._cr.fetchone()[0]

                                    self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_credit_id, partner.id, 0.0, abs(diff), date, 'valid'))
                                    move_line_id2 = self._cr.fetchone()[0]

                                    if diff > 0.0:
                                        new_ids.append(move_line_id2)
                                    else:
                                        new_ids.append(move_line_id1)

                                    dif= True
                                else:
                                    cont += 1
                                    type = 'Masivo Parcial'
                                    seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                                    name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                                    self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES 
                                                (%s,%s,%s) RETURNING id''',(time.strftime('%Y-%m-%d'),name,type))
                                    r_id = self._cr.fetchone()[0]
                                    self._cr.execute('''UPDATE account_move_line SET (reconcile_partial_id,reconcile_ref) = (%s,%s) WHERE id in %s''',(r_id,name,tuple(new_ids)))
                                    for new_id in new_ids:
                                        l_ids.append(new_id)
                            if dif:
                                cont += 1
                                type = 'Masivo Total'
                                seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                                name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                                self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES 
                                        (%s,%s,%s) RETURNING id''' ,
                                                 (time.strftime('%Y-%m-%d'),name,type))
                                r_id = self._cr.fetchone()[0]
                                self._cr.execute('''UPDATE account_move_line SET (reconcile_id,reconcile_ref) = (%s,%s) WHERE id in %s''',(r_id,name,tuple(new_ids)))
                                for new_id in new_ids:
                                    l_ids.append(new_id)
                # self._cr.commit()
                i += 1
                bar.update(i, bar.widgets[7].update_mapping(item=partner.id))
        else:
            partner = self.partner_id
            self._cr.execute('''SELECT aml.id,aml.partner_id,aml.ref1,aml.reconcile_id,aml.account_id,aml.move_id,aml.state, aml.reconcile_partial_id FROM
                                account_move_line AS aml WHERE (partner_id = %s and ref1 != %s AND reconcile_id is null AND
                                (SELECT aa.reconcile FROM account_account AS aa WHERE aa.id = aml.account_id) != %s
                                AND (SELECT am.state FROM account_move AS am WHERE id = aml.move_id) = %s AND state = %s)''',(partner.id,states[0],states[1],states[2],states[3]))
            active_ids = self._cr.dictfetchall()
            if active_ids:
                for p_rec in active_ids:
                    key = (p_rec['ref1'] ,p_rec['account_id'])
                    if key not in dict:
                        dict[key]=[p_rec['id']]
                        if p_rec['reconcile_partial_id']:
                            self._cr.execute('''SELECT aml.id FROM account_move_line aml WHERE aml.reconcile_partial_id = %s and ref1 = %s and partner_id = %s
                                                    and account_id = %s''',(p_rec['reconcile_partial_id'],p_rec['ref1'],partner.id,p_rec['account_id']))
                            lp_ids = self._cr.fetchall()
                            for l in lp_ids:
                                if l[0] != p_rec['id']:
                                    dict[key].append(l[0])
                    else:
                        if p_rec['reconcile_partial_id']:
                            self._cr.execute('''SELECT aml.id FROM account_move_line aml WHERE aml.reconcile_partial_id = %s and ref1 = %s and partner_id = %s
                                                    and account_id = %s''',(p_rec['reconcile_partial_id'],p_rec['ref1'],partner.id,p_rec['account_id']))
                            lp_ids = self._cr.fetchall()
                            for l in lp_ids:
                                dict[key].append(l[0])
                        else:
                            dict[key].append(p_rec['id'])

                for new_ids in dict.values():
                    cont2 += 1
                    if len(new_ids)>1:
                        self._cr.execute(''' SELECT SUM(debit), SUM(credit), account_id FROM account_move_line WHERE id in %s GROUP BY account_id''',(tuple(new_ids),))
                        result = self._cr.fetchall()
                        for res in result:
                            n_debit = float(res[0] or 0.0),
                            n_credit= float(res[1] or 0.0),
                            account_id= res[2],

                        if isinstance(n_debit, (list, tuple)):
                            n_debit = n_debit[0]
                        else:
                            n_debit = n_debit

                        if isinstance(n_credit, (list, tuple)):
                            n_credit = n_credit[0]
                        else:
                            n_credit = n_credit

                        diff = float(n_debit-n_credit)
                        dif = currency_obj.is_zero(self._cr, SUPERUSER_ID, currency_id, diff)
                        if n_credit > 0 and n_debit > 0 and not dif:
                            if abs(diff) < limit_ajuste_peso:
                                ref = str(new_ids)
                                move = {
                                    'journal_id': journal_id.id,
                                    'date': date,
                                    'period_id': period_id.id,
                                    'ref': ref,
                                    'state': 'posted',
                                }
                                move_id = account_move_obj.create(move)
                                move_id.post()

                                account_debit_id = account_id[0]
                                account_credit_id = account_id[0]


                                if diff > 0.0:
                                    account_debit_id = account_ajuste_id2.id
                                else:
                                    account_credit_id = account_ajuste_id.id

                                self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_debit_id, partner.id, abs(diff), 0.0, date, 'valid'))
                                move_line_id1 = self._cr.fetchone()[0]

                                self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_credit_id, partner.id, 0.0, abs(diff), date, 'valid'))
                                move_line_id2 = self._cr.fetchone()[0]

                                if diff > 0.0:
                                    new_ids.append(move_line_id2)
                                else:
                                    new_ids.append(move_line_id1)

                                dif= True
                            else:
                                cont += 1
                                type = 'Masivo Parcial'
                                seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                                name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                                self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES
                                        (%s,%s,%s) RETURNING id''' ,
                                        (time.strftime('%Y-%m-%d'),name,type))
                                r_id = self._cr.fetchone()[0]
                                move_line_obj_old.write(self._cr, SUPERUSER_ID, new_ids, {'reconcile_partial_id': r_id}, context=self._context)
                                for new_id in new_ids:
                                    l_ids.append(new_id)
                        if dif:
                            cont += 1
                            type = 'Masivo Total'
                            seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                            name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                            self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES
                                    (%s,%s,%s) RETURNING id''' ,
                                    (time.strftime('%Y-%m-%d'),name,type))
                            r_id = self._cr.fetchone()[0]
                            move_line_obj_old.write(self._cr, SUPERUSER_ID, new_ids, {'reconcile_id': r_id}, context=self._context)
                            for new_id in new_ids:
                                l_ids.append(new_id)

        # self._cr.execute('''DELETE FROM account_move_reconcile amr where amr.create_date = '2017-12-21' AND type = 'Masivo Parcial'
        # AND amr.id not in (SELECT reconcile_partial_id from account_move_line where reconcile_partial_id is not null)''')
        domain = [('id','in',l_ids)]
        contx = {'group_by': ['partner_id','reconcile_ref']}
        return {
            'domain': domain,
            'name': 'Movimientos Conciliados',
            'view_type': 'form',
            'view_mode': 'tree,graph',
            'view_id': False,
            'res_model': 'account.move.line',
            'type': 'ir.actions.act_window',
            'context': contx,
        }

    @api.multi
    def automatic_reconcile(self):
        seq_obj = self.pool.get('ir.sequence')
        currency_obj = self.pool.get('res.currency')
        period_obj = self.env['account.period']
        account_move_obj = self.env['account.move']
        move_line_obj_old = self.pool.get('account.move.line')
        orm2sql = self.env['avancys.orm2sql']

        company_id = self.company_id
        currency_id = company_id.currency_id
        limit_ajuste_peso = company_id.limit_ajuste_peso
        account_ajuste_id = company_id.account_ajuste_id
        account_ajuste_id2 = company_id.account_ajuste_id2
        journal_id = company_id.journal_ajustes_id
        dict={}#OrderedDict()
        cont, cont2 = 1, 1
        l_ids = []
        date = datetime.now().date()

        states = [0,'f','posted','valid']
        n_debit, n_credit = 0,0

        if not account_ajuste_id or not account_ajuste_id2:
            raise osv.except_osv(_('Configuration !'), _("Por favor configure una cuenta de ajustes al peso en la parametrizacion de la compañia."))
        if not journal_id:
            raise osv.except_osv(_('Configuration !'), _("Por favor configure un diario de ajuste al peso en la configuracion de la compañia. Actualmente tiene configurado un valor de tolerancia de '%s'."  % limit_ajuste_peso))
        period_id = period_obj.search([('date_start','<=',date),('date_stop','>=',date)], limit=1)
        if not period_id:
            raise osv.except_osv(_('Configuration !'), _("No existe un periodo para la fecha '%s'."  % date))
        if self.partners:
            if self.partner_ids:
                partner_list = self.partner_ids
            else:
                partner_list = self.env['res.partner'].search([])
            i, bar = 0, progressbar.ProgressBar(max_value=len(partner_list), redirect_stdout=True,
                                                redirect_stderr=True, widgets=orm2sql.widgets()).start()
            for partner in partner_list:
                dict={}
                cont, cont2 = 1,1
                n_debit, n_credit = 0,0
                self._cr.execute('''SELECT aml.id,aml.account_id,aml.debit FROM account_move_line AS aml WHERE (aml.partner_id = %s AND aml.debit > %s 
                                    AND aml.credit = %s AND aml.reconcile_id IS NULL AND reconcile_partial_id IS NULL AND (SELECT aa.reconcile FROM account_account 
                                    AS aa WHERE aa.id = aml.account_id) != %s AND (SELECT am.state FROM account_move AS am WHERE id = aml.move_id) = %s AND state = %s) 
                                    ORDER BY aml.write_date''', (partner.id,states[0],states[0],states[1],states[2],states[3]))
                active_ids = self._cr.dictfetchall()
                if active_ids:
                    for deb in active_ids:
                        self._cr.execute('''SELECT aml.id, aml.credit, aml.debit FROM account_move_line AS aml 
                                            INNER JOIN account_account aa ON aa.id = aml.account_id AND aa.reconcile IS TRUE
                                            INNER JOIN account_move am ON am.id = aml.move_id 
                                            WHERE aml.partner_id = {partner_id} AND aml.account_id = {cuenta} AND aml.credit > {liminf} AND aml.credit < {limsup} 
                                            AND am.state = 'posted' AND aml.state = 'valid' 
                                            AND aml.reconcile_id IS NULL AND reconcile_partial_id IS NULL
                                            ORDER BY aml.write_date LIMIT 1'''.format(partner_id = partner.id,cuenta = deb['account_id'],
                                                                                      liminf = deb['debit']-limit_ajuste_peso,limsup = deb['debit']+limit_ajuste_peso))
                        active_id = self._cr.dictfetchall()
                        if active_id:
                            new_ids = [deb['id'],active_id[0]['id']]
                            cont2 += 1
                            account_id = []
                            self._cr.execute(''' SELECT SUM(debit), SUM(credit), account_id FROM account_move_line WHERE id in %s GROUP BY account_id''',(tuple(new_ids),))
                            result = self._cr.fetchall()
                            for res in result:
                                if res[0] > 0:
                                    n_debit = float(res[0]),
                                if res[1] > 0:
                                    n_credit = float(res[1]),
                                account_id += res[2],

                            if isinstance(n_debit, (list, tuple)):
                                n_debit = n_debit[0]
                            else:
                                n_debit = n_debit

                            if isinstance(n_credit, (list, tuple)):
                                n_credit = n_credit[0]
                            else:
                                n_credit = n_credit

                            diff = float(n_debit-n_credit)
                            dif = currency_obj.is_zero(self._cr, SUPERUSER_ID, currency_id, diff)
                            if n_credit > 0 and n_debit > 0 and not dif:
                                if abs(diff) < limit_ajuste_peso:
                                    ref = str(new_ids)
                                    move = {
                                        'journal_id': journal_id.id,
                                        'date': date,
                                        'period_id': period_id.id,
                                        'ref': ref,
                                        'state': 'posted',
                                    }
                                    move_id = account_move_obj.create(move)
                                    move_id.post()

                                    account_debit_id = account_id[0]
                                    account_credit_id = account_id[0]

                                    if diff > 0.0:
                                        account_debit_id = account_ajuste_id2.id
                                    else:
                                        account_credit_id = account_ajuste_id.id

                                    self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_debit_id, partner.id, abs(diff), 0.0, date, 'valid'))
                                    move_line_id1 = self._cr.fetchone()[0]

                                    self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_credit_id, partner.id, 0.0, abs(diff), date, 'valid'))
                                    move_line_id2 = self._cr.fetchone()[0]

                                    if diff > 0.0:
                                        new_ids.append(move_line_id2)
                                    else:
                                        new_ids.append(move_line_id1)

                                    dif = True
                            if dif:
                                cont += 1
                                type = 'Masivo Total'
                                seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                                name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                                self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES 
                                        (%s,%s,%s) RETURNING id''' ,
                                                 (time.strftime('%Y-%m-%d'),name,type))
                                r_id = self._cr.fetchone()[0]
                                self._cr.execute('''UPDATE account_move_line SET (reconcile_id,reconcile_ref) = (%s,%s) WHERE id in %s''',(r_id,name,tuple(new_ids)))
                                for new_id in new_ids:
                                    l_ids.append(new_id)
                            self._cr.commit()
                i += 1
                bar.update(i, bar.widgets[7].update_mapping(item=partner.id))
        else:
            partner = self.partner_id
            self._cr.execute('''SELECT aml.id,aml.account_id,aml.debit FROM account_move_line AS aml WHERE (aml.partner_id = %s AND aml.debit > %s 
                                AND aml.credit = %s AND aml.reconcile_id IS NULL AND reconcile_partial_id IS NULL AND (SELECT aa.reconcile FROM account_account 
                                AS aa WHERE aa.id = aml.account_id) != %s AND (SELECT am.state FROM account_move AS am WHERE id = aml.move_id) = %s AND state = %s) 
                                ORDER BY aml.write_date''', (partner.id,states[0],states[0],states[1],states[2],states[3]))
            active_ids = self._cr.dictfetchall()
            if active_ids:
                for deb in active_ids:
                    self._cr.execute('''SELECT aml.id, aml.credit, aml.debit FROM account_move_line AS aml 
                                        INNER JOIN account_account aa ON aa.id = aml.account_id AND aa.reconcile IS TRUE
                                        INNER JOIN account_move am ON am.id = aml.move_id 
                                        WHERE aml.partner_id = {partner_id} AND aml.account_id = {cuenta} AND aml.credit > {liminf} AND aml.credit < {limsup} 
                                        AND am.state = 'posted' AND aml.state = 'valid' 
                                        AND aml.reconcile_id IS NULL AND reconcile_partial_id IS NULL
                                        ORDER BY aml.write_date LIMIT 1'''.format(partner_id = partner.id,cuenta = deb['account_id'],
                                                                                  liminf = deb['debit']-limit_ajuste_peso,limsup = deb['debit']+limit_ajuste_peso))
                    active_id = self._cr.dictfetchall()
                    if active_id:
                        new_ids = [deb['id'],active_id[0]['id']]
                        cont2 += 1
                        account_id = []
                        self._cr.execute(''' SELECT SUM(debit), SUM(credit), account_id FROM account_move_line WHERE id in %s GROUP BY account_id''',(tuple(new_ids),))
                        result = self._cr.fetchall()
                        for res in result:
                            if res[0] > 0:
                                n_debit = float(res[0]),
                            if res[1] > 0:
                                n_credit = float(res[1]),
                            account_id += res[2],

                        if isinstance(n_debit, (list, tuple)):
                            n_debit = n_debit[0]
                        else:
                            n_debit = n_debit

                        if isinstance(n_credit, (list, tuple)):
                            n_credit = n_credit[0]
                        else:
                            n_credit = n_credit

                        diff = float(n_debit-n_credit)
                        dif = currency_obj.is_zero(self._cr, SUPERUSER_ID, currency_id, diff)
                        if n_credit > 0 and n_debit > 0 and not dif:
                            if abs(diff) < limit_ajuste_peso:
                                ref = str(new_ids)
                                move = {
                                    'journal_id': journal_id.id,
                                    'date': date,
                                    'period_id': period_id.id,
                                    'ref': ref,
                                    'state': 'posted',
                                }
                                move_id = account_move_obj.create(move)
                                move_id.post()

                                account_debit_id = account_id[0]
                                account_credit_id = account_id[0]

                                if diff > 0.0:
                                    account_debit_id = account_ajuste_id2.id
                                else:
                                    account_credit_id = account_ajuste_id.id

                                self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_debit_id, partner.id, abs(diff), 0.0, date, 'valid'))
                                move_line_id1 = self._cr.fetchone()[0]

                                self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, ref, period_id, account_id,  partner_id, debit, credit, date, state) VALUES
                                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''', (move_id.id, company_id.id, journal_id.id, 'Ajuste al Peso', ref, period_id.id, account_credit_id, partner.id, 0.0, abs(diff), date, 'valid'))
                                move_line_id2 = self._cr.fetchone()[0]

                                if diff > 0.0:
                                    new_ids.append(move_line_id2)
                                else:
                                    new_ids.append(move_line_id1)

                                dif = True
                        if dif:
                            cont += 1
                            type = 'Masivo Total'
                            seq = seq_obj.search(self._cr, SUPERUSER_ID, [('code', '=', 'account.reconcile')])
                            name = seq_obj.next_by_id(self._cr, SUPERUSER_ID, seq[0], context=self._context)
                            self._cr.execute('''INSERT INTO account_move_reconcile (create_date,name,type) VALUES
                                    (%s,%s,%s) RETURNING id''', (time.strftime('%Y-%m-%d'),name,type))
                            r_id = self._cr.fetchone()[0]
                            move_line_obj_old.write(self._cr, SUPERUSER_ID, new_ids, {'reconcile_id': r_id}, context=self._context)
                            for new_id in new_ids:
                                l_ids.append(new_id)
                        self._cr.commit()

        domain = [('id','in',l_ids)]
        contx = {'group_by': ['partner_id','reconcile_ref']}
        return {
            'domain': domain,
            'name': 'Movimientos Conciliados',
            'view_type': 'form',
            'view_mode': 'tree,graph',
            'view_id': False,
            'res_model': 'account.move.line',
            'type': 'ir.actions.act_window',
            'context': contx,
        }

class account_invoice(osv.Model):
    _inherit = 'account.invoice'

    def invoice_validate(self, cr, uid, ids, context=None):
        res = super(account_invoice, self).invoice_validate(cr, uid, ids, context=context)
        for invoice in self.browse(cr, uid, ids, context=context):
            if  invoice.move_id:
                for move_line in invoice.move_id.line_id:
                    self.pool.get('account.move.line').write(cr, uid, [move_line.id], {'ref1': invoice.number, 'ref2': invoice.ref2}, context=context)
        return res