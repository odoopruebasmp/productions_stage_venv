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

class stock_report_sql_group_location_lot(models.Model):
    _name = "stock.report.sql.group.location.lot"
    
    name = fields.Char(string='Name', required=True)
    location_ids = fields.Many2many('stock.location', string='Ubicaciones', required=True)
    

class stock_report_sql_group_product_lot(models.Model):
    _name = "stock.report.sql.group.product.lot"
    
    name = fields.Char(string='Name', required=True)
    product_ids = fields.Many2many('product.product', string='Productos', required=True)
    

class stock_report_sql_line_lot(models.Model):
    _name = 'stock.report.sql.line.lot'            
    
    product_id = fields.Char(string='Producto')
    product_ref = fields.Char(string='Referencia Interna')
    product_category = fields.Char(string='Linea de Producto')    
    product_category_padre = fields.Char(string='Linea Padre')
    location_id = fields.Many2one('stock.location', string='Ubicacion')
    warehouse_id = fields.Many2one('stock.warehouse', string='Bodega')
    product_qty_end = fields.Float(string='Cantidad', digits_compute=dp.get_precision('Product UoM'))
    cost_end = fields.Float(string='Costo Unitario', digits=dp.get_precision('Account'))
    cost_total_end = fields.Float(string='Costo Total', digits=dp.get_precision('Account'))
    company_id = fields.Many2one('res.company', string='Compania')
    lot_id = fields.Many2one('stock.production.lot', string='Serial/Lote')
    
    
class stock_report_sql_wizard_lot(models.TransientModel):
    _name = 'stock.report.sql.wizard.lot'
    
    group_location_ids = fields.Many2one('stock.report.sql.group.location.lot', string='Ubicaciones')
    group_product_ids = fields.Many2one('stock.report.sql.group.product.lot', string='Productos')
    warehouse_id = fields.Many2one('stock.warehouse', string='Bodega')
    report_option = fields.Selection([('location', 'Ubicacion'),('warehouse', 'Bodega')], string='Bodega/Ubicacion', required=True, default='location')
        
        
    @api.multi
    def calcular_report(self):
        report_line_obj = self.env['stock.report.sql.line.lot']
        product_obj = self.env['product.product']
        location_obj = self.env['stock.location']
        warehouse_obj = self.env['stock.warehouse']
        location_obj2 = self.pool.get('stock.location')
        location_supplier = tuple([x.id for x in location_obj.search([('active','=',True),('usage','=','supplier')])])
        company_id = self.env['res.company'].search([])[0]
        l_ids = []
        location_ids_dos = []
        cont = 1
        cost_end = 0.0
        inicio = datetime.now()
        warehouses={}
        date=datetime.now()+timedelta(days=5)
        
        if self.group_product_ids:
            product_ids = tuple([x.id for x in self.group_product_ids.product_ids])
        else:
            product_ids = tuple([x.id for x in product_obj.search([('active','=',True),('type','=','product')])])
        
        
        for l in location_obj.search([('active','=',True),('usage','=','internal')]):
            warehouse_id = warehouse_obj.search([('view_location_id.parent_left', '<=', l.parent_left),('view_location_id.parent_right', '>=', l.parent_left)])
            warehouses[l.id]={'warehouse':warehouse_id.id}
        
        if self.report_option == 'location':
            if self.group_location_ids:
                location_ids = tuple([x.id for x in self.group_location_ids.location_ids])
            else:
                location_ids = tuple([x.id for x in location_obj.search([('active','=',True),('usage','=','internal')])])
        else:
            locations_internas = [x for x in location_obj.search([('active','=',True),('usage','=','internal')])]
            
            if self.warehouse_id:                
                for location in locations_internas:
                    if self.warehouse_id.id == location_obj2.get_warehouse(self._cr,self._uid,location,context=self._context):
                        location_ids_dos.append(location.id)
                location_ids = tuple(location_ids_dos)
            else:
                location_ids = tuple([x.id for x in location_obj.search([('active','=',True),('usage','=','internal')])])
        
        print ""
        print "--------------------------------------------------------------------"
        print "---------------       ELIMINANDO REGISTROS        ------------------"
        print "--------------------------------------------------------------------"
        print ""
        self._cr.execute(''' DELETE FROM stock_report_sql_line_lot''')
         
                
        print "-------------------------------------------------------------"
        print "-------            CALCULA LA DISPONIBILIDAD     ------------"
        print "-------------------------------------------------------------"
        print ""
        self._cr.execute('''SELECT 
                                product_category.name, 
                                product_product.id,
                                product_template.id,
                                product_template.name,
                                product_product.default_code,
                                stock_location.id,
                                stock_quant.lot_id,
                                SUM(stock_quant.qty)
                            FROM 
                                product_product,
                                stock_location,
                                product_category,
                                product_template,
                                stock_quant
                            WHERE  
                                product_template.id = product_product.product_tmpl_id
                                AND product_category.id = product_template.categ_id
                                AND product_id in %s
                                AND stock_location.id =  stock_quant.location_id
                                AND product_product.id = stock_quant.product_id
                                AND stock_quant.location_id in %s
                                AND product_template.type = 'product'
                            GROUP BY
                                product_category.name, 
                                product_product.id,
                                product_template.id,
                                product_template.name,
                                product_product.default_code,
                                stock_location.id,
                                stock_quant.lot_id''',
                    (product_ids,location_ids))        
        
        result = self._cr.fetchall()
        for res in result:
            product_category = res[0] or 'Indefinida', 
            product_id   = res[1],
            template_id   = res[2],
            product_name = res[3] or 'Indefinido', 
            product_ref = res[4] or 'Indefinido',
            location_id = res[5] or 'Indefinido',
            lot_id = res[6] or False,
            qty  = float(res[7]) or 0.0,
                                    
            
            
            if isinstance(location_id, (list, tuple)):
                location_id = location_id[0]
            else:
                location_id = location_id
            
            if isinstance(warehouses[location_id]['warehouse'], (list, tuple)):
                warehouse_id = warehouses[location_id]['warehouse']
            else:
                warehouse_id = warehouses[location_id]['warehouse']
            
            self._cr.execute('''SELECT
                                    costo_promedio,
                                    cost
                                FROM
                                    stock_move
                                WHERE  
                                    product_id = %s
                                    AND (date <= %s AND stock_move.state = 'done')
                                ORDER BY
                                    date''',
                            (product_id,date))
            result1 = self._cr.fetchall()                
            if result1:
                cost = result1[len(result1)-1][0] or result1[len(result1)-1][1]
            else:
                continue  
            
            
            try:
                if isinstance(qty, (list, tuple)):
                    qty = qty[0]
                else:
                    qty = qty
            except:
                qty = 0.0
                
            try:
                if isinstance(cost, (list, tuple)):
                    cost = cost[0]
                else:
                    cost = cost
            except:
                cost = 0.0
            
            try:
                if isinstance(lot_id, (list, tuple)):
                    lot_id = lot_id[0]
                else:
                    lot_id = lot_id
            except:
                lot_id = False
                
            print ""
            print cont
            print len(result)
            print ""
            cont+=1
            self._cr.execute('''INSERT INTO stock_report_sql_line_lot (lot_id,product_id,location_id,product_qty_end,cost_end,cost_total_end,product_category,product_ref,company_id,warehouse_id) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (lot_id or None,product_name,location_id,qty,cost,qty*cost,product_category,product_ref,company_id.id,warehouse_id or None))
            print "22222222222222"
        
        final = datetime.now()
        diferencia = final-inicio
        
        print "----------------------------------------------------------------------"
        print "----------------------------------------------------------------------"
        print "---------------------------- TERMINO ---------------------------------"
        print "----------------------------------------------------------------------"
        print "                           ",diferencia
        print ""
        print "----------------------------------------------------------------------"
        print ""
          
        return {
            'name': 'Analisis de Inventario',
            'view_type': 'form',
            'view_mode': 'graph,tree',
            'view_id': False,
            'res_model': 'stock.report.sql.line.lot',
            'type': 'ir.actions.act_window'
        }
   
        
#
