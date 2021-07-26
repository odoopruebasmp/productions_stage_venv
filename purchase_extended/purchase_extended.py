# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
# from openerp.tools.translate import _
from openerp import addons
from openerp import SUPERUSER_ID
import itertools
from dateutil.relativedelta import relativedelta
from lxml import etree
from openerp import models, fields, api, _
from openerp.osv import osv, fields as fields2
from openerp.exceptions import except_orm, Warning, RedirectWarning
import openerp.addons.decimal_precision as dp
import math


class account_invoice(models.Model):
    _inherit = 'account.invoice'
    
    def invoice_validate(self, cr, uid, ids, context=None):
        res = super(account_invoice, self).invoice_validate(cr, uid, ids, context=context)
        for inv in self.browse(cr, uid, ids, context=context):
            for line in inv.invoice_line:
                order_line = False
                if line.order_line_id:
                    order_line = line.order_line_id
                if line.stock_move_id and line.stock_move_id.purchase_line_id:
                    order_line = line.stock_move_id.purchase_line_id
                if order_line:
                    if order_line.product_id.id != line.product_id.id:
                        raise osv.except_osv(_('Error!'), _('El producto "%s" de la factura es diferente al producto "%s" de la orden de compra') % (line.product_id.name, order_line.product_id.name,))
                    po = order_line.order_id
                    if not any([True for x in po.picking_ids if x.state in ('cancel', 'done')]):
                        po.state = 'done'
            for stock_mv in inv.stock_picking_id.move_lines:
                if stock_mv.purchase_line_id:
                    po = stock_mv.purchase_line_id.order_id
                    if not any([True for x in po.picking_ids if x.state in ('cancel', 'done')]):
                        po.state = 'done'
        return res

class account_invoice_line(models.Model):
    _inherit = 'account.invoice.line'
    
    order_line_id = fields.Many2one('purchase.order.line', string='Linea de compra', readonly=True)
    

class stock_move(models.Model):
    _inherit = 'stock.move'
    
    @api.one
    @api.depends('purchase_line_id', 'purchase_line_id.order_currency_id')
    def _currency_id(self):
        if self.purchase_line_id and self.purchase_line_id.order_currency_id:
            self.currency_id = self.purchase_line_id.order_currency_id.id
    
    currency_id = fields.Many2one('res.currency', string='Moneda', compute="_currency_id", readonly=True, store=True)
    
class purchase_order_line(osv.osv):
    _inherit = "purchase.order.line"

    def _amount_line(self, cr, uid, ids, prop, arg, context=None):
        res = {}
        cur_obj=self.pool.get('res.currency')
        tax_obj = self.pool.get('account.tax')
        for line in self.browse(cr, uid, ids, context=context):
            line_price = self._calc_line_base_price(cr, uid, line,
                                                    context=context)
            line_qty = self._calc_line_quantity(cr, uid, line,
                                                context=context)
            taxes = tax_obj.compute_all(cr, uid, line.taxes_id, line_price,
                                        line_qty, line.product_id,
                                        line.order_id.partner_id)
            cur = line.order_id.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, taxes['total'])
        return res
        
    _columns = {
        'local_currency_id': fields2.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Moneda Local", readonly=True),
        'discount': fields2.float('Descuento (%)', digits_compute= dp.get_precision('Discount'), states={'draft':[('readonly',False)]}),
        'order_currency_id': fields2.related('order_id', 'currency_id', type="many2one", relation="res.currency", string="Moneda", readonly=True, store=True),
        'product_id': fields2.many2one('product.product', 'Product', domain=[('purchase_ok','=',True)], change_default=True, required=True),
        'price_subtotal': fields2.function(_amount_line, string='Subtotal', digits_compute= dp.get_precision('Account'), store=True),
    }
    
    def onchange_product_id(self, cr, uid, ids, pricelist_id, product_id, qty, uom_id, partner_id, date_order=False, fiscal_position_id=False, date_planned=False,
                            name=False, price_unit=False, state='draft', context=None):

        obj_partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context)
        obj_partner_list = obj_partner.property_product_pricelist_purchase
        if obj_partner_list.name != "Lista de Precios de Compra por Defecto" and obj_partner_list.active:
            ldp = obj_partner_list.version_id[-1]
            if ldp.active and product_id:
                cr.execute('''SELECT price_surcharge FROM product_pricelist_item where product_id = %s and price_version_id = %s''', (product_id,ldp.id))
                try:
                    price_unit = cr.fetchone()[0]
                except:
                    price_unit = False
        res = super(purchase_order_line, self).onchange_product_id(cr, uid, ids, pricelist_id, product_id, qty, uom_id, partner_id, date_order=date_order, fiscal_position_id=fiscal_position_id, date_planned=date_planned,
                    name=name, price_unit=price_unit, state='draft', context=context)
        if product_id:
            cr.execute('''SELECT id FROM account_analytic_default WHERE product_id = %s AND user_id = %s LIMIT 1''', (product_id,uid))
            try:
                analytic_id = cr.fetchone()[0]
            except:
                analytic_id = False
            if analytic_id:
                res.get('value').update({'account_analytic_id': self.pool.get('account.analytic.default').browse(cr, uid, analytic_id, context=context).analytic_id.id})
        return res

class purchase_order(osv.osv):
    _inherit = "purchase.order"
    
    @api.one
    @api.depends('order_line', 'order_line.date_planned')
    def _date_planned(self):
        if self.order_line:
            date_max=self.order_line[0].date_planned
            date_min=self.order_line[0].date_planned
            for line in self.order_line:
                if line.date_planned > date:
                    date_min = line.date_planned
                else:
                    date_max = line.date_planned
            self.maximum_planned_date = date_max
            self.minimum_planned_date = date_min
    
    
    maximum_planned_date = fields.Date(string='Fecha Maxima', readonly=True, compute="_date_planned", store=True)
    minimum_planned_date = fields.Date(string='Fecha Minima', readonly=True, compute="_date_planned", store=True)
    
    date_order = fields.Datetime('Order Date', required=True, states={'confirmed':[('readonly',True)],
                                                                      'approved':[('readonly',True)],
                                                                      'done':[('readonly',True)]},
                                 select=True, help="Depicts the date where the Quotation should be validated and converted into a Purchase Order, by default it's the creation date.",
                                 copy=False)
    
    def valid_invoice_method(self, cr, uid, ids, context=None):
        for purchase in self.browse(cr, uid, ids, context=context):
            valid = True
            if purchase.invoice_method == 'picking':
                valid = False
                for line in purchase.order_line:
                    if line.product_id.type != 'service':
                        valid = True
                        break
            if not valid:
                raise osv.except_osv(_('Error!'), _('El metodo de facturacion seleccionado es basado en recepciones, pero no tiene ningun producto almacenable o consumible en esta compra'))
        return True
    
    def _prepare_inv_line(self, cr, uid, account_id, order_line, context=None):
        res = super(purchase_order, self)._prepare_inv_line(cr, uid, account_id, order_line, context=context)
        res.update({'order_line_id':order_line.id})
        if order_line and order_line.account_analytic_id and order_line.account_analytic_id.costo_gasto == 'costo':
            res['account_id'] = order_line.product_id.costo_account_property.id or order_line.product_id.categ_id.property_account_costos_categ.id
            if not res['account_id']:
                raise osv.except_osv(_('Error !'),_("La Cuenta de Costos no esta definida en el producto '%s' ni en su categoria") % (order_line.product.name,))
        return res
    
    def _map_account(self, cr, uid, po_line, context=None):
        fiscal_obj = self.pool.get('account.fiscal.position')
        acc_id = False
        if po_line.product_id:
            acc_id = po_line.product_id.property_account_expense.id
            if not acc_id:
                acc_id = po_line.product_id.categ_id.property_account_expense_categ.id
            if not acc_id:
                raise osv.except_osv(_('Error!'), _('Define expense account for this company: "%s" (id:%d).') % (po_line.product_id.name, po_line.product_id.id,))
        else:
            acc_id = property_obj.get(cr, uid, 'property_account_expense_categ', 'product.category').id
        fpos = po_line.order_id.fiscal_position or False
        acc_id = fiscal_obj.map_account(cr, uid, fpos, acc_id)
        
        return acc_id
    
    def wkf_confirm_order(self, cr, uid, ids, context=None):
        self.button_dummy(cr, uid, ids, context=context)
        res = super(purchase_order, self).wkf_confirm_order(cr, uid, ids, context=context)
        return res
