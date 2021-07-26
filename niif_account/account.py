# -*- coding: utf-8 -*-
from openerp.osv import osv
from openerp.osv import fields as fields2
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import openerp.netsvc
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil import relativedelta, parser
import openerp.tools
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval
from openerp import models, api, _, fields
from openerp import api



class fpa_financial_reports(models.Model):
    _inherit = "fpa.financial.reports"


    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False,submenu=False):
        company = self.env['res.users'].browse(self._uid).company_id
        if company:
            self._cr.execute(''' UPDATE fpa_financial_reports SET update_niif=%s''',(company.update_niif,))
        result =super(fpa_financial_reports,self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        return result


    update_niif = fields.Datetime(string="Date NIIF", readonly=True, help="Fecha de ultima sincronizacion de los movimientos NIIF")


class res_company(models.Model):
    _inherit = "res.company"

    update_niif = fields.Datetime(string="Ultima Actualizacion proceso niif", default=datetime.now()-timedelta(hours=5))


    @api.model
    def update_move_niif(self):
        companys = self.env['res.company'].search([])
        for company in companys:
            date=datetime.now()-timedelta(hours=5)
            date_from = company.update_niif[0:10]
            #Actualiza movimientos contables con equivalente niif
            self._cr.execute(" UPDATE account_move_line SET account_niif_id = child_id "\
                " FROM account_account_consol_rel aacr WHERE account_move_line.account_id = aacr.parent_id AND account_id IS NOT NULL "\
                " AND account_move_line.create_date >= '%s' "%(date_from,))
            #Actualiza movimientos contables con cuenta niif en campo cuenta
            self._cr.execute(" UPDATE account_move_line SET account_niif_id = account_id "\
                " FROM account_account aa WHERE account_move_line.account_id = aa.id AND niif IS TRUE "\
                " AND account_move_line.create_date >= '%s' "%(date_from,))
            self._cr.execute(''' UPDATE res_company SET update_niif=%s WHERE id=%s''',(date, company.id))
        return True



class report_move_line_niif_massive(models.TransientModel):
    _name = "wizard.move.line.niif.massive"

    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')
    update = fields.Boolean(string='Actualizacion Registros NIIF')
    clean = fields.Boolean(string='Limpiar todos los moves')
    parent_zero = fields.Boolean(string='Calcular Parent Zero')
    account_id = fields.Many2one('account.account', string='Cuenta')
    journal_id = fields.Many2one('account.journal', string='Comprobante')

    @api.multi
    def generar(self):
        
        if (self.update or self.clean) and (self.env['account.period'].search([('date_start', '<=', self.date_from),('date_stop', '>=', self.date_from),('state', '=', 'done')]) or self.env['account.period'].search([('date_start', '<=', self.date_to),('date_stop', '>=', self.date_to),('state', '=', 'done')]) or self.env['account.period'].search([('date_start', '>=', self.date_from),('date_start', '<=', self.date_to),('state', '=', 'done')]) or self.env['account.period'].search([('date_start', '<=', self.date_from),('date_stop', '>=', self.date_to),('state', '=', 'done')])) :
            raise osv.except_osv(_('Error'),_("No es posible realizar la operacion para las fechas configuradas, por favor validar que todos los periodos dentro de las fechas de consulta esten abiertos."))

        if self.clean:
            # if self._uid != 1:
            #     raise osv.except_osv(_('Error'),_("No es posible limpiar los movimientos, solo el administrador puede ejecutar este tipo de operacion."))
            #blanquear movimienos contables para niif antes de ejecutar el proceso
            acc = ''
            jrn = ''
            if self.account_id:
                acc = ''' AND account_id = '%s' ''' % (self.account_id.id)
            if self.journal_id:
                jrn = ''' AND journal_id = '%s' ''' % (self.journal_id.id)

            query = ''' UPDATE account_move_line SET account_niif_id = NULL WHERE date between '%s' AND '%s' ''' % (self.date_from,self.date_to) + acc +jrn
            self._cr.execute(query)

        if self.update:
            #blanquear movimienos contables para niif antes de ejecutar el proceso
            acc = ''
            jrn = ''
            if self.account_id:
                acc = ''' AND account_id = '%s' ''' % (self.account_id.id)
            if self.journal_id:
                jrn = ''' AND journal_id = '%s' ''' % (self.journal_id.id)

            query = ''' UPDATE account_move_line SET account_niif_id = NULL WHERE date between '%s' AND '%s' ''' % (self.date_from,self.date_to) + acc +jrn
            self._cr.execute(query)

            # #Actualiza movimientos contables con equivalente niif
            query = '''UPDATE account_move_line SET write_uid = %s, write_date = now(), account_niif_id = child_id FROM account_account_consol_rel aacr 
                        WHERE account_move_line.account_id = aacr.parent_id AND account_id IS NOT NULL AND account_move_line.date between '%s' AND '%s' 
                        and account_niif_id is Null'''\
                        % (self.env.user.id,self.date_from,self.date_to) + acc + jrn
            self._cr.execute(query)

            #Actualiza movimientos contables con cuenta niif en campo cuenta
            query = ''' UPDATE account_move_line SET write_uid = %s, write_date = now(), account_niif_id = account_id FROM account_account aa 
                        WHERE account_move_line.account_id = aa.id AND niif IS TRUE AND date between '%s' and '%s' 
                        and account_niif_id is Null''' \
                        % (self.env.user.id,self.date_from,self.date_to) + acc + jrn
            self._cr.execute(query)

        if self.parent_zero:
            accounts = self.env['account.account'].search([('active', '=', True)])
            for account_id in accounts:
                account=False
                if account_id.parent_id:
                    account=account_id.parent_id
                    while (account.parent_id):
                        account = account.parent_id
                    account=account.id
                self._cr.execute("UPDATE account_account SET parent_zero=%s WHERE id=%s", (account or None,account_id.id))

        return True



class account_move_line_niif(models.Model):
    _inherit = "account.move.line"

    def onchange_niif(self, cr , uid, ids, account_niif_id, context = None):

        return {'value': {'account_id' : account_niif_id}}

    @api.one
    @api.constrains('account_id','account_niif_id')
    def _check(self):

        if not self.account_niif_id and not self.account_id:
            raise osv.except_osv(_('Error'),_("Debe definir una cuenta del PUC o NIIF."))

    def _check_no_view(self, cr, uid, ids, context=None):

        lines = self.browse(cr, uid, ids, context=context)
        for l in lines:
            if l.account_id.type in ('view'):
                return False
        return True


    account_niif_id = fields.Many2one('account.account', string='Cuenta NIIF', domain=[('niif','=',True),('type','<>','view'), ('type', '<>', 'closed')], select=True)
    not_map = fields.Boolean(string='No mapear niif',default=False)

    _constraints = [
        (_check_no_view, 'You cannot create journal items on an account of type view or consolidation.', ['account_id']),
    ]


class account_account_niif(models.Model):
    _inherit = "account.account"

    niif = fields.Boolean(string='Es NIIF', default=False, select=True)
    deterioro_cartera = fields.Boolean(string='Deterioro Cartera', default=False, select=True)
