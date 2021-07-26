# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning, RedirectWarning
import openerp.addons.decimal_precision as dp
import logging

_logger = logging.getLogger('FLUJO DE CAJA')

class account_financial_reports_accounting_flujocaja(models.Model):
    _name = "fpa.flujocaja"

    date = fields.Datetime(string="Fecha")
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    estado = fields.Selection(
        [('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='todos', string='Estados')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',
                                       help='Select Charts of Accounts', required=True, domain=[('parent_id', '=', False)])


class account_financial_reports_accounting_flujocaja_line(models.Model):
    _name = "fpa.flujocaja.line"

    account_id = fields.Many2one(
        'account.account', string='Cuenta', ondelete='cascade')
    amount_01 = fields.Float(
        string='Enero', digits=dp.get_precision('Account'))
    amount_02 = fields.Float(
        string='Febrero', digits=dp.get_precision('Account'))
    amount_03 = fields.Float(
        string='Marzo', digits=dp.get_precision('Account'))
    amount_04 = fields.Float(
        string='Abril', digits=dp.get_precision('Account'))
    amount_05 = fields.Float(
        string='Mayo', digits=dp.get_precision('Account'))
    amount_06 = fields.Float(
        string='Junio', digits=dp.get_precision('Account'))
    amount_07 = fields.Float(
        string='Julio', digits=dp.get_precision('Account'))
    amount_08 = fields.Float(
        string='Agosto', digits=dp.get_precision('Account'))
    amount_09 = fields.Float(
        string='Septiembre', digits=dp.get_precision('Account'))
    amount_10 = fields.Float(
        string='Octubre', digits=dp.get_precision('Account'))
    amount_11 = fields.Float(
        string='Noviembre', digits=dp.get_precision('Account'))
    amount_12 = fields.Float(
        string='Diciembre', digits=dp.get_precision('Account'))
    amount_total = fields.Float(
        string='Monto total', digits=dp.get_precision('Account'))
    nivel = fields.Integer(string='Nivel')
    cuenta = fields.Char(string='Cuenta')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    description = fields.Text(string="Descripción")
    resume = fields.Boolean(string="Resumen")
    bold = fields.Boolean(string="Bold")
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade')
    encabezado_id = fields.Many2one('fpa.flujocaja', string='Encabezado', ondelete='cascade')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')

class wizard_account_financial_reports_accounting_flujocaja(models.TransientModel):
    _name = "fpa.flujocaja.wizard"

    account_filter = fields.Boolean(string="Filtro adicional de cuentas")
    partner_filter = fields.Boolean(string="Filtro adicional de terceros")
    journal_filter = fields.Boolean(string="Filtro adicional de diarios")
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',
                                       help='Select Charts of Accounts', required=True, domain=[('parent_id', '=', False)])
    company_id = fields.Many2one(
        'res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    period_balance_ids = fields.Many2many('account.period', string='Periodos')
    fiscalyear_id = fields.Many2one(
        'account.fiscalyear', string='Año fiscal',required=True)
    journal_ids = fields.Many2many('account.journal', string='Diarios')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type', '!=', 'view')])
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), (
        'todos', 'Todos')], default='todos', string='Estados', required=True)

    @api.one
    @api.onchange('chart_account_id')
    def get_filter(self):
        id = self.env.context.get('active_ids',False)
        financial_reports = self.env['fpa.financial.reports'].browse(id)
        self.account_filter = financial_reports.account_filter
        self.partner_filter = financial_reports.partner_filter
        self.journal_filter = financial_reports.journal_filter

    @api.one
    @api.constrains('date_froreguetones 2016 lo mas nuevom', 'date_to')
    def _validar_fechas(self):
        if self.date_from > self.date_to:
            raise Warning(_('Error en las fechas!'), _(
                "Las fechas planificadas estan mal configuradas"))

    @api.multi
    def generar(self):
        # self.env.cr.execute(''' DELETE FROM fpa_flujocaja_line WHERE company_id = %s and user_id = %s''' % (
        #     self.company_id.id, self.env.user.id))
        self.env.cr.execute(''' DELETE FROM fpa_flujocaja WHERE company_id = %s and user_id = %s''' % (
            self.company_id.id, self.env.user.id))
        where = ''
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])
        if financial_reports:
            if financial_reports.concepts_ids:
                where = ' AND ( '
                for conceptos in financial_reports.concepts_ids:
                    if conceptos.account_ids and not conceptos.resume:
                        for cuentas in conceptos.account_ids:
                            where += " aa.code like '%s%s' OR" % (cuentas.code,'%')
                where = where[:len(where)-2]
                where += ' ) '

        # Agrega encabezado con parametros indicados por el usuario
        sql = " INSERT INTO fpa_flujocaja(date, date_from, date_to, estado, company_id, user_id, "\
            " chart_account_id,financial_id) VALUES ('%s','%s','%s','%s',%s,%s,%s,%s) RETURNING ID " %(datetime.now(),self.fiscalyear_id.date_start, self.fiscalyear_id.date_stop, self.estado,
            self.company_id.id, self.env.user.id, self.chart_account_id.id, financial_reports.id)
        self.env.cr.execute(sql)
        encabezado_id = False
        try:
            encabezado_id = self.env.cr.fetchone()[0]
        except ValueError:
            encabezado_id = False

        if self.journal_ids:
            where += ''' AND aml.journal_id in (%s) ''' % (
                ','.join(str(x.id) for x in self.journal_ids))
        if self.account_ids:
            if self.chart_account_id.niif:
                where += ''' AND aml.account_niif_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
            else:
                where += ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))

        if self.estado:
            estado = ''
        if self.estado == 'borrador':
            estado = 'draft'
        elif self.estado == 'validados':
            estado = 'valid'
        else:
            estado = '%'
        where += ''' AND aml.state like '%s' ''' % estado

        # Verificar si tiene el modulo de niif_account instalado
        module = self.env['ir.module.module'].search([('name','=','niif_account'),('state','=','installed')])
        if not module:
            condition = 'aa.id = aml.account_id'
        else:
            condition = '((aa.id = aml.account_id AND aa.niif is false)or((aa.id = aml.account_niif_id AND aa.niif is true)))'
        #ingresar movimientos
        movimientos = " INSERT INTO fpa_flujocaja_line (bold,financial_id,user_id,company_id,account_id,cuenta,amount_01,amount_02,amount_03,amount_04,amount_05,"\
                        " amount_06,amount_07,amount_08,amount_09,amount_10,amount_11,amount_12,encabezado_id,nivel,resume,concepts_id) "\
                        " SELECT False,%s,%s, %s, aa.id, aa.code, (CASE "\
                        "    WHEN substring(aml.date::character varying from 6 for 2)::text ='01'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_01, "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='02'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_02,  "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='03'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_03,  "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='04'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_04,  "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='05'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_05,  "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='06'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_06,  "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='07'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_07,  "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='08'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_08,  "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='09'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_09,  "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='10'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_10, "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='11'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_11,  "\
                        "    (CASE WHEN substring(aml.date::character varying from 6 for 2)::text ='12'::text THEN sum(aml.debit - aml.credit) ELSE 0 END) as amount_12, "\
                        " %s::integer as encabezado_id, "\
                        " 100::integer nivel,False,ffrc.id "\
                        " FROM account_move_line aml "\
                        " INNER JOIN account_period ap on ap.id = aml.period_id and ap.special IS FALSE "\
                        " INNER JOIN account_account aa ON %s AND aml.company_id = aa.company_id "\
                        " INNER JOIN fpa_financial_reports_concepts_account ffrca ON ffrca.account_account_id = aa.id "\
                        " INNER JOIN fpa_financial_reports_concepts ffrc ON ffrca.fpa_financial_reports_concepts_id = ffrc.id AND ffrc.financial_reports=%s "\
                        " WHERE  aml.company_id = %s AND aa.parent_zero = %s "\
                        " AND aml.date BETWEEN '%s' and '%s' "\
                        " %s "\
                        " GROUP BY aa.id, aa.code, ffrc.id, aml.date  "%(financial_reports.id, self.env.user.id, self.company_id.id, encabezado_id,
                        condition, financial_reports.id, self.env.user.company_id.id, self.chart_account_id.id, self.fiscalyear_id.date_start,
                        self.fiscalyear_id.date_stop, where)
        #_logger.debug(movimientos)
        self.env.cr.execute(movimientos)
        #actualizar totales de movimientos
        self.env.cr.execute(" UPDATE fpa_flujocaja_line set amount_total = amount_01+amount_02+amount_03+amount_04+amount_05+amount_06+amount_07+amount_08+"\
            "amount_09+amount_10+amount_11+amount_12 WHERE user_id = %s AND company_id=%s AND financial_id=%s"%(self.env.user.id,self.env.user.company_id.id,financial_reports.id))

        #ingresar totales por conceptos
        sql = " INSERT INTO fpa_flujocaja_line (bold,financial_id,user_id,company_id,amount_01,amount_02,amount_03,amount_04,amount_05,amount_06,amount_07,"\
                " amount_08,amount_09,amount_10,amount_11,amount_12,amount_total,encabezado_id,nivel,resume,concepts_id) "\
                " SELECT True, financial_id, user_id, company_id, "\
                " SUM(amount_01), SUM(amount_02), SUM(amount_03), SUM(amount_04), SUM(amount_05),SUM(amount_06), "\
                " SUM(amount_07), SUM(amount_08), SUM(amount_09), SUM(amount_10), SUM(amount_11), SUM(amount_12), SUM(amount_total), %s, 99, False, concepts_id "\
                " FROM fpa_flujocaja_line "\
                " WHERE user_id=%s AND company_id=%s AND financial_id=%s "\
                " GROUP BY user_id, company_id, financial_id, concepts_id "%(encabezado_id, self.env.user.id, self.env.user.company_id.id, financial_reports.id)
        self.env.cr.execute(sql)
        #buscar id concepto saldo inicial, para luego actualizar los montos de los saldos
        self.env.cr.execute(" SELECT id FROM fpa_financial_reports_concepts ffrc WHERE financial_reports = %s AND name = 'SALDO INICIAL'"%(financial_reports.id))
        concepts_si_id = self.env.cr.fetchone()
        if not concepts_si_id:
            raise Warning("Debe indicar un conceptos de saldo inicial (sin cuentas).")
        #buscar id concepto saldo inicial, para luego actualizar los montos de los saldos
        self.env.cr.execute(" SELECT id FROM fpa_financial_reports_concepts ffrc WHERE financial_reports = %s AND name = 'SALDO FINAL'"%(financial_reports.id))
        concepts_sf_id = self.env.cr.fetchone()
        if not concepts_sf_id:
            raise Warning("Debe indicar un conceptos de saldo final (sin cuentas).")
        #ingresar saldo inicial en ceros
        sql = " INSERT INTO fpa_flujocaja_line (bold,financial_id,user_id,company_id,encabezado_id,nivel,resume,concepts_id) "\
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "%(True,financial_reports.id, self.env.user.id, self.env.user.company_id.id,encabezado_id,99,False,concepts_si_id[0])
        self.env.cr.execute(sql)
        sql = " INSERT INTO fpa_flujocaja_line (bold,financial_id,user_id,company_id,encabezado_id,nivel,resume,concepts_id) "\
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "%(True,financial_reports.id, self.env.user.id, self.env.user.company_id.id,encabezado_id,99,False,concepts_sf_id[0])
        self.env.cr.execute(sql)

        for month in range(1,13):
            amount = 0
            if month == 1:
                amount_final = 0
                sql = " SELECT SUM(debit-credit) FROM account_move_line aml "\
                                   " INNER JOIN account_period ap on ap.id = aml.period_id and ap.special IS FALSE "\
                                   " INNER JOIN account_account aa ON %s AND aml.company_id = aa.company_id "\
                                   " INNER JOIN fpa_financial_reports_concepts_account ffrca ON ffrca.account_account_id = aa.id "\
                                   " INNER JOIN fpa_financial_reports_concepts ffrc "\
                                   "   ON ffrca.fpa_financial_reports_concepts_id = ffrc.id AND ffrc.financial_reports=%s "\
                                   " WHERE  aml.company_id = %s AND aa.parent_zero = %s "\
                                   " AND aml.date < '%s' "%(condition, financial_reports.id, self.env.user.company_id.id, self.chart_account_id.id, self.fiscalyear_id.date_start)
                _logger.info(sql)
                self.env.cr.execute(sql)
                amount = self.env.cr.fetchone()
                if amount:
                    amount=amount[0] or 0.0
            else:
                amount = amount_final

            _logger.info(month)

            #if amount>0:
            #actualiza saldo inicial
            sql = " UPDATE fpa_flujocaja_line SET amount_"+str(month).rjust(2,'0')+" = %s WHERE user_id = %s "\
                " AND company_id = %s AND financial_id = %s AND concepts_id = %s "%(amount,self.env.user.id, self.env.user.company_id.id, 
                    financial_reports.id,concepts_si_id[0])
            self.env.cr.execute(sql)
            _logger.info('amount')
            _logger.info(amount)

            sql = " SELECT SUM(amount_"+str(month).rjust(2,'0')+") FROM fpa_flujocaja_line "\
                                " WHERE financial_id=%s AND company_id = %s AND user_id =%s AND nivel = 99 "%(financial_reports.id,
                                    self.env.user.company_id.id,self.env.user.id)
            _logger.info(sql)
            self.env.cr.execute(sql)
            amount_final = self.env.cr.fetchone()
            if amount_final:
                amount_final = amount_final[0]
            else:
                amount_final = 0

            #if amount_final>0:
            sql = " UPDATE fpa_flujocaja_line SET amount_"+str(month).rjust(2,'0')+" = %s WHERE user_id = %s "\
                " AND company_id = %s AND financial_id = %s AND concepts_id = %s "%(amount_final,self.env.user.id, self.env.user.company_id.id, 
                    financial_reports.id,concepts_sf_id[0])
            self.env.cr.execute(sql)
            _logger.info('amount_final')
            _logger.info(amount_final)

        if financial_reports.unidades > 1:
            self.env.cr.execute(
                ''' UPDATE fpa_flujocaja_line SET amount_01=amount_01/{unidades}, 
                    amount_02=amount_02/{unidades}, amount_03=amount_03/{unidades},amount_04=amount_04/{unidades},
                    amount_05=amount_05/{unidades},amount_06=amount_06/{unidades},amount_07=amount_07/{unidades},
                    amount_08=amount_08/{unidades},amount_10=amount_10/{unidades},amount_11=amount_11/{unidades},
                    amount_12=amount_12/{unidades}, amount_total=amount_total/{unidades}
                    WHERE company_id={company_id} AND user_id={user_id} AND financial_id = {financial_id} '''.format(
                    unidades=financial_reports.unidades, financial_id=financial_reports.id, user_id=self.env.user.id,
                    company_id=self.env.user.company_id.id))
        return financial_reports.view_function(generate=False)
