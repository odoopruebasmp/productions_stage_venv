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
from openerp.addons.edi import EDIMixin
import math

  
    
class account_account(models.Model):
    _inherit = "account.account"
    
    
    @api.one
    @api.depends('name')
    def _compute(self):
        self.balance = 1  
        self.credit = 1
        self.debit = 1
        self.foreign_balance = 1
        self.adjusted_balance = 1
        self.unrealized_gain_loss = 1
    
    balance = fields.Float(string='Balance', digits=dp.get_precision('Account'),  compute="_compute")
    credit = fields.Float(string='Debit', digits=dp.get_precision('Account'),  compute="_compute")
    debit = fields.Float(string='Debit', digits=dp.get_precision('Account'),  compute="_compute")
    foreign_balance = fields.Float(string='1', digits=dp.get_precision('Account'),  compute="_compute")
    adjusted_balance = fields.Float(string='2', digits=dp.get_precision('Account'),  compute="_compute")
    unrealized_gain_loss = fields.Float(string='3', digits=dp.get_precision('Account'),  compute="_compute")
    
#