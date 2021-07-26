# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
import openerp.netsvc
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil import relativedelta, parser
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval
from openerp import models, api
from openerp import fields as fields2

class res_ciiu(osv.osv):
    _name = "res.ciiu"
    _order = 'name asc'
    
    _columns = {
        'name' : fields.char('Codigo', size=4, required=True),
        'desc' : fields.char('Descripcion', size=256, required=True),
        'tax_ids': fields.many2many('account.tax', 'res_ciiu_tax', 'ciiu_id', 'tax_id', 'Taxes', domain=[('parent_id','=',False)]),
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
    ]

class res_partner_ciiu(osv.osv):
    _inherit = "res.partner"

    _columns = {
        'ciiu_id': fields.many2one('res.ciiu', "CIIU"),
    }

class account_fiscal_position(osv.osv):
    _inherit = 'account.fiscal.position'

    def map_tax2(self, cr, uid, fposition_id, taxes_to_map, partner, direccion, ciiu, context=None):
        cr.execute("SELECT company_id from res_users where id = %s" % uid)
        company_id = self.pool.get('res.company').browse(cr, uid, cr.fetchone()[0], context=context)
        ctx = context.copy()
        if company_id.ciiu_ica:            
            if partner.ciiu_id and not ciiu:
                ciiu = partner.ciiu_id
        result = super(account_fiscal_position, self).map_tax2(cr, uid, fposition_id, taxes_to_map, partner, direccion, ciiu, context=ctx)
        if partner:
            ciiu = partner.ciiu_id
            if ciiu:
                for x in ciiu.tax_ids:
                    if x.id not in result:
                        result.append(x.id)
        return result


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'
    _name = 'account.invoice.line'

    ciiu_id = fields2.Many2one('res.ciiu', 'CIIU')
    city_id = fields2.Many2one('res.city', 'Ciudad')

