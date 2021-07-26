# -*- coding: utf-8 -*-
import logging
from datetime import datetime

import openerp.addons.decimal_precision as dp
from openerp import models, fields, api, _
from openerp.exceptions import Warning

_logger = logging.getLogger(__name__)


class account_financial_reports_accounting_balance_general(models.Model):
    _name = "fpa.balance.general"

    date = fields.Datetime(string="Fecha")
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    estado = fields.Selection(
        [('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='validados',
        string='Estados')
    company_id = fields.Many2one('res.company', string='Compañia')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    user_id = fields.Many2one('res.users', string='Usuario')
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts',
                                       required=True, domain=[('parent_id', '=', False)])


class account_financial_reports_accounting_balance_general_line(models.Model):
    _name = "fpa.balance.general.line"

    account_id = fields.Many2one(
        'account.account', string='Cuenta', ondelete='cascade')
    amount_inicial = fields.Float(
        string='Saldo Inicial', digits=dp.get_precision('Account'))
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_final = fields.Float(
        string='Saldo Final', digits=dp.get_precision('Account'))
    nivel = fields.Integer(string='Nivel')
    cuenta = fields.Char(string='Cuenta')
    clase = fields.Char(string='Clase')
    company_id = fields.Many2one('res.company', string='Compañia')
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista')
    user_id = fields.Many2one('res.users', string='Usuario')
    description = fields.Text(string="Descripción")
    resume = fields.Boolean(string="Resumen")
    bold = fields.Boolean(string="Bold", default=False)
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    encabezado_id = fields.Many2one(
        'fpa.balance.general', string='Encabezado', ondelete='cascade')


class wizard_account_financial_reports_accounting_balance_general(models.TransientModel):
    _name = "fpa.balance.general.wizard"

    def _set_niveles(self):
        id = self.env.context.get('active_ids', False)
        return self.env['fpa.niveles'].search([('financial_reports', '=', id), ('code', 'in', ('99', '100'))],
                                              order='code asc')

    def _get_domain(self):
        id = self.env.context.get('active_ids', False)
        return [('financial_reports', '=', id)]

    account_filter = fields.Boolean(string="Filtro adicional de cuentas")
    partner_filter = fields.Boolean(string="Filtro adicional de terceros")
    journal_filter = fields.Boolean(string="Filtro adicional de diarios")
    niveles = fields.Many2many('fpa.niveles', string='Niveles', help='Seleccione los niveles para la consulta.',
                               default=_set_niveles, domain=_get_domain, required=True)
    cierre = fields.Boolean(string="Cierre")
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',
                                       help='Select Charts of Accounts', required=True,
                                       domain=[('parent_id', '=', False)])
    company_id = fields.Many2one(
        'res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    period_balance_ids = fields.Many2many('account.period', string='Periodos')
    journal_ids = fields.Many2many('account.journal', string='Diarios')
    account_ids = fields.Many2many(
        'account.account', string='Cuentas', domain=[('type', '!=', 'view')])
    date_from = fields.Date(string="Fecha Inicial", required=True)
    date_to = fields.Date(string="Fecha Final", required=True)
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), (
        'todos', 'Todos')], default='todos', string='Estados', required=True)

    @api.one
    @api.onchange('chart_account_id')
    def get_filter(self):
        print 'contexto'
        id = self.env.context.get('active_ids', False)
        financial_reports = self.env['fpa.financial.reports'].browse(id)
        self.account_filter = financial_reports.account_filter
        self.partner_filter = financial_reports.partner_filter
        self.journal_filter = financial_reports.journal_filter

    @api.one
    @api.constrains('date_from', 'date_to')
    def _validar_fechas(self):
        if self.date_from > self.date_to:
            raise Warning(_('Error en las fechas!'), _(
                "Las fechas planificadas estan mal configuradas"))

    @api.multi
    def generar(self):
        niveles = [x.code for x in self.niveles]
        _logger.debug(niveles)
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])

        self.env.cr.execute(
            ''' DELETE FROM fpa_balance_general_line WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
                financial_reports.id, self.company_id.id, self.env.user.id))
        self.env.cr.execute(
            ''' DELETE FROM fpa_balance_general WHERE financial_id =%s AND  company_id = %s and user_id = %s''' % (
                financial_reports.id, self.company_id.id, self.env.user.id))
        where = ''
        cuenta = []
        # Cuentas
        if financial_reports:
            if financial_reports.concepts_ids:
                for conceptos in financial_reports.concepts_ids:
                    for cuentas in conceptos.account_ids:
                        cuenta.append(cuentas.id)
        if len(cuenta) > 0:
            where += 'AND ( aml.account_id IN ' + str(tuple(cuenta)) + ' )'

        # Agrega encabezado con parametros indicados por el usuario
        sql = " INSERT INTO fpa_balance_general(date, date_from, date_to, estado, company_id, user_id,chart_account_id,financial_id) VALUES ('%s','%s','%s','%s',%s, %s, %s, %s) RETURNING ID " % (
            datetime.now(), self.date_from, self.date_to, self.estado, self.company_id.id, self.env.user.id,
            self.chart_account_id.id, financial_reports.id)
        self.env.cr.execute(sql)
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

        # verificar si tiene el modulo de niif_account instalado
        module = self.env['ir.module.module'].search([('name', '=', 'niif_account'), ('state', '=', 'installed')])
        # agregar condición de cuentas indicadas en el wizard
        condition = 'aa.id = movimientos.account_id'
        account = 'account_id'
        where_add = ''
        if self.account_ids:
            where_add = ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
            if module:
                if self.chart_account_id.niif:
                    where_add = ''' AND aml.account_niif_id in (%s) ''' % (
                        ','.join(str(x.id) for x in self.account_ids))
        if module:
            if self.chart_account_id.niif:
                condition = 'aa.id = account_niif_id'
                account = 'account_niif_id'
        where += where_add

        # Saldo inicial
        self.env.cr.execute(" select ap.date_start from account_move_line aml "
                            " inner join account_move am on am.id = aml.move_id "
                            " inner join account_period ap on ap.id = aml.period_id and special is True "
                            " inner join account_journal aj on aj.id = aml.journal_id and aj.type = 'situation' "
                            " inner join account_account_type aat on aat.report_type in ('asset','liability') "
                            " where am.company_id = %s and am.state = 'posted' and am.name = 'CIERRE%s' and aml.date <='%s' "
                            " order by date_start desc limit 1" % (self.env.user.company_id.id, '%', self.date_from))
        date_start = self.env.cr.fetchone()
        if not date_start:
            date_start = str('1900-01-01')
        else:
            date_start = date_start[0]

        relation = ' LEFT '
        if financial_reports.concepts_ids:
            relation = ' INNER '

        # #Movimientos
        movimientos = '''INSERT INTO fpa_balance_general_line (bold, concepts_id, sequence, user_id,company_id,account_id, cuenta, amount_inicial, debit, credit, amount_final,encabezado_id,nivel,resume,financial_id)
                            SELECT False, ffrc.id as concepts_id, ffrc.sequence, %s,%s, account_id, aa.code, sum(si) as amount_inicial, sum(debit) AS debit, sum(credit) AS credit, sum(si+debit-credit) as amount_final, %s::integer as encabezado_id,
                            99::integer nivel, False, %s
                            FROM (
                                SELECT %s as account_id,  0 as si, sum(aml.debit) as debit, sum(aml.credit) as credit
                                    FROM account_move_line aml
                                        INNER JOIN account_period ap on ap.id = aml.period_id
                                            WHERE aml.company_id = %s
                                            AND aml.date BETWEEN '%s' and '%s'
                                            %s
                                            GROUP BY %s
                                UNION
                                --Saldos iniciales
                                SELECT %s as account_id, sum(debit-credit) as si, 0 as debit, 0 as credit
                                    FROM account_move_line aml
                                        INNER JOIN account_period ap on ap.id = aml.period_id
                                        WHERE  aml.company_id = %s
                                        AND aml.date < '%s'
                                        %s
                                        GROUP BY %s
                            ) AS movimientos
                            INNER JOIN account_account aa ON %s AND aa.company_id = %s AND aa.parent_zero = %s
			                %s JOIN fpa_financial_reports_concepts_account ffrca ON ffrca.account_account_id = aa.id 
                            %s JOIN fpa_financial_reports_concepts ffrc on ffrc.id = ffrca.fpa_financial_reports_concepts_id 
			                AND ffrc.financial_reports = %s
                            GROUP BY account_id, ffrc.sequence, aa.code, ffrc.id ''' % (
            self.env.user.id, self.company_id.id, encabezado_id, financial_reports.id,
            account, self.env.user.company_id.id, self.date_from, self.date_to, where, account,
            account, self.env.user.company_id.id, self.date_from, where, account,
            condition, self.env.user.company_id.id, self.chart_account_id.id, relation, relation, financial_reports.id)
        self.env.cr.execute(movimientos)
        if '100' in niveles:
            # Agregar totales por concepto
            self.env.cr.execute(
                "INSERT INTO fpa_balance_general_line (bold,user_id,company_id,account_id, cuenta, amount_inicial, debit, " \
                " credit, amount_final,encabezado_id,resume, concepts_id, financial_id) " \
                " SELECT True, %s, %s, null, null, 0,0,0, SUM(amount_final), %s, False, ffrc.id, %s " \
                " FROM fpa_financial_reports_concepts ffrc " \
                " LEFT JOIN fpa_balance_general_line fpl ON ffrc.id = fpl.concepts_id " \
                " WHERE ffrc.financial_reports = %s AND fpl.nivel = 99 AND fpl.user_id=%s AND fpl.company_id=%s " \
                " GROUP BY ffrc.id " % (
                    self.env.user.id, self.company_id.id, encabezado_id, financial_reports.id, financial_reports.id,
                    self.env.user.id, self.env.user.company_id.id))

        self.env.cr.execute(
            " DELETE FROM fpa_balance_general_line WHERE amount_inicial = 0 and debit = 0 and credit = 0 and amount_final=0 and user_id=%s and company_id=%s and financial_id=%s " % (
                self.env.user.id, self.env.user.company_id.id, self.id))

        if '99' not in niveles:
            self.env.cr.execute(
                " DELETE FROM fpa_balance_general_line WHERE nivel = 99 and user_id =%s and company_id=%s and financial_id=%s " % (
                    self.env.user.id, self.env.company_id.id, self.id))

            # cambia el signo
        if financial_reports.sign:
            self.env.cr.execute(" UPDATE fpa_pyg_line SET amount_inicial = amount_inicial * -1, " \
                                " amount_final = amount_final * -1 WHERE user_id=%s AND company_id=%s AND financial_id =%s " % (
                                    self.env.user.id, self.env.user.company_id.id, self.id))

        # aplicar conversion de miles
        if financial_reports.unidades > 1:
            self.env.cr.execute(
                ''' UPDATE fpa_pyg_line SET amount_inicial=amount_inicial/{unidades}, debit=debit/{unidades}, 
                    credit=credit/{unidades},amount_final=amount_final/{unidades} 
                    WHERE company_id={company_id} AND user_id={user_id} AND financial_id = {financial_id} '''.format(
                    unidades=financial_reports.unidades, financial_id=financial_reports.id, user_id=self.env.user.id,
                    company_id=self.env.user.company_id.id))

        return financial_reports.view_function(generate=False)
