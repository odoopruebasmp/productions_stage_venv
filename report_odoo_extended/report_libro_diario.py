# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
from openerp import addons
from openerp import SUPERUSER_ID
import itertools
from dateutil.relativedelta import relativedelta
from lxml import etree
from openerp import models, fields, api, _
from openerp.osv import osv, fields as fields2
from openerp.exceptions import except_orm, Warning, RedirectWarning
import openerp.addons.decimal_precision as dp
import math

class account_report_diario_avancys_line_encabezado(models.Model):
    _name = "account.report.diario.avancys.line.sql.encabezado"
    
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='todos', string='Estados')
    company_id = fields.Many2one('res.company', string='Company')
    resumen_ids = fields.One2many('account.report.diario.avancys.resumen.sql', 'encabezado_id', string='Lineas Resumen')
  
class account_report_diario_avancys_resumen(models.Model):
    _name = "account.report.diario.avancys.resumen.sql"
    _order = "journal_name"
    
    journal_name = fields.Char(string='Diario')
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    encabezado_id = fields.Many2one('account.report.diario.avancys.line.sql.encabezado', string='Encabezado')
  
class account_report_diario_avancys_line(models.Model):
    _name = "account.report.diario.avancys.line.sql"
    _order = "code, journal_id desc"
    
    name = fields.Char(string='Nombre Cuenta')
    code = fields.Char(string='Codigo')
    subcuenta = fields.Char(string='Subcuenta')
    cuenta = fields.Char(string='cuenta')
    grupo = fields.Char(string='Grupo')
    clase = fields.Char(string='Clase')
    journal_name = fields.Char(string='Diario')
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    journal_id = fields.Integer(string='Journal ID')
    account_id_int = fields.Integer(string='Cuenta ID')
    nivel = fields.Integer(string='Clase')
    date = fields.Date('Fecha')
    encabezado_id = fields.Many2one('account.report.diario.avancys.line.sql.encabezado', string='Encabezado')

class account_report_diario_avancys_report_wizard(models.TransientModel):
    _name = "wizard.report.diario.avancys.sql.report"
    
    nivel = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('todos', 'Todos')], string='Nivel', required=True, default='todos')
    
    @api.multi
    def imprimir_calc(self): 
        if self.nivel != 'todos':
            self._cr.execute('''SELECT id FROM account_report_diario_avancys_line_sql WHERE nivel = %s or nivel = 10 order by code, journal_id desc''',(int(self.nivel),))
        else:
            self._cr.execute('''SELECT id FROM account_report_diario_avancys_line_sql order by code, journal_id desc''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.diario.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.reporte_diario_aeroo',
        'report_type': 'aeroo',
        'datas': datas,
        }

    @api.multi
    def imprimir_ld_pdf(self):
        if self.nivel != 'todos':
            self._cr.execute('''SELECT id FROM account_report_diario_avancys_line_sql WHERE nivel = %s or nivel = 10 order by code, journal_id desc''',(int(self.nivel),))
        else:
            self._cr.execute('''SELECT id FROM account_report_diario_avancys_line_sql order by code, journal_id desc''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.diario.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.template_reporte_diario',
        'datas': datas,
        }
        
class account_report_diario_avancys(models.TransientModel):
    _name = "account.report.diario.avancys.sql"
    
    @api.one
    @api.constrains('date_from', 'date_to')
    def _validar_fechas(self):           
        if self.date_from > self.date_to:
                raise Warning(_('Error en las fechas!'),_("Las fechas planificadas estan mal configuradas"))  
    
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts', required=True, domain = [('parent_id','=',False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    period_diario_ids = fields.Many2many('account.period', string='Periodos')
    journal_ids = fields.Many2many('account.journal', string='diarios')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain = [('type','!=','view')])
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='todos', string='Estados', required=True)
    
    @api.multi
    def calcular(self):        
        encabezado_obj = self.env['account.report.diario.avancys.line.sql.encabezado']
        report_line_obj = self.env['account.report.diario.avancys.line.sql']
        report_resumen_obj = self.env['account.report.diario.avancys.resumen.sql']
        account_obj = self.env['account.account']
        journal_obj = self.env['account.journal']
        account_analytic_obj = self.env['account.analytic.account']
        total_credit=0
        total_debit=0
        dict={}
        account_ids=[]
        company_id = self.company_id.id
        cr = self._cr
        cr.execute(''' DELETE FROM account_report_diario_avancys_line_sql''')
        cr.execute(''' DELETE FROM account_report_diario_avancys_line_sql_encabezado''')
        cr.execute(''' DELETE FROM account_report_diario_avancys_resumen_sql''')
        
        encabezado = encabezado_obj.create({'date_from':self.date_from,'date_to':self.date_to,'estado':self.estado,'company_id':company_id})
        encabezado_id = encabezado.id
        
        if self.date_from and  self.date_to:
            date_from = self.date_from
            date_to = self.date_to
        
        print "----------Generando Debitos Creditos Con Diario----------"
        inicio = datetime.now()
        
        select_from = '''SELECT account_account.id AS account_id, 
                         account_journal.id AS journal_id, 
                         SUM(account_move_line.credit) AS la_somme_credit, 
                         SUM(account_move_line.debit) AS la_somme_debit, 
                         LEFT(account_account.code,6) AS subcuenta, 
                         LEFT(account_account.code,4) AS cuenta, 
                         LEFT(account_account.code,2) AS grupo, 
                         LEFT(account_account.code,1) AS clase, 
                         account_account.code AS code, 
                         account_account.name AS name, 
                         account_journal.name AS journal_name, 
                         account_journal.code AS journal_code  
                        FROM 
                         (
                          account_account
                          INNER JOIN
                          account_move_line
                          ON account_account.id = account_move_line.account_id 
                         RIGHT OUTER JOIN
                         account_journal
                         ON account_move_line.journal_id = account_journal.id )'''
        where = ''' WHERE
	  	     (account_account.parent_zero in(%s) OR (account_account.id = %s))
                     AND account_move_line.date >= %s
                     AND account_move_line.date <= %s
                     AND account_move_line.company_id = %s
                        '''
        group_by = ''' GROUP BY 
                        account_account.id,
                        account_journal.id'''
        
        if self.estado == 'borrador':
            where +=''' AND state != 'valid' '''
        elif self.estado == 'validados':
            where +=''' AND state = 'valid' '''
        tuples = []
        if self.journal_ids:
            where += ''' AND account_move_line.journal_id in %s '''
            tuples.append(tuple([x.id for x in self.journal_ids]))
        if self.account_ids:
            where += ''' AND account_move_line.account_id in %s '''
            tuples.append(tuple([x.id for x in self.account_ids]))
        
        query = select_from+where+group_by
        if tuples:
            tuples = (self.chart_account_id.id,self.chart_account_id.id,date_from,date_to,company_id)+tuple(tuples)
            cr.execute(query,tuples)
        else:
            cr.execute(query,(self.chart_account_id.id,self.chart_account_id.id,date_from,date_to,company_id))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
            
        print "----------Creando Tabla----------"
        inicio = datetime.now()
        result = self._cr.fetchall()
        for res in result:
            account_id = res[0]
            journal_id = res[1]
            credit = float(res[2])
            debit = float(res[3])
            subcuenta = res[4]
            cuenta = res[5]
            grupo = res[6]
            clase = res[7]
            code = res[8]
            name = res[9]
            journal_name = res[10] or 'Indefinido'
            journal_code = res[11] or 'Indefinido'
            journal_name = "["+journal_code+"] "+journal_name
            if account_id not in account_ids:
                account_ids.append(account_id)
            total_credit+=credit
            total_debit+=debit
                
            cr.execute('''insert into account_report_diario_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,journal_id,debit,credit,journal_name,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,subcuenta,journal_id,debit,credit,journal_name,account_id,encabezado_id,10))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Clase----------"
        inicio = datetime.now()
        cr.execute('''SELECT
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit,  
                         clase
                        FROM 
                         account_report_diario_avancys_line_sql 
                        WHERE
                         nivel=10
                        GROUP BY 
                         clase
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            code = res[2]
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR (account_account.id = %s)) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_diario_avancys_line_sql (name,code,debit,credit,account_id_int,encabezado_id,nivel) values (%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,debit,credit,account_id,encabezado_id,1))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Grupo----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         grupo
                        FROM 
                         account_report_diario_avancys_line_sql
                        WHERE
                         nivel=10
                        GROUP BY 
                         grupo 
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            grupo = res[2]
            clase = grupo[0]
            code = grupo
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR (account_account.id = %s)) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_diario_avancys_line_sql (name,code,clase,debit,credit,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,debit,credit,account_id,encabezado_id,2))

        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Cuenta----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         cuenta
                        FROM 
                         account_report_diario_avancys_line_sql
                        WHERE
                         nivel=10
                        GROUP BY 
                         cuenta 
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            cuenta = res[2]
            grupo = cuenta[0:2]
            clase = grupo[0]
            code = cuenta
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR (account_account.id = %s)) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_diario_avancys_line_sql (name,code,clase,grupo,debit,credit,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,debit,credit,account_id,encabezado_id,3))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        account_ids_repetidas = []
        print "----------Calculando Subcuenta----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit,  
                         subcuenta
                        FROM 
                         account_report_diario_avancys_line_sql 
                        WHERE
                         nivel=10
                        GROUP BY 
                         subcuenta 
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            subcuenta = res[2]
            cuenta = subcuenta[0:4]
            grupo = cuenta[0:2]
            clase = grupo[0]
            code = subcuenta
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR (account_account.id = %s)) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            if account_id not in account_ids_repetidas:
                account_ids_repetidas.append(account_id)
            cr.execute('''insert into account_report_diario_avancys_line_sql (name,code,clase,grupo,cuenta,debit,credit,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,debit,credit,account_id,encabezado_id,4))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Regular----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit,
                         code 
                        FROM 
                         account_report_diario_avancys_line_sql 
                        WHERE 
                         nivel=10 
                         AND account_id_int not in %s
                        GROUP BY 
                         code 
                         ''',(tuple(account_ids_repetidas),))
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            code = res[2]
            subcuenta = code[0:6]
            cuenta = subcuenta[0:4]
            grupo = cuenta[0:2]
            clase = grupo[0]
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR (account_account.id = %s)) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_diario_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,debit,credit,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,subcuenta,debit,credit,account_id,encabezado_id,5))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Resumen Diario----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit,
                         journal_name
                        FROM 
                         account_report_diario_avancys_line_sql 
                        WHERE 
                         nivel=10 
                         AND account_id_int not in %s
                        GROUP BY 
                         journal_name 
                         ''',(tuple(account_ids_repetidas),))
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            journal_name = res[2]
            cr.execute('''insert into account_report_diario_avancys_resumen_sql(journal_name,debit,credit,encabezado_id) values 
                (%s,%s,%s,%s) ''' ,
                (journal_name,debit,credit,encabezado_id))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        return {
            'domain': [],
            'context': {},
            'name': 'Informe de diario de diario',
            'view_type': 'form',
            'view_mode': 'tree,graph',
            'view_id': False,
            'res_model': 'account.report.diario.avancys.line.sql',
            'type': 'ir.actions.act_window'
        }
#
