# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp import models, fields, api, _
from openerp.exceptions import Warning, RedirectWarning
import openerp.addons.decimal_precision as dp
import logging

_logger = logging.getLogger('LIBRO DIARIO')

class account_financial_reports_accounting_diario(models.Model):
    _name = "fpa.diario"

    date = fields.Datetime(string="Fecha")
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='validados', string='Estados')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', required=True, domain=[('parent_id', '=', False)])


class account_financial_reports_accounting_diario_line(models.Model):
    _name = "fpa.diario.line"

    account_id = fields.Many2one('account.account', string='Cuenta', ondelete='cascade', index=True)
    journal_id = fields.Many2one('account.journal', string='Diario', ondelete='cascade', index=True)
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    resume = fields.Boolean(string="Resumen")
    nivel = fields.Integer(string="Nivel")
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte', index=True)
    bold = fields.Boolean(string="Bold", default=False)
    sequence = fields.Integer(string="Secuencia",required=False, help='Secuencia en la cual se muestran en la vista')
    fecha = fields.Date(string='Fecha')
    cuenta = fields.Char(string='Cuenta')
    asiento = fields.Char(string='Asiento')
    encabezado_id = fields.Many2one('fpa.diario', string='Encabezado', ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Compañia', index=True)
    user_id = fields.Many2one('res.users', string='Usuario', index=True)

class wizard_account_financial_reports_accounting_diario(models.TransientModel):
    _name = "fpa.diario.wizard"

    def _set_niveles(self):
        id = self.env.context.get('active_ids',False)
        financial_reports = self.env['fpa.financial.reports'].browse(id)
        return self.env['fpa.niveles'].search([('financial_reports','=',financial_reports.id),('code','in',('-1','3','103'))],order='code asc')

    def _get_domain(self):
        id = self.env.context.get('active_ids',False)
        return [('financial_reports','=',id)]

    account_filter = fields.Boolean(string="Filtro adicional de cuentas")
    journal_filter = fields.Boolean(string="Filtro adicional de diarios")
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',help='Plan de cuentas asociado a las cuentas contables que se desean consultar.', required=True, domain=[('parent_id', '=', False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True, help='Compañia asociada a los movimientos contables a consultar.')
    period_balance_ids = fields.Many2many('account.period', string='Periodos', help='Período asociado a los movimientos contables a consultar.')
    journal_ids = fields.Many2many('account.journal', string='Diarios', help='Diario asociado a los movimientos contables a consultar.')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type', '!=', 'view')], help='Cuentas contables asociadas a los movimientos a consultar.')
    analytic_ids = fields.Many2many('account.analytic.account', string='Cuentas analiticas', domain=[('type', '!=', 'view')])
    date_from = fields.Date(string="Fecha Inicial", required=True, help='Fecha inicial de consulta, el informe retornará los movimientos contables desde esta fecha.')
    date_to = fields.Date(string="Fecha Final", required=True, help='Fecha final de consulta, el informe retornará los movimientos contables hasta esta fecha.')
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='todos', string='Estados', required=True, help='Estado en el cual se desean consultar los movimientos contables.')
    user_id = fields.Many2one('res.users', string='Usuario', help='Usuario que ejecuta la consulta.')
    niveles = fields.Many2many('fpa.niveles', string='Niveles', help='Seleccione los niveles para la consulta.', default=_set_niveles, required=True, domain=_get_domain)
    sp_periods = fields.Boolean('Apertura/Cierre', help='Marque este check si quiere tener en cuenta los '
                                    'movimientos pertenecientes a periodos de Apertura/Cierre', default=True)

    @api.one
    @api.onchange('chart_account_id')
    def get_filter(self):
        id = self.env.context.get('active_ids',False)
        financial_reports = self.env['fpa.financial.reports'].browse(id)
        self.account_filter = financial_reports.account_filter
        self.journal_filter = financial_reports.journal_filter

    @api.one
    @api.constrains('date_from', 'date_to')
    def _validar_fechas(self):
        if self.date_from > self.date_to:
            raise Warning(_('Error en las fechas!'), _("Las fechas planificadas estan mal configuradas"))

    @api.multi
    def generar(self):
        st = datetime.now()

        self.env.cr.execute(''' select count(*) from fpa_diario_line ''')
        count = self.env.cr.fetchone()[0]
        
        #recorre conceptos configurados en el informe
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])
        te = datetime.now()
        #truncate a la tabla cuando sean mas de 1millón de registros, para que no tarde tanto eliminando las lineas antes de crear las nuevas
        if count >1000000:
            self.env.cr.execute(''' TRUNCATE fpa_diario_line ''')
        else:
            self.env.cr.execute(''' DELETE FROM fpa_diario_line WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (financial_reports.id, self.env.user.company_id.id, self.env.user.id))
        self.env.cr.execute(''' DELETE FROM fpa_diario WHERE financial_id =%s AND company_id = %s and user_id = %s''' % (financial_reports.id, self.env.user.company_id.id, self.env.user.id))
        _logger.info('culminó de eliminar movimientos anteriores. Tiempo: %s'%(datetime.now()-te))
        where = ''

        # Agrega encabezado con parametros indicados por el usuario
        self.env.cr.execute(''' INSERT INTO fpa_diario(date, date_from, date_to, estado, company_id, user_id,chart_account_id,financial_id) VALUES ('%s','%s','%s','%s',%s,%s,%s,%s) RETURNING ID ''' % (
            datetime.now(), self.date_from, self.date_to, self.estado, self.env.user.company_id.id, self.env.user.id, self.chart_account_id.id,financial_reports.id))
        try:
            encabezado_id = self.env.cr.fetchone()[0]
        except ValueError:
            encabezado_id = False

        #Filtros adicionales
        if self.journal_ids:
            where += ''' AND aml.journal_id in (%s) ''' % (
                ','.join(str(x.id) for x in self.journal_ids))
        where_account = ''
        if self.account_ids:
            if self.chart_account_id.niif:
                where_account = ''' AND aml.account_niif_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
            else:
                where_account = ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))

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
        condition = 'AND aa.id = account_id'
        #verificar si tiene el modulo de niif_account instalado
        module = self.env['ir.module.module'].search([('name','=','niif_account'),('state','=','installed')])
        if module:
            if self.chart_account_id.niif:            
                account = 'aml.account_niif_id'
                condition = 'AND aa.id = aml.account_niif_id'

        te = datetime.now()
        #INGRESAR MOVIMIENTOS
        movimientos = ''' INSERT INTO fpa_diario_line (bold,user_id,company_id,journal_id,account_id,fecha,debit,credit,encabezado_id,financial_id,nivel,cuenta)
                                SELECT False, %s, %s, aml.journal_id, %s::integer as account_id, aml.date,SUM(aml.debit) as debit, 
                                    SUM(aml.credit) as credit, %s, %s, 99, aa.code
                                    FROM account_move_line aml
                                        INNER JOIN account_account aa ON aa.parent_zero = %s %s
                                        INNER JOIN account_period ap on ap.id = aml.period_id
                                        WHERE aml.company_id = %s 
                                             AND aml.date BETWEEN '%s' and '%s'
                                         %s %s GROUP BY %s, aml.journal_id, aml.date, aa.code                                  
                                    ''' % ( self.env.user.id, self.env.user.company_id.id, account, encabezado_id, financial_reports.id,
                                            self.chart_account_id.id, condition, self.env.user.company_id.id, self.date_from, self.date_to, 
                                            where_account, where, account)
        _logger.info(movimientos)
        self.env.cr.execute(movimientos)
        _logger.info('culminó de agregar movimientos. Tiempo: %s'%(datetime.now()-te))
        
        niveles = [x.code for x in self.niveles]
        _logger.info('NIVELES:'+str(niveles))

        if '-1' in niveles:
            te = datetime.now()
            #INGRESAR TOTAL POR DIA
            totales = ''' INSERT INTO fpa_diario_line (bold,user_id,company_id,fecha,debit,credit,encabezado_id,financial_id,nivel)
                                    SELECT True, %s, %s, fdl.fecha, SUM(fdl.debit) as debit, 
                                        SUM(fdl.credit) as credit, %s, %s, -1
                                         FROM fpa_diario_line fdl
                                                 WHERE fecha is not null AND fdl.user_id =%s AND fdl.company_id = %s AND fdl.nivel = 99
                                             GROUP BY fecha
                                        ''' % ( self.env.user.id, self.env.user.company_id.id, encabezado_id, financial_reports.id, 
                                            self.env.user.id, self.env.user.company_id.id)
            _logger.debug(totales)
            self.env.cr.execute(totales)
            _logger.info('culminó de agregar totales por dia. Tiempo: %s'%(datetime.now()-te))

        if '-2' in niveles:
            te = datetime.now()
            #INGRESAR TOTAL POR CUENTA Y DIA A NIVEL DE REGULAR
            totales = ''' INSERT INTO fpa_diario_line (bold,user_id,company_id,account_id,fecha,debit,credit,encabezado_id,financial_id,nivel,cuenta)
                                    SELECT True, %s, %s, account_id, fdl.fecha, SUM(fdl.debit) as debit, 
                                        SUM(fdl.credit) as credit, %s, %s, -2, aa.code
                                         FROM fpa_diario_line fdl
                                             INNER JOIN account_account aa ON aa.id = fdl.account_id AND aa.parent_zero = %s
                                                 WHERE fecha is not null AND fdl.user_id =%s AND fdl.company_id = %s AND fdl.nivel = 99
                                             GROUP BY account_id, fecha, aa.code 
                                        ''' % ( self.env.user.id, self.env.user.company_id.id, encabezado_id, financial_reports.id, self.chart_account_id.id, self.env.user.id, self.env.user.company_id.id)
            _logger.debug(totales)
            self.env.cr.execute(totales)
            _logger.info('culminó de agregar totales por cuenta. Tiempo: %s'%(datetime.now()-te))
        
        #INGRESAR TOTAL POR CUENTA Y DIA
        # if '-3' in niveles:
        #     te = datetime.now()
        #     totales = ''' INSERT INTO fpa_diario_line (bold,user_id,company_id,account_id,fecha,debit,credit,encabezado_id,financial_id,nivel)
        #                             SELECT True, %s, %s, fdl.account_id, fdl.fecha, SUM(fdl.debit) as debit, 
        #                                 SUM(fdl.credit) as credit, %s, %s, -3
        #                                  FROM fpa_diario_line fdl
        #                                     WHERE fecha is not null AND fdl.user_id =%s AND fdl.company_id = %s AND fdl.nivel = 99
        #                                  GROUP BY fdl.fecha, fdl.account_id
        #                                 ''' % ( self.env.user.id, self.env.user.company_id.id, encabezado_id, financial_reports.id, self.env.user.id, self.env.user.company_id.id)
        #     _logger.debug(totales)
        #     self.env.cr.execute(totales)
        #     _logger.info('culminó de agregar totales por cuenta y dia. Tiempo: %s'%(datetime.now()-te))

        #INGRESAR TOTAL POR diario Y DIA
        if '-3' in niveles:
            te = datetime.now()
            totales = ''' INSERT INTO fpa_diario_line (bold,user_id,company_id,journal_id,fecha,debit,credit,encabezado_id,financial_id,nivel)
                                    SELECT True, %s, %s, fdl.journal_id, fdl.fecha, SUM(fdl.debit) as debit, 
                                        SUM(fdl.credit) as credit, %s, %s, -3
                                         FROM fpa_diario_line fdl
                                            WHERE fecha is not null AND fdl.user_id =%s AND fdl.company_id = %s AND fdl.nivel = 99
                                         GROUP BY fdl.fecha, fdl.journal_id
                                        ''' % ( self.env.user.id, self.env.user.company_id.id, encabezado_id, financial_reports.id, self.env.user.id, self.env.user.company_id.id)
            _logger.debug(totales)
            self.env.cr.execute(totales)
            _logger.info('culminó de agregar totales por diario y dia. Tiempo: %s'%(datetime.now()-te))        

        te = datetime.now()
        for structure in self.chart_account_id.structure_id.sorted(key=lambda r: r.sequence, reverse=True):
            if str(structure.sequence) in niveles:
                # nivel
                nivel = '''INSERT INTO fpa_diario_line(bold, user_id,company_id, account_id, cuenta, fecha, debit, credit, encabezado_id,nivel,financial_id)
                            SELECT True, %s,%s, aar.id, aar.code, al.fecha, sum(al.debit) as debit, sum(al.credit) as credit, %s, %s, %s
                                FROM fpa_diario_line al
                                    INNER JOIN  account_account aar on aar.code = substring(al.cuenta from 1 for %s) AND aar.parent_zero = %s
                                        and aar.type = 'view' and aar.company_id = al.company_id
                                    WHERE al.nivel=99 and al.user_id =%s and al.company_id = %s
                                    GROUP BY aar.id, al.fecha, aar.code ''' % (self.env.user.id, self.env.user.company_id.id, encabezado_id, structure.sequence, financial_reports.id,
                                        structure.digits, self.chart_account_id.id, self.env.user.id, self.env.user.company_id.id)
                self.env.cr.execute(nivel)

            niv = str('10')+str(structure.sequence)
            _logger.info('NIVELES niv:'+str(niv))
            if niv in niveles:
                te = datetime.now()
                #INGRESAR TOTAL POR CUENTA, DIARIO Y DIA A NIVELES
                totales = ''' INSERT INTO fpa_diario_line (bold,user_id,company_id,account_id,cuenta,journal_id,fecha,debit,credit,encabezado_id,financial_id,nivel)
                                        SELECT True, %s, %s, aa.id,aa.code, fdl.journal_id, fdl.fecha, SUM(fdl.debit) as debit, 
                                            SUM(fdl.credit) as credit, %s, %s, %s
                                             FROM fpa_diario_line fdl
                                                INNER JOIN account_account aa ON aa.code = substring(fdl.cuenta from 1 for %s) AND aa.parent_zero = %s
                                                        and aa.type = 'view' and aa.company_id = fdl.company_id
                                                    WHERE fdl.user_id =%s AND fdl.company_id = %s AND fdl.nivel = 99
                                                 GROUP BY aa.id,aa.code,journal_id,fecha ''' % ( self.env.user.id, self.env.user.company_id.id, encabezado_id, financial_reports.id, niv,
                                                structure.digits,self.chart_account_id.id, self.env.user.id, self.env.user.company_id.id)
                _logger.debug(totales)
                self.env.cr.execute(totales)
                _logger.info('culminó de agregar totales por cuenta, diario y dia para nivel %s. Tiempo: %s'%(structure.sequence,datetime.now()-te))

            #if str(structure.sequence) not in niveles:
            #    self.env.cr.execute(''' DELETE FROM fpa_diario_line WHERE nivel = %s '''%str(structure.sequence))

        _logger.info('culminó de agregar las estructuras. Tiempo: %s'%(datetime.now()-te))
        
        if '99' not in niveles:
            self.env.cr.execute(''' DELETE FROM fpa_diario_line WHERE nivel = 99 ''')
        
        #eliminar lineas sin saldo inicial, debito y credito
        self.env.cr.execute(''' DELETE FROM fpa_diario_line WHERE debit=0 and credit=0 ''')
        _logger.info('Tiempo: %s'%(datetime.now()-st))

        if financial_reports.unidades > 1:
            self.env.cr.execute(
                ''' UPDATE fpa_diario_line SET debit=debit/{unidades}, 
                    credit=credit/{unidades} 
                    WHERE company_id={company_id} AND user_id={user_id} AND financial_id = {financial_id} '''.format(
                    unidades=financial_reports.unidades, financial_id=financial_reports.id, user_id=self.env.user.id,
                    company_id=self.env.user.company_id.id))
        return financial_reports.view_function(generate=False)


