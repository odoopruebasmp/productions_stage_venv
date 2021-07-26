# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
# from openerp.tools.translate import _
from openerp import addons
from openerp import SUPERUSER_ID
import itertools
from dateutil.relativedelta import relativedelta
from lxml import etree
from openerp import models, fields, api, _
from openerp.osv import osv, fields as fields2
from openerp.exceptions import except_orm, Warning, RedirectWarning
import openerp.addons.decimal_precision as dp
import locale

class account_asset_asset_close_wizard(models.TransientModel):
    _inherit = 'account.asset.asset.close.wizard'

    @api.one
    def do_close(self):
        orm2sql = self.pool.get('avancys.orm2sql')
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']
        period_obj = self.env['account.period']
        line_obj = self.env['account.asset.depreciation.line']
        asset_id = self.asset_id
        date = datetime.now().date()
        reference = asset_id.code
        partner_id = asset_id.company_id.partner_id.id
        period_id = period_obj.search([('date_start', '<=', date), ('date_stop', '>=', date), ('state', '=', 'draft')], limit=1)
        
        res = super(account_asset_asset_close_wizard, self).do_close()
        if not period_id:
            raise osv.except_osv(_('Error !'), _("No existe un periodo abierto para la fecha '%s'") % date)
        if self.type == 'depreciacion':
            if asset_id.move_eliminated_niif_id:
                raise osv.except_osv(_('Error !'), _("La baja del activo '%s' para el plan contable ya fue realizada, no es posible procesar este requerimiento") % asset_id.name)
            
            depreciation = line_obj.search([('asset_id2', '=', asset_id.id), ('move_id', '=', False)])
            if depreciation:
                raise osv.except_osv(_('Error !'), _("No es posible realizar la baja de un activo por metodo 'Deterioro Total' si aun tiene deterioros por contabilizar."))
            
            account_activacion = asset_id.category_id.account_asset_nif_property and asset_id.category_id.account_asset_nif_property.id or False
            if not account_activacion:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de activacion en la categoria '%s'") % asset_id.category_id.name)
            account_depreciation_id = asset_id.category_id.account_depreciation_nif_property and asset_id.category_id.account_depreciation_nif_property.id or False
            if not account_depreciation_id:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de depreciacion contable de la categoria '%s'") % asset_id.category_id.name)
            journal_id = asset_id.category_id.journal_down_id and asset_id.category_id.journal_down_id.id or False
            if not journal_id:
                raise osv.except_osv(_('Error !'), _("Debe configurar el diario contable 'Diario Baja Activo Deterioro Total' en la categoria '%s'") % asset_id.category_id.name)
            name = self.pool.get('ir.sequence').next_by_id(self._cr, self._uid, asset_id.category_id.journal_down_id.sequence_id.id, context=self._context)
            name_move = 'BAJA ACTIVO POR DETERIORO TOTAL NIIF' + asset_id.name
            account_analytic_id = asset_id.centrocosto_id and asset_id.centrocosto_id.id or False
            
            move_vals = [{'name': name,
                'date': str(date),
                'ref': name_move,
                'period_id': period_id.id,
                'journal_id': journal_id,
                'state': 'posted'}]
            move_id = orm2sql.sqlcreate(self._uid, self._cr, 'account_move', move_vals, company=True, commit=False)[0][0]
            
            line = [{'name': name_move,
                'ref': name,
                'ref1': 'Valor Activo',
                'move_id': move_id,
                'account_id': account_activacion,
                'account_niif_id': account_activacion,
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
            
            line = [{'name': name_move,
                'ref': name,
                'ref1': 'Valor Depreciacion',
                'move_id': move_id,
                'account_id': account_depreciation_id,
                'account_niif_id': account_depreciation_id,
                'debit': asset_id.value_to_depreciate_niif,
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
                    'account_niif_id': account_activacion,
                    'debit': asset_id.salvage_value_niif,
                    'credit': 0.0,
                    'period_id': period_id.id,
                    'journal_id': journal_id,
                    'partner_id': partner_id,
                    'analytic_account_id': account_analytic_id,
                    'date': str(date),
                    'asset_id': asset_id.id,
                    'state': 'valid'}]
                orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
            
            if asset_id.deterioro_id:
                for line in asset_id.deterioro_id.filtered(lambda x: x.move_id != False):
                    if line.type == 'deterioro':
                        account_id = asset_id.category_id.account_deterioro and asset_id.category_id.account_deterioro.id or False
                        if not account_id:
                            raise osv.except_osv(_('Error!'),_("Para realizar esta operacion, debe configurar la cuenta de deterioro en la categoria '%s'") % (asset_id.category_id.name))
                        line = [{'name': name_move,
                        'ref': name,
                        'ref1': 'Reversion Deterioro',
                        'move_id': move_id,
                        'account_id': account_id,
                        'account_niif_id': account_id,
                        'debit': abs(line.value),
                        'credit': 0.0,
                        'period_id': period_id.id,
                        'journal_id': journal_id,
                        'partner_id': partner_id,
                        'analytic_account_id': account_analytic_id,
                        'date': str(date),
                        'asset_id': asset_id.id,
                        'state': 'valid'}]
                        orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
                    else:
                        account_id = asset_id.category_id.account_recuperacion and asset_id.category_id.account_recuperacion.id or False
                        if not account_id:
                            raise osv.except_osv(_('Error!'),_("Para realizar esta operacion, debe configurar la cuenta de deterioro en la categoria '%s'") % (asset_id.category_id.name))
                        line = [{'name': name_move,
                        'ref': name,
                        'ref1': 'Reversion Recuperacion',
                        'move_id': move_id,
                        'account_id': account_id,
                        'account_niif_id': account_id,
                        'debit': 0.0,
                        'credit': abs(line.value),
                        'period_id': period_id.id,
                        'journal_id': journal_id,
                        'partner_id': partner_id,
                        'analytic_account_id': account_analytic_id,
                        'date': str(date),
                        'asset_id': asset_id.id,
                        'state': 'valid'}]
                        orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)                    
            asset_id.move_eliminated_niif_id=move_id
        elif self.type == 'perdida':
            if asset_id.move_eliminated_niif_id:
                raise osv.except_osv(_('Error !'), _("La baja del activo '%s' para el plan Contable ya fue realizada, no es posible procesar este requerimiento") % asset_id.name)
            
            account_activacion = asset_id.category_id.account_asset_nif_property and asset_id.category_id.account_asset_nif_property.id or False
            if not account_activacion:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de activacion en la categoria '%s'") % asset_id.category_id.name)
            
            account_depreciation_id = asset_id.category_id.account_depreciation_nif_property and asset_id.category_id.account_depreciation_nif_property.id or False
            if not account_depreciation_id:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de depreciacion contable de la categoria '%s'") % asset_id.category_id.name)
            
            journal_id = asset_id.category_id.journal_down_id1 and asset_id.category_id.journal_down_id1.id or False
            if not journal_id:
                raise osv.except_osv(_('Error !'), _("Debe configurar el 'Diario Baja Activo por Perdida' en la categoria '%s'") % asset_id.category_id.name)
            
            name = self.pool.get('ir.sequence').next_by_id(self._cr, self._uid, asset_id.category_id.journal_down_id1.sequence_id.id, context=self._context)
            name_move = 'BAJA ACTIVO POR PERDIDA ' + asset_id.name
            account_analytic_id = asset_id.centrocosto_id and asset_id.centrocosto_id.id or False
            date_maturity = False
            partner_id2 = partner_id
            if self.partner_id:
                partner_id2 = self.partner_id.id
                account_id = self.partner_id.property_account_receivable or False
                if not account_id:
                    raise osv.except_osv(_('Error !'), _("Debe configurar la cuenta por cobrar en el tercero '%s'") % self.partner_id.name)
                
                self._cr.execute('''SELECT
                                        child_id
                                    FROM                 
                                        account_account_consol_rel
                                    WHERE  
                                        parent_id = %s ''',
                                (account_id.id,))   
                account_id = self._cr.fetchall()
                if not account_id:
                    raise osv.except_osv(_('Error !'), _("Debe configurar la cuenta en consolidacion de la cuenta '%s'.") % self.partner_id.property_account_receivable.name)
                
                if isinstance(account_id, (list, tuple)):
                    account_id = account_id[0]
                else:
                    account_id = account_id
                    
                if isinstance(account_id, (list, tuple)):
                    account_id = account_id[0]
                else:
                    account_id = account_id
                
                date_maturity = str(self.date_maturity)
            else:
                account_id = asset_id.category_id.account_down_id and asset_id.category_id.account_down_id.id or False
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
            for l in asset_id.depreciation_line_nif_ids:
                if l.move_id:
                    amount_depreciacion += l.amount

            if amount_depreciacion:
                line = [{'name': name_move,
                  'ref': name,
                  'ref1': 'Valor Depreciacion',
                  'move_id': move_id,
                  'account_id': account_depreciation_id,
                  'account_niif_id': account_depreciation_id,
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
              'account_niif_id': account_activacion,
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
            
            
            if asset_id.deterioro_id:
                for line in asset_id.deterioro_id.filtered(lambda x: x.move_id != False):
                    if line.type == 'deterioro':
                        account_idx = asset_id.category_id.account_deterioro and asset_id.category_id.account_deterioro.id or False
                        if not account_idx:
                            raise osv.except_osv(_('Error!'),_("Para realizar esta operacion, debe configurar la cuenta de deterioro en la categoria '%s'") % (asset_id.category_id.name))
                        line = [{'name': name_move,
                        'ref': name,
                        'ref1': 'Reversion Deterioro',
                        'move_id': move_id,
                        'account_id': account_idx,
                        'account_niif_id': account_idx,
                        'debit': abs(line.value),
                        'credit': 0.0,
                        'period_id': period_id.id,
                        'journal_id': journal_id,
                        'partner_id': partner_id,
                        'analytic_account_id': account_analytic_id,
                        'date': str(date),
                        'asset_id': asset_id.id,
                        'state': 'valid'}]
                        orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
                    else:
                        account_idx = asset_id.category_id.account_recuperacion and asset_id.category_id.account_recuperacion.id or False
                        if not account_idx:
                            raise osv.except_osv(_('Error!'),_("Para realizar esta operacion, debe configurar la cuenta de deterioro en la categoria '%s'") % (asset_id.category_id.name))
                        line = [{'name': name_move,
                        'ref': name,
                        'ref1': 'Reversion Recuperacion',
                        'move_id': move_id,
                        'account_id': account_idx,
                        'account_niif_id': account_idx,
                        'debit': 0.0,
                        'credit': abs(line.value),
                        'period_id': period_id.id,
                        'journal_id': journal_id,
                        'partner_id': partner_id,
                        'analytic_account_id': account_analytic_id,
                        'date': str(date),
                        'asset_id': asset_id.id,
                        'state': 'valid'}]
                        orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)  
                
            if asset_id.purchase_value_niif - amount_depreciacion -  asset_id.amount_deterioro > 0.0:
                line = [{'name': name_move,
                  'ref': name,
                  'ref1': 'Valor por Perdida del Activo',
                  'move_id': move_id,
                  'account_id': account_id,
                  'account_niif_id': account_id,
                  'debit': asset_id.purchase_value_niif - amount_depreciacion -  asset_id.amount_deterioro,
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
                
            asset_id.move_eliminated_niif_id=move_id
            
        else:
            if asset_id.move_eliminated_niif_id:
                raise osv.except_osv(_('Error !'), _("La baja del activo '%s' para el plan contable ya fue realizada, no es posible procesar este requerimiento") % asset_id.name)
            product_id = self.asset_id.product_id
            
            account_activacion = asset_id.category_id.account_asset_nif_property and asset_id.category_id.account_asset_nif_property.id or False
            if not account_activacion:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de activacion en la categoria '%s'") % asset_id.category_id.name)
            
            account_depreciation_id = asset_id.category_id.account_depreciation_nif_property and asset_id.category_id.account_depreciation_nif_property.id or False
            if not account_depreciation_id:
                raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de depreciacion contable de la categoria '%s'") % asset_id.category_id.name)
            
            journal_id = asset_id.category_id.journal_sale_id and asset_id.category_id.journal_sale_id.id or False
            if not journal_id:
                raise osv.except_osv(_('Error !'), _("Debe configurar el 'Diario Baja Activo por Venta' en la categoria '%s'") % asset_id.category_id.name)
            
            name = self.pool.get('ir.sequence').next_by_id(self._cr, self._uid, asset_id.category_id.journal_sale_id.sequence_id.id, context=self._context)
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
            for l in asset_id.depreciation_line_nif_ids:
                if l.move_id:
                    amount_depreciacion += l.amount

            if amount_depreciacion:
                line = [{'name': name_move,
                  'ref': name,
                  'ref1': 'Valor Depreciacion',
                  'move_id': move_id,
                  'account_id': account_depreciation_id,
                  'account_niif_id': account_depreciation_id,
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
              'account_niif_id': account_activacion,
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
            
            
            if asset_id.deterioro_id:
                for line in asset_id.deterioro_id.filtered(lambda x: x.move_id != False):
                    if line.type == 'deterioro':
                        account_idx = asset_id.category_id.account_deterioro and asset_id.category_id.account_deterioro.id or False
                        if not account_idx:
                            raise osv.except_osv(_('Error!'),_("Para realizar esta operacion, debe configurar la cuenta de deterioro en la categoria '%s'") % (asset_id.category_id.name))
                        line = [{'name': name_move,
                        'ref': name,
                        'ref1': 'Reversion Deterioro',
                        'move_id': move_id,
                        'account_id': account_idx,
                        'account_niif_id': account_idx,
                        'debit': abs(line.value),
                        'credit': 0.0,
                        'period_id': period_id.id,
                        'journal_id': journal_id,
                        'partner_id': partner_id,
                        'analytic_account_id': account_analytic_id,
                        'date': str(date),
                        'asset_id': asset_id.id,
                        'state': 'valid'}]
                        orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
                    else:
                        account_idx = asset_id.category_id.account_recuperacion and asset_id.category_id.account_recuperacion.id or False
                        if not account_idx:
                            raise osv.except_osv(_('Error!'),_("Para realizar esta operacion, debe configurar la cuenta de deterioro en la categoria '%s'") % (asset_id.category_id.name))
                        line = [{'name': name_move,
                        'ref': name,
                        'ref1': 'Reversion Recuperacion',
                        'move_id': move_id,
                        'account_id': account_idx,
                        'account_niif_id': account_idx,
                        'debit': 0.0,
                        'credit': abs(line.value),
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
                raise osv.except_osv(_('Error !'), _("El sistema no logra encontrar una linea en la factura '%s' para el producto del activo en cuention "  % self.invoice_id.name))
            
            amount=amount_depreciacion - asset_id.purchase_value_niif - asset_id.amount_deterioro     
            
            asset_id.amount_venta_contable=invoice_line.price_subtotal + amount_depreciacion - asset_id.purchase_value_niif - asset_id.amount_deterioro     
            
            account_idx=asset_id.category_id.account_asset_ganancia_niif_id and asset_id.category_id.account_asset_ganancia_niif_id.id or False
            if not account_idx:
                raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta de 'Cuenta de Utilidad Venta Activo' en la categoria del activo %s "  % asset_id.category_id.name))
            
            linex = [{
                'name': name_move,                    
                'ref': self.invoice_id.origin or str(self.invoice_id.id),
                'ref1': 'Gasto por venta Activo',
                'move_id': move_id,
                'account_id': account_idx,
                'account_niif_id': account_idx,
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
            
            asset_id.move_eliminated_niif_id=move_id
            
        return True
    
    
class account_invoice(models.Model):
    _inherit = "account.invoice"
    

    @api.multi
    def action_move_create(self):        
        res = super(account_invoice, self).action_move_create()        
        if self.type in ['in_invoice', 'in_refund']:
            for line in self.invoice_line:
                if line.asset_category_id:
                    for l in self.move_id.line_id:
                        if not line.asset_category_id.account_asset_nif_property:
                            raise osv.except_osv(_('Error!'),_("Por favor configurar la cuenta de de activacion NIIF en la categoria del activo '%s' para el producto '%s' ") % (line.asset_category_id.name, line.product_id.name))
                        if l.account_id.id == line.asset_category_id.account_asset_id.id:
                            self._cr.execute(''' UPDATE account_move_line SET account_niif_id=%s WHERE move_id=%s AND account_id=%s''',(line.asset_category_id.account_asset_nif_property.id,l.move_id.id,l.account_id.id))
                        self._cr.execute(''' UPDATE account_move_line SET base_code_id=%s, tax_code_id=%s WHERE move_id=%s AND (account_id=%s OR account_id=%s)''',(None,None,l.move_id.id,line.asset_category_id.account_asset_id.id, line.asset_category_id.account_asset_tax_id.id or 0))
                        
        return res
    

class asset_depreciation_confirmation_wizard(models.TransientModel):
    _inherit = 'asset.depreciation.confirmation.wizard'
    
    type_plan = fields.Selection([('colgaap','FISCAL'),('niif','NIIF'),('all','FISCAL - NIIF')], string='PLAN', required=True, default="all")
    
    def asset_compute(self, cr, uid, ids, context):
        ctx = context.copy()
        ctx.update({'type_plan': self.browse(cr, uid, ids, context=context).type_plan})
        res = super(asset_depreciation_confirmation_wizard, self).asset_compute(cr, uid, ids, context=ctx)
        return res
        
    
class account_asset_depreciation_line(models.Model):
    _inherit = 'account.asset.depreciation.line'
        
    
    @api.one
    @api.depends('asset_id', 'asset_id2', 'asset_id.state', 'asset_id2.state')
    def _state(self):
        if self.asset_id:          
            self.state= self.asset_id.state
            self.category_id = self.asset_id.category_id.id
        elif self.asset_id2:
            self.state= self.asset_id2.state
            self.category_id = self.asset_id2.category_id.id
    
    is_niff = fields.Boolean(string="Es Niff")
    asset_id2 = fields.Many2one('account.asset.asset', string='Activo Contable', readonly=True, ondelete='cascade', required=False)
    asset_id = fields.Many2one('account.asset.asset', string='Activo Fiscal', readonly=True, ondelete='cascade', required=False)
    batched = fields.Boolean('ejecutado')
    state = fields.Char(string='Estado', compute="_state", store=True, readonly=True)
    category_id = fields.Many2one('account.asset.category', string='Categoria', readonly=True, store=True, compute="_state")
    remaining_value_end = fields.Float(string='Valor Libros', digits=dp.get_precision('Account'), readonly=False)
    valorizado_id = fields.Many2one('account.asset.deterioro', string='Valorizacion', readonly=True)
    amount_valorizado = fields.Float(string='Valorizacion', digits=dp.get_precision('Account'), readonly=False)
    
    #copia 07/04 de account_asset_extended con cuentas y parametros modificados
    def unlink_move_nif(self, cr, uid, ids, context=None):
        orm2sql = self.pool.get('avancys.orm2sql')
        acc_asset_obj = self.pool.get('account.asset.asset')
        for line in self.browse(cr, uid, ids, context=context):
            if line.move_id:
                line.move_id.button_cancel()
                line.move_id.unlink()
                line.move_check = False
            if line.asset_id2:
                acc_asset = line.asset_id2.id
                orm2sql.sqlupdate(cr, 'account_asset_depreciation_line', {'batched': 'f'}, ('id', line.id))
                acc_asset_obj.write(cr, uid, line.asset_id2.id, {'amount_depreciado': line.asset_id2.amount_depreciado-line.amount, 'amount_valorizacion': line.asset_id2.amount_valorizacion+line.amount_valorizado}, context=context)
                acc_asset_obj.browse(cr, uid, acc_asset, context).update_depreciations()
        return True
    
    
    def create_move(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        asset_obj = self.pool.get('account.asset.asset')
        period_obj = self.pool.get('account.period')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        orm2sql = self.pool.get('avancys.orm2sql')
        
        currency_obj = self.pool.get('res.currency')
        created_move_ids = []
        asset_ids = []
        i, l = 0, len(self.browse(cr, uid, ids, context=context))
        start = datetime.now()
        orm2sql.printProgressBar(i, l, start=start)
        
        for line in self.browse(cr, uid, ids, context=context):
            period=period_obj.search(cr, uid, [('date_start', '<', line.depreciation_date),('date_stop', '>', line.depreciation_date),('state', '=', 'done')], context=context)
            if period:
                raise osv.except_osv(_("Error !"), _("No es posible crear asientos contables en un periodo contable cerrado, Activo %s")%(line.asset_id.name))
            if line.asset_id.state == 'eliminated':
                continue
            if line.batched:
                continue
            if line.asset_id2:
                depreciation_date = line.depreciation_date#FR
                period_ids = period_obj.find(cr, uid, depreciation_date, context=context)
                company_currency = line.asset_id2.company_id.currency_id.id
                current_currency = line.asset_id2.currency_id.id
                context.update({'date': depreciation_date})

                #tasa
                if company_currency != current_currency:
                    amount = line.asset_id2.tasa_moneda*line.amount
                else:
                    amount = line.amount
                amount = currency_obj.compute(cr, uid, current_currency, current_currency, amount, context=context)
                #tasa

                category_asset_id = line.asset_id2.category_id
                analytic_account = line.asset_id2.centrocosto_id or False

                if analytic_account and analytic_account.costo_gasto == 'gasto_venta':
                    account_debit = category_asset_id.account_gasto_venta_nif_property and category_asset_id.account_gasto_venta_nif_property.id
                    if not account_debit:
                        raise osv.except_osv(_('Error!'),_("Por favor configurar la cuenta de gasto de venta de Amortizacion/Depreciacion de la categoria del activo '%s'") % (line.asset_id2.name))
                elif analytic_account and analytic_account.costo_gasto == 'costo':
                    account_debit = category_asset_id.account_cost_nif_property and category_asset_id.account_cost_nif_property.id
                    if not account_debit:
                        raise osv.except_osv(_('Error!'),_("Por favor configurar la cuenta de costo de Amortizacion/Depreciacion de la categoria del activo '%s'") % (line.asset_id2.name))
                else:
                    account_debit = category_asset_id.account_expense_depreciation_nif_property and category_asset_id.account_expense_depreciation_nif_property.id
                    if not account_debit:
                        raise osv.except_osv(_('Error!'),_("Por favor configurar la cuenta de gastos de Amortizacion/Depreciacion de la categoria del activo '%s'") % (line.asset_id2.name))

                account_credit = line.asset_id2.category_id.account_depreciation_nif_property.id

                sign = (category_asset_id.journal_niff_structure_property.type == 'purchase' and 1)*-1 or 1
                name2 = str('NIIF / '+(line.asset_id2.product_id.default_code or str(line.asset_id2.name.encode('ascii', 'ignore').decode('ascii'))) +' / '+str(line.depreciation_date))
                sequence = category_asset_id.journal_niff_structure_property.sequence_id or False
                if not sequence:
                    raise osv.except_osv(_('Error!'),_("Por favor asigne la secuencia al diario de la categoria '%s'") % (line.asset_id2.category_asset_id.name))
                name = self.pool.get('ir.sequence').next_by_id(cr, uid, sequence.id, context) or '/'
                reference = str(line.name)
                journal_id = category_asset_id.journal_niff_structure_property or False
                if not journal_id:
                    raise osv.except_osv(_('Error!'),_("Por favor configurar el diario  de Amortizacion/Depreciacion NIIF en la categoria del activo '%s'") % (line.asset_id2.name))
                move_vals = [{
                    'name': name,
                    'narration': name2,
                    'date': depreciation_date,
                    'ref': reference,
                    'period_id': period_ids and period_ids[0] or False,
                    'journal_id': journal_id.id,
                    'state': 'posted',
                }]
                # move_id = move_obj.create(cr, uid, move_vals, context=context)
                move_id = orm2sql.sqlcreate(uid, cr, 'account_move', move_vals, company=True, commit=False)
                move_id = move_obj.search(cr, uid, [('id', 'in', move_id)])[0]

                partner_id = line.asset_id2.partner_id.id
                line1 = [{
                    'name': name,
                    'ref': reference,
                    'move_id': move_id,
                    'account_id': account_credit,
                    'account_niif_id': account_credit,
                    'debit': 0.0,
                    'credit': amount,
                    'period_id': period_ids and period_ids[0] or False,
                    'journal_id': journal_id.id,
                    'partner_id': partner_id,
                    'currency_id': company_currency != current_currency and  current_currency or False,
                    'amount_currency': company_currency != current_currency and - sign * line.amount or 0.0,
                    'analytic_account_id': line.asset_id2.centrocosto_id.id,#FR 
                    'date': depreciation_date,
                    'state': 'valid'
                }]
                move_line_id=orm2sql.sqlcreate(uid, cr, 'account_move_line', line1, company=True, commit=False)
                if line.asset_id2.centrocosto_id.id:
                    move_line_id = move_line_obj.search(cr, uid, [('id', 'in', move_line_id)])[0]
                    if not journal_id.analytic_journal_id:
                        raise osv.except_osv(_('Error!'),_("Por favor configurar el diario  Analitico para el diario '%s'") % (journal_id.name))
                    analine = [{
                        "account_id": line1[0]['analytic_account_id'],
                        "general_account_id": line1[0]['account_id'],
                        "journal_id": journal_id.analytic_journal_id.id or False,
                        "amount": -line1[0]['credit'],
                        "unit_amount": 0.0,
                        "date": line1[0]['date'],
                        "ref": reference,
                        "name": line1[0]['name'],
                        "move_id": move_line_id,
                        "credit": line1[0]['credit'],                        
                    }]
                    orm2sql.sqlcreate(uid, cr, 'account_analytic_line', analine, company=True, commit=False)
                
                line2 = [{
                    'name': name,
                    'ref': reference,
                    'move_id': move_id,
                    'account_id': account_debit,
                    'account_niif_id': account_debit,
                    'credit': 0.0,
                    'debit': amount,
                    'period_id': period_ids and period_ids[0] or False,
                    'journal_id': journal_id.id,
                    'partner_id': partner_id,
                    'currency_id': company_currency != current_currency and  current_currency or False,
                    'amount_currency': company_currency != current_currency and sign * line.amount or 0.0,
                    'analytic_account_id': line.asset_id2.centrocosto_id.id,#FR 
                    'date': depreciation_date,
                    'asset_id': line.asset_id2.id,
                    'state': 'valid'
                }]
                move_line_id = orm2sql.sqlcreate(uid, cr, 'account_move_line', line2, company=True, commit=False)
                if line.asset_id2.centrocosto_id.id:
                    move_line_id = move_line_obj.search(cr, uid, [('id', 'in', move_line_id)])[0]
                    if not journal_id.analytic_journal_id:
                        raise osv.except_osv(_('Error!'),_("Por favor configurar el diario  Analitico para el diario '%s'") % (journal_id.name))
                    analine = [{
                        "account_id": line2[0]['analytic_account_id'],
                        "general_account_id": line2[0]['account_id'],
                        "journal_id": journal_id.analytic_journal_id.id or False,
                        "amount": line2[0]['debit'],
                        "unit_amount": 0.0,
                        "date": line2[0]['date'],
                        "ref": reference,
                        "name": line2[0]['name'],
                        "move_id": move_line_id,
                        "debit": line2[0]['debit'],
                    }]
                    orm2sql.sqlcreate(uid, cr, 'account_analytic_line', analine, company=True, commit=False)
                if line.amount_valorizado:                    
                    account_activacion = line.asset_id2.category_id.account_asset_nif_property and line.asset_id2.category_id.account_asset_nif_property.id or False
                    if not account_activacion:
                        raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de activacion en la categoria '%s'") % line.asset_id2.category_id.name)
                    
                    account_superavit_id = line.asset_id2.category_id.account_superavit_id and line.asset_id2.category_id.account_superavit_id.id or False
                    if not account_superavit_id:
                        raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta 'Cuenta de Superavit' en la categoria '%s'") % line.asset_id2.category_id.name)
                        
                    line1 = [{
                        'name': name,
                        'ref': reference,
                        'move_id': move_id,
                        'account_id': account_activacion,
                        'account_niif_id': account_activacion,
                        'debit': 0.0,
                        'credit': line.amount_valorizado,
                        'period_id': period_ids and period_ids[0] or False,
                        'journal_id': journal_id.id,
                        'partner_id': partner_id,
                        'date': depreciation_date,
                        'state': 'valid',
                        'asset_id': line.asset_id2.id,
                        'analytic_account_id': line.asset_id2.centrocosto_id.id,#FR 
                    }]
                    move_line_id=orm2sql.sqlcreate(uid, cr, 'account_move_line', line1, company=True, commit=False)
                    if line.asset_id2.centrocosto_id.id:
                        move_line_id = move_line_obj.search(cr, uid, [('id', 'in', move_line_id)])[0]
                        if not journal_id.analytic_journal_id:
                            raise osv.except_osv(_('Error!'),_("Por favor configurar el diario  Analitico para el diario '%s'") % (journal_id.name))
                        analine = [{
                            "account_id": line1[0]['analytic_account_id'],
                            "general_account_id": line1[0]['account_id'],
                            "journal_id": journal_id.analytic_journal_id.id or False,
                            "amount": -line1[0]['credit'],
                            "unit_amount": 0.0,
                            "date": line1[0]['date'],
                            "ref": reference,
                            "name": line1[0]['name'],
                            "move_id": move_line_id,
                            "credit": line1[0]['credit'],
                        }]
                        orm2sql.sqlcreate(uid, cr, 'account_analytic_line', analine, company=True, commit=False)
                    line2 = [{
                        'name': name,
                        'ref': reference,
                        'move_id': move_id,
                        'account_id': account_superavit_id,
                        'account_niif_id': account_superavit_id,
                        'credit': 0.0,
                        'debit': line.amount_valorizado,
                        'period_id': period_ids and period_ids[0] or False,
                        'journal_id': journal_id.id,
                        'partner_id': partner_id,
                        'analytic_account_id': line.asset_id2.centrocosto_id.id,#FR 
                        'date': depreciation_date,
                        'asset_id': line.asset_id2.id,
                        'state': 'valid'
                    }]
                    move_line_id = orm2sql.sqlcreate(uid, cr, 'account_move_line', line2, company=True, commit=False)
                    if line.asset_id2.centrocosto_id.id:
                        move_line_id = move_line_obj.search(cr, uid, [('id', 'in', m)])[0]
                        if not journal_id.analytic_journal_id:
                            raise osv.except_osv(_('Error!'),_("Por favor configurar el diario  Analitico para el diario '%s'") % (journal_id.name))
                        analine = [{
                            "account_id": line2[0]['analytic_account_id'],
                            "general_account_id": line2[0]['account_id'],
                            "journal_id": journal_id.analytic_journal_id.id or False,
                            "amount": line2[0]['debit'],
                            "unit_amount": 0.0,
                            "date": line2[0]['date'],
                            "ref": reference,
                            "name": line2[0]['name'],
                            "move_id": move_line_id,
                            "debit": line2[0]['debit'], 
                        }]
                        orm2sql.sqlcreate(uid, cr, 'account_analytic_line', analine, company=True, commit=False)
                created_move_ids.append(move_id)
                asset_ids.append(line.asset_id2.id)
            else:
                depreciation_date = line.depreciation_date#FR
                period_ids = period_obj.find(cr, uid, depreciation_date, context=context)
                company_currency = line.asset_id.company_id.currency_id.id
                current_currency = line.asset_id.currency_id.id
                context.update({'date': depreciation_date})

                line_amount = line.amount/(1+line.asset_id.tax_value/line.asset_id.purchase_value)

                impuestos = 0
                computed_taxes = []
                taxes = [x.id for x in line.asset_id.tax_ids]
                for tax in self.pool.get('account.tax').compute_all(cr, uid, line.asset_id.tax_ids, line_amount, 1)['taxes']:
                    if tax['id'] in taxes:
                        impuestos += tax['amount']
                        computed_taxes.append(tax)

                #tasa
                if company_currency != current_currency:
                    amount = line.asset_id.tasa_moneda*line_amount
                    impuestos_local = impuestos*line.asset_id.tasa_moneda
                else:
                    amount = line_amount
                    impuestos_local = impuestos

                amount = currency_obj.compute(cr, uid, current_currency, current_currency, amount, context=context)

                #tasa                
                sign = (line.asset_id.category_id.journal_id.type == 'purchase' and 1)*-1 or 1
                name2 = line.asset_id.product_id and line.asset_id.product_id.default_code or line.asset_id.name
                name2 = name2.encode('ascii', 'replace').replace('?',' ')
                name2 = str('LOCAL / '+name2+' / '+str(line.depreciation_date))
                sequence = line.asset_id.category_id.journal_id.sequence_id or False
                if not sequence:
                    raise osv.except_osv(_('Error!'),_("Por favor asigne la secuencia al periodo de la categoria '%s'") % (line.asset_id.category_id.journal_id.name))
                name = self.pool.get('ir.sequence').next_by_id(cr, uid, sequence.id, context) or '/'
                reference = str(line.name)
                journal_id = line.asset_id.category_id.journal_id.id
                move_vals = [{
                    'name': name,
                    'narration': name2,
                    'date': depreciation_date,
                    'ref': reference,
                    'period_id': period_ids and period_ids[0] or False,
                    'journal_id': line.asset_id.category_id.journal_id.id,
                    'state': 'posted',
                }]
                # move_id = move_obj.create(cr, uid, move_vals, context=context)
                orm2sql = self.pool.get('avancys.orm2sql')
                move_id = orm2sql.sqlcreate(uid, cr, 'account_move', move_vals, company=True, commit=False)[0][0]
                #move_id = move_obj.search(cr, uid, [('id', 'in', move_id)])

                partner_id = line.asset_id.partner_id.id


                line1 = [{
                    'name': name,
                    'ref': reference,
                    'move_id': move_id,
                    'account_id': line.asset_id.category_id.account_depreciation_id.id,
                    'debit': 0.0,
                    'credit': amount+impuestos_local,
                    'period_id': period_ids and period_ids[0] or False,
                    'journal_id': journal_id,
                    'partner_id': partner_id,
                    'currency_id': company_currency != current_currency and  current_currency or False,
                    'amount_currency': company_currency != current_currency and - sign * (line.amount+impuestos) or 0.0,
                    'analytic_account_id': line.asset_id.centrocosto_id and line.asset_id.centrocosto_id.id or False,
                    'date': depreciation_date,
                    'state': 'valid',                    
                }]
                move_line_id=orm2sql.sqlcreate(uid, cr, 'account_move_line', line1, company=True, commit=False)
                if line.asset_id.centrocosto_id:
                    if not line.asset_id.category_id.journal_id.analytic_journal_id:
                        raise osv.except_osv(_('Error!'),_("Debe configurar el Diario Analitico para el Diario '%s' configurado en la categoria del activo") % line.asset_id.category_id.journal_id.name)
                    move_line_id = move_line_obj.search(cr, uid, [('id', 'in', move_line_id)])[0]
                    analine = [{
                        "account_id": line1[0]['analytic_account_id'],
                        "general_account_id": line1[0]['account_id'],
                        "journal_id": line.asset_id.category_id.journal_id.analytic_journal_id.id,
                        "amount": -line1[0]['credit'],
                        "unit_amount": 0.0,
                        "date": line1[0]['date'],
                        "ref": reference,
                        "name": line1[0]['name'],
                        "move_id": move_line_id,
                        "debit": 0.0,
                        "credit": line1[0]['credit'],
                    }]
                    orm2sql.sqlcreate(uid, cr, 'account_analytic_line', analine, company=True, commit=False)
                
                for tax in computed_taxes:
                    if tax['amount'] >  0:
                        if company_currency != current_currency:
                            tax_amount = line.asset_id.tasa_moneda*tax['amount']
                        else:
                            tax_amount = tax['amount']
                        linet = [{
                            'name': str(tax['name']),
                            'ref': reference,
                            'move_id': move_id,
                            'account_id': asset_obj.get_depreciation_account(cr, uid, line.asset_id, line.asset_id.centrocosto_id, tax=True, context=context),
                            'credit': 0.0,
                            'debit': tax_amount,
                            'period_id': period_ids and period_ids[0] or False,
                            'journal_id': journal_id,
                            'partner_id': partner_id,
                            'currency_id': company_currency != current_currency and  current_currency or False,
                            'amount_currency': company_currency != current_currency and sign * tax_amount or 0.0,
                            'analytic_account_id': line.asset_id.centrocosto_id and line.asset_id.centrocosto_id.id or False,
                            'date': depreciation_date,
                            'asset_id': line.asset_id.id,
                            'tax_code_id': False,
                            'tax_amount': 0,
                            'state': 'valid',
                        }]
                        move_line_id = orm2sql.sqlcreate(uid, cr, 'account_move_line', linet, company=True, commit=False)
                        if line.asset_id.centrocosto_id:
                            if not line.asset_id.category_id.journal_id.analytic_journal_id:
                                raise osv.except_osv(_('Error!'),_("Debe configurar el Diario Analitico para el Diario '%s' configurado en la categoria del activo") % line.asset_id.category_id.journal_id.name)
                            move_line_id = move_line_obj.search(cr, uid, [('id', 'in', move_line_id)])[0]
                            analine = [{
                                "account_id": linet[0]['analytic_account_id'],
                                "general_account_id": linet[0]['account_id'],
                                "journal_id": line.asset_id.category_id.journal_id.analytic_journal_id.id,
                                "amount": linet[0]['debit'],
                                "unit_amount": 0.0,
                                "date": linet[0]['date'],
                                "ref": reference,
                                "name": linet[0]['name'],
                                "move_id": move_line_id,
                                "debit": linet[0]['debit'],
                                "credit": 0.0,
                            }]
                            orm2sql.sqlcreate(uid, cr, 'account_analytic_line', analine, company=True, commit=False)
                    
                line2 = [{
                    'name': name,
                    'ref': reference,
                    'move_id': move_id,
                    'account_id': asset_obj.get_depreciation_account(cr, uid, line.asset_id, line.asset_id.centrocosto_id, context=context),
                    'credit': 0.0,
                    'debit': amount,
                    'period_id': period_ids and period_ids[0] or False,
                    'journal_id': journal_id,
                    'partner_id': partner_id,
                    'currency_id': company_currency != current_currency and  current_currency or False,
                    'amount_currency': company_currency != current_currency and sign * line_amount or 0.0,
                    'analytic_account_id': line.asset_id.centrocosto_id.id,
                    'date': depreciation_date,
                    'asset_id': line.asset_id.id,
                    'state': 'valid'
                }]
                move_line_id = orm2sql.sqlcreate(uid, cr, 'account_move_line', line2, company=True, commit=False)

                if line.asset_id.centrocosto_id:
                    if not line.asset_id.category_id.journal_id.analytic_journal_id:
                        raise osv.except_osv(_('Error!'),_("Debe configurar el Diario Analitico para el Diario '%s' configurado en la categoria del activo") % line.asset_id.category_id.journal_id.name)
                    move_line_id = move_line_obj.search(cr, uid, [('id', 'in', move_line_id)])[0]
                    analine = [{
                        "account_id": line2[0]['analytic_account_id'],
                        "general_account_id": line2[0]['account_id'],
                        "journal_id": line.asset_id.category_id.journal_id.analytic_journal_id.id,
                        "amount": line2[0]['debit'],
                        "unit_amount": 0.0,
                        "date": line2[0]['date'],
                        "ref": reference,
                        "name": line2[0]['name'],
                        "move_id": move_line_id,                        
                        "debit": line2[0]['debit'],
                        "credit": 0.0,
                    }]
                    orm2sql.sqlcreate(uid, cr, 'account_analytic_line', analine, company=True, commit=False)

                # self.write(cr, uid, line.id, {'move_id': move_id}, context=context)
                created_move_ids.append(move_id)
                asset_ids.append(line.asset_id.id)
            orm2sql.sqlupdate(cr, 'account_asset_depreciation_line', {'move_check': 'true'}, ('id', line.id))
            orm2sql.sqlupdate(cr, 'account_asset_depreciation_line', {'move_id': move_id}, ('id', line.id))
            orm2sql.sqlupdate(cr, 'account_asset_depreciation_line', {'batched': 't'}, ('id', line.id))

            if line.asset_id2:
                self.pool.get('account.asset.asset').write(cr, uid, line.asset_id2.id, {'amount_depreciado': line.asset_id2.amount_depreciado+line.amount, 'amount_valorizacion': line.asset_id2.amount_valorizacion-line.amount_valorizado}, context=context)
                line.asset_id2.update_depreciations()
            else:
                line.asset_id.update_depreciations()
            i += 1
            orm2sql.printProgressBar(i, l, start=start)
        return created_move_ids
    
    
class account_asset_category(models.Model):
    _inherit = "account.asset.category"
    
    journal_niff_structure_property = fields.Many2one('account.journal', company_dependent=True, string='Diario Depreciacion', domain=[('niif','=',True)])
    account_asset_nif_property = fields.Many2one('account.account', company_dependent=True, string='Cuenta de activo', domain=[('niif','=',True),('type','!=','view')])
    account_depreciation_nif_property = fields.Many2one('account.account', company_dependent=True, string='Amortizacion acumulada', domain=[('niif','=',True),('type','!=','view')])
    account_expense_depreciation_nif_property = fields.Many2one('account.account', company_dependent=True, required=True, string='Cuenta gastos amortizacion',domain=[('niif','=',True),('type','!=','view')])
    account_cost_nif_property = fields.Many2one('account.account', company_dependent=True, string='Cuenta costo amortizacion', domain=[('niif','=',True),('type','!=','view')])
    account_gasto_venta_nif_property = fields.Many2one('account.account', company_dependent=True, string='Cuenta gasto venta amortizacion', domain=[('niif','=',True),('type','!=','view')])
    journal_niff_deterioro = fields.Many2one('account.journal', company_dependent=True, string='Diario Deterioro/Recuperacion', domain=[('niif','=',True)])
    account_deterioro = fields.Many2one('account.account', company_dependent=True, string='Cuenta deterioro', domain=[('niif','=',True),('type','!=','view')])
    account_deterioro_gasto = fields.Many2one('account.account', company_dependent=True, string='Cuenta gasto deterioro', domain=[('niif','=',True),('type','!=','view')])
    account_recuperacion = fields.Many2one('account.account', company_dependent=True, string='Cuenta recuperacion', domain=[('niif','=',True),('type','!=','view')])
    account_recuperacion_ingreso = fields.Many2one('account.account', company_dependent=True, string='Cuenta ingreso recuperacion', domain=[('niif','=',True),('type','!=','view')])
    journal_niff = fields.Many2one('account.journal', company_dependent=True, string='Diario Activacion', domain=[('niif','=',True)])
    account_down_id = fields.Many2one('account.account', company_dependent=True, string='Cuenta de Gasto Baja Activo por Perdida', domain=[('niif','=',True),('type','!=','view')])
    journal_down_id = fields.Many2one('account.journal', company_dependent=True, string='Diario Baja Activo Deterioro Total', domain=[('niif','=',True)])
    journal_down_id1 = fields.Many2one('account.journal', company_dependent=True, string='Diario Baja Activo por Perdida', domain=[('niif','=',True)])
    account_asset_ganancia_niif_id = fields.Many2one('account.account', string='Cuenta de Gasto Baja Activo por Venta', domain=[('type', '!=', 'view'),('niif', '=', True)])
    journal_sale_id = fields.Many2one('account.journal', company_dependent=True, string='Diario Baja Activo por Venta', domain=[('niif','=',True)])
    model_method = fields.Selection([('revaluacion','Modelo de Revaluacion'),('costo','Model del Costo')], string='Modelo de Medicion', required=True)
    account_superavit_id = fields.Many2one('account.account', company_dependent=True, string='Cuenta de Superavit', domain=[('niif','=',True),('type','!=','view')])
    nif_method_number = fields.Integer(string='Numero de depreciaciones NIIF', default=1)
 
class account_asset_deterioro(models.Model):
    _name = "account.asset.deterioro"
    
    @api.one
    @api.depends('cost_realy','cost_use')
    def _deterioro(self):
        if self.cost_realy and self.cost_use and not self.move_id:
            if self.type == 'deterioro':
                if self.asset_id.amount_valorizacion > 0.0:
                    cost_recuperable=0.0
                    if self.cost_realy > self.cost_use:
                        cost_recuperable = self.cost_realy
                    else:
                        cost_recuperable = self.cost_use
                    
                    if cost_recuperable > self.asset_id.amount_residual_niif:
                        raise osv.except_osv(_('Error!'),_("El ' Valor Recuperable ' es superior al Valor del activo, por tal motivo no es posible generar un deterioro del mismo. por favor valide los montos asignados."))
                    
                    self.cost_recuperable = cost_recuperable                    
                    self.cost = self.asset_id.amount_residual_niif 
                    self.value = self.asset_id.amount_residual_niif - cost_recuperable - self.asset_id.amount_valorizacion
                    self.valorizacion = -self.asset_id.amount_valorizacion
                    
                else:
                    cost_recuperable=0.0
                    if self.cost_realy > self.cost_use:
                        cost_recuperable = self.cost_realy
                    else:
                        cost_recuperable = self.cost_use
                    
                    if cost_recuperable > self.asset_id.amount_residual_niif:
                        raise osv.except_osv(_('Error!'),_("El ' Valor Recuperable ' es superior al Valor del activo, por tal motivo no es posible generar un deterioro del mismo. por favor valide los montos asignados."))
                
                    self.cost_recuperable = cost_recuperable
                    self.value = self.asset_id.amount_residual_niif - cost_recuperable
                    self.cost = self.asset_id.amount_residual_niif   
        if self.type == 'recuperar' and self.cost_realy > 0.0 and not self.move_id:
            if self.cost_realy < self.asset_id.amount_residual_niif:
                raise osv.except_osv(_('Error!'),_("El ' Valor Razonable es $ %s y el valor del activo es $ %s y es inferior al Valor del activo, por tal motivo no es posible generar una recuperacion del mismo. por favor valide los montos asignados.") % (locale.format('%.2f', self.cost_realy, True), locale.format('%.2f', self.asset_id.amount_residual_niif, True)))
            else:
                value=self.cost_realy-self.asset_id.amount_residual_niif
                if self.asset_id.category_id.model_method == 'cost':                    
                    if value > self.asset_id.amount_deterioro:
                        raise osv.except_osv(_('Error!'),_("El monto que intenta recuperar es $ %s y por polica de la compañia esta restringido hasta $ %s. El maximo valor que se puede asignar al 'Valor Razonables' es $ %s. Por favor verifique los mosntos asignados o consulte con el area responsable.") % (locale.format('%.2f', value, True), locale.format('%.2f', self.asset_id.amount_deterioro, True), locale.format('%.2f', self.cost, True)))
                    self.value = -value
                    self.cost = self.asset_id.amount_residual_niif 
                else:
                    valorizacion=  value - self.asset_id.amount_deterioro
                    if valorizacion > 0:
                        self.valorizacion=valorizacion
                        self.value = -self.asset_id.amount_deterioro
                    else:
                        self.value = -value
                    self.cost = self.asset_id.amount_residual_niif 
    
    @api.one
    @api.depends('asset_id', 'asset_id.state')
    def _state(self):
        if self.asset_id:          
            self.state= self.asset_id.state
            self.category_id = self.asset_id.category_id.id
        elif self.asset_id2:
            self.state= self.asset_id2.state
            self.category_id = self.asset_id2.category_id.id
    
    cost_realy = fields.Float(string='Valor razonable')
    cost_use = fields.Float(string='Valor de Uso')
    cost_recuperable = fields.Float(string='Valor Recuperable', compute='_deterioro', digits=dp.get_precision('Account'), readonly=True, store=True)
    cost = fields.Float(string='Valor Residual', readonly=True, compute='_deterioro', digits=dp.get_precision('Account'), store=True)
    valorizacion = fields.Float(string='Valorizacion', readonly=True, compute='_deterioro', digits=dp.get_precision('Account'), store=True)
    value = fields.Float(string='Deterioro/Recuperacion', readonly=True, compute='_deterioro', digits=dp.get_precision('Account'), store=True)
    create_date = fields.Datetime(string='Fecha', readonly=True)
    asset_id = fields.Many2one('account.asset.asset', string='Activo', readonly=True)
    type = fields.Selection([('deterioro','Deterioro'),('recuperar','Recuperar')], string='Tipo', required=True)
    recuperado = fields.Boolean(string='Ejecutado', readonly=True)
    move_id = fields.Many2one('account.move', string="Asiento", readonly=True)
    date = fields.Date(string="Fecha", required=True)
    state = fields.Char(string='Estado', compute="_state", store=True, readonly=True)
    
                            
    
    @api.multi
    def calcular(self):
        orm2sql = self.pool.get('avancys.orm2sql')
        
        if not self.asset_id.state == 'open':
            raise osv.except_osv(_('Error!'),_("Operacion no valida, el activo debe estar en ejecuccion para poder realizar este tipo de proceso"))
        
        if self.cost_realy <= 0.0:
            raise osv.except_osv(_('Error!'),_("El precio de venta del activo no puede ser menor o igual a cero"))
        
        if self.cost <= 0.0 and self.type != "valorizacion":
            raise osv.except_osv(_('Error!'),_("Operacion no valida, no tiene valor por afectar"))
        
        company_id = self.asset_id.company_id
        date = self.date
        
        name_move = self.asset_id.name+' / '+str(self.type)+' / '+ str(date)
        ref = str(self.type)
        value=self.value
        amount = abs(self.value)
        analytic_account_id = self.asset_id.centrocosto_id and self.asset_id.centrocosto_id.id or False
        valorizacion=0.0
        
        if not company_id:
            raise osv.except_osv(_('Error!'),_("El activo no tiene una compañia seleccionada"))
        
        period_id = self.env['account.period'].search([('company_id','<=',company_id.id),('date_start','<=',date),('date_stop','>=',date)])
        if not period_id:
            raise osv.except_osv(_('Error!'),_("No existe un periodo defino para la fecha de la depreciacion"))
        
        account_analytic_id = self.asset_id.centrocosto_id and self.asset_id.centrocosto_id.id or False
        
        journal_id = self.asset_id.category_id and self.asset_id.category_id.journal_niff_deterioro or False
        if not journal_id:
            raise osv.except_osv(_('Error!'),_("Por favor configurar el diario de deterioro en la categoria del activo"))
        
        name = self.pool.get('ir.sequence').next_by_id(self._cr, self._uid, self.asset_id.category_id.journal_niff_deterioro.sequence_id.id, context=self._context)
        
        move_vals = {
            'name': name,
            'ref': ref,
            'journal_id': journal_id.id,
            'date': date,
            'period_id': period_id.id,
            'company': company_id.id,
            }
        move_id = self.env['account.move'].create(move_vals)
        
        if self.type == 'recuperar':
            account_debit_id = self.asset_id.category_id.account_recuperacion and self.asset_id.category_id.account_recuperacion.id or False            
            if not account_debit_id:
                raise osv.except_osv(_('Error!'),_("Para realizar esta operacion, debe configurar la cuenta de recuperacion en la categoria '%s'") % (self.asset_id.category_id.name))
            
            account_credit_id = self.asset_id.category_id.account_recuperacion_ingreso and self.asset_id.category_id.account_recuperacion_ingreso.id or False            
            if not account_credit_id:
                raise osv.except_osv(_('Error!'),_("Para realizar esta operacion, debe configurar la cuenta de ingresos por recuperacion del deterioro en la categoria '%s'") % (self.asset_id.category_id.name)) 
                
            if self.asset_id.category_id.model_method == 'costo':      
                if not self.asset_id.amount_deterioro > abs(self.value):
                    raise osv.except_osv(_('Error!'),_("El monto que intenta recuperar es $ %s y por polica de la compañia esta restringido hasta $ %s. El maximo valor que se puede asignar al 'Valor Razonables' es $ %s. Por favor verifique los mosntos asignados o consulte con el area responsable.") % (locale.format('%.2f', self.value, True), locale.format('%.2f', self.asset_id.amount_deterioro, True), locale.format('%.2f', self.cost, True)))                
            else:
                if self.valorizacion > 0.0:
                    value=-self.asset_id.amount_deterioro
                    
                    
                    account_activacion = self.asset_id.category_id.account_asset_nif_property and self.asset_id.category_id.account_asset_nif_property.id or False
                    if not account_activacion:
                        raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de activacion en la categoria '%s'") % self.asset_id.category_id.name)
                        
                        
                    amount_depreciacion = 0.0
                    for l in self.asset_id.depreciation_line_nif_ids:
                        if l.move_id and not l.valorizado_id:
                            amount_depreciacion += l.amount
                            l.valorizado_id = self.id
                    
                    
                    if amount_depreciacion:                        
                        account_depreciation_id = self.asset_id.category_id.account_depreciation_nif_property and self.asset_id.category_id.account_depreciation_nif_property.id or False
                        if not account_depreciation_id:
                            raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de depreciacion contable de la categoria '%s'") % self.asset_id.category_id.name)
                        
                        
            
                        line = [{'name': name_move,
                                'ref': name,
                                'ref1': 'Reversion Depreciacion',
                                'move_id': move_id.id,
                                'account_id': account_depreciation_id,
                                'debit': amount_depreciacion,
                                'credit': 0.0,
                                'period_id': period_id.id,
                                'journal_id': journal_id.id,
                                'partner_id': company_id.id,
                                'analytic_account_id': account_analytic_id,
                                'date': str(date),
                                'asset_id': self.asset_id.id,
                                'state': 'valid',
                                }]
                        orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
                        
                        line = [{'name': name_move,                                 
                                'ref': name,
                                'ref1': 'Reversion Depreciacion',
                                'ref2': 'PP&Y',
                                'move_id': move_id.id,
                                'account_id': account_activacion,
                                'debit': 0.0,
                                'credit': amount_depreciacion,
                                'period_id': period_id.id,
                                'journal_id': journal_id.id,
                                'partner_id': company_id.id,
                                'analytic_account_id': account_analytic_id,
                                'date': str(date),
                                'asset_id': self.asset_id.id,
                                'state': 'valid',
                                }]                        
                        orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
                    
                    
                    account_superavit_id = self.asset_id.category_id.account_superavit_id and self.asset_id.category_id.account_superavit_id.id or False
                    if not account_superavit_id:
                        raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta 'Cuenta de Superavit' en la categoria '%s'") % self.asset_id.category_id.name)
                    
        
                    line = [{'name': name_move,
                            'ref': name,
                            'ref1': 'Valorizacion',
                            'move_id': move_id.id,
                            'account_id': account_activacion,
                            'debit': self.valorizacion,
                            'credit': 0.0,
                            'period_id': period_id.id,
                            'journal_id': journal_id.id,
                            'partner_id': company_id.id,
                            'analytic_account_id': account_analytic_id,
                            'date': str(date),
                            'asset_id': self.asset_id.id,
                            'state': 'valid',
                            }]
                    orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
                    
                    line = [{'name': name_move,                                 
                            'ref': name,
                            'ref1': 'Valorizacion',
                            'move_id': move_id.id,
                            'account_id': account_superavit_id,
                            'debit': 0.0,
                            'credit': self.valorizacion,
                            'period_id': period_id.id,
                            'journal_id': journal_id.id,
                            'partner_id': company_id.id,
                            'analytic_account_id': account_analytic_id,
                            'date': str(date),
                            'asset_id': self.asset_id.id,
                            'state': 'valid',
                            }]                        
                    orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
                    
                    amount = abs(self.asset_id.amount_deterioro)
                    #orm2sql.sqlupdate(cr, 'account_asset_asset', {'amount_depreciado': self.asset_id.amount_depreciado-line.amount}, ('id', self.asset_id.id))
                    
                    
        else:
            
            account_debit_id = self.asset_id.category_id.account_deterioro_gasto and self.asset_id.category_id.account_deterioro_gasto.id or False            
            if not account_debit_id:
                raise osv.except_osv(_('Error!'),_("Para realizar esta operacion, debe configurar la cuenta de gastos por deterioro en la categoria '%s'") % (self.asset_id.category_id.name))
            
            account_credit_id = self.asset_id.category_id.account_deterioro and self.asset_id.category_id.account_deterioro.id or False            
            if not account_credit_id:
                raise osv.except_osv(_('Error!'),_("Para realizar esta operacion, debe configurar la cuenta de deterioro en la categoria '%s'") % (self.asset_id.category_id.name))
            
            if self.valorizacion < 0:
                account_activacion = self.asset_id.category_id.account_asset_nif_property and self.asset_id.category_id.account_asset_nif_property.id or False
                if not account_activacion:
                    raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta de activacion en la categoria '%s'") % self.asset_id.category_id.name)
                    
                account_superavit_id = self.asset_id.category_id.account_superavit_id and self.asset_id.category_id.account_superavit_id.id or False
                if not account_superavit_id:
                    raise osv.except_osv(_('Error !'), _("Por favor configurar la cuenta 'Cuenta de Superavit' en la categoria '%s'") % self.asset_id.category_id.name)
                
    
                line = [{'name': name_move,
                        'ref': name,
                        'ref1': 'Reversion Valorizacion',
                        'move_id': move_id.id,
                        'account_id': account_activacion,
                        'debit': 0.0,
                        'credit': abs(self.valorizacion),
                        'period_id': period_id.id,
                        'journal_id': journal_id.id,
                        'partner_id': company_id.id,
                        'analytic_account_id': account_analytic_id,
                        'date': str(date),
                        'asset_id': self.asset_id.id,
                        'state': 'valid',
                        }]
                orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
                
                line = [{'name': name_move,                                 
                        'ref': name,
                        'ref1': 'Reversion Valorizacion',
                        'move_id': move_id.id,
                        'account_id': account_superavit_id,
                        'debit': abs(self.valorizacion),
                        'credit': 0.0,
                        'period_id': period_id.id,
                        'journal_id': journal_id.id,
                        'partner_id': company_id.id,
                        'analytic_account_id': account_analytic_id,
                        'date': str(date),
                        'asset_id': self.asset_id.id,
                        'state': 'valid',
                        }]                        
                orm2sql.sqlcreate(self._uid, self._cr, 'account_move_line', line, company=True, commit=False)
            
            
        #print "wwwwwwww  DEBITO wwwwwwwwwww"
        self._cr.execute('''INSERT INTO account_move_line (account_id,account_niif_id,date,ref,name,create_date,partner_id,credit,debit,analytic_account_id,move_id,journal_id,period_id,company_id,state) VALUES 
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
        (account_debit_id,account_debit_id,date,name,ref,date,company_id.id,0.0,amount,analytic_account_id or None, move_id.id, journal_id.id, period_id.id,company_id.id,'valid'))
        
        #print "wwwwwwww  CREDITO wwwwwwwwwww"
        self._cr.execute('''INSERT INTO account_move_line (account_id,account_niif_id,date,ref,name,create_date,partner_id,credit,debit,analytic_account_id,move_id,journal_id,period_id,company_id,state) VALUES 
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''' ,
        (account_credit_id,account_credit_id,date,name,ref,date,company_id.id,amount,0.0,analytic_account_id or None,move_id.id, journal_id.id, period_id.id,company_id.id,'valid'))
                        
            
        move_id.post()
        self.asset_id.amount_deterioro = self.asset_id.amount_deterioro + value
        self.asset_id.amount_valorizacion = self.asset_id.amount_valorizacion + self.valorizacion
        self.asset_id.compute_depreciation_board_niff()
        return self.write({'recuperado':True, 'move_id': move_id.id})
    
    @api.multi
    def cancelar(self):
        if self.move_id:
            self.move_id.button_cancel()
            self.move_id.unlink()            
        self.asset_id.amount_deterioro = self.asset_id.amount_deterioro - self.value
        self.asset_id.amount_valorizacion = self.asset_id.amount_valorizacion - self.valorizacion
        self._cr.execute(''' UPDATE account_asset_depreciation_line SET valorizado_id=%s WHERE valorizado_id = %s''',(None, self.id,))        
        self.asset_id.compute_depreciation_board_niff()
        return self.write({'recuperado':False})
 
 
class account_asset_asset(models.Model):
    _inherit = "account.asset.asset"
    
    @api.one
    @api.depends('depreciation_line_nif_ids.move_id','value_to_depreciate_niif','amount_depreciado')
    def _amount_niff(self):
        amount = self.value_to_depreciate_niif
        if self.depreciation_line_nif_ids:            
            for line in self.depreciation_line_nif_ids:
                if line.move_id:
                    amount-=line.amount
        self.amount_residual_niif = amount + self.salvage_value_niif
        
    @api.one
    @api.depends('purchase_value_niif','salvage_value_niif','amount_deterioro','amount_valorizacion')
    def _amount_depreciar(self):
        self.value_to_depreciate_niif = self.purchase_value_niif - self.salvage_value_niif - self.amount_deterioro + self.amount_valorizacion
    
    depreciation_date = fields.Date('Fecha de depreciaciòn', readonly=True, states={'draft':[('readonly',False)]})
    purchase_value_niif = fields.Float(string="Valor bruto", digits=dp.get_precision('Account'), readonly=True, states={'draft':[('readonly',False)]})
    salvage_value_niif = fields.Float(string="Valor salvaguarda", digits=dp.get_precision('Account'), readonly=True,
                                      states={'draft':[('readonly',False)]})
    value_to_depreciate_niif = fields.Float(string="Valor a depreciar", digits=dp.get_precision('Account'), compute="_amount_depreciar", store=True)
    deterioro_id = fields.One2many('account.asset.deterioro', 'asset_id', string='Deterioro')    
    depreciation_line_nif_ids = fields.One2many('account.asset.depreciation.line', 'asset_id2', string='TABLA DEPRECIACION NIIF', readonly=True, states={'draft':[('readonly',False)],'open':[('readonly',False)]})
    depreciation_line_ids = fields.One2many('account.asset.depreciation.line', 'asset_id', string='TABLA DEPRECIACION', readonly=True, states={'draft':[('readonly',False)],'open':[('readonly',False)]})
    nif_method = fields.Selection([('lineal', 'Lineal'), ('reduction', 'Reducción de Saldos')], 'Metodo de Calculo',
                                  required=True, readonly=True, states={'draft': [('readonly', False)]})
    nif_method_number = fields.Integer(string='Numero de depreciaciones', readonly=True,
                                       states={'draft': [('readonly', False)]})
    nif_method_period = fields.Integer(string='Numero de meses en un periodo', readonly=True, states={'draft':[('readonly',False)]})
    nif_method_time = fields.Selection([('number', 'Numero de Depreciaciones'), ('end', 'Fecha Final')],
                                       string='Metodo de Tiempo',  required=True, readonly=True,
                                       states={'draft': [('readonly', False)]})
    nif_method_end = fields.Date(string='Fecha Final', readonly=True, states={'draft':[('readonly', False)]})
    nif_prorata = fields.Boolean(string='Tiempo Prorrateo', readonly=True, states={'draft': [('readonly', False)]})
    amount_residual_niif = fields.Float(string="Valor Libro Contable", digits=dp.get_precision('Account'),
                                        compute="_amount_niff", store=True)
    amount_deterioro = fields.Float(string="Deterioro", digits=dp.get_precision('Account'), readonly=True)
    amount_valorizacion = fields.Float(string="Valorizacion", digits=dp.get_precision('Account'), readonly=True)
    amount_depreciado = fields.Float(string="Depreciacion", digits=dp.get_precision('Account'), readonly=True)
    period_prorate_niif = fields.Integer(string='Desfase Periodo Inicial', help='El desfaz de periodo es un numero que se le sumara a la fecha de compra del activo, el resultado indica la fecha inicial de depreciacion del activo', readonly=True, states={'draft': [('readonly', False)]}, default=1)

    def validate(self, cr, uid, ids, context=None):
        if context is None:
            context = {}            
        cr.execute(''' UPDATE account_asset_depreciation_line SET state='open' WHERE asset_id2 = %s''',(ids[0],))
        return self.write(cr, uid, ids, {
            'state':'open'
        }, context)

    @api.model
    def create(self, vals):
        vals.update({'nif_method_time':'number', 'nif_method':'lineal', 'asset_type':'fixed'})
        if 'centrocosto_id' in vals and not vals['centrocosto_id']:
            raise Warning('No se ha definido un centro de costo en alguna de las lineas de la factura')
        res = super(account_asset_asset, self).create(vals)
        res.write({'period_prorate_niif': res.category_id.period_prorate,
                   'purchase_value_niif':  res.value_to_depreciate,
                   'nif_method_number': res.category_id.nif_method_number if not res.nif_method_number else res.nif_method_number,
                   'nif_method_period': res.method_period,
                   'nif_prorata': res.prorata})
        res.compute_depreciation_board_niff()
        return res
    
    def open_entries(self, cr, uid, ids, context=None):        
        context = dict(context or {})
        inv=[]
        for asset in self.browse(cr, uid, ids, context=context):
            for move in asset.depreciation_line_ids:
                if move.move_id:
                    inv.append(move.move_id.id)
            for move in asset.depreciation_line_nif_ids:
                if move.move_id:
                    inv.append(move.move_id.id)
            for move in asset.deterioro_id:
                if move.move_id:
                    inv.append(move.move_id.id)
                    
        domain = [('id','in',inv)]
        return {
            'domain':domain,
            'name': _('Journal Items'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': context,
        }
       
    @api.onchange('nif_method_time')
    def _get_method_time(self):
        if self.nif_method_time == 'number':
            self.nif_prorata = False
          
    
    def _compute_entries(self, cr, uid, ids, period_id, context=None):
        result = []
        period_obj = self.pool.get('account.period')
        depreciation_obj = self.pool.get('account.asset.depreciation.line')
        period = period_obj.browse(cr, uid, period_id, context=context)
        if context.get('type_plan' or False) == 'colgaap':
            depreciation_ids = depreciation_obj.search(cr, uid, [('asset_id', 'in', ids), ('depreciation_date', '<=', period.date_stop), ('depreciation_date', '>=', period.date_start), ('move_id', '=', False), ('state', '=', 'open')], context=context)
        elif context.get('type_plan' or False) == 'niif':
            depreciation_ids = depreciation_obj.search(cr, uid, [('asset_id2', 'in', ids), ('depreciation_date', '<=', period.date_stop), ('depreciation_date', '>=', period.date_start), ('move_id', '=', False), ('state', '=', 'open')], context=context)
        else:
            depreciation_ids = depreciation_obj.search(cr, uid, ['|',('asset_id', 'in', ids),('asset_id2', 'in', ids), ('depreciation_date', '<=', period.date_stop), ('depreciation_date', '>=', period.date_start), ('move_id', '=', False), ('state', '=', 'open')], context=context)
        
        context = dict(context or {}, depreciation_date=period.date_stop)
        res = depreciation_obj.create_move(cr, uid, depreciation_ids, context=context)
        return  res
        
    
    #copia 07/04 de account_asset_asset con cuentas y parametros modificados
    def _compute_board_undone_dotation_nb_nif(self, cr, uid, asset, depreciation_date, total_days, context=None):
        undone_dotation_number = asset.nif_method_number
        if asset.nif_method_time == 'end':
            end_date = datetime.strptime(asset.nif_method_end, '%Y-%m-%d')
            undone_dotation_number = 0
            while depreciation_date <= end_date:
                depreciation_date = (datetime(depreciation_date.year, depreciation_date.month, depreciation_date.day) + relativedelta(months=+asset.nif_method_period))
                undone_dotation_number += 1
        if asset.nif_prorata:
            undone_dotation_number += 1
        return undone_dotation_number

    def _compute_board_amount_nif(self, cr, uid, asset, i, residual_amount, amount_to_depr, undone_dotation_number,
                                  posted_depreciation_line_ids, total_days, depreciation_date, context=None):
        amount = 0
        if i == undone_dotation_number:
            amount = residual_amount
        else:
            if asset.nif_method == 'lineal':
                amount = amount_to_depr / (undone_dotation_number - len(posted_depreciation_line_ids))
            elif asset.nif_method == 'reduction':
                reduc_factor = 1 - pow(asset.salvage_value_niif / asset.purchase_value_niif,
                                       1.0 / asset.nif_method_number)
                amount = (asset.salvage_value_niif + residual_amount) * reduc_factor
                if asset.prorata:
                    days = total_days - float(depreciation_date.strftime('%j'))
                    if i == 1:
                        amount = amount / total_days * days
                    elif i == undone_dotation_number:
                        amount = amount / total_days * (total_days - days)
        return amount
    
    #copia 07/04 de account_asset_extended con cuentas y parametros modificados
    def compute_depreciation_board_niff(self, cr, uid, ids, context=None):
        depreciation_lin_obj = self.pool.get('account.asset.depreciation.line')
        currency_obj = self.pool.get('res.currency')
        for asset in self.browse(cr, uid, ids, context=context):
            if asset.amount_residual_niif == 0.0:
                continue
            posted_depreciation_line_ids = depreciation_lin_obj.search(cr, uid, [('asset_id2', '=', asset.id), ('move_id', '!=', False)],order='depreciation_date desc')
            old_depreciation_line_ids = depreciation_lin_obj.search(cr, uid, [('asset_id2', '=', asset.id), ('move_id', '=', False)])
            if old_depreciation_line_ids:
                depreciation_lin_obj.unlink(cr, uid, old_depreciation_line_ids, context=context)

            amount_to_depr = residual_amount = asset.amount_residual_niif - asset.salvage_value_niif
            
            if asset.nif_prorata:
                if (len(posted_depreciation_line_ids)>0):
                    last_depreciation_date = datetime.strptime(depreciation_lin_obj.browse(cr,uid,posted_depreciation_line_ids[0],context=context).depreciation_date, '%Y-%m-%d')
                    depreciation_date = (last_depreciation_date+relativedelta(months=+asset.nif_method_period))
                else:
                    #depreciation_date = datetime.strptime(self._get_last_depreciation_date(cr, uid, [asset.id], context)[asset.id], '%Y-%m-%d')
                    purchase_date = datetime.strptime(asset.purchase_date, '%Y-%m-%d')
                    if asset.depreciation_date:
                        depreciation_date = (datetime.strptime(asset.depreciation_date, DEFAULT_SERVER_DATE_FORMAT) + relativedelta(months=+asset.period_prorate_niif))
                        
                    else:
                        depreciation_date = datetime.strptime(asset.purchase_date, '%Y-%m-%d') + relativedelta(months=+asset.period_prorate_niif)
                    
            else:
                # depreciation_date = 1st January of purchase year
                purchase_date = datetime.strptime(asset.purchase_date, '%Y-%m-%d')
                if asset.depreciation_date:
                    depreciation_date = datetime.strptime(asset.depreciation_date, '%Y-%m-%d')
                #if we already have some previous validated entries, starting date isn't 1st January but last entry + method period
                if (len(posted_depreciation_line_ids)>0):
                    
                    last_depreciation_date = datetime.strptime(depreciation_lin_obj.browse(cr,uid,posted_depreciation_line_ids[0],context=context).depreciation_date, '%Y-%m-%d')
                    depreciation_date = (last_depreciation_date+relativedelta(months=+asset.nif_method_period))
                else:
                    if asset.depreciation_date:
                        depreciation_date = datetime(depreciation_date.year, 1, 1)
                    else:
                        depreciation_date = datetime(purchase_date.year, 1, 1)
            
            date_depreciation=depreciation_date
            year = depreciation_date.year
            
            total_days = (year % 4) and 365 or 366
            undone_dotation_number = self._compute_board_undone_dotation_nb_nif(cr, uid, asset, depreciation_date, total_days, context=context)
                        
            if len(posted_depreciation_line_ids) > asset.nif_method_number:
                raise osv.except_osv(_('Error!'),_("Operacion no valida, el numero de depreciaciones no puede superar las depreciaciones ya contabiliazadas"))
            undone_dotation_number -= 1#FR
            
            orm2sql = self.pool.get('avancys.orm2sql')
            vals = []
            y=0
            
            valorizacion=0.0
            valorizado=0.0
            
            pendientes = asset.nif_method_number - len(posted_depreciation_line_ids)
            
            if asset.amount_valorizacion > 0.0 and pendientes > 0.0:
                valorizacion=asset.amount_valorizacion/pendientes
            
            
            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                i = x + 1
                
                amount = self._compute_board_amount_nif(cr, uid, asset, i, residual_amount, amount_to_depr, undone_dotation_number, posted_depreciation_line_ids, total_days, depreciation_date, context=context)
                #company_currency = asset.company_id.currency_id.id
                current_currency = asset.currency_id.id
                # redondea para la moneda seleccionada
                amount = currency_obj.compute(cr, uid, current_currency, current_currency, amount, context=context)
                residual_amount -= amount
                
                if y+1 == pendientes:
                    valorizacion=asset.amount_valorizacion-valorizado
                else:
                    valorizado+=valorizacion
                
                fecha = date_depreciation + relativedelta(months=+asset.nif_method_period*y)
                vals = [{
                     'amount': amount,
                     'asset_id2': asset.id,
                     'sequence': i,
                     'name': str(asset.id) +'/' + str(i),
                     'remaining_value': residual_amount + asset.salvage_value_niif,
                     'remaining_value_end': residual_amount + asset.salvage_value_niif + amount,
                     'amount_valorizado': valorizacion,
                     'depreciated_value': (asset.purchase_value_niif - asset.salvage_value_niif) - (residual_amount + amount),
                     'depreciation_date': str(fecha.date()),
                     'state': 'open',
                }]
                y += 1
                # depreciation_lin_obj.create(cr, uid, vals, context=context)
                # Considering Depr. Period as months
                #date_depreciation = (date_depreciation) + relativedelta(months=+asset.nif_method_period))
                orm2sql.sqlcreate(uid, cr, 'account_asset_depreciation_line', vals, company=False)
        return True


class compute_depreciation_tables_wiz(models.TransientModel):
    _name = 'compute.depreciation.tables.wiz'

    @api.multi
    def calcular_tablas(self):

        orm2sql = self.env['avancys.orm2sql']
        asset_obj = self._context.get('active_ids', [])
        asset_obj = self.env['account.asset.asset'].browse(
            asset_obj)
        i, l = 0, len(asset_obj)
        print "Procesando %s activos" % l
        orm2sql.printProgressBar(i, l)
        for asset in asset_obj:
            if asset.state == 'open':
                raise Warning('Esta intentando calcular la tabla de un activo en ejecucion')
            i += 1
            orm2sql.printProgressBar(i, l)
        i, l = 0, len(asset_obj)
        print "Recorriendo %s activos" % l
        orm2sql.printProgressBar(i, l)
        for asset in asset_obj:
            i += 1
            orm2sql.printProgressBar(i, l)
            asset.compute_depreciation_board()
            asset.compute_depreciation_board_niff()
            orm2sql.sqlupdate('account_asset_asset', {'state': 'open'}, ('id', asset.id))
        return True
