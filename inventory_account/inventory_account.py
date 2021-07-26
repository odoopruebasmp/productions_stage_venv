# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2011 Serpent Consulting Services (<http://serpentcs.com>).
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
from openerp.tools.translate import _
import openerp.netsvc
from openerp import SUPERUSER_ID, api, models
from openerp import fields as fields2
from datetime import datetime, timedelta
import openerp.addons.decimal_precision as dp
from openerp.addons.avancys_orm import avancys_orm
from openerp.exceptions import Warning


class res_company(models.Model):
    _inherit = "res.company"
    
    invoice_import = fields2.Boolean(string='Factura en Importaciones', help="POLITICA A NIVEL DE COMPANIA, AFECTA EL PROCESO DE RECPECION DE UNA ORDEN DE COMPRA QUE TIENE ASOCIADA UNA IMPORTACION, PARA LO CUAL ELSISTEMA REQUIERE GENERAR PRIMERO LA FACTURA DE COMPRA ANTES DE PERMITIR RECEPCIONAR LOS PRODUCTOS.")
    sale_cost_invoice = fields2.Boolean(string='Costo de venta en facturacion', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE REMISION DE VENTA Y RECEPCION EN DEVOLUCION DE VENTA. El sistema por defecto, realiza el movimiento del costo de venta en la remision de una venta o en la recepcion de una devolucion de venta, SI SE MARCA ESTA OPCION, el sistema realizara este apunte contable en la facturacion o la generacion de la nota credito. Esto quiere decir que: en la remision o recepcion de devoluciones de venta solo afectara el inventario en unidades y que en la facturacion o nota credito, afectara ademas de los ingresos, cuenta por cobrar e impuestos, el costo de venta y el inventario a modo contable.")
    automatic_invoice = fields2.Boolean(string='Facturacion Automatica', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE REMISION DE VENTA. El sistema por defecto, realiza el proceso en dos partes, remision y generacion de factura. SI SE MARCA ESTA OPCION, el sistema realizara estos dos procesos en un solo paso, generando la transferencia del inventario y generarando la factura en estado borrador, lista para revision")
    automatic_reserve = fields2.Boolean(string='Reserva Automatica', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE CONFIRMACION DE VENTA. El sistema por defecto, realiza el proceso en dos partes, confirmacion de pedido de venta y comprobacion de disponibilidad (reserva). SI SE MARCA ESTA OPCION, el sistema realizara estos dos procesos en un solo paso, generando la remision de salida y reservando la mercancia de forma automatica.")
    automatic_valid = fields2.Boolean(string='Validacion Automatica', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE VALIDACION DE FACTURA DE VENTA. El sistema por defecto, realiza el proceso en dos partes, creacion de la factura de venta y validacion de la misma. SI SE MARCA ESTA OPCION, el sistema realizara la validacion de forma automatica.")
    move_date_invoice = fields2.Boolean(string='Fecha de remision igual a la factura', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE REMISION Y FACTURACION. El sistema por defecto selecciona como fecha del movimiento de inventario, la fecha de la transferencia. SI SE MARCA ESTA OPCION, el sistema modificara la fecha del movimeinto de inventario y su equivalente contable, a la fecha de la factura.")
    uom_uos_invoice = fields2.Boolean(string='Unidad de Factura de Proveedor', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE FACTURADE PROVEEDOR.")
    invoice_lot = fields2.Boolean(string='Factura de Venta con Serial/Lote', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE FACTURADE VENTA, DONDE EL SISTEMA CONSULTA LOS LOTES QUE SE UTILIZARON EN LA REMISION Y LA FECHA DE FABRICACION DE LOS MISMOS, Y LOS AGREGA A LA LINEA DE FACTURA PARA PODER SER IMPRESOS EN LA FACTURA")
    analytic_default = fields2.Boolean(string='C. Analitica Ventas', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE REMISION Y FACTURA DE VENTA, DONDE EL SISTEMA CONSULTA LOS VALORES ANALITICOS POR DEFECTO, TENIENDO EN CUENTA EL USUARIO Y EL PRODUCTO, Y ASIGNA LA CUENTA ANALITICA AL COSTO DE VENTA Y EL INGRESO")
    line_for_sale = fields2.Boolean(string='Linea de factura/Linea de Venta', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE REMISION Y FACTURA DE VENTA, DONDE EL SISTEMA TIENE EN CUENTA COMO CRITERIO DE AGRUPACION DE LA FACTURA DE VENTA, EL SALE_ORDER.")
    restriction_cost_zero = fields2.Boolean(string='Restriccion Costo Cero', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO LOGISTICO, DONDE EL SISTEMA NO PERMITE REALIZAR MOVIMEINTOS DE INVENTARIO DE PRODUCTOS ALMACENABLES CON COSTO CERO")
    purchase_asset = fields2.Boolean(string='Almacenables como Activos', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO LOGISTICO Y CONTABLE, PERMITE GESTIONAR PRODUCTOS DE INVENTARIO Y ACTIVOS FIJOS BAJO UNA MISMA REFERENCIA.")
    negative_qty = fields2.Boolean(string='Cantidades Negativas', help="POLITICA A NIVEL DE COMPANIA, AFECTACIÓN EN EL "
                                    "PROCESO LOGISTICO Y CONTABLE, PERMITE MOVIMIENTOS DE CANTIDADES NEGATIVAS EN EL "
                                    "SISTEMA, SIEMPRE Y CUANDO LA UBICACIÓN ORIGEN SEA DE TIPO INTERNO - POLÍTICA "
                                    "RECOMENDADA ÚNICAMENTE EN BASES DE DATOS DESTINADAS A PUNTO DE VENTA.")
    
    @api.multi
    def write(self, vals):
        if self._uid not in (1, 196):
            raise osv.except_osv(_('Error !'), _('No esta autorizado para realizar modificaciones de la compania, consultar con el area encargada'))
        res = super(res_company, self).write(vals)
        return res
    

class sale_order(models.Model):
    _inherit = 'sale.order'
    
    # Esta funcion permite generar las reservas de forma automatica y disminuir los tiempos para la operacion logistica "company_id.automatic_reserve"
    def action_ship_create(self, cr, uid, ids, context=None):
        super(sale_order, self).action_ship_create(cr, uid, ids, context=context)
        picking_obj=self.pool.get('stock.picking')
        for sale in self.browse(cr, uid, ids, context=context):
            if sale.company_id and sale.company_id.automatic_reserve:
                stock_picking_ids = picking_obj.search(cr, uid, [('group_id', '=', sale.procurement_group_id.id),('state', '!=', 'cancel')], context=context)
                picking_obj.action_assign(cr, uid, stock_picking_ids, context=context)
        return True

class res_partner(osv.osv):
    _inherit = 'res.partner'

    _columns = {
        'accrued_account_payable_id': fields.property(type='many2one', relation='account.account', string="Cuenta Puente Recepcion",  help="", required=False),
    }

res_partner()

class product_category(models.Model):
    _inherit = "product.category"

    cogs_account_id=fields2.Many2one('account.account',string="Costo de Venta",  company_dependent=True, domain="[('type','!=','view')]")
    transit_accout_id=fields2.Many2one('account.account',string="Cuenta de Transito",  company_dependent=True, domain="[('type','!=','view')]")
    account_production_transit_id=fields2.Many2one('account.account', company_dependent=True, string="Cuenta Producto en Proceso", domain="[('type','!=','view')]")
    account_production_analytic_id=fields2.Many2one('account.analytic.account', company_dependent=True, string="Cuenta Analitica Produccion", domain="[('type','!=','view')]")
    journal_production_id = fields2.Many2one('account.journal', company_dependent=True, string='Diario Producto Proceso')
    

class product_template(models.Model):
    _inherit = "product.template"

    cogs_account_id=fields2.Many2one('account.account',string="Cogs Account", company_dependent=True, domain="[('type','!=','view')]")
    transit_accout_id=fields2.Many2one('account.account',string="Cuenta de Transito", company_dependent=True, domain="[('type','!=','view')]")


class product_product(models.Model):
    _inherit = "product.product"

    cost_purchase=fields2.Float(string="Costo", readonly=True)
    date_purchase=fields2.Date(string="Fecha", readonly=True)
    qty_purchase=fields2.Float(string="Cantidad", readonly=True)
    document_purchase=fields2.Char(string="Origen Compra", readonly=True)
    document_sale=fields2.Char(string="Origen Venta", readonly=True)
    partner_purchase=fields2.Many2one('res.partner', string="Proveedor", readonly=True)
    price_sale=fields2.Float(string="Precio", readonly=True)
    date_sale=fields2.Date(string="Fecha", readonly=True)
    qty_sale=fields2.Float(string="Cantidad", readonly=True)
    partner_sale=fields2.Many2one('res.partner', string="Cliente", readonly=True)
    costo_standard=fields2.Float(string="Costo standard", digits=dp.get_precision('Account'))
    costo_variation=fields2.Integer(string="Variacion Costo")
    costo_zero=fields2.Boolean(string="Costo Cero")
    fabricante_id=fields2.Many2one('res.partner', string="Fabricante", readonly=True) 

    # SE AGREGA ESTA FUNCION PARA EVITAR EL CAMBIO DEL PUERTO DE LOS REPORTES QWEB
    @api.multi
    def write(self, vals):
        if vals.get('standard_price'):
            costo_zero = 'False'
            if self.costo_zero:
                costo_zero='True'
            cost=self.standard_price
            cost_str=str(cost)
            cost_new=vals.get('standard_price')
            cost_new_str=str(cost_new)
            if cost_new < 0.0:
                raise osv.except_osv(_('Error !'), _("No es posible asignar un costo menor a cero para el producto '%s'") % (self.display_name))
            elif self.costo_variation > 0.0 and  self.costo_variation < 100 and abs(cost_new - cost) >self.costo_variation*cost/100 and cost != 0.0:
                raise osv.except_osv(_('Error !'), _("El producto '%s' cuenta con un CONTROL DE COSTO PROMEDIO. Se tiene un costo promedio de %s y lo desea actualizar a %s, donde el procentaje de tolerancia es '%s'. Por favor consulte con el area encargada.") % (self.display_name, cost, cost_new, self.costo_variation))
            user_id=self.env['res.users'].browse(self._uid)
            body ='<html><body>'             
            body+='<br/>'
            body+="""<table border="1" style="width: 500px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat;">"""              
            body+='<tr>'
            body+='<th colspan="4" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">CONTROL DE CAMBIOS DEL COSTO PROMEDIO</th>'
            body+='</tr>'
            body+='<tr>'
            body+='<td style="font-size: 10px; color: #222;"><strong>Fecha:</strong></td><th><span style="font-size: 8px; color: #222;">'+str(datetime.now()-timedelta(hours=5))+'</span></th>'
            body+='<td style="font-size: 10px; color: #222;"><strong>Responsable:</strong></td><th><span style="font-size: 8px; color: #222;">'+user_id.name+'</span></th>'
            body+='</tr>'
            body+='<tr>'
            body+='<td style="font-size: 10px; color: #222;"><strong>Costo Cero:</strong></td><th><span style="font-size: 8px; color: #222;">'+costo_zero+'</span></th>'
            body+='<td style="font-size: 10px; color: #222;"><strong>Variacion:</strong></td><th><span style="font-size: 8px; color: #222;">'+str(self.costo_variation)+'</span></th>'
            body+='</tr>'
            body+='<tr>'
            body+='<td style="font-size: 10px; color: #222;"><strong>Costo Anterior:</strong></td><th><span style="font-size: 12px; color: #222;">'+cost_str+'</span></th>'
            body+='<td style="font-size: 10px; color: #222;"><strong>Costo Nuevo:</strong></td><th><span style="font-size: 12px; color: #222;">'+cost_new_str+'</span></th>'            
            body+='</tr>'            
            body+='</table>'
            body +='</body></html>'
            self._cr.execute('''INSERT INTO mail_message (subject, model, author_id, res_id, date, type, body) VALUES
                (%s,%s,%s,%s,%s,%s,%s)''' , ('Actualizacion de Costo Promedio', 'product.product', user_id.partner_id.id, self.id, datetime.now(), 'notification', body))
        res = super(product_product, self).write(vals)
        return res
    
    
class stock_picking_type(models.Model):
    _inherit = "stock.picking.type"

    journal_id=fields2.Many2one('account.journal', string="Diario Movimiento de almacen", domain="[('stock_journal','=', True)]")
    journal_invoice_id=fields2.Many2one('account.journal', string="Diario de Facturacion", domain="[('type','=', 'sale')]")
    journal_return_invoice_id=fields2.Many2one('account.journal', string="Diario Devolucion Facturacion", domain="[('type','=', 'sale_refund')]")


class stock_change_product_qty(models.TransientModel):
    _inherit = "stock.change.product.qty"
    
    def default_get(self, cr, uid, fields, context):
        if uid != 1:
            raise osv.except_osv(_('Error !'), _("No tiene autorizacion para realizar este tipo de ajustes de inventario, por favor debe gestionar el movimiento con el departamento Logistica o Abastecimiento"))
        res = super(stock_change_product_qty, self).default_get(cr, uid, fields, context=context)
        return res
    
    
class stock_location(osv.osv):
    _inherit = "stock.location"

    _columns = {
        'account_location_id': fields.property(type='many2one', relation='account.account', string="Account Location",  required=False),
    }

stock_location()

class account_move_line(osv.osv):
    _inherit = "account.move.line"
    _columns = {
        'stock_move_id': fields.many2one('stock.move', 'Stock Move'),
        'stock_picking_id': fields.many2one('stock.picking', 'Stock Picking'),
    }

account_move_line()


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _create_invoice_from_picking(self, cr, uid, picking, vals, context=None):
        vals.update({'stock_picking_id': picking.id})
        res = super(StockPicking, self)._create_invoice_from_picking(cr, uid, picking, vals, context=context)
        return res

    @api.multi
    def _calc_invl_group(self, move_line, product, uos_id, account_analytic_id, discount, account_id, invoice, group,
                         quantity, stk_move_obj, code, spolicy, project_id=False):
        if not account_id:
            raise Warning("La cuenta de ingreso no esta definida en el producto '%s' ni en su categoria" %
                          product.name)
        lot_ids = ''
        if invoice.company_id.invoice_lot:
            dicc = {}
            for quant in move_line.quant_ids:
                if quant.lot_id:
                    key1 = quant.lot_id.id
                    if key1 in dicc:
                        dicc[key1].update({'qty': quant.qty + dicc[key1]['qty']})
                    else:
                        dicc[key1] = {
                            'Lote': quant.lot_id.name, 'qty': quant.qty,
                            'Fab': str(quant.lot_id.create_date[0:10])
                            }
            if dicc:
                for val in dicc:
                    lot_ids += '[(' + str(dicc[val]['qty']) + ') Lote:' + dicc[val]['Lote'] + \
                               '/(' + dicc[val]['Fab'] + ')] '
        key = (product.id, uos_id.id, account_analytic_id, discount)
        asset = False
        if spolicy:
            sale_order_line = move_line.sale_line_id and move_line.sale_line_id.id
            key += (sale_order_line,)
        else:
            if invoice.company_id.purchase_asset and invoice.type == 'in_invoice':
                if 'purchase_asset' in move_line._columns:
                    if move_line.purchase_asset == 'inventary':
                        asset = True
                key += (asset,)
        if key not in group:
            group[key] = {}
            group[key]['name'] = move_line.name
            group[key]['invoice_id'] = invoice.id
            group[key]['product_id'] = product.id
            group[key]['uos_id'] = uos_id.id
            group[key]['account_id'] = account_id
            group[key]['quantity'] = quantity
            group[key]['cost'] = move_line.cost
            if getattr(product, 'aseet_category_id', None):
                group[key]['asset_category_id'] = product.aseet_category_id.id
                if not spolicy and code == "incoming" and not asset:
                    group[key]['account_id'] = product.aseet_category_id and \
                                               product.aseet_category_id.account_asset_id and \
                                               product.aseet_category_id.account_asset_id.id
            group[key]['price_unit'] = stk_move_obj._get_price_unit_invoice(move_line, invoice.type)
            group[key]['discount'] = discount
            group[key]['invoice_line_tax_id'] = [(6, 0, stk_move_obj._get_taxes_invoice(move_line,
                                                                                        invoice.type))]
            group[key]['account_analytic_id'] = account_analytic_id
            #####
            group[key]['project_id'] = project_id
            #####
            group[key]['stock_move_ids'] = [move_line.id]
            group[key]['lot_ids'] = lot_ids
        else:
            group[key]['quantity'] += move_line.product_uom_qty
            group[key]['stock_move_ids'] += [move_line.id]
            group[key]['lot_ids'] += lot_ids
        return group

    account_move_id = fields2.Many2one('account.move', string='Comprobante Contable', readonly=True, copy=False)
    
    @api.multi
    def do_location_button(self):

        if self:
            if self.state == 'done':
                raise osv.except_osv(_('Error !'), _("El picking no puede estar transferido para ejecutar esta operación"))
            # Validaciones
            ptc = self.picking_type_id.code
            sl = self.source_location.usage
            dl = self.dest_location.usage
            pi = self.id

            if ptc == 'incoming':
                if sl and not sl == 'supplier':
                    raise osv.except_osv(_('Error !'), _("La ubicacion Origen seleccionada debe ser tipo Proveedor"))
                if dl and not dl == 'internal':
                    raise osv.except_osv(_('Error !'), _("La ubicacion Destino seleccionada debe ser tipo Interna"))
            elif ptc == 'outgoing':
                if sl and not sl == 'internal':
                    raise osv.except_osv(_('Error !'), _("La ubicacion Origen seleccionada debe ser tipo Interna"))
                if sl and not dl == 'customer':
                    raise osv.except_osv(_('Error !'), _("La ubicacion Destino seleccionada debe ser tipo Cliente"))
                for move in self.move_lines:
                    if move.reserved_quant_ids:
                        self._cr.execute(''' UPDATE stock_quant SET reservation_id=%s WHERE reservation_id = %s''', (move.id, move.id))
                self._cr.execute(''' UPDATE stock_picking SET state='confirmed' WHERE id = %s''', (pi,))
            elif ptc == 'internal':
                if sl and not sl == 'internal':
                    raise osv.except_osv(_('Error !'), _("La ubicacion Origen seleccionada debe ser tipo Interna"))
                if dl and not dl == 'internal':
                    raise osv.except_osv(_('Error !'), _("La ubicacion Destino seleccionada debe ser tipo Interna"))
                for move in self.move_lines:
                    if move.reserved_quant_ids:
                        self._cr.execute(''' UPDATE stock_quant SET reservation_id=%s WHERE reservation_id = %s''', (move.id, move.id))
                self._cr.execute(''' UPDATE stock_picking SET state='confirmed' WHERE id = %s''',(pi,))
            if sl:
                sl_id = self.source_location.id
                self._cr.execute('UPDATE stock_move SET location_id = {sli} WHERE picking_id = {pk}'.format(sli=sl_id, pk=self.id))
                self._cr.execute('UPDATE stock_pack_operation SET location_id = {sli} WHERE picking_id = {pk}'.format(sli=sl_id, pk=self.id))
            if dl:
                dl_id = self.dest_location.id
                self._cr.execute('UPDATE stock_move SET location_dest_id = {dli} WHERE picking_id = {pk}'.format(dli=dl_id, pk=self.id))
                self._cr.execute('UPDATE stock_pack_operation SET location_dest_id = {dli} WHERE picking_id = {pk}'.format(dli=dl_id, pk=self.id))
            
        return True

    @api.cr_uid_ids_context
    def do_transfer_button(self, cr, uid, picking_ids, bandera=False, context=None):
        move_line_in = []

        '''if bandera:
            pass
        else:
            if uid != 1:
                raise osv.except_osv(_('Error !'), _("El sistema no restringe esta operacion para el administrador del sistema, por favor consulte con su ADMINISTRADOR."))'''

        if context is None:
            context = {}
        else:
            context = dict(context)
        move_obj = self.pool.get('stock.move')
        currency_obj = self.pool.get('res.currency')
        tax_obj = self.pool.get('account.tax')
        period_obj = self.pool.get('account.period')
        account_move_obj = self.pool.get('account.move')
        account_default_obj = self.pool.get('account.analytic.default')
        account_analytic_id=False

        for pick in self.browse(cr, uid, picking_ids, context=context):
            if pick.account_move_id:
                cr.execute(''' DELETE FROM account_move WHERE id = %s''',(pick.account_move_id.id,))
            if pick.state != 'done':
                raise osv.except_osv(_('Error !'), _("El picking debe estar transferido para generar su equivalente contable")) 
            company_id = pick.company_id.id
            picking_date = pick.date_done or datetime.now().date()
            refund = False
            if pick.picking_type_id.code != "internal":
                # Validacion del tercero
                if pick.partner_id and pick.partner_id.parent_id:
                    partner_id = pick.partner_id.parent_id
                elif pick.partner_id:
                    partner_id =pick.partner_id
                else:
                    raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con un tercero asociado al movimiento de inventario %s" % pick.name))

                # Validacion del Diario
                journal_id = pick.picking_type_id.journal_id or False
                if not journal_id:
                    raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con un diario, configurado en el tipo de operacion %s"  % pick.picking_type_id.name))

                # Validacion del periodo
                period_id = period_obj.search(cr, uid, [('state','=','draft'),('date_start','<=',picking_date),('date_stop','>=',picking_date)], limit=1,context=context)
                if period_id:
                    period_id = period_id[0]
                elif pick.picking_type_id.code != "internal":
                    raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con un periodo contable abierto para este tipo de transferencia para la fecha %s"  % picking_date))
            for move in pick.move_lines:
                product_data = move.product_id
                product_qty = move.product_qty
                price_unit = move.price_unit
                product_uom_qty = move.product_uom_qty
                cost = move.cost

                try:
                    asset = product_data.is_asset
                except:
                    asset = False
                    

                if (move.location_id.usage != "internal" or move.location_dest_id.usage != "internal") and move.product_id.type == "product" and move.state != "cancel" and not asset:
                    if move.location_id.usage == "supplier" and move.location_dest_id.usage == "internal":#COMPRAS
                        if pick.picking_type_id.code != "incoming":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))
                        account_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ.id
                        if not account_id:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con una cuenta de entrada de almacen. Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % product_data.name, product_data.categ_id.name))
                        tax_mayor_valor = []
                        impuestos_mayor_valor = {}

                        if self.pool.get('ir.module.module').search(cr, uid, [('name','=','stock_picking_dotacion'),
                                                                              ('state','=','installed')], context=context):
                            refund = move.picking_id.is_refund

                        if move.purchase_line_id:
                            try:
                                fabricante_id = move.purchase_line_id.fabricante_id and move.purchase_line_id.fabricante_id.id or False
                            except:
                                fabricante_id = move.purchase_line_id.partner_id and move.purchase_line_id.partner_id.id or False

                            if fabricante_id:
                                cr.execute(''' UPDATE product_product SET  fabricante_id = %s WHERE id = %s''',(fabricante_id, product_data.id))

                            #  REQ-0000011300
                            if product_uom_qty != move.purchase_line_id.product_uom:
                                if move.purchase_line_id.product_uom.uom_type == 'bigger':
                                    product_qty /= move.purchase_line_id.product_uom.factor_inv
                                elif move.purchase_line_id.product_uom.uom_type == 'smaller':
                                    product_qty *= move.purchase_line_id.product_uom.factor_inv

                            if move.purchase_line_id.product_uom == move.product_id.uos_id and move.product_id.uos_id != move.product_id.uom_id:
                                product_qty = move.purchase_line_id.product_qty / move.product_id.uos_coeff
                                price_unit = move.purchase_line_id.price_unit * move.product_id.uos_coeff
                            for tax_check in move.purchase_line_id.taxes_id:
                                if tax_check.mayor_valor:
                                    tax_mayor_valor.append(tax_check)
                            if len(tax_mayor_valor) > 1:
                                raise osv.except_osv(_('Error !'), _("Hay mas de un impuesto de mayor valor para el producto '%s'") % (move.product_id.name))
                            for tax in tax_obj.compute_all(cr, uid, tax_mayor_valor, (move.purchase_line_id.price_unit* (1-(move.purchase_line_id.discount or 0.0)/100.0)), product_qty, product_data, partner_id)['taxes']:
                                impuestos_mayor_valor={'base_code_id':tax['base_code_id'],'tax_code_id':tax['tax_code_id'],'account_id':account_id, 'amount': tax['amount'], 'base': (move.purchase_line_id.price_unit*(1-(move.purchase_line_id.discount or 0.0)/100.0)*product_qty)}
                        else:
                            move_origin = move_obj.search(cr, uid, [('picking_id','=',move.picking_id.id),('id','!=',move.id),('product_id','=',move.product_id.id),('purchase_line_id','!=',False)], context=context)
                            if move_origin:
                                move_origin = move_obj.browse(cr, uid, move_origin, context=context)
                                cr.execute(''' UPDATE stock_move SET purchase_line_id=%s WHERE id = %s''',(move_origin.purchase_line_id.id, move.id))
                            else:
                                if not refund:
                                    raise osv.except_osv(_('Error !'), _("El producto '%s' con referencia interna '%s' no esta asociado a la orden de compra '%s'. Si desea incluirlo en la recepcion debe 1.Cancelar O.C. ---->   2.Regresar a borrador ---->   3.Modificar la O.C. ---->   4.Confirmar O.C.") % (move.product_id.name, move.product_id.default_code, pick.origin))

                        if tax_mayor_valor:
                            additional_cost = (cost*product_qty) - (price_unit*product_qty + impuestos_mayor_valor['amount'])
                            invoiced = price_unit*product_qty + impuestos_mayor_valor['amount']
                        else:
                            additional_cost = (cost-price_unit)*product_qty
                            invoiced = price_unit*product_qty

                        invoiced = currency_obj.round(cr, uid, move.local_currency_id, invoiced)
                        additional_cost = currency_obj.round(cr, uid, move.local_currency_id, additional_cost)
                        total_cost = invoiced+additional_cost                           

                        dr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': account_id,
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                            'partner_id': partner_id.id,
                            'credit': 0.0,
                            'debit': total_cost,
                            'date': picking_date,
                            'stock_picking_id': move.picking_id.id,
                            'tax_code_id': impuestos_mayor_valor.get('tax_code_id', False),
                            'tax_amount': impuestos_mayor_valor.get('amount', False), 
                            'base_code_id': impuestos_mayor_valor.get('base_code_id', False),
                            'base_amount': impuestos_mayor_valor.get('base', False), 
                        }
                        cr_move_val = dr_move_val.copy()
                        cuenta_puente = partner_id.accrued_account_payable_id.id
                        if not cuenta_puente:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con la parametrizacion de la cuenta puente de recepcion del tercero '%s', se sugiere una cuenta del pasivo 26."  % partner_id.name))
                        cr_move_val.update({
                            'account_id': cuenta_puente,
                            'debit': 0.0,
                            'credit': invoiced,
                            'tax_code_id': False,
                            'tax_amount': 0,
                            'base_code_id': False,
                            'base_amount': 0, 
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                        if not currency_obj.is_zero(cr, uid, move.local_currency_id, additional_cost):
                            if additional_cost < 0 :
                                n = product_data.name +' '+ (product_data.default_code or '')
                                raise osv.except_osv(_('Error !'), _("El costo del producto '%s' no puede ser menor al valor configurado, el costo es '%s' mientras el precio es '%s'")  % (n, cost, price_unit))
                            if additional_cost > 0:
                                cr_move_val2 = dr_move_val.copy()
                                transit_account = (product_data.transit_accout_id and product_data.transit_accout_id.id) or (product_data.categ_id.transit_accout_id and product_data.categ_id.transit_accout_id.id) or False
                                if not transit_account:
                                    raise osv.except_osv(_('Configuration !'), _("La cuenta de transito no esta definida en el producto '%s' ni en su categoria"  % product_data.name))
                                cr_move_val2.update({
                                    'account_id': transit_account,
                                    'debit': 0.0,
                                    'credit': additional_cost,
                                })
                                move_line_in.append(cr_move_val2)

                    elif move.location_id.usage == "customer" and move.location_dest_id.usage == "internal" and pick.picking_type_id.code != "return":#DEVOLUCION VENTAS 1
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            continue

                        if pick.picking_type_id.code != "incoming":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        account_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ.id
                        if not account_id:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con una cuenta de entrada de almacen. Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % product_data.name, product_data.categ_id.name))

                        account_move_return = (product_data.cogs_account_id and product_data.cogs_account_id.id) or (product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id) or False
                        if not account_move_return:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con una cuenta de costo de venta. Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % product_data.name, product_data.categ_id.name))

                        #COSTO PROMEDIO DEVOLUCIONES DE VENTA
                        standard_price=move.cost
                        total_cost = move.product_qty * standard_price
                        
                        # Contabilidad Analitica por default
                        if pick.company_id.analytic_default:
                            account_analytic_id = move.origin_returned_move_id and move.origin_returned_move_id.account_analytic_id and move.origin_returned_move_id.account_analytic_id.id
                            
                            if not account_analytic_id:
                                analytic_id = account_default_obj.search(cr, uid, [('product_id', '=', move.product_id.id),('user_id', '=', pick.create_uid and pick.create_uid.id or False)], context=context, limit=1)
                                if analytic_id:
                                    account_analytic_id=account_default_obj.browse(cr, uid, analytic_id[0], context=context).analytic_id.id
                                    cr.execute(''' UPDATE stock_move SET account_analytic_id=%s WHERE id=%s''',(account_analytic_id, move.id))
                                else:
                                    raise osv.except_osv(_('Configuration !'), _("El sistema esta configurado para requerir la cuenta analitica en el proceso de remision, sin embargo no logra encontrar una cuenta para el producto '%s' y el usuario ''. Esto puede ser porque no tiene valores predeterminados 'CONSULTAR CON EL AREA ENCARGADA' o porque el pedido de venta fue generado por un usuario que no es comercial." % move.product_id.default_code, pick.create_uid.name))

                        cr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': account_move_return,
                            'partner_id': partner_id.id,
                            'debit': 0.0,
                            'credit': total_cost,
                            'analytic_account_id': account_analytic_id or False,
                            'date': picking_date,
                            'tax_code_id': False,
                            'tax_amount': 0, 
                            'base_code_id': False,
                            'base_amount': 0,
                        }
                        dr_move_val = cr_move_val.copy()
                        dr_move_val.update({
                            'account_id': account_id,
                            'credit': 0.0,
                            'debit': total_cost,
                            'tax_code_id': False,
                            'tax_amount': 0, 
                            'base_code_id': False,
                            'base_amount': 0,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                    elif move.location_id.usage in ["customer"] and move.location_dest_id.usage == "internal" and pick.picking_type_id.code == "return":#DEVOLUCION VENTAS 2

                        if pick.picking_type_id.code != "return":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            continue

                        account_debit_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ and product_data.categ_id.property_stock_account_input_categ.id

                        account_credit_id = product_data.cogs_account_id and product_data.cogs_account_id.id or product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id

                        date_dev=pick.date_dev or pick.date

                        if not account_debit_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de entrada de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name))

                        if not account_credit_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de devolucion no esta definida en el producto '%s' ni en su categoria"  % product_data.name))
                        
                        id_s = []
                        
                        cr.execute('SELECT id  FROM product_pricelist_item where price_version_id in (SELECT  id FROM product_pricelist_version where pricelist_id=%s and active=True and date_start <= %s and date_end >= %s ) and product_id=%s',(partner_id.property_product_pricelist.id,date_dev,date_dev,product_data.id))
                        result = cr.fetchone()

                        if not result:
                            cr.execute('SELECT id  FROM product_pricelist_item where price_version_id in (SELECT  id FROM product_pricelist_version where pricelist_id=%s and active=True) and product_id=%s',(partner_id.property_product_pricelist.id,product_data.id))
                            result = cr.fetchone()
                            if result:
                                id_s = result[0]
                        else:
                            id_s = result[0]

                        if not id_s:
                            if pick.company_id.sale_cost_invoice:
                                raise osv.except_osv(_('Configuration !'), _("el producto '%s' no esta definido en la lista de precios "  % product_data.name))
                            else:
                                price = product_data.lst_price
                        else:
                            items = self.pool.get('product.pricelist.item').browse(cr, uid, [id_s], context=context)
                            price = items.precio_lista

                        #COSTO PROMEDIO DEVOLUCIONES DE VENTA
                        standard_price = move.cost
                        total_cost = standard_price*move.product_qty

                        dr_move_val = {
                                'company_id': company_id,
                                'journal_id': journal_id.id,
                                'name': product_data.default_code or product_data.name,
                                'ref': product_data.name,
                                'ref1': product_data.name,
                                'period_id': period_id,
                                'account_id': account_debit_id,
                                'partner_id': partner_id.id,
                                'credit': 0.0,
                                'debit': total_cost,
                                'date': move.date_expected,
                                'stock_picking_id': move.picking_id.id,
                                'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or False,
                                'tax_code_id': False,
                                'base_code_id': False,
                            }
                        cr_move_val = dr_move_val.copy()
                        cr_move_val.update({
                            'account_id': account_credit_id,
                            'debit': 0.0,
                            'credit': total_cost,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)
                    
                    
                    elif move.location_id.usage != "internal" and move.location_dest_id.usage == "internal":#AJUSTES/PRODUCCIONES/OTROS
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            continue
                        
                        if pick.picking_type_id.code not in ["incoming", "return"]:
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        account_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ.id
                        if not account_id:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con una cuenta de entrada de almacen. Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % product_data.name, product_data.categ_id.name))

                        account_move_return = (product_data.cogs_account_id and product_data.cogs_account_id.id) or (product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id) or False
                        if not account_move_return and not move.origin_returned_move_id:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con una cuenta de costo de venta. Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % product_data.name, product_data.categ_id.name))

                        #COSTO PROMEDIO AJUSTES/PRODUCCIONES/OTROS
                        standard_price=move.cost
                        total_cost = move.product_qty * standard_price

                        cr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': account_move_return,
                            'partner_id': partner_id.id,
                            'debit': 0.0,
                            'credit': total_cost,
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                            'date': picking_date,
                            'tax_code_id': False,
                            'tax_amount': 0, 
                            'base_code_id': False,
                            'base_amount': 0,
                        }
                        dr_move_val = cr_move_val.copy()
                        dr_move_val.update({
                            'account_id': account_id,
                            'credit': 0.0,
                            'debit': total_cost,
                            'tax_code_id': False,
                            'tax_amount': 0, 
                            'base_code_id': False,
                            'base_amount': 0,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                    elif move.location_id.usage == "internal" and move.location_dest_id.usage == "customer":#VENTAS
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            continue

                        if pick.picking_type_id.code == "customer":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        output_account_id = product_data.property_stock_account_output and product_data.property_stock_account_output.id or product_data.categ_id.property_stock_account_output_categ.id
                        if not output_account_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de salida de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name))

                        account_id = (product_data.cogs_account_id and product_data.cogs_account_id.id) or (product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id) or False
                        if move.product_id.valuation == 'real_time' or move.product_id.cost_method != 'average':
                            raise osv.except_osv(_('Configuration !'), _("Cambiar configuracion de evaluacion del producto '%s', modo tiempo real no soportado, y por favor valide que el metodo de costeo del producto sea PROMEDIO"  % product_data.name))
                        
                        # Contabilidad Analitica por default
                        if pick.company_id.analytic_default:
                            account_analytic_id = move.sale_line_id and move.sale_line_id.account_analytic_id and move.sale_line_id.account_analytic_id.id
                            
                            if not account_analytic_id:
                                analytic_id = account_default_obj.search(cr, uid, [('product_id', '=', move.product_id.id),('user_id', '=', pick.create_uid and pick.create_uid.id or False)], context=context, limit=1)
                                if analytic_id:
                                    account_analytic_id=account_default_obj.browse(cr, uid, analytic_id[0], context=context).analytic_id.id
                                    cr.execute(''' UPDATE stock_move SET account_analytic_id=%s WHERE id=%s''',(account_analytic_id, move.id))
                                else:
                                    raise osv.except_osv(_('Configuration !'), _("El sistema esta configurado para requerir la cuenta analitica en el proceso de remision, sin embargo no logra encontrar una cuenta para el producto '%s' y el usuario ''. Esto puede ser porque no tiene valores predeterminados 'CONSULTAR CON EL AREA ENCARGADA' o porque el pedido de venta fue generado por un usuario que no es comercial." % move.product_id.default_code, pick.create_uid.name))
                        else:
                            account_analytic_id = move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False


                        #COSTO PROMEDIO VENTA
                        price = move.cost
                        price_total = price*product_qty

                        cr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': output_account_id,                            
                            'partner_id': partner_id.id,
                            'analytic_account_id': account_analytic_id or False,
                            'debit': 0.0,
                            'credit': price_total,
                            'date': picking_date,
                            'tax_code_id': False,
                            'base_code_id': False,
                        }
                        dr_move_val = cr_move_val.copy()
                        dr_move_val.update({
                            'account_id': account_id,
                            'credit': 0.0,
                            'debit': price_total,
                            'analytic_account_id': account_analytic_id or False,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                    elif move.location_id.usage == "internal" and move.location_dest_id.usage == "supplier":#DEVOLUCION COMPRAS
                        if pick.picking_type_id.code == "customer":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        impuestos_mayor_valor = {}
                        var=0
                        if move.origin_returned_move_id:
                            var=product_qty/(move.origin_returned_move_id.product_qty)
                            if move.origin_returned_move_id.picking_id and move.origin_returned_move_id.picking_id.account_move_id:
                                for line in move.origin_returned_move_id.picking_id.account_move_id.line_id:
                                    if line.tax_code_id and line.base_code_id:
                                        impuestos_mayor_valor={'base_code_id':line.base_code_id,'tax_code_id':line.tax_code_id,'tax_amount': line.tax_amount, 'base_amount': line.base_amount}

                        if not partner_id.accrued_account_payable_id:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con la parametrizacion de la cuenta puente de recepcion del tercero '%s', se sugiere una cuenta del pasivo 26."  % partner_id.name))
                        account_move_return = partner_id.accrued_account_payable_id.id

                        output_account_id = product_data.property_stock_account_output and product_data.property_stock_account_output.id or product_data.categ_id.property_stock_account_output_categ.id
                        if not output_account_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de salida de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name))


                        #COSTO PROMEDIO DEVOLUCIONES COMPRA
                        price = move.cost
                        price_total = price*product_qty

                        cr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': output_account_id,
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                            'partner_id': partner_id.id,
                            'debit': 0.0,
                            'credit': price_total,
                            'date': picking_date,
                            'tax_code_id': impuestos_mayor_valor.get('tax_code_id', False) and impuestos_mayor_valor.get('tax_code_id').id,
                            'tax_amount':  impuestos_mayor_valor.get('tax_amount', False) and impuestos_mayor_valor.get('tax_amount')* (-var),
                            'base_code_id': impuestos_mayor_valor.get('base_code_id', False) and impuestos_mayor_valor.get('base_code_id').id,
                            'base_amount': impuestos_mayor_valor.get('base_amount', False) and impuestos_mayor_valor.get('base_amount')*(-var),
                        }
                        dr_move_val = cr_move_val.copy()
                        dr_move_val.update({
                            'account_id': account_move_return,
                            'credit': 0.0,
                            'debit': price_total,
                            'tax_code_id': False,
                            'tax_amount': 0, 
                            'base_code_id': False,
                            'base_amount': 0,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                    elif move.location_id.usage == "internal" and move.location_dest_id.usage != "internal":#AJUSTES/PRODUCCIONES/OTROS
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            continue

                        if pick.picking_type_id.code == "customer":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        output_account_id = product_data.property_stock_account_output and product_data.property_stock_account_output.id or product_data.categ_id.property_stock_account_output_categ.id
                        if not output_account_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de salida de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name))

                        account_id = (product_data.cogs_account_id and product_data.cogs_account_id.id) or (product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id) or False

                        if move.product_id.valuation == 'real_time':
                            raise osv.except_osv(_('Configuration !'), _("Cambiar configuracion de evaluacion del producto '%s', modo tiempo real no soportado"  % product_data.name))

                        #COSTO PROMEDIO VENTA
                        price = move.cost
                        price_total = price*product_qty

                        cr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': output_account_id,
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                            'partner_id': partner_id.id,
                            'debit': 0.0,
                            'credit': price_total,
                            'date': picking_date,
                            'tax_code_id': False,
                            'base_code_id': False,
                        }
                        dr_move_val = cr_move_val.copy()
                        dr_move_val.update({
                            'account_id': account_id,
                            'credit': 0.0,
                            'debit': price_total,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

            move_id = False
            if move_line_in and not refund:
                move = {
                    'line_id': [],
                    'journal_id': journal_id.id,
                    'date': picking_date,
                    'period_id': period_id,
                }
                move_id = account_move_obj.create(cr, uid, move, context=context)
                cr.execute(''' UPDATE stock_picking SET  account_move_id = %s WHERE id = %s''',(move_id, pick.id))
                if journal_id.no_agrupar:
                    array = []
                    for x in move_line_in:    
                        cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, period_id, account_id, analytic_account_id, partner_id, debit, credit, date, state) VALUES
                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''' , (move_id, company_id, journal_id.id, x['name'], period_id, x['account_id'], x['analytic_account_id'] or None, partner_id.id, float(x['debit']), float(x['credit']), x['date'], 'valid'))
                else:
                    group_move_line = self.group_lines(cr, uid, move_line_in)
                    account_move_obj.write(cr, uid, [move_id], {'line_id': group_move_line})
                account_move_obj.post(cr, uid, [move_id])
            #IMPORTACIONES
            purchase = self.pool('purchase.order').search(cr, uid, [('name','=',pick.origin)], context=context, limit=1)
            if purchase and pick.picking_type_code == 'incoming':            
                purchase = self.pool('purchase.order').browse(cr, uid, purchase, context=context)
                try:
                    if purchase and purchase.import_id and pick.account_move_id:
                        if company_id.invoice_import:
                            cr.execute(''' UPDATE stock_picking SET invoice_state='invoiced' WHERE id=%s''', (pick.id,))
                        cr.execute(''' UPDATE account_move_line SET import_id=%s WHERE move_id=%s''', (purchase.import_id.id, pick.account_move_id.id))
                except:
                    print "EMPRESA NO TIENE IMPORTACIONES"
            #DEVOLUCIONES
            try:
                if pick.dev_id:
                    cr.execute(''' update return_order set user_transfer=%s, date_transfer=%s where id=%s''', (uid, datetime.now(), pick.dev_id.id))
            except:
                print "EMPRESA NO TIENE EL MODULO DE DEVOLUCIONES"
            
        # ESTA FUNCION ES LA ENCARGADA DE VALIDAR EL CAMPO automatic_invoice Y PERMITE GENERAR LA FACTURA DE FORMA DIRECTA DESDE LA TRANSFERENCIA.
        for pick in self.browse(cr, uid, picking_ids, context=context):
            ot=False
            try:
                ot = pick.ot
            except:
                ot = False
            if pick.account_move_id and ot:                
                cr.execute(''' UPDATE stock_move SET  ot=%s WHERE picking_id=%s''',(pick.ot.id,pick.id))
                if pick.picking_type_id.code == 'outgoing':
                    account_id = pick.picking_type_id.default_location_dest_id.valuation_out_account_id and pick.picking_type_id.default_location_dest_id.valuation_out_account_id.id or False
                    if not account_id:
                        raise osv.except_osv(_('Warning!'), _("Un movimiento de salida asociado a una OT debe tener configurada la cuenta de valorizacion de existencias (saliente) en la ubicacion destino '%s'. Por favor realice la configuracion o consulte con el area encargada.") % (pick.picking_type_id.default_location_dest_id.name))
                    cr.execute(''' UPDATE account_move_line SET  account_id=%s, ot=%s WHERE move_id=%s AND debit > 0.0 AND credit <= 0.0 ''',(account_id,pick.ot.id,pick.account_move_id.id))
                elif pick.picking_type_id.code in ['incoming','return']:
                    account_id = pick.picking_type_id.default_location_src_id.valuation_in_account_id and pick.picking_type_id.default_location_src_id.valuation_in_account_id.id or False
                    if not account_id:
                        raise osv.except_osv(_('Warning!'), _("Un movimiento de entrada asociado a una OT debe tener configurada la cuenta de valorizacion de existencias (entrante) en la ubicacion origen '%s'. Por favor realice la configuracion o consulte con el area encargada.") % (pick.picking_type_id.default_location_src_id.name))
                    cr.execute(''' UPDATE account_move_line SET  account_id=%s, ot=%s WHERE move_id=%s AND credit > 0.0 AND debit <= 0.0 ''',(account_id,pick.ot.id,pick.account_move_id.id))

        return move_id or False


    @api.cr_uid_ids_context
    def do_transfer(self, cr, uid, picking_ids, context=None):
        move_line_in = []
        if context is None:
            context = {}
        else:
            context = dict(context)

        aap = avancys_orm.fetchall(cr, "SELECT id from ir_module_module where name = 'account_analytic_project' "
                                       "and state = 'installed'")

        move_obj = self.pool.get('stock.move')
        currency_obj = self.pool.get('res.currency')

        tax_obj = self.pool.get('account.tax')
        period_obj = self.pool.get('account.period')
        account_move_obj = self.pool.get('account.move')
        account_default_obj = self.pool.get('account.analytic.default')
        account_analytic_id=False
        obj_precision = self.pool.get('decimal.precision')
        prec = obj_precision.precision_get(cr, uid, 'Account')
        additional_cost = 0

        #Costo por Bodega
        costo_por_bodega = False
        model_obj = self.pool.get('ir.model').search(cr, uid, [('model','=','product.warehouse.standard.price')], context=context)
        if model_obj:
            costo_por_bodega = True

        res = super(StockPicking, self).do_transfer(cr, uid, picking_ids, context=context)

        for pick in self.browse(cr, uid, picking_ids, context=context):
            
            # RESTRICCION DE DUPLICACION DE MOVIMIENTOS CONTABLES
            if pick.account_move_id:
                raise osv.except_osv(_('Error !'), _("POR FAVOR ACTUALICE Y VALIDE EL ESTADO DE LA TRANSFERENCIA"))

                
            company_id = pick.company_id.id
            picking_date = pick.date_done and pick.date_done[0:10] or datetime.now().date()
            refund = False

            if pick.picking_type_id.code != "internal":
                
                if pick.partner_id and pick.partner_id.parent_id:
                    partner_id = pick.partner_id.parent_id
                elif pick.partner_id:
                    partner_id =pick.partner_id
                else:
                    raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con un tercero asociado al movimiento de inventario %s" % pick.name))

                journal_id = pick.picking_type_id.journal_id or False
                if not journal_id:
                    raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con un diario, configurado en el tipo de operacion %s"  % pick.picking_type_id.name))

                period_id = period_obj.search(cr, uid, [('state','=','draft'),('date_start','<=',picking_date),('date_stop','>=',picking_date)], limit=1,context=context)
                if period_id:
                    period_id = period_id[0]
                elif pick.picking_type_id.code != "internal":
                    raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con un periodo contable abierto para este tipo de transferencia para la fecha %s"  % picking_date))

            for move in pick.move_lines:
                product_data = move.product_id
                product_qty = move.product_qty
                price_unit = move.price_unit
                cost = move.cost
                asset = False
                
                # RESTRICCION DE MOVIMIENTOS CON UBICACIONES DE TIPO VISTA
                if move.location_id.usage == "view" or move.location_dest_id.usage == "view":
                    raise osv.except_osv(_('Configuration !'), _("El sistema no permite realizar movimientos desde/para una  ubicacion de tipo VISTA, por favor valide el origen y destino del movimeinto de inventario"))
                
                try:
                    asset = product_data.is_asset
                except:
                    asset = False
                    
                
                if pick.company_id.purchase_asset and asset:
                    try:
                        if move.purchase_asset == 'inventary':
                            asset=False
                    except:
                        asset = True
                        
                # COSTO POR BODEGA
                if costo_por_bodega:
                    context.update({'warehouse':self.pool.get('stock.location').get_warehouse(cr, uid, move.location_id, context=context)})

                if (move.location_id.usage != "internal" or move.location_dest_id.usage != "internal") and move.product_id.type == "product" and move.state != "cancel" and not asset:
                    if move.location_id.usage == "supplier" and move.location_dest_id.usage == "internal":#COMPRAS
                        if pick.picking_type_id.code != "incoming":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))
                        account_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ.id
                        if not account_id:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con una cuenta de entrada de almacen. Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % product_data.name, product_data.categ_id.name))
                        tax_mayor_valor = []
                        impuestos_mayor_valor = {}
                        if self.pool.get('ir.module.module').search(cr, uid, [('name','=','stock_picking_dotacion'),
                                                                              ('state','=','installed')], context=context):
                            refund = move.picking_id.is_refund
                        if move.purchase_line_id:
                            try:
                                fabricante_id = move.purchase_line_id.fabricante_id and move.purchase_line_id.fabricante_id.id or False
                            except:
                                fabricante_id = move.purchase_line_id.partner_id and move.purchase_line_id.partner_id.id or False

                            if fabricante_id:
                                cr.execute(''' UPDATE product_product SET  fabricante_id = %s WHERE id = %s''',(fabricante_id, product_data.id))     

                            if move.purchase_line_id.product_uom == move.product_id.uos_id and move.product_id.uos_id != move.product_id.uom_id:
                                product_qty = move.purchase_line_id.product_qty / move.product_id.uos_coeff
                                price_unit = move.purchase_line_id.price_unit * move.product_id.uos_coeff
                            for tax_check in move.purchase_line_id.taxes_id:
                                if tax_check.mayor_valor:
                                    tax_mayor_valor.append(tax_check)
                            if len(tax_mayor_valor) > 1:
                                raise osv.except_osv(_('Error !'), _("Hay mas de un impuesto de mayor valor para el producto '%s'") % (move.product_id.name))
                            for tax in tax_obj.compute_all(cr, uid, tax_mayor_valor, (move.purchase_line_id.price_unit* (1-(move.purchase_line_id.discount or 0.0)/100.0)), product_qty, product_data, partner_id)['taxes']:
                                impuestos_mayor_valor={'base_code_id':tax['base_code_id'],'tax_code_id':tax['tax_code_id'],'account_id':account_id, 'amount': tax['amount'], 'base': (move.purchase_line_id.price_unit*(1-(move.purchase_line_id.discount or 0.0)/100.0)*product_qty)}
                        else:
                            move_origin = move_obj.search(cr, uid, [('picking_id','=',move.picking_id.id),('id','!=',move.id),('product_id','=',move.product_id.id),('purchase_line_id','!=',False)], context=context)
                            if move_origin:
                                move_origin = move_obj.browse(cr, uid, move_origin, context=context)
                                cr.execute(''' UPDATE stock_move SET purchase_line_id=%s WHERE id = %s''',(move_origin.purchase_line_id.id, move.id))
                            else:
                                if not refund:
                                    raise osv.except_osv(_('Error !'), _("El producto '%s' con referencia interna '%s' no esta asociado a la orden de compra '%s'. Si desea incluirlo en la recepcion debe 1.Cancelar O.C. ---->   2.Regresar a borrador ---->   3.Modificar la O.C. ---->   4.Confirmar O.C.") % (move.product_id.name, move.product_id.default_code, pick.origin))

                        if tax_mayor_valor:
                            additional_cost = (cost*product_qty) - (price_unit*product_qty + impuestos_mayor_valor['amount'])
                            invoiced = price_unit*product_qty + impuestos_mayor_valor['amount']
                        else:
                        #     additional_cost = (cost-price_unit)*product_qty
                            invoiced = cost*product_qty

                        discount = move.purchase_line_id.discount
                        # invoiced = currency_obj.round(cr, uid, move.local_currency_id, invoiced)
                        # additional_cost = currency_obj.round(cr, uid, move.local_currency_id, additional_cost)
                        # total_cost = invoiced+additional_cost
                        total_cost = invoiced

                        dr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': account_id,
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                            'partner_id': partner_id.id,
                            'credit': 0.0,
                            'debit': total_cost*(1-discount/100),
                            'date': picking_date,
                            'stock_picking_id': move.picking_id.id,
                            'tax_code_id': impuestos_mayor_valor.get('tax_code_id', False),
                            'tax_amount': impuestos_mayor_valor.get('amount', False), 
                            'base_code_id': impuestos_mayor_valor.get('base_code_id', False),
                            'base_amount': impuestos_mayor_valor.get('base', False), 
                        }
                        if aap and move.account_analytic_id:
                            dr_move_val['project_id'] = move.project_id.id

                        cr_move_val = dr_move_val.copy()
                        cuenta_puente = partner_id.accrued_account_payable_id.id
                        if not cuenta_puente:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con la parametrizacion de la cuenta puente de recepcion del tercero '%s', se sugiere una cuenta del pasivo 26."  % partner_id.name))
                        cr_move_val.update({
                            'account_id': cuenta_puente,
                            'debit': 0.0,
                            'credit': invoiced*(1-discount/100),
                            'tax_code_id': False,
                            'tax_amount': 0,
                            'base_code_id': False,
                            'base_amount': 0, 
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                        })
                        if aap and move.account_analytic_id:
                            cr_move_val['project_id'] = move.project_id.id
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                        if not currency_obj.is_zero(cr, uid, move.local_currency_id, additional_cost):
                            if additional_cost < -1 and not refund:
                                n = product_data.name +' '+ (product_data.default_code or '')
                                raise osv.except_osv(_('Error !'), _("El costo del producto '%s' no puede ser menor al valor configurado, el costo es '%s' mientras el precio es '%s'")  % (n, cost, price_unit))
                            if additional_cost > 0:
                                cr_move_val2 = dr_move_val.copy()
                                transit_account = (product_data.transit_accout_id and product_data.transit_accout_id.id) or (product_data.categ_id.transit_accout_id and product_data.categ_id.transit_accout_id.id) or False
                                if not transit_account:
                                    raise osv.except_osv(_('Configuration !'), _("La cuenta de transito no esta definida en el producto '%s' ni en su categoria"  % product_data.name))
                                cr_move_val2.update({
                                    'account_id': transit_account,
                                    'debit': 0.0,
                                    'credit': additional_cost,
                                })
                                move_line_in.append(cr_move_val2)

                    elif move.location_id.usage == "customer" and move.location_dest_id.usage == "internal" and pick.picking_type_id.code != "return":#DEVOLUCION VENTAS 1
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            standard_price=product_data.standard_price
                            total_cost = move.product_qty * standard_price
                            cr.execute(''' update stock_move set cost=%s, total_cost=%s, costo_promedio=%s where id=%s''', (standard_price, total_cost, standard_price, move.id))
                            continue

                        if pick.picking_type_id.code != "incoming":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        account_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ.id
                        if not account_id:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con una cuenta de entrada de almacen. Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % product_data.name, product_data.categ_id.name))

                        account_move_return = (product_data.cogs_account_id and product_data.cogs_account_id.id) or (product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id) or False
                        if not account_move_return:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con una cuenta de costo de venta. Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % product_data.name, product_data.categ_id.name))

                        #COSTO PROMEDIO DEVOLUCIONES DE VENTA
                        standard_price=product_data.standard_price
                        total_cost = move.product_qty * standard_price
                        cr.execute(''' update stock_move set cost=%s, total_cost=%s, costo_promedio=%s where id=%s''', (standard_price, total_cost, standard_price, move.id))
                        
                        # Contabilidad Analitica por default
                        if pick.company_id.analytic_default:
                            account_analytic_id = move.origin_returned_move_id and move.origin_returned_move_id.account_analytic_id and move.origin_returned_move_id.account_analytic_id.id
                            
                            if not account_analytic_id:
                                analytic_id = account_default_obj.search(cr, uid, [('product_id', '=', move.product_id.id),('user_id', '=', pick.create_uid and pick.create_uid.id or False)], context=context, limit=1)
                                if analytic_id:
                                    account_analytic_id=account_default_obj.browse(cr, uid, analytic_id[0], context=context).analytic_id.id
                                    cr.execute(''' UPDATE stock_move SET account_analytic_id=%s WHERE id=%s''',(account_analytic_id, move.id))
                                else:
                                    raise osv.except_osv(_('Configuration !'), _("El sistema esta configurado para requerir la cuenta analitica en el proceso de remision, sin embargo no logra encontrar una cuenta para el producto '%s' y el usuario ''. Esto puede ser porque no tiene valores predeterminados 'CONSULTAR CON EL AREA ENCARGADA' o porque el pedido de venta fue generado por un usuario que no es comercial." % move.product_id.default_code, pick.create_uid.name))

                        cr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': account_move_return,
                            'partner_id': partner_id.id,
                            'debit': 0.0,
                            'credit': total_cost,
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                            'date': picking_date,
                            'tax_code_id': False,
                            'tax_amount': 0, 
                            'base_code_id': False,
                            'base_amount': 0,
                        }
                        dr_move_val = cr_move_val.copy()
                        dr_move_val.update({
                            'account_id': account_id,
                            'credit': 0.0,
                            'debit': total_cost,
                            'tax_code_id': False,
                            'tax_amount': 0, 
                            'base_code_id': False,
                            'base_amount': 0,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                    elif move.location_id.usage == "customer" and move.location_dest_id.usage == "internal" and pick.picking_type_id.code == "return":#DEVOLUCION VENTAS 2
                        if pick.picking_type_id.code != "return":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))
                        
                        id_s = []
                        date_dev=pick.date_dev or pick.date
                        
                        cr.execute('SELECT id  FROM product_pricelist_item where price_version_id in (SELECT  id FROM product_pricelist_version where pricelist_id=%s and active=True and date_start <= %s and date_end >= %s ) and product_id=%s',(partner_id.property_product_pricelist.id,date_dev,date_dev,product_data.id))
                        result = cr.fetchone()

                        if not result:
                            cr.execute('SELECT id  FROM product_pricelist_item where price_version_id in (SELECT  id FROM product_pricelist_version where pricelist_id=%s and active=True) and product_id=%s',(partner_id.property_product_pricelist.id,product_data.id))
                            result = cr.fetchone()
                            if result:
                                id_s = result[0]
                        else:
                            id_s = result[0]

                        if not id_s:
                            if pick.company_id.sale_cost_invoice:
                                raise osv.except_osv(_('Configuration !'), _("el producto '%s' no esta definido en la lista de precios "  % product_data.name))
                            else:
                                price = product_data.lst_price
                        else:
                            items = self.pool.get('product.pricelist.item').browse(cr, uid, [id_s], context=context)
                            price = items.precio_lista
                            
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            standard_price = product_data.standard_price
                            total_cost = standard_price*move.product_qty
                            cr.execute(''' update stock_move set cost=%s, total_cost=%s, price_unit=%s, costo_promedio=%s where id=%s''', (standard_price, total_cost, price, standard_price, move.id))
                            continue

                        account_debit_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ and product_data.categ_id.property_stock_account_input_categ.id

                        account_credit_id = product_data.cogs_account_id and product_data.cogs_account_id.id or product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id

                        if not account_debit_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de entrada de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name))

                        if not account_credit_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de devolucion no esta definida en el producto '%s' ni en su categoria"  % product_data.name))

                        #COSTO PROMEDIO DEVOLUCIONES DE VENTA
                        standard_price = product_data.standard_price
                        total_cost = standard_price*move.product_qty
                        cr.execute(''' update stock_move set cost=%s, total_cost=%s, price_unit=%s, costo_promedio=%s where id=%s''', (standard_price, total_cost, price, standard_price, move.id))

                        dr_move_val = {
                                'company_id': company_id,
                                'journal_id': journal_id.id,
                                'name': product_data.default_code or product_data.name,
                                'ref': product_data.name,
                                'ref1': product_data.name,
                                'period_id': period_id,
                                'account_id': account_debit_id,
                                'partner_id': partner_id.id,
                                'credit': 0.0,
                                'debit': total_cost,
                                'date': move.date_expected,
                                'stock_picking_id': move.picking_id.id,
                                'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or False,
                                'tax_code_id': False,
                                'base_code_id': False,
                            }
                        cr_move_val = dr_move_val.copy()
                        cr_move_val.update({
                            'account_id': account_credit_id,
                            'debit': 0.0,
                            'credit': total_cost,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                    elif move.location_id.usage != "internal" and move.location_dest_id.usage == "internal":#AJUSTES/PRODUCCIONES/OTROS
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            standard_price=product_data.standard_price
                            total_cost = move.product_qty * standard_price
                            cr.execute(''' update stock_move set cost=%s, total_cost=%s, costo_promedio=%s where id=%s''', (standard_price, total_cost, standard_price, move.id))
                            continue
                        
                        if pick.picking_type_id.code not in ["incoming", "return"]:
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        account_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ.id
                        if not account_id:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con una cuenta de entrada de almacen. Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % product_data.name, product_data.categ_id.name))

                        account_move_return = (product_data.cogs_account_id and product_data.cogs_account_id.id) or (product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id) or False
                        if not account_move_return and not move.origin_returned_move_id:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con una cuenta de costo de venta. Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % product_data.name, product_data.categ_id.name))

                        #COSTO PROMEDIO AJUSTES/PRODUCCIONES/OTROS
                        standard_price=product_data.standard_price
                        total_cost = move.product_qty * standard_price
                        cr.execute(''' update stock_move set cost=%s, total_cost=%s, costo_promedio=%s where id=%s''', (standard_price, total_cost, standard_price, move.id))

                        cr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': account_move_return,
                            'partner_id': partner_id.id,
                            'debit': 0.0,
                            'credit': total_cost,
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                            'date': picking_date,
                            'tax_code_id': False,
                            'tax_amount': 0, 
                            'base_code_id': False,
                            'base_amount': 0,
                        }
                        dr_move_val = cr_move_val.copy()
                        dr_move_val.update({
                            'account_id': account_id,
                            'credit': 0.0,
                            'debit': total_cost,
                            'tax_code_id': False,
                            'tax_amount': 0, 
                            'base_code_id': False,
                            'base_amount': 0,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                    elif move.location_id.usage == "internal" and move.location_dest_id.usage == "customer":#VENTAS
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            price = product_data.standard_price
                            price_total = price*product_qty
                            # RESTRICCION DE MOVIMIENTOS CON COSTO CERO
                            if price <= 0.0 and pick.company_id.restriction_cost_zero:
                                raise osv.except_osv(_('Error !'), _("El movimiento que esta tratando de transferir tiene un costo menor o igual a cero, por favor valide con el area encargada."))
                            cr.execute(''' update stock_move set cost=%s, total_cost=%s, costo_promedio=%s where id=%s''', (price, price_total, price, move.id))
                            continue

                        if pick.picking_type_id.code == "customer":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        output_account_id = product_data.property_stock_account_output and product_data.property_stock_account_output.id or product_data.categ_id.property_stock_account_output_categ.id
                        if not output_account_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de salida de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name))
                        
                        # Contabilidad Analitica por default
                        if pick.company_id.analytic_default:
                            account_analytic_id = move.sale_line_id and move.sale_line_id.account_analytic_id and move.sale_line_id.account_analytic_id.id
                            
                            if not account_analytic_id:
                                analytic_id = account_default_obj.search(cr, uid, [('product_id', '=', move.product_id.id),('user_id', '=', pick.create_uid and pick.create_uid.id or False)], context=context, limit=1)
                                if analytic_id:
                                    account_analytic_id=account_default_obj.browse(cr, uid, analytic_id[0], context=context).analytic_id.id
                                    cr.execute(''' UPDATE stock_move SET account_analytic_id=%s WHERE id=%s''',(account_analytic_id, move.id))
                                else:
                                    raise osv.except_osv(_('Configuration !'), _("El sistema esta configurado para requerir la cuenta analitica en el proceso de remision, sin embargo no logra encontrar una cuenta para el producto '%s' y el usuario ''. Esto puede ser porque no tiene valores predeterminados 'CONSULTAR CON EL AREA ENCARGADA' o porque el pedido de venta fue generado por un usuario que no es comercial." % move.product_id.default_code, pick.create_uid.name))
                        else:
                            if 'is_dotation' in self._fields:
                                if pick.is_dotation or pick.to_puesto:
                                    if not pick.analytic_account_id:
                                        raise Warning("No se ha definido una cuenta analitica en la asignacion de dotacion")
                                    else:
                                        account_analytic_id = pick.analytic_account_id.id
                            else:
                                account_analytic_id = move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False

                        account_id = (product_data.cogs_account_id and product_data.cogs_account_id.id) or \
                                     (product_data.categ_id.cogs_account_id and
                                      product_data.categ_id.cogs_account_id.id) or False
                        if not account_id:
                            raise osv.except_osv(_('Configuracion !'), _(
                                "La cuenta de Costos de Venta no esta configurada en el producto %s ni en su "
                                "categoria" %
                                move.product_id.default_code))

                        if move.product_id.valuation == 'real_time':
                            raise osv.except_osv(_('Configuration !'), _("Cambiar configuracion de evaluacion del producto '%s', modo tiempo real no soportado"  % product_data.name))

                        # Flujo de ventas SCB
                        if getattr(pick, 'sale_stock_picking', None):
                            account_id = product_data.categ_id.account_production_transit_id and product_data.categ_id.account_production_transit_id.id or False
                            if not account_id:
                                raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta de producto en proceso de la categoria '%s' para realizar el reconocimiento de producto donde el cliente"  % product_data.categ_id.name))


                        #COSTO PROMEDIO VENTA
                        price = product_data.standard_price
                        price_total = price*product_qty
                        # RESTRICCION DE MOVIMIENTOS CON COSTO CERO
                        if price <= 0.0 and pick.company_id.restriction_cost_zero:
                            raise osv.except_osv(_('Error !'), _("El movimiento que esta tratando de transferir tiene "
                                                        "un costo menor o igual a cero, producto %s, "
                                                        "por favor valide con el area encargada." % product_data.name))
                        cr.execute(''' update stock_move set cost=%s, total_cost=%s, costo_promedio=%s where id=%s''', (price, price_total, price, move.id))

                        cr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': output_account_id,
                            'partner_id': partner_id.id,
                            'analytic_account_id': (account_analytic_id or False) if 'is_dotation' not in self._fields else False,
                            'debit': 0.0,
                            'credit': round(price_total, prec),
                            'date': picking_date,
                            'tax_code_id': False,
                            'base_code_id': False,
                        }
                        dr_move_val = cr_move_val.copy()
                        dr_move_val.update({
                            'account_id': account_id,
                            'credit': 0.0,
                            'debit': round(price_total, prec),
                            'analytic_account_id': account_analytic_id or False,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                    elif move.location_id.usage == "internal" and move.location_dest_id.usage == "supplier":#DEVOLUCION COMPRAS
                        if pick.picking_type_id.code == "customer":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        impuestos_mayor_valor = {}
                        var=0
                        if move.origin_returned_move_id:
                            var=product_qty/(move.origin_returned_move_id.product_qty)
                            if move.origin_returned_move_id.picking_id and move.origin_returned_move_id.picking_id.account_move_id:
                                for line in move.origin_returned_move_id.picking_id.account_move_id.line_id:
                                    if line.tax_code_id and line.base_code_id:
                                        impuestos_mayor_valor={'base_code_id':line.base_code_id,'tax_code_id':line.tax_code_id,'tax_amount': line.tax_amount, 'base_amount': line.base_amount}

                        if not partner_id.accrued_account_payable_id:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con la parametrizacion de la cuenta puente de recepcion del tercero '%s', se sugiere una cuenta del pasivo 26."  % partner_id.name))
                        account_move_return = partner_id.accrued_account_payable_id.id

                        output_account_id = product_data.property_stock_account_output and product_data.property_stock_account_output.id or product_data.categ_id.property_stock_account_output_categ.id
                        if not output_account_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de salida de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name))

                        #COSTO PROMEDIO DEVOLUCIONES COMPRA
                        price = product_data.standard_price
                        price_total = price*product_qty
                        cr.execute(''' update stock_move set cost=%s, total_cost=%s, costo_promedio=%s where id=%s''', (price, price_total, price, move.id))

                        cr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': output_account_id,
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                            'partner_id': partner_id.id,
                            'debit': 0.0,
                            'credit': price_total,
                            'date': picking_date,
                            'tax_code_id': impuestos_mayor_valor.get('tax_code_id', False) and impuestos_mayor_valor.get('tax_code_id').id,
                            'tax_amount':  impuestos_mayor_valor.get('tax_amount', False) and impuestos_mayor_valor.get('tax_amount')* (-var),
                            'base_code_id': impuestos_mayor_valor.get('base_code_id', False) and impuestos_mayor_valor.get('base_code_id').id,
                            'base_amount': impuestos_mayor_valor.get('base_amount', False) and impuestos_mayor_valor.get('base_amount')*(-var),
                        }
                        dr_move_val = cr_move_val.copy()
                        dr_move_val.update({
                            'account_id': account_move_return,
                            'credit': 0.0,
                            'debit': price_total,
                            'tax_code_id': False,
                            'tax_amount': 0,
                            'base_code_id': False,
                            'base_amount': 0,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)

                    elif move.location_id.usage == "internal" and move.location_dest_id.usage != "internal":#AJUSTES/PRODUCCIONES/OTROS
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            price = product_data.standard_price
                            price_total = price*product_qty
                            # RESTRICCION DE MOVIMIENTOS CON COSTO CERO
                            if price <= 0.0 and pick.company_id.restriction_cost_zero:
                                raise osv.except_osv(_('Error !'), _("El movimiento que esta tratando de transferir tiene un costo menor o igual a cero, por favor valide con el area encargada."))
                            cr.execute(''' update stock_move set cost=%s, total_cost=%s, costo_promedio=%s where id=%s''', (price, price_total, price, move.id))
                            continue

                        if pick.picking_type_id.code == "customer":
                            raise osv.except_osv(_('Configuration !'), _("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento."))

                        output_account_id = product_data.property_stock_account_output and product_data.property_stock_account_output.id or product_data.categ_id.property_stock_account_output_categ.id
                        if not output_account_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de salida de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name))

                        account_id = (product_data.cogs_account_id and product_data.cogs_account_id.id) or (product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id) or False

                        if move.product_id.valuation == 'real_time':
                            raise osv.except_osv(_('Configuration !'), _("Cambiar configuracion de evaluacion del producto '%s', modo tiempo real no soportado"  % product_data.name))


                        #COSTO PROMEDIO VENTA
                        price = product_data.standard_price
                        price_total = price*product_qty
                        # RESTRICCION DE MOVIMIENTOS CON COSTO CERO
                        if price <= 0.0 and pick.company_id.restriction_cost_zero:
                            raise osv.except_osv(_('Error !'), _("El movimiento que esta tratando de transferir tiene un costo menor o igual a cero, por favor valide con el area encargada."))
                        cr.execute(''' update stock_move set cost=%s, total_cost=%s, costo_promedio=%s where id=%s''', (price, price_total, price, move.id))

                        cr_move_val = {
                            'company_id': company_id,
                            'journal_id': journal_id.id,
                            'name': product_data.default_code or product_data.name,
                            'ref': product_data.name,
                            'ref1': product_data.name,
                            'period_id': period_id,
                            'account_id': output_account_id,
                            'analytic_account_id': move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False,
                            'partner_id': partner_id.id,
                            'debit': 0.0,
                            'credit': price_total,
                            'date': picking_date,
                            'tax_code_id': False,
                            'base_code_id': False,
                        }
                        dr_move_val = cr_move_val.copy()
                        dr_move_val.update({
                            'account_id': account_id,
                            'credit': 0.0,
                            'debit': price_total,
                        })
                        move_line_in.append(dr_move_val)
                        move_line_in.append(cr_move_val)
                elif not costo_por_bodega:
                    # COSTO PROMEDIO MOVIMIENTOS INTERNOS
                    price = product_data.standard_price
                    price_total = price*product_qty

                    # RESTRICCION DE MOVIMIENTOS CON COSTO CERO
                    if product_data.type == "product" and price <= 0.0 and pick.company_id.restriction_cost_zero:
                        raise osv.except_osv(_('Error !'), _("El producto que esta tratando de transferir tiene un costo menor o igual a cero, por favor valide con el area encargada."))
                    cr.execute(''' update stock_move set cost=%s, total_cost=%s, costo_promedio=%s where id=%s''', (price, price_total, price, move.id))



            if move_line_in and not refund:
                move = {
                    'line_id': [],
                    'journal_id': journal_id.id,
                    'date': picking_date,
                    'period_id': period_id,
                }
                move_id = account_move_obj.create(cr, uid, move, context=context)
                cr.execute(''' UPDATE stock_picking SET  account_move_id = %s WHERE id = %s''',(move_id, pick.id))
                if journal_id.no_agrupar:
                    array = []
                    for x in move_line_in:
                        if not x['account_id']:
                            raise Warning("No se ha especificado una cuenta para la transaccion")
                        cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, period_id, account_id, analytic_account_id, partner_id, debit, credit, date, tax_code_id, base_code_id, state) VALUES
                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''' , (move_id, company_id, journal_id.id, x['name'], period_id, x['account_id'], x['analytic_account_id'] or None, partner_id.id, float(x['debit']), float(x['credit']), x['date'], x['tax_code_id'] or None, x['base_code_id'] or None, 'valid'))
                else:
                    group_move_line = self.group_lines(cr, uid, move_line_in)
                    account_move_obj.write(cr, uid, [move_id], {'line_id': group_move_line})
                account_move_obj.post(cr, uid, [move_id])

            #IMPORTACIONES
            purchase = self.pool('purchase.order').search(cr, uid, [('name','=',pick.origin)], context=context, limit=1)
            if purchase and pick.picking_type_code == 'incoming':
                purchase = self.pool('purchase.order').browse(cr, uid, purchase, context=context)
                try:
                    if purchase and purchase.import_id and pick.account_move_id:
                        cr.execute(''' UPDATE account_move_line SET import_id=%s WHERE move_id=%s''', (purchase.import_id.id, pick.account_move_id.id))
                except:
                    print "EMPRESA NO TIENE EL MODULO DE IMPORTACIONES"
            #DEVOLUCIONES
            try:
                if pick.dev_id:
                    cr.execute(''' update return_order set user_transfer=%s, date_transfer=%s where id=%s''', (uid, datetime.now(), pick.dev_id.id))
            except:
                print "EMPRESA NO TIENE EL MODULO DE DEVOLUCIONES"


        # ESTA FUNCION ES LA ENCARGADA DE VALIDAR EL CAMPO automatic_invoice Y PERMITE GENERAR LA FACTURA DE FORMA DIRECTA DESDE LA TRANSFERENCIA.
        for pick in self.browse(cr, uid, picking_ids, context=context):
            ot=False
            try:
                ot = pick.ot
            except:
                ot = False
            if pick.account_move_id and ot:
                cr.execute(''' UPDATE stock_move SET  ot=%s WHERE picking_id=%s''',(pick.ot.id,pick.id))
                if pick.picking_type_id.code == 'outgoing':
                    account_id = pick.picking_type_id.default_location_dest_id.valuation_out_account_id and pick.picking_type_id.default_location_dest_id.valuation_out_account_id.id or False
                    if not account_id:
                        raise osv.except_osv(_('Warning!'), _("Un movimiento de salida asociado a una OT debe tener configurada la cuenta de valorizacion de existencias (saliente) en la ubicacion destino '%s'. Por favor realice la configuracion o consulte con el area encargada.") % (pick.picking_type_id.default_location_dest_id.name))
                    cr.execute(''' UPDATE account_move_line SET  account_id=%s, ot=%s WHERE move_id=%s AND debit > 0.0 AND credit <= 0.0 ''',(account_id,pick.ot.id,pick.account_move_id.id))
                elif pick.picking_type_id.code in ['incoming','return']:
                    account_id = pick.picking_type_id.default_location_src_id.valuation_in_account_id and pick.picking_type_id.default_location_src_id.valuation_in_account_id.id or False
                    if not account_id:
                        raise osv.except_osv(_('Warning!'), _("Un movimiento de entrada asociado a una OT debe tener configurada la cuenta de valorizacion de existencias (entrante) en la ubicacion origen '%s'. Por favor realice la configuracion o consulte con el area encargada.") % (pick.picking_type_id.default_location_src_id.name))
                    cr.execute(''' UPDATE account_move_line SET  account_id=%s, ot=%s WHERE move_id=%s AND credit > 0.0 AND debit <= 0.0 ''',(account_id,pick.ot.id,pick.account_move_id.id))



            # FUNCION ENCARGADA DE GUARDAR EL COSTO PROMEDIO DEL MOVIMIENTO FUTURO, ES IMPORTANTE PARA EL INFORME VALORIZADO
            move_return = True
            for move in pick.move_lines:
                if move.location_dest_id.usage == 'supplier':
                    move_return=False
                if costo_por_bodega:
                    context.update({'warehouse':self.pool.get('stock.location').get_warehouse(cr, uid, move.location_id, context=context)})
                costo_promedio = move.product_id.standard_price
                cr.execute(''' UPDATE stock_move SET  costo_promedio=%s WHERE id=%s''',(costo_promedio, move.id))
            if pick.company_id and pick.company_id.automatic_invoice and pick.picking_type_id.code in ['return','outgoing'] and move_return:
                partner = pick.partner_id and pick.partner_id.parent_id and  pick.partner_id.parent_id.id or pick.partner_id.id
                if not partner:
                    raise osv.except_osv(_('Configuration !'), _("No se encontro un tercero para la factura."))
                else:
                    partner = self.pool.get('res.partner').browse(cr, uid, partner, context=context)
                if not partner.property_account_receivable:
                    raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta por cobrar del tercero '%s'."  % partner.name))
                if not partner.property_account_position:
                    raise osv.except_osv(_('Configuration !'), _("Debe configurar la posicion fiscal del tercero '%s'."  % partner.name))

                payment_term = partner.property_payment_term and partner.property_payment_term.id

                if pick.picking_type_id.code == 'return':
                    if not pick.picking_type_id.journal_return_invoice_id:
                        continue
                    else:
                        vals = {
                            'comment': pick.note or '',
                            'user_id': uid,
                            'origin': pick.origin,
                            'stock_picking_id': pick.id,
                            'company_id': pick.company_id.id,
                            'partner_id': partner.id,
                            'fiscal_position': partner.property_account_position.id,
                            'payment_term': payment_term or None,
                            'partner_shipping_id': pick.partner_id.id,
                            'journal_id': pick.picking_type_id.journal_return_invoice_id.id,
                            'account_id': partner.property_account_receivable.id,
                            'currency_id': pick.company_id.currency_id.id,
                            'type': 'out_refund',
                            'date_invoice': datetime.now().date(),
                            }
                        invoice_id = self.pool.get('account.invoice').create(cr, uid, vals, context=context)
                        cr.execute(''' UPDATE stock_picking SET picking_invoice_id=%s, invoice_state='invoiced' WHERE id = %s''',(invoice_id, pick.id))
                        self.compute_invoice(cr, uid, picking_ids, invoice_id, context=context)
                else:
                    sale_id = self.pool.get('sale.order').search(cr, uid, [('name','=',pick.origin)], limit=1, context=context)

                    if not sale_id:
                        currency_id = pick.company_id.currency_id.id
                    else:
                        sale_id = self.pool.get('sale.order').browse(cr, uid, sale_id, context=context)
                        currency_id = sale_id.currency_id.id
                        if sale_id.payment_term:
                            payment_term = sale_id.payment_term.id

                    if not pick.picking_type_id.journal_invoice_id:
                        continue
                    else:
                        vals = {
                            'comment': pick.note or '',
                            'user_id': sale_id.user_id and sale_id.user_id.id or uid,
                            'origin': pick.origin,
                            'stock_picking_id': pick.id,
                            'company_id': pick.company_id.id,
                            'partner_id': partner.id,
                            'fiscal_position': partner.property_account_position.id,
                            'payment_term': payment_term or None,
                            'partner_shipping_id': pick.partner_id.id,
                            'journal_id': pick.picking_type_id.journal_invoice_id.id,
                            'account_id': partner.property_account_receivable.id,
                            'currency_id': currency_id,
                            'type': 'out_invoice',
                            'date_invoice': datetime.now().date(),
                            }
                        invoice_id = self.pool.get('account.invoice').create(cr, uid, vals, context=context)
                        if sale_id:
                            self.pool.get('sale.order').write(cr, uid, [sale_id.id], {'invoice_ids': [(6, 0, [invoice_id])]}, context=context)
                            cr.execute(''' UPDATE sale_order SET shipped=%s WHERE id = %s''',(True, sale_id.id))
                        cr.execute(''' UPDATE stock_picking SET picking_invoice_id=%s, invoice_state='invoiced' WHERE id = %s''',(invoice_id, pick.id))
                        self.compute_invoice(cr, uid, picking_ids, invoice_id, context=context)
                        if pick.company_id.automatic_valid:
                            wf_service = openerp.netsvc.LocalService("workflow")
                            wf_service.trg_validate(uid, 'account.invoice', invoice_id, 'invoice_open', cr)
        return res

    def inv_line_characteristic_hashcode(self, invoice_line):
        return '"%s","%s","%s"'%(invoice_line['account_id'],invoice_line['tax_code_id'],invoice_line['base_code_id'])

    def group_lines(self, cr, uid, line):
        line2 = {}
        for l in line:
            tmp = self.inv_line_characteristic_hashcode(l)
            if tmp in line2:
                am = line2[tmp]['debit'] - line2[tmp]['credit'] + (l['debit'] - l['credit'])
                line2[tmp]['debit'] = (am > 0) and am or 0.0
                line2[tmp]['credit'] = (am < 0) and -am or 0.0
                line2[tmp]['name'] += ', '+l['name']
            else:
                line2[tmp] = l
        line = []
        for key, val in line2.items():

            line.append((0,0,val))
        return line

    def action_transit(self, cr, uid, ids, context=None):
        res = super(StockPicking, self).action_transit(cr, uid, ids, context)
        period_obj = self.pool.get('account.period')
        account_move_obj = self.pool.get('account.move')
        total_move_line = []
        picking_date = False
        journal_id = False
        for picking in self.browse(cr, uid, ids, context):
            if picking.type != 'internal':
                continue
            picking_date = picking.date
            for move in picking.move_lines:
                journal_id = move.product_id.categ_id.property_stock_journal
                if not journal_id:
                    raise osv.except_osv(_('Configuration !'), _("Stock Journal not define in %s product category"  % move.product_id.categ_id.name))
                if not move.location_id.account_location_id:
                    raise osv.except_osv(_('Configuration !'), _("Account not define in %s source location"  % move.location_id.name))
                if not move.location_dest_id.account_location_id:
                    raise osv.except_osv(_('Configuration !'), _("Account not define in %s destination location"  % move.location_dest_id.name))
                period_ids = period_obj.find(cr, uid, dt=picking.date, context=context)
                tax_amount = move.product_id.standard_price * move.product_qty
                move_line = {
                    'company_id': picking.company_id.id,
                    'journal_id': journal_id.id,
                    'name': 'Transit Product',
                    'period_id': period_ids[0],
                    'account_id': move.location_id.account_location_id.id,
                    'partner_id': picking.partner_id and picking.partner_id.id,
                    'quantity': move.product_qty,
                    'debit': 0.0,
                    'credit': tax_amount,
                    'date': move.date_expected,
                    'amount_currency': 0.0,
                    'currency_id': False,
                }
                total_move_line.append(move_line)
                cr_move_val = move_line.copy()
                cr_move_val.update({'account_id': move.location_dest_id.account_location_id.id,
                                  'credit': 0.0,
                                  'debit': tax_amount})
                total_move_line.append(cr_move_val)
        if total_move_line:
            move = {
                'line_id': [],
                'journal_id': journal_id.id,
                'date': picking_date,
            }
            move_id = account_move_obj.create(cr, uid, move, context=context)
            if journal_id.group_invoice_lines:
                total_move_line = self.group_lines(cr, uid, total_move_line)
            account_move_obj.write(cr, uid, [move_id], {'line_id': total_move_line})
            account_move_obj.post(cr, uid, [move_id])
        return res

    @api.multi
    def compute_invoice(self, invoice_id):
        stk_move_obj = self.env['stock.move']
        invoice = self.env['account.invoice'].browse(invoice_id)
        section_id = invoice.type == 'out_invoice' and invoice.user_id and invoice.user_id.default_section_id and \
                     invoice.user_id.default_section_id.id or False
        partner_shipping = self.partner_id
        currency_rate = 1
        account_id = False
        if self:
            self.env.cr.execute(u"UPDATE account_invoice SET comment = '%s' WHERE id = %s" % (self.note, invoice.id))
            group = {}
            code = self.picking_type_id.code
            moves_lines = self.move_lines.filtered(lambda x: x.state in ['done'])
            p_serv = any('service' == x.product_id.type for x in moves_lines)
            for move_line in moves_lines:  # TODO
                partner_shipping = stk_move_obj._get_partner_shipping_id(move_line) or \
                                   (partner_shipping if type(partner_shipping).__name__ == 'int' else partner_shipping.id)
                currency_rate = stk_move_obj._get_currency_order(move_line)
                product = move_line.product_id
                product_uom = move_line.product_uom
                product_uos = move_line.product_uos
                if not invoice.company_id.uom_uos_invoice:
                    uos_id = product_uom or product_uos
                    quantity = move_line.product_qty
                else:
                    if move_line.purchase_line_id.product_uom == product_uom:
                        uos_id = product_uom or product_uos
                        quantity = move_line.product_qty
                    else:
                        uos_id = product_uos or product_uom
                        quantity = move_line.product_uos_qty

                if not p_serv and code == 'outgoing' and getattr(invoice.company_id, 'electronic_invoice', None) and \
                        getattr(invoice.company_id, 'receipt_notice', None) and invoice.company_id.receipt_notice and \
                        partner_shipping.electronic_invoice and partner_shipping.receipt_notice:
                    quantity = move_line.received_amount

                if move_line.purchase_line_id.product_uom.id != move_line.purchase_line_id.product_id.uom_id.id:
                    # quantity = move_line.purchase_line_id.product_qty # Aqui
                    quantity = move_line.product_uom_qty

                account_analytic = stk_move_obj._get_account_analytic_invoice(invoice.stock_picking_id, move_line)
                account_analytic_id = account_analytic and account_analytic.id or False
                ########
                aap = avancys_orm.fetchall(self._cr,
                                   "SELECT id from ir_module_module where name = 'account_analytic_project' "
                                   "and state = 'installed'")
                if aap:
                    project_id = move_line.project_id and move_line.project_id.id or False
                else:
                    project_id = False
                ########
                discount = stk_move_obj._get_discount_invoice(move_line)
                if code == 'incoming':
                    if move_line.origin_returned_move_id.picking_id:
                        account_id = product.account_return_id.id or product.categ_id.account_return_id.id
                        if not account_id:
                            raise Warning("La cuenta de Devolucion no esta definida en el producto '%s' ni en su "
                                          "categoria" % product.name)
                    else:
                        if product.type == 'product':
                            account_id = invoice.partner_id.accrued_account_payable_id.id or False
                            if not account_id:
                                raise Warning("Debe configurar la cuenta puente del Proveedor '%s'" %
                                              invoice.partner_id.name)
                        else:
                            if account_analytic and account_analytic.costo_gasto == 'costo':
                                account_id = product.costo_account_property.id or \
                                             product.categ_id.property_account_costos_categ.id
                                if not account_id:
                                    raise Warning("La cuenta de costo no esta definida en el producto '%s' "
                                                  "ni en su categoria" % product.name)
                            elif account_analytic and account_analytic.costo_gasto == 'gasto_venta':
                                account_id = product.gasto_venta_property_id.id or \
                                             product.categ_id.gasto_venta_property_id.id
                                if not account_id:
                                    raise Warning("La cuenta de gasto de venta no esta definida en el producto "
                                                  "'%s' ni en su categoria" % product.name)
                            else:
                                account_id = product.property_account_expense.id or \
                                             product.categ_id.property_account_expense_categ.id
                                if not account_id:
                                    raise Warning("La cuenta de gasto no esta definida en el producto '%s' ni en su "
                                                  "categoria" % product.name)
                elif code == 'outgoing':
                    account_id = product.property_account_income.id or \
                                 product.categ_id.property_account_income_categ.id
                    # Devolucion en Compras
                    if self.location_id.usage == "internal" and self.location_dest_id.usage == "supplier":
                        if not invoice.partner_id.accrued_account_payable_id:
                            raise Warning("El sistema debe contar con la parametrizacion de la cuenta puente recepcion "
                                          "del tercero '%s', se sugiere una cuenta del pasivo 26." %
                                          invoice.partner_id.name)
                        account_id = invoice.partner_id.accrued_account_payable_id.id

                    if not account_id:
                        raise Warning("La cuenta de ingreso no esta definida en el producto '%s' ni en su categoria"
                                      % product.name)
                    if invoice.company_id.analytic_default:
                        account_analytic_id = move_line.sale_line_id.account_analytic_id.id
                        if not account_analytic_id:
                            self.env.cr.execute("SELECT analytic_id FROM account_analytic_default WHERE product_id = %s "
                                                "AND user_id = %s LIMIT 1" % (product.id, self.create_uid.id or False))
                            analytic_id = self.env.cr.fetchone()
                            if analytic_id[0]:
                                self.env.cr.execute("UPDATE stock_move SET account_analytic_id = %s WHERE id = %s" %
                                                    (analytic_id[0], move_line.id))
                            else:
                                raise Warning("El sistema esta configurado para requerir la cuenta analitica en el "
                                              "proceso de remision, sin embargo no logra encontrar una cuenta para el "
                                              "producto '%s' y el usuario '%s'. Esto puede ser porque no tiene valores "
                                              "predeterminados 'CONSULTAR CON EL AREA ENCARGADA' o porque el pedido "
                                              "de venta fue generado por un usuario que no es comercial" %
                                              (product.default_code, self.create_uid.name))
                elif code == 'return':
                    account_id = product.account_return_id.id or product.categ_id.account_return_id.id
                    if not account_id:
                        raise Warning("La cuenta de Devolucion no esta definida en el producto '%s' ni en su "
                                      "categoria" % product.name)
                    invoice.type = 'out_refund'

                if invoice.company_id.line_for_sale and code == 'outgoing':
                    group = self._calc_invl_group(move_line, product, uos_id, account_analytic_id, discount,
                                                  account_id, invoice, group, quantity, stk_move_obj, code, True,
                                                  project_id=project_id)
                else:
                    group = self._calc_invl_group(move_line, product, uos_id, account_analytic_id, discount,
                                                  account_id, invoice, group, quantity, stk_move_obj, code, False,
                                                  project_id=project_id)
            # ELIMINANDO ACCOUNT INVOICE LINE
            self.env.cr.execute("DELETE FROM account_invoice_line WHERE invoice_id = %s" % invoice.id)
            inv_aut = 0
            for key in group.values():
                key['stock_move_ids'] = [(6, 0, key['stock_move_ids'])]
                if float(key['quantity']) > 0:
                    invl_pu = float(key['price_unit'])
                    invl_qty = float(key['quantity'])
                    inv_aut += invl_pu * invl_qty
                    sql = u"INSERT INTO account_invoice_line (invoice_id, product_id, name, quantity, price_unit, " \
                           "discount, uos_id, lot_ids, account_id, account_analytic_id) VALUES ({iid},{pid},'{nam}'," \
                          "{qty},{pui},{dis},{uos},'{lid}',{aid},{aai}) RETURNING id".format(iid=key['invoice_id'],
                           pid=key['product_id'], nam=key['name'], qty=invl_qty, pui=invl_pu, dis=float(key['discount']),
                           uos=key['uos_id'], lid=key['lot_ids'], aid=key['account_id'], aai=key['account_analytic_id']
                                                                                            or 'Null')
                    if 'asset_category_id' in key:
                        pos1 = sql.find(") V")
                        pos2 = sql.find(") R")
                        sql = sql[:pos1] + ',asset_category_id' + sql[pos1:pos2] + ',' + \
                              str(key['asset_category_id'] or None) + sql[pos2:]
                    self.env.cr.execute(sql)
                    invoice_line = self.env.cr.fetchone()[0]
                    self.env['account.invoice.line'].browse(invoice_line).write({'invoice_line_tax_id':
                                               key['invoice_line_tax_id'], 'stock_move_ids': key['stock_move_ids']})
                    ######
                    aap = avancys_orm.fetchall(self._cr,
                                       "SELECT id from ir_module_module where name = 'account_analytic_project' "
                                       "and state = 'installed'")
                    if aap:
                        self.env['account.invoice.line'].browse(invoice_line).write({'project_id': key['project_id']})
                    ######
                    if invoice.type == 'out_invoice':
                        #vincular sale lines
                        moves_objects = stk_move_obj.browse(key['stock_move_ids'][0][2])
                        for move_line in moves_objects:
                            move_line.procurement_id.sale_line_id.write({'invoice_lines': [(4, invoice_line)]})
                        self.env.cr.execute(u"UPDATE product_product SET document_sale = '%s', partner_sale = '%s', "
                                            "date_sale = '%s', qty_sale = %s, price_sale = %s WHERE id = %s" %
                                            (self.origin or self.name, invoice.partner_id.id, datetime.now().date(),
                                             key['quantity'], key['price_unit'], key['product_id']))
                    elif invoice.type == 'in_invoice':
                        #vincular purchase lines
                        moves_objects = stk_move_obj.browse(key['stock_move_ids'][0][2])
                        for move_line in moves_objects:
                            move_line.purchase_line_id.write({'invoice_lines': [(4, invoice_line)]})
                        self.env.cr.execute(u"UPDATE product_product SET document_purchase = '%s', partner_purchase = "
                                            "'%s', date_purchase = '%s', qty_purchase = %s, cost_purchase = %s "
                                            "WHERE id = %s" % (self.origin or self.name, invoice.partner_id.id,
                                            datetime.now().date(), key['quantity'], key['cost'], key['product_id']))
            invoice.amount_untaxed = inv_aut
            invoice.amount_total = inv_aut
        if isinstance(invoice_id, (list, tuple)):
            invoice_id = invoice_id[0]
        else:
            invoice_id = invoice_id
        # TODO
        self.env.cr.execute("UPDATE account_invoice SET  partner_shipping_id = %s, check_total = %s, tasa_manual = %s, "
                            "es_multidivisa = %s WHERE id = %s" %
                            ((partner_shipping if type(partner_shipping).__name__ == 'int' else partner_shipping.id),
                             0, currency_rate, currency_rate != 1, invoice_id))
        if section_id and invoice_id:
            invoice.section_id = section_id
        if not self._context.get('no_reset_taxes', False):
            invoice.button_reset_taxes()
        return invoice_id

    def action_invoice_create(self, cr, uid, ids, journal_id, group=False, type='out_invoice', context=None):
        context = context or {}
        res = super(StockPicking, self).action_invoice_create(cr, uid, ids, journal_id, group, type, context=context)
        ctx = context.copy()
        if ctx.get('active_model', False) == 'stock.picking' and ctx.get('inv_type', False) == 'in_invoice':
            ctx["no_reset_taxes"] = True
        self.compute_invoice(cr, uid, ids, res, context=ctx)
        return res

    # SE SUPERPONE LA FUNCION ORIGINAL POR DESEMPE�O //PATH/odoo/addons/sotck_account/stock.py
    def _invoice_create_line(self, cr, uid, moves, journal_id, inv_type='out_invoice', context=None):
        invoice_obj = self.pool.get('account.invoice')
        move_obj = self.pool.get('stock.move')
        invoices = {}
        for move in moves:
            picking = move.picking_id
            company = move.company_id
            origin = move.picking_id.name
            partner, user_id, currency_id = move_obj._get_master_data(cr, uid, move, company, context=context)

            key = (partner, currency_id, company.id, user_id)
            invoice_vals = self._get_invoice_vals(cr, uid, key, inv_type, journal_id, move, context=context)

            if key not in invoices:
                # Get account and payment terms
                invoice_id = self._create_invoice_from_picking(cr, uid, move.picking_id, invoice_vals, context=context)
                invoices[key] = invoice_id
            else:
                invoice = invoice_obj.browse(cr, uid, invoices[key], context=context)
                merge_vals = {}
                if not invoice.origin or invoice_vals['origin'] not in invoice.origin.split(', '):
                    invoice_origin = filter(None, [invoice.origin, invoice_vals['origin']])
                    merge_vals['origin'] = ', '.join(invoice_origin)
                if invoice_vals.get('name', False) and (not invoice.name or invoice_vals['name'] not in invoice.name.split(', ')):
                    invoice_name = filter(None, [invoice.name, invoice_vals['name']])
                    merge_vals['name'] = ', '.join(invoice_name)
                if merge_vals:
                    invoice.write(merge_vals)
            invoice_line_vals = {}
            invoice_line_vals['account_id'] = invoice_vals['account_id']
            invoice_line_vals['invoice_id'] = invoices[key]
            invoice_line_vals['origin'] = origin
            invoice_line_vals['name'] = origin

            move_obj._upd_orig_doc(cr, uid, move, invoice_line_vals, context=context)
            cr.execute("UPDATE stock_move SET  invoice_state = 'invoiced' WHERE id = %s" % move.id)
        cr.execute("UPDATE stock_picking SET  invoice_state = 'invoiced' WHERE id = %s" % picking.id)
        return invoices.values()    
    

class account_invoice(models.Model):
    _inherit = "account.invoice"

    stock_picking_id=fields2.Many2one('stock.picking', string='Stock Move')
    
    @api.multi
    def action_move_create(self):
        res = super(account_invoice, self).action_move_create()
        try:
            sale_stock_picking = self.sale_stock_picking
        except:
            sale_stock_picking = False
            
        if self.type == 'out_invoice' and self.move_id and not self.stock_picking_id and sale_stock_picking:
            dt_created = self.move_id.date
            partner = self.partner_id
            m_id = self.move_id.id
            journal = self.journal_id
            period = self.period_id
            base_line = self.move_id.line_id[0]
            central = base_line.centralisation
            blocked = base_line.blocked
            for line in self.invoice_line:
                total_cost = 0.0
                if line.product_id.type == 'product':
                    if self.type == 'out_invoice':
                        account_credit_id = line.product_id.categ_id.account_production_transit_id and \
                                            line.product_id.categ_id.account_production_transit_id.id or False
                        if not account_credit_id:
                            raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta de producto en "
                                                                         "proceso de la categoria '%s' para realizar "
                                                                         "el reconocimiento de producto donde el "
                                                                         "cliente" % line.product_id.categ_id.name))
                            
                        account_debit_id = (line.product_id.cogs_account_id and line.product_id.cogs_account_id.id) or \
                                           (line.product_id.categ_id.cogs_account_id and
                                            line.product_id.categ_id.cogs_account_id.id) or False
                    
                        if not account_debit_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de costo de venta no esta definida "
                                                                         "en el producto '%s' ni en su categoria"
                                                                         % line.product_id.name))
                    else:
                        account_debit_id = line.product_id.categ_id.account_production_transit_id and \
                                           line.product_id.categ_id.account_production_transit_id.id or False
                        if not account_debit_id:
                            raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta de producto en "
                                                                         "proceso de la categoria '%s' para realizar "
                                                                         "el reconocimiento de producto donde el "
                                                                         "cliente"  % line.product_id.categ_id.name))
                        
                        account_credit_id = (line.product_id.cogs_account_id and line.product_id.cogs_account_id.id) \
                                            or (line.product_id.categ_id.cogs_account_id and
                                                line.product_id.categ_id.cogs_account_id.id) or False
                    
                        if not account_credit_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de costo de venta no esta definida "
                                                                         "en el producto '%s' ni en su categoria"
                                                                         % line.product_id.name))
                    
                    if line.stock_move_ids:
                        for move in line.stock_move_ids.filtered(lambda x: x.state in ['done']):
                            total_cost += move.total_cost

                    damlcd = {
                        'date_created': dt_created,
                        'partner_id': partner.id,
                        'name': line.product_id.default_code or line.product_id.name,
                        'ref': line.product_id.name[:31],
                        'ref1': line.product_id.name[:31],
                        'date': dt_created,
                        'credit': total_cost,
                        'debit': 0,
                        'account_id': account_credit_id,
                        'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
                        'amount_currency': 0,
                        'currency_id': False,
                        'move_id': m_id,
                        'journal_id': journal.id,
                        'period_id': period.id,
                        'state': 'valid',
                        'centralisation': central,
                        'blocked': blocked
                        }

                    damldd = {
                        'date_created': dt_created,
                        'partner_id': partner.id,
                        'name': line.product_id.default_code or line.product_id.name,
                        'ref': line.product_id.name[:31],
                        'ref1': line.product_id.name[:31],
                        'date': dt_created,
                        'credit': 0,
                        'debit': total_cost,
                        'account_id': account_debit_id,
                        'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
                        'amount_currency': 0,
                        'currency_id': False,
                        'move_id': m_id,
                        'journal_id': journal.id,
                        'period_id': period.id,
                        'state': 'valid',
                        'centralisation': central,
                        'blocked': blocked
                        }
                    avancys_orm.direct_create(self._cr, self._uid, 'account_move_line', [damlcd, damldd], company=True)
        
        if self.type in ['out_invoice', 'out_refund'] and self.move_id and self.company_id.sale_cost_invoice:
            dt_created = self.move_id.date
            partner = self.partner_id
            m_id = self.move_id.id
            journal = self.journal_id
            period = self.period_id
            base_line = self.move_id.line_id[0]
            central = base_line.centralisation
            blocked = base_line.blocked
            for line in self.invoice_line:
                total_cost = 0.0
                if line.product_id.type == 'product':
                    if self.type == 'out_invoice':
                        account_credit_id = (line.product_id.property_stock_account_output and
                                             line.product_id.property_stock_account_output.id) or \
                                            (line.product_id.categ_id.property_stock_account_output_categ and
                                             line.product_id.categ_id.property_stock_account_output_categ.id) or False
                        if not account_credit_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de salida de inventario no esta "
                                                                         "definida en el producto '%s' ni en su "
                                                                         "categoria" % line.product_id.name))
                        
                        account_debit_id = (line.product_id.cogs_account_id and line.product_id.cogs_account_id.id) or \
                                           (line.product_id.categ_id.cogs_account_id and
                                            line.product_id.categ_id.cogs_account_id.id) or False
                    
                        if not account_debit_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de costo de venta no esta definida "
                                                                         "en el producto '%s' ni en su categoria"
                                                                         % line.product_id.name))
                    else:
                        account_debit_id = (line.product_id.property_stock_account_output and
                                            line.product_id.property_stock_account_output.id) or \
                                           (line.product_id.categ_id.property_stock_account_output_categ and
                                            line.product_id.categ_id.property_stock_account_output_categ.id) or False
                        if not account_debit_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de salida de inventario no esta "
                                                                         "definida en el producto '%s' ni en su "
                                                                         "categoria" % line.product_id.name))
                        
                        account_credit_id = (line.product_id.cogs_account_id and line.product_id.cogs_account_id.id) \
                                            or (line.product_id.categ_id.cogs_account_id and
                                                line.product_id.categ_id.cogs_account_id.id) or False
                    
                        if not account_credit_id:
                            raise osv.except_osv(_('Configuration !'), _("La cuenta de costo de venta no esta definida "
                                                                         "en el producto '%s' ni en su categoria"
                                                                         % line.product_id.name))
                    
                    for move in line.stock_move_ids.filtered(lambda x: x.state in ['done']):
                        if move._fields.get('novelty_amount', False):
                            total_cost += move.total_cost if not move.novelty_amount or move.novelty_amount == 0 else \
                                (move.received_amount * move.cost)
                        else:
                            total_cost += move.total_cost

                    damlcd = {
                        'date_created': dt_created,
                        'partner_id': partner.id,
                        'name': line.product_id.default_code or line.product_id.name,
                        'ref': line.product_id.name[:31],
                        'ref1': line.product_id.name[:31],
                        'date': dt_created,
                        'credit': total_cost,
                        'debit': 0,
                        'account_id': account_credit_id,
                        'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
                        'amount_currency': 0,
                        'currency_id': False,
                        'move_id': m_id,
                        'journal_id': journal.id,
                        'period_id': period.id,
                        'state': 'valid',
                        'centralisation': central,
                        'blocked': blocked
                        }

                    damldd = {
                        'date_created': dt_created,
                        'partner_id': partner.id,
                        'name': line.product_id.default_code or line.product_id.name,
                        'ref': line.product_id.name[:31],
                        'ref1': line.product_id.name[:31],
                        'date': dt_created,
                        'credit': 0,
                        'debit': total_cost,
                        'account_id': account_debit_id,
                        'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
                        'amount_currency': 0,
                        'currency_id': False,
                        'move_id': m_id,
                        'journal_id': journal.id,
                        'period_id': period.id,
                        'state': 'valid',
                        'centralisation': central,
                        'blocked': blocked
                        }
                    avancys_orm.direct_create(self._cr, self._uid, 'account_move_line', [damlcd, damldd], company=True)
        
        # Modifica fecha de inventario y fecha de contabilizacion, segun la validacion de la factura
        if self.company_id.move_date_invoice and self.type == 'out_invoice' and self.stock_picking_id:
            if self.stock_picking_id.account_move_id:
                self._cr.execute(''' UPDATE account_move SET date=%s, period_id=%s WHERE id=%s''',
                            (self.date_invoice, self.period_id.id, self.stock_picking_id.account_move_id.id))
                self._cr.execute(''' UPDATE account_move_line SET date=%s, period_id=%s, state='valid' WHERE move_id=%s''',                            (self.date_invoice,self.period_id.id,self.stock_picking_id.account_move_id.id))
                        
            self._cr.execute(''' UPDATE stock_move SET date=%s WHERE picking_id=%s''',(self.date_invoice+' '+self.write_date[11:19],self.stock_picking_id.id))
        return res    
    
    def recompute_stock_picking(self, cr, uid, ids, context=None):
        picking_pool = self.pool.get('stock.picking')
        for invoice in self.browse(cr, uid, ids, context=context):
            if invoice.stock_picking_id:
                picking_pool.compute_invoice(cr, uid, ids, invoice.id, context=context)
        return True
    
    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default['stock_picking_id'] = False
        return super(account_invoice, self).copy(cr, uid, id, default, context)

    def get_converted_curr_amt(self, cr, uid, from_currency, to_from_currency, amount, context=None):
        if not context: context = {}
        currency_obj = self.pool.get('res.currency')
        diff_currency_p = False
        if from_currency != to_from_currency:
            diff_currency_p = from_currency
        if diff_currency_p:
            amount_currency = currency_obj.compute(cr, uid, from_currency, to_from_currency, amount, round=True, context=context)
        else:
            amount_currency = 0.0
        return diff_currency_p, amount_currency

    def get_currency_exchange_diff(self, cr, uid, invoice, purchase_date, invoice_date, amount, context=None):
        ctx = context.copy()
        ctx.update({'date': purchase_date})
        pur_diff_currency_p, pur_amount_currency = self.get_converted_curr_amt(cr, uid, invoice.currency_id.id, invoice.company_id.currency_id.id, amount, context=ctx)
        ctx.update({'date': invoice_date})
        inv_diff_currency_p, inv_amount_currency = self.get_converted_curr_amt(cr, uid, invoice.currency_id.id, invoice.company_id.currency_id.id, amount, context=ctx)
        if pur_diff_currency_p and inv_diff_currency_p:
            return pur_amount_currency - inv_amount_currency
        return 0.0
    
    @api.model
    def line_get_convert(self, line, part, date):
        res = super(account_invoice, self).line_get_convert(line, part, date)
        if line.get('invl_id',False):
            line = self.env['account.invoice.line'].browse(line['invl_id'])
            if line.invoice_id.type == 'in_invoice' and line.invoice_id.stock_picking_id and not line.asset_category_id and line.product_id and line.product_id.type == "product":
                if not line.invoice_id.partner_id.accrued_account_payable_id:
                    raise osv.except_osv(_('Configuration !'), _("La cuenta de pago puente no esta configurada en el proveedor %s "  % line.invoice_id.partner_id.name))
                accrued_acc_id = line.invoice_id.partner_id.accrued_account_payable_id.id
                res.update({'account_id': accrued_acc_id})
        return res
    
    def inv_line_new_characteristic_hashcode(self, invoice_line):
        """Overridable hashcode generation for invoice lines. Lines having the same hashcode
        will be grouped together if the journal has the 'group line' option. Of course a module
        can add fields to invoice lines that would need to be tested too before merging lines
        or not."""
        return "%s-%s-%s"%(
            invoice_line['account_id'],
            invoice_line.get('analytic_account_id',"False"),
            invoice_line.get('date_maturity',"False"))

    def group_new_lines(self, cr, uid, line):
        line2 = {}
        for l in line:
            tmp = self.inv_line_new_characteristic_hashcode(l)

            if tmp in line2:
                am = line2[tmp]['debit'] - line2[tmp]['credit'] + (l['debit'] - l['credit'])
                line2[tmp]['debit'] = (am > 0) and am or 0.0
                line2[tmp]['credit'] = (am < 0) and -am or 0.0
                line2[tmp]['tax_amount'] += l['tax_amount']
                line2[tmp]['amount_currency'] += l['amount_currency']
            else:
                line2[tmp] = l
        line = []
        for key, val in line2.items():
            line.append((0,0,val))
        return line


class StockMove(models.Model):
    _inherit = "stock.move"
    
    def _upd_orig_doc(self, cr, uid, move, invoice_line_vals, context=None):
        if context.get('inv_type') in ('in_invoice', 'in_refund') and move.purchase_line_id:
            purchase_line = move.purchase_line_id
            self.pool.get('purchase.order').write(cr, uid, [purchase_line.order_id.id],
                                                  {'invoice_ids': [(4, invoice_line_vals['invoice_id'])]})
            purchase_line_obj = self.pool.get('purchase.order.line')
            purchase_obj = self.pool.get('purchase.order')
            invoice_line_obj = self.pool.get('account.invoice.line')
            purchase_id = move.purchase_line_id.order_id.id
            p_cond = [('order_id', '=', purchase_id), ('invoice_lines', '=', False), '|', ('product_id', '=', False),
                      ('product_id.type', '=', 'service')]
            purchase_line_ids = purchase_line_obj.search(cr, uid, p_cond, context=context)
            if purchase_line_ids:
                inv_lines = []
                for po_line in purchase_line_obj.browse(cr, uid, purchase_line_ids, context=context):
                    acc_id = purchase_obj._choose_account_from_po_line(cr, uid, po_line, context=context)
                    inv_line_data = purchase_obj._prepare_inv_line(cr, uid, acc_id, po_line, context=context)
                    inv_line_id = invoice_line_obj.create(cr, uid, inv_line_data, context=context)
                    inv_lines.append(inv_line_id)
                    po_line.write({'invoice_lines': [(4, inv_line_id)]})
                invoice_line_obj.write(cr, uid, inv_lines, {'invoice_id': invoice_line_vals['invoice_id']},
                                       context=context)
        if context.get('inv_type') in ('out_invoice', 'out_refund') and move.procurement_id and \
                move.procurement_id.sale_line_id:
            sale_line = move.procurement_id.sale_line_id
            self.pool.get('sale.order').write(cr, uid, [sale_line.order_id.id],
                                              {'invoice_ids': [(4, invoice_line_vals['invoice_id'])]})
            sale_line_obj = self.pool.get('sale.order.line')
            invoice_line_obj = self.pool.get('account.invoice.line')
            s_cond = [('order_id', '=', move.procurement_id.sale_line_id.order_id.id), ('invoiced', '=', False), '|',
                      ('product_id', '=', False), ('product_id.type', '=', 'service')]
            sale_line_ids = sale_line_obj.search(cr, uid, s_cond, context=context)
            if sale_line_ids:
                created_lines = sale_line_obj.invoice_line_create(cr, uid, sale_line_ids, context=context)
                invoice_line_obj.write(cr, uid, created_lines, {'invoice_id': invoice_line_vals['invoice_id']},
                                       context=context)

    invoice_line_id = fields2.Many2one('account.invoice.line', string='Invoice', readonly=True)
    account_analytic_id = fields2.Many2one('account.analytic.account', string='Cuenta analitica')
    type_product = fields2.Selection(string='Tipo de Compra', related="product_id.type", store=True)

    def get_price_unit(self, cr, uid, move, context=None):
        """ Returns the unit price to store on the quant """
        return move.cost or move.price_unit or move.product_id.standard_price
    
    def check_average_update(self, cr, uid, move, context=None):
        return move.location_id.usage in ['supplier','production'] or context.get('promedio') == True
    
    #funcion de base odoo 8.0 que actualiza el costo promedio, actualmente este se actualiza en do_transfer
    def product_price_update_before_done(self, cr, uid, ids, context=None):
        context = context or {}
        product_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')
        tmpl_dict = {}
        for move in self.browse(cr, uid, ids, context=context):
            new_std_price=move.product_id.standard_price
            #implementacion de precio promedio por bodega
            costo_por_bodega = False
            model_obj = self.pool.get('ir.model').search(cr, uid, [('model','=','product.warehouse.standard.price')], context=context)
            if model_obj:
                costo_por_bodega = True
            
            #adapt standard price on incomming moves if the product cost_method is 'average'
            check = self.check_average_update(cr, uid, move, context=context) or costo_por_bodega
            if (check and move.location_dest_id.usage == 'internal' and move.product_qty > 0):
                product_uom = move.product_uom.id
                qty = move.product_qty
                if costo_por_bodega:
                    context.update({'warehouse': location_obj.get_warehouse(cr, uid, move.location_dest_id, context=context)})
                product_data = product_obj.browse(cr, uid, move.product_id.id, context=context)
                product_cost = move.cost
                new_price = product_cost
                available = product_data.qty_available
                if available <= 0.0001:
                    new_std_price = new_price
                else:
                    amount_unit = product_data.standard_price
                    new_std_price = ((amount_unit * available) + (new_price * qty))/(available + qty)
                    # ( (anterior * anterior_qty) + (nuevo_precio * entrante_qty) )/ (anterior_qty+entrante_qty)
                product_obj.write(cr, uid, [product_data.id], {'standard_price': new_std_price}, context=context)
                #amount_unit = product_data.standard_price
            if not costo_por_bodega:
                cr.execute(''' UPDATE stock_move SET costo_promedio=%s WHERE id=%s''',(new_std_price, move.id))
        return True
    
    #TODO traer valores del sale_line y purchase_line
    def _get_account_analytic_invoice(self, cr, uid, picking, move_line, context=None):
        if move_line.account_analytic_id:
            return move_line.account_analytic_id
        elif move_line.purchase_line_id and move_line.purchase_line_id.account_analytic_id:
            return move_line.purchase_line_id.account_analytic_id
        else:
            return False
    
    def _get_taxes_invoice(self, cr, uid, move_line, type, context=None):        
        if type in ('in_invoice', 'in_refund'):
            taxes = move_line.product_id.supplier_taxes_id_1 or move_line.product_id.categ_id.supplier_taxes_id
        else:
            taxes = move_line.product_id.taxes_id_1 or move_line.product_id.categ_id.taxes_id
        return map(lambda x: x.id, taxes)
    
    def _get_discount_invoice(self, cr, uid, move_line, context=None):
        '''Return the discount for the move line'''
        if move_line.sale_line_id:
            return move_line.sale_line_id.discount
        if move_line.purchase_line_id:
            return move_line.purchase_line_id.discount
        return 0.0
    
    def _get_price_unit_invoice(self, cr, uid, move_line, type, context=None):
        if move_line.sale_line_id:
            res=move_line.sale_line_id.price_unit
        elif move_line.purchase_line_id:
            res=move_line.purchase_line_id.price_unit
        else:
            res=move_line.price_unit
            if move_line.picking_id.picking_type_id.code == 'outgoing':
                sale_order_line = self.pool.get('sale.order.line').search(cr, uid, [('product_id','=',move_line.product_id.id),('order_id.name','=',move_line.picking_id.origin)], limit=1,context=context)
                if sale_order_line:
                    sale_order_line = self.pool.get('sale.order.line').browse(cr, uid, sale_order_line, context=context)
                    res=sale_order_line.price_unit
                    cr.execute(''' UPDATE stock_move SET sale_line_id=%s WHERE id=%s''',(sale_order_line.id, move_line.id))
        return res
        
    def _get_partner_shipping_id(self, cr, uid, move_line, context=None):
        if move_line.sale_line_id:
            res = move_line.sale_line_id.order_id.partner_shipping_id
        elif move_line.purchase_line_id:
            res = move_line.company_id.partner_id
        else:
            res = move_line.partner_id
        return res
        
    def _get_currency_order(self, cr, uid, move_line, context=None):
        if move_line.sale_line_id:
            res = move_line.sale_line_id.order_id.tasa_cambio_pactada
        elif move_line.purchase_line_id:
            res = move_line.purchase_line_id.order_id.rate_pactada
        else:
            res = 1
        return res
    
    def separate_line(self, cr, uid, ids, context=None):
        invoice_line_obj = self.pool.get('account.invoice.line')
        invoice_obj = self.pool.get('account.invoice')
        message_obj = self.pool.get('avancys.message.notificacion')
        res = False
        
        for line in self.browse(cr, uid, ids, context=context):
            if line.invoice_line_id and len(line.invoice_line_id.stock_move_ids) > 1 and line.invoice_line_id.invoice_id.state == 'draft':
                data = invoice_line_obj.copy_data(cr, uid, line.invoice_line_id.id, context=context)
                data['stock_move_ids'] = False
                new_line_id = invoice_line_obj.create(cr, uid, data, context=context)
                self.write(cr, uid, [line.id], {'invoice_line_id': new_line_id}, context=context)
                invoice_line_obj.write(cr, uid, [line.invoice_line_id.id], {'quantity': line.invoice_line_id.quantity - line.product_qty}, context=context)
                invoice_line_obj.write(cr, uid, [new_line_id], {'quantity': line.product_qty}, context=context)
                res = message_obj.new_message(cr, uid, 'Recuerde actualizar la factura', 'Linea Separada', context=context)
        
        return res


class account_invoice_line(models.Model):
    _inherit = "account.invoice.line"
            
    stock_move_id = fields2.Many2one('stock.move', string='Stock Move', readonly=True)
    stock_move_ids = fields2.One2many('stock.move', 'invoice_line_id', string='Stock Moves', readonly=True)
    lot_ids = fields2.Char(string='Lotes', readonly=True)
    
    
class purchase_order(osv.Model):
    _inherit = "purchase.order"
    
    def _prepare_inv_line(self, cr, uid, account_id, order_line, context=None):
        if not context: context = {}
        vals = super(purchase_order, self)._prepare_inv_line(cr, uid, account_id, order_line, context=context)
        account_id = vals.get('account_id', False) 
        if vals.get('product_id'):
            product_data = self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context)
            if product_data.type == 'product':
                if product_data.is_asset: # Caso especifico en carvajal donde se mueven activos por inventario
                    account_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ.id
                else:
                    account_id = order_line.partner_id.accrued_account_payable_id.id
                if not account_id:
                    raise osv.except_osv(_('Configuration !'), _(
                        "The bridge reception account or Stock Input Account not define in %s product or product category" % product_data.name))
        vals.update({'account_id': account_id})

        aap = avancys_orm.fetchall(cr, "SELECT id from ir_module_module where name = 'account_analytic_project' "
                                       "and state = 'installed'")
        if aap:
            if 'project_id' not in vals and order_line.project_id:
                vals['project_id'] = order_line.project_id.id
        return vals


    
#
