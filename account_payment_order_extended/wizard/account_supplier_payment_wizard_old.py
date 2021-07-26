# -*- encoding: utf-8 -*-
from openerp.osv import osv, fields
import base64
import time
import codecs
import unicodedata
from datetime import datetime
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import zlib

class payment_order_create(osv.osv_memory):
    _inherit = 'payment.order.create'
    
    def create_payment(self, cr, uid, ids, context=None):
        order_obj = self.pool.get('payment.order')
        line_obj = self.pool.get('account.move.line')
        payment_obj = self.pool.get('payment.line')
        if context is None:
            context = {}
        data = self.browse(cr, uid, ids, context=context)[0]
        line_ids = [entry.id for entry in data.entries]
        if not line_ids:
            return {'type': 'ir.actions.act_window_close'}

        payment = order_obj.browse(cr, uid, context['active_id'], context=context)
        t = None
        line2bank = line_obj.line2bank(cr, uid, line_ids, t, context)

        ## Finally populate the current payment with new lines:
        for line in line_obj.browse(cr, uid, line_ids, context=context):
            if payment.date_prefered == "now":
                #no payment date => immediate payment
                date_to_pay = False
            elif payment.date_prefered == 'due':
                date_to_pay = line.date_maturity
            elif payment.date_prefered == 'fixed':
                date_to_pay = payment.date_scheduled
            line_id = payment_obj.create(cr, uid,{
                    'move_line_id': line.id,
                    'amount_currency': line.amount_residual_currency,
                    'bank_id': line2bank.get(line.id),
                    'order_id': payment.id,
                    'partner_id': line.partner_id and line.partner_id.id or False,
                    'other_partner_id': line.partner_id and line.partner_id.id or False,
                    'bank_id': line.partner_id and line.partner_id.default_bank_id and line.partner_id.default_bank_id.id or False,
                    'communication': line.ref or '/',
                    'state': line.invoice and line.invoice.reference_type != 'none' and 'structured' or 'normal',
                    'date': date_to_pay,
                    'currency': (line.invoice and line.invoice.currency_id.id) or line.journal_id.currency.id or line.journal_id.company_id.currency_id.id,
                }, context=context)
        # order_obj.write(cr, uid, [payment.id], {'dummy': not payment.dummy}, context=context)
        return {'type': 'ir.actions.act_window_close'}  


class account_suppier_payment_wizard(osv.osv_memory):
    _name = 'account.suppier.payment.wizard'
    _columns = {
                'name': fields.char(size=64, string='Archivo Pago Banco'),
                'date_order' : fields.datetime('Order Date', required=True),
                'file_text':fields.binary(string="Archivo Pago Banco"),
        }
    
    _defaults = {
        'date_order': lambda *args: time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    
    def do_process(self, cr, uid, ids, context=None):
        date_order = self.browse(cr, uid, ids)[0].date_order
        date_order = datetime.strptime(date_order,DEFAULT_SERVER_DATETIME_FORMAT)
        date_order = fields.datetime.context_timestamp(cr, uid, date_order, context=context)
        text_final = ''
        active_model = context['active_model']
        active_pool = self.pool.get(active_model)
        total_amount = 0.0
        contar = 0
        count,amount_total,code,cantidad = 0,0,0,0
        cuenta = ''
        
        def strip_accents(s):
            new_string = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
            new_string = new_string.encode('ascii', 'replace').replace('?',' ')
            return new_string
        
        for total in active_pool.browse(cr, uid, context.get('active_ids')):
            if active_model in ['account.voucher']:
                amount_total += total.amount
            elif active_model in ['payment.order']:
                amount_total += total.total
        
        for object in active_pool.browse(cr, uid, context.get('active_ids')):            
            bank_name = object.mode and object.mode.bank_id.bank.name
            if active_model in ['account.voucher','purchase.advance.supplier']:
                total = object.amount
                if active_model == 'purchase.advance.supplier':
                    date = object.pay_date
                    lines = [object.move_id]
                    reference = object.name and object.name or ''
                    # bank_name = object.bank_account_id
                else:
                    lines = object.line_dr_ids
                    date = object.date
                    reference = object.reference and object.reference or ''
            elif active_model == 'payment.order':
                lines = object.line_ids
                total = object.total
                date = object.payment_order_date
                reference = object.reference and object.reference or ''
            if not date:
                raise osv.except_osv(_('Error!'),_("La fecha de pago no fue ingresada"))
            date = datetime.strptime(date,DEFAULT_SERVER_DATE_FORMAT)

            if not object.mode.bank_id.bank.bic:
                raise osv.except_osv(_('Error!'),_("El banco no tiene configurado el BIC"))
            bank_bic = object.mode.bank_id.bank.bic
            
            # Banco Davivienda:
            if bank_bic[-2:] == '51':
                ref_tipo = object.company_id.partner_id.ref_type.code
                final_file_name="pago_davivienda_"+str(date_order)
                
                text_final += 'RC'
                text_final += (object.company_id.partner_id.ref+str(object.company_id.partner_id.dev_ref)).rjust(16,'0')[0:16]
                text_final += 'PROV'
                text_final += 'PROV'
                text_final += object.mode.bank_id.acc_number.rjust(16,'0')
                text_final += object.mode.bank_id.state == 'corriente' and 'CC' or object.mode.bank_id.state == 'ahorros' and 'CA'
                text_final += object.mode.bank_id.bank.bic.rjust(6,'0')
                text_final += str(total).replace('.','').rjust(18,'0')
                text_final += str(len(lines)).rjust(6,'0')
                text_final += date_order.strftime('%Y%m%d')
                text_final += date_order.strftime('%H%M%S')
                text_final += ''.rjust(4,'0')
                text_final += ''.rjust(4,'9')
                text_final += ''.rjust(8,'0')
                text_final += ''.rjust(6,'0')
                text_final += ''.rjust(2,'0')
                text_final += (ref_tipo == 'NI' and '01') or (ref_tipo == 'CC' and '02' or (ref_tipo == 'RC' and '03' or (ref_tipo == 'CE' and '04')))
                text_final += ''.rjust(12,'0')
                text_final += ''.rjust(4,'0')
                text_final += ''.rjust(40,'0')
                text_final += "\n"
                
                partner_ids = []
                for line in lines:
                    if line.move_line_id.partner_id.id not in partner_ids:
                        partner_ids.append(line.move_line_id.partner_id.id)
                        if active_model in ['account.voucher','purchase.advance.supplier']:
                            other_partner_id = object.other_partner_id
                            other_amount = object.amount
                            bank_account_id = object.mode.bank_id
                        elif active_model == 'payment.order':
                            other_partner_id = line.other_partner_id
                            other_amount = line.amount_currency
                            for all_line in lines:
                                if all_line.partner_id.id == line.partner_id.id and all_line.id != line.id:
                                    other_amount += all_line.amount_currency
                            # bank_account_id = line.bank_id
                            bank_account_id = object.mode.bank_id
                            if not bank_account_id:
                                raise osv.except_osv(_('Configuration Error !'),_("No hay cuenta de banco definida para la linea '%s'!")%(line.move_line_id.name))
                        
                        ref_tipo_otro = other_partner_id.ref_type.code
                        text_final += 'TR'
                        text_final += (other_partner_id.ref+str(other_partner_id.dev_ref)).rjust(16,'0')[0:16]
                        text_final += ''.rjust(16,'0')
                        text_final += bank_account_id.acc_number.rjust(16,'0')
                        text_final += bank_account_id.state == 'corriente' and 'CC' or (bank_account_id.state == 'ahorros' and 'CA' or 'OP')
                        text_final += bank_account_id.bank.bic.rjust(6,'0')
                        text_final += str(other_amount).replace('.','').rjust(18,'0')
                        text_final += ''.rjust(6,'0')
                        text_final += (ref_tipo_otro == 'NI' and '01') or (ref_tipo_otro == 'CC' and '02' or (ref_tipo_otro == 'RC' and '03' or (ref_tipo_otro == 'CE' and '04')))
                        text_final += '1'
                        text_final += ''.rjust(4,'9')
                        text_final += ''.rjust(40,'0')
                        text_final += ''.rjust(18,'0')
                        text_final += ''.rjust(8,'0')
                        text_final += ''.rjust(4,'0')
                        text_final += ''.rjust(4,'0')
                        text_final += ''.rjust(7,'0')
                        text_final += "\n"
            # Banco Popular:
            #if bank_bic[-2:] == '02':
              #  ref_tipo = object.company_id.partner_id.ref_type.code
               # final_file_name="pago_bco_popular_"+str(date_order)
                
              #  text_final += 'RC'
              #  text_final += (object.company_id.partner_id.ref+str(object.company_id.partner_id.dev_ref)).rjust(16,'0')[0:16]
              #  text_final += 'PROV'
             #   text_final += 'PROV'
              #  text_final += object.mode.bank_id.acc_number.rjust(16,'0')
              #  text_final += object.mode.bank_id.state == 'corriente' and 'CC' or object.mode.bank_id.state == 'ahorros' and 'CA'
             #   text_final += object.mode.bank_id.bank.bic.rjust(6,'0')
              #  text_final += str(total).replace('.','').rjust(18,'0')
              #  text_final += str(len(lines)).rjust(6,'0')
              #  text_final += date_order.strftime('%Y%m%d')
              #  text_final += date_order.strftime('%H%M%S')
              #  text_final += ''.rjust(4,'0')
              #  text_final += ''.rjust(4,'9')
              #  text_final += ''.rjust(8,'0')
              #  text_final += ''.rjust(6,'0')
              #  text_final += ''.rjust(2,'0')
              #  text_final += (ref_tipo == 'NI' and '01') or (ref_tipo == 'CC' and '02' or (ref_tipo == 'RC' and '03' or (ref_tipo == 'CE' and '04')))
             #   text_final += ''.rjust(12,'0')
              #  text_final += ''.rjust(4,'0')
               # text_final += ''.rjust(40,'0')
                #text_final += "\n"
                
                #partner_ids = []
                #for line in lines:
                #    #if line.move_line_id.partner_id.id not in partner_ids:
                    #    partner_ids.append(line.move_line_id.partner_id.id)
                    #    if active_model in ['account.voucher','purchase.advance.supplier']:
                    #        other_partner_id = object.other_partner_id
                    #        other_amount = object.amount
                    #        bank_account_id = object.mode.bank_id
                    #    elif active_model == 'payment.order':
                    #        other_partner_id = line.other_partner_id
                    #        other_amount = line.amount_currency
                    #        for all_line in lines:
                    #            if all_line.partner_id.id == line.partner_id.id and all_line.id != line.id:
                    #                other_amount += all_line.amount_currency
                    #        # bank_account_id = line.bank_id
                    #        bank_account_id = object.mode.bank_id
                    #        if not bank_account_id:
                    #            raise osv.except_osv(_('Configuration Error !'),_("No hay cuenta de banco definida para la linea '%s'!")%(line.move_line_id.name))
                    #    
                    #    ref_tipo_otro = other_partner_id.ref_type.code
                    #    text_final += 'TR'
                    #    text_final += (other_partner_id.ref+str(other_partner_id.dev_ref)).rjust(16,'0')[0:16]
                    #    text_final += ''.rjust(16,'0')
                    #    text_final += bank_account_id.acc_number.rjust(16,'0')
                    #    text_final += bank_account_id.state == 'corriente' and 'CC' or (bank_account_id.state == 'ahorros' and 'CA' or 'OP')
                    #    text_final += bank_account_id.bank.bic.rjust(6,'0')
                    #    text_final += str(other_amount).replace('.','').rjust(18,'0')
                    #    text_final += ''.rjust(6,'0')
                    #    text_final += (ref_tipo_otro == 'NI' and '01') or (ref_tipo_otro == 'CC' and '02' or (ref_tipo_otro == 'RC' and '03' or (ref_tipo_otro == 'CE' and '04')))
                    #    text_final += '1'
                    #    text_final += ''.rjust(4,'9')
                    #    text_final += ''.rjust(40,'0')
                    #    text_final += ''.rjust(18,'0')
                    #    text_final += ''.rjust(8,'0')
                    #    text_final += ''.rjust(4,'0')
                    #    text_final += ''.rjust(4,'0')
                    #    text_final += ''.rjust(7,'0')
                    #    text_final += "\n"                        
###################################### More Products S.A.
            # Banco Popular:
            if bank_bic[-2:] == '02':
                ref_tipo = object.company_id.partner_id.ref_type.code
                final_file_name="pago_bco_popular_"+str(date_order)

                text_final += '01'#(ref_tipo == 'NI' and '01') or (ref_tipo == 'CC' and '02' or (ref_tipo == 'RC' and '03' or (ref_tipo == 'CE' and '04')))
                text_final += date_order.strftime('%Y%m%d')    
                text_final += str(object.company_id.partner_id.name)[0:15].ljust(16,'0')                           
                #text_final += (object.company_id.partner_id.ref+str(object.company_id.partner_id.dev_ref)).rjust(16,'0')[0:16]
                #text_final += '          '
                text_final += ''.rjust(3,'0') # Cuenta Corriente
                text_final += str(object.mode.bank_id.acc_number)[0:9] #NUMERO DE CUENTA LONGITUD 9 063144935
                #text_final += ' '
                text_final += str(object.company_id.partner_id.ref)[0:9].ljust(9,'0')                    
                text_final += str(len(lines)).rjust(6,'0')
                text_final += str(total).replace('.','').rjust(18,'0')
                text_final += ''.rjust(12,'0') #Nombre archivo o 12 espacios en blanco                                                                                                               
                text_final += str('PROVEEDOR').rjust(10,' ')  #tipo de pago
                text_final += ''.rjust(26,'0') # campo discrecional 26 posiciones
                text_final += ''.rjust(1,' ') # por defecto consolidado
                text_final += ''.rjust(44,' ') # campo discrecional 44 posiciones                
                text_final += str('V').rjust(2,' ') # Indicador obligatorio para validar la información del destinatario, enviada contra la identificación contenida en la base de datos de la institución destinataria. V y un espacio en blanco.
                text_final += ''.rjust(40,' ')# por defecto consolidado

                #text_final += object.mode.bank_id.state == 'corriente' and 'CC' or object.mode.bank_id.state == 'ahorros' and 'CA'
                #text_final += object.mode.bank_id.bank.bic.rjust(6,'0')
                #text_final += str(total).replace('.','').rjust(18,'0')
                #text_final += str(len(lines)).rjust(6,'0')
                #text_final += date_order.strftime('%Y%m%d')
                #text_final += date_order.strftime('%H%M%S')
                #text_final += ''.rjust(4,'0')
                #text_final += ''.rjust(4,'9')
                #text_final += ''.rjust(8,'0')
                #text_final += ''.rjust(6,'0')
                #text_final += ''.rjust(2,'0')
                #text_final += ''.rjust(12,'0')
                #text_final += ''.rjust(4,'0')
                #text_final += ''.rjust(40,'0')
                text_final += "\r\n"             
             
                partner_ids = []
                for line in lines:
                    if line.move_line_id.partner_id.id not in partner_ids:
                        partner_ids.append(line.move_line_id.partner_id.id)
                        if active_model in ['account.voucher','purchase.advance.supplier']:
                            other_partner_id = object.other_partner_id
                            other_amount = object.amount
                            bank_account_id = object.mode.bank_id
                        elif active_model == 'payment.order':
                            other_partner_id = line.other_partner_id
                            other_amount = line.amount_currency
                            for all_line in lines:
                                if all_line.partner_id.id == line.partner_id.id and all_line.id != line.id:
                                    other_amount += all_line.amount_currency
                            # bank_account_id = line.bank_id
                            bank_account_id = object.mode.bank_id
                            if not bank_account_id:
                                raise osv.except_osv(_('Configuration Error !'),_("No hay cuenta de banco definida para la linea '%s'!")%(line.move_line_id.name))

                        ref_tipo_otro = other_partner_id.ref_type.code
                        text_final += (ref_tipo == 'NI' and '01') or (ref_tipo == 'CC' and '02' or (ref_tipo == 'RC' and '03' or (ref_tipo == 'CE' and '04')))                   
                        text_final += (other_partner_id.ref+str(other_partner_id.dev_ref))[0:16]
                        text_final += '     '                        
                        text_final += str(other_amount).replace('.','').rjust(18,'0')
                        text_final += (other_partner_id.name).rjust(23,'0')[0:22]
                        text_final += '00001002922'                     
                        text_final += bank_account_id.acc_number
                        text_final += '          '
                        text_final += (object.company_id.partner_id.ref+str(object.company_id.partner_id.dev_ref))[0:16]                        
                        text_final += '        '
                        text_final += 'PROVEEDOR'  
                        text_final += ' '
                        text_final += "Coment"                                                                      
                        text_final += "\r\n"



            # Bancolombia:
            elif bank_bic == '07':
                final_file_name = "pago_bancolombia_"+str(date_order)
                text_final += '1' 
                text_final += (object.company_id.partner_id.ref).rjust(10,'0')[0:10]
                text_final += object.company_id.partner_id.name.ljust(16,' ')[0:16]
                if active_model == 'payment.order':
                    if object.type_payment == 'Pago Nomina':
                        text_final += '225'
                        text_final += 'PAGO NOMIN'.ljust(10,' ')
                    else:
                        text_final += '220'
                        text_final += 'PAGO PROVE'.ljust(10,' ')
                else:
                    text_final += '220'
                    text_final += 'PAGO PROVE'.ljust(10,' ')
                
                text_final += date_order.strftime('%y%m%d')
                text_final += 'A'
                text_final += date.strftime('%y%m%d')
                text_final += str(len(lines)).rjust(6,'0')
                text_final += ''.rjust(12,'0')
                text_final += str(int(total)).rjust(12,'0')
                text_final += object.mode.bank_id.acc_number.rjust(11,'0')
                text_final += object.mode.bank_id.state == 'corriente' and 'D' or object.mode.bank_id.state == 'ahorros' and 'S'
                text_final += "\n"
                partner_ids = []
                for line in lines:
                    if line.partner_id.id not in partner_ids:
                        partner_ids.append(line.partner_id.id)
                        if active_model in ['account.voucher','purchase.advance.supplier']:
                            other_partner_id = object.other_partner_id
                            other_amount = object.amount
                            bank_account_id = object.bank_account_id
                        elif active_model == 'payment.order':
                            other_partner_id = line.other_partner_id
                            other_amount = line.amount_currency
                            if object.type_payment == 'Pago Nomina':
                                bank_account_id = other_partner_id.employee_id.bank_account_id
                            else:
                                bank_account_id = other_partner_id.bank_ids[-1]
                                # Otra opcion: asegurarse que tenga definido default_bank_id

                            for all_line in lines:
                                if all_line.partner_id.id == line.partner_id.id and all_line.id != line.id:
                                    other_amount += all_line.amount_currency
                        if not bank_account_id:
                            raise osv.except_osv(_('Configuration Error !'),_("Hay una linea sin cuenta de banco definida"))
                                
                        text_final += "6"
                        text_final += (other_partner_id.ref).rjust(15,'0')[0:15]
                        text_final += other_partner_id.name.ljust(18,' ')[0:18]
                        #nota1
                        text_final += bank_account_id.bank.bic.rjust(9,'0')
                        #nota2 
                        text_final += bank_account_id.acc_number.rjust(17,'0')
                        #nota3
                        text_final += 'S'
                        text_final += bank_account_id.state == 'corriente' and '27' or bank_account_id.state == 'ahorros' and '37'
                        text_final += str(int(other_amount)).rjust(10,'0')
                        #nota4
                        text_final += ''.ljust(9,' ')
                        #nota5
                        text_final += ''.ljust(12,' ')
                        text_final += ' '
                        text_final += "\n"
            
            # Banco Comercial AV Villas S.A.:
            elif bank_bic[-2:] == '49':
                if contar == 0:
                    final_file_name = "pago_av_villas_"+str(date_order)
                    text_final += '01' 
                    text_final += date_order.strftime('%Y%m%d')
                    text_final += date_order.strftime('%H%M%S')
                    text_final += '08802'
                    text_final += ' '.ljust(50,' ')
                    text_final += ' '.ljust(120,' ')
                    text_final += "\r\n"
                    seq = 0
                    partner_ids = []
                contar += 1
                if contar >= 1 and active_model in ['account.voucher','purchase.advance.supplier']:
                    if object.partner_id.id not in partner_ids:
                        partner_ids.append(object.partner_id.id)
                        seq += 1
                        text_final += "02"
                        text_final += "000023"
                        text_final += object.mode.bank_id.state == 'ahorros' and '01' or object.mode.bank_id.state == 'corriente' and '06'
                        text_final += (object.mode.bank_id.acc_number).replace('-','').rjust(16,'0')
                        text_final += object.mode.bank_id.bank.bic.rjust(3,'0')
                        text_final += object.mode.bank_id.state == 'ahorros' and '01' or (object.mode.bank_id.state == 'corriente' and '06' or '01')
                        if not object.mode.bank_id:
                                raise osv.except_osv(_('Configuration Error !'),_("Hay una objecta sin cuenta de banco definida"))
                        text_final += object.mode.bank_id.acc_number.rjust(16,'0')
                        text_final += str(seq).rjust(9,'0')
                        text_final += str(int(object.amount)).replace('.','').rjust(16,'0') 
                        text_final += str(object.amount)[-2:].replace('.','').rjust(2,'0') 
                        text_final += str(0).rjust(16,'0')
                        text_final += str(0).rjust(16,'0')
                        text_final += str(0).rjust(16,'0')
                        text_final += object.partner_id.name.ljust(30,' ')[0:30]
                        text_final += object.partner_id.ref.rjust(11,'0')[0:11]
                        text_final += str(0).rjust(6,'0')
                        text_final += "00"
                        text_final += str(0).rjust(18,'0')
                        text_final += '00'
                        text_final += "\r\n"
                            
                if active_model == 'payment.order':
                    for line in lines:
                        if line.partner_id.id not in partner_ids:
                            partner_ids.append(line.partner_id.id)
                            seq += 1
                            text_final += "02"
                            text_final += "000023"
                            text_final += object.mode.bank_id.state == 'ahorros' and '01' or object.mode.bank_id.state == 'corriente' and '06'
                            text_final += (object.mode.bank_id.acc_number).replace('-','').rjust(16,'0')
                            text_final += object.mode.bank_id.bank.bic.rjust(3,'0')
                            text_final += line.bank_id.state == 'ahorros' and '01' or (line.bank_id.state == 'corriente' and '06' or '01')
                            if not line.bank_id:
                                    raise osv.except_osv(_('Configuration Error !'),_("Hay una linea sin cuenta de banco definida"))
                            text_final += line.bank_id.acc_number.rjust(16,'0')
                            text_final += str(seq).rjust(9,'0')
                            text_final += str(int(line.amount_currency)).replace('.','').rjust(16,'0') 
                            text_final += str(line.amount_currency)[-2:].replace('.','').rjust(2,'0') 
                            text_final += str(0).rjust(16,'0')
                            text_final += str(0).rjust(16,'0')
                            text_final += str(0).rjust(16,'0')
                            text_final += line.partner_id.name.ljust(30,' ')[0:30]
                            text_final += line.partner_id.ref.rjust(11,'0')[0:11]
                            text_final += str(0).rjust(6,'0')
                            text_final += "00"
                            text_final += str(0).rjust(18,'0')
                            text_final += '00'
                            text_final += "\r\n"
                
                if contar == len(active_pool.browse(cr, uid, context.get('active_ids'))):
                    for total in active_pool.browse(cr, uid, context.get('active_ids')):
                        if active_model in ['account.voucher','purchase.advance.supplier']:
                            total_amount += total.amount
                        elif active_model in ['payment.order']:
                            total_amount += total.total
                    text_final += '03'
                    text_final += str(seq).rjust(9,'0')
                    text_final += str(int(total_amount)).replace('.','').rjust(18,'0')
                    text_final += str(total_amount)[-2:].replace('.','').rjust(2,'0')
                    text_final += hex(zlib.crc32(str(total_amount))).rjust(15,' ')
                    text_final += ' '.ljust(145,' ')
                    text_final += "\r\n"
            
            # Banco de Occidente S.A.:
            elif bank_bic[-2:] == '23':
                if count == 0:
                    cantidad = str(len(active_pool.browse(cr, uid, context.get('active_ids'))))
                    if active_model in ['payment.order']:
                        date_order = object.payment_order_date
                        cantidad = str(len(object.line_ids))
                        
                    final_file_name = "pago_occidente_"+str(date_order)
                    text_final += '1'
                    text_final += '0'.ljust(4,'0')
                    text_final += str(date_order)[0:10].replace('-','').rjust(8,'0')
                    text_final += cantidad.rjust(4,'0')
                    text_final += str(int(amount_total)).replace(',','').replace('.','').rjust(16,'0')
                    text_final += str(amount_total)[-2:].replace(',','').replace('.','').ljust(2,'0')
                    text_final += (object.mode.bank_id.acc_number).replace('-','').rjust(16,'0')
                    text_final += '0'.ljust(6,'0')
                    text_final += '0'.ljust(142,'0')
                    text_final += "\r\n"
                    
                count += 1
                
                if count >= 1 and active_model in ['account.voucher']:
                    if not object.state == 'posted':
                        raise osv.except_osv(_('Error!'),_("Los movimientos deben estar contabilizados para generar el archivo"))
                    if object.mode.bank_id.bank.bic == object.bank_account_id.bank.bic:
                        code = 2
                    else:
                        code = 3
                    if object.bank_account_id.state == 'corriente':
                        cuenta = 'C'
                    elif object.bank_account_id.state == 'ahorros':
                        cuenta = 'A'
                    else:
                        cuenta = '0'
                        
                    text_final += '2'
                    text_final += str(count).rjust(4,'0')
                    text_final += (object.mode.bank_id.acc_number).replace('-','').rjust(16,'0')
                    text_final += str(object.other_partner_id.name)[0:30].ljust(30,' ')
                    text_final += object.other_partner_id.ref.rjust(11,'0')
                    text_final += object.mode.bank_id.bank.bic.rjust(4,'0')
                    text_final += str(object.date).replace('-','').rjust(8,'0')
                    text_final += str(code).rjust(1,'0')
                    text_final += str(int(object.amount)).replace(',','').replace('.','').rjust(13,'0')
                    text_final += str(object.amount)[-2:].replace(',','').replace('.','').ljust(2,'0')
                    text_final += object.bank_account_id.acc_number.ljust(16,' ')
                    text_final += (object.number)[0:12].rjust(12,' ')
                    text_final += str(cuenta).rjust(1,' ')
                    text_final += '0'.ljust(80,'0')
                    text_final += "\r\n"
                    
                if count >= 1 and active_model in ['payment.order']:
                    # if not object.state == 'done':
                        # raise osv.except_osv(_('Error!'),_("Los movimientos deben estar realizados para generar el archivo"))
                    line = 0
                    for lines in object.line_ids:
                        line += 1
                        bank_account_id = object.mode.bank_id
                        
                        if object.mode.bank_id.bank.bic == lines.bank_id.bank.bic:
                            code = 2
                        else:
                            code = 3
                            
                        if lines.bank_id.state == 'corriente':
                            cuenta = 'C'
                        elif lines.bank_id.state == 'ahorros':
                            cuenta = 'A'
                        else:
                            cuenta = '0'
                            
                        text_final += '2'
                        text_final += str(line).rjust(4,'0')
                        text_final += (bank_account_id.acc_number).replace('-','').rjust(16,'0')
                        text_final += str(strip_accents(lines.other_partner_id.name))[0:30].ljust(30,' ')
                        text_final += lines.other_partner_id.ref.rjust(11,'0')
                        text_final += bank_account_id.bank.bic.rjust(4,'0')
                        text_final += str(lines.ml_maturity_date).replace('-','').rjust(8,'0')
                        text_final += str(code).rjust(1,'0')
                        text_final += str(int(lines.amount)).replace(',','').replace('.','').rjust(13,'0')
                        text_final += str(lines.amount)[-2:].replace(',','').replace('.','').ljust(2,'0')
                        text_final += bank_account_id.acc_number.ljust(16,' ')
                        text_final += str(lines.move_line_id.move_id.name)[0:12].rjust(12,' ')
                        text_final += str(cuenta).rjust(1,' ')
                        text_final += '0'.ljust(80,'0')
                        text_final += "\r\n"
                
                if (count + 1) == (len(active_pool.browse(cr, uid, context.get('active_ids'))) + 1):
                    text_final += '3'
                    text_final += '9999'
                    text_final += cantidad.rjust(4,'0')
                    text_final += str(int(amount_total)).replace(',','').replace('.','').rjust(16,'0')
                    text_final += str(amount_total)[-2:].replace(',','').replace('.','').ljust(2,'0')
                    text_final += '0'.ljust(172,'0')
                    text_final += "\r\n"
            
            # Banco de Bogota:
            elif bank_bic[-2:] == '01':
                if count == 0:
                    cantidad = str(len(active_pool.browse(cr, uid, context.get('active_ids'))))
                    
                    if active_model in ['payment.order']:
                        date_order = object.payment_order_date
                        cantidad = str(len(object.line_ids))
                        
                    if object.mode.bank_id.state == 'corriente':
                        cuenta = '1'
                    elif object.mode.bank_id.state == 'ahorros':
                        cuenta = '2'
                    else:
                        cuenta = '5'
                        
                    if object.type_payment == 'Pago Nomina':
                        type_payment = '001'
                    elif object.type_payment == 'Pago Proveedores':
                        type_payment = '002'
                    elif object.type_payment == 'Transferencias':
                        type_payment = '003'
                    elif object.type_payment == 'Otros':
                        type_payment = '995'
                    else:
                        raise osv.except_osv(_('Configuration Error !'),_("Debe configurar un tipo de Transferencia"))
                    
                    
                    final_file_name = 'pago_banco_bogota_'+str(date_order)
                    text_final += '1'
                    text_final += str(date_order)[0:10].replace('-','').rjust(8,'0')
                    text_final += '0'.ljust(24,'0')
                    text_final += str(cuenta)
                    text_final += '0'.ljust(6,'0')
                    text_final += (object.mode.bank_id.acc_number).replace('-','').rjust(11,'0')
                    text_final += str(object.mode.bank_id.partner_id.name)[0:40].ljust(40,' ')
                    text_final += object.mode.bank_id.partner_id.ref.rjust(10,'0')
                    text_final += str(object.mode.bank_id.partner_id.dev_ref)
                    text_final += str(type_payment)
                    text_final += '0001'
                    text_final += str(object.time_of_process)[0:10].replace('-','').rjust(8,'0')
                    text_final += '001'
                    text_final += 'N'
                    text_final += ' '.ljust(48,' ')
                    text_final += ' '.ljust(1,' ')
                    text_final += ' '.ljust(80,' ')
                    text_final += "\r\n"
             
                count += 1
                    
                if count >= 1 and active_model in ['payment.order']:
                    cont = 0
                    for line in object.line_ids:
                        cont += 1
                        
                        if not line.other_partner_id and line.other_partner_id.ref_type and line.other_partner_id.ref_type.code:
                            raise osv.except_osv(_('Configuration Error !'),_("Debe configurar un tipo de documento para el tercero '%s'")%(line.other_partner_id.name))
                        else:
                            ref_tipo = line.other_partner_id.ref_type.code
                        
                        if not line.bank_id:
                            raise osv.except_osv(_('Configuration Error !'),_("Debe configurar una cuenta para el tercero '%s'")%(line.other_partner_id.name))
                        else:
                            acc_number = line.bank_id.acc_number
                          
                        
                        if line.bank_id.state == 'corriente':
                            cuenta = '1'
                        elif line.bank_id.state == 'ahorros':
                            cuenta = '2'
                        else:
                            cuenta = 'X'
                        
                        # if not line.bank_id.city_code:
                        #     raise osv.except_osv(_('Configuration Error !'),_("Para transferencias con el Banco de Bogota es necesario configurar el codigo de la ciudad en la cuenta '%s'")%(line.bank_id.acc_number))
                        # if len(line.bank_id.city_code) > 4:
                        #     raise osv.except_osv(_('Configuration Error !'),_("El codigo de la ciudad de la cuenta '%s' no debe ser mayor a 4 digitos")%(line.bank_id.acc_number))
                            
                            
                        text_final += '2'
                        text_final += (ref_tipo == 'NI' and 'N') or (ref_tipo == 'CC' and 'C') or (ref_tipo == 'TI' and 'T') or (ref_tipo == 'CE' and 'E')
                        text_final += line.other_partner_id.ref.rjust(11,'0')
                        text_final += line.other_partner_id.name.ljust(40,' ')
                        text_final += '0'
                        text_final += str(cuenta)
                        text_final += (acc_number).replace('-','').ljust(17,' ')
                        text_final += str(int(line.amount)).replace(',','').replace('.','').rjust(16,'0')
                        text_final += str(line.amount)[-2:].replace(',','').replace('.','').rjust(2,'0')
                        text_final += 'A'
                        text_final += '000'
                        #text_final += '001'
                        #text_final += str(line.bank_id.city_code)
                        text_final += str(line.bank_id.bank.bic)# A: cambiado por wmoreno A POR B
                        text_final += '001' # B: cambiado por wmoreno B por A
                        text_final += 'TESORERIA'
                        text_final += ' '
                        text_final += (object.type_payment+' '+str(date_order)+' '+ object.mode.name).rjust(70,' ')
                        text_final += '0'
                        text_final += '0000000000'
                        text_final += 'N'
                        text_final += ' '.ljust(8,' ')
                        text_final += ' '.ljust(16,' ')
                        text_final += ' '.ljust(2,' ')
                        text_final += ' '.ljust(11,' ')
                        text_final += ' '.ljust(11,' ')
                        text_final += 'N'
                        text_final += ' '.ljust(8,' ')
                        text_final += "\r\n"                    
            else:
                raise osv.except_osv(_('Error!'),_("Solo se han desarrollado formatos de pagos para Bancolombia, Davivienda, BCO Popular, AV Villas, Occidente y Bogota"))
        
        text_final = strip_accents(text_final)
        file_text=base64.b64encode(text_final)
        file_name=str(final_file_name +'.txt')
        self.write(cr, uid, ids,{'name':file_name,'file_text': file_text,})
        active_pool.write(cr, uid, context.get('active_ids'),{'file_name':file_name,'file_text': file_text,'time_of_process': self.browse(cr, uid, ids)[0].date_order})
        
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': self._name,
            'target': 'new',
            'context': context,
            'res_id': ids[0]
        }
account_suppier_payment_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:           