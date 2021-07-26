# -*- coding: utf-8 -*-
from openerp import models, fields
import pytz
import re
import time
import openerp
import openerp.service.report
import uuid
import collections
import babel.dates
from werkzeug.exceptions import BadRequest
from datetime import datetime, timedelta
from dateutil import parser
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from openerp import api
from openerp import tools, SUPERUSER_ID
from openerp.osv import fields as fields2, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _
from openerp.http import request
from operator import itemgetter
import openerp.addons.decimal_precision as dp
import locale
from openerp.addons.avancys_tools import report_tools
from openerp.addons.edi import EDIMixin


class payment_order(osv.osv, EDIMixin):
    _name = "payment.order"
    _inherit = ['payment.order', 'mail.thread', 'ir.needaction_mixin']
    
    def action_send(self, cr, uid, ids, context=None):
        user_id = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        headers = dict(request.httprequest.__dict__.get('headers'))
        lines=False
        
        if headers.get('Host', False):
            host=headers.get('Host')+'/logo.png'
            lines='<img class="img-responsive" src="http://'+host+'"/>'   
            
        dir={}
        voucher_id = self.browse(cr, uid, ids, context=context)
        
        for voucher in self.browse(cr, uid, ids, context=context):
            for line in voucher.line_ids:                
                key=(line.partner_id.id)
                if key in dir:
                    dir[key].update({'amount': dir[key]['amount']+line.amount_currency})
                else:
                    dir[key]={'amount': line.amount_currency, 'partner_name':line.partner_id.name, 'lang': line.partner_id.lang, 'partner_id': line.partner_id.id}
            
        for line in dir.values():
            date= voucher_id.payment_order_date
            reference=voucher_id.reference
            amount=locale.format('%.2f', line['amount'], True)
            amount_text=' '
            amount_text=report_tools.avancys_amount_to_text_decimal(line['amount'], line['lang'])  
            body ='<html><body>'            
            body+='<div align="right">'             
            body+='<div align="right">'
            body+='<p align="right">'
            body+='<img  class="img-responsive" src="http://www.avancys.com/logo.png" alt="" style="height:100px"/>'                 
            body+='</p>'
            body+='</div>'
            body+='<div align="right">'
            body+='By ERP <a href="http://www.avancys.com">'+ 'Avancys' +'</a>'
            body+='</div>'
            body+='</div>'
            if lines:
                body+='<p>'
                body+='<center>'
                body+=lines                                              
                body+='</center>'
                body+='</p>'
            body+='<p>'
            body+='<center>'
            body+='<strong><font size=5> NOTIFICACION DE PAGO </font></strong>'                                                
            body+='</center>'
            body+='</p>'   
            body+='<br/>'
            body+='<p><justify>Apreciados <strong>'+line['partner_name']+'</strong> un cordial saludo, con el presente se busca confirmar el pago realizado con referencia <strong>'+ reference +'</strong> por un valor de <strong> $ '+ str(amount) +' "('+ amount_text +')"</strong> con fecha <strong>'+ str(date)+'</strong> .</p>'                
            body+='</justify><p>'
            body+='<p><justify>A continuacion podra encontrar informacion mas detallada del pago.</p>'
            body+='</p>'
            body+='<center>' 
            body+="""<table border="1" style="width: 800px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat;">"""        
            body+='<tr>'
            body+='<th colspan="10" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">INFORMACION DE PAGO</th>'
            body+='</tr>'
            body+='<tr>'
            body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">FECHA</th>'
            body+='<th colspan="1" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">REFERENCIA</th>'
            body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">V. INICIAL</th>'
            body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">V. SALDO</th>'
            body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">V. PAGADO</th>'
            body+='</tr>'
            for pago in voucher_id.line_ids.filtered(lambda x: x.partner_id.id == line['partner_id']):
                amount_unreconciled=locale.format('%.2f', pago.amount_currency, True)
                amount_pago=locale.format('%.2f', pago.amount_currency, True)
                amount_original=locale.format('%.2f', pago.move_line_id.debit + pago.move_line_id.credit, True)   
                
                body+='<tr>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(pago.move_line_id.date) +'</th>'
                body+='<th colspan="1" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ pago.name +'</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(amount_original) +'</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(amount_unreconciled) +'</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(amount_pago) +'</th>'
                body+='</tr>'                
            body+='</table>'
            body+='<br/>'    
            body+='<br/>'                 
            body+='<div style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat;">'
            body+='<h3 style="margin: 0px; padding: 2px 14px; font-size: 15px; color: #FFF;">'
            body+='<strong style="text-transform:uppercase;">'+voucher_id.company_id.name+'</strong>'
            body+='</h3>'        
            body+='</div>'
            body+="""<div style="width: 347px; margin: 0px; padding: 5px 14px; line-height: 16px; background-color: #F2F2F2;">
                <span style="color: #222; margin-bottom: 5px; display: block; ">"""
            body+=voucher_id.company_id.street +'<br/>'
            body+=voucher_id.company_id.country_id.name +'-'+ voucher_id.company_id.partner_id.city_id.name +'<br/>'
            body+='</span>'
            body+='<div style="margin-top: 0px; margin-right: 0px; margin-bottom: 0px; margin-left: 0px; padding-top: 0px; padding-right: 0px; padding-bottom: 0px; padding-left: 0px; ">'
            body+='Telefono:&nbsp;'+voucher_id.company_id.phone
            body+='</div>'
            body+='<div>'
            body+='Web :&nbsp;<a href="'+ voucher_id.company_id.website +'">'+ voucher_id.company_id.website +'</a>'
            body+='</div>'
            body+='<p></p>'
            body+='</div>'
            body+='</center>'
            body +='</body></html>'        
            
            vals = {
                'email_from': user_id.name+' '+user_id.email,
                'email_to': line['partner_name'],
                'state': 'outgoing',
                'subject': 'Notifiacion de Pago'+' '+voucher_id.display_name,
                'body_html': body,
                'type':'email',
                'auto_delete': False,
                'notification': True,
                'recipient_ids': [(6, 0, [line['partner_id']])]
                }               
                
                
            mail=self.pool.get('mail.mail').create(cr, uid, vals, context=context)
            self.pool.get('mail.mail').send(cr, uid, mail, context=context)
        return True
    
    
    
class account_voucher(models.Model):
    _inherit = 'account.voucher'
    
    account_amount_ids = fields.One2many('account.distribution.amount', 'voucher_id', string='Account Distributions')
    diferencia = fields.Float(string='Diferencia', digits= dp.get_precision('Account'), readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Cuenta Analitica')
    
        
    def action_send(self, cr, uid, ids, context=None):
        user_id = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        headers = dict(request.httprequest.__dict__.get('headers'))
        line=False
        
        if headers.get('Host', False):
            host=headers.get('Host')+'/logo.png'
            line='<img class="img-responsive" src="http://'+host+'"/>'        
        for voucher in self.browse(cr, uid, ids, context=context):
            reference=voucher.reference or voucher.display_name
            amount=locale.format('%.2f', voucher.amount, True)
            amount_text=' '
            amount_text=report_tools.avancys_amount_to_text_decimal(voucher.amount, voucher.partner_id.lang)  
            body ='<html><body>'            
            body+='<div align="right">'             
            body+='<div align="right">'
            body+='<p align="right">'
            body+='<img  class="img-responsive" src="http://www.avancys.com/logo.png" alt="" style="height:100px"/>'                 
            body+='</p>'
            body+='</div>'
            body+='<div align="right">'
            body+='By ERP <a href="http://www.avancys.com">'+ 'Avancys' +'</a>'
            body+='</div>'
            body+='</div>'
            
            if line:
                body+='<p>'
                body+='<center>'
                body+=line                                              
                body+='</center>'
                body+='</p>'
            body+='<p>'
            body+='<center>'
            body+='<strong><font size=5> NOTIFICACION DE PAGO </font></strong>'                                                
            body+='</center>'
            body+='</p>'   
            body+='<br/>'
            body+='<p><justify>Apreciados <strong>'+voucher.partner_id.name+'</strong> un cordial saludo, con el presente se busca confirmar el pago realizado con referencia <strong>'+ reference +'</strong> por un valor de <strong> $ '+ str(amount) +' "('+ amount_text +')"</strong> con fecha <strong>'+ str(voucher.date)+'</strong> .</p>'                
            body+='</justify><p>'
            body+='<p><justify>A continuacion podra encontrar informacion mas detallada del pago.</p>'
            body+='</p>'
            body+='<center>' 
            body+="""<table border="1" style="width: 800px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat;">"""        
            body+='<tr>'
            body+='<th colspan="10" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">INFORMACION DE PAGO</th>'
            body+='</tr>'
            body+='<tr>'
            body+='<th colspan="1" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">TIPO</th>'
            body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">FECHA</th>'
            body+='<th colspan="1" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">REFERENCIA</th>'
            body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">V. INICIAL</th>'
            body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">V. SALDO</th>'
            body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #FFF;">V. PAGADO</th>'
            body+='</tr>'
            for pago in voucher.line_dr_ids.filtered(lambda x: x.amount > 0.0 or x.reconcile == True):
                amount_unreconciled=locale.format('%.2f', pago.amount_unreconciled, True)
                amount_pago=locale.format('%.2f', pago.amount, True)
                amount_original=locale.format('%.2f', pago.amount_original, True)   
                
                body+='<tr>'
                body+='<th colspan="1" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">A PAGAR</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(pago.date_original) +'</th>'
                body+='<th colspan="1" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ pago.move_line_id.display_name +'</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(amount_original) +'</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(amount_unreconciled) +'</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(amount_pago) +'</th>'
                body+='</tr>'
                
            for cobro in voucher.line_cr_ids.filtered(lambda x: x.amount > 0.0 or x.reconcile == True):
                amount_unreconciled=locale.format('%.2f', cobro.amount_unreconciled, True)
                amount_pago=locale.format('%.2f', cobro.amount, True)
                amount_original=locale.format('%.2f', cobro.amount_original, True)      
                
                body+='<tr>'
                body+='<th colspan="1" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">A COBRAR</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(cobro.date_original) +'</th>'
                body+='<th colspan="1" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ cobro.move_line_id.display_name +'</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(amount_original) +'</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(amount_unreconciled) +'</th>'
                body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(amount_pago) +'</th>'
                body+='</tr>'
            if voucher.payment_option == 'with_writeoff':
                for diff in voucher.account_amount_ids:
                    amount_pago=locale.format('%.2f', diff.amount, True)                         
                    body+='<tr>'
                    body+='<th colspan="1" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">CONCILIACION</th>'
                    body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;"> - </th>'
                    body+='<th colspan="1" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ diff.name +'</th>'
                    body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;"> - </th>'
                    body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;"> - </th>'
                    body+='<th colspan="2" style="width: 375px; margin: 0px; padding: 0px; background-color: #F2F2F2; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat; color: #222;">'+ str(amount_pago) +'</th>'
                    body+='</tr>'
            body+='</table>'
            body+='<br/>'    
            body+='<br/>'                 
            body+='<div style="width: 375px; margin: 0px; padding: 0px; background-color: #8E0000; border-top-left-radius: 5px 5px; border-top-right-radius: 5px 5px; background-repeat: repeat no-repeat;">'
            body+='<h3 style="margin: 0px; padding: 2px 14px; font-size: 15px; color: #FFF;">'
            body+='<strong style="text-transform:uppercase;">'+voucher.company_id.name+'</strong>'
            body+='</h3>'        
            body+='</div>'
            body+="""<div style="width: 347px; margin: 0px; padding: 5px 14px; line-height: 16px; background-color: #F2F2F2;">
                <span style="color: #222; margin-bottom: 5px; display: block; ">"""
            body+=voucher.company_id.street +'<br/>'
            body+=voucher.company_id.country_id.name +'-'+ voucher.company_id.partner_id.city_id.name +'<br/>'
            body+='</span>'
            body+='<div style="margin-top: 0px; margin-right: 0px; margin-bottom: 0px; margin-left: 0px; padding-top: 0px; padding-right: 0px; padding-bottom: 0px; padding-left: 0px; ">'
            body+='Telefono:&nbsp;'+voucher.company_id.phone
            body+='</div>'
            body+='<div>'
            body+='Web :&nbsp;<a href="'+ voucher.company_id.website +'">'+ voucher.company_id.website +'</a>'
            body+='</div>'
            body+='<p></p>'
            body+='</div>'
            body+='</center>'                
            body +='</body></html>'        
            
            vals = {
                'email_from': user_id.name+' '+user_id.email,
                'email_to': voucher.partner_id.name,
                'state': 'outgoing',
                'subject': 'Notifiacion de Pago'+' '+voucher.display_name,
                'body_html': body,
                'type':'email',
                'auto_delete': False,
                'notification': True,
                'recipient_ids': [(6, 0, [x.id for x in voucher.partner_id])]
                }               
                
                
            mail=self.pool.get('mail.mail').create(cr, uid, vals, context=context)
            self.pool.get('mail.mail').send(cr, uid, mail, context=context)
        return True
