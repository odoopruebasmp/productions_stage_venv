# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api
from openerp.tools import float_compare, float_round
from openerp.tools.translate import _
from openerp import SUPERUSER_ID, api
from datetime import datetime

class stock_inventory_invoice(models.Model):
    _inherit = 'stock.inventory'
        
    account_invoice_id=fields.Many2one('account.invoice', 'Factura', readonly=True)
    
    @api.multi
    def create_invoice(self,line_ids):
        vals = {
            'comment': self.name or '',
            'user_id': self.create_uid.id,
            'origin': self.name,
            'internal_number': self.name,      
            'name': self.name, 
            'display_name': self.name,                                
            'company_id': self.company_id.id,
            'partner_id': self.partner_id2.id,
            'fiscal_position': self.partner_id2.property_account_position.id,
            'payment_term': self.partner_id2.property_payment_term.id or None,
            'partner_shipping_id': self.partner_id2.id,
            'journal_id': self.journal_id.id,
            'account_id': self.account_transaction_in_id.id,
            'currency_id': self.company_id.currency_id.id,
            'type': 'out_invoice',
            'date_invoice': self.date,
            'state': 'paid',
            'period_id': self.period_id.id,            
            }
            
        invoice_id = self.env['account.invoice'].create(vals)
                
        self.account_invoice_id=invoice_id

        
        for move in self.move_ids:
            lines = {
                'name': move.product_id.display_name,            
                'product_id': move.product_id.id, 
                'quantity': move.product_uos_qty,                            
                'cost_file': move.cost,
                'cost': move.cost,                                
                'user_id': self.create_uid.id,
                'account_id': self.account_transaction_in_id.id,
                'currency_id': self.company_id.currency_id.id,
                'type': 'out_invoice',
                'date': self.date,
                'invoice_id': invoice_id.id,
                'state': 'paid',
                }

            self.env['account.invoice.line'].create(lines)

    @api.multi
    def deletebdinvoice(self):
        self.account_invoice_id._cr.execute("delete from account_invoice where id={id}".format(id=self.account_invoice_id.id))

        return True           
