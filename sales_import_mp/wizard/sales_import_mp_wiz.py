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


class import_xlsx_file(osv.TransientModel):    
    _name = 'import.xlsx.file'
    
    _columns = {
        'file': fields2.binary('File', filters='*.xlsx', required=True),
        'warehouse_id': fields2.many2one('stock.warehouse', string='Almacen', required=True),
        'location_id': fields2.many2one('stock.location', string='Ubicacion', required=True, domain=[('usage','=', 'internal'),('sale_ok','=', True),('active','=', True)]),
        'cross_docking' : fields2.boolean('Cross Docking'),
        'type_cross' : fields2.selection([('remision', 'Remisionar'),('factura', 'Facturar')], string='Tipo de Remision', required=True),
        'picking_type_cross': fields2.many2one('stock.picking.type', string='Tipo de Albaran', domain=[('cross_docking','=', True)]),        
    }
    
    def make_log(self, cr, uid, ids, log_count, context=None):
        if not context: context = {}
        report = []
        if log_count:
            report = [
                '%s: %s' % (_('Total number Sale Order'),
                            log_count.get('st_cnt')),
                '%s: %s' % (_('Number of errors found'),
                            log_count.get('error_cnt')),
                '%s: %s' % (_('Number of transactions skipped due to errors'),
                            log_count.get('skipped_cnt')),
                '%s  %s' % (_('Line number'), log_count.get('error_list'))
            ]
        return report 
    
    def parse_file(self, cr, uid, ids, context=None):
        if not context: context = {}
        rec = self.browse(cr, uid, ids[0], context)
        file_path = tempfile.gettempdir()+'/sale_order.xlsx'
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
                        order_dict['partner_ean'] = worksheet.cell_value(row, cell)
                    elif cell== 1:
                        order_dict['company'] = worksheet.cell_value(row, cell)
                    elif cell== 2:
                        order_dict['order_type'] = worksheet.cell_value(row, cell)
                    elif cell== 3:
                        order_dict['partner_ref'] = worksheet.cell_value(row, cell)
                    elif cell== 4:
                        order_dict['partner_invoice_ean'] = worksheet.cell_value(row, cell)
                    elif cell== 5:
                        order_dict['partner_invoice_name'] = worksheet.cell_value(row, cell)
#                    elif cell== 6:
#                        order_dict['partner_shipping_ean'] = worksheet.cell_value(row, cell)
                    elif cell== 7:
                        order_dict['partner_shipping_name'] = worksheet.cell_value(row, cell)
                    elif cell== 8:
                        order_dict['min_date_shipping'] = worksheet.cell_value(row, cell)
                    elif cell== 9:
                        order_dict['max_date_shipping'] = worksheet.cell_value(row, cell)
                    elif cell== 10:
                        order_dict['promotional_agreement'] = worksheet.cell_value(row, cell)
                    elif cell== 11:
                        order_dict['product_ean'] = worksheet.cell_value(row, cell)
                    elif cell== 12:
                        order_dict['product_plu'] = worksheet.cell_value(row, cell)
                    elif cell== 13:
                        order_dict['product_code'] = worksheet.cell_value(row, cell)
                    elif cell== 14:
                        order_dict['product_name'] = worksheet.cell_value(row, cell)
                    elif cell== 15:
                        order_dict['partner_shipping_ean'] = worksheet.cell_value(row, cell)
                    elif cell== 16:
                        order_dict['stock_location_name'] = worksheet.cell_value(row, cell)
                    elif cell== 17:
                        order_dict['total_qty'] = worksheet.cell_value(row, cell)
                    elif cell== 18:
                        order_dict['shop_ean'] = worksheet.cell_value(row, cell)
                    elif cell== 19:
                        order_dict['shop_name'] = worksheet.cell_value(row, cell)
                    elif cell== 20:
                        order_dict['qty_order'] = worksheet.cell_value(row, cell)
                    elif cell== 21:
                        order_dict['unit_price'] = worksheet.cell_value(row, cell)
                    elif cell== 22:
                        order_dict['net_price'] = worksheet.cell_value(row, cell)
                    elif cell== 27:
                        order_dict['note'] = worksheet.cell_value(row, cell)
                    # elif cell==29:
                        # order_dict['remisionada'] = worksheet.cell_value(row, cell)
                order_data_list.append(order_dict)
        return order_data_list
    
    def import_order(self, cr, uid, ids, context=None):
        if not context: context = {}
        vals_line = {}
        vals = {}
        orders = []
        vals_con_office = {}
        order_data_list = self.parse_file(cr, uid, ids, context=context)
        sale_import = self.browse(cr, uid, ids, context)[0]
        import_file = sale_import.file
        cross_docking = sale_import.cross_docking
        partner_obj = self.pool.get('res.partner')
        company_obj = self.pool.get('res.company')
        shop_obj = self.pool.get('sale.shop')
        product_obj = self.pool.get('product.product')
        sale_line_obj = self.pool.get('sale.order.line')
        sale_obj = self.pool.get('sale.order')
        contro_de_obj = self.pool.get('control.office')
        temp_sale_ids = []
        previous_order = []
        old_ids = []
        st_cnt, skipped_cnt, error_cnt  = 0, 0, 0
        line_number = []
        error_list = '\n'
        sale_id = []
        line_count = 0
        aux = 0
        cont = 1
        
        for order_data in order_data_list:
            aux+=1
            print "-----------------"
            print cont
            print len(order_data_list)
            print ""
            cont+=1
            if not order_data.get('total_qty'):
                res = {
                     'ean_punto_de_venta': order_data.get('shop_ean'),
                     'nombre_punto_de_venta' : order_data.get('shop_name'),
                     'cantidad_pto_vta': order_data.get('qty_order'),
                     'precio_bruto': order_data.get('unit_price'),
                     'precio_neto' : order_data.get('net_price')
                }
                product_ids = product_obj.search(cr, uid, [('ean_codigo', '=', order_data.get('product_ean'))])
                if not product_ids:
                    raise osv.except_osv(_('Error!'), _('El codigo EAN %s no se encuentra asociado a ningun producto'%(order_data.get('product_ean'))))
                sale_line_id = sale_line_obj.search(cr, uid, [('product_id','=',product_ids[0]), ('order_id','=',previous_order)])
                sale_line_obj.write(cr, uid, sale_line_id, {'pos_extra_ids' : [(0,0,res)]} )
            else:
                partner_ids = partner_obj.search(cr, uid, [('partner_ean', '=', order_data.get('partner_ean'))])
                part_shi_id = partner_obj.search(cr, uid, [('partner_ean','=',order_data.get('partner_shipping_ean'))])                
                neto_price = 0.0
                discount = 0.0
                if not partner_ids:
                    raise osv.except_osv(_('Error!'), _('El codigo EAN para el tercero no corresponde, este es %s EAN.'%(order_data.get('partner_ean'))))
                
                if not part_shi_id:
                    raise osv.except_osv(_('Error!'), _('El codigo EAN para la sucursal no corresponde, este es %s EAN.'%(order_data.get('partner_shipping_ean'))))
                
                partner_rec = partner_obj.browse(cr, uid, partner_ids[0], context)
                shipping_rec = partner_obj.browse(cr, uid, part_shi_id[0], context)
                
                order_line_dict = {}
                                                    
                if cross_docking:                
                    if order_data.get('qty_order') and order_data.get('total_qty'):
                        order_line_dict['product_uom_qty'] = order_data.get('total_qty')
                    else:
                        order_line_dict['product_uom_qty'] = 0.0
                else:
                    if order_data.get('total_qty'):
                        order_line_dict['product_uom_qty'] = order_data.get('total_qty')
                    else:
                        order_line_dict['product_uom_qty'] = order_data.get('qty_order')
                        
                product_ids = product_obj.search(cr, uid, [('ean_codigo', '=', order_data.get('product_ean'))])
                
                if not product_ids:
                    raise osv.except_osv(_('Error!'), _('El producto con el codigo EAN %s no se encuentra en el sistema'%(order_data.get('product_ean'))))
                
                product_rec = product_obj.browse(cr, uid, product_ids[0], context)
                order_line_dict['product_id'] = product_rec.id
                order_line_dict['name'] = order_data.get('product_name')
                order_line_dict['price_unit'] = product_rec.list_price
                order_line_dict['product_uom'] = product_rec.uom_id.id
                order_line_dict['acuerdo_promocional'] = order_data.get('promotional_agreement')
                order_line_dict['ean_del_tem'] = str(order_data.get('product_ean'))
                order_line_dict['plu_lineas'] = order_data.get('product_plu')
                order_line_dict['cantidad_total'] = order_data.get('total_qty')
                order_line_dict['ean_punto_de_venta'] = order_data.get('shop_ean')
                order_line_dict['nombre_punto_de_venta'] = order_data.get('shop_name')

                if order_data.get('qty_order'):
                    order_line_dict['qty_pto_vta'] = order_data.get('qty_order')
                if cross_docking:               
                    if order_data.get('qty_order') and order_data.get('total_qty'):
                        line_vals = sale_line_obj.product_id_change(cr, uid, ids, partner_rec.property_product_pricelist.id, product_rec.id, int(order_data.get('total_qty')), partner_id=partner_rec.id, context=context)
                    else:
                        line_vals = sale_line_obj.product_id_change(cr, uid, ids, partner_rec.property_product_pricelist.id, product_rec.id, int(order_data.get('qty_order')), partner_id=partner_rec.id, context=context)
                else:
                    if order_data.get('qty_order'):
                        line_vals = sale_line_obj.product_id_change(cr, uid, ids, partner_rec.property_product_pricelist.id, product_rec.id, int(order_data.get('qty_order')), partner_id=partner_rec.id, context=context)
                    else:
                        line_vals = sale_line_obj.product_id_change(cr, uid, ids, partner_rec.property_product_pricelist.id, product_rec.id, int(order_data.get('total_qty')), partner_id=partner_rec.id, context=context)
                
                if  partner_rec.property_product_pricelist:
                    date_dev = datetime.now()
                    date_dev = date_dev.date()
                    cr.execute('SELECT id  FROM product_pricelist_item where price_version_id in (SELECT  id FROM product_pricelist_version where pricelist_id=%s and active=True and date_start <= %s and date_end >= %s ) and product_id=%s',(partner_rec.property_product_pricelist.id,date_dev,date_dev,product_rec.id))
                    if cr.fetchone():
                        cr.execute('SELECT discount, price_surcharge FROM product_pricelist_item where price_version_id in (SELECT  id FROM product_pricelist_version where pricelist_id=%s and active=True and date_start <= %s and date_end >= %s ) and product_id=%s',(partner_rec.property_product_pricelist.id,date_dev,date_dev,product_rec.id))
                        res = cr.fetchone()
                        discount = res[0]
                        price_unit = res[1]
                    else:
                        raise osv.except_osv(_('Error!'), _('El producto %s no se encuentra asociado a la lista de precios %s'%(product_rec.name, partner_rec.property_product_pricelist.name)))
                    
                line_vals['value']['discount'] = discount
                precio_bruto = order_data.get('unit_price')
                precio_neto = order_data.get('net_price')
                    
                   
                line_vals['value']['price_unit'] = price_unit
                neto_price = float(price_unit - ((price_unit * discount) / 100))
                if precio_bruto == 0:
                    precio_bruto = precio_neto
                if precio_neto == 0:
                    precio_neto = precio_bruto
                total_discount = (price_unit * float(order_data.get('total_qty')) * discount) / 100
                try:
                    tax_ids = line_vals.get('value')['tax_id']
                except:
                    tax_ids = []
                
                order_line_dict.update(line_vals.get('value'))
                order_line_dict['precio_bruto'] = precio_bruto
                order_line_dict['precio_neto'] = precio_neto
                order_line_dict['discount'] = discount
                order_line_dict['neto_price'] = neto_price
                order_line_dict['total_discount'] = total_discount                
                order_line_dict['tax_id'] = [(6, 0, tax_ids)]
                                
                vals['order_line'] = [(0,0,order_line_dict)]
                
                if temp_sale_ids:                    
                    old_ids = sale_obj.search(cr, uid, [('id','in',temp_sale_ids),('partner_invoice_id.partner_ean','=',order_data.get('partner_invoice_ean')),                                              ('partner_shipping_id.partner_ean','=',order_data.get('partner_shipping_ean')),('n_oc','=',order_data.get('partner_ref'))])                    
                                        
                if old_ids:
                    vals.pop('name', None)
                    lines = vals['order_line']
                    vals['order_line'] = False
                    for o_id in old_ids:
                        for line in lines:
                            cr.execute('''insert into sale_order_line (active,delay,product_id, product_uom,order_id,price_unit,product_uom_qty, name,state, type, product_uos_qty, nombre_punto_de_venta,discount,cantidad_total,ean_del_tem,plu_lineas,acuerdo_promocional,precio_bruto,precio_neto,total_discount,neto_price,ean_punto_de_venta,proposed_qty)
                                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',(True,0.0,line[2]['product_id'], line[2]['product_uom'], o_id,line[2]['price_unit'], line[2]['product_uom_qty'],line[2]['name'], line[2].get('state') or 'draft', line[2].get('type') or 'out', line[2].get("product_uos_qty"), line[2].get("nombre_punto_de_venta,"), line[2].get("discount"),line[2].get("cantidad_total"),line[2].get("ean_del_tem"),line[2].get("plu_lineas"),line[2].get("acuerdo_promocional"),line[2].get("precio_bruto"),line[2].get("precio_neto"),                        line[2].get("total_discount"),line[2].get("neto_price"),line[2].get("ean_punto_de_venta"),line[2]['product_uom_qty']))
                        line_id = cr.fetchone()[0]
                        if line[2].get('tax_id'):
                            for tax_id in line[2].get('tax_id')[0][2]:
                                cr.execute('insert into sale_order_tax (order_line_id,tax_id) values (%s,%s)', (line_id,tax_id))
                    line_count +=1
                else:
                    vals['name'] = '/'
                    vals['fecha_malla'] = fields.date.today()
                    vals['order_type'] = order_data.get('order_type')
                    vals['min_ship_date'] = order_data.get('min_date_shipping')
                    vals['max_ship_date'] = order_data.get('max_date_shipping')
                    #vals['agreement'] = order_data.get('agreement')
                    vals['n_oc'] = order_data.get('partner_ref')
                    vals['net_price'] = order_data.get('net_price')
                    vals['partner_id'] = partner_rec.id
                    vals['type_cross'] = 'factura'
                    vals['warehouse_id'] = sale_import.warehouse_id.id
                    vals['location_id'] = sale_import.location_id.id                    
                    vals['note'] = order_data.get('note',' ')
                    if sale_import.type_cross == 'remision':
                        vals['type_cross'] = 'remision'
                        vals['picking_type_cross'] = sale_import.picking_type_cross.id
                    sale_vals = sale_obj.onchange_partner_id(cr, uid, ids, partner_rec.id, context=context)
                    part_shi_id = partner_obj.search(cr, uid, [('partner_ean','=',order_data.get('partner_shipping_ean'))])
                    part_inv_id = partner_obj.search(cr, uid, [('partner_ean','=',order_data.get('partner_invoice_ean'))])
                    sale_vals['value']['partner_shipping_id']= part_shi_id[0]
                    sale_vals['value']['partner_invoice_id'] = part_inv_id[0]
                    
                    vals.update(sale_vals.get('value'))
                    lines = vals['order_line'] 
                    vals['order_line'] = {}
                    sale_id = sale_obj.create(cr, uid, vals, context)
                    line_ids = []
                    
                    for line in lines:
                        cr.execute('''insert into sale_order_line (active,delay,product_id, product_uom,order_id,price_unit,product_uom_qty, name,state, type, product_uos_qty, nombre_punto_de_venta,discount,cantidad_total,ean_del_tem,plu_lineas,acuerdo_promocional,precio_bruto,precio_neto,total_discount,neto_price,ean_punto_de_venta,proposed_qty) 
                                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                                                                                (True,0.0,line[2]['product_id'],
                                                                                 line[2]['product_uom'],
                                                                                 sale_id,line[2]['price_unit'], line[2]['product_uom_qty'],
                                                                                 line[2]['name'], line[2].get('state') or 'draft',
                                                                                 line[2].get('type') or 'out',
                                                        line[2].get("product_uos_qty"), line[2].get("nombre_punto_de_venta,"),
                                                                        line[2].get("discount"),line[2].get("cantidad_total"),line[2].get("ean_del_tem"),line[2].get("plu_lineas"),
                                                                        line[2].get("acuerdo_promocional"),line[2].get("precio_bruto"),line[2].get("precio_neto"),
                                                                line[2].get("total_discount"),line[2].get("neto_price"),line[2].get("ean_punto_de_venta"), line[2]['product_uom_qty']))

                        line_id = cr.fetchone()[0]
                        if line[2].get('tax_id'):
                            for tax_id in line[2].get('tax_id')[0][2]:
                                cr.execute('insert into sale_order_tax (order_line_id,tax_id) values (%s,%s)', (line_id,tax_id))
                    
                    previous_order = sale_id 
                    st_cnt += 1
                    temp_sale_ids.append(sale_id)
                    orders.append(sale_id)
                    line_count +=1
                    
                    
                if cross_docking:                    
                    res = {
                        'ean_punto_de_venta': order_data.get('shop_ean'),
                        'nombre_punto_de_venta' : order_data.get('shop_name'),
                        'cantidad_pto_vta': order_data.get('qty_order'),
                        'precio_bruto': order_data.get('unit_price'),
                        'precio_neto' : order_data.get('net_price')
                    }
                    product_ids = product_obj.search(cr, uid, [('ean_codigo', '=', order_data.get('product_ean'))])
                    if not product_ids:
                        raise osv.except_osv(_('Error!'), _('El codigo EAN %s no se encuentra asociado a ningun producto'%(order_data.get('product_ean'))))
                    sale_line_id = sale_line_obj.search(cr, uid, [('product_id','=',product_ids[0]), ('order_id','=',previous_order)])
                    sale_line_obj.write(cr, uid, sale_line_id, {'pos_extra_ids' : [(0,0,res)]})
                    #sale_obj.write(cr, uid, [sale_id], {'type_cross':'remision'}, context=context)
            
            #if cont == 500 or cont == 1000 or cont == 1500 or cont == 2000:
                 #cr.commit()
                
                
        
        vals={}
        old_ids=[]
        temp_sale_ids =[]
        previous_order = []
        
        domain = [('id','in',orders)]
        for sale_order in sale_obj.browse(cr, uid, orders, context):
            order_line = self.pool.get('sale.order.line').create(cr, uid, {'order_id':sale_order.id,'name':'mario zuniga'}, context=context)
            self.pool.get('sale.order.line').unlink(cr, uid, [order_line], context=context)
        
        return {
            'domain': domain,
            'name': 'Imported Sale Order',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window'
        }
import_xlsx_file()