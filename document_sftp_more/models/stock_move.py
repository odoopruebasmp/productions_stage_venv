# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta

class stock_move(models.Model):
    _inherit = 'stock.move'

    bool_receive = fields.Boolean('Leido', copy=False)
    bool_transfer = fields.Boolean('Transferir', copy=False)
    scheduled_time_ol = fields.Datetime('Fecha de entrega OL', related='picking_id.scheduled_time_ol')

    @api.multi
    def lot_names(self):
        lot_name = ''
        for reserved in self.reserved_quant_ids:
            if reserved.lot_id:
                lot_name += ', ' + reserved.lot_id.name
        for quant in self.quant_ids:
            if quant.lot_id:
                lot_name += ', ' + quant.lot_id.name
        return lot_name

    @api.multi
    def quant_qty(self):
        qty = 0
        for reserved in self.reserved_quant_ids:
            qty += reserved.qty
        return qty
    
    @api.multi
    def date_more(self):
        date = str(datetime.strptime(
            self.scheduled_time_ol, "%Y-%m-%d %H:%M:%S") - timedelta(hours=5))
        # AAAAMMDDHHSS
        AAAA = date[:4]
        MM = date[5:7]
        DD = date[8:10]
        HH = date[11:13]
        SS = date[-2:]
        dater = AAAA + MM + DD + HH + SS
        return dater

    @api.multi
    def partner_name(self):
        name = ''
        name1 = self.partner_id.city_id.name or ''
        name2 = self.partner_id.state_id.name or ''
        name += name1 + '' + name2
        return name
