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



class stock_inventory_cost(models.Model):
    _name = "stock.inventory.cost"
    _inherit = ['mail.thread']
    _order = 'name desc'
        
    @api.one
    @api.depends('move_ids')
    def _move(self):
        if self.move_ids:                  
            self.move_count = len(self.move_ids)
    
    @api.one
    @api.depends('line_ids')
    def _line(self):
        if self.line_ids:                  
            self.line_count = len(self.line_ids)
    
    @api.one
    @api.depends('location_id')
    def _warehouse(self):
        if self.location_id:                  
            self.warehouse_id = self.pool.get('stock.location').get_warehouse(self._cr,self._uid,self.location_id,context=self._context) or False
            
    @api.one
    @api.depends('causal')
    def _stock_type(self):
        model_obj = self.env['ir.model'].search([('model','=','product.warehouse.standard.price')])
        if model_obj:
            self.cost_por_bodega = True
        else:
            self.cost_por_bodega = False
                
    
    cost_por_bodega=fields.Boolean(string="Costo Bodega", compute="_stock_type", readonly=True)
    line_count=fields.Integer(string='Move Count', compute="_line")
    move_count=fields.Integer(string='Move Count', compute="_move")
    move_ids=fields.One2many('stock.move', 'inventory_cost_id',string='Movimientos', readonly=True, states={'borrador':[('invisible',True)]})
    name=fields.Char(string='Nombre', readonly=True)
    causal=fields.Char(string='Causal', readonly=True, required=True, states={'borrador':[('readonly',False)]})
    create_date=fields.Datetime(string='Fecha Creacion', readonly=True)
    create_uid=fields.Many2one('res.users', string='Usuario Creacion', readonly=True)
    date=fields.Datetime(string='Fecha', default=datetime.now()+timedelta(minutes=5), readonly=True, states={'aprobado':[('readonly',True)]})
    date_confirm=fields.Datetime(string='Fecha Confirmacion', readonly=True)
    user_confirm=fields.Many2one('res.users', string='Usuario Confirmacion', readonly=True)
    date_aprobacion=fields.Datetime(string='Fecha Aprobacion', readonly=True)
    user_aprobacion=fields.Many2one('res.users', string='Usuario Aprobacion', readonly=True)   
    warehouse_id=fields.Many2one('stock.warehouse',string='Almacen', readonly=True, compute="_warehouse")
    location_id=fields.Many2one('stock.location',string='Ubicacion', required=True, readonly=True, states={'borrador':[('readonly',False)]}, domain=[('usage','=', 'internal')])    
    observaciones=fields.Text(string='Observaciones', readonly=False, states={'aprobado':[('readonly',True)]})
    line_ids=fields.One2many('stock.inventory.cost.line', 'order_id', string='Items', required=True)
    state=fields.Selection([('borrador', 'Borrador'),('confirmado', 'Confirmado'),('aprobado', 'Aprobado'),('cancelado', 'Cancelado')], string='Estado', select=True, default='borrador')
    recosteo=fields.Boolean(string='Recosteo', readonly=False, states={'aprobado':[('readonly',True)]})
    recosteo_feedforward=fields.Boolean(string='Recosteo FEEDFORWARD', readonly=False, states={'aprobado':[('readonly',True)]})
    recosteo_feedback=fields.Boolean(string='Recosteo FEEDBACK', readonly=False, states={'aprobado':[('readonly',True)]})
    feedforward_text=fields.Text(string="Recosteo", readonly=True, default="FEEDFORWARD: actualizacion hacia adelante, actualiza el costo PROMEDIO/POR_BODEGA de los productos asociados al actual documento. Toma como referencia la Fecha seleccionada para recalcular el costo unitario y total de todos los movimientos que sean mayores o iguales a esta.")
    feedback_text=fields.Text(string="Recosteo", readonly=True, default="FEEDBACK: actualizacion hacia atras, esta opcion actualiza el costo PROMEDIO/POR_BODEGA de los productos asociados al actual documento. Toma como referencia la Fecha seleccionada para actualizar el costo unitario y total de todos los movimientos que sean menores a esta.")
    text=fields.Text(string="Recosteo", readonly=True, default="En caso de ser necesario, este proceso realiza un movimiento de ajuste  para garantizar  que a la Fecha se  tengan  las  existencias seleccionadas (Cantidad Real). Tener en cuenta que con esta funcionalidad se podrian perder trazabilidad del costo PROMEDIO/POR_BODEGA para los movimientos de inventario. Por ser un procedimiento de alto impacto y sin reversion, debe varidar toda la informacion y configuracion antes de aprobar este documento.")
    validate=fields.Boolean(string='Validado')
    journal_stock_id=fields.Many2one('account.journal', string="Diario Stock", domain=[('stock_journal','=',True)])
    journal_cost_id=fields.Many2one('account.journal', string="Diario Costo", domain=[('type','=','general')])
    move_stock=fields.Many2one('account.move', string="Movimiento Contable Stock")
    move_cost=fields.Many2one('account.move', string="Movimiento Contable Costo")
    
    _track = {
        'state': {
            'stock_inventory_cost.mt_borrador': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'borrador',
            'stock_inventory_cost.mt_confirmado': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'confirmado',
            'stock_inventory_cost.mt_aprobado': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'aprobado',
            'stock_inventory_cost.mt_cancelado': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelado',
        }        
    }
        
    def view_moves(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for move in self.browse(cr, uid, ids, context=context).move_ids:
            inv.append(move.id)
        
        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Movimientos de Ajuste',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'stock.move',
                'type': 'ir.actions.act_window'
            }
    
    def view_products(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for move in self.browse(cr, uid, ids, context=context).line_ids:
            inv.append(move.product_id.id)
        
        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Productos del Ajuste',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'product.product',
                'type': 'ir.actions.act_window'
            }
    
    
    @api.multi
    def confirmado(self):
        if not self.line_ids:
            raise osv.except_osv(_('Error !'), _("Para confirmar la solicitud de actualizacion de costo debe agregar lineas de productos "))
        number_seq = self.env['ir.sequence'].get('stock.inventoy.cost.number')
        return self.write({'date_confirm': datetime.now(), 'user_confirm': self._uid,'state': 'confirmado','name':number_seq})
    
    @api.multi
    def aprobado(self):
        quant_obj = self.env['stock.quant']
        account_obj = self.env['account.move']
        move_obj = self.env['stock.move']
        period_obj = self.env['account.period']
        location_obj = self.env['stock.location']
        location_id = location_obj.search([('usage','=','inventory')], limit=1)
        company_id = self.env['res.users'].browse(self._uid).company_id.id
        location_ids = []
        cont1 = 0
        cont2 = 0
        move_id = False
        for location in location_obj.search([('usage','=','internal')]):
            if self.cost_por_bodega:
                if self.warehouse_id.id == self.pool.get('stock.location').get_warehouse(self._cr,self._uid,location,context=self._context):
                    location_ids.append(location.id)
            else:
                location_ids.append(location.id)
        location_ids = tuple(location_ids)
        
        if not location_id:
            raise osv.except_osv(_('Error !'), _("Para realizar esta operacion debe contar con una ubicacion de tipo Inventary, la cual sera tenida en cuenta como ubicacion origen en los movimeintos de ajuste"))
            
        for line in self.line_ids:
            #VALIDACIONES DE QUE LA INFORMACION DE CANTIDAD Y COSTO SIGUEN DE ACUERDO A LA FECHA DE PLANEACION
            cost = 0.0
            qty = 0.0            
            # CALCULA EL INVENTARIO A UNA FECHA DETERMINADA
            self._cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move AS sm
                                WHERE  
                                    product_id = %s
                                    AND location_dest_id = %s
                                    AND (date <= %s AND state = 'done')''',
                                (line.product_id.id,line.order_id.location_id.id,datetime.now()+timedelta(hours=60)))
            result = self._cr.fetchall()
            for res in result:
                qty_in = res[0] or 0.0            
            self._cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    product_id = %s
                                    AND location_id = %s
                                    AND (date <= %s AND state = 'done')''',
                                (line.product_id.id,line.order_id.location_id.id,datetime.now()+timedelta(hours=60)))
            result = self._cr.fetchall()
            for res in result:
                qty_out = res[0] or 0.0                    
            qty = qty_in - qty_out     
            
            if line.product_qty_actual != qty:
                raise osv.except_osv(_('Las condiciones del ajuste, no son iguales a las iniciales !'), _("La 'Cantidad Actual' era de %s, en este momento el sistema registra un inventario de %s, por favor cancelar el ajuste y registrarlo nuevamente.")%(line.product_qty_actual,qty))
            try:
                cost_id = self.env['product.warehouse.standard.price'].search([('product_id','=',line.product_id.product_tmpl_id.id),('warehouse_id','=',line.order_id.warehouse_id.id)], limit=1)
                if cost_id:
                    cost = cost_id.standard_price
            except:
                cost = self.product_id.standard_price
            
            if cost != line.cost_actual:
                raise osv.except_osv(_('Las condiciones del ajuste, no son iguales a las iniciales !'), _("El 'Costo Actual' era de %s, en este momento el sistema registra un costo promedio de %s, por favor cancelar el ajuste y registrarlo nuevamente.")%(line.cost_actual,cost))
                
            balance = line.product_qty - line.product_qty_actual  
            
            if not self.recosteo:
                date_now = datetime.now()
                # MOVIMIENTOS DE INVENTARIO
                if balance < 0.0:
                    self._cr.execute('''INSERT INTO stock_move (inventory_cost_id,create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,total_cost,origin) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        (self.id, date_now, line.product_id.uom_id.id, 'make_to_stock', company_id, line.product_id.uom_id.id, line.product_id.id, 'none', abs(balance), abs(balance),'Ajuste Negativo'+' '+ self.name, date_now, date_now, self.location_id.id, location_id.id, 'draft', line.cost, line.cost*abs(balance), 'Ajuste Negativo'+' '+self.name))
                    move_id = move_obj.browse(self._cr.fetchone()[0])          
                elif balance > 0.0:
                    self._cr.execute('''INSERT INTO stock_move (inventory_cost_id,create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,total_cost,origin) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        (self.id, date_now, line.product_id.uom_id.id, 'make_to_stock', company_id, line.product_id.uom_id.id, line.product_id.id, 'none', balance, balance,'Ajuste Positivo'+' '+ self.name, date_now, date_now, location_id.id, self.location_id.id, 'draft', line.cost, line.cost*balance, 'Ajuste Positivo'+' '+self.name))
                    move_id = move_obj.browse(self._cr.fetchone()[0])
                elif line.cost != line.cost_actual:
                    self._cr.execute('''INSERT INTO stock_move (inventory_cost_id,create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,total_cost,origin) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        (self.id, date_now, line.product_id.uom_id.id, 'make_to_stock', company_id, line.product_id.uom_id.id, line.product_id.id, 'none', 0.0, 0.0,'Ajuste al Costo'+' '+ self.name, date_now, date_now, location_id.id, self.location_id.id, 'draft', line.cost, 0.0, 'Ajuste al Costo'+' '+self.name))
                    move_id = move_obj.browse(self._cr.fetchone()[0])
                
                if move_id:
                    move_id.action_done()                
                    self._cr.execute(''' UPDATE stock_move SET date=%s WHERE id=%s''',(date_now, move_id.id))
                    
                    # RECOSTEO PARA MOVIMIENTOS NO TRANSFERIDOS
                    self._cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=product_qty*%s WHERE product_id=%s and location_id in %s and state != 'done' ''',(line.cost, line.cost, line.product_id.id, location_ids))
                    
                    # ACTUALIZACION DE COSTO PROMEDIO / POR_BODEGA
                    if line.cost != line.cost_actual:
                        if self.cost_por_bodega:                        
                            cost_id = self.env['product.warehouse.standard.price'].search([('product_id','=',line.product_id.product_tmpl_id.id),('warehouse_id','=',self.warehouse_id.id)], limit=1)
                            if cost_id:
                                self._cr.execute(''' UPDATE product_warehouse_standard_price SET standard_price=%s WHERE product_id=%s and warehouse_id=%s''',(line.cost, line.product_id.product_tmpl_id.id, self.warehouse_id.id))
                            else:
                                raise osv.except_osv(_('Error !'), _("No existe un costo definido en el producto '%s' para la bodega '%s'") % (line.product_id.default_code,self.warehouse_id.name))
                        else:
                            line.product_id.standard_price = line.cost
                            
                                    
                    # AFECTACION CONTABLE INVENTARIO
                    if line.account_stock_id:
                        amount_stock = abs(line.cost*balance)
                        if balance > 0.0:
                            account_debit_id = line.product_id.categ_id.property_stock_account_input_categ and line.product_id.categ_id.property_stock_account_input_categ.id
                            account_credit_id = line.account_stock_id.id
                            
                        elif balance < 0.0:
                            account_debit_id = line.account_stock_id.id
                            account_credit_id = line.product_id.categ_id.property_stock_account_input_categ and line.product_id.categ_id.property_stock_account_input_categ.id
                        else:
                            continue
                        
                        if not self.journal_stock_id:
                            raise osv.except_osv(_('Error !'), _("Para realizar esta operacion debe configurar el diario de stock en el presente documento."))
                            
                        if cont1 < 1:
                            date = datetime.now().date()
                            period_id = period_obj.search([('date_start','<=',date),('date_stop','>=',date)])
                            if not period_id:
                                raise osv.except_osv(_('Error !'), _("No se encontro un periodo contable para '%s'.")% (date))
                                                    
                            move_vals1 = {
                            'date': date,
                            'ref': self.name,
                            'period_id': period_id.id,
                            'journal_id': self.journal_stock_id.id,
                            }
                            move1 = account_obj.sudo().create(move_vals1)
                            self.move_stock=move1.id
                            cont1+=1
                        
                        self._cr.execute('''insert into account_move_line (credit, date, name, debit, ref, move_id, journal_id, account_id, period_id, partner_id, state, company_id) values 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                        (0.0,date,self.name,amount_stock,line.product_id.default_code or line.product_id.name, move1.id, self.journal_stock_id.id, account_debit_id, period_id.id, company_id, 'draft', company_id))
                        
                        self._cr.execute('''insert into account_move_line (credit, date, name, debit, ref, move_id, journal_id, account_id, period_id, partner_id, state, company_id) values 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                        (amount_stock,date,self.name,0.0,line.product_id.default_code or line.product_id.name, move1.id, self.journal_stock_id.id, account_credit_id, period_id.id, company_id, 'draft', company_id))
                        
                    # AFECTACION CONTABLE COSTOS
                    if line.account_cost_id:                        
                        if not self.journal_cost_id:
                            raise osv.except_osv(_('Error !'), _("Para realizar esta operacion, debe configurar el diario de costo en el presente documento."))
                        
                        amount_cost = line.cost - line.cost_actual
                        if amount_cost > 0.0:
                            account_debit_id = line.product_id.categ_id.property_stock_account_input_categ and line.product_id.categ_id.property_stock_account_input_categ.id
                            account_credit_id = line.account_cost_id.id
                            
                        elif amount_cost < 0.0:
                            account_debit_id = line.account_cost_id.id
                            account_credit_id = line.product_id.categ_id.property_stock_account_input_categ and line.product_id.categ_id.property_stock_account_input_categ.id
                        else:
                            continue
                        
                        if cont2 < 1:
                            date = datetime.now().date()
                            period_id = period_obj.search([('date_start','<=',date),('date_stop','>=',date)])
                            if not period_id:
                                raise osv.except_osv(_('Error !'), _("No se encontro un periodo contable para '%s'.")% (date))
                            
                            move_vals2 = {
                            'date': date,
                            'ref': self.name,
                            'period_id': period_id.id,
                            'journal_id': self.journal_cost_id.id,
                            }
                            move2 = account_obj.sudo().create(move_vals2)
                            self.move_cost=move2.id
                            cont2+=1
                        
                        self._cr.execute('''insert into account_move_line (credit, date, name, debit, ref, move_id, journal_id, account_id, period_id, partner_id, state, company_id) values 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                        (0.0,date,self.name,abs(amount_cost),line.product_id.default_code or line.product_id.name, move2.id, self.journal_cost_id.id, account_debit_id, period_id.id, company_id, 'draft', company_id))
                        
                        self._cr.execute('''insert into account_move_line (credit, date, name, debit, ref, move_id, journal_id, account_id, period_id, partner_id, state, company_id) values 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                        (abs(amount_cost),date,self.name,0.0,line.product_id.default_code or line.product_id.name, move2.id, self.journal_cost_id.id, account_credit_id, period_id.id, company_id, 'draft', company_id))
                
                
                print "------- ELIMINANDO QUANTS DEL PRODUCTO PARA UNA UBICACION ESPECIFICA ------------"
                self._cr.execute(''' DELETE FROM stock_quant WHERE product_id=%s and location_id=%s''',(line.product_id.id,self.location_id.id))
                
                self._cr.execute('''SELECT 
                                        SUM(product_qty)
                                    FROM 
                                        stock_move AS sm
                                    WHERE  
                                        product_id = %s
                                        AND location_dest_id = %s
                                        AND (state = 'done')''',
                                    (line.product_id.id,self.location_id.id))
                result = self._cr.fetchall()
                for res in result:
                    qty_in = res[0] or 0.0            
                self._cr.execute('''SELECT 
                                        SUM(product_qty)
                                    FROM 
                                        stock_move
                                    WHERE  
                                        product_id = %s
                                        AND location_id = %s
                                        AND (state = 'done')''',
                                    (line.product_id.id,self.location_id.id))
                result = self._cr.fetchall()
                for res in result:
                    qty_out = res[0] or 0.0
                
                product_qty_end = qty_in - qty_out
                if product_qty_end > 0.0:
                    vals = {
                        'create_date': datetime.now(),
                        'company_id' : company_id,
                        'product_id' : line.product_id.id,
                        'qty' : product_qty_end,
                        'in_date' : datetime.now(),
                        'location_id': self.location_id.id,
                        'cost': line.cost,
                    }
                    quant_id = quant_obj.create(vals)
                
            else:                
                date_now = self.date
                # MOVIMIENTOS DE INVENTARIO
                if balance < 0.0:
                    self._cr.execute('''INSERT INTO stock_move (inventory_cost_id,create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,total_cost,origin) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        (self.id, date_now, line.product_id.uom_id.id, 'make_to_stock', company_id, line.product_id.uom_id.id, line.product_id.id, 'none', abs(balance), abs(balance),'Ajuste Negativo'+' '+ self.name, date_now, date_now, self.location_id.id, location_id.id, 'draft', line.cost, line.cost*abs(balance), 'Ajuste Negativo'+' '+self.name))
                    move_id = move_obj.browse(self._cr.fetchone()[0])          
                elif balance > 0.0:
                    self._cr.execute('''INSERT INTO stock_move (inventory_cost_id,create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,total_cost,origin) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        (self.id, date_now, line.product_id.uom_id.id, 'make_to_stock', company_id, line.product_id.uom_id.id, line.product_id.id, 'none', balance, balance,'Ajuste Positivo'+' '+ self.name, date_now, date_now, location_id.id, self.location_id.id, 'draft', line.cost, line.cost*balance, 'Ajuste Positivo'+' '+self.name))
                    move_id = move_obj.browse(self._cr.fetchone()[0])
                elif line.cost != line.cost_actual:
                    self._cr.execute('''INSERT INTO stock_move (inventory_cost_id,create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,total_cost,origin) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        (self.id, date_now, line.product_id.uom_id.id, 'make_to_stock', company_id, line.product_id.uom_id.id, line.product_id.id, 'none', 0.0, 0.0,'Ajuste al Costo'+' '+ self.name, date_now, date_now, location_id.id, self.location_id.id, 'draft', line.cost, 0.0, 'Ajuste al Costo'+' '+self.name))
                    move_id = move_obj.browse(self._cr.fetchone()[0])
                else:
                    continue
                
                move_id.action_done()
                self._cr.execute(''' UPDATE stock_move SET date=%s WHERE id=%s''',(date_now, move_id.id))
                
                # RECOSTEO PARA MOVIMIENTOS YA TRANSFERIDOS TRANSFERIDOS
                moves_cost = move_obj.search([('product_id', '=', product_id),('date', '>', date_now),('state','=','done')])
                cost_calc = line.cost 
                if moves_cost:                                                  
                    sorted_lines=sorted(moves_cost, key=lambda x: x.date)                    
                    for move in sorted_lines:
                        qty_in_cost = 0.0
                        qty_out_cost = 0.0
                        qty_move_cost = 0.0
                        
                        if move.location_id.usage in ['supplier','production'] and move.location_dest_id.usage == 'internal':
                            self._cr.execute('''SELECT 
                                                SUM(product_qty)
                                            FROM 
                                                stock_move
                                            WHERE  
                                                product_id = %s
                                                AND location_dest_id in %s
                                                AND (date <= %s AND state = 'done')''',
                                        (line.product_id.id,location_ids,move.date))
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
                                                AND (date <= %s AND state = 'done')''',
                                        (line.product_id.id,location_ids,move.date))
                            result = self._cr.fetchall()
                            for res in result:
                                qty_out_cost = res[0] or 0.0                       
                            qty_move_cost = qty_in_cost - qty_out_cost
                            cost_calc = (qty_move_cost*cost_calc + move.product_qty*move.cost)/(qty_move_cost+move.product_qty)
                            line.product_id.write({'standard_price': cost_calc})
                        else:
                            self._cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=%s WHERE id=%s''',(cost_calc, cost_calc*move.product_qty, move.id))
                                                    
                else:
                    line.product_id.write({'standard_price': cost_calc})
                        
                self._cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=product_qty*%s WHERE product_id=%s and location_id in %s and state != 'done' ''',(cost_calc, cost_calc, line.product_id.id, location_ids))
                                
                # ACTUALIZACION DE LOS QUANTS A VALOR PRESENTE
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
                                            AND product_id = %s
                                            AND stock_location.id =  stock_move.location_id
                                            AND product_product.id = stock_move.product_id
                                            AND stock_move.location_id in %s
                                            AND product_template.type = 'product'
                                            AND stock_move.state = 'done'
                                        GROUP BY
                                            product_product.id,
                                            product_template.id,
                                            product_category.name,
                                            product_template.name,
                                            stock_location.id,
                                            product_product.default_code,
                                            stock_location.id''',
                                    (line.product_id.id,location_ids))
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
                    
                    dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'location_id':location_id, 'qty_in':0.0, 'qty_out':0.0, 'qty_out_end': qty_out_end}
                        
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
                                        AND product_id = %s
                                        AND stock_location.id =  stock_move.location_dest_id
                                        AND product_product.id = stock_move.product_id
                                        AND stock_move.location_dest_id in %s
                                        AND product_template.type = 'product'
                                        AND stock_move.state = 'done'
                                    GROUP BY
                                        product_product.id,
                                        product_template.id,
                                        product_category.name,
                                        product_template.name,
                                        stock_location.id,
                                        product_product.default_code''',
                            (line.product_id.id,location_ids))        
                    
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
                    
                    print "------- ELIMINANDO QUANTS DEL PRODUCTO PARA UNA UBICACION ESPECIFICA ------------"
                    cr.execute(''' DELETE FROM stock_quant WHERE product_id=%s and location_id=%s''',(product_id,location_id))
                    
                    if product_qty_end > 0.0:
                        vals = {
                            'create_date': datetime.now(),
                            'company_id' : company_id,
                            'product_id' : product_id,
                            'qty' : product_qty_end,
                            'in_date' : datetime.now(),
                            'location_id': location_id,
                            'cost': cost_calc,
                        }
                        quant_id = quant_obj.create(vals)
                

                # AFECTACION CONTABLE INVENTARIO
                if line.account_stock_id:
                    amount_stock = abs(line.cost*balance)
                    if balance > 0.0:
                        account_debit_id = line.product_id.categ_id.property_stock_account_input_categ and line.product_id.categ_id.property_stock_account_input_categ.id
                        account_credit_id = line.account_stock_id.id
                        
                    elif balance < 0.0:
                        account_debit_id = line.account_stock_id.id
                        account_credit_id = line.product_id.categ_id.property_stock_account_input_categ and line.product_id.categ_id.property_stock_account_input_categ.id
                    else:
                        continue
                    
                    if not self.journal_stock_id:
                        raise osv.except_osv(_('Error !'), _("Para realizar esta operacion debe configurar el diario de stock en el presente documento."))
                        
                    if cont1 < 1:
                        date = datetime.strptime(date_now, DEFAULT_SERVER_DATE_FORMAT).date()
                        period_id = period_obj.search([('date_start','<=',date),('date_stop','>=',date)])
                        if not period_id:
                            raise osv.except_osv(_('Error !'), _("No se encontro un periodo contable para '%s'.")% (date))
                                                
                        move_vals1 = {
                        'date': date,
                        'ref': self.name,
                        'period_id': period_id.id,
                        'journal_id': self.journal_stock_id.id,
                        }
                        move1 = account_obj.sudo().create(move_vals1)
                        self.move_stock=move1.id
                        cont1+=1
                     
                    self._cr.execute('''insert into account_move_line (credit, date, name, debit, ref, move_id, journal_id, account_id, period_id, partner_id, state, company_id) values 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (0.0,date,self.name,amount_stock,line.product_id.default_code or line.product_id.name, move1.id, self.journal_stock_id.id, account_debit_id, period_id.id, company_id, 'draft', company_id))
                    
                    self._cr.execute('''insert into account_move_line (credit, date, name, debit, ref, move_id, journal_id, account_id, period_id, partner_id, state, company_id) values 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (amount_stock,date,self.name,0.0,line.product_id.default_code or line.product_id.name, move1.id, self.journal_stock_id.id, account_credit_id, period_id.id, company_id, 'draft', company_id))
                    
                # AFECTACION CONTABLE COSTOS
                if line.account_cost_id:
                    if not self.journal_cost_id:
                        raise osv.except_osv(_('Error !'), _("Para realizar esta operacion, debe configurar el diario de costo en el presente documento."))
                    
                    amount_cost = line.cost - line.cost_actual
                    if amount_cost > 0.0:
                        account_debit_id = line.product_id.categ_id.property_stock_account_input_categ and line.product_id.categ_id.property_stock_account_input_categ.id
                        account_credit_id = line.account_cost_id.id
                        
                    elif amount_cost < 0.0:
                        account_debit_id = line.account_cost_id.id
                        account_credit_id = line.product_id.categ_id.property_stock_account_input_categ and line.product_id.categ_id.property_stock_account_input_categ.id
                    else:
                        continue
                    
                    if cont2 < 1:
                        date = datetime.strptime(date_now, DEFAULT_SERVER_DATE_FORMAT).date()
                        period_id = period_obj.search([('date_start','<=',date),('date_stop','>=',date)])
                        if not period_id:
                            raise osv.except_osv(_('Error !'), _("No se encontro un periodo contable para '%s'.")% (date))
                        
                        move_vals2 = {
                        'date': date,
                        'ref': self.name,
                        'period_id': period_id.id,
                        'journal_id': self.journal_cost_id.id,
                        }
                        move2 = account_obj.sudo().create(move_vals2)
                        self.move_cost=move2.id
                        cont2+=1
                     
                    self._cr.execute('''insert into account_move_line (credit, date, name, debit, ref, move_id, journal_id, account_id, period_id, partner_id, state, company_id) values 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (0.0,date,self.name,abs(amount_cost),line.product_id.default_code or line.product_id.name, move2.id, self.journal_cost_id.id, account_debit_id, period_id.id, company_id, 'draft', company_id))
                    
                    self._cr.execute('''insert into account_move_line (credit, date, name, debit, ref, move_id, journal_id, account_id, period_id, partner_id, state, company_id) values 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (abs(amount_cost),date,self.name,0.0,line.product_id.default_code or line.product_id.name, move2.id, self.journal_cost_id.id, account_credit_id, period_id.id, company_id, 'draft', company_id))
                

        return self.write({'date_aprobacion': datetime.now(), 'user_aprobacion': self._uid,'state': 'aprobado'})
    
    
    @api.multi
    def cancelado(self):       
        return self.write({'state': 'cancelado'})
    
        

class stock_inventory_cost_line(models.Model):
    _name = "stock.inventory.cost.line"
    
    @api.one
    @api.depends('product_id', 'order_id.location_id', 'order_id.date')
    def _stock(self):
        if self.product_id and self.order_id.location_id and self.order_id.date:   
            cost = 0.0
            qty = 0.0            
            # CALCULA EL INVENTARIO A UNA FECHA DETERMINADA
            self._cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move AS sm
                                WHERE  
                                    product_id = %s
                                    AND location_dest_id = %s
                                    AND (date <= %s AND state = 'done')''',
                                (self.product_id.id,self.order_id.location_id.id,self.order_id.date))
            result = self._cr.fetchall()
            for res in result:
                qty_in = res[0] or 0.0            
            self._cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    product_id = %s
                                    AND location_id = %s
                                    AND (date <= %s AND state = 'done')''',
                                (self.product_id.id,self.order_id.location_id.id,self.order_id.date))
            result = self._cr.fetchall()
            for res in result:
                qty_out = res[0] or 0.0                    
            qty = qty_in - qty_out            
            
            # CALCULA EL COSTO PROMEDIO O POR BODEGA DEPENDIENDO DE LA OPCION DE RECOSTEO            
            if self.order_id.recosteo:
                location_ids = []            
                for location in self.env['stock.location'].search([('usage','=','internal')]):
                    if self.order_id.warehouse_id.id == self.pool.get('stock.location').get_warehouse(self._cr,self._uid,location,context=self._context):
                        location_ids.append(location.id)
                location_ids = tuple(location_ids) 
                self._cr.execute('''SELECT 
                                        cost
                                    FROM 
                                        stock_move
                                    WHERE  
                                        product_id = %s
                                        AND (location_id in %s OR location_dest_id in %s)
                                        AND (date <= %s AND state = 'done')
                                    ORDER BY
                                        date desc
                                    LIMIT 1''',
                                    (self.product_id.id,location_ids,location_ids,self.order_id.date))
                res = self._cr.fetchall()
                if res:
                    if isinstance(res[0], (list, tuple)):
                        cost = res[0][0]
                    else:
                        cost = res[0]
            else:
                try:
                    cost_id = self.env['product.warehouse.standard.price'].search([('product_id','=',self.product_id.product_tmpl_id.id),('warehouse_id','=',self.order_id.warehouse_id.id)], limit=1)
                    if cost_id:
                        cost = cost_id.standard_price
                except:
                    cost = self.product_id.standard_price
            
            self.cost_actual = float(cost)
            self.product_qty_actual = qty
                
        
    observaciones=fields.Char(string='Nota')
    product_id=fields.Many2one('product.product',string='Producto', required=True)
    product_uom_id=fields.Many2one('product.uom',string='Unidad', related="product_id.uom_id", readonly=True)
    account_stock_id=fields.Many2one('account.account',string='Cuenta Stock', domain=[('type','!=', 'view')])
    account_cost_id=fields.Many2one('account.account',string='Cuenta Costo', domain=[('type','!=', 'view')])
    cost_actual=fields.Float(string='Costo Actual', readonly=True, digits=dp.get_precision('Account'), compute="_stock", store=True) 
    cost=fields.Float(string='Costo Real', required=True, digits=dp.get_precision('Account'))
    product_qty_actual=fields.Float(string='Cantidad Actual', readonly=True, digits=dp.get_precision('Product UoM'), compute="_stock", store=True)
    product_qty=fields.Float(string='Cantidad real', required=True, digits=dp.get_precision('Product UoM'))
    order_id=fields.Many2one('stock.inventory.cost', string='Inventario/costo', readonly=True)
    
    

class stock_move(models.Model):
    _inherit = "stock.move"
    
    inventory_cost_id=fields.Many2one('stock.inventory.cost', string='Inventario/costo', readonly=True)
#
