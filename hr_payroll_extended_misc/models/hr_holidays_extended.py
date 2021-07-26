# -*- coding: utf-8 -*-
import logging

from openerp import models, fields, api
from openerp.exceptions import ValidationError

_logger = logging.getLogger('HR HOLIDAYS EXTENDED')


class HRHolidaysStatusExtended(models.Model):
    _inherit = "hr.holidays.status"

    days_limit = fields.Integer(string='Dias limite', required=False,
                                help='Los dias indicados en este campo, permitirán establecer un limite de dias a registrar para este tipo de ausencia, en la periodicidad indicada en el siguiente campo.')
    schedule_limit = fields.Selection([('annually', 'Anual')], string='Planificación de limite', index=True,
                                      required=False,
                                      help='La periodicidad indicada en este campo, va a permitir que se pueda establecer un limite de registro de ausencias de este tipo para esa periodicidad.')


class HRHolidaysExtended(models.Model):
    _inherit = "hr.holidays"

    def _verify_holidays_status(self, employee_id, holiday_status_id, date_from, date_to):
        if holiday_status_id.days_limit > 0:
            year_from = date_from[0:4]
            year_to = date_to[0:4]
            date_start_from = year_from + '-01-01'
            date_start_to = year_from + '-12-31'
            date_end_from = year_to + '-01-01'
            date_end_to = year_to + '-12-31'
            self.env.cr.execute(
                ''' SELECT SUM(number_of_days_temp) 
                            FROM hr_holidays 
                            WHERE employee_id = {employee_id} 
                                AND holiday_status_id = {holiday_status_id}
                                AND ((date_from BETWEEN '{date_start_from}' AND '{date_start_to}') 
                                OR (date_to BETWEEN '{date_end_from}' AND '{date_end_to}')) 
                                '''.format(employee_id=employee_id.id, holiday_status_id=holiday_status_id.id,
                                           date_start_from=date_start_from, date_start_to=date_start_to,
                                           date_end_from=date_end_from, date_end_to=date_end_to))
            data = self.env.cr.fetchone()[0]
            if data > holiday_status_id.days_limit:
                raise ValidationError(
                    'El colaborador debe tener registrado en el periodo, máximo {max} dias de ausencias para el tipo {type}'.format(
                        max=holiday_status_id.days_limit, type=holiday_status_id.name))
        return True

    @api.multi
    def holidays_validate(self):
        res = super(HRHolidaysExtended, self).holidays_validate()
        _logger.info(self)
        # self.compute()
        self._verify_holidays_status(self.employee_id, self.holiday_status_id, self.date_from, self.date_to)
        _logger.info(res)
        return res
