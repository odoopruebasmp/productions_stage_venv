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


class account_analytic_line(models.Model):
    _inherit = "account.analytic.line"
    
    debit = fields.Float(string='Debito', digits= dp.get_precision('Account'), readonly=True)
    credit = fields.Float(string='Credito', digits= dp.get_precision('Account'), readonly=True)
    amount = fields.Float(string='Saldo', required=True, help='Calculated by multiplying the quantity and the price given in the Product\'s cost price. Always expressed in the company main currency.', digits=dp.get_precision('Account'))

class account_report_consultas(models.Model):
    _name = "account.report.consultas"
    
    name = fields.Char(string='Name', required=True)
    account_ids = fields.Many2many('account.account', string='Cuentas', required=True)
    
    
class account_report_analytic_consultas(models.Model):
    _name = "account.report.analytic.consultas"
    
    name = fields.Char(string='Name', required=True)
    account_ids = fields.Many2many('account.analytic.account', 'accounts_analytics_dos',  'report_id_dos', 'analytic_id_dos', string='Cuentas Analiticas', required=True)


class account_analytic_account(models.Model):
    _inherit = "account.analytic.account"
    
    account_report_analytic_id_dos = fields.Many2many('account.report.analytic.consultas', 'accounts_analytics_dos', 'analytic_id_dos', 'report_id_dos', string='Informes Analiticos')
    

class account_report_balance_avancys_line_dos(models.Model):
    _name = "account.report.balance.avancys.line.dos"
    _order = "account_id"
        
    name = fields.Char(string='Name', related='account_id.name')
    code = fields.Char(string='Ref', related='account_id.code')
    account_id = fields.Many2one('account.account', string='Cuenta Consulta', required=True, domain = [('type','!=','view')])
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_inicial = fields.Float(string='Saldo Inicial', digits=dp.get_precision('Account'))
    amount_final = fields.Float(string='Saldo Final', digits=dp.get_precision('Account'))
    amount_final_consulta = fields.Float(string='Saldo Final Consulta', digits=dp.get_precision('Account'))
    clase_id = fields.Char(string='PUC')
    grupo_id = fields.Char(string='clase')
    cuenta_id = fields.Char(string='Grupo')
    subcuenta_id = fields.Char(string='Cuenta')
    regular_id = fields.Char(string='Subcuenta')
    otras_id = fields.Char(string='Auxiliar')
    partner_id = fields.Many2one('res.partner', string='Tercero')
    partner_ref = fields.Char(string='Ref Tercero')
    account_analytic_id = fields.Many2one('account.analytic.account', string='Cuenta Analitica')
    
    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, lazy=True):
        if 'debit' not in fields:
            fields.append('debit')
        if 'credit' not in fields:
            fields.append('credit')
        if 'amount_inicial' not in fields:
            fields.append('amount_inicial')
        result = super(account_report_balance_avancys_line_dos, self).read_group(cr, uid, domain, fields, groupby, offset=offset, limit=limit, context=context, orderby=orderby, lazy=lazy)
        
        for res in result:
            if res['amount_final'] > 0:
                res.update({'amount_final':res['amount_inicial'] + res['debit'] - res['credit']})
        return result

    
    
class account_report_prueba_avancys_dos(models.TransientModel):
    _name = "account.report.prueba.avancys.dos"
    
    @api.one
    @api.constrains('date_from', 'date_to')
    def _validar_fechas(self):           
        if self.date_from > self.date_to:
                raise Warning(_('Error en las fechas!'),_("Las fechas planificadas estan mal configuradas"))  
            
    
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts', required=True, domain = [('parent_id','=',False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    period_balance_ids = fields.Many2many('account.period', string='Periodos')
    account_group_id = fields.Many2one('account.report.consultas', string='Consulta', required=True)
    account_analytic_group_id = fields.Many2one('account.report.analytic.consultas', string='Consulta Analitica', required=True)
    account_regural_ids = fields.Many2many('account.account', string='Cuentas', domain = [('type','!=','view')])
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    move_zero = fields.Boolean(string='Incluir Cuentas sin Movimientos')
    
    @api.multi
    def calcular(self):     
        report_line_obj = self.env['account.report.balance.avancys.line.dos']
        account_obj = self.env['account.account']
        account_analytic_obj = self.env['account.analytic.account']
        
        l_ids = []
        account_ids = []
        
        amount_inicial = 0.0
        amount_final = 0.0
        amount_final_consulta = 0.0
        
        otras = 'Indefinido'
        regular = 'Indefinido'
        subcuenta = 'Indefinido'
        cuenta = 'Indefinido'
        grupo = 'Indefinido'
        clase = 'Indefinido'
        
        if self.date_from and  self.date_to:
            date_from = self.date_from
            date_to = self.date_to
            
                        
        self._cr.execute(''' DELETE FROM account_report_balance_avancys_line_dos''')                    
        account_ids = [x.id for x in self.account_group_id.account_ids]
        analytic_ids = [x.id for x in self.account_analytic_group_id.account_ids]
            
         

        
        date_from = date_from + ' 00:00:01'
        date_to = date_to + ' 23:59:59'
        "CALCULA EL SALDO INICIAL"
        self._cr.execute('''SELECT account_analytic_account.id AS account_analytic_id,
                                account_account.id AS account_id,
                                SUM(account_analytic_line.amount) AS la_somme_amount 
                            FROM  
                                account_analytic_account,  
                                account_analytic_line,
                                account_account
                            WHERE  
                                account_account.parent_zero in(%s)
                                AND account_analytic_account.id in %s
                                AND account_account.id in %s
                                AND account_account.id = account_analytic_line.general_account_id
                                AND 
                                ( 
                                account_analytic_line.date <= %s 
                                AND account_analytic_line.company_id = %s 
                                ) 
                            GROUP BY
                                account_analytic_account.id,                                    
                                account_account.id''',
                        (self.chart_account_id.id,tuple(analytic_ids),tuple(account_ids),date_from,self.company_id.id))        
        dict={}
        result = self._cr.fetchall()
        for res in result:
            account_analytic_id = res[0]
            account_id = res[1]
            amount_inicial = float(res[2])
            key = (account_id,account_analytic_id)
            dict[key]={'amount_inicial':amount_inicial,'account_id':account_id,'account_analytic_id':account_analytic_id}           
        
        self._cr.execute('''SELECT account_analytic_account.id AS account_analytic_id,
                                account_account.id AS account_id,                          
                                account_account.code AS code,
                                account_account.name AS name_ac,
                                SUM(account_analytic_line.amount) AS la_somme_amount
                            FROM
                                (
                                account_account
                                RIGHT OUTER JOIN
                                account_analytic_line
                                ON account_analytic_line.general_account_id = account_account.id
                                )
                                INNER JOIN
                                account_analytic_account
                                ON account_analytic_account.id = account_analytic_line.account_id                                                                      
                            WHERE 
                                account_account.parent_zero in(%s)
                                AND account_analytic_account.id in %s
                                AND account_account.id in %s
                                AND account_analytic_line.date >= %s
                                AND account_analytic_line.date <= %s
                                AND account_analytic_line.company_id = %s
                            GROUP BY
                                account_analytic_account.id,
                                account_account.id''',            
                        (self.chart_account_id.id,tuple(analytic_ids),tuple(account_ids),date_from,date_to,self.company_id.id))
        
        result = self._cr.fetchall()
        for res in result:                
            account_analytic_id = res[0]
            account_id = res[1]
            code = res[2]
            name = res[3]
            amount = float(res[4])                
            
            key = (account_id,account_analytic_id)
            try:
                amount_inicial = dict[key]['amount_inicial']
            except:
                amount_inicial = 0.0    
            
            dict.pop(key,None)
            account = self.env['account.account'].browse(res[1])
            otras = account.parent_id.name
            regular = account.parent_id.parent_id.name
            subcuenta = account.parent_id.parent_id.parent_id.name
            cuenta = account.parent_id.parent_id.parent_id.parent_id.name
            grupo = account.parent_id.parent_id.parent_id.parent_id.parent_id.name
            clase = account.parent_id.parent_id.parent_id.parent_id.parent_id.parent_id.name
            
            debit = 0.0
            credit = 0.0
            
            
            if amount > 0:
                debit = abs(amount)
            else:
                credit = abs(amount)
            
            amount_inicial = abs(amount_inicial)
            amount = abs(amount)
            
            if account.user_type and (account.user_type.report_type == 'asset' or account.user_type.report_type == 'expense'):                
                amount_final = amount_inicial + debit - credit
            elif account.user_type and (account.user_type.report_type == 'income' or account.user_type.report_type == 'liability'):
                amount_final = amount_inicial - debit + credit
            
           
            self._cr.execute('''INSERT INTO account_report_balance_avancys_line_dos (account_id,debit,credit,account_analytic_id,amount_inicial,amount_final,amount_final_consulta,clase_id,grupo_id,cuenta_id,subcuenta_id,regular_id,otras_id) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (account_id,debit,credit,account_analytic_id,amount_inicial,amount_final,amount,clase,grupo,cuenta,subcuenta,regular,otras))
            
        
        return {
            'domain': [],
            'name': 'Analisis Analitico',
            'view_type': 'form',
            'view_mode': 'graph,tree',
            'view_id': False,
            'res_model': 'account.report.balance.avancys.line.dos',
            'type': 'ir.actions.act_window'
        }
#
