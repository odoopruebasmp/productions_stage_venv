# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
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



class stock_return_picking(models.TransientModel):
    _inherit = "stock.return.picking"
    
    def default_get(self, cr, uid, fields, context=None):
        res = super(stock_return_picking, self).default_get(cr, uid, fields, context=context)
        result1 = []
        record_id = context and context.get('active_id', False) or False
        pick_obj = self.pool.get('stock.picking')
        pick = pick_obj.browse(cr, uid, record_id, context=context)
        chained_move_exist = False
        if pick:
            if pick.state != 'done':
                raise osv.except_osv(_('Warning!'), _("You may only return pickings that are Done!"))

            for move in pick.move_lines:
                if move.move_dest_id:
                    chained_move_exist = True
                #Sum the quants in that location that can be returned (they should have been moved by the moves that were included in the returned picking)
                result1.append({'product_id': move.product_id.id, 'quantity': move.product_qty, 'move_id': move.id})

            if len(result1) == 0:
                raise osv.except_osv(_('Warning!'), _("No products to return (only lines in Done state and not fully returned yet can be returned)!"))
            if 'product_return_moves' in fields:
                res.update({'product_return_moves': result1})
            if 'move_dest_exists' in fields:
                res.update({'move_dest_exists': chained_move_exist})
        return res
    
    
class stock_location(models.Model):
    _inherit = "stock.location"    
    
    purchase_ok = fields.Boolean(string='Compra')
    sale_ok = fields.Boolean(string='Venta')
    return_ok = fields.Boolean(string='Devolucion')


class return_order(models.Model):
    _name = "return.order"
    _inherit = ['mail.thread']
    _order = 'name desc'
    
    @api.one
    @api.depends('picking_ids')
    def _moves(self):
        if self.picking_ids:
            pik=[]
            for picking in self.picking_ids:
                if picking.move_lines:
                    for move in picking.move_lines:
                        pik.append(move.id)                    
            self.move_ids = [(6, 0,pik)]
    
    @api.one
    @api.depends('invoice_ids')
    def _invoice(self):
        if self.invoice_ids:                  
            self.invoice_count = len(self.invoice_ids)
    
    @api.one
    @api.depends('picking_ids')
    def _picking(self):
        if self.picking_ids:                  
            self.picking_count = len(self.picking_ids)
    
    picking_count=fields.Integer(string='Invoices', compute="_picking")
    invoice_count=fields.Integer(string='Invoices', compute="_invoice")
    name=fields.Char(string='Nombre', readonly=True)
    causal=fields.Many2one('return.order.causal', string='Causal', required=True, readonly=True, states={'borrador':[('readonly',False)]})    
    partner_id=fields.Many2one('res.partner',string='Cliente', required=True, readonly=True, states={'borrador':[('readonly',False)]}, domain=[('is_company','=', True)])
    partner_shipping_id=fields.Many2one('res.partner',string='Sucursal', readonly=True, states={'borrador':[('readonly',False)]}) 
    date=fields.Date(string='Fecha Lista Precios', help='Fecha que el sistema tendra en cuenta para la busqueda en listas de precios', required=True, readonly=False, states={'terminado':[('readonly',True)]})
    create_date=fields.Datetime(string='Fecha Creacion', readonly=True)
    create_uid=fields.Many2one('res.users', string='Usuario Creacion', readonly=True)
    date_confirm=fields.Datetime(string='Fecha Confirmacion', readonly=True)
    user_confirm=fields.Many2one('res.users', string='Usuario Confirmacion', readonly=True)
    date_aprobacion=fields.Datetime(string='Fecha Aprobacion', readonly=True)
    user_aprobacion=fields.Many2one('res.users', string='Usuario Aprobacion', readonly=True)
    date_transfer=fields.Date(string='Fecha Transferencia', readonly=True)
    user_transfer=fields.Many2one('res.users', string='Usuario Transferencia', readonly=True)
    location_id=fields.Many2one('stock.location',string='Ubicacion', required=True, readonly=True, states={'borrador':[('readonly',False)]}, domain=[('usage','=', 'internal'),('return_ok','=', True)])
    picking_ids=fields.One2many('stock.picking', 'dev_id', string='Movimiento', readonly=True, states={'borrador':[('invisible',True)]})
    move_ids=fields.One2many('stock.move', 'picking_id',string='Picking', compute="_moves", readonly=True, states={'borrador':[('invisible',True)]})
    invoice_ids=fields.One2many('account.invoice', 'dev_id',string='Facturas', readonly=True, states={'borrador':[('invisible',True)]})
    observaciones=fields.Text(string='Observaciones', required=True, readonly=False, states={'terminado':[('readonly',True)]})
    line_ids=fields.One2many('return.order.line', 'order_id', string='Items', required=True, readonly=True, states={'borrador':[('readonly',False)]})
    state=fields.Selection([('borrador', 'Borrador'),('confirmado', 'Confirmado'),('aprobado', 'Aprobado'),('terminado', 'Terminado'),('cancelado', 'Cancelado')], string='Estado', select=True, default='borrador')
    bultos=fields.Integer(string='Paquetes', readonly=True, states={'borrador':[('readonly',False)]})
    remesa=fields.Char(string='Remesa', readonly=True, states={'borrador':[('readonly',False)]})
    amount_declarado=fields.Float(string='Valor Declarado', digits=dp.get_precision('Account'), readonly=True, states={'borrador':[('readonly',False)]})
    
    _track = {
        'state': {
            'stock_return.mt_borrador': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'borrador',
            'stock_return.mt_confirmado': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'confirmado',
            'stock_return.mt_aprobado': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'aprobado',
            'stock_return.mt_terminado': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'terminado',
            'stock_return.mt_cancelado': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelado',
        }        
    }
        
    def view_invoice(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for invoice in self.browse(cr, uid, ids, context=context).invoice_ids:
            inv.append(invoice.id)
        
        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Return Invoice',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.invoice',
                'type': 'ir.actions.act_window'
            }
    
    def view_picking(self, cr, uid, ids, context=None):
        context = dict(context or {})
        pik=[]
        for picking in self.browse(cr, uid, ids, context=context).picking_ids:
            pik.append(picking.id)
        domain = [('id','in',pik)]
        return {
                'domain': domain,
                'name': 'Return Invoice',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'stock.picking',
                'type': 'ir.actions.act_window'
            }
    
    @api.multi
    def confirmado(self):
        if not self.line_ids:
            raise osv.except_osv(_('Error !'), _("Para confirmar la solicitud de devolucion debe agregar lineas de productos "))
        number_seq = self.env['ir.sequence'].get('return.order.number')
        return self.write({'date_confirm': datetime.now(), 'user_confirm': self._uid,'state': 'confirmado','name':number_seq})
        
    @api.multi
    def aprobado(self):
        picking_type=self.env['stock.picking.type'].search([('code','=','return')])
        if not picking_type:
            raise osv.except_osv(_('Error !'), _("No existe un tipo de operacion de tipo Devolucion registrada en el sistema, por favor consulte con el Gerente Logistico para que realice esta configuracion."))
        name = self.env['ir.sequence'].get('return.order.number.picking')
        company_id=self.env['res.users'].browse(self._uid).company_id.id
        picking_type_id=picking_type[0].id
        location=self.env['stock.location'].search([('usage','=','customer')], limit=1)
        location_id = location.id

        self._cr.execute('''INSERT INTO stock_picking
            (dev_id, date_dev, name, company_id, cliente_id, partner_id, sucursal_id, date, max_date, origin, move_type, invoice_state, picking_type_id, priority, state, weight_uom_id, create_date) VALUES 
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
            (self.id, self.date, name, company_id, self.partner_id.id, self.partner_id.id, self.partner_shipping_id and self.partner_shipping_id.id or None, datetime.now(), datetime.now(), self.name, 'direct', '2binvoiced', picking_type_id, '1','draft',1,datetime.now()))
        picking_id = self._cr.fetchone()[0]

        for move in self.line_ids:
            self._cr.execute('''INSERT INTO stock_move
                (name, company_id, product_id, product_uom_qty, product_qty, product_uom, cost, total_cost, location_id, location_dest_id, procure_method, date, date_expected, invoice_state, picking_type_id, state, weight_uom_id, picking_id, priority, create_date) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
                ('['+move.product_id.default_code or 'Indefinido'+']'+move.product_id.name, company_id,  move.product_id.id, move.product_qty, move.product_qty, move.product_uom_id.id, move.product_id.standard_price, move.product_id.standard_price*move.product_qty, location_id, self.location_id.id, 'make_to_stock', datetime.now(), datetime.now(), '2binvoiced', picking_type_id, 'draft',1,picking_id,'1',datetime.now()))

        picking = self.env['stock.picking'].browse(picking_id)
        picking.rereserve_pick()
        return self.write({'picking_id':picking_id,'date_aprobacion': datetime.now(), 'user_aprobacion': self._uid,'state': 'aprobado'})

    @api.multi
    def cancelado(self):       
        return self.write({'state': 'cancelado'})
    

class return_order_line(models.Model):
    _name = "return.order.line"
        
    #causal=fields.Char(string='Causal', required=True)
    product_id=fields.Many2one('product.product',string='Producto', required=True)
    product_uom_id=fields.Many2one('product.uom',string='Unidad', related="product_id.uom_id", readonly=True)
    product_qty=fields.Float(string='Cantidad', required=True, digits=dp.get_precision('Product UoM'))
    order_id=fields.Many2one('return.order',string='Order', readonly=True)


class return_order_causal(models.Model):
    _name = "return.order.causal"
        
    name=fields.Char(string='Name', required=True)
    description=fields.Char(string='Descripcion')
    

class stock_invoice_onshipping(osv.osv_memory):    
    _inherit = "stock.invoice.onshipping"
        
    def _get_journal_type(self, cr, uid, context=None):
        if context is None:
            context = {}
        res_ids = context and context.get('active_ids', [])
        pick_obj = self.pool.get('stock.picking')
        pickings = pick_obj.browse(cr, uid, res_ids, context=context)
        vals = []
        pick = pickings and pickings[0]
        if not pick or not pick.move_lines:
            return 'sale'
        src_usage = pick.move_lines[0].location_id.usage
        dest_usage = pick.move_lines[0].location_dest_id.usage
        type = pick.picking_type_id.code
        if type == 'outgoing' and dest_usage == 'supplier':
            journal_type = 'purchase_refund'
        elif type == 'outgoing' and dest_usage == 'customer':
            journal_type = 'sale'
        elif type == 'incoming' and src_usage == 'supplier':
            journal_type = 'purchase'
        elif type == 'incoming' and src_usage == 'customer':
            journal_type = 'sale_refund'
        elif type == 'return':
            journal_type = 'sale_refund'
        else:
            journal_type = 'sale'
        return journal_type


class stock_picking(models.Model):
    _inherit = 'stock.picking'
    
    return_dap = fields.Char(string="DAP")
    return_guia = fields.Char(string="Guia Retorno")
    return_mpp = fields.Char(string="MPP")
    sucursal_id = fields.Many2one('res.partner',string="Sucursal", domain=[('type','=', 'sucursal')])
    cliente_id = fields.Many2one('res.partner',string="Cliente")


class product_pricelist_item(models.Model):
    _inherit = "product.pricelist.item"

    discount = fields.Float(string='Discount %', digits=dp.get_precision('Discount'))


class account_invoice(models.Model):
    _inherit = 'account.invoice'
    
    return_dap = fields.Char(string="DAP", related='stock_picking_id.return_dap')
    return_guia = fields.Char(string="Guia Retorno", related='stock_picking_id.return_guia')
    return_mpp = fields.Char(string="MPP", related='stock_picking_id.return_mpp')
    sucursal_id = fields.Many2one('res.partner',string="Sucursal", related='stock_picking_id.sucursal_id')

    
class stock_picking_type(models.Model):
    _inherit = 'stock.picking.type'    
    
    code = fields.Selection(selection_add=[('return', 'Devolucion')])
    
    def onchange_picking_code(self, cr, uid, ids, picking_code=False):
        if not picking_code:
            return False
        
        obj_data = self.pool.get('ir.model.data')
        stock_loc = obj_data.xmlid_to_res_id(cr, uid, 'stock.stock_location_stock')
        
        result = {
            'default_location_src_id': stock_loc,
            'default_location_dest_id': stock_loc,
        }
        if picking_code == 'incoming':
            result['default_location_src_id'] = obj_data.xmlid_to_res_id(cr, uid, 'stock.stock_location_suppliers')
        elif picking_code == 'outgoing':
            result['default_location_dest_id'] = obj_data.xmlid_to_res_id(cr, uid, 'stock.stock_location_customers')
        elif picking_code == 'return':
            result['default_location_src_id'] = obj_data.xmlid_to_res_id(cr, uid, 'stock.stock_location_customers')
        return {'value': result}


class AccountInvoice(models.Model):
    _inherit = "account.invoice"
    
    dev_id = fields.Many2one('return.order', string="Devolucion")


class StockPicking(models.Model):
    _inherit = "stock.picking"
    
    dev_id = fields.Many2one('return.order',string="Devolucion")
    date_dev = fields.Date(string="Fecha Devolucion", help='Fecha que el sistema tendra en cuenta para la busqueda en listas de precios', readonly=True, states={'draft':[('readonly',False)]})

    def compute_invoice(self, cr, uid, ids, invoice_id, context=None):
        invoice = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
        res = super(StockPicking, self).compute_invoice(cr, uid, ids, invoice_id, context=context)
        if invoice.type == 'out_refund' and invoice.stock_picking_id:
            invoice = self.pool.get('account.invoice').browse(cr, uid, res, context=context)
            if invoice.stock_picking_id and invoice.stock_picking_id.dev_id:
                cr.execute(''' update account_invoice set dev_id=%s where id=%s''', (invoice.stock_picking_id.dev_id.id, invoice.id))
        return res
    
#