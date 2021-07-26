# -*- coding: utf-8 -*-
"""
Model for generation of recoup sale invoices from recoup lines
"""
from itertools import groupby
from openerp import fields, api, models
from openerp.exceptions import Warning


NO_SELECTED_PIGKING_WARNING = """
No hay ningun documento valido por comprobar
"""

PICKING_MAP = {
    'draft': 'Borrador',
    'cancel': 'Cancelado(a)',
    'waiting': 'Esperando otra operacion',
    'confirmed': 'Esperando Disponibilidad',
    'partially_available': 'Parcialmente disponible',
    'assigned': 'Listo para transferir',
    'done': 'Transferido',
}

class PickingMultiAssign(models.TransientModel):
    _name = 'picking.multi.assign'
    _description = 'Comprobar disponibilidad'

    pickings = fields.Text(
        'Documentos por comprobar disponibilidad', readonly=True)

    @api.onchange('pickings')
    def populate_invoices(self):
        txt = ''
        for picking in self.env['stock.picking'].browse(self._context['active_ids']).filtered(
                lambda picking: picking.state in ('confirmed')):
            txt += u'{name} - {origin} - {state}\n'.format(
                name=picking.name, origin=picking.origin, state=PICKING_MAP.get(picking.state,''))
        self.pickings = txt

    @api.multi
    def assign_pickings(self):
        pickings = self.env['stock.picking'].browse(self._context['active_ids']).filtered(
            lambda picking: picking.state in ('confirmed'))
        if not pickings:
            raise Warning(NO_SELECTED_PIGKING_WARNING)
        for picking in pickings:
            picking.action_assign()
        pass
