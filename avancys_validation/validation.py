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


class res_company(models.Model):
    _inherit = "res.company"
    
    account_inventory_ids = fields.One2many('account.account', 'inventory_conf_id', string='Cuentas de Inventario', help="Estas cuentas se tendran en cuenta en el proceso de auditoria para validar la correcta afectacion contable en movimientos de inventario.")
    tolerancia = fields.Float(string="Tolerancia", digits=dp.get_precision('Account'), help="Valor maximo de diferencia Costo del movimiento vs Afectacion Contable")
    

class account_account(models.Model):
    _inherit = "account.account"
    
    inventory_conf_id = fields.Many2one('res.company')
    
    
class avancys_validation(models.Model):
    _name = 'avancys.validation'    
    
    @api.one
    @api.depends('line_ids')
    def _import(self):
        if self.line_ids:
            self.count = len(self.line_ids)

    count=fields.Integer(string='Items', compute="_import")
    name = fields.Char(string='Nombre', readonly=True)
    create_date = fields.Datetime(string='Fecha Ejecucion', readonly=True)    
    company_id = fields.Many2one('res.company', string='Compañia', readonly=True)
    create_uid = fields.Many2one('res.users', string='Responsable', readonly=True)
    line_ids = fields.One2many('avancys.validation.line', 'validation_id', string='Lineas', readonly=True)
    
    @api.multi
    def view_validation(self):        
        domain = [('id','in',[x.id for x in self.line_ids])]
        ctx = {'search_default_group_by_type': 1, 'search_default_group_by_period_id': 1}
        return {
                'domain': domain,
                'name': 'Lines',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'avancys.validation.line',
                'type': 'ir.actions.act_window',
                'context': ctx
            }
    
class avancys_validation_line(models.Model):
    _name = 'avancys.validation.line'            
    
    create_date = fields.Datetime(string='Fecha Ejecucion', readonly=True)    
    company_id = fields.Many2one('res.company', string='Compañia', readonly=True)
    create_uid = fields.Many2one('res.users', string='Responsable', readonly=True)
    period_id = fields.Many2one('account.period', string='Periodo', readonly=True)    
    type = fields.Char(string='Tipo', readonly=True)
    description = fields.Text(string='Descripcion', readonly=True)
    validation_id = fields.Many2one('avancys.validation', string='Proceso', readonly=True)
    name = fields.Char(string='Id', readonly=True)
    observaciones = fields.Char(string='Observaciones', readonly=True)
    model = fields.Char(string='Modelo', readonly=True)
    amount = fields.Float(string='Amount', digits=dp.get_precision('Account'), readonly=True)
    
    @api.multi
    def view_validation(self):        
        domain = [('id','=',self.name)]
        return {
                'domain': domain,
                'name': 'Lines',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': self.model,
                'type': 'ir.actions.act_window'
            }
    
    
class avancys_validation_wizard(models.TransientModel):
    _name = 'avancys.validation.wizard'
    
    company_id = fields.Many2one('res.company', string='Compañia')
    date = fields.Datetime(string='Fecha recosteo', default=datetime.now()-timedelta(days=datetime.now().day - 1) -timedelta(hours=datetime.now().hour - 5), help="Esta es la fecha de corte inical del recosteo, el sistema recalcula todos los movimientos de esta fecha en adelante.")
    product_id = fields.Many2one('product.product', string='Producto', help="Este es el producto a recostear. Si no se selecciona ningun producto, el sistema ejecuta el procedimiento para todos los productos de tipo almacenables que esten activos.")
    config_analytic_global = fields.Boolean(string='Contabilidad Analitica Global',help="Si se selecciona, el sistema se encarga de actualizar la cuenta analitica, en los pagos, recaudos, movimientos de inventario, facturas de venta, devoluciones, notas debito, notas credito, factura de proveedor")
    picking_opetarion = fields.Boolean(string='Revision PIcking - Tipo de Operacion',help="Si se selecciona, el sistema realiza una revision de todos los movimientos de inventario en los periodos abiertos, donde revisa que la afectacion contable, este acorde al tipo de movimiento, y que las cuentas contables afectadas, sean las configuradas como cuentas de inventario de la compañia.")
    type = fields.Selection([('recosteo','Recosteo'),('auditoria','Auditoria')], string='Tipo')
    picking_contable = fields.Boolean(string='Revision Contabilidad vs Pickings ',help="Si se selecciona, el sistema realiza una revision de todos los movimientos contables en los periodos abiertos de las cuentas de inventario configuradas en la compania, donde revisa que tengan un equivalente logistico y que este seaequivalente al mismo.")
    move_quants = fields.Boolean(string='Revision Quants vs Moves ',help="Si se selecciona, el sistema realiza una revision de todos los movimientos de inventario en los periodos abiertos vs la disponibilidad de los productos.")
    picking_consu = fields.Boolean(string='Revision Productos Consumibles y Servicios ',help="Si se selecciona, el sistema realiza una revision de todos los movimientos de inventario en los periodos abiertos de los productos de tipo servicio y consumibles.")
    product_detail = fields.Boolean(string='Analisis Detallado por Producto',help="Si se selecciona, el sistema realiza una revision de todos los productos,comparando sus movimientos de inventario vs su afectacion contable.")
    cost_zero = fields.Boolean(string='Costo Cero',help="Si se selecciona, el sistema realiza una revision de todos los movimientos con costo cero.")
    

    #FUNCION DE RECOSTEO
    @api.multi
    def recosteo(self):
        if self._uid != 1:
            raise osv.except_osv(_('ERROR !'), _("Esta operacion solo puede ser ejecutada por el administrador"))
        product_obj = self.env['product.product']
        move_obj = self.env['stock.move']
        location_obj = self.env['stock.location']
        location_ids = tuple([x.id for x in location_obj.search([('active','=',True),('usage','=','internal')])])
        cont=1

        if self.product_id:
            products = self.product_id
        else:
            products = product_obj.search([('active','=',True),('type','=','product')])

        for product in products:
            print "-----------------"
            print len(products)
            print cont
            print ""
            cont+=1
            cost_def=0.0

            moves_cost = move_obj.search([('product_id', '=', product.id),('state', '=', 'done'),('date', '>=', self.date)])
            moves_cost_inicial = move_obj.search([('product_id', '=', product.id),('state', '=', 'done'),('date', '<', self.date)])
            if moves_cost:
                sorted_lines=sorted(moves_cost, key=lambda x: x.date)
                moves_cost_inicial=sorted(moves_cost_inicial, key=lambda x: x.date)
                print moves_cost_inicial
                print moves_cost

                if moves_cost_inicial:
                    cost_def=moves_cost_inicial[len(moves_cost_inicial)-1].costo_promedio
                else:
                    cost_def=sorted_lines[0].cost

                for move in sorted_lines:
                    qty_in_cost = 0.0
                    qty_out_cost = 0.0
                    qty_move_cost = 0.0
                    if move.location_id.usage not in ['supplier','production']:
                        self._cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=%s, costo_promedio=%s WHERE id=%s''',(cost_def, cost_def*move.product_uom_qty, cost_def, move.id))
                    else:
                        self._cr.execute('''SELECT 
                                            SUM(product_qty)
                                        FROM 
                                            stock_move
                                        WHERE  
                                            product_id = %s
                                            AND location_dest_id in %s
                                            AND (date < %s AND state = 'done')''',
                                    (product.id,location_ids,move.date))
                        result = self._cr.fetchall()
                        for res in result:
                            qty_in_cost = res[0] or 0.0
                        self._cr.execute('''SELECT 
                                            SUM(product_qty)
                                        FROM 
                                            stock_move
                                        WHERE  
                                            product_id = %s
                                            AND location_id in %s
                                            AND (date < %s AND state = 'done')''',
                                    (product.id,location_ids,move.date))
                        result = self._cr.fetchall()
                        for res in result:
                            qty_out_cost = res[0] or 0.0
                        qty_move_cost = qty_in_cost - qty_out_cost
                        if qty_move_cost >= 0.0:
                            cost_def = (qty_move_cost*cost_def + move.product_qty*move.cost)/(qty_move_cost+move.product_qty)
                        else:
                            cost_def = 0.0
                        price_unit = move.purchase_line_id and move.purchase_line_id.price_unit or move.price_unit
                        self._cr.execute(''' UPDATE stock_move SET price_unit=%s, costo_promedio=%s WHERE id=%s''',(price_unit, cost_def, move.id))
                self._cr.execute('UPDATE product_product SET costo_standard=%s where id=%s' % (cost_def, product.id))
                self._cr.execute("UPDATE ir_property set value_float=%s where res_id = 'product.template,%s' "
                                 "and name = 'standard_price'" % (cost_def, product.product_tmpl_id.id))
        return True 

    #FUNCION DE AUDITORIA
    @api.multi
    def calculation(self):
        inventory_obj = self.env['stock.inventory']
        product_obj = self.env['product.product']
        warehouse_obj = self.env['stock.warehouse']
        quant_obj = self.env['stock.quant']
        account_obj = self.env['account.account']
        picking_type_obj = self.env['stock.picking.type']
        period_obj = self.env['account.period']
        picking_obj = self.env['stock.picking']
        account_move_obj = self.env['account.move']
        account_move_line_obj = self.env['account.move.line']
        move_obj = self.env['stock.move']
        periods = period_obj.search([('state','=','draft')])
        date=fields.datetime.now()
        validation_ids=[]
        location_obj = self.env['stock.location']
        location_ids = tuple([x.id for x in location_obj.search([('active','=',True),('usage','=','internal')])])
        move_delete=[]
        sequence_obj = self.env['ir.sequence']
        number_seq = sequence_obj.get('validation.avancys')

        self._cr.execute('''INSERT INTO avancys_validation (name,create_date,create_uid,company_id) VALUES 
            (%s,%s,%s,%s) RETURNING id''' ,
            (number_seq,date,self._uid,self.company_id.id))
        validation_id = self._cr.fetchone()[0]


        print "************************************************"
        print "************** FUNCIONES INTERNAS **************"
        print "************************************************"
        print ""

        print "-------------------------------------------------------------------------------------------------------------------------"
        print "FUNCION QUE ACTUALIZA EL ESTADO DE LOS REGISTROS EN BASE AL ESTADO DEL MOVIMIENTO PARA PERIODOS ABIERTOS"
        print "--------------------------------------------------------------------------------------------------------------------------"
        print ""
        move_ids_1 = account_move_line_obj.search([('state','!=','valid'),('move_id.state','=','posted'),('period_id.state','=','draft')])
        if move_ids_1:
            self._cr.execute(''' UPDATE account_move_line SET state='valid' WHERE id in %s''',(tuple([x.id for x in move_ids_1]),))

        print ""
        print "-------------------------------------------------------------------------------------------------------------------------"
        print "FUNCION QUE ACTUALIZA LOS COMPROBANTES Y REGISTROS SIN COMPAÑIA"
        print "--------------------------------------------------------------------------------------------------------------------------"
        print ""
        for account_move_id in account_move_obj.search([('company_id','=',False)]):
            self._cr.execute(''' UPDATE account_move SET company_id=%s WHERE id=%s''',(account_move_id.journal_id.company_id.id, account_move_id.id))
            self._cr.execute(''' UPDATE account_move_line SET company_id=%s WHERE move_id=%s''',(account_move_id.journal_id.company_id.id, account_move_id.id))

        print ""
        print "-------------------------------------------------------------------------------------------------------------------------"
        print "FUNCION QUE ACTUALIZA LOS MOVIMIENTOS DE INVENTARIO SIN COMPAÑIA"
        print "--------------------------------------------------------------------------------------------------------------------------"
        print ""
        for move_id in move_obj.search([('company_id','=',False)]):
            self._cr.execute(''' UPDATE stock_move SET company_id=%s WHERE id=%s''',(move_id.location_id.company_id.id, move_id.id))

        print ""
        print "-------------------------------------------------------------------------------------------------------------------------"
        print "FUNCION QUE ACTUALIZA LOS MOVIMIENTOS DE INVENTARIO SIN COSTO PROMEDIO"
        print "--------------------------------------------------------------------------------------------------------------------------"
        print ""
        for period in periods:
            self._cr.execute(''' UPDATE stock_move SET costo_promedio=cost WHERE state='done' AND date>=%s AND date <=%s AND ((costo_promedio<=0.0 AND cost>0.0) OR costo_promedio=Null)''',(period.date_start, period.date_stop))

        print ""
        print "-------------------------------------------------------------------------------------------------------------------------"
        print "FUNCION QUE ACTUALIZA LOS PERIODOS ABIERTOS DE LOS COMPROBANTES Y REGISTROS CONTABLES DE ACUERDO A LA FECHA DE LOS MISMOS"
        print "--------------------------------------------------------------------------------------------------------------------------"
        print ""
        for period in periods:
            self._cr.execute(''' UPDATE account_move SET period_id=%s WHERE date>=%s AND date <=%s AND company_id=%s''',(period.id, period.date_start, period.date_stop, self.company_id.id))
            self._cr.execute(''' UPDATE account_move_line SET period_id=%s WHERE date>=%s AND date <=%s AND company_id=%s''',(period.id, period.date_start, period.date_stop, self.company_id.id))
        
        
        print ""
        print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
        print "FUNCION QUE REVISA QUE LOS DEBITOS Y CREDITOS DE LOS COMPROBANTES ESTEN CUADRADOS"
        print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
        print ""
        for period in periods:
            self._cr.execute('''SELECT  
                                    move_id,
                                    SUM(debit-credit)
                                FROM 
                                    account_move_line
                                WHERE  
                                    date >= %s AND date <= %s
                                GROUP BY
                                    move_id;''',
                        (period.date_start, period.date_stop))   
            result = self._cr.fetchall()
            for res in result:
                move_id  = res[0] or 'Indefinida', 
                amount  = float(res[1]) or 0.0,
                
                if isinstance(amount, (list, tuple)):
                    amount = amount[0]
                else:
                    amount = amount
                
                if abs(amount) > 0.01:
                    self._cr.execute('''INSERT INTO avancys_validation_line (model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                    ('account.move',move_id,validation_id,date,self._uid,self.company_id.id,'ACCOUNT MOVE DESCUADRADO','SE DEBE HACER SEGUIMIENTO PARA VALIDAR EL DESCUADRE','SE DEBE REALIZAR UNA REVISION EN LA TRAZABILIDAD'))
                    validation_ids.append(self._cr.fetchone()[0])
                
                
            
        if self.move_quants:
            print ""
            print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
            print "FUNCION QUE COMPARA Y AJUSTA LOS QUANTS VS LOS MOVES"
            print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
            print ""        
            product_obj = self.env['product.product']
            location_obj = self.env['stock.location']
            l_ids = []
            location_ids_dos = []
            cost_end = 0.0
            cont=1
            product_ids = tuple([x.id for x in product_obj.search([('active','=',True),('type','=','product')])])        
                    
            date_end='2100-01-01 00:00:01'        
            dict={}
            
            self._cr.execute('''SELECT  product_category.name, 
                                    product_product.id,
                                    product_template.id,
                                    product_template.name,
                                    product_product.default_code,
                                    stock_location.id,
                                    SUM(stock_move.product_qty),
                                    COUNT(stock_move.product_qty)
                                FROM 
                                    product_product,
                                    stock_location,
                                    product_category,
                                    product_template,
                                    stock_move
                                WHERE  
                                    product_template.id = product_product.product_tmpl_id
                                    AND product_category.id = product_template.categ_id
                                    AND product_id in %s
                                    AND stock_location.id =  stock_move.location_id
                                    AND product_product.id = stock_move.product_id
                                    AND stock_move.location_id in %s
                                    AND product_template.type = 'product'
                                    AND (stock_move.date <= %s AND stock_move.state = 'done')
                                GROUP BY
                                    product_product.id,
                                    product_template.id,
                                    product_category.name,
                                    product_template.name,
                                    stock_location.id,
                                    product_product.default_code;''',
                        (product_ids,location_ids,date_end))   
            result = self._cr.fetchall()
            for res in result:
                categoria    = res[0] or 'Indefinida', 
                product_id   = res[1],
                template_id   = res[2],
                product_name = res[3] or 'Indefinido', 
                default_code = res[4] or 'Indefinido',
                location_id = res[5] or 'Indefinido',
                qty_out_end  = float(res[6]) or 0.0,
                count  = float(res[7]) or 0.0,
                key = (product_id,location_id)
                
                dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'location_id':location_id, 'qty_out_end': qty_out_end}
                    
            self._cr.execute('''SELECT 
                                    product_category.name, 
                                    product_product.id,
                                    product_template.id,
                                    product_template.name,
                                    product_product.default_code,
                                    stock_location.id,
                                    SUM(stock_move.product_qty),
                                    COUNT(stock_move.product_qty)
                                FROM 
                                    product_product,
                                    stock_location,
                                    product_category,
                                    product_template,
                                    stock_move
                                WHERE  
                                    product_template.id = product_product.product_tmpl_id
                                    AND product_category.id = product_template.categ_id
                                    AND product_id in %s
                                    AND stock_location.id =  stock_move.location_dest_id
                                    AND product_product.id = stock_move.product_id
                                    AND stock_move.location_dest_id in %s
                                    AND product_template.type = 'product'
                                    AND (stock_move.date <= %s AND stock_move.state = 'done')
                                GROUP BY
                                    product_product.id,
                                    product_template.id,
                                    product_category.name,
                                    product_template.name,
                                    stock_location.id,
                                    product_product.default_code''',
                        (product_ids,location_ids,date_end))        
            
            result = self._cr.fetchall()
            for res in result:
                categoria    = res[0] or 'Indefinida', 
                product_id   = res[1],
                template_id   = res[2],
                product_name = res[3] or 'Indefinido', 
                default_code = res[4] or 'Indefinido',
                location_id = res[5] or 'Indefinido',
                qty_in_end  = float(res[6]) or 0.0,
                count  = float(res[7]) or 0.0,
                key = (product_id,location_id)
                if key in dict:
                    dict[key].update({'qty_in_end': qty_in_end})
                else:
                    dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'location_id':location_id, 'qty_out_end': 0.0, 'qty_in_end': qty_in_end}
                
                if isinstance(dict[key]['qty_in_end'], (list, tuple)):
                    qty_in_end = dict[key]['qty_in_end'][0]
                else:
                    qty_in_end = dict[key]['qty_in_end']
                
                try:
                    if isinstance(dict[key]['qty_out_end'], (list, tuple)):
                        qty_out_end = dict[key]['qty_out_end'][0]
                    else:
                        qty_out_end = dict[key]['qty_out_end']
                except:
                    qty_out_end = 0.0                       
            
                product_qty_end = qty_in_end - qty_out_end
                
                
                self._cr.execute('''SELECT SUM(qty) FROM stock_quant WHERE product_id=%s AND location_id=%s''', (product_id,location_id))
                product_qty_quant = self._cr.fetchall()[0] or 0.0
                
                if isinstance(product_qty_quant, (list, tuple)):
                    product_qty_quant = product_qty_quant[0]
                dict.pop(key,None)
                                
                try:
                    product_qty_quant = float(product_qty_quant)
                except:
                    product_qty_quant = 0.0
                                    
                balance = product_qty_end-product_qty_quant
                
                print "--------"
                print cont
                print len(result)
                cont+=1
                if balance > 0.0:
                    self._cr.execute('''INSERT INTO avancys_validation_line (model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        ('product.product',product_id,validation_id,date,self._uid,self.company_id.id,'MOVES SUPERIORES A LOS QUANTS','SE DEBE HACER SEGUIMIENTO PARA VALIDAR EL DESCUADRE','LA LOCATION QUE PRESENTA DESCUADRE ES'+' '+str(location_id)+' '+str(balance)))
                    validation_ids.append(self._cr.fetchone()[0])
                    product=product_obj.browse(product_id)
                    vals = {
                        'create_date': datetime.now(),
                        'company_id' : self.company_id.id,
                        'product_id' : product_id,
                        'qty' : balance,
                        'in_date' : datetime.now(),
                        'location_id': location_id,
                        'cost': product.standard_price,
                    }
                    quant_obj.create(vals)                
                elif balance < 0.0:
                    self._cr.execute('''INSERT INTO avancys_validation_line (model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        ('product.product',product_id,validation_id,date,self._uid,self.company_id.id,'QUANTS SUPERIORES A LOS MOVES','SE DEBE HACER SEGUIMIENTO PARA VALIDAR EL DESCUADRE','LA LOCATION QUE PRESENTA DESCUADRE ES'+' '+str(location_id)+' '+str(balance)))
                    validation_ids.append(self._cr.fetchone()[0])
                    #self._cr.execute('''INSERT INTO stock_move (create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,total_cost,origin) VALUES 
                    #(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                    #(datetime.now(), product.uom_id.id, 'make_to_stock', company_id.id, product.uom_id.id, product.id, 'none', abs(balance), abs(balance),'Ajuste Negativo'+' '+ str(product_qty_end)+'->'+str(product_qty_quant), '2015-12-31 16:59:59', '2015-12-31 16:59:59', location_id, 6, 'done', product.standard_price, product.standard_price*abs(balance), 'Ajuste Odoo REQ-0000005363'))
            
        
        if self.picking_opetarion:
            print ""
            print "-------------------------------------------------------------------------------------------------------------------------"
            print "FUNCION QUE REVISA QUE TODOS LOS MOVIMIENTOS ESTEN ACORDES CON EL TIPO DE OPERACION"
            print "-------------------------------------------------------------------------------------------------------------------------"
            print ""
            p_y=[]
            p_i=[]
                        
            if self.company_id.account_inventory_ids:
                account_ids = tuple([x.id for x in self.company_id.account_inventory_ids])
            else:
                raise osv.except_osv(_('CONFIGURATION !'), _("Por favor configurar las cuentas de inventario de la compañia, este proceso lo debe realizar un usuario administrador, en el menu /Ajustes/Compañias/Compañias."))
        
            print len(account_ids)
            print ""
            for period in periods:
                move_ids = move_obj.search([('product_id.type','=','product'),('state','=','done'),('date','>=',period.date_start),('date','<=',period.date_stop)])
                margen = abs(self.company_id.tolerancia)
                cont= 1
                for move in move_ids:
                    print "-----"
                    print cont
                    print len(move_ids)
                    cont+=1
                    cost_entradas = 0.0
                    cost_salidas = 0.0
                    cost_move = 0.0
                    
                    if move.location_id.usage in ['view','procurement','transit'] or move.location_dest_id.usage in ['view','procurement','transit']:
                        self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                            (period.id,move.total_cost,'stock.move',move.id,validation_id,date,self._uid,self.company_id.id,'MOVIMIENTOS DE UBICACIONES TIPO VISTA - ABASTECIMIENTO - TRANSITO','INVENTARIO DE INVENTARIO QUE UTILIZA UBICACIONESNO PERMITIDAS','SE DEBE REALIZAR UN ANALISIS DEL MOVIMIENTOY BUSCAR LA AFECTACION CONTABLE Y LOGISCA'))
                    
                    if not move.product_id.active:
                        self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                            (period.id,move.total_cost,'product.product',move.product_id.id,validation_id,date,self._uid,self.company_id.id,'MOVIMIENTOS DE PRODUCTOS INACTIVOS','ES PROBABLE QUE NO ESTEN SIENDO TENIDOS EN CUENTA EN EL INFORME VALORIZADO','SE DEBE REALIZAR UN ANALISIS DE LA DESACTIVACION DELPRODUCTO Y EL IMPACTO QUE PÚDOTENER'))
                    
                    if not move.location_id.active or not move.location_dest_id.active:
                        self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                            (period.id,move.total_cost,'stock.move',move.id,validation_id,date,self._uid,self.company_id.id,'MOVIMIENTOS CON UBICACIONES INACTIVAS','ES PROBABLE QUE NO ESTEN SIENDO TENIDOS EN CUENTA EN EL INFORME VALORIZADO','SE DEBE REALIZAR UN ANALISIS DE LA DESACTIVACION DE LA UBICACION Y EL IMPACTO QUE PÚDOTENER'))
                    

                    if move.production_id:#MOVIMIENTOS DE PRODUCCION
                        print "1111111"#TODO
                    elif move.inventory_id:#MOVIMIENTOS DE AJUSTE DE INVENTARIO
                        if not move.inventory_id.id in p_i: 
                            p_i.append(move.inventory_id.id)
                            if not move.inventory_id.account_move_id:
                                self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE inventory_id=%s AND state='done' AND location_id in %s AND location_dest_id not in %s''',(move.inventory_id.id,location_ids,location_ids))
                                cost_salidas=self._cr.fetchall()[0] or 0.0
                                if isinstance(cost_salidas, (list, tuple)):
                                    cost_salidas = cost_salidas[0]
                                else:
                                    cost_salidas = cost_salidas

                                self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE inventory_id=%s AND state='done' AND location_id not in %s AND location_dest_id in %s''',(move.inventory_id.id,location_ids,location_ids))
                                cost_entradas=self._cr.fetchall()[0] or 0.0
                                if isinstance(cost_entradas, (list, tuple)):
                                    cost_entradas = cost_entradas[0]
                                else:
                                    cost_entradas = cost_entradas

                                cost_move = (cost_entradas or 0.0) - (cost_salidas or 0.0)

                                self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                    (period.id,cost_move,'stock.inventory',move.inventory_id.id,validation_id,date,self._uid,self.company_id.id,'AJUSTE DE INVENTARIO SIN AFECTACION CONTABLE','AJUSTE DE INVENTARIO QUE NO TIENE COMPROBANTE CONTABLE ASOCIADO','SE DEBE VALIDAR LA RAZON DE NO TENER AFECTACION CONTABLE, PARA QUE EL SISTEMA REALICE ESTA OPERACION DE FORMA AUTOMATICA, SE DEBE PARAMETRIZAR UNA CUENTA DE PERDIDAS Y UNA CUENTA DE APROVECHAMIENTO EN EL AJUSTE DE INVENTARIO ANTES DE VALIDARLO'))
                            else:
                                self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE inventory_id=%s AND state='done' AND location_id in %s AND location_dest_id not in %s''',(move.inventory_id.id,location_ids,location_ids))
                                cost_salidas=self._cr.fetchall()[0] or 0.0
                                if isinstance(cost_salidas, (list, tuple)):
                                    cost_salidas = cost_salidas[0]
                                else:
                                    cost_salidas = cost_salidas

                                self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE inventory_id=%s AND state='done' AND location_id not in %s AND location_dest_id in %s''',(move.inventory_id.id,location_ids,location_ids))
                                cost_entradas=self._cr.fetchall()[0] or 0.0
                                if isinstance(cost_entradas, (list, tuple)):
                                    cost_entradas = cost_entradas[0]
                                else:
                                    cost_entradas = cost_entradas

                                cost_move = (cost_entradas or 0.0) - (cost_salidas or 0.0)

                                self._cr.execute(''' SELECT SUM(debit-credit) FROM account_move_line WHERE move_id=%s AND account_id in %s AND date >= %s AND date <= %s''',(move.inventory_id.account_move_id.id, account_ids, period.date_start, period.date_stop))
                                cost_account=self._cr.fetchall()[0]
                                if isinstance(cost_account, (list, tuple)):
                                    cost_account = cost_account[0]

                                if abs(cost_move-cost_account) > margen:
                                    amount= cost_move-cost_account
                                    self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                    (period.id,amount,'stock.inventory',move.inventory_id.id,validation_id,date,self._uid,self.company_id.id,'AJUSTE DE INVENTARIO CON MALA AFECTACION CONTABLE','EL COSTO DE LOS MIVIMIENTOS DEL AJUSTE, NO CONCUERDA CON LA AFECTACION CONTABLE DEL MISMO','SE RECOMIENDA REVISAR CUAL ES EL PRODUCTO QUE GENERA EL DESCUADRE, Y REVISAR LA VARACION DEL COSTOS DEL MISMO'))
                    elif move.picking_id:#MOVIMIENTOS DE PICKING
                        if move.location_id.usage == 'internal' and move.location_dest_id.usage == 'internal':#MOVE INTERNOS SIN AFECTACION CONTABLE
                            if move.picking_id.account_move_id and move.picking_id.account_move_id.id not in move_delete:
                                if move.picking_id.picking_type_id.code != 'internal':
                                    picking_type_id = move.picking_id.picking_type_id.warehouse_id.int_type_id.id
                                    self._cr.execute(''' UPDATE stock_picking SET picking_type_id=%s WHERE id=%s ''',(picking_type_id,move.picking_id.id))
                                    move_delete.append(move.picking_id.account_move_id.id)
                        elif move.location_id.usage == 'supplier' and move.location_dest_id.usage == 'internal':#RECEPCION DE COMPRA - DEBITO AL INVENTARIO
                            if not move.picking_id.id in p_y:
                                p_y.append(move.picking_id.id)
                                if not move.picking_id.account_move_id:
                                    if move.picking_id.picking_type_id.code != 'incoming':
                                        picking_type_id = move.picking_id.picking_type_id.warehouse_id.in_type_id.id
                                        self._cr.execute(''' UPDATE stock_picking SET picking_type_id=%s WHERE id=%s ''',(picking_type_id,move.picking_id.id))
                                        try:
                                            move.picking_id.do_transfer_button()
                                        except:
                                            self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                            amount=self._cr.fetchall()[0]
                                            if isinstance(amount, (list, tuple)):
                                                amount = amount[0]
                                            else:
                                                amount = amount
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                                    else:
                                        self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                        amount=self._cr.fetchall()[0]
                                        if isinstance(amount, (list, tuple)):
                                            amount = amount[0]
                                        else:
                                            amount = amount
                                        print amount
                                        self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'SIN COMPROBANTE',' ',' '))
                                else:
                                    self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                    cost1=self._cr.fetchall()[0]
                                    if isinstance(cost1, (list, tuple)):
                                        cost1 = cost1[0]
                                    else:
                                        cost1 = cost1
                                    self._cr.execute(''' SELECT SUM(debit) FROM account_move_line WHERE move_id=%s and account_id in %s ''',(move.picking_id.account_move_id.id,account_ids))
                                    cost2=self._cr.fetchall()[0]
                                    if isinstance(cost2, (list, tuple)):
                                        cost2 = cost2[0]

                                    try:
                                        balance=cost1-cost2
                                    except:
                                        balance=0.0

                                    if abs(balance) > margen:
                                        try:
                                            move.picking_id.do_transfer_button()
                                        except:
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,cost1-cost2,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                        elif move.location_id.usage == 'customer' and move.location_dest_id.usage == 'internal':#DEVOLUCION DE VENTA - DEBITO AL INVENTARIO
                            if not move.picking_id.id in p_y:
                                p_y.append(move.picking_id.id)
                                if not move.picking_id.account_move_id:
                                    if move.picking_id.picking_type_id.code not in ['incoming','return']:
                                        picking_type_id = move.picking_id.picking_type_id.warehouse_id.in_type_id.id
                                        self._cr.execute(''' UPDATE stock_picking SET picking_type_id=%s WHERE id=%s ''',(picking_type_id,move.picking_id.id))
                                        try:
                                            move.picking_id.do_transfer_button()
                                        except:
                                            self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                            amount=self._cr.fetchall()[0]
                                            if isinstance(amount, (list, tuple)):
                                                amount = amount[0]
                                            else:
                                                amount = amount
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                                    else:
                                        self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                        amount=self._cr.fetchall()[0]
                                        if isinstance(amount, (list, tuple)):
                                            amount = amount[0]
                                        else:
                                            amount = amount
                                        self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'SIN COMPROBANTE',' ',' ')) 
                                else:
                                    self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                    cost1=self._cr.fetchall()[0]
                                    if isinstance(cost1, (list, tuple)):
                                        cost1 = cost1[0]
                                    else:
                                        cost1 = cost1
                                    self._cr.execute(''' SELECT SUM(debit) FROM account_move_line WHERE move_id=%s and account_id in %s ''',(move.picking_id.account_move_id.id,account_ids))
                                    cost2=self._cr.fetchall()[0]
                                    if isinstance(cost2, (list, tuple)):
                                        cost2 = cost2[0]

                                    try:
                                        balance=cost1-cost2
                                    except:
                                        balance=0.0

                                    if abs(balance) > margen:
                                        try:
                                            move.picking_id.do_transfer_button()
                                        except:
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,cost1-cost2,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))    
                        elif move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal':#PRODUCCION U OTROS - DEBITO AL INVENTARIO
                            if not move.picking_id.id in p_y:
                                p_y.append(move.picking_id.id)
                                if not move.picking_id.account_move_id:
                                    if move.picking_id.picking_type_id.code not in ['incoming','return']:
                                        picking_type_id = move.picking_id.picking_type_id.warehouse_id.in_type_id.id
                                        self._cr.execute(''' UPDATE stock_picking SET picking_type_id=%s WHERE id=%s ''',(picking_type_id,move.picking_id.id))
                                        try:
                                            move.picking_id.do_transfer_button()
                                        except:
                                            self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                            amount=self._cr.fetchall()[0]
                                            if isinstance(amount, (list, tuple)):
                                                amount = amount[0]
                                            else:
                                                amount = amount
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                                    else:
                                        self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                        amount=self._cr.fetchall()[0]
                                        if isinstance(amount, (list, tuple)):
                                            amount = amount[0]
                                        else:
                                            amount = amount
                                        self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'SIN COMPROBANTE',' ',' '))
                                else:
                                    self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                    cost1=self._cr.fetchall()[0]
                                    if isinstance(cost1, (list, tuple)):
                                        cost1 = cost1[0]
                                    else:
                                        cost1 = cost1
                                    self._cr.execute(''' SELECT SUM(debit) FROM account_move_line WHERE move_id=%s and account_id in %s ''',(move.picking_id.account_move_id.id,account_ids))
                                    cost2=self._cr.fetchall()[0]
                                    if isinstance(cost2, (list, tuple)):
                                        cost2 = cost2[0]

                                    try:
                                        balance=cost1-cost2
                                    except:
                                        balance=0.0

                                    if abs(balance) > margen:
                                        try:
                                            move.picking_id.do_transfer_button()
                                        except:
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,cost1-cost2,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                        elif move.location_id.usage == 'internal' and move.location_dest_id.usage == 'customer':#REMISION DE VENTA - CREDITO AL INVENTARIO
                            if not move.picking_id.id in p_y:   
                                p_y.append(move.picking_id.id)
                                if not move.picking_id.account_move_id:
                                    if move.picking_id.picking_type_id.code not in ['outgoing']:
                                        picking_type_id = move.picking_id.picking_type_id.warehouse_id.out_type_id.id
                                        self._cr.execute(''' UPDATE stock_picking SET picking_type_id=%s WHERE id=%s ''',(picking_type_id,move.picking_id.id))
                                        try:
                                            move.picking_id.do_transfer_button()
                                        except:
                                            self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                            amount=self._cr.fetchall()[0]
                                            if isinstance(amount, (list, tuple)):
                                                amount = amount[0]
                                            else:
                                                amount = amount
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                                    else:
                                        self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                        amount=self._cr.fetchall()[0]
                                        if isinstance(amount, (list, tuple)):
                                            amount = amount[0]
                                        else:
                                            amount = amount
                                        self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'SIN COMPROBANTE',' ',' '))
                                else:
                                    self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                    cost1=self._cr.fetchall()[0]
                                    if isinstance(cost1, (list, tuple)):
                                        cost1 = cost1[0]
                                    else:
                                        cost1 = cost1
                                    self._cr.execute(''' SELECT SUM(credit) FROM account_move_line WHERE move_id=%s and account_id in %s ''',(move.picking_id.account_move_id.id,account_ids))
                                    cost2=self._cr.fetchall()[0]
                                    if isinstance(cost2, (list, tuple)):
                                        cost2 = cost2[0]
                                    
                                    try:
                                        balance=cost1-cost2
                                    except:
                                        balance=0.0

                                    if abs(balance) > margen:
                                        try:
                                            move.picking_id.do_transfer_button()
                                        except:
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,cost1-cost2,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                        elif move.location_id.usage == 'internal' and move.location_dest_id.usage == 'supplier':#DEVOLUCION DE COMPRA - CREDITO AL INVENTARIO
                            if not move.picking_id.id in p_y:
                                p_y.append(move.picking_id.id)
                                if not move.picking_id.account_move_id:
                                    if move.picking_id.picking_type_id.code not in ['outgoing']:
                                        picking_type_id = move.picking_id.picking_type_id.warehouse_id.out_type_id.id
                                        self._cr.execute(''' UPDATE stock_picking SET picking_type_id=%s WHERE id=%s ''',(picking_type_id,move.picking_id.id))
                                        try:
                                            move.picking_id.do_transfer_button()
                                        except:
                                            self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                            amount=self._cr.fetchall()[0]
                                            if isinstance(amount, (list, tuple)):
                                                amount = amount[0]
                                            else:
                                                amount = amount
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                                    else:
                                        self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                        amount=self._cr.fetchall()[0]
                                        if isinstance(amount, (list, tuple)):
                                            amount = amount[0]
                                        else:
                                            amount = amount
                                        self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'SIN COMPROBANTE',' ',' ')) 
                                else:
                                    self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                    cost1=self._cr.fetchall()[0]
                                    if isinstance(cost1, (list, tuple)):
                                        cost1 = cost1[0]
                                    else:
                                        cost1 = cost1
                                    self._cr.execute(''' SELECT SUM(credit) FROM account_move_line WHERE move_id=%s and account_id in %s ''',(move.picking_id.account_move_id.id,account_ids))
                                    cost2=self._cr.fetchall()[0]
                                    if isinstance(cost2, (list, tuple)):
                                        cost2 = cost2[0]

                                    try:
                                        balance=cost1-cost2
                                    except:
                                        balance=0.0

                                    if abs(balance) > margen:
                                        try:
                                            move.picking_id.do_transfer_button()
                                            const2-=1
                                        except:
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,cost1-cost2,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                        elif move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal':#CONSUMOS - CREDITO AL INVENTARIO
                            if not move.picking_id.id in p_y:
                                p_y.append(move.picking_id.id)
                                if not move.picking_id.account_move_id:
                                    if move.picking_id.picking_type_id.code not in ['outgoing']:
                                        picking_type_id = move.picking_id.picking_type_id.warehouse_id.out_type_id.id
                                        self._cr.execute(''' UPDATE stock_picking SET picking_type_id=%s WHERE id=%s ''',(picking_type_id,move.picking_id.id))
                                        try:
                                            move.picking_id.do_transfer_button()
                                        except:
                                            self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                            amount=self._cr.fetchall()[0]
                                            if isinstance(amount, (list, tuple)):
                                                amount = amount[0]
                                            else:
                                                amount = amount
                                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                                    else:
                                        self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                        amount=self._cr.fetchall()[0]
                                        if isinstance(amount, (list, tuple)):
                                            amount = amount[0]
                                        else:
                                            amount = amount
                                        self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (period.id,amount,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'SIN COMPROBANTE',' ',' '))
                                else:
                                    self._cr.execute(''' SELECT SUM(total_cost) FROM stock_move WHERE picking_id=%s AND state='done' ''',(move.picking_id.id,))
                                    cost1=self._cr.fetchall()[0]
                                    if isinstance(cost1, (list, tuple)):
                                        cost1 = cost1[0]
                                    else:
                                        cost1 = cost1
                                    self._cr.execute(''' SELECT SUM(credit) FROM account_move_line WHERE move_id=%s and account_id in %s ''',(move.picking_id.account_move_id.id,account_ids))
                                    cost2=self._cr.fetchall()[0]
                                    if isinstance(cost2, (list, tuple)):
                                        cost2 = cost2[0]

                                    try:
                                        balance=cost1-cost2
                                    except:
                                        balance=0.0

                                    if abs(balance) > margen:
                                        try:
                                            move.picking_id.do_transfer_button()
                                            const2-=1
                                        except:
                                            self._cr.execute('''INSERT INTO avancys_validation_line (amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                            (cost1-cost2,'stock.picking',move.picking_id.id,validation_id,date,self._uid,self.company_id.id,'ERROR DO TRANSFER BUTTON',' ',' '))
                    else:#MOVIMIENTOS SIN CLASIFICAR
                        amount=move.total_cost
                        self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                            (period.id,amount,'stock.move',move.id,validation_id,date,self._uid,self.company_id.id,'MOVIMIENTOS SIN DOCUMENTO ORIGEN','ESTE MOVIMIENTO NO TIENE ASOCIADO UN AJUSTE DE INVENTARIO, UNA ORDEN DE PRODUCCION, NI UN MOVIMIENTO DE INVENTARIO NORMAL','SE RECOMIENDA CONSULTAR CON EL AREA LOGISTICA SOBRE ESTE MOVIMIENTO'))
        
                
        if self.picking_contable:
            print ""
            print "-------------------------------------------------------------------------------------------------------------------------"
            print "FUNCION QUE REVISA TODOS LOS MOVIMIENTOS CONTABLES DE PERIODOS ABIERTOS Y VALIDA QUE TENGAN EQUIVALENTE LOGISTICO"
            print "-------------------------------------------------------------------------------------------------------------------------"
            print ""
            for period in periods:
                if self.company_id.account_inventory_ids:
                    account_ids = [x.id for x in self.company_id.account_inventory_ids]
                else:
                    raise osv.except_osv(_('CONFIGURATION !'), _("Por favor configurar las cuentas de inventario de la compañia, este proceso lo debe realizar un usuario administrador, en el menu /Ajustes/Compañias/Compañias."))
            
                move_ids_7 = self.env['account.move.line'].search([('period_id','=',period.id),('account_id','in',account_ids)])
                cont=1
                l_mario=[]
                for move in move_ids_7:
                    print len(move_ids_7)                    
                    print cont
                    cont+=1
                    picking = picking_obj.search([('account_move_id','=',move.move_id.id),('state','=','done')])
                    if len(picking) > 1:
                        print "------mario----"
                        print picking
                        print ""
                        print ERROR
                        print ""
                    
                    if picking and not picking.date_done[0:10] == move.date:
                        print "xxxxxxxxx"
                        print picking.date_done[0:10]
                        print move.date
                        print ""
                        print ERROR
                    
                    if not picking:
                        if move.move_id.id not in l_mario and not inventory_obj.search([('account_move_id','=',move.move_id.id)]):
                            l_mario.append(move.move_id.id)
                            self._cr.execute(''' SELECT SUM(debit-credit) FROM account_move_line WHERE move_id=%s AND account_id in %s AND date >= %s AND date <= %s''',(move.move_id.id, account_ids, period.date_start, period.date_stop))
                            amount=self._cr.fetchall()[0]
                            if isinstance(amount, (list, tuple)):
                                amount = amount[0]
                            else:
                                amount = amount
                            self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                                (period.id,amount,'account.move',move.move_id.id,validation_id,date,self._uid,self.company_id.id,'ASIENTOS CONTABLES SIN EQUIVALENTE LOGISTICO','MOVIMIENTO CONTABLES DE CUENTAS DE INVENTARIO QUE NO ESTAN RELACIONADOS A UN PICKING O A UN AJUSTE DE INVENTARIO, SE DEBE REALIZAR UNA VALIDACION Y SEGUIMIENTO A ESTOS REGISTROS PORQUE ESTAN DESCUADRANDO LA CONTABILIDAD','EN EL NOMBRE SE AGREGA EL ID DEL REGISTRO Y EN EL MODELO EL TIPO DE DOCUMENTO. POR FAVOR VALIDAR EL ORIGEN DE ESTE DOCUMENTO Y MEDIANTE PERFILERIA Y CONTROL INTERNO, CONTROLAR Y MITIGAR ESTE RIESGO'))
                            validation_ids.append(self._cr.fetchone()[0])


        if self.picking_consu:
            print ""
            print "---------------------------------------------------------------------------------------------------"
            print "FUNCION QUE REVISA QUE TODOS LOS MOVIMIENTOS DE PRODUCTOS CONSUMIBLES NO TENGAN AFECTACION CONTABLE"
            print "---------------------------------------------------------------------------------------------------"
            print ""
        
            for period in periods:
                move_ids = move_obj.search([('product_id.type','!=','product'),('picking_id','!=',False),('state','=','done'),('date','>=',period.date_start),('date','<=',period.date_stop)])
                
                cont= 1
                for move in move_ids:
                    if move.picking_id.account_move_id:
                        self._cr.execute('''INSERT INTO avancys_validation_line (amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                            (move.total_cost,'stock.move',move.id,validation_id,date,self._uid,self.company_id.id,'MOVIMIENTO DE PRODUCTOS CONSUMIBLES CON AFECTACION CONTABLE','MOVIMIENTO QUE GENERARON AFECTACION CONTABLE, ES POSIBLE QUE ESTEN MAL, SE DEBE REVISAR SU EQUIVALENCIA CONTABLE.','EN EL NOMBRE SE AGREGA EL ID DEL REGISTRO Y EN EL MODELO EL TIPO DE DOCUMENTO.'))
                        validation_ids.append(self._cr.fetchone()[0])
                        
        #if self.product_detail:
            #dict={}
            #cont=1
            #product_ids = tuple([x.id for x in product_obj.search([('active','=',True),('type','=','product')])])
            #location_ids = tuple([x.id for x in location_obj.search([('active','=',True),('usage','=','internal')])])
            #location_virtual_ids = tuple([x.id for x in location_obj.search([('active','=',True),('usage','!=','internal')])])
            
            #if self.company_id.account_inventory_ids:
                #account_ids = tuple([x.id for x in self.company_id.account_inventory_ids])
            #else:
                #raise osv.except_osv(_('CONFIGURATION !'), _("Por favor configurar las cuentas de inventario de la compañia, este proceso lo debe realizar un usuario administrador, en el menu /Ajustes/Compañias/Compañias."))
            
            #for period in periods:
                #d_start=period.date_start+' 00:00:01'
                #d_stop=period.date_stop+' 23:59:59'
                #print "------------------------------------------------------------"
                #print "------- CALCULA TODAS LAS SALIDAS SALDOS FINALES------------"
                #print "------------------------------------------------------------"
                #print ""
                #self._cr.execute('''SELECT  
                                        #product_template.name,
                                        #SUM(stock_move.product_qty),
                                        #SUM(stock_move.total_cost)
                                    #FROM
                                        #product_template,
                                        #product_product,
                                        #stock_location,
                                        #stock_move
                                    #WHERE  
                                        #product_template.id = product_product.product_tmpl_id
                                        #AND product_product.id in %s
                                        #AND stock_location.id =  stock_move.location_id
                                        #AND product_product.id = stock_move.product_id
                                        #AND stock_move.location_id in %s
                                        #AND stock_move.location_dest_id in %s
                                        #AND product_template.type = 'product'
                                        #AND (stock_move.date >= %s AND stock_move.date <= %s AND stock_move.state = 'done')
                                    #GROUP BY
                                        #product_template.name''',
                            #(product_ids,location_ids,location_virtual_ids,d_start,d_stop))   
                #result = self._cr.fetchall()
                #for res in result:
                    #product_name = res[0] or 'Indefinido',
                    #amount_out  = float(res[1]) or 0.0,
                    #total_out  = float(res[2]) or 0.0,
                    #key = (product_name)
                    
                    #dict[key]={'amount_out': amount_out, 'total_out': total_out}
                        
                        
                #print "-------------------------------------------------------------"
                #print "------- CALCULA TODOS LOS INGRESOS SALDOS FINALES------------"
                #print "-------------------------------------------------------------"
                #print ""
                #self._cr.execute('''SELECT  
                                        #product_template.name,
                                        #SUM(stock_move.product_qty),
                                        #SUM(stock_move.total_cost)
                                    #FROM 
                                        #product_template,
                                        #product_product,
                                        #stock_location,
                                        #stock_move
                                    #WHERE  
                                        #product_template.id = product_product.product_tmpl_id
                                        #AND product_product.id in %s
                                        #AND stock_location.id =  stock_move.location_id
                                        #AND product_product.id = stock_move.product_id
                                        #AND stock_move.location_dest_id in %s
                                        #AND stock_move.location_id in %s
                                        #AND product_template.type = 'product'
                                        #AND (stock_move.date >= %s AND stock_move.date <= %s AND stock_move.state = 'done')
                                    #GROUP BY
                                        #product_template.name''',
                            #(product_ids,location_ids,location_virtual_ids,d_start,d_stop))   
                #resultw = self._cr.fetchall()
                #for res in resultw:
                    #product_name = res[0] or 'Indefinido',
                    #amount_in  = float(res[1]) or 0.0,
                    #total_in  = float(res[2]) or 0.0,
                    #key = (product_name)
                    
                    
                    #if isinstance(product_name, (list, tuple)):
                        #product_name = product_name[0]
                    #else:
                        #product_name = product_name
                        
                    #if isinstance(amount_in, (list, tuple)):
                        #amount_in = amount_in[0]
                    #else:
                        #amount_in = amount_in
                    
                    #if isinstance(total_in, (list, tuple)):
                        #total_in = total_in[0]
                    #else:
                        #total_in = total_in
                                            
                    #try:
                        #if isinstance(dict[key]['amount_out'], (list, tuple)):
                            #amount_out = dict[key]['amount_out'][0]
                        #else:
                            #amount_out = dict[key]['amount_out']
                    #except:
                        #amount_out = 0.0
                        
                    #try:
                        #if isinstance(dict[key]['total_out'], (list, tuple)):
                            #total_out = dict[key]['total_out'][0]
                        #else:
                            #total_out = dict[key]['total_out']
                    #except:
                        #total_out = 0.0
                                                            
                
                    #amount_inv = amount_in - amount_out
                    #total_inv = total_in - total_out
                                
                    #print ""
                    #print cont
                    #print product_name
                    #print len(resultw)
                    #print ""
                    #cont+=1
                    
                
                    #self._cr.execute('''SELECT
                                            #SUM(debit - credit)
                                        #FROM
                                            #account_move_line
                                        #WHERE  
                                            #name = %s
                                            #AND account_id in %s
                                            #AND state = 'done'
                                            #AND (date >= %s AND date <= %s)''',
                                    #(product_name,account_ids,d_start,d_stop))
                    #result1 = self._cr.fetchall()
                    #for res in result1:
                        #total_account  = float(res[0] or 0.0),
                        
                        #try:
                            #if isinstance(total_account, (list, tuple)):
                                #total_account = total_account[0]
                            #else:
                                #total_account = total_account
                        #except:
                            #total_account = 0.0
                    
                    #if abs(total_account - total_inv) >= self.company_id.tolerancia:
                        #products = product_obj.search([('name','=',product_name),('active','=',True)])
                        #for p in products:
                            #self._cr.execute('''SELECT
                                                    #SUM(total_cost)
                                                #FROM
                                                    #stock_move
                                                #WHERE 
                                                    #product_id = %s
                                                    #AND location_id in %s
                                                    #AND location_dest_id in %s
                                                    #AND (date >= %s AND date <= %s AND state = 'done')''',
                                        #(p.id,location_ids,location_virtual_ids,d_start,d_stop))   
                            #result = self._cr.fetchall()
                            #for res in result:
                                #total_new_out  = float(res[0] or 0.0),
                                    
                            #self._cr.execute('''SELECT
                                                    #SUM(total_cost)
                                                #FROM
                                                    #stock_move
                                                #WHERE 
                                                    #product_id = %s                                                    
                                                    #AND location_dest_id in %s
                                                    #AND location_id in %s
                                                    #AND (date >= %s AND date <= %s AND state = 'done')''',
                                        #(p.id,location_ids,location_virtual_ids,d_start,d_stop))   
                            #result = self._cr.fetchall()
                            #for res in result:
                                #total_new_in  = float(res[0] or 0.0),
                            
                            #if isinstance(total_new_out, (list, tuple)):
                                #total_new_out = total_new_out[0]
                            #else:
                                #total_new_out = total_new_out
                            
                            #if isinstance(total_new_in, (list, tuple)):
                                #total_new_in = total_new_in[0]
                            #else:
                                #total_new_in = total_new_in
                                        
                            #total_new = total_new_in - total_new_out
                            
                            
                            #self._cr.execute('''SELECT
                                                    #SUM(debit - credit)
                                                #FROM
                                                    #account_move_line
                                                #WHERE  
                                                    #name = %s
                                                    #AND account_id in %s
                                                    #AND state = 'done'
                                                    #AND (date >= %s AND date <= %s)''',
                                            #(p.default_code,account_ids,d_start,d_stop))
                            #result1 = self._cr.fetchall()
                            #for res in result1:
                                #total_account_new  = float(res[0] or 0.0),
                                
                                #try:
                                    #if isinstance(total_account_new, (list, tuple)):
                                        #total_account_new = total_account_new[0]
                                    #else:
                                        #total_account_new = total_account_new
                                #except:
                                    #total_account_new = 0.0
                            
                            
                            #if abs(total_new - total_account_new) >= self.company_id.tolerancia:
                                
                                #self._cr.execute('''INSERT INTO avancys_validation_line (period_id,amount,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                                    #(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                                    #(period.id,abs(total_account_new - total_new),'product.product',p.id,validation_id,date,self._uid,self.company_id.id,'DIFERECIAS POR PRODUCTO DETALLADO','TOTAL CONTABLE -> '+str(total_account_new)+' VS TOTAL INVENTARIO ->'+ str(total_new),product_name))
                
        print ""
        print ""
        print "************************************************"
        print "************** FUNCIONES EXTERNAS **************"
        print "************************************************"
        print ""
        
        print ""
        print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
        print "FUNCION QUE REVISA MOVIMIENTOS NO ASENTADOS EN PERIODOS ABIERTOS"
        print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
        print ""
        for account_move_id in account_move_obj.search([('company_id','=',self.company_id.id),('period_id.state','=','draft'),('state','=','draft')]):
            self._cr.execute('''INSERT INTO avancys_validation_line (model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                ('account.move',account_move_id.id,validation_id,date,self._uid,self.company_id.id,'MOVIMIENTO NO ASENTADO EN UN PERIODO ABIERTO','MOVIMIENTO QUE ESTA PENDIENTE POR ASENTAR, RECUERDE QUE PUEDE REALIZAR ESTE PROCESO DE FORMA AUTOMATICAMENTE EN LA OPCION ***Auto-Asentar Asientos Creados*** DEL DIARIO ASOCIADO','EN EL NOMBRE SE AGREGA EL ID DEL REGISTRO Y EN EL MODELO EL TIPO DE DOCUMENTO.'))
            validation_ids.append(self._cr.fetchone()[0])
            
        print ""
        print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
        print "FUNCION QUE REVISA MOVIMIENTOS NO ASENTADOS EN PERIODOS YA CERRADOS"
        print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
        print ""
        for account_move_id in account_move_obj.search([('company_id','=',self.company_id.id),('period_id.state','=','done'),('state','!=','posted')]):
            self._cr.execute('''INSERT INTO avancys_validation_line (model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                ('account.move',account_move_id.id,validation_id,date,self._uid,self.company_id.id,'MOVIMIENTO NO ASENTADO EN UN PERIODO CERRADO','MOVIMIENTO QUE ESTA PENDIENTE POR ASENTAR, RECUERDE QUE PUEDE REALIZAR ESTE PROCESO DE FORMA AUTOMATICAMENTE EN LA OPCION ***Auto-Asentar Asientos Creados*** DEL DIARIO ASOCIADO','EN EL NOMBRE SE AGREGA EL ID DEL REGISTRO Y EN EL MODELO EL TIPO DE DOCUMENTO.'))
            validation_ids.append(self._cr.fetchone()[0])
        
        
        if self.cost_zero:
            print ""
            print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
            print "FUNCION QUE REVISA TODOS LOS MOVIMIENTOS DE INVENTARIO DE PERIODOS ABIERTOS CON COSTO CERO"
            print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
            print ""
            for period in periods:
                move_ids_6 = move_obj.search([('product_id.type','=','product'),('state','=','done'),('date','>=',period.date_start),('date','<=',period.date_stop),('company_id','=',self.company_id.id),('cost','<=',0.0)])            
                if  move_ids_6:
                    for move in move_ids_6:
                        self._cr.execute('''INSERT INTO avancys_validation_line (amount,period_id,model,name,validation_id,create_date,create_uid,company_id,type,description,observaciones) VALUES 
                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                            (move.product_id.standard_price, period.id,'stock.move',move.id,validation_id,date,self._uid,self.company_id.id,'MOVES CON COSTO CERO','MOVIMIENTO DE INVENTARIO CON COSTO UNITARIO CERO, SE DEBE REALIZAR UNA VALIDACION Y SEGUIMIENTO AL PRODUCTO','EN EL NOMBRE SE AGREGA EL ID DEL REGISTRO Y EN EL MODELO EL TIPO DE DOCUMENTO. POR FAVOR VALIDAR LA CONFIGURACION DEL METODO DE COSTEO DEL PRODUCTO'))
                        validation_ids.append(self._cr.fetchone()[0])

        
        print ""
        print "************************************************"
        print "***         CONTABILIDAD ANALITICA           ***"
        print "************************************************"
        print ""
        
        
        if self.company_id.config_analytic_global and self.config_analytic_global:
            print ""
            print "-------------------------------------------------------------------------------------------------------------------------"
            print "FUNCION QUE ACTUALIZA LAS CUENTAS ANALITICAS PARA AQUELLAS EMPRESAS QUE TIENEN CONFIGURADO A NIVEL DE COMPAÑIA LA GESTION"
            print "-------------------------------------------------------------------------------------------------------------------------"
            print ""
        
            for period in periods:     
                #PICKING
                pickings = self.env['stock.picking'].search([('account_move_id','!=',False),('date_done','>=',period.date_start),('date_done','<=',period.date_stop),('state','=','done')])
                for picking in pickings:
                    if picking.move_lines:
                        move = picking.move_lines[0]
                        if move.account_analytic_id:
                            account_analytic_id = move.account_analytic_id.id
                            self._cr.execute(''' UPDATE account_move_line SET analytic_account_id=%s WHERE move_id = %s''',(account_analytic_id, picking.account_move_id.id))
                #VOUCHERS
                vouchers = self.env['account.voucher'].search([('analytic_account_id','!=',False),('date','>=',period.date_start),('date','<=',period.date_stop),('state','=','posted')])
                for voucher in vouchers:
                    if voucher.move_ids and voucher.move_ids[0].move_id:
                        self._cr.execute(''' UPDATE account_move_line SET analytic_account_id=%s WHERE move_id = %s''',(voucher.analytic_account_id.id, voucher.move_ids[0].move_id.id))
                #FACTURAS
                invoices = self.env['account.invoice'].search([('move_id','!=',False),('date_invoice','>=',period.date_start),('date_invoice','<=',period.date_stop),('state','in',['open','paid'])])
                for invoice in invoices:
                    if invoice.invoice_line and invoice.invoice_line[0].account_analytic_id:
                        self._cr.execute(''' UPDATE account_move_line SET analytic_account_id=%s WHERE move_id = %s''',(invoice.invoice_line[0].account_analytic_id.id, invoice.move_id.id))
                
        
        print ""
        print "************************************************"
        print "**************       ARREGLOS     **************"
        print "************************************************"
        print ""
      
        if move_delete:
            print len(move_delete)
            self._cr.execute(''' DELETE FROM account_move WHERE id in %s''',(tuple(move_delete),))
        
        print "************************************************"
        domain = [('id','=',validation_id)]        
        return {
            'domain': domain,
            'name': 'Proceso de Validacion',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'avancys.validation',
            'type': 'ir.actions.act_window'
        }
    
            
#
