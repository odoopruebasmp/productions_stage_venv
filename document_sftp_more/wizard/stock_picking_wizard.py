# -*- coding: utf-8 -*-

from openerp import models, fields, api


class stock_picking_wizard(models.TransientModel):
    _name = 'stock.picking.wizard'

    def _default_pickings(self):
        return self.env['stock.picking'].browse(self._context.get('active_ids'))

    picking_ids = fields.Many2many('stock.picking',
                                   string="Pickings", required=True, default=_default_pickings)

    @api.multi
    def pickings_send(self):
        pickings = [x.id for x in self.picking_ids]
        self.env['sftp.more'].sftp_send(pickings)
        return True
