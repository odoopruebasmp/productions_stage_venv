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



class account_cartera_type(models.Model):
    _name = 'account.cartera.type'
                
    name = fields.Char(string='Nombre', required=True)
    
    
class res_partner(models.Model):
    _inherit = "res.partner"
    
    type_customer = fields.Many2one('account.cartera.type', string='Tipo Cartera')
    

class account_move_line(models.Model):
    _inherit = "account.move.line"            
    
    @api.one
    @api.constrains('journal_id', 'account_id')
    def _check_move_niff(self):
        if self.journal_id and self.journal_id.niif and not self.account_id.niif:
            raise Warning(_('El diario asociado solo permite registro contables de cuentas niif, por favor valide la informacion o consulte con el area responsable.'))
        elif self.account_id.niif and self.journal_id and not self.journal_id.niif:
            raise Warning(_('El diario asociado solo permite registro contables de cuentas niif, por favor valide la informacion o consulte con el area responsable.'))
    
    @api.one
    @api.depends('move_deterioro_ids', 'move_deterioro_ids.state', 'deterioro_process','move_recuperable_ids', 'move_recuperable_ids.state')       
    def _amount_cartera(self):
        move_id = self._context.get('move_id', False) or self.id or False
        if move_id: 
            cartera_amount = 0.0
            if self.move_deterioro_ids or self.move_recuperable_ids:
                self._cr.execute('''SELECT
                                        SUM(debit-credit)
                                    FROM
                                        account_move_line
                                    WHERE  
                                        account_id = %s
                                        AND (move_deterioro_id = %s OR move_recuperable_id = %s)
                                        AND state = 'valid' ''',
                            (self.account_niif_id.id,move_id,move_id)) 
                result = self._cr.fetchall()[0]
                if result:
                    cartera_amount = result[0]
                    if isinstance(cartera_amount, (list, tuple)):
                        cartera_amount = float(cartera_amount[0] or 0.0)
                    else:
                        cartera_amount = float(cartera_amount or 0.0)
                if cartera_amount == 0.0:
                    self.cartera_ok = True
            self.cartera_amount = cartera_amount 
    
    
    cartera_id = fields.Many2one('change.cartera', string='Proceso Deterioro y Recuperacion de Cartera', readonly=True)
    move_deterioro_id = fields.Many2one('account.move.line', string='Movimiento Relacionado Deterioro' , readonly=True)
    move_deterioro_ids = fields.One2many('account.move.line', 'move_deterioro_id', string='Movimientos de Deterioro de Cartera', readonly=True)
    move_recuperable_id = fields.Many2one('account.move.line', string='Movimiento Relacionado Recuperable' , readonly=True)
    move_recuperable_ids = fields.One2many('account.move.line', 'move_recuperable_id', string='Movimientos de Recuperacion de Cartera', readonly=True)
    cartera_residual = fields.Float(string='Valor de Referencia', digits=dp.get_precision('Account'), readonly=True)
    cartera_old = fields.Float(string='Deterioro Anterior', digits=dp.get_precision('Account'), readonly=True)
    cartera_politica = fields.Integer(string='% Politica Anual', readonly=True)
    cartera_amount = fields.Float(string='Deterioro Acumulado', digits=dp.get_precision('Account'), readonly=True, compute="_amount_cartera")
    deterioro_process = fields.Char(string="Ultimo Proceso", readonly=True)
    deterioro_ids = fields.Many2many('change.cartera', string="Cuentas")
    politica_id = fields.Many2one('politica.cartera.line', string='Politica de Deterioro y recuperacion', help="Esta es la ultima politica, con la cual fue calculado el deterioro", readonly=True)
    cartera_ok = fields.Boolean(string='Cartera OK')
    
    
class account_analytic_line(models.Model):
    _inherit = "account.analytic.line"
    
    cartera_id = fields.Many2one('change.cartera', string='Proceso Deterioro y Recuperacion de Cartera')
    
    
class account_move(models.Model):
    _inherit = "account.move"
    
    cartera_process = fields.Many2one('change.cartera', string='Proceso Deterioro y Recuperacion de Cartera')
  
  
class account_journal(models.Model):
    _inherit = "account.journal"
            
    niif = fields.Boolean(string='NIIF', help="Si se selecciona, solo permite realizar registros contables a cuentas regulares niif y cuentas consolidadas")


class politica_cartera(models.Model):
    _name = 'politica.cartera'
    
    name = fields.Char(string='Nombre', required=True)
    description = fields.Text(string='Descripcion', required=True)
    active = fields.Boolean(string='activo', default=True)
    line_ids = fields.One2many('politica.cartera.line', 'politica_id', string='Lineas', required=True)
    company_id = fields.Many2one('res.company', string='Compañia', required=True)    
    type = fields.Selection([('dia', 'VPN Dia'),('periodo', 'VPN Periodo')], 'Periodo', required=True, default="dia")
    type_calc = fields.Selection([('documento', 'Documento'),('tercero', 'Tercero')], 'Nivel', required=True, default="tercero")
    type_interes = fields.Selection([('anual', 'Anual'),('mensual', 'Mensual'),('directo', 'Directo')], 'Interes', required=True, default="anual")
    type_customer = fields.Many2one('account.cartera.type', string='Tipo Cartera', required=True)
    

class politica_cartera_line(models.Model):
    _name = 'politica.cartera.line'
    
    @api.one
    @api.constrains('deterioro')
    def _check_deterioro(self):
        if self.deterioro < 0 or self.deterioro > 100:
            raise Warning(_('El valor del deterioro es porcentual, el valor debe estar entre 0 y 100.'))
    
    name = fields.Char(string='Nombre', required=True)
    amount_start = fields.Integer(string="Desde", required=True)
    amount_end = fields.Integer(string="Hasta", required=True)
    deterioro = fields.Integer(string="% Deterioro", required=True)
    account_deterioro_id = fields.Many2one('account.account', string='Cuenta Deterioros', domain="[('niif','=',True),('type','!=','view')]", required=True)
    account_recuperable_id = fields.Many2one('account.account', string='Cuenta Recuperables', required=True, domain="[('niif','=',True),('type','!=','view')]")
    politica_id = fields.Many2one('politica.cartera', string='Politica')
    


class account_move_line_deterioro(models.Model):
    _name = 'account.move.line.deterioro'
    
    @api.one
    @api.constrains('ok')
    def _check_adicional_max(self):
        if self.move_id:
            self._cr.execute(''' UPDATE account_move_line SET cartera_ok=True WHERE id=%s ''',(self.move_id.id,))
            
    
    name = fields.Char(string='Nombre', readonly=True)
    ref = fields.Char(string="Referencia", readonly=True)
    date = fields.Date(string="F. Afectacion", readonly=True)
    date_maturity = fields.Date(string="F. Vencimiento", readonly=True)
    days = fields.Integer(string='Dias vencidos', readonly=True)
    account_id = fields.Many2one('account.account', string='Cuenta Local', readonly=True)
    politica_id = fields.Many2one('politica.cartera.line', string='Politica de Deterioro y recuperacion', help="Esta es la ultima politica, con la cual fue calculado el deterioro", readonly=True)
    partner_id = fields.Many2one('res.partner', string="Cliente", readonly=True)    
    analytic_account_id = fields.Many2one('account.analytic.account', string="Cuenta Analitica", readonly=True)    
    type = fields.Selection([('deterioro', 'Deterioro'),('recuperacion', 'Recuperacion')], 'Tipo', readonly=True)
    amount_start = fields.Float(string='Valor Saldo', digits=dp.get_precision('Account'), readonly=True)
    amount = fields.Float(string='Valor Calculado', digits=dp.get_precision('Account'), readonly=True)
    amount_history = fields.Float(string='Valor Acumulado', digits=dp.get_precision('Account'), readonly=True)
    amount_aplicar = fields.Float(string='Valor Ajuste', digits=dp.get_precision('Account'), readonly=True)
    amount_end = fields.Float(string='Valor Resultante', digits=dp.get_precision('Account'), readonly=True)
    cartera_politica = fields.Integer(string='% Politica Anual', readonly=True)
    ok = fields.Boolean(string='Aplica') 
    deterioro_id = fields.Many2one('change.cartera', string="Proceso", readonly=True)
    company_id = fields.Many2one('res.company', string='Compania', readonly=True)
    move_id = fields.Many2one('account.move.line', string='Movimiento', readonly=True)
    type_customer = fields.Many2one('account.cartera.type', string='Tipo Cartera', readonly=True)    
        
    
class change_cartera(models.Model):
    _name = 'change.cartera'
          
    @api.one
    @api.depends('date')       
    def _period(self):
        if self.date:
            period_id = self.env['account.period'].search([('date_start','<=', self.date),('date_stop','>=', self.date),('state','=', 'draft')])
            if not period_id:
                raise osv.except_osv(_('Error !'), _("No existe un periodo Abierto parala fecha '%s'") % (self.date))
            self.period_id = period_id.id
    
    @api.one
    @api.depends('prueba_ids', 'state')       
    def _count(self):
        if self.prueba_ids:
            self.count = len(self.prueba_ids)
    
                
    name = fields.Char(string='Name', readonly=True)
    state = fields.Selection([('draft', 'Nuevo'),('confirmed', 'Confirmado'),('done', 'Realizado')], 'Estado', readonly=True, select=True, default="draft")
    period_id = fields.Many2one('account.period', compute="_period", string='Periodo', store=True)
    date = fields.Date(string='Fecha', default=fields.datetime.now(), readonly=False, required=True, states={'draft':[('readonly',False)]})
    line_ids = fields.One2many('account.move.line', 'cartera_id', string='Movimientos', readonly=True)
    line_analytic_ids = fields.One2many('account.analytic.line', 'cartera_id', string='Lineas Analiticas', readonly=True)
    journal_id = fields.Many2one('account.journal', string='Diario', required=True, readonly=True, states={'draft':[('readonly',False)]}, domain="[('niif','=',True)]")
    politica_id = fields.Many2one('politica.cartera', string='Politica', required=True, readonly=True, states={'draft':[('readonly',False)]}, domain="[('active','=',True)]")
    company_id = fields.Many2one('res.company', string='Compañia', required=True, readonly=True, states={'draft':[('readonly',False)]})
    move_ids = fields.Many2many('account.move.line', string="Movimiento") 
    prueba_ids = fields.One2many('account.move.line.deterioro', 'deterioro_id', string='Movimientos', readonly=True)
    count = fields.Integer(string="Count",compute="_count")
    
    
    def view_detalle(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for invoice in self.browse(cr, uid, ids, context=context).prueba_ids:
            inv.append(invoice.id)
        
        
        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Invoice FOB',
                'view_type': 'form',
                'view_mode': 'graph,tree',
                'view_id': False,
                'res_model': 'account.move.line.deterioro',
                'type': 'ir.actions.act_window'
            }
    
    @api.multi
    def calcular(self):         
        #blanquear movimienos contables para niif antes de ejecutar el proceso
        #self._cr.execute(" UPDATE account_move_line SET account_niif_id = NULL WHERE date between '%s' AND '%s' "%('2010-01-01','2020-12-31'))
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
        dict1 = {}
        move_ids = []
        
        company_id = self.company_id.id        
        accounts = [x.id for x in account_obj.search([('type','in',['receivable']),('company_id','=',company_id),('niif','=',False),('deterioro_cartera','=',True)])]
        if not accounts:
            raise osv.except_osv(_('Error !'), _("No existen cuentas por cobrar seleccionadas paraelproceso de deterioro de cartera, por favor marcar aquellas cuentas que segun la politica de la compañia apliquen para este proceso."))
        
        date = self.date
        
        type_customer = self.politica_id.type_customer.id
        
        self._cr.execute(''' DELETE FROM account_move_line_deterioro WHERE deterioro_id = %s''',(self.id,))
    
        for politica in self.politica_id.line_ids:      
            print "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            print politica.name
            print type_customer
            print ""
            date_start = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=politica.amount_start)
            date_end = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=politica.amount_end)
            print date_start
            print date_end
            print ""                
            self._cr.execute('''SELECT 
                                    account_move_line.id,
                                    account_move_line.name,
                                    account_move_line.ref,
                                    account_move_line.ref1,
                                    account_move_line.partner_id,
                                    account_move_line.account_id,
                                    account_move_line.account_niif_id,
                                    account_move_line.date,
                                    account_move_line.date_maturity,
                                    account_move_line.reconcile_partial_id,
                                    account_move_line.reconcile_id,
                                    account_move_line.analytic_account_id,
                                    SUM(account_move_line.debit - account_move_line.credit)
                                FROM                 
                                    account_move_line,
                                    res_partner
                                WHERE  
                                    account_move_line.account_id in %s
                                    AND account_move_line.date_maturity <= %s
                                    AND account_move_line.date_maturity >= %s
                                    AND account_move_line.date <= %s
                                    AND account_move_line.company_id = %s
                                    AND account_move_line.debit > 0.0
                                    AND account_move_line.partner_id = res_partner.id
                                    AND res_partner.type_customer = %s
                                GROUP BY
                                    account_move_line.id,
                                    account_move_line.name,
                                    account_move_line.ref,
                                    account_move_line.ref1,
                                    account_move_line.partner_id,
                                    account_move_line.account_id,
                                    account_move_line.account_niif_id,
                                    account_move_line.date,
                                    account_move_line.date_maturity,
                                    account_move_line.reconcile_partial_id,
                                    account_move_line.analytic_account_id''',
                            (tuple(accounts),date_start,date_end,date,company_id,type_customer))   
            result1 = self._cr.fetchall()
            print "-------------"
            print result1
            print "-------------"
            if result1:
                for res in result1:
                    move_id = res[0]                
                    name = res[3] or res[1]
                    move_ref = res[2] or 'Indefinido'
                    partner_id = res[4] or False              
                    account_id = res[5] or False
                    account_niif_id = res[6] or False
                    date_move = res[7]
                    date_maturity = res[8]
                    reconcile_partial_id = res[9] or False
                    reconcile_id = res[10] or False
                    analytic_account_id = res[11] or False
                    valor_residual = float(res[12] or 0.0)
                    cartera_amount=0.0
                    
                    date_maturity_calc = datetime.strptime(date_maturity, DEFAULT_SERVER_DATE_FORMAT).date()
                    date_line = datetime.strptime(date, DEFAULT_SERVER_DATE_FORMAT).date()
                    days = (date_line - date_maturity_calc).days
                    print "++++++++++++++++++"
                    print days
                    print "++++++++++++++++++"
                    
                    if self.politica_id.type_calc == 'tercero':
                        key = (partner_id)
                    else:
                        key = (partner_id,move_id)
                    
                    
                    self._cr.execute('''SELECT
                                            SUM(debit-credit)
                                        FROM
                                            account_move_line
                                        WHERE  
                                            account_id = %s
                                            AND (move_deterioro_id = %s OR move_recuperable_id = %s)
                                            AND state = 'valid' ''',
                                (account_niif_id,move_id,move_id)) 
                    result = self._cr.fetchall()[0]
                    if result:
                        cartera_amount = result[0]
                        if isinstance(cartera_amount, (list, tuple)):
                            cartera_amount = float(cartera_amount[0] or 0.0)
                        else:
                            cartera_amount = float(cartera_amount or 0.0)
                    amount_history = cartera_amount
                    
                    print "wwwwwwwwwwwwwwwww"
                    print amount_history
                    print ""

                    if reconcile_id:
                        self._cr.execute('''SELECT
                                            SUM(debit - credit)
                                        FROM
                                            account_move_line
                                        WHERE
                                            reconcile_id = %s AND id != %s AND date <= %s''',
                                    (reconcile_id,move_id,date))   
                        result2 = self._cr.fetchall()
                        for res in result2:
                            valor_residual += float(res[0] or 0.0)
                            
                    elif reconcile_partial_id:
                        self._cr.execute('''SELECT
                                            SUM(debit - credit)
                                        FROM
                                            account_move_line
                                        WHERE
                                            reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                    (reconcile_partial_id,move_id,date))   
                        result2 = self._cr.fetchall()
                        for res in result2:
                            valor_residual += float(res[0] or 0.0)
                    
                    if valor_residual > 0.0:
                        if key in dict:
                            vals = {'amount_history':amount_history, 'account_niif_id':account_niif_id, 'politica':politica, 'move_id':move_id, 'name':name, 'move_ref':move_ref, 'partner_id':partner_id, 'account_id':account_id, 'date_move':date_move, 'date_maturity':date_maturity, 'valor_residual': valor_residual, 'analytic_account_id': analytic_account_id}
                            dict[key].append(vals)
                            if politica.deterioro > dict1[key]['deterioro']:
                                dict1[key].update({'deterioro':politica.deterioro})
                        else:
                            dict1[key] = ({'deterioro':politica.deterioro})
                            dict[key] = [] 
                            dict[key].append({'amount_history':amount_history, 'account_niif_id':account_niif_id, 'politica':politica, 'move_id':move_id, 'name':name, 'move_ref':move_ref, 'partner_id':partner_id, 'account_id':account_id, 'date_move':date_move, 'date_maturity':date_maturity, 'valor_residual': valor_residual, 'analytic_account_id': analytic_account_id})                        
                    elif valor_residual == 0.0 and amount_history < 0.0:
                        
                        self._cr.execute(''' UPDATE account_move_line SET cartera_ok=False WHERE id=%s ''',(move_id,))
                        
                        amount = abs(amount_history)
                        self._cr.execute('''INSERT INTO account_move_line_deterioro (move_id,name,ref,date,date_maturity,days,account_id,politica_id,partner_id,analytic_account_id,amount_history,type,amount_start,cartera_politica,ok,deterioro_id,company_id,amount) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        (move_id,name,move_ref,date_move,date_maturity,days,account_id,politica.id,partner_id,analytic_account_id or None ,amount_history,'recuperacion',valor_residual,politica.deterioro,True, self.id, company_id, amount))                        
                        move_ids.append(self._cr.fetchone()[0])
        
        for vals in dict:            
            deterioro = dict1[vals]['deterioro']
            if deterioro == 0.0:
                continue
            print "--------------------------------------------"
            politica_line = self.env['politica.cartera.line'].search([('politica_id','=',self.politica_id.id),('deterioro','=',deterioro)])
            for move in dict[vals]:
                print ""
                print move
                print ""
                move_id = move['move_id']
                account_niif_id = move['account_niif_id']
                name = move['name']
                move_ref = move['move_ref']
                partner_id = move['partner_id']
                valor_residual = move['valor_residual']
                amount_history = move['amount_history']
                
                analytic_account_id = move['analytic_account_id']                
                
                
                if self.politica_id.type == 'periodo':   
                    days = politica_line.amount_end
                else:
                    date_maturity_calc = datetime.strptime(move['date_maturity'], DEFAULT_SERVER_DATE_FORMAT).date()
                    date_line = datetime.strptime(date, DEFAULT_SERVER_DATE_FORMAT).date()
                    days = (date_line - date_maturity_calc).days
                
                
                
                if self.politica_id.type_interes == 'anual':
                    amount = valor_residual*((float(politica_line.deterioro)/36000)*days)
                elif self.politica_id.type_interes == 'mensual':
                    amount = valor_residual*((float(politica_line.deterioro)/3000)*days)
                else:
                    amount = valor_residual*((float(politica_line.deterioro)/100))
                
                                                    
                amount_start = valor_residual
                amount_aplicar = amount + amount_history
                amount_end = amount_start - amount
                
                
                
                if amount_aplicar > 0.0:                    
                    type = 'deterioro'
                elif amount_aplicar < 0.0:
                    type = 'recuperacion'
                else:
                    continue
                    
                self._cr.execute(''' UPDATE account_move_line SET cartera_ok=False WHERE id=%s ''',(move_id,))
                
                self._cr.execute('''INSERT INTO account_move_line_deterioro (move_id,name,ref,date,date_maturity,days,account_id,politica_id,partner_id,analytic_account_id,amount_history,type,amount_start,cartera_politica,ok,deterioro_id,company_id,amount,amount_end,amount_aplicar) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                (move_id,name,move_ref,date_move,date_maturity,days,account_id,politica_line.id,partner_id,analytic_account_id or None ,amount_history,type,valor_residual,politica_line.deterioro, True,self.id, company_id, amount,amount_end,amount_aplicar))                        
                move_ids.append(self._cr.fetchone()[0])
        
        
        
        domain = [('id','in',move_ids)]
        return {    
            'domain': domain,
            'name': 'Provision Dterioro y Recuperacion',
            'view_type': 'form',
            'view_mode': 'tree,graph',
            'view_id': False,
            'res_model': 'account.move.line.deterioro',
            'type': 'ir.actions.act_window'
            }
    
    
    @api.multi
    def confirmar(self):
        sequence_obj = self.env['ir.sequence']
        number_seq = sequence_obj.get('cartera.change')
        self.write({'state': 'confirmed','name':number_seq})   
        return True
    
    
    @api.multi
    def borrador(self):
        self.write({'state':'draft'})        
        return True
    
    
    
    @api.multi
    def recalcular(self):
        if self.search([('date','>',self.date),('state','=','done')]):
            raise osv.except_osv(_('Error !'), _("No puede recalcular un proceso de deterioro y recuperacion de cartera con un proceso de meses posteriores ya calculado."))
        
        if self.period_id.state == "done":
            raise osv.except_osv(_('Error !'), _("No puede recalcular un proceso de deterioro y recuperacion de cartera que afecte un periodo contable cerrrado, por favor consulte con el area responsable"))
        
        if self.id:
            self._cr.execute("DELETE FROM account_move WHERE cartera_process=%s", (self.id,))
            
        self._cr.commit()                
        if self.move_ids:
            for move in self.move_ids:
                move.write({'deterioro_process': 'RECALCULO'+'-'+self.name+'-'+str(fields.datetime.now())})
                       
        return self.write({'state': 'confirmed'})
        
    
    @api.multi
    def contabilizar(self):
        #blanquear movimienos contables para niif antes de ejecutar el proceso
        #self._cr.execute(" UPDATE account_move_line SET account_niif_id = NULL WHERE date between '%s' AND '%s' "%('2010-01-01','2020-12-31'))
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
        dict1 = {}
        move_ids = []
        
        company_id = self.company_id.id        
        accounts = [x.id for x in account_obj.search([('type','in',['receivable']),('company_id','=',company_id),('niif','=',False)])]
        date = self.date
        
        move_vals = {
            'name': self.name,
            'ref': self.name,
            'journal_id': self.journal_id.id,
            'date': date,
            'period_id': self.period_id.id,
            'company': company_id,
            'cartera_process': self.id,
            }
        move_deterioro = self.env['account.move'].create(move_vals)
        type_customer = self.politica_id.type_customer.id
        for politica in self.politica_id.line_ids:            
            date_start = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=politica.amount_start)
            date_end = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=politica.amount_end)
            self._cr.execute('''SELECT 
                                    account_move_line.id,
                                    account_move_line.name,
                                    account_move_line.ref,
                                    account_move_line.ref1,
                                    account_move_line.partner_id,
                                    account_move_line.account_id,
                                    account_move_line.account_niif_id,
                                    account_move_line.date,
                                    account_move_line.date_maturity,
                                    account_move_line.reconcile_partial_id,
                                    account_move_line.reconcile_id,
                                    account_move_line.analytic_account_id,
                                    SUM(account_move_line.debit - account_move_line.credit)
                                    
                                FROM                 
                                    account_move_line,
                                    res_partner
                                WHERE  
                                    account_move_line.account_id in %s
                                    AND account_move_line.date_maturity <= %s
                                    AND account_move_line.date_maturity >= %s
                                    AND account_move_line.date <= %s
                                    AND account_move_line.company_id = %s
                                    AND account_move_line.debit > 0.0
                                    AND account_move_line.partner_id = res_partner.id
                                    AND res_partner.type_customer = %s
                                    AND account_move_line.cartera_ok = False
                                GROUP BY
                                    account_move_line.id,
                                    account_move_line.name,
                                    account_move_line.ref,
                                    account_move_line.ref1,
                                    account_move_line.partner_id,
                                    account_move_line.account_id,
                                    account_move_line.account_niif_id,
                                    account_move_line.date,
                                    account_move_line.date_maturity,
                                    account_move_line.reconcile_partial_id,
                                    account_move_line.analytic_account_id''',
                            (tuple(accounts),date_start,date_end,date,company_id,type_customer))   
            result1 = self._cr.fetchall()
            for res in result1:
                move_id = res[0]                
                name = res[3] or res[1]
                move_ref = res[2] or 'Indefinido'
                partner_id = res[4] or False              
                account_id = res[5] or False
                account_niif_id = res[6] or False
                date_move = res[7]
                date_maturity = res[8]
                reconcile_partial_id = res[9] or False
                reconcile_id = res[10] or False
                analytic_account_id = res[11] or False
                valor_residual = float(res[12] or 0.0)
                cartera_amount=0.0
                
                self._cr.execute('''SELECT
                                        SUM(debit-credit)
                                    FROM
                                        account_move_line
                                    WHERE  
                                        account_id = %s
                                        AND (move_deterioro_id = %s OR move_recuperable_id = %s)
                                        AND state = 'valid' ''',
                            (account_niif_id,move_id,move_id)) 
                result = self._cr.fetchall()[0]
                if result:
                    cartera_amount = result[0]
                    if isinstance(cartera_amount, (list, tuple)):
                        cartera_amount = float(cartera_amount[0] or 0.0)
                    else:
                        cartera_amount = float(cartera_amount or 0.0)
                cartera_amount = cartera_amount
                
                if self.politica_id.type_calc == 'tercero':
                    key = (partner_id)
                else:
                    key = (partner_id,move_id)
                        
                if reconcile_id:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_id = %s AND id != %s AND date <= %s''',
                                (reconcile_id,move_id,date))   
                    result2 = self._cr.fetchall()
                    for res in result2:
                        valor_residual += float(res[0] or 0.0)
                        
                elif reconcile_partial_id:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                (reconcile_partial_id,move_id,date))   
                    result2 = self._cr.fetchall()
                    for res in result2:
                        valor_residual += float(res[0] or 0.0)
                
                if valor_residual > 0.0:
                    if key in dict:
                        vals = {'cartera_amount':cartera_amount, 'account_niif_id':account_niif_id, 'politica':politica, 'move_id':move_id, 'name':name, 'move_ref':move_ref, 'partner_id':partner_id, 'account_id':account_id, 'date_move':date_move, 'date_maturity':date_maturity, 'valor_residual': valor_residual, 'analytic_account_id': analytic_account_id}
                        dict[key].append(vals)
                        if politica.deterioro > dict1[key]['deterioro']:
                            dict1[key].update({'deterioro':politica.deterioro})
                    else:
                        dict1[key] = ({'deterioro':politica.deterioro})
                        dict[key] = [] 
                        dict[key].append({'cartera_amount':cartera_amount, 'account_niif_id':account_niif_id, 'politica':politica, 'move_id':move_id, 'name':name, 'move_ref':move_ref, 'partner_id':partner_id, 'account_id':account_id, 'date_move':date_move, 'date_maturity':date_maturity, 'valor_residual': valor_residual, 'analytic_account_id': analytic_account_id})                        
                elif valor_residual == 0.0 and cartera_amount < 0.0:                    
                    #"wwwwwwww  DEBITO wwwwwwwwwww"
                    self._cr.execute('''INSERT INTO account_move_line (cartera_residual,cartera_old,cartera_politica,politica_id,account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,cartera_id,move_recuperable_id,journal_id,period_id,company_id,state) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (valor_residual,cartera_amount,politica.deterioro,politica.id,account_niif_id,account_niif_id,date,name,move_ref,date,partner_id,0.0,abs(cartera_amount),analytic_account_id or None,move_deterioro.id,self.id,move_id,self.journal_id.id,self.period_id.id,company_id,'valid'))
                    
                    #"wwwwwwww  CREDITO wwwwwwwwwww"
                    self._cr.execute('''INSERT INTO account_move_line (cartera_residual,cartera_old,cartera_politica,politica_id,account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,cartera_id,move_recuperable_id,journal_id,period_id,company_id,state) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (valor_residual,cartera_amount,politica.deterioro,politica.id,politica.account_recuperable_id.id,politica.account_recuperable_id.id,date,name,move_ref,date,partner_id,abs(cartera_amount),0.0,analytic_account_id or None,move_deterioro.id,self.id,move_id,self.journal_id.id, self.period_id.id,company_id,'valid'))
                    move_ids.append(move_id)
        
        for vals in dict:            
            deterioro = dict1[vals]['deterioro']
            if deterioro == 0.0:
                continue
            politica_line = self.env['politica.cartera.line'].search([('politica_id','=',self.politica_id.id),('deterioro','=',deterioro)])
            for move in dict[vals]:
                move_id = move['move_id']
                account_niif_id = move['account_niif_id']
                name = move['name']
                move_ref = move['move_ref']
                partner_id = move['partner_id']
                valor_residual = move['valor_residual']
                cartera_amount = move['cartera_amount']
                
                analytic_account_id = move['analytic_account_id']
                
                if self.politica_id.type == 'periodo':     
                    days = politica_line.amount_end
                else:
                    date_maturity_calc = datetime.strptime(move['date_maturity'], DEFAULT_SERVER_DATE_FORMAT).date()
                    date_line = datetime.strptime(date, DEFAULT_SERVER_DATE_FORMAT).date()
                    days = (date_line - date_maturity_calc).days                
                
                if self.politica_id.type_interes == 'anual':
                    amount = valor_residual*((float(politica_line.deterioro)/36000)*days)
                elif self.politica_id.type_interes == 'mensual':
                    amount = valor_residual*((float(politica_line.deterioro)/3000)*days)
                else:
                    amount = valor_residual*((float(politica_line.deterioro)/100))
                                                                                 
                amount = amount + cartera_amount
                
                
                print "xxxxxxxxxxxxx"
                print account_niif_id
                move_ids.append(move_id)
                if amount > 0.0:
                    #"wwwwwwww  DEBITO wwwwwwwwwww"
                    self._cr.execute('''INSERT INTO account_move_line (cartera_residual,cartera_old,cartera_politica,politica_id,account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,cartera_id,move_deterioro_id,journal_id,period_id,company_id,state) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (valor_residual,cartera_amount,deterioro,politica_line.id,politica_line.account_deterioro_id.id,politica_line.account_deterioro_id.id,date,name,move_ref,date,partner_id,0.0,amount,analytic_account_id or None,move_deterioro.id,self.id,move_id,self.journal_id.id,self.period_id.id,company_id,'valid'))
                    
                    #"wwwwwwww  CREDITO wwwwwwwwwww"
                    self._cr.execute('''INSERT INTO account_move_line (cartera_residual,cartera_old,cartera_politica,politica_id,account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,cartera_id,move_deterioro_id,journal_id,period_id,company_id,state) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (valor_residual,cartera_amount,deterioro,politica_line.id,account_niif_id,account_niif_id,date,name,move_ref,date,partner_id,amount,0.0,analytic_account_id or None,move_deterioro.id,self.id,move_id,self.journal_id.id, self.period_id.id,company_id,'valid'))
                elif amount < 0.0:
                    #"wwwwwwww  DEBITO wwwwwwwwwww"
                    self._cr.execute('''INSERT INTO account_move_line (cartera_residual,cartera_old,cartera_politica,politica_id,account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,cartera_id,move_recuperable_id,journal_id,period_id,company_id,state) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (valor_residual,cartera_amount,deterioro,politica_line.id,account_niif_id,account_niif_id,date,name,move_ref,date,partner_id,0.0,abs(amount),analytic_account_id or None,move_deterioro.id,self.id,move_id,self.journal_id.id,self.period_id.id,company_id,'valid'))
                    
                    #"wwwwwwww  CREDITO wwwwwwwwwww"
                    self._cr.execute('''INSERT INTO account_move_line (cartera_residual,cartera_old,cartera_politica,politica_id,account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,cartera_id,move_recuperable_id,journal_id,period_id,company_id,state) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (valor_residual,cartera_amount,deterioro,politica_line.id,politica_line.account_recuperable_id.id,politica_line.account_recuperable_id.id,date,name,move_ref,date,partner_id,abs(amount),0.0,analytic_account_id or None,move_deterioro.id,self.id,move_id,self.journal_id.id, self.period_id.id,company_id,'valid'))
                    move_ids.append(move_id)
                self._cr.execute(''' UPDATE account_move_line SET politica_id=%s, cartera_politica=%s WHERE id = %s''',(politica_line.id,deterioro,move_id)) 
        if move_ids:            
            move_ids = list(set(move_ids))
            for move in move_ids:
                move_obj.browse(move).write({'deterioro_process': self.name+'-'+str(fields.datetime.now())})
        move_deterioro.post()
        self._cr.commit()
        
        return self.write({'state':'done', 'move_ids': [(6, 0, [x for x in move_ids])]})
#
