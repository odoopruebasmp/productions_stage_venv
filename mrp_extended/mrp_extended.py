# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
# from openerp.tools.translate import _
from openerp import addons
from openerp import SUPERUSER_ID
import itertools
from dateutil.relativedelta import relativedelta
from lxml import etree
from openerp import models, api, _, fields as fields2
from openerp.osv import osv, fields 
from openerp.exceptions import except_orm, Warning, RedirectWarning
import openerp.addons.decimal_precision as dp
import math

class product_template(osv.osv):
    _inherit = 'product.template'

    _columns= {
        'default_code': fields.related('product_variant_ids', 'default_code', type='char', string='Internal Reference', track_visibility='onchange'),
        'name': fields.char('Name', required=True, translate=True, select=True, track_visibility='onchange'),
        'active': fields.boolean('Active', help="If unchecked, it will allow you to hide the product without removing it.", track_visibility='onchange'),
    }

class product_product(osv.osv):
    _inherit = 'product.product'
    
    def _check_uom_bom(self, cr, uid, ids, context=None):
        for product in self.browse(cr, uid, ids, context=context):
            bom_line = self.pool.get('mrp.bom.line').search(cr, uid, [('product_id','=',product.id)], context=context)
            if bom_line:
                return False
            bom = self.pool.get('mrp.bom').search(cr, uid, [('product_id','=',product.id)], context=context)
            if bom:
                return False
        return True

    _columns = {
        'default_code' : fields.char('Internal Reference', select=True, track_visibility='onchange'),
        'active': fields.boolean('Active', help="If unchecked, it will allow you to hide the product without removing it.", track_visibility='onchange'),
    }

    _constraints = [
        (_check_uom_bom, 'No es posible modifica la unidad de medida. El producto se encuentra asociado a una lista de materiales', ['uom_id']),
    ]

class mrp_routing(osv.osv):
    _inherit = "mrp.routing" 
    
    def _costo(self, cr, uid, ids, name, args, context=None):
        res = {}
        for routing in self.browse(cr, uid, ids, context=context):
            sum = 0
            for workcenter in routing.workcenter_lines:
                sum += workcenter.cost
            res[routing.id] = sum
        return res
    
    _columns = {
        'cost': fields.function(_costo, digits_compute=dp.get_precision('Account'), string='Costo', type='float', readonly=True),
    }

class mrp_workcenter(osv.osv):
    _inherit = "mrp.workcenter" 
    
    def _costo(self, cr, uid, ids, name, args, context=None):
        res = {}
        for workcenter in self.browse(cr, uid, ids, context=context):
            costo_hora = workcenter.costs_hour
            if not costo_hora:
                costo_hora = workcenter.product_id and workcenter.product_id.standard_price or 0
            if workcenter.time_efficiency <= 0.0:
                raise osv.except_osv(_('Error!'), _('El valor de la eficiencia no puede ser igual o inferior a cero, por favor valide la parametrizacion.'))
            elif workcenter.time_efficiency > 1.0:
                raise osv.except_osv(_('Error!'), _('El valor de la eficiencia no puede ser mayor a uno, por favor valide la parametrizacion.'))
            
            if workcenter.costs_cycle > 0.0 and workcenter.costs_hour > 0.0:
                raise osv.except_osv(_('Error!'), _('Solo es permitido gestionar costeo por hora o ciclo, por favor debe configurar el costo de la hora o del ciclo'))
            if workcenter.capacity_per_cycle > 0:
                cost = ((costo_hora*(workcenter.time_cycle+workcenter.time_start+workcenter.time_stop)+workcenter.costs_cycle)/workcenter.time_efficiency)/workcenter.capacity_per_cycle    
                
            else:
                cost = ((costo_hora*(workcenter.time_cycle+workcenter.time_start+workcenter.time_stop)+workcenter.costs_cycle)/workcenter.time_efficiency)
                
            res[workcenter.id] = cost
            if workcenter.type_cost == 'variable':
                res[workcenter.id] = 0.0
        return res
    
    _columns = {
        'total_cost_for_cycle': fields.function(_costo, digits_compute=dp.get_precision('Account'), string='Costo de un Ciclo', type='float', readonly=True),
        'type_cost': fields.selection([('proporcional', 'Proporcional'), ('fijo', 'Fijo'), ('variable', 'Variable')], string='Metodo de Calculo', required=True),
        'mrp_working_workcenter_range_ids': fields.one2many('mrp.routing.workcenter.range', 'mrp_working_workcenter_id2','Rangos'),
    }
    
    _defaults= {
        'type_cost': 'proporcional',
    }

class mrp_routing_workcenter(models.Model):
    _inherit = "mrp.routing.workcenter" 

    @api.one
    @api.depends('hour_nbr', 'workcenter_id')
    def _costo(self):
        if self.workcenter_id:
            self.cost = self.workcenter_id.total_cost_for_cycle*self.cycle_nbr

    @api.one
    @api.depends('workcenter_id', 'cycle_nbr')
    def _hour(self):
        if self.workcenter_id:
            self.hour_nbr = (self.workcenter_id.time_cycle+self.workcenter_id.time_start+self.workcenter_id.time_stop)*self.cycle_nbr

    cost = fields2.Float(compute="_costo", digits=dp.get_precision('Account'), string='Costo', readonly=True)
    type_cost = fields2.Selection([('proporcional', 'Proporcional'), ('fijo', 'Fijo'), ('variable', 'Variable')], string='Metodo de Calculo', related="workcenter_id.type_cost", readonly=True)
    attribute_value_ids = fields2.Many2many('product.attribute.value', string='Variantes', help="BOM Product Variants needed form apply this line.")
    hour_nbr = fields2.Float(string="Total Horas", compute="_hour", readonly=True)
    
    
class mrp_working_workcenter_range(osv.osv):
    _name = "mrp.routing.workcenter.range" 
        
    _columns = {
        'size_1': fields.float('Rango Inferior', required=True),
        'size_2': fields.float('Rango Superior', required=True),
        'cost': fields.float(digits_compute=dp.get_precision('Account'), string='Costo', required=True),
        'mrp_working_workcenter_id2': fields.many2one('mrp.workcenter', 'Operacion'),
    }
    
class mrp_bom_line(osv.osv):
    _inherit = "mrp.bom.line" 
    
    def _check_uom_product(self, cr, uid, ids, context=None):
        for bom_line in self.browse(cr, uid, ids, context=context):
            if bom_line.product_id and bom_line.product_uom and bom_line.product_id.uom_id and bom_line.product_id.uom_id.category_id != bom_line.product_uom.category_id:
                return False                 
        return True
    
    def _costo_productos(self, cr, uid, ids, name, args, context=None):
        res = {}
        for bom_padre in self.browse(cr, uid, ids, context=context):
            res[bom_padre.id] = self.get_products_cost(cr, uid, bom_padre, context=context)
        return res
    
    _columns = {
        'products_cost': fields.function(_costo_productos, digits_compute=dp.get_precision('Account'), string='Costo Productos', type='float', readonly=True),
        'tolerancia': fields.float('% Tolerancia Adicional', digits_compute=dp.get_precision('Product Unit of Measure'),help="Ejemplo: se necesitan 100 unidades del producto A, si tengo tolerancia de 10, solo puedo consumir un maximo de 110 del producto A, y tendria que consumir un minimo 90, -1 se desactiva"),
        'tolerancia_inferior': fields.float('% Tolerancia Inferior', digits_compute=dp.get_precision('Product Unit of Measure'),help="Ejemplo: se necesitan 100 unidades del producto A, si tengo tolerancia de 10, solo puedo consumir un maximo de 110 del producto A, y tendria que consumir un minimo 90, -1 se desactiva"),
    }
    
    _defaults= {
        'tolerancia': -1,
        'tolerancia_inferior': -1,
    }
    
    _constraints = [
        (_check_uom_product, 'La unidad que intenta asociar a la lista de materiales no es valida, por favor valide la configuracion del producto', ['product_uom']),
    ]
    
    def get_products_cost(self, cr, uid, bom_padre, context=None):
        uom_obj = self.pool.get('product.uom')
        product_qty = uom_obj._compute_qty(cr, uid, bom_padre.product_uom.id, bom_padre.product_qty, bom_padre.product_id.uom_id.id)
        sum = bom_padre.product_id.standard_price*product_qty
        return sum

class mrp_bom(osv.osv):
    _inherit = "mrp.bom" 
    
    def _costo_productos(self, cr, uid, ids, name, args, context=None):
        res = {}
        for bom_padre in self.browse(cr, uid, ids, context=context):
            res[bom_padre.id] = self.get_products_cost(cr, uid, bom_padre, context=context)
        return res
    
    def _costo_operaciones(self, cr, uid, ids, name, args, context=None):
        res = {}
        for bom_padre in self.browse(cr, uid, ids, context=context):
            cost = 0
            qty = bom_padre.product_qty
            for line in bom_padre.routing_id.workcenter_lines:
                if line.workcenter_id.type_cost == 'variable':
                    for lines in line.workcenter_id.mrp_working_workcenter_range_ids:
                        if qty >= lines.size_1 and qty <= lines.size_2:
                            cost += lines.cost
                else:
                    cost += line.cost
            res[bom_padre.id] = cost
        return res

    def _costo_total(self, cr, uid, ids, name, args, context=None):
        res = {}
        for bom_padre in self.browse(cr, uid, ids, context=context):
            res[bom_padre.id] = bom_padre.operaciones_cost+bom_padre.products_cost
        return res

    _columns = {
        'total_cost': fields.function(_costo_total, digits_compute=dp.get_precision('Account'), string='Costo Total', type='float', readonly=True),
        'products_cost': fields.function(_costo_productos, digits_compute=dp.get_precision('Account'), string='Costo Productos', type='float', readonly=True),
        'operaciones_cost': fields.function(_costo_operaciones, digits_compute=dp.get_precision('Account'), string='Costo Operaciones', type='float', readonly=True),
    }


    def get_products_cost(self, cr, uid, bom_padre, context=None):
        sum=0.0
        uom_obj = self.pool.get('product.uom')
        bom_line_obj = self.pool.get('mrp.bom.line')
        if len(bom_padre.bom_line_ids) == 0:
            sum = 0
        else:
            for bom in bom_padre.bom_line_ids:
                sum += bom_line_obj.get_products_cost(cr, uid, bom, context=context)
        return sum


class mrp_production_workcenter_line(osv.osv):
    _inherit = "mrp.production.workcenter.line" 

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if vals.get('hour', False):
            workcenter_id = self.pool.get('mrp.workcenter').browse(cr, uid, vals.get('workcenter_id', False), context=context)
            if workcenter_id and workcenter_id.type_cost == 'fijo':
                vals.update({'hour': (vals.get('hour', False)/2)/vals.get('cycle', False), 'cycle': (vals.get('cycle', False))/vals.get('cycle', False)})
            else:
                vals.update({'hour': vals.get('hour', False)/2, 'cycle': vals.get('cycle', False)/vals.get('cycle', False)})
            
        result = super(mrp_production_workcenter_line, self).create(cr, uid, vals, context=context)
        return result 

    def _costo(self, cr, uid, ids, name, args, context=None):
        res = {}
        qty = 0.0
        for workcenter in self.browse(cr, uid, ids, context=context):
            qty = workcenter.production_id.product_qty/workcenter.production_id.bom_id.product_qty
            if workcenter.workcenter_id.type_cost == 'fijo':
                res[workcenter.id] = workcenter.workcenter_id.total_cost_for_cycle*workcenter.cycle
            elif workcenter.workcenter_id.type_cost == 'proporcional':
                if workcenter.hour == 0.0:
                    res[workcenter.id] = workcenter.workcenter_id.total_cost_for_cycle*workcenter.cycle
                else:
                    res[workcenter.id] = workcenter.workcenter_id.costs_hour*workcenter.hour
            elif workcenter.workcenter_id.type_cost == 'variable':
                for line in workcenter.workcenter_id.mrp_working_workcenter_range_ids:
                    if qty >= line.size_1 and qty <= line.size_2:
                        res[workcenter.id] = line.cost
        return res


    def action_done(self, cr, uid, ids, context=None):
        account_move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        production_obj = self.pool.get('mrp.production')
        
        result = super(mrp_production_workcenter_line, self).action_done(cr, uid, ids, context=context)
        for workcenter_line in self.browse(cr, uid, ids, context=context):
            if workcenter_line.production_id and workcenter_line.production_id.product_id.categ_id and workcenter_line.production_id.product_id.categ_id.journal_production_id:                
                period_id = account_move_obj._get_period(cr, SUPERUSER_ID, context)
                date = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                journal_id = workcenter_line.production_id.product_id.categ_id.journal_production_id                
                debit_account = workcenter_line.production_id.product_id.categ_id and  workcenter_line.production_id.product_id.categ_id.account_production_transit_id.id or False
                credit_account = workcenter_line.workcenter_id and workcenter_line.workcenter_id.costs_general_account_id and workcenter_line.workcenter_id.costs_general_account_id.id or False
                analytic_account_id = False
                
                if not debit_account:
                    raise osv.except_osv(_('Error!'), _('Debe configurar una cuenta para la gestion de productos en proceso para la categoria "%s"' % workcenter_line.production_id.categ_id.name))
                
                if not credit_account:
                    raise osv.except_osv(_('Error!'), _('Debe configurar una cuenta para el centro de produccion "%s"' % workcenter_line.name))
                
                if not period_id:
                    raise osv.except_osv(_('Error!'), _('No se encontro un periodo para la fecha "%s"' % date))
                                
                if workcenter_line.production_id.move_product_process_id:
                    move_id = workcenter_line.production_id.move_product_process_id.id
                else:                
                    move_vals = {
                        'name': 'P. Proceso'+' '+workcenter_line.production_id.name,
                        'date': date,
                        'ref': workcenter_line.production_id.name,
                        'period_id': period_id,
                        'journal_id': journal_id.id,
                        'company_id': journal_id.company_id.id
                        }                
                    move_id = account_move_obj.create(cr, uid, move_vals, context=context)
                    production_obj.write(cr, uid, [workcenter_line.production_id.id], {'move_product_process_id':  move_id}, context=context)
                
                if workcenter_line.production_id.company_id.analytic_default:
                    analytic_account_id = workcenter_line.production_id.product_id.categ_id.account_production_analytic_id and workcenter_line.production_id.product_id.categ_id.account_production_analytic_id.id
                    if not analytic_account_id:
                        raise osv.except_osv(_('Configuration !'), _("El sistema esta configurado para requerir la cuenta analitica en el proceso de produccion, sin embargo no logra encontrar una cuenta analitica configurada en la categoria '%s'. Por favor 'CONSULTAR CON EL AREA ENCARGADA." % workcenter_line.production_id.product_id.categ_id.name))
                
                partner_id = journal_id.company_id.partner_id
                move_line_obj.create(cr, uid, {
                    'name': workcenter_line.name,
                    'ref': workcenter_line.production_id.name,
                    'move_id': move_id,
                    'account_id': debit_account,
                    'debit': workcenter_line.cost,
                    'credit': 0.0,
                    'period_id': period_id,
                    'journal_id': journal_id.id,
                    'partner_id': partner_id.id,
                    'date': date,
                    'product_id': workcenter_line.production_id.product_id.id,
                    'mrp_id': workcenter_line.production_id.id,
                    'quantity': workcenter_line.cycle,
                    'analytic_account_id': analytic_account_id or False,
                })
                move_line_obj.create(cr, uid, {
                    'name': workcenter_line.name,
                    'ref': workcenter_line.production_id.name,
                    'move_id': move_id,
                    'account_id': credit_account,
                    'debit': 0.0,
                    'credit': workcenter_line.cost,
                    'period_id': period_id,
                    'journal_id': journal_id.id,
                    'partner_id': partner_id.id,
                    'date': date,
                    'analytic_account_id': analytic_account_id or False,
                })            
        return result 
    
    
    _columns = {
        'cost': fields.function(_costo, digits_compute=dp.get_precision('Account'), string='Costo', type='float', store=True, readonly=True),
        'hour': fields.float('Number of Hours', digits=(16, 6)),
        'type_cost': fields.related('workcenter_id', 'type_cost', type='char', string='Metodo de Calculo', readonly=True, store=True),
        'product':fields.related('production_id','product_id',type='many2one',relation='product.product',string='Product',
            readonly=True, store=True),
    }
        
class mrp_production_product_line(osv.osv):
    _inherit = "mrp.production.product.line" 
    
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if not vals.get('cost'):
            production_pool = self.pool.get('mrp.production')
            production = production_pool.browse(cr, uid, vals['production_id'], context=context)
            location_src_id = production.location_src_id
            context.update({'location_w_id': location_src_id.id})
            product_qty = self.pool.get('product.uom')._compute_qty(cr, uid, vals.get('product_uom'), vals.get('product_qty'), self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context=context).uom_id.id)
            standard_price = self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context=context).standard_price
            vals.update({'cost':standard_price*product_qty})

        result = super(mrp_production_product_line, self).create(cr, uid, vals, context=context)
        return result 
    
    def _eficiencia(self, cr, uid, ids, name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.consumido_qty:
                res[line.id] = line.product_qty/line.consumido_qty*100
            else:
                res[line.id] = 0
        return res
    
    _columns = {
        'date_planned': fields.related('production_id', 'date_planned', type='datetime', string='Fecha', readonly=True, store=True),
        'cost': fields.float('Costo Planeado', digits_compute=dp.get_precision('Account'), readonly=True),
        'consume_cost': fields.float('Costo Consumido', digits_compute=dp.get_precision('Account'), readonly=True),
        'consumido_qty': fields.float('Consumido', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),
        'eficiencia': fields.function(_eficiencia, digits_compute=dp.get_precision('Product Unit of Measure'), string='% Eficiencia', type='float', readonly=True, store=True),
    }
    
    
    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, lazy=True):
        if context is None:
            context = {}
        if 'product_qty' not in fields:
            fields.append('product_qty')
        if 'consumido_qty' not in fields:
            fields.append('consumido_qty')
        result = super(mrp_production_product_line, self).read_group(cr, uid, domain, fields, groupby, offset, limit, context, orderby, lazy)
        for res in result:
            if res['consumido_qty']:
                res.update({'eficiencia':res['product_qty']/res['consumido_qty']*100})
        return result

class stock_production_lot(osv.osv):
    _inherit = "stock.production.lot"
    
    _columns = {
        'create_date':fields.datetime('Fecha de Formulacion'),
    }
    
    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if context.get('filter_reserved_lots',False):
            move = self.pool.get('stock.move').browse(cr, user, context['move_id'], context=context)
            args += [('id','in',[x.id for x in move.lot_ids])]
        return super(stock_production_lot,self).name_search(cr, user, name=name, args=args, operator=operator, context=context, limit=limit)


class account_move_line(models.Model):
    _inherit = "account.move.line"
    
    mrp_id = fields2.Many2one('mrp.production', string="Production", readonly=True)
    state_mrp = fields2.Selection(string='State MRP', related='mrp_id.state', readonly=True, store=True)
    

class stock_move(osv.osv):
    _inherit = "stock.move"
    
    _columns = {
        'adicional': fields.boolean('Adicional', readonly=True),
        'adicional_aux': fields.boolean('Adicional'),
        'raw_material_production_id': fields.many2one('mrp.production', 'Orden de Produccion', select=True),
        'acopio_production_id': fields.many2one('mrp.production', 'Orden de Produccion', select=True),
        'qty_available': fields.related('product_id', 'qty_available', type='float', string='Disponible', readonly=True),
        'product_uom_id': fields.related('product_id', 'uom_id', type='many2one', relation='product.uom', string='Unidad de Medida', readonly=True),
    }
    
    def action_consume(self, cr, uid, ids, product_qty, location_id=False, restrict_lot_id=False, restrict_partner_id=False,consumed_for=False, context=None):
        production_obj = self.pool.get('mrp.production')
        account_move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        res = super(stock_move, self).action_consume(cr, uid, ids, product_qty, location_id=location_id, restrict_lot_id=restrict_lot_id, restrict_partner_id=restrict_partner_id,consumed_for=consumed_for, context=context)
        for move in self.browse(cr, uid, ids, context=context):
            total_cost = move.product_id.standard_price * move.product_qty
            cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=%s, costo_promedio=%s WHERE id = %s''',
                       (move.product_id.standard_price, total_cost, move.product_id.standard_price, move.id))
            if move.raw_material_production_id and move.raw_material_production_id.product_id and move.raw_material_production_id.product_id.categ_id and move.raw_material_production_id.product_id.categ_id.journal_production_id:
                period_id = account_move_obj._get_period(cr, SUPERUSER_ID, context)
                date = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                journal_id = move.raw_material_production_id.product_id.categ_id.journal_production_id                
                debit_account = move.raw_material_production_id.product_id.categ_id and  move.raw_material_production_id.product_id.categ_id.account_production_transit_id.id or False
                credit_account = move.product_id.categ_id and  move.product_id.categ_id.property_stock_account_output_categ.id or move.product_id.property_stock_account_output and  move.product_id.property_stock_account_output.id or False
                total_cost = move.product_id.standard_price*move.product_qty
                cr.execute(''' UPDATE stock_move SET cost=%s, total_cost=%s, costo_promedio=%s WHERE id = %s''',(move.product_id.standard_price, total_cost, move.product_id.standard_price, move.id))
                if not debit_account:
                    raise osv.except_osv(_('Error!'), _('Debe configurar una cuenta para la gestion de productos en proceso para la categoria "%s"' % move.raw_material_production_id.product_id.categ_id.name))
                
                if not credit_account:
                    raise osv.except_osv(_('Error!'), _('Debe configurar una cuenta de salida de stock para el producto "%s", o su categoria' % move.product_id.name))
                
                if not period_id:
                    raise osv.except_osv(_('Error!'), _('No se encontro un periodo para la fecha "%s"' % date))
                
                if move.raw_material_production_id.move_product_process_id:
                    move_id = move.raw_material_production_id.move_product_process_id.id
                else:                
                    move_vals = {
                        'name': 'P. Proceso'+' '+move.raw_material_production_id.name,
                        'date': date,
                        'ref': move.raw_material_production_id.name,
                        'period_id': period_id,
                        'journal_id': journal_id.id,
                        'company_id': journal_id.company_id.id
                        }                
                    move_id = account_move_obj.create(cr, uid, move_vals, context=context)
                    production_obj.write(cr, uid, [move.raw_material_production_id.id], {'move_product_process_id':  move_id}, context=context)
                
                partner_id = journal_id.company_id.partner_id
                move_line_obj.create(cr, uid, {
                    'name': move.product_id.name,
                    'ref': move.raw_material_production_id.name,
                    'move_id': move_id,
                    'account_id': debit_account,
                    'debit': total_cost,
                    'credit': 0.0,
                    'period_id': period_id,
                    'journal_id': journal_id.id,
                    'partner_id': partner_id.id,
                    'date': date,
                    'product_id': move.raw_material_production_id.product_id.id,
                    'mrp_id': move.raw_material_production_id.id,
                    'quantity': move.product_qty,
                })
                move_line_obj.create(cr, uid, {
                    'name': move.product_id.name,
                    'ref': move.raw_material_production_id.name,
                    'move_id': move_id,
                    'account_id': credit_account,
                    'debit': 0.0,
                    'credit': total_cost,
                    'period_id': period_id,
                    'journal_id': journal_id.id,
                    'partner_id': partner_id.id,
                    'date': date,
                })            
            self.write(cr, uid, res, {'consumed_for':  move.id}, context=context)
            
        
    
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        raw_material_production_id = vals.get('raw_material_production_id', False)
        product_id = vals.get('product_id', False)
        production_id = vals.get('production_id', False)
        if raw_material_production_id and product_id:
            production = self.pool.get('mrp.production').browse(cr, uid, raw_material_production_id, context=context)
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            if not product.property_stock_production:
                raise osv.except_osv(_('Error !'),_("La ubicacion de produccion para el producto '%s' no esta configurada")%(product.name))
            location_dest_id = vals.get('location_dest_id', False) or product.property_stock_production.id
            
            if production.routing_id and production.routing_id.location_id:
                location_id = production.routing_id.location_id.id
            else:
                location_id = production.location_src_id.id
            vals.update({'adicional':vals.get('adicional_aux', False), 'name': production.name+' '+production.location_src_id.name, 'location_id':location_id,'location_dest_id': location_dest_id})
        elif production_id and product_id:
            production = self.pool.get('mrp.production').browse(cr, uid, production_id, context=context)
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            if not product.property_stock_production:
                raise osv.except_osv(_('Error !'),_("La ubicacion de produccion para el producto '%s' no esta configurada")%(product.name))
            location_dest_id = vals.get('location_dest_id', False) or production.location_dest_id.id
            vals.update({'product_uom': production.product_uom.id,'adicional':vals.get('adicional_aux', False), 'name': production.name+' '+production.location_dest_id.name, 'location_id':product.property_stock_production.id,'location_dest_id': location_dest_id})
            
        result = super(stock_move, self).create(cr, uid, vals, context=context)
        return result
    
    
    
    def write(self, cr, uid, ids, vals, context=None):
        uom_obj = self.pool.get('product.uom')
        production_obj = self.pool.get('mrp.production')
        state_new = vals.get('state',False)
        if ids is int:
            ids = [ids]
        result = super(stock_move, self).write(cr, uid, ids, vals, context=context) 
        for move in self.browse(cr, uid, ids, context=context):
            if move.raw_material_production_id and state_new and state_new in ['confirmed', 'assigned', 'done']: 
                production_obj.check_limite_superior(cr, uid, [move.raw_material_production_id.id], context=context)
        return result
    
    def split_quantities(self, cr, uid, ids, vals, context=None):
        move = False
        for det in self.browse(cr, uid, ids, context=context):
            if det.product_uom_qty>1:
                det.product_uom_qty = (det.product_uom_qty-1)
                move = self.copy(cr, uid, det.id, default={
                    'product_uom_qty': 1,
                    'restrict_lot_id': False,
                    'quant_ids': [],}
                ,context=context)
        return move

class mrp_production(osv.osv):
    _inherit = "mrp.production" 
    _order = "name desc"
    
    def check_limite_superior(self, cr, uid, ids, context=None):
        uom_obj = self.pool.get('product.uom')
        for record in self.browse(cr, uid, ids, context=context):
            for bom in record.bom_id.bom_line_ids:
                if bom.tolerancia >= 0:
                    adicional_qty = 0
                    if record.state not in ['confirmed','ready','in_production','done']:
                        for line in record.product_lines:
                            if bom.product_id.id == line.product_id.id:
                                adicional_qty += uom_obj._compute_qty(cr, uid, line.product_uom.id, line.product_qty, line.product_id.uom_id.id)
                    else:
                        for move2 in record.move_lines2:
                            if move2.state!= 'cancel' and bom.product_id.id == move2.product_id.id:
                                adicional_qty += uom_obj._compute_qty(cr, uid, move2.product_uom.id, move2.product_qty, move2.product_id.uom_id.id)
                        
                    raw_qty = uom_obj._compute_qty(cr, uid, record.product_uom.id, record.product_qty, record.product_id.uom_id.id)
                    bom_raw_qty = uom_obj._compute_qty(cr, uid, record.bom_id.product_uom.id, record.bom_id.product_qty, record.bom_id.product_id.uom_id.id)
                    limite = (raw_qty/bom_raw_qty)*(bom.product_qty+((bom.tolerancia/100)*bom.product_qty))
                    if adicional_qty > limite:
                        ir_model_data = self.pool.get('ir.model.data')
                        group_id = ir_model_data.get_object_reference(cr, uid, 'mrp_extended', 'group_user_mrp_no_limits')[1]
                        user_obj = self.pool.get('res.users').browse(cr, uid, uid, context=context)
                        if group_id not in [x.id for x in user_obj.groups_id]:
                            raise osv.except_osv(_('Error !'),_("El limite de consumo de '%s' se a superado para el producto '%s', la suma de consumos, da un total de '%s', es necesario que alguien perteneciente al grupo de adicionales haga esta accion") % (limite,bom.product_id.name,adicional_qty))
        return True
        
    def check_limite_inferior(self, cr, uid, ids, context=None):
        uom_obj = self.pool.get('product.uom')
        for record in self.browse(cr, uid, ids, context=context):
            for bom_product in record.bom_id.bom_line_ids:
                raw_qty = uom_obj._compute_qty(cr, uid, record.product_uom.id, record.product_qty, record.product_id.uom_id.id)
                bom_raw_qty = uom_obj._compute_qty(cr, uid, record.bom_id.product_uom.id, record.bom_id.product_qty, record.bom_id.product_id.uom_id.id)
                limite_inferior = (record.product_qty/record.bom_id.product_qty)*((bom_product.tolerancia_inferior/100)*bom_product.product_qty)
                usado = 0
                if bom_product.tolerancia_inferior >= 0:
                    if record.state not in ['confirmed','ready','in_production','done']:
                        for line in record.product_lines:
                            if bom_product.product_id.id == line.product_id.id:
                                usado += uom_obj._compute_qty(cr, uid, line.product_uom.id, line.product_qty, line.product_id.uom_id.id)
                    else:
                        for move2 in record.move_lines2:
                            if move2.state!= 'cancel' and bom_product.product_id.id == move2.product_id.id:
                                usado += uom_obj._compute_qty(cr, uid, move2.product_uom.id, move2.product_qty, move2.product_id.uom_id.id)
                    if usado < limite_inferior:
                        ir_model_data = self.pool.get('ir.model.data')
                        group_id = ir_model_data.get_object_reference(cr, uid, 'mrp_extended', 'group_user_mrp_no_limits')[1]
                        user_obj = self.pool.get('res.users').browse(cr, uid, uid, context=context)
                        if group_id not in [x.id for x in user_obj.groups_id]:
                            raise osv.except_osv(_('Error !'),_("El limite inferior de consumo de '%s' no se a cumplido para el producto '%s', la suma de cantidades da un total de '%s', es necesario que alguien perteneciente al grupo de adicionales haga esta accion") % (limite_inferior,bom_product.product_id.name,usado))
        return True
        
    def _costos(self, cr, uid, ids, field_name, arg, context=None):
        res = dict([(id, 
            {
            'planned_cost': 0, 
            'consumos_cost': 0,
            'desechos_cost': 0,
            'operaciones_cost': 0,
            'adiciones_cost': 0,
            'total_consumos_cost': 0,
            'production_cost': 0,
            'planned_operations_cost': 0,
            }
        ) for id in ids])
        
        for record in self.browse(cr, uid, ids, context=context):
            planned_cost = 0
            consumos_cost = 0
            desechos_cost = 0
            operaciones_cost = 0
            adiciones_cost = 0
            total_consumos_cost = 0
            production_cost = 0
            planned_total = 0
            planned_operations_cost = 0
            operaciones2_cost = 0
            
            for line in record.product_lines:
                planned_cost += line.cost
                
            for move in record.move_lines2:
                if move.state != 'cancel':
                    if move.location_dest_id.scrap_location:
                        desechos_cost += move.total_cost
                    elif move.adicional:
                        adiciones_cost += move.total_cost
                    else:
                        consumos_cost += move.total_cost
                
            for center in record.workcenter_lines:
                operaciones_cost += center.cost
                if center.state == 'done':
                    operaciones2_cost += center.cost
            
            res[record.id]['planned_cost'] = planned_cost
            res[record.id]['consumos_cost'] = consumos_cost
            res[record.id]['operaciones_cost'] = operaciones2_cost
            
            res[record.id]['desechos_cost'] = desechos_cost
            res[record.id]['adiciones_cost'] = adiciones_cost
            
            total_consumos_cost=consumos_cost+desechos_cost+adiciones_cost
            res[record.id]['total_consumos_cost'] = total_consumos_cost
            res[record.id]['production_cost'] = total_consumos_cost+operaciones2_cost
            
            if record.state != 'draft':
                planned_operations_cost = record.planned_operations_cost_hidden
            else:
                planned_operations_cost = operaciones_cost
            
            res[record.id]['planned_operations_cost'] = planned_operations_cost
            res[record.id]['planned_total'] = planned_cost+planned_operations_cost
            
        return res
    
    def _eficiencia(self, cr, uid, ids, name, args, context=None):
        res = dict([(id, 
            {
            'produced_product_qty': 0, 
            'remaining_product_qty': 0, 
            'eficiencia': 0, 
            'eficiencia_precio': 0,
            'eficiencia_cantidad': 0,
            }
        ) for id in ids])
        for record in self.browse(cr, uid, ids, context=context):
            produced_product_qty = 0
            remaining_product_qty = 0
            for move in record.move_created_ids2:
                if move.state != 'cancel' and not move.scrapped and move.product_id.id == record.product_id.id:
                    produced_product_qty += move.product_qty
            for move in record.move_created_ids:
                if move.state != 'draft':
                    remaining_product_qty += move.product_qty
            if record.product_qty and record.production_cost:
                eficiencia_cantidad = produced_product_qty/record.product_qty
                eficiencia_precio = record.planned_total/record.production_cost
                eficiencia = eficiencia_cantidad*eficiencia_precio
                res[record.id]['eficiencia_cantidad'] = eficiencia_cantidad*100
                res[record.id]['eficiencia_precio'] = eficiencia_precio*100
                res[record.id]['eficiencia'] = eficiencia*100
            res[record.id]['remaining_product_qty'] = remaining_product_qty
            res[record.id]['produced_product_qty'] = produced_product_qty
        return res
    
    def _get_from_move_raw(self, cr, uid, ids, context=None):
        list = []
        stock_move_pool = self.pool.get('stock.move')
        for move in stock_move_pool.browse(cr, uid, ids, context=context):
            if move.raw_material_production_id:
                list+=[move.raw_material_production_id.id]
        return list
        
    def _get_from_workcenter_line(self, cr, uid, ids, context=None):
        list = []
        workcenter_line_pool = self.pool.get('mrp.production.workcenter.line')
        for workcenter_line in workcenter_line_pool.browse(cr, uid, ids, context=context):
            if workcenter_line.production_id:
                list+=[workcenter_line.production_id.id]
        return list
    
    def _get_from_move(self, cr, uid, ids, context=None):
        list = []
        stock_move_pool = self.pool.get('stock.move')
        for move in stock_move_pool.browse(cr, uid, ids, context=context):
            if move.production_id:
                list+=[move.production_id.id]
        return list
    
    _columns = {
        'notes' : fields.text('Observaciones'),
        'planned_cost': fields.function(_costos,  multi='costos', digits_compute=dp.get_precision('Account'), string='Costo Productos Planificado', type='float', readonly=True, store={
                                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                'stock.move': (_get_from_move_raw, ['state'], 10),
                                'mrp.production.workcenter.line': (_get_from_workcenter_line, ['state'], 10),
                            }),
        'planned_total': fields.function(_costos,  multi='costos', digits_compute=dp.get_precision('Account'), string='Costo Total Planificado', type='float', readonly=True, store={
                        'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                        'stock.move': (_get_from_move_raw, ['state'], 10),
                        'mrp.production.workcenter.line': (_get_from_workcenter_line, ['state'], 10),
                    }),
        'consumos_cost': fields.function(_costos,  multi='costos', digits_compute=dp.get_precision('Account'), string='Costo Productos Consumidos', type='float', readonly=True, store={
                                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                'stock.move': (_get_from_move_raw, ['state'], 10),
                                'mrp.production.workcenter.line': (_get_from_workcenter_line, ['state'], 10),
                            }),
        'total_consumos_cost': fields.function(_costos,  multi='costos', digits_compute=dp.get_precision('Account'), string='Costo Total Productos Consumidos', type='float', readonly=True, store={
                                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                'stock.move': (_get_from_move_raw, ['state'], 10),
                                'mrp.production.workcenter.line': (_get_from_workcenter_line, ['state'], 10),
                            }),
        'desechos_cost': fields.function(_costos,  multi='costos', digits_compute=dp.get_precision('Account'), string='Costo Productos Desechados', type='float', readonly=True, store={
                                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                'stock.move': (_get_from_move_raw, ['state'], 10),
                                'mrp.production.workcenter.line': (_get_from_workcenter_line, ['state'], 10),
                            }),
        'operaciones_cost': fields.function(_costos,  multi='costos', digits_compute=dp.get_precision('Account'), string='Costo Operaciones', type='float', readonly=True, store={
                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                'stock.move': (_get_from_move_raw, ['state'], 10),
                'mrp.production.workcenter.line': (_get_from_workcenter_line, ['state'], 10),
            }),
        'adiciones_cost': fields.function(_costos,  multi='costos', digits_compute=dp.get_precision('Account'), string='Costo Productos Adicionales', type='float', readonly=True, store={
                                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                'stock.move': (_get_from_move_raw, ['state'], 10),
                                'mrp.production.workcenter.line': (_get_from_workcenter_line, ['state'], 10),
                            }),
        'production_cost': fields.function(_costos,  multi='costos', digits_compute=dp.get_precision('Account'), string='Costo Total Produccion', type='float', readonly=True, store={
                        'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                        'stock.move': (_get_from_move_raw, ['state'], 10),
                        'mrp.production.workcenter.line': (_get_from_workcenter_line, ['state'], 10),
                    }),
        'planned_operations_cost': fields.function(_costos,  multi='costos', digits_compute=dp.get_precision('Account'), string='Costo Operaciones Planificado', type='float', readonly=True, store=True),
        'planned_operations_cost_hidden': fields.float('Costo Planificado de Operaciones', digits_compute=dp.get_precision('Account'), readonly=True),
        'move_lines': fields.one2many('stock.move', 'raw_material_production_id', 'Products to Consume',
            domain=[('state', 'not in', ('done', 'cancel'))], readonly=False, states={'draft':[('readonly',True)],'cancel':[('readonly',True)],'done':[('readonly',True)]}),
        'move_lines2': fields.one2many('stock.move', 'raw_material_production_id', 'Consumed Products',
            domain=[('state', 'in', ('done', 'cancel'))], readonly=True),
        'workcenter_lines': fields.one2many('mrp.production.workcenter.line', 'production_id', 'Work Centers Utilisation'
            , readonly=False, states={'cancel':[('readonly',True)],'done':[('readonly',True)],}),
        'account_move_id': fields.many2one('account.move', 'Comprobante Contable', readonly=True),
        'move_product_process_id': fields.many2one('account.move', 'Comprobante Productos en Proceso', readonly=True),
        'product_qty': fields.float('Product Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), required=True, readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange'),
        'produced_product_qty': fields.function(_eficiencia,  multi='eficiencia', digits_compute=dp.get_precision('Product Unit of Measure'), string='Cantidad Producida', type='float', readonly=True, store={
                                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                'stock.move': (_get_from_move, ['state'], 10),
                            }),
        'remaining_product_qty': fields.function(_eficiencia,  multi='eficiencia', digits_compute=dp.get_precision('Product Unit of Measure'), string='Cantidad Pendiente', type='float', readonly=True, store={
                                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                'stock.move': (_get_from_move, ['state'], 10),
                            }),
        'eficiencia_cantidad': fields.function(_eficiencia,  multi='eficiencia', digits_compute=dp.get_precision('Product Unit of Measure'), string='% Eficiencia Cantidad', type='float', readonly=True, store={
                                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                'stock.move': (_get_from_move, ['state'], 10),
                            }),
        'eficiencia_precio': fields.function(_eficiencia,  multi='eficiencia', digits_compute=dp.get_precision('Product Unit of Measure'), string='% Eficiencia Costos', type='float', readonly=True, store={
                                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                'stock.move': (_get_from_move, ['state'], 10),
                            }),
        'eficiencia': fields.function(_eficiencia,  multi='eficiencia', digits_compute=dp.get_precision('Product Unit of Measure'), string='% Eficiencia', type='float', readonly=True, store={
                                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, None,50),
                                'stock.move': (_get_from_move, ['state'], 10),
                            }),
        'move_created_ids': fields.one2many('stock.move', 'production_id', 'Products to Produce',
            domain=[('state', 'not in', ('done', 'cancel'))], readonly=False, states={'draft':[('readonly',True)],'cancel':[('readonly',True)],'done':[('readonly',True)]}),
    }
    
    _defaults = {
        'account_move_id': False,
        'move_product_process_id': False,
    }   
    
    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, lazy=True):
        if context is None:
            context = {}
        if 'product_qty' not in fields:
            fields.append('product_qty')
        if 'produced_product_qty' not in fields:
            fields.append('produced_product_qty')
        if 'production_cost' not in fields:
            fields.append('production_cost')
        if 'planned_total' not in fields:
            fields.append('planned_total')
        result = super(mrp_production, self).read_group(cr, uid, domain, fields, groupby, offset=offset, limit=limit, context=context, orderby=orderby, lazy=lazy)
        for res in result:
            eficiencia_cantidad = 0
            eficiencia_precio = 0
            if res['product_qty']:
                eficiencia_cantidad = res['produced_product_qty']/res['product_qty']
            if res['production_cost']:
                eficiencia_precio = res['planned_total']/res['production_cost']
            eficiencia = eficiencia_cantidad*eficiencia_precio
            res.update({
                        'eficiencia_cantidad': eficiencia_cantidad*100,
                        'eficiencia_precio':eficiencia_precio*100,
                        'eficiencia':eficiencia*100})
                
        return result
    
    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'account_move_id':False,
            'move_product_process_id':False,
            'move_created_ids': [],
            'move_created_ids2': [],
            'move_lines': [],
            'move_lines2': [],
        })
        return super(mrp_production, self).copy(cr, uid, id, default, context)
    
    def force_production(self, cr, uid, ids, *args):
        return True
    
    def _make_production_internal_shipment_line(self, cr, uid, production_line, shipment_id, parent_move_id, destination_location_id=False, context=None):
        move_id = super(mrp_production, self)._make_production_internal_shipment_line(cr, uid, production_line, shipment_id, parent_move_id, destination_location_id=destination_location_id, context=context)
        self.pool.get('stock.move').write(cr, uid, [move_id], {'acopio_production_id':production_line.production_id.id}, context=context)
        return move_id
        
    def action_produce(self, cr, uid, production_id, production_qty, production_mode, wiz=False, context=None):
        stock_move_pool = self.pool.get('stock.move')
        production = self.browse(cr, uid, production_id, context=context)
        # Actualizacion de costos
        if production_mode == 'consume_produce':

            costo_anterior = 0
            for move in production.move_created_ids2:
                costo_anterior += move.total_cost
            for move in production.move_created_ids:
                if wiz:
                    costo = wiz.product_id.standard_price
                else:
                    costo = (production.production_cost-costo_anterior)/production_qty
                stock_move_pool.write(cr, uid, [move.id], {'price_unit':costo,'cost':costo}, context=context)
        result = super(mrp_production, self).action_produce(cr, uid, production_id, production_qty, production_mode, wiz=wiz, context=context)
        return result
    
    def test_if_product(self, cr, uid, ids):
        result = super(mrp_production, self).test_if_product(cr, uid, ids)
        self.check_limite_inferior(cr, uid, ids, context={})
        self.check_limite_superior(cr, uid, ids, context={})
        return result
    
    def action_confirm(self, cr, uid, ids, context=None):
        result = super(mrp_production, self).action_confirm(cr, uid, ids, context=context)
        for production in self.browse(cr, uid, ids, context=context):
            operaciones_cost = 0
            for center in production.workcenter_lines:
                operaciones_cost += center.cost
            self.write(cr, uid, production.id, {'planned_operations_cost_hidden':operaciones_cost}, context=context)
        return result
    
    def action_production_end(self, cr, uid, ids, context=None):
        result = super(mrp_production, self).action_production_end(cr, uid, ids, context=context)
        #verificacion limite por debajo
        self.check_limite_inferior(cr, uid, ids, context=context)
        product_line_obj = self.pool.get('mrp.production.product.line')

        stock_move_pool = self.pool.get('stock.move')
        move_obj = self.pool.get('stock.move')
        stock_quant_pool = self.pool.get('stock.quant')
        product_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')

        stock_quant_pool = self.pool.get('stock.quant')
        for production in self.browse(cr, uid, ids):
            if len(production.move_lines) > 0:
                raise osv.except_osv(_('Error !'),_("No pueden haber insumos pendientes para consumir"))
            debit_sum = 0
            costo = 0.0
            costo_producto_final = 0.0
            production_qty = 0.0
            productos_consumidos={}
            location_ids = []
            cost_def=0.0
            costo_promedio=0.0

            for location in location_obj.search(cr, uid, [('usage','=','internal')], context=context):
                location_ids.append(location)
            location_ids = tuple(location_ids)
            for line_move in production.move_lines2:
                if line_move.state != 'cancel':
                    if line_move.product_id.id in productos_consumidos:
                        productos_consumidos[line_move.product_id.id]['qty'] += line_move.product_qty
                        productos_consumidos[line_move.product_id.id]['costo'] += line_move.cost*line_move.product_qty
                    else:
                        productos_consumidos[line_move.product_id.id] = {'product':line_move.product_id,'qty':line_move.product_qty,'costo':line_move.cost*line_move.product_qty}

            for line in production.product_lines:
                for product_line in productos_consumidos.values():
                    product = product_line['product']
                    qty = product_line['qty']
                    costo = product_line['costo']
                    if line.product_id.id == product.id:
                        product_line_obj.write(cr, uid, line.id , {'consumido_qty': qty,'consume_cost': costo}, context=context)
            self.create_account_move(cr, uid, production, productos_consumidos, context=context)
            for move in production.move_created_ids2:
                if move.state == 'done':
                    production_qty += move.product_qty
            for move in production.move_created_ids2:
                if move.state == 'done':
                    cost_init = move.product_id.standard_price
            for move in production.move_created_ids2.filtered(lambda x: x.state == 'done'):
                costo_producto_final = (production.production_cost)/production_qty
                cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    product_id = %s
                                    AND location_dest_id in %s
                                    AND (date < %s AND state = 'done')''',
                            (move.product_id.id,location_ids,move.date))
                result1 = cr.fetchall()
                for res in result1:
                    qty_in_cost = res[0] or 0.0
                cr.execute('''SELECT 
                                    SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    product_id = %s
                                    AND location_id in %s
                                    AND (date < %s AND state = 'done')''',
                            (move.product_id.id,location_ids,move.date))
                result1 = cr.fetchall()
                for res in result1:
                    qty_out_cost = res[0] or 0.0
                qty_move_cost = qty_in_cost - qty_out_cost
                costo_promedio=(qty_move_cost*cost_init + move.product_qty*costo_producto_final)/(qty_move_cost+move.product_qty)
                cost_init = costo_promedio

                cr.execute(''' UPDATE stock_move SET costo_promedio=%s, cost=%s, total_cost=%s*product_qty WHERE id=%s''',(costo_promedio, costo_producto_final, costo_producto_final, move.id))
            
            if not costo_promedio:
                raise osv.except_osv(_('Error !'),_("El sistema presenta inconsistencia en el costo del producto terminado, por favor valide que tengra producto terminado para costear o que el costo de la produccion sea diferente de cero."))

            product_obj.write(cr, SUPERUSER_ID, [production.product_id.id], {'standard_price': costo_promedio}, context=context) 
            stock_quant_pool.write(cr, SUPERUSER_ID, [x for x in stock_quant_pool.search(cr, SUPERUSER_ID, [('product_id', '=', production.product_id.id), ('qty', '>', 0)])], {'cost':costo_promedio}, context=context)
        return result
     
     
    def create_account_move(self, cr, uid, production, productos_consumidos, context=None):
        account_move_obj = self.pool.get('account.move')
        product_obj = self.pool.get('product.product')
        period_id = account_move_obj._get_period(cr, SUPERUSER_ID, context)
        today_date = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        journal_id = production.product_id.categ_id.property_stock_journal and production.product_id.categ_id.property_stock_journal.id or False
        if not journal_id:
            raise osv.except_osv(_('Error!'), _('No se encontro diario de inventario en la categoria de producto "%s"' % production.product_id.categ_id.name))
        final_debit_account = production.product_id.property_stock_account_input and production.product_id.property_stock_account_input.id or (production.product_id.categ_id.property_stock_account_input_categ and production.product_id.categ_id.property_stock_account_input_categ.id or False)
        if not final_debit_account:
            raise osv.except_osv(_('Error !'), _("La cuenta de entrada de almacen no esta definida en el producto '%s'."  % production.product_id.name))
        cr_move_line_list = []
        dr_move_line_list = []
        debit_sum = 0
        sum_total = 0
        for product_line in productos_consumidos.values():            
            product = product_line['product']
            qty = product_line['qty']
            costo = product_line['costo']
            context2 = context.copy()
            context2.update({'production': production})
            if production.product_id.categ_id.journal_production_id:
                sum_total+=costo
            else:
                credit_account = product.property_stock_account_output and product.property_stock_account_output.id or (product.categ_id.property_stock_account_output_categ and product.categ_id.property_stock_account_output_categ.id or False)
                if not credit_account:
                    raise osv.except_osv(_('Error !'), _("La cuenta de salida de almacen no esta definida en el producto '%s'."  % product.name))
                debit_account = product_obj.get_account_from_analytic(cr, uid, product, False, context=context2)
                if not debit_account:
                    raise osv.except_osv(_('Error !'), _("La cuenta de costos no esta definida en el producto '%s'."  % product.name))            
                if costo != 0:
                    cr_move_line = {
                        'name': product.name,
                        'date': today_date,
                        'period_id': period_id,
                        'debit': 0,
                        'credit': costo,
                        'account_id': credit_account, 
                    }
                    cr_move_line_list.append(cr_move_line)
                    debit_sum += costo
        for wc_line in production.workcenter_lines:
            if production.product_id.categ_id.journal_production_id:
                sum_total+=wc_line.cost
            else:
                credit_account = wc_line.workcenter_id.costs_general_account_id and wc_line.workcenter_id.costs_general_account_id.id or False
                if not credit_account and wc_line.workcenter_id.product_id:
                    credit_account = wc_line.workcenter_id.product_id.costo_account_property and wc_line.workcenter_id.product_id.costo_account_property.id or (wc_line.workcenter_id.product_id.categ_id.property_account_costos_categ and wc_line.workcenter_id.product_id.categ_id.property_account_costos_categ.id or False)
                if not credit_account:
                    product_name = wc_line.workcenter_id.product_id and wc_line.workcenter_id.product_id.name or False
                    raise osv.except_osv(_('Error !'), _("La cuenta de costos no esta definida en el centro de produccion '%s' ni en el producto '%s'.")  % (wc_line.workcenter_id.name,product_name))            
                amount = wc_line.cost
                if amount != 0:
                    cr_move_line = {
                        'name': wc_line.workcenter_id.name,
                        'date': today_date,
                        'period_id': period_id,
                        'debit': 0,
                        'credit': amount,
                        'account_id': credit_account, 
                    }
                    cr_move_line_list.append(cr_move_line)
                    debit_sum += amount
        
        if production.product_id.categ_id.journal_production_id:
            journal_id = production.product_id.categ_id.journal_production_id.id or False
            final_credit_account = production.product_id.categ_id.account_production_transit_id and production.product_id.categ_id.account_production_transit_id.id or False
            if not final_credit_account:
                raise osv.except_osv(_('Error !'), _("La cuenta de producto en proceso no se encuentra configurada para la categoria '%s'."  % production.product_id.categ_id.name))
            debit_sum = sum_total            
            dr_move_line_process = {
                'name': production.product_id.name,
                'date': today_date,
                'period_id': period_id,
                'debit': 0,
                'credit': sum_total,
                'account_id': final_credit_account,
                }
            dr_move_line_list.append(dr_move_line_process)
            
        dr_move_line = {
            'name': production.product_id.name,
            'date': today_date,
            'period_id': period_id,
            'debit': debit_sum,
            'credit': 0,
            'account_id': final_debit_account, 
        }
        dr_move_line_list.append(dr_move_line)    
        moves_lines = self.group_lines(cr, uid, dr_move_line_list)
        moves_lines += self.group_lines(cr, uid, cr_move_line_list)
        moves_vals = {
            'period_id': period_id,
            'journal_id': journal_id,
            'date': today_date,
            'ref': production.name,
            'line_id': moves_lines,
        }
        account_move = account_move_obj.create(cr, SUPERUSER_ID, moves_vals, context=context)
        self.write(cr, uid, production.id , {'account_move_id': account_move}, context=context)
    
    def inv_line_characteristic_hashcode(self, line):
        return '"%s","%s"'%(line['account_id'],line['name'])
    
    #magic method
    def group_lines(self, cr, uid, line):
        line2 = {}
        for l in line:
            tmp = self.inv_line_characteristic_hashcode(l)

            if tmp in line2:
                am = line2[tmp]['debit'] - line2[tmp]['credit'] + (l['debit'] - l['credit'])
                line2[tmp]['debit'] = (am > 0) and am or 0.0
                line2[tmp]['credit'] = (am < 0) and -am or 0.0
            else:
                line2[tmp] = l
        line = []
        for key, val in line2.items():
            line.append((0,0,val))
        return line
    
    def test_production_done(self, cr, uid, ids):
        for production in self.browse(cr, uid, ids):
            if production.move_lines:
                raise osv.except_osv(_('Error !'), _("Para finalizar la produccion no pueden existir productos sin consumir"))
            if production.move_created_ids:
                raise osv.except_osv(_('Error !'), _("Para finalizar la produccion no pueden existir productos sin fabricar"))
            for work in production.workcenter_lines:
                if work.state != 'done':
                    raise osv.except_osv(_('Error !'), _("Para finalizar la produccion no pueden existir servicios sin consumir"))
        return True
    

class stock_move_consume(osv.osv_memory):
    _inherit = "stock.move.consume"

    _columns = {
        'location_id': fields.many2one('stock.location', 'Location', readonly=True),
        'move_id': fields.many2one('stock.move', 'Move', readonly=True),
    }
    
    def do_move_consume(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        move_ids = context['active_ids']
        for data in self.browse(cr, uid, ids, context=context):
            if move_ids and move_ids[0]:
                move = move_obj.browse(cr, uid, move_ids[0], context=context)
            if data.product_qty < 0 or data.product_qty == 0 or data.product_qty > move.product_uom_qty:
                raise osv.except_osv(_('Error !'), _("La cantidad no puede ser menor o igual 0, ni mayor a la cantidad del movimiento."))
        res = super(stock_move_consume, self).do_move_consume(cr, uid, ids, context=context)
        return res
    
    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(stock_move_consume, self).default_get(cr, uid, fields, context=context)
        move = self.pool.get('stock.move').browse(cr, uid, context['active_id'], context=context)
        if 'move_id' in fields:
            res.update({'move_id': move.id})
            if len(move.lot_ids) >= 1:
                res.update({'restrict_lot_id': move.lot_ids[0].id})
        return res

class mrp_production_api(models.Model):
    _inherit = "mrp.production" 
    _order = "name desc"
    
    @api.one
    @api.depends('product_id','state','user_id')
    def _category_id(self):
        if self.product_id:
            if self.product_id.categ_id:
                self.category_id=self.product_id.categ_id.id
                if self.product_id.categ_id.parent_id:
                    self.division_id=self.product_id.categ_id.parent_id.id
                        
    division_id = fields2.Many2one('product.category', compute="_category_id", string='Division', store=True)
    category_id = fields2.Many2one('product.category', compute="_category_id", string='Categoria', store=True)


class stock_move_scrap(osv.osv_memory):
    _inherit = "stock.move.scrap"
        
    def move_scrap(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        move_ids = context['active_ids']
        if len(move_ids) >= 1:
            move = move_obj.browse(cr, uid, move_ids[0], context=context)
            if move.production_id.state in ['done','cancel']:
                raise osv.except_osv(_('Error !'), _("No es posible desechar un producto terminado, en una produccion finalizada o cancelada."))
        res = super(stock_move_scrap, self).move_scrap(cr, uid, ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

#
