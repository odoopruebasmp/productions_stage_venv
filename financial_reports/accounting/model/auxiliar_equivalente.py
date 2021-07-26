# -*- coding: utf-8 -*-
import logging
from datetime import datetime

import openerp.addons.decimal_precision as dp
from openerp import models, fields, api, _
from openerp.exceptions import Warning

_logger = logging.getLogger(__name__)


class account_financial_reports_accounting_auxiliar_equivalente(models.Model):
    _name = "fpa.auxiliar.equivalente"

    date = fields.Datetime(string="Fecha")
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')],
                              default='validados', string='Estados')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', required=True,
                                       domain=[('parent_id', '=', False)])


class account_financial_reports_accounting_auxiliar_equivalente_line(models.Model):
    _name = "fpa.auxiliar.equivalente.line"

    account_id = fields.Many2one('account.account', string='Cuenta NIIF', ondelete='cascade', index=True)
    account_equivalente_id = fields.Many2one('account.account', string='Cuenta Equiv. Colgaap', ondelete='cascade',
                                             index=True)
    account_analytic_id = fields.Many2one('account.analytic.account', string='Cuenta analitica', ondelete='cascade',
                                          index=True)
    partner_id = fields.Many2one('res.partner', string='Tercero', ondelete='cascade', index=True)
    move_line_id = fields.Many2one('account.move.line', string='Move line', ondelete='cascade', index=True)
    amount_inicial = fields.Float(string='Saldo Inicial', digits=dp.get_precision('Account'))
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    debit_c = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit_c = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_final = fields.Float(string='Saldo Final', digits=dp.get_precision('Account'))
    resume = fields.Boolean(string="Resumen")
    nivel = fields.Integer(string="Nivel")
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte', index=True)
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade', index=True)
    bold = fields.Boolean(string="Bold", default=False)
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista')
    fecha = fields.Date(string='Fecha')
    cuenta = fields.Char(string='Cuenta')
    asiento = fields.Char(string='Asiento')
    encabezado_id = fields.Many2one('fpa.auxiliar.equivalente', string='Encabezado', ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Compañia', index=True)
    user_id = fields.Many2one('res.users', string='Usuario', index=True)


class wizard_account_financial_reports_accounting_auxiliar_equivalente(models.TransientModel):
    _name = "fpa.auxiliar.equivalente.wizard"

    def _set_niveles(self):
        id = self.env.context.get('active_ids', False)
        return self.env['fpa.niveles'].search([('financial_reports', '=', id), (
            'code', 'in', ('98', '99'))], order='code asc')

    def _get_domain(self):
        id = self.env.context.get('active_ids', False)
        return [('financial_reports', '=', id)]

    account_filter = fields.Boolean(string="Filtro adicional de cuentas")
    partner_filter = fields.Boolean(string="Filtro adicional de terceros")
    journal_filter = fields.Boolean(string="Filtro adicional de diarios")
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',
                                       help='Plan de cuentas asociado a las cuentas contables que se desean consultar.',
                                       required=True, domain=[('parent_id', '=', False), ('niif', '=', True)])
    niveles = fields.Many2many('fpa.niveles', string='Niveles', help='Seleccione los niveles para la consulta.',
                               default=_set_niveles, domain=_get_domain, required=True)
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True,
                                 help='Compañia asociada a los movimientos contables a consultar.')
    period_balance_ids = fields.Many2many('account.period', string='Periodos',
                                          help='Período asociado a los movimientos contables a consultar.')
    journal_ids = fields.Many2many('account.journal', string='Diarios',
                                   help='Diario asociado a los movimientos contables a consultar.')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type', '!=', 'view')],
                                   help='Cuentas contables asociadas a los movimientos a consultar.')
    analytic_ids = fields.Many2many('account.analytic.account', string='Cuentas analiticas',
                                    domain=[('type', '!=', 'view')])
    partner_ids = fields.Many2many('res.partner', string='Terceros',
                                   help='Tercero asociado a los movimientos contables a consultar.')
    date_from = fields.Date(string="Fecha Inicial", required=True,
                            help='Fecha inicial de consulta, el informe retornará los movimientos contables desde esta fecha.')
    date_to = fields.Date(string="Fecha Final", required=True,
                          help='Fecha final de consulta, el informe retornará los movimientos contables hasta esta fecha.')
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')],
                              default='todos', string='Estados', required=True,
                              help='Estado en el cual se desean consultar los movimientos contables.')
    company_id = fields.Many2one('res.company', string='Compañia',
                                 help='Compañia asociada a los movimientos contables a consultar.')
    user_id = fields.Many2one('res.users', string='Usuario', help='Usuario que ejecuta la consulta.')
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
            raise Warning(_('Error en las fechas!'), _("Las fechas planificadas estan mal configuradas"))

    @api.multi
    def generar(self):
        niveles = [x.code for x in self.niveles]
        st = datetime.now()
        self.env.cr.execute(''' select count(*) from fpa_auxiliar_equivalente_line ''')
        count = self.env.cr.fetchone()[0]

        # recorre conceptos configurados en el informe
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])
        te = datetime.now()
        # truncate a la tabla cuando sean mas de 1millón de registros, para que no tarde tanto eliminando las lineas antes de crear las nuevas
        if count > 1000000:
            self.env.cr.execute(''' TRUNCATE fpa_auxiliar_equivalente_line ''')
        else:
            self.env.cr.execute(
                ''' DELETE FROM fpa_auxiliar_equivalente_line WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
                    financial_reports.id, self.env.user.company_id.id, self.env.user.id))
        self.env.cr.execute(
            ''' DELETE FROM fpa_auxiliar_equivalente WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
                financial_reports.id, self.env.user.company_id.id, self.env.user.id))
        _logger.info('culminó de eliminar movimientos anteriores. Tiempo: %s' % (datetime.now() - te))
        where = ''

        # Agrega encabezado con parametros indicados por el usuario
        self.env.cr.execute(
            ''' INSERT INTO fpa_auxiliar_equivalente(date, date_from, date_to, estado, company_id, user_id,chart_account_id,financial_id) VALUES ('%s','%s','%s','%s',%s,%s,%s,%s) RETURNING ID ''' % (
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

        if self.analytic_ids:
            where += ''' AND aml.analytic_account_id in (%s) ''' % (','.join(str(x.id) for x in self.analytic_ids))

        if self.estado == 'borrador':
            estado = 'draft'
        elif self.estado == 'validados':
            estado = 'valid'
        else:
            estado = '%'
        where += ''' AND aml.state like '%s' ''' % estado

        sp_periods = '' if self.sp_periods else ' AND ap.special is False '
        where += sp_periods

        te = datetime.now()
        # INGRESAR MOVIMIENTOS
        movimientos = ''' INSERT INTO fpa_auxiliar_equivalente_line (bold,user_id,company_id,account_id,account_equivalente_id,account_analytic_id,fecha,asiento,
                                partner_id,amount_inicial,debit,credit,amount_final,encabezado_id,financial_id, nivel, cuenta)
                            SELECT a.*, aan.code FROM (
                                SELECT False, {user_id}, {company_id}, aml.account_niif_id as account_id, aml.account_id as account_equivalente_id, 
                                        {fields} 
                                        0 as si, aml.debit::numeric, aml.credit::numeric, (aml.debit-aml.credit)::numeric as amount_final, 
                                        {encabezado_id}::integer as encabezado_id, {financial_id}, {nivel}
                                            FROM account_move_line aml
                                                INNER JOIN account_move am ON am.id = aml.move_id                                         
                                                INNER JOIN account_period ap on ap.id = aml.period_id
                                                    WHERE aml.company_id = {company_id} AND aml.date BETWEEN '{date_from}' and '{date_to}' {where_account} {where} 
                            ) as a
                            LEFT JOIN account_account aan ON aan.id = a.account_id AND aan.parent_zero = {chart_account_id} AND aan.niif IS TRUE
                            LEFT JOIN account_account aa ON aa.id = a.account_equivalente_id AND aa.niif IS FALSE 
                            '''.format(user_id=self.env.user.id, company_id=self.env.user.company_id.id,
                                       encabezado_id=encabezado_id,
                                       financial_id=financial_reports.id, date_from=self.date_from,
                                       date_to=self.date_to,
                                       where_account=where_account, where=where,
                                       chart_account_id=self.chart_account_id.id, fields='{fields}', nivel='{nivel}')

        movimientos_tmp = movimientos
        if '99' in niveles:  # TERCEROS
            fields = ''' aml.analytic_account_id,aml.date,am.name,aml.partner_id, '''
            self.env.cr.execute(movimientos.format(fields=fields, nivel=99))
        # if '98' in niveles:  # CUENTAS
        #    fields = ''' NULL::integer,NULL::timestamp,NULL::varchar,NULL::integer, '''
        #    self.env.cr.execute(movimientos_tmp.format(fields=fields,nivel=98))

        _logger.info('culminó de agregar movimientos. Tiempo: %s' % (datetime.now() - te))
        te = datetime.now()
        # INGRESAR SALDOS INICIALES
        saldo_inicial = ''' INSERT INTO fpa_auxiliar_equivalente_line (bold,user_id,company_id,account_id,account_equivalente_id,account_analytic_id,fecha,asiento,partner_id,amount_inicial,debit_c,credit_c,amount_final,encabezado_id,financial_id, nivel, cuenta)
                            SELECT a.*, aan.code FROM (
                                  --saldos por cuenta antes de la fecha inicial de consulta
                                  SELECT True as bold, {user_id} as user_id, {company_id} as company_id, account_id, account_equivalente_id, NULL::integer as account_analytic_id, 
                                        NULL::date as fecha, NULL::varchar as asiento, NULL::integer as partner_id, SUM(si) as si, SUM(debit) as debit, 
                                        SUM(credit) as credit, SUM(amount_final) as amount_final,
                                        {encabezado_id}::integer as encabezado_id, {financial_id} as financial_id, 98 as nivel FROM(
                                         SELECT aml.account_niif_id as account_id, aml.account_id as account_equivalente_id, SUM(aml.debit-aml.credit) as si, 0 as debit, 
                                            0 as credit, 0 as amount_final
                                             FROM account_move_line aml
                                                 INNER JOIN account_move am ON am.id = aml.move_id                                         
                                                 INNER JOIN account_period ap on ap.id = aml.period_id
                                                     WHERE aml.company_id = {company_id} 
                                                         AND aml.date < '{date_from}'
                                                      {where_account} {where} GROUP BY aml.account_niif_id, aml.account_id
                                    UNION
                                    --cuentas en el periodo de consulta
                                    SELECT aml.account_niif_id, aml.account_id as account_equivalente_id, 0 as si, SUM(aml.debit) as debit, 
                                        SUM(aml.credit) as credit, 0 as amount_final
                                         FROM account_move_line aml
                                             INNER JOIN account_move am ON am.id = aml.move_id               
                                             INNER JOIN account_period ap on ap.id = aml.period_id
                                                 WHERE aml.company_id = {company_id}
                                                     AND aml.date BETWEEN '{date_from}' and '{date_to}'
                                        {where_account} {where} GROUP BY aml.account_niif_id, aml.account_id
                                    ) as datos
                                    GROUP BY account_id, account_equivalente_id
                            ) as a
                            LEFT JOIN account_account aan ON aan.id = a.account_id AND aan.parent_zero = {chart_account} AND aan.niif IS TRUE --NIIF
                            LEFT JOIN account_account aa ON aa.id = a.account_equivalente_id AND aa.niif IS FALSE --COLGAAP
                            '''.format(user_id=self.env.user.id, company_id=self.env.user.company_id.id,
                                       encabezado_id=encabezado_id,
                                       financial_id=financial_reports.id,
                                       date_from=self.date_from, date_to=self.date_to,
                                       where_account=where_account, where=where, chart_account=self.chart_account_id.id)
        self.env.cr.execute(saldo_inicial)
        _logger.info('culminó de agregar saldos iniciales. Tiempo: %s' % (datetime.now() - te))

        te = datetime.now()
        # actualiza saldo final
        self.env.cr.execute(''' UPDATE fpa_auxiliar_equivalente_line SET amount_final = COALESCE(amount_inicial,0) + debit_c - credit_c
            WHERE company_id = %s AND user_id = %s ''' % (self.env.user.company_id.id, self.env.user.id))
        _logger.info('culminó de actualizar saldo final. Tiempo: %s' % (datetime.now() - te))
        # # recorre la estructura indicada en el plan de cuentas para agregar las cuentas de tipo vista
        te = datetime.now()
        for structure in self.chart_account_id.structure_id.sorted(key=lambda r: r.sequence, reverse=True):
            # nivel
            nivel = '''INSERT INTO fpa_auxiliar_equivalente_line (bold, user_id,company_id, account_id, cuenta, partner_id, amount_inicial, debit, credit, amount_final,encabezado_id,nivel,financial_id)
                        SELECT True, %s,%s,aar.id, aar.code, null, sum(al.amount_inicial) as amount_inicial, sum(al.debit_c) as debit,
                            sum(al.credit_c) as credit, sum(al.amount_final) as amount_final, %s, %s, %s
                            FROM fpa_auxiliar_equivalente_line al
                                INNER JOIN  account_account aar on aar.code = substring(al.cuenta from 1 for %s) 
                                    and aar.type = 'view' and aar.company_id = al.company_id
                                WHERE al.nivel=99 and al.user_id =%s and al.company_id = %s
                                GROUP BY aar.id, aar.code ''' % (
                self.env.user.id, self.env.user.company_id.id, encabezado_id, structure.sequence, financial_reports.id,
                structure.digits, self.env.user.id, self.env.user.company_id.id)
            self.env.cr.execute(nivel)
        _logger.info('culminó de agregar las estructuras. Tiempo: %s' % (datetime.now() - te))
        # Inserta PUC como resumen de todos los movimiento
        chart_account = '''INSERT INTO fpa_auxiliar_equivalente_line (bold,user_id,company_id, account_id, cuenta, partner_id, amount_inicial,
                        debit, credit, amount_final,encabezado_id,nivel,financial_id) select True, %s,%s,%s, '%s', null, sum(al.amount_inicial) as amount_inicial, 
                        sum(al.debit_c) as debit,  sum(al.credit_c) as credit, 
                        sum(al.amount_final) as amount_final, %s, 1, %s from fpa_auxiliar_equivalente_line al where al.nivel=99
                        and al.user_id = %s and al.company_id = %s''' % (
            self.env.user.id, self.env.user.company_id.id, self.chart_account_id.id,
            self.chart_account_id.code, encabezado_id, financial_reports.id, self.env.user.id,
            self.env.user.company_id.id)
        self.env.cr.execute(chart_account)

        # actualizacion para intereses implicitos
        # self.env.cr.execute(''' UPDATE fpa_auxiliar_equivalente_line SET account_equivalente_id = a.account_tax_niif_id
        #                            FROM (SELECT aa.account_tax_niif_id, aa.id FROM account_account aa ) a
        #                            WHERE a.id = fpa_auxiliar_equivalente_line.account_id
        #                            AND fpa_auxiliar_equivalente_line.user_id = %s
        #                            AND fpa_auxiliar_equivalente_line.company_id = %s ''' % (
        # self.env.user.id, self.env.user.company_id.id))
        # eliminar lineas sin saldo inicial, debito y credito
        # self.env.cr.execute(''' DELETE FROM fpa_auxiliar_equivalente_line WHERE amount_inicial=0 and debit=0 and credit=0 ''')
        # _logger.info('Tiempo: %s' % (datetime.now() - st))

        # aplicar conversion de miles
        if financial_reports.unidades > 1:
            self.env.cr.execute(
                ''' UPDATE fpa_auxiliar_equivalente_line SET amount_inicial=amount_inicial/{unidades}, debit=debit/{unidades}, 
                    credit=credit/{unidades},amount_final=amount_final/{unidades} 
                    WHERE company_id={company_id} AND user_id={user_id} AND financial_id = {financial_id} '''.format(
                    unidades=financial_reports.unidades, financial_id=financial_reports.id, user_id=self.env.user.id,
                    company_id=self.env.user.company_id.id))

        return financial_reports.view_function(generate=False)
