# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
from openerp import models, fields, api, _
from openerp.osv import osv
import openerp.addons.decimal_precision as dp

class account_report_cartera_avancys_line(models.Model):
    _name = "account.report.cartera.avancys.line"
    _order = "partner_id,account_id,fecha_vencimiento"
    
    invoice = fields.Char(string='Factura')
    supplier_invoice = fields.Char(string='Factura Proveedor')
    partner_id = fields.Many2one('res.partner', string='Tercero')
    company_id = fields.Many2one('res.company', string='Compania')
    account_id = fields.Many2one('account.account', string='Cuenta')
    fecha_elaboracion = fields.Date(string='Fecha de elaboracion')
    fecha_vencimiento = fields.Date(string='Fecha de vencimiento')
    numero_dias_expedicion = fields.Integer(string='Numero de dias de Expedicion')
    numero_dias_vencidos = fields.Integer(string='Numero de dias Vencidos')
    en_mora = fields.Boolean(string='En Mora')
    valor_facturado = fields.Float(string='Valor Facturado', digits=dp.get_precision('Account'))
    valor_residual = fields.Float(string='Valor Adeudado', digits=dp.get_precision('Account'))
    currency_id = fields.Many2one('res.currency', string='Moneda')
    currency_facturado = fields.Float(string='Valor Facturado Currency', digits=dp.get_precision('Account'))
    currency_residual = fields.Float(string='Valor Adeudado Currency', digits=dp.get_precision('Account'))
    currency_facturado_rate = fields.Float(string='Valor Facturado Currency Rate', digits=dp.get_precision('Account'))
    currency_residual_rate = fields.Float(string='Valor Adeudado Currency Rate', digits=dp.get_precision('Account'))
    date = fields.Date(string="Fecha de Corte")
    date_emision = fields.Datetime(string="Fecha Emision Informe")
    rango = fields.Char(string='Rango')
    type = fields.Selection([('cartera', 'Cartera'),('tesoreria', 'Tesoreria')], string='Consulta')
    name = fields.Char(string='Nombre')

class account_report_cartera_avancys_report_wizard(models.TransientModel):
    _name = "wizard.report.cartera.avancys.report"
    
    @api.multi
    def imprimir_pdf(self):
        self._cr.execute('''SELECT id FROM account_report_cartera_avancys_line order by fecha_vencimiento''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.cartera.avancys.line'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.template_reporte_balance',
        'datas': datas,
        }
        
    @api.multi
    def imprimir_calc_terceros(self): 
        self._cr.execute('''SELECT id FROM account_report_cartera_avancys_line order by fecha_vencimiento''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.cartera.avancys.line'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.reporte_balance_aeroo',
        'report_type': 'aeroo',
        'datas': datas,
        }
        
    @api.multi
    def imprimir_calc_sin_terceros(self): 
        self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql WHERE partner_id is NULL order by code''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.cartera.avancys.line'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.reporte_balance_aeroo',
        'report_type': 'aeroo',
        'datas': datas,
        }
        
class account_report_cartera_avancys(models.TransientModel):
    _name = "account.report.cartera.avancys"
    
    @api.onchange('date', 'currency_id')
    def _rate(self):
        if self.date and self.currency_id:
            rate = 0.0
            rate = self.env['res.currency.rate'].search([('date_sin_hora','=',self.date),('currency_id','=',self.currency_id.id)]).rate_inv
            if rate == 0.0:
                raise osv.except_osv(_('Error !'), _("No existe un una tasa configurada para la fecha '%s' en la divisa '%s'") % (self.date,self.currency_id.name))
            self.rate = rate
    
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts', required=True, domain = [('parent_id','=',False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    account_ids = fields.Many2many('account.account', string='Cuentas', domain = [('type','!=','view'),'|',('type','=','payable'),('type','=','receivable')])
    journal_ids = fields.Many2many('account.journal', string='Diarios')
    partner_ids = fields.Many2many('res.partner', string='Terceros')
    date = fields.Date(string="Fecha de Corte",required=True)
    type = fields.Selection([('cartera', 'Cartera'),('tesoreria', 'Tesoreria')], string='Consulta', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda')
    rate = fields.Float(string='Tasa', digits=dp.get_precision('Exchange Precision'), default=1)
    print_report = fields.Selection([('print_basico', 'Basico Excel'),('print', 'Excel'),('analizar', 'Analizar')], string='Visualizacion', required=True, default='analizar')
    
    
    @api.multi
    def calcular(self):        
        report_line_obj = self.env['account.report.cartera.avancys.line']
        account_obj = self.env['account.account']
        partner_obj = self.env['res.partner']
        conciliaciones=[]
        parciales=[]
        
        tolerancia = 1
        company_id = self.company_id.id
        cr = self._cr
        cr.execute(''' DELETE FROM account_report_cartera_avancys_line''')
        date = self.date
        accounts = 0
        partners = 0
        date_cut = datetime.strptime(self.date, '%Y-%m-%d')
        
        inicio = datetime.now() 

        if self.type == 'cartera':
            partners = [x.id for x in partner_obj.search([('active','=',True),('customer','=',True)])]
            if self.account_ids:
                accounts = [x.id for x in self.account_ids.filtered(lambda x: x.type in ['receivable'])]
            else:
                accounts = [x.id for x in account_obj.search([('type','in',['receivable']),('company_id','=',company_id)])]
        elif self.type == 'tesoreria':
            partners = [x.id for x in partner_obj.search([('active','=',True),('supplier','=',True)])]
            if self.account_ids:
                accounts = [x.id for x in self.account_ids.filtered(lambda x: x.type in ['payable'])]
            else:
                accounts = [x.id for x in account_obj.search([('type','in',['payable']),('company_id','=',company_id)])]
        
        if self.partner_ids:
            partners = [x.id for x in self.partner_ids]
                
        print "***************  CALCULA LOS MOVIMIENTOS VIGENTES ***************"
        self._cr.execute('''SELECT 
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_move_line.amount_currency,                                
                                SUM(account_move_line.debit - account_move_line.credit),
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date                                                            
                            FROM                                
                                (
                                account_move_line
                                LEFT JOIN
                                account_invoice
                                ON account_move_line.move_id = account_invoice.move_id
                                LEFT JOIN
                                account_move_reconcile AS reconcile
                                ON account_move_line.reconcile_id = reconcile.id
                                LEFT JOIN
                                account_move_reconcile AS reconcile_partial
                                ON account_move_line.reconcile_partial_id = reconcile_partial.id
                                )                                
                            WHERE  
                                account_move_line.account_id in %s
                                AND account_move_line.date_maturity >= %s
                                AND account_move_line.date <= %s
                                AND account_move_line.company_id = %s
                                AND account_move_line.partner_id in %s
                                AND account_move_line.state = 'valid'
                            GROUP BY
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                account_move_line.amount_currency,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date
                            ORDER BY
                                account_move_line.date''',
                        (tuple(accounts),date,date,company_id,tuple(partners)))
        result = self._cr.fetchall()

        for res in result:
            move_id = res[0]                
            name = res[3] or res[1]
            move_ref = res[2] or 'Indefinido'
            partner_id = res[4] or False              
            account_id = res[5] or False
            date_move = res[6]
            date_maturity = res[7]
            currency_id = res[8] or self.company_id.currency_id.id
            reconcile_partial_id = res[9] or False
            reconcile_id = res[10] or False
            invoice = res[11] or 'Indefinido'
            currency_facturado = float(res[12] or 0.0)
            currency_residual = float(res[12] or 0.0)
            valor_facturado = float(res[13])
            valor_residual = float(res[13])
            supplier_invoice = res[14] or 'Indefinido'
            date_reconcile = res[15] or False
            date_partial = res[16] or False

            num_exped = (date_cut - (datetime.strptime(date_move, '%Y-%m-%d') if date_move else False)).days if date_move else 0
            num_venc = (date_cut - (datetime.strptime(date_maturity, '%Y-%m-%d') if date_maturity else False)).days if date_maturity else 0

            if (self.type == 'cartera' and valor_residual <= 0.0) or (self.type == 'tesoreria' and valor_residual >= 0.0):
                valor_facturado=0.0
                if reconcile_id  and date_reconcile <= date or reconcile_partial_id and date_partial <= date:
                    continue
            
            if reconcile_id:
                if reconcile_id in conciliaciones:
                    valor_residual=0.0
                else:                    
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_id = %s AND id != %s AND date <= %s''',
                                (reconcile_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:                    
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            conciliaciones.append(reconcile_id)
            
            
            if reconcile_partial_id and not reconcile_id:
                if reconcile_partial_id in parciales:
                    valor_residual=0.0
                else:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                (reconcile_partial_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            parciales.append(reconcile_partial_id)
            
            if abs(valor_residual) > tolerancia:
                cr.execute('''insert into account_report_cartera_avancys_line (supplier_invoice,company_id,invoice,name,account_id,
                    fecha_elaboracion,fecha_vencimiento,en_mora,valor_facturado,valor_residual,partner_id,date,currency_id,currency_facturado,
                    currency_residual,rango,date_emision,type,numero_dias_expedicion,numero_dias_vencidos) values
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''', (supplier_invoice,company_id,invoice,name,
                    account_id,date_move,date_maturity,False,valor_facturado, valor_residual,partner_id or None,date,
                    currency_id or None, currency_facturado,currency_residual, '1. A TIEMPO',datetime.now(),self.type,num_exped,num_venc))
            
        
        print "***************  CALCULA LOS MOVIMIENTOS VENCIDOS 01 - 30 ***************"       
        date_30 = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=30)
        self._cr.execute('''SELECT 
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_move_line.amount_currency,                                
                                SUM(account_move_line.debit - account_move_line.credit),
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date      
                            FROM                                
                                (
                                account_move_line
                                LEFT JOIN
                                account_invoice
                                ON account_move_line.move_id = account_invoice.move_id
                                LEFT JOIN
                                account_move_reconcile AS reconcile
                                ON account_move_line.reconcile_id = reconcile.id
                                LEFT JOIN
                                account_move_reconcile AS reconcile_partial
                                ON account_move_line.reconcile_partial_id = reconcile_partial.id
                                )
                            WHERE  
                                account_move_line.account_id in %s
                                AND account_move_line.date_maturity < %s
                                AND account_move_line.date_maturity >= %s
                                AND account_move_line.date <= %s
                                AND account_move_line.company_id = %s
                                AND account_move_line.partner_id in %s
                                AND account_move_line.state = 'valid'
                            GROUP BY
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                account_move_line.amount_currency,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_invoice.supplier_invoice,
                                reconcile.create_date
                            ORDER BY
                                account_move_line.date''',
                        (tuple(accounts),date,date_30,date,company_id,tuple(partners)))   
        result = self._cr.fetchall()
        print "----------"
        print len(result)
        for res in result:
            move_id = res[0]                
            name = res[3] or res[1]
            move_ref = res[2] or 'Indefinido'
            partner_id = res[4] or False              
            account_id = res[5] or False
            date_move = res[6]
            date_maturity = res[7]
            currency_id = res[8] or self.company_id.currency_id.id
            reconcile_partial_id = res[9] or False
            reconcile_id = res[10] or False
            invoice = res[11] or 'Indefinido'
            currency_facturado = float(res[12] or 0.0)
            currency_residual = float(res[12] or 0.0)
            valor_facturado = float(res[13])
            valor_residual = float(res[13])
            supplier_invoice = res[14] or 'Indefinido'
            date_reconcile = res[15] or False
            date_partial = res[16] or False

            num_exped = (date_cut - (datetime.strptime(date_move, '%Y-%m-%d') if date_move else False)).days if date_move else 0
            num_venc = (date_cut - (datetime.strptime(date_maturity, '%Y-%m-%d') if date_maturity else False)).days if date_maturity else 0
                        
            if (self.type == 'cartera' and valor_residual <= 0.0) or (self.type == 'tesoreria' and valor_residual >= 0.0):
                valor_facturado=0.0
                if reconcile_id  and date_reconcile <= date or reconcile_partial_id and date_partial <= date:
                    continue
            
            if reconcile_id:
                if reconcile_id in conciliaciones:
                    valor_residual=0.0
                else:                    
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_id = %s AND id != %s AND date <= %s''',
                                (reconcile_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:                    
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            conciliaciones.append(reconcile_id)
            
            
            if reconcile_partial_id and not reconcile_id:
                if reconcile_partial_id in parciales:
                    valor_residual=0.0
                else:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                (reconcile_partial_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            parciales.append(reconcile_partial_id)
            
            if abs(valor_residual) > tolerancia:
                cr.execute('''insert into account_report_cartera_avancys_line (supplier_invoice,company_id,invoice,name,
                    account_id,fecha_elaboracion,fecha_vencimiento,en_mora,valor_facturado,valor_residual,partner_id,date,currency_id,
                    currency_facturado,currency_residual,rango,date_emision,type,numero_dias_expedicion,numero_dias_vencidos) values
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (supplier_invoice,company_id,invoice,name,
                    account_id,date_move,date_maturity,True,valor_facturado,valor_residual,partner_id or None,date,currency_id or None,
                    currency_facturado,currency_residual,'2. (1 - 30)',datetime.now(),self.type,num_exped,num_venc))
                    
        print "***************  CALCULA LOS MOVIMIENTOS VENCIDOS 31 - 60 ***************"
        date_60 = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=60)
        self._cr.execute('''SELECT 
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_move_line.amount_currency,                                
                                SUM(account_move_line.debit - account_move_line.credit),
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date
                            FROM                                
                                (
                                account_move_line
                                LEFT JOIN
                                account_invoice
                                ON account_move_line.move_id = account_invoice.move_id
                                LEFT JOIN
                                account_move_reconcile AS reconcile
                                ON account_move_line.reconcile_id = reconcile.id
                                LEFT JOIN
                                account_move_reconcile AS reconcile_partial
                                ON account_move_line.reconcile_partial_id = reconcile_partial.id
                                )
                            WHERE  
                                account_move_line.account_id in %s
                                AND account_move_line.date_maturity < %s
                                AND account_move_line.date_maturity >= %s
                                AND account_move_line.date <= %s
                                AND account_move_line.company_id = %s
                                AND account_move_line.partner_id in %s
                                AND account_move_line.state = 'valid'
                            GROUP BY
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                account_move_line.amount_currency,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date
                            ORDER BY
                                account_move_line.date''',
                        (tuple(accounts),date_30,date_60,date,company_id,tuple(partners)))   
        result = self._cr.fetchall()
        print "----------"
        print len(result)
        for res in result:
            move_id = res[0]                
            name = res[3] or res[1]
            move_ref = res[2] or 'Indefinido'
            partner_id = res[4] or False              
            account_id = res[5] or False
            date_move = res[6]
            date_maturity = res[7]
            currency_id = res[8] or self.company_id.currency_id.id
            reconcile_partial_id = res[9] or False
            reconcile_id = res[10] or False
            invoice = res[11] or 'Indefinido'
            currency_facturado = float(res[12] or 0.0)
            currency_residual = float(res[12] or 0.0)
            valor_facturado = float(res[13])
            valor_residual = float(res[13])
            supplier_invoice = res[14] or 'Indefinido'
            date_reconcile = res[15] or False
            date_partial = res[16] or False

            num_exped = (date_cut - (datetime.strptime(date_move, '%Y-%m-%d') if date_move else False)).days if date_move else 0
            num_venc = (date_cut - (datetime.strptime(date_maturity, '%Y-%m-%d') if date_maturity else False)).days if date_maturity else 0
                        
            if (self.type == 'cartera' and valor_residual <= 0.0) or (self.type == 'tesoreria' and valor_residual >= 0.0):
                valor_facturado=0.0
                if reconcile_id  and date_reconcile <= date or reconcile_partial_id and date_partial <= date:
                    continue
            
            if reconcile_id:
                if reconcile_id in conciliaciones:
                    valor_residual=0.0
                else:                    
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_id = %s AND id != %s AND date <= %s''',
                                (reconcile_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:                    
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            conciliaciones.append(reconcile_id)
            
            
            if reconcile_partial_id and not reconcile_id:
                if reconcile_partial_id in parciales:
                    valor_residual=0.0
                else:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                (reconcile_partial_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            parciales.append(reconcile_partial_id)
            
            if abs(valor_residual) > tolerancia:
                cr.execute('''insert into account_report_cartera_avancys_line (supplier_invoice,company_id,invoice,name,
                    account_id,fecha_elaboracion,fecha_vencimiento,en_mora,valor_facturado,valor_residual,partner_id,date,
                    currency_id,currency_facturado,currency_residual,rango,date_emision,type,numero_dias_expedicion,numero_dias_vencidos) values
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (supplier_invoice,company_id,invoice,name,
                    account_id,date_move,date_maturity,True,valor_facturado,valor_residual,partner_id or None,date,currency_id or None,
                    currency_facturado,currency_residual,'3. (31 - 60)',datetime.now(),self.type,num_exped,num_venc))
                
        print "***************  CALCULA LOS MOVIMIENTOS VENCIDOS 61 - 90 ***************"
        date_90 = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=90)
        self._cr.execute('''SELECT 
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_move_line.amount_currency,                                
                                SUM(account_move_line.debit - account_move_line.credit),
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date                          
                            FROM                                
                                (
                                account_move_line
                                LEFT JOIN
                                account_invoice
                                ON account_move_line.move_id = account_invoice.move_id
                                LEFT JOIN
                                account_move_reconcile AS reconcile
                                ON account_move_line.reconcile_id = reconcile.id
                                LEFT JOIN
                                account_move_reconcile AS reconcile_partial
                                ON account_move_line.reconcile_partial_id = reconcile_partial.id
                                )
                            WHERE  
                                account_move_line.account_id in %s
                                AND account_move_line.date_maturity < %s
                                AND account_move_line.date_maturity >= %s
                                AND account_move_line.date <= %s
                                AND account_move_line.company_id = %s
                                AND account_move_line.partner_id in %s
                                AND account_move_line.state = 'valid'
                            GROUP BY
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                account_move_line.amount_currency,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date
                            ORDER BY
                                account_move_line.date''',
                        (tuple(accounts),date_60,date_90,date,company_id,tuple(partners)))   
        result = self._cr.fetchall()
        print "----------"
        print len(result)
        for res in result:
            move_id = res[0]                
            name = res[3] or res[1]
            move_ref = res[2] or 'Indefinido'
            partner_id = res[4] or False              
            account_id = res[5] or False
            date_move = res[6]
            date_maturity = res[7]
            currency_id = res[8] or self.company_id.currency_id.id
            reconcile_partial_id = res[9] or False
            reconcile_id = res[10] or False
            invoice = res[11] or 'Indefinido'
            currency_facturado = float(res[12] or 0.0)
            currency_residual = float(res[12] or 0.0)
            valor_facturado = float(res[13])
            valor_residual = float(res[13])
            supplier_invoice = res[14] or 'Indefinido'
            date_reconcile = res[15] or False
            date_partial = res[16] or False

            num_exped = (date_cut - (datetime.strptime(date_move, '%Y-%m-%d') if date_move else False)).days if date_move else 0
            num_venc = (date_cut - (datetime.strptime(date_maturity, '%Y-%m-%d') if date_maturity else False)).days if date_maturity else 0
                        
            if (self.type == 'cartera' and valor_residual <= 0.0) or (self.type == 'tesoreria' and valor_residual >= 0.0):
                valor_facturado=0.0
                if reconcile_id  and date_reconcile <= date or reconcile_partial_id and date_partial <= date:
                    continue
            
            if reconcile_id:
                if reconcile_id in conciliaciones:
                    valor_residual=0.0
                else:                    
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_id = %s AND id != %s AND date <= %s''',
                                (reconcile_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:                    
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            conciliaciones.append(reconcile_id)
            
            
            if reconcile_partial_id and not reconcile_id:
                if reconcile_partial_id in parciales:
                    valor_residual=0.0
                else:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                (reconcile_partial_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            parciales.append(reconcile_partial_id)
            
            if abs(valor_residual) > tolerancia:
                cr.execute('''insert into account_report_cartera_avancys_line (company_id,invoice,name,account_id,fecha_elaboracion,
                fecha_vencimiento,en_mora,valor_facturado,valor_residual,partner_id,date,currency_id,currency_facturado,
                currency_residual,rango,date_emision,type,numero_dias_expedicion,numero_dias_vencidos) values
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (company_id,invoice,name, account_id,date_move,
                date_maturity,True,valor_facturado,valor_residual,partner_id or None,date,currency_id or None, currency_facturado,
                currency_residual,'4. (61 - 90)',datetime.now(),self.type,num_exped,num_venc))
            
        print "***************  CALCULA LOS MOVIMIENTOS VENCIDOS 91 - 120 ***************"
        date_120 = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=120)
        self._cr.execute('''SELECT 
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_move_line.amount_currency,                                
                                SUM(account_move_line.debit - account_move_line.credit),
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date                         
                            FROM                                
                                (
                                account_move_line
                                LEFT JOIN
                                account_invoice
                                ON account_move_line.move_id = account_invoice.move_id
                                LEFT JOIN
                                account_move_reconcile AS reconcile
                                ON account_move_line.reconcile_id = reconcile.id
                                LEFT JOIN
                                account_move_reconcile AS reconcile_partial
                                ON account_move_line.reconcile_partial_id = reconcile_partial.id
                                )
                            WHERE 
                                account_move_line.account_id in %s
                                AND account_move_line.date_maturity < %s
                                AND account_move_line.date_maturity >= %s
                                AND account_move_line.date <= %s
                                AND account_move_line.company_id = %s
                                AND account_move_line.partner_id in %s
                                AND account_move_line.state = 'valid'
                            GROUP BY
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                account_move_line.amount_currency,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date
                            ORDER BY
                                account_move_line.date''',
                        (tuple(accounts),date_90,date_120,date,company_id,tuple(partners)))   
        result = self._cr.fetchall()
        print "----------"
        print len(result)
        for res in result:
            move_id = res[0]                
            name = res[3] or res[1]
            move_ref = res[2] or 'Indefinido'
            partner_id = res[4] or False              
            account_id = res[5] or False
            date_move = res[6]
            date_maturity = res[7]
            currency_id = res[8] or self.company_id.currency_id.id
            reconcile_partial_id = res[9] or False
            reconcile_id = res[10] or False
            invoice = res[11] or 'Indefinido'
            currency_facturado = float(res[12] or 0.0)
            currency_residual = float(res[12] or 0.0)
            valor_facturado = float(res[13])
            valor_residual = float(res[13])
            supplier_invoice = res[14] or 'Indefinido'
            date_reconcile = res[15] or False
            date_partial = res[16] or False

            num_exped = (date_cut - (datetime.strptime(date_move, '%Y-%m-%d') if date_move else False)).days if date_move else 0
            num_venc = (date_cut - (datetime.strptime(date_maturity, '%Y-%m-%d') if date_maturity else False)).days if date_maturity else 0
                        
            if (self.type == 'cartera' and valor_residual <= 0.0) or (self.type == 'tesoreria' and valor_residual >= 0.0):
                valor_facturado=0.0
                if reconcile_id  and date_reconcile <= date or reconcile_partial_id and date_partial <= date:
                    continue
            
            if reconcile_id:
                if reconcile_id in conciliaciones:
                    valor_residual=0.0
                else:                    
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_id = %s AND id != %s AND date <= %s''',
                                (reconcile_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:                    
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            conciliaciones.append(reconcile_id)
            
            
            if reconcile_partial_id and not reconcile_id:
                if reconcile_partial_id in parciales:
                    valor_residual=0.0
                else:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                (reconcile_partial_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            parciales.append(reconcile_partial_id)
            
            if abs(valor_residual) > tolerancia:
                cr.execute('''insert into account_report_cartera_avancys_line (supplier_invoice,company_id,invoice,name,account_id,
                fecha_elaboracion,fecha_vencimiento,en_mora,valor_facturado,valor_residual,partner_id,date,currency_id,
                currency_facturado,currency_residual,rango,date_emision,type,numero_dias_expedicion,numero_dias_vencidos) values
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (supplier_invoice,company_id,invoice,name,account_id,
                date_move,date_maturity,True,valor_facturado,valor_residual,partner_id or None,date,currency_id or None,
                currency_facturado,currency_residual,'5. (91 - 120)',datetime.now(),self.type,num_exped,num_venc))

        print "***************  CALCULA LOS MOVIMIENTOS VENCIDOS 121 - 150 ***************"
        date_150 = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=150)
        self._cr.execute('''SELECT 
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_move_line.amount_currency,                                
                                SUM(account_move_line.debit - account_move_line.credit),
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date                       
                            FROM                                
                                (
                                account_move_line
                                LEFT JOIN
                                account_invoice
                                ON account_move_line.move_id = account_invoice.move_id
                                LEFT JOIN
                                account_move_reconcile AS reconcile
                                ON account_move_line.reconcile_id = reconcile.id
                                LEFT JOIN
                                account_move_reconcile AS reconcile_partial
                                ON account_move_line.reconcile_partial_id = reconcile_partial.id
                                )
                            WHERE  
                                account_move_line.account_id in %s
                                AND account_move_line.date_maturity < %s
                                AND account_move_line.date_maturity >= %s
                                AND account_move_line.date <= %s
                                AND account_move_line.company_id = %s
                                AND account_move_line.partner_id in %s
                                AND account_move_line.state = 'valid'
                            GROUP BY
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                account_move_line.amount_currency,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date
                            ORDER BY
                                account_move_line.date''',
                        (tuple(accounts),date_120,date_150,date,company_id,tuple(partners)))   
        result = self._cr.fetchall()
        print "----------"
        print len(result)
        for res in result:
            move_id = res[0]                
            name = res[3] or res[1]
            move_ref = res[2] or 'Indefinido'
            partner_id = res[4] or False              
            account_id = res[5] or False
            date_move = res[6]
            date_maturity = res[7]
            currency_id = res[8] or self.company_id.currency_id.id
            reconcile_partial_id = res[9] or False
            reconcile_id = res[10] or False
            invoice = res[11] or 'Indefinido'
            currency_facturado = float(res[12] or 0.0)
            currency_residual = float(res[12] or 0.0)
            valor_facturado = float(res[13])
            valor_residual = float(res[13])
            supplier_invoice = res[14] or 'Indefinido'
            date_reconcile = res[15] or False
            date_partial = res[16] or False

            num_exped = (date_cut - (datetime.strptime(date_move, '%Y-%m-%d') if date_move else False)).days if date_move else 0
            num_venc = (date_cut - (datetime.strptime(date_maturity, '%Y-%m-%d') if date_maturity else False)).days if date_maturity else 0
                        
            if (self.type == 'cartera' and valor_residual <= 0.0) or (self.type == 'tesoreria' and valor_residual >= 0.0):
                valor_facturado=0.0
                if reconcile_id  and date_reconcile <= date or reconcile_partial_id and date_partial <= date:
                    continue
            
            if reconcile_id:
                if reconcile_id in conciliaciones:
                    valor_residual=0.0
                else:                    
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_id = %s AND id != %s AND date <= %s''',
                                (reconcile_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:                    
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            conciliaciones.append(reconcile_id)
            
            
            if reconcile_partial_id and not reconcile_id:
                if reconcile_partial_id in parciales:
                    valor_residual=0.0
                else:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                (reconcile_partial_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            parciales.append(reconcile_partial_id)
            
            if abs(valor_residual) > tolerancia:
                cr.execute('''insert into account_report_cartera_avancys_line (supplier_invoice,company_id,invoice,name,
                account_id,fecha_elaboracion,fecha_vencimiento,en_mora,valor_facturado,valor_residual,partner_id,date,currency_id,
                currency_facturado,currency_residual,rango,date_emision,type,numero_dias_expedicion,numero_dias_vencidos) values
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (supplier_invoice,company_id,invoice,name,account_id,
                date_move,date_maturity,True,valor_facturado,valor_residual,partner_id or None,date,currency_id or None,
                currency_facturado,currency_residual,'6. (121 - 150)',datetime.now(),self.type,num_exped,num_venc))
            
        print "***************  CALCULA LOS MOVIMIENTOS VENCIDOS 151 - 180 ***************"
        date_180 = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=180)
        self._cr.execute('''SELECT 
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_move_line.amount_currency,                                
                                SUM(account_move_line.debit - account_move_line.credit),
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date                                
                            FROM                                
                                (
                                account_move_line
                                LEFT JOIN
                                account_invoice
                                ON account_move_line.move_id = account_invoice.move_id
                                LEFT JOIN
                                account_move_reconcile AS reconcile
                                ON account_move_line.reconcile_id = reconcile.id
                                LEFT JOIN
                                account_move_reconcile AS reconcile_partial
                                ON account_move_line.reconcile_partial_id = reconcile_partial.id
                                )
                            WHERE  
                                account_move_line.account_id in %s
                                AND account_move_line.date_maturity < %s
                                AND account_move_line.date_maturity >= %s
                                AND account_move_line.date <= %s
                                AND account_move_line.company_id = %s
                                AND account_move_line.partner_id in %s
                                AND account_move_line.state = 'valid'
                            GROUP BY
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                account_move_line.amount_currency,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date
                            ORDER BY
                                account_move_line.date''',
                        (tuple(accounts),date_150,date_180,date,company_id,tuple(partners)))   
        result = self._cr.fetchall()
        print "----------"
        print len(result)
        for res in result:
            move_id = res[0]                
            name = res[3] or res[1]
            move_ref = res[2] or 'Indefinido'
            partner_id = res[4] or False              
            account_id = res[5] or False
            date_move = res[6]
            date_maturity = res[7]
            currency_id = res[8] or self.company_id.currency_id.id
            reconcile_partial_id = res[9] or False
            reconcile_id = res[10] or False
            invoice = res[11] or 'Indefinido'
            currency_facturado = float(res[12] or 0.0)
            currency_residual = float(res[12] or 0.0)
            valor_facturado = float(res[13])
            valor_residual = float(res[13])
            supplier_invoice = res[14] or 'Indefinido'
            date_reconcile = res[15] or False
            date_partial = res[16] or False

            num_exped = (date_cut - (datetime.strptime(date_move, '%Y-%m-%d') if date_move else False)).days if date_move else 0
            num_venc = (date_cut - (datetime.strptime(date_maturity, '%Y-%m-%d') if date_maturity else False)).days if date_maturity else 0
                        
            if (self.type == 'cartera' and valor_residual <= 0.0) or (self.type == 'tesoreria' and valor_residual >= 0.0):
                valor_facturado=0.0
                if reconcile_id  and date_reconcile <= date or reconcile_partial_id and date_partial <= date:
                    continue
            
            if reconcile_id:
                if reconcile_id in conciliaciones:
                    valor_residual=0.0
                else:                    
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_id = %s AND id != %s AND date <= %s''',
                                (reconcile_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:                    
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            conciliaciones.append(reconcile_id)
            
            
            if reconcile_partial_id and not reconcile_id:
                if reconcile_partial_id in parciales:
                    valor_residual=0.0
                else:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                (reconcile_partial_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            parciales.append(reconcile_partial_id)
            
            if abs(valor_residual) > tolerancia:
                cr.execute('''insert into account_report_cartera_avancys_line (supplier_invoice,company_id,invoice,name,account_id,
                fecha_elaboracion,fecha_vencimiento,en_mora,valor_facturado,valor_residual,partner_id,date,currency_id,
                currency_facturado,currency_residual,rango,date_emision,type,numero_dias_expedicion,numero_dias_vencidos) values
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (supplier_invoice,company_id,invoice,name,
                account_id,date_move,date_maturity,True,valor_facturado,valor_residual,partner_id or None,date,currency_id or None,
                currency_facturado,currency_residual,'7. (151 - 180)',datetime.now(),self.type,num_exped,num_venc))
                        
        print "***************  CALCULA LOS MOVIMIENTOS VENCIDOS  MAYORES DE 180 ***************"
        date_180 = datetime.strptime(self.date, DEFAULT_SERVER_DATE_FORMAT).date() - timedelta(days=180)
        self._cr.execute('''SELECT 
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_move_line.amount_currency,                                
                                SUM(account_move_line.debit - account_move_line.credit),
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date                              
                            FROM                                
                                (
                                account_move_line
                                LEFT JOIN
                                account_invoice
                                ON account_move_line.move_id = account_invoice.move_id
                                LEFT JOIN
                                account_move_reconcile AS reconcile
                                ON account_move_line.reconcile_id = reconcile.id
                                LEFT JOIN
                                account_move_reconcile AS reconcile_partial
                                ON account_move_line.reconcile_partial_id = reconcile_partial.id
                                )
                            WHERE  
                                account_move_line.account_id in %s
                                AND account_move_line.date_maturity < %s
                                AND account_move_line.date <= %s
                                AND account_move_line.company_id = %s
                                AND account_move_line.partner_id in %s
                                AND account_move_line.state = 'valid'
                            GROUP BY
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.date_maturity,
                                account_move_line.currency_id,
                                account_move_line.amount_currency,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date                                
                            ORDER BY
                                account_move_line.date''',
                        (tuple(accounts),date_180,date,company_id,tuple(partners)))   
        result = self._cr.fetchall()
        print "----------"
        print len(result)
        for res in result:
            move_id = res[0]                
            name = res[3] or res[1]
            move_ref = res[2] or 'Indefinido'
            partner_id = res[4] or False              
            account_id = res[5] or False
            date_move = res[6]
            date_maturity = res[7]
            currency_id = res[8] or self.company_id.currency_id.id
            reconcile_partial_id = res[9] or False
            reconcile_id = res[10] or False
            invoice = res[11] or 'Indefinido'
            currency_facturado = float(res[12] or 0.0)
            currency_residual = float(res[12] or 0.0)
            valor_facturado = float(res[13])
            valor_residual = float(res[13])
            supplier_invoice = res[14] or 'Indefinido'              
            date_reconcile = res[15] or False
            date_partial = res[16] or False

            num_exped = (date_cut - (datetime.strptime(date_move, '%Y-%m-%d') if date_move else False)).days if date_move else 0
            num_venc = (date_cut - (datetime.strptime(date_maturity, '%Y-%m-%d') if date_maturity else False)).days if date_maturity else 0
                        
            if (self.type == 'cartera' and valor_residual <= 0.0) or (self.type == 'tesoreria' and valor_residual >= 0.0):
                valor_facturado=0.0
                if reconcile_id  and date_reconcile <= date or reconcile_partial_id and date_partial <= date:
                    continue
            
            if reconcile_id:
                if reconcile_id in conciliaciones:
                    valor_residual=0.0
                else:                    
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_id = %s AND id != %s AND date <= %s''',
                                (reconcile_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:                    
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            conciliaciones.append(reconcile_id)
            
            
            if reconcile_partial_id and not reconcile_id:
                if reconcile_partial_id in parciales:
                    valor_residual=0.0
                else:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                (reconcile_partial_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            parciales.append(reconcile_partial_id)
            if abs(valor_residual) > tolerancia:
                cr.execute('''insert into account_report_cartera_avancys_line (supplier_invoice,company_id,invoice,name,account_id,
                fecha_elaboracion,fecha_vencimiento,en_mora,valor_facturado,valor_residual,partner_id,date,currency_id,
                currency_facturado,currency_residual,rango,date_emision,type,numero_dias_expedicion,numero_dias_vencidos) values
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (supplier_invoice,company_id, invoice,name,
                account_id,date_move,date_maturity,True,valor_facturado,valor_residual,partner_id or None,date,currency_id or None,
                currency_facturado,currency_residual,'8. (MAYOR a 180)',datetime.now(),self.type,num_exped,num_venc))
            
        
        print "***************  CALCULA LOS MOVIMIENTOS SIN FECHA DE VENCIMIENTO ***************"
        self._cr.execute('''SELECT 
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.currency_id,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_move_line.amount_currency,                                
                                SUM(account_move_line.debit - account_move_line.credit),
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date                      
                            FROM                                
                                (
                                account_move_line
                                LEFT JOIN
                                account_invoice
                                ON account_move_line.move_id = account_invoice.move_id
                                LEFT JOIN
                                account_move_reconcile AS reconcile
                                ON account_move_line.reconcile_id = reconcile.id
                                LEFT JOIN
                                account_move_reconcile AS reconcile_partial
                                ON account_move_line.reconcile_partial_id = reconcile_partial.id
                                )
                            WHERE  
                                account_move_line.account_id in %s
                                AND account_move_line.date_maturity IS NULL
                                AND account_move_line.date <= %s
                                AND account_move_line.company_id = %s
                                AND account_move_line.partner_id in %s
                                AND account_move_line.state = 'valid'
                            GROUP BY
                                account_move_line.id,
                                account_move_line.name,
                                account_move_line.ref,
                                account_move_line.ref1,
                                account_move_line.partner_id,
                                account_move_line.account_id,
                                account_move_line.date,
                                account_move_line.currency_id,
                                account_move_line.amount_currency,
                                reconcile_partial.id,
                                reconcile.id,
                                account_invoice.internal_number,
                                account_invoice.supplier_invoice,
                                reconcile.create_date,
                                reconcile_partial.create_date
                            ORDER BY
                                account_move_line.date''',
                        (tuple(accounts), date,company_id,tuple(partners)))   
        result = self._cr.fetchall()
        print "----------"
        print len(result)
        for res in result:
            move_id = res[0]                
            name = res[3] or res[1]
            move_ref = res[2] or 'Indefinido'
            partner_id = res[4] or False              
            account_id = res[5] or False
            date_move = res[6]
            date_maturity = date
            currency_id = res[7] or self.company_id.currency_id.id
            reconcile_partial_id = res[8] or False
            reconcile_id = res[9] or False
            invoice = res[10] or 'Indefinido'
            currency_facturado = float(res[11] or 0.0)
            currency_residual = float(res[11] or 0.0)
            valor_facturado = float(res[12])
            valor_residual = float(res[12])
            supplier_invoice = res[13] or 'Indefinido'            
            date_reconcile = res[14] or False
            date_partial = res[15] or False

            num_exped = (date_cut - (datetime.strptime(date_move, '%Y-%m-%d') if date_move else False)).days if date_move else 0
            num_venc = (date_cut - (datetime.strptime(date_maturity, '%Y-%m-%d') if date_maturity else False)).days if date_maturity else 0
                        
            if (self.type == 'cartera' and valor_residual <= 0.0) or (self.type == 'tesoreria' and valor_residual >= 0.0):
                valor_facturado=0.0
                if reconcile_id  and date_reconcile <= date or reconcile_partial_id and date_partial <= date:
                    continue
            
            if reconcile_id:
                if reconcile_id in conciliaciones:
                    valor_residual=0.0
                else:                    
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_id = %s AND id != %s AND date <= %s''',
                                (reconcile_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:                    
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            conciliaciones.append(reconcile_id)
            
            
            if reconcile_partial_id and not reconcile_id:
                if reconcile_partial_id in parciales:
                    valor_residual=0.0
                else:
                    self._cr.execute('''SELECT
                                        SUM(debit - credit),
                                        SUM(amount_currency)
                                    FROM
                                        account_move_line
                                    WHERE
                                        reconcile_partial_id = %s AND id != %s AND date <= %s''',
                                (reconcile_partial_id,move_id,date))   
                    result1 = self._cr.fetchall()
                    for res in result1:
                        valor_residual += float(res[0] or 0.0)
                        currency_residual += float(res[1] or 0.0)
                        if valor_residual != 0.0:
                            parciales.append(reconcile_partial_id)
                            
            if abs(valor_residual) > tolerancia:
                cr.execute('''insert into account_report_cartera_avancys_line (supplier_invoice,company_id,invoice,name,account_id,
                fecha_elaboracion,fecha_vencimiento,en_mora,valor_facturado,valor_residual,partner_id,date,currency_id,
                currency_facturado,currency_residual,rango,date_emision,type,numero_dias_expedicion,numero_dias_vencidos) values
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (supplier_invoice,company_id, invoice,name, account_id,
                date_move,date_maturity,True,valor_facturado,valor_residual,partner_id or None,date,currency_id or None, currency_facturado,
                currency_residual,'9. (SIN FECHA VENCIMIENTO)',datetime.now(),self.type,num_exped,num_venc))
           
        final = datetime.now()
        diff = final-inicio
            
        print "----------------------------------------------------------------------"
        print "----------------------------------------------------------------------"
        print "---------------------------- TERMINO ---------------------------------"
        print "----------------------------------------------------------------------"
        print "                           ",diff
        print ""
        print "----------------------------------------------------------------------"
        print ""
        
        if self.print_report == 'print':
            datas = {}
            datas['ids'] = [x.id for x in report_line_obj.search([])]
            datas['model'] = 'account.report.cartera.avancys.line'
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'report_odoo_extended.reporte_tesoreria_cartera_aeroo',
                'report_type': 'aeroo',
                'datas': datas,
                }
        elif self.print_report == 'print_basico':
            datas = {}
            datas['ids'] = [x.id for x in report_line_obj.search([])]
            datas['model'] = 'account.report.cartera.avancys.line'
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'report_odoo_extended.reporte_tesoreria_cartera_basico_aeroo',
                'report_type': 'aeroo',
                'datas': datas,
                }
        else:    
            return {
                'name': 'Informe de Tesoreria y Cartera',
                'view_type': 'form',
                'view_mode': 'graph,tree,form',
                'view_id': False,
                'res_model': 'account.report.cartera.avancys.line',
                'type': 'ir.actions.act_window'
            }
        
#
