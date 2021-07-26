# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from openerp import models, fields, api
import openerp.addons.decimal_precision as dp
from openerp.http import request
import xlsxwriter

class stock_report_sql_group_location(models.Model):
    _name = "stock.report.sql.group.location"
    
    name = fields.Char(string='Name', required=True)
    location_ids = fields.Many2many('stock.location', string='Ubicaciones', required=True)
    

class stock_report_sql_group_product(models.Model):
    _name = "stock.report.sql.group.product"
    
    name = fields.Char(string='Name', required=True)
    product_ids = fields.Many2many('product.product', string='Productos', required=True)
    

class stock_report_sql_line(models.Model):
    _name = 'stock.report.sql.line'            
    
    product_id = fields.Char(string='Producto')
    product_ref = fields.Char(string='Referencia Interna')
    product_category = fields.Char(string='Linea de Producto')    
    product_category_padre = fields.Char(string='Linea Padre')
    location_id = fields.Many2one('stock.location', string='Ubicacion')
    warehouse_id = fields.Many2one('stock.warehouse', string='Bodega')
    location_parent_id = fields.Many2one('stock.location', string='Ubicacion Padre')
    product_qty_start = fields.Float(string='Cantidad Inicial', digits_compute=dp.get_precision('Product UoM'))
    product_qty_in = fields.Float(string='Ingresos', digits_compute=dp.get_precision('Product UoM'))
    product_qty_out = fields.Float(string='Salidas', digits_compute=dp.get_precision('Product UoM'))
    product_qty_end = fields.Float(string='Cantidad Final', digits_compute=dp.get_precision('Product UoM'))
    cost_end = fields.Float(string='Costo Unitario Final', digits=dp.get_precision('Account'))
    cost_total_end = fields.Float(string='Costo Total Final', digits=dp.get_precision('Account'))
    cost_start = fields.Float(string='Costo Unitario Inicial', digits=dp.get_precision('Account'))
    cost_total_start = fields.Float(string='Costo Total Inicial', digits=dp.get_precision('Account'))
    date_start = fields.Datetime(string='Fecha Inicial', required=True)
    date_end = fields.Datetime(string='Fecha Final', required=True)
    company_id = fields.Many2one('res.company', string='Compañia')
    product_qty_quant = fields.Float(string='Disponibilidad', digits_compute=dp.get_precision('Product UoM'))
    
    
class stock_report_sql_wizard(models.TransientModel):
    _name = 'stock.report.sql.wizard'
    
    date_start = fields.Datetime(string='Fecha Inicial', required=True, default=datetime.now()-timedelta(days=datetime.now().day - 1) -timedelta(hours=datetime.now().hour - 5))
    date_end = fields.Datetime(string='Fecha Final', required=True, default=datetime.now())
    group_location_ids = fields.Many2one('stock.report.sql.group.location', string='Ubicaciones')
    group_product_ids = fields.Many2one('stock.report.sql.group.product', string='Productos')
    warehouse_id = fields.Many2one('stock.warehouse', string='Bodega')
    report_option = fields.Selection([('location', 'Ubicacion'),('warehouse', 'Bodega')], string='Bodega/Ubicacion', required=True, default='location')
    cost_option = fields.Selection([('promedio_global', 'Promedio Global'),('promedio_warehouse', 'Promedio Bodega')], string='Costeo', required=True, default='promedio_global')
    print_report = fields.Selection([('printfast', 'Excel (xlsx)'),('print', 'Excel'),('analizar', 'Analizar')], string='Visualizacion', required=True, default='print')
    title = fields.Char(string='titulos',default='LINEA,REFERENCIA,PRODUCTO,BODEGA,UBICACION,SALDO INICIAL,INGRESOS,SALIDAS,SALDO FINAL,COSTO UNITARIO,COSTO FINAL')        
        
    @api.multi
    def calcular_report(self):
        report_line_obj = self.env['stock.report.sql.line']
        product_obj = self.env['product.product']
        location_obj = self.env['stock.location']
        warehouse_obj = self.env['stock.warehouse']
        location_obj2 = self.pool.get('stock.location')
        company_id = self.env['res.company'].search([])[0]
        warehouses={}
        location_ids_dos = []
        cont = 1
        inicio = datetime.now()
        asset = self.env['ir.module.module'].search([('name', '=', 'asset_extended'), ('state', '=', 'installed')])
        if self.group_product_ids:
            product_ids = tuple([x.id for x in self.group_product_ids.product_ids])
        else:
            if asset:
                product_ids = tuple([x.id for x in product_obj.search([('active','=',True),('type','=','product'),('is_asset','=',False)])])
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
        self._cr.execute(''' DELETE FROM stock_report_sql_line''')
        
        
        dict={}
        print "---------------------------------------------------------------------"
        print "------- CALCULA ENTRADAS DE INVENTARIO EN EL PERIODO DADO------------"
        print "---------------------------------------------------------------------"
        print ""
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
                                AND (stock_move.date <= %s AND stock_move.date >= %s AND stock_move.state = 'done')
                            GROUP BY
                                product_product.id,
                                product_template.id,
                                product_category.name,
                                product_template.name,
                                stock_location.id,
                                product_product.default_code''',
                    (product_ids,location_ids,self.date_end,self.date_start))
        result = self._cr.fetchall()
        for res in result:
            categoria    = res[0] or 'Indefinida', 
            product_id   = res[1],
            template_id   = res[2],
            product_name = res[3] or 'Indefinido', 
            default_code = res[4] or 'Indefinido',
            location_id = res[5] or 'Indefinido',
            qty_in  = float(res[6]) or 0.0,
            count  = float(res[7]) or 0.0,
            key = (product_id,location_id)
            
            dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'location_id':location_id,'qty_in':qty_in}
        
        print "--------------------------------------------------------------------"
        print "------- CALCULA SALIDAS DE INVENTARIO EN EL PERIODO DADO------------"
        print "--------------------------------------------------------------------"
        print ""
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
                                AND stock_location.id =  stock_move.location_id
                                AND product_product.id = stock_move.product_id
                                AND stock_move.location_id in %s
                                AND product_template.type = 'product'
                                AND (stock_move.date <= %s AND stock_move.date >= %s AND stock_move.state = 'done')
                            GROUP BY
                                product_product.id,
                                product_template.id,
                                product_category.name,
                                product_template.name,
                                stock_location.id,
                                product_product.default_code''',
                    (product_ids,location_ids,self.date_end,self.date_start))        
        
        result = self._cr.fetchall()
        for res in result:
            categoria    = res[0] or 'Indefinida', 
            product_id   = res[1],
            template_id   = res[2],
            product_name = res[3] or 'Indefinido', 
            default_code = res[4] or 'Indefinido',
            location_id = res[5] or 'Indefinido',
            qty_out  = float(res[6]) or 0.0,
            count  = float(res[7]) or 0.0,
            
            key = (product_id,location_id)
            
            if key in dict:
                dict[key].update({'qty_out': qty_out})
            else:
                dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'location_id':location_id,'qty_in':0.0, 'qty_out': qty_out}
        
        print "------------------------------------------------------------"
        print "------- CALCULA TODAS LAS SALIDAS SALDOS FINALES------------"
        print "------------------------------------------------------------"
        print ""
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
                                product_product.default_code''',
                    (product_ids,location_ids,self.date_end))   
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
            
            if key in dict:
                dict[key].update({'qty_out_end': qty_out_end})
            else:
                dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'location_id':location_id, 'qty_in':0.0, 'qty_out':0.0, 'qty_out_end': qty_out_end}
                
                
        print "-------------------------------------------------------------"
        print "------- CALCULA TODOS LOS INGRESOS SALDOS FINALES------------"
        print "-------------------------------------------------------------"
        print ""
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
                    (product_ids,location_ids,self.date_end))        
        
        result = self._cr.fetchall()
        # for val_0 in dict.values():
        #     if val_0['qty_in'] == 0 and val_0['qty_out'] > 0:
        #         apn = []
        #         apn.append(val_0['categoria'][0])
        #         apn.append(val_0['product_id'][0])
        #         apn.append(val_0['template_id'][0])
        #         apn.append(val_0['product_name'][0])
        #         apn.append(val_0['default_code'][0])
        #         apn.append(val_0['location_id'][0])
        #         apn.append(0)
        #         apn.append(0)
        #         result.append(apn)
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
                dict[key]={'categoria':categoria,'product_id':product_id,'template_id':template_id,'product_name':product_name,'default_code':default_code,'location_id':location_id, 'qty_in':0.0, 'qty_out':0.0, 'qty_out_end': 0.0, 'qty_in_end': qty_in_end}
                
        
            
                    
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
            
        
            product_qty_end = qty_in_end - qty_out_end
            product_qty_in = qty_in
            product_qty_out = qty_out
            product_qty_start = product_qty_end - qty_in + qty_out
                        
            print ""
            print cont
            print len(result)
            print ""
            cont+=1
            
        
            if product_qty_start != 0.0 or product_qty_end != 0.0 or product_qty_in != 0.0 or product_qty_out != 0.0:
                if isinstance(location_id, (list, tuple)):
                    location_id = location_id[0]
                else:
                    location_id = location_id
                
                if isinstance(warehouses[location_id]['warehouse'], (list, tuple)):
                    warehouse_id = warehouses[location_id]['warehouse']
                else:
                    warehouse_id = warehouses[location_id]['warehouse']
                    
                if self.cost_option == 'promedio_global':            
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
                                    (product_id,self.date_end))
                    result1 = self._cr.fetchall()                
                    if result1:
                        cost_end = result1[len(result1)-1][0] or result1[len(result1)-1][1]
                        self._cr.execute('''SELECT
                                                costo_promedio,
                                                cost
                                            FROM
                                                stock_move
                                            WHERE  
                                                product_id = %s
                                                AND (date < %s AND stock_move.state = 'done')
                                            ORDER BY
                                                date''',
                                        (product_id,self.date_start))
                        result2 = self._cr.fetchall()                
                        if result2:
                            cost_start = result2[len(result2)-1][0] or result2[len(result2)-1][1]
                        else:
                            cost_start = cost_end
                    else:
                        continue   
                else:
                    moves_start = self.env['stock.move'].search([('product_id','=',product_id),('date','>=',self.date_start),('date','<=',self.date_end),('state','=','done'),('location_dest_id','=',location_id)], order='date asc')
                    if moves_start:
                        cost_end = moves_start[len(moves_start)-1].costo_promedio                    
                    else:
                        moves_start2 = self.env['stock.move'].search([('product_id','=',product_id),('date','<=',self.date_end),('state','=','done'),('location_dest_id','=',location_id)], order='date asc')
                        if moves_start2:
                            cost_end = moves_start2[len(moves_start2)-1].costo_promedio
                        else:
                            continue
            
                    moves_all = self.env['stock.move'].search([('product_id','=',product_id),('date','>=',self.date_start),('date','<=',self.date_end),('state','=','done'),'|',('location_dest_id','=',location_id),('location_id','=',location_id)], order='date asc')
                    if moves_all:
                        cost_start = moves_all[0].costo_promedio
                    else:
                        moves_all2 = self.env['stock.move'].search([('product_id','=',product_id),('date','<=',self.date_end),('state','=','done'),'|',('location_dest_id','=',location_id),('location_id','=',location_id)], order='date asc')
                        if moves_all2:
                            cost_start = moves_all2[0].costo_promedio
                        else:
                            continue
                                    
                cost_total_end = cost_end*product_qty_end
                cost_total_start = cost_start*product_qty_start
                                
                self._cr.execute('''INSERT INTO stock_report_sql_line (product_id,location_id,product_qty_start,product_qty_in,product_qty_out,product_qty_end,cost_end,cost_total_end,cost_start,cost_total_start,product_category,product_ref,date_start,date_end,company_id,warehouse_id) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                    (product_name,location_id,product_qty_start,product_qty_in,product_qty_out,product_qty_end,cost_end,cost_total_end,cost_start,cost_start*product_qty_start,categoria,default_code,self.date_start,self.date_end,company_id.id,warehouse_id or None))
                    
        
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
        

        if self.print_report == 'printfast':
            datos = {}
            #datos['ids'] = [x.id for x in report_line_obj.search([])]
            ids = ','.join(str(x.id) for x in report_line_obj.search([]))
            self._cr.execute(''' SELECT srsl.product_category, srsl.product_ref, srsl.product_id, sw.name as warehouse_id, sl.name as location_id,
            							srsl.product_qty_start, srsl.product_qty_in, srsl.product_qty_out, srsl.product_qty_end, srsl.cost_end,srsl.cost_total_end
											FROM stock_report_sql_line srsl
											INNER JOIN stock_warehouse sw ON sw.id = srsl.warehouse_id
											INNER JOIN stock_location sl ON sl.id = srsl.location_id 
											WHERE srsl.id IN (%s)
									ORDER BY srsl.product_ref, sw.name, sl.name '''%ids)
            datos = self._cr.fetchall()
            url = self.printfast(datos)
            return {'type': 'ir.actions.act_url', 'url': str(url), 'target': 'self'}
        elif self.print_report == 'print':
            datas = {}
            datas['ids'] = [x.id for x in report_line_obj.search([])]
            datas['model'] = 'stock.report.sql.line'
            return {
            'type': 'ir.actions.report.xml',
            'report_name': 'report_odoo_extended.reporte_stock_sql_aeroo',
            'report_type': 'aeroo',
            'datas': datas,
            }
        else:    
            return {
                'name': 'Analisis de Inventario',
                'view_type': 'form',
                'view_mode': 'graph,tree',
                'view_id': False,
                'res_model': 'stock.report.sql.line',
                'type': 'ir.actions.act_window'
            }
    
    @api.multi
    def printfast(self, datos):
        actual = str(datetime.now()).replace('-', '').replace(':', '').replace('.', '').replace(' ', '')
        data_attach = {
            'name': 'Valorizado_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.xlsx',
            'datas': '.',
            'datas_fname': 'Valorizado_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.',
            'res_model': 'stock.report.sql.wizard',
            'res_id': self.id,
        }
        self.env['ir.attachment'].search(
            [('res_model', '=', 'stock.report.sql.wizard'), ('company_id', '=', self.env.user.company_id.id), (
                'name', 'like',
                '%Valorizado%' + self.env.user.name + '%')]).unlink()  # elimina adjuntos del usuario

        # crea adjunto en blanco
        attachments = self.env['ir.attachment'].create(data_attach)

        headers = dict(request.httprequest.__dict__.get('headers'))

        if headers.get('Origin', False):
            url = dict(request.httprequest.__dict__.get('headers')).get(
                'Origin') + '/web/binary/saveas?model=ir.attachment&field=datas&filename_field=name&id=' + str(
                attachments.id)
        else:
            url = dict(request.httprequest.__dict__.get('headers')).get(
                'Referer') + '/binary/saveas?model=ir.attachment&field=datas&filename_field=name&id=' + str(
                attachments.id)
        path = attachments.store_fname
        self.env['ir.attachment'].search([['store_fname', '=', path]]).write(
            {'store_fname': attachments._get_path(path)[0]})
        wb = xlsxwriter.Workbook(attachments._get_path(path)[1])
        bold = wb.add_format({'bold': True})
        bold2 = wb.add_format({'bold': True, 'fg_color': '#2E86C1'})
        bold.set_align('center')
        bold2.set_align('center')
        money_format = wb.add_format({'num_format': '$#,##0'})
        money_format.set_align('right')
        ws = wb.add_worksheet('VALORIZADO')
        ws.set_column('A:A', 20)
        ws.merge_range('A1:K1', 'INFORME VALORIZADO',bold)
        ws.write('D2','DESDE:',bold)
        ws.write('E2',self.date_start)
        ws.write('G2','DESDE:',bold)
        ws.write('H2',self.date_end)
        
        titulos = self.title.split(',')
        abc = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U',
               'V', 'W', 'X', 'Y', 'Z']
        num = [x for x in range(0, 101)]
        resultado = zip(abc, num)
        for i, l in enumerate(titulos):
            for pos in resultado:
                if i == pos[1]:
                    position = pos[0]
                    break
            title = position
            ws.write(position + str(5), l, bold2)
        for x, line in enumerate(datos):
            for y, f in enumerate(titulos):
                for pos in resultado:
                    if y == pos[1]:
                        position = pos[0]
                        break
                if position in ('J','K'):
                    ws.write(position + str(6 + x), line[y] or str(0.0),money_format)
                else:
                    ws.write(position + str(6 + x), line[y] or '')
        wb.close()
        print url
        return url
    # Calcula diferencias entre movimientos y quants
    @api.multi
    def calcular_diferencias(self):
        return {
                'name': 'Analisis de Inventario',
                'view_type': 'form',
                'view_mode': 'graph,tree',
                'view_id': False,
                'res_model': 'stock.report.sql.line',
                'type': 'ir.actions.act_window'
            }

        
#
