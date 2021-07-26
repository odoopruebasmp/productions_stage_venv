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

class wizard_assign_proposed(models.TransientModel):    
    _name = 'wizard.assign.proposed'
    
    
    def assign_proposed(self, cr, uid, ids, context=None):
        '''
            will assign the line qty to proposed qty if the the other order has less qty than available qty. 
        '''
        if not context: context = {}
        line_obj = self.pool.get('sale.order.line')
        order_obj = self.pool.get('sale.order')
        product_dict = {}
        
        quote_ids = order_obj.search(cr, uid, [('state', '=', 'draft')])
        for quote_id in quote_ids:
            line_ids = line_obj.search(cr, uid, [('order_id', '=', quote_id)])
            for line in line_obj.browse(cr, uid, line_ids, context=context):
                if product_dict.get(line.product_id.id):
                    product_dict.update({line.product_id.id:product_dict.get(line.product_id.id) + line.product_uom_qty})
                else:
                    product_dict.update({line.product_id.id:line.product_uom_qty})
    
        for quote_id in quote_ids:
            line_ids = line_obj.search(cr, uid, [('order_id', '=', quote_id)])
            for line in line_obj.browse(cr, uid, line_ids, context=context):
                if product_dict.get(line.product_id.id) and product_dict.get(line.product_id.id) <= line.product_id.qty_available:
                    line_obj.write(cr, uid, [line.id], {'proposed_qty': line.product_uom_qty}, context=context)
        return True
        