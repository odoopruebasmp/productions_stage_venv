# -*- coding: utf-8 -*-
from openerp import models, fields, api
from openerp.exceptions import Warning


class NoveltyMovementSolution(models.TransientModel):
    _name = 'novelty.movement.solution'

    move_note = fields.Char(string='Nota', size=280)

    @api.multi
    def novelty_note(self):
        if 'active_id' in self._context:
            move = self.env['stock.move'].browse(self._context['active_id'])
            move.note = self.move_note
            move.novelty_state = 'done'
        else:
            raise Warning("Por favor contacte al área de soporte para así atender el problema presentado")