# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
# from openerp.tools.translate import _
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

class account_move_line(models.Model):    
    _inherit = "account.move.line"
    
    def create(self, cr, uid, vals, context=None):
        if not vals.get('account_id'):
            res = 0
            if vals.has_key('journal_id'):
                if self.pool.get('account.journal').read(cr, uid, vals.get('journal_id'), ['type'], context=context)['type'] == 'crossing':
                    res = 0
                else:
                    raise osv.except_osv(_('Error!'),_("Está intentando crear un movimiento contable sin cuentas"))
        else:
            res = super(account_move_line,self).create(cr, uid, vals, context=context)
        return res

class account_journal(models.Model):    
    _inherit = "account.journal"
    
    type = fields.Selection(selection_add=[('crossing', 'Cruce de cuentas')])
        
class account_voucher(models.Model):
    _inherit = "account.voucher"
    
    account_id=fields.Many2one('account.account', string='Account', required=False, readonly=True, states={'draft':[('readonly',False)]})
    type = fields.Selection(selection_add=[('crossing','Crossing')])
        
    def recompute_voucher_lines(self, cr, uid, ids, partner_id, journal_id, price, currency_id, ttype, date, context=None):
        values = super(account_voucher, self).recompute_voucher_lines(cr, uid, ids, partner_id, journal_id, price, currency_id, ttype, date, context=context)
        if context.get('type') == 'crossing':
            values_2 = super(account_voucher, self).recompute_voucher_lines(cr, uid, ids, partner_id, journal_id, price, currency_id, 'payment', date, context=context)
            values['value']['line_dr_ids'] += values_2['value']['line_dr_ids']
        return values
   
    def write(self, cr, uid, ids, values, context=None):
        res = super(account_voucher, self).write(cr, uid, ids, values, context=context)
        for voucher in self.browse(cr, uid, ids, context=context):
            if voucher.type == 'crossing' and voucher.writeoff_amount != 0:
                if voucher.diferencia != 0.0:
                    raise osv.except_osv(_('Error!'),_("No puede existir una diferencia a conciliar"))                    
        return res
#
