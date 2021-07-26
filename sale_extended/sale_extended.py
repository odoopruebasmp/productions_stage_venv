# -*- coding: utf-8 -*-
from openerp.osv import osv, fields
import openerp.addons.decimal_precision as dp
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp import netsvc
from openerp import models, api, _
from openerp import fields as fields2
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp import SUPERUSER_ID
import time
import openerp
import locale

class res_users(models.Model):
    _inherit = "res.users"
    
    sale_teams = fields2.Many2many('crm.case.section', 'sale_member_rel', 'member_id', 'section_id', 'Equipos de Venta')

class crm_case_section(models.Model):
    _inherit = "crm.case.section"
    
    analytic_account_id = fields2.Many2one('account.analytic.account', 'Centro de Costo')

class sale_order_line(models.Model):
    _inherit = "sale.order.line"
    
    project_id = fields2.Many2one('project.project', 'Proyecto')
    

class sale_order_api(models.Model):
    _inherit = "sale.order"
    
    @api.onchange('section_id')
    def section_on_change(self):
        self.project_id = self.section_id.analytic_account_id.id
        
    @api.onchange('user_id')
    def user_on_change(self):
        sale_team = False
        if len(self.user_id.sale_teams) == 1:
            sale_team = self.user_id.sale_teams[0].id
        self.section_id = sale_team
    
    contact_name = fields2.Char('Contacto')
    garantia = fields2.Char('Garantia')
    time_entrega = fields2.Char('Tiempo Entrega')
    
class res_partner(osv.osv):
    _inherit = "res.partner"
    
    _columns = {
        'block': fields.boolean('Credito Bloqueado', help="Bloquado por limite de credito", readonly=True),
        'check_due': fields.boolean('Bloqueo por facturas vencidas', help="Aplicar un bloquado en el cliente cuando este tenga facturas vencidas y se trate de hacer un venta"),
    }

class account_invoice(osv.osv):
    _inherit = 'account.invoice'
    
    _columns = {
        'partner_shipping_id': fields.many2one('res.partner', 'Direccion de Entrega', readonly=True, states={'draft': [('readonly', False)]}),
        'sale_order_id': fields.many2one('sale.order', 'Orden Facturacion', readonly=True, states={'draft': [('readonly', False)]}),
    }
    
    def onchange_partner_id(self, cr, uid, ids, type, partner_id, date_invoice=False, payment_term=False,
                            partner_bank_id=False, company_id=False, context=None):
        res = {}
        val = super(account_invoice, self).onchange_partner_id(cr, uid, ids, type, partner_id,
                date_invoice=date_invoice, payment_term=payment_term, partner_bank_id=partner_bank_id,
                company_id=company_id, context=context)['value']
        addr = self.pool.get('res.partner').address_get(cr, uid, [partner_id], ['delivery', 'invoice', 'contact'])
        val['partner_shipping_id'] = addr['delivery']
        salesman = self.pool.get('res.partner').browse(cr, uid, [partner_id]).user_id
        if salesman:
            val['user_id'] = salesman.id
        res['value'] = val
        tp_add = context.get('journal_type', False) == 'sale_add'
        if (type == 'out_refund' or tp_add) and partner_id:
            inv_st = ('state', '=', 'open')
            if tp_add:
                inv_st = ('state', 'in', ['open', 'paid'])
            partner = self.pool.get('res.partner').browse(cr, uid, [partner_id])
            inv_ids = self.search(cr, uid, [('type', '=', 'out_invoice'), inv_st, ('partner_id', '=', partner.id),
                                            ('journal_id.type', '=', 'sale')])
            part_chs = partner.child_ids.filtered(lambda p: p.type == 'invoice')
            if part_chs:
                inv_ids += self.search(cr, uid, [('type', '=', 'out_invoice'), inv_st, ('journal_id.type', '=', 'sale'),
                                                 ('partner_id', 'in', part_chs.ids)])
            inv_tp = 'invoice_out_refund_id' if type == 'out_refund' else 'invoice_out_add_id'
            res['domain'] = {inv_tp: [('id', 'in', inv_ids)]}
        return res
    
class sale_order(osv.osv):
    _inherit = "sale.order"
    
    def action_cancel_draft(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state':'draft'})
        wf_service = openerp.netsvc.LocalService("workflow")
        for sale_id in ids:
            wf_service.trg_delete(uid, 'sale.order', sale_id, cr)
            wf_service.trg_create(uid, 'sale.order', sale_id, cr)
            for linea in self.browse(cr, uid, sale_id, context=None).order_line:
                self.pool.get('sale.order.line').write(cr, uid, linea.id, {'state':'draft'})
        return True
    
    def action_cancel(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
                     
        res = super(sale_order,self).action_cancel(cr, uid, ids, context=context)
        for sale_id in self.browse(cr, uid, ids, context=context):
            if self.pool.get('stock.picking').search(cr, SUPERUSER_ID, [('state','=','done'),('origin','=',sale_id.name)], context=context):
                raise osv.except_osv(_('ERROR!'), _('No puede cancelar un pedido que tiene un picking ya transferido!'))            
            for line in sale_id.order_line:
                cr.execute(''' DELETE FROM procurement_order WHERE sale_line_id = %s''',(line.id,))   
        return res
    
    def check_limit(self, cr, uid, ids, context={}):
        for order_dataset in self.browse(cr, uid, ids, context=context):
            partner = order_dataset.partner_id
            partner_obj = self.pool.get('res.partner')
            ir_model_data = self.pool.get('ir.model.data')
            group_object = self.pool.get('res.groups')
            mail_object = self.pool.get('email.template')
            user_data = self.pool.get('res.users')
            moveline_obj = self.pool.get('account.move.line')
            ir_model_data = self.pool.get('ir.model.data')
            group_id = ir_model_data.get_object_reference(cr, uid, 'sale_extended', 'group_modify_over_credit_limit')[1]
            user_obj = self.pool.get('res.users').browse(cr, uid, uid, context=context)
            if group_id in [x.id for x in user_obj.groups_id]:
                restringido = False
            else:
                restringido = True
                
            if partner.check_due:
                today = datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
                move_ids = moveline_obj.search(cr, SUPERUSER_ID, [('partner_id','=',partner.id),('reconcile_id', '=', False),('account_id.active','=', True), ('account_id.type', '=', 'receivable'), ('debit', '>', 0.0), ('state', '!=', 'draft'), ('date_maturity','<',today)], context=context)
                if move_ids:
                    for move_line in moveline_obj.browse(cr, SUPERUSER_ID, move_ids, context=context):
                        move_id = move_line.move_id
                        if move_id.state == 'posted':
                            partner_obj.write(cr, uid, [partner.id], {'block':True}, context=context)
                            if restringido == True:
                                raise osv.except_osv(_('Bloqueado!'), _('El cliente tiene un pago vencido y esta bloqueado, comprobante "%s"!')%(move_id.name))
            elif partner:
                partner_obj.write(cr, uid, [partner.id], {'block':False}, context=context)
            if partner.credit_limit:
                if (partner.credit + order_dataset.amount_total) > partner.credit_limit:
                    #mail_template = ir_model_data.get_object(cr, uid, 'sale_extended', 'email_template_sale_order_over_credit')
                    #mail_id = mail_template.id
                    #partner_obj.write(cr, uid, [partner.id], {'block':True}, context=context)
                    #mail_object.send_mail(cr, uid, mail_id, order_dataset.id,force_send=False, context=context)
                    #cr.commit()
                    amount_total=locale.format('%.2f', order_dataset.amount_total, True)
                    credit=locale.format('%.2f', partner.credit, True)
                    credit_limit=locale.format('%.2f', partner.credit_limit, True)
                    if restringido == True:
                        raise osv.except_osv(_('Bloqueado!'), _('El cliente sobrepaso el limite de credito $ %s, y se encuentra bloqueado por un saldo de $ %s y la presente venta $ %s') % (credit_limit, credit, amount_total))
        return True
    
    def button_confirm(self, cr, uid, ids, context=None):
        self.button_dummy(cr, uid, ids, context=context)
        res = super(sale_order,self).button_confirm(cr, uid, ids, context=context)
        return res
    
    def _prepare_invoice(self, cr, uid, order, lines, context=None):
        invoice_vals = super(sale_order,self)._prepare_invoice(cr, uid, order, lines, context=context)
        invoice_vals['partner_shipping_id'] = order.partner_shipping_id.id
        invoice_vals['sale_order_id'] = order.id
        return invoice_vals
    

class product_product(osv.osv):
    _inherit = 'product.product'
    
    def need_procurement(self, cr, uid, ids, context=None):
        return True
