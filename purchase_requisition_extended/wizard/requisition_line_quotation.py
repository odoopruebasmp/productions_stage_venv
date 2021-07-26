# -*- coding: utf-8 -*-
import openerp.netsvc
from openerp.osv import osv, fields
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import date, datetime, timedelta

class requisition_quotation(osv.osv_memory):
    _name = 'purchase.requisition.quotation.wizard'
    
    _columns = {
        'suppliers': fields.many2many('res.partner', 'hr_wizquota_supplier_rel', 'wizquota_id', 'supplier_id', 'Proveedores'),
    }
    
    def confirm_quotation(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        req_model = self.pool.get('purchase.requisition.line')
        quo_model = self.pool.get('purchase.quotation.supplier')
        quo_line_model = self.pool.get('purchase.quotation.supplier.line')
        seq_model = self.pool.get('ir.sequence')
        line_ids = context.get('active_ids', [])
        suppliers = False
        key = False
        order_code = seq_model.get(cr, uid, 'purchase.quotation.order')
        for data in self.browse(cr, uid, ids, context):
            suppliers = data.suppliers or False
        
        for line in req_model.browse(cr, uid, line_ids, context):
            if not key:
                key = [line.project_id]
            elif key != [line.project_id]:
                raise osv.except_osv(_('Error!'), _('Las lineas seleccionadas deben ser del mismo proyecto'))
            # if not line.incoterm_id:
                # raise osv.except_osv(_('Error!'), _('No puede seleccionar lineas sin metodo de entrega'))
            if not suppliers:
                raise osv.except_osv(_('Error!'), _('tiene que seleccionar al menos un proveedor'))
            project = line.project_id.id
        
        for supplier in suppliers:
            line_number = 0
            cuotation_code = seq_model.get(cr, uid, 'purchase.quotation.supplier')
            purchase_quotation = quo_model.create(cr, uid, 
                   {
                    'name' : cuotation_code,
                    'numero_pedido' : order_code,
                    'supplier_id' : supplier.id,
                    'project_id' : project,
                    })            
            for line in req_model.browse(cr, uid, line_ids, context=context):
                line_number+=1
                self.pool.get('purchase.requisition.line').write(cr, uid, line_ids, {'state':'cotizado'}, context=context)
                purchase_quotation_lines = quo_line_model.create(cr, uid, 
                       {
                        'name' : line_number,
                        'quotation_id' : purchase_quotation,
                        'product_id' : line.product_id.id,
                        'product_qty' : line.product_qty,
                        'product_uom_id' : line.product_uom_id.id,
                        'incoterm_id' : line.incoterm_id and line.incoterm_id.id or False,
                        'descripcion' : line.descripcion,
                        'picking_type_id' : line.picking_type_id.id,
                        'date_solicitud' : line.date_start,
                        'date_esperada' : line.schedule_date,
                        'analytic_account_id' : line.analytic_account_id.id,
                        'requisition_line_id' : line.id,
                        }, context=context)
        return {'type': 'ir.actions.act_window_close'}


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
