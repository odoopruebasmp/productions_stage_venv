# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
# from openerp import api
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import openerp.netsvc
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil import relativedelta, parser
import openerp.tools
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval
from openerp import fields as fields2
from openerp import models, api, _
from openerp import api
from openerp.exceptions import Warning


class product_pricelist_item(models.Model):
    _inherit = "product.pricelist.item"
    
    @api.one
    @api.depends('currency_id','price_list','price_version_id','price_discount','product_id','product_tmpl_id','categ_id','min_quantity','base','price_surcharge','price_round','price_min_margin','price_max_margin')
    def _price_rule(self):
        #copia 19/05/2015 de _price_rule_get_multi product/pricelist.py')
        pricelist_obj = self.env['product.pricelist']
        currency_obj = self.env['res.currency']
        product_obj = self.env['product.template']
        product_uom_obj = self.env['product.uom']
        price_type_obj = self.env['product.price.type']
        rule = self
        currency_id = rule.price_list.currency_id
        ptype_src = rule.base_pricelist_id.currency_id
        price_type = price_type_obj.browse(int(rule.base))
        if not currency_id and rule.base > 0:
            currency_id = price_type.currency_id
        product = rule.product_id
        price = 0
        qty_uom_id = product.uom_id.id
        price_uom_id = qty_uom_id
        if product:
            if rule.base == -1:
                if rule.base_pricelist_id:
                    price_tmp = pricelist_obj._price_get_multi(rule.base_pricelist_id, [(product,
                            rule.min_quantity, False)])[product.id]
                    price = ptype_src.compute(price_tmp, currency_id, round=False)
            elif rule.base == -2:
                seller = False
                for seller_id in product.seller_ids:
                    if (not partner) or (seller_id.name.id != partner):
                        continue
                    seller = seller_id
                if not seller and product.seller_ids:
                    seller = product.seller_ids[0]
                if seller:
                    qty_in_seller_uom = qty
                    seller_uom = seller.product_uom.id
                    if qty_uom_id != seller_uom:
                        qty_in_seller_uom = product_uom_obj._compute_qty(qty_uom_id, qty, to_uom_id=seller_uom)
                    price_uom_id = seller_uom
                    for line in seller.pricelist_ids:
                        if line.min_quantity <= qty_in_seller_uom:
                            price = line.price
            else:
                # price_get returns the price in the context UoM, i.e. qty_uom_id
                price_uom_id = qty_uom_id
                price = price_type.currency_id.compute(product_obj._price_get([product], price_type.field)[product.id], currency_id, round=True)
                        
            if price is not False:
                price_limit = price
                price = price * (1.0+(rule.price_discount or 0.0))
                if rule.price_round:
                    price = openerp.tools.float_round(price, precision_rounding=rule.price_round)

                convert_to_price_uom = (lambda price: product_uom_obj._compute_price(
                                            product.uom_id.id,
                                            price, price_uom_id))
                if rule.price_surcharge:
                    price_surcharge = convert_to_price_uom(rule.price_surcharge)
                    price += price_surcharge

                if rule.price_min_margin:
                    price_min_margin = convert_to_price_uom(rule.price_min_margin)
                    price = max(price, price_limit + price_min_margin)

                if rule.price_max_margin:
                    price_max_margin = convert_to_price_uom(rule.price_max_margin)
                    price = min(price, price_limit + price_max_margin)
            
            # Final price conversion to target UoM
            price = product_uom_obj._compute_price(price_uom_id, price, qty_uom_id)
        self.precio_lista = price
    
    precio_lista = fields2.Float(string='Precio Calculado', compute='_price_rule')
    price_list = fields2.Many2one('product.pricelist', string="Lista", related='price_version_id.pricelist_id', readonly=True)
    currency_id = fields2.Many2one('res.company', string="Moneda", related='price_list.currency_id', readonly=True)

class stock_warehouse(osv.osv):
    _inherit = "stock.warehouse"

    _columns = {
        'partner_id': fields.many2one('res.partner', 'Owner Address', required=True),
    }

class res_company(osv.osv):
    _inherit = "res.company"

    _columns = {
        'warehouse_ids': fields.one2many('stock.warehouse', 'company_id', 'Almacenes'),
        'ciiu_ica': fields.boolean('CIIU en ICA'),
        'city_cc': fields.boolean('Ciudad en cuentas analiticas', help="Marcar si dentro de las cuentas analiticas existe el campo city_id")
    }
    
    def company_warehouse_cities(self, cr, uid, company, context=None):
        city_ids = []
        for warehouse in company.warehouse_ids:
            if not warehouse.partner_id:
                raise osv.except_osv(_('Error !'), _("No esta configurada la direccion del almacen '%s' " %(warehouse.name,)))
            if not warehouse.partner_id.city_id:
                raise osv.except_osv(_('Error !'), _("No esta configurada la ciudad de'%s' " %(warehouse.partner_id.name,)))
            if warehouse.partner_id.city_id not in city_ids:
                city_ids.append(warehouse.partner_id.city_id)
        
        return city_ids

class account_tax(osv.osv):
    _inherit = "account.tax"

    _columns = {
        'ciudad': fields.many2one('res.city', "Ciudad"),
        'ciiu_ids': fields.many2many('res.ciiu', 'tax_ciiu_rel', 'tax_id', 'ciiu_id', string='CIIU asociados'),
        'parent_city_id': fields.many2one('account.tax', 'Impuesto Ciudades Padre'),
        'child_cities_ids': fields.one2many('account.tax', 'parent_city_id', 'Impuestos Ciudades Hijas'),
        'check_lines': fields.boolean('Impuesto ICA')
    }

class product_product(osv.osv):
    _inherit = "product.product"
    _columns = {
        'default_code' : fields.char('Internal Reference', size=64, select=True),
    }
    
    _sql_constraints = [
        ('ref_uniq', 'unique(default_code)', 'El codigo interno no puede ser repetido'),
    ]
    
class product_category(osv.osv):
    _inherit = "product.category"
    _columns = {
        'taxes_id': fields.many2many('account.tax', 'product_category_taxes_rel',
            'product_category_id', 'tax_id', 'Impuestos Cliente',
            domain=[('parent_id','=',False),('type_tax_use','in',['sale','all'])]),
        'supplier_taxes_id': fields.many2many('account.tax',
            'product_category_supplier_taxes_rel', 'product_category_id', 'tax_id',
            'Impuestos Proveedor', domain=[('parent_id', '=', False),('type_tax_use','in',['purchase','all'])]),
    }

#Se cambia taxes_id por una funcion que devuelve taxes_id de la categoria si este no existe en el producto
class product_template(osv.osv):
    _inherit = "product.template"
    
    def _get_taxes(self, cr, uid, ids, field_name, arg, context=None):
        result = {}
        for record in self.browse(cr, uid, ids, context=context):
            if record.taxes_id_1:
                result[record.id] = [x.id for x in record.taxes_id_1]
            elif record.categ_id.taxes_id:
                result[record.id] = [x.id for x in record.categ_id.taxes_id]
            else:
                result[record.id] = []

        return result
        
    def _get_supplier_taxes(self, cr, uid, ids, field_name, arg, context=None):
        result = {}
        for record in self.browse(cr, uid, ids, context=context):
            if record.supplier_taxes_id_1:
                result[record.id] = [x.id for x in record.supplier_taxes_id_1]
            elif record.categ_id.supplier_taxes_id:
                result[record.id] = [x.id for x in record.categ_id.supplier_taxes_id]
            else:
                result[record.id] = []

        return result
    
    _columns = {
        'taxes_id': fields.function(_get_taxes, type='many2many', relation="account.tax", string="Impuestos Cliente"),
        'supplier_taxes_id': fields.function(_get_supplier_taxes, type='many2many', relation="account.tax", string="Impuestos"),
        'taxes_id_1': fields.many2many('account.tax', 'product_taxes_rel',
            'prod_id', 'tax_id', 'Impuestos Cliente',
            domain=[('parent_id','=',False),('type_tax_use','in',['sale','all'])]),
        'supplier_taxes_id_1': fields.many2many('account.tax',
            'product_supplier_taxes_rel', 'prod_id', 'tax_id',
            'Impuestos Proveedor', domain=[('parent_id', '=', False),('type_tax_use','in',['purchase','all'])]),
    }

#Valor a superar para que se aplique la regla
class account_fiscal_position_tax(osv.osv):
    _inherit = 'account.fiscal.position.tax'
    
    _columns = {
        'valor': fields.float('Valor'),
        'option': fields.selection((('always','Siempre'), ('great','>'), ('great_equal','>='), ('equal','='), ('minor','<'), ('minor_equal','<=')),'Opcion', required=True),
    }

class account_fiscal_position(osv.osv):
    _inherit = 'account.fiscal.position'
    
    #odoo default mapping is desactivated
    @api.v7
    def map_tax(self, cr, uid, fpos, taxes, context=None):
        if taxes:
            return map(lambda x: x.id, taxes)
        else:
            return []
    @api.v8
    def map_tax(self, taxes):
        return taxes

    def map_base(self, cr, uid, fposition, taxes_to_map, context=None):
        cr.execute("SELECT company_id from res_users where id = %s" % uid)
        company_id = self.pool.get('res.company').browse(cr, uid, cr.fetchone()[0], context=context)

        if not fposition:
            raise osv.except_osv(_('Error !'), _("No esta configurada la posicion Fiscal del tercero"))

        result = []

        if company_id.ciiu_ica:
            if taxes_to_map:
                for t in taxes_to_map.keys():
                    if not t.check_lines and t.child_cities_ids:
                        raise Warning("En uno de los impuestos configurados tiene calculo especial pero no tiene "
                                      "activada la opcion de validacion por lineas")
                    subtotal = taxes_to_map[t]
                    # value mapping
                    delete = False
                    if not context.get('return', False):
                        for mapp in fposition.tax_ids:
                            if mapp.tax_src_id and mapp.tax_src_id.id == t.id and mapp.option:
                                if mapp.option == 'always' or (mapp.option == 'great' and subtotal > mapp.valor) or (
                                        mapp.option == 'great_equal' and subtotal >= mapp.valor) or (
                                        mapp.option == 'equal' and subtotal == mapp.valor) or (
                                        mapp.option == 'minor' and subtotal < mapp.valor) or (
                                        mapp.option == 'minor_equal' and subtotal <= mapp.valor):
                                    if not mapp.tax_dest_id:
                                        delete = True
                                        break
                                    t = mapp.tax_dest_id
                    if not delete:
                        result.append(t.id)
        return result

    def map_city(self, cr, uid, taxes_to_map, ciudad, ciiu, context=None):
        result = []
        cr.execute("SELECT company_id from res_users where id = %s" % uid)
        company_id = self.pool.get('res.company').browse(cr, uid, cr.fetchone()[0], context=context)
        if company_id.ciiu_ica:
            if taxes_to_map:
                for t in taxes_to_map.keys():
                    # city mapping
                    delete = False
                    if not delete and t.child_cities_ids:
                        delete = True
                        for child in t.child_cities_ids:
                            if child.ciudad == ciudad and ciiu in child.ciiu_ids:
                                t = child
                                delete = False
                                break

                    if not delete:
                        result.append(t.id)

        return result

    def map_tax2(self, cr, uid, fposition, taxes_to_map, partner, ciudad, ciiu, context=None):
        cr.execute("SELECT company_id from res_users where id = %s" % uid)
        company_id = self.pool.get('res.company').browse(cr, uid, cr.fetchone()[0], context=context)

        if not fposition:
            raise osv.except_osv(_('Error !'), _("Configure la posicion Fiscal del tercero %s") %
                                 (context['partner_id'].name if context.get('partner_id', False) else partner.name))
        
        result = []

        if company_id.ciiu_ica:
            # if not partner.ciiu_id:
            #     raise Warning("El tercero no tiene asociado un CIIU")
            if taxes_to_map:
                for t in taxes_to_map.keys():
                    if not t.check_lines and t.child_cities_ids:
                        raise Warning("En uno de los impuestos configurados tiene calculo especial pero no tiene "
                                      "activada la opcion de validacion por lineas")

                    found = False
                    subtotal = taxes_to_map[t]
                    #city verify mapping
                    if t.parent_city_id:
                        if t.ciudad != ciudad:
                            if ciudad:
                                for child in t.parent_city_id.child_cities_ids:
                                    if child.ciudad == ciudad and ciiu in child.ciiu_ids:
                                        t=child
                                        found = True
                                        break
                            if not found:
                                t=t.parent_city_id
                    #value mapping
                    delete = False
                    if not context.get('return', False):
                        for mapp in fposition.tax_ids:
                            if mapp.tax_src_id and mapp.tax_src_id.id == t.id and mapp.option:
                                if mapp.option == 'always' or (mapp.option == 'great' and subtotal > mapp.valor) or (mapp.option == 'great_equal' and subtotal >= mapp.valor) or (mapp.option == 'equal' and subtotal == mapp.valor) or (mapp.option == 'minor' and subtotal < mapp.valor) or (mapp.option == 'minor_equal' and subtotal <= mapp.valor):
                                    if not mapp.tax_dest_id:
                                        delete = True
                                        break
                                    t=mapp.tax_dest_id
                    #city mapping
                    if not delete and t.child_cities_ids:
                        delete = True
                        for child in t.child_cities_ids:
                            if child.ciudad == ciudad and ciiu in child.ciiu_ids:
                                t = child
                                delete = False
                                break

                    if not delete:
                        result.append(t.id)


        else:
            if taxes_to_map:
                for t in taxes_to_map.keys():
                    found = False
                    subtotal = taxes_to_map[t]
                    #city verify mapping
                    if t.parent_city_id:
                        if t.ciudad != ciudad:
                            if ciudad:
                                for child in t.parent_city_id.child_cities_ids:
                                    if child.ciudad == ciudad:
                                        t=child
                                        found = True
                                        break
                            if not found:
                                t=t.parent_city_id
                    #value mapping
                    delete = False

                    if not context.get('return', False):
                        for mapp in fposition.tax_ids:
                            if mapp.tax_src_id and mapp.tax_src_id.id == t.id and mapp.option:
                                if mapp.option == 'always' or (mapp.option == 'great' and subtotal > mapp.valor) or ( mapp.option == 'great_equal' and subtotal >= mapp.valor) or (mapp.option == 'equal' and subtotal == mapp.valor) or (mapp.option == 'minor' and subtotal < mapp.valor) or (mapp.option == 'minor_equal' and subtotal <= mapp.valor):
                                    if not mapp.tax_dest_id:
                                        delete = True
                                        break
                                    t=mapp.tax_dest_id
                    #city mapping
                    if not delete and t.child_cities_ids:
                        delete=True
                        for child in t.child_cities_ids:
                            if child.ciudad == ciudad:
                                t=child
                                ok=True
                                delete=False
                                break

                    if not delete:
                        result.append(t.id)
        return result


class account_invoice(osv.osv):
    _inherit = 'account.invoice'
    
    def subtotal_per_tax(self, cr, uid, lines, tax, context=None):
        new_lines = []
        subtotal = 0
        for line in lines:
            if tax in line.invoice_line_tax_id:
                new_lines.append(line)
        for line in new_lines:
            subtotal += line.price_subtotal
        return subtotal

    def subtotal_per_tax2(self, cr, uid, lines, tax, city, ciiu, context=None):
        subtotal = 0
        new_lines = []
        key = "{tax}-{city}-{ciiu}".format(tax=tax, city=city, ciiu=ciiu)
        for line in lines:
            if tax in line.invoice_line_tax_id:
                if city == line.city_id and ciiu == line.ciiu_id:
                    new_lines.append(line)
        for line in new_lines:
            subtotal += line.price_subtotal
        return subtotal
    
    @api.multi
    def button_reset_taxes(self):
        cr = self._cr
        uid = self._uid
        context = self._context
        ctx = context.copy()
        fposition_pool = self.pool.get('account.fiscal.position')
        invoice_line_pool = self.pool.get('account.invoice.line')
        company_pool = self.pool.get('res.company')
        cr.execute("SELECT company_id from res_users where id = %s" % uid)
        company_id = self.pool.get('res.company').browse(cr, uid, cr.fetchone()[0], context=context)

        for inv in self:
            
            #if inv.type in ['out_refund','in_refund']:
                #continue
            tax_subtotals = {}
            tax_keys_subtotals = {}
            company_partner = False
            if company_id.ciiu_ica:
                company_partner = inv.partner_id

            cities = company_pool.company_warehouse_cities(cr, uid, inv.company_id, context=context)
            if inv.type in ['out_invoice','out_refund']:
                company_partner = inv.company_id.partner_id
            self.invalidate_cache()
            for line in inv.invoice_line:
                # [IMP] Politica de ICA por CIIU y ciudad por linea
                if company_id.ciiu_ica:
                    taxes_to_map = {}
                    city = False

                    result_taxes = []

                    for tax in line.invoice_line_tax_id:

                        fposition = inv.fiscal_position or inv.partner_id.property_account_position or False
                        ctx = context.copy()
                        if inv.type in ['out_refund', 'in_refund']:
                            ctx.update({'return': True})

                        if tax.check_lines and company_id.city_cc:
                            city = line.account_analytic_id.city_id
                        elif tax.check_lines:
                            city = line.city_id

                        if line.invoice_id.partner_shipping_id:
                            if not line.city_id:
                                if inv.type in ['out_invoice', 'out_refund']:
                                    if line.invoice_id.partner_shipping_id.city_id:
                                        line.city_id = line.invoice_id.partner_shipping_id.city_id

                        if not line.ciiu_id:
                            if inv.type in ['out_invoice', 'out_refund']:
                                line.ciiu_id = inv.company_id.partner_id.ciiu_id
                            else:
                                line.ciiu_id = inv.partner_id.ciiu_id
                        if not line.city_id:
                            if inv.type in ['out_invoice', 'out_refund']:
                                line.city_id = inv.company_id.partner_id.city_id
                            else:
                                # Tiene en cuenta la direccion de entrega del proveedor
                                line.city_id = inv.partner_shipping_id.city_id
                        ciiu = line.ciiu_id

                        if tax.child_cities_ids:
                            tax_key = "{tax}-{city}-{ciiu}".format(tax=tax.id, city=city, ciiu=ciiu)
                            if tax_key not in tax_keys_subtotals:
                                tax_keys_subtotals[tax_key] = self.subtotal_per_tax2(inv.invoice_line, tax, city, line.ciiu_id) * inv.tasa_manual
                            ind_taxtomap = {tax: self.subtotal_per_tax2(inv.invoice_line, tax, city, line.ciiu_id)}
                            restax = fposition_pool.map_tax2(
                                cr, uid, fposition, ind_taxtomap, company_partner, city, ciiu, context)
                            if restax:
                                result_taxes.append(restax[0])
                            taxes_to_map[tax] = self.subtotal_per_tax2(inv.invoice_line, tax, city, line.ciiu_id)
                        else:
                            if tax.id not in tax_subtotals:
                                tax_subtotals[tax.id] = self.subtotal_per_tax(inv.invoice_line, tax) * inv.tasa_manual
                            ind_taxtomap = {tax: tax_subtotals[tax.id]}

                            restax = fposition_pool.map_tax2(
                                cr, uid, fposition, ind_taxtomap, company_partner, city, ciiu, context)
                            if restax:
                                result_taxes.append(restax[0])
                            taxes_to_map[tax] = tax_subtotals[tax.id]

                else:
                    # Politica generica
                    taxes_to_map = {}
                    city = False

                    for tax in line.invoice_line_tax_id:
                        if tax.id not in tax_subtotals:
                            tax_subtotals[tax.id] = self.subtotal_per_tax(inv.invoice_line, tax)*inv.tasa_manual
                        taxes_to_map[tax] = tax_subtotals[tax.id]

                    result_taxes = [x.id for x in line.invoice_line_tax_id]

                    fposition = inv.fiscal_position or inv.partner_id.property_account_position or False
                    ctx=context.copy()
                    if inv.type in ['out_refund']:
                        ctx.update({'return': True})

                    # [ADD] condicional para revisar centro de costo

                    if len(result_taxes) > 0:
                        reteica_ck_lines = '''
                                    SELECT id, check_lines from account_tax where check_lines = 'true' and id in (%s)
                                ''' % ','.join(str(x) for x in result_taxes)
                        cr.execute(reteica_ck_lines)
                        reteica_ck_lines = cr.dictfetchall()

                        if reteica_ck_lines and reteica_ck_lines[0]['check_lines'] is True:
                            if company_id.city_cc:
                                city = line.account_analytic_id.city_id
                            else:
                                city = line.city_id
                        else:
                            if inv.partner_shipping_id and inv.partner_shipping_id.city_id:
                                city = inv.partner_shipping_id.city_id
                            elif company_partner and company_partner.city_id:
                                city = company_partner.city_id

                            # if line.product_id.type in ['consu', 'product']:
                            #     city = inv.partner_id.city_id

                                if city not in cities:
                                    # city = False
                                    pass

                    # Enviando CIIU por contexto
                    if not line.ciiu_id:
                        line.ciiu_id = inv.partner_id.ciiu_id
                    ctx['ciiu'] = line.ciiu_id
                    ctx['partner_id'] = inv.partner_id

                    result_taxes = fposition_pool.map_tax2(cr, uid, fposition, taxes_to_map, company_partner, city, line.ciiu_id, context=ctx)
                # JOIN methods
                invoice_line_pool.write(cr, uid, [line.id], {'invoice_line_tax_id': [(6, 0, result_taxes)]}, context=context)
                
        return super(account_invoice, self).button_reset_taxes()


class stock_invoice_onshipping(osv.osv_memory):
    _inherit = "stock.invoice.onshipping"

    _columns = {
        'journal_id': fields.many2one('account.journal', 'Destination Journal', required=True),
    }

class purchase_order(osv.osv):
    _inherit = "purchase.order"
    
    def subtotal_per_tax(self, cr, uid, lines, tax, context=None):
        new_lines = []
        subtotal = 0
        for line in lines:
            if tax in line.taxes_id:
                new_lines.append(line)
        for line in new_lines:
            subtotal += line.price_subtotal
        return subtotal

    def subtotal_per_tax2(self, cr, uid, lines, tax, city, ciiu, context=None):
        subtotal = 0
        new_lines = []
        key = "{tax}-{city}-{ciiu}".format(tax=tax, city=city, ciiu=ciiu)
        for line in lines:
            if tax in line.taxes_id:
                if city == line.city_id and ciiu == line.ciiu_id:
                    new_lines.append(line)
        for line in new_lines:
            subtotal += line.price_subtotal
        return subtotal
    
    def button_dummy(self, cr, uid, ids, context=None):
        fposition_pool = self.pool.get('account.fiscal.position')
        purchase_line_pool = self.pool.get('purchase.order.line')
        company_pool = self.pool.get('res.company')
        for purchase in self.browse(cr, uid, ids, context=context):
            tax_subtotals = {}
            company_partner = purchase.company_id.partner_id
            cities = company_pool.company_warehouse_cities(cr, uid, purchase.company_id, context=context)
            for line in purchase.order_line:
                taxes_to_map = {}

                if purchase.company_id.ciiu_ica:
                    city = company_partner.city_id
                    # Politica de ciudad en centro de costo
                    if purchase.company_id.city_cc:
                        city = line.account_analytic_id.city_id
                    else:
                        if purchase.dest_address_id and purchase.dest_address_id.city_id:
                            city = purchase.dest_address_id.city_id
                        if purchase.picking_type_id.warehouse_id and line.product_id.type in ['consu', 'product']:
                            if purchase.partner_id.city_id in cities:
                                city = purchase.partner_id.city_id
                            else:
                                city = False

                    result_taxes = []
                    for tax in line.taxes_id:

                        fposition = purchase.fiscal_position or purchase.partner_id.property_account_position or False
                        ctx = context.copy()

                        city = company_partner.city_id
                        # Politica de ciudad en centro de costo
                        if purchase.company_id.city_cc:
                            city = line.account_analytic_id.city_id
                        else:
                            if purchase.dest_address_id and purchase.dest_address_id.city_id:
                                city = purchase.dest_address_id.city_id
                            if purchase.picking_type_id.warehouse_id and line.product_id.type in ['consu', 'product']:
                                if purchase.partner_id.city_id in cities:
                                    city = purchase.partner_id.city_id
                                else:
                                    city = False

                        if not line.ciiu_id:
                            line.ciiu_id = purchase.partner_id.ciiu_id
                        ctx['ciiu'] = line.ciiu_id

                        if tax.id not in tax_subtotals:
                            tax_subtotals[tax.id] = self.subtotal_per_tax(cr, uid, purchase.order_line, tax)*purchase.rate_pactada
                        ind_taxtomap = {tax: tax_subtotals[tax.id]}
                        restax = fposition_pool.map_tax2(
                            cr, uid, fposition, ind_taxtomap, company_partner, city, line.ciiu_id, context=ctx)
                        if restax:
                            result_taxes.append(restax[0])
                        taxes_to_map[tax] = tax_subtotals[tax.id]

                else:
                    city = company_partner.city_id
                    # Politica de ciudad en centro de costo
                    if purchase.company_id.city_cc:
                        city = line.account_analytic_id.city_id
                    else:
                        if purchase.dest_address_id and purchase.dest_address_id.city_id:
                            city = purchase.dest_address_id.city_id
                        if purchase.picking_type_id.warehouse_id and line.product_id.type in ['consu','product']:
                            if purchase.partner_id.city_id in cities:
                                city = purchase.partner_id.city_id
                            else:
                                city = False

                    for tax in line.taxes_id:
                        if tax.id not in tax_subtotals:
                            tax_subtotals[tax.id] = self.subtotal_per_tax(cr, uid, purchase.order_line, tax)*purchase.rate_pactada
                        taxes_to_map[tax] = tax_subtotals[tax.id]

                    result_taxes = fposition_pool.map_tax2(cr, uid, purchase.partner_id.property_account_position, taxes_to_map, purchase.partner_id, city, line.ciiu_id, context=context)
                purchase_line_pool.write(cr, uid, [line.id], {'taxes_id': [(6, 0, result_taxes)]}, context=context)
        return super(purchase_order, self).button_dummy(cr, uid, ids, context=context)


class purchase_order_line(models.Model):
    _inherit = "purchase.order.line"

    ciiu_id = fields2.Many2one('res.ciiu', string='CIIU')
    city_id = fields2.Many2one('res.city', 'Ciudad')


class sale_order(osv.osv):
    _inherit = "sale.order"
    
    def subtotal_per_tax(self, cr, uid, lines, tax, context=None):
        new_lines = []
        subtotal = 0
        for line in lines:
            if tax in line.tax_id:
                new_lines.append(line)
        for line in new_lines:
            subtotal += line.price_subtotal
        return subtotal
    
    def button_dummy(self, cr, uid, ids, context=None):
        fposition_pool = self.pool.get('account.fiscal.position')
        sale_line_pool = self.pool.get('sale.order.line')
        company_pool = self.pool.get('res.company')
        for sale in self.browse(cr, uid, ids, context=context):
            tax_subtotals = {}
            company_partner = sale.company_id.partner_id
            cities = company_pool.company_warehouse_cities(cr, uid, sale.company_id, context=context)
            for line in sale.order_line:
                taxes_to_map = {}
                city = sale.partner_shipping_id and sale.partner_shipping_id.city_id or False
                if line.product_id.type in ['consu','product']:
                    if sale.partner_invoice_id.city_id in cities:
                        city = sale.partner_invoice_id.city_id
                    else:
                        city = False
                for tax in line.tax_id:
                    if tax.id not in tax_subtotals:
                        tax_subtotals[tax.id] = self.subtotal_per_tax(cr, uid, sale.order_line, tax)*sale.tasa_cambio_pactada
                    taxes_to_map[tax] = tax_subtotals[tax.id]
                
                result_taxes = fposition_pool.map_tax2(cr, uid, sale.partner_id.property_account_position, taxes_to_map, company_partner, city, False, context=context)
                sale_line_pool.write(cr, uid, [line.id], {'tax_id': [(6, 0, result_taxes)]}, context=context)

        return super(sale_order, self).button_dummy(cr, uid, ids, context)
#
