# Embedded file name: /home/mazuniga/avancys_pymes/account_asset_extended/account_asset_extended.py
# -*- coding: utf-8 -*-
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from datetime import datetime
import time
from dateutil.relativedelta import relativedelta
from openerp.tools.float_utils import float_round
from openerp.addons.edi import EDIMixin
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.osv import osv, fields
from openerp import api, models
from openerp import fields as fields2
from openerp import netsvc
import openerp.netsvc

class account_asset_asset_close_wizard(models.TransientModel):
    _name = 'account.asset.asset.close.wizard'
    
    type = fields2.Selection([('perdida', 'Perdida'), ('venta', 'Venta'), ('depreciacion', 'Depreciacion Total')], string='Tipo de Operacion', required=True)
    asset_id = fields2.Many2one('account.asset.asset', string='Activo')
    invoice_id = fields2.Many2one('account.invoice', string='Factura')
    cliente_id = fields2.Many2one('res.partner', string='Cliente')
    partner_id = fields2.Many2one('res.partner', string='Tercero')
    date_maturity = fields2.Date(string='Fecha de Vencimiento')

    @api.one
    def do_close(self):
        orm2sql = self.pool.get('avancys.orm2sql')
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']
        period_obj = self.env['account.period']
        asset_id = self.asset_id
        date = datetime.now().date()
        reference = asset_id.code
        partner_id = asset_id.company_id.partner_id.id
        period_id = period_obj.search([('date_start', '<=', date), ('date_stop', '>=', date), ('state', '=', 'draft')], limit=1)
        if not period_id:
            raise osv.except_osv(_('Error !'), _("No existe un periodo abierto para la fecha '%s'") % date)
        if self.type == 'depreciacion':
            if asset_id.move_eliminated_id:
                raise osv.except_osv(_('Error !'), _("La baja del activo '%s' para el plan fiscal ya fue realizada, no es posible procesar este requerimiento") % asset_id.name)
            if asset_id.depreciation_line_ids.filtered(lambda x: x.move_check == False):
                raise osv.except_osv(_('Error !'), _("No es posible realizar la baja de un activo por metodo 'Deterioro Total' si aun tiene deterioros por contabilizar."))
            account_activacion = asset_id.category_id.account_asset_id and asset_id.category_id.account_asset_id.id or False
            if not account_activacion:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta fiscal 'Cuenta de Activacion' en la categoria '%s'") % asset_id.category_id.name)
            account_depreciation_id = asset_id.category_id.account_depreciation_id and asset_id.category_id.account_depreciation_id.id or False
            if not account_depreciation_id:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta fiscal 'Cuenta de Depreciacion' de la categoria '%s'") % asset_id.category_id.name)
            journal_id = asset_id.category_id.journal_eliminated_id and asset_id.category_id.journal_eliminated_id.id or False
            if not journal_id:
                raise osv.except_osv(_('Error !'), _("Debe configurar el diario fiscal 'Diario Baja Activo Deterioro Total' en la categoria '%s'") % asset_id.category_id.name)
            name = self.pool.get('ir.sequence').next_by_id(self._cr, self._uid, asset_id.category_id.journal_eliminated_id.sequence_id.id, context=self._context)
            name_move = 'BAJA ACTIVO POR DETERIORO TOTAL FISCAL' + asset_id.name
            account_analytic_id = asset_id.centrocosto_id and asset_id.centrocosto_id.id or False
            move_vals = [{'name': name,
                'date': str(date),
                'ref': name_move,
                'period_id': period_id.id,
                'journal_id': journal_id,
                'state': 'posted'}]
            print '11111111'
            print date
            move_id = orm2sql.sqlcreate(self._uid, self._cr, 'account_move', move_vals, company=True, commit=False)[0][0]
            print '222222222'
            line = [{'name': name_move,
                'ref': name,
                'ref1': 'Valor Activo',
                'move_id': move_id,
                'account_id': account_activacion,
                'debit': 0.0,
                'credit': asset_id.purchase_value + asset_id.tax_value,
                'period_id': period_id.id,
                'journal_id': journal_id,
                'partner_id': partner_id,
                'analytic_account_id': account_analytic_id,
                'date': str(date),
                'asset_id': asset_id.id,
                'state': 'valid'}]
            orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
            line = [{'name': name_move,
                'ref': name,
                'ref1': 'Valor Depreciacion',
                'move_id': move_id,
                'account_id': account_depreciation_id,
                'debit': asset_id.purchase_value + asset_id.tax_value - asset_id.salvage_value,
                'credit': 0.0,
                'period_id': period_id.id,
                'journal_id': journal_id,
                'partner_id': partner_id,
                'analytic_account_id': account_analytic_id,
                'date': str(date),
                'asset_id': asset_id.id,
                'state': 'valid'}]
            orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
            if asset_id.salvage_value:
                line = [{'name': name_move,
                    'ref': name,
                    'ref1': 'Valor Salvamento',
                    'move_id': move_id,
                    'account_id': account_activacion,
                    'debit': asset_id.salvage_value,
                    'credit': 0.0,
                    'period_id': period_id.id,
                    'journal_id': journal_id,
                    'partner_id': partner_id,
                    'analytic_account_id': account_analytic_id,
                    'date': str(date),
                    'asset_id': asset_id.id,
                    'state': 'valid'}]
                orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
            asset_id.move_eliminated_id=move_id
        elif self.type == 'perdida':
            if asset_id.move_eliminated_id:
                raise osv.except_osv(_('Error !'), _("La baja del activo '%s' para el plan fiscal ya fue realizada, no es posible procesar este requerimiento") % asset_id.name)
            account_activacion = asset_id.category_id.account_asset_id and asset_id.category_id.account_asset_id.id or False
            if not account_activacion:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de activacion en la categoria '%s'") % asset_id.category_id.name)
            account_depreciation_id = asset_id.category_id.account_depreciation_id and asset_id.category_id.account_depreciation_id.id or False
            if not account_depreciation_id:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de depreciacion contable de la categoria '%s'") % asset_id.category_id.name)
            journal_id = asset_id.category_id.journal_eliminated_id1 and asset_id.category_id.journal_eliminated_id1.id or False
            if not journal_id:
                raise osv.except_osv(_('Error !'), _("Debe configurar el 'Diario Baja Activo por Perdida' en la categoria '%s'") % asset_id.category_id.name)
            name = self.pool.get('ir.sequence').next_by_id(self._cr, self._uid, asset_id.category_id.journal_eliminated_id1.sequence_id.id, context=self._context)
            name_move = 'BAJA ACTIVO POR PERDIDA ' + asset_id.name
            account_analytic_id = asset_id.centrocosto_id and asset_id.centrocosto_id.id or False
            date_maturity = False
            partner_id2 = partner_id
            if self.partner_id:
                partner_id2 = self.partner_id.id
                account_id = self.partner_id.property_account_receivable and self.partner_id.property_account_receivable.id or False
                if not account_id:
                    raise osv.except_osv(_('Error !'), _("Debe configurar la cuenta por cobrar en el tercero '%s'") % self.partner_id.name)
                date_maturity = str(self.date_maturity)
            else:
                account_id = asset_id.category_id.property_account_eliminated_id and asset_id.category_id.property_account_eliminated_id.id or False
                if not account_id:
                    raise osv.except_osv(_('Error !'), _("Debe configurar 'Cuenta de Gasto Baja Activo por Perdida' en la categoria '%s'") % asset_id.category_id.name)
            move_vals = [{'name': name,
              'date': str(date),
              'ref': name_move,
              'period_id': period_id.id,
              'journal_id': journal_id,
              'state': 'posted'}]
            move_id = orm2sql.sqlcreate(self._uid, self._cr, 'account_move', move_vals, company=True, commit=False)[0][0]
            
            amount_depreciacion = 0.0
            for l in asset_id.depreciation_line_ids:
                if l.move_id:
                    amount_depreciacion += l.amount

            if amount_depreciacion:
                line = [{'name': name_move,
                  'ref': name,
                  'ref1': 'Valor Depreciacion',
                  'move_id': move_id,
                  'account_id': account_depreciation_id,
                  'debit': amount_depreciacion,
                  'credit': 0.0,
                  'period_id': period_id.id,
                  'journal_id': journal_id,
                  'partner_id': partner_id,
                  'analytic_account_id': account_analytic_id,
                  'date': str(date),
                  'asset_id': asset_id.id,
                  'state': 'valid'}]
                orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
                
            line = [{'name': name_move,
              'ref': name,
              'ref1': 'Valor Activo',
              'move_id': move_id,
              'account_id': account_activacion,
              'debit': 0.0,
              'credit': asset_id.purchase_value + asset_id.tax_value,
              'period_id': period_id.id,
              'journal_id': journal_id,
              'partner_id': partner_id,
              'analytic_account_id': account_analytic_id,
              'date': str(date),
              'asset_id': asset_id.id,
              'state': 'valid'}]
            orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
            
                
            if asset_id.purchase_value + asset_id.tax_value - amount_depreciacion > 0.0:
                line = [{'name': name_move,
                  'ref': name,
                  'ref1': 'Valor por Perdida del Activo',
                  'move_id': move_id,
                  'account_id': account_id,
                  'debit': asset_id.purchase_value + asset_id.tax_value - amount_depreciacion,
                  'credit': 0.0,
                  'period_id': period_id.id,
                  'journal_id': journal_id,
                  'partner_id': partner_id2,
                  'analytic_account_id': account_analytic_id,
                  'date': str(date),
                  'asset_id': asset_id.id,
                  'state': 'valid',
                  'date_maturity': date_maturity}]
                orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
            asset_id.move_eliminated_id=move_id
        else:
            
            
            if asset_id.move_eliminated_id:
                raise osv.except_osv(_('Error !'), _("La baja del activo '%s' para el plan fiscal ya fue realizada, no es posible procesar este requerimiento") % asset_id.name)
            product_id = self.asset_id.product_id
            
            
            account_activacion = asset_id.category_id.account_asset_id and asset_id.category_id.account_asset_id.id or False
            if not account_activacion:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de activacion en la categoria '%s'") % asset_id.category_id.name)
            
            account_depreciation_id = asset_id.category_id.account_depreciation_id and asset_id.category_id.account_depreciation_id.id or False
            if not account_depreciation_id:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de depreciacion contable de la categoria '%s'") % asset_id.category_id.name)
            
            journal_id = asset_id.category_id.journal_eliminated_id2 and asset_id.category_id.journal_eliminated_id2.id or False
            if not journal_id:
                raise osv.except_osv(_('Error !'), _("Debe configurar el 'Diario Baja Activo por Venta' en la categoria '%s'") % asset_id.category_id.name)
            
            name = self.pool.get('ir.sequence').next_by_id(self._cr, self._uid, asset_id.category_id.journal_eliminated_id2.sequence_id.id, context=self._context)
            name_move = 'BAJA ACTIVO POR VENTA ' + asset_id.name
            account_analytic_id = asset_id.centrocosto_id and asset_id.centrocosto_id.id or False
            
            partner_id = self.cliente_id.id
            
            move_vals = [{'name': name,
              'date': str(date),
              'ref': name_move,
              'period_id': period_id.id,
              'journal_id': journal_id,
              'state': 'posted'}]
            move_id = orm2sql.sqlcreate(self._uid, self._cr, 'account_move', move_vals, company=True, commit=False)[0][0]
            
            
            amount_depreciacion = 0.0
            for l in asset_id.depreciation_line_ids:
                if l.move_id:
                    amount_depreciacion += l.amount

            if amount_depreciacion:
                line = [{'name': name_move,
                  'ref': name,
                  'ref1': 'Valor Depreciacion',
                  'move_id': move_id,
                  'account_id': account_depreciation_id,
                  'debit': amount_depreciacion,
                  'credit': 0.0,
                  'period_id': period_id.id,
                  'journal_id': journal_id,
                  'partner_id': partner_id,
                  'analytic_account_id': account_analytic_id,
                  'date': str(date),
                  'asset_id': asset_id.id,
                  'state': 'valid'}]
                orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
                
                
            line = [{'name': name_move,
              'ref': name,
              'ref1': 'Valor Activo',
              'move_id': move_id,
              'account_id': account_activacion,
              'debit': 0.0,
              'credit': asset_id.purchase_value_niif,
              'period_id': period_id.id,
              'journal_id': journal_id,
              'partner_id': partner_id,
              'analytic_account_id': account_analytic_id,
              'date': str(date),
              'asset_id': asset_id.id,
              'state': 'valid'}]
            orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
            
            invoice_line = self.env['account.invoice.line'].search([('invoice_id', '=', self.invoice_id.id), ('product_id', '=', asset_id.product_id.id)], limit=1)
            if not invoice_line:
                name_raise= str(self.invoice_id.origin or self.id) +' -> '+ str(self.invoice_id.date_invoice or self.invoice_id.create_date)+' -> $'+ str(self.invoice_id.amount_total)
                raise osv.except_osv(_('Error !'), _("El sistema no logra encontrar una linea en la factura '%s' para el producto del activo en cuention "  % name_raise))
            
            amount=amount_depreciacion - asset_id.purchase_value     
            
            asset_id.amount_venta_fiscal=invoice_line.price_subtotal + amount_depreciacion - asset_id.purchase_value     
            
            account_idx=asset_id.category_id.account_asset_ganancia_id and asset_id.category_id.account_asset_ganancia_id.id or False
            if not account_idx:
                raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta de 'Cuenta de Utilidad Venta Activo' en la categoria del activo %s "  % asset_id.category_id.name))
            
            linex = [{
                'name': name_move,                    
                'ref': self.invoice_id.origin or str(self.invoice_id.id),
                'ref1': 'Gasto por venta Activo',
                'move_id': move_id,
                'account_id': account_idx,
                'debit': abs(amount),
                'credit': 0.0,                        
                'period_id': period_id.id,
                'journal_id': journal_id,
                'partner_id': partner_id,
                'analytic_account_id': account_analytic_id,
                'date': str(date),
                'asset_id': asset_id.id,
                'state': 'valid',
            }]                                    
            orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', linex, company=True, commit=False)            
            asset_id.move_eliminated_id=move_id
            asset_id.invoice_baja_id=self.invoice_id.id
        asset_id.type_baja=self.type
        return True


class account_asset_asset_api(models.Model):
    _inherit = 'account.asset.asset'

    @api.depends('depreciation_line_ids', 'depreciation_line_ids.move_check')
    @api.one
    def _get_local_depreciation(self):
        if self.ids:
            self._cr.execute("SELECT SUM(amount) from account_asset_depreciation_line "
                             "where asset_id = {aid} and move_check = 't'".format(aid=self.id))
            self.local_depreciation = self._cr.fetchall()[0][0]

            self._cr.execute(" SELECT id from ir_module_module where name='niif_asset' and state='installed'")
            if self._cr.fetchall():
                self._cr.execute("SELECT SUM(amount) from account_asset_depreciation_line "
                             "where asset_id2 = {aid} and move_check = 't'".format(aid=self.id))
                self.niif_depreciation = self._cr.fetchall()[0][0]

    type_baja = fields2.Selection([('perdida', 'Perdida'), ('venta', 'Venta'), ('depreciacion', 'Depreciacion Total')], string='Tipo de Operacion', readonly=True)
    move_eliminated_id = fields2.Many2one('account.move', string='Baja Inventario Fiscal', readonly=True)
    move_eliminated_niif_id = fields2.Many2one('account.move', string='Baja Inventario Contable', readonly=True)
    invoice_baja_id = fields2.Many2one('account.invoice', string='Factura Baja de Activo')
    amount_venta_fiscal = fields2.Float(string='Utilidad/Perdida Fiscal')
    amount_venta_contable = fields2.Float(string='Utilidad/Perdida Contable')
    local_depreciation = fields2.Float('Depreciacion Local Acum', digits_compute=dp.get_precision('Account'),
                                       compute=_get_local_depreciation, store=True)
    niif_depreciation = fields2.Float('Depreciacion NIIF Acum', digits_compute=dp.get_precision('Account'),
                                      compute=_get_local_depreciation, store=True)

    @api.multi
    def set_eliminated(self):
        return {'name': 'Cierre de Activo',
         'view_type': 'form',
         'view_mode': 'form',
         'view_id': False,
         'res_model': 'account.asset.asset.close.wizard',
         'type': 'ir.actions.act_window',
         'target': 'new',
         'context': "{'default_asset_id': active_id}"}

    @api.multi
    def update_depreciations(self):
        self._cr.execute("SELECT SUM(amount) from account_asset_depreciation_line "
                         "where asset_id = {aid} and move_check = 't'".format(aid=self.id))
        self.local_depreciation = self._cr.fetchall()[0][0]

        self._cr.execute("SELECT SUM(amount) from account_asset_depreciation_line "
                         "where asset_id2 = {aid} and move_check = 't'".format(aid=self.id))
        self.niif_depreciation = self._cr.fetchall()[0][0]


class account_invoice(models.Model):
    _inherit = 'account.invoice'
    asset_id = fields2.Many2one('account.asset.asset', string='Activo Para Dar de Baja', readonly=True)

    @api.multi
    def action_cancel(self):
        moves = self.env['account.asset.asset']
        for inv in self:
            for line in inv.invoice_line:
                if line.account_asset_id:
                    if len(line.account_asset_id.account_move_line_ids) > 0:
                        raise except_orm(_('Error!'), _('Esta tratando de cancelar una factura con una linea relacionada al activo "%s" el cual ya se empezo a depreciar.') % line.account_asset_id.name)
                    else:
                        line.account_asset_id.unlink()

        res = super(account_invoice, self).action_cancel()
        return res


class account_asset_asset(osv.osv):
    _inherit = 'account.asset.asset'

    def _amount_all(self, cr, uid, ids, field_name, arg, context = None):
        res = dict()
        tax_pool = self.pool.get('account.tax')
        for asset in self.browse(cr, uid, ids, context):
            res[asset.id] = {'value_to_depreciate': 0.0,
             'asset_value': 0.0,
             'value_residual': 0.0,
             'tax_value': 0.0}
            paid = 0
            taxes = 0
            for tax in tax_pool.compute_all(cr, uid, asset.tax_ids, asset.purchase_value, 1)['taxes']:
                tax_id = tax_pool.browse(cr, uid, tax['id'], context)
                if tax_id.en_activo:
                    taxes += tax['amount']

            for dep in asset.depreciation_line_ids:
                if dep.move_check:
                    paid += dep.amount

            res[asset.id]['tax_value'] = taxes
            res[asset.id]['value_to_depreciate'] = asset.purchase_value + taxes - asset.salvage_value
            res[asset.id]['asset_value'] = asset.purchase_value + taxes
            res[asset.id]['value_residual'] = asset.purchase_value + taxes - paid

        return res

    def _check_salvage_value(self, cr, uid, ids, vals, context=None):
        if 'method' in vals and vals['method'] == 'reduction' or \
                'nif_method' in vals and vals['nif_method'] == 'reduction':
            if 'salvage_value' in vals or 'salvage_value_niif' in vals:
                if vals.get('salvage_value') <= 0 and vals.get('salvage_value_niif') <= 0:
                    raise osv.except_osv(_('Error !'), _('El valor de Salvaguarda para el Método de Cálculo por '
                                                         'Reducción de Saldos debe ser mayor a 0, por favor validar.'))
            else:
                asset = self.browse(cr, uid, ids)
                if asset.salvage_value <= 0 or asset.salvage_value_niif <= 0:
                    raise osv.except_osv(_('Error !'), _('El valor de Salvaguarda para el Método de Cálculo por '
                                                         'Reducción de Saldos debe ser mayor a 0, por favor validar.'))

    _columns = {'centrocosto_id': fields.many2one('account.analytic.account', 'Centro de Costo', required=True, readonly=True, states={'draft': [('readonly', False)]}),
     'tax_ids': fields.many2many('account.tax', 'asset_tax_rel', 'asset_id', 'tax_id', 'Impuestos', readonly=True, states={'draft': [('readonly', False)]}),
     'period_prorate': fields.integer('Desfase Periodo Inicial', help='El desfaz de periodo es un numero que se le sumara a la fecha de compra del activo, el resultado indica la fecha inicial de depreciacion del activo', readonly=True, states={'draft': [('readonly', False)]}),
     'historico': fields.float('Historico', digits_compute=dp.get_precision('Product Price'), readonly=True, states={'draft': [('readonly', False)]}),
     'depresiacion_historica': fields.float('Depresiacion Acumulada', digits_compute=dp.get_precision('Product Price'), readonly=True, states={'draft': [('readonly', False)]}),
     'valor_compra': fields.float('Valor Historico de compra', digits_compute=dp.get_precision('Product Price'), readonly=True, states={'draft': [('readonly', False)]}),
     'tasa_moneda': fields.float('Tasa Moneda Extranjera', digits_compute=dp.get_precision('Exchange Precision'), readonly=True, states={'draft': [('readonly', False)]}),
     'fecha_compra': fields.date('Fecha de Compra Historica', readonly=True, states={'draft': [('readonly', False)]}),
     'multicurrency': fields.boolean('multicurrency'),
     'value_to_depreciate': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'), string='Valor Inicial Depreciar', multi='compute',store= True),
     'asset_value': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'), string='Valor Inicial Libros', multi='compute',store= True),
     'value_residual': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'), string='Valor Libro Fiscal', multi='compute',store= True),
     'tax_value': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'), string='Valor Impuestos', multi='compute')}

    _defaults = {'period_prorate': 1}

    def write(self, cr, uid, ids, vals, context=None):
        self._check_salvage_value(cr, uid, ids, vals, context=context)
        return super(account_asset_asset, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        res = super(account_asset_asset, self).create(cr, uid, vals, context=context)
        self._check_salvage_value(cr, uid, res, vals, context=context)
        return res

    def set_to_close(self, cr, uid, ids, context = None):
        asset = self.browse(cr, uid, ids, context=context)
        if not asset.move_eliminated_id:
            raise osv.except_osv(_('Error !'), _('No es posible realizar el cierre del activo, debe primero realizar la baja en el Plan Contable'))
        if not asset.move_eliminated_niif_id:
            raise osv.except_osv(_('Error !'), _('No es posible realizar el cierre del activo, debe primero realizar la baja en el Plan Fiscal'))
        return self.write(cr, uid, ids, {'state': 'close'}, context=context)

    def _check_prorata(self, cr, uid, ids, context = None):
        return True

    _constraints = [(_check_prorata, 'Prorata temporis can be applied only for time method "number of depreciations".', ['prorata'])]

    def _compute_board_undone_dotation_nb(self, cr, uid, asset, depreciation_date, total_days, context = None):
        undone_dotation_number = asset.method_number
        if asset.method_time == 'end':
            end_date = datetime.strptime(asset.method_end, DEFAULT_SERVER_DATE_FORMAT)
            undone_dotation_number = 0
            while depreciation_date <= end_date:
                depreciation_date = datetime(depreciation_date.year, depreciation_date.month, depreciation_date.day) + relativedelta(months=+asset.method_period)
                undone_dotation_number += 1

        return undone_dotation_number

    def onchange_method_time(self, cr, uid, ids, method_time = 'number', context = None):
        res = {'value': {}}
        return res

    def onchange_category_id(self, cr, uid, ids, category_id, context = None):
        res = super(account_asset_asset, self).onchange_category_id(cr, uid, ids, category_id, context=context)
        asset_categ_obj = self.pool.get('account.asset.category')
        if category_id:
            category_obj = asset_categ_obj.browse(cr, uid, category_id, context=context)
            res['value'].update({'period_prorate': category_obj.period_prorate})
        return res

    def get_depreciation_account(self, cr, uid, asset, analytic_account, tax = False, context = None):
        res = False
        if tax:
            if analytic_account.costo_gasto == 'gasto':
                res = asset.category_id.property_account_tax_expense_depreciation_id and asset.category_id.property_account_tax_expense_depreciation_id.id
            elif analytic_account.costo_gasto == 'costo':
                res = asset.category_id.property_account_tax_cost_depreciation_id and asset.category_id.property_account_tax_cost_depreciation_id.id
            elif analytic_account.costo_gasto == 'gasto_venta':
                res = asset.category_id.property_account_gasto_de_venta_depreciation_id and asset.category_id.property_account_gasto_de_venta_depreciation_id.id
        elif analytic_account.costo_gasto == 'gasto':
            res = asset.category_id.account_expense_depreciation_id and asset.category_id.account_expense_depreciation_id.id
        elif analytic_account.costo_gasto == 'gasto_venta':
            res = asset.category_id.property_account_gasto_de_venta_depreciation_id and asset.category_id.property_account_gasto_de_venta_depreciation_id.id
        elif analytic_account.costo_gasto == 'costo':
            res = asset.category_id.property_account_cost_depreciation_id and asset.category_id.property_account_cost_depreciation_id.id
        if not res:
            raise osv.except_osv(_('Error!'), _('La categoria de activo "%s" no tiene bien definidas las cuentas de costo/gasto/gasto de venta.') % asset.category_id.name)
        return res

    def onchange_currency_id(self, cr, uid, ids, purchase_date, currency_id, company_id, context = None):
        if not currency_id or not company_id:
            return {}
        warning = {}
        val = {}
        company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
        currency = self.pool.get('res.currency').browse(cr, uid, currency_id, context=context)
        if company.currency_id.id != currency_id:
            val['multicurrency'] = True
            val['tasa_cambio_pactada'] = self.pool.get('res.currency').tasa_dia(cr, uid, purchase_date, company, currency, context=context)
            if val['tasa_cambio_pactada'] == 0:
                warning = {'title': _('Advertencia!'),
                 'message': _('La tasa de cambio para esta fecha no esta especificada! : ')}
        else:
            val['multicurrency'] = False
        return {'value': val,
         'warning': warning}

    def _compute_board_amount(self, cr, uid, asset, i, residual_amount, amount_to_depr, undone_dotation_number,
                              posted_depreciation_line_ids, total_days, depreciation_date, context=None):
        amount = 0
        if i == undone_dotation_number:
            amount = residual_amount
        elif asset.method == 'linear':
            amount = amount_to_depr / (undone_dotation_number - len(posted_depreciation_line_ids))
        elif asset.method == 'reduction':
            reduc_factor = 1 - pow(asset.salvage_value/asset.purchase_value, 1.0/asset.method_number)
            amount = (asset.salvage_value + residual_amount) * reduc_factor
            if asset.prorata:
                days = total_days - float(depreciation_date.strftime('%j'))
                if i == 1:
                    amount = amount / total_days * days
                elif i == undone_dotation_number:
                    amount = amount / total_days * (total_days - days)
        return amount

    def compute_depreciation_board(self, cr, uid, ids, context = None):
        depreciation_lin_obj = self.pool.get('account.asset.depreciation.line')
        currency_obj = self.pool.get('res.currency')
        orm2sql = self.pool.get('avancys.orm2sql')
        i, l = 0, len(self.browse(cr, uid, ids, context=context))
        start = datetime.now()
        orm2sql.printProgressBar(i, l, start=start)
        for asset in self.browse(cr, uid, ids, context=context):
            if asset.value_residual == 0.0:
                continue
            posted_depreciation_line_ids = depreciation_lin_obj.search(cr, uid, [('asset_id', '=', asset.id), ('move_check', '=', True)], order='depreciation_date desc')
            old_depreciation_line_ids = depreciation_lin_obj.search(cr, uid, [('asset_id', '=', asset.id), ('move_id', '=', False)])
            if old_depreciation_line_ids:
                depreciation_lin_obj.unlink(cr, uid, old_depreciation_line_ids, context=context)
            amount_to_depr = residual_amount = asset.value_residual - asset.salvage_value
            if asset.prorata:
                if len(posted_depreciation_line_ids) > 0:
                    last_depreciation_date = datetime.strptime(depreciation_lin_obj.browse(cr, uid, posted_depreciation_line_ids[0], context=context).depreciation_date, DEFAULT_SERVER_DATE_FORMAT)
                    depreciation_date = last_depreciation_date + relativedelta(months=+asset.method_period)
                else:
                    depreciation_date = datetime.strptime(asset.purchase_date, DEFAULT_SERVER_DATE_FORMAT)
                    depreciation_date = depreciation_date + relativedelta(months=+asset.period_prorate)
                    if asset.method_time == 'end' and depreciation_date > datetime.strptime(asset.method_end, DEFAULT_SERVER_DATE_FORMAT):
                        depreciation_date = datetime.strptime(asset.method_end, DEFAULT_SERVER_DATE_FORMAT)
            else:
                purchase_date = datetime.strptime(asset.purchase_date, DEFAULT_SERVER_DATE_FORMAT)
                if len(posted_depreciation_line_ids) > 0:
                    last_depreciation_date = datetime.strptime(depreciation_lin_obj.browse(cr, uid, posted_depreciation_line_ids[0], context=context).depreciation_date, DEFAULT_SERVER_DATE_FORMAT)
                    depreciation_date = last_depreciation_date + relativedelta(months=+asset.method_period)
                else:
                    depreciation_date = datetime(purchase_date.year, 1, 1)
            day = depreciation_date.day
            month = depreciation_date.month
            year = depreciation_date.year
            total_days = year % 4 and 365 or 366
            undone_dotation_number = self._compute_board_undone_dotation_nb(cr, uid, asset, depreciation_date,
                                                                            total_days, context=context)
            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                i = x + 1
                amount = self._compute_board_amount(cr, uid, asset, i, residual_amount, amount_to_depr,
                                                    undone_dotation_number, posted_depreciation_line_ids, total_days,
                                                    depreciation_date, context=context)
                current_currency = asset.currency_id.id
                amount = currency_obj.compute(cr, uid, current_currency, current_currency, amount, context=context)
                residual_amount -= amount
                vals = [{
                    'amount': amount,  # Amortización Actual
                    'asset_id': asset.id,
                    'sequence': i,
                    'name': str(asset.id) + '/' + str(i),
                    'state': 'open',
                    'remaining_value': residual_amount + asset.salvage_value,  # Amortización del siguiente periodo
                    'remaining_value_end': residual_amount + asset.salvage_value + amount,  # Valor Libros
                    'depreciated_value': asset.purchase_value + asset.tax_value - asset.salvage_value -
                                         (residual_amount + amount),  # Importe Depreciado
                    'depreciation_date': depreciation_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
                    }]
                orm2sql.sqlcreate(uid, cr, 'account_asset_depreciation_line', vals, company=False, commit=False)
                depreciation_date = datetime(year, month, day) + relativedelta(months=+asset.method_period)
                day = depreciation_date.day
                month = depreciation_date.month
                year = depreciation_date.year
            i += 1
            orm2sql.printProgressBar(i, l, start=start)
        return True

class account_asset_category(osv.osv):
    _inherit = 'account.asset.category'
    _columns = {
        'period_prorate': fields.integer('Desfase Periodo Inicial', help='El desfaz de periodo es un numero que se le sumara a la fecha de compra del activo, el resultado indica la fecha inicial de depreciacion del activo'),
        'property_account_cost_depreciation_id': fields.property(type='many2one', relation='account.account', string='Cuenta de costos de amortizacion', domain="[('type', '!=', 'view')]"),
        'property_account_gasto_de_venta_depreciation_id': fields.property(type='many2one', relation='account.account', string='Cuenta de gasto de venta de amortizacion', domain="[('type', '!=', 'view')]"),
        'property_account_tax_cost_depreciation_id': fields.property(type='many2one', relation='account.account', string='Cuenta de costos de impuestos amortizacion', domain="[('type', '!=', 'view')]"),
        'property_account_tax_expense_depreciation_id': fields.property(type='many2one', relation='account.account', string='Cuenta de gastos de impuestos amortizacion', domain="[('type', '!=', 'view')]"),
        'property_account_eliminated_id': fields.property(type='many2one', relation='account.account', string='Cuenta de Gasto Baja Activo por Perdida', domain="[('type', '!=', 'view'),('niif', '=', False)]"),
        'journal_eliminated_id': fields.property(type='many2one', relation='account.journal', domain="[('type', '=', 'general')]", string='Diario Baja Activo Deterioro Total'),
        'journal_eliminated_id1': fields.property(type='many2one', relation='account.journal', domain="[('type', '=', 'general')]", string='Diario Baja Activo por Perdida'),
        'journal_eliminated_id2': fields.property(type='many2one', relation='account.journal', domain="[('type', '=', 'general')]", string='Diario Baja Activo por Venta'),
        'account_asset_ganancia_id': fields.property(type='many2one', relation='account.account', string='Cuenta de Gasto Baja Activo por Venta', domain="[('niif', '=', False),('type', '=', 'other')]"),
        'account_asset_tax_id': fields.property(type='many2one', relation='account.account', string='Cuenta de Impuesto', domain="[('niif', '=', False),('type', '=', 'other')]"),
        }
        
            
    _defaults = {'period_prorate': 1}


class account_asset_depreciation_line(osv.osv):
    _inherit = 'account.asset.depreciation.line'
    _columns = {'remaining_value_end': fields.float(string='Valor Libros', digits_compute=dp.get_precision('Account'), readonly=False)}

    def create_move(self, cr, uid, ids, context = None):
        can_close = False
        if context is None:
            context = {}
        asset_obj = self.pool.get('account.asset.asset')
        period_obj = self.pool.get('account.period')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        currency_obj = self.pool.get('res.currency')
        created_move_ids = []
        asset_ids = []
        for line in self.browse(cr, uid, ids, context=context):
            depreciation_date = line.depreciation_date
            period_ids = period_obj.find(cr, uid, depreciation_date, context=context)
            company_currency = line.asset_id.company_id.currency_id.id
            current_currency = line.asset_id.currency_id.id
            context.update({'date': depreciation_date})
            line_amount = line.amount / (1 + line.asset_id.tax_value / line.asset_id.purchase_value)
            impuestos = 0
            computed_taxes = []
            for tax in self.pool.get('account.tax').compute_all(cr, uid, line.asset_id.tax_ids, line_amount, 1)['taxes']:
                impuestos += tax['amount']
                computed_taxes.append(tax)

            if company_currency != current_currency:
                amount = line.asset_id.tasa_moneda * line_amount
                impuestos_local = impuestos * line.asset_id.tasa_moneda
            else:
                amount = line_amount
                impuestos_local = impuestos
            amount = currency_obj.compute(cr, uid, current_currency, current_currency, amount, context=context)
            sign = (line.asset_id.category_id.journal_id.type == 'purchase' and 1) * -1 or 1
            asset_name = line.asset_id.name
            reference = line.name
            move_vals = {'name': asset_name,
             'date': depreciation_date,
             'ref': reference,
             'period_id': period_ids and period_ids[0] or False,
             'journal_id': line.asset_id.category_id.journal_id.id}
            move_id = move_obj.create(cr, uid, move_vals, context=context)
            journal_id = line.asset_id.category_id.journal_id.id
            partner_id = line.asset_id.partner_id.id
            move_line_obj.create(cr, uid, {'name': asset_name,
             'ref': reference,
             'move_id': move_id,
             'account_id': line.asset_id.category_id.account_depreciation_id.id,
             'debit': 0.0,
             'credit': amount + impuestos_local,
             'period_id': period_ids and period_ids[0] or False,
             'journal_id': journal_id,
             'partner_id': partner_id,
             'currency_id': company_currency != current_currency and current_currency or False,
             'amount_currency': company_currency != current_currency and -sign * (line.amount + impuestos) or 0.0,
             'date': depreciation_date}, context=context)
            for tax in computed_taxes:
                if tax['amount'] > 0:
                    if company_currency != current_currency:
                        tax_amount = line.asset_id.tasa_moneda * tax['amount']
                    else:
                        tax_amount = tax['amount']
                    move_line_obj.create(cr, uid, {'name': tax['name'],
                     'ref': reference,
                     'move_id': move_id,
                     'account_id': asset_obj.get_depreciation_account(cr, uid, line.asset_id, line.asset_id.centrocosto_id, tax=True, context=context),
                     'credit': 0.0,
                     'debit': tax_amount,
                     'period_id': period_ids and period_ids[0] or False,
                     'journal_id': journal_id,
                     'partner_id': partner_id,
                     'currency_id': company_currency != current_currency and current_currency or False,
                     'amount_currency': company_currency != current_currency and sign * tax_amount or 0.0,
                     'analytic_account_id': line.asset_id.centrocosto_id.id,
                     'date': depreciation_date,
                     'asset_id': line.asset_id.id,
                     'tax_code_id': tax['tax_code_id'],
                     'tax_amount': tax['amount']}, context=context)

            move_line_obj.create(cr, uid, {'name': asset_name,
             'ref': reference,
             'move_id': move_id,
             'account_id': asset_obj.get_depreciation_account(cr, uid, line.asset_id, line.asset_id.centrocosto_id, context=context),
             'credit': 0.0,
             'debit': amount,
             'period_id': period_ids and period_ids[0] or False,
             'journal_id': journal_id,
             'partner_id': partner_id,
             'currency_id': company_currency != current_currency and current_currency or False,
             'amount_currency': company_currency != current_currency and sign * line_amount or 0.0,
             'analytic_account_id': line.asset_id.centrocosto_id.id,
             'date': depreciation_date,
             'asset_id': line.asset_id.id}, context=context)
            self.write(cr, uid, line.id, {'move_id': move_id}, context=context)
            created_move_ids.append(move_id)
            asset_ids.append(line.asset_id.id)

        for asset in asset_obj.browse(cr, uid, list(set(asset_ids)), context=context):
            if currency_obj.is_zero(cr, uid, asset.currency_id, asset.value_residual):
                asset.write({'state': 'close'})

        return created_move_ids


class account_tax(osv.osv):
    _inherit = 'account.tax'
    _columns = {'en_activo': fields.boolean('En Activos')}


class account_invoice_line(osv.osv):
    _inherit = 'account.invoice.line'
    _columns = {
        'account_asset_id': fields.many2one('account.asset.asset', 'Activo', readonly=True),
        'type_asset_tax': fields.boolean(string='Iva como Gasto', select=True, help="Se reconoce el impuesto IVA como gasto, esta cuenta se parametriza en la categoria del activo."),
        }

    def onchange_asset_category_id(self, cr, uid, ids, asset_category_id, context = None):
        res = {}
        if asset_category_id:
            asset = self.pool.get('account.asset.category').browse(cr, uid, asset_category_id, context=context)
            if asset.account_asset_id:
                res['account_id'] = asset.account_asset_id.id
        return {'value': res}

    def asset_create(self, cr, uid, lines, context = None):
        context = context or {}
        asset_obj = self.pool.get('account.asset.asset')
        
        for line in lines:
            if line.asset_category_id:
                purchase_asset=False
                try:
                    if line.stock_move_ids and line.stock_move_ids[0].purchase_asset == 'inventary':
                        purchase_asset=True
                except:
                    pass
                
                if not purchase_asset:
                    vals = self.asset_create_depreciation_values(cr, uid, line, context=context)
                    if line.invoice_id.type == 'in_invoice':
                        asset_id = asset_obj.create(cr, uid, vals, context=context)
                        self.write(cr, uid, [line.id], {'account_asset_id': asset_id}, context=context)
                        if line.asset_category_id.open_asset:
                            asset_obj.validate(cr, uid, [asset_id], context=context)

        return True

    def asset_create_depreciation_values(self, cr, uid, line, context = None):
        asset_obj = self.pool.get('account.asset.asset')
        vals = {'name': line.name,
         'code': line.invoice_id.number or False,
         'category_id': line.asset_category_id.id,
         'purchase_value': line.price_subtotal,
         'period_id': line.invoice_id.period_id.id,
         'partner_id': line.invoice_id.partner_id.id,
         'company_id': line.invoice_id.company_id.id,
         'currency_id': line.invoice_id.currency_id.id,
         'purchase_date': line.invoice_id.date_invoice,
         'centrocosto_id': line.account_analytic_id.id,
         'multicurrency': line.invoice_id.es_multidivisa,
         'tasa_moneda': line.invoice_id.tasa_manual,
         'product_id': line.product_id.id,
         'tax_ids': [(6, 0, [ tax.id for tax in line.invoice_line_tax_id if tax.en_activo ])]}
        try:
            changed_vals = asset_obj.onchange_category_id(cr, uid, [], vals['category_id'], context=context)
        except:
            changed_vals = asset_obj.onchange_category_id(cr, uid, [], vals['category_id'], vals['purchase_value'], 0, vals['tax_ids'], vals['company_id'], vals['purchase_date'], context=context)

        vals.update(changed_vals['value'])
        return vals
