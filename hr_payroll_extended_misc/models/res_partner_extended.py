# -*- coding: utf-8 -*-
import logging
from openerp import models, fields, api
from openerp.exceptions import ValidationError

_logger = logging.getLogger('RES PARTNER EXTENDED')


class ResPartner(models.Model):
    _inherit = 'res.partner'


    @api.onchange('employee_id')
    def _is_employee(self):
        if self.employee_id:
            self.employee = True
        else:
            self.employee = False