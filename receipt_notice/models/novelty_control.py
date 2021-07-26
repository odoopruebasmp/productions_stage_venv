# -*- coding: utf-8 -*-
from openerp import models, fields, api
from openerp.exceptions import Warning


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.multi
    def change_move_nov_state(self):
        if self.novelty_state == 'pending':
            self.novelty_state = 'in_progress'
        elif self.novelty_state == 'in_progress':
            res_id = self.env['novelty.movement.solution'].create({'move_note': ''})
            view_ref = self.env['ir.model.data'].get_object_reference('receipt_notice',
                                                                      'update_novelty_move')
            view_id = view_ref and view_ref[1] or False,
            return {
                'type': 'ir.actions.act_window',
                'name': 'Causal Novedad',
                'res_model': 'novelty.movement.solution',
                'res_id': res_id.id,
                'view_type': 'form',
                'view_mode': 'form',
                'context': self._context,
                'view_id': view_id,
                'target': 'new',
                }


class StockTransferDetails(models.TransientModel):
    _inherit = 'stock.transfer_details'

    @api.one
    def do_detailed_transfer(self):
        self.env.cr.execute('SELECT novelty_location_id FROM res_company WHERE id = %s' % self.write_uid.company_id.id)
        nov_loc = self.env.cr.fetchone()
        if nov_loc[0]:
            self.env.cr.execute('SELECT destinationloc_id FROM stock_transfer_details_items WHERE transfer_id = %s' %
                                self.id)
            dest_locs = self.env.cr.fetchall()
            if nov_loc in dest_locs:
                if self.picking_id.picking_type_id.default_location_dest_id.id == nov_loc[0]:
                    res = super(StockTransferDetails, self).do_detailed_transfer()
                    return res
                else:
                    raise Warning("Por favor verifique la ubicación destino de los productos a transferir, esta ubicación "
                              "solo es seleccionable para las notas de entrega de Factura Electrónica.")
            else:
                res = super(StockTransferDetails, self).do_detailed_transfer()
                return res
        res = super(StockTransferDetails, self).do_detailed_transfer()
        return res
