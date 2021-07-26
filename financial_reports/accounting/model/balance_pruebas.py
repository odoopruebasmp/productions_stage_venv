# -*- coding: utf-8 -*-
import logging
from datetime import datetime

import openerp.addons.decimal_precision as dp
from openerp import models, fields, api, _
from openerp.exceptions import Warning

_logger = logging.getLogger(__name__)


class account_financial_reports_accounting_balance_pruebas(models.Model):
    _name = "fpa.balance.pruebas"

    date = fields.Datetime(string="Fecha")
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    estado = fields.Selection(
        [('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='validados',
        string='Estados')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',
                                       help='Select Charts of Accounts', required=True,
                                       domain=[('parent_id', '=', False)])


class account_financial_reports_accounting_balance_pruebas_line(models.Model):
    _name = "fpa.balance.pruebas.line"

    account_id = fields.Many2one(
        'account.account', string='Cuenta', ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Tercero', ondelete='cascade')
    amount_inicial = fields.Float(
        string='Saldo Inicial', digits=dp.get_precision('Account'))
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_final = fields.Float(
        string='Saldo Final', digits=dp.get_precision('Account'))
    cuenta = fields.Char(string='Cuenta')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista')
    resume = fields.Boolean(string="Resumen")
    nivel = fields.Integer(string="Nivel")
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade')
    bold = fields.Boolean(string="Bold", default=False)
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista')
    encabezado_id = fields.Many2one(
        'fpa.balance.pruebas', string='Encabezado', ondelete='cascade')


class wizard_account_financial_reports_accounting_balance_pruebas(models.TransientModel):
    _name = "fpa.balance.pruebas.wizard"

    def _set_niveles(self):
        id = self.env.context.get('active_ids', False)
        return self.env['fpa.niveles'].search([('financial_reports', 'in', id), (
            'code', 'in', ('0', '1', '2', '3', '4', '5', '6', '7', '8', '98', '99'))], order='code asc')

    def _get_domain(self):
        id = self.env.context.get('active_ids', False)
        return [('financial_reports', '=', id)]

    account_filter = fields.Boolean(string="Filtro adicional de cuentas")
    partner_filter = fields.Boolean(string="Filtro adicional de terceros")
    journal_filter = fields.Boolean(string="Filtro adicional de diarios")
    niveles = fields.Many2many('fpa.niveles', string='Niveles', help='Seleccione los niveles para la consulta.',
                               default=_set_niveles, domain=_get_domain, required=True)
    cierre = fields.Boolean(string="Cierre")
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts',
                                       required=True, domain=[('parent_id', '=', False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    resume = fields.Boolean(string="Resumen")
    period_balance_ids = fields.Many2many('account.period', string='Periodos')
    analytic_ids = fields.Many2many('account.analytic.account', string='Cuentas analiticas',
                                    domain=[('type', '!=', 'view')])
    journal_ids = fields.Many2many('account.journal', string='Diarios', help='Seleccione los diarios a consultar.')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type', '!=', 'view')],
                                   help='Seleccione las cuentas contables a consultar.')
    partner_ids = fields.Many2many('res.partner', string='Terceros',
                                   help='Seleccione los terceros que desee consultar.')
    date_from = fields.Date(string="Fecha Inicial", required=True, help='Fecha inicial para el rango de consulta.')
    date_to = fields.Date(string="Fecha Final", required=True, help='Fecha limite final para el rango de consulta.')
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')],
                              default='todos', string='Estados', required=True)
    sp_periods = fields.Boolean('Apertura/Cierre', help='Marque este check si quiere tener en cuenta los '
                                    'movimientos pertenecientes a periodos de Apertura/Cierre', default=True)

    @api.one
    @api.onchange('chart_account_id')
    def get_filter(self):
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
        _logger.info(niveles)
        st = datetime.now()

        self.env.cr.execute(''' select count(*) from fpa_balance_pruebas_line ''')
        count = self.env.cr.fetchone()[0]  # 5139 #4347

        # recorre conceptos configurados en el informe
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])

        # truncate a la tabla cuando sean mas de 1millón de registros, para que no tarde tanto eliminando las lineas antes de crear las nuevas
        if count > 1000000:
            self.env.cr.execute(''' TRUNCATE fpa_balance_pruebas_line ''')
        else:
            self.env.cr.execute(
                ''' DELETE FROM fpa_balance_pruebas_line WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
                    financial_reports.id, self.env.user.company_id.id, self.env.user.id))
        self.env.cr.execute(
            ''' DELETE FROM fpa_balance_pruebas WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
                financial_reports.id, self.env.user.company_id.id, self.env.user.id))

        where = ''

        # Agrega encabezado con parametros indicados por el usuario
        self.env.cr.execute(
            ''' INSERT INTO fpa_balance_pruebas(date, date_from, date_to, estado, company_id, user_id,chart_account_id,financial_id) VALUES ('%s','%s','%s','%s',%s,%s,%s,%s) RETURNING ID ''' % (
                datetime.now(), self.date_from, self.date_to, self.estado, self.env.user.company_id.id,
                self.env.user.id, self.chart_account_id.id, financial_reports.id))
        try:
            encabezado_id = self.env.cr.fetchone()[0]
        except ValueError:
            encabezado_id = False

        # Filtros adicionales
        if self.journal_ids:
            where += ''' AND aml.journal_id in (%s) ''' % (
                ','.join(str(x.id) for x in self.journal_ids))
        where_account = ''
        if self.account_ids:
            if self.chart_account_id.niif:
                where_account = ''' AND aml.account_niif_id in (%s) ''' % (
                    ','.join(str(x.id) for x in self.account_ids))
            else:
                where_account = ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))

        if self.partner_ids:
            where += ''' AND aml.partner_id in (%s) ''' % (','.join(str(x.id) for x in self.partner_ids))

        estado = ''
        if self.estado == 'borrador':
            estado = 'draft'
        elif self.estado == 'validados':
            estado = 'valid'
        else:
            estado = '%'
        where += ''' AND aml.state like '%s' ''' % estado

        sp_periods = '' if self.sp_periods else ' AND ap.special is False '
        where += sp_periods

        account = 'aml.account_id'
        # verificar si tiene el modulo de niif_account instalado
        module = self.env['ir.module.module'].search([('name', '=', 'niif_account'), ('state', '=', 'installed')])
        if module:
            if self.chart_account_id.niif:
                account = 'aml.account_niif_id'

        te = datetime.now()
        # Movimientos
        movimientos = '''INSERT INTO fpa_balance_pruebas_line (bold, user_id,company_id,account_id,cuenta,partner_id,amount_inicial,debit,credit,amount_final,encabezado_id,nivel,resume,financial_id)
                            SELECT False, %s, %s, account_id as id, aa.code, 
                                movimientos.partner_id, si, debit, credit, amount_final, %s::integer as encabezado_id,
                            99::integer nivel, False, %s
                            FROM (
                                --------------------- 3 SUMANDO SI, DEBITO Y CREDITO AGRUPAGO POR CUENTA
                                SELECT account_id, partner_id, sum(si) as si, sum(debit) as debit, sum(credit) as credit, 
                                    sum(si+debit-credit) as amount_final FROM (
                                --------------------- 1 MOVIMIENTOS EN EL PERIODO
                                SELECT %s as account_id, aml.partner_id, 0 as si, sum(aml.debit) as debit, sum(aml.credit) as credit
                                    FROM account_move_line aml
                                        INNER JOIN account_period ap on ap.id = aml.period_id
                                            WHERE  aml.company_id = %s
                                            AND aml.date BETWEEN '%s' AND '%s'
                                            %s %s
                                            GROUP BY %s, aml.partner_id
                                --------------------- 1 MOVIMIENTOS EN EL PERIODO
                                UNION
                                --------------------- 2 SALDOS INICIALES
                                SELECT %s as account_id, aml.partner_id, sum(debit-credit) as si, 0 as debit, 0 as credit
                                    FROM account_move_line aml
                                        INNER JOIN account_period ap on ap.id = aml.period_id
                                        WHERE  aml.company_id = %s 
                                        AND aml.date < '%s'
                                        %s %s
                                        GROUP BY %s, aml.partner_id
                                --------------------- 2
                                ) AS grupo
                                GROUP BY account_id, partner_id
                            ) AS movimientos
                             INNER JOIN account_account aa ON aa.id = movimientos.account_id 
                                AND aa.company_id = %s AND aa.parent_zero = %s ''' % (
            self.env.user.id, self.env.user.company_id.id, encabezado_id, financial_reports.id,
            account, self.env.user.company_id.id, self.date_from, self.date_to,
            where_account, where, account,
            account, self.env.user.company_id.id, self.date_from, where_account,
            where, account, self.env.user.company_id.id, self.chart_account_id.id)
        _logger.info('culminó de agregar movimientos. Tiempgo: %s' % (datetime.now() - te))
        _logger.info(movimientos)
        self.env.cr.execute(movimientos)

        if '98' in niveles:
            # Inserta regulares sin tercero
            regulares_stercero = '''INSERT INTO fpa_balance_pruebas_line (bold,user_id,company_id,account_id, cuenta,  
                                    amount_inicial, debit, credit, amount_final,encabezado_id,nivel,financial_id)
                                        select True,%s,%s, account_id, cuenta, sum(fbpl.amount_inicial) as amount_inicial, sum(fbpl.debit) as debit, 
                                        sum(fbpl.credit) as credit, sum(fbpl.amount_final) as amount_final, %s, 98, %s
                                            from fpa_balance_pruebas_line fbpl
                                                where fbpl.user_id = %s and fbpl.nivel=99 
                                                and fbpl.company_id = %s
                                                GROUP BY account_id, cuenta ''' % (self.env.user.id, self.company_id.id,
                                                                                   encabezado_id, financial_reports.id,
                                                                                   self.env.user.id, self.company_id.id)
            self.env.cr.execute(regulares_stercero)

        for structure in self.chart_account_id.structure_id.sorted(key=lambda r: r.sequence, reverse=True):
            _logger.debug('Structure: %s' % structure.sequence)
            if str(structure.sequence) in niveles:
                nivel = '''INSERT INTO fpa_balance_pruebas_line (bold,user_id, company_id, account_id, cuenta, partner_id,
                            amount_inicial, debit, credit, amount_final,encabezado_id,nivel,financial_id)
                              select True, %s,%s,aar.id, aar.code, null, sum(fbpl.amount_inicial) as amount_inicial,
                              sum(fbpl.debit) as debit, sum(fbpl.credit) as credit, sum(fbpl.amount_final) as amount_final,
                              %s, %s, %s
                                 from
                                     fpa_balance_pruebas_line fbpl
                                    inner join account_account aar on aar.code = substring(fbpl.cuenta from 1 for %s) 
                                        and aar.type ='view' and length(fbpl.cuenta) > %s and length(aar.code) = %s and aar.company_id = fbpl.company_id
                                     where fbpl.nivel=99 and fbpl.user_id = %s and fbpl.company_id = %s
                                     group by aar.id, aar.code ''' % (
                    self.env.user.id, self.company_id.id, encabezado_id,
                    structure.sequence, financial_reports.id, structure.digits, structure.digits,
                    structure.digits, self.env.user.id, self.company_id.id)
                _logger.debug('Nivel: %s' % nivel)
                self.env.cr.execute(nivel)
        if '0' in niveles:
            # Inserta PUC como resumen de todos los movimiento
            chart_account = '''INSERT INTO fpa_balance_pruebas_line (user_id,company_id,account_id, cuenta, partner_id, amount_inicial, debit, credit, amount_final,encabezado_id,nivel,financial_id)
                                select %s,%s,%s, '%s', null, sum(fbpl.amount_inicial) as amount_inicial, sum(fbpl.debit) as debit, sum(fbpl.credit) as credit, sum(fbpl.amount_final) as amount_final, %s, 0, %s
                                    from fpa_balance_pruebas_line fbpl
                                        where fbpl.user_id = %s and fbpl.nivel=99 and fbpl.company_id = %s''' % (
                self.env.user.id, self.company_id.id, self.chart_account_id.id, self.chart_account_id.code,
                encabezado_id,
                financial_reports.id, self.env.user.id, self.company_id.id)
            self.env.cr.execute(chart_account)
        if '99' not in niveles:
            self.env.cr.execute(" DELETE FROM fpa_balance_pruebas_line WHERE nivel = 99 ")
        # eliminar lineas sin saldo final
        self.env.cr.execute(
            " DELETE FROM fpa_balance_pruebas_line WHERE amount_inicial=0 AND debit=0 AND credit=0 AND amount_final=0 ")

        # aplicar conversion de miles
        if financial_reports.unidades > 1:
            self.env.cr.execute(''' UPDATE fpa_balance_pruebas_line SET amount_inicial=amount_inicial/{unidades}, debit=debit/{unidades},
                   credit=credit/{unidades},amount_final=amount_final/{unidades}
                   WHERE company_id={company_id} AND user_id={user_id} AND financial_id = {financial_id} '''.format(
                unidades=financial_reports.unidades, financial_id=financial_reports.id, user_id=self.env.user.id,
                company_id=self.env.user.company_id.id))
        return financial_reports.view_function(generate=False)
