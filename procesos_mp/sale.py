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


class sale_order(models.Model):
    _inherit = 'sale.order'
    
    fecha_malla = fields.Date(string='Fecha malla', required=True)
    n_oc = fields.Char(string='Numero O.C.', required=True)
    punto_de_venta = fields.Many2one('res.partner', string='Punto de venta')
    
    
    #def _prepare_order_line_move(self, cr, uid, order, line, picking_id, date_planned, context=None):
        #if not context : context={}
        #res = super(sale_order,self)._prepare_order_line_move(cr, uid, order, line, picking_id, date_planned, context=context)
        #res['nombre_punto_de_venta'] = line.nombre_punto_de_venta or ''
        #res['cliente_final'] = line.cliente_final or ''
        #res['note_pedido'] = line.note_pedido or ''
        #return res
     
    #def action_view_delivery(self, cr, uid, ids, context=None):
         #stock_move_obj = self.pool.get('stock.move')
         #line_ids = []
         #sale_data = self.browse(cr, uid, ids, context=context)
         #sale_order_line_obj  = self.pool.get('sale.order.line')
         #line_ids = sale_order_line_obj.search(cr, uid, [('order_id','=',ids)], context=context)
         #mod_obj = self.pool.get('ir.model.data')
         #form_result = mod_obj.get_object_reference(cr, uid, 'stock', 'view_move_form')
         #form_view_id = form_result and form_result[1] or False
         #tree_result = mod_obj.get_object_reference(cr, uid, 'procesos_mp', 'view_stock_move_gourp_view')
         #tree_view_id = tree_result and tree_result[1] or False
         #search_result = mod_obj.get_object_reference(cr, uid, 'procesos_mp', 'view_stock_move_search_view')
         #search_view_id = search_result and search_result[1] or False
         #context.update({'group_by':['product_id']})
         #return {
              #'domain':[('sale_line_id', 'in',line_ids)],
              #'name': _('Product wise group of delivery view'),
              #'view_type': 'form',
              #"view_mode": 'tree, form',
              #'res_model': 'stock.move',
              #'type': 'ir.actions.act_window',
              #'views': [(tree_view_id, 'tree'),(form_view_id,'form')],
              #'view_id': tree_view_id,
              #'search_view_id': search_view_id,
              #'context': context, 
              #}
    
    #def _create_pickings_and_procurements(self, cr, uid, order, order_lines, picking_id=False, context=None):
        #move_obj = self.pool.get('stock.move')
        #picking_obj = self.pool.get('stock.picking')
        #procurement_obj = self.pool.get('procurement.order')
        #proc_ids = []

        #if order.remisionada:
            #for line in order_lines:
                #if line.state == 'done':
                    #continue
                #date_planned = self._get_date_planned(cr, uid, order, line, order.date_order, context=context)
                #if line.product_id:
                    #if line.product_id.type in ('product', 'consu'):
                        #if not picking_id:
                            #vals = self._prepare_order_picking(cr, uid, order, context=context)
                            #vals.update({'type' : 'internal'})
                            #picking_id = picking_oremisionadabj.create(cr, uid, vals)
                        #move_id = move_obj.create(cr, uid, self._prepare_order_line_move(cr, uid, order, line, picking_id, date_planned, context=context))
                    #else:
                        #move_id = False
        #else:
            #for line in order_lines:
                #if line.state == 'done':
                    #continue
    
                #date_planned = self._get_date_planned(cr, uid, order, line, order.date_order, context=context)
    
                #if line.product_id:
                    #if line.product_id.type in ('product', 'consu'):
                        #if not picking_id:
                            #picking_id = picking_obj.create(cr, uid, self._prepare_order_picking(cr, uid, order, context=context))
                        #move_id = move_obj.create(cr, uid, self._prepare_order_line_move(cr, uid, order, line, picking_id, date_planned, context=context))
                    #else:
                        ## a service has no stock move
                        #move_id = False
    
                    #proc_id = procurement_obj.create(cr, uid, self._prepare_order_line_procurement(cr, uid, order, line, move_id, date_planned, context=context))
                    #proc_ids.append(proc_id)
                    #line.write({'procurement_id': proc_id})
                    #self.ship_recreate(cr, uid, order, line, move_id, proc_id)
    
            #wf_service = netsvc.LocalService("workflow")
            #if picking_id:
                #wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
            #for proc_id in proc_ids:
                #wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
    
            #val = {}
            #if order.state == 'shipping_except':
                #val['state'] = 'progress'
                #val['shipped'] = False
    
                #if (order.order_policy == 'manual'):
                    #for line in order.order_line:
                        #if (not line.invoiced) and (line.state not in ('cancel', 'draft')):
                            #val['state'] = 'manual'
                            #break
            #order.write(val)
            #return True
#sale_order()

class sale_order_line(models.Model):
    _inherit = 'sale.order.line'
    
    despacho = fields.Boolean(string='No despacho')
    acuerdo_promocional = fields.Char(string='Acuerdo Promocional', size=48)
    ean_del_tem = fields.Char(string='EAN del Ítem',size=32)
    plu_lineas =  fields.Char(string='PLU lineas',size=32)
    cantidad_total = fields.Float(string='Cantidad Total', readonly=True)
    ean_punto_de_venta = fields.Char(string='EAN Punto de Venta',size=32, readonly=True)
    nombre_punto_de_venta = fields.Char(string='Nombre Punto de Venta', size=48)
    precio_bruto = fields.Float(string='Precio Bruto')
    precio_neto = fields.Float(string='Precio Neto')
    cliente_final = fields.Char(string='cliente final',size=32)
    note_pedido = fields.Char(string='Note pedido',size=32)
    
#