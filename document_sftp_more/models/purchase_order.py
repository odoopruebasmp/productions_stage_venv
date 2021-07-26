# -*- coding: utf-8 -*-

from openerp import models, fields, api


class purchase_order(models.Model):
    _inherit = 'purchase.order'

    @api.multi
    def action_picking_create(self):
        res = super(purchase_order, self).action_picking_create()
        if self.picking_ids:
            picking_ids = [x.id for x in self.picking_ids]
            self.env['sftp.more'].sftp_send(picking_ids)
        return res
