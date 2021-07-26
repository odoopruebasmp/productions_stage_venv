# -*- coding: utf-8 -*-
"""
Model for generation of recoup sale invoices from recoup lines
"""
from itertools import groupby
from openerp import fields, api, models
from openerp.exceptions import Warning


NO_SELECTED_PIGKING_WARNING = """
No hay ningun documento valido por enviar
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

class SFTPMultiSend(models.TransientModel):
    _name = 'sftp.multi.send'
    _description = 'Envio multiple de SFTP'

    pickings = fields.Text('Documentos por enviar', readonly=True)

    @api.onchange('pickings')
    def populate_invoices(self):
        txt = ''
        for picking in self.env['stock.picking'].browse(self._context['active_ids']).filtered(
                lambda picking: not picking.bool_send
                and picking.state not in ('draft', 'cancel', 'confirmed', 'done')):
            txt += u'{name} - {origin} - {state}\n'.format(
                name=picking.name, origin=picking.origin, state=PICKING_MAP.get(picking.state,''))
        self.pickings = txt

    @api.multi
    def send_pickings(self):
        pickings = self.env['stock.picking'].browse(self._context['active_ids']).filtered(
            lambda picking: not picking.bool_send
            and picking.state not in ('draft', 'cancel', 'confirmed', 'done'))
        if not pickings:
            raise Warning(NO_SELECTED_PIGKING_WARNING)
        for picking in pickings:
            picking.picking_send()
        pass
