# -*- coding: utf-8 -*-
from openerp import models, fields, api, _


class stock_picking(models.Model):
    _inherit = "stock.picking"
    
    @api.one
    @api.depends('move_lines','move_lines.product_qty')
    def _qty_items(self):
        if self.move_lines:
            qty_items=0.0
            for move in self.move_lines:
                qty_items+=move.product_qty
            self.qty_items = qty_items         
       
    qty_items = fields.Float(string='Cantidad de Items', compute="_qty_items")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    deli_addres = fields.Char('Dirección', size=200, help="Llene este campo con la dirección"
                                "de envío Real, por defecto está la dirección asociada al tercero")

    def onchange_partner_id2(self, cr, uid, ids, part, date, context=None):
        res = super(SaleOrder, self).onchange_partner_id2(cr, uid, ids, part, date, context=context)
        if res['value']['partner_shipping_id']:
            part_obj = self.pool.get('res.partner')
            partner = part_obj.browse(cr, uid, res['value']['partner_shipping_id'], context)
            if partner.main_street:
                cr.execute("UPDATE res_partner SET street = '{st}' WHERE id = {pi}"
                                 .format(st=partner.main_street, pi=partner.id))
            addres = partner.street
            res['value']['deli_addres'] = str(addres)
        return res

    @api.model
    @api.onchange('deli_addres')
    def change_partner_addres(self):
        if self.deli_addres:
            main_street = self.partner_shipping_id.street
            self._cr.execute("UPDATE res_partner SET (street,main_street) = ('{st}','{mad}') WHERE id = {pi}"
                         .format(st=self.deli_addres, mad=main_street, pi=self.partner_shipping_id.id))
        return

class ResPartner(models.Model):
    _inherit = 'res.partner'

    main_street = fields.Char('Dirección Principal', size=200, help="Esta es la Dirección Principal por defecto para "
                                                                    "los Pedidos de Venta")
