
from openerp.osv import fields, osv
from openerp.tools.translate import _
from datetime import datetime
from openerp import SUPERUSER_ID
from openerp.addons.avancys_orm import avancys_orm

class stock_inventory(osv.osv):
    _inherit = "stock.inventory"
    _order = 'date desc'
    
    _columns = {
        'account_move_id': fields.many2one('account.move', 'Comprobante Contable', readonly=True),
        'journal_id': fields.many2one('account.journal', 'Diario', domain=[('type', '=', 'general'), ('stock_journal', '=', True)], states={'done':[('readonly',True)]}),
        'partner_id2': fields.many2one('res.partner', 'Tercero', states={'done':[('readonly',True)]}),
        'account_transaction_in_id': fields.many2one('account.account', string="Cuenta de Perdidas", help="Esta cuenta se utiliza para registrar las perdidas de inventario", states={'done':[('readonly',True)]}),
        'account_transaction_out_id': fields.many2one('account.account', string="Cuenta de Ganancias", help="Esta cuenta se utiliza para registrar las ganancias de inventario", states={'done':[('readonly',True)]}),
        'account_analytic_id': fields.many2one('account.analytic.account', string="Cuenta Analitica", help="Centro de costos al cual asociar los movimientos contables", states={'done':[('readonly',True)]}),
    }
    
    def unlink(self, cr, uid, ids, context=None):
        for inventory in self.browse(cr, uid, ids, context=context):
            if inventory.state != "draft":
                raise osv.except_osv(_('ERROR !'), _("El sistema no permite realizar este tipo de operacion, el ajuste de inventario %s, ya tiene afectacion."  % inventory.name))
        return super(stock_inventory, self).unlink(cr, uid, ids, context=context)

    def action_cancel_inventory(self, cr, uid, ids, context=None):
        res = super(stock_inventory, self).action_cancel_inventory(cr, uid, ids, context=context)
        account_move_obj = self.pool.get('account.move')
        for inv in self.browse(cr, uid, ids, context=context):
            if inv.account_move_id:
                account_move_obj.button_cancel(cr, uid, [inv.account_move_id.id], context=context)
                account_move_obj.unlink(cr, uid, [inv.account_move_id.id], context=context)
        return res

    def action_done(self, cr, uid, ids, context=None):
        res = super(stock_inventory, self).action_done(cr, uid, ids, context=context)
        
        if context is None:
            context = {}
        product_context = dict(context, compute_child=False)
        account_move_obj = self.pool.get('account.move')
        today_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        period_id = account_move_obj._get_period(cr, uid, context)
        move_line_list = []
        seq_obj = self.pool.get('ir.sequence')
        for inv in self.browse(cr, uid, ids, context=context):
            if inv.account_transaction_in_id and inv.account_transaction_out_id:
                seq = seq_obj.search(cr, SUPERUSER_ID, [('id','=',inv.journal_id.sequence_id.id)])
                partner_id = inv.partner_id2
                if not partner_id:
                    raise osv.except_osv(_('Configuration !'), _("Para realizar el ajuste contable debe configurar un tercero en el inventario %s."  % inv.name))
                move_vals = {
                    'period_id': period_id,
                    'journal_id': inv.journal_id.id,
                    'date': today_date,
                    'ref': inv.name,
                    'name': seq_obj.next_by_id(cr, SUPERUSER_ID, seq[0], context=context),
                    'state': 'posted',
                    'company_id': inv.company_id.id
                }
                account_move = avancys_orm.direct_create(cr, uid, 'account_move', [move_vals])
                for line_move in inv.line_ids:
                    product_context.update(uom=line_move.product_uom_id.id, to_date=inv.date, date=inv.date, prodlot_id=line_move.prod_lot_id.id)
                    change =  line_move.product_qty - line_move.theoretical_qty
                    
                    if change > 0:#hay ganancias
                        context.update({'location_w_id':line_move.location_id.id})
                        account_id = line_move.product_id.property_stock_account_input or line_move.product_id.categ_id.property_stock_account_input_categ
                        if not account_id:
                            raise osv.except_osv(_('Configuration !'), _("Stock input account not define in %s product."  % line_move.product_id.default_code))
                        debit_account = account_id
                        credit_account = inv.account_transaction_out_id
                        
                        cost = line_move.product_id.standard_price
                        
                        if cost <= 0.0 and not line_move.product_id.costo_zero:
                            raise osv.except_osv(_('Error!'), _("El producto %s, tiene un costo igual o menor a cero, por favor validar o consultar con el area encargada"  % line_move.product_id.default_code))
                        
                        amount = abs(cost * change)
                        cr.execute(''' update stock_move set cost=%s, costo_promedio=%s, total_cost=%s*product_qty where inventory_id=%s and product_id=%s''', (cost, cost, cost, inv.id, line_move.product_id.id))
                        if amount != 0:
                            acc_typ = credit_account.user_type.report_type
                            analytic_account = inv.account_analytic_id.id if acc_typ in ['income', 'expense'] else False
                            cr_move_line = {
                                'name': line_move.product_id.name,
                                'date': today_date,
                                'period_id': period_id,
                                'debit': 0,
                                'credit': amount,
                                'account_id': credit_account.id,
                                'partner_id': partner_id.id,
                                'move_id': account_move[0][0],
                                'journal_id': inv.journal_id.id,
                                'company_id': inv.company_id.id,
                                'state': 'valid',
                                'analytic_account_id': analytic_account
                            }
                            move_line_list.append(cr_move_line)
                            acc_typ = debit_account.user_type.report_type
                            analytic_account = inv.account_analytic_id.id if acc_typ in ['income', 'expense'] else False
                            dr_move_line = {
                                'name': line_move.product_id.name,
                                'date': today_date,
                                'period_id': period_id,
                                'debit': amount,
                                'credit': 0,
                                'account_id': debit_account.id,
                                'partner_id': partner_id.id,
                                'move_id': account_move[0][0],
                                'journal_id': inv.journal_id.id,
                                'company_id': inv.company_id.id,
                                'state': 'valid',
                                'analytic_account_id': analytic_account
                            }
                            move_line_list.append(dr_move_line)
                    else:
                        account_id = line_move.product_id.property_stock_account_input or line_move.product_id.categ_id.property_stock_account_input_categ
                        if not account_id:
                            raise osv.except_osv(_('Configuration !'), _("Stock input account not define in %s product."  % line_move.product_id.default_code))
                        debit_account = inv.account_transaction_in_id
                        credit_account = account_id
                        cost = line_move.product_id.standard_price
                        if cost <= 0.0 and not line_move.product_id.costo_zero:
                            raise osv.except_osv(_('Error!'), _("El producto %s, tiene un costo igual o menor a cero, por favor validar o consultar con el area encargada"  % line_move.product_id.default_code))
                        cr.execute(''' update stock_move set cost=%s, costo_promedio=%s, total_cost=%s*product_qty where inventory_id=%s and product_id=%s''', (cost, cost, cost, inv.id, line_move.product_id.id))
                        amount = abs(cost * change)
                        if amount != 0:
                            acc_typ = credit_account.user_type.report_type
                            analytic_account = inv.account_analytic_id.id if acc_typ in ['income', 'expense'] else False
                            cr_move_line = {
                                'name': line_move.product_id.name,
                                'date': today_date,
                                'period_id': period_id,
                                'debit': 0,
                                'credit': amount,
                                'account_id': credit_account.id,
                                'partner_id': partner_id.id,
                                'move_id': account_move[0][0],
                                'journal_id': inv.journal_id.id,
                                'company_id': inv.company_id.id,
                                'state': 'valid',
                                'analytic_account_id': analytic_account
                            }
                            move_line_list.append(cr_move_line)
                            acc_typ = debit_account.user_type.report_type
                            analytic_account = inv.account_analytic_id.id if acc_typ in ['income', 'expense'] else False
                            dr_move_line = {
                                'name': line_move.product_id.name,
                                'date': today_date,
                                'period_id': period_id,
                                'debit': amount,
                                'credit': 0,
                                'account_id': debit_account.id,
                                'partner_id': partner_id.id,
                                'move_id': account_move[0][0],
                                'journal_id': inv.journal_id.id,
                                'company_id': inv.company_id.id,
                                'state': 'valid',
                                'analytic_account_id': analytic_account
                            }
                            move_line_list.append(dr_move_line)

                avancys_orm.direct_create(cr, uid, 'account_move_line', move_line_list)
                self.write(cr, uid, inv.id, {'account_move_id': account_move[0][0]}, context=context)
            else:
                raise osv.except_osv(_('Error!'), _("Para validar el ajuste de inventario, debe parametrizar las cuentas de perdida y ganancia"))
        
        return res

#
