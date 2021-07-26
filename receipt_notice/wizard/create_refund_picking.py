# -*- coding: utf-8 -*-
from openerp import models, fields, api
from openerp.exceptions import Warning
from datetime import datetime


class RefundPickingWizard(models.TransientModel):
    _name = 'refund.picking.wizard'

    location_id = fields.Many2one('stock.location', 'Ubicación Destino', required=True, domain=[('usage', '=',
                                                                                                 'internal')])

    @api.multi
    def create_picking(self):
        picking = self.env['stock.picking'].browse(self._context['active_id'])
        self.env.cr.execute('SELECT novelty_state FROM stock_move WHERE picking_id = %s GROUP BY novelty_state' %
                            picking.id)
        nov_states = self.env.cr.fetchall()
        if not(len(nov_states) == 1 and nov_states[0][0] == 'done'):
            raise Warning("El estado de novedad de todos los movimientos asociados a esta transferencia debe ser "
                          "'Resuelto', favor validar.")
        picking.novelty_state = 'done'
        self.env.cr.execute("UPDATE stock_picking SET novelty_state = 'done' WHERE name = '%s'" % picking.origin)
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        self.env.cr.execute("SELECT id FROM stock_picking_type WHERE warehouse_id = %s AND code = 'incoming' LIMIT 1" %
                            picking.picking_type_id.warehouse_id.id)
        picking_type = self.env.cr.fetchone()
        if not picking_type or not picking_type[0]:
            raise Warning("Por favor configure una nota de entrega de tipo proveedor para el almacén %s" %
                          picking.picking_type_id.warehouse_id.name)
        new_picking = pick_obj.copy(self._cr, self._uid, picking.id, {
            'move_lines': [],
            'picking_type_id': picking_type[0],
            'state': 'draft',
            'origin': picking.name,
            'novelty_id': None,
            'novelty_state': None,
            'invoice_state': 'none',
            'date': datetime.now(),
            'max_date': datetime.now(),
            'move_type': 'one',
            }, context=picking._context)
        loc_dest = self.location_id.id
        for move in picking.move_lines:
            move_obj.copy(self._cr, self._uid, move.id, {
                'product_id': move.product_id.id,
                'product_uom_qty': move.product_uom_qty,
                'product_uos_qty': move.product_uos_qty,
                'picking_id': new_picking,
                'state': 'draft',
                'location_id': move.location_dest_id.id,
                'location_dest_id': loc_dest,
                'picking_type_id': picking_type[0],
                'warehouse_id': picking.picking_type_id.warehouse_id.id,
                'origin_returned_move_id': move.id,
                'procure_method': 'make_to_stock',
                'received_amount': 0,
                'novelty_amount': 0,
                'novelty_state': None
                })
        pick_obj.action_confirm(self._cr, self._uid, [new_picking], context=picking._context)
        pick_obj.action_assign(self._cr, self._uid, [new_picking], context=picking._context)
        picking.refund_document_id = new_picking
        std_obj = self.pool.get('stock.transfer_details')
        stdi_obj = self.pool.get('stock.transfer_details_items')
        vals = {
            'picking_id': new_picking,
            'item_ids': []
            }
        stk_tx_det = std_obj.create(self._cr, self._uid, vals, context=picking._context)
        vals = {
            'transfer_id': stk_tx_det,
            'date': datetime.now()
            }
        for mv in self.env['stock.picking'].browse(new_picking).move_lines:
            vals.update({
                'product_id': mv.product_id.id,
                'product_uom_id': mv.product_uom_id.id,
                'quantity': mv.product_qty,
                'sourceloc_id': mv.location_id.id,
                'destinationloc_id': mv.location_dest_id.id
                })
            stdi_obj.create(self._cr, self._uid, vals, context=picking._context)
        std_obj.browse(self._cr, self._uid, stk_tx_det).do_detailed_transfer()
