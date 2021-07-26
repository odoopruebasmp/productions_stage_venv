from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.amount_to_text_en import amount_to_text
from lxml import etree

class account_invoice(osv.Model):
    _inherit = "account.invoice"


    def invoice_print(self, cr, uid, ids, context=None):
        res= super(account_invoice, self).invoice_print(cr, uid, ids, context=context)
        s= {}
        for val in self.browse(cr, uid, ids,context):
            s= val.is_copy + 1
        self.write(cr, uid, ids, {'is_copy':s}, context=context)
        return res
                    
    def action_cancel(self, cr, uid, ids, context=None):
        res = super(account_invoice, self).action_cancel(cr, uid, ids, context=context) #self, cr, uid, ids, context)
        self.write(cr, uid, ids, {'is_copy': -1}, context=context)
        return res


    _columns = {
        'is_copy': fields.integer('Copia',invisible='True'),
    }
