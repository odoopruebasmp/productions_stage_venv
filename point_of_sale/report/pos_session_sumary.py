# -*- coding: utf-8 -*-
from openerp import fields, models, api

class PosSession(models.Model):
    _inherit = 'pos.session'

    def query_resumen(self, id):
        query = "select pp.name_template as name, " \
                "sum(pol.qty) as qty, " \
                "sum(pol.price_subtotal) as price " \
                "from pos_session ps " \
                "inner join pos_order po on po.session_id = ps.id " \
                "inner join pos_order_line pol on pol.order_id = po.id " \
                "inner join product_product pp on pp.id = pol.product_id " \
                "where  ps.id = %s " \
                "group by pp.name_template"
        self._cr.execute(query, (id, ))
        data = self._cr.dictfetchall()
        return data
        