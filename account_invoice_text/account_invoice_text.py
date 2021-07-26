from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.amount_to_text_en import amount_to_text
from lxml import etree
from amount_to_text_sp import Numero_a_Texto

class account_invoice(osv.osv):
    _inherit = "account.invoice"
    

    def _compute_total_tax(self, cr, uid, ids, name, args, context=None):
            res = {}
            for inovoice in self.browse(cr, uid, ids):
                amount = 0.0
                for tax in inovoice.tax_line:
                    if tax.account_id.code == '24080103':
                        amount += tax.amount
                res[inovoice.id] = amount
            return res        

    def _compute_total_value(self, cr, uid, ids, name, args, context=None):
            res_tax = {}
            res = {}
            for inovoice in self.browse(cr, uid, ids):
                amount = 0.0
                for tax in inovoice.tax_line:
                    if tax.account_id.code == '24080103':
                        amount += tax.amount
                res_tax[inovoice.id] = amount
                ttamount = (int(inovoice.amount_untaxed))
            
                res[inovoice.id] = ttamount + res_tax[inovoice.id]
            return res        

    def _compute_amount_word(self, cr, uid, ids, name, args, context=None):
        res = {}
        for voucher in self.browse(cr, uid, ids, context):
            res[voucher.id] = Numero_a_Texto(int(voucher.amount_total))
            res[voucher.id] += " PESOS MCTE"
        return res

            
    _columns = {
        'amount_in_word' : fields.function(_compute_amount_word, method=True, type="char", size=255, string="Total en letras"),
    }

account_invoice()
