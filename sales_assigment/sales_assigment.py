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

#class sale_order(models.Model):    
    #_inherit = 'sale.order'
    
    ##def _prepare_order_line_move(self, cr, uid, order, line, picking_id, date_planned, context=None):
        ##res = super(sale_order, self)._prepare_order_line_move(cr, uid, order, line, picking_id, date_planned, context)
        ##if line.proposed_qty:
            ##res.update({'product_qty':line.proposed_qty})
        ##return res
    
    #def _prepare_order_picking(self, cr, uid, order, context=None):
        #res = super(sale_order, self)._prepare_order_picking(cr, uid, order, context)
        #if order.fecha_malla:
            #res.update({'fecha_malla':order.fecha_malla})
        #return res
    
    ##def action_ship_create(self, cr, uid, ids, context=None):
        ##result = super(sale_order, self).action_ship_create(cr, uid, ids, context=context)
        ##picking_obj = self.pool.get('stock.picking')
        ##picking_ids = []
        ##for sale in self.browse(cr, uid, ids, context):
            ##picking_ids.extend([picking.id for picking in sale.picking_ids])
        ##picking_obj.split_move(cr, uid, picking_ids, context=context)
        ##return result



#class stock_picking(models.Model):    
    #_inherit = 'stock.picking'
    
    #fecha_malla = fields.Date(string='Fecha malla', required=True)
    
    #def get_product_avbl_qty(self, cr, uid, product_id, context=None):
        #if not context: context = {}
        #query = '''
               #SELECT  report.product_id, report.location_id, sum(report.qty) AS qty
               #FROM (         SELECT - max(sm.id) AS id, sm.location_id, sm.product_id, sm.prodlot_id, - sum(sm.product_qty / uo.factor) AS qty
                               #FROM stock_move sm
                          #LEFT JOIN stock_location sl ON sl.id = sm.location_id
                     #LEFT JOIN product_uom uo ON uo.id = sm.product_uom
                    #WHERE sm.state::text = 'done'::text
                    #GROUP BY sm.location_id, sm.product_id, sm.product_uom, sm.prodlot_id
                    #UNION ALL 
                             #SELECT max(sm.id) AS id, sm.location_dest_id AS location_id, sm.product_id, sm.prodlot_id, sum(sm.product_qty / uo.factor) AS qty
                               #FROM stock_move sm
                          #LEFT JOIN stock_location sl ON sl.id = sm.location_dest_id
                     #LEFT JOIN product_uom uo ON uo.id = sm.product_uom
                    #WHERE sm.state::text = 'done'::text
                    #GROUP BY sm.location_dest_id, sm.product_id, sm.product_uom, sm.prodlot_id) report
              #WHERE report.product_id in (%s)
              #GROUP BY report.location_id, report.product_id
              #order by report.product_id;
        #'''%(product_id)
        #cr.execute(query)
        #location_result = cr.fetchall()
        #location_dict = {}
        #for i in location_result:
            #if i[2] < 0:
                #continue
            #if location_dict.get(i[0]):
                #location_list = [(i[1], i[2])]
                #location_list.extend(location_dict.get(i[0]))
                #location_dict.update({i[0]:location_list})
            #else:
                #location_dict.update({i[0]:[(i[1], i[2])]})
        #return location_dict
    
    #def split_move(self, cr, uid, ids, context=None):
        #if not context: context = {}
        #move_obj = self.pool.get('stock.move')
        #for picking in self.browse(cr, uid, ids, context=context):
            #for move in picking.move_lines:
                #location_result = self.get_product_avbl_qty(cr, uid, str(move.product_id.id), context)
                #if not location_result:
                    #continue
                #location_result.get(move.product_id.id).sort(key=lambda tup: tup[1])
##                 loc_result = [x for x in reversed(location_result.get(move.product_id.id))]
                #flag = False
                #for loc in location_result.get(move.product_id.id):
                    #if loc[1] > move.product_qty:
                        #move_obj.write(cr, uid, [move.id], {'location_id':loc[0]})
                        #flag = True
                
                #if not flag:
                    #rem_qty = move.product_qty
                    #move_id = None
                    #for loc in location_result.get(move.product_id.id):
                        #if rem_qty <= 0:
                            #break
                        #qty = 0
                        #if rem_qty > loc[1]:
                            #qty = loc[1]
                        #else:
                            #qty = rem_qty
                        
                        #if location_result.get(move.product_id.id).index(loc) == 0:
                            #move_obj.write(cr, uid, [move.id], {'location_id':loc[0],'product_qty': qty})
                            #move_id = move.id
                            
                        #else:
                            #default_value = {'location_id':loc[0],'product_qty': qty}
                            #move_obj.copy(cr, uid, move_id, default_value, context)
                            
                        #rem_qty -= loc[1]
        #return True

#