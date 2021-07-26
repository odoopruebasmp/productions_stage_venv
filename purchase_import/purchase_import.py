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
from openerp.addons.edi import EDIMixin
import math



class stock_picking(models.Model):
    _inherit = "stock.picking"

    @api.cr_uid_ids_context
    def do_enter_transfer_details(self, cr, uid, picking, context=None):
        if not context:
            context = {}
        picking_obj=self.browse(cr, uid, picking, context=context)
        if picking_obj.picking_type_id.code != 'internal':
            cr.execute(''' UPDATE stock_picking SET invoice_state='2binvoiced' WHERE id=%s''',(picking_obj.id,))
            cr.execute(''' UPDATE stock_move SET invoice_state='2binvoiced' WHERE picking_id=%s''',(picking_obj.id,))
        res = super(stock_picking, self).do_enter_transfer_details(cr, uid, picking, context=context)
        purchase = self.pool('purchase.order').search(cr, uid, [('name','=',picking_obj.origin)], context=context, limit=1)
        if purchase and picking_obj.picking_type_code == 'incoming':
            purchase = self.pool('purchase.order').browse(cr, uid, purchase, context=context)
            if purchase and purchase.import_id and purchase.import_id.state != 'finished':
                raise osv.except_osv(_('Error!'), _('La importacion "%s" aun no se encuentra cerrada') % purchase.import_id.name)
            elif purchase and purchase.import_id and purchase.company_id.invoice_import and not purchase.invoiced:
                raise osv.except_osv(_('Error!'), _('Por politica de la compañia, la orden de compra "%s", asociada a la importacion "%s", se le debe generar una factura de compra, por favor consultar con el area contable.') % (purchase.name, purchase.import_id.name))
        return res

    def action_cancel(self, cr, uid, ids, context=None):
        for picking in self.browse(cr, uid, ids, context=context):
            purchase = self.pool.get('purchase.order').search(cr, uid, [('name','=',picking.origin)], context=context)
            if purchase and picking.picking_type_code == 'incoming':
                purchase = self.pool('purchase.order').browse(cr, uid, purchase, context=context)
                if purchase.import_id and purchase.import_id.state == 'finished':
                    raise osv.except_osv(_('Warning!'), _("Operacion no valida, no es posible cancelar la recepcion de la importacion '%s'. Por favor si necesita realizar una modificacion al pedido, recuerde que debe volver a asociar las lineas a prorratear, esto lo puede hacer desde la orden de compra en la sesion de PRODUCTOS A TRANSPORTAR. Si no conoce este procedimiento, consulte con el area de compras internacionales, esto podria generar un resultado no deseado.")  % (purchase.import_id.name))
        return super(stock_picking, self).action_cancel(cr, uid, ids, context=context)


class account_move_line(models.Model):
    _inherit = 'account.move.line'

    import_id = fields.Many2one('purchase.import', string='Importacion')


class stock_move(models.Model):
    _inherit = 'stock.move'

    cost_product_import = fields.Float(string='Valor Productos Declaracion', digits_compute=dp.get_precision('Account'), copy=False)
    import_cost = fields.Float(string='Costo Importacion', digits_compute=dp.get_precision('Account'), copy=False)
    flete_cost = fields.Float(string='Costo Fletes', digits_compute=dp.get_precision('Account'), copy=False)
    seguro_cost = fields.Float(string='Costo Seguro', digits_compute=dp.get_precision('Account'), copy=False)
    aduana_cost = fields.Float(string='Valor en Aduana', digits_compute=dp.get_precision('Account'), copy=False)
    arancel_cost = fields.Float(string='Valor Arancel', digits_compute=dp.get_precision('Account'), copy=False)
    arancel_id = fields.Many2one('account.tax',  string="Arancel", readonly=True)
    purchase_id = fields.Many2one('purchase.order', related='purchase_line_id.order_id', string="Importacion", readonly=True, store=True)

class account_invoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_move_create(self):
        res = super(account_invoice, self).action_move_create()
        if self.type == 'in_invoice' and self.import_id:
            self._cr.execute(''' UPDATE account_move_line SET import_id=%s WHERE move_id=%s''', (self.import_id.id, self.move_id.id))
        if self.type == 'in_invoice' and self.import_id2:
            self._cr.execute(''' UPDATE account_move_line SET import_id=%s WHERE move_id=%s''', (self.import_id2.id, self.move_id.id))
        return res

    import_id = fields.Many2one('purchase.import', string='Importacion')
    import_id2 = fields.Many2one('purchase.import', string='Importacion Arancel', help="Aplica cuando esta factura, representa el valor del arancel de la importacion a relacionar")

class account_tax(models.Model):
    _inherit = 'account.tax'

    arancel = fields.Boolean(string='Arancel')

class product_arancel(models.Model):
    _name = 'product.arancel'

    product_id = fields.Many2one('product.template', string='Producto')
    arancel_id = fields.Many2one('account.tax', string='Partida Aranclaria', domain=[('parent_id','=',False),('arancel','=',True)], required=True)
    country_id = fields.Many2one('res.country', string='Pais', required=True)

class product_template(models.Model):
    _inherit = 'product.template'

    arancel_ids = fields.One2many('product.arancel', 'product_id', string='Partida Aranclaria')

class purchase_order(models.Model):
    _inherit = 'purchase.order'

    @api.one
    @api.depends('date_origen')
    def _check_order(self):
        if self.date_origen:
            date_actual = date.today()
            date_actual = date_actual.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            var = False
            for leave in self:
                if leave.date_origen and leave.date_origen <= date_actual:
                    var = True
            self.diff_order = var

    import_id = fields.Many2one('purchase.import', string='Importacion')
    diff_order = fields.Boolean(compute="_check_order", string='Vencidos')
    date_origen = fields.Date(string='Fecha Origen', readonly=False, states={'done':[('readonly',True)]})
    event_id = fields.Many2one('event.event', 'Evento',  states={'done':[('readonly',True)], 'approved':[('readonly',True)]})

    @api.multi
    def write(self, vals):
        if vals.get('state',False) == 'cancel':
            if self.import_id and self.import_id.state == 'finished':
                raise osv.except_osv(_('Warning!'), _("Operacion no valida, no es posible cancelar una orden de compra asociada a la importacion '%s'. Por favor si necesita realizar una modificacion al pedido, recuerde que debe volver a asociar las lineas a prorratear, esto lo puede hacer desde la orden de compra en la sesion de PRODUCTOS A TRANSPORTAR. Si no conoce este procedimiento, consulte con el area de compras internacionales, esto podria generar un resultado no deseado.")  % (self.import_id.name))
        if self and 'import_id' in vals and not vals.get('import_id',False) and self.import_id.state != 'draft':
            raise osv.except_osv(_('Warning!'), _("Operacion no valida, no es posible eliminar la relacion de una orden de compra con una importacion que no este en estado borrador."))
        return super(purchase_order, self).write(vals)

class purchase_order_line(models.Model):
    _inherit = 'purchase.order.line'

    additional_cost = fields.Float(string='Costo Adicional')
    import_id = fields.Many2one('purchase.import', related='order_id.import_id', string="Importacion", readonly=True)


    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        '''
        Will restrict the duplicated lines to be added in another purchase import.
        '''
        vals = super(purchase_order_line, self).search(cr, uid, args, offset=offset, limit=limit, order=order, context=context, count=False)
        if not context.get('po_lines'):
            return vals
        po_import_obj = self.pool.get('purchase.import')
        po_imp_ids = po_import_obj.search(cr, uid, [])
        po_line_list = []
        for po_imp in  po_import_obj.read(cr, uid, po_imp_ids, ['po_lines']):
            if po_imp.get('po_lines'):
                po_line_list.extend(po_imp.get('po_lines'))
        return list(set(vals).difference(set(po_line_list)))

class purchase_import(osv.Model, EDIMixin):
    _name = "purchase.import"
    _description = "Purchase Import"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _order = 'name desc'

    STATE_SELECTION = [
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('progress', 'Progreso'),
        ('finished', 'Cerrado'),
        ('committed', 'Entregado'),
        ('cancel', 'Anulado'),
    ]

    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('purchase.order.line').browse(cr, uid, ids, context=context):
            result[line.order_id.import_id.id] = True
        return result.keys()

    def _get_import(self, cr, uid, ids, context=None):
        result = {}
        for order in self.pool.get('purchase.order').browse(cr, uid, ids, context=context):
            result[order.import_id.id] = True
        return result.keys()

    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        purchase_order_line = self.pool.get('purchase.order.line')
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {
                    'amount_total_products':0.0,
                    #'amount_products':0.0,
                    'amount_total_products_aduana':0.0,
                    'amount_total_weight':0.0,
                    'amount_total_transport':0.0,
                    'amount_total_expenses':0.0,
                    'amount_total_aranceles':0.0,
                    'amount_total_importation':0.0,
                    'amount_total_seguro':0.0,
            }
            #amount_products = 0.0
            amount_total_products = 0.0
            amount_total_weight = 0.0
            amount_total_transport = 0.0
            amount_total_expenses = 0.0
            amount_total_aranceles = 0.0
            amount_total_seguro = 0.0
            amount_total_flete = 0.0
            var = 0.0

            for line in order.transport_stock_move_ids:
                amount_total_products += line.cost_product_import
                amount_total_weight += line.weight
                amount_total_aranceles += line.arancel_cost
                amount_total_seguro += line.seguro_cost
                amount_total_flete += line.flete_cost
                #amount_products += line.aduana_cost
            for line in order.transport_order_line_ids:
                var = line.local_subtotal
                if order.date_cost and order.currency_rate > 0.0 and line.order_currency_id == order.currency_id:
                    var = line.price_subtotal * order.currency_rate
                amount_total_transport += var

            for line in order.invoices_ids:
                if line.state != 'cancel':
                    amount_total_expenses += line.amount_untaxed_moneda_local

            for line in order.refund_ids:
                if line.state != 'cancel':
                    amount_total_expenses -= line.amount_untaxed_moneda_local


            total_import = amount_total_transport + amount_total_expenses + amount_total_aranceles + order.value_flete + amount_total_seguro + amount_total_products

            res[order.id]['amount_total_products'] = amount_total_products
            res[order.id]['amount_total_products_aduana'] = amount_total_products + amount_total_seguro + amount_total_flete + amount_total_transport
            res[order.id]['amount_total_weight'] = amount_total_weight
            res[order.id]['amount_total_transport'] = amount_total_transport
            res[order.id]['amount_total_expenses'] = amount_total_expenses
            res[order.id]['amount_total_importation'] = total_import
            res[order.id]['amount_total_aranceles'] = amount_total_aranceles



        return res

    def _get_moves(self, cr, uid, ids, name, args, context=None):
        res = {}

        for importacion in self.browse(cr, uid, ids, context=context):
            list = []
            for transport in importacion.purchase_order_ids:
                list += [x.id for x in transport.transport_stock_move_ids]
            res[importacion.id] = list
        return res

    def _get_transport_lines(self, cr, uid, ids, name, args, context=None):
        res = {}
        for importacion in self.browse(cr, uid, ids, context=context):
            list = []
            for transport in importacion.purchase_order_ids:
                # for transport in transport.order_line:
                list += [x.id for x in transport.order_line if x.product_id.landed_cost_ok]
            res[importacion.id] = list
        return res


    def _get_currency_rate(self, cr, uid, ids, name, args, context=None):
        if not context: context = {}
        var= 0.0
        res={}
        for importacion in self.browse(cr, uid, ids, context=context):
            currency_obj = self.pool.get('res.currency')
            var = currency_obj.tasa_dia(cr, uid, importacion.date_cost, importacion.company_id, importacion.currency_id, context=context)
            if var == 0.0 and importacion.date_cost:
                raise osv.except_osv(_('Error !'), _("La tasa para '%s' aun no a sido configurada para la fecha'%s'")  % (importacion.currency_id.name, importacion.date_cost))
            res[importacion.id] = var
        return res


    _columns = {
        'number' : fields2.char('Number', size=32, states={'finished':[('readonly',True)]}),
        'name' : fields2.char('Name', size=32, readonly=True, states={'finished':[('readonly',True)]}),
        'caricom' : fields2.boolean('Caricom', states={'finished':[('readonly',True)]}),
        'value_flete': fields2.float('Flete', digits_compute=dp.get_precision('Account'), states={'finished':[('readonly',True)]}),
        'value_seguro': fields2.float('Porcentaje', digits_compute=dp.get_precision('Exchange Precision'), states={'finished':[('readonly',True)]}),
        'type_seguro': fields2.selection((('price','Precio'), ('porce','Porcentaje')),'Calculo del Seguro', states={'finished':[('readonly',True)]}),
        'value_seguro_dos': fields2.float('Precio', digits_compute=dp.get_precision('Account'), states={'finished':[('readonly',True)]}),
        'trading_id' : fields2.many2one('res.partner', 'Trading', required=True, states={'finished':[('readonly',True)]}),
        'origin' : fields2.many2one('stock.location', 'Origin', states={'finished':[('readonly',True)]}),
        'destination' : fields2.many2one('stock.location', 'Destination', states={'finished':[('readonly',True)]}),
        'date_cost':fields2.date('Fecha de Declaracion', help="La hora debe ser igual a las 7:00:00 para que el sistema la reconosca", states={'finished':[('readonly',True)]}),
        'dates':fields2.date('Fecha Estimada', required=True, states={'finished':[('readonly',True)]}),
        'dates_realy':fields2.date('Fecha Real', states={'finished':[('readonly',True)]}),
        'date_cerrar':fields2.date('Fecha Cierre', readonly=True, states={'finished':[('readonly',True)]}),
        'date_realy':fields2.date('Fecha Real', states={'finished':[('readonly',True)]}),
        'date_origin':fields2.date('Fecha Estimada', required=True, states={'finished':[('readonly',True)]}),
        'date_out_realy':fields2.date('Fecha Real', states={'finished':[('readonly',True)]}),
        'date_out_origin':fields2.date('Fecha Estimada', states={'finished':[('readonly',True)]}),
        'purchase_order_ids' : fields2.one2many('purchase.order', 'import_id', 'Transportes', states={'finished':[('readonly',True)]}),
        'bl_doc_ids': fields2.one2many('bl.doc', 'purchase_import_id', 'Bill Of Landing Doc', states={'finished':[('readonly',True)]}),
        'company_id': fields2.many2one('res.company', 'Company', required=True, states={'finished':[('readonly',True)]}),
        'invoices_ids':fields2.one2many('account.invoice', 'import_id', 'Costos adicionales', readonly=True, states={'finished':[('readonly',True)]}, domain=[('state','!=','cancel'), ('type', '=', 'in_invoice')]),
        'refund_ids':fields2.one2many('account.invoice', 'import_id', 'Notas credito', readonly=True, states={'finished':[('readonly',True)]}, domain=[('state','!=','cancel'), ('type', '=', 'in_refund')]),
        'invoices_arancel_ids':fields2.one2many('account.invoice', 'import_id2', 'Arancel', readonly=True, states={'finished':[('readonly',True)]}, domain=[('state','!=','cancel')]),
        'transport_stock_move_ids': fields2.function(_get_moves, relation='stock.move', type="one2many", string='Productos a Transportar',readonly=True, states={'finished':[('readonly',True)]}),
        'transport_order_line_ids': fields2.function(_get_transport_lines, relation='purchase.order.line', type="one2many", string='Transportes',readonly=True, states={'finished':[('readonly',True)]}),
        'state': fields2.selection(STATE_SELECTION, 'State', readonly=True),
        'supplier_importation_num': fields2.char('Referencia',size = 32, states={'finished':[('readonly',True)]}),
        'amount_total_products': fields2.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'),
                                          store={
                                          'purchase.import': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                          'purchase.order' : (_get_import, ['import_id','order_line','amount_untaxed','state'], 10)},
                                           type='float', string='Total Productos',
                                           multi='sums', states={'finished':[('readonly',True)]}),
        'amount_total_products_aduana': fields2.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'),
                                          store={
                                          'purchase.import': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                          'purchase.order' : (_get_import, ['import_id','order_line','amount_untaxed'], 10)},
                                           type='float', string='Total Productos en Aduana',
                                           multi='sums', states={'finished':[('readonly',True)]}),
        'amount_total_weight': fields2.function(_amount_all, method=True, digits_compute=dp.get_precision('Stock Weight'),
                                          store={
                                          'purchase.import': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                          'purchase.order' : (_get_import, ['import_id','order_line','amount_untaxed'], 10)},
                                           type='float', string='Total Peso',
                                           multi='sums', states={'finished':[('readonly',True)]}),
        'amount_total_transport': fields2.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'),
                                          store={
                                          'purchase.import': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                          'purchase.order' : (_get_import, ['import_id','order_line','amount_untaxed'], 10)},
                                           type='float', string='Total Transporte',
                                           multi='sums', states={'finished':[('readonly',True)]}),
        'amount_total_expenses': fields2.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'),
                                          store={
                                          'purchase.import': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                          'purchase.order' : (_get_import, ['import_id','order_line','amount_untaxed'], 10)},
                                           type='float', string='Total Otros Gastos',
                                           multi='sums',),
        'amount_total_importation': fields2.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'),
                                          store={
                                          'purchase.import': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                          'purchase.order' : (_get_import, ['import_id','order_line','amount_untaxed'], 10)},
                                           type='float', string='Total Importacion',
                                           multi='sums',),
        'amount_total_aranceles': fields2.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'),
                                                   store={
                                                       'purchase.import': (
                                                       lambda self, cr, uid, ids, c={}: ids, None, 10),
                                                       'purchase.order': (
                                                       _get_import, ['import_id', 'order_line', 'amount_untaxed'], 10)},
                                                   type='float', string='Total Aranceles',
                                                   multi='sums', ),
        'currency_id': fields2.many2one('res.currency', "Currency", required=True,states={'finished':[('readonly',True)]}),
        'currency_rate': fields2.function(_get_currency_rate, method=True, type='float', string='Tasa de Costo', digits_compute=dp.get_precision('Exchange Precision'), readonly=True, store={
            'purchase.import': (lambda self, cr, uid, ids, c={}: ids, None, 10)}),

        'calculate_method': fields2.selection((('price','Por Precio'), ('weight','Por Peso')), string='Metodo Prorateo', states={'finished':[('readonly',True)]}, help="""El metodo con el cual se calculara el costo del producto
        'Por Linea': El precio unitario de cada linea se divide por el precio total, este porcentaje se multiplica por el valor del transporte; este sera el costo de transporte para la linea.
        'Por Peso: El peso de cada linea se divide por el peso total, este porcentaje se multiplica por el valor del transporte; este sera el costo de transporte para la linea'
        """, required=True),
    }

    _track = {
        'state': {
            'purchase_import.mt_draft': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'draft',
            'purchase_import.mt_confirmed': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'progress',
            'purchase_import.mt_progress': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'finished',
            'purchase_import.mt_finished': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'committed',
            'purchase_import.mt_cancel': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancel',
        }
    }


    def confirm_po(self, cr, uid, ids, context=None):
        for data in self.browse(cr, uid, ids, context=context):
            if not data.purchase_order_ids:
                raise osv.except_osv(_('Warning!'),_('No es posible confirmar esta importacion, sin tener por lo menos una orden de compra asociada.'))
        return True

    def _get_currency(self, cr, uid, context=None):
        if not context: context = {}
        currency_obj = self.pool.get('res.currency')
        dolar = currency_obj.search(cr,uid,[('name','=','USD')], context=context)
        if len(dolar) > 0:
            result = currency_obj.browse(cr,uid,dolar[0],context=context).id
        else:
            result = False
        return result


    _defaults = {
        'state' : 'draft',
        'dates' : datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'currency_id': _get_currency,
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'purchase.import', context=c),
    }

    def create(self, cr, uid, vals, context={}):
        if (not 'name' in vals) or (vals['name'] == False):
            # get the sequence code
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'purchase.import') or '/'
        return super(purchase_import, self).create(cr, uid, vals, context)

    def wf_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'draft'})
        return True

    def wf_confirmed(self, cr, uid, ids, context=None):
        self.confirm_po(cr, uid, ids, context=context)
        self.write(cr, uid, ids , {'state':'confirmed'})
        return True

    def wf_progress(self, cr, uid, ids, context=None):
        self.compute_cost(cr, uid, ids, context=context)
        for rec in self.browse(cr, uid, ids, context=context):
            # for order in rec.purchase_order_ids:
            #     if order.state != "approved" or order.state != "done":
            #         raise osv.except_osv(_('Warning!'), _("La orden de compra '%s' no esta aprobada o terminada!"  % order.name))
            for product_line in rec.transport_stock_move_ids:
                if product_line.state == "done":
                    raise osv.except_osv(_('Warning!'), _("El movimiento '%s' ya fue recepcionado, es imposible modificar este docuemnto"  % product_line.product_id.name))
        return self.write(cr, uid, ids , {'state':'progress'})

    def wf_committed(self, cr, uid, ids, context=None):
        self.compute_cost(cr, uid, ids, context=context)
        self.write(cr, uid, ids , {'state':'committed'})
        return True

    def wf_finished(self, cr, uid, ids, context=None):
        date_late = str(date.today())
        self.compute_cost(cr, uid, ids, context=context)
        self.compute_cost(cr, uid, ids, context=context)
        self.write(cr, uid, ids , {'state':'finished'})
        self.write(cr, uid, ids , {'date_cerrar': date_late})
        return True

    def wf_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'cancel'})
        return True

    def compute_cost(self, cr, uid, ids, context=None):
        if not context: context = {}
        vals = {}
        purchase_order_obj = self.pool.get('purchase.order')
        stock_move_obj = self.pool.get('stock.move')
        account_tax_obj = self.pool.get('account.tax')
        arancel_obj = self.pool.get('product.arancel')

        move_line = []
        for rec in self.browse(cr, uid, ids, context=context):
            # TODO#update TRM in POs, only if is the same currency?
            # purchase_order_obj.prorate_cost(cr, uid, rec.purchase_order_ids, context=context)
            # linea con error x
            amount_total_aranceles = 0
            seguro = 0.0
            costo_importacion = 0
            total_declaracion = 0
            total_aduana = 0
            rec.amount_total_products = 0
            for move in rec.transport_stock_move_ids:
                stock_move_obj.write(cr, uid, move.id, {
                    'arancel_id': 0,
                    'arancel_cost': 0,
                    'import_cost': 0,
                    'flete_cost': 0,
                    'seguro_cost': 0,
                    'aduana_cost': 0,
                    'cost': 0,
                    'price_unit': 0,

                })

                if move.product_qty > 0:

                    if move.purchase_line_id:
                        if move.purchase_line_id.state != 'cancel':
                            price_unit_total = move.purchase_line_id.price_subtotal * rec.currency_rate
                        else:
                            raise Warning(_("La orden de produccion '%s' con ID '%s' se encuentra Cancelada") %
                                          (move.purchase_line_id.name, move.purchase_line_id.id))
                    else:
                        raise Warning(_("El producto '%s' en la pestaña Productos no tiene Linea de orden de compra.")
                                      % (move.product_id.name))
                    total_declaracion += price_unit_total
                    #price_unit_total = move.price_unit_total

                    #if rec.date_cost and rec.currency_rate > 0.0 and move.purchase_line_id:
                    #    price_unit_total = move.purchase_line_id.price_subtotal * rec.currency_rate

                    if rec.calculate_method == 'price' and rec.amount_total_products != 0.0:
                        prorate = (price_unit_total / rec.amount_total_products)
                    elif rec.calculate_method == 'weight':
                        prorate = (move.weight / rec.amount_total_weight)
                    else:
                        prorate = 0

                    if rec.type_seguro == 'porce':
                        seguro = rec.value_seguro * price_unit_total
                    elif rec.type_seguro == 'price':
                        seguro = rec.value_seguro_dos * prorate

                    flete = prorate * rec.value_flete
                    aduana_cost = seguro + flete + price_unit_total

                    aditional_costs = 0
                    # if not rec.caricom and product_arancel:
                    #     arancel_cost = account_tax_obj.compute_all(cr, uid, [product_arancel], aduana_cost, 1,
                    #                                                product=move.product_id.id,
                    #                                                partner=rec.trading_id.id, force_excluded=False)[
                    #         'taxes'][0]['amount']
                    #     amount_total_aranceles += arancel_cost
                    # if not rec.caricom and not product_arancel and rec.invoices_arancel_ids:
                    #     for invoices in rec.invoices_arancel_ids:
                    #         amount_total_expenses += invoices.amount_untaxed_moneda_local
                    amount_total_expenses = 0
                    for object in rec.invoices_ids:
                        if object.amount_untaxed_moneda_local <> 0:
                            amount_total_expenses += object.amount_untaxed_moneda_local
                        else:
                            amount_total_expenses += object.amount_untaxed
                    for object in rec.refund_ids:
                        if object.amount_untaxed_moneda_local <> 0:
                            amount_total_expenses -= object.amount_untaxed_moneda_local
                        else:
                            amount_total_expenses -= object.amount_untaxed
                    aditional_costs = prorate * amount_total_expenses
                    costo = (aduana_cost + aditional_costs)/move.product_qty
                    stock_move_obj.write(cr, uid, move.id, {
                        'import_cost': aditional_costs,
                        'flete_cost': flete,
                        'seguro_cost': seguro,
                        'aduana_cost': aduana_cost,
                        # 'price_unit': total_cost / move.product_qty,
                        'cost_product_import': price_unit_total,
                        'cost': costo,
                        'price_unit': costo,
                    })
            # self.write(cr, uid, rec.id, {'amount_total_aranceles': amount_total_aranceles})

            # Ejecuta la funcion calculate_arancel
            self.calculate_arancel(cr, uid, ids)
            # self.calculate_cost(cr,uid,ids)
            rec.amount_total_products = total_declaracion
        return True
    def calculate_arancel(self, cr, uid, ids, context=None):
        # Calculo de los aranceles despues de que se ejecuta la funcion compute_cost
        stock_move_obj = self.pool.get('stock.move')
        total_productos = 0
        total_suma_procentajes = 0
        for rec in self.browse(cr, uid, ids, context=context):

            # Valor total Facturas de aranceles
            total_suma_facturas = 0

            try:
                suma = 0
                for factura in rec.invoices_arancel_ids:
                    suma += factura.amount_untaxed
                total_suma_facturas = suma
                print 'Total Facturas con arancel ', total_suma_facturas

            except:
                pass

            if total_suma_facturas > 0:
                # Valor total de productos que tienen aranceles del mismo pais que el proveedor
                total_productos = 0
                productos = 0

                try:
                    for prod in rec.transport_stock_move_ids:
                        for line in prod.product_id.arancel_ids:
                            if line.arancel_id.arancel and line.arancel_id.amount > 0 and line.country_id.id == prod.purchase_line_id.partner_id.country_id.id:
                                productos += prod.cost_product_import
                                print 'productos ', productos
                                step_two = True
                    total_productos = productos
                    print 'Total productos con arancel ', total_productos

                except:
                    pass

            if total_productos > 0:
                # Total de la sumatoria de los porcentajes
                paso_tres = 0
                if total_productos > 0:
                    for prod in rec.transport_stock_move_ids:
                        for line in prod.product_id.arancel_ids:
                            paso_uno = prod.cost_product_import / total_productos
                            paso_dos = paso_uno * line.arancel_id.amount
                            paso_tres += paso_dos
                    total_suma_procentajes = paso_tres
                    print 'Total de porcentajes ', total_suma_procentajes

            if total_suma_procentajes > 0:
                # Operaciones por producto con arancel
                arancel_id = False

                for move in rec.transport_stock_move_ids:
                    resultado = 0
                    for line in move.product_id.arancel_ids:
                        if total_suma_facturas > 0 and total_productos and line.arancel_id.id:
                            if line.arancel_id.arancel and line.arancel_id.amount > 0:
                                if line.country_id.id == move.purchase_line_id.partner_id.country_id.id:
                                    paso_uno = move.cost_product_import / total_productos
                                    paso_dos = paso_uno * line.arancel_id.amount
                                    resultado = (total_suma_facturas * paso_dos) / total_suma_procentajes
                                    arancel_id = line.arancel_id.id
                                    stock_move_obj.write(cr, uid, move.id, {
                                        'arancel_id': arancel_id,
                                        'arancel_cost': resultado,
                                    })
                    costo = (move.aduana_cost + resultado + move.import_cost ) / move.product_qty
                    stock_move_obj.write(cr, uid, move.id, {
                        'cost': costo,
                        'price_unit': costo,
                    })

    def calculate_cost(self, cr, uid, ids, context=None):
        # Calculo de los costos totales
        stock_move_obj = self.pool.get('stock.move')
        total_productos = 0
        total_suma_procentajes = 0
        for rec in self.browse(cr, uid, ids, context=context):
            for move in rec.transport_stock_move_ids:
                costo = move.aduana_cost / move.product_qty

                stock_move_obj.write(cr, uid, move.id, {
                    'cost': costo,
                    'price_unit': costo,
                })

class purchase_import_api(models.Model):
    _inherit = "purchase.import"

    #@api.one
    #@api.depends('purchase_order_ids', 'purchase_order_ids.date_origen', 'purchase_order_ids.date_order')
    #def _date_origen(self):
        #if self.purchase_order_ids:
            #date_origen = self.purchase_order_ids[0].date_origen
            #date_order = self.purchase_order_ids[0].date_order
            #for order in self.purchase_order_ids:
                #if order.date_origen > date_origen:
                    #date_origen = order.date_origen
                #if order.date_order > date_order:
                    #date_order = order.date_order
            #self.date_origin = date_origen
            #self.dates = date_order

    flete_currency = fields.Float(string='Flete en divisa', digits=dp.get_precision('Account'), states={'finished':[('readonly',True)]})
    incoterm_id = fields.Many2one('stock.incoterms', string="Incoterm", required=True, states={'finished':[('readonly',True)]})
    #dates = fields.Date(string='Fecha Estimada', readonly=True, store=True, compute="_date_origen")
    #date_origin = fields.Date(string='Fecha Estimada', readonly=True, store=True, compute="_date_origen")


    @api.onchange('currency_rate')
    def onchange_rate(self):
        if self.currency_rate:
            if self.flete_currency:
                self.value_flete = self.flete_currency*self.currency_rate
            if self.value_flete:
                self.flete_currency = self.value_flete/self.currency_rate

    @api.onchange('flete_currency')
    def onchange_flete_currency(self):
        if self.flete_currency and self.currency_rate:
            self.value_flete = self.flete_currency*self.currency_rate

    @api.onchange('value_flete')
    def onchange_value_flete(self):
        if self.value_flete and self.currency_rate:
            self.flete_currency = self.value_flete/self.currency_rate

class bl_doc(models.Model):
    _name = 'bl.doc'

    name = fields.Char(string='Nº B/L' , size=32, required=True)
    doc = fields.Boolean(string='DOC. OR')
    shipment_date = fields.Date(string='Fecha De Embarque')
    arrival_date = fields.Date(string='Fecha De Arribo A Puerto')
    crtn = fields.Char(string='Crtn' , size=32)
    klgr = fields.Float(string='KLGR', digits=(16, 2))
    m3 = fields.Float(string='M3', digits_compute=dp.get_precision('Account'))
    transcribing_imp = fields.Char(string='Registro De Imp.', size=32)
    policy_no = fields.Char(string='Poliza Nº' , size=32)
    comment = fields.Text(string='comment', readonly=True)
    purchase_import_id = fields.Many2one('purchase.import', string='Purchase Import Ref')

#
