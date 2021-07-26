# -*- coding: utf-8 -*-

import time
from openerp.report import report_sxw

class quotation_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(quotation_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update( {'time': time,})
                   
report_sxw.report_sxw('report.purchase.quotation.supplier', 'purchase.quotation.supplier', 'purchase_requisition_extended/report/cotizacion.rml', parser=quotation_report)