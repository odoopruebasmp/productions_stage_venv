import codecs
from openerp import models, fields, api
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.osv import osv
import csv
import base64
import time
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
from datetime import datetime
from openerp.exceptions import except_orm, Warning, RedirectWarning

class deterioro_producto_wiz(models.TransientModel):
    _name = 'deterioro.product.wiz'
    
    date = fields.Datetime(string='Fecha de referencia')
    date_start = fields.Date(string='Fecha Inicial')
    date_end = fields.Date(string='Fecha Final')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type','!=','view'), ('type', '!=', 'closed')])
    product_ids = fields.Many2many('product.product', string='Productos', domain=[('type','=','product'), ('tipo_producto_niff', '!=', False)])
    location_ids = fields.Many2many('stock.location', string='Ubicaciones', domain=[('active','=',True),('usage','=','internal')])
    journal_id = fields.Many2one('account.journal', string='Diario', domain=[('niif','=',True)])
    company_id = fields.Many2one('res.company', string='Compania')
    
    
    @api.multi
    def deterioro(self):    
        moves=[]
        obj_sequence = self.pool.get('ir.sequence')
        products = self.env['product.product'].search([('active','=',True),('is_asset','=',False),('type','=','product'),('deterioro','=','aplica')])
        if products:
            
            
            name = obj_sequence.next_by_id(self._cr, self._uid, self.journal_id.sequence_id.id, context=self._context)
            
            print "11111111111111"
            print name
            print ""
            
            
            period_id = self.env['account.period'].search([('date_start','<=', self.date),('date_stop','>=', self.date),('state','=', 'draft')], limit=1)
            if not period_id:
                raise osv.except_osv(_('Error !'), _("No existe un periodo Abierto para la fecha '%s'") % (self.date))
            
            journal_id = self.journal_id.id
            period_id = period_id.id
            company_id = self.company_id.id
            
            move_vals = {
                'name': name,
                'ref': name,
                'journal_id': journal_id,
                'date': self.date,
                'period_id': period_id,
                'company': company_id,
                'state': 'posted'
                }
            move_id = self.env['account.move'].create(move_vals)
            moves.append(move_id.id)
            for product in products:
                
                move_ref = product.default_code                
                debit_account_id = product.categ_id.account_depreciacion_debit_id and product.categ_id.account_depreciacion_debit_id.id or False
                credit_account_id = product.categ_id.account_depreciacion_credit_id and product.categ_id.account_depreciacion_credit_id.id or False
                amount = abs(product.valor_diferencia_total)
                analytic_account_id = product.categ_id.analytic_inventory_deterioro_id and product.categ_id.analytic_inventory_deterioro_id.id or False
                
                if not credit_account_id:
                    raise osv.except_osv(_('Error !'), _("La categoria '%s' no tiene la cuenta de deterioro de inventario configurada, por favor realizar este proceso o consultar con el area responsable") % (product.categ_id.name))
                
                if not debit_account_id:
                    raise osv.except_osv(_('Error !'), _("La categoria '%s' no tiene la cuenta de gasto deterioro de inventario configurada, por favor realizar este proceso o consultar con el area responsable") % (product.categ_id.name))
                
                print "xxxxxxxxxxxxxx"
                print credit_account_id
                print debit_account_id
                print ""
                #"wwwwwwww  DEBITO wwwwwwwwwww"
                self._cr.execute('''INSERT INTO account_move_line (deterioro_niff_id,account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,journal_id,period_id,company_id,state) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (product.id,debit_account_id,debit_account_id,self.date,name,move_ref,self.date,company_id,0.0,amount,analytic_account_id or None,move_id.id,journal_id,period_id,company_id,'valid'))
                
                #"wwwwwwww  CREDITO wwwwwwwwwww"
                self._cr.execute('''INSERT INTO account_move_line (deterioro_niff_id,account_id,account_niif_id,date,ref,name,date_created,partner_id,credit,debit,analytic_account_id,move_id,journal_id,period_id,company_id,state) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                (product.id,credit_account_id,credit_account_id,self.date,name,move_ref,self.date,company_id,amount,0.0,analytic_account_id or None,move_id.id,journal_id, period_id,company_id,'valid'))
                
                product.costo_standard=product.standard_price
                product.standard_price=product.valor_neto_realizable
        
        domain = [('id','in',moves)]
        return {
            'domain': domain,
            'name': 'Deterioro de Inventario',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'account.move',
            'type': 'ir.actions.act_window'
                }
    
    
    @api.multi
    def update_cost_expense(self):    
        products=[]
        accounts = [x.id for x in self.account_ids]
        self._cr.execute('''SELECT
                                SUM(costo_niif)
                            FROM 
                                product_product
                            WHERE
                                tipo_producto_niff = 'producto_terminado'
                                AND active = True''')
        result = self._cr.fetchall()
        for res in result:
            costos = res[0] or 0.0
            
            if isinstance(costos, (list, tuple)):
                costos = costos[0]            
            costos = abs(costos)            
        
        self._cr.execute('''SELECT
                                SUM(debit-credit)
                            FROM 
                                account_move_line
                            WHERE
                                account_id in %s
                                AND date >= %s
                                AND date <= %s
                                AND state = 'valid' ''', 
                            (tuple(accounts), self.date_start, self.date_end))
        result = self._cr.fetchall()
        for res in result:
            gastos = res[0] or 0.0            
            if isinstance(gastos, (list, tuple)):
                gastos = gastos[0]            
            gastos = abs(gastos)
            
        for product in self.env['product.product'].search([('active','=',True),('is_asset','=',False),('type','=','product'),('tipo_producto_niff','=','producto_terminado'),('costo_total_niif','>',0.0)]):
            products.append(product.id)
            product.costo_estimado_de_venta = ((product.costo_niif/costos)*gastos)/product.qty_niif
            
        domain = [('id','in',products)]
        view_id=self.env['ir.ui.view'].search([('name','=','product.product.niif.form.inherit2')], limit=1)
        
        return {
            'domain': domain,
            'name': 'Productos NIIF',
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': view_id.id,
            'res_model': 'product.product',
            'type': 'ir.actions.act_window'
                }
    
    @api.multi
    def update_semielaborados(self):    
        products=[]
        line_obj = self.env['mrp.bom.line']
        product_obj = self.env['product.product']
        dict={}
        product_ids =product_obj.search([('is_asset','=',False),('active','=',True),('type','=','product'),('tipo_producto_niff','=','semi_elaborado')])
        
        if not product_ids:
            raise osv.except_osv(_('Error !'), _("No existen productos de tipo Semi-elaborados"))
            
        for product in product_ids:
            products.append(product.id)
            self._cr.execute('''SELECT
                                    mrp_bom.product_id
                                FROM 
                                    product_product,
                                    mrp_bom_line,
                                    mrp_bom
                                WHERE  
                                    product_product.id = mrp_bom_line.product_id
                                    AND mrp_bom.id =  mrp_bom_line.bom_id
                                    AND product_product.id = %s 
                                    AND product_product.tipo_producto_niff = 'semi_elaborado' ''',
                        (product.id,))
            result = self._cr.fetchall()
            
            if result:
                print result
                print result[0]
                self._cr.execute('''SELECT
                                        id,
                                        valor_neto_realizable
                                    FROM 
                                        product_product
                                    WHERE  
                                        valor_neto_realizable > 0.0
                                        AND id  in %s
                                    ORDER BY
                                        valor_neto_realizable asc limit 1''',
                            (tuple(result),))
                result1 = self._cr.fetchall()
                
                if result1:
                    p_id    = result1[0][0]
                    amount   = result1[0][1] or 0.0
                    
                    valor_diferencia = amount- product.costo_niif
                    
                    if valor_diferencia < 0.0:
                        deterioro='aplica'
                    else:
                        deterioro='no_aplica'
                        valor_diferencia = 0.0
                        
                    self._cr.execute(''' UPDATE product_product SET costo_end=%s, product_costo_end=%s, date_cost_end=%s, user_cost_end=%s, valor_neto_realizable=%s, deterioro=%s, valor_diferencia=%s, valor_diferencia_total=%s WHERE id=%s''',(amount, p_id, fields.datetime.now(), self._uid, amount*product.amount_costo_end/100, deterioro, valor_diferencia, valor_diferencia*product.qty_niif, product.id))
            
            
        domain = [('id','in',products)]
        view_id=self.env['ir.ui.view'].search([('name','=','product.product.niif.form.inherit2')], limit=1)
        return {
            'domain': domain,
            'name': 'Productos NIIF',
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': view_id.id,
            'res_model': 'product.product',
            'type': 'ir.actions.act_window'
                }
    
    
    @api.multi
    def update_qty(self):  
        products=[]
        location_obj = self.env['stock.location']
        product_obj = self.env['product.product']
        dict={}
        if self.product_ids:
            product_ids = tuple([x.id for x in self.product_ids])
        else:
            product_ids = tuple([x.id for x in product_obj.search([('is_asset','=',False),('active','=',True),('type','=','product'),('tipo_producto_niff','!=',False)])])
        if self.location_ids:
            location_ids = tuple([x.id for x in self.location_ids])
        else:
            location_ids = tuple([x.id for x in location_obj.search([('active','=',True),('usage','=','internal')])])
        
        self._cr.execute('''SELECT 
                                product_category.name, 
                                product_product.id,
                                product_template.id,
                                product_template.name,
                                product_product.default_code,
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
                                AND product_product.id in %s
                                AND stock_location.id =  stock_move.location_dest_id
                                AND product_product.id = stock_move.product_id
                                AND stock_move.location_id in %s
                                AND product_template.type = 'product'
                                AND (stock_move.date <= %s AND stock_move.state = 'done')
                            GROUP BY
                                product_product.id,
                                product_template.id,
                                product_category.name,
                                product_template.name,
                                product_product.default_code''',
                    (product_ids,location_ids,self.date))
        result = self._cr.fetchall()
        for res in result:
            categoria    = res[0] or 'Indefinida', 
            product_id   = res[1],
            template_id   = res[2],
            product_name = res[3] or 'Indefinido', 
            default_code = res[4] or 'Indefinido',
            qty_out  = float(res[5]) or 0.0,
            count  = float(res[6]) or 0.0,
            
            if isinstance(product_id, (list, tuple)):
                product_id = product_id[0]
                    
            key = (product_id)
            
            dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'qty_out':qty_out}
        
        self._cr.execute('''SELECT 
                                product_category.name, 
                                product_product.id,
                                product_template.id,
                                product_template.name,
                                product_product.default_code,
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
                                AND product_product.id in %s
                                AND stock_location.id =  stock_move.location_id
                                AND product_product.id = stock_move.product_id
                                AND stock_move.location_dest_id in %s
                                AND product_template.type = 'product'
                                AND (stock_move.date <= %s AND stock_move.state = 'done')
                            GROUP BY
                                product_product.id,
                                product_template.id,
                                product_category.name,
                                product_template.name,
                                product_product.default_code''',
                    (product_ids,location_ids,self.date))        
        
        result = self._cr.fetchall()
        for res in result:
            categoria    = res[0] or 'Indefinida', 
            product_id   = res[1],
            template_id   = res[2],
            product_name = res[3] or 'Indefinido', 
            default_code = res[4] or 'Indefinido',
            qty_in  = float(res[5]) or 0.0,
            count  = float(res[6]) or 0.0,
            
            if isinstance(product_id, (list, tuple)):
                product_id = product_id[0]
                
            key = (product_id)
            
            if key in dict:
                dict[key].update({'qty_in': qty_in})
            else:
                dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'qty_out': 0.0, 'qty_in': qty_in}
                
            cost=0.0
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
                            (product_id,self.date))
            result1 = self._cr.fetchall()                
            if result1:
                cost = result1[len(result1)-1][0] or result1[len(result1)-1][1] 
                        
            try:
                if isinstance(dict[key]['qty_in'], (list, tuple)):
                    qty_in = dict[key]['qty_in'][0]
                else:
                    qty_in = dict[key]['qty_in']
            except:
                qty_in = 0.0
                
            try:
                if isinstance(dict[key]['qty_out'], (list, tuple)):
                    qty_out = dict[key]['qty_out'][0]
                else:
                    qty_out = dict[key]['qty_out']
            except:
                qty_out = 0.0
            
            print "11111111111111"
            print qty_in
            print qty_out
            product_qty = qty_in - qty_out
            
            costo_total_niif = product_qty*cost
            
            products.append(product_id)
            
            self._cr.execute(''' UPDATE product_product SET costo_total_niif=%s, costo_niif=%s, qty_niif=%s, date_qty_cost=%s, date_qty_cost_update=%s, user_qty_cost=%s WHERE id=%s''',(costo_total_niif, cost, product_qty, self.date, fields.datetime.now(), self._uid, product_id))
            
        domain = [('id','in',products)]
        view_id=self.env['ir.ui.view'].search([('name','=','product.product.niif.form.inherit2')], limit=1)
        return {
            'domain': domain,
            'name': 'Productos NIIF',
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': view_id.id,
            'res_model': 'product.product',
            'type': 'ir.actions.act_window'
                }
            
            
    
    
    @api.multi
    def update_price(self):    
        products=[]
        for product in self.env['product.product'].search([('active','=',True),('is_asset','=',False),('type','=','product'),('tipo_producto_niff','=','producto_terminado')]):
            products.append(product.id)
            product.price_niif=product.lst_price
                    
        domain = [('id','in',products)]
        view_id=self.env['ir.ui.view'].search([('name','=','product.product.niif.form.inherit2')], limit=1)
        return {
            'domain': domain,
            'name': 'Productos NIIF',
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': view_id.id,
            'res_model': 'product.product',
            'type': 'ir.actions.act_window'
                }
    
    @api.multi
    def update_valor_de_reposicion(self):    
        products=[]
        for product in self.env['product.product'].search([('active','=',True),('is_asset','=',False),('type','=','product'),('tipo_producto_niff','=','materia_prima')]):
            products.append(product.id)
            if product.cost_purchase:
                product.price_niif=product.cost_purchase
            else:
                product.price_niif=0.0
                    
        domain = [('id','in',products)]
        view_id=self.env['ir.ui.view'].search([('name','=','product.product.niif.form.inherit2')], limit=1)
        return {
            'domain': domain,
            'name': 'Productos NIIF',
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': view_id.id,
            'res_model': 'product.product',
            'type': 'ir.actions.act_window'
                }
