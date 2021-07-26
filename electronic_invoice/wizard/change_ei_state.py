# -*- coding: utf-8 -*-
from openerp import models, fields, api


class ChangeEiState(models.TransientModel):
    _name = 'change.ei.state'

    @api.multi
    def chg_ei_state(self):
        self.env['account.invoice'].browse(self._context['active_id']).ei_state = 'pending'
