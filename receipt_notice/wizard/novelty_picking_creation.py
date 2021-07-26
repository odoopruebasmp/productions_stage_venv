# -*- coding: utf-8 -*-
from openerp import models, fields, api
from openerp.exceptions import Warning
from lxml import etree
from datetime import datetime


class StockInvoiceOnshipping(models.TransientModel):
    _inherit = 'stock.invoice.onshipping'

    @api.multi
    def _exec_query(self):
        if 'full_nov' not in self._context:
            sql_s = 'pp.name_template,sm.novelty_amount,sm.id,sm.product_uom_qty'
            sql_w = 'AND (sm.novelty_amount > 0 OR (sm.received_amount = 0 AND sm.product_uom_qty > 0) OR (sm.received_amount IS Null AND sm.product_uom_qty > 0))'
        else:
            sql_s = 'pp.name_template,sm.product_uom_qty,sm.id'
            sql_w = ''
        self.env.cr.execute("SELECT %s FROM stock_move sm INNER JOIN stock_picking "
                            "sp ON sm.picking_id = sp.id INNER JOIN product_product pp ON sm.product_id = pp.id INNER "
                            "JOIN res_partner rp ON sp.partner_id = rp.id WHERE sm.picking_id = %s AND "
                            "rp.receipt_notice = True %s" % (sql_s, self._context['active_id'], sql_w))
        return self.env.cr.fetchall()

    @api.onchange('journal_id')
    def _calc_novelty(self):
        md = self._context.get('active_model', False)
        if md == 'stock.picking':
            pick = self.env[md].browse(self._context['active_id'])
            if pick.picking_type_code == 'outgoing':
                novelty = self._exec_query()
                txt = ''
                for nov in novelty:
                    txt += u'- {q}  - {p} \n'.format(q=nov[1] or nov[3], p=nov[0].strip())
                self.novelty_stock_moves = txt

    @api.multi
    def _create_novelty_returns(self):
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        pick = self.env['stock.picking'].browse(self._context['active_id'])

        # Cancel assignment of existing chained assigned moves
        moves_to_unreserve = []
        for move in pick.move_lines:
            to_check_moves = [move.move_dest_id] if move.move_dest_id.id else []
            while to_check_moves:
                current_move = to_check_moves.pop()
                if current_move.state not in ('done', 'cancel') and current_move.reserved_quant_ids:
                    moves_to_unreserve.append(current_move.id)
                split_move_ids = move_obj.search([('split_from', '=', current_move.id)])
                if split_move_ids:
                    to_check_moves += move_obj.browse(split_move_ids)

        if moves_to_unreserve:
            move_obj.do_unreserve(self._cr, self._uid, moves_to_unreserve, context=self._context)
            #break the link between moves in order to be able to fix them later if needed
            move_obj.write(self._cr, self._uid, moves_to_unreserve, {'move_orig_ids': False}, context=self._context)

        #Create new picking for returned products
        pick_type = pick.picking_type_id.novelty_picking_type_id
        if not pick_type:
            raise Warning("Por favor configure en el tipo de operacion '%s' el Tipo de Nota de Entrega para las "
                          "Novedades" % pick.picking_type_id.name)
        move_location_dest = pick_type.default_location_dest_id
        if pick.company_id.novelty_location_id != move_location_dest:
            raise Warning("Verifique que la ubicacion de novedades configurada en la compañia sea la misma que la "
                          "configurada en la Nota de Entrega de Novedades")
        new_picking = pick_obj.copy(self._cr, self._uid, pick.id, {
            'move_lines': [],
            'picking_type_id': pick_type.id,
            'state': 'draft',
            'origin': pick.name,
            'novelty_id': None,
            'novelty_state': 'open',
            'invoice_state': 'none'
            }, context=self._context)
        moves = self._exec_query()
        for mv in moves:
            move = move_obj.browse(self._cr, self._uid, mv[2], context=self._context)
            no_full_nov = 3
            new_qty = (mv[1] or mv[3]) if len(mv) > no_full_nov else mv[1]
            if new_qty:
                # The return of a return should be linked with the original's destination move if it was not cancelled
                if move.origin_returned_move_id.move_dest_id.id and \
                        move.origin_returned_move_id.move_dest_id.state != 'cancel':
                    move_dest_id = move.origin_returned_move_id.move_dest_id.id
                else:
                    move_dest_id = False

                move_obj.copy(self._cr, self._uid, move.id, {
                    'product_id': move.product_id.id,
                    'product_uom_qty': new_qty,
                    'product_uos_qty': new_qty * move.product_uos_qty / move.product_uom_qty,
                    'picking_id': new_picking,
                    'state': 'draft',
                    'location_id': move.location_dest_id.id,
                    'location_dest_id': move_location_dest.id,
                    'picking_type_id': pick_type.id,
                    'warehouse_id': pick_type.warehouse_id.id,
                    'origin_returned_move_id': move.id,
                    'procure_method': 'make_to_stock',
                    'move_dest_id': move_dest_id,
                    'received_amount': 0,
                    'novelty_amount': 0,
                    'novelty_state': 'pending',
                    'invoice_line_id': None
                    })

        pick_obj.action_confirm(self._cr, self._uid, [new_picking], context=self._context)
        pick_obj.action_assign(self._cr, self._uid, [new_picking], context=self._context)
        novelty_id = pick_obj.browse(self._cr, self._uid, new_picking).id
        pick.novelty_id = novelty_id
        pick.novelty_state = 'open'
        return novelty_id

    @api.multi
    def _create_transfer_nov_pick(self):
        novelty_pick = self.env['stock.picking'].browse(self._create_novelty_returns())
        std_obj = self.env['stock.transfer_details']
        stdi_obj = self.env['stock.transfer_details_items']
        vals = {
            'picking_id': novelty_pick.id,
            'item_ids': []
            }
        stk_tx_det = std_obj.create(vals)
        vals = {
            'transfer_id': stk_tx_det.id,
            'date': datetime.now()
            }
        for mv in novelty_pick.move_lines:
            vals.update({
                'product_id': mv.product_id.id,
                'product_uom_id': mv.product_uom_id.id,
                'quantity': mv.product_qty,
                'sourceloc_id': mv.location_id.id,
                'destinationloc_id': mv.location_dest_id.id
                })
            stdi_obj.create(vals)
        stk_tx_det.do_detailed_transfer()

    novelty_stock_moves = fields.Text('Movimientos con Novedades', readonly=True, help='Al pulsar el botón "Crear" se '
                                    'creará además de la factura un documento de Transferencia de inventario '
                                    'correspondiente a los movimientos que tuvieron Novedad')

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(StockInvoiceOnshipping, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            md = self._context.get('active_model', False)
            if md == 'stock.picking':
                pick = self.env[md].browse(self._context['active_id'])
                novelty = self._exec_query() if pick.picking_type_code == 'outgoing' else False
                if not novelty:
                    doc = etree.XML(res['arch'])
                    node = doc.xpath("//div")
                    doc.remove(node[0])
                    res['arch'] = etree.tostring(doc)
        return res

    @api.one
    def open_invoice(self):
        b = False
        if self._context.get('active_model', False) == 'stock.picking':
            self.env.cr.execute("SELECT rp.receipt_notice, sp.receipt_notice, rp.name, pt.type, spt.code FROM "
                                "stock_picking sp INNER JOIN res_partner rp ON sp.partner_id=rp.id INNER JOIN "
                                "stock_move sm ON sp.id=sm.picking_id INNER JOIN product_product pp ON "
                                "sm.product_id=pp.id INNER JOIN product_template pt ON pp.product_tmpl_id=pt.id INNER "
                                "JOIN stock_picking_type spt ON sp.picking_type_id=spt.id WHERE sp.id = %s" %
                                self._context['active_id'])
            pick = self.env.cr.fetchall()
            if pick[0][0]:
                if 'service' not in [x[3] for x in pick] and pick[0][4] == 'outgoing':
                    if not pick[0][1]:
                        raise Warning("El cliente %s, tiene marcado el check de Aviso de Recibo, por tanto no es posible "
                                      "crear la factura hasta que el documento de transferencia tenga un aviso de recibo "
                                      "asociado" % pick[0][2])
                    if pick[0][1] == 'Cancelado':
                        raise Warning("No es posible crear la factura para este documento, ya que la entrega fue "
                                      "cancelada. Revise la referencia del aviso de recibo.")
                    b = True
                else:
                    pick_obj = self.env['stock.picking']
                    b = True if pick[0][4] == 'outgoing' else False
                    pick = pick_obj.browse(self._context['active_id'])
                    deliv_order = pick.n_oc if 'n_oc' in pick._columns else pick.name
                    dt_now = datetime.now()
                    pick.write({
                        'rn_transaction_status': 'done',
                        'transaction_date': dt_now,
                        'receipt_notice': 'No Aplica',
                        'cust_accep_number': '',
                        'document_date': None,
                        'delivery_order': deliv_order,
                        'recadv_file': '',
                        'order_lines': 0
                        })
        res = super(StockInvoiceOnshipping, self).open_invoice()
        novelty = self._exec_query() if b else False
        if novelty:
            self._create_transfer_nov_pick()
        return res


class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    @api.one
    def create_returns(self):
        self.env.cr.execute("SELECT novelty_id FROM stock_picking WHERE id = %s" % self._context['active_id'])
        novelty_id = self.env.cr.fetchone()[0]
        if novelty_id and self.product_return_moves:
            self.env.cr.execute("SELECT product_id FROM stock_return_picking_line WHERE wizard_id = %s" % self.id)
            products = self.env.cr.fetchall()
            products = tuple([x[0] for x in products])
            self.env.cr.execute("SELECT pp.name_template FROM stock_move sm INNER JOIN product_product pp ON "
                                "sm.product_id = pp.id INNER JOIN stock_picking sp ON sm.picking_id = sp.id "
                                "WHERE sp.id = '{nid}' AND sm.product_id IN {prods}".format(nid=novelty_id,
                                prods=products if len(products) > 1 else tuple([products[0], 0])))
            products = self.env.cr.fetchall()
            if products:
                products = ['-' + x[0] + '-' for x in products]
                self.env.cr.execute("SELECT name FROM stock_picking WHERE id = %s" % novelty_id)
                novelty = self.env.cr.fetchone()[0]
                raise Warning("Producto(s) {prod} en novedad {nov}, favor validar".format(prod=products,
                                                                                          nov=novelty))
        res = super(StockReturnPicking, self).create_returns()
        return res


class FullNoveltyPickingWizard(models.TransientModel):
    _name = 'full.novelty.picking.wizard'

    @api.one
    def full_novelty(self):
        # noinspection PyMethodFirstArgAssignment
        self = self.with_context(full_nov=True)
        pick_obj = self.env['stock.picking']
        pick = pick_obj.browse(self._context['active_id'])
        if not pick.partner_id.receipt_notice:
            raise Warning("Para crear esta novedad el cliente {0} debe estar habilitado para gestion de Avisos de "
                          "Recibo, por favor validar".format(pick.partner_id.name))
        self.env['stock.invoice.onshipping']._create_transfer_nov_pick()
        msg = 'Entrega cancelada, no existe Aviso de recibo para picking ' + pick.name
        deliv_order = pick.n_oc if 'n_oc' in pick._columns else pick.name
        dt_now = datetime.now()
        pick_obj._create_ei_order_log('', pick.id, '', dt_now, msg, deliv_order, 'close', '', 'done', '', '', '')
        pick.write({
            'rn_transaction_status': 'done',
            'transaction_date': dt_now,
            'receipt_notice': 'Cancelado',
            'cust_accep_number': '',
            'document_date': None,
            'delivery_order': deliv_order,
            'recadv_file': '',
            'order_lines': 0
            })
