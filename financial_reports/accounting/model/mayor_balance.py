# -*- coding: utf-8 -*-
import logging
from datetime import datetime

import openerp.addons.decimal_precision as dp
from openerp import models, fields, api, _
from openerp.exceptions import Warning

_logger = logging.getLogger(__name__)


class afrp_mayor_balance(models.Model):
    _name = "fpa.mayor.balance"

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


class afrp_mayor_balance_line(models.Model):
    _name = "fpa.mayor.balance.line"

    account_id = fields.Many2one('account.account', string='Cuenta', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Tercero', ondelete='cascade')
    nivel = fields.Integer(string="Nivel")
    amount_inicial_debit = fields.Float(string='Saldo Inicial Débito', digits=dp.get_precision('Account'))
    amount_inicial_credit = fields.Float(string='Saldo Inicial Crédito', digits=dp.get_precision('Account'))
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_final_debit = fields.Float(string='Saldo Final Débito', digits=dp.get_precision('Account'))
    amount_final_credit = fields.Float(string='Saldo Final Crédito', digits=dp.get_precision('Account'))
    cuenta = fields.Char(string='Cuenta')
    resume = fields.Boolean(string="Resumen")
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade')
    bold = fields.Boolean(string="Bold", default=False)
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    encabezado_id = fields.Many2one('fpa.mayor.balance', string='Encabezado', ondelete='cascade')


class wizard_afrp_mayor_balance(models.TransientModel):
    _name = "fpa.mayor.balance.wizard"

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
    cierre = fields.Boolean(string="Cierre")
    niveles = fields.Many2many('fpa.niveles', string='Niveles', help='Seleccione los niveles para la consulta.',
                               default=_set_niveles, domain=_get_domain, required=True)
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts',
                                       required=True, domain=[('parent_id', '=', False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    period_balance_ids = fields.Many2many('account.period', string='Periodos')
    journal_ids = fields.Many2many('account.journal', string='Diarios')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type', '!=', 'view')])
    partner_ids = fields.Many2many('res.partner', string='Terceros')
    date_from = fields.Date(string="Fecha Inicial", required=True)
    date_to = fields.Date(string="Fecha Final", required=True)
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
            raise Warning(_('Error en las fechas!'), _("Las fechas planificadas estan mal configuradas"))

    @api.multi
    def generar(self):
        niveles = [x.code for x in self.niveles]
        self.env.cr.execute(''' select count(*) from fpa_mayor_balance_line ''')
        count = self.env.cr.fetchone()[0]

        # recorre conceptos configurados en el informe
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])

        # truncate a la tabla cuando sean mas de 1millón de registros, para que no tarde tanto eliminando las lineas
        if count > 1000000:
            self.env.cr.execute(''' TRUNCATE fpa_mayor_balance_line ''')
        else:
            self.env.cr.execute(
                ''' DELETE FROM fpa_mayor_balance_line WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
                    financial_reports.id, self.company_id.id, self.env.user.id))
            self.env.cr.execute(
                ''' DELETE FROM fpa_mayor_balance WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
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
            ''' INSERT INTO fpa_mayor_balance(date, date_from, date_to, estado, company_id, user_id,chart_account_id,financial_id) VALUES ('%s','%s','%s','%s',%s,%s,%s,%s) RETURNING ID ''' % (
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

        # if self.partner_ids:
        #     where += ''' AND aml.partner_id in (%s) ''' % (','.join(str(x.id) for x in self.partner_ids))

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

        # Obtener fecha inicial de ultimo cierre/ Se comenta porque esta mal
        self.env.cr.execute(" SELECT date_start FROM account_fiscalyear af WHERE state = 'done' "
                            " AND company_id = {company_id} order by write_date desc limit 1 ".
                            format(company_id=self.env.user.company_id.id))
        date_start = self.env.cr.fetchone()
        if not date_start:
            date_start = str('1900-01-01')
        else:
            date_start = date_start[0]

        relation = ' LEFT '
        if financial_reports.concepts_ids:
            relation = ' INNER '

        ##Movimientos
        movimientos = '''INSERT INTO fpa_mayor_balance_line (nivel, sequence, concepts_id, bold, user_id,company_id,account_id, cuenta, amount_inicial_debit, amount_inicial_credit,
							      debit, credit, amount_final_debit, amount_final_credit,encabezado_id,financial_id)
                        	  SELECT 99, ffrc.sequence, ffrc.id as concepts_id, False, %s,%s, account_id, aa.code, 
                                        sum(amount_inicial_debit) as amount_inicial_debit, sum(amount_inicial_credit) as amount_inicial_credit, 
                                        sum(debit) AS debit, sum(credit) AS credit,
                                        (CASE WHEN (sum(amount_inicial_debit + debit - amount_inicial_credit - credit))>0 
                                            THEN sum(amount_inicial_debit + debit - amount_inicial_credit - credit) ELSE 0 END ) as amount_final_debit,
                        	            (CASE WHEN (sum(amount_inicial_credit + credit - amount_inicial_debit - debit))>0 
                                            THEN sum(amount_inicial_credit + credit - amount_inicial_debit - debit) ELSE 0 END ) as amount_final_credit, 
                                            %s::integer as encabezado_id, 
                                            %s::integer as financial_id
                        	   FROM (
                                        SELECT %s as account_id, 0 as amount_inicial_debit,0 as amount_inicial_credit, 
                                            sum(aml.debit) as debit, sum(aml.credit) as credit
                                            FROM account_move_line aml
                                                INNER JOIN account_period ap on ap.id = aml.period_id
                                                WHERE  aml.company_id = %s
                                                AND aml.date BETWEEN '%s' and '%s'
                                                %s
                                            GROUP BY %s
                                        UNION
                                        --Saldos iniciales
                                        SELECT %s as account_id,
                                        (CASE WHEN sum(debit-credit)>0 THEN sum(debit-credit) ELSE 0 END) as amount_inicial_debit,
                                        (CASE WHEN sum(debit-credit)<0 THEN sum(credit-debit) ELSE 0 END) as amount_inicial_credit,
                                        0 as debit, 0 as credit
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
            account, self.env.user.company_id.id, self.date_from, where,
            account,
            condition, self.env.user.company_id.id, self.chart_account_id.id, relation, relation, financial_reports.id)
        _logger.info(movimientos)
        self.env.cr.execute(movimientos)

        if '100' in niveles:
            # Agregar totales por concepto
            sql = " INSERT INTO fpa_mayor_balance_line (nivel, sequence, bold, user_id,company_id,account_id, cuenta, amount_inicial_debit,amount_inicial_credit, " \
                  " debit,credit,amount_final_debit,amount_final_credit,encabezado_id,resume, concepts_id, financial_id) " \
                  " SELECT 100, ffrc.sequence, True, %s, %s, null, null, SUM(amount_inicial_debit),SUM(amount_inicial_credit),SUM(debit),SUM(credit), " \
                  " SUM(amount_final_debit),SUM(amount_final_credit), %s, False, ffrc.id, %s " \
                  " FROM fpa_financial_reports_concepts ffrc " \
                  " LEFT JOIN fpa_mayor_balance_line fpl ON ffrc.id = fpl.concepts_id " \
                  " WHERE ffrc.financial_reports = %s AND fpl.user_id=%s AND fpl.company_id=%s" \
                  " GROUP BY ffrc.sequence, ffrc.id " % (
                      self.env.user.id, self.company_id.id, encabezado_id, financial_reports.id, financial_reports.id,
                      self.env.user.id, self.env.user.company_id.id)
            self.env.cr.execute(sql)

        if '99' not in niveles:
            self.env.cr.execute(" DELETE FROM fpa_mayor_balance_line WHERE nivel = 99 ")

        # eliminar movimientos en cero
        self.env.cr.execute(
            " DELETE FROM fpa_mayor_balance_line WHERE amount_inicial_debit=0 and amount_inicial_credit = 0 and debit = 0 and credit = 0 and amount_final_debit=0 and amount_final_credit=0 ")
        # Hacer cero los negativos
        self.env.cr.execute(
            " UPDATE fpa_mayor_balance_line SET amount_final_debit = 0 WHERE amount_final_debit < 0 AND company_id = %s AND user_id = %s " % (
                self.company_id.id, self.env.user.id))
        self.env.cr.execute(
            " UPDATE fpa_mayor_balance_line SET amount_final_credit = 0 WHERE amount_final_credit < 0 AND company_id = %s AND user_id = %s " % (
                self.company_id.id, self.env.user.id))

        # amount inicial y amount final
        # self.env.cr.execute(
        #     " UPDATE fpa_mayor_balance_line SET amount_inicial = amount_inicial_debit-amount_inicial_credit, amount_final = amount_final_debit-amount_final_credit WHERE company_id = %s AND user_id = %s " % (
        #         self.company_id.id, self.env.user.id))

        if financial_reports.unidades > 1:
            self.env.cr.execute(
                ''' UPDATE fpa_mayor_balance_line SET amount_inicial_debit=amount_inicial_debit/{unidades}, amount_inicial_credit=amount_inicial_credit/{unidades},
                    debit=debit/{unidades},credit=credit/{unidades},amount_final_debit=amount_final_debit/{unidades}, amount_final_credit=amount_final_credit/{unidades} 
                    WHERE company_id={company_id} AND user_id={user_id} AND financial_id = {financial_id} '''.format(
                    unidades=financial_reports.unidades, financial_id=financial_reports.id, user_id=self.env.user.id,
                    company_id=self.env.user.company_id.id))

        return financial_reports.view_function(generate=False)
