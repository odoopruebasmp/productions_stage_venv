# -*- coding: utf-8 -*-
import logging
from datetime import datetime

import openerp.addons.decimal_precision as dp
from openerp import models, fields, api, _
from openerp.exceptions import Warning

_logger = logging.getLogger(__name__)


class account_financial_reports_accounting_auxiliar_fc(models.Model):
    _name = "fpa.auxiliar.fc"

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


class account_financial_reports_accounting_auxiliar_fc_line(models.Model):
    _name = "fpa.auxiliar.fc.line"

    account_id = fields.Many2one('account.account', string='Cuenta', ondelete='cascade', index=True)
    account_niif_id = fields.Many2one('account.account', string='Cuenta NIIF', ondelete='cascade', index=True)
    account_analytic_id = fields.Many2one('account.analytic.account', string='Cuenta analitica', ondelete='cascade',
                                          index=True)
    partner_id = fields.Many2one('res.partner', string='Tercero', ondelete='cascade', index=True)
    move_line_id = fields.Many2one('account.move.line', string='Move line', ondelete='cascade', index=True)
    amount_inicial = fields.Float(string='Saldo Inicial', digits=dp.get_precision('Account'))
    ai_fc = fields.Float('SI - ME', digits=dp.get_precision('Account'), help='Saldo inicial en moneda extranjera')
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    mv_fc = fields.Float('DC - ME', digits=dp.get_precision('Account'), help='Movimiento en moneda extranjera')
    amount_final = fields.Float(string='Saldo Final', digits=dp.get_precision('Account'))
    af_fc = fields.Float('SF - ME', digits=dp.get_precision('Account'), help='Saldo final en moneda extranjera')
    currency_id = fields.Many2one('res.currency', 'Moneda', index=True)
    resume = fields.Boolean(string="Resumen")
    nivel = fields.Integer(string="Nivel")
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte', index=True)
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade', index=True)
    bold = fields.Boolean(string="Bold", default=False)
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista')
    fecha = fields.Date(string='Fecha')
    cuenta = fields.Char(string='Cuenta')
    asiento = fields.Char(string='Asiento')
    linea = fields.Char(string='Linea')
    encabezado_id = fields.Many2one('fpa.auxiliar', string='Encabezado', ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Compañia', index=True)
    user_id = fields.Many2one('res.users', string='Usuario', index=True)


class wizard_account_financial_reports_accounting_auxiliar_fc(models.TransientModel):
    _name = "fpa.auxiliar.fc.wizard"

    def _set_niveles(self):
        id = self.env.context.get('active_ids', False)
        return self.env['fpa.niveles'].search([('financial_reports', '=', id), (
            'code', 'in', ('0', '1', '2', '3', '4', '5', '6', '7', '8', '97', '99'))], order='code asc')

    def _get_domain(self):
        id = self.env.context.get('active_ids', False)
        return [('financial_reports', '=', id)]

    account_filter = fields.Boolean(string="Filtro adicional de cuentas")
    partner_filter = fields.Boolean(string="Filtro adicional de terceros")
    journal_filter = fields.Boolean(string="Filtro adicional de diarios")
    niveles = fields.Many2many('fpa.niveles', string='Niveles', help='Seleccione los niveles para la consulta.',
                               default=_set_niveles, domain=_get_domain, required=True)
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',
                                       help='Plan de cuentas asociado a las cuentas contables que se desean consultar.',
                                       required=True, domain=[('parent_id', '=', False)])
    period_balance_ids = fields.Many2many('account.period', string='Periodos',
                                          help='Período asociado a los movimientos contables a consultar.')
    currency_ids = fields.Many2many('res.currency', string='Monedas', help='Moneda de conversión asociada a los '
                                                                           'movimientos a consultar')
    journal_ids = fields.Many2many('account.journal', string='Diarios',
                                   help='Diario asociado a los movimientos contables a consultar.')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type', '!=', 'view')],
                                   help='Cuentas contables asociadas a los movimientos a consultar.')
    analytic_ids = fields.Many2many('account.analytic.account', string='Cuentas analiticas',
                                    domain=[('type', '!=', 'view')])
    partner_ids = fields.Many2many('res.partner', string='Terceros',
                                   help='Tercero asociado a los movimientos contables a consultar.')
    date_from = fields.Date(string="Fecha Inicial", required=True, help='Fecha inicial de consulta, el informe '
                                                                        'retornará los movimientos contables desde '
                                                                        'esta fecha.')
    date_to = fields.Date(string="Fecha Final", required=True, help='Fecha final de consulta, el informe retornará '
                                                                    'los movimientos contables hasta esta fecha.')
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')],
                              default='todos', string='Estados', required=True,
                              help='Estado en el cual se desean consultar los movimientos contables.')
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
        _logger.debug('NIVELES:' + str(niveles))
        st = datetime.now()

        self.env.cr.execute(''' select count(*) from fpa_auxiliar_fc_line ''')
        count = self.env.cr.fetchone()[0]

        # recorre conceptos configurados en el informe
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])
        te = datetime.now()
        # truncate a la tabla cuando sean mas de 1millón de registros, para que no tarde tanto eliminando las lineas antes de crear las nuevas
        if count > 1000000:
            self.env.cr.execute(''' TRUNCATE fpa_auxiliar_fc_line ''')
        else:
            self.env.cr.execute(
                ''' DELETE FROM fpa_auxiliar_fc_line WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
                    financial_reports.id, self.env.user.company_id.id, self.env.user.id))
        self.env.cr.execute(
            ''' DELETE FROM fpa_auxiliar WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
                financial_reports.id, self.env.user.company_id.id, self.env.user.id))

        where = ''
        # Agrega encabezado con parametros indicados por el usuario
        self.env.cr.execute(
            ''' INSERT INTO fpa_auxiliar(date, date_from, date_to, estado, company_id, user_id,chart_account_id,financial_id) VALUES ('%s','%s','%s','%s',%s,%s,%s,%s) RETURNING ID ''' % (
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

        account = 'aml.account_id'
        condition = 'aa.id = account_id'
        # verificar si tiene el modulo de niif_account instalado
        module = self.env['ir.module.module'].search([('name', '=', 'niif_account'), ('state', '=', 'installed')])
        if module:
            if self.chart_account_id.niif:
                account = 'aml.account_niif_id'
                condition = 'aa.id = aml.account_niif_id'

        te = datetime.now()
        # INGRESAR MOVIMIENTOS
        movimientos = ''' INSERT INTO fpa_auxiliar_fc_line (bold,user_id,company_id,account_id,cuenta,account_analytic_id,
        fecha,asiento,linea,partner_id,debit,credit,amount_final,mv_fc,af_fc,currency_id,encabezado_id,financial_id, nivel)
                            SELECT False as bold, %s as user_id, %s as company_id, %s::integer as account_id, aa.code,
                                aml.analytic_account_id, aml.date as fecha, am.name, aml.name, 
                                aml.partner_id, round(aml.debit,2) as debit, round(aml.credit,2) as credit, 
                                aml.debit-aml.credit as amount_final,aml.amount_currency,aml.amount_currency,
                                aml.currency_id,%s::integer as encabezado_id, %s as financial_id, 99 as nivel
                                 FROM account_move_line aml
                                    INNER JOIN account_move am ON am.id = aml.move_id
                                    INNER JOIN account_account aa ON %s AND aa.parent_zero = %s
                                    INNER JOIN account_period ap on ap.id = aml.period_id                                 
                                    WHERE aml.company_id = %s 
                                        AND aml.date BETWEEN '%s' and '%s'
                                %s %s  ''' % (
            self.env.user.id, self.env.user.company_id.id,
            account, encabezado_id, financial_reports.id, condition, self.chart_account_id.id,
            self.env.user.company_id.id,
            self.date_from, self.date_to, where_account, where)
        self.env.cr.execute(movimientos)

        # SALDO INICIAL; DEBITO; CREDITO Y SALDO FINAL POR CUENTA CONTABLE
        saldo_inicial = ''' INSERT INTO fpa_auxiliar_fc_line (bold,user_id,company_id,account_id,cuenta,amount_inicial,debit, 
                                        credit,amount_final,ai_fc,mv_fc,af_fc,currency_id,encabezado_id,financial_id,nivel)
                                        SELECT True as bold,  %s as user_id, %s as company_id, account_id, cuenta, SUM(amount_inicial),
                                                SUM(round(debit,2)) as debit,SUM(round(credit,2)) as credit,SUM(round(amount_inicial+debit-credit,2)) as amount_final,
                                                SUM(ai_fc),SUM(mv_fc),SUM(round(ai_fc+mv_fc,2)) as af_fc,currency_id,
                                                %s::integer as encabezado_id, %s as financial_id, 97 as nivel
                                                FROM (
                                                    SELECT %s as account_id, aa.code as cuenta,
                                                        SUM(round(aml.debit,2)-round(aml.credit,2)) as amount_inicial,0 as debit,0 as credit,
                                                        SUM(round(aml.amount_currency,2)) as ai_fc,0 as mv_fc,aml.currency_id
                                                         FROM account_move_line aml
                                                             INNER JOIN account_move am ON am.id = aml.move_id
                                                             INNER JOIN account_account aa ON %s AND aa.parent_zero = %s
                                                             INNER JOIN account_period ap on ap.id = aml.period_id
                                                                 WHERE aml.company_id = %s 
                                                                    AND aml.date < '%s'
                                                        %s %s GROUP BY %s,aa.code,aml.currency_id 
                                                    UNION
                                                    SELECT account_id, cuenta,
                                                        0 as amount_inicial, sum(round(debit,2)), sum(round(credit,2)),
                                                        0 as ai_fc,sum(round(mv_fc,2)), currency_id
                                                         FROM fpa_auxiliar_fc_line aml
                                                                 WHERE aml.company_id = %s AND aml.user_id = %s
                                                                 AND nivel = 99
                                                    GROUP BY account_id, cuenta, currency_id
                                                ) as datos GROUP BY account_id, cuenta, currency_id
                                        ''' % (
            self.env.user.id, self.env.user.company_id.id, encabezado_id, financial_reports.id,
            account, condition, self.chart_account_id.id, self.env.user.company_id.id, self.date_from,
            where_account, where, account, self.env.user.company_id.id,
            self.env.user.id)
        _logger.debug(saldo_inicial)
        self.env.cr.execute(saldo_inicial)
        _logger.debug('culminó de ingresar debito, credito y saldo final. Tiempo: %s' % (datetime.now() - te))

        # # recorre la estructura indicada en el plan de cuentas para agregar las cuentas de tipo vista
        te = datetime.now()
        for structure in self.chart_account_id.structure_id.sorted(key=lambda r: r.sequence, reverse=True):
            if str(structure.sequence) in niveles:
                # nivel
                nivel = '''INSERT INTO fpa_auxiliar_fc_line (bold, user_id,company_id, account_id, cuenta, partner_id, 
                amount_inicial, debit, credit, amount_final,ai_fc,mv_fc,af_fc,currency_id,encabezado_id,nivel,financial_id)
                            SELECT True, %s,%s,aar.id, aar.code, null, sum(al.amount_inicial) as amount_inicial, sum(al.debit) as debit,
                                sum(al.credit) as credit, sum(al.amount_final) as amount_final, sum(al.ai_fc) as ai_fc,
                                sum(al.mv_fc) as mv_fc, sum(al.af_fc) as af_fc, al.currency_id  as currency_id,
                                %s, %s, %s
                                FROM fpa_auxiliar_fc_line al
                                    INNER JOIN account_account aar on aar.code = substring(al.cuenta from 1 for %s) 
                                        and aar.type = 'view' and aar.company_id = al.company_id
                                    WHERE al.nivel=97 and al.user_id =%s and al.company_id = %s
                                    GROUP BY aar.id, aar.code,al.currency_id ''' % (
                    self.env.user.id, self.env.user.company_id.id, encabezado_id, structure.sequence,
                    financial_reports.id,
                    structure.digits, self.env.user.id, self.env.user.company_id.id)
                self.env.cr.execute(nivel)
        _logger.debug('culminó de agregar las estructuras. Tiempo: %s' % (datetime.now() - te))
        if '0' in niveles:
            # Inserta PUC como resumen de todos los movimiento
            chart_account = '''INSERT INTO fpa_auxiliar_fc_line (bold,user_id,company_id, account_id, cuenta, partner_id, amount_inicial,
                            debit, credit, amount_final,ai_fc,mv_fc,af_fc,currency_id,encabezado_id,nivel,financial_id) 
                            select True, %s,%s,%s, '%s', null, sum(al.amount_inicial) as amount_inicial, 
                            sum(al.debit) as debit,  sum(al.credit) as credit, sum(al.amount_final) as amount_final, 
                            sum(al.ai_fc) as ai_fc,sum(al.mv_fc) as mv_fc,sum(al.af_fc) as af_fc,al.currency_id as 
                            currency_id, %s, 0, %s from fpa_auxiliar_fc_line al where al.nivel=97
                            and al.user_id = %s and al.company_id = %s GROUP BY al.currency_id''' % (
                self.env.user.id, self.env.user.company_id.id, self.chart_account_id.id,
                self.chart_account_id.code, encabezado_id, financial_reports.id, self.env.user.id,
                self.env.user.company_id.id)
            _logger.info(chart_account)
            self.env.cr.execute(chart_account)
        if '97' not in niveles:
            # eliminar lineas de saldo inicial por cuenta
            self.env.cr.execute(''' DELETE FROM fpa_auxiliar_fc_line WHERE nivel=97 ''')
        if '99' not in niveles:
            # eliminar lineas de movimientos
            self.env.cr.execute(''' DELETE FROM fpa_auxiliar_fc_line WHERE nivel=99 ''')
        # eliminar lineas sin saldo inicial, debito y credito
        self.env.cr.execute(
            ''' DELETE FROM fpa_auxiliar_fc_line WHERE amount_inicial=0 and debit=0 and credit=0 and amount_final=0''')

        # aplicar conversion de miles
        if int(financial_reports.unidades) > 1:
            self.env.cr.execute(
                ''' UPDATE fpa_auxiliar_fc_line SET amount_inicial=amount_inicial/{unidades}, debit=debit/{unidades}, 
                    credit=credit/{unidades},amount_final=amount_final/{unidades},ai_fc/{unidades},mv_fc/{unidades},
                    af_fc/{unidades} WHERE company_id={company_id} AND user_id={user_id} AND financial_id = 
                    {financial_id} '''.format(unidades=financial_reports.unidades, financial_id=financial_reports.id,
                                              user_id=self.env.user.id, company_id=self.env.user.company_id.id))
        _logger.debug('Tiempo: %s' % (datetime.now() - st))
        return financial_reports.view_function(generate=False)
