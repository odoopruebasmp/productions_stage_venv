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


class import_file_move_quant(osv.TransientModel):    
    _name = 'import.file.move.quant'
    
    _columns = {
        'type_operation': fields2.selection([('saldos','Saldos Iniciales'),('update','Actualizacion Movimientos - Quants')], string='Tipo', required=True),
        'file': fields2.binary('File', filters='*.xlsx'),
        'date': fields2.datetime(string='Fecha de Corte Historica', required=True),
        'location_abastecimiento': fields2.many2one('stock.location', string='Ubicacion Abastecimiento', required=True),
        'location_desecho': fields2.many2one('stock.location', string='Ubicacion Desecho', required=True),
        'company_id': fields2.many2one('res.company', string='Compañia', required=True),
        'feedforward': fields2.boolean(string='Feedforward'),
        'feedback': fields2.boolean(string='Feedback'),
        'product_id': fields2.many2one('product.product', 'Producto especifico'),
        'product_list': fields2.text(string='Lista de Productos No actualizados'),
        }
       
    
    def parse_file(self, cr, uid, ids, context=None):
        if not context: context = {}
        rec = self.browse(cr, uid, ids[0], context)
        file_path = tempfile.gettempdir()+'/move_quant.xlsx'
        data = rec.file
        f = open(file_path,'wb')
        f.write(data.decode('base64'))
        f.close()
        wb = xlrd.open_workbook(file_path)
        sheet_list = wb.sheet_names()
        for sheet in sheet_list:
            worksheet = wb.sheet_by_name(sheet)
            order_data_list = []
            for row in range(1, worksheet.nrows):
                order_dict = {}
                for cell in range(worksheet.ncols):
                    if cell== 0:
                        order_dict['product_code'] = worksheet.cell_value(row, cell)
                    elif cell== 1:
                        order_dict['product_qty'] = worksheet.cell_value(row, cell)
                    elif cell== 2:
                        order_dict['location_id'] = worksheet.cell_value(row, cell)
                    elif cell== 3:
                        order_dict['cost'] = worksheet.cell_value(row, cell)
                order_data_list.append(order_dict)
        return order_data_list


    def import_order(self, cr, uid, ids, context=None):
        if not context: context = {}                
        date_import = self.browse(cr, uid, ids, context)[0]
        date = date_import.date
        company_id = date_import.company_id
        location_abastecimiento = date_import.location_abastecimiento.id
        location_desecho = date_import.location_desecho.id
                
        product_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('stock.move')
        quant_obj = self.pool.get('stock.quant')
        location_ids = []
        
        for location in location_obj.search(cr, uid, [('usage','=','internal')]):
            location_ids.append(location)
        location_ids = tuple(location_ids)
        dict = {}
        cost_calc = 0.0
        cont = 1
        qty_in = 0.0
        qty_out = 0.0
        qty_move = 0.0
        qty_in_total = 0.0
        qty_out_total = 0.0
        qty_move_total = 0.0
        cost = 0.0
        cantidad = 0.0
        balance = 0.0
        product_list = ''        
        if date_import.type_operation == 'saldos':
            data_list = self.parse_file(cr, uid, ids, context=context)
            for item in data_list:
                default_code = str(item.get('product_code')).replace(".0", "")
                location_id = str(item.get('location_id')).replace(".0", "")
                cantidad = float(item.get('product_qty'))
                cost = float(item.get('cost'))
                cost_def = cost
                
                # PRODUCTO            
                product_id = product_obj.search(cr, uid, [('default_code', '=', default_code)], limit=1)
                if not product_id:
                    product_list = product_list+' '+str(default_code)
                    print product_list
                    continue       
                product = product_obj.browse(cr, uid, product_id, context)
                #LOCATION
                location_id = location_obj.search(cr, uid, [('id', '=', location_id)], limit=1)            
                if not location_id:
                    raise osv.except_osv(_('Error!'), _('La ubicacion con ID %s no se encuentra registrado en el sistema.'%(item.get('location_id'))))            
                location = location_obj.browse(cr, uid, location_id, context)
                
                product_id = product_id[0]
                location_id = location_id[0]           
                
                
                # CALCULA EL SALDO A LA FECHA DE CORTE HISTORICA
                cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    product_id = %s
                                    AND location_dest_id = %s
                                    AND (date <= %s AND state = 'done')''',
                            (product_id,location_id,date))
                result = cr.fetchall()
                for res in result:
                    qty_in = res[0] or 0.0
                
                cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    product_id = %s
                                    AND location_id = %s
                                    AND (date <= %s AND state = 'done')''',
                            (product_id,location_id,date))
                result = cr.fetchall()
                for res in result:
                    qty_out = res[0] or 0.0
                    
                qty_move = qty_in - qty_out                
                balance = qty_move-cantidad
                                
                #CREACION DE MOVIMIENTO DE INVENTARIO DE AJUSTE
                if balance >0.0:
                    print "------- CREACION DE MOVIMIENTO DE INVENTARIO DE AJUSTE NEGATIVO SIN QUANT ------------"
                    cr.execute('''INSERT INTO stock_move (create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,total_cost,origin) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (datetime.now(),product.uom_id.id,'make_to_stock',company_id.id,product.uom_id.id,product_id,'none',balance,balance,'Ajuste Odoo'+' '+default_code,date,date,location_id,location_desecho,'done',cost,cost*abs(balance),'Ajuste Odoo MARZO-2016'))                
                elif balance < 0.0:               
                    cr.execute('''INSERT INTO stock_move (create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,total_cost,origin) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (datetime.now(),product.uom_id.id,'make_to_stock',company_id.id,product.uom_id.id,product_id,'none',abs(balance),abs(balance),'Ajuste Odoo'+' '+default_code,date,date,location_abastecimiento,location_id,'done',cost,cost*abs(balance),'Ajuste Odoo MARZO-2016'))
                    
                    
            
                # RECOSTEO DE TODOS LOS MOVIMIENTOS SIGUIENTES A LA FECHA DE CORTE HISTORICO
                if date_import.feedforward:
                    moves_cost = move_obj.search(cr, uid, [('product_id', '=', product_id),('state', '=', 'done'),('date', '>', date)])
                    cost_def = cost
                    if moves_cost:
                        cost_def = cost                    
                        moves_cost = move_obj.browse(cr, uid,moves_cost, context=context)           
                        sorted_lines=sorted(moves_cost, key=lambda x: x.date)
                        
                        for move in sorted_lines:
                            qty_in_cost = 0.0
                            qty_out_cost = 0.0
                            qty_move_cost = 0.0
                            if move.location_id.usage != 'supplier':
                                cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=%s WHERE id=%s''',(cost_def, cost_def*move.product_uom_qty, move.id))
                                #move_obj.write(cr, SUPERUSER_ID, [move.id], {'cost': cost_calc}, context=context)
                            else:                        
                                cr.execute('''SELECT 
                                                    SUM(product_qty)
                                                FROM 
                                                    stock_move
                                                WHERE  
                                                    product_id = %s
                                                    AND location_dest_id in %s
                                                    AND (date <= %s AND state = 'done')''',
                                            (product_id,location_ids,move.date))
                                result = cr.fetchall()
                                for res in result:
                                    qty_in_cost = res[0] or 0.0                        
                                cr.execute('''SELECT 
                                                    SUM(product_qty)
                                                FROM 
                                                    stock_move
                                                WHERE  
                                                    product_id = %s
                                                    AND location_id in %s
                                                    AND (date <= %s AND state = 'done')''',
                                            (product_id,location_ids,move.date))
                                result = cr.fetchall()
                                for res in result:
                                    qty_out_cost = res[0] or 0.0                       
                                qty_move_cost = qty_in_cost - qty_out_cost
                                cost_def = (qty_move_cost*cost_def + move.product_qty*move.cost)/(qty_move_cost+move.product_qty)
                                product_obj.write(cr, SUPERUSER_ID, [product_id], {'standard_price': cost_def,'costo_standard':cost}, context=context)
                    else:                        
                        product_obj.write(cr, SUPERUSER_ID, [product_id], {'standard_price': cost_def,'costo_standard':cost}, context=context)
                
                
                # SE VALIDA SI EL INVENTARIO A VALOR PRESENTE ES DIFERENTE A CERO Y SE CREAN LOS QUANTS
                cr.commit()                
                # CALCULA EL SALDO A LA FECHA ACTUAL
                cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    product_id = %s
                                    AND location_dest_id = %s
                                    AND (state = 'done')''',
                            (product_id,location_id))
                result = cr.fetchall()
                for res in result:
                    qty_in_total = res[0] or 0.0
                
                cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    product_id = %s
                                    AND location_id = %s
                                    AND (state = 'done')''',
                            (product_id,location_id))
                result = cr.fetchall()
                for res in result:
                    qty_out_total = res[0] or 0.0
                    
                qty_move_total = qty_in_total - qty_out_total
                
                
                print "------- ELIMINANDO QUANTS DEL PRODUCTO PARA UNA UBICACION ESPECIFICA ------------"
                cr.execute(''' DELETE FROM stock_quant WHERE product_id=%s and location_id=%s''',(product_id,location_id))
                
                if qty_move_total > 0.0:
                    vals = {
                        'create_date': datetime.now(),
                        'company_id' : company_id.id,
                        'product_id' : product_id,
                        'qty' : qty_move_total,
                        'in_date' : datetime.now(),
                        'location_id': location_id,
                        'cost': cost_def,
                    }
                    quant_id = quant_obj.create(cr, uid, vals, context=context)
                
                
                # RECOSTEO PARA MOVIMIENTOS NO TRANSFERIDOS
                cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=product_qty*%s WHERE product_id=%s and location_id in %s and state != 'done' ''',(cost_def, cost_def, product_id, location_ids))
                
                if date_import.feedback:
                    cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=product_qty*%s WHERE product_id=%s and location_id in %s and state = 'done' and date < %s''',(cost, cost, product_id, location_ids, date))                 
        else:
            print "------------------------------------------------------------"
            print "------------------- ELIMINANDO QUANTS ----------------------"
            print "------------------------------------------------------------"
            print ""
            wh_pr = '' if not date_import.product_id else 'WHERE product_id = {pid}'.format(pid=date_import.product_id.id)
            cr.execute(''' DELETE FROM stock_quant {wh_pr}'''.format(wh_pr=wh_pr))
            print "------------------------------------------------------------"
            print "-------   ACTUALIZACION DE QUANTS VERSUS MOVES  ------------"
            print "------------------------------------------------------------"
            print ""
            if date_import.product_id:
                product_ids = tuple([x.id for x in product_obj.browse(cr, uid, date_import.product_id.id)])
            else:
                product_ids = tuple([x for x in product_obj.search(cr, uid,
                                                                   [('active','=',True),('type','!=','service')])])
            location_ids = tuple([x for x in location_obj.search(cr, uid,
                                                                 [('active','=',True),('usage','=','internal')])])
            
            print len(product_ids)
            print len(location_ids)
            print ""
            
            print "------- CALCULA TODAS LAS SALIDAS SALDOS FINALES------------"
            print ""            
            cr.execute('''SELECT  
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
                                product_product.default_code;''',
                    (product_ids,location_ids))   
            result = cr.fetchall()
            print "1111111111111111111111"
            print len(result)
            for res in result:
                categoria    = res[0] or 'Indefinida', 
                product_id   = res[1],
                template_id   = res[2],
                product_name = res[3] or 'Indefinido', 
                default_code = res[4] or 'Indefinido',
                location_id = res[5] or 'Indefinido',
                qty_out_end  = float(res[6]) or 0.0,
                count  = float(res[7]) or 0.0,
                
                if isinstance(product_id, (list, tuple)):
                    product_id = product_id[0]
                else:
                    product_id = product_id
                    
                if isinstance(location_id, (list, tuple)):
                    location_id = location_id[0]
                else:
                    location_id = location_id
                        
                key = (product_id,location_id)
                
                dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'location_id':location_id, 'qty_out_end': qty_out_end}
                    
                    
            print "------- CALCULA TODOS LOS INGRESOS SALDOS FINALES------------"
            print ""
            cr.execute('''SELECT 
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
                                AND stock_move.state = 'done'
                            GROUP BY
                                product_product.id,
                                product_template.id,
                                product_category.name,
                                product_template.name,
                                stock_location.id,
                                product_product.default_code''',
                    (product_ids,location_ids))        
            
            result = cr.fetchall()
            print "2222222222222222222"
            print len(result)
            print ""
            for res in result:
                categoria    = res[0] or 'Indefinida', 
                product_id   = res[1],
                template_id   = res[2],
                product_name = res[3] or 'Indefinido', 
                default_code = res[4] or 'Indefinido',
                location_id = res[5] or 'Indefinido',
                qty_in_end  = float(res[6]) or 0.0,
                count  = float(res[7]) or 0.0,
                
                if isinstance(product_id, (list, tuple)):
                    product_id = product_id[0]
                else:
                    product_id = product_id
                    
                if isinstance(location_id, (list, tuple)):
                    location_id = location_id[0]
                else:
                    location_id = location_id
                
                key = (product_id,location_id)
                
                if key not in dict:
                    qty_out_end = 0.0
                else:                    
                    if isinstance(dict[key]['qty_out_end'], (list, tuple)):
                        qty_out_end = dict[key]['qty_out_end'][0]
                    else:
                        qty_out_end = dict[key]['qty_out_end']
                                    
                if isinstance(qty_in_end, (list, tuple)):
                    qty_in_end = qty_in_end[0]
                else:
                    qty_in_end = qty_in_end
                    
            
                balance = qty_in_end-qty_out_end
                
                print "xxxxxxxxxxxxxxxxxxxxxx"
                print balance
                print qty_in_end
                print qty_out_end
                if balance >= 0.0:                                        
                    # SE CREA EL QUANT SEGUN EL COSTO CALCULADO
                    
                    #cr.execute('''INSERT INTO stock_quant (create_date,company_id,product_id,qty,in_date,location_id,cost) VALUES 
                    #(%s,%s,%s,%s,%s,%s) ''' ,
                    #(datetime.now(),company_id.id,product_id,qty_move_total,date,location_id,cost_def))
                    if balance > 0.0:                            
                        print "------- CREACION DE QUANT DEL PRODUCTO PARA UNA UBICACION ESPECIFICA A LA FECHA ACTUAL------------"
                        if date_import.feedforward:
                            moves_cost = move_obj.search(cr, uid, [('product_id', '=', product_id),'|',('location_id', '=', location_id),('location_dest_id', '=', location_id)])
                            if moves_cost:
                                sorted_lines=sorted(moves_cost, key=lambda x: x.date)                                                    
                                moves_cost = move_obj.browse(cr, uid,sorted_lines, context=context)
                                cost_calc = moves_cost[0].cost
                                for move in moves_cost:                                        
                                    qty_in_cost = 0.0
                                    qty_out_cost = 0.0
                                    qty_move_cost = 0.0
                                    if location_id == move.location_id.id:
                                        cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=%s WHERE id=%s''',(cost_calc, cost_calc*move.product_qty, move.id))
                                        #move_obj.write(cr, SUPERUSER_ID, [move.id], {'cost': cost_calc}, context=context)
                                    else:
                                        cr.execute('''SELECT
                                                            SUM(stock_move.product_qty)
                                                        FROM
                                                            stock_move
                                                        WHERE
                                                            stock_move.product_id = %s
                                                            AND stock_move.location_dest_id = %s
                                                            AND (stock_move.date < %s AND stock_move.state = 'done')''',
                                                    (product_id,location_id,move.date))
                                        result = cr.fetchall()
                                        for res in result:
                                            qty_in_cost = res[0] or 0.0
                                            
                                        cr.execute('''SELECT 
                                                            SUM(stock_move.product_qty)
                                                        FROM 
                                                            stock_move
                                                        WHERE  
                                                            stock_move.product_id = %s
                                                            AND stock_move.location_id = %s
                                                            AND (stock_move.date < %s AND stock_move.state = 'done')''',
                                                    (product_id,location_id,move.date))
                                        result = cr.fetchall()
                                        for res in result:
                                            qty_out_cost = res[0] or 0.0
                                        
                                        
                                        qty_move_cost = qty_in_cost - qty_out_cost
                                        
                                        if qty_move_cost >= 0:
                                            cost_calc = (qty_move_cost*cost_calc + move.product_qty*move.cost)/(qty_move_cost+move.product_qty)
                                            product_obj.write(cr, SUPERUSER_ID, [product_id], {'standard_price': cost_calc}, context=context)
                                            cost_def = cost_calc
                                        else:
                                            cost_calc = 0.0
                                            product_obj.write(cr, SUPERUSER_ID, [product_id], {'standard_price': cost_calc}, context=context)
                                            cost_def = 0.0
                        else:                                                  
                            product = product_obj.browse(cr, uid,product_id, context=context)
                            cost_def = product.standard_price
                        vals = {
                            'create_date': datetime.now(),
                            'company_id' : company_id.id,
                            'product_id' : product_id,
                            'qty' : balance,
                            'in_date' : date,
                            'location_id': location_id,
                            'cost': cost_def,
                        }
                        print "-------------------"
                        quant_id = quant_obj.create(cr, uid, vals, context=context)
                        print "-------------------"
                
                print ""
                print cont
                print len(result)
                cont+=1
        print ""
        print "**********************"
        print "-------TERMINO--------"
        print "**********************"
        print ""
        print product_list
        print ""
        self.write(cr, SUPERUSER_ID, ids, {'product_list': product_list}, context=context)
        datas = {}
        datas['ids'] = ids
        datas['model'] = 'import.file.move.quant'
        return {
        'type': 'ir.actions.report.xml',
        'report_name': 'update_move_quant.reporte_stock_quant_aeroo',
        'report_type': 'aeroo',
        'datas': datas,
        }































































    
    #def import_order(self, cr, uid, ids, context=None):
        #if not context: context = {}                
        #date_import = self.browse(cr, uid, ids, context)[0]
        #date = date_import.date
        #company_id = date_import.company_id
        #location_abastecimiento = date_import.location_abastecimiento.id
        #location_desecho = date_import.location_desecho.id
                
        #product_obj = self.pool.get('product.product')
        #location_obj = self.pool.get('stock.location')
        #invoice_obj = self.pool.get('account.invoice')
        #move_obj = self.pool.get('stock.move')
        #quant_obj = self.pool.get('stock.quant')
        #dict = {}
        #cost_calc = 0.0
        #cont = 1
        #qty_in = 0.0
        #qty_out = 0.0
        #qty_move = 0.0
        #qty_in_total = 0.0
        #qty_out_total = 0.0
        #qty_move_total = 0.0
        #cost = 0.0
        #cantidad = 0.0
        #balance = 0.0
        #product_list = ''     
        #list = []
        #data_list = self.parse_file(cr, uid, ids, context=context)
        #for item in data_list:
            
            #default_code = str(item.get('product_code')).replace(".0", "")
            #cost = float(item.get('cost'))
            
            #print "aaaaaaaaaaaaaaa"
            #print default_code
            #print ""
            
            #product_id = product_obj.search(cr, uid, [('default_code', '=', default_code)], limit=1)
            #if not product_id:
                #product_list = product_list+' '+str(default_code)
                #continue       
            #product = product_obj.browse(cr, uid, product_id, context)
            #product_id = product_id[0]
            
            #move_ids = move_obj.search(cr, uid, [('product_id', '=', product_id)])
            
            #print "bbbbbbbbbbbbbbb"
            #print len(move_ids)
            #print move_ids
            #print tuple(move_ids)
            #print ""
            #if move_ids:
                #cr.execute(''' UPDATE stock_move SET cost=%s WHERE id in %s''',(cost, tuple(move_ids)))
                #cr.execute(''' UPDATE stock_move SET total_cost=cost*product_qty WHERE id in %s''',(tuple(move_ids),))
                #product_obj.write(cr, SUPERUSER_ID, product_id, {'standard_price': cost, 'costo_standard': cost}, context=context)
                
                #for move in move_obj.browse(cr, uid, move_ids, context):
                    #if move.picking_id and move.picking_id.picking_type_id and move.picking_id.picking_type_id.code == "outgoing" and move.picking_id.state == "done":
                        #if not move.picking_id in list:
                            #list.append(move.picking_id)
                #print "ccccccccccccccc"
                #print len(list)
                #print ""
                #if list:
                    #for pick in list:
                        #pick.do_transfer_button()                        
                        #if pick.picking_invoice_id:
                            #invoice_obj.write(cr, SUPERUSER_ID, pick.picking_invoice_id.id, {'ref2': pick.name}, context=context)
                        
                
            
        #print ""
        #print "**********************"
        #print "-------TERMINO--------"
        #print "**********************"
        #print ""
        #print product_list
        #print ""
        #self.write(cr, SUPERUSER_ID, ids, {'product_list': product_list}, context=context)
        #datas = {}
        #datas['ids'] = ids
        #datas['model'] = 'import.file.move.quant'
        #return {
        #'type': 'ir.actions.report.xml',
        #'report_name': 'update_move_quant.reporte_stock_quant_aeroo',
        #'report_type': 'aeroo',
        #'datas': datas,
        #}
    
    
    #def import_order(self, cr, uid, ids, context=None):
        #if not context: context = {}                
        #date_import = self.browse(cr, uid, ids, context)[0]
        #date = date_import.date
        #company_id = date_import.company_id
        #location_abastecimiento = date_import.location_abastecimiento.id
        #location_desecho = date_import.location_desecho.id
                
        #product_obj = self.pool.get('product.product')
        #location_obj = self.pool.get('stock.location')
        #move_obj = self.pool.get('stock.move')
        #quant_obj = self.pool.get('stock.quant')
        #dict = {}
        #cost_calc = 0.0
        #cont = 1
        #qty_in = 0.0
        #qty_out = 0.0
        #qty_move = 0.0
        #qty_in_total = 0.0
        #qty_out_total = 0.0
        #qty_move_total = 0.0
        #cost = 0.0
        #cantidad = 0.0
        #balance = 0.0
        #product_list = ''        
        #if date_import.type_operation == 'saldos':
            #data_list = self.parse_file(cr, uid, ids, context=context)
            #for item in data_list:
                #default_code = str(item.get('product_code')).replace(".0", "")
                #location_id = str(item.get('location_id')).replace(".0", "")
                #cantidad = float(item.get('product_qty'))
                #cost = float(item.get('cost'))
                #cost_def = cost
                
                ## PRODUCTO            
                #product_id = product_obj.search(cr, uid, [('default_code', '=', default_code)], limit=1)
                #if not product_id:
                    #product_list = product_list+' '+str(default_code)
                    #print product_list
                    #continue       
                #product = product_obj.browse(cr, uid, product_id, context)
                ##LOCATION
                #location_id = location_obj.search(cr, uid, [('id', '=', location_id)], limit=1)            
                #if not location_id:
                    #raise osv.except_osv(_('Error!'), _('La ubicacion con ID %s no se encuentra registrado en el sistema.'%(item.get('location_id'))))            
                #location = location_obj.browse(cr, uid, location_id, context)
                
                #product_id = product_id[0]
                #location_id = location_id[0]           
                
                
                ## CALCULA EL SALDO A LA FECHA DE CORTE HISTORICA
                #cr.execute('''SELECT 
                                    #SUM(stock_move.product_qty)
                                #FROM 
                                    #stock_move
                                #WHERE  
                                    #stock_move.product_id = %s
                                    #AND stock_move.location_dest_id = %s
                                    #AND (stock_move.date <= %s AND stock_move.state = 'done')''',
                            #(product_id,location_id,date))
                #result = cr.fetchall()
                #for res in result:
                    #qty_in = res[0] or 0.0
                
                #cr.execute('''SELECT 
                                    #SUM(stock_move.product_qty)
                                #FROM 
                                    #stock_move
                                #WHERE  
                                    #stock_move.product_id = %s
                                    #AND stock_move.location_id = %s
                                    #AND (stock_move.date <= %s AND stock_move.state = 'done')''',
                            #(product_id,location_id,date))
                #result = cr.fetchall()
                #for res in result:
                    #qty_out = res[0] or 0.0
                    
                #qty_move = qty_in - qty_out
                
                
                
                ## CALCULA EL SALDO A LA FECHA ACTUAL
                #cr.execute('''SELECT 
                                    #SUM(stock_move.product_qty)
                                #FROM 
                                    #stock_move
                                #WHERE  
                                    #stock_move.product_id = %s
                                    #AND stock_move.location_dest_id = %s
                                    #AND (stock_move.state = 'done')''',
                            #(product_id,location_id))
                #result = cr.fetchall()
                #for res in result:
                    #qty_in_total = res[0] or 0.0
                
                #cr.execute('''SELECT 
                                    #SUM(stock_move.product_qty)
                                #FROM 
                                    #stock_move
                                #WHERE  
                                    #stock_move.product_id = %s
                                    #AND stock_move.location_id = %s
                                    #AND (stock_move.state = 'done')''',
                            #(product_id,location_id))
                #result = cr.fetchall()
                #for res in result:
                    #qty_out_total = res[0] or 0.0
                    
                #qty_move_total = qty_in_total - qty_out_total
                
                
                #balance = qty_move-cantidad
                                
                ##CREACION DE MOVIMIENTO DE INVENTARIO DE AJUSTE
                #if balance >0.0:
                    #print "------- CREACION DE MOVIMIENTO DE INVENTARIO DE AJUSTE NEGATIVO SIN QUANT ------------"
                    #cr.execute('''INSERT INTO stock_move (create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,origin) VALUES 
                    #(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    #(datetime.now(),product.uom_id.id,'make_to_stock',company_id.id,product.uom_id.id,product_id,'none',balance,balance,'Ajuste Odoo'+' '+default_code,date,date,location_id,location_desecho,'done',cost,'Ajuste Odoo 2015-2016'))                
                #elif balance < 0.0:               
                    #cr.execute('''INSERT INTO stock_move (create_date,weight_uom_id,procure_method,company_id,product_uom,product_id,invoice_state,product_uom_qty,product_qty,name,date,date_expected,location_id,location_dest_id,state,cost,origin) VALUES 
                    #(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    #(datetime.now(),product.uom_id.id,'make_to_stock',company_id.id,product.uom_id.id,product_id,'none',abs(balance),abs(balance),'Ajuste Odoo'+' '+default_code,date,date,location_abastecimiento,location_id,'done',cost,'Ajuste Odoo 2015-2016'))
                    
                    
            
                ## RECOSTEO DE TODOS LOS MOVIMIENTOS SIGUIENTES A LA FECHA DE CORTE HISTORICO
                #if date_import.feedforward:
                    #moves_cost = move_obj.search(cr, uid, [('product_id', '=', product_id),('state', '=', 'done'),('date', '>', date)])
                    #if moves_cost:
                        #cost_calc = cost                    
                        #moves_cost = move_obj.browse(cr, uid,moves_cost, context=context)           
                        #sorted_lines=sorted(moves_cost, key=lambda x: x.date)
                        
                        #for move in sorted_lines:
                            #qty_in_cost = 0.0
                            #qty_out_cost = 0.0
                            #qty_move_cost = 0.0
                            #if move.location_id.usage != 'supplier':
                                #cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=%s WHERE id=%s''',(cost_calc, cost_calc*move.product_uom_qty, move.id))
                                ##move_obj.write(cr, SUPERUSER_ID, [move.id], {'cost': cost_calc}, context=context)
                            #else:                        
                                #cr.execute('''SELECT 
                                                    #SUM(stock_move.product_qty)
                                                #FROM 
                                                    #stock_move
                                                #WHERE  
                                                    #stock_move.product_id = %s
                                                    #AND stock_move.location_id = %s
                                                    #AND (stock_move.date < %s AND stock_move.state = 'done')''',
                                            #(product_id,location_abastecimiento,move.date))
                                #result = cr.fetchall()
                                #for res in result:
                                    #qty_in_cost = res[0] or 0.0                        
                                #cr.execute('''SELECT 
                                                    #SUM(stock_move.product_qty)
                                                #FROM 
                                                    #stock_move
                                                #WHERE  
                                                    #stock_move.product_id = %s
                                                    #AND stock_move.location_dest_id = %s
                                                    #AND (stock_move.date < %s AND stock_move.state = 'done')''',
                                            #(product_id,location_desecho,move.date))
                                #result = cr.fetchall()
                                #for res in result:
                                    #qty_out_cost = res[0] or 0.0                       
                                #qty_move_cost = qty_in_cost - qty_out_cost
                                #cost_calc = (qty_move_cost*cost_calc + move.product_qty*move.cost)/(qty_move_cost+move.product_qty)
                                #product_obj.write(cr, SUPERUSER_ID, [product_id], {'standard_price': cost_calc,'costo_standard':cost}, context=context)
                                ##cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=%s WHERE id=%s''',(cost_calc, cost_calc*move.product_uom_qty, move.id))
                                #cost_def = cost_calc
                    #else:
                        #cost_def = cost
                        #product_obj.write(cr, SUPERUSER_ID, [product_id], {'standard_price': cost_def,'costo_standard':cost}, context=context)
                
                ## SE VALIDA SI EL INVENTARIO A VALOR PRESENTE ES DIFERENTE A CERO Y SE CREAN LOS QUANTS
                ## SE ELIMINAN EL QUANT DEL PRODUCTO PARA LA UBICACION ESPECIFICA
                ##print "------- UPDATE QUANTS DEL PRODUCTO PARA UNA UBICACION ESPECIFICA ------------"
                ##cr.execute(''' UPDATE stock_quant SET cost=%s WHERE product_id=%s''',(cost_def, product_id))                
                    ## SE CREA EL QUANT SEGUN EL COSTO CALCULADO
                    ##print "------- CREACION DE QUANT DEL PRODUCTO PARA UNA UBICACION ESPECIFICA A LA FECHA ACTUAL------------"
                    ##cr.execute('''INSERT INTO stock_quant (create_date,company_id,product_id,qty,in_date,location_id,cost) VALUES 
                    ##(%s,%s,%s,%s,%s,%s) ''' ,
                    ##(datetime.now(),company_id.id,product_id,qty_move_total,date,location_id,cost_def))
                    ##if (qty_move_total - balance) > 0.0: 
                        ##vals = {
                            ##'create_date': datetime.now(),
                            ##'company_id' : company_id.id,
                            ##'product_id' : product_id,
                            ##'qty' : qty_move_total - balance,
                            ##'in_date' : date,
                            ##'location_id': location_id,
                            ##'cost': cost_def,
                        ##}
                        ##quant_id = quant_obj.create(cr, uid, vals, context=context)
                ##else:
                    ##product_list = product_list+' '+str(default_code)
                    
                #if date_import.feedback:                    
                    ## SE ACTUALIZA EL COSTO DE LOS MOVIMIENTOS ANTERIORES A LA FECHA DE CORTE PARA TENER COHERENCIA EN LOS INFORMES DE INVENTARIO
                    ## NO SE REALIZA EN SQL POR LOS CAMPOS CALCULADOS COMO COST_TOTAL
                    ##cr.execute(''' UPDATE stock_move SET cost=%s WHERE id=%s''',(cost_calc,move.id))
                    #moves_old = move_obj.search(cr, uid, [('product_id', '=', product_id),('state', '=', 'done'),('date', '<', date)])
                    #moves_old = move_obj.browse(cr, uid,moves_old, context=context)
                    #if moves_old:
                        #for move in moves_old:
                            #print move
                            #print ""
                            #move_obj.write(cr, SUPERUSER_ID, [move.id], {'cost': cost,'total_cost': move.product_uom_qty*cost}, context=context)                    
        #else:
            #print "------------------------------------------------------------"
            #print "------------------- ELIMINANDO QUANTS ----------------------"
            #print "------------------------------------------------------------"
            #print ""
            #cr.execute(''' DELETE FROM stock_quant''')
            #print "------------------------------------------------------------"
            #print "-------   ACTUALIZACION DE QUANTS VERSUS MOVES  ------------"
            #print "------------------------------------------------------------"
            #print ""
            #product_ids = tuple([x for x in product_obj.search(cr, uid, [('active','=',True),('type','!=','service')])])
            #location_ids = tuple([x for x in location_obj.search(cr, uid, [('active','=',True),('usage','=','internal')])])
            
            #print len(product_ids)
            #print len(location_ids)
            #print ""
            
            #print "------- CALCULA TODAS LAS SALIDAS SALDOS FINALES------------"
            #print ""            
            #cr.execute('''SELECT  
                                #product_category.name, 
                                #product_product.id,
                                #product_template.id,
                                #product_template.name,
                                #product_product.default_code,
                                #stock_location.id,
                                #SUM(stock_move.product_qty),
                                #COUNT(stock_move.product_qty)
                            #FROM 
                                #product_product,
                                #stock_location,
                                #product_category,
                                #product_template,
                                #stock_move
                            #WHERE  
                                #product_template.id = product_product.product_tmpl_id
                                #AND product_category.id = product_template.categ_id
                                #AND product_id in %s
                                #AND stock_location.id =  stock_move.location_id
                                #AND product_product.id = stock_move.product_id
                                #AND stock_move.location_id in %s
                                #AND product_template.type = 'product'
                                #AND stock_move.state = 'done'
                            #GROUP BY
                                #product_product.id,
                                #product_template.id,
                                #product_category.name,
                                #product_template.name,
                                #stock_location.id,
                                #product_product.default_code;''',
                    #(product_ids,location_ids))   
            #result = cr.fetchall()
            #print "1111111111111111111111"
            #print len(result)
            #for res in result:
                #categoria    = res[0] or 'Indefinida', 
                #product_id   = res[1],
                #template_id   = res[2],
                #product_name = res[3] or 'Indefinido', 
                #default_code = res[4] or 'Indefinido',
                #location_id = res[5] or 'Indefinido',
                #qty_out_end  = float(res[6]) or 0.0,
                #count  = float(res[7]) or 0.0,
                
                #if isinstance(product_id, (list, tuple)):
                    #product_id = product_id[0]
                #else:
                    #product_id = product_id
                    
                #if isinstance(location_id, (list, tuple)):
                    #location_id = location_id[0]
                #else:
                    #location_id = location_id
                        
                #key = (product_id,location_id)
                
                #dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'location_id':location_id, 'qty_out_end': qty_out_end}
                    
                    
            #print "------- CALCULA TODOS LOS INGRESOS SALDOS FINALES------------"
            #print ""
            #cr.execute('''SELECT 
                                #product_category.name, 
                                #product_product.id,
                                #product_template.id,
                                #product_template.name,
                                #product_product.default_code,
                                #stock_location.id,
                                #SUM(stock_move.product_qty),
                                #COUNT(stock_move.product_qty)
                            #FROM 
                                #product_product,
                                #stock_location,
                                #product_category,
                                #product_template,
                                #stock_move
                            #WHERE  
                                #product_template.id = product_product.product_tmpl_id
                                #AND product_category.id = product_template.categ_id
                                #AND product_id in %s
                                #AND stock_location.id =  stock_move.location_dest_id
                                #AND product_product.id = stock_move.product_id
                                #AND stock_move.location_dest_id in %s
                                #AND product_template.type = 'product'
                                #AND stock_move.state = 'done'
                            #GROUP BY
                                #product_product.id,
                                #product_template.id,
                                #product_category.name,
                                #product_template.name,
                                #stock_location.id,
                                #product_product.default_code''',
                    #(product_ids,location_ids))        
            
            #result = cr.fetchall()
            #print "2222222222222222222"
            #print len(result)
            #print ""
            #for res in result:
                #categoria    = res[0] or 'Indefinida', 
                #product_id   = res[1],
                #template_id   = res[2],
                #product_name = res[3] or 'Indefinido', 
                #default_code = res[4] or 'Indefinido',
                #location_id = res[5] or 'Indefinido',
                #qty_in_end  = float(res[6]) or 0.0,
                #count  = float(res[7]) or 0.0,
                
                #if isinstance(product_id, (list, tuple)):
                    #product_id = product_id[0]
                #else:
                    #product_id = product_id
                    
                #if isinstance(location_id, (list, tuple)):
                    #location_id = location_id[0]
                #else:
                    #location_id = location_id
                
                #key = (product_id,location_id)
                
                #if key not in dict:
                    #qty_out_end = 0.0
                #else:                    
                    #if isinstance(dict[key]['qty_out_end'], (list, tuple)):
                        #qty_out_end = dict[key]['qty_out_end'][0]
                    #else:
                        #qty_out_end = dict[key]['qty_out_end']
                                    
                #if isinstance(qty_in_end, (list, tuple)):
                    #qty_in_end = qty_in_end[0]
                #else:
                    #qty_in_end = qty_in_end
                    
            
                #balance = qty_in_end-qty_out_end
                
                #print "xxxxxxxxxxxxxxxxxxxxxx"
                #print balance
                #print qty_in_end
                #print qty_out_end
                #if balance >= 0.0:                                        
                    ## SE CREA EL QUANT SEGUN EL COSTO CALCULADO
                    
                    ##cr.execute('''INSERT INTO stock_quant (create_date,company_id,product_id,qty,in_date,location_id,cost) VALUES 
                    ##(%s,%s,%s,%s,%s,%s) ''' ,
                    ##(datetime.now(),company_id.id,product_id,qty_move_total,date,location_id,cost_def))
                    #if balance > 0.0:                            
                        #print "------- CREACION DE QUANT DEL PRODUCTO PARA UNA UBICACION ESPECIFICA A LA FECHA ACTUAL------------"
                        #if date_import.feedforward:
                            #moves_cost = move_obj.search(cr, uid, [('product_id', '=', product_id),'|',('location_id', '=', location_id),('location_dest_id', '=', location_id)])
                            #if moves_cost:
                                #sorted_lines=sorted(moves_cost, key=lambda x: x.date)                                                    
                                #moves_cost = move_obj.browse(cr, uid,sorted_lines, context=context)
                                #cost_calc = moves_cost[0].cost
                                #for move in moves_cost:                                        
                                    #qty_in_cost = 0.0
                                    #qty_out_cost = 0.0
                                    #qty_move_cost = 0.0
                                    #if location_id == move.location_id.id:
                                        #cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=%s WHERE id=%s''',(cost_calc, cost_calc*move.product_qty, move.id))
                                        ##move_obj.write(cr, SUPERUSER_ID, [move.id], {'cost': cost_calc}, context=context)
                                    #else:
                                        #cr.execute('''SELECT
                                                            #SUM(stock_move.product_qty)
                                                        #FROM
                                                            #stock_move
                                                        #WHERE
                                                            #stock_move.product_id = %s
                                                            #AND stock_move.location_dest_id = %s
                                                            #AND (stock_move.date < %s AND stock_move.state = 'done')''',
                                                    #(product_id,location_id,move.date))
                                        #result = cr.fetchall()
                                        #for res in result:
                                            #qty_in_cost = res[0] or 0.0
                                            
                                        #cr.execute('''SELECT 
                                                            #SUM(stock_move.product_qty)
                                                        #FROM 
                                                            #stock_move
                                                        #WHERE  
                                                            #stock_move.product_id = %s
                                                            #AND stock_move.location_id = %s
                                                            #AND (stock_move.date < %s AND stock_move.state = 'done')''',
                                                    #(product_id,location_id,move.date))
                                        #result = cr.fetchall()
                                        #for res in result:
                                            #qty_out_cost = res[0] or 0.0
                                        
                                        
                                        #qty_move_cost = qty_in_cost - qty_out_cost
                                        
                                        #if qty_move_cost >= 0:
                                            #cost_calc = (qty_move_cost*cost_calc + move.product_qty*move.cost)/(qty_move_cost+move.product_qty)
                                            #product_obj.write(cr, SUPERUSER_ID, [product_id], {'standard_price': cost_calc}, context=context)
                                            #cost_def = cost_calc
                                        #else:
                                            #cost_calc = 0.0
                                            #product_obj.write(cr, SUPERUSER_ID, [product_id], {'standard_price': cost_calc}, context=context)
                                            #cost_def = 0.0
                        #else:                                                  
                            #product = product_obj.browse(cr, uid,product_id, context=context)
                            #cost_def = product.standard_price
                        #vals = {
                            #'create_date': datetime.now(),
                            #'company_id' : company_id.id,
                            #'product_id' : product_id,
                            #'qty' : balance,
                            #'in_date' : date,
                            #'location_id': location_id,
                            #'cost': cost_def,
                        #}
                        #print "-------------------"
                        #quant_id = quant_obj.create(cr, uid, vals, context=context)
                        #print "-------------------"
                
                #print ""
                #print cont
                #print len(result)
                #cont+=1
        #print ""
        #print "**********************"
        #print "-------TERMINO--------"
        #print "**********************"
        #print ""
        #print product_list
        #print ""
        #self.write(cr, SUPERUSER_ID, ids, {'product_list': product_list}, context=context)
        #datas = {}
        #datas['ids'] = ids
        #datas['model'] = 'import.file.move.quant'
        #return {
        #'type': 'ir.actions.report.xml',
        #'report_name': 'update_move_quant.reporte_stock_quant_aeroo',
        #'report_type': 'aeroo',
        #'datas': datas,
        #}
    
    #def import_order(self, cr, uid, ids, context=None):
        #if not context: context = {}        
        #data_list = self.parse_file(cr, uid, ids, context=context)
        #date_import = self.browse(cr, uid, ids, context)[0]
        #date = date_import.date
        #company_id = date_import.company_id
        #location_abastecimiento = date_import.location_abastecimiento.id
        #location_desecho = date_import.location_desecho.id
                
        #product_obj = self.pool.get('product.product')
        #location_obj = self.pool.get('stock.location')
        #invoice_obj = self.pool.get('account.invoice.line')
        #quant_obj = self.pool.get('stock.quant')
        #cont = 1
        #qty_in = 0.0
        #qty_out = 0.0
        #qty_move = 0.0
        #qty_in_total = 0.0
        #qty_out_total = 0.0
        #qty_move_total = 0.0
        #cost = 0.0
        #cantidad = 0.0
        #balance = 0.0
        #product_list = ''
        #lista = []
            
        #for item in data_list:
            #default_code = str(item.get('product_code')).replace(".0", "")
            #location_id = str(item.get('location_id')).replace(".0", "")
            #cantidad = float(item.get('product_qty'))
            #cost = float(item.get('cost'))
            #cost_def = cost
            
            ## PRODUCTO            
            #product_id = product_obj.search(cr, uid, [('default_code', '=', default_code)])
            
            #for product in product_id:                           
                #invoice_line = invoice_obj.search(cr, uid, [('product_id', '=', product),('date', '>', '2015-12-31'),'|',('type', '=', 'out_invoice'),('type', '=', 'out_refund')])
                #for line in invoice_line:
                    #invoice_obj.write(cr, SUPERUSER_ID, line, {'cost_file': cost}, context=context)
                    
            #print cont
            #print len(data_list)        
            #cont+=1           
        
        #return True

#