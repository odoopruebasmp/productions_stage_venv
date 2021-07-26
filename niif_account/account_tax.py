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
import tempfile
import xlrd
from openerp.models import onchange_v7
import time


class account_account(models.Model):
    _inherit = "account.account"
    
    tax_niif = fields.Boolean(string='Impuesto Diferido')
    name_tax_niif = fields.Char(string='Nombre Concepto')
    type_tax_niif = fields.Selection([('temporarias', 'Temporarias'),('permanentes', 'Permanentes')], string='Tipo Diferencia')    
    account_tax_niif_ids = fields.One2many('account.account', 'account_tax_niif_id', string='Cuentas Equivalentes', domain=[('type','!=','view'),('niif','=',True)])
    account_tax_niif_id = fields.Many2one('account.account', string='Cuenta Ingresos NIIF')
    porcentaje_tax = fields.Float(string="Tarifa (%)", digits=dp.get_precision('Account'))
    

class politica_tax_niif_line(models.Model):
    _name = 'politica.tax.niif.line'
    
    name = fields.Char(string='Concepto', required=True, readonly=True)
    name_fiscal = fields.Char(string='Fiscal', required=True, readonly=True)
    name_niif = fields.Char(string='Contable', required=True, readonly=True)
    amount_fiscal = fields.Float(string="Balance Fiscal", required=True, digits=dp.get_precision('Account'), readonly=True)
    amount_niif = fields.Float(string="Balance Contable", required=True, digits=dp.get_precision('Account'), readonly=True)
    amount_base = fields.Float(string="Base Neta", required=True, digits=dp.get_precision('Account'), readonly=True)
    type_tax_niif = fields.Selection([('temporarias', 'Temporarias'),('permanentes', 'Permanentes')], string='Tipo Diferencia')
    porcentaje_tax = fields.Float(string="Tarifa (%)", required=True, digits=dp.get_precision('Account'), readonly=True)
    amount = fields.Float(string="Impuesto Diferido", required=True, digits=dp.get_precision('Account'), readonly=True)
    amount_activo = fields.Float(string="Diferido Activo", required=True, digits=dp.get_precision('Account'), readonly=True)
    amount_pasivo = fields.Float(string="Diferido Pasivo", required=True, digits=dp.get_precision('Account'), readonly=True)
    politica_id = fields.Many2one('politica.tax.niif', required=True, string='Proceso', readonly=True)
    aplica = fields.Selection([('aplica', 'Aplica'),('no_aplica', 'No Aplica')], string='Aplica', default='borrador')
    
    
class politica_tax_niif(models.Model):
    _name = 'politica.tax.niif'
    
    name = fields.Char(string='Nombre', readonly=True)
    description = fields.Text(string='Observaciones')
    state = fields.Selection([('borrador', 'Borrador'),('ejecucion', 'Ejecucion'),('terminado', 'Terminado'),('cancelar', 'Cancelar')], 'Estado', readonly=True, default='borrador')
    line_ids = fields.One2many('politica.tax.niif.line', 'politica_id', string='Lineas')
    company_id = fields.Many2one('res.company', string='Compañia', required=True, readonly=True, states={'borrador':[('readonly',False)]})
    journal_id = fields.Many2one('account.journal', string='Diario', readonly=True, required=True, states={'borrador':[('readonly',False)]})
    date_start = fields.Date(string='Desde', readonly=True, required=True, states={'borrador':[('readonly',False)]})
    date_end = fields.Date(string='Hasta', readonly=True, required=True, states={'borrador':[('readonly',False)]})
    date = fields.Date(string='Fecha Contabilizacion', default=fields.datetime.now(), readonly=True, required=True, states={'borrador':[('readonly',False)]})
    move_id = fields.Many2one('account.move', string='Move', readonly=True)
    
    
    @api.multi
    def calcular(self):
        #Actualiza movimientos contables con equivalente niif
        self._cr.execute(" UPDATE account_move_line SET write_uid = %s, write_date = now(), "\
            " account_niif_id = child_id "\
            " FROM account_account_consol_rel aacr WHERE account_move_line.account_id = aacr.parent_id AND account_id IS NOT NULL "\
            #" AND account_move_line.move_id not in (SELECT am.id FROM account_move am INNER JOIN account_journal aj ON aj.id = am.journal_id WHERE aj.type = 'situation') "\
            " AND account_move_line.date between '%s' AND '%s' "%(self.env.user.id,'2010-01-01','2020-12-31'))

        #Actualiza movimientos contables con cuenta niif en campo cuenta
        self._cr.execute(" UPDATE account_move_line SET write_uid = %s, write_date = now(), "\
            " account_niif_id = account_id "\
            " FROM account_account aa WHERE account_move_line.account_id = aa.id AND niif IS TRUE "\
            #" AND account_move_line.move_id not in (SELECT am.id FROM account_move am INNER JOIN account_journal aj ON aj.id = am.journal_id WHERE aj.type = 'situation') "\
            " AND date between '%s' and '%s' "%(self.env.user.id,'2010-01-01','2020-12-31'))
        
        move_obj = self.env['account.move.line']
        account_obj = self.env['account.account']
        dict = {}
        move_ids = []
        
        company_id = self.company_id.id        
        accounts = [x.id for x in account_obj.search([('company_id','=',company_id),('niif','=',False),('tax_niif','=',True)])]
        if not accounts:
            raise osv.except_osv(_('Error !'), _("No existen cuentas configuradas para la consulta del impuesto diferido"))
        
        date = self.date
        date_start = self.date_start
        date_end = self.date_end
        
        self._cr.execute(''' DELETE FROM politica_tax_niif_line WHERE politica_id = %s''',(self.id,))
    
        print "+++++++++++++++++++++++"
        print tuple(accounts)
        print ""
        self._cr.execute('''SELECT
                                account_id,
                                SUM(debit - credit)
                            FROM                 
                                account_move_line
                            WHERE  
                                account_id in %s
                                AND date >= %s
                                AND date <= %s
                                AND company_id = %s
                            GROUP BY
                                account_id''',
                        (tuple(accounts),date_start,date_end,company_id))   
        result = self._cr.fetchall()
        print "-------------"
        print len(result)
        print "-------------"
        if result:
            for res in result:             
                account_id = res[0] or False
                amount_fiscal = float(res[1] or 0.0)
                
                account_tax_niif_ids = [x.id for x in account_obj.search([('company_id','=',company_id),('niif','=',True),('account_tax_niif_id','=',account_id)])]
                                
                self._cr.execute('''SELECT
                                        SUM(debit - credit)
                                    FROM                 
                                        account_move_line
                                    WHERE  
                                        account_niif_id in %s
                                        AND date >= %s
                                        AND date <= %s
                                        AND company_id = %s''',
                                (tuple(account_tax_niif_ids),date_start,date_end,company_id))   
                result1 = self._cr.fetchall()
                print "-------------"
                print len(result1)
                print "-------------"
                if result1:
                    for res in result1:             
                        amount_niif = float(res[0] or 0.0)
                        name_niif=''
                        account_id = self.env['account.account'].browse(account_id)
                        print "11111111111"
                        print account_id
                        print ""

                        name = account_id.name_tax_niif or 'Indefinido'
                        name_fiscal = account_id.code+' '+account_id.name
                        
                        if len(account_id.account_tax_niif_ids) > 1:
                            for a in account_id.account_tax_niif_ids:
                                name_niif+=' '+a.code+' '+a.name+'/'
                        else:
                            name_niif = account_id.account_tax_niif_ids[0].code+' '+account_id.account_tax_niif_ids[0].name
                            
                        if isinstance(amount_niif, (list, tuple)):
                            amount_niif = amount_niif[0]
                    
                        if isinstance(amount_fiscal, (list, tuple)):
                            amount_fiscal = amount_fiscal[0]
                    
                        amount_base = amount_fiscal - amount_niif
                        
                        type_tax_niif = account_id.type_tax_niif
                        
                        porcentaje_tax = account_id.porcentaje_tax
                        
                        amount = amount_base*porcentaje_tax/100
                        
                        amount_activo = 0.0
                        amount_pasivo = 0.0
                        aplica= 'no_aplica'
                        if amount > 0.0:
                            amount_activo = amount
                            aplica= 'aplica'
                        elif amount < 0.0:
                            amount_pasivo = amount
                            aplica= 'aplica'
    
                            
                        self._cr.execute('''INSERT INTO politica_tax_niif_line (name,name_fiscal,name_niif,amount_fiscal,amount_niif,amount_base,type_tax_niif,porcentaje_tax,amount,amount_activo,amount_pasivo,politica_id,aplica) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        (name,name_fiscal,name_niif,amount_fiscal,amount_niif,amount_base,type_tax_niif,porcentaje_tax,amount,amount_activo,amount_pasivo,self.id,aplica))                        
                        move_ids.append(self._cr.fetchone()[0])
        
        
        
        
        
        domain = [('id','in',move_ids)]
        return {    
            'domain': domain,
            'name': 'Impuesto Diferido',
            'view_type': 'form',
            'view_mode': 'graph,tree',
            'view_id': False,
            'res_model': 'politica.tax.niif.line',
            'type': 'ir.actions.act_window'
            }
    
    
    @api.multi
    def contabilizar(self):
        date=self.date
        company_id=self.company_id.id
        name = self.name
        date_created=date        
        partner_id=company_id        
        journal_id=self.journal_id.id
        
        period_id = self.env['account.period'].search([('date_start','<=', date),('date_stop','>=', date),('state','=', 'draft')])
        if not period_id:
            raise osv.except_osv(_('Error !'), _("No existe un periodo Abierto parala fecha '%s'") % (date))
        period_id = period_id.id
        
        account_tax_active_niif_id = self.company_id.account_tax_active_niif_id or False        
        if not account_tax_active_niif_id:
            raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de impuestos diferidos de tipo activo en la compania"))        
        
        account_tax_pasivo_niif_id = self.company_id.account_tax_pasivo_niif_id or False
        if not account_tax_pasivo_niif_id:
            raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de impuestos diferidos de tipo pasivo en la compania"))  
        
        account_tax_expense_niif_id = self.company_id.account_tax_expense_niif_id or False
        if not account_tax_expense_niif_id:
            raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de impuestos diferidos para el gasto en la compania")) 
        
        account_tax_income_niif_id = self.company_id.account_tax_income_niif_id or False
        if not account_tax_income_niif_id:
            raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de impuestos diferidos para el ingreso en la compania")) 
        
        
    
        move = {
            'name': name,
            'journal_id': journal_id,
            'date': date,
            'period_id': period_id,
            'state':'posted'
        }
        move_id = self.env['account.move'].create(move)
        
        balance = 0.0
        
        for line in self.line_ids.filtered(lambda x: x.aplica == 'aplica'):
            ref=line.name
            
            if line.amount > 0.0:
                ref='IMPUESTO DIFERIDO ACTIVO'
                debit=abs(line.amount)
                credit=0.0
                account_id=account_tax_active_niif_id
            elif line.amount < 0.0:
                ref='IMPUESTO DIFERIDO PASIVO'
                account_id=account_tax_pasivo_niif_id
                debit=0.0
                credit=abs(line.amount)
            else:
                continue
            
            
            if account_id.niif == True:
                account_niif_id=account_id.id
                account_id=account_id.id
            else:
                account_id=account_id.id
                self._cr.execute('''SELECT
                                        child_id
                                    FROM                 
                                        account_account_consol_rel
                                    WHERE  
                                        parent_id = %s ''',
                                (account_id,))   
                account_niif_id = self._cr.fetchall()
                if not account_niif_id:
                    account_niif_id = None
            
            balance+=line.amount
            
            self._cr.execute('''INSERT INTO account_move_line (account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,move_id,journal_id,period_id,company_id,state) VALUES 
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
            (account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,move_id.id,journal_id,period_id,company_id,'valid'))
        
        if balance != 0.0:
            if balance < 0.0:
                ref='Ajuste Gasto Impuesto Diferido'
                debit=abs(balance)
                credit=0.0
                account_id=account_tax_expense_niif_id
            elif balance > 0.0:
                ref='Ajuste Ingreso Impuesto Diferido'
                account_id=account_tax_income_niif_id
                debit=0.0
                credit=abs(balance)
            
            
            if account_id.niif == True:
                account_niif_id=account_id.id
                account_id=account_id.id
            else:
                account_id=account_id.id
                self._cr.execute('''SELECT
                                        child_id
                                    FROM                 
                                        account_account_consol_rel
                                    WHERE  
                                        parent_id = %s ''',
                                (account_id.id,))   
                account_niif_id = self._cr.fetchall()
                if not account_niif_id:
                    account_niif_id = None
                
            self._cr.execute('''INSERT INTO account_move_line (account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,move_id,journal_id,period_id,company_id,state) VALUES 
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
            (account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,move_id.id,journal_id,period_id,company_id,'valid'))
            
        self.write({'state':'terminado','move_id':move_id.id})        
        return True
    
    @api.multi
    def recalcular(self):
        self._cr.execute("DELETE FROM account_move WHERE id=%s", (self.move_id.id,))
        self.write({'state':'ejecucion'})        
        return True
    
    @api.multi
    def confirmar(self):
        number_seq = self.pool.get('ir.sequence').next_by_id(self._cr, SUPERUSER_ID, self.journal_id.sequence_id.id, context=self._context)
        self.write({'state': 'ejecucion','name':number_seq})   
        return True
    
    
    @api.multi
    def cancelar(self):
        self.write({'state':'cancelar'})        
        return True
    
            
