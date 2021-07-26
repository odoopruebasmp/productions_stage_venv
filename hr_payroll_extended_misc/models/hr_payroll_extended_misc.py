# -*- coding: utf-8 -*-
import logging
from openerp import models, fields, api
from openerp.exceptions import ValidationError

# from openerp.tools.safe_eval import safe_eval as eval

_logger = logging.getLogger('HR PAYROLL EXTENDED MISC')


class hr_job_risk(models.Model):
    _inherit = "hr.job"

    risk_id = fields.Many2one('hr.contract.risk', string='% de riesgo', required=False,
                              help='Este campo permite indicar el tipo de riesgo asociado al cargo, este campo es util porque dependiente del valor indicado se calculará el valor de ARL para este empleado.')


class res_partner_bank_extended(models.Model):
    _inherit = "res.partner.bank"

    partner_id = fields.Many2one('res.partner', string='Propietario de la cuenta', required=True,
                                 help='Este campo permite asociar la cuenta bancaria con el dueño de la misma.')

    _sql_constraints = [('acc_number_tercero_uniq', 'unique(partner_id, acc_number)',
                         'Las cuentas bancarias/terceros no se pueden repetir, por favor verificar.')]


class HRPayslipRunExtended(models.Model):
    _inherit = 'hr.payslip.run'

    group_id = fields.Many2one('hr.contract.group', string='Grupo de contrato',
                               help='Esta campo permite agrupar los contratos, según se va a calcular la nómina. Sirve para grupos que no sea por banco, centro de costo y/o ciudad de desempeño.')


    @api.multi
    def view_payslip(self):
        return {
            'name': 'Nóminas de colaboradores',
            'res_model': 'hr.payslip',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'view_type': 'form',
            'domain': [('payslip_run_id','=',self.id)],
            'target': 'current',
            'context': '',
        }


class HRPayslipExtended(models.Model):
    _inherit = 'hr.payslip'

    payslip_id = fields.Many2one('hr.payslip', string='Nómina relacionada', required=False,
                                 help='Este campo permite asociar la nómina actual con otras previamente calculadas, para así poder realizar nóminas retroactivas y/o reliquidación de contrato.')
    base = fields.Boolean(string='Basado en otras nóminas?', default=False,
                          help='Este campo permite indicar que el tipo de nómina esta basado en otras nóminas, esto sirve para nómina retroactivas o reliquidación de contrato.')

    @api.onchange('tipo_nomina')
    def _change_tipo_nomina(self):
        if self.tipo_nomina:
            self.base = self.tipo_nomina.base

    @api.multi
    def compute_prestamos_total(self):
        _logger.info('compute_prestamos_total')
        res = {}
        prestamos_obj = self.env['hr.payslip.prestamo.cuota']
        for payslip in self:
            _logger.info(payslip.prestamos_total_ids)
            self.env.cr.execute(
                ''' DELETE FROM hr_payslip_prestamo_cuota WHERE payslip_id = {payslip_id}'''.format(payslip_id=payslip.id))
            prestamos = {}
            for prestamo in payslip.prestamos_ids:
                if prestamo.category_id.name in prestamos:
                    prestamos[prestamo.category_id.name]['deuda'] += prestamo.deuda
                    prestamos[prestamo.category_id.name]['cuota'] += prestamo.cuota
                else:
                    prestamos[prestamo.category_id.name] = {
                        'category_id': prestamo.category_id.id,
                        'deuda': prestamo.deuda,
                        'cuota': prestamo.cuota,
                        'payslip_id': payslip.id,
                    }
            valores = [value for key, value in prestamos.items()]
            for val in valores:
                prestamos_obj.create(val)
        return True


class HRPayslipTypeExtended(models.Model):
    _inherit = 'hr.payslip.type'

    base = fields.Boolean(string='Basado en otras nóminas?', default=False,
                          help='Este campo permite indicar que el tipo de nómina esta basado en otras nóminas, esto sirve para nómina retroactivas o reliquidación de contrato.')
