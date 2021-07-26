# -*- coding: utf-8 -*-
from openerp.osv import osv,fields
from openerp import api,models
from openerp import fields as fields2
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
import openerp.netsvc
from datetime import datetime
import time
from dateutil.relativedelta import relativedelta
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.exceptions import Warning
from openerp.addons.avancys_orm import avancys_orm as orm

class ir_config_parameter(models.Model):
    _inherit = "ir.config_parameter"

    # SE AGREGA ESTA FUNCION PARA EVITAR EL CAMBIO DEL PUERTO DE LOS REPORTES QWEB
    @api.multi
    def write(self, vals):
        if vals.get('value',False) and self.key == 'web.base.url':
            vals.update({'value':self.value})
        res = super(ir_config_parameter, self).write(vals)
        return res
       
    
class res_company(models.Model):
    _inherit = "res.company"
    
    account_pg_perdida_id = fields2.Many2one('account.account', string='Perdida del Ejercicio')
    account_pg_ganancia_id = fields2.Many2one('account.account', string='Ganancia del Ejercicio')
    account_pg_pyg_id = fields2.Many2one('account.account', string='Utilidad del Ejercicio')
    account_vacation_id = fields2.Many2one('account.account', string='Cuenta de porvision/consolidacion Vacaciones', required=True, domain=[('type', '=', 'other')])
    amount_vacation = fields2.Float(string='% Provision/Consolidacion Vacaciones', required=True, digits=dp.get_precision('Account'), default=4.17)
    invoice_tax_analytic = fields2.Boolean(string='Impuesto a nivel analitico', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE FACTURACION, DONDE EL SISTEMA TIENE EN CUENTA LA CUENTA ANALITICA COMO CRITERIO DE AGRUPACION DE LOS IMPUESTOS.")

class account_tax_code(osv.osv):
    _inherit = "account.tax.code"
    
    def _sum(self, cr, uid, ids, name, args, context, where ='', where_params=()):
        res2 = super(account_tax_code, self)._sum(cr, uid, ids, name, args, context, where=where, where_params=where_params)
        parent_ids = tuple(self.search(cr, uid, [('parent_id', 'child_of', ids)]))
        if context.get('based_on', 'invoices') == 'payments':
            cr.execute('SELECT line.base_code_id, sum(line.base_amount) \
                    FROM account_move_line AS line, \
                        account_move AS move \
                        LEFT JOIN account_invoice invoice ON \
                            (invoice.move_id = move.id) \
                    WHERE line.base_code_id IN %s '+where+' \
                        AND move.id = line.move_id \
                        AND ((invoice.state = \'paid\') \
                            OR (invoice.id IS NULL)) \
                            GROUP BY line.base_code_id',
                                (parent_ids,) + where_params)
            res=dict(cr.fetchall())
        else:
            cr.execute('SELECT line.base_code_id, sum(line.base_amount) \
                    FROM account_move_line AS line, \
                    account_move AS move \
                    WHERE line.base_code_id IN %s '+where+' \
                    AND move.id = line.move_id \
                    GROUP BY line.base_code_id',
                       (parent_ids,) + where_params)
            res=dict(cr.fetchall())
        obj_precision = self.pool.get('decimal.precision')
        for record in self.browse(cr, uid, ids, context=context):
            def _rec_get(record):
                amount = res.get(record.id, 0.0)
                for rec in record.child_ids:
                    amount += _rec_get(rec) * rec.sign
                return amount
            res2[record.id] += round(_rec_get(record), obj_precision.precision_get(cr, uid, 'Account'))
        return res2
    

class account_tax_api(models.Model):
    _inherit = "account.tax"

    mayor_valor = fields2.Boolean(string='Mayor Valor')
    amount = fields2.Float(string='Amount', required=True, digits=dp.get_precision('Payment Term'), help="For taxes of type percentage, enter % ratio between 0-1.", oldname="amount")  


class purchase_order_line(osv.osv):
    _inherit = "purchase.order.line"
    
    def mayor_valor(self, cr, uid, purchase_line_id, context=None):
        tax_obj = self.pool.get('account.tax')
        tax_mayor_valor = []
        costo_adicional = 0
        for tax_check in purchase_line_id.taxes_id:
            if tax_check.mayor_valor:
                tax_mayor_valor.append(tax_check)
        for tax in tax_obj.compute_all(cr, uid, tax_mayor_valor, (purchase_line_id.price_unit* (1-(purchase_line_id.discount or 0.0)/100.0)), purchase_line_id.product_qty, purchase_line_id.product_id, purchase_line_id.order_id.partner_id)['taxes']:
            costo_adicional+=tax['amount']/purchase_line_id.product_qty
        return costo_adicional


class account_voucher(osv.osv):
    _inherit = "account.voucher"
    
    def cancel_voucher(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        for voucher in self.browse(cr, uid, ids, context=context):
            if voucher.move_id:
                move_pool.button_cancel(cr, uid, [voucher.move_id.id])
                cr.execute("DELETE FROM account_move_line where move_id = {mid}".format(mid=voucher.move_id.id))
                cr.execute("DELETE FROM account_move where id = {mid}".format(mid=voucher.move_id.id))
        res = {
            'state':'cancel',
            'move_id':False,
        }
        self.write(cr, uid, ids, res)
        return True
        
    _columns = {
            'other_partner_id': fields.many2one('res.partner', 'Beneficiario', required=False, readonly=True, states={'draft':[('readonly',False)]}),
            }
    
    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'number':False,
        })
        return super(account_voucher, self).copy(cr, uid, id, default, context)
    
    def onchange_other_partner_id(self, cr, uid, ids, other_partner_id, context):
        res = {}
        if other_partner_id:
            other_partner = self.pool.get('res.partner').browse(cr, uid, other_partner_id, context=context)
            if other_partner.default_bank_id:
                res={'value':{'bank_account_id': other_partner.default_bank_id.id}}
            else:
                res={'value':{'bank_account_id': False}}
        return res
    
    def onchange_partner_id(self, cr, uid, ids, partner_id, journal_id, amount, currency_id, ttype, date, context=None):
        if not journal_id:
            return {}
        res = super(account_voucher,self).onchange_partner_id(cr, uid, ids, partner_id, journal_id, amount, currency_id, ttype, date, context=context)
        res['value'].update({'other_partner_id': partner_id})
        return res

class account_move(models.Model):
    _inherit = "account.move"
    
        
    @api.multi
    def write(self, vals):
        period=self.env['account.period'].search([('date_start', '<=', self.date),('date_stop', '>=', self.date),('state', '=', 'done')])
        if self.date and  period:
            raise osv.except_osv(_('Error !'), _('No es posible modificar registros contables en un periodo contable cerrado'))
        res = super(account_move, self).write(vals)
        return res

    def button_cancel(self, cr, uid, ids, context=None):
        res = super(account_move, self).button_cancel(cr, uid, ids, context=context)
        reconcile_pool = self.pool.get('account.move.reconcile')
        account_move_line_obj = self.pool.get('account.move.line')
        for move in self.browse(cr, uid, ids, context=context):
            recs_control = []
            to_remove = []
            if move.period_id and move.period_id.state == 'done':
                raise osv.except_osv(_('Error!'), _('No es posible Cancelar un comprobante de un periodo ya Cerrado '
                                                    '%s.') % (move.period_id.name))

            cr.execute("SELECT state FROM ir_module_module WHERE name='report_odoo_extended'")
            module = cr.fetchone()
            if module and module[0] == 'installed':
                cr.execute('SELECT move_id FROM account_report_avancys_line where move_id = {move}'
                           .format(move=move.id))
                result1 = cr.fetchall()
                if result1:
                    raise osv.except_osv(_('Error!'), _('No puede cancelar una factura involucrada en un informe '
                                                        'auxiliar de impuestos, por integridad de la informacion '
                                                        'dentro del sistema debe generar un nuevo reporte que no '
                                                        'involucre esta factura (para liberarla). Y posterior al '
                                                        'ajuste requerido ya es posible tener en cuenta esta factura '
                                                        'para que tome la informacion actualizada.'))
            for line in move.line_id:
                if line.state == 'valid':
                    line.state = 'draft'
                if line.reconcile_id:
                    to_remove.append(line.id)
                    if line.reconcile_id not in recs_control:
                        recs_control.append(line.reconcile_id)
                if line.reconcile_partial_id:
                    to_remove.append(line.id)
                    if line.reconcile_partial_id not in recs_control:
                        recs_control.append(line.reconcile_partial_id)
            for recon in recs_control:
                move_line_reconcile_ids = [(x.id, x.debit) for x in recon.line_id if x.id not in to_remove]
                move_line_reconcile_ids += [(x.id, x.debit) for x in recon.line_partial_ids if x.id not in to_remove]
                reconcile_pool.unlink(cr, uid, [recon.id])
                cr.execute("UPDATE account_move_line SET reconcile_id=Null, reconcile_partial_id=Null,"
                           "reconcile_ref=Null WHERE reconcile_id = {rid} OR reconcile_partial_id = {rid}"
                           .format(rid=recon.id))
                cr.execute("DELETE FROM account_move_reconcile WHERE id = %s" % recon.id)
                if len(move_line_reconcile_ids) > 1 and sum([x[1] for x in move_line_reconcile_ids]) > 0:
                    account_move_line_obj.reconcile_partial(cr, uid, [x[0] for x in move_line_reconcile_ids],
                                                            writeoff_acc_id=False, writeoff_period_id=False,
                                                            writeoff_journal_id=False)
        return res


class account_fiscal_position(osv.osv):
    _inherit = "account.fiscal.position"
    _columns = {
        'sequence_sale_id': fields.many2one('ir.sequence', 'Consecutivo de ventas', help="este consecutivo se usara en las facturas de venta"),
        'sequence_purchase_id': fields.many2one('ir.sequence', 'Consecutivo de compras', help="este consecutivo se usara en las facturas de compra"),
    }
    
    def get_sequence(self, cr, uid, position, type='purchase', context=None):
        obj_sequence = self.pool.get('ir.sequence')
        res = False
        if type=='purchase' and position.sequence_purchase_id:
            res = obj_sequence.next_by_id(cr, uid, position.sequence_purchase_id.id, context=context)
        elif type=='sale' and position.sequence_sale_id:
            res = obj_sequence.next_by_id(cr, uid, position.sequence_sale_id.id, context=context)
            
        return res

class mail_message_subtype(osv.osv):
    _inherit = 'mail.message.subtype'
    _order = "sequence desc"
    _columns = {
        'sequence': fields.float('Sequence'),
    }

class account_period(osv.osv):
    _inherit = 'account.period'
    
    _columns = {
        'closing_period': fields.date('Cierre Contable', states={'done':[('readonly',True)]}),
    }
    
    def cron_periodo_cercano_a_cierre(self, cr, uid, dias_aviso=5, mensaje=False, subject=False, context=None):
        if not context:
            context={}
        contract_obj = self.pool.get('hr.contract')
        company_obj = self.pool.get('res.company')
        message_obj = self.pool.get('mail.message')
        fecha_hoy = datetime.now()
        fecha_hoy_str = fecha_hoy.strftime(DEFAULT_SERVER_DATE_FORMAT)
        fecha_now_str = fecha_hoy.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        fecha_aviso = fecha_hoy+relativedelta(days=dias_aviso)
        fecha_aviso_str = fecha_aviso.strftime(DEFAULT_SERVER_DATE_FORMAT)
        if not subject:
            subject = 'Alerta cierre contable del mes'
        if not mensaje:
            mensaje = 'El proximo cierre contable del mes sera en '+str(dias_aviso)+' dias ('+fecha_aviso_str+')'
        company_ids = company_obj.search(cr, uid, [], context=context)
        contract_ids = False
        
        for company in company_obj.browse(cr, uid, company_ids, context=context):
            context.update({'company_id': company.id})
            period_ids = self.find(cr, uid, fecha_hoy, context=context)
            period_id = period_ids and period_ids[0] or False
            if period_id:
                period = self.browse(cr, uid, period_id, context=context)
                if period.closing_period and period.closing_period == fecha_aviso_str:
                    if not contract_ids:
                        contract_ids = contract_obj.search(cr, uid, [('manager', '=', True)], context=context) 
                    if contract_ids:
                        partners = []
                        for contract in contract_obj.browse(cr, uid, contract_ids, context=context):
                            user = contract.employee_id.user_id
                            if user and (company.id in [x.id for x in user.company_ids] or company.id == user.company_id.id):
                                partners.append(user.partner_id.id)
                            
                        vals = {
                            'author_id': company.partner_id.id,
                            'date' : fecha_now_str,
                            'subject' : subject,
                            'body' : mensaje,
                            'type' : 'comment',
                            'partner_ids': [(6, 0,partners)],
                            'notified_partner_ids': [(6, 0,partners)],
                        }
                        messaje_id = message_obj.create(cr, uid, vals, context=context)
                
        return True

class res_company_old(osv.osv):
    _inherit = 'res.company'
    
    _columns = {
        'config_analytic_global': fields.boolean(string='Contabilidad Analitica Global',help="Permite Gestionar la contabilidad analitica en cuentas de balance"),
        'journal_expense_ids': fields.many2many('account.journal', 'rel_journals_default', 'company_id', 'journal_id', 'Diarios Legalizaciones'),
        'date_expense': fields.boolean('Usar fecha legalizacion',help="Utiliza la fecha de la legalizacion para todas las lineas del comprobante, de lo contrario la linea usara la fecha de su linea de legalizacion correspondiente"),
    }
    
    def _check_journals_currency(self, cr, uid, ids, context=None):
        res = {}
        for company in self.browse(cr, uid, ids, context=context):
            currencys = []
            local = 0
            for journal in company.journal_expense_ids:
            
                if not journal.currency:
                    if local == 0:
                        local = 1
                    else:
                        return False
                if journal.currency in currencys:
                    return False
                else:
                    currencys.append(journal.currency)
        return True
    
    _constraints = [
        (_check_journals_currency, 'Error! Solo puede haber un diario de una moneda configurado por defecto', ['journal_expense_ids']),
    ]

class account_tax(osv.osv):    
    _inherit = 'account.tax'
    
    _columns = {
        'cost_efect': fields.boolean('Afecta CC Costo'),
        'expense_efect': fields.boolean('Afecta CC Gasto'),
        'cost_venta':fields.boolean(string='Afecta CC Gastos de Venta'),
        'paid_cost_venta':fields.boolean(string='Afecta CC Gastos de Venta'),
        'property_account_gastos_venta':fields.property(type='many2one',relation='account.account', string="Cuenta de Gastos de venta"),
        'paid_property_account_gastos_venta':fields.property(type='many2one',relation='account.account', string="Cuenta de Gasto de Venta Reintegro"),        
        'property_account_cost': fields.property(type='many2one',relation='account.account',string="Cuenta de Costo"),
        'property_account_expense': fields.property(type='many2one',relation='account.account',string="Cuenta de Gasto"),
        'paid_cost_efect': fields.boolean('Afecta CC Costo'),
        'paid_expense_efect': fields.boolean('Afecta CC Gasto'),
        'paid_property_account_cost': fields.property(type='many2one',relation='account.account',string="Cuenta de Costo Reintegro"),
        'paid_property_account_expense': fields.property(type='many2one',relation='account.account',string="Cuenta de Gasto Reintegro"),
    }
    
    def _unit_compute(self, cr, uid, taxes, price_unit, product=None, partner=None, quantity=0):
        taxes =  super(account_tax, self)._unit_compute(cr, uid, taxes, price_unit, product=product, partner=partner, quantity=quantity)
        for tax in taxes:
            # we compute the amount for the current tax object and append it to the result
            tax_obj = self.browse(cr, uid, tax['id'], context=None)
            tax['property_account_cost'] = tax_obj.property_account_cost and tax_obj.property_account_cost.id or False
            tax['cost_efect'] = tax_obj.cost_efect or False
            tax['property_account_expense'] = tax_obj.property_account_expense and tax_obj.property_account_expense.id or False
            tax['expense_efect'] = tax_obj.expense_efect or False
            tax['property_account_gastos_venta'] = tax_obj.property_account_gastos_venta and tax_obj.property_account_gastos_venta.id or False
            tax['cost_venta'] = tax_obj.cost_venta or False
            
            tax['paid_property_account_cost'] = tax_obj.property_account_cost and tax_obj.property_account_cost.id or False
            tax['paid_cost_efect'] = tax_obj.cost_efect or False
            tax['paid_property_account_expense'] = tax_obj.property_account_expense and tax_obj.property_account_expense.id or False
            tax['paid_expense_efect'] = tax_obj.expense_efect or False
            tax['paid_property_account_gastos_venta'] = tax_obj.paid_property_account_gastos_venta and tax_obj.paid_property_account_gastos_venta.id or False
            tax['paid_cost_venta'] = tax_obj.cost_venta or False
        return taxes
    
class account_invoice_tax(models.Model):
    _inherit = "account.invoice.tax"
    
    @api.one
    @api.depends('manual')
    def _state_manual(self):
        if self.manual:
            self.state = 'manual'
        else:
            self.state = 'automatic'
    
    manual = fields2.Boolean(string='Manual', default=True, readonly=True)
    invoice_id = fields2.Many2one('account.invoice', string='Invoice Line',ondelete='cascade', index=True, readonly=True, states={'manual':[('readonly',False)]})
    partner_id_2 = fields2.Many2one('res.partner', string='Tercero', index=True, readonly=True, states={'manual':[('readonly',False)]})
    name = fields2.Char(string='Tax Description', required=True, readonly=True, states={'manual':[('readonly',False)]})
    account_id = fields2.Many2one('account.account', string='Tax Account', required=True, readonly=True, states={'manual':[('readonly',False)]}, domain=[('type', 'not in', ['view', 'income', 'closed'])])
    account_analytic_id = fields2.Many2one('account.analytic.account', string='Analytic account', readonly=True, states={'manual':[('readonly',False)]})
    ##
    base = fields2.Float(string='Base', digits=dp.get_precision('Account'), readonly=True, states={'manual':[('readonly',False)]})
    amount = fields2.Float(string='Amount', digits=dp.get_precision('Account'), readonly=True, states={'manual':[('readonly',False)]})
    sequence = fields2.Integer(string='Sequence', help="Gives the sequence order when displaying a list of invoice tax.", readonly=True, states={'manual':[('readonly',False)]})
    base_code_id = fields2.Many2one('account.tax.code', string='Base Code', help="The account basis of the tax declaration.", readonly=True, states={'manual':[('readonly',False)]})
    base_amount = fields2.Float(string='Base Code Amount', digits=dp.get_precision('Account'), default=0.0, readonly=True, states={'manual':[('readonly',False)]})
    tax_code_id = fields2.Many2one('account.tax.code', string='Tax Code', help="The tax basis of the tax declaration.", readonly=True, states={'manual':[('readonly',False)]})
    tax_amount = fields2.Float(string='Tax Code Amount', digits=dp.get_precision('Account'), default=0.0, readonly=True, states={'manual':[('readonly',False)]})
    state = fields2.Char(string='State', compute='_state_manual', store=True)
    
    @api.model
    def move_line_get(self, invoice_id):
        res = []
        self._cr.execute(
            'SELECT * FROM account_invoice_tax WHERE invoice_id = %s',
            (invoice_id,)
        )
        for row in self._cr.dictfetchall():
            if not (row['amount'] or row['tax_code_id'] or row['tax_amount']):
                continue
            res.append({
                'type': 'tax',
                'name': row['name'],
                'price_unit': row['amount'],
                'quantity': 1,
                'price': row['amount'] or 0.0,
                'account_id': row['account_id'],
                'tax_code_id': row['tax_code_id'],
                'tax_amount': row['tax_amount'],
                'base_code_id': row['base_code_id'],
                'base_amount': row['base_amount'],
                'account_analytic_id': row['account_analytic_id'],
                'partner_id_2': row['partner_id_2'],
            })
        return res
    
    @api.v8
    def compute(self, inv):
        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        product_obj = self.pool.get('product.product')
        fposition_pool = self.pool.get('account.fiscal.position')
        fposition = inv.fiscal_position or inv.partner_id.property_account_position or False
        cr = self._cr
        uid = self._uid
        context = self._context
        cur = inv.currency_id
        company_currency = inv.company_id.currency_id.id
        invoice_tax_analytic= inv.company_id.invoice_tax_analytic
        config_analytic_global=inv.company_id.config_analytic_global
        for line in inv.invoice_line:
            final_taxes = []
            taxes_to_compute = tax_obj.compute_all(
                cr, uid, line.invoice_line_tax_id, (line.price_unit * (1-(line.discount or 0.0)/100.0)), line.quantity,
                line.product_id, inv.partner_id)['taxes']
            # Mapping child taxes REQ-0000006885
            if taxes_to_compute:
                for tax in taxes_to_compute:
                    company_partner = False
                    if inv.company_id.ciiu_ica:
                        company_partner = inv.partner_id
                    if inv.type in ['out_invoice', 'out_refund']:
                        company_partner = inv.company_id.partner_id
                    if not line.ciiu_id:
                        if inv.type in ['out_invoice', 'out_refund']:
                            line.ciiu_id = inv.company_id.partner_id.ciiu_id
                        else:
                            line.ciiu_id = inv.partner_id.ciiu_id
                    ctx = {'ciiu': line.ciiu_id}

                    tax_id = tax_obj.browse(cr, uid, tax['id'], context=context)
                    city = False
                    if tax_id.check_lines:
                        if inv.company_id.city_cc:
                            city = line.account_analytic_id.city_id
                        else:
                            city = line.city_id
                    else:
                        if inv.partner_shipping_id and inv.partner_shipping_id.city_id:
                            city = inv.partner_shipping_id.city_id
                        elif company_partner and company_partner.city_id:
                            city = company_partner.city_id
                        if line.product_id.type in ['consu', 'product']:
                            city = inv.partner_id.city_id

                    tax_base = cur_obj.round(cr, uid, cur, tax['price_unit'] * line['quantity'])
                    taxes_to_map = {tax_id: tax_base}

                    if tax_id.check_lines:
                        if inv.company_id.ciiu_ica:
                            r = fposition_pool.map_city(cr, uid, taxes_to_map, city, line.ciiu_id, context=ctx)
                        else:
                            r = [x.id for x in taxes_to_map]
                        if r:
                            if tax['id'] == r[0]:
                                final_taxes.append(tax)
                            else:
                                final_taxes.append(
                                    tax_obj.compute_all(cr, uid, tax_obj.browse(cr, uid, r, context=context),
                                                        tax['price_unit'], line.quantity,
                                                        line.product_id, inv.partner_id)['taxes'][0])
                    else:
                        final_taxes.append(tax)

            print [t['name'] for t in final_taxes]
            for tax in final_taxes:
                val = {}
                valid = True
                val['id'] = tax['id']
                val['invoice_id'] = inv.id
                val['partner_id_2'] = line.partner_id_2 and line.partner_id_2.id or inv.partner_id.id
                val['account_analytic_id'] = False
                val['name'] = tax['name']
                val['amount'] = tax['amount']
                val['state'] = 'automatic'
                val['sequence'] = tax['sequence']
                val['manual'] = False
                val['base'] = cur_obj.round(cr, uid, cur, tax['price_unit'] * line['quantity'])
                if inv.type in ('out_invoice','in_invoice'):
                    analytic_default=False
                    val['base_code_id'] = tax['base_code_id']
                    val['tax_code_id'] = tax['tax_code_id']
                    val['base_amount'] = cur_obj.compute_tasa(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['base_sign'], rate=inv.tasa_manual, context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute_tasa(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['tax_sign'], rate=inv.tasa_manual, context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    
                    try:
                        if inv.company_id.analytic_default and inv.type == 'out_invoice':
                            analytic_default=True
                    except:
                        pass
                    
                    if line.account_analytic_id and line.account_analytic_id.costo_gasto == 'gasto' and not analytic_default and tax['property_account_expense']:
                        val['account_id'] = tax['property_account_expense']
                        if tax['expense_efect']:
                            if tax['account_analytic_collected_id']:
                                val['account_analytic_id'] = tax['account_analytic_collected_id']
                            else:
                                val['account_analytic_id'] = line.account_analytic_id.id
                    elif line.account_analytic_id and line.account_analytic_id.costo_gasto == 'costo' and tax['property_account_cost'] and not analytic_default:
                        val['account_id'] = tax['property_account_cost']
                        if tax['cost_efect']:
                            if tax['account_analytic_collected_id']:
                                val['account_analytic_id'] = tax['account_analytic_collected_id']
                            else:
                                val['account_analytic_id'] = line.account_analytic_id.id
                    
                    elif line.account_analytic_id and line.account_analytic_id.costo_gasto == 'gasto_venta' and tax['property_account_gastos_venta'] and not analytic_default:                        
                        val['account_id'] = tax['property_account_gastos_venta']
                        if tax['cost_venta']:
                            if tax['account_analytic_collected_id']:
                                val['account_analytic_id'] = tax['account_analytic_collected_id']
                            else:
                                val['account_analytic_id'] = line.account_analytic_id.id
                        
                    elif tax['account_collected_id']:
                        val['account_id'] = tax['account_collected_id']
                        if tax['account_analytic_collected_id']:
                            val['account_analytic_id'] = tax['account_analytic_collected_id']
                        else:
                            val['account_analytic_id'] = line.account_analytic_id.id
                    elif not tax['account_collected_id'] and not tax['property_account_cost'] and not tax['property_account_expense']:
                        val['account_analytic_id'] = tax['account_analytic_collected_id']
                        if tax['account_analytic_collected_id']:
                            val['account_id'] = product_obj.get_account_from_analytic(cr, uid, line.product_id, tax['account_analytic_collected_id'], context)
                        else:
                            val['account_analytic_id'] = line.account_analytic_id.id
                            val['account_id'] = line.account_id.id
                    else:
                        valid = False
                    
                    #Eliminar registros analiticos en cuentas de impuestos
                    tax_account = tax['account_collected_id']
                    if tax_account:
                        tax_account = self.env['account.account'].browse(tax_account)
                        if not val['account_analytic_id']:
                            val['account_analytic_id'] = line.account_analytic_id.id
                        if not config_analytic_global and str(tax_account.code[0]) not in ['4', '5', '6', '7']:
                            val['account_analytic_id'] = False


                        
                else:
                    val['base_code_id'] = tax['ref_base_code_id']
                    val['tax_code_id'] = tax['ref_tax_code_id']
                    val['base_amount'] = cur_obj.compute_tasa(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['ref_base_sign'], rate=inv.tasa_manual, context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute_tasa(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['ref_tax_sign'], rate=inv.tasa_manual, context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    if line.account_analytic_id:
                        val['account_analytic_id'] = line.account_analytic_id.id
                    if tax['account_paid_id']:
                        val['account_id'] = tax['account_paid_id']
                        if tax['account_analytic_paid_id']:
                            val['account_analytic_id'] = tax['account_analytic_paid_id']
                    elif line.account_analytic_id and line.account_analytic_id.costo_gasto == 'gasto' and 'paid_property_account_expense' in tax and tax['paid_property_account_expense']:
                        val['account_id'] = tax['paid_property_account_expense']
                        if tax['paid_expense_efect']:
                            val['account_analytic_id'] = line.account_analytic_id.id
                    elif line.account_analytic_id and line.account_analytic_id.costo_gasto == 'costo' and 'paid_property_account_cost' in tax and tax['paid_property_account_cost']:
                        val['account_id'] = tax['paid_property_account_cost']
                        if tax['paid_cost_efect']:
                            val['account_analytic_id'] = line.account_analytic_id.id                            
                    elif line.account_analytic_id and line.account_analytic_id.costo_gasto == 'gasto_venta' and 'paid_property_account_gastos_venta' in tax and  tax['paid_property_account_gastos_venta']:
                        val['account_id'] = tax['paid_property_account_gastos_venta']
                        if tax['paid_cost_venta']:
                            val['account_analytic_id'] = line.account_analytic_id.id                         
                    elif not tax['account_paid_id'] and not tax['paid_property_account_cost'] and not tax['paid_property_account_expense']:
                        val['account_analytic_id'] = tax['account_analytic_paid_id']
                        if tax['account_analytic_paid_id']:
                            val['account_id'] = product_obj.get_account_from_analytic(cr, uid, line.product_id, tax['account_analytic_paid_id'], context)
                        else:
                            val['account_id'] = product_obj.get_account_from_analytic(cr, uid, line.product_id, line.account_analytic_id, context)
                    else:
                        valid = False
                    
                    #Eliminar registros analiticos en cuentas de impuestos
                    tax_account = tax['account_collected_id']
                    if tax_account:
                        tax_account = self.env['account.account'].browse(tax_account)
                        if not val['account_analytic_id']:
                            val['account_analytic_id'] = line.account_analytic_id.id
                        if not config_analytic_global and str(tax_account.code[0]) not in ['4', '5', '6', '7']:
                            val['account_analytic_id'] = False
                
                
                
                #implementacion de funcionalidad de account_asset_extended
                try:
                    purchase_asset=False
                    impuesto = tax_obj.browse(cr, uid, tax['id'], context=context)
                    if (line.asset_category_id and impuesto.en_activo):
                        try:
                            if inv.company_id.purchase_asset and line.stock_move_ids and line.stock_move_ids[0].purchase_asset == 'inventary':
                                purchase_asset=True
                        except:
                            pass
                        
                        if not purchase_asset:
                            try:
                                val['account_id'] = line.asset_category_id.account_asset_id.id
                            except:
                                raise osv.except_osv(_('Error !'), _(
                                    "Usted no cuenta con permisos de lectura para el modelo de categoria de activos"))

                except:
                    raise osv.except_osv(_('Error !'), _(
                            "Usted no cuenta con permisos de lectura para el modelo de categoria de activos, por favor contacte al administrador del sistema para poder continuar con el proceso"))

                #implementacion para el modulo accrued_account_payable_id
                try:
                    if impuesto.mayor_valor and line.product_id and line.product_id.type != 'service' and inv.partner_id.accrued_account_payable_id:
                        val['account_id'] = inv.partner_id.accrued_account_payable_id.id
                        val['tax_code_id'] = False
                        val['base_code_id'] = False
                        val['base_amount'] = 0
                        val['tax_amount'] = 0
                    elif impuesto.mayor_valor and (line.product_id.type == 'service' or not line.product_id) and line.account_id:
                        val['account_id'] = line.account_id.id
                        val['tax_code_id'] = False
                        val['base_code_id'] = False
                        val['base_amount'] = 0
                        val['tax_amount'] = 0
                except:
                    pass
                
                if valid:
                    tax_to_group = tax_obj.browse(cr, uid, tax['id'], context=context)
                    if invoice_tax_analytic:
                        if inv.company_id.ciiu_ica and tax_to_group.parent_city_id:
                            key = (
                                val['tax_code_id'], val['base_code_id'], val['account_id'], val['account_analytic_id'],
                                val['partner_id_2'], val['id'])
                        else:
                            key = (val['tax_code_id'], val['base_code_id'], val['account_id'],
                                   val['account_analytic_id'], val['partner_id_2'])
                    else:
                        if inv.company_id.ciiu_ica and tax_to_group.parent_city_id:
                            key = (val['tax_code_id'], val['base_code_id'], val['account_id'], val['partner_id_2'],
                                   val['id'])
                        else:
                            key = (val['tax_code_id'], val['base_code_id'], val['account_id'], val['partner_id_2'])

                    # key = (val['tax_code_id'], val['base_code_id'], val['account_id'], val['account_analytic_id'])
                    if key not in tax_grouped:
                        tax_grouped[key] = val
                    else:
                        tax_grouped[key]['amount'] += val['amount']
                        tax_grouped[key]['base'] += val['base']
                        tax_grouped[key]['base_amount'] += val['base_amount']
                        tax_grouped[key]['tax_amount'] += val['tax_amount']

        if inv.company_id.ciiu_ica:
            taxes_mapped = {}
            for k, t in tax_grouped.iteritems():
                ttm = {tax_obj.browse(cr, uid, t['id'], context): t['base']}
                bandera = fposition_pool.map_base(cr, uid, fposition, ttm, context)
                if bandera:
                    t['base'] = cur_obj.round(cr, uid, cur, t['base'])
                    t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
                    t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
                    t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])
                    taxes_mapped[k] = t
        else:
            taxes_mapped = {}
            for k, t in tax_grouped.iteritems():
                t['base'] = cur_obj.round(cr, uid, cur, t['base'])
                t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
                t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
                t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])
                taxes_mapped[k] = t
        return taxes_mapped


class account_analytic_account(osv.osv):
    _inherit = "account.analytic.account"

    _columns = {
        'cc1': fields.char('cc1',size=32, required=False),
        'cc2': fields.char('cc2',size=32, required=False),
        'cc3': fields.char('cc3',size=32, required=False),
        'cc4': fields.char('cc4',size=32, required=False),
        'cc5': fields.char('cc5',size=32, required=False),
        'costo_gasto': fields.selection([('costo','Costo'),('gasto','Gasto'),('gasto_venta','Gasto de Venta')], string='Tipo', select=True),
    }
    
    def onchange_atrb(self, cr , uid, ids, cc1, cc2, cc3, cc4, cc5, context = None):
        return {'value': {'name' : (cc1 or '') +"-"+ (cc2 or '') +"-"+ (cc3 or '') +"-"+ (cc4 or '') +"-"+ (cc5 or '') }}
    
class account_analytic_line(models.Model):
    _inherit = "account.analytic.line"
    
    @api.one
    @api.depends('currency_id','move_id.amount_currency','move_id.debit','move_id.credit')
    def _get_currency_amount(self):
        if self.currency_id and self.move_id.amount_currency and self.move_id.debit+self.move_id.credit:
            rate = (self.move_id.debit+self.move_id.credit)/self.move_id.amount_currency
            self.amount_currency = self.amount/rate
        else:
            self.amount_currency = 0
            
    @api.one
    @api.depends('move_id.partner_id','move_id.period_id')
    def _get_partner(self):
        if self.move_id and self.move_id.partner_id:
            self.partner_id = self.move_id.partner_id.id
        if self.move_id and self.move_id.period_id:
            self.period_id = self.move_id.period_id.id
        
    
    cc1 = fields2.Char(related='account_id.cc1', string="cc1", store=True, readonly=True)
    cc2 = fields2.Char(related='account_id.cc2', string="cc2", store=True, readonly=True)
    cc3 = fields2.Char(related='account_id.cc3', string="cc3", store=True, readonly=True)
    cc4 = fields2.Char(related='account_id.cc4', string="cc4", store=True, readonly=True)
    cc5 = fields2.Char(related='account_id.cc5', string="cc5", store=True, readonly=True)
    partner_id = fields2.Many2one('res.partner', string="Tercero", compute="_get_partner", store=True, readonly=True)
    period_id = fields2.Many2one('account.period', string="Periodo", compute="_get_partner", store=True, readonly=True)
    amount_currency = fields2.Float(string='Amount Currency', digits=dp.get_precision('Account'), compute="_get_currency_amount", readonly=True, store=True, help="The amount expressed in the related account currency if not equal to the company one.")
    account_niif_id = fields2.Many2one('account.account', string="Cuenta NIIF")
        
class product_category(osv.osv):
    _inherit = "product.category"

    _columns = {
        'property_account_costos_categ': fields.property(type='many2one', relation='account.account',string="Cuenta de Costo"),
        'gasto_venta_property_id': fields.property(type='many2one', relation='account.account', string="Cuenta de Gasto de Venta", domain=[('type', 'not in', ['view', 'income', 'closed'])]),
        'account_discount_id': fields.property(type='many2one',relation='account.account',string='Cuenta Descuentos Comerciales', domain=[('type', 'not in', ['view', 'income', 'closed'])]),
        'account_return_id': fields.property(type='many2one', relation='account.account', string="Cuenta Devolucion", domain=[('type', 'not in', ['view', 'income', 'closed'])]),
    }

class product_pricelist(osv.osv):
    _inherit = "product.pricelist"

    _columns = {
        'currency2_id': fields.many2one('res.currency','Moneda de facturacion'),
    }

class res_partner(osv.osv):
    _inherit = "res.partner"
    
    _columns = {
        'default_bank_id': fields.many2one('res.partner.bank','Cuenta de banco por defecto', domain="[('partner_id','=',active_id)]"),
    }
    
class partner_bank(osv.osv):
    _inherit = "res.partner.bank"

    _columns = {
        'state': fields.selection((('iban','Cuenta IBAN'), ('bank','Cuenta Normal de Banco'), ('ahorros','Cuenta de Ahorros'), ('corriente','Cuenta Corriente')),'state'),
        'bank_name': fields.related('bank','name',type="char",string="Nombre", readonly=True),
        'bank_bic': fields.related('bank','bic',type="char",string="Codigo", readonly=True),
    }

class product_product(osv.osv):
    _inherit = "product.product"
    
    def get_account_from_analytic(self, cr, uid, product, centro_costo, context=None):
        cuenta = False
        if product:
            if centro_costo and centro_costo.costo_gasto == 'gasto':
                if product.property_account_expense:
                    cuenta = product.property_account_expense.id
                elif product.categ_id.property_account_expense_categ:
                    cuenta = product.categ_id.property_account_expense_categ.id
                else:
                    raise osv.except_osv(_('Error !'), _("La Cuenta de Gastos no esta definida en el producto '%s' ni en su categoria") % (product.name,))
            elif centro_costo and centro_costo.costo_gasto == 'gasto_venta':
                if product.gasto_venta_property_id:
                    cuenta = product.gasto_venta_property_id.id
                elif product.categ_id.gasto_venta_property_id:
                    cuenta = product.categ_id.gasto_venta_property_id.id
                else:
                    raise osv.except_osv(_('Error !'), _("La Cuenta de Gastos de venta no esta definida en el producto '%s' ni en su categoria") % (product.name,))
            else:#costo
                if product.costo_account_property:
                    cuenta = product.costo_account_property.id
                elif product.categ_id.property_account_costos_categ:
                    cuenta = product.categ_id.property_account_costos_categ.id
                else:
                    raise osv.except_osv(_('Error !'), _("La Cuenta de Costos no esta definida en el producto '%s' ni en su categoria") % (product.name,))
        return cuenta
    
class product_template(osv.osv):
    _inherit = "product.template"

    _columns = {
        'costo_account_property': fields.property(type='many2one',relation='account.account',string="Cuenta de Costo"),
        'gasto_venta_property_id': fields.property(type='many2one',relation='account.account',string='Cuenta de Gasto de Venta', domain=[('type', 'not in', ['view', 'income', 'closed'])]),
        'account_discount_id': fields.property(type='many2one',relation='account.account',string='Cuenta Descuentos Comerciales', domain=[('type', 'not in', ['view', 'income', 'closed'])]),
        'account_return_id': fields.property(type='many2one', relation='account.account', string="Cuenta Devolucion", domain=[('type', 'not in', ['view', 'income', 'closed'])]),
    }

class account_invoice(models.Model):
    _inherit = "account.invoice"

    @api.multi
    def _get_domain(self):
        country_id = self.env.user.company_id.country_id.id
        self._cr.execute('SELECT id FROM res_country_state WHERE country_id = {cid}'.format(cid=country_id))
        prov_ids = self._cr.fetchall()
        prov_ids = tuple([x[0] for x in prov_ids])
        return [('provincia_id', 'in', prov_ids)]

    @api.one
    @api.depends('invoice_line')
    def _num_items(self):
        if self.invoice_line:
            num_items = 0.0
            for line in self.invoice_line:
                num_items += line.quantity
            self.num_items = num_items
    
    num_items=fields2.Float(string='Numero de items', compute="_num_items", store=True)
    ref1=fields2.Char(string='Referencia 1',size=32, readonly=True, states={'draft':[('readonly',False)]})
    ref2=fields2.Char(string='Referencia 2',size=32, readonly=True, states={'draft':[('readonly',False)]})
    print_date=fields2.Date(string='Fecha Impresa')
    supplier_invoice=fields2.Char(string='No. Factura Proveedor', copy=False, size=32, readonly=True, states={'draft':[('readonly',False)],'cancel':[('readonly',False)]})
    equivalente=fields2.Boolean(string='Equivalente', related='journal_id.equivalente', readonly=True, store=True)
    munic_id = fields2.Many2one('res.city', string='Municipio', domain=_get_domain, help='Municipio donde se vendió el'
                                    ' producto o prestó el servicio')
    munic_cod = fields2.Char(string='Código', readonly=True, help='Código del Municipio')
    
    _sql_constraints = [
        ('number2_uniq', 'unique(supplier_invoice,partner_id)', 'El "No. Factura Proveedor" debe ser unico por tercero!'),
    ]

    @api.multi
    @api.onchange('munic_id')
    def get_code(self):
        if self.munic_id:
            self.munic_cod = self.munic_id.provincia_id.code + self.munic_id.code

    @api.model
    def create(self, vals):
        if not vals.has_key('munic_cod') and vals.has_key('munic_id'):
            munic_obj = self.env['res.city'].browse(vals['munic_id'])
            vals['munic_cod'] = munic_obj.provincia_id.code + munic_obj.code
        return super(account_invoice, self).create(vals)

    @api.multi
    def write(self, vals):
        if not vals.has_key('munic_cod') and vals.has_key('munic_id'):
            munic_obj = self.env['res.city'].browse(vals['munic_id'])
            vals['munic_cod'] = munic_obj.provincia_id.code + munic_obj.code
        return super(account_invoice, self).write(vals)

    @api.multi
    def check_tax_lines(self, compute_taxes):
        for t in self.tax_line:
            t.unlink()
        account_invoice_tax = self.env['account.invoice.tax']
        company_currency = self.company_id.currency_id
        account_tax = self.env['account.tax']
        if not self.tax_line:
            for tax in compute_taxes.values():
                account_invoice_tax.create(tax)
        else:
            tax_key = []
            precision = self.env['decimal.precision'].precision_get('Account')
            for tax in self.tax_line:
                tax_ref = account_tax.search([('name', '=', tax.name)])
                if tax_ref and len(tax_ref) > 0:
                    tax_ref = tax_ref[0]
                else:
                    tax_ref = False

                if tax.manual:
                    continue

                if self.company_id.invoice_tax_analytic:
                    if self.company_id.ciiu_ica and tax_ref and tax_ref.parent_city_id:
                        key = (tax.tax_code_id.id, tax.base_code_id.id, tax.account_id.id, tax.account_analytic_id.id,
                               tax.partner_id_2.id, tax_ref.id)
                    else:
                        key = (tax.tax_code_id.id, tax.base_code_id.id, tax.account_id.id, tax.account_analytic_id.id,
                               tax.partner_id_2.id)
                else:
                    if self.company_id.ciiu_ica and tax_ref and tax_ref.parent_city_id:
                        key = (tax.tax_code_id.id, tax.base_code_id.id, tax.account_id.id, tax.partner_id_2.id,
                               tax_ref.id)
                    else:
                        key = (tax.tax_code_id.id, tax.base_code_id.id, tax.account_id.id, tax.partner_id_2.id)

                tax_key.append(key)
                if key not in compute_taxes:
                    raise Warning(_('Global taxes defined, but they are not in invoice lines !'))
                base = compute_taxes[key]['base']
                if float_compare(abs(base - tax.base), company_currency.rounding, precision_digits=precision) == 1:
                    raise Warning(_('Tax base different!\nClick on compute to update the tax base.'))
            for key in compute_taxes:
                if key not in tax_key:
                    raise Warning(_('Taxes are missing!\nClick on compute button.'))

    @api.multi
    def _get_analytic_lines(self):
        """ Return a list of dict for creating analytic lines for self[0] """
        company_currency = self.company_id.currency_id
        sign = 1 if self.type in ('out_invoice', 'in_refund') else -1

        iml = self.env['account.invoice.line'].move_line_get(self.id)
        for il in iml:
            if il['account_analytic_id']:
                if self.type in ('in_invoice', 'in_refund'):
                    ref = self.reference
                else:
                    ref = self.number
                if not self.journal_id.analytic_journal_id:
                    raise Warning(_('No Analytic Journal!'),
                                     _("You have to define an analytic journal on the '%s' journal!") % (
                                     self.journal_id.name,))
                currency = self.currency_id.with_context(date=self.date_invoice)
                il['analytic_lines'] = [(0, 0, {
                    'name': il['name'],
                    'date': self.date_invoice,
                    'account_id': il['account_analytic_id'],
                    'unit_amount': il['quantity'],
                    'amount': currency.compute(il['price'], company_currency) * sign,
                    'product_id': il['product_id'],
                    'product_uom_id': il['uos_id'],
                    'general_account_id': il['account_id'],
                    'journal_id': self.journal_id.analytic_journal_id.id,
                    'ref': ref,
                })]
        return iml
            
    @api.one
    def action_move_create(self):        
        res = super(account_invoice, self).action_move_create()
        
        if self.type == 'out_invoice' and self.move_id and self.move_id.journal_id.discount:
            dt_created = self.move_id.date
            partner = self.partner_id
            m_id = self.move_id.id
            journal = self.journal_id
            period = self.period_id
            base_line = self.move_id.line_id[0]
            central = base_line.centralisation
            blocked = base_line.blocked
            for line in self.invoice_line:
                    
                if 0 < line.discount < 100 and line.product_id.type == 'product':
                    account_discount_id = line.product_id.categ_id.account_discount_id and \
                                          line.product_id.categ_id.account_discount_id.id
                    
                    account_id = line.product_id.property_account_income and line.product_id.property_account_income.id \
                                 or line.product_id.categ_id.property_account_income_categ and \
                                 line.product_id.categ_id.property_account_income_categ.id
                    
                    if not account_discount_id:
                        raise osv.except_osv(_('Error'),_('La Categoria del producto "%s" no tiene una cuenta de '
                                                          'descuentos comerciales configurada') % line.name)

                    damlcd = {
                        'date_created': dt_created,
                        'partner_id': partner.id,
                        'name': 'Descuento Comercial Mayor Valor del Ingreso',
                        'ref2': line.name[:31],
                        'date': dt_created,
                        'credit': (line.price_unit*line.quantity*line.discount)/100,
                        'debit': 0,
                        'account_id': account_id,
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
                    aap = orm.fetchall(self._cr,
                                       "SELECT id from ir_module_module where name = 'account_analytic_project' "
                                       "and state = 'installed'")
                    if aap:
                        damlcd['project_id'] = line.project_id and line.project_id.id or False,
                    damldd = {
                        'date_created': dt_created,
                        'partner_id': partner.id,
                        'name': 'Descuento Comercial'+' '+line.name,
                        'ref2': line.name[:31],
                        'date': dt_created,
                        'credit': 0,
                        'debit': (line.price_unit*line.quantity*line.discount)/100,
                        'account_id': account_discount_id,
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
                    if aap:
                        damldd['project_id'] = line.project_id and line.project_id.id or False,
                    orm.direct_create(self._cr, self._uid, 'account_move_line', [damlcd, damldd], company=True)
                    
                elif line.discount < 0.0 or line.discount >= 100:
                    raise osv.except_osv(_('Error'), _('La linea de factura "%s" tiene un valor de descuento "%s", '
                                                      'el cual es incorrecto.') % (line.name, line.discount))
        elif self.type == 'out_refund' and self.move_id and self.move_id.journal_id.discount:
            dt_created = self.move_id.date
            partner = self.partner_id
            m_id = self.move_id.id
            journal = self.journal_id
            period = self.period_id
            base_line = self.move_id.line_id[0]
            central = base_line.centralisation
            blocked = base_line.blocked
            for line in self.invoice_line:
                if 0 < line.discount < 100 and line.product_id.type == 'product':
                    account_discount_id = line.product_id.categ_id.account_discount_id and \
                                          line.product_id.categ_id.account_discount_id.id
                    
                    account_id = line.product_id.account_return_id and line.product_id.account_return_id.id or \
                                 line.product_id.categ_id.account_return_id and \
                                 line.product_id.categ_id.account_return_id.id
                    
                    if not account_discount_id:
                        raise osv.except_osv(_('Error'), _('La Categoria del producto "%s" no tiene una cuenta de '
                                                          'descuentos comerciales configurada') % line.name)

                    damlcd = {
                        'date_created': dt_created,
                        'partner_id': partner.id,
                        'name': 'Devolucion Descuento Comercial',
                        'ref2': line.name[:31] if line.name else '',
                        'date': dt_created,
                        'credit': 0,
                        'debit': (line.price_unit*line.quantity*line.discount)/100,
                        'account_id': account_id,
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
                    aap = orm.fetchall(self._cr,
                                       "SELECT id from ir_module_module where name = 'account_analytic_project' "
                                       "and state = 'installed'")
                    if aap:
                        damlcd['project_id'] = line.project_id and line.project_id.id or False,

                    damldd = {
                        'date_created': dt_created,
                        'partner_id': partner.id,
                        'name': 'Devolucion Descuento Comercial'+' '+line.name,
                        'ref2': line.name[:31] if line.name else '',
                        'date': dt_created,
                        'credit': (line.price_unit*line.quantity*line.discount)/100,
                        'debit': 0,
                        'account_id': account_discount_id,
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
                    if aap:
                        damldd['project_id'] = line.project_id and line.project_id.id or False,
                    orm.direct_create(self._cr, self._uid, 'account_move_line', [damlcd, damldd], company=True)
                    
                elif line.discount < 0.0 or line.discount >= 100:
                    raise osv.except_osv(_('Error'), _('La linea de factura "%s" tiene un valor de descuento "%s", '
                                                      'el cual es incorrecto.') % (line.name, line.discount))
                            
        if self.company_id.config_analytic_global:
            line1 = []
            line2 = {}
            total_amount = 0.0
            
            for line in self.move_id.line_id:            
                if line.analytic_account_id:
                    tmp = line.analytic_account_id.id
                    if tmp in line2:
                        line2[tmp] = line2[tmp] + line.debit - line.credit
                    else:
                        line2[tmp] = line.debit - line.credit
                elif line.date_maturity:
                    line1.append(line)
                    total_amount += line.debit + line.credit
                    
            if line1 and line2: 
                for l in line1:                    
                    for l2 in line2:
                        if not l.journal_id.analytic_journal_id:
                            raise osv.except_osv(_('Error'), _('Debe asociar un diario analitico a el diario "%s".')
                                                 % l.journal_id.name)
                        if len(line2) == 1:
                            l.write({'analytic_account_id':  l2})
                        amount = abs((l.credit+l.debit)*(line2[l2]/total_amount))
                        lid = self.env['account.analytic.line'].create({
                                        'account_id': l2,
                                        'date':l.date,
                                        'name': l.name,
                                        'ref': l.ref,
                                        'move_id': l.id,
                                        'user_id': self._uid,
                                        'journal_id': l.journal_id.analytic_journal_id.id,
                                        'general_account_id': l.account_id.id,
                                        'amount': amount,
                                            }).id
                        if line2[l2] < 0:
                            self._cr.execute('UPDATE account_analytic_line SET amount = {val} WHERE id = {lid}'
                                             .format(val=amount, lid=lid))
        return res
    
    def inv_line_characteristic_hashcode(self, invoice_line):
        return "%s-%s-%s-%s" % (
            invoice_line['account_id'],
            invoice_line.get('tax_code_id', False) or False,
            invoice_line.get('base_code_id', False) or False,
            invoice_line.get('analytic_account_id', False) or False,
        )
        
    def group_lines(self, iml, line):
        if self.journal_id.group_invoice_lines:
            line2 = {}
            for x, y, l in line:
                tmp = self.inv_line_characteristic_hashcode(l)
                if tmp in line2:
                    am = line2[tmp]['debit'] - line2[tmp]['credit'] + (l['debit'] - l['credit'])
                    line2[tmp]['debit'] = (am > 0) and am or 0.0
                    line2[tmp]['credit'] = (am < 0) and -am or 0.0
                    line2[tmp]['tax_amount'] += l['tax_amount']
                    line2[tmp]['base_amount'] += l['base_amount']
                    line2[tmp]['amount_currency'] += l['amount_currency']
                    line2[tmp]['analytic_lines'] += l['analytic_lines']
                    line2[tmp]['name'] += ', '+l['name']
                else:
                    line2[tmp] = l
            line = []
            for key, val in line2.items():
                line.append((0,0,val))
        return line
    
    @api.model
    def line_get_convert(self, line, part, date):
        res = super(account_invoice, self).line_get_convert(line, part, date)
        res.update({
                'base_code_id': line.get('base_code_id', False),
                'base_amount': line.get('base_amount', False),
                'partner_id': line.get('partner_id_2', False) or part,
                })
        aap = orm.fetchall(self._cr,
                           "SELECT id from ir_module_module where name = 'account_analytic_project' "
                           "and state = 'installed'")
        if aap:
            res.update({
                'project_id': line.get('project_id', False),
            })
        return res
        
    @api.multi
    def action_cancel(self):
        self = self.with_context(factura=True)
        res = super(account_invoice, self).action_cancel()
        return res


class AccountMoveReconcile(models.Model):
    _inherit = "account.move.reconcile"

    name = fields2.Char(string='Name', size=64, required=True, copy=False)

    def unlink(self, cr, uid, ids, context=None):
        for reconcile in self.browse(cr, uid, ids, context=context):
            lines = reconcile.line_id + reconcile.line_partial_ids
            account_move_ids = [aml.move_id.id for aml in lines]
            expense_obj = self.pool.get('hr.expense.expense')
            if account_move_ids:
                expense_ids = expense_obj.search(cr, uid, [('account_move_id', 'in', account_move_ids),
                                                           ('state', '=', 'paid')],
                                                 context=context)
                expense_obj.write(cr, uid, expense_ids, {'state': 'to_refund'}, context=context)
        return super(AccountMoveReconcile, self).unlink(cr, uid, ids, context=context)
    
    
class account_move_line(models.Model):
    _inherit = "account.move.line"

    ref=fields2.Char('Referencia',size=32)
    ref1=fields2.Char('Referencia 1',size=32)
    ref2=fields2.Char('Referencia 2',size=32)
    date_cartera=fields2.Date('Fecha Cartera')
    base_code_id=fields2.Many2one('account.tax.code',string='Codigo Base')
    base_amount=fields2.Float(string='Base', digits=dp.get_precision('Account'))
    currency_conv_id = fields2.Many2one('res.currency', string='Moneda conversión',help='Esta TRM será usada para hacer la conversion del valor en los informes financieros.')
    amount_currency_conv = fields2.Float(string='Monto conversión', digits=dp.get_precision('Account'), default=0, help='Este valor es el correspondiente a la conversión acumulada al movimiento, se usa para saldos iniciales.')

    @api.multi
    def _check_debit_credit_conv(self):
        if self.amount_currency_conv >0 and self.debit<=0:
            return False
        elif self.amount_currency_conv <0 and self.credit<=0:
            return False
        return True

    _constraints = [
        (_check_debit_credit_conv,'''Valor errado, el monto conversión debe ser negativo si el movimiento es crédito. O positivo si es débito ''',['amount_currency_conv']),
    ]

    def write(self, cr, uid, ids, vals, context=None, check=False):
        for move in self.browse(cr, uid, ids, context=context):
            periodo=self.pool.get('account.period').search(cr, uid, [('date_start', '<=', move.date),('date_stop', '>=', move.date),('state', '=', 'done')], context=context)
            if move.date and periodo:
                if not 'ref1' in vals and not 'reconcile_id' in vals and not 'reconcile_ref' in vals and not 'reconcile_partial_id' in vals:
                    raise osv.except_osv(_('Error !'), _('No es posible modificar registros contables en un periodo contable cerrado')) 
        
        return super(account_move_line, self).write(cr, uid, ids, vals, context=context, check=check)
        
    @api.multi
    def unlink(self):
        factura = self._context.get('factura',False)
        for line in self:     
            if line.period_id and line.period_id.state == 'done':
                raise osv.except_osv(_('Error!'), _('No es posible Eliminar registros contables en un periodo ya cerrado %s.') % (line.period_id.name))
            if factura and not line.reconcile_partial_id:
                if line.reconcile_id:
                    self._cr.execute("DELETE FROM account_move_reconcile WHERE id in %s", (line.reconcile_id.id,))
                    self._cr.execute("UPDATE account_move_line SET reconcile_ref='' WHERE reconcile_ref = %s", (line.reconcile_ref,))
                    self._cr.execute("DELETE FROM account_move_line WHERE move_id=%s", (line.move_id.id,))
                else:
                    self._cr.execute("DELETE FROM account_move_line WHERE id=%s", (line.id,))                
                return self._cr.commit()  
        return super(account_move_line, self).unlink()
            
    def reconcile(self, cr, uid, ids, type='auto', writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False, context=None):
        res = super(account_move_line, self).reconcile(cr, uid, ids, type=type, writeoff_acc_id=writeoff_acc_id, writeoff_period_id=writeoff_period_id, writeoff_journal_id=writeoff_journal_id, context=context)
        #when making a full reconciliation of account move lines 'ids', we may need to recompute the state of some hr.expense
        account_move_ids = [aml.move_id.id for aml in self.browse(cr, uid, ids, context=context)]
        account_move_ids = list(set(account_move_ids))
        expense_obj = self.pool.get('hr.expense.expense')
        currency_obj = self.pool.get('res.currency')
        if account_move_ids:
            expense_ids = expense_obj.search(cr, uid, [('account_move_id', 'in', account_move_ids),('state','=','to_refund')], context=context)
            for expense in expense_obj.browse(cr, uid, expense_ids, context=context):
                #making the postulate it has to be set paid, then trying to invalidate it
                new_status_is_paid = True
                for aml in expense.account_move_id.line_id:
                    if aml.account_id.type == 'payable' and not currency_obj.is_zero(cr, uid, expense.company_id.currency_id, aml.amount_residual):
                        new_status_is_paid = False
                if new_status_is_paid:
                    expense_obj.write(cr, uid, [expense.id], {'state': 'paid'}, context=context)
        return res

class hr_expense_line_api(models.Model):
    _inherit = "hr.expense.line"
    
    @api.one
    @api.depends('sin_impuesto','tax_id','tax_line.amount','total_base1','expense_id.currency_id','unit_amount','unit_quantity')
    def _amount_all(self):
        cur_obj = self.pool.get('res.currency')
        cur = self.expense_id.currency_id
        cr = self._cr
        uid = self._uid
        asumidos = 0
        impuestos = 0
        for tax in self.tax_line:
            if tax.asumido:
                asumidos += tax.amount
            else:
                impuestos += tax.amount
        self.total = cur_obj.round(cr, uid, cur, impuestos+self.sin_impuesto+self.total_base1)
        self.total_amount = cur_obj.round(cr, uid, cur, impuestos+self.sin_impuesto+self.total_base1)
        self.impuestos = cur_obj.round(cr, uid, cur, impuestos)
        self.impuestos_asumidos = cur_obj.round(cr, uid, cur, asumidos)
    
    total_amount=fields2.Float(string='Total', compute='_amount_all', digits_compute=dp.get_precision('Product Price'), store=True)
    total=fields2.Float(string='Total', compute='_amount_all', digits_compute=dp.get_precision('Sale Price'), store=True)
    impuestos=fields2.Float(string='Impuestos', compute='_amount_all', digits_compute=dp.get_precision('Sale Price'), store=True)
    impuestos_asumidos=fields2.Float(string='Importe Total', compute='_amount_all', digits_compute=dp.get_precision('Sale Price'), help="Si este valor es diferente a 0 el registro contable NO esta balanceado", store=True)
    
    state = fields2.Selection(string='Proyecto', related='expense_id.state', readonly=True, store=True)
    currency_id = fields2.Many2one('res.currency',string='Moneda', related='expense_id.currency_id', readonly=True, store=True)
    fiscal_id = fields2.Many2one('account.fiscal.position',string='Posicion Fiscal', related='partner_id.property_account_position', readonly=True, store=True)
    
class hr_expense_expense_api(models.Model):
    _inherit = "hr.expense.expense"
    
    @api.one
    @api.depends('line_ids','line_ids.total','line_ids.total_base1')
    def _amount(self):
        total = 0.0
        total_con_impuestos = 0.0
        for line in self.line_ids:
            total += line.total_base1
            total_con_impuestos += line.total
        self.amount = total
        self.amount_total2 = total_con_impuestos
    
    amount=fields2.Float(string='Total Base', compute='_amount', digits_compute=dp.get_precision('Account'), store=True)
    amount_total2=fields2.Float(string='Total con Impuestos', compute='_amount', digits_compute=dp.get_precision('Account'), readonly=True, store=True)
    line_ids=fields2.One2many('hr.expense.line', 'expense_id', string='Expense Lines', copy=True, readonly=True, states={'draft':[('readonly',False)]} )
    
class hr_expense(osv.osv):
    _inherit = "hr.expense.expense"
        
    def verificacionDirector(self, cr, uid, ids, context=None):
        director = False
        for expense in self.browse(cr, uid, ids, context=context):
            if not expense.employee_id.parent_id:
                raise osv.except_osv(_('Error de Configuracion'),_('El Empleado no tiene configurado un Director'))
            if not expense.employee_id.parent_id.user_id:
                raise osv.except_osv(_('Error de Configuracion'),_('El Director no tiene un Usuario asignado'))
            if expense.employee_id.parent_id.user_id.id != uid:
                raise osv.except_osv(_('Error de Permisos'),_('Usted no es el director del empleado'))
            else:
                director = True
        
        return director
        
    def _get_local_currency_total(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for expense in self.browse(cr, uid, ids, context):
            #para compatibilidad con un modulo hijo, hr_payroll_extended
            if expense.multicurrency:
                try:
                    tasa_cambio = expense.advance_id.tasa_cambio
                except: 
                    pass
                if not tasa_cambio:
                    tasa_cambio = expense.tasa_cambio
            else:
                tasa_cambio = 1
                
            res[expense.id] = expense.amount_total2*tasa_cambio
        return res
    
    def get_journal_expenses(self, cr, uid, company, currency, context=None):
        journal_this = False
        for journal in company.journal_expense_ids:
            if company.currency_id.id == currency.id and not journal.currency:
                journal_this = journal.id
                break
            # Se agrega doble validación porque a la función estan llegando tanto ids, como el objeto de currency
            elif journal.currency.id == currency or journal.currency == currency:
                journal_this = journal.id
                break       
        if not journal_this:
            raise osv.except_osv(_('Error de Configuracion'),_("La compania no tiene configurado un diario para legalizaciones con moneda '%s'") % (currency.name,))
        
        return  journal_this
        
    def _get_journal(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for expense in self.browse(cr, uid, ids, context):
            
            if expense.type == 'tarjeta_credito':
                if not expense.employee_id.journal_tarjeta_id:
                    raise osv.except_osv(_('Error de Configuracion'),_('El empleado no tiene configurado una tarjet de credito'))
                res[expense.id] = expense.employee_id.journal_tarjeta_id.id 
            elif expense.type == 'rembolso_caja_menor':
                if not expense.employee_id.journal_id2:
                    raise osv.except_osv(_('Error de Configuracion'),_('El empleado no tiene configurado una caja menor'))
                res[expense.id] = expense.employee_id.journal_id2.id 
            elif expense.state == 'draft':
                res[expense.id] = self.get_journal_expenses(cr, uid, expense.company_id, expense.currency_id, context=context)
            else:
                res[expense.id] = expense.journal_id and expense.journal_id.id or False
            
        return res
    
    def _reconciled(self, cr, uid, ids, name, args, context=None):
        res = {}
        wf_service = openerp.netsvc.LocalService("workflow")
        for exp in self.browse(cr, uid, ids, context=context):
            
            if exp.account_move_line_refund_id and exp.account_move_line_refund_id.reconcile_id:
                res[exp.id] = True
                wf_service.trg_validate(uid, 'hr.expense.expense', exp.id, 'done', cr)
            else:
                res[exp.id] = False
                
        return res
    
    def _get_expense_from_line(self, cr, uid, ids, context=None):
        move = {}
        for line in self.pool.get('account.move.line').browse(cr, uid, ids, context=context):
            if line.reconcile_partial_id:
                for line2 in line.reconcile_partial_id.line_partial_ids:
                    move[line2.move_id.id] = True
            if line.reconcile_id:
                for line2 in line.reconcile_id.line_id:
                    move[line2.move_id.id] = True
                    
        expense_ids = []
        if move:
            expense_ids = self.pool.get('hr.expense.expense').search(cr, uid, [('account_move_id','in',move.keys())], context=context)
        return expense_ids

    def _get_expense_from_reconcile(self, cr, uid, ids, context=None):
        move = {}
        for r in self.pool.get('account.move.reconcile').browse(cr, uid, ids, context=context):
            for line in r.line_partial_ids:
                move[line.move_id.id] = True
            for line in r.line_id:
                move[line.move_id.id] = True
                
        expense_ids = []
        if move:
            expense_ids = self.pool.get('hr.expense.expense').search(cr, uid, [('account_move_id','in',move.keys())], context=context)
        return expense_ids
    
    _columns = {
    
        'parent_id': fields.related('employee_id','parent_id',type="many2one",relation="hr.employee",string="Director", readonly=True ,store=True),
        'move_name': fields.char('Nombre Comprobante', size=64, readonly=True, copy=False),
        'cause': fields.char('Causal',size=60),
        'date': fields.date('Fecha Asiento', select=True, readonly=True, states={'confirm':[('readonly',False)],'accepted':[('readonly',False)]}),
        'create_date': fields.date('Fecha de creacion', readonly=True,  states={'draft':[('readonly',False)]}),
        'line_ids': fields.one2many('hr.expense.line', 'expense_id', 'Expense Lines', readonly=True, states={'draft':[('readonly',False)],'confirm':[('readonly',False)],'accepted':[('readonly',False)]} ),
        'tasa_cambio' : fields.float("Tasa Cambio", digits=(20,12), default=1,states={'done':[('readonly',True)]}),
        'multicurrency': fields.boolean('Multimoneda'),
        'total_local': fields.function(_get_local_currency_total, type="float", string="En Moneda Local", digits_compute=dp.get_precision('Account'), readonly=True, store=True),
        'type':fields.selection([ ('anticipo', 'Anticipo'),
                                  ('tarjeta_credito', 'Tarjeta Credito'),
                                  ('rembolso_gastos', 'Reembolso Gastos'),
                                  ('rembolso_caja_menor', 'Reembolso Caja Menor'),
                                  ], 'Tipo', select=True, readonly=True, track_visibility='always', states={'draft': [('readonly', False),('required', True)]}),
        
        'journal_id': fields.function(_get_journal, type="many2one", relation='account.journal', string="Diario", readonly=True, store=True),
        'account_move_line_refund_id': fields.many2one('account.move.line', 'Linea a reconciliar reembolso', readonly=True),
        'reconciled': fields.function(_reconciled, string='Paid/Reconciled', type='boolean',
            store={
                'account.move.line': (_get_expense_from_line, None, 50),
                'account.move.reconcile': (_get_expense_from_reconcile, None, 50),
            }),
        'state': fields.selection([
            ('draft', 'New'),
            ('cancelled', 'Refused'),
            ('confirm', 'Waiting Approval'),
            ('accepted', 'Approved'),
            ('to_refund', 'Por Reembolsar'),
            ('done', 'DEPRECATED'),
            ('paid', 'Paid'),
            ],
            'Status', readonly=True, track_visibility='onchange',
            help='When the expense request is created the status is \'Draft\'.\n It is confirmed by the user and request is sent to admin, the status is \'Waiting Confirmation\'.\
            \nIf the admin accepts it, the status is \'Accepted\'.\n If a receipt is made for the expense request, the status is \'Done\'.'),
        'employee_id': fields.many2one('hr.employee', "Employee", required=True, track_visibility='always', readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True, track_visibility='always', readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
    }
    
    _defaults={
        'multicurrency': False,
    }
    
    def es_rembolsable(self, cr, uid, ids, context=None):
        for expense in self.browse(cr, uid, ids):
            if expense.type in ['rembolso_gastos','rembolso_caja_menor','tarjeta_credito']:
                return True
            elif expense.type == 'anticipo' and expense.advance_id:
                if expense.amount_total2 > expense.advance_id.remaining:
                    return True
                else:
                    self.write(cr, uid, ids, {'state':'paid'}, context=context)
                    return False
        return False
    
    def wf_to_refund(self, cr, uid, ids, context=None):
        self.action_move_create(cr, uid, ids, context=context)
        self.write(cr, uid, ids , {'state':'to_refund'})
        return True
    
    def onchange_currency_id(self, cr, uid, ids, currency_id, company_id, date, context=None):
        val = {}
        warning = {}
        if currency_id and date and company_id:
            company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
            if company.currency_id.id != currency_id:
                currency_obj = self.pool.get('res.currency.rate')
                #currency_date_id = currency_obj.search(cr, uid, [('name','=',date),('currency_id','=',currency_id)])
                cr.execute("SELECT id FROM res_currency_rate WHERE currency_id = {currency} and name::varchar like "
                           "'{date}%'".format(currency=currency_id, date=date))
                currency_date_id = cr.fetchone()
                if currency_date_id:
                    currency_date_id = currency_obj.browse(cr, uid, currency_date_id[0], context=context)

                if not currency_date_id:
                    warning = {
                        'title': _('Advertencia!'),
                        'message' : _("No existe la tasa de cambio para la fecha '%s' ") % (date,)
                    }
                    rate = 1
                else:
                    rate = currency_date_id.rate_inv
                multi = True
            else:
                rate = 1
                multi = False
                
            val['currency_id'] = currency_id
            val['tasa_cambio'] = rate
            val['multicurrency'] = multi
        return {'value': val,'warning': warning}
    
    def expense_regret(self, cr, uid, expense, context=None):
        moveobj = self.pool.get('account.move')
        reconcile_pool = self.pool.get('account.move.reconcile')
        voucher_line_pool = self.pool.get('account.voucher.line')
        if expense.account_move_id:
            for move_line in expense.account_move_id.line_id:
                lines = move_line.reconcile_id.line_id+move_line.reconcile_partial_id.line_partial_ids
                lines_ids = [x.id for x in lines]
                voucher_lines = voucher_line_pool.search(cr, uid, [('move_line_id','in',lines_ids)], context=context, limit=1)
                if voucher_lines:
                    numero = voucher_line_pool.browse(cr, uid, voucher_lines[0], context=context).voucher_id.number
                    raise osv.except_osv(_('Error'),_('Primero tiene que devolver el pago realizado "%s".')%(numero))
            moveobj.button_cancel(cr, uid, [expense.account_move_id.id], context=context)
            moveobj.unlink(cr, uid, [expense.account_move_id.id], context=context)
        return True
            
    def expense_accept(self, cr, uid, ids, context=None):
        objec = self.pool.get('hr.expense.line')
        for expense in self.browse(cr, uid, ids):
            self.expense_regret(cr, uid, expense, context)
                
            for line in expense.line_ids:
                objec.write(cr, uid, [line.id],{'legalizacion_id1': line.legalizacion_id.id,'total_base1': line.total_base,'impuestos1': line.impuestos,'total1': line.total})
        self.write(cr, uid, ids, {'state': 'accepted', 'date_valid': time.strftime('%Y-%m-%d'), 'user_valid': uid}, context=context)
        return True
    
    @api.multi
    def button_dummy(self):
        for expense in self.line_ids:
            expense.button_reset_taxes()
        return True
    
    def expense_confirm(self, cr, uid, ids, context=None):
        objec = self.pool.get('hr.expense.line')
        for expense in self.browse(cr, uid, ids):
            if expense.type == 'rembolso_caja_menor' and expense.employee_id.journal_id2.petty_cash and expense.saldo_caja < 0:
                raise Warning("No se pueden legalizar gastos superiores al fondo de la caja")
            for line in expense.line_ids:
                objec.write(cr, uid, [line.id],{'legalizacion_id1': line.legalizacion_id.id,'total_base1': line.total_base,'impuestos1': line.impuestos,'total1': line.total})
        return self.write(cr, uid, ids, {'state': 'confirm', 'date_confirm': time.strftime('%Y-%m-%d')}, context=context)
        
    ##Para mover ref1 y ref2 a account_move_line
    def line_get_convert(self, cr, uid, x, part, date, context=None):
        partner_id  = self.pool.get('res.partner')._find_accounting_partner(part).id
        return {
            'date_maturity': x.get('date_maturity', False),
            'partner_id': partner_id,
            'name': x['name'][:64],
            'date': date,
            'debit': x['price']>0 and x['price'],
            'credit': x['price']<0 and -x['price'],
            'account_id': x['account_id'],
            'analytic_lines': x.get('analytic_lines', []),
            'amount_currency': x['price']>0 and abs(x.get('amount_currency', False)) or -abs(x.get('amount_currency', False)),
            'currency_id': x.get('currency_id', False),
            'tax_code_id': x.get('tax_code_id', False),
            'tax_amount': x.get('tax_amount', False),
            'ref': x.get('ref', False),
            'quantity': x.get('quantity',1.00),
            'product_id': x.get('product_id', False),
            'product_uom_id': x.get('uos_id', False),
            'analytic_account_id': x.get('account_analytic_id', False),
            'ref1': x.get('ref1', False),
            'ref2': x.get('ref2', False),
        }
    
    ##Para mover ref1 y ref2  a account_move_line    
    @api.multi
    def _get_analytic_lines(self):
        iml = super(hr_expense, self)._get_analytic_lines()
        for il in iml:
            il.update({'ref1': self['ref1'], 'ref2': self['ref2']})
        return iml
    
        
    def action_move_create(self, cr, uid, ids, context=None):
        self.button_dummy(cr, uid, ids, context=context)
        self.crear_comprobantes(cr, uid, ids)
        return True
        
    # def get_date_for_move_lines(self, cr, uid, line, context=None):
    #     #funcion para sobrescribir
    #     if line.expense_id.company_id.date_expense:
    #         res = line.expense_id.date
    #     else:
    #         res = line.date_value
    #
    #     return res
        
    def crear_comprobantes(self, cr, uid, ids, context=None):
        ait_obj = self.pool.get('account.expense.tax')
        cur_obj = self.pool.get('res.currency')
        period_obj = self.pool.get('account.period')
        payment_term_obj = self.pool.get('account.payment.term')
        journal_obj = self.pool.get('account.journal')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        product_obj = self.pool.get('product.product')
        fiscal_obj = self.pool.get('account.fiscal.position')
        expense_line_obj = self.pool.get('hr.expense.line')
        obj_precision = self.pool.get('decimal.precision')
        prec = obj_precision.precision_get(cr, uid, 'Account')

        if context is None:
            context = {}
        
        for gasto in self.browse(cr, uid, ids, context=context):
            if gasto.account_move_id:
                continue
            period_ids = period_obj.find(cr, uid, gasto.date)
            period_id = period_ids and period_ids[0] or False
            if not period_id:
                    raise osv.except_osv(_('Warning !'), _('No hay un periodo definido para esta fecha'))
            if not gasto.employee_id.partner_id:
                raise osv.except_osv(_('Corrija !'), _('El Tercero del empleado no esta asignado'))
            
            move = {
                'ref': gasto.name,
                'journal_id': gasto.journal_id.id,
                'date': gasto.date,
                'period_id': period_id,
                'company': gasto.company_id.id,
            }
            
            if gasto.move_name:
                move['name'] = gasto.move_name
            
            move_id = move_obj.create(cr, uid, move)
            account_move_line_refund_id = False
            
            if gasto.type == 'rembolso_caja_menor':
                if not gasto.journal_id.rembolsos_account_id:
                    raise osv.except_osv(_('Corrija !'), _('El Diario Seleccionado no tiene cuenta de reembolso'))
                cuenta_rem = gasto.journal_id.rembolsos_account_id.id
            elif gasto.type == 'tarjeta_credito':
                if not gasto.journal_id.credit_card_account_id:
                    raise osv.except_osv(_('Corrija !'), _('El Diario Seleccionado no tiene cuenta de tarjeta de credito'))
                cuenta_rem = gasto.journal_id.credit_card_account_id.id
            
            elif gasto.type == 'rembolso_gastos':
                if not gasto.employee_id.partner_id.property_account_payable:
                    raise osv.except_osv(_('Corrija !'), _('El Tercero del empleado no tiene cuenta de pago asignada'))
                cuenta_rem = gasto.employee_id.partner_id.property_account_payable.id  
            else:
                if not gasto.employee_id.partner_id.property_account_receivable:
                    raise osv.except_osv(_('Corrija !'), _('El Tercero del empleado no tiene cuenta de cobro asignada'))
                cuenta_rem = gasto.employee_id.partner_id.property_account_receivable.id  
            
            #para compatibilidad con un modulo hijo, hr_payroll_extended
            if gasto.multicurrency:
                try:
                    tasa_cambio = gasto.advance_id.tasa_cambio
                except: 
                    pass
                if not tasa_cambio:
                    tasa_cambio = gasto.tasa_cambio
            else:
                tasa_cambio = 1
            
            
            currency =  gasto.company_id.currency_id != gasto.currency_id and gasto.currency_id.id or False
            total = gasto.amount_total2*tasa_cambio
            total_moneda = currency and gasto.amount_total2 or False
            
            line = move_line_obj.create(cr, uid,{
                    'date_created': gasto.date,
                    'partner_id': gasto.employee_id.partner_id.id,
                    'name': gasto.name,
                    'date': gasto.date,
                    'credit': total,
                    'debit': 0,
                    'account_id': cuenta_rem,
                    'analytic_account_id': False,#TODO?
                    'amount_currency': total_moneda*-1,
                    'currency_id': currency,
                    'move_id' : move_id,
                }, context=context)
                
            if gasto.type in ['rembolso_gastos','rembolso_caja_menor']:
                account_move_line_refund_id = line
            
            
            for x in gasto.line_ids:
                date_move = gasto.date#self.get_date_for_move_lines(cr, uid, x, context=context)
                
                if not x.partner_id.property_account_position:
                    raise osv.except_osv(_('Corrija !'), _('El Tercero "%s" no tiene posicion fiscal asignada') % (x.partner_id.name,))
                    
                if x.ref1:
                    ref1 = x.ref1
                else:
                    ref1 = fiscal_obj.get_sequence(cr, uid, x.partner_id.property_account_position, type='purchase', context=context)
                    x.ref1 = ref1
                # VALIDACION MULTICURRENCY EN LINEAS
                if gasto.multicurrency:
                    cr.execute("SELECT rate_inv FROM res_currency_rate WHERE currency_id = {currency} and name::varchar"
                               " like '{date}%'".format(currency=gasto.currency_id.id, date=date_move))
                    tasa_cambio = cr.fetchone()
                    if not tasa_cambio:
                        raise Warning("No se ha definido una tasa de cambio para la fecha {d}".format(d=date_move))
                    else:
                        tasa_cambio = tasa_cambio[0]
                else:
                    tasa_cambio = 1

                total = x.total*tasa_cambio
                total_moneda = currency and x.total or False
                centro_costo = x.analytic_account
                product = x.product_id
                precio = (x.total_base+x.sin_impuesto)*tasa_cambio
                cuenta = product_obj.get_account_from_analytic(cr, uid, product, centro_costo, context)
                cantidad_moneda = currency and x.total_base+x.sin_impuesto or False
                
                
                line = move_line_obj.create(cr, uid,{
                    'date_created': x.date_value,
                    'partner_id': x.partner_id.id,
                    'name': x.name,
                    'date': date_move,
                    'credit': 0,
                    'debit': precio,
                    'account_id': cuenta,
                    'amount_currency': cantidad_moneda,
                    'currency_id': currency,
                    'ref': x.ref or "",
                    'ref1': ref1,
                    'ref2': x.ref2 or "",
                    'product_id': x.product_id.id,
                    'analytic_account_id': centro_costo.id,
                    'move_id' : move_id,
                }, context=context)

                aap = orm.fetchall(cr, "SELECT id from ir_module_module where name = 'account_analytic_project' "
                                   "and state = 'installed'")
                if aap and centro_costo:
                    move_line_obj.write(cr, uid, [line], {'project_id': x.project_id.id})
                
                for tax in x.tax_line:
                    line = move_line_obj.create(cr, uid,{
                        'date_created': x.date_value,
                        'partner_id': x.partner_id.id,
                        'name': tax.name,
                        'date': date_move,
                        'account_id': tax.account_id.id,
                        'ref': x.ref or "",
                        'ref1': ref1,
                        'ref2': x.ref2 or x.id,
                        'analytic_account_id': tax.account_analytic_id.id,
                        'move_id' : move_id,
                        'credit': tax.tax_amount < 0 and abs(tax.tax_amount) or 0,
                        'debit': tax.tax_amount > 0 and abs(tax.tax_amount) or 0,
                        'tax_amount': tax.tax_amount,
                        'tax_code_id': tax.tax_code_id.id,
                        'base_amount': tax.base_amount,
                        'currency_id': currency,
                        'amount_currency': currency and tax.amount or False,
                    }, context=context)
                    if aap and tax.account_analytic_id:
                        move_line_obj.write(cr, uid, [line], {'project_id': x.project_id.id})
                expense_line_obj.write(cr, uid, [x.id], {'ref1': ref1,})

                
            new_move_name = move_obj.browse(cr, uid, move_id, context=context).name
            self.write(cr, uid, [gasto.id], {
                'account_move_id':move_id,
                'account_move_line_refund_id': account_move_line_refund_id,
                'ref1': ref1,
                'move_name': new_move_name,
            })
            move_id = move_obj.browse(cr, uid, move_id, context=context)
            debs = sum([line.debit for line in move_id.line_id])
            credts = sum([line.credit for line in move_id.line_id])
            diff = debs - credts
            if round(diff, prec - 1) != 0.00:
                #if diff != 0:
                # Ajuste por diferencia en cambio
                diff_account = gasto.company_id.income_currency_exchange_account_id.id if diff < 0 else \
                    gasto.company_id.expense_currency_exchange_account_id.id
                line = move_line_obj.create(cr, uid, {
                    'date_created': gasto.date,
                    'partner_id': gasto.employee_id.partner_id.id,
                    'name': gasto.name,
                    'date': gasto.date,
                    'credit': abs(diff) if diff > 0 else 0,
                    'debit': abs(diff) if diff < 0 else 0,
                    'account_id': diff_account,
                    'analytic_account_id': False,  # TODO?
                    'amount_currency': 0,
                    'currency_id': currency,
                    'move_id': move_id.id,
                }, context=context)

            move_obj.post(cr, uid, [move_id.id])
        return True
        
    def write(self, cr, uid, ids, vals, context=None):
        #llama al metodo padre
        if 'employee_id' in vals:
            for req in self.browse(cr, uid, ids, context=context):
                empleado = self.pool.get('hr.employee').browse(cr, uid, vals.get('employee_id'), context=context)
                if empleado.partner_id not in req.message_follower_ids:
                    message_follower_ids = []
                    message_follower_ids += req.message_follower_ids
                    message_follower_ids.append(empleado.partner_id)
                    vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
                    if empleado.parent_id.partner_id not in req.message_follower_ids:
                        message_follower_ids += req.message_follower_ids
                        message_follower_ids.append(empleado.partner_id)
                        vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
        result = super(hr_expense, self).write(cr, uid, ids, vals, context=context)
        
        return result
    
class account_expense_tax(models.Model):
    _inherit = "account.invoice.tax"
    _name = "account.expense.tax"
    
    @api.one
    @api.depends('manual')
    def _state_manual(self):
        if self.manual:
            self.state = 'manual'
        else:
            self.state = 'automatic'
    
    manual = fields2.Boolean(string='Manual', default=True, readonly=True)
    asumido = fields2.Boolean('Asumido', readonly=True)
    invoice_id = fields2.Many2one('hr.expense.line', string='Expense Line',ondelete='cascade', index=True, readonly=True, states={'manual':[('readonly',False)]})
    partner_id_2 = fields2.Many2one('res.partner', string='Tercero', index=True, readonly=True, states={'manual':[('readonly',False)]})
    name = fields2.Char(string='Tax Description', required=True, readonly=True, states={'manual':[('readonly',False)]})
    account_id = fields2.Many2one('account.account', string='Tax Account', required=True, readonly=True, states={'manual':[('readonly',False)]}, domain=[('type', 'not in', ['view', 'income', 'closed'])])
    account_analytic_id = fields2.Many2one('account.analytic.account', string='Analytic account', readonly=True, states={'manual':[('readonly',False)]})
    ##
    base = fields2.Float(string='Base', digits=dp.get_precision('Account'), readonly=True, states={'manual':[('readonly',False)]})
    amount = fields2.Float(string='Amount', digits=dp.get_precision('Account'), readonly=True, states={'manual':[('readonly',False)]})
    sequence = fields2.Integer(string='Sequence', help="Gives the sequence order when displaying a list of invoice tax.", readonly=True, states={'manual':[('readonly',False)]})
    base_code_id = fields2.Many2one('account.tax.code', string='Base Code',help="The account basis of the tax declaration.", readonly=True, states={'manual':[('readonly',False)]})
    base_amount = fields2.Float(string='Base Code Amount', digits=dp.get_precision('Account'),default=0.0, readonly=True, states={'manual':[('readonly',False)]})
    tax_code_id = fields2.Many2one('account.tax.code', string='Tax Code',help="The tax basis of the tax declaration.", readonly=True, states={'manual':[('readonly',False)]})
    tax_amount = fields2.Float(string='Tax Code Amount', digits=dp.get_precision('Account'),default=0.0, readonly=True, states={'manual':[('readonly',False)]})
    state = fields2.Char(string='State', compute='_state_manual', store=True)
    
    
    def compute(self, cr, uid, invoice_id, context=None):
        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        ana_obj = self.pool.get('account.analytic.account')
        product_obj = self.pool.get('product.product')
        inv = line = self.pool.get('hr.expense.line').browse(cr, uid, invoice_id, context=context)
        cur = inv.expense_id.currency_id
        company_currency = inv.expense_id.company_id.currency_id.id
        
        #asumidos se repite el proceso con line.tax_out_id
        for tax in tax_obj.compute_all(cr, uid, line.tax_out_id, line.unit_amount, line.unit_quantity, line.product_id, inv.partner_id)['taxes']:
            val={}
            valid = True
            val['invoice_id'] = inv.id
            val['name'] = tax['name']
            val['amount'] = tax['amount']
            val['manual'] = False
            val['asumido'] = True
            
            val['sequence'] = tax['sequence']
            val['base'] = cur_obj.round(cr, uid, cur, tax['price_unit'] * line['unit_quantity'])
            val['base_code_id'] = tax['base_code_id']
            val['tax_code_id'] = tax['tax_code_id']
            val['base_amount'] = cur_obj.compute_tasa(cr, uid, cur.id, company_currency, val['base'] * tax['base_sign'], rate=inv.expense_id.tasa_cambio, context=context, round=False)
            val['tax_amount'] = cur_obj.compute_tasa(cr, uid, cur.id, company_currency, val['amount'] * tax['tax_sign'], rate=inv.expense_id.tasa_cambio, context=context, round=False)
            
            if line.analytic_account and line.analytic_account.costo_gasto == 'gasto' and tax['property_account_expense']:
                val['account_id'] = tax['property_account_expense']
                if tax['expense_efect']:
                    val['account_analytic_id'] = line.analytic_account.id
            elif line.analytic_account and line.analytic_account.costo_gasto == 'costo' and tax['property_account_cost']:
                val['account_id'] = tax['property_account_cost']
                if tax['cost_efect']:
                    val['account_analytic_id'] = line.analytic_account.id
            elif line.analytic_account and line.analytic_account.costo_gasto == 'gasto_venta' and tax['property_account_gastos_venta']:
                val['account_id'] = tax['property_account_gastos_venta']
                if tax['cost_gasto_venta']:
                    val['account_analytic_id'] = line.analytic_account.id
            elif tax['account_collected_id']:
                val['account_id'] = tax['account_collected_id']
                val['account_analytic_id'] = tax['account_analytic_collected_id']
            elif not tax['account_collected_id'] and not tax['property_account_cost'] and not tax['property_account_expense']:
                val['account_analytic_id'] = tax['account_analytic_collected_id']
                if tax['account_analytic_collected_id']:
                    val['account_id'] = product_obj.get_account_from_analytic(cr, uid, line.product_id, tax['account_analytic_collected_id'], context)
                else:
                    val['account_id'] = product_obj.get_account_from_analytic(cr, uid, line.product_id, line.analytic_account, context)
            else:
                valid = False
            
            if valid:
                key = (val['tax_code_id'], val['base_code_id'], val['account_id'], val['account_analytic_id'], val['asumido'])
                if not key in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']
        
        for tax in tax_obj.compute_all(cr, uid, line.tax_id, line.unit_amount, line.unit_quantity, line.product_id, inv.partner_id)['taxes']:
            # mapeo secundario por base en lineas de gastos
            fposition_pool = self.pool.get('account.fiscal.position')
            fposition = inv.partner_id.property_account_position or False
            if inv.expense_id.company_id.city_cc:
                ttm = {tax_obj.browse(cr, uid, tax['id'], context): tax['price_unit'] * line.unit_quantity}
                bandera = fposition_pool.map_base(cr, uid, fposition, ttm, context)
                if not bandera:
                    continue
            val = {}
            valid = True
            val['invoice_id'] = inv.id
            val['name'] = tax['name']
            val['amount'] = tax['amount']
            val['manual'] = False
            val['asumido'] = False
            
            val['sequence'] = tax['sequence']
            val['base'] = cur_obj.round(cr, uid, cur, tax['price_unit'] * line['unit_quantity'])
            val['base_code_id'] = tax['base_code_id']
            val['tax_code_id'] = tax['tax_code_id']
            val['base_amount'] = cur_obj.compute_tasa(cr, uid, cur.id, company_currency, val['base'] * tax['base_sign'], rate=inv.expense_id.tasa_cambio, context=context, round=False)
            val['tax_amount'] = cur_obj.compute_tasa(cr, uid, cur.id, company_currency, val['amount'] * tax['tax_sign'], rate=inv.expense_id.tasa_cambio, context=context, round=False)
            val['account_analytic_id'] = False
            if line.analytic_account and line.analytic_account.costo_gasto == 'gasto' and tax['property_account_expense']:
                val['account_id'] = tax['property_account_expense']
                if tax['expense_efect']:
                    val['account_analytic_id'] = line.analytic_account.id
            elif line.analytic_account and line.analytic_account.costo_gasto == 'costo' and tax['property_account_cost']:
                val['account_id'] = tax['property_account_cost']
                if tax['cost_efect']:
                    val['account_analytic_id'] = line.analytic_account.id
            elif line.analytic_account and line.analytic_account.costo_gasto == 'gasto_venta' and tax['property_account_gastos_venta']:
                val['account_id'] = tax['property_account_gastos_venta']
                if tax['cost_gasto_venta']:
                    val['account_analytic_id'] = line.analytic_account.id
            elif tax['account_collected_id']:
                val['account_id'] = tax['account_collected_id']
                val['account_analytic_id'] = tax['account_analytic_collected_id']
            elif not tax['account_collected_id'] and not tax['property_account_cost'] and not tax['property_account_expense']:
                val['account_analytic_id'] = tax['account_analytic_collected_id']
                if tax['account_analytic_collected_id']:
                    val['account_id'] = product_obj.get_account_from_analytic(cr, uid, line.product_id, tax['account_analytic_collected_id'], context)
                else:
                    val['account_id'] = product_obj.get_account_from_analytic(cr, uid, line.product_id, line.analytic_account, context)
            else:
                valid = False
            
            if valid:
                key = (val['tax_code_id'], val['base_code_id'], val['account_id'], val['account_analytic_id'], val['asumido'])
                if not key in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']

        for t in tax_grouped.values():
            t['base'] = cur_obj.round(cr, uid, cur, t['base'])
            t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
            t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
            t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])
        return tax_grouped
        
class hr_expense_line(osv.osv):
    _inherit = "hr.expense.line"
    
    _columns = {
        'partner_id': fields.many2one('res.partner','Tercero'),
        'analytic_account': fields.many2one('account.analytic.account','Centro Costo'),
        'total_base': fields.float('Total Base', digits_compute= dp.get_precision('Sale Price')),
        'tax_id': fields.many2many('account.tax', 'gasto_tax', 'line_id', 'tax_id', 'Impuestos'),
        'sin_impuesto': fields.float('Rubro Adicional',help="No aplica impuestos", digits_compute= dp.get_precision('Sale Price')),
        'tax_out_id': fields.many2many('account.tax', 'gasto_asumido_tax', 'line_id', 'tax_id', 'Impuestos Asumidos'),
        'legalizacion_id': fields.many2one('account.account','Legalizacion de Gastos'),
        'legalizacion_id1': fields.many2one('account.account','Legalizacion de Gastos', readonly=True),
        'fiscal_id1': fields.many2one('account.fiscal.position','Posicion Fiscal', readonly=True),
        'total_base1': fields.float('Total Base', digits_compute= dp.get_precision('Sale Price'), readonly=True),
        'total_segunda_base': fields.float('Total Base 2', digits_compute= dp.get_precision('Sale Price'), readonly=True),
        'ref1': fields.char('Referencia 1',size=32, readonly=True),
        'ref2': fields.char('Referencia 2',size=32),
        'nota': fields.text('Nota'),
        'tax_line': fields.one2many('account.expense.tax', 'invoice_id', 'Calculo Impuestos'),
        'city_id': fields.many2one('res.city','Ciudad'),
    }
    
    def button_reset_taxes(self, cr, uid, ids, context=None):
        cr.execute("SELECT company_id from res_users where id = %s" % uid)
        company_id = self.pool.get('res.company').browse(cr, uid, cr.fetchone()[0], context=context)
        fposition_pool = self.pool.get('account.fiscal.position')
        ait_obj = self.pool.get('account.expense.tax')
        for expense_line in self.browse(cr, uid, ids, context=context):
            taxes_to_map = {}
            subtotal = expense_line.total_base*expense_line.expense_id.tasa_cambio
            partner = expense_line.partner_id
            if not expense_line.city_id:
                # Politica de ciudad en centro de costo
                if company_id.city_cc:
                    expense_line.city_id = expense_line.analytic_account.city_id
                else:
                    expense_line.city_id = partner.city_id
            for tax in expense_line.tax_id:
                taxes_to_map[tax] = subtotal
            if company_id.ciiu_ica:
                ctx = context.copy()
                if partner.ciiu_id:
                    ctx['ciiu'] = partner.ciiu_id
                else:
                    raise Warning("El tercero %s no tiene configurado una actividad economica principal" % (partner.name))
                result_taxes = fposition_pool.map_tax2(cr, uid, partner.property_account_position, taxes_to_map, partner, expense_line.city_id, partner.ciiu_id, context=ctx)
            else:
                if not partner.property_account_position:
                    raise osv.except_osv(_('Error !'), _("No esta configurada la posicion Fiscal del tercero %s, "
                                                         "por favor validar" % partner.name))
                result_taxes = fposition_pool.map_tax2(cr, uid, partner.property_account_position, taxes_to_map,
                                                       False, expense_line.city_id, False, context=context)
            self.write(cr, uid, [expense_line.id], {'tax_id': [(6, 0, result_taxes)],'legalizacion_id1': expense_line.legalizacion_id.id,'total_base1': expense_line.total_base,'impuestos1': expense_line.impuestos,'total1': expense_line.total}, context=context)
            cr.execute("DELETE FROM account_expense_tax WHERE invoice_id=%s AND manual is False", (expense_line.id,))
            ctx=context.copy()
            if partner.lang:
                ctx.update({'lang': partner.lang})
            for taxe in ait_obj.compute(cr, uid, expense_line.id, context=ctx).values():
                ait_obj.create(cr, uid, taxe, context=ctx)
        return True
    
    def button_dummy(self, cr, uid, ids, context=None):
        return True
    
    def onchange_partner_id(self, cr, uid, ids, partner_id, context=None):
        res = {}
        partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)
        res['fiscal_id'] = partner.property_account_position.id
        res['fiscal_id1'] = partner.property_account_position.id
        nuevo = self.browse(cr, uid, ids, context=context)
        for line in nuevo:
            self.write(cr, uid, [line.id],{'legalizacion_id1': line.legalizacion_id.id,'total_base1': line.total_base})
        return {'value': res}
        
    def onchange_product_id(self, cr, uid, ids, product_id, uom_id, employee_id, unit_quantity, sin_impuesto, context=None):
        res = {}
        if product_id:
            
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            tax_obj = self.pool.get('account.tax')
            fpos = False
            amount_unit = product.price_get('standard_price')[product.id]
            res['unit_amount'] = amount_unit
            res['uom_id'] = product.uom_id.id
            res['tax_id'] = self.pool.get('account.fiscal.position').map_tax(cr, uid, fpos, product.supplier_taxes_id)
            taxes = tax_obj.compute_all(cr, uid, product.supplier_taxes_id, amount_unit, unit_quantity)
            res['total_base'] = taxes['total']
            res['total_base1'] = taxes['total']
            res['total_segunda_base'] = res['total_base'] + sin_impuesto
            nuevo = self.browse(cr, uid, ids, context=context)
            for line in nuevo:
                self.write(cr, uid, [line.id],{'legalizacion_id1': line.legalizacion_id.id,'total_base1': line.total_base})
        return {'value': res}
        
    def onchange_amount(self, cr, uid, ids, product_id, uom_id, employee_id, unit_quantity, unit_amount, tax_id, sin_impuesto, context=None):
        res = {}
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            tax_obj = self.pool.get('account.tax')
            fpos = False
            impuestos = tax_obj.browse(cr, uid, tax_id[0][2], context=context)
            taxes = tax_obj.compute_all(cr, uid, impuestos, unit_amount, unit_quantity)
            res['total_base'] = taxes['total']
            res['total_base1'] = taxes['total']
            res['total_segunda_base'] = res['total_base'] + sin_impuesto
            nuevo = self.browse(cr, uid, ids, context=context)
            for line in nuevo:
                self.write(cr, uid, [line.id],{'legalizacion_id1': line.legalizacion_id.id,'total_base1': line.total_base})
        return {'value': res}

class journal_resposable(osv.osv):
    _inherit = 'account.journal'
    
    _columns = {
        'rembolsos_account_id': fields.many2one('account.account','Rembolso de Caja', help="Cuenta utilizada para reembolsos de gastos"),
        'credit_card_account_id': fields.many2one('account.account','Tarjeta Credito', help="Cuenta utilizada para tarjetas de credito"),
        'recaudo': fields.boolean('Recaudo(si),Pago(no)', help="seleccionar si la cuenta es de recaudo, si no se selecciona, la cuenta sera de pago"),
        'resolucion': fields.text('Resolucion de Facturacion'),
        'datos_empresa': fields.text('Datos de empresa'),
        'equivalente': fields.boolean('Equivalente', help="Diario Documentos Equivalentes"),
        'discount': fields.boolean('Descuento Comercial', help="Aplica Descuento Comercial"),        
    }    

class product_template(osv.osv):
    _inherit = 'product.template'
    _columns = {
        'member_price': fields.float('Member Price', digits_compute= dp.get_precision('Sale Price')),
    }

class hr_employee(osv.osv):
    _inherit = 'hr.employee'
    
    def _check_recursion(self, cr, uid, ids, context=None):
        return True
    
    _columns = {
        'responsable_caja': fields.boolean('Responsable de Caja'),
        'journal_id2': fields.many2one('account.journal','Diario Caja Menor'),
        'journal_tarjeta_id': fields.many2one('account.journal','Diario Tarjeta Credito'),
    }   
    
    _constraints = [
        (_check_recursion, 'Error! You cannot create recursive hierarchy of Employee(s).', ['parent_id']),
    ]
    
class account_invoice_line(models.Model):
    _inherit = 'account.invoice.line'
    
    partner_id_2=fields2.Many2one('res.partner', string='Tercero')
    
    # NO PERMITE AGREGAR LINEAS A UNA FACTURA CON UN ALBARAN YA RECEPCIONADO
    @api.model
    def create(self, vals):
        res = super(account_invoice_line, self).create(vals)
        if res.product_id and  res.product_id.type == 'product' and res.invoice_id and res.invoice_id.stock_picking_id:
            move = self.env['stock.move'].search([('product_id', '=', res.product_id.id),('picking_id', '=', res.invoice_id.stock_picking_id.id)], limit=1)
            if not move and not self._context.get('group',False):
                raise osv.except_osv(_('Error !'), _('No es posible crear una linea de una factura con un albaran ya recepcionado'))
        return res
    
    # NO PERMITE MODIFICAR VALORES DE UNA FACTURA CON UN ALBARAN YA RECEPCIONADO
    @api.multi
    def write(self, vals):
        for line in self:
            if line.invoice_id.type != "out_refund" and line.invoice_id.stock_picking_id and line.product_id and line.product_id.type == 'product' and not self._uid == 1:
                if vals.get('quantity', False):
                    raise osv.except_osv(_('Error !'), _('No es posible modificar una cantidad de una factura ya recepcionada'))
                if vals.get('price_unit', False):
                    raise osv.except_osv(_('Error !'), _('No es posible modificar el precio de una factura ya recepcionada'))
                if vals.get('discount', False):
                    raise osv.except_osv(_('Error !'), _('No es posible modificar el descuento de una factura ya recepcionada'))
        res = super(account_invoice_line, self).write(vals)
        return res
        
    @api.model
    def move_line_get(self, invoice_id):
        inv = self.env['account.invoice'].browse(invoice_id)
        tax_obj = self.env['account.tax']
        currency = inv.currency_id.with_context(date=inv.date_invoice)
        company_currency = inv.company_id.currency_id
        res = []
        for line in inv.invoice_line:                
            mres = self.move_line_get_item(line)
            mres['invl_id'] = line.id
            aap = orm.fetchall(self._cr, "SELECT id from ir_module_module where name = 'account_analytic_project' "
                                         "and state = 'installed'")
            if aap:
                if line.project_id:
                    mres['project_id'] = line.project_id.id
            res.append(mres)
            if line.product_id.type == 'product':
                continue
            tax_code_found = False
            taxes = line.invoice_line_tax_id.compute_all(
                (line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)),
                line.quantity, line.product_id, inv.partner_id)['taxes']
            for tax in taxes:
                impuesto = tax_obj.browse(tax['id'])
                if impuesto.mayor_valor:
                    if inv.type in ('out_invoice', 'in_invoice'):
                        tax_code_id = tax['tax_code_id']
                        base_code_id = tax['base_code_id']
                    else:
                        tax_code_id = tax['ref_tax_code_id']
                        base_code_id = tax['ref_base_code_id']
                    
                    res[-1]['tax_code_id'] = tax_code_id
                    res[-1]['base_code_id'] = base_code_id
                    
        return res
    
    @api.multi
    def analytic_account_change(self, product, account_analytic_id, fposition_id, type, company_id=None):
        values = {}
        if not (product and account_analytic_id and fposition_id and type):
            return {'value': values}
        self = self.with_context(company_id=company_id, force_company=company_id)
        cr = self._cr
        uid = self._uid
        context = self._context
        product_obj = self.pool.get('product.product')
        fpos = self.env['account.fiscal.position'].browse(fposition_id)
        product = self.env['product.product'].browse(product)
        company_id = company_id if company_id is not None else context.get('company_id', False)
        account = False
        
        if type in ('out_invoice','out_refund'):
            account = product.property_account_income.id
            if not account:
                account = product.categ_id.property_account_income_categ.id
        else:
            account = product.property_account_expense.id
            if not account:
                account = product.categ_id.property_account_expense_categ.id
        
        if not account_analytic_id or type in ('out_invoice','out_refund'):
            account = fpos.map_account(account)
        else:
            centro_costo = self.env['account.analytic.account'].browse(account_analytic_id)
            if centro_costo:
                account = product_obj.get_account_from_analytic(cr, uid, product, centro_costo, context=context)
            else:
                account = fpos.map_account(account)
        
        values['account_id'] = account
        
        return {'value': values}
        
    @api.multi
    def product_id_change(self, product, uom_id, qty=0, name='', type='out_invoice', partner_id=False,
                          fposition_id=False, price_unit=False, currency_id=False, company_id=None,
                          account_analytic_id=False):
        res = super(account_invoice_line, self).product_id_change(product, uom_id, qty=qty, name=name, type=type,
            partner_id=partner_id, fposition_id=fposition_id, price_unit=price_unit, currency_id=currency_id,
            company_id=company_id, account_analytic_id=account_analytic_id)
        if product and account_analytic_id and fposition_id and type:
            res['value']['account_id'] = self.analytic_account_change(product, account_analytic_id, fposition_id, type, company_id=company_id)['value']['account_id']
            
        return res
    
    @api.model
    def move_line_get_item(self, line):
        res = super(account_invoice_line, self).move_line_get_item(line)
        res.update({'partner_id_2': line.partner_id_2.id,})
        return res

class account_parent(models.Model):
    _inherit = 'account.account'

    @api.one
    @api.depends('parent_id')
    def _get_parent_zero(self):
        account=False
        if self.parent_id:
            account=self.parent_id
            while (account.parent_id):                    
                account = account.parent_id
            account=account.id
        self.parent_zero = account
                    
    
    parent_zero = fields2.Many2one('account.account',string='Parent Zero', compute='_get_parent_zero', store=True)

# Se debe ejecutar en las bases de datos el siguiente comando ---->  UPDATE ir_act_window SET "limit"=20;
class ir_actions_act_window(models.Model):
    _inherit = 'ir.actions.act_window'
    
    limit = fields2.Integer(string='Limit', help='Default limit for the list view', default=20)
    
    
#
