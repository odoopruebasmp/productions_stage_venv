# -*- coding: utf-8 -*-
import logging
from datetime import datetime

import openerp.addons.decimal_precision as dp
from openerp import models, fields, api, _
from openerp.exceptions import Warning

_logger = logging.getLogger(__name__)


class account_financial_reports_accounting_inventario_balance(models.Model):
    _name = "fpa.inventario.balance"

    date = fields.Datetime(string="Fecha")
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')],
                              default='validados', string='Estados')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts',
                                       required=True, domain=[('parent_id', '=', False)])


class account_financial_reports_accounting_inventario_balance_line(models.Model):
    _name = "fpa.inventario.balance.line"

    account_id = fields.Many2one('account.account', string='Cuenta', ondelete='cascade')
    amount_inicial = fields.Float(string='Saldo inicial', digits=dp.get_precision('Account'))
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_final = fields.Float(string='Saldo final', digits=dp.get_precision('Account'))
    amount_inicial = fields.Float(string='Saldo', digits=dp.get_precision('Account'))
    resume = fields.Boolean(string="Resumen")
    nivel = fields.Integer(string="Nivel")
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade')
    bold = fields.Boolean(string="Bold", default=False)
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista')
    cuenta = fields.Char(string='Cuenta')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    encabezado_id = fields.Many2one('fpa.inventario.balance', string='Encabezado', ondelete='cascade')


class wizard_account_financial_reports_accounting_inventario_balance(models.TransientModel):
    _name = "fpa.inventario.balance.wizard"

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
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts',
                                       required=True, domain=[('parent_id', '=', False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    period_balance_ids = fields.Many2many('account.period', string='Periodos')
    journal_ids = fields.Many2many('account.journal', string='Diarios')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type', '!=', 'view')])
    date_from = fields.Date(string="Fecha Inicial", required=True)
    date_to = fields.Date(string="Fecha Final", required=True)
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')],
                              default='todos', string='Estados', required=True)
    sp_periods = fields.Boolean('Apertura/Cierre', help='Marque este check si quiere tener en cuenta los '
                                    'movimientos pertenecientes a periodos de Apertura/Cierre', default=True)

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
            raise Warning(_('Error en las fechas!'), _("Las fechas planificadas estan mal configuradas"))

    @api.multi
    def generar(self):
        niveles = [x.code for x in self.niveles]
        _logger.info(niveles)
        self.env.cr.execute(''' select count(*) from fpa_inventario_balance_line ''')
        count = self.env.cr.fetchone()[0]

        # recorre conceptos configurados en el informe
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])

        # truncate a la tabla cuando sean mas de 1millón de registros, para que no tarde tanto eliminando las lineas
        if count > 1000000:
            self.env.cr.execute(''' TRUNCATE fpa_inventario_balance_line ''')
        else:
            self.env.cr.execute(
                ''' DELETE FROM fpa_inventario_balance_line WHERE financial_id = %s AND company_id = %s and user_id = %s''' % (
                financial_reports.id, self.company_id.id, self.env.user.id))
            self.env.cr.execute(
                ''' DELETE FROM fpa_inventario_balance WHERE financial_id = %s AND company_id = %s and user_id = %s''' % (
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
        self.env.cr.execute(
            ''' INSERT INTO fpa_inventario_balance(date, date_from, date_to, estado, company_id, user_id,chart_account_id, financial_id) VALUES ('%s','%s','%s','%s',%s,%s,%s,%s) RETURNING ID ''' % (
                datetime.now(), self.date_from, self.date_to, self.estado, self.company_id.id, self.env.user.id,
                self.chart_account_id.id, financial_reports.id))
        try:
            encabezado_id = self.env.cr.fetchone()[0]
        except ValueError:
            pass

        # Filtros adicionales
        if self.journal_ids:
            where += ''' AND aml.journal_id in (%s) ''' % (
                ','.join(str(x.id) for x in self.journal_ids))

        if self.account_ids:
            if self.chart_account_id.niif:
                where += ''' AND aml.account_niif_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
            else:
                where += ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))

        if self.estado == 'borrador':
            estado = 'draft'
        elif self.estado == 'validados':
            estado = 'valid'
        else:
            estado = '%'
        where += ''' AND aml.state like '%s' ''' % estado

        sp_periods = '' if self.sp_periods else ' AND ap.special is False '
        where += sp_periods

        # verificar si tiene el modulo de niif_account instalado
        module = self.env['ir.module.module'].search([('name', '=', 'niif_account'), ('state', '=', 'installed')])
        # agregar condición de cuentas indicadas en el wizard
        condition = 'aa.id = movimientos.account_id'
        account = 'aml.account_id'
        where_add = ''
        if self.account_ids:
            where_add = ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
            if module:
                if self.chart_account_id.niif:
                    where_add = ''' AND aml.account_niif_id in (%s) ''' % (
                        ','.join(str(x.id) for x in self.account_ids))
        if module:
            if self.chart_account_id.niif:
                condition = 'aa.id = account_id'
                account = 'aml.account_niif_id'
        where += where_add

        # Saldo inicial
        self.env.cr.execute(" select ap.date_start from account_move_line aml "
                            " inner join account_move am on am.id = aml.move_id "
                            " inner join account_period ap on ap.id = aml.period_id and special is True "
                            " inner join account_journal aj on aj.id = aml.journal_id and aj.type = 'situation' "
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

        # Movimientos
        movimientos = '''INSERT INTO fpa_inventario_balance_line (sequence, concepts_id, bold, user_id,company_id,account_id, cuenta,
                            amount_inicial,debit,credit,amount_final,encabezado_id,financial_id,nivel)
                            SELECT ffrc.sequence, ffrc.id as concepts_id, False,%s,%s, account_id, aa.code, sum(si) as si, 
                            sum(debit) as debit, sum(credit) as credit, 
                            sum(si+debit-credit) as amount_final, %s::integer as encabezado_id, %s financial_id, 99
                            FROM (
                                SELECT %s as account_id, 0 as si, sum(aml.debit) as debit, sum(aml.credit) as credit
                                    FROM account_move_line aml
                                        INNER JOIN account_period ap on ap.id = aml.period_id
                                            WHERE  aml.company_id = %s
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
                            GROUP BY ffrc.sequence, ffrc.id, account_id, aa.code ''' % (
        self.env.user.id, self.company_id.id, encabezado_id, financial_reports.id,
        account, self.env.user.company_id.id, self.date_from, self.date_to, where, account,
        account, self.env.user.company_id.id, self.date_from, where, account,
        condition, self.env.user.company_id.id, self.chart_account_id.id, relation, relation, financial_reports.id)
        _logger.info(movimientos)
        self.env.cr.execute(movimientos)

        if '100' in niveles:
            # Agregar totales por concepto
            sql = " INSERT INTO fpa_inventario_balance_line (sequence, bold, user_id,company_id,account_id, cuenta, amount_inicial, " \
                  " debit,credit,amount_final,encabezado_id,resume, concepts_id, financial_id,nivel) " \
                  " SELECT ffrc.sequence, True, %s, %s, null, null, SUM(amount_inicial),SUM(debit),SUM(credit), " \
                  " SUM(amount_final), %s, False, ffrc.id, %s, 100 " \
                  " FROM fpa_financial_reports_concepts ffrc " \
                  " LEFT JOIN fpa_inventario_balance_line fpl ON ffrc.id = fpl.concepts_id " \
                  " WHERE ffrc.financial_reports = %s AND fpl.user_id=%s AND fpl.company_id=%s" \
                  " GROUP BY ffrc.sequence, ffrc.id " % (
                  self.env.user.id, self.company_id.id, encabezado_id, financial_reports.id, financial_reports.id,
                  self.env.user.id, self.env.user.company_id.id)
            self.env.cr.execute(sql)

        if '99' not in niveles:
            self.env.cr.execute(" DELETE FROM fpa_inventario_balance_line WHERE nivel=99 and user_id =%s and company_id=%s and financial_id=%s " % (
                    self.env.user.id, self.env.company_id.id, self.id))

        self.env.cr.execute(
            " DELETE FROM fpa_inventario_balance_line WHERE amount_inicial=0 AND debit=0 AND credit=0 AND amount_final=0 and user_id=%s and company_id=%s and financial_id=%s " % (
                self.env.user.id, self.env.user.company_id.id, self.id))

        if financial_reports.unidades > 1:
            self.env.cr.execute(
                ''' UPDATE fpa_inventario_balance_line SET debit=debit/{unidades}, 
                    credit=credit/{unidades},amount_final=amount_final/{unidades} 
                    WHERE company_id={company_id} AND user_id={user_id} AND financial_id = {financial_id} '''.format(
                    unidades=financial_reports.unidades, financial_id=financial_reports.id, user_id=self.env.user.id,
                    company_id=self.env.user.company_id.id))
        return financial_reports.view_function(generate=False)
