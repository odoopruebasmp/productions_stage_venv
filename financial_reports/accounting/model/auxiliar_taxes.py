# -*- coding: utf-8 -*-
import logging
from datetime import datetime

import openerp.addons.decimal_precision as dp
from openerp import models, fields, api, _
from openerp.exceptions import Warning

_logger = logging.getLogger(__name__)


class FinancialAuxiliarTaxes(models.Model):
    _name = "fpa.auxiliar.taxes"

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


class FinancialAuxiliarTaxesLine(models.Model):
    _name = "fpa.auxiliar.taxes.line"

    account_id = fields.Many2one('account.account', string='Cuenta', ondelete='cascade', index=True)
    account = fields.Char(string='Cuenta')
    account_niif_id = fields.Many2one('account.account', string='Cuenta NIIF', ondelete='cascade', index=True)
    account_analytic_id = fields.Many2one('account.analytic.account', string='Cuenta analitica', ondelete='cascade',
                                          index=True)
    partner_id = fields.Many2one('res.partner', string='Tercero', ondelete='cascade', index=True)
    move_line_id = fields.Many2one('account.move.line', string='Move line', ondelete='cascade', index=True)
    # amount_initial = fields.Float(string='Saldo Inicial', digits=dp.get_precision('Account'))
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_final = fields.Float(string='Saldo Final', digits=dp.get_precision('Account'))
    base_amount = fields.Float(string='Base', digits=dp.get_precision('Account'))
    tax_amount = fields.Float(string='Retención', digits=dp.get_precision('Account'))
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte', index=True)
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade', index=True)
    bold = fields.Boolean(string="Bold", default=False)
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista')
    fecha = fields.Date(string='Fecha')
    move_id = fields.Many2one('account.move', string='Reporte', index=True, ondelete='cascade')
    line = fields.Char(string='Linea')
    encabezado_id = fields.Many2one('fpa.auxiliar.taxes', string='Encabezado', ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Compañia', index=True)
    user_id = fields.Many2one('res.users', string='Usuario', index=True)
    account_tax_id = fields.Many2one('account.tax', string='Impuesto', index=True, ondelete='cascade')


class FinancialAuxiliarTaxesWizard(models.TransientModel):
    _name = "fpa.auxiliar.taxes.wizard"

    def _get_domain(self):
        id = self.env.context.get('active_ids', False)
        return [('financial_reports', '=', id)]

    account_filter = fields.Boolean(string="Filtro adicional de cuentas")
    partner_filter = fields.Boolean(string="Filtro adicional de terceros")
    analytic_filter = fields.Boolean(string="Filtro adicional de cuentas analiticas")
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',
                                       help='Plan de cuentas asociado a las cuentas contables que se desean consultar.',
                                       required=True, domain=[('parent_id', '=', False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True,
                                 help='Compañia asociada a los movimientos contables a consultar.')
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
    user_id = fields.Many2one('res.users', string='Usuario', help='Usuario que ejecuta la consulta.')

    @api.one
    @api.onchange('chart_account_id')
    def get_filter(self):
        id = self.env.context.get('active_ids', False)
        financial_reports = self.env['fpa.financial.reports'].browse(id)
        self.account_filter = financial_reports.account_filter
        self.partner_filter = financial_reports.partner_filter
        self.analytic_filter = financial_reports.analytic_filter

    @api.one
    @api.constrains('date_from', 'date_to')
    def _validar_fechas(self):
        if self.date_from > self.date_to:
            raise Warning(_('Error en las fechas!'), _("Las fechas planificadas estan mal configuradas"))

    @api.multi
    def generar(self):
        self.env.cr.execute(''' select count(*) from fpa_auxiliar_taxes_line ''')
        count = self.env.cr.fetchone()[0]

        # recorre conceptos configurados en el informe
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])

        # truncate a la tabla cuando sean mas de 1millón de registros, para que no tarde tanto eliminando las lineas antes de crear las nuevas
        if count > 1000000:
            self.env.cr.execute(''' TRUNCATE fpa_auxiliar_taxes_line ''')
        else:
            self.env.cr.execute(
                ''' DELETE FROM fpa_auxiliar_taxes_line WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
                    financial_reports.id, self.env.user.company_id.id, self.env.user.id))
        self.env.cr.execute(
            ''' DELETE FROM fpa_auxiliar_taxes WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (
                financial_reports.id, self.env.user.company_id.id, self.env.user.id))

        # Agrega encabezado con parametros indicados por el usuario
        self.env.cr.execute(
            ''' INSERT INTO fpa_auxiliar_taxes(date, date_from, date_to, company_id, user_id,chart_account_id,financial_id) 
                VALUES ('{date}','{date_from}','{date_to}',{company_id},{user_id},{chart_account_id},{financial_id}) 
                RETURNING ID '''.format(date=datetime.now(), date_from=self.date_from, date_to=self.date_to,
                                        company_id=self.env.user.company_id.id,
                                        user_id=self.env.user.id, chart_account_id=self.chart_account_id.id,
                                        financial_id=financial_reports.id))
        try:
            header_id = self.env.cr.fetchone()[0]
        except ValueError:
            header_id = False

        where = ' aml.company_id = {company_id} '.format(company_id=self.env.user.company_id.id)
        if self.account_ids:
            if self.chart_account_id.niif:
                where += ''' AND aml.account_niif_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
            else:
                where += ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))

        if self.partner_ids:
            where += ''' AND aml.partner_id in (%s) ''' % (','.join(str(x.id) for x in self.partner_ids))

        if self.analytic_ids:
            where += ''' AND aml.analytic_account_id in (%s) ''' % (','.join(str(x.id) for x in self.analytic_ids))

        # account = 'aml.account_id'
        # condition = 'aa.id = account_id'
        # # verificar si tiene el modulo de niif_account instalado
        # module = self.env['ir.module.module'].search([('name', '=', 'niif_account'), ('state', '=', 'installed')])
        # if module:
        #     if self.chart_account_id.niif:
        #         account = 'aml.account_niif_id'
        #         condition = 'aa.id = aml.account_niif_id'

        #     SELECT
        #     aml.account_id, aml.partner_id, aml.analytic_account_id, aml.date, SUM(
        #         aml.debit - aml.credit) as si, 0 as debit, 0 as credit,
        #     SUM(COALESCE(aml.base_amount, 0)) as base_amount, SUM(
        #         COALESCE(aml.tax_amount, 0)) as tax_amount, aml.account_tax_id, aml.move_id
        #     FROM
        #     account_move_line
        #     aml
        #     WHERE
        #     aml.date < '{date_from}'
        #     AND
        #     {where}
        #     GROUP
        #     BY
        #     aml.account_id, aml.partner_id, aml.analytic_account_id, aml.date, aml.account_tax_id, aml.move_id
        #
        # UNION

        sql = ''' INSERT INTO fpa_auxiliar_taxes_line (bold,user_id,company_id,account_id,account,account_analytic_id,fecha,partner_id,
                    debit,credit,amount_final,base_amount,tax_amount,encabezado_id,financial_id, move_id, account_tax_id)
                        SELECT False,{user_id},{company_id},aml.account_id, aa.code, aml.analytic_account_id, aml.date, aml.partner_id, SUM(aml.debit) as debit, SUM(aml.credit) as credit, 
                                        SUM(debit-credit) as sf, SUM(COALESCE(aml.base_amount,0)) as base_amount, SUM(COALESCE(aml.tax_amount,0)) as tax_amount, 
                                         {header_id}, {financial_id}, aml.move_id, aml.account_tax_id
                                        FROM account_move_line aml
                                        INNER JOIN account_account aa ON aa.id = aml.account_id
                                        WHERE aml.date BETWEEN '{date_from}' AND '{date_to}'
                                        AND {where}
                                        GROUP BY aml.account_id, aml.partner_id, aml.analytic_account_id, aa.code, aml.date, aml.account_tax_id, aml.move_id
                        HAVING SUM(tax_amount)!=0 '''.format(date_from=self.date_from,
                                                             date_to=self.date_to,
                                                             user_id=self.env.user.id,
                                                             financial_id=financial_reports.id,
                                                             header_id=header_id,
                                                             where=where,
                                                             company_id=self.env.user.company_id.id
                                                             )
        _logger.info(sql)
        self.env.cr.execute(sql)
        return financial_reports.view_function(generate=False)
