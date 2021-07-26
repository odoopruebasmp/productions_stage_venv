# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from openerp import models, fields, api, _
from openerp.exceptions import Warning
import openerp.addons.decimal_precision as dp
import logging

_logger = logging.getLogger('ESTADO DE RESULTADOS (POR CC)')

class account_financial_reports_accounting_pyg_cc(models.Model):
    _name = "fpa.pyg.cc"

    date = fields.Datetime(string="Fecha")
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    estado = fields.Selection(
        [('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='todos', string='Estados')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',help='Select Charts of Accounts', required=True, domain=[('parent_id', '=', False)])

class account_financial_reports_accounting_pyg_cc_line(models.Model):
    _name = "fpa.pyg.cc.line"

    account_id = fields.Many2one(
        'account.account', string='Cuenta', ondelete='cascade')
    nivel = fields.Integer(string="Nivel")
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Cuenta analitica', ondelete='cascade')
    amount_inicial = fields.Float(
        string='Saldo Inicial', digits=dp.get_precision('Account'))
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_final = fields.Float(
        string='Saldo Final', digits=dp.get_precision('Account'))
    amount_1 = fields.Float(
        string='Saldo Año 1', digits=dp.get_precision('Account'))
    amount_2 = fields.Float(
        string='Saldo Año 2', digits=dp.get_precision('Account'))
    amount_3 = fields.Float(
        string='Saldo Año 3', digits=dp.get_precision('Account'))
    amount_4 = fields.Float(
        string='Saldo Año 4', digits=dp.get_precision('Account'))
    amount_5 = fields.Float(
        string='Saldo Año 5', digits=dp.get_precision('Account'))
    cuenta = fields.Char(string='Cuenta')
    cc1 = fields.Char(string='cc1')
    cc2 = fields.Char(string='cc2')
    cc3 = fields.Char(string='cc3')
    cc4 = fields.Char(string='cc4')
    cc5 = fields.Char(string='cc5')
    sequence = fields.Integer(string="Secuencia",required=False, help='Secuencia en la cual se muestran en la vista')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    resume = fields.Boolean(string="Resumen")
    bold = fields.Boolean(string="Bold", default=False)
    encabezado_id = fields.Many2one('fpa.pyg.cc', string='Encabezado', ondelete='cascade')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade')

class wizard_account_financial_reports_accounting_pyg_cc(models.TransientModel):
    _name = "fpa.pyg.cc.wizard"

    def _set_niveles(self):
        id = self.env.context.get('active_ids',False)
        return self.env['fpa.niveles'].search([('financial_reports','=',id),('code','in',('99','100'))])

    def _get_domain(self):
        id = self.env.context.get('active_ids',False)
        return [('financial_reports','=',id)]

    account_filter = fields.Boolean(string="Filtro adicional de cuentas")
    partner_filter = fields.Boolean(string="Filtro adicional de terceros")
    journal_filter = fields.Boolean(string="Filtro adicional de diarios")
    analytic_filter = fields.Boolean(string="Filtro adicional de cuenta analitica")
    cierre = fields.Boolean(string="Cierre")
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',
                                       help='Select Charts of Accounts', required=True, domain=[('parent_id', '=', False)])
    company_id = fields.Many2one(
        'res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    period_balance_ids = fields.Many2many('account.period', string='Periodos')
    journal_ids = fields.Many2many('account.journal', string='Diarios')
    partner_ids = fields.Many2many('res.partner', string='Terceros')
    account_ids = fields.Many2many(
        'account.account', string='Cuentas', domain=[('type', '!=', 'view')])
    analytic_ids = fields.Many2many(
        'account.analytic.account', string='Cuentas analiticas', domain=[('type', '!=', 'view')])
    date_from = fields.Date(string="Fecha Inicial", required=True)
    date_to = fields.Date(string="Fecha Final", required=True)
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), (
        'todos', 'Todos')], default='todos', string='Estados', required=True)
    niveles = fields.Many2many('fpa.niveles', string='Niveles', help='Seleccione los niveles para la consulta.', default=_set_niveles, domain=_get_domain, required=True)

    @api.one
    @api.onchange('chart_account_id')
    def get_filter(self):
        id = self.env.context.get('active_ids',False)
        financial_reports = self.env['fpa.financial.reports'].browse(id)
        self.account_filter = financial_reports.account_filter
        self.partner_filter = financial_reports.partner_filter
        self.journal_filter = financial_reports.journal_filter
        self.analytic_filter = financial_reports.analytic_filter

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
        self.env.cr.execute(''' select count(*) from fpa_pyg_cc_line ''')
        count = self.env.cr.fetchone()[0]
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])
        #truncate a la tabla cuando sean mas de 1millón de registros, para que no tarde tanto eliminando las lineas
        if count > 1000000:
            self.env.cr.execute(''' TRUNCATE fpa_pyg_cc_line ''')
            self.env.cr.execute(''' TRUNCATE fpa_pyg_cc ''')
        else:
            self.env.cr.execute(''' DELETE FROM fpa_pyg_cc_line WHERE financial_id=%s AND company_id = %s and user_id = %s''' % (financial_reports.id, self.company_id.id, self.env.user.id))
            self.env.cr.execute(''' DELETE FROM fpa_pyg_cc WHERE financial_id=%s AND company_id = %s and user_id = %s''' % (financial_reports.id, self.company_id.id, self.env.user.id))
        where = ''
        cuenta = []
        #Cuentas
        if financial_reports:
            if financial_reports.concepts_ids:
                for conceptos in financial_reports.concepts_ids:
                    for cuentas in conceptos.account_ids:
                        cuenta.append(cuentas.id)
        if len(cuenta) > 0:
            where += 'AND ( aml.account_id IN ' + str(tuple(cuenta)) + ' )'

        # Agrega encabezado con parametros indicados por el usuario
        sql = " INSERT INTO fpa_pyg_cc(date, date_from, date_to, estado, company_id, user_id,chart_account_id, financial_id) VALUES ('%s','%s','%s','%s',%s,%s,%s,%s) RETURNING ID " %(datetime.now(), self.date_from, self.date_to, self.estado, self.company_id.id, self.env.user.id, self.chart_account_id.id,financial_reports.id)
        self.env.cr.execute(sql)
        encabezado_id = False
        try:
            encabezado_id = self.env.cr.fetchone()[0]
        except ValueError:
            pass

        if self.journal_ids:
            where += ''' AND aml.journal_id in (%s) ''' % (
                ','.join(str(x.id) for x in self.journal_ids))
        if self.account_ids:
            if self.chart_account_id.niif:
                where += ''' AND aml.account_niif_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
            else:
                where += ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
        if self.partner_ids:
            where += ''' AND aml.partner_id in (%s) ''' % (
                ','.join(str(x.id) for x in self.partner_ids))
        cuenta_analitica = ' aml.analytic_account_id '
        cuenta_analitica1 = ' analytic_account_id, '           
        if self.analytic_ids:
            where += ''' AND aml.analytic_account_id in (%s) ''' % (','.join(str(x.id) for x in self.analytic_ids))
            
        if self.estado:
            estado = ''
        if self.estado == 'borrador':
            htoestado = 'draft'
        elif self.estado == 'validados':
            estado = 'valid'
        else:
            estado = '%'
        where += ''' AND aml.state like '%s' ''' % estado

        #verificar si tiene el modulo de niif_account instalado
        module = self.env['ir.module.module'].search([('name','=','niif_account'),('state','=','installed')])
        #agregar condición de cuentas indicadas en el wizard
        condition = 'aa.id = movimientos.account_id'
        account = 'aml.account_id'
        where_add = ''
        if self.account_ids:
            where_add = ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))            
            if module:
                if self.chart_account_id.niif:
                    where_add = ''' AND aml.account_niif_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
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

        mov_cierre = ' '
        if self.cierre is True:
            mov_cierre = " UNION SELECT %s, %s::integer, sum(aml.debit) as debit, sum(aml.credit) as credit "\
                            " FROM account_move_line aml "\
                            " INNER JOIN account_period ap on ap.id = aml.period_id "\
                            " WHERE  aml.company_id = %s AND (aml.date BETWEEN '%s' AND '%s') and ap.special IS TRUE "\
                            " %s "\
                            " GROUP BY analytic_account_id, %s "%(account, cuenta_analitica, self.env.user.company_id.id, self.date_from, self.date_to, where, account)
        #Movimientos
        movimientos = " INSERT INTO fpa_pyg_cc_line (nivel,sequence,bold,user_id,company_id,account_id, cuenta, analytic_account_id, cc1, cc2, cc3, cc4, cc5, concepts_id,  debit, credit, amount_final,encabezado_id,resume,financial_id) "\
                            " SELECT 99,ffrc.sequence, False, %s, %s, account_id, aa.code, analytic_account_id, aaa.cc1, aaa.cc2, aaa.cc3, aaa.cc4, aaa.cc5, ffrc.id as concepts_id, sum(debit) AS debit, sum(credit) AS credit, "\
                            " sum(debit-credit) as amount_final, %s::integer as encabezado_id, False, %s "\
                            " FROM ( "\
                                " SELECT %s as account_id, %s::integer as analytic_account_id, sum(aml.debit) as debit, sum(aml.credit) as credit "\
                                    " FROM account_move_line aml "\
                                        " INNER JOIN account_period ap on ap.id = aml.period_id "\
                                            " WHERE aml.company_id = %s "\
                                            " AND aml.date BETWEEN '%s' and '%s' "\
                                            " %s "\
                                            " GROUP BY analytic_account_id, %s "\
                                " %s "\
                            " ) AS movimientos "\
                            " INNER JOIN account_account aa ON %s AND aa.company_id = %s AND aa.parent_zero = %s "\
                            " %s JOIN fpa_financial_reports_concepts_account ffrca ON ffrca.account_account_id = aa.id "\
                            " %s JOIN fpa_financial_reports_concepts ffrc on ffrc.id = ffrca.fpa_financial_reports_concepts_id "\
                            " LEFT JOIN account_analytic_account aaa ON aaa.id = movimientos.analytic_account_id "\
                            " INNER JOIN account_account_type aat ON aa.user_type = aat.id "\
                            " AND ffrc.financial_reports = %s "\
                            " GROUP BY ffrc.sequence, account_id, analytic_account_id, cc1, cc2, cc3, cc4, cc5, aa.code, ffrc.id " % (self.env.user.id, self.company_id.id, encabezado_id, financial_reports.id, 
                                account, cuenta_analitica, self.env.user.company_id.id, self.date_from, self.date_to, where, account, 
                                mov_cierre, condition, self.env.user.company_id.id, self.chart_account_id.id, relation, relation, financial_reports.id)
        # print movimientos
        self.env.cr.execute(movimientos)
        if '100' in niveles:
            #Agregar totales por concepto
            sql = "INSERT INTO fpa_pyg_cc_line (nivel,bold,user_id,company_id,account_id, cuenta, debit, "\
                " credit, amount_final,encabezado_id,resume, concepts_id, financial_id) "\
                " SELECT 100,True, %s, %s, null, null, SUM(debit),SUM(credit), SUM(amount_final), %s, False, ffrc.id, %s "\
                " FROM fpa_financial_reports_concepts ffrc "\
                " LEFT JOIN fpa_pyg_cc_line fpl ON ffrc.id = fpl.concepts_id "\
                " WHERE fpl.nivel=99 and ffrc.financial_reports = %s AND fpl.user_id=%s AND fpl.company_id=%s" \
                " GROUP BY ffrc.id "% (self.env.user.id, self.company_id.id, encabezado_id, financial_reports.id, financial_reports.id,self.env.user.id,self.env.user.company_id.id)
            self.env.cr.execute(sql)

        if '99' not in niveles:
            self.env.cr.execute(" DELETE FROM fpa_pyg_cc_line WHERE nivel=99 AND user_id=%s AND financial_id =%s AND company_id=%s"%(self.env.user.id,financial_reports.id,self.env.user.company_id.id))

        #Eliminar lineas sin saldo inicial, débitos y créditos
        self.env.cr.execute(" DELETE FROM fpa_pyg_cc_line WHERE amount_final=0 AND debit=0 AND credit=0 AND amount_final=0 AND user_id=%s AND financial_id =%s AND company_id=%s"%(self.env.user.id,financial_reports.id,self.env.user.company_id.id))
       
        #cambia el signo
        if financial_reports.sign:
            sql = " UPDATE fpa_pyg_cc_line SET amount_final = amount_final * -1 WHERE user_id=%s AND financial_id =%s AND company_id=%s"%(self.env.user.id,financial_reports.id,self.env.user.company_id.id)
            self.env.cr.execute(sql)

        if financial_reports.unidades > 1:
            self.env.cr.execute(
                ''' UPDATE fpa_pyg_cc_line SET amount_inicial=amount_inicial/{unidades}, debit=debit/{unidades}, 
                    credit=credit/{unidades},amount_final=amount_final/{unidades},
                    amount_1=amount_1/{unidades},amount_2=amount_2/{unidades},amount_3=amount_3/{unidades},
                    amount_4=amount_4/{unidades},amount_5=amount_5/{unidades}
                    WHERE company_id={company_id} AND user_id={user_id} AND financial_id = {financial_id} '''.format(
                    unidades=financial_reports.unidades, financial_id=financial_reports.id, user_id=self.env.user.id,
                    company_id=self.env.user.company_id.id))

        return financial_reports.view_function(generate=False)
