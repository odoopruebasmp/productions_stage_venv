# -*- coding: utf-8 -*-
import openerp.netsvc
from openerp.osv import osv, fields
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import date, datetime, timedelta

class quotation_to_order(osv.osv_memory):
    _name = 'quotation.to.order.wizard'
    
    def set_seleccionada(self, cr, uid, ids, context=None):
        line_ids = context.get('active_ids', [])
        quo_line_model = self.pool.get('purchase.quotation.supplier.line')
        for line in quo_line_model.browse(cr, uid, line_ids, context):
            if line.state != 'confirmed':
                raise osv.except_osv(_('Error!'), _('Todas las lineas seleccionadas tienen que estar en estado confirmado'))
            set_seleccionada(self, cr, uid, [line.id], context=None)
        return {'type': 'ir.actions.act_window_close'}
        
    def set_validar(self, cr, uid, ids, context=None):
        line_ids = context.get('active_ids', [])
        quo_line_model = self.pool.get('purchase.quotation.supplier.line')
        for line in quo_line_model.browse(cr, uid, line_ids, context):
            if line.state != 'seleccionada':
                raise osv.except_osv(_('Error!'), _('Todas las lineas seleccionadas tienen que estar en estado seleccionado'))
            set_validar(self, cr, uid, [line.id], context=None)
        return {'type': 'ir.actions.act_window_close'}
        
    def set_rechazada(self, cr, uid, ids, context=None):
        line_ids = context.get('active_ids', [])
        quo_line_model = self.pool.get('purchase.quotation.supplier.line')
        for line in quo_line_model.browse(cr, uid, line_ids, context):
            if line.state != 'seleccionada':
                raise osv.except_osv(_('Error!'), _('Todas las lineas seleccionadas tienen que estar en estado rechazado'))
            set_rechazada(self, cr, uid, [line.id], context=None)
        return {'type': 'ir.actions.act_window_close'}
        
    def undo_seleccion(self, cr, uid, ids, context=None):
        line_ids = context.get('active_ids', [])
        quo_line_model = self.pool.get('purchase.quotation.supplier.line')
        for line in quo_line_model.browse(cr, uid, line_ids, context):
            if line.state not in ['seleccionada','validada','rechazada','no_seleccionada']:
                raise osv.except_osv(_('Error!'), _('Todas las lineas seleccionadas tienen que estar en estado rechazado'))
            undo_seleccion(self, cr, uid, [line.id], context=None)
        return {'type': 'ir.actions.act_window_close'}
    
    def confirm_quotation(self, cr, uid, ids, context=None):
        purchase_requisition = self.pool.get('purchase.requisition')
        order_model = self.pool.get('purchase.order')
        order_line_model = self.pool.get('purchase.order.line')
        quo_line_model = self.pool.get('purchase.quotation.supplier.line')
        line_ids = context.get('active_ids', [])
        ordenes_agrupadas = {}
        req_id = []
        for line in quo_line_model.browse(cr, uid, line_ids, context):
            if line.state != 'validada':
                raise osv.except_osv(_('Error!'), _('Todas las lineas seleccionadas tienen que estar validadas'))
            supplier = line.supplier_id
            picking_type = line.requisition_line_id.requisition_id.picking_type_id.id
            key = (supplier,picking_type)
            taxes = []
            if line.product_id and line.product_id.supplier_taxes_id_1:                
                taxes = line.product_id.supplier_taxes_id_1
            elif line.product_id.categ_id and line.product_id.categ_id.supplier_taxes_id:
                taxes = line.product_id.categ_id.supplier_taxes_id
                
            if not key in ordenes_agrupadas:
                purchase_order = order_model.create(cr, uid, 
                   {
                    'partner_id' : supplier.id,
                    'picking_type_id' : picking_type,
                    'location_id': line.requisition_line_id.requisition_id.picking_type_id.default_location_dest_id.id,
                    'pricelist_id': supplier.property_product_pricelist_purchase.id,
                    'bid_date': datetime.now(),
                    'fiscal_position': supplier.property_account_position.id,
                    'requisition_id':line.requisition_line_id.requisition_id.id,
                    'origin': line.requisition_line_id.requisition_id.name,
                    })
                ordenes_agrupadas[key] = purchase_order
            order_line_model.create(cr, uid,
                   {
                    'name' : line.descripcion or "ninguna",
                    'order_id' : ordenes_agrupadas[key],
                    'product_id' : line.product_id.id,
                    'product_qty' : line.product_qty,
                    'product_uom' : line.product_uom_id.id,
                    'incoterm_id' : line.incoterm_id and line.incoterm_id.id or False,
                    'date_solicitud' : line.date_solicitud,
                    'date_planned' : line.date_esperada,
                    'price_unit' : line.price_final if line.discount > 0 else line.price,
                    'account_analytic_id' : line.analytic_account_id.id,
                    'requisition_line_id' : line.requisition_line_id.id,
                    'requisition_id' : line.requisition_line_id.requisition_id.id,
                    'quotation_line_id' : line.id,
                    'discount': 0,
                    'fletes': line.fletes,
                    'project_id': line.quotation_id.project_id.id,
                    'taxes_id': [(6, 0,[x.id for x in taxes])]
                    })
            quo_line_model.set_done(cr, uid, [line.id], context)
            req_id.append(line.requisition_line_id.requisition_id.id)
        ord = 'ordenado'
        for datos in sorted(list(set(req_id))):
            if purchase_order:
                cr.execute('''INSERT INTO purchase_order_rel_requis(order_id, requisition_id) VALUES (%s,%s)''',(int(purchase_order), int(datos)))
            cr.execute('''select count(*) from purchase_requisition_line where requisition_id=%s''' % (datos,))
            numero = cr.fetchone()[0]
            cr.execute('''select count(*) from purchase_requisition_line where requisition_id=%s and state=%s''',(int(datos), str(ord)))
            valores = cr.fetchone()[0]
            if numero == valores:
                purchase_requisition.write(cr, uid, [datos], {'state': 'done'}, context=context)
        return {'type': 'ir.actions.act_window_close'}


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
