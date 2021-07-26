# -*- coding: utf-8 -*-

from openerp import models, fields, api
from openerp.addons.avancys_orm import avancys_orm


class sftp_quant_wizard(models.TransientModel):
    _name = 'sftp.quant.wizard'

    product_ids = fields.Many2many('product.product', 'sftp_product_rel', 'sftp_id', 'product_id',
                                   'Productos')
    location_ids = fields.Many2many('stock.location', 'sftp_location_rel', 'sftp_id', 'location_id',
                                    'Ubicaciones')
    user_id = fields.Many2one('res.users', 'Usuario', default=lambda self: self.env.user, copy=False)
    company_id = fields.Many2one('res.company', 'Compañia')

    @api.multi
    def action_confirm(self):
        sftp_obj = self.env['sftp.quant']
        # Productos
        if not self.product_ids:
            domain = [('type', '=', 'product')]
            products = self.env['product.product'].search(domain)
            bool_product = False
        else:
            products = self.product_ids
            bool_product = True
        products = [x.id for x in products]
        if len(products) > 1:
            wp = 'in'
            products = tuple(products)
        else:
            wp = '='
            products = products[0]
        # Ubicaciones
        if not self.location_ids:
            domain = [('usage', '=', 'internal'),('state_dlx','!=',False)]
            locations = self.env['stock.location'].search(domain)
            bool_location = False
        else:
            locations = self.location_ids
            bool_location = True
        locations = [x.id for x in locations]
        if len(locations) > 1:
            wl = 'in'
            locations = tuple(locations)
        else:
            wl = '='
            locations = locations[0]
        # Query
        query = 'select pp.id, sl.id, sq.lot_id, pt.uom_id, sum(sq.qty) ' \
                'from stock_quant sq ' \
                'inner join product_product pp on pp.id = sq.product_id ' \
                'inner join stock_location sl on sl.id = sq.location_id ' \
                'inner join product_template pt on pt.id = pp.product_tmpl_id '
        query_where = 'where pp.id ' + wp + ' %s ' + 'and sl.id ' + wl + ' %s '
        query_group = 'group by pp.id, sl.id, sq.lot_id, pt.uom_id'
        query = query + query_where + query_group
        values = {'bool_product': bool_product,
                  'bool_location': bool_location}
        sftp_id = sftp_obj.create(values)
        line = []
        self._cr.execute(query, (products, locations))
        for row in self._cr.fetchall():
            if not row[2]:
                line_value = {'sftp_id': sftp_id.id,
                              'product_id': row[0],
                              'location_id': row[1],
                              'uom_id': row[3],
                              'qty': row[4]}
            else:
                line_value = {'sftp_id': sftp_id.id,
                              'product_id': row[0],
                              'location_id': row[1],
                              'lot_id': row[2],
                              'uom_id': row[3],
                              'qty': row[4]}
            line.append(line_value)
        avancys_orm.direct_create(self._cr, self._uid, 'sftp_quant_line', line, progress=True)
        return {
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'sftp.quant',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'name': 'Stock compare',
            'domain': [('id', '=', sftp_id.id)]
            }
