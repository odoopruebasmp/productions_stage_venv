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



class stock_inventory_extended(models.Model):
    _name = "stock.inventory.extended"
    _inherit = ['mail.thread']
    _order = 'name desc'    
    
    
    @api.one
    @api.depends('line_ids')
    def _date(self):        
        if self.line_ids:
            move=sorted(self.line_ids, key=lambda y: y.date)[0]
            self.date=move.date
            self.cost=move.cost_update
            
    line_ids=fields.One2many('stock.inventory.extended.line', 'inventory_id',string='Movimientos', required=True, readonly=False, states={'borrador':[('readonly',False)]})
    name=fields.Char(string='Nombre', readonly=True)
    causal=fields.Char(string='Causal', readonly=True, required=True, states={'borrador':[('readonly',False)]})
    date=fields.Datetime(string='Fecha', compute="_date", readonly=True)
    cost=fields.Float(string='Costo', compute="_date", digits=dp.get_precision('Account'), readonly=True, help="Costo de referencia, costo del movimiento mas antiguo y que tomara el sistema para iniciar el recosteo")
    cost_new=fields.Float(string='Costo', digits=dp.get_precision('Account'), readonly=True)
    observaciones=fields.Text(string='Observaciones', readonly=False, states={'validado':[('readonly',True)]})
    state=fields.Selection([('borrador', 'Borrador'),('confirmado', 'Por Aprobacion Logistica'),('aprobado', 'Por Aprobacion Contable'),('por_ejecutar', 'Por Ejecutar'),('ejecutado', 'Por Validar'),('validado', 'Validado'),('cancelado', 'Cancelado')], string='Estado', select=True, default='borrador')
    product_id=fields.Many2one('product.product', string="Producto", required=True, domain=[('type','=','product'),('active','=',True)], readonly=True, states={'borrador':[('readonly',False)]})
    type=fields.Selection([('inventario', 'Inventario'),('contable', 'Contable')], string='Afectacion', required=True, help="Si selecciona 'Inventario', el recosteo tendra solo afectacion de inventario, el valor del valorizado a valor presente se modificara y las analisis de ventas el costo del producto de las facturas relacionadas. Esta opcion no es recomendada ya que todo movimiento de inventario debe tener su reflejo contable y equivalente. Si se selecciona 'Contable',  el recosteo tendra afectacion de inventario y contable, ademas de afectar el informe valorizado y el analisis de ventas, tambien afectara la contabilidad 'Cuentas 14 y 61'.", readonly=True, states={'borrador':[('readonly',False)]})
    
    
    _track = {
        'state': {
            'stock_inventory_extended_mp.mt_borrador': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'borrador',
            'stock_inventory_extended_mp.mt_confirmado': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'confirmado',
            'stock_inventory_extended_mp.mt_aprobado': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'aprobado',
            'stock_inventory_extended_mp.mt_por_ejecutar': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'por_ejecutar',
            'stock_inventory_extended_mp.mt_ejecutado': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'ejecutado',
            'stock_inventory_extended_mp.mt_validado': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'validado',
            'stock_inventory_extended_mp.mt_cancelado': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelado',
        }        
    }    
    
    @api.multi
    def confirmar(self):
        for line in  self.line_ids:
            if len(self.env['stock.inventory.extended.line'].search([('move_id','=',line.move_id.id),('inventory_id','=',self.id)]))>1:
                raise osv.except_osv(_('Un movimiento fue seleccionado mas de una vez!'), _("Por favor realizar una revision del movimiento %s")% (line.move_id.name))
        number_seq = self.env['ir.sequence'].get('stock.inventoy.extended.number')
        return self.write({'state': 'confirmado','name':number_seq})
    
    @api.multi
    def aprobacion_logistica(self):
        return self.write({'state': 'aprobado'})
    
    @api.multi
    def aprobacion_contable(self):
        return self.write({'state': 'por_ejecutar'})
        
    @api.multi
    def ejecutar(self):
        
        move_obj = self.env['stock.move']
        company_id = self.env['res.users'].browse(self._uid).company_id
        location_obj = self.env['stock.location']
        location_ids = tuple([x.id for x in location_obj.search([('active','=',True),('usage','=','internal')])])
        invoices=[]
        pickings=[]
        invoice_lines=[]
        
        #UPDATE MOVES
        for line in self.line_ids:
            if line.cost_update <= 0.0:
                raise osv.except_osv(_('Costo Incorrecto!'), _("Por favor validar el costo del movimiento %s, recuerde que el costo debe ser superior a cero.")% (line.move_id.name))            
            self._cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=product_qty*%s WHERE id = %s''',(line.cost_update,line.cost_update,line.move_id.id))        
        self._cr.commit()
        
        #RECOSTEO
        product_id=self.product_id
        moves_cost = move_obj.search([('product_id', '=', product_id.id),('state', '=', 'done'),('date', '>=', self.date)])
        sorted_lines=sorted(moves_cost, key=lambda x: x.date)
        cont=0
        cost_def=self.cost
        for move in sorted_lines:
            print "--------RECOSTEO-------"
            print move.id
            print len(sorted_lines)
            print cont
            cont+=1
            qty_in_cost = 0.0
            qty_out_cost = 0.0
            qty_move_cost = 0.0
            
            if move.location_id.usage not in ['supplier','production']:
                self._cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=%s, costo_promedio=%s WHERE id=%s''',(cost_def, cost_def*move.product_uom_qty, cost_def, move.id))                
                if company_id.sale_cost_invoice:
                    if move.invoice_line_id:
                        invoices.append(move.invoice_line_id.invoice_id)
                else:
                    if move.picking_id and move.picking_id.account_move_id:
                        pickings.append(move.picking_id)
                        
                if move.invoice_line_id:
                    invoice_lines.append(move.invoice_line_id)
                
            else:
                if move.picking_id and move.picking_id.account_move_id:
                    pickings.append(move.picking_id)
                                        
                self._cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    product_id = %s
                                    AND location_dest_id in %s
                                    AND (date < %s AND state = 'done')''',
                            (product_id.id,location_ids,move.date))
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
                            (product_id.id,location_ids,move.date))
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
                
                
            
        
        
        
        product_id.write({'standard_price': cost_def,'costo_standard':cost_def})
        self._cr.commit()
        self.invalidate_cache()
        contx=1
        conty=1
        
        if invoice_lines:
             for line in invoice_lines:
                 line.date_recalcular = datetime.now()-timedelta(hours=5)
        
        if self.type == "contable":
            self._cr.commit()
            if invoices:
                for invoice in invoices:
                    print "xxxxxxxxCONTABLE-FACTURASxxxxxxxx"
                    print len(invoices)
                    print contx
                    print ""
                    invoice.compute_cost()
                    contx+=1
            self._cr.commit()
            if pickings:
                for picking in pickings:
                    print "xxxxxxxxCONTABLE-PICKINGSxxxxxxxx"
                    print len(pickings)
                    print conty
                    print ""
                    picking.do_transfer_button(bandera=True)
                    conty+=1
        
        return self.write({'state': 'ejecutado', 'cost_new': cost_def})
    
    
    @api.multi
    def validar(self):
        return self.write({'state': 'validado'})
    
    @api.multi
    def cancelar(self):       
        return self.write({'state': 'cancelado'})
    
        

class stock_inventory_extended_line(models.Model):
    _name = "stock.inventory.extended.line"
                
    move_id=fields.Many2one('stock.move',string='Movimiento', required=True)
    product_id=fields.Many2one('product.product',string='Producto', readonly=True, related="inventory_id.product_id")
    product_uom=fields.Many2one('product.uom',string='Unidad', readonly=True, related="move_id.product_uom")    
    product_qty=fields.Float(string='Cantidad', readonly=True, digits=dp.get_precision('Product UoM'), related="move_id.product_qty")
    cost=fields.Float(string='Costo Unitario', readonly=True, digits=dp.get_precision('Account'), related="move_id.cost", store=True)
    total_cost=fields.Float(string='Costo Total', readonly=True, digits=dp.get_precision('Account'), related="move_id.total_cost", store=True)
    inventory_id=fields.Many2one('stock.inventory.extended', string='Inventario/costo', readonly=True)
    note=fields.Char(string='Notas', required=True)
    cost_update=fields.Float(string='Costo Unitario Real', required=True, digits=dp.get_precision('Account'))
    location_id=fields.Many2one('stock.location',string='Origen', readonly=True, related="move_id.location_id")
    location_dest_id=fields.Many2one('stock.location',string='Destino', readonly=True, related="move_id.location_dest_id")
    date=fields.Datetime(string='Fecha', readonly=True, related="move_id.date")
    

class stock_move(models.Model):
    _inherit = "stock.move"
    
    inventory_extended_id=fields.Many2one('stock.inventory.extended', string='Ajuste Inventario/costo', readonly=True)
    
    
#
