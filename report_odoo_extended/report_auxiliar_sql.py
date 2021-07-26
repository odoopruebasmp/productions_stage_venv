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

class account_report_auxiliar_avancys_line_encabezado(models.Model):
    _name = "account.report.auxiliar.avancys.line.sql.encabezado"
    
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    date = fields.Datetime(string="Fecha")
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='todos', string='Estados')    
    company_id = fields.Many2one('res.company', string='Company')

class account_report_auxiliar_avancys_line(models.Model):
    _name = "account.report.auxiliar.avancys.line.sql"
    _order = "code, partner_id desc, date desc"
    
    name = fields.Char(string='Nombre Cuenta')
    code = fields.Char(string='Codigo')
    subcuenta = fields.Char(string='Subcuenta')
    cuenta = fields.Char(string='cuenta')
    grupo = fields.Char(string='Grupo')
    clase = fields.Char(string='Clase')
    partner_name = fields.Char(string='Tercero')
    partner_ref = fields.Char(string='Nit')
    partner_dev_ref = fields.Char(string='Digito Verificacion')
    detalle = fields.Char(string='Name')
    detalle1 = fields.Char(string='Detalle')
    cuenta_analitica = fields.Char(string='Cuenta Analitica')
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_inicial = fields.Float(string='Saldo Inicial', digits=dp.get_precision('Account'))
    amount_final = fields.Float(string='Saldo Final', digits=dp.get_precision('Account'))
    base = fields.Float(string='Base', digits=dp.get_precision('Account'))
    partner_id = fields.Integer(string='Tercero ID')
    account_id_int = fields.Integer(string='Cuenta ID')
    nivel = fields.Integer(string='Clase')
    date = fields.Date('Fecha')
    encabezado_id = fields.Many2one('account.report.auxiliar.avancys.line.sql.encabezado', string='Encabezado')

class account_report_auxiliar_avancys_report_wizard(models.TransientModel):
    _name = "wizard.report.auxiliar.avancys.sql.report"
    
    @api.multi
    def imprimir_pdf(self):
        self._cr.execute('''SELECT id FROM account_report_auxiliar_avancys_line_sql order by code, partner_id desc, date desc''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.auxiliar.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.template_reporte_auxiliar',
        'datas': datas,
        }
        
    @api.multi
    def imprimir_calc(self): 
        self._cr.execute('''SELECT id FROM account_report_auxiliar_avancys_line_sql order by code, partner_id desc, date desc''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.auxiliar.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.reporte_auxiliar_aeroo',
        'report_type': 'aeroo',
        'datas': datas,
        }
    
    @api.multi
    def imprimir_calc_con_movimientos(self): 
        self._cr.execute('''SELECT id FROM account_report_auxiliar_avancys_line_sql WHERE debit != 0.0 OR credit != 0.0 order by code, partner_id desc, date desc''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.auxiliar.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.reporte_auxiliar_aeroo',
        'report_type': 'aeroo',
        'datas': datas,
        }
        
class account_report_auxiliar_avancys(models.TransientModel):
    _name = "report.axuliar.avancys"
    
    @api.one
    @api.constrains('date_from', 'date_to')
    def _validar_fechas(self):           
        if self.date_from > self.date_to:
                raise Warning(_('Error en las fechas!'),_("Las fechas planificadas estan mal configuradas"))  
    
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts', required=True, domain = [('parent_id','=',False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")    
    account_ids = fields.Many2many('account.account', string='Cuentas', domain = [('type','!=','view')])
    journal_ids = fields.Many2many('account.journal', string='Diarios')
    partner_ids = fields.Many2many('res.partner', string='Terceros')
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='todos', string='Estados', required=True)
    
    @api.multi
    def calcular(self):        
        report_line_obj = self.env['account.report.auxiliar.avancys.line.sql']
        account_obj = self.env['account.account']
        account_analytic_obj = self.env['account.analytic.account']
        encabezado_obj = self.env['account.report.auxiliar.avancys.line.sql.encabezado']
        total_credit=0
        total_debit=0
        account_ids=[]
        dict={}
        company_id = self.company_id.id
        cr = self._cr
        cr.execute(''' DELETE FROM account_report_auxiliar_avancys_line_sql''')
        cr.execute(''' DELETE FROM account_report_auxiliar_avancys_line_sql_encabezado''')
        
        encabezado = encabezado_obj.create({'date':datetime.now()-timedelta(hours=5),'date_from':self.date_from,'date_to':self.date_to,'estado':self.estado,'company_id':company_id})
        encabezado_id = encabezado.id
        
        if self.date_from and  self.date_to:
            date_from = self.date_from
            date_to = self.date_to
        
        print "----------Generando Debito Credito Detalle Contable----------"
        inicio = datetime.now()
        select_from = '''SELECT account_account.id AS account_id, 
                         account_move_line.credit AS la_somme_credit, 
                         account_move_line.debit AS la_somme_debit, 
                         LEFT(account_account.code,6) AS subcuenta, 
                         LEFT(account_account.code,4) AS cuenta, 
                         LEFT(account_account.code,2) AS grupo, 
                         LEFT(account_account.code,1) AS clase, 
                         account_account.code AS code, 
                         account_account.name AS name, 
                         account_move_line.name AS detalle, 
                         account_move_line.ref AS ref, 
                         account_move_line.date AS date, 
                         account_move_line.analytic_account_id AS cuenta_analitica, 
                         account_move_line.partner_id AS partner_id, 
                         account_move_line.move_id AS move_id,
                         account_move_line.base_amount AS base
                        FROM 
                         account_account, 
                         account_move_line '''
        where = ''' WHERE  
   		     (account_account.parent_zero in(%s) OR account_account.id = %s)
                     AND account_account.id = account_move_line.account_id  
                     AND account_move_line.date >= %s  
                     AND account_move_line.date <= %s  
                     AND account_move_line.company_id = %s  '''
        
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
        query = select_from+where
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
            credit = float(res[1])
            debit = float(res[2])
            subcuenta = res[3]
            cuenta = res[4]
            grupo = res[5]
            clase = res[6]
            code = res[7]
            name = res[8]
            detalle1 = res[9] or ''
            detalle2 = res[10] or ''
            date = res[11] or ''
            cuenta_analitica_id = res[12] or 0
            cuenta_analitica = ''
            partner_id = res[13] or 0
            partner_name = 'indefinido'
            partner_ref = 'indefinido'
            partner_dev_ref = 'indefinido'
            move_id = res[14] or 0
            base = res[15] or 0
            move_name = ''
            total_credit+=credit
            total_debit+=debit
            if cuenta_analitica_id:
                cr.execute('''Select name from account_analytic_account WHERE id = %s''',(cuenta_analitica_id,))
                cuenta_analitica = self._cr.fetchall()[0][0]
            if partner_id:
                cr.execute('''Select name,ref,dev_ref from res_partner WHERE id = %s''',(partner_id,))
                fetch = self._cr.fetchall()[0]
                partner_name = fetch[0] or 'indefinido'
                partner_ref = fetch[1] or 'indefinido'
                partner_dev_ref = fetch[2] or 'indefinido'
            if move_id:
                cr.execute('''Select name from account_move WHERE id = %s''',(move_id,))
                move_name = self._cr.fetchall()[0][0]
            detalle = move_name
            detalle1 = detalle1+' '+detalle2
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_auxiliar_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,partner_name,partner_ref,partner_dev_ref,nivel,detalle,detalle1,date,cuenta_analitica,encabezado_id,account_id_int,base) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,partner_name,partner_ref,partner_dev_ref,20,detalle,detalle1,date,cuenta_analitica,encabezado_id,account_id,base))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
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
		 (account_account.parent_zero in(%s) OR account_account.id = %s)
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
            tuples = (self.chart_account_id.id,self.chart_account_id.id, date_from,company_id)+tuple(tuples)
            cr.execute(query,tuples)
        else:
            cr.execute(query,(self.chart_account_id.id,self.chart_account_id.id,date_from,company_id))
            
        result = self._cr.fetchall()
        for res in result:
            account_id = res[0]
            partner_id = res[1] or 0
            amount_inicial = float(res[2])
            key = (account_id,partner_id)
            dict[key]={'amount_inicial':amount_inicial,'account_id':account_id,'partner_id':partner_id}
        
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
			(account_account.parent_zero in(%s) OR account_account.id = %s)
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
                key = (account_id,partner_id)
                dict[key]={'amount_inicial':amount_inicial,'account_id':account_id,'partner_id':partner_id}
                
            final = datetime.now()
            diferencia = final-inicio
            print diferencia
        
        print "----------Generando Debitos Creditos----------"
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
                         res_partner.ref AS partner_ref,
                         res_partner.dev_ref AS partner_dev_ref
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
		     (account_account.parent_zero in(%s) OR account_account.id = %s)
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
            partner_dev_ref = res[12] or 'Indefinido'
            try:
                key = (account_id,partner_id)
                amount_inicial = dict[key]['amount_inicial']
            except:
                amount_inicial = 0
            amount_final = amount_inicial+debit-credit
            dict.pop(key,None)
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_auxiliar_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial,amount_final,partner_name,partner_ref,partner_dev_ref,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial,amount_final,partner_name,partner_ref,partner_dev_ref,account_id,encabezado_id,10))
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
			 (account_account.parent_zero in(%s) OR account_account.id = %s)
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
                partner_id = 0
                credit = float(res[1])
                debit = float(res[2])
                subcuenta = res[3]
                cuenta = res[4]
                grupo = res[5]
                clase = res[6]
                code = res[7]
                name = res[8]
                partner_name = "Indefinido"
                partner_ref = "[Indefinido]"
                partner_dev_ref = "Indefinido"
                try:
                    key = (account_id,partner_id)
                    amount_inicial = dict[key]['amount_inicial']
                except:
                    amount_inicial = 0
                amount_final = amount_inicial+debit-credit
                dict.pop(key,None)
                if account_id not in account_ids:
                    account_ids.append(account_id)
                cr.execute('''insert into account_report_auxiliar_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial,amount_final,partner_name,partner_ref,partner_dev_ref,account_id_int,encabezado_id,nivel) values 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial,amount_final,partner_name,partner_ref,partner_dev_ref,account_id,encabezado_id,10))
            final = datetime.now()
            diferencia = final-inicio
            print diferencia
        
        print "----------Creando Tabla Sin Debitos Creditos----------"
        inicio = datetime.now()
        for d in dict.values():
            amount_inicial = d['amount_inicial']
            account_id = d['account_id']
            partner_id = d['partner_id']
            cr.execute('''SELECT 
                         LEFT(account_account.code,6) AS subcuenta, 
                         LEFT(account_account.code,4) AS cuenta, 
                         LEFT(account_account.code,2) AS grupo, 
                         LEFT(account_account.code,1) AS clase,
                         account_account.code AS code,
                         account_account.name AS name
                        FROM account_account WHERE (account_account.parent_zero in(%s) OR account_account.id = %s) AND id=%s''',
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
                             res_partner.ref AS partner_ref,
                             res_partner.dev_ref AS partner_dev_ref
                             FROM res_partner WHERE id=%s''',
                                (partner_id,))
                rep = self._cr.fetchall()[0]
                partner_name = rep[0] or 'Indefinido'
                partner_ref = rep[1] or 'Indefinido'
                partner_dev_ref = rep[2] or 'Indefinido'
            else:
                partner_name = "Indefinido"
                partner_ref = "[indefinido]"
                partner_dev_ref = 'Indefinido'
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_auxiliar_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial,amount_final,partner_name,partner_ref,partner_dev_ref,account_id_int,encabezado_id,nivel) values 
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
            (name,code,clase,grupo,cuenta,subcuenta,partner_id,0,0,amount_inicial,amount_inicial,partner_name,partner_ref,partner_dev_ref,account_id,encabezado_id,10))
            self._cr.execute("""select * from account_report_auxiliar_avancys_line_sql_id_seq""")
        
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Clase----------"
        inicio = datetime.now()
        cr.execute('''SELECT
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial) AS suma_inicial, 
                         SUM(amount_final) AS suma_final, 
                         clase
                        FROM 
                         account_report_auxiliar_avancys_line_sql 
                        WHERE
                         nivel=10
                        GROUP BY 
                         clase
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            amount_inicial = float(res[2])
            amount_final = float(res[3])
            code = res[4]
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR account_account.id = %s) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_auxiliar_avancys_line_sql (name,code,debit,credit,amount_inicial,amount_final,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,debit,credit,amount_inicial,amount_final,account_id,encabezado_id,1))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Grupo----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial) AS suma_inicial, 
                         SUM(amount_final) AS suma_final, 
                         grupo
                        FROM 
                         account_report_auxiliar_avancys_line_sql
                        WHERE
                         nivel=10
                        GROUP BY 
                         grupo 
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            amount_inicial = float(res[2])
            amount_final = float(res[3])
            grupo = res[4]
            clase = grupo[0]
            code = grupo
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR account_account.id = %s) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id, code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_auxiliar_avancys_line_sql (name,code,clase,debit,credit,amount_inicial,amount_final,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,debit,credit,amount_inicial,amount_final,account_id,encabezado_id,2))

        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Cuenta----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial) AS suma_inicial, 
                         SUM(amount_final) AS suma_final, 
                         cuenta
                        FROM 
                         account_report_auxiliar_avancys_line_sql
                        WHERE
                         nivel=10
                        GROUP BY 
                         cuenta 
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            amount_inicial = float(res[2])
            amount_final = float(res[3])
            cuenta = res[4]
            grupo = cuenta[0:2]
            clase = grupo[0]
            code = cuenta
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR account_account.id = %s) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_auxiliar_avancys_line_sql (name,code,clase,grupo,debit,credit,amount_inicial,amount_final,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,debit,credit,amount_inicial,amount_final,account_id,encabezado_id,3))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Subcuenta----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial) AS suma_inicial, 
                         SUM(amount_final) AS suma_final, 
                         subcuenta
                        FROM 
                         account_report_auxiliar_avancys_line_sql 
                        WHERE
                         nivel=10
                        GROUP BY 
                         subcuenta 
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            amount_inicial = float(res[2])
            amount_final = float(res[3])
            subcuenta = res[4]
            cuenta = subcuenta[0:4]
            grupo = cuenta[0:2]
            clase = grupo[0]
            code = subcuenta
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR account_account.id = %s) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_auxiliar_avancys_line_sql (name,code,clase,grupo,cuenta,debit,credit,amount_inicial,amount_final,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,debit,credit,amount_inicial,amount_final,account_id,encabezado_id,4))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        
        print "----------Calculando Regular----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial) AS suma_inicial, 
                         SUM(amount_final) AS suma_final, 
                         code
                        FROM 
                         account_report_auxiliar_avancys_line_sql
                        WHERE
                         nivel=10
                        GROUP BY 
                         code 
                         ''')
        result = self._cr.fetchall()
        for res in result:
            credit = float(res[0])
            debit = float(res[1])
            amount_inicial = float(res[2])
            amount_final = float(res[3])
            code = res[4]
            subcuenta = code[0:6]
            cuenta = subcuenta[0:4]
            grupo = cuenta[0:2]
            clase = grupo[0]
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero in(%s) OR account_account.id = %s) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_auxiliar_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,debit,credit,amount_inicial,amount_final,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,subcuenta,debit,credit,amount_inicial,amount_final,account_id,encabezado_id,5))
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
			                 (account_account.parent_zero in(%s) OR account_account.id = %s)
                             AND id not in %s 
                             AND company_id = %s 
                             ''',(self.chart_account_id.id,self.chart_account_id.id,tuple(account_ids),company_id))
            result = self._cr.fetchall()
            for res in result:
                credit = 0
                debit = 0
                amount_inicial = 0
                amount_final = 0
                account_id = res[0]
                code = res[1]
                name = res[2]
                if self.chart_account_id.id==account_id:
                    credit = total_credit
                    debit = total_debit
                cr.execute('''insert into account_report_auxiliar_avancys_line_sql (name,code,debit,credit,amount_inicial,amount_final,account_id_int,encabezado_id,nivel) values 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (name,code,debit,credit,amount_inicial,amount_final,account_id,encabezado_id,5))
            final = datetime.now()
            diferencia = final-inicio
            print diferencia
        
        return {
            'domain': [],
            'context': {},
            'name': 'Informe auxiliar',
            'view_type': 'form',
            'view_mode': 'tree,graph',
            'view_id': False,
            'res_model': 'account.report.auxiliar.avancys.line.sql',
            'type': 'ir.actions.act_window'
        }
#
