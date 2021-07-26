# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2014 Avancys SAS
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

from openerp.osv import osv, fields
from openerp.tools.translate import _
from openerp import netsvc

class confirm_quote_wiz(osv.TransientModel):
    
    _name = 'confirm.quote.wiz'
    
    def confirm_multi_quote(self, cr, uid, ids, context=None):
        if not context : context={}
        for id in context['active_ids']:
            wf_service = netsvc.LocalService('workflow')
            wf_service.trg_validate(uid, 'sale.order', id, 'order_confirm', cr)
        domain = [('id', 'in', context['active_ids'])]
        return {
              'name': _('Confirmed Order'),
              'view_type': 'form',
              "view_mode": 'tree,form',
              'res_model': 'sale.order',
              'type': 'ir.actions.act_window',
              'domain': domain,
              'context': context,
        }
    
confirm_quote_wiz()