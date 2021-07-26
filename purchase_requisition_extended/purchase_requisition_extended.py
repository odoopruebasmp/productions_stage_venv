# -*- coding: utf-8 -*-
from datetime import datetime
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
from openerp import addons
from openerp import SUPERUSER_ID
import itertools
from dateutil.relativedelta import relativedelta
from lxml import etree
import openerp
from urllib import urlencode, quote as quote
from openerp import models, fields, api, _
from openerp.osv import osv, fields as fields2
from openerp.exceptions import except_orm, Warning, RedirectWarning
import openerp.addons.decimal_precision as dp
import math

class product_uom(models.Model):
    _inherit = 'product.uom'
    
    products_ids = fields.Many2many('product.product', 'uom_product_rel', 'uom_id', 'product_id', string='Productos')
    
    
class product_product(models.Model):
    _inherit = 'product.product'
    
    @api.one
    @api.constrains('uoms_ids')
    def _check_uoms(self):
        if self.uoms_ids:
            for uom in self.uoms_ids:
                if uom.category_id != self.uom_po_id.category_id:
                    raise Warning(_('Hay alguna unidad de medida que no pertenece a la categoria principal de medida.'))
    
    uoms_ids = fields.Many2many('product.uom','uom_product_rel','product_id','uom_id', string='Unidades de Medida')

class purchase_quotation(osv.osv):
    _name = "purchase.quotation.supplier"
    _description = "Purchase Quotation"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _order = 'id desc'
    
    def _compute_reqs(self, cr, uid, ids, name, args, context=None):
        res = {}
        for quotation in self.browse(cr, uid, ids, context=context):
            lista = []
            for line in quotation.line_ids:
                if line.requisition_id.id not in lista:
                    lista.append(line.requisition_id.id)
            res[quotation.id] = lista
        return res
        
    def _compute_reqs_char(self, cr, uid, ids, name, args, context=None):
        res = {}
        for quotation in self.browse(cr, uid, ids, context=context):
            lista = []
            lista_2 = ''
            for line in quotation.line_ids:
                if line.requisition_id.name and line.requisition_id.name not in lista:
                    lista.append(line.requisition_id.id)
                    lista_2+=line.requisition_id.name+','
            res[quotation.id] = lista_2
        return res
    
    _columns = {
        'name': fields2.char('Codigo Cotizacion', size=32, required=True, states={'draft':[('readonly',False)]}),
        'company_id': fields2.many2one('res.company','Company',required=True,select=1, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)]}),
        'numero_pedido': fields2.char('Codigo Pedido', size=32,required=True, states={'draft':[('readonly',False)]}),
        'date': fields2.date('Fecha Pedido', required=True, states={'draft':[('readonly',False)]}),
        'line_ids': fields2.one2many('purchase.quotation.supplier.line', 'quotation_id', 'Lineas'),
        'supplier_id': fields2.many2one('res.partner', "Proveedor", required=True, states={'draft':[('readonly',False)]}),
        'project_id': fields2.many2one('project.project', "Proyecto", required=True, states={'draft':[('readonly',False)]}),
        'state': fields2.selection([('draft','Nueva'),('sent','Enviada'),('confirmed','Confirmada'),('done','Terminada'),('cancel','Cancelada')],'Estado', track_visibility='onchange', required=True),
        'requisition_line_ids': fields2.function(_compute_reqs, relation='purchase.requisition', type="one2many", string='Requisiciones',readonly=True),
        'requisition_line_char': fields2.function(_compute_reqs_char, relation='purchase.requisition', type="char", string='Requisiciones',readonly=True, store=True),
    }
    _defaults = {
        'state': 'draft',
        'date': (datetime.now()).strftime(DEFAULT_SERVER_DATE_FORMAT),
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'purchase.order', context=c),
    }
    
    def set_sent(self, cr, uid, ids, context=None):
        if context is None: context = {}
        compose_data = self.pool.get('mail.compose.message')
        object = self.browse(cr, uid, ids, context)
        self.pool.get('purchase.quotation.supplier.line').write(cr, uid, [x.id for x in object.line_ids], {'state':'sent'} ,context=context)
        self.write(cr, uid, ids, {'state':'sent'} ,context=context)
        assert len(ids) == 1, 'This option should only be used for a single id at a time.'
        ir_model_data = self.pool.get('ir.model.data') 
        try:
            template_id = ir_model_data.get_object_reference(cr, uid, 'purchase_requisition_extended', 'email_template_edi_requisition')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference(cr, uid, 'mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        cty = dict(context)
        cty.update({
            'default_model': 'purchase.quotation.supplier',
            'default_res_id': ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True
        })          
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': cty,
        }
    
    def set_confirmed(self, cr, uid, ids, context=None):
        for object in self.browse(cr, uid, ids, context):
            self.pool.get('purchase.quotation.supplier.line').write(cr, uid, [x.id for x in object.line_ids], {'state':'confirmed'} ,context=context)
        self.write(cr, uid, ids, {'state':'confirmed'} ,context=context)
        return True
        
    def set_cancel(self, cr, uid, ids, context=None):
        for object in self.browse(cr, uid, ids, context):
            self.pool.get('purchase.quotation.supplier.line').write(cr, uid, [x.id for x in object.line_ids], {'state':'cancel'} ,context=context)

        return True
        
    def set_draft(self, cr, uid, ids, context=None):
        for object in self.browse(cr, uid, ids, context):
            self.pool.get('purchase.quotation.supplier.line').write(cr, uid, [x.id for x in object.line_ids], {'state':'draft'} ,context=context)
        self.write(cr, uid, ids, {'state':'draft'} ,context=context)
        return True
    
class purchase_quotation_supplier_line(models.Model):
    _name = "purchase.quotation.supplier.line"
    _description = "Purchase Quotation Line"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    
    
    @api.one
    @api.constrains('state', 'name')
    def _get_last_price(self):
        line_obj = self.env['account.invoice.line']
        price = 0.0
        price_partner = 0.0
        for line in self:
            invoice_line = line_obj.search([('invoice_id.state', '!=', 'cancel'),('product_id', '=', line.product_id.id),('invoice_id.type', '=', 'in_invoice')])
            if invoice_line:
                price = invoice_line[0].price_unit
                invoice_line_partner = line_obj.search([('invoice_id.state', '!=', 'cancel'),('invoice_id.partner_id', '=', line.supplier_id.id),('product_id', '=', line.product_id.id),('invoice_id.type', '=', 'in_invoice')])
                if invoice_line_partner:
                    price_partner = invoice_line_partner[0].price_unit
            self.last_price = price
            self.last_price_partner = price_partner
    
    @api.one
    @api.depends('price', 'discount')
    def _amount(self):                 
        self.price_final = self.price*(1 - (self.discount/100)) 
    
    STATE_SELECTION = [
        ('draft', 'Nueva'),
        ('sent', 'Enviada'),
        ('confirmed','Confirmada'), 
        ('cancel','Cancelada'), 
        ('seleccionada','Seleccionada'), 
        ('no_seleccionada','No Seleccionada'), 
        ('validada','Validada'), 
        ('rechazada','Rechazada'),
        ('done','Ordenada'), 
        ('done2','No Ordenada')
    ]
    
    name = fields.Char(string='Codigo Linea', required=True, states={'draft': [('readonly', False)]})
    quotation_id = fields.Many2one('purchase.quotation.supplier', string="Cotizacion", required=True, ondelete='cascade', states={'draft':[('readonly',False)]})
    product_id = fields.Many2one('product.product', string="Producto", required=True, states={'draft':[('readonly',False)]})
    product_qty = fields.Float(string='Cantidad', digits=dp.get_precision('Product Unit of Measure'), required=True, states={'draft':[('readonly',False)]})
    product_uom_id = fields.Many2one('product.uom', string='Unidad', required=True, states={'draft':[('readonly',False)]})
    warehouse_id = fields.Many2one('stock.warehouse', string="Almacen", states={'draft':[('readonly',False)]})
    picking_type_id = fields.Many2one("stock.picking.type", related="requisition_line_id.picking_type_id", string='Tipo de Albaran', store=True)
    discount = fields.Float('Descuento (%)', digits= dp.get_precision('Discount'), states={'sent':[('readonly',False)]})
    incoterm_id = fields.Many2one('stock.incoterms', "Metodo de entrega", states={'sent':[('readonly',False)]})
    fletes = fields.Float('Fletes', digits=dp.get_precision('Account'), states={'sent':[('readonly',False)]})
    price = fields.Float('Precio Unitario', digits=dp.get_precision('Account'), readonly=True, states={'sent':[('readonly',False)]})
    price_final = fields.Float('Precio Unitario Final', digits=dp.get_precision('Account'), readonly=True, compute="_amount")
    descripcion = fields.Char('Caracteristicas especiales del producto', states={'draft':[('readonly',False)]})
    analytic_account_id = fields.Many2one('account.analytic.account', "Centro de costo", states={'draft':[('readonly',False)]})
    state = fields.Selection(STATE_SELECTION, string='Estado', required=True, default='draft')
    requisition_line_id = fields.Many2one('purchase.requisition.line', string="Linea Requisicion", states={'draft':[('readonly',False)]})        
    date_solicitud = fields.Date(string='Fecha solicitud', required=True, states={'draft':[('readonly',False)]})
    date_esperada = fields.Date(string='Fecha estimada de entrega', required=True, states={'draft':[('readonly',False)]})        
    requisition_id = fields.Many2one("purchase.requisition", related="requisition_line_id.requisition_id", string='Requisicion', store=True)
    company_id = fields.Many2one("res.company", related="quotation_id.company_id", string="Compania", readonly=True, store=True)
    date_quotation = fields.Date(related="quotation_id.date", string='Fecha Cotizacion',store=True)
    project_id = fields.Many2one("project.project", related="quotation_id.project_id", string='Proyecto',store=True)
    supplier_id = fields.Many2one("res.partner", related="quotation_id.supplier_id", string='Proveedor',store=True)
    numero_pedido = fields.Char(related="quotation_id.numero_pedido", string='Numero Pedido',store=True)
    category_id = fields.Many2one("product.category", related="product_id.categ_id", string='Categoria',store=True)
    last_price = fields.Float(compute="_get_last_price", string="Ultimo Precio General", digits=dp.get_precision('Account'), readonly=True, store=True, help="Este es el ultimo precio de compra facturado a esta compañia")
    last_price_partner = fields.Float(compute="_get_last_price", string="Ultimo Precio Proveedor", digits=dp.get_precision('Account'), readonly=True, store=True, help="Este es el ultimo precio de compra facturado a este proveedor")
    lugar_entrega = fields.Char(string='Lugar de Entrega', readonly=True, states={'sent':[('readonly',False)]})
    payment_term_id = fields.Many2one('account.payment.term', readonly=True, string="Plazo de Pago", states={'sent':[('readonly',False)]})
    tipo_compra = fields.Selection(related="product_id.type", string='Tipo de Compra', store=True, help="Esta campo nos permite")
    
    def validacion(self, cr, uid, ids, context=None):
        #TODO para extender la validacion en otro modulo
        return True
    
    def set_seleccionada(self, cr, uid, ids, context=None):
        self.validacion(cr, uid, ids)
        self.write(cr, uid, ids, {'state':'seleccionada'} ,context=context)
        for object in self.browse(cr, uid, ids, context):
            numero_pedido = object.quotation_id.numero_pedido
            codigo_linea = object.name
            otras_lineas = self.search(cr, uid, [('numero_pedido', '=', numero_pedido), ('name', '=', codigo_linea), ('id', '<>',object.id)], context=context)
            self.write(cr, uid, otras_lineas, {'state':'no_seleccionada'} ,context=context)
        ids += otras_lineas
        return True
        
    def undo_seleccion(self, cr, uid, ids, context=None):
        self.validacion(cr, uid, ids)
        self.write(cr, uid, ids, {'state':'confirmed'} ,context=context)
        for object in self.browse(cr, uid, ids, context):
            numero_pedido = object.quotation_id.numero_pedido
            codigo_linea = object.name
            las_lineas = self.search(cr, uid, [('numero_pedido', '=', numero_pedido), ('name', '=', codigo_linea), ('state', '=', 'no_seleccionada')], context=context)
            self.write(cr, uid, las_lineas, {'state':'confirmed'} ,context=context)
        ids += las_lineas
        return True
        
    def set_validar(self, cr, uid, ids, context=None):
        self.validacion(cr, uid, ids)
        for line in self.browse(cr, uid, ids, context):
            self.write(cr, uid, line.id, {'state':'validada'} ,context=context)
        return True
        
    def set_rechazada(self, cr, uid, ids, context=None):
        self.validacion(cr, uid, ids)
        self.write(cr, uid, ids, {'state':'rechazada'} ,context=context)
        for object in self.browse(cr, uid, ids, context):
            numero_pedido = object.quotation_id.numero_pedido
            codigo_linea = object.name
            otras_lineas = self.search(cr, uid, [('numero_pedido', '=', numero_pedido), ('name', '=', codigo_linea), ('id', '<>',object.id)], context=context)
            self.write(cr, uid, otras_lineas, {'state':'confirmed'} ,context=context)
        ids += otras_lineas
        return True
    
    def refresh(self, cr, uid, ids, context=None):
        return True
        
    def set_done(self, cr, uid, ids, context=None):
        self.validacion(cr, uid, ids)
        self.write(cr, uid, ids, {'state':'done'} ,context=context)
        for object in self.browse(cr, uid, ids, context):
            numero_pedido = object.quotation_id.numero_pedido
            codigo_linea = object.name
            otras_lineas = self.search(cr, uid, [('numero_pedido', '=', numero_pedido), ('name', '=', codigo_linea), ('id', '<>',object.id)], context=context)
            self.write(cr, uid, otras_lineas, {'state':'done2'} ,context=context)
        self.pool.get('purchase.quotation.supplier').write(cr, uid, object.quotation_id.id, {'state':'done'} ,context=context)
        self.pool.get('purchase.requisition.line').write(cr, uid, [object.requisition_line_id.id], {'state':'ordenado'} ,context=context)
        return True

class purchase_requisition(osv.Model):
    _inherit = "purchase.requisition"
    _order = 'id desc'
    _columns = {
        'project_id': fields2.many2one('project.project', "Proyecto", help="El proyecto permite gestionar un nivel de autorizacion. El sistema restringe la aprobacion de la requisicion junto con sus lineas solicitadas al Gerente del proyecto."),
        'name': fields2.char('Requisition Reference', size=32, readonly=True),
        'origin': fields2.char('Source Document',readonly=True, states={'draft':[('readonly',False)]}),
        'analytic_account_id': fields2.many2one('account.analytic.account', "Centro de costo"),
        'date_end': fields2.date('Limite Licitacion', readonly=True, states={'in_progress':[('readonly',False)]}),        
        'state': fields2.selection([('draft','Nuevo'),('in_progress','En Progreso'),('cancel','Cancelado'),('confirmed','Confirmado'),('done','Terminado')], string='Estado', track_visibility='onchange', required=True),
        'purchase_line_ids': fields2.one2many('purchase.order.line', 'requisition_id', 'Lineas Orden de Compra'),
    }
    
    _defaults = {
        'name': '',
    }
    
    _track = {
        'state': {
            'purchase_requisition_extended.mt_draft_in_progress': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'in_progress',
            'purchase_requisition_extended.mt_in_progress_confirmed': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'confirmed',
            'purchase_requisition_extended.mt_confirmed_done': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'done',
        }        
    }

    def approve_lines(self, cr, uid, id, context=None):
        requisition = self.browse(cr, uid, id, context=context)
        for line in requisition.line_ids:
            line.set_approve()
        return

    def not_approve_lines(self, cr, uid, id, context=None):
        requisition = self.browse(cr, uid, id, context=context)
        for line in requisition.line_ids:
            line.not_approve()
        return

    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'name':False,
        })
        return super(purchase_requisition, self).copy(cr, uid, id, default, context)
    
    
    def create(self, cr, uid, vals, context={}):
        if (not 'name' in vals) or (vals['name'] == False):
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'purchase.order.requisition') or '/'               
        return super(purchase_requisition, self).create(cr, uid, vals, context)

    def onchange_project_id(self, cr, uid, ids, project_id, context=None):
        value = {'analytic_account_id': ''}
        if project_id:
            value = {'analytic_account_id': self.pool.get('project.project').browse(cr, uid, project_id, context=context).analytic_account_id.id}
        return {'value': value}
    
    def tender_reset(self, cr, uid, ids, context=None):
        for object in self.browse(cr, uid, ids, context):
            self.pool.get('purchase.requisition.line').write(cr, uid, [x.id for x in object.line_ids], {'state':'draft'} ,context=context)
        return self.write(cr, uid, ids, {'state': 'draft'})
        
    def tender_cancel(self, cr, uid, ids, context=None):
        purchase_order_obj = self.pool.get('purchase.order')
        for purchase in self.browse(cr, uid, ids, context=context):
            self.pool.get('purchase.requisition.line').write(cr, uid, [x.id for x in purchase.line_ids], {'state':'cancel'} ,context=context)
            for purchase_id in purchase.purchase_ids:
                if str(purchase_id.state) in('draft'):
                    purchase_order_obj.action_cancel(cr,uid,[purchase_id.id])
        return self.write(cr, uid, ids, {'state': 'cancel'})
    
    def tender_done(self, cr, uid, ids, context=None):
        for req in self.browse(cr, uid, ids, context=context):
            if req.state == 'confirmed':
                self.write(cr, uid, ids, {'state': 'done'})
        return True
        
    def tender_reconfirm(self, cr, uid, ids, context=None):
        for req in self.browse(cr, uid, ids, context=context):
            if req.state == 'done' and (uid == req.user_id.id or uid == SUPERUSER_ID):
                self.write(cr, uid, ids, {'state': 'confirmed'})
            else:
                raise osv.except_osv(_('Error!'), _('Solo el reponsable puede devolver la requisición'))
        return True
    
    def tender_confirm(self, cr, uid, ids, context=None):
        for purchase in self.browse(cr, uid, ids, context=context):
            undef_lines = [x.id for x in purchase.line_ids if x.state == 'undefined']
            if undef_lines:
                raise osv.except_osv(_('Error!'), _('No pueden existir líneas sin ser tratadas)'))
            no_aprov_lines = [x.id for x in purchase.line_ids if x.state == 'not_aproved']
            if no_aprov_lines:
                self.pool.get('purchase.requisition.line').write(cr, uid, no_aprov_lines, {'state': 'cancel'},
                                                                 context=context)
            aprov_lines = [(x.id, x.product_qty - x.product_transfer) for x in purchase.line_ids if x.state == 'aproved']
            for al in aprov_lines:
                dval = {'state': 'ordenado'}
                if al[1] > 0:
                    dval['product_qty_cot'] = al[1]
                    dval['state'] = 'confirmed'
                self.pool.get('purchase.requisition.line').write(cr, uid, al[0], dval, context=context)
        return self.write(cr, uid, ids, {'state': 'confirmed'}, context=context)

    def action_notification_mass_send(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        
        assert len(ids) == 1, 'This option should only be used for a single id at a time.'
        ir_model_data = self.pool.get('ir.model.data')
        compose_data = self.pool.get('mail.compose.message')
        try:
            template_id = ir_model_data.get_object_reference(cr, uid, 'purchase_requisition_extended', 'email_template_edi_requisition1')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference(cr, uid, 'mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False 
        res_id = ids[0]
        ctx = {
            'default_model': 'purchase.requisition',
            'default_res_id': res_id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'search_default_model_id'
            'mark_so_as_sent': True,
            'lang': 'es_CO',
            'tz': 'America/Bogota',
            'uid': uid,
        }
        object = self.browse(cr, uid, ids, context=ctx)[0]
        if template_id:
            values = compose_data.generate_email_for_composer(cr, uid, template_id, res_id, context=ctx)
        compose_id = compose_data.create(cr, uid, values, context=ctx)
        compose_data.write(cr, uid, compose_id, {'partner_ids': [(6, 0, [x.partner_id.id for x in object.project_id.members])]})
        compose_data.send_mail(cr, uid, [compose_id], context=ctx)
        self.write(cr, uid, ids, {'state':'in_progress'} ,context=context)
        for x in object.line_ids:
            self.pool.get('purchase.requisition.line').write(cr, uid, [x.id], {'state':'undefined','product_qty': x.product_request_qty} ,context=context)
        return True

class purchase_requisition_line(osv.Model):
    _inherit = "purchase.requisition.line"
    
    def _check_quantity(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context=context):
            if line.product_request_qty < line.product_qty:
                return False
        return True
    
    _columns = {
        'aprobado': fields2.boolean('Aprobado'),
        'descripcion': fields2.char('Caracteristicas especiales del producto', readonly=True, states={'draft': [('readonly', False)]}),
        'analytic_account_id': fields2.many2one('account.analytic.account', "Centro de costo", readonly=True, states={'draft': [('readonly', False)]}),
        'incoterm_id': fields2.many2one('stock.incoterms', "Metodo de entrega", readonly=True, states={'confirmed': [('readonly', False)]}),
        'project_id' : fields2.related('requisition_id', 'project_id', relation="project.project",type='many2one', string='Proyecto',store=True),
        'analytic_account_parent_id' : fields2.related('project_id', 'analytic_account_id', relation="account.analytic.account",type='many2one', string='Centro Costo Padre'),
        'picking_type_id': fields2.related('requisition_id', 'picking_type_id', type='many2one', relation='stock.picking.type', string=' Purchase Requisition Line', store=True, readonly=True),
        'category_id' : fields2.related('product_id', 'categ_id', relation="product.category",type='many2one', string='Categoria',store=True),
        'date_start' : fields2.related('requisition_id', 'date_start',type='datetime', string='Fecha pedido', store=True),
        'date_end' : fields2.related('requisition_id', 'date_end',type='date', string='Fecha Limite Requisicion',store=True, readonly=True, states={'confirmed': [('readonly', False)]}),
        'product_qty': fields2.float('Cantidad Aprobada', digits_compute=dp.get_precision('Product Unit of Measure')),
        'product_qty_cot': fields2.float('Cantidad Cotizacion', digits_compute=dp.get_precision('Product Unit of Measure')),
        'product_request_qty': fields2.float('Cantidad Pedida', digits_compute=dp.get_precision('Product Unit of Measure'), required=True, readonly=True, states={'draft': [('readonly', False)]}),        
        'product_id': fields2.many2one('product.product', 'Product', readonly=True, states={'draft': [('readonly', False)]}),
        'product_uom_id': fields2.many2one('product.uom', 'Product Unit of Measure', readonly=True, states={'draft': [('readonly', False)]}),
        'state': fields2.selection([('draft','Nuevo'),('undefined','Indefinido'),('aproved','Aprobado'),('not_aproved','No Aprobado'),('cancel','Cancelada'),('confirmed','Confirmada'),('cotizado','Cotizado'),('ordenado','Ordenado')], string='estado'),        
    }
    
    _defaults = {
        'state': 'draft',
    }
    
    _constraints = [
        (_check_quantity, 'La cantidad aprobada tiene que ser menor o igual a la pedida', ['employee_id']),
    ]
    
    def validacion(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context):
            if line.requisition_id.project_id.user_id.id != uid:
                raise osv.except_osv(_('Error!'), _('No puede aprobar/desaprobar una linea de un proyecto en el cual usted no es manager'))
        return True
    
    def set_approve(self, cr, uid, ids, context=None):
        self.validacion(cr, uid, ids)
        self.write(cr, uid, ids, {'state':'aproved'} ,context=context)
        return True
    
    def not_approve(self, cr, uid, ids, context=None):
        self.validacion(cr, uid, ids)
        self.write(cr, uid, ids, {'state':'not_aproved'} ,context=context)
        return True
    
    def set_undo(self, cr, uid, ids, context=None):
        self.validacion(cr, uid, ids)
        self.write(cr, uid, ids, {'state':'undefined'} ,context=context)
        return True

class product_category(models.Model):
    _inherit = "product.category"
    
    department_id = fields.Many2one('hr.department', string="Departamento Encargado")

class departamento(models.Model):
    _inherit = "hr.department"

    category_ids = fields.One2many('product.category', 'department_id', string='Responsables de estos productos', readonly=True)

class purchase_order_line(models.Model):
    _inherit = "purchase.order.line"
    
    STATE_SELECTION = [
        ('draft', 'Draft PO'),
        ('sent', 'RFQ'),
        ('bid', 'Bid Received'),
        ('confirmed', 'Waiting Approval'),
        ('approved', 'Purchase Confirmed'),
        ('except_picking', 'Shipping Exception'),
        ('except_invoice', 'Invoice Exception'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ]

    project_id = fields.Many2one('project.project', string="Proyecto", required=False, states={'draft':[('readonly',False)]})
    date_solicitud = fields.Date(string='Fecha solicitud', states={'draft':[('readonly',False)]})
    tiempo_entrega = fields.Integer(string='Tiempo de entrega (dias)', states={'draft':[('readonly',False)]})
    discount = fields.Float(string='Descuento (%)', digits_compute= dp.get_precision('Discount'), states={'draft':[('readonly',False)]})
    price_final = fields.Float(string='Precio Unitario Final', digits=dp.get_precision('Account'), readonly=True, compute="_amount")
    incoterm_id = fields.Many2one('stock.incoterms', "Metodo de entrega", states={'draft':[('readonly',False)]})
    fletes = fields.Float('Fletes', digits_compute=dp.get_precision('Account'), states={'draft':[('readonly',False)]})
    quotation_line_id = fields.Many2one('purchase.quotation.supplier.line', "Linea de Cotizacion", states={'draft':[('readonly',False)]})
    quotation_id = fields.Many2one("purchase.quotation.supplier", related='quotation_line_id.quotation_id', string='Cotizacion',store=True, readonly=True)
    parent_state = fields.Selection(STATE_SELECTION, related='order_id.state', string='Estado')
    requisition_line_id = fields.Many2one('purchase.requisition.line', "Linea Requisicion", states={'draft':[('readonly',False)]})
    requisition_id = fields.Many2one('purchase.requisition', string='Requisicion', readonly=True)

    @api.one
    @api.depends('price_unit', 'discount')
    def _amount(self):
        self.price_final = self.price_unit*(1 - (self.discount/100))

    def onchange_product_id(self, cr, uid, ids, pricelist_id, product_id, qty, uom_id,
            partner_id, date_order=False, fiscal_position_id=False, date_planned=False,
            name=False, price_unit=False, state='draft', context=None):        
        if product_id:
            cr.execute('''SELECT id FROM account_invoice_line ail WHERE ail.product_id = %s AND (SELECT ai.type FROM account_invoice ai WHERE ai.id = ail.invoice_id) = 'in_invoice' LIMIT 1''',([product_id]))
            invoice_line = cr.fetchone()
            if invoice_line:
                # price_unit = self.pool.get('account.invoice.line').browse(cr, uid, invoice_line, context=context).price_unit
                cr.execute('''SELECT price_unit FROM account_invoice_line WHERE id = %s''', (invoice_line))
                price_unit = cr.fetchone()[0]
        res = super(purchase_order_line, self).onchange_product_id(cr, uid, ids, pricelist_id, product_id, qty, uom_id,
            partner_id, date_order=date_order, fiscal_position_id=fiscal_position_id, date_planned=date_planned,
            name=name, price_unit=price_unit, state='draft', context=context)
        return res

    def _calc_line_base_price(self, cr, uid, line, context=None):
        return line.price_final

    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self,vals):
        res = super(purchase_order_line, self).create(vals)  
        if vals.get('order_id',False):
            if not vals.get('requisition_id',False):
                order = self.env['purchase.order'].browse(vals.get('order_id'))
                if order.requisition_id:
                    self._cr.execute(''' update purchase_requisition_line set state=%s where requisition_id=%s''', ('cotizado',order.requisition_id.id))    
                    date_solicitud = datetime.strptime(order.requisition_id.date_start, DEFAULT_SERVER_DATETIME_FORMAT).date()
                    date_planned = datetime.strptime(res.date_planned, DEFAULT_SERVER_DATE_FORMAT).date()
                    tiempo_entrega = (date_planned - date_solicitud).days
                    self._cr.execute(''' update purchase_order_line set requisition_id=%s,tiempo_entrega=%s,date_solicitud=%s where id=%s''', (order.requisition_id.id,tiempo_entrega,date_solicitud,res.id))           
            if vals.get('price_unit',0.0) <= 0.0:
                invoice_line = self.env['account.invoice.line'].search([('product_id', '=', res.product_id.id),('invoice_id.type', '=', 'in_invoice')], limit=1)
                if invoice_line:
                    self._cr.execute(''' update purchase_order_line set price_unit=%s where id=%s''', (invoice_line.price_unit,res.id))                 
        return res

class purchase_order(models.Model):
    _inherit = "purchase.order"

    requisition_idss = fields.Many2many('purchase.requisition', 'purchase_order_rel_requis', 'order_id', 'requisition_id', string='Requisiciones')

    def wkf_approve_order(self, cr, uid, ids, context=None):
        res = super(purchase_order, self).wkf_approve_order(cr, uid, ids, context=context)

        return res
        
    def wkf_confirm_order(self, cr, uid, ids, context=None):
        res = super(purchase_order, self).wkf_confirm_order(cr, uid, ids, context=context)
        if self.browse(cr, uid, ids, context=context).amount_total <= 0.0:
            raise Warning(_('No puede confirmar una orden de compra con valor menor o igual a cero.'))
        for line in self.browse(cr, uid, ids, context=context).order_line:
            if line.requisition_id and line.requisition_id.terminados+1 == len(line.requisition_id.line_ids):
                self.pool.get('purchase.requisition').write(cr, uid, [line.requisition_id.id], {'state':'done'} ,context=context)
            elif line.requisition_id:
                self.pool.get('purchase.requisition').write(cr, uid, [line.requisition_id.id], {'terminados':line.requisition_id.terminados+1} ,context=context)
        return res
    
    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self,vals):
        date = fields.datetime.now().date()
        if not vals.get('origin_id',False) and vals.get('picking_type_id',False):
            vals.update({'origin_id':self.env['stock.picking.type'].browse(vals.get('picking_type_id')).default_location_src_id.id})
        vals['name'] = 'Dummy'
        res = super(purchase_order, self).create(vals)
        if self.pricelist_id and self.pricelist_id.currency_id  and not self.pricelist_id.currency_id.base:            
            currency_obj = self.env['res.currency.rate']
            rate = currency_obj.search([('date_sin_hora','=',date),('currency_id','=',res.pricelist_id.currency_id.id)], limit=1)
            res.rate_pactada = rate and rate.rate_inv or 0.0
            res.multi_currency = True
        if vals.get('requisition_id',False):
            requisition = self.env['purchase.requisition'].browse(vals.get('requisition_id'))
            self._cr.execute(''' UPDATE purchase_order SET date_order=%s,bid_date=%s, bid_validity=%s WHERE id=%s ''',(fields.datetime.now(), date, requisition.schedule_date or None, res.id))
        if res.name == 'Dummy':
            res.name = self.pool.get('ir.sequence').get(
                self._cr, self._uid, 'purchase.order', context=self._context)
        return res


class purchase_requisition_line_api(models.Model):
    _inherit = "purchase.requisition.line"    
    
    @api.one
    @api.constrains('product_id', 'product_qty', 'product_request_qty')
    def _stock(self):
        if self.product_id:
            self.product_stock = self.product_id.qty_available
            if self.requisition_id.picking_type_id and self.requisition_id.picking_type_id.warehouse_id:
                cxt = self._context.copy()
                cxt.update({'warehouse': self.requisition_id.picking_type_id.warehouse_id.id})
                res = self.with_context(cxt).product_id._product_available()
                if res:
                    self.product_stock_location = res.values()[0].get('qty_available')
    
    product_stock = fields.Float('Cantidad Compania', digits_compute=dp.get_precision('Product Unit of Measure'), compute="_stock", store=True)
    product_stock_location = fields.Float('Cantidad Almacen', digits_compute=dp.get_precision('Product Unit of Measure'), compute="_stock", store=True)
    product_transfer = fields.Float('Cantidad Transferida', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True, copy=False, default=0.0)
    picking_id = fields.Many2one('stock.picking', string='Picking', copy=False, readonly=True)
    
    
    def action_open_quants(self, cr, uid, ids, context=None):
        if context is None:
            context = {}            
        for line in self.browse(cr, uid, ids, context=context):
            return self.pool.get('product.template').action_open_quants(cr, uid, [line.product_id.product_tmpl_id.id], context=context)
        
    def action_transfer(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context=context):
            if line.picking_id:
                raise Warning(_("No es posible generar varias transferencias para una linea de requisicion, la line de la requisicion '%s' para el producto '%s', ya esta asociada a la transferencia '%s'") % (line.requisition_id.name, line.product_id.name, line.picking_id.name))
            context.update({
            'default_line_id': line.id,
            'default_product_qty': line.product_qty,
            'default_requisition_id': line.requisition_id.id,
        })
        return {
                'name': 'Solicitud de Transferencia',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': False,
                'res_model': 'purchase.requisition.line.wizard',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': context
            }
    

class purchase_requisition_line_wizard(models.TransientModel):
    _name = "purchase.requisition.line.wizard"
    
    @api.one
    @api.depends('type', 'location_id','location_dest_id','location_dest_id2')
    def _agrupar(self):
        if self.location_id and (self.location_dest_id or self.location_dest_id2):
            location_dest_id = self.location_dest_id and self.location_dest_id.id or self.location_dest_id2 and self.location_dest_id2.id
            if self.requisition_id:
                requisition_id = self.requisition_id.id
                if self.env['stock.picking'].search([('source_location', '=', self.location_id.id),('dest_location', '=', location_dest_id),('requisition_id', '=', requisition_id),('state', '=', 'draft')]):
                    self.agrupar = True

            
    location_id = fields.Many2one('stock.location', string='Ubicacion Origen', required=True, domain="[('usage','=','internal')]")
    location_dest_id = fields.Many2one('stock.location', string='Ubicacion Destino', domain="[('usage','=','internal')]")
    location_dest_id2 = fields.Many2one('stock.location', string='Ubicacion Destino', domain="[('usage','not in',['internal','view'])]")
    product_qty = fields.Float('Cantidad', required=True, digits_compute=dp.get_precision('Product Unit of Measure'))
    line_id = fields.Many2one('purchase.requisition.line', string='Linea')
    requisition_id = fields.Many2one('purchase.requisition', string='Requisicion')
    picking_id = fields.Many2one('stock.picking', string='Picking')
    agrupar = fields.Boolean(string='Agrupar', compute="_agrupar")
    type = fields.Selection([('consumo','Consumo'),('transferencia','Transferencia')], string='Tipo de Operacion', required=True)
    
    
    @api.multi
    def calcular(self):
        if self.product_qty <= 0.0:
            raise Warning(_('No es posible transferir una cantidad igual o menor que cero'))
        if self.product_qty > self.line_id.product_request_qty:
            raise Warning(_('No es posible transferir una cantidad superior a la solicitada.'))        
        if self.product_qty > self.line_id.product_stock:
            raise Warning(_('No es posible transferir una cantidad superior a la disponible en la compañia.'))
        
        company_id=self.env['res.users'].browse(self._uid).company_id.id
        
        
        if self.type == 'transferencia':
            picking_type_id=self.line_id.requisition_id.picking_type_id.warehouse_id.int_type_id.id
            location_id = self.location_id.id
            location_dest_id = self.location_dest_id.id
        else:
            picking_type_id=self.line_id.requisition_id.picking_type_id.warehouse_id.out_type_id.id
            location_id = self.location_id.id
            location_dest_id = self.location_dest_id2.id
            
        requisition_id = self.requisition_id.id
        
        if self.picking_id:
            picking_id = self.picking_id.id
        else:
            if self.type == 'transferencia':                
                code=self.line_id.requisition_id.picking_type_id.warehouse_id.int_type_id.sequence_id.code
                name = self.env['ir.sequence'].get(code)
            else:                
                code=self.line_id.requisition_id.picking_type_id.warehouse_id.out_type_id.sequence_id.code
                name = self.env['ir.sequence'].get(code)

            date_schedule = self.requisition_id.schedule_date + ' 24:00:00'

            self._cr.execute('''INSERT INTO stock_picking
                (requisition_id, source_location, dest_location, name, company_id, date, max_date, origin, move_type, invoice_state, picking_type_id, priority, state, weight_uom_id, create_date) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                (requisition_id, location_id, location_dest_id, name, company_id, datetime.now(), date_schedule, self.requisition_id.name, 'direct', 'none', picking_type_id, '1','draft',1,datetime.now()))
            picking_id = self._cr.fetchone()[0]
        date_schedule = self.requisition_id.schedule_date + ' 24:00:00'
        self._cr.execute('''INSERT INTO stock_move
            (name, company_id, product_id, product_uom_qty, product_qty, product_uom, cost, total_cost, location_id, location_dest_id, procure_method, date, date_expected, invoice_state, picking_type_id, state, weight_uom_id, picking_id, priority, create_date) VALUES 
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
            ( self.line_id.product_id.name, company_id,  self.line_id.product_id.id, self.product_qty, self.product_qty, self.line_id.product_uom_id.id, self.line_id.product_id.standard_price, self.line_id.product_id.standard_price*self.product_qty, location_id, location_dest_id, 'make_to_stock', datetime.now(), date_schedule, '2binvoiced', picking_type_id, 'draft',1,picking_id,'1',datetime.now()))
        
        picking = self.env['stock.picking'].browse(picking_id)
        self.line_id.picking_id = picking_id
        
        if self.product_qty == self.line_id.product_qty:
            self.line_id.state = 'ordenado'
            self.line_id.product_transfer = self.product_qty


        
        domain = [('id','=',picking_id)]
        return {
                'domain': domain,
                'name': 'TRANSFERENCIAS REQUISICION',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'stock.picking',
                'type': 'ir.actions.act_window'
            }
    
    
class stock_picking(models.Model):
    _inherit = "stock.picking"   
    
    requisition_id = fields.Many2one('purchase.requisition', string='Requisicion', copy=False)

class stock_transfer_details(models.TransientModel):
    _inherit = "stock.transfer_details"

    @api.one
    def do_detailed_transfer(self):
        res = super(stock_transfer_details, self).do_detailed_transfer()
        if self.picking_id.origin:
            if self.picking_id.state == 'done':
                pi_lines = self.env['stock.transfer_details_items'].search([('transfer_id', '=', self.id)])
                cant_pick = {}
                for pick_li in pi_lines:
                    if pick_li.product_id.id not in cant_pick:
                        cant_pick[pick_li.product_id.id] = pick_li.quantity
                    else:
                        cant_pick[pick_li.product_id.id] += pick_li.quantity

                if self.picking_id.picking_type_id.name == 'Transferencias Internas':
                    purchase = self.env['purchase.requisition'].search([('name', '=', self.picking_id.origin)])
                    purc_lines = self.env['purchase.requisition.line'].search([('requisition_id', '=', purchase.id)])
                    cant_purc = {}
                    for purc_li in purc_lines:
                        if purc_li.product_id.id not in cant_purc:
                            cant_purc[purc_li.product_id.id] = purc_li.product_request_qty
                        else:
                            cant_purc[purc_li.product_id.id] += purc_li.product_request_qty

                    if cant_pick == cant_purc:
                        purchase.write({'state':'done'})
                    else:
                        for purc_li in purc_lines:
                            if purc_li.product_id.id in cant_pick:
                                purc_li.product_transfer = cant_pick[purc_li.product_id.id] if cant_pick[purc_li.product_id.id] <= purc_li.product_qty else purc_li.product_qty
                                cant_pick[purc_li.product_id.id] -= purc_li.product_transfer

                if self.picking_id.picking_type_id.name == 'Recibos':
                    purch_order = self.env['purchase.order'].search([('name', '=', self.picking_id.origin)])
                    orig = purch_order.origin
                    purch_order_lines = self.env['purchase.order.line'].search([('order_id', '=', purch_order.id)])
                    cant_purch = 0.00
                    for purch_li in purch_order_lines:
                        cant_purch = cant_purch + purch_li.product_qty
                    if (cant_pick == cant_purch):
                        purch_order.write({'state':'done'})
        return res
    
class purchase_requisition_api(models.Model):
    _inherit = "purchase.requisition"    
    
    @api.one
    @api.constrains('schedule_date', 'date_start', 'date_end')
    def _check_date(self):
        if self.schedule_date < self.date_start[0:10]:
            raise Warning(_('La fecha planificada no puede ser inferior a la fecha de solicitud, por favor revizar esta informacion.'))

    international = fields.Boolean(string='Internacional', help="Este campo permite identificar si es una compra internacional, no tiene afectacion funcional, sirve para informes")
    terminados = fields.Integer(string='Terminados')
    multiple_rfq_per_supplier = fields.Boolean('Multiple RFQ per supplier', default=False)
    date_start = fields.Datetime(string='Fecha de Solicitud', required=True, help="Esta fecha nos ayuda a llevar registro de la fecha en que se realizo la solicitud de requisicion.", readonly=False)

    def _prepare_purchase_order_line(self, cr, uid, requisition, requisition_line, purchase_id, supplier, context=None):
        vals = super(purchase_requisition, self)._prepare_purchase_order_line(cr, uid, requisition, requisition_line, purchase_id, supplier, context)
        qty_new = requisition_line.product_qty - requisition_line.product_transfer
        vals.update({'product_qty': qty_new})
        return vals

class RequisitionPOWiz(models.TransientModel):

    _name = 'requisition.po.wiz'
    supplier = fields.Many2one('res.partner', string="Proveedor", domain=[('supplier', '=', True)])
    picking_type_id = fields.Many2one('stock.picking.type', 'Ubicacion de entrega')

    @api.multi
    def do_purchase_order(self):
        orm2sql = self.env['avancys.orm2sql']
        req_lines = self._context.get('active_ids', [])
        req_lines = self.env['purchase.requisition.line'].browse(req_lines)

        picking_type = self.picking_type_id
        purchase_order = self.env['purchase.order']
        purchase_order_line = self.env['purchase.order.line']
        purchase_requisition = self.env['purchase.requisition']
        purchase_requisition_line = self.env['purchase.requisition.line']
        id_req = 0
        if len(req_lines) == 1:
            id_req = req_lines.requisition_id.id
        if not id_req == 0:
            data = {
                'requisition_id': id_req,
                'partner_id': self.supplier.id,
                'maximum_planned_date': datetime.now(),
                'picking_type_id': picking_type.id,
                'date_order': datetime.now(),
                'location_id': picking_type.default_location_dest_id.id,
                'pricelist_id': self.supplier.property_product_pricelist_purchase.id,
                'state': 'draft',
                'name': 'DUMMY0000',
            }
        else:
            data = {
                'partner_id': self.supplier.id,
                'maximum_planned_date': datetime.now(),
                'picking_type_id': picking_type.id,
                'date_order': datetime.now(),
                'location_id': picking_type.default_location_dest_id.id,
                'pricelist_id': self.supplier.property_product_pricelist_purchase.id,
                'state': 'draft',
                'name': 'DUMMY0000',
            }
        new_order = purchase_order.create(data)

        gl = {}

        i, l = 0, len(req_lines)
        start = datetime.now()
        orm2sql.printProgressBar(i, l, start=start)
        req_id = []
        for line in req_lines:
            code = str(line.product_id.id)
            if code not in gl:
                req_id.append(line.requisition_id.id)
                price = new_order.pricelist_id.price_get(
                    line.product_id.id, line.product_qty, new_order.partner_id)[new_order.pricelist_id.id]
                categ_id = line.product_id.categ_id
                tax_ids = []
                if line.product_id.supplier_taxes_id_1:
                    for tax in line.product_id.supplier_taxes_id_1:
                        tax_ids.append(tax.id)
                else:
                    for tax in categ_id.supplier_taxes_id:
                        tax_ids.append(tax.id)
                gl[code] = {
                    'product_id': line.product_id.id,
                    'account_analytic_id': line.analytic_account_id.id,
                    'product_qty': line.product_qty - line.product_transfer,
                    'name': line.product_id.name,
                    'product_uom': line.product_uom_id.id,
                    'price_unit': price,
                    'order_id': new_order.id,
                    'requisition_id': line.requisition_id.id,
                    'date_planned': line.schedule_date,
                    'taxes_id': [(6, 0, tax_ids)],
                }

            else:
                gl[code]['product_qty'] += line.product_qty
            line.state = 'ordenado'
            pte = False
            for lin in line.requisition_id:
                if lin.state != 'ordenado':
                    pte = True
            if pte is False:
                line.requisition_id.state = 'done'

            i += 1
            orm2sql.printProgressBar(i, l, start=start)

        for code in gl:
            purchase_order_line.create(gl[code])

        for datos in sorted(list(set(req_id))):
            if new_order:
                self._cr.execute('''INSERT INTO purchase_order_rel_requis(order_id, requisition_id) VALUES (%s,%s)''',(int(new_order), int(datos)))
            numero = purchase_requisition_line.search_count([('requisition_id', '=', int(datos))])
            valores = purchase_requisition_line.search_count([('requisition_id','=',int(datos)),('state','=','ordenado')])
            if numero == valores:
                pr = purchase_requisition.search([('id', '=', int(datos))])
                pr.write({'state':'done'})
        if new_order.name == 'DUMMY0000':
            new_order.name = self.pool.get('ir.sequence').get(
                self._cr, self._uid, 'purchase.order', context=self._context)

        return True



    
    #@api.multi
    #def action_notification_mass_send(self):
        #body ='<html><body><p>Un cordial saludo</p>' 
        #body+='<p>Esta es una requisicion que se creo para el proyecto'+' '+self.project_id.name+' '+'de la compania'+' '+ self.company_id.name
        #body+='<p>Puede seguir el siguiente link ingresar y aprobar el requerimeinto: </p>'
        #body+='<p>'
        #body+='<h3 id="right">'
        #body+='<script type="text/javascript">'
        #body+='document.write(location.href);'
        #body+='</script>'
        #body+='</h3>'
        #body+='</p>'
        #body+='<p>'
        #body+='Link :&nbsp;<a href="'+ self.env['ir.config_parameter'].get_param('web.base.url') +'">'+ 'Requerimiento' +'</a>'
        #body+='</p>'
        #body+="""<table border="1" style="width: 800px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat;">"""        
        #body+='<tr>'
        #body+='<th colspan="8" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">INFORMACION</th>'
        #body+='</tr>'
        #body+='<tr>'
        #body+='<td style="font-size: 15px; color: #222;"><strong>Requisicion:</strong></td><th><span style="font-size: 10px; color: #222;">'+self.name+'</span></th>'
        #body+='<td style="font-size: 15px; color: #222;"><strong>F. Solicitud:</strong></td><th><span style="font-size: 10px; color: #222;">'+self.date_start[0:10]+'</span></th>'
        #body+='<td style="font-size: 15px; color: #222;"><strong>F. Planificada:</strong></td><th><span style="font-size: 10px; color: #222;">'+self.schedule_date+'</span></th>'
        #body+='<td style="font-size: 15px; color: #222;"><strong>Entrega a:</strong></td><th><span style="font-size: 10px; color: #222;">'+self.picking_type_id.warehouse_id.name+'</span></th>'
        #body+='</tr>'
        #body+='</table><br/>'        
        #body+='<center>'        
        #body+='<div style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat;">'
        #body+='<h3 style="margin: 0px; padding: 2px 14px; font-size: 15px; color: #FFF;">'
        #body+='<strong style="text-transform:uppercase;">'+self.company_id.name+'</strong>'
        #body+='</h3>'        
        #body+='</div>'
        #body+="""<div style="width: 347px; margin: 0px; padding: 5px 14px; line-height: 16px; background-color: #F2F2F2;">
            #<span style="color: #222; margin-bottom: 5px; display: block; ">"""
        #body+=self.company_id.street +'<br/>'
        #body+=self.company_id.country_id.name +'-'+ self.company_id.partner_id.city_id.name +'<br/>'
        #body+='</span>'
        #body+='<div style="margin-top: 0px; margin-right: 0px; margin-bottom: 0px; margin-left: 0px; padding-top: 0px; padding-right: 0px; padding-bottom: 0px; padding-left: 0px; ">'
        #body+='Telefono:&nbsp;'+self.company_id.phone
        #body+='</div>'
        #body+='<div>'
        #body+='Web :&nbsp;<a href="'+ self.company_id.website +'">'+ self.company_id.website +'</a>'
        #body+='</div>'
        #body+='<p></p>'
        #body+='</div>'
        #body+='</center>'
        #body +='</body></html>'        
        
        #vals = {
            #'email_from': self.user_id.name+' '+self.user_id.email,
            #'email_to': self.project_id.name,
            #'state': 'outgoing',
            #'subject': 'Solicitud de Aprobacion'+' '+self.name,
            #'body_html': body,
            #'type':'email',
            #'auto_delete': False,
            #'notification': True,
            #'recipient_ids': [(6, 0, [x.partner_id.id for x in self.project_id.members])]
            #}
        #mail=self.env['mail.mail'].create(vals)
        #mail.send()
        #self._cr.execute(''' UPDATE purchase_requisition SET  state = 'in_progress' WHERE id = %s''',(self.id,))
        #self._cr.execute(''' UPDATE purchase_requisition_line SET  state = 'undefined', product_qty=product_request_qty WHERE requisition_id = %s''',(self.id,))
        
        #return True
