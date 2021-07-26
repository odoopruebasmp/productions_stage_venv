# -*- coding: utf-8 -*-
from openerp import api
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
import openerp.netsvc
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil.relativedelta import relativedelta
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval
from openerp import models, api, _, fields as fields2
from openerp.osv import osv, fields 
import calendar
from openerp import SUPERUSER_ID
from openerp.addons.avancys_orm import avancys_orm

class res_currency_rate(models.Model):
    _inherit = "res.currency.rate"
    
    @api.one
    @api.depends('name', 'currency_id.company_id')       
    def _date_notime(self):
        if self.name:
            date = datetime.strptime(self.name, DEFAULT_SERVER_DATETIME_FORMAT)
            date = fields.datetime.context_timestamp(self._cr, self._uid, date, context=self._context)
            date = date.strftime(DEFAULT_SERVER_DATE_FORMAT)
            self.date_sin_hora = date
    
    rate=fields2.Float(string='Rate', digits=dp.get_precision('Exchange Precision'), help='The rate of the currency to the currency of rate 1', default=1)
    rate_inv=fields2.Float(string='Tasa Inversa', digits=dp.get_precision('Exchange Precision'), help='la tasa de cambios inversa, cantidad de moneda base para que de 1 de esta (OPCIONAL)', default=1)
    date_sin_hora=fields2.Date(string="Fecha", compute="_date_notime", store=True)
    name = fields2.Datetime(string='Date', required=True, select=True, default=datetime.now())
    
    
    def onchange_rate(self, cr , uid, ids, rate, context = None):
        if rate == 0:
            raise osv.except_osv(_('Error!'), _('No puede ser 0!'))
        return {'value': {'rate_inv' : 1.0/rate }}
    
    def onchange_rate_inv(self, cr , uid, ids, rate_inv, context = None):
        if rate_inv == 0:
            raise osv.except_osv(_('Error!'), _('No puede ser 0!'))
        return {'value': {'rate' : 1.0/rate_inv }}

class currency_res(osv.osv):
    _inherit = "res.currency"
    
    def _get_conversion_rate(self, cr, uid, from_currency, to_currency, context=None):
        if not context: context = {}
        if not context.get('pricelist_rate'):
            return super(currency_res, self)._get_conversion_rate(cr, uid, from_currency, to_currency, context=context)
        else:
            return context.get('pricelist_rate')
    
    def tasa_dia(self, cr, uid, date, company, currency, context=None):
        rate=1
        if company.currency_id.id != currency.id:
            currency_obj = self.pool.get('res.currency.rate')
            currency_date_id = currency_obj.search(cr, uid, [('date_sin_hora','=',date),('currency_id','=',currency.id)])
            if currency_date_id:
                rate = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv
            else:
                rate = 0
        
        return rate
        
    def compute_tasa(self, cr, uid, from_currency_id, to_currency_id, from_amount, round=True, currency_rate_type_from=False, currency_rate_type_to=False, rate=False, context=None):
        if not context:
            context = {}
        if not from_currency_id:
            from_currency_id = to_currency_id
        if not to_currency_id:
            to_currency_id = from_currency_id
        xc = self.browse(cr, uid, [from_currency_id,to_currency_id], context=context)
        from_currency = (xc[0].id == from_currency_id and xc[0]) or xc[1]
        to_currency = (xc[0].id == to_currency_id and xc[0]) or xc[1]
        if (to_currency_id == from_currency_id) and (currency_rate_type_from == currency_rate_type_to):
            if round:
                return self.round(cr, uid, to_currency, from_amount)
            else:
                return from_amount
        else:
            context.update({'currency_rate_type_from': currency_rate_type_from, 'currency_rate_type_to': currency_rate_type_to})
            if not rate:
                rate = self.tasa_dia(cr, uid, context['date'], company, currency, context=context)
            if round:
                return self.round(cr, uid, to_currency, from_amount * rate)
            else:
                return from_amount * rate
    
    def _current_rate(self, cr, uid, ids, name, arg, context=None):
        return super(currency_res,self)._current_rate(cr, uid, ids, name, arg, context=context)
    
    def _current_rate_silent(self, cr, uid, ids, name, arg, context=None):
        return super(currency_res,self)._current_rate_silent(cr, uid, ids, name, arg, context=context)

    def _get_current_rate(self, cr, uid, ids, raise_on_no_rate=True, context=None):
        return super(currency_res,self)._get_current_rate(cr, uid, ids, raise_on_no_rate=raise_on_no_rate, context=context)
    
    _columns = {
        'rate': fields.function(_current_rate, string='Current Rate', digits=dp.get_precision('Exchange Precision'),
            help='The rate of the currency to the currency of rate 1.'),
        'rate_silent': fields.function(_current_rate_silent, string='Current Rate', digits=dp.get_precision('Exchange Precision'),
            help='The rate of the currency to the currency of rate 1 (0 if no rate defined).'),
        'rounding_invoice': fields.integer(string='Factor Impresion Factura'),
        'name_print': fields.char(string='Nombre Impresion'),
    }
   
class sale_order(osv.osv):
    _inherit = 'sale.order'
    
    def _amount_total_local(self, cr, uid, ids, name, args, context=None):
        result = {}
        for order in self.browse(cr, uid, ids, context=context):
            if order.company_id.currency_id.id != order.currency_id.id:
                result[order.id] = order.amount_total*order.tasa_cambio_pactada
            else:
                result[order.id] = order.amount_total
        return result
    
    def _check_rate(self, cr, uid, ids, context=None):
        for object in self.browse(cr, uid, ids, context):
            if object.tasa_cambio_pactada == 0 or object.tasa_cambio_pactada < 0:
                return False
        return True
    
    _columns = {
        'tasa_cambio_pactada': fields.float('Tasa Pactada', digits_compute=dp.get_precision('Exchange Precision'), help='La tasa de cambio usada para el cambio de moneda, dejela en 0 si no hay ninguna pactada', readonly=True, states={'draft': [('readonly', False)]}),
        'multicurrency': fields.boolean('multicurrency', readonly=True, states={'draft': [('readonly', False)]}),
        'pricelist_version_id': fields.many2one('product.pricelist.version', "Version de Tarifa", readonly=True),
        'total_moneda_local': fields.function(_amount_total_local, digits_compute=dp.get_precision('Account'), string='Total en Moneda Local'),
        'moneda_local': fields.related('company_id','currency_id',type="many2one",relation="res.currency",string="Moneda Local"),
    }
    
    _defaults = {
        'tasa_cambio_pactada': 1,
    }
    
    _constraints = [
        (_check_rate, 'La tasa de cambio no puede ser 0 o negativa', ['tasa_cambio_pactada']),
    ]
    
    def _prepare_invoice(self, cr, uid, order, lines, context=None):
        invoice_vals = super(sale_order,self)._prepare_invoice(cr, uid, order, lines, context=context)
        invoice_vals.update({
            'tasa_manual': order.tasa_cambio_pactada,
            'es_multidivisa': order.multicurrency,
        })
        
        return invoice_vals
    
    def onchange_partner_id2(self, cr, uid, ids, part, date, context=None):
        val = super(sale_order,self).onchange_partner_id(cr, uid, ids, part, context=context)['value']
        if not part:
            return {'value': {'partner_invoice_id': False, 'partner_shipping_id': False,  'payment_term': False, 'fiscal_position': False,'tasa_cambio_pactada':False}}
        if date:
            date = datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT) - relativedelta(hours=5)
        else:
            date= fields2.datetime.now().date() - relativedelta(hours=5)
        date=date.strftime(DEFAULT_SERVER_DATE_FORMAT)
        part = self.pool.get('res.partner').browse(cr, uid, part, context=context)
        #if the chosen partner is not a company and has a parent company, use the parent to choose the delivery, the 
        #invoicing addresses and all the fields related to the partner.
        if part.parent_id and not part.is_company:
            part = part.parent_id
        pricelist = part.property_product_pricelist and part.property_product_pricelist.id or False
        warning = {}
        if pricelist:
            company = part.property_product_pricelist.company_id
            pricelist_version_ids = self.pool.get('product.pricelist.version').search(cr, uid, [
                                                        ('pricelist_id', '=', pricelist),
                                                        '|',
                                                        ('date_start', '=', False),
                                                        ('date_start', '<=', date),
                                                        '|',
                                                        ('date_end', '=', False),
                                                        ('date_end', '>=', date),
                                                    ])
            if len(pricelist_version_ids) < 1:
                warning = {
                       'title': _('Advertencia!'),
                       'message' : _("No hay una version de tarifa valida para esa tarifa en esta fecha! : "),
                    }
            elif company.currency_id != part.property_product_pricelist.currency_id:
                list = self.pool.get('product.pricelist.version').browse(cr, uid, pricelist_version_ids[0], context=context)
                val['pricelist_version_id'] = list.id
                val['multicurrency'] = True
                if list.tasa_cambio_pactada != 0:
                    val['tasa_cambio_pactada'] = list.tasa_cambio_pactada
                else:
                    print "1111111111"
                    print date
                    print type(date)
                    print ""
                    print date[0:10]
                    print ""
                    val['tasa_cambio_pactada'] = self.pool.get('res.currency').tasa_dia(cr, uid, date[0:10], company, part.property_product_pricelist.currency_id, context=context)
            else:
                val['multicurrency'] = False
        return {'value': val,'warning': warning}
        
    def onchange_pricelist(self, cr, uid, ids, order_line, date, pricelist_id, context=None):
        if not pricelist_id:
            return {}
        val = self.onchange_pricelist_id(cr, uid, ids, pricelist_id, order_line, context=context)['value']
        
        if date:
            date = datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT) - relativedelta(hours=5)
        else:
            date= fields2.datetime.now().date() - relativedelta(hours=5)
        
        date=date.strftime(DEFAULT_SERVER_DATE_FORMAT)
        warning = {}
        val['tasa_cambio_pactada'] = 1
        if pricelist_id:
            pricelist_version_ids = self.pool.get('product.pricelist.version').search(cr, uid, [('pricelist_id', '=', pricelist_id),('active', '=', True), '|', ('date_start', '=', False),('date_start', '<=', date), '|', ('date_end', '=', False), ('date_end', '>=', date)])
            if not pricelist_version_ids:
                raise osv.except_osv(_('Error!'), _('No existe una version de tarifa configurada para la fecha.'))
            
            pricelist = self.pool.get('product.pricelist').browse(cr, uid, pricelist_id, context=context)
            if pricelist.company_id.currency_id.id != pricelist.currency_id.id:
                val['multicurrency'] = True
                val['tasa_cambio_pactada'] = 0
                if len(pricelist_version_ids) > 0:
                    list = self.pool.get('product.pricelist.version').browse(cr, uid, pricelist_version_ids[0], context=context)
                    if list.tasa_cambio_pactada != 0:
                        val['tasa_cambio_pactada'] = list.tasa_cambio_pactada
                if val['tasa_cambio_pactada'] == 0:
                    val['tasa_cambio_pactada'] = self.pool.get('res.currency').tasa_dia(cr, uid, date[0:10], pricelist.company_id, pricelist.currency_id, context=context)
                if val['tasa_cambio_pactada'] == 0:
                    warning = {
                       'title': _('Advertencia!'),
                       'message' : _("La tasa de cambio para la fecha '%s' no esta especificada!" % date),
                    }
            else:
                val['multicurrency'] = False
        return {'value': val,'warning': warning}

class product_pricelist_version(osv.osv):
    _inherit = 'product.pricelist.version'
    _columns = {
        'tasa_cambio_pactada': fields.float('Tasa Pactada', digits_compute=dp.get_precision('Exchange Precision'), help='La tasa de cambio usada para el cambio de moneda, dejela en 0 si no hay ninguna pactada'),
    }

#Para anadir la tasa de cambio manual
class account_change_currency(osv.osv_memory):
    _inherit = 'account.change.currency'
    _columns = {
       'currency_id': fields.many2one('res.currency', 'Change to', required=True, help="Select a currency to apply on the invoice"),
       'tasa_cambio_conversion': fields.float('Tasa Usada en Conversion', digits_compute=dp.get_precision('Exchange Precision'), required=True, help='La tasa de cambio usada para el cambio de moneda'),
    }
    
    def onchange_currency_id(self, cr, uid, ids, currency_id,  context=None):
        val = {}
        warning = {}
        invoice = self.pool.get('account.invoice').browse(cr, uid, context['active_id'], context=context)
        date = invoice.date_invoice or time.strftime(DEFAULT_SERVER_DATE_FORMAT)
        currency_obj = self.pool.get('res.currency.rate')
        # if not currency_id:
        #     return
        #
        # cr.execute("select id from res_currency_rate where currency_id = {c} and "
        #                               "name::varchar like '{d}%'".format(c=currency_id, d=date))
        # currency_date_id = cr.fetchone()
        # cr.execute("select id from res_currency_rate where currency_id = {c} and "
        #            "name::varchar like '{d}%'".format(c=invoice.currency_id.id, d=date))
        # currency_date_id2 = cr.fetchone()
        # if currency_date_id:
        #     currency_date_id = currency_obj.browse(cr, uid, currency_date_id[0], context)
        # if currency_date_id2:
        #     currency_date_id2 = currency_obj.browse(cr, uid, currency_date_id2[0], context)
        currency_date_id = currency_obj.search(cr, uid, [('name', '=', date), ('currency_id', '=', currency_id)])
        currency_date_id2 = currency_obj.search(cr, uid, [('name', '=', date), ('currency_id', '=', invoice.currency_id.id)])
        rate = 1
        if not currency_date_id and invoice.company_id.currency_id.id != currency_id :
            warning = {
                       'title': _('Advertencia!'),
                       'message' : _("No existe la tasa de cambio para la fecha '%s' ") % (date,)
                    }
        elif invoice.company_id.currency_id.id == invoice.currency_id.id and invoice.company_id.currency_id.id != currency_id:
            rate = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv
        elif invoice.company_id.currency_id.id != invoice.currency_id.id and invoice.company_id.currency_id.id == currency_id:
            if not currency_date_id2:
                warning = {
                       'title': _('Advertencia!'),
                       'message' : _("No existe la tasa de cambio para la fecha '%s' ") % (date,)
                    }
            else:
                rate = 1/currency_obj.browse(cr, uid, currency_date_id2, context=context)[0].rate_inv
        elif invoice.company_id.currency_id.id != invoice.currency_id.id and invoice.company_id.currency_id.id != currency_id:
            if not currency_date_id:
                warning = {
                       'title': _('Advertencia!'),
                       'message' : _("No existe la tasa de cambio para la fecha '%s' ") % (date,)
                    }
            else:
                rate = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv / currency_obj.browse(cr, uid, currency_date_id2, context=context)[0].rate_inv
            
        val['tasa_cambio_conversion'] = rate
        return {'value': val,'warning': warning}
    
    def change_currency(self, cr, uid, ids, context=None):
        obj_inv = self.pool.get('account.invoice')
        obj_inv_line = self.pool.get('account.invoice.line')
        obj_currency = self.pool.get('res.currency')
        currency_obj = self.pool.get('res.currency.rate')
        if context is None:
            context = {}
        data = self.browse(cr, uid, ids, context=context)[0]
        new_currency = data.currency_id.id
        invoice = obj_inv.browse(cr, uid, context['active_id'], context=context)
        date = invoice.date_invoice or time.strftime(DEFAULT_SERVER_DATE_FORMAT)
        rate = data.tasa_cambio_conversion
        
        if rate <= 0:
            raise osv.except_osv(_('Error!'), _('La tasa no puede ser negativa.'))
        if not invoice.currency_id:
            raise osv.except_osv(_('Error!'), _('La factura no tiene divisa'))
        if new_currency == invoice.company_id.currency_id.id:
            raise osv.except_osv(_('Error!'), _('Seleccione una moneda diferente a la de la compania'))
        if new_currency == invoice.currency_id.id:
            raise osv.except_osv(_('Error!'), _('Seleccione una moneda diferente a la de la factura'))
            
        antigua = invoice.currency_id.id
        for line in invoice.invoice_line:
            new_price = 0
            new_price = line.price_unit / rate
            obj_inv_line.write(cr, uid, [line.id], {'price_unit': new_price})
        if new_currency == invoice.company_id.currency_id.id:
            obj_inv.write(cr, uid, [invoice.id], {'currency_id': new_currency,'currency_id2': antigua,'fue_convertida': True,'tasa_manual': 1,'tasa_cambio_conversion': rate,'es_multidivisa' : False}, context=context)
        elif invoice.currency_id.id == invoice.company_id.currency_id.id:
            obj_inv.write(cr, uid, [invoice.id], {'currency_id': new_currency,'currency_id2': antigua,'fue_convertida': True,'tasa_cambio_conversion': rate,'tasa_manual': rate,'es_multidivisa' : True}, context=context)
        elif new_currency != invoice.company_id.currency_id.id and invoice.currency_id.id != invoice.company_id.currency_id.id:
            currency_date_id = currency_obj.search(cr, uid, [('name','=',date),('currency_id','=',new_currency)])
            currency_date_id2 = currency_obj.search(cr, uid, [('name','=',date),('currency_id','=',invoice.currency_id.id)])
            rate2 = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv
            obj_inv.write(cr, uid, [invoice.id], {'currency_id': new_currency,'currency_id2': antigua,'fue_convertida': True,'tasa_cambio_conversion': rate,'tasa_manual': rate2,'es_multidivisa' : True}, context=context)
        obj_inv.onchange_currency_id(cr, uid, ids, new_currency, invoice.company_id.id, date, True, context=context)
            
        return {'type': 'ir.actions.act_window_close'}
    
#Modificacion en el voucher para que tome la tasa correcta
class account_invoice(osv.osv):
    _inherit = "account.invoice"
    
    def change_back_currency(self, cr, uid, ids, context={}):
        obj_inv = self.pool.get('account.invoice')
        obj_inv_line = self.pool.get('account.invoice.line')
        obj_currency = self.pool.get('res.currency')
        currency_obj = self.pool.get('res.currency.rate')
        for invoice in self.browse(cr, uid, ids, context=context):
        
            if not invoice.fue_convertida:
                raise osv.except_osv(_('Error!'), _('La factura no fue convertida'))
            new_currency = invoice.currency_id2.id
            rate = invoice.tasa_cambio_conversion
                
            for line in invoice.invoice_line:
                if new_currency == invoice.company_id.currency_id.id:
                    new_price = line.price_unit * rate
                else:
                    new_price = line.price_unit / rate
                obj_inv_line.write(cr, uid, [line.id], {'price_unit': new_price})
            
            if new_currency == invoice.company_id.currency_id.id:
                obj_inv.write(cr, uid, [invoice.id], {'currency_id': new_currency,'currency_id2': False,'fue_convertida': False,'tasa_manual': 1,'es_multidivisa' : False}, context=context)
            elif invoice.currency_id.id == invoice.company_id.currency_id.id:
                obj_inv.write(cr, uid, [invoice.id], {'currency_id': new_currency,'currency_id2': False,'fue_convertida': False,'tasa_manual': rate,'es_multidivisa' : True}, context=context)
            elif new_currency != invoice.company_id.currency_id.id and invoice.currency_id.id != invoice.company_id.currency_id.id:
                currency_date_id = currency_obj.search(cr, uid, [('name','=',date),('currency_id','=',new_currency)])
                currency_date_id2 = currency_obj.search(cr, uid, [('name','=',date),('currency_id','=',invoice.currency_id.id)])
                rate2 = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv
                obj_inv.write(cr, uid, [invoice.id], {'currency_id': new_currency,'currency_id2': False,'fue_convertida': False,'tasa_manual': rate2,'es_multidivisa' : True}, context=context)
            obj_inv.onchange_currency_id(cr, uid, ids, new_currency, invoice.company_id.id, date, True, context=context)
        return True
    
    def change_to_base_currency(self, cr, uid, ids, context={}):
        obj_inv = self.pool.get('account.invoice')
        obj_inv_line = self.pool.get('account.invoice.line')
        obj_currency = self.pool.get('res.currency')
        currency_obj = self.pool.get('res.currency.rate')
        
        for invoice in self.browse(cr, uid, ids, context=context):
            date = invoice.date_invoice or time.strftime(DEFAULT_SERVER_DATE_FORMAT)
            new_currency = invoice.company_id.currency_id.id
            if invoice.currency_id:
                antigua = invoice.currency_id.id
            else:
                raise osv.except_osv(_('Error!'), _('La factura no tiene divisa'))
            
            if invoice.currency_id.id == new_currency:
                return True
            rate = invoice.tasa_manual
            for line in invoice.invoice_line:
                new_price = line.price_unit * rate
                if new_price <= 0:
                    raise osv.except_osv(_('Error!'), _('La moneda no esta configurada correctamente.'))
                obj_inv_line.write(cr, SUPERUSER_ID, [line.id], {'price_unit': new_price}, context=context)
            
            self.write(cr, uid, [invoice.id], {'currency_id': new_currency,'currency_id2': antigua,'fue_convertida': True, 'tasa_manual': 1,'tasa_cambio_conversion': rate, 'es_multidivisa' : False}, context=context)
        return True
    
    @api.multi
    def compute_invoice_totals(self, company_currency, ref, invoice_move_lines):
        total = 0
        total_currency = 0
        for line in invoice_move_lines:
            if self.currency_id != company_currency:
                currency = self.currency_id.with_context(date=self.date_invoice or fields.Date.context_today(self))
                line['currency_id'] = currency.id
                line['amount_currency'] = line['price']
                # line['price'] = currency.compute(line['price'], company_currency)
                #unico cambio en funcion original
                line['price'] = round(line['price']*self.tasa_manual) if company_currency.rounding == 1 else line['price']*self.tasa_manual
            else:
                line['currency_id'] = False
                line['amount_currency'] = False
            line['ref'] = ref
            if self.type in ('out_invoice','in_refund'):
                total += round(line['price']) if company_currency.rounding == 1 else line['price']
                total_currency += line['amount_currency'] or line['price']
                line['price'] = - line['price']
            else:
                total -= line['price']
                total_currency -= line['amount_currency'] or line['price']
        return total, total_currency, invoice_move_lines
    
    def _amount_locals_all(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            res[invoice.id] = {
                    'amount_untaxed_moneda_local':0.0,
                    'amount_tax_moneda_local':0.0,
                    'total_moneda_local':0.0,
            }
            
            if invoice.journal_id and invoice.journal_id.company_id.currency_id.id != invoice.currency_id.id and invoice.tasa_manual:
                res[invoice.id]['amount_untaxed_moneda_local'] = invoice.amount_untaxed*invoice.tasa_manual
                res[invoice.id]['amount_tax_moneda_local'] = invoice.amount_tax*invoice.tasa_manual
                res[invoice.id]['total_moneda_local'] = round(invoice.amount_total*invoice.tasa_manual) if invoice.company_id.currency_id.rounding == 1 else invoice.amount_total*invoice.tasa_manual
            else:
                res[invoice.id]['amount_untaxed_moneda_local'] = invoice.amount_untaxed
                res[invoice.id]['amount_tax_moneda_local'] = invoice.amount_tax
                res[invoice.id]['total_moneda_local'] = invoice.amount_total
        return res
    
    
    def _check_rate(self, cr, uid, ids, context=None):
        for object in self.browse(cr, uid, ids, context):
            if object.tasa_manual == 0 or object.tasa_manual < 0:
                return False
        return True
    
    _columns = {
        'tasa_manual': fields.float('Tasa de Cambio', digits_compute=dp.get_precision('Exchange Precision'), help='la tasa de cambio, cantidad de moneda para que de 1 de la base',readonly=True, states={'draft':[('readonly',False)]}),
        'moneda_local': fields.related('company_id','currency_id',type="many2one",relation="res.currency",string="Moneda Local"),
        'es_multidivisa': fields.boolean("Multidivisa"),
        'fue_convertida': fields.boolean("Conversion"),
        'tasa_cambio_conversion': fields.float('Tasa Usada en Conversion', digits_compute=dp.get_precision('Exchange Precision'), help='Tasa de cambio usada para el cambio de moneda'),
        'currency_id2': fields.many2one('res.currency', 'Change to', help="Moneda desde la cual se hizo el cambio",readonly=True),
        'amount_untaxed_moneda_local': fields.function(_amount_locals_all, digits_compute=dp.get_precision('Account'), multi='local', string='Total sin impuestos en Moneda Local'),
        'amount_tax_moneda_local': fields.function(_amount_locals_all, digits_compute=dp.get_precision('Account'), multi='local', string='Total impuestos en Moneda Local'),
        'total_moneda_local': fields.function(_amount_locals_all, digits_compute=dp.get_precision('Account'), multi='local', string='Total en Moneda Local',store=True),
    }
    
    _defaults = {
        'tasa_manual': 1,
    }
    
    _constraints = [
        (_check_rate, 'La tasa de cambio no puede ser 0 o negativa', ['tasa_manual']),
    ]
    
    
    def onchange_currency_id(self, cr, uid, ids, currency_id, company_id, date_invoice, fue_convertida, context=None):
        val = {}
        warning = {}
        if currency_id:
            company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
            if fue_convertida:
                if company.currency_id.id != currency_id:
                    multi = True
                else:
                    multi = False
                val['es_multidivisa'] = multi
                val['fue_convertida'] = True
            else:
                if company.currency_id.id != currency_id:
                    date = date_invoice or time.strftime(DEFAULT_SERVER_DATE_FORMAT)
                    currency_obj = self.pool.get('res.currency.rate')
                    currency_date_id = currency_obj.search(cr, uid, [('date_sin_hora','=',date),('currency_id','=',currency_id)])
                    if not currency_date_id:
                        warning = {
                            'title': _('Advertencia!'),
                            'message' : _("No existe la tasa de cambio para la fecha '%s' ") % (date,)
                        }
                        rate = 1
                    else:
                        rate = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv
                    multi = True
                else:
                    rate = 1
                    multi = False
                    
                val['currency_id'] = currency_id
                val['tasa_manual'] = rate
                val['es_multidivisa'] = multi
        return {'value': val,'warning': warning}
    
class account_voucher_line(osv.osv):
    _inherit = 'account.voucher.line'
    _columns = {
        'invoice': fields.many2one('account.invoice', "Factura"),
    }

class account_invoice_line(osv.osv):
    _inherit = "account.invoice.line"
    
    @api.one
    @api.depends('price_subtotal','invoice_id.tasa_manual')
    def _get_local_subtotal(self):
        for record in self:
            type = 1
            if record.invoice_id.type == 'out_refund':
                type = -1
            elif record.invoice_id.type == 'in_refund':
                type = -1
            tasa = record.invoice_id and record.invoice_id.tasa_manual or 1
            self.local_subtotal = record.price_subtotal*tasa*type

    local_subtotal = fields2.Float(compute="_get_local_subtotal", digits=dp.get_precision('Account'), string='Subtotal moneda local', store=True)
    
        
class purchase_order_line(osv.osv):
    _inherit = "purchase.order.line"
    
    def _get_local_subtotal(self, cr, uid, ids, name, arg, context=None):
        res={}
        for record in self.browse(cr, uid, ids, context=context):
            res[record.id] = record.price_subtotal*record.order_id.rate_pactada
        return res
        
    _columns = {
        'local_subtotal': fields.function(_get_local_subtotal, type='float', digits_compute=dp.get_precision('Account'), string='Subtotal moneda local', store=True),
    }
        
class purchase_order(osv.osv):
    _inherit = 'purchase.order'
    
    def _amount_total_local(self, cr, uid, ids, name, args, context=None):
        result = {}
        for order in self.browse(cr, uid, ids, context=context):
            if order.company_id.currency_id.id != order.currency_id.id:
                result[order.id] = order.amount_total*order.rate_pactada
            else:
                result[order.id] = order.amount_total
        return result
        
    def _check_rate(self, cr, uid, ids, context=None):
        for object in self.browse(cr, uid, ids, context):
            if object.rate_pactada == 0 or object.rate_pactada < 0:
                return False
        return True
    
    _columns = {
        'rate_pactada': fields.float('Rate', digits_compute=dp.get_precision('Exchange Precision'), readonly=True, states={'draft': [('readonly', False)]}),
        'multi_currency': fields.boolean('multicurrency', readonly=True, states={'draft': [('readonly', False)]}),
        'total_moneda_local': fields.function(_amount_total_local, digits_compute=dp.get_precision('Account'), string='Total en Moneda Local'),
        'moneda_local': fields.related('company_id','currency_id',type="many2one",relation="res.currency",string="Moneda Local"),
    }
    
    _defaults = {
        'rate_pactada': 1,
    }
    
    _constraints = [
        (_check_rate, 'La tasa de cambio no puede ser 0 o negativa', ['rate_pactada']),
    ]
    
    def _prepare_order_line_move(self, cr, uid, order, order_line, picking_id, group_id, context=None):
        res = super(purchase_order,self)._prepare_order_line_move(cr, uid, order, order_line, picking_id, group_id, context=context)
        if order.currency_id.id != order.company_id.currency_id.id:
            price_unit = order_line.local_subtotal/order_line.product_qty
            res[0].update({'price_unit': price_unit})
        
        return res
        
    def action_invoice_create(self, cr, uid, ids, context=None):
        invoice_pool = self.pool.get('account.invoice')
        invoice_id = False
        for order in self.browse(cr, uid, ids, context=context):
            invoice_id = super(purchase_order,self).action_invoice_create(cr, uid, ids, context=context)
            invoice_pool.write(cr, uid, [invoice_id], {'tasa_manual': order.rate_pactada,'es_multidivisa': order.multi_currency}, context=context)
        return invoice_id
    
    def onchange_pricelist(self, cr, uid, ids, pricelist_id, context=None):
        if not pricelist_id:
            return {}
        val = super(purchase_order, self).onchange_pricelist(cr, uid, ids, pricelist_id, context)

        val['value'].update({'multi_currency': True})
        pricelist_obj = self.pool.get('product.pricelist')

        if pricelist_id:
            rate = 1
            pricelist_rec = pricelist_obj.browse(cr, uid, pricelist_id, context)
            for version in pricelist_rec.version_id:
                if version.active:
                    rate = version.tasa_cambio_pactada

            if pricelist_rec.currency_id and pricelist_rec.currency_id.base:
                val['value'].update({'multi_currency': False, 'rate_pactada': 1})
            elif rate > 1 and pricelist_rec.currency_id:
                val['value'].update({'multi_currency': True, 'rate_pactada': rate})
            else:
                if context.get('date', False):
                    ver_date = context.get('date')
                else:
                    # Homologacion hora servidor
                    ver_date = datetime.strftime(fields2.datetime.now().date() + relativedelta(hours=5),
                                                 "%Y-%m-%d %H:%M:%S")

                currency_obj = self.pool.get('res.currency.rate')
                date_local = avancys_orm.local_date(ver_date, 'UTC')
                currency_date_id = currency_obj.search(cr, uid, [('date_sin_hora', '=', date_local),
                                                                 ('currency_id', '=', pricelist_rec.currency_id.id)])
                if not currency_date_id:
                    raise osv.except_osv(_('Error!'), _('La moneda %s, no tiene tasa de cambio para la fecha %s.') %
                                         (pricelist_rec.currency_id.name, date_local))
                rate = currency_obj.browse(cr, uid, currency_date_id, context=context)[0].rate_inv
                val['value'].update({'multi_currency': True, 'rate_pactada': rate})
        return val

#
