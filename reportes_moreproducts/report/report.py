# -*- coding: utf-8 -*-

import time
from openerp.report import openerp.report_sxw

class report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update( {'time': time,})

report_sxw.report_sxw('report.account.report_invoice2', 'account.invoice', 'reportes_moreproducts/report/factura.rml', parser=order)


