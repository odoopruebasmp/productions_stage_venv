# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2013 Avancys SAS
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import osv, fields
from openerp import models, api, _
from openerp import fields as fields2
import openerp.addons.decimal_precision as dp

class product_product(osv.osv):
    _inherit = "product.template"

    _columns = {
        'is_asset': fields.boolean('Es un activo', help="Especifica si el producto puede ser un activo"),
        'aseet_category_id': fields.many2one('account.asset.category','Categoria de activo'),
    }

class account_invoice_line(osv.osv):    
    _inherit = 'account.invoice.line'
        
    @api.multi
    def product_id_change(self, product, uom_id, qty=0, name='', type='out_invoice', partner_id=False,
                          fposition_id=False, price_unit=False, currency_id=False, company_id=None,
                          account_analytic_id=False):
        res = super(account_invoice_line, self).product_id_change(product, uom_id, qty=qty, name=name, type=type,
            partner_id=partner_id, fposition_id=fposition_id, price_unit=price_unit, currency_id=currency_id,
            company_id=company_id, account_analytic_id=account_analytic_id)
        if product and type == 'in_invoice':
            part = self.env['res.partner'].browse(partner_id)
            if part and part.lang:
                self = self.with_context(lang=part.lang)
            product_data = self.env['product.product'].browse(product)
            category = product_data.aseet_category_id and product_data.aseet_category_id.id or False
            res.get('value', {}).update({'asset_category_id':category })
        return res

    def asset_create(self, cr, uid, lines, context=None):
        context = context or {}
        asset_obj = self.pool.get('account.asset.asset')
        for line in lines:
            if line.asset_category_id and line.product_id:
                if not line.stock_move_ids:
                    super(account_invoice_line, self).asset_create(cr, uid, [line], context)                    
                else:
                    for move in line.stock_move_ids:
                        purchase_asset=False
                        try:
                            if move.purchase_asset == 'inventary':
                                purchase_asset=True
                        except:
                            pass
                        if not purchase_asset:
                            for operation_link in move.linked_move_operation_ids:
                                operation = operation_link.operation_id
                                if operation.lot_id:
                                    asset_ids = asset_obj.search(cr, uid, [('category_id','=', line.asset_category_id.id),('product_id', '=', line.product_id.id), ('prodlot_id', '=', operation.lot_id.id)])
                                    if asset_ids:
                                        continue
                                    else:
                                        vals = {
                                            'name': line.name,
                                            'code': line.invoice_id.number or False,
                                            'category_id': line.asset_category_id.id,
                                            'purchase_value': line.price_unit*operation.product_qty,
                                            'period_id': line.invoice_id.period_id.id,
                                            'partner_id': line.invoice_id.partner_id.id,
                                            'product_id': line.product_id.id,
                                            'prodlot_id': operation.lot_id.id,
                                            'company_id': line.invoice_id.company_id.id,
                                            'currency_id': line.invoice_id.currency_id.id,
                                            'purchase_date' : line.invoice_id.date_invoice,
                                            'centrocosto_id' : line.account_analytic_id.id,
                                            'tax_ids': [(6, 0, [tax.id for tax in line.invoice_line_tax_id if tax.en_activo])],
                                        }
                                        
                                        #onchange in 7.0 workaround for compatibility with colombian localization
                                        try:
                                            changed_vals = asset_obj.onchange_category_id(cr, uid, [], vals['category_id'], context=context)
                                        except:
                                            changed_vals = asset_obj.onchange_category_id(cr, uid, [], vals['category_id'], vals['purchase_value'], 0, vals['tax_ids'], vals['company_id'], vals['purchase_date'], context=context)
                                        
                                        vals.update(changed_vals['value'])
                                        if not vals['centrocosto_id']:
                                            raise osv.except_osv(_('Advertencia!'),_("Asigne una cuenta analitica para la linea de factura con producto %s") % (line.product_id.name))
                                        # Restriccion para que no cree activos en devoluciones
                                        if line.invoice_id.type == 'in_invoice':
                                            asset_id = asset_obj.create(cr, uid, vals, context=context)
                                            if line.asset_category_id.open_asset:
                                                asset_obj.validate(cr, uid, [asset_id], context=context)
        return True

account_invoice_line()

class account_asset_asset(osv.osv):
    _inherit = 'account.asset.asset'

    def _amount_all(self, cr, uid, ids, name, args, context=None):
        res = {}
        for asset in self.browse(cr, uid, ids, context=context):
            asset_ids = self.search(cr, uid, [('parent_id', '=', asset.id),('state', '=', 'open')], context=context)
            total_values = 0.0
            if asset_ids:
                for child_asset in self.browse(cr, uid, asset_ids, context=context):
                    total_values += child_asset.asset_value
            else:
                total_values = asset.asset_value
            res[asset.id] = total_values
        return res
    
    _columns = {
        'product_id': fields.many2one('product.product','Product',required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'asset_type': fields.selection((('deferred', 'Deferred'), ('fixed', 'Fixed'), ('intangible','Intangible')), 'Asset Type', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'prodlot_id': fields.many2one('stock.production.lot','Serial Number',required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'total_value': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Total Value', type="float"),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Running'), ('close', 'Close')], 'Status',
                                  required=True, copy=False, track_visibility="onchange")
    }
    
    _sql_constraints = [('lot_uniq', 'unique(prodlot_id)', 'Ya existe un activo con el serial seleccionado'), ]


class stock_picking(osv.osv):
    _inherit = "stock.picking"

    _columns = {
        'aseet_category_id': fields.many2one('account.asset.category','Asset Category'),
    }

    def _prepare_invoice_line(self, cr, uid, group, picking, move_line, invoice_id, invoice_vals, context=None):
        result = super(stock_picking, self)._prepare_invoice_line(cr, uid, group, picking, move_line, invoice_id, invoice_vals, context)
        result.update({'asset_category_id': move_line.product_id and move_line.product_id.aseet_category_id and move_line.product_id.aseet_category_id.id or False})
        return result


class stock_production_lot(osv.osv):
    _inherit = 'stock.production.lot'

    def _last_assigned(self, cr, uid, ids, context=None):
        result = {}
        for assign in self.pool.get('stock.production.lot.user.assigned').browse(cr, uid, ids, context=context):
            if assign.production_lot_id:
                result[assign.production_lot_id.id] = True
        return result.keys()

    _columns = {
        'assignment_ids':fields.one2many('stock.production.lot.user.assigned','production_lot_id',' Assigned User'),
        'last_assigned' : fields.related('assignment_ids', 'user_id', relation ='res.users', string = 'Last Assigned Person', type='many2one',
                    store ={
                    'stock.production.lot': (lambda self, cr, uid, ids, c={}: ids, [], 10),
                    'stock.production.lot.user.assigned': (_last_assigned, ['user_id', 'date'], 10),
                    }),
    }

class user_assigned(osv.osv):
    _name = 'stock.production.lot.user.assigned'
    _order = 'date desc'
    _rec_name = "date"

    _columns = {
        'production_lot_id':fields.many2one('stock.production.lot','Production Lot'),
        'user_id':fields.many2one('res.users','User', required=True),
        'date':fields.datetime('Assigned Date', required=True),
    }


class purchase_order(osv.osv):
    _inherit = "purchase.order"

    def _prepare_inv_line(self, cr, uid, account_id, order_line, context=None):
        result = super(purchase_order, self)._prepare_inv_line(cr, uid, account_id, order_line, context)
        result.update({'asset_category_id': order_line.product_id and order_line.product_id.aseet_category_id and order_line.product_id.aseet_category_id.id or False})
        return result


class asset_depreciation_confirmation_wizard(models.TransientModel):
    _inherit = 'asset.depreciation.confirmation.wizard'

    def asset_compute(self, cr, uid, ids, context):
        ctx = context.copy()
        ctx.update({'activos_fijos': True})
        res = super(asset_depreciation_confirmation_wizard, self).asset_compute(cr, uid, ids, context=ctx)
        return res
