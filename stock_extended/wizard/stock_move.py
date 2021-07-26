# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp.osv import osv, fields as fields2
from lxml import etree


class product_category(models.Model):
    _inherit = "product.category"
     
    tolerancia_inferior_compras = fields.Integer(string='Parciales Compras', help="Ejemplo: se necesitan 100 unidades del producto A, si tengo tolerancia de 10, solo puedo recepcionar un minimo de 90 unidades del producto A", default=-1)
    tolerancia_superior_compras = fields.Integer(string='Adicional Compras', help="Ejemplo: se solicitaron 100 unidades del producto A, si tengo tolerancia de 10, solo puedo recepcionar un maximo de 110 unidades del producto A", default=-1)
    tolerancia_inferior_ventas = fields.Integer(string='Parciales Ventas', help="Ejemplo: se necesitan 100 unidades del producto A, si tengo tolerancia de 10, solo puedo recepcionar un minimo de 90 unidades del producto A", default=-1)
    tolerancia_superior_ventas = fields.Integer(string='Adicional Ventas', help="Ejemplo: se solicitaron 100 unidades del producto A, si tengo tolerancia de 10, solo puedo recepcionar un maximo de 110 unidades del producto A", default=-1)

class stock_transfer_details(models.TransientModel):
    _inherit = 'stock.transfer_details'

    div_b = fields.Boolean(string='Dividir Lineas', help='Marque esta casilla si quiere dividir lineas automaticamente', default=False)
    div_lineas = fields.Float(string='Cantidad', help='Escriba el numero de lineas en las que desea dividir el producto a recibir', default=1)
    p_line = fields.Float(string='Linea', help='Numero de la linea en la que se encuentra el producto (Primera linea de arriba hacia abajo correspondea 1)', default=1)

    @api.multi
    def div_line(self):
        if self.p_line != 0:
            if self.p_line > len(self.item_ids):
                raise osv.except_osv(_('Error !'), _("Elija correctamente el numero de la linea de producto"))
            p = int(self.p_line) - 1
            if self.div_lineas > 0:
                linea = self.item_ids[p]
                for l_p in linea:
                    if l_p.quantity >= self.div_lineas:
                        for n_l in range(0,int(self.div_lineas)):
                            if l_p.quantity > 1:
                                l_p.quantity = (l_p.quantity-1)
                                new_id = l_p.copy(context=self.env.context)
                                new_id.quantity = 1
                                new_id.packop_id = False
                                if not l_p.product_id.lot_sequence_id:
                                    raise osv.except_osv(_('Error !'), _("Para crear el lote automaticamente, debe configurar una secuencia de lote en el producto"))
                                new_id.lot_id = self.pool['stock.production.lot'].create(self._cr, self._uid, {'product_id':l_p.product_id.id}, self._context)
                                if l_p.quantity == 1:
                                    l_p.lot_id = self.pool['stock.production.lot'].create(self._cr, self._uid, {'product_id':l_p.product_id.id}, self._context)
                        if linea and linea[0]:
                            self.div_b = False
                            return linea[0].transfer_id.wizard_view()
                    else:
                        raise osv.except_osv( _('Error !'), _("La cantidad de producto %s es menor al numero deseado a dividir") % (l_p.product_id.name))
        else:
            raise osv.except_osv( _('Error !'), _("Por favor elija la linea del producto dividir"))

class stock_transfer_details_items(models.TransientModel):
    _inherit = 'stock.transfer_details_items'

    @api.multi
    def put_in_lot(self):
        newlot = None
        for packop in self:
            if not packop.lot_id:
                if not newlot:
                    if not packop.product_id.lot_sequence_id:
                        raise osv.except_osv(_('Error !'), _("Para crear el lote automaticamente, debe configurar una secuencia de lote en el producto"))
                    newlot = self.pool['stock.production.lot'].create(self._cr, self._uid, {'product_id':packop.product_id.id}, self._context)
                packop.lot_id = newlot
        if self and self[0]:
            return self[0].transfer_id.wizard_view()
    
    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self,vals):
        vals.update({'quantity_init': vals.get('quantity', 0.0)})
        res = super(stock_transfer_details_items, self).create(vals)
        return res
    
    @api.one
    @api.constrains('quantity')
    def _min_quantity(self):
        if self.sourceloc_id.usage == 'supplier' and self.destinationloc_id.usage == 'internal':
            tinfc = self.product_id.categ_id.tolerancia_inferior_compras
            if self.quantity <  self.quantity_init*(1 - float(tinfc)/100) and tinfc > 0.0 and tinfc <= 100:
                raise osv.except_osv(_('Error !'), _('La cantidad del producto "%s" que esta tratando de transferir es menor que el valor minimo de tolerancia configurado para ingresos de inventario') % (self.product_id.name,))
            tsupc = self.product_id.categ_id.tolerancia_superior_compras
            if self.quantity >  self.quantity_init*(1 + float(tsupc)/100) and tsupc > 0.0 and tsupc <= 100:
                raise osv.except_osv(_('Error !'), _('La cantidad del producto "%s" que esta tratando de transferir es mayor que el valor maximo de tolerancia configurado para ingresos de inventario') % (self.product_id.name,))
        elif self.sourceloc_id.usage == 'internal' and self.destinationloc_id.usage == 'customer':
            tinfv = self.product_id.categ_id.tolerancia_inferior_ventas
            if self.quantity <  self.quantity_init*(1 - float(tinfv)/100) and tinfv > 0.0 and tinfv <= 100:
                raise osv.except_osv(_('Error !'), _('La cantidad del producto "%s" que esta tratando de transferir es menor que el valor minimo de tolerancia configurado para salidas de inventario') % (self.product_id.name,))
            tsupv = self.product_id.categ_id.tolerancia_superior_ventas
            if self.quantity >  self.quantity_init*(1 + float(tsupv)/100) and tsupv > 0.0 and tsupv <= 100:
                raise osv.except_osv(_('Error !'), _('La cantidad del producto "%s" que esta tratando de transferir es mayor que el valor maximo de tolerancia configurado para salidas de inventario') % (self.product_id.name,))
    
    quantity_init = fields.Float(string='Cantidad Inicial')

class stock_move_scrap(osv.osv_memory):
    _inherit = "stock.move.scrap"
    
    move_id = fields.Many2one('stock.move', string='Move', readonly=True)
    
    
    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(stock_move_scrap, self).default_get(cr, uid, fields, context=context)
        move = self.pool.get('stock.move').browse(cr, uid, context['active_id'], context=context)
        if 'move_id' in fields:
            res.update({'move_id': move.id})
            if len(move.lot_ids) >= 1:
                res.update({'restrict_lot_id': move.lot_ids[0].id})
        return res
        
    def move_scrap(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        move_ids = context['active_ids']
        for data in self.browse(cr, uid, ids, context=context):
            if move_ids and move_ids[0]:
                move = move_obj.browse(cr, uid, move_ids[0], context=context)
            if data.product_qty < 0 or data.product_qty == 0 or data.product_qty > move.product_uom_qty:
                raise osv.except_osv(_('Error !'), _("La cantidad no puede ser menor o igual 0, ni mayor a la cantidad del movimiento."))
        res = super(stock_move_scrap, self).move_scrap(cr, uid, ids, context=context)
        for move in move_obj.browse(cr, uid, move_ids, context=context):
            #workaround
            if move.reserved_quant_ids:
                move_obj.do_unreserve(cr, uid, move.id, context=context)
                move_obj.action_assign(cr, uid, move.id, context=context)
        return res
    
class stock_invoice_onshipping(osv.osv_memory):
    _inherit = "stock.invoice.onshipping"

    def _get_invoice_type(self, cr, uid, context=None):
        print "pasa1"
        if context is None:
            context = {}
        res_ids = context and context.get('active_ids', [])
        pick_obj = self.pool.get('stock.picking')
        pickings = pick_obj.browse(cr, uid, res_ids, context=context)
        pick = pickings and pickings[0]
        usage = ''
        if pick.move_lines[0].location_id.usage == 'internal' and pick.move_lines[0].location_dest_id.usage == 'customer':
            usage = 'out_invoice'
        elif pick.move_lines[0].location_id.usage == 'customer' and pick.move_lines[0].location_dest_id.usage == 'internal':
            usage = 'out_refund'
        elif pick.move_lines[0].location_id.usage == 'supplier' and pick.move_lines[0].location_dest_id.usage == 'internal':
            usage = 'in_invoice'
        elif pick.move_lines[0].location_id.usage == 'internal' and pick.move_lines[0].location_dest_id.usage == 'supplier':
            usage = 'in_refund'
        else:
            raise osv.except_osv(_('Error !'), _("Los movimientos registrados en el picking,no concuerdan para generar facturacion de ninguno de los siguientes tipos - F. Venta, F. Compra, N. Credito, N. Debito."))
        return usage
    
    def _get_journal_type(self, cr, uid, context=None):
        print "pasa2"
        if context is None:
            context = {}
        res_ids = context and context.get('active_ids', [])
        pick_obj = self.pool.get('stock.picking')
        pickings = pick_obj.browse(cr, uid, res_ids, context=context)
        pick = pickings and pickings[0]
        usage = ''
        if pick.move_lines[0].location_id.usage == 'internal' and pick.move_lines[0].location_dest_id.usage == 'customer':
            usage = 'sale'
        elif pick.move_lines[0].location_id.usage == 'customer' and pick.move_lines[0].location_dest_id.usage == 'internal':
            usage = 'sale_refund'
        elif pick.move_lines[0].location_id.usage == 'supplier' and pick.move_lines[0].location_dest_id.usage == 'internal':
            usage = 'purchase'
        elif pick.move_lines[0].location_id.usage == 'internal' and pick.move_lines[0].location_dest_id.usage == 'supplier':
            usage = 'purchase_refund'
        else:
            raise osv.except_osv(_('Error !'), _("Los movimientos registrados en el picking,no concuerdan para generar facturacion de ninguno de los siguientes tipos - F. Venta, F. Compra, N. Credito, N. Debito."))
        return usage
    
    
    def _get_partner(self, cr, uid, context=None):
        print "pasa3"
        if context is None:
            context = {}
        res_ids = context and context.get('active_ids', [])
        pick_obj = self.pool.get('stock.picking')
        pickings = pick_obj.browse(cr, uid, res_ids, context=context)
        pick = pickings and pickings[0]        
        return pick.partner_id.id
    
    _columns = {
        'invoice_id': fields2.many2one('account.invoice', 'Factura'),
        'invoice_type': fields2.selection([('out_invoice', 'Venta'), ('out_refund', 'N. Credito'),('in_invoice', 'Compra'), ('in_refund', 'N. Debito')], 'Tipo Factura', readonly=True),
        'partner_id': fields2.many2one('res.partner', 'Tercero', readonly=True),
        'journal_type': fields2.selection([('sale', 'Venta'), ('sale_refund', 'N. Credito'),('purchase', 'Compra'), ('purchase_refund', 'N. Debito')], 'Tipo Diario', readonly=True),
    }
        
    _defaults = {
        'invoice_type': _get_invoice_type,
        'journal_type': _get_journal_type,
        'partner_id': _get_partner,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        res = super(stock_invoice_onshipping, self).fields_view_get(cr, uid, view_id, view_type, context=context,
                                                                    toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='invoice_id']"):
                invoice_type = self._get_invoice_type(cr, uid, context=context)
                partnet_id = self.pool.get('res.partner').browse(cr, uid, self._get_partner(cr, uid, context=context))
                partner_ids = [partnet_id.id]
                if partnet_id.type == 'delivery':
                    partner_ids += partnet_id.parent_id.child_ids.filtered(lambda x: x.type == 'invoice').ids
                node.set('domain', str([('state', '=', 'draft'), ('partner_id', 'in', partner_ids),
                                        ('type', '=', invoice_type)]))
                res['arch'] = etree.tostring(doc)
        return res


    def open_invoice(self, cr, uid, ids, context=None):
        ctx = context.copy()
        for stock_invoice in self.browse(cr, uid, ids, context=ctx):
            if stock_invoice.group and stock_invoice.invoice_id:
                ctx.update({'invoice_id': stock_invoice.invoice_id})
        res = super(stock_invoice_onshipping, self).open_invoice(cr, uid, ids, context=ctx)
        return res

    def create_invoice(self, cr, uid, ids, context=None):
        print "pasa5"
        context = dict(context or {})
        move_pool = self.pool.get('stock.move')
        picking_pool = self.pool.get('stock.picking')
        invoice_line_pool = self.pool.get('account.invoice.line')
        invoice_pool = self.pool.get('account.invoice')
        data = self.browse(cr, uid, ids[0], context=context)
        journal2type = {'sale':'out_invoice', 'purchase':'in_invoice', 'sale_refund':'out_refund', 'purchase_refund':'in_refund'}
        context['date_inv'] = data.invoice_date
        inv_type = journal2type.get(data.journal_type) or 'out_invoice'
        context['inv_type'] = inv_type
        active_ids = context.get('active_ids', [])
        invoice = context.get('invoice_id',False)
        account_id = False
        if invoice and data.group and active_ids:
            context['group'] = True
            pickings = picking_pool.browse(cr, uid, active_ids, context=context)
            pick = pickings and pickings[0]
            ptype = ['product', 'consu', 'service']
            for move in pick.move_lines:
                product = move.product_id
                if product.type == ptype[0] and not product.is_asset:
                    account_id = invoice.partner_id.accrued_account_payable_id.id
                    if not account_id:
                        raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta puente del Proveedor '%s'"  % invoice.partner_id.name))
                elif product.type == ptype[1] or product.type == ptype[2]:
                    account_id = product.property_account_expense.id or product.categ_id.property_account_expense_categ.id
                    if not account_id:
                        raise osv.except_osv(_('Configuracion!'), _("Debe configurar la Cuenta de Gastos para el producto '%s' o para su categoria"  % product.name))
                elif product.is_asset:
                    account_id = product.aseet_category_id.account_asset_id.id
                    if not account_id:
                        raise osv.except_osv(_('Configuracion!'), _("Debe configurar la cuenta de activo fijo, de la Categoria de activo, para el producto '%s'"  % product.name))

                data = {
                    'name': product.display_name,
                    'invoice_id': invoice.id,
                    'product_id': product.id,
                    'uos_id': move.product_uos.id or move.product_uom.id,
                    'quantity': move.product_uom_qty,
                    'price_unit': move.price_unit,
                    'account_id': account_id,
                    'invoice_line_tax_id': [(6, 0, move_pool._get_taxes_invoice(cr, uid, move, invoice.type,
                                                                                context=context))],
                    'ciiu_id': invoice.partner_id.ciiu_id.id,
                    'city_id': invoice.partner_id.city_id.id,
                    'account_analytic_id': move.purchase_line_id.account_analytic_id.id,
                    'asset_category_id': product.aseet_category_id.id,
                    'discount': move.purchase_line_id.discount
                    }
                line = invoice_line_pool.create(cr, uid, data, context=context)
                move_pool.write(cr, uid, [move.id], {'invoice_line_id': line},context=context)
            res = [invoice.id]
            picking_pool.write(cr, uid, active_ids, {'invoice_state': 'invoiced', 'picking_invoice_id': invoice.id},
                               context=context)
            invoice_pool.write(cr, uid, [invoice.id], {'ref1': invoice.origin+ '-' + pick.name}, context=context)
        else:
            res = picking_pool.action_invoice_create(cr, uid, active_ids, journal_id=data.journal_id.id,
                                                     group=data.group, type=inv_type, context=context)
            picking_pool.write(cr, uid, active_ids, {'picking_invoice_id': res[0]}, context=context)
        return res
    
    
class account_invoice(models.Model):
    _inherit = "account.invoice"
    
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if type(ids) == int:
            ids = [ids]
        if not len(ids):
            return []
        list=[]
        group =context.get('group',False)
        group_out = context.get('group_out',False)
        result = super(account_invoice,self).name_get(cr, user, ids, context=context)
        if group and result:
            for val in result:
                i=self.browse(cr,user,val[0],context=context)
                origin = str(i.origin)+' // '+ str(i.supplier_invoice)
                val = (val[0],origin+' // $'+str(i.amount_total))
                list.append(val)
            result = list  
        
        if group_out and result:
            for val in result:
                i=self.browse(cr,user,val[0],context=context)
                origin = str(i.origin)+' // '+ str(i.date_invoice or i.create_date)
                val = (val[0],origin+' // $'+str(i.amount_total))
                list.append(val)
            result = list  
            
        
        return result
    
#





