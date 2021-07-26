# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from lxml import etree
from openerp import tools, models, fields, api, _
from openerp.exceptions import Warning
import openerp.addons.decimal_precision as dp
import logging
import calendar

_logger = logging.getLogger(__name__)


class FPAForeingCurrency(models.Model):
    _name = "fpa.foreing.currency"

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


class FPAForeingCurrencyLine(models.Model):
    _name = "fpa.foreing.currency.line"

    account_id = fields.Many2one('account.account', string='Cuenta', ondelete='cascade', index=True)
    accumulated = fields.Boolean(string='Acumulado', index=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', ondelete='cascade', index=True)
    january = fields.Float(string='Enero', digits=dp.get_precision('Account'))
    february = fields.Float(string='Febrero', digits=dp.get_precision('Account'))
    march = fields.Float(string='Marzo', digits=dp.get_precision('Account'))
    april = fields.Float(string='Abril', digits=dp.get_precision('Account'))
    may = fields.Float(string='Mayo', digits=dp.get_precision('Account'))
    june = fields.Float(string='Junio', digits=dp.get_precision('Account'))
    july = fields.Float(string='Julio', digits=dp.get_precision('Account'))
    august = fields.Float(string='Agosto', digits=dp.get_precision('Account'))
    september = fields.Float(string='Septiembre', digits=dp.get_precision('Account'))
    october = fields.Float(string='Octubre', digits=dp.get_precision('Account'))
    november = fields.Float(string='Noviembre', digits=dp.get_precision('Account'))
    december = fields.Float(string='Diciembre', digits=dp.get_precision('Account'))
    amount_final = fields.Float(string='Saldo final', digits=dp.get_precision('Account'))
    cuenta = fields.Char(string='Cuenta')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista',
                              index=True)
    resume = fields.Boolean(string="Resumen")
    nivel = fields.Integer(string="Nivel", index=True)
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte', required=True)
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade')
    bold = fields.Boolean(string="Bold", default=False)
    cierre = fields.Boolean(string="Cierre", default=True)
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista')
    encabezado_id = fields.Many2one('fpa.foreing.currency', string='Encabezado', ondelete='cascade')


class FPAForeingCurrencyWizard(models.TransientModel):
    _name = "fpa.foreing.currency.wizard"

    def _get_domain(self):
        id = self.env.context.get('active_ids', False)
        return [('financial_reports', '=', id)]

    account_filter = fields.Boolean(string="Filtro adicional de cuentas")
    journal_filter = fields.Boolean(string="Filtro adicional de diarios")
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts',
                                       required=True, domain=[('parent_id', '=', False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', domain="['|',('name', '=', 'USD'),('name', '=', 'COP')]",required=True)
    resume = fields.Boolean(string="Resumen")
    period_balance_ids = fields.Many2many('account.period', string='Periodos')
    analytic_ids = fields.Many2many('account.analytic.account', string='Cuentas analiticas',
                                    domain=[('type', '!=', 'view')])
    journal_ids = fields.Many2many('account.journal', string='Diarios', help='Seleccione los diarios a consultar.')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type', '!=', 'view')],
                                   help='Seleccione las cuentas contables a consultar.')
    partner_ids = fields.Many2many('res.partner', string='Terceros',
                                   help='Seleccione los terceros que desee consultar.')
    date_to = fields.Date(string="Fecha Final", required=True, help='Fecha limite final para el rango de consulta.')
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')],
                              default='todos', string='Estados', required=True)

    @api.one
    @api.onchange('chart_account_id')
    def get_filter(self):
        id = self.env.context.get('active_ids', False)
        financial_reports = self.env['fpa.financial.reports'].browse(id)
        self.account_filter = financial_reports.account_filter
        self.journal_filter = financial_reports.journal_filter

    @api.multi
    def generar(self):
        _logger.debug('GENERAR')
        self.env.cr.execute(''' select count(*) from fpa_foreing_currency_line ''')
        count = self.env.cr.fetchone()[0]
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])
        # truncate a la tabla cuando sean mas de 1millón de registros, para que no tarde tanto eliminando las lineas
        if count > 10000000:
            self.env.cr.execute(''' TRUNCATE fpa_foreing_currency_line ''')
            self.env.cr.execute(''' TRUNCATE fpa_foreing_currency ''')
        else:
            sql = ''' DELETE FROM fpa_foreing_currency WHERE financial_id={financial_id} AND company_id={company_id} and user_id={user_id}'''.format(
                financial_id=financial_reports.id, company_id=self.company_id.id, user_id=self.env.user.id)
            self.env.cr.execute(sql)
        where = ' WHERE 1=1 '
        cuenta = []
        # Cuentas
        if financial_reports:
            if financial_reports.concepts_ids:
                for conceptos in financial_reports.concepts_ids:
                    for cuentas in conceptos.account_ids:
                        cuenta.append(cuentas.id)
        # Agrega encabezado con parametros indicados por el usuario
        sql = " INSERT INTO fpa_foreing_currency(date, date_to, estado, company_id, user_id,chart_account_id, financial_id) " \
              "VALUES ('{date}','{date_to}','{estado}',{company_id},{user_id},{chart_account_id},{financial_id}) RETURNING ID ".format(
            date=datetime.now(),date_to=self.date_to,estado=self.estado,company_id=self.company_id.id,user_id=self.env.user.id,
            chart_account_id=self.chart_account_id.id,financial_id=financial_reports.id)
        self.env.cr.execute(sql)
        encabezado_id = False
        try:
            encabezado_id = self.env.cr.fetchone()[0]
        except ValueError:
            pass

        account = 'aml.account_id'

        if self.journal_ids:
            where += ''' AND aml.journal_id in ({journal_ids}) '''.format(
                journal_ids=(','.join(str(x.id) for x in self.journal_ids)))

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
        where_add = ''
        if self.account_ids:
            where_add = ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
            if module:
                if self.chart_account_id.niif:
                    where_add = ''' AND aml.account_niif_id in (%s) ''' % (
                        ','.join(str(x.id) for x in self.account_ids))
        where_account = ''
        if len(cuenta) > 0:
            where_account = 'AND ( aml.account_id IN ' + str(tuple(cuenta)) + ' )'
        if module:
            if self.chart_account_id.niif:
                account = 'aml.account_niif_id'
                if len(cuenta) > 0:
                    where_account = 'AND ( aml.account_niif_id IN ' + str(tuple(cuenta)) + ' )'

        if self.account_ids:
            where += ''' AND {account} in ({account_ids}) '''.format(
                account_ids=(','.join(str(x.id) for x in self.account_ids)), account=account)

        condition = 'aa.id = {account}'.format(account=account)
        where += where_add + where_account
        # construir query para meses no acumulativos para cuentas de resultados y acumulativas para el resto
        actual_month = int(self.date_to[5:7])
        actual_year = int(self.date_to[0:4])
        start_month = 1
        month_where = ''
        while start_month <= actual_month:
            month = calendar.monthrange(actual_year, start_month)
            date_stop = str(actual_year) + '-' + str(start_month).rjust(2, '0') + '-' + str(month[1]).rjust(2, '0')
            date_start = str(actual_year) + '-' + str(start_month).rjust(2, '0') + '-' + '01'
            #para obtener acumulado segun la configuracion del concepto
            month_where += ''' SUM(CASE WHEN ffrc.accumulated AND (aml.date <='{date_stop}') --ACUMULADOS
                                                THEN (CASE WHEN ffrc.cierre IS TRUE 
                                                                THEN (CASE WHEN rp.currency_id != {currency_id} --ACUMULADO CON TRM CIERRE 
                                                                            THEN (debit-credit)*currency_rate_closed(COALESCE('{date_stop}',aml.date), COALESCE(aml.currency_id,{currency_id}))
                                                                            ELSE (debit-credit) 
                                                                    END)
                                                                ELSE (CASE WHEN rp.currency_id != {currency_id} --ACUMULADO SIN CIERRE (DOLARES DEL MOVIMIENTO + TRM CIERRE)
                                                                            THEN (CASE WHEN amount_currency_conv = 0 THEN (debit-credit)*currency_rate_closed(aml.date, COALESCE(aml.currency_id,{currency_id})) ELSE amount_currency_conv END )
                                                                            ELSE (debit-credit) 
                                                                    END) 
                                                                
                                                    END)
                                        WHEN (ffrc.accumulated IS FALSE OR ffrc.accumulated IS NULL)AND(aml.date BETWEEN '{date_start}' AND '{date_stop}')  --MOVIMIENTOS PERIODO
                                                THEN (CASE WHEN ffrc.cierre IS TRUE 
                                                                THEN (CASE WHEN rp.currency_id != {currency_id} -- MOVIMIENTO DEL PERIODO CON TRM CIERRE
                                                                            THEN (debit-credit)*currency_rate_closed(COALESCE('{date_stop}',aml.date), COALESCE(aml.currency_id,{currency_id}))
                                                                            ELSE (debit-credit) 
                                                                    END)
                                                                ELSE (CASE WHEN rp.currency_id != {currency_id} --MOVIMIENTO DEL PERIODO SIN CIERRE (DOLARES DEL MOVIMIENTO + TRM CIERRE )
                                                                            THEN (CASE WHEN amount_currency_conv = 0 THEN (debit-credit)*currency_rate_closed(COALESCE('{date_stop}',aml.date), COALESCE(aml.currency_id,{currency_id})) ELSE amount_currency_conv END )
                                                                            ELSE (debit-credit) 
                                                                    END) 
                                                                
                                                    END)
                                                ELSE 0.0 
                                    END) as month{indicador}, '''.format(date_start=date_start,
                                                                         date_stop=date_stop,
                                                                         indicador=str(start_month),
                                                                         currency_id=self.currency_id.id)
            start_month += 1
        if start_month <= 12:
            for x in range(start_month, 12 + 1):
                month_where += ''' 0 as month{indicador}, '''.format(indicador=x)

        months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october',
                  'november', 'december']
        # movimientos
        sql = ''' INSERT INTO fpa_foreing_currency_line(accumulated,concepts_id,sequence,account_id,january,february,march,april,may, 
                                june,july,august,september,october,november,december,user_id,financial_id,company_id,encabezado_id,bold,cierre)
                                    SELECT COALESCE(ffrc.accumulated,FALSE), ffrc.id,ffrc.sequence,{account},
                                    {month_where} {user_id},{financial_id},{company_id},{encabezado_id},False, ffrc.cierre
                                        FROM account_move_line aml
                                        INNER JOIN account_account aa ON {condition}
                                        LEFT JOIN res_company rp ON rp.id = aml.company_id
                                        INNER JOIN fpa_financial_reports_concepts_account ffrca ON ffrca.account_account_id = aa.id
                                        INNER JOIN fpa_financial_reports_concepts ffrc on ffrc.id = ffrca.fpa_financial_reports_concepts_id
                                            AND ffrc.financial_reports = {financial_id}
                                        {where}
                                        AND aml.date <= '{date_to}'
                                        GROUP BY {account}, ffrc.sequence, aa.code, ffrc.id, ffrc.accumulated, rp.currency_id
                                        ORDER BY {account} '''.format(where=where,
                                                                       condition=condition,
                                                                       user_id=self.env.user.id,
                                                                       financial_id=financial_reports.id,
                                                                       company_id=self.env.user.company_id.id,
                                                                       encabezado_id=encabezado_id,
                                                                       month_where=month_where,
                                                                       date_to=self.date_to,
                                                                       account=account)
        _logger.info(sql)
        self.env.cr.execute(sql)
        # ACTUALIZAR SALDO FINAL CON MOVIMIENTOS NO ACUMULATIVOS PARA CUENTAS DE RESULTADO
        self.env.cr.execute(
            ''' UPDATE fpa_foreing_currency_line SET amount_final = january+february+march+april+may+june+july+august+september+october+november+december
                    WHERE accumulated IS FALSE AND user_id={user_id} AND financial_id={financial_id} AND company_id={company_id} '''.format(
                user_id=self.env.user.id, financial_id=financial_reports.id, company_id=self.env.user.company_id.id))

        # ACTUALIZAR SALDO FINAL CON ACUMULATIVOS PARA CUENTAS DE BALANCE Y PATRIMONIO
        for x in enumerate(months):
            sql =''' UPDATE fpa_foreing_currency_line SET amount_final = {month} WHERE accumulated AND {month} != 0 AND user_id={user_id} 
                                AND financial_id={financial_id} AND company_id={company_id} '''.format(
                                user_id=self.env.user.id,
                                financial_id=financial_reports.id,
                                company_id=self.env.user.company_id.id,
                                month=x[1])
            self.env.cr.execute(sql)

        # Agregar totales por concepto
        sql = ''' INSERT INTO fpa_foreing_currency_line (sequence, bold, user_id,company_id,account_id, cuenta, encabezado_id,resume, concepts_id, 
                            financial_id,january,february,march,may,june,july,august,september,october,november,december,amount_final)
                            SELECT ffrc.sequence, True, {user_id}, {company_id}, null, null, {encabezado_id}, False, ffrc.id,
                                {financial_id},SUM(january),SUM(february),SUM(march),SUM(may),SUM(june),SUM(july),SUM(august),SUM(september),SUM(october),
                                SUM(november),SUM(december),SUM(amount_final) FROM fpa_financial_reports_concepts ffrc 
                        LEFT JOIN fpa_foreing_currency_line fpl ON ffrc.id = fpl.concepts_id 
                            WHERE ffrc.financial_reports = {financial_id} AND fpl.user_id={user_id} AND fpl.company_id={company_id} 
                            GROUP BY ffrc.sequence, ffrc.id '''.format(user_id=self.env.user.id,company_id=self.env.user.company_id.id,
                                                                       encabezado_id=encabezado_id,financial_id=financial_reports.id)
        self.env.cr.execute(sql)


        # Eliminar lineas sin VALORES
        # deletes= ''
        # for x in enumerate(months):
        #     deletes += ''' {x}=0 AND '''.format(x=x[1])
        # deletes+='''  amount_final=0 '''
        sql = ''' DELETE FROM fpa_foreing_currency_line WHERE amount_final = 0 AND user_id={user_id} AND financial_id={financial_id} AND company_id={company_id} '''.format(
            user_id=self.env.user.id,financial_id=financial_reports.id,company_id=self.env.user.company_id.id)
        self.env.cr.execute(sql)

        # ACTUALIZAR UNIDADES
        if financial_reports.unidades > 1:
            setters = ''
            for x in enumerate(months):
                setters += ''' {x}={x}/{unidades}, '''.format(x=x[1], unidades=financial_reports.unidades)
            setters += ''' amount_final = amount_final / {unidades} '''.format(unidades=financial_reports.unidades)
            sql = ''' UPDATE fpa_foreing_currency_line SET {setters} WHERE company_id={company_id} AND user_id={user_id} AND financial_id = {financial_id} '''.format(
                    unidades=financial_reports.unidades, financial_id=financial_reports.id, user_id=self.env.user.id,
                    company_id=self.env.user.company_id.id,setters=setters)
            self.env.cr.execute(sql)

        # cambia el signo
        if financial_reports.sign:
            sings = ''
            for x in enumerate(months):
                sings += ''' {x}={x}*-1, '''.format(x=x[1])
            sings += ''' amount_final=amount_final*-1 '''
            sql = ''' UPDATE fpa_foreing_currency_line SET {sings} WHERE user_id={user_id} AND financial_id={financial_id} AND company_id={company_id} '''.format(
                user_id=self.env.user.id,financial_id=financial_reports.id,company_id=self.env.user.company_id.id,sings=sings)
            self.env.cr.execute(sql)
        return financial_reports.view_function(generate=False)
