from openerp.osv import osv, fields
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from datetime import datetime
import time
from dateutil.relativedelta import relativedelta
from openerp.tools.float_utils import float_round
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare

class res_company(osv.osv):
    _inherit = "res.company"
    
    _columns = {
        'uvt_number': fields.float('UVTs Activos', digits_compute= dp.get_precision('Variable Economica'),help="Este es el numero de UVT, si el valor del activo; es menor al valor del UVT de la fecha comprada multiplicado por este numero, este debera ser depreciado totalmente el mismo ano de compra"),
    }

class account_asset_asset(osv.osv):
    _inherit = "account.asset.asset"
        
    def onchange_category_id(self, cr, uid, ids, category_id, purchase_value, salvage_value, tax_ids, company_id, purchase_date, context=None):
        res = super(account_asset_asset, self).onchange_category_id(cr, uid, ids, category_id, context=context)
        asset_categ_obj = self.pool.get('account.asset.category')
        company_obj = self.pool.get('res.company')
        var_eco = self.pool.get('variables.economicas')
        tax_pool = self.pool.get('account.tax')
        
        if category_id:
            category_obj = asset_categ_obj.browse(cr, uid, category_id, context=context)
            res['value'].update({
                'period_prorate': category_obj.period_prorate,
            })
            if purchase_value and purchase_date and company_id:
                taxes = 0
                
                try:
                    for tax in tax_pool.compute_all(cr, uid, tax_pool.browse(cr, uid, tax_ids[0][2], context=context), purchase_value, 1)['taxes']: 
                        taxes += tax['amount']
                except:
                    pass

                purchase_date= str(purchase_date) + " 00:00:00"
                valor_uvt = var_eco.getValue(cr, 'UVT', purchase_date, context=context)
                max_uvt = company_obj.browse(cr, uid, company_id, context=context).uvt_number*valor_uvt
                
                if (purchase_value+taxes-salvage_value) <= max_uvt:
                    
                    res['value'].update({
                        'uvt_calculado': max_uvt,
                        'prorata': True,
                        'method': 'linear',
                        'method_time': 'end',
                        'method_end': purchase_date[0:4]+'-12-31',
                    })
            
        return res
        
    def onchange_atrb(self, cr , uid, ids, purchase_value, purchase_date, context = None):
        uvt = self.pool.get('variables.economicas').getValue(cr, uid, 'UVT', purchase_date, context)
        if purchase_value <= uvt*50: 
            purchase_date = datetime.strptime(purchase_date, DEFAULT_SERVER_DATE_FORMAT)
            month = purchase_date.month
            if month == 12:
                numero = 12
            else:
                numero = 12-month
                    
            return {'value': {'method_number': numero,'method_period': 1,}}
        else:
            return False
        
#
