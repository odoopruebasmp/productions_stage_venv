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

class account_report_mayor_avancys_line_encabezado(models.Model):
    _name = "account.report.mayor.avancys.line.sql.encabezado"
    
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='todos', string='Estados')
    company_id = fields.Many2one('res.company', string='Company')
    debit_total = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit_total = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_inicial_debito_total = fields.Float(string='Saldo Inicial Debito', digits=dp.get_precision('Account'))
    amount_inicial_credito_total = fields.Float(string='Saldo Inicial Credito', digits=dp.get_precision('Account'))
    amount_final_debito_total = fields.Float(string='Saldo Final Debito', digits=dp.get_precision('Account'))
    amount_final_credito_total = fields.Float(string='Saldo Final Credito', digits=dp.get_precision('Account'))
    
class account_report_mayor_avancys_line(models.Model):
    _name = "account.report.mayor.avancys.line.sql"
    _order = "code, partner_id desc"
    
    name = fields.Char(string='Nombre Cuenta')
    code = fields.Char(string='Codigo')
    subcuenta = fields.Char(string='Subcuenta')
    cuenta = fields.Char(string='cuenta')
    grupo = fields.Char(string='Grupo')
    clase = fields.Char(string='Clase')
    partner_name = fields.Char(string='Tercero')
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_inicial_debito = fields.Float(string='Saldo Inicial Debito', digits=dp.get_precision('Account'))
    amount_inicial_credito = fields.Float(string='Saldo Inicial Credito', digits=dp.get_precision('Account'))
    amount_final_debito = fields.Float(string='Saldo Final Debito', digits=dp.get_precision('Account'))
    amount_final_credito = fields.Float(string='Saldo Final Credito', digits=dp.get_precision('Account'))
    partner_id = fields.Integer(string='Tercero ID')
    account_id_int = fields.Integer(string='Cuenta ID')
    nivel = fields.Integer(string='Clase')
    date = fields.Date('Fecha')
    encabezado_id = fields.Many2one('account.report.mayor.avancys.line.sql.encabezado', string='Encabezado')

class account_report_mayor_avancys_report_wizard(models.TransientModel):
    _name = "wizard.report.mayor.avancys.sql.report"
    
    nivel = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('10', 'Detalle Tercero')], string='Nivel', required=True, default='10')
    
    @api.multi
    def imprimir_calc(self): 
        if self.nivel != '10':
            self._cr.execute('''SELECT id FROM account_report_mayor_avancys_line_sql WHERE nivel <= %s order by code''',(int(self.nivel),))
        else:
            self._cr.execute('''SELECT id FROM account_report_mayor_avancys_line_sql order by code, partner_id desc''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.mayor.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.reporte_mayor_aeroo',
        'report_type': 'aeroo',
        'datas': datas,
        }


    @api.multi
    def imprimir_lm_pdf(self):
        if self.nivel != '10':
            self._cr.execute('''SELECT id FROM account_report_mayor_avancys_line_sql WHERE nivel <= %s order by code''',(int(self.nivel),))
        else:
            self._cr.execute('''SELECT id FROM account_report_mayor_avancys_line_sql order by code, partner_id desc''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.mayor.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.template_reporte_mayorybalance',
        'datas': datas,
        }
        
class account_report_mayor_avancys(models.TransientModel):
    _name = "account.report.mayor.avancys.sql"
    
    @api.one
    @api.constrains('date_from', 'date_to')
    def _validar_fechas(self):           
        if self.date_from > self.date_to:
                raise Warning(_('Error en las fechas!'),_("Las fechas planificadas estan mal configuradas"))  
    
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts', required=True, domain = [('parent_id','=',False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    period_balance_ids = fields.Many2many('account.period', string='Periodos')
    journal_ids = fields.Many2many('account.journal', string='Diarios')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain = [('type','!=','view')])
    partner_ids = fields.Many2many('res.partner', string='Terceros')
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='todos', string='Estados', required=True)
    
    @api.multi
    def calcular(self):        
        encabezado_obj = self.env['account.report.mayor.avancys.line.sql.encabezado']
        report_line_obj = self.env['account.report.mayor.avancys.line.sql']
        account_obj = self.env['account.account']
        journal_obj = self.env['account.journal']
        account_analytic_obj = self.env['account.analytic.account']
        total_credit=0
        total_debit=0
        dict={}
        account_ids=[]
        company_id = self.company_id.id
        cr = self._cr
        cr.execute(''' DELETE FROM account_report_mayor_avancys_line_sql''')
        cr.execute(''' DELETE FROM account_report_mayor_avancys_line_sql_encabezado''')
        
        encabezado = encabezado_obj.create({'date_from':self.date_from,'date_to':self.date_to,'estado':self.estado,'company_id':company_id})
        encabezado_id = encabezado.id
        
        if self.date_from and  self.date_to:
            date_from = self.date_from
            date_to = self.date_to
        
        print "----------Generando Saldo Inicial Tercero----------"
        inicio = datetime.now()
        select_from = '''SELECT account_account.id AS account_id, 
                             res_partner.id AS partner_id,  
                             SUM(account_move_line.debit - account_move_line.credit) AS SI 
                            FROM  
                             account_account,  
                             account_move_line,  
                             res_partner '''
        where =  ''' WHERE 
		 (account_account.parent_zero in(%s) OR account_account.id = %s )
                 AND account_account.id = account_move_line.account_id 
                 AND account_move_line.partner_id = res_partner.id 
                 AND 
                 ( 
                  account_move_line.date < %s 
                  AND account_move_line.company_id = %s 
                 ) '''
        group_by = ''' GROUP BY 
                     account_account.id, 
                     res_partner.id '''
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
        if self.partner_ids:
            where += ''' AND account_move_line.partner_id in %s '''
            tuples.append(tuple([x.id for x in self.partner_ids]))
        query = select_from+where+group_by
        if tuples:
            tuples = (self.chart_account_id.id,self.chart_account_id.id,date_from,company_id)+tuple(tuples)
            cr.execute(query,tuples)
        else:
            cr.execute(query,(self.chart_account_id.id,self.chart_account_id.id,date_from,company_id))
        
        result = self._cr.fetchall()
        for res in result:
            account_id = res[0]
            partner_id = res[1]
            amount_inicial = float(res[2])
            if amount_inicial > 0:
                amount_inicial_debito = amount_inicial
                amount_inicial_credito = 0
            elif amount_inicial < 0:
                amount_inicial_debito = 0
                amount_inicial_credito = abs(amount_inicial)
            else:
                amount_inicial_debito = 0
                amount_inicial_credito = 0
                
            key = (account_id,partner_id)
            dict[key]={'amount_inicial_debito':amount_inicial_debito,'amount_inicial_credito':amount_inicial_credito,'account_id':account_id,'partner_id':partner_id}
        
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        if not self.partner_ids:
            print "----------Generando Saldo Inicial Sin Tercero----------"
            inicio = datetime.now()
            select_from = '''SELECT account_account.id AS account_id, 
                            SUM(account_move_line.debit - account_move_line.credit) AS SI 
                            FROM 
                            account_account,
                            account_move_line '''
            where =  ''' WHERE 
                        (account_account.parent_zero in(%s) OR account_account.id = %s )
                        AND account_account.id = account_move_line.account_id 
                        AND account_move_line.partner_id is NULL 
                        AND 
                        ( 
                        account_move_line.date < %s
                        AND account_move_line.company_id = %s 
                        ) '''
            group_by = ''' GROUP BY 
                         account_account.id '''
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
                tuples = (self.chart_account_id.id,self.chart_account_id.id,date_from,company_id)+tuple(tuples)
                cr.execute(query,tuples)
            else:
                cr.execute(query,(self.chart_account_id.id,self.chart_account_id.id,date_from,company_id))
            
            result = self._cr.fetchall()
            for res in result:
                account_id = res[0]
                partner_id = 0
                amount_inicial = float(res[1])
                if amount_inicial > 0:
                    amount_inicial_debito = amount_inicial
                    amount_inicial_credito = 0
                elif amount_inicial < 0:
                    amount_inicial_debito = 0
                    amount_inicial_credito = abs(amount_inicial)
                else:
                    amount_inicial_debito = 0
                    amount_inicial_credito = 0
                key = (account_id,partner_id)
                dict[key]={'amount_inicial_debito':amount_inicial_debito,'amount_inicial_credito':amount_inicial_credito,'account_id':account_id,'partner_id':partner_id}
                
            final = datetime.now()
            diferencia = final-inicio
            print diferencia
        
        print "----------Generando Debitos Creditos Con Tercero----------"
        inicio = datetime.now()
        
        select_from = '''SELECT account_account.id AS account_id, 
                         res_partner.id AS partner_id, 
                         SUM(account_move_line.credit) AS la_somme_credit, 
                         SUM(account_move_line.debit) AS la_somme_debit, 
                         LEFT(account_account.code,6) AS subcuenta, 
                         LEFT(account_account.code,4) AS cuenta, 
                         LEFT(account_account.code,2) AS grupo, 
                         LEFT(account_account.code,1) AS clase, 
                         account_account.code AS code, 
                         account_account.name AS name, 
                         res_partner.name AS partner_name, 
                         res_partner.ref AS partner_ref 
                        FROM 
                         (
                          account_account
                          INNER JOIN
                          account_move_line
                          ON account_account.id = account_move_line.account_id

                         )
                         RIGHT OUTER JOIN
                         res_partner
                         ON account_move_line.partner_id = res_partner.id '''
        where = ''' WHERE 
		     (account_account.parent_zero in(%s) OR account_account.id = %s )
                     AND account_move_line.date >= %s
                     AND account_move_line.date <= %s
                     AND account_move_line.company_id = %s
                        '''
        group_by = ''' GROUP BY 
                        account_account.id,
                        res_partner.id'''
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
        if self.partner_ids:
            where += ''' AND account_move_line.partner_id in %s '''
            tuples.append(tuple([x.id for x in self.partner_ids]))
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
            partner_id = res[1]
            credit = float(res[2])
            debit = float(res[3])
            subcuenta = res[4]
            cuenta = res[5]
            grupo = res[6]
            clase = res[7]
            code = res[8]
            name = res[9]
            partner_name = res[10] or 'Indefinido'
            partner_ref = res[11] or 'Indefinido'
            partner_name = "["+partner_ref+"] "+partner_name
            try:
                key = (account_id,partner_id)
                amount_inicial_debito = dict[key]['amount_inicial_debito']
                amount_inicial_credito = dict[key]['amount_inicial_credito']
            except:
                amount_inicial_debito = 0
                amount_inicial_credito = 0
                
            amount_final_debito = amount_inicial_debito+debit
            amount_final_credito = amount_inicial_credito+credit
            if amount_final_debito > amount_final_credito:
                amount_final_debito = amount_final_debito - amount_final_credito
                amount_final_credito = 0
            elif amount_final_debito < amount_final_credito:
                amount_final_credito = amount_final_credito - amount_final_debito
                amount_final_debito = 0
            else:
                amount_final_credito = 0
                amount_final_debito = 0
            dict.pop(key,None)
            if account_id not in account_ids:
                account_ids.append(account_id)
            total_credit+=credit
            total_debit+=debit
                
            cr.execute('''insert into account_report_mayor_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,partner_name,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,partner_name,account_id,encabezado_id,10))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        if not self.partner_ids:
            print "----------Generando Debitos Creditos Sin Tercero----------"
            inicio = datetime.now()
            
            select_from = '''SELECT account_account.id AS account_id, 
                             SUM(account_move_line.credit) AS la_somme_credit, 
                             SUM(account_move_line.debit) AS la_somme_debit, 
                             LEFT(account_account.code,6) AS subcuenta, 
                             LEFT(account_account.code,4) AS cuenta, 
                             LEFT(account_account.code,2) AS grupo, 
                             LEFT(account_account.code,1) AS clase, 
                             account_account.code AS code, 
                             account_account.name AS name
                            FROM 
                             ( 
                              account_account 
                              INNER JOIN 
                              account_move_line 
                              ON account_account.id = account_move_line.account_id 
                             )''' 
            where = ''' WHERE
			 (account_account.parent_zero in(%s) OR account_account.id = %s )
                         AND account_move_line.date >= %s 
                         AND account_move_line.date <= %s 
                         AND account_move_line.company_id = %s 
                         AND account_move_line.partner_id is NULL 
                            '''
            group_by = ''' GROUP BY 
                            account_account.id'''
            
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
            if self.partner_ids:
                where += ''' AND account_move_line.partner_id in %s '''
                tuples.append(tuple([x.id for x in self.partner_ids]))
            query = select_from+where+group_by
            if tuples:
                tuples = (self.chart_account_id.id,self.chart_account_id.id, date_from,date_to,company_id)+tuple(tuples)
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
                partner_id = 0
                credit = float(res[1])
                debit = float(res[2])
                subcuenta = res[3]
                cuenta = res[4]
                grupo = res[5]
                clase = res[6]
                code = res[7]
                name = res[8]
                partner_name = "[Indefinido] Indefinido"
                try:
                    key = (account_id,partner_id)
                    amount_inicial_debito = dict[key]['amount_inicial_debito']
                    amount_inicial_credito = dict[key]['amount_inicial_credito']
                except:
                    amount_inicial_debito = 0
                    amount_inicial_credito = 0
                    
                amount_final_debito = amount_inicial_debito+debit
                amount_final_credito = amount_inicial_credito+credit
                if amount_final_debito > amount_final_credito:
                    amount_final_debito = amount_final_debito - amount_final_credito
                    amount_final_credito = 0
                elif amount_final_debito < amount_final_credito:
                    amount_final_credito = amount_final_credito - amount_final_debito
                    amount_final_debito = 0
                else:
                    amount_final_credito = 0
                    amount_final_debito = 0
                dict.pop(key,None)
                if account_id not in account_ids:
                    account_ids.append(account_id)
                total_credit+=credit
                total_debit+=debit


                cr.execute('''insert into account_report_mayor_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,partner_name,account_id_int,encabezado_id,nivel) values 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,partner_name,account_id,encabezado_id,10))
            final = datetime.now()
            diferencia = final-inicio
            print diferencia
        
        print "----------Creando Tabla Sin Debitos Creditos----------"
        inicio = datetime.now()
        for d in dict.values():
            amount_inicial_debito = d['amount_inicial_debito']
            amount_inicial_credito = d['amount_inicial_credito']
            amount_final_debito = amount_inicial_debito
            amount_final_credito = amount_inicial_credito
            account_id = d['account_id']
            partner_id = d['partner_id']
            cr.execute('''SELECT 
                         LEFT(account_account.code,6) AS subcuenta, 
                         LEFT(account_account.code,4) AS cuenta, 
                         LEFT(account_account.code,2) AS grupo, 
                         LEFT(account_account.code,1) AS clase,
                         account_account.code AS code,
                         account_account.name AS name
                        FROM account_account 
			WHERE (account_account.parent_zero in(%s) OR account_account.id = %s )
                        AND id=%s''',
                            (self.chart_account_id.id,self.chart_account_id.id,account_id,))
            rep = self._cr.fetchall()[0]
            subcuenta = rep[0]
            cuenta = rep[1]
            grupo = rep[2]
            clase = rep[3]
            code = rep[4]
            name = rep[5]
            if partner_id:
                cr.execute('''SELECT 
                             res_partner.name AS partner_name, 
                             res_partner.ref AS partner_ref
                             FROM res_partner WHERE id=%s''',
                                (partner_id,))
                rep = self._cr.fetchall()[0]
                partner_name = rep[0] or 'Indefinido'
                partner_ref = rep[1] or 'Indefinido'
                partner_name = "["+partner_ref+"] "+partner_name
            else:
                partner_name = "[indefinido] Indefinido"
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_mayor_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,partner_name,account_id_int,encabezado_id,nivel) values 
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
            (name,code,clase,grupo,cuenta,subcuenta,partner_id,0,0,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,partner_name,account_id,encabezado_id,10))
            self._cr.execute("""select * from account_report_mayor_avancys_line_sql_id_seq""")
        
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Clase----------"
        inicio = datetime.now()
        cr.execute('''SELECT
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial_debito) AS suma_inicial_debito, 
                         SUM(amount_inicial_credito) AS suma_inicial_credito, 
                         SUM(amount_final_debito) AS suma_final_debito, 
                         SUM(amount_final_credito) AS suma_final_credito, 
                         clase
                        FROM 
                         account_report_mayor_avancys_line_sql 
                        WHERE
                         nivel=10
                        GROUP BY 
                         clase
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            amount_inicial_debito = float(res[2])
            amount_inicial_credito = float(res[3])
            amount_final_debito = float(res[4])
            amount_final_credito = float(res[5])
            
            amount_inicial = amount_inicial_debito - amount_inicial_credito
            if amount_inicial > 0:
                amount_inicial_debito = amount_inicial
                amount_inicial_credito = 0
            elif amount_inicial < 0:
                amount_inicial_debito = 0
                amount_inicial_credito = abs(amount_inicial)
            else:
                amount_inicial_debito = 0
                amount_inicial_credito = 0
            amount_final_debito = amount_inicial_debito+debit
            amount_final_credito = amount_inicial_credito+credit
            if amount_final_debito > amount_final_credito:
                amount_final_debito = amount_final_debito - amount_final_credito
                amount_final_credito = 0
            elif amount_final_debito < amount_final_credito:
                amount_final_credito = amount_final_credito - amount_final_debito
                amount_final_debito = 0
            else:
                amount_final_credito = 0
                amount_final_debito = 0
            
            code = res[6]
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR account_account.id = %s ) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)

            cr.execute('''insert into account_report_mayor_avancys_line_sql (name,code,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id,encabezado_id,1))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Grupo----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial_debito) AS suma_inicial_debito, 
                         SUM(amount_inicial_credito) AS suma_inicial_credito, 
                         SUM(amount_final_debito) AS suma_final_debito, 
                         SUM(amount_final_credito) AS suma_final_credito, 
                         grupo
                        FROM 
                         account_report_mayor_avancys_line_sql
                        WHERE
                         nivel=10
                        GROUP BY 
                         grupo 
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            amount_inicial_debito = float(res[2])
            amount_inicial_credito = float(res[3])
            amount_final_debito = float(res[4])
            amount_final_credito = float(res[5])
            amount_inicial = amount_inicial_debito - amount_inicial_credito
            if amount_inicial > 0:
                amount_inicial_debito = amount_inicial
                amount_inicial_credito = 0
            elif amount_inicial < 0:
                amount_inicial_debito = 0
                amount_inicial_credito = abs(amount_inicial)
            else:
                amount_inicial_debito = 0
                amount_inicial_credito = 0
            amount_final_debito = amount_inicial_debito+debit
            amount_final_credito = amount_inicial_credito+credit
            if amount_final_debito > amount_final_credito:
                amount_final_debito = amount_final_debito - amount_final_credito
                amount_final_credito = 0
            elif amount_final_debito < amount_final_credito:
                amount_final_credito = amount_final_credito - amount_final_debito
                amount_final_debito = 0
            else:
                amount_final_credito = 0
                amount_final_debito = 0
            grupo = res[6]
            clase = grupo[0]
            code = grupo
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR account_account.id = %s ) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_mayor_avancys_line_sql (name,code,clase,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id,encabezado_id,2))

        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Cuenta----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial_debito) AS suma_inicial_debito, 
                         SUM(amount_inicial_credito) AS suma_inicial_credito, 
                         SUM(amount_final_debito) AS suma_final_debito, 
                         SUM(amount_final_credito) AS suma_final_credito, 
                         cuenta
                        FROM 
                         account_report_mayor_avancys_line_sql
                        WHERE
                         nivel=10
                        GROUP BY 
                         cuenta 
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            amount_inicial_debito = float(res[2])
            amount_inicial_credito = float(res[3])
            amount_final_debito = float(res[4])
            amount_final_credito = float(res[5])
            amount_inicial = amount_inicial_debito - amount_inicial_credito
            if amount_inicial > 0:
                amount_inicial_debito = amount_inicial
                amount_inicial_credito = 0
            elif amount_inicial < 0:
                amount_inicial_debito = 0
                amount_inicial_credito = abs(amount_inicial)
            else:
                amount_inicial_debito = 0
                amount_inicial_credito = 0
            amount_final_debito = amount_inicial_debito+debit
            amount_final_credito = amount_inicial_credito+credit
            if amount_final_debito > amount_final_credito:
                amount_final_debito = amount_final_debito - amount_final_credito
                amount_final_credito = 0
            elif amount_final_debito < amount_final_credito:
                amount_final_credito = amount_final_credito - amount_final_debito
                amount_final_debito = 0
            else:
                amount_final_credito = 0
                amount_final_debito = 0
            cuenta = res[6]
            grupo = cuenta[0:2]
            clase = grupo[0]
            code = cuenta
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR account_account.id = %s ) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_mayor_avancys_line_sql (name,code,clase,grupo,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id,encabezado_id,3))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        account_ids_repetidas = []
        print "----------Calculando Subcuenta----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial_debito) AS suma_inicial_debito, 
                         SUM(amount_inicial_credito) AS suma_inicial_credito, 
                         SUM(amount_final_debito) AS suma_final_debito, 
                         SUM(amount_final_credito) AS suma_final_credito, 
                         subcuenta
                        FROM 
                         account_report_mayor_avancys_line_sql 
                        WHERE
                         nivel=10
                        GROUP BY 
                         subcuenta 
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            amount_inicial_debito = float(res[2])
            amount_inicial_credito = float(res[3])
            amount_final_debito = float(res[4])
            amount_final_credito = float(res[5])
            amount_inicial = amount_inicial_debito - amount_inicial_credito
            if amount_inicial > 0:
                amount_inicial_debito = amount_inicial
                amount_inicial_credito = 0
            elif amount_inicial < 0:
                amount_inicial_debito = 0
                amount_inicial_credito = abs(amount_inicial)
            else:
                amount_inicial_debito = 0
                amount_inicial_credito = 0
            amount_final_debito = amount_inicial_debito+debit
            amount_final_credito = amount_inicial_credito+credit
            if amount_final_debito > amount_final_credito:
                amount_final_debito = amount_final_debito - amount_final_credito
                amount_final_credito = 0
            elif amount_final_debito < amount_final_credito:
                amount_final_credito = amount_final_credito - amount_final_debito
                amount_final_debito = 0
            else:
                amount_final_credito = 0
                amount_final_debito = 0
            subcuenta = res[6]
            cuenta = subcuenta[0:4]
            grupo = cuenta[0:2]
            clase = grupo[0]
            code = subcuenta
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR account_account.id = %s ) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
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
           
            cr.execute('''insert into account_report_mayor_avancys_line_sql (name,code,clase,grupo,cuenta,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id,encabezado_id,4))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        print "----------Calculando Regular----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial_debito) AS suma_inicial_debito, 
                         SUM(amount_inicial_credito) AS suma_inicial_credito, 
                         SUM(amount_final_debito) AS suma_final_debito, 
                         SUM(amount_final_credito) AS suma_final_credito, 
                         code 
                        FROM 
                         account_report_mayor_avancys_line_sql 
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
            amount_inicial_debito = float(res[2])
            amount_inicial_credito = float(res[3])
            amount_final_debito = float(res[4])
            amount_final_credito = float(res[5])
            amount_inicial = amount_inicial_debito - amount_inicial_credito
            if amount_inicial > 0:
                amount_inicial_debito = amount_inicial
                amount_inicial_credito = 0
            elif amount_inicial < 0:
                amount_inicial_debito = 0
                amount_inicial_credito = abs(amount_inicial)
            else:
                amount_inicial_debito = 0
                amount_inicial_credito = 0
            amount_final_debito = amount_inicial_debito+debit
            amount_final_credito = amount_inicial_credito+credit
            if amount_final_debito > amount_final_credito:
                amount_final_debito = amount_final_debito - amount_final_credito
                amount_final_credito = 0
            elif amount_final_debito < amount_final_credito:
                amount_final_credito = amount_final_credito - amount_final_debito
                amount_final_debito = 0
            else:
                amount_final_credito = 0
                amount_final_debito = 0
            code = res[6]
            subcuenta = code[0:6]
            cuenta = subcuenta[0:4]
            grupo = cuenta[0:2]
            clase = grupo[0]
            cr.execute('''SELECT name,id FROM account_account 
                WHERE 
                code=%s AND company_id = %s ''',(code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            
            cr.execute('''insert into account_report_mayor_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,subcuenta,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id,encabezado_id,5))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        if not self.account_ids:
            print "----------Agregar Cuentas sin Movimientos ni Saldos----------"
            inicio = datetime.now()
            cr.execute('''SELECT 
                             id, 
                             code, 
                             name
                            FROM 
                             account_account
                            WHERE
                            (account_account.parent_zero in(%s) OR account_account.id = %s )
                             AND id not in %s
                             AND company_id = %s
                             ''',(self.chart_account_id.id,self.chart_account_id.id,tuple(account_ids),company_id))
            result = self._cr.fetchall()
            for res in result:
                credit = 0
                debit = 0
                amount_inicial_credito = 0
                amount_inicial_debito = 0
                amount_final_credito = 0
                amount_final_debito = 0
                account_id = res[0]
                code = res[1]
                name = res[2]
                if self.chart_account_id.id==account_id:
                    print "11111111111111"
                    print res
                    credit = total_credit
                    debit = total_debit
                cr.execute('''insert into account_report_mayor_avancys_line_sql (name,code,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id_int,encabezado_id,nivel) values 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (name,code,debit,credit,amount_inicial_debito,amount_inicial_credito,amount_final_debito,amount_final_credito,account_id,encabezado_id,5))
            final = datetime.now()
            diferencia = final-inicio
            print diferencia
        
        print "----------AGREGAR TOTALES DEBITOS Y CREDITOS----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                            SUM(amount_inicial_debito), 
                            SUM(amount_inicial_credito), 
                            SUM(debit), 
                            SUM(credit), 
                            SUM(amount_final_debito), 
                            SUM(amount_final_credito) 
                        FROM 
                            account_report_mayor_avancys_line_sql
                        WHERE
                            nivel = 1
                            ''')
        result = self._cr.fetchall()
        for res in result:
            amount_inicial_debito_total = res[0] or 0.0
            amount_inicial_credito_total = res[1] or 0.0
            debit_total = res[2] or 0.0
            credit_total = res[3] or 0.0
            amount_final_debito_total = res[4] or 0.0
            amount_final_credito_total = res[5] or 0.0
        
            encabezado.write({'amount_inicial_debito_total': amount_inicial_debito_total, 'amount_inicial_credito_total': amount_inicial_credito_total, 'debit_total':debit_total, 'credit_total':credit_total, 'amount_final_debito_total': amount_final_debito_total, 'amount_final_credito_total': amount_final_credito_total})
        
        return {
            'domain': [],
            'context': {},
            'name': 'Libro Mayor y Balance',
            'view_type': 'form',
            'view_mode': 'tree,graph',
            'view_id': False,
            'res_model': 'account.report.mayor.avancys.line.sql',
            'type': 'ir.actions.act_window'
        }
#
