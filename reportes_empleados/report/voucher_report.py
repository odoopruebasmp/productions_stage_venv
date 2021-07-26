# -*- coding: utf-8 -*-

import time
from openerp.report import report_sxw
from openerp import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta
import calendar
from calendar import monthrange as mr


def monthrange(year=None, month=None):
    today = datetime.today()
    y = year or today.year
    m = month or today.month
    return y, m, calendar.monthrange(y, m)[1]

class hr_employee(models.Model):
    _inherit = "hr.employee"
    
    coordinador_rrhh = fields.Many2one('hr.employee', string='Coordinador de RRHH')

class report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update( {'time': time,})
                   
report_sxw.report_sxw('report.hr.contract.certificado', 'hr.contract', 'reportes_empleados/report/certificado_laboral.rml', parser=report)


class HrContract(models.Model):
    _inherit = 'hr.contract'

    @api.multi
    def get_avg(self):
        for contract in self:
            date = datetime.now()
            if contract.state == 'done':
                date = datetime.strptime(contract.date_end, "%Y-%m-%d")
            date_from = datetime.strftime(date - relativedelta(months=3), "%Y-%m-%d")[0:7] + '-01'
            date_to = datetime.strftime(date - relativedelta(months=1), "%Y-%m-%d")
            max_days = mr(int(date_to[0:4]), int(date_to[5:7]))[1]
            date_to = date_to[0:7] + '-' + str(max_days)

            is_itv = self.env['hr.payslip'].get_interval_category('earnings', date_from, date_to, exclude=('BASICO',),
                                                                  contract=contract.id)
            comp_itv = self.env['hr.payslip'].get_interval_category('comp_earnings', date_from, date_to,
                                                                    contract=contract.id)
            osal_itv = self.env['hr.payslip'].get_interval_category('o_salarial_earnings', date_from, date_to,
                                                                    contract=contract.id)
            ns_itv = self.env['hr.payslip'].get_interval_category('o_earnings', date_from, date_to,
                                                                  contract=contract.id)

            is_avg = (sum([x[1] for x in is_itv]) + sum([x[1] for x in comp_itv]) + sum([x[1] for x in osal_itv])) / 3
            ns_avg = sum([x[1] for x in ns_itv]) / 3

            return is_avg, ns_avg

    @api.multi
    def get_avg12(self):
        for contract in self:
            date = datetime.now()
            if contract.state == 'done':
                date = datetime.strptime(contract.date_end, "%Y-%m-%d")
            date_from = datetime.strftime(date - relativedelta(months=12), "%Y-%m-%d")[0:7] + '-01'
            date_to = datetime.strftime(date - relativedelta(months=1), "%Y-%m-%d")
            max_days = mr(int(date_to[0:4]), int(date_to[5:7]))[1]
            date_to = date_to[0:7] + '-' + str(max_days)

            is_itv = self.env['hr.payslip'].get_interval_category('earnings', date_from, date_to, exclude=('BASICO',),
                                                                  contract=contract.id)
            comp_itv = self.env['hr.payslip'].get_interval_category('comp_earnings', date_from, date_to,
                                                                    contract=contract.id)
            osal_itv = self.env['hr.payslip'].get_interval_category('o_salarial_earnings', date_from, date_to,
                                                                    contract=contract.id)
            ns_itv = self.env['hr.payslip'].get_interval_category('o_earnings', date_from, date_to,
                                                                  contract=contract.id)

            is_avg = (sum([x[1] for x in is_itv]) + sum([x[1] for x in comp_itv]) + sum([x[1] for x in osal_itv])) / 12
            ns_avg = sum([x[1] for x in ns_itv]) / 12

            return is_avg, ns_avg
