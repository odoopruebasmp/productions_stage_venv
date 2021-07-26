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


class account_report_balance_general(models.Model):
    _name = "account.report.balance.general"
    
    amount_activo = fields.Float(string='Total Activo', digits=dp.get_precision('Account'))
    amount_pasivo = fields.Float(string='Total Pasivo', digits=dp.get_precision('Account'))
    amount_patrimonio = fields.Float(string='Total Patrimonio', digits=dp.get_precision('Account'))
    amount_ingresos = fields.Float(string='Total Ingresos', digits=dp.get_precision('Account'))
    amount_gastos =  fields.Float(string='Total Gastos', digits=dp.get_precision('Account'))
    amount_costos =  fields.Float(string='Total Costos de Venta', digits=dp.get_precision('Account'))
    amount_costos_produccion = fields.Float(string='Total Costos de Produccion', digits=dp.get_precision('Account'))
    amount_orden_deudoras = fields.Float(string='Total Cuentas de Orden Deuduras', digits=dp.get_precision('Account'))
    amount_orden_acreedoras = fields.Float(string='Total Cuentas de Orden Acreedoras', digits=dp.get_precision('Account'))    
    amount_pasivo_patrimonio = fields.Float(string='Total Pasivo + Patrimonio', digits=dp.get_precision('Account'))
    amount_activo_pasivo_patrimonio = fields.Float(string='Total Cuentas de Orden', digits=dp.get_precision('Account'))
    amount_deudoras_acreedoras = fields.Float(string='Total Cuentas de Orden', digits=dp.get_precision('Account'))
    amount_utilidad = fields.Float(string='Total Utilidad', digits=dp.get_precision('Account'))


class account_report_balance_general_line(models.Model):
    _name = "account.report.balance.general.line"
    _order = "code desc"
    
    name = fields.Char(string='Nombre Cuenta')
    code = fields.Char(string='Codigo')
    subcuenta = fields.Char(string='Subcuenta')
    cuenta = fields.Char(string='cuenta')
    grupo = fields.Char(string='Grupo')
    clase = fields.Char(string='Clase')
    partner_name = fields.Char(string='Tercero')
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_inicial = fields.Float(string='Saldo Inicial', digits=dp.get_precision('Account'))
    amount_final = fields.Float(string='Saldo Final', digits=dp.get_precision('Account'))
    partner_id = fields.Integer(string='Tercero ID')
    account_id_int = fields.Integer(string='Cuenta ID')
    nivel = fields.Integer(string='Clase')
    date = fields.Date('Fecha')
    encabezado_id = fields.Many2one('account.report.balance.avancys.line.sql.encabezado', string='Encabezado')
    general_id = fields.Many2one('account.report.balance.general', string='Balance General')

class account_report_balance_avancys_line_sql_encabezado(models.Model):
    _name = "account.report.balance.avancys.line.sql.encabezado"
    
    date = fields.Datetime(string="Fecha")
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], default='todos', string='Estados')
    company_id = fields.Many2one('res.company', string='Company')
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    general_id = fields.Many2one('account.report.balance.general', string='Perdidas y Ganacias')
    
    
class account_report_balance_avancys_line_sql(models.Model):
    _name = "account.report.balance.avancys.line.sql"
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
    amount_inicial = fields.Float(string='Saldo Inicial', digits=dp.get_precision('Account'))
    amount_final = fields.Float(string='Saldo Final', digits=dp.get_precision('Account'))
    amount_consulta = fields.Float(string='Saldo', digits=dp.get_precision('Account'))
    partner_id = fields.Integer(string='Tercero ID')
    account_id_int = fields.Integer(string='Cuenta ID')
    nivel = fields.Integer(string='Nivel')
    date = fields.Date('Fecha')
    encabezado_id = fields.Many2one('account.report.balance.avancys.line.sql.encabezado', string='Encabezado')


class account_report_prueba_avancys_report_wizard(models.TransientModel):
    _name = "wizard.report.prueba.avancys.sql.report"
    
    nivel = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('10', 'Detalle Tercero')], string='Nivel', required=True, default='10')
    movimientos = fields.Selection([('todos', 'Todos'), ('movimientos', 'Solo Con Movimientos y Saldo Inicial')], string='Movimientos', required=True, default='movimientos')
    
    
    #PERDIDA Y GANANCIA PDF
    @api.multi
    def imprimir_pg_pdf(self):
        report_line_obj = self.env['account.report.balance.avancys.line.sql']
        general_obj = self.env['account.report.balance.general']
        cr = self._cr        
        account_update = []
        amount_costos_produccion = 0.0
        
        if self.nivel != '10':
            cr.execute('''SELECT id,code FROM account_report_balance_avancys_line_sql WHERE nivel <= %s AND  (LEFT(code,1) = '4' OR LEFT(code,1) = '5' OR LEFT(code,1) = '6' OR LEFT(code,1) = '7') order by code''',(int(self.nivel),))
        else:
            raise Warning(_('Error!'),_("El Nivel de Detalle Tercero, no esta permitido para el Informe de Balance General, puede generar un Informe de Balance de Prueba si desea ver al detalle."))
                
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
            
        ingresos = report_line_obj.search([('code', '=', '4')])
        if not ingresos:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique el Ingreso, su codigo debe ser 4"))
        
        gastos = report_line_obj.search([('code', '=', '5')])
        if not gastos:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique el Gastos, su codigo debe ser 5"))
            
        costos = report_line_obj.search([('code', '=', '6')])
        if not costos:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique el Costos de Venta, su codigo debe ser 6"))
        
        costos_produccion = report_line_obj.search([('code', '=', '7')])
        if costos_produccion:
            amount_costos_produccion = costos_produccion.debit - costos_produccion.credit
        
        
        utilidad = (ingresos.debit - ingresos.credit) + (gastos.debit - gastos.credit) + (costos.debit - costos.credit) + amount_costos_produccion
                
            
        general = general_obj.create({
            'amount_ingresos':ingresos.debit - ingresos.credit,
            'amount_gastos':gastos.debit - gastos.credit,
            'amount_costos':costos.debit - costos.credit,
            'amount_costos_produccion':amount_costos_produccion,
            'amount_utilidad':-utilidad,
        })
        cr.execute('''UPDATE account_report_balance_avancys_line_sql_encabezado SET general_id = %s''',(general.id,))
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.balance.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.template_reporte_perdida_ganancia',
        'datas': datas,
        }
    
    
    #BALANCE GENERAL PDF
    @api.multi
    def imprimir_bg_pdf(self):
        report_line_obj = self.env['account.report.balance.avancys.line.sql']
        general_obj = self.env['account.report.balance.general']
        general_line_obj = self.env['account.report.balance.general.line']
        cr = self._cr        
        ids2 = []
        account_update = []
        amount_costos_produccion = 0.0
        
        cr.execute(''' DELETE FROM account_report_balance_general_line''')
        cr.execute(''' DELETE FROM account_report_balance_general''')
        
        if self.nivel != '10':
            cr.execute('''SELECT id,code FROM account_report_balance_avancys_line_sql WHERE nivel <= %s AND  (LEFT(code,1) = '1' OR LEFT(code,1) = '2' OR LEFT(code,1) = '3') order by code''',(int(self.nivel),))
        else:
            raise Warning(_('Error!'),_("El Nivel de Detalle Tercero, no esta permitido para el Informe de Balance General, puede generar un Informe de Balance de Prueba si desea ver al detalle."))
                
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])       
            
        for line in report_line_obj.browse(ids):
            cr.execute('''insert into account_report_balance_general_line (name,code,debit,credit,amount_inicial,amount_final,encabezado_id) values 
                (%s,%s,%s,%s,%s,%s,%s) ''' ,
                (line.name,line.code,line.debit,line.credit,line.amount_inicial,line.amount_final,line.encabezado_id.id))
        
        
        activo = general_line_obj.search([('code', '=', '1')])
        if not activo:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique el Activo, su codigo debe ser 1"))
        
        pasivo = general_line_obj.search([('code', '=', '2')])
        if not pasivo:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique el Pasivo, su codigo debe ser 2"))
            
        patrimonio = general_line_obj.search([('code', '=', '3')])
        if not patrimonio:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique el Patrimonio, su codigo debe ser 3"))
        
        ingresos = report_line_obj.search([('code', '=', '4')])
        if not ingresos:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique el Ingreso, su codigo debe ser 4"))
        
        gastos = report_line_obj.search([('code', '=', '5')])
        if not gastos:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique el Gastos, su codigo debe ser 5"))
            
        costos = report_line_obj.search([('code', '=', '6')])
        if not costos:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique el Costos de Venta, su codigo debe ser 6"))
        
        costos_produccion = report_line_obj.search([('code', '=', '7')])
        if costos_produccion:
            amount_costos_produccion = costos_produccion.amount_final
        
        orden_deudoras = report_line_obj.search([('code', '=', '8')])
        if not orden_deudoras:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique las Cuentas de Orden Deudoras, su codigo debe ser 8"))
        
        orden_acreedoras = report_line_obj.search([('code', '=', '9')])
        if not orden_acreedoras:
            raise Warning(_('Error!'),_("El sistema debe contar con una cuenta que identifique las Cuentas de Orden Acreedoras, su codigo debe ser 9"))
        
        company = activo.encabezado_id.company_id
        
        if not company.account_pg_perdida_id or not company.account_pg_ganancia_id:
            raise Warning(_('Error!'),_("La compañia debe tener configurada una cuenta de Ganancia y perdida del Ejercicio, verificar esta parametrizacion o comunicarce con el administrador del sistema"))
        
        account_pg_ganancia_id = company.account_pg_ganancia_id.id
        account_pg_perdida_id = company.account_pg_perdida_id.id
        
        utilidad = ingresos.amount_final + gastos.amount_final + costos.amount_final + amount_costos_produccion
        if utilidad < 0:
            account = company.account_pg_ganancia_id
            while (account.parent_id):                    
                general_line_id = general_line_obj.search([('code', '=', account.code)])
                general_line_id.write({'amount_final':general_line_id.amount_final - utilidad})
                account = account.parent_id
        elif utilidad > 0:            
            account = company.account_pg_perdida_id
            while (account.parent_id):                
                general_line_id = general_line_obj.search([('code', '=', account.code)])
                general_line_id.write({'amount_final':general_line_id.amount_final + utilidad})
                account = account.parent_id
                
            
        general = general_obj.create({
            'amount_activo':abs(activo.amount_final), 
            'amount_pasivo':abs(pasivo.amount_final),
            'amount_patrimonio':abs(patrimonio.amount_final),
            'amount_ingresos':abs(ingresos.amount_final),
            'amount_gastos':abs(gastos.amount_final),
            'amount_costos':abs(costos.amount_final),
            'amount_costos_produccion':abs(amount_costos_produccion),
            'amount_orden_deudoras':abs(orden_deudoras.amount_final),
            'amount_orden_acreedoras':abs(orden_acreedoras.amount_final),
            'amount_pasivo_patrimonio':abs(pasivo.amount_final + patrimonio.amount_final),
            'amount_activo_pasivo_patrimonio':abs(activo.amount_final + pasivo.amount_final + patrimonio.amount_final),
            'amount_deudoras_acreedoras':abs(orden_deudoras.amount_final + orden_acreedoras.amount_final),
            'amount_utilidad':utilidad,
        })
        cr.execute('''UPDATE account_report_balance_general_line SET general_id = %s''',(general.id,))            
        cr.execute('''SELECT id FROM account_report_balance_general_line order by code''')
        result = cr.fetchall()
        for res in result:
            ids2.append(res[0])
        datas = {}
        datas['ids'] = ids2
        datas['model'] = 'account.report.balance.general.line'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.template_reporte_balance_general',
        'datas': datas,
        }
    
    
    #BALANCE DE PRUEBAS PDF
    @api.multi
    def imprimir_bp_pdf(self):
        if self.nivel != '10':
            self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql WHERE nivel <= %s order by code''',(int(self.nivel),))
        else:
            self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql order by code, partner_id desc''')
            
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.balance.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.template_reporte_balance',
        'datas': datas,
        }
    
        
    #BALANCE DE PRUEBAS EXCEL
    @api.multi
    def imprimir_calc(self):
        if self.movimientos == 'movimientos':
            if self.nivel != '10':
                self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql WHERE nivel <= %s AND (amount_inicial != 0.0 OR debit != 0.0 OR credit != 0.0) order by code''',(int(self.nivel),))
            else:
                self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql WHERE amount_inicial != 0.0 OR debit != 0.0 OR credit != 0.0 order by code, partner_id desc''')
        else:
            if self.nivel != '10':
                self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql WHERE nivel <= %s order by code''',(int(self.nivel),))
            else:
                self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql order by code, partner_id desc''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.balance.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.reporte_balance_aeroo',
        'report_type': 'aeroo',
        'datas': datas,
        }
    
    
    #INVENTARIO Y BALANCE PDF
    @api.multi
    def imprimir_calc_saldos_pdf(self):
        if self.nivel != '10':
            self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql WHERE nivel <= %s order by code''',(int(self.nivel),))
        else:
            self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql order by code, partner_id desc''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.balance.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.template_reporte_inventario',
        'datas': datas,
        }
    
    
    #INVENTARIO Y BALANCE EXCEL
    @api.multi
    def imprimir_calc_saldos(self):
        if self.nivel != '10':
            self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql WHERE nivel <= %s order by code''',(int(self.nivel),))
        else:
            self._cr.execute('''SELECT id FROM account_report_balance_avancys_line_sql order by code, partner_id desc''')
        result = self._cr.fetchall()
        ids = []
        for res in result:
            ids.append(res[0])
        
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'account.report.balance.avancys.line.sql'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'report_odoo_extended.reporte_inventario_aeroo',
        'report_type': 'aeroo',
        'datas': datas,
        }
        
class account_report_prueba_avancys(models.TransientModel):
    _name = "account.report.prueba.avancys.sql"
    
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
        encabezado_obj = self.env['account.report.balance.avancys.line.sql.encabezado']        
        report_line_obj = self.env['account.report.balance.avancys.line.sql']
        account_obj = self.env['account.account']
        journal_obj = self.env['account.journal']
        account_analytic_obj = self.env['account.analytic.account']
        total_credit=0
        total_debit=0
        dict={}
        account_ids=[]
        company_id = self.company_id.id
        cr = self._cr
        cr.execute(''' DELETE FROM account_report_balance_avancys_line_sql''')
        cr.execute(''' DELETE FROM account_report_balance_avancys_line_sql_encabezado''')
        cr.execute(''' DELETE FROM account_report_balance_general''')
        
        encabezado = encabezado_obj.create({'date_from':self.date_from, 'date_to':self.date_to, 'estado':self.estado, 'company_id':company_id, 'date': datetime.now()-timedelta(hours=5)})
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
                account_account.parent_zero = %s
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
            tuples = (self.chart_account_id.id,date_from,company_id)+tuple(tuples)
            cr.execute(query,tuples)
        else:
            cr.execute(query,(self.chart_account_id.id,date_from,company_id))
        
        result = self._cr.fetchall()
        for res in result:
            account_id = res[0]
            partner_id = res[1]
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
                        account_account.parent_zero = %s
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
                tuples = (self.chart_account_id.id,date_from,company_id)+tuple(tuples)
                cr.execute(query,tuples)
            else:
                cr.execute(query,(self.chart_account_id.id,date_from,company_id))
                
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
                     account_account.parent_zero = %s
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
            tuples = (self.chart_account_id.id,date_from,date_to,company_id)+tuple(tuples)
            cr.execute(query,tuples)
        else:
            cr.execute(query,(self.chart_account_id.id,date_from,date_to,company_id))
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
                amount_inicial = dict[key]['amount_inicial']
            except:
                amount_inicial = 0
            amount_final = amount_inicial+debit-credit
            amount_consulta = debit-credit
            dict.pop(key,None)
            if account_id not in account_ids:
                account_ids.append(account_id)
            total_credit+=credit
            total_debit+=debit
                
            cr.execute('''insert into account_report_balance_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial,amount_final, amount_consulta,partner_name,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial,amount_final,amount_consulta,partner_name,account_id,encabezado_id,10))
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
                         account_account.parent_zero = %s
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
                tuples = (self.chart_account_id.id,date_from,date_to,company_id)+tuple(tuples)
                cr.execute(query,tuples)
            else:
                cr.execute(query,(self.chart_account_id.id,date_from,date_to,company_id))
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
                    amount_inicial = dict[key]['amount_inicial']
                except:
                    amount_inicial = 0
                amount_final = amount_inicial+debit-credit
                amount_consulta = debit-credit
                dict.pop(key,None)
                if account_id not in account_ids:
                    account_ids.append(account_id)
                total_credit+=credit
                total_debit+=debit
                    
                cr.execute('''insert into account_report_balance_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial,amount_final,amount_consulta,partner_name,account_id_int,encabezado_id,nivel) values 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial,amount_final,amount_consulta,partner_name,account_id,encabezado_id,10))
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
                        FROM account_account WHERE (account_account.parent_zero = %s OR account_account.id = %s ) AND id=%s''',
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
            cr.execute('''insert into account_report_balance_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,partner_id,debit,credit,amount_inicial,amount_final,amount_consulta,partner_name,account_id_int,encabezado_id,nivel) values 
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
            (name,code,clase,grupo,cuenta,subcuenta,partner_id,0,0,amount_inicial,amount_inicial,0.0,partner_name,account_id,encabezado_id,10))
            self._cr.execute("""select * from account_report_balance_avancys_line_sql_id_seq""")
        
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
                         SUM(debit-credit) AS suma_consulta,
                         clase
                        FROM 
                         account_report_balance_avancys_line_sql 
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
            amount_consulta = float(res[4])
            code = res[5]
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero = %s OR account_account.id = %s ) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_balance_avancys_line_sql (name,code,debit,credit,amount_inicial,amount_final,amount_consulta,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,debit,credit,amount_inicial,amount_final,amount_consulta,account_id,encabezado_id,1))
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
                         SUM(debit-credit) AS suma_consulta,
                         grupo
                        FROM 
                         account_report_balance_avancys_line_sql
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
            amount_consulta = float(res[4])
            grupo = res[5]
            clase = grupo[0]
            code = grupo
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero = %s OR account_account.id = %s ) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_balance_avancys_line_sql (name,code,clase,debit,credit,amount_inicial,amount_final,amount_consulta,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,debit,credit,amount_inicial,amount_final,amount_consulta,account_id,encabezado_id,2))

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
                         SUM(debit-credit) AS suma_consulta,
                         cuenta
                        FROM 
                         account_report_balance_avancys_line_sql
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
            amount_consulta = float(res[4])
            cuenta = res[5]
            grupo = cuenta[0:2]
            clase = grupo[0]
            code = cuenta
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero = %s OR account_account.id = %s ) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_balance_avancys_line_sql (name,code,clase,grupo,debit,credit,amount_inicial,amount_final,amount_consulta,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,debit,credit,amount_inicial,amount_final,amount_consulta,account_id,encabezado_id,3))
        final = datetime.now()
        diferencia = final-inicio
        print diferencia
        account_ids_repetidas = []
        print "----------Calculando Subcuenta----------"
        inicio = datetime.now()
        cr.execute('''SELECT 
                         SUM(credit) AS suma_credit, 
                         SUM(debit) AS suma_debit, 
                         SUM(amount_inicial) AS suma_inicial, 
                         SUM(amount_final) AS suma_final,
                         SUM(debit-credit) AS suma_consulta,
                         subcuenta
                        FROM 
                         account_report_balance_avancys_line_sql 
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
            amount_consulta = float(res[4])
            subcuenta = res[5]
            cuenta = subcuenta[0:4]
            grupo = cuenta[0:2]
            clase = grupo[0]
            code = subcuenta
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero = %s OR account_account.id = %s ) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
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
            cr.execute('''insert into account_report_balance_avancys_line_sql (name,code,clase,grupo,cuenta,debit,credit,amount_inicial,amount_final,amount_consulta,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,debit,credit,amount_inicial,amount_final,amount_consulta,account_id,encabezado_id,4))
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
                         SUM(debit-credit) AS suma_consulta,
                         code 
                        FROM 
                         account_report_balance_avancys_line_sql 
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
            amount_inicial = float(res[2])
            amount_final = float(res[3])
            amount_consulta = float(res[4])
            code = res[5]
            subcuenta = code[0:6]
            cuenta = subcuenta[0:4]
            grupo = cuenta[0:2]
            clase = grupo[0]
            cr.execute('''SELECT name,id FROM account_account WHERE (account_account.parent_zero = %s OR account_account.id = %s ) AND code=%s AND company_id = %s ''',(self.chart_account_id.id,self.chart_account_id.id,code,company_id))
            try:
                fetch = self._cr.fetchall()[0]
                name = fetch[0]
                account_id = fetch[1]
            except:
                name = 'Indefinido'
                account_id = 0
            if account_id not in account_ids:
                account_ids.append(account_id)
            cr.execute('''insert into account_report_balance_avancys_line_sql (name,code,clase,grupo,cuenta,subcuenta,debit,credit,amount_inicial,amount_final,amount_consulta,account_id_int,encabezado_id,nivel) values 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (name,code,clase,grupo,cuenta,subcuenta,debit,credit,amount_inicial,amount_final,amount_consulta,account_id,encabezado_id,5))
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
                             (account_account.parent_zero = %s OR account_account.id = %s )
                             AND id not in %s
                             AND company_id = %s
                             ''',(self.chart_account_id.id,self.chart_account_id.id,tuple(account_ids),company_id))
            result = self._cr.fetchall()
            for res in result:
                credit = 0
                debit = 0
                amount_inicial = 0
                amount_final = 0
                amount_consulta = 0
                account_id = res[0]
                code = res[1]
                name = res[2]
                nivel = 1
                
                if self.chart_account_id.id==account_id:
                    nivel = 0
                elif len(code) == 1:
                    nivel = 1
                elif len(code) == 2:
                    nivel = 2
                elif len(code) <= 4:
                    nivel = 3
                elif len(code) <= 6:
                    nivel = 4
                elif len(code) > 6:
                    nivel = 5
                    
                #credit = total_credit
                #debit = total_debit
                cr.execute('''insert into account_report_balance_avancys_line_sql (name,code,debit,credit,amount_inicial,amount_final,amount_consulta,account_id_int,encabezado_id,nivel) values 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (name,code,debit,credit,amount_inicial,amount_final,amount_consulta,account_id,encabezado_id,nivel))
            final = datetime.now()
            diferencia = final-inicio
            print diferencia        
            encabezado.write({'debit':total_debit,'credit':total_credit})
                
        return {
            'domain': [],
            'context': {},
            'name': 'Informe de Balance de Prueba',
            'view_type': 'form',
            'view_mode': 'tree,graph',
            'view_id': False,
            'res_model': 'account.report.balance.avancys.line.sql',
            'type': 'ir.actions.act_window'
        }
#
