# -*- coding: utf-8 -*-

from openerp import models, fields, api


class picking_move_product(models.Model):
    _name = 'picking.move.product'

    picking_id = fields.Char('Origen')
    move_id = fields.Char('Codigo')
    qty = fields.Char('Cantidad')
    lot_id = fields.Char('Lote')
    type_id = fields.Char('Tipo')
