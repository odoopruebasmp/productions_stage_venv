# -*- encoding: utf-8 -*-
from openerp.osv import osv, fields
import base64
import time
import copy
import codecs
import unicodedata
from datetime import datetime
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
#Import logger
import logging
#Get the logger
_logger = logging.getLogger(__name__)


class account_suppier_payment_wizard(osv.osv_memory):
    _name = 'planilla.aportes.wizard'
    _columns = {
                'name': fields.char(size=64, string='Archivo Plano'),
                'date' : fields.datetime('Fecha', required=True),
                'file_text':fields.binary(string="Archivo Plano"),
        }
    
    _defaults = {
        'date': lambda *args: time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    
    def do_process(self, cr, uid, ids, context=None):
        date = self.browse(cr, uid, ids)[0].date
        date = datetime.strptime(date,DEFAULT_SERVER_DATETIME_FORMAT)
        date = fields.datetime.context_timestamp(cr, uid, date, context=context)
        text_final = ''
        line_end = '\r\n' #CRLF
        active_model = context['active_model']
        active_pool = self.pool.get(active_model)
        final_file_name = ''
        all_eps = {}
        all_arl = {}

        def nov(option):
            return option and 'X' or ' '
            
        def rule(slip,code,property):
            result = 0
            for line in slip.details_by_salary_rule_category:
                if line.code == code:
                    if property=='quantity':
                        result=line.quantity
                    elif property=='rate':
                        result=line.rate/100
                    elif property=='amount':
                        result=line.amount
                    else:
                        result=line.total
                    break
            return result
        
        def strip_accents(s):
            new_string = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
            new_string = new_string.encode('ascii', 'replace').replace('?',' ')
            return new_string
        
        #Articulo 7 1747 ENCABEZADO
        for run in active_pool.browse(cr, uid, context.get('active_ids')):
            text_enc = ['']*(21+1)
            final_file_name = 'Planilla Aportes ' + run.name
            text_enc[1]='01'
            text_enc[2]='1' #2A: lo genera automaticamente el operador de informacion, 1 ELEC, 2 Asistida, #RES 20080625
            text_enc[2]+='0001' #2B secuencia
            text_enc[3]=strip_accents(run.company_id.name).upper().ljust(200,' ')
            if not run.company_id.partner_id.ref or not run.company_id.partner_id.ref_type:
                raise osv.except_osv(_('Error!'),_("El tercero '%s' no esta correctamente configurado, no tiene documento!") % (run.company_id.partner_id.name,))
            text_enc[4]=run.company_id.partner_id.ref_type.code.ljust(2,' ')
            text_enc[5]=run.company_id.partner_id.ref.ljust(16,' ')
            text_enc[6]=str(run.company_id.partner_id.dev_ref)
            if not run.tipo_nomina.planilla_type_id:
                raise osv.except_osv(_('Error!'),_("El tipo de nomina '%s' no tiene configurado tipo de planilla!") % (run.tipo_nomina.name,))
            text_enc[7]=run.tipo_nomina.planilla_type_id.code.ljust(1,' ') 
            #E Planilla Empleados Empresas. #TODO
            #Y Planilla Independientes Empresas. #TODO
            #A Planilla Empleados Adicionales #TODO
            #S Planilla Empleados de Independientes #TODO
            #M Planilla Mora. puede ser una planilla de otro periodo #TODO
            #N Planilla Correcciones.  y Correcciones sin pago, como se pago y como se debio haber pagado, siempre doble linea #TODO
            text_enc[8]=''.ljust(10,' ') #Numero de la planilla asociada a esta planilla, solo aplica en N,F(del periodo) y A(numero de tipo E) 
            text_enc[9]=''.ljust(10,' ') #Fecha de pago Planilla asociada a esta planilla. (AAAA-MM-DD). 
            text_enc[10]='U' #Forma de presentacion. U=Unica #TOREWORK
            text_enc[11]=''.ljust(10,' ') # Codigo de la Sucursal
            text_enc[12]=''.ljust(40,' ') # Nombre de la Sucursal
            
            arl = run.company_id.arl_id
            if not arl:
                raise osv.except_osv(_('Error!'),_("La Compania '%s' no tiene ARL configurada!") % (run.company_id.name,))
            if not arl.codigo_arl:
                raise osv.except_osv(_('Error!'),_("El tercero de la ARL '%s' no tiene codigo de ARL configurado!") % (arl.name,))
            
            text_enc[13]=arl.codigo_arl.ljust(6,' ')
            text_enc[14]=run.payslip_period.start_period[0:7].ljust(7,' ') # Periodo de Pago diferente a salud #se genera automaticamente #RES 20080625 #TOCHECK
            
            mes_mas = run.payslip_period.start_period[5:7]
            if mes_mas == '12':
                mes_mas = '01'
            else:
                mes_mas = str(int(mes_mas)+1).rjust(2,'0')
            mes_mas = run.payslip_period.start_period[0:5]+mes_mas
            text_enc[15]=mes_mas.ljust(7,' ') # Periodo de Pago para salud
            text_enc[16]=''.ljust(10,' ') # Numero de radicacion o de la Planilla, asignado por el operador de informacion
            text_enc[17]=''.ljust(10,' ') #Fecha de Pago
            text_enc[18]=str(len(run.slip_ids)).rjust(6,'0') #Numero de empleados # se agrega el 6 por el 5
            
            total_ibc = 0
            for slip in run.slip_ids:
                total_ibc+=rule(slip,'BASE_APORTES_MES','total')
            
            text_enc[19]="{:012.0f}".format(total_ibc) # valor total de la nomina. sumatoria de la IBC #TOCHECK
            text_enc[20]='1'.rjust(1,'0') #tipo de aportante, 4 para Empleador
            text_enc[21]='0'.rjust(2,'0') # codigo del operador de informacion
            for x in text_enc:
                text_final+=x
            text_final+=line_end
            
            #Articulos 10(1-45),12(46-53),14(54-60),16(61-63),18(64-73) 1747 LIQUIDACION DETALLADA DE APORTES, RES 20130425
            seq_liq = 0
            for slip in run.slip_ids:
                if slip.contract_id.fiscal_type_id.code == '03':
                    continue
                text_liq = ['']*(97+1)
                seq_liq += 1
                text_liq[1]='02'
                text_liq[2]=str(seq_liq).rjust(5,'0')
                if not slip.employee_id.partner_id.primer_nombre or not slip.employee_id.partner_id.primer_apellido or not slip.employee_id.partner_id.ref or not slip.employee_id.partner_id.ref_type:
                    raise osv.except_osv(_('Error!'),_("El tercero '%s' no esta correctamente configurado, no tiene documento o apellido!") % (slip.employee_id.partner_id.name,))
                text_liq[3]=slip.employee_id.partner_id.ref_type.code.upper().ljust(2,' ')
                
                #3A,4A #TOCHECK RES 20121008 TIPO de documento UPC, y numero de identificacion UPC adicional
                text_liq[4]=slip.employee_id.partner_id.ref.ljust(16,' ')
                if not slip.contract_id.fiscal_type_id:
                    raise osv.except_osv(_('Error!'),_("El contrato '%s' no tiene configurado el tipo de cotizante!") % (slip.contract_id.name,))
                text_liq[5]=slip.contract_id.fiscal_type_id.code.rjust(2,'0')
                text_liq[6]=slip.contract_id.fiscal_subtype_id and slip.contract_id.fiscal_subtype_id.code.rjust(2,'0') or '00'
                
                es_colombiano=slip.employee_id.country_id and slip.employee_id.country_id.code=='CO' or True
                text_liq[7]=es_colombiano and ' ' or 'X'# Extranjero no obligado a aportar pension, hay extranjeros que aportan pension? #TOCHECK
                
                if not slip.employee_id.address_id:
                    raise osv.except_osv(_('Error!'),_("El empleado '%s' no tiene configurada la direccion de trabajo!") % (slip.employee_id.name,))
                
                trabaja_colombia = slip.employee_id.address_id.country_id.code=='CO'
                text_liq[8]=trabaja_colombia and ' ' or 'X' # Colombiano residente en el exterior #TOCHECK
                text_liq[9]=trabaja_colombia and slip.employee_id.address_id.state_id.code.rjust(2,'0')[0:2] or ' '.rjust(2,'0')
                text_liq[10]=trabaja_colombia and slip.employee_id.address_id.city_id.code.rjust(3,'0')[0:3] or ''.rjust(3,'0')
                text_liq[11]=strip_accents(slip.employee_id.partner_id.primer_apellido).upper().ljust(20,' ')
                text_liq[12]=slip.employee_id.partner_id.segundo_apellido and strip_accents(slip.employee_id.partner_id.segundo_apellido).upper().ljust(30,' ') or "".ljust(30,' ')
                text_liq[13]=strip_accents(slip.employee_id.partner_id.primer_nombre).upper().ljust(20,' ')
                text_liq[14]=slip.employee_id.partner_id.otros_nombres and strip_accents(slip.employee_id.partner_id.otros_nombres).upper().ljust(30,' ') or "".ljust(30,' ')
                
                #Novedades
                text_liq[15]=slip.ing or ' '
                text_liq[16]=slip.ret or ' '
                text_liq[17]=nov(slip.tde)
                text_liq[18]=nov(slip.tae)
                text_liq[19]=nov(slip.tdp) #no aplica para extranjero
                text_liq[20]=nov(slip.tap) #no aplica para extranjero
                text_liq[21]=nov(slip.vsp)
                text_liq[22]=slip.correcciones and slip.correcciones or ' '
                text_liq[23]=nov(slip.vst)
                text_liq[24]=nov(slip.sln) #TOREWORK X o C #RES 20120321
                text_liq[25]=''.ljust(1,' ') #ige
                text_liq[26]=''.ljust(1,' ') #lma
                text_liq[27]=''.ljust(1,' ') #vac
                #text_liq[25]=nov(slip.ige)
                #text_liq[26]=nov(slip.lma)
                #text_liq[27]=nov(slip.vac)
                text_liq[28]=nov(slip.avp) #no aplica para extranjero
                text_liq[29]=nov(slip.vct)
                text_liq[30]=''.rjust(2,'0')  
                
                afp = slip.contract_id.pensiones
                codigo_afp = ''
                if afp:
                    codigo_afp = afp.codigo_afp
                    if not codigo_afp:
                        raise osv.except_osv(_('Error!'),_("El tercero de la AFP '%s' no tiene codigo de AFP configurado!") % (afp.name,))
                text_liq[31]=codigo_afp.ljust(6,' ')
                text_liq[32]=''.ljust(6,' ') #afp a la cual se translada #TODO
                
                eps = slip.contract_id.eps
                if not eps:
                    raise osv.except_osv(_('Error!'),_("El contrato '%s' no tiene EPS configurado!") % (slip.contract_id.name,))
                if not eps.codigo_eps:
                    raise osv.except_osv(_('Error!'),_("El tercero de la EPS '%s' no tiene codigo de EPS configurado!") % (eps.name,))
                text_liq[33]=eps.codigo_eps.ljust(6,' ')
                text_liq[34]=''.ljust(6,' ') #eps a la cual se translada #TODO
                
                ccf = slip.contract_id.cajacomp
                codigo_ccf = ''
                if ccf:
                    codigo_ccf = ccf.codigo_ccf
                    if not codigo_ccf:
                        raise osv.except_osv(_('Error!'),_("El tercero de la CCF '%s' no tiene codigo de CCF configurado!") % (ccf.name,))
                text_liq[35]=codigo_ccf.ljust(6,' ')
                dias = 0
                for horas in slip.worked_days_line_ids.filtered(lambda x: x.code in ['WORK101']):
                    if horas.number_of_days>0:
                        dias = horas.number_of_days
                #descontar detalle de ausencias para considerar domingos y feriados
                if slip.leave_days_ids:
                    for y in slip.leave_days_ids:
                        dias-=y.days_payslip
                
                # text_liq[36]="{:02.0f}".format(rule(slip,'COT_PENSION','quantity'))
                # text_liq[37]="{:02.0f}".format(rule(slip,'COT_EPS','quantity'))
                # text_liq[38]="{:02.0f}".format(rule(slip,'APORTESARL','quantity')) 
                # text_liq[39]="{:02.0f}".format(rule(slip,'CCF','quantity'))
                text_liq[36]="{:02.0f}".format(dias)
                text_liq[37]="{:02.0f}".format(dias)
                text_liq[38]="{:02.0f}".format(dias) 
                text_liq[39]="{:02.0f}".format(dias)
                
                text_liq[40]="{:09.0f}".format(slip.contract_id.wage)
                text_liq[41]=slip.contract_id.type_id.clase == 'integral' and 'X' or ' '
                
                                
                base_aportes = rule(slip,'BASE_APORTES_MES','total')
                bap = round((base_aportes*dias)/30,-3) or 0.0
                text_liq[42]="{:09.0f}".format(round(bap,-3))
                text_liq[43]="{:09.0f}".format(round(bap,-3))
                text_liq[44]="{:09.0f}".format(round(bap,-3))
                text_liq[45]="{:09.0f}".format(round(bap,-3))
                round_up = lambda num: round(num,-2)+100 if num - round(num,-2)>0 else round(num,-2)
                text_liq[46]="{:01.5f}".format(rule(slip,'COT_PENSION','rate'))
                text_liq[47]="{:09.0f}".format(round(rule(slip,'COT_PENSION','total'),-2))

                text_liq[48]="{:09.0f}".format(rule(slip,'PENSION_VOL_AF','total')) #TODO REGLA
                text_liq[49]="{:09.0f}".format(rule(slip,'PENSION_VOL_EMPR','total')) #TODO REGLA
                text_liq[50]="0".rjust(9,'0') #espacio para sumatoria por el otro sistema
                
                text_liq[51]="{:09.0f}".format(rule(slip,'FONDOSOLID','total'))
                text_liq[52]="{:09.0f}".format(round(rule(slip,'FONDOSUBSISTENCIA','total')),-2)
                text_liq[53]="{:09.0f}".format(rule(slip,'NO_RET','total')) #valor no retenido por aportes voluntarios #TODO REGLA
                
                total_eps = int("{:09.0f}".format(rule(slip,'COT_EPS','total')))
                total_ups = int("{:09.0f}".format(rule(slip,'AP_VOL_UPC','total')))
                text_liq[54]="{:01.5f}".format(rule(slip,'COT_EPS','rate'))
                text_liq[55]="{:09.0f}".format(round(total_eps,-2))
                text_liq[56]="{:09.0f}".format(total_ups)
                
                if eps.id not in all_eps:
                    all_eps[eps.id] = {'eps':eps,'total': total_eps,'total_ups': total_ups,'base_aportes': base_aportes,'cantidad': 1}
                else:
                    all_eps[eps.id]['total'] += total_eps
                    all_eps[eps.id]['total_ups'] += total_ups
                    all_eps[eps.id]['base_aportes'] += base_aportes
                    all_eps[eps.id]['cantidad'] += 1
                
                text_liq[57]=''.ljust(15,' ') #no se utiliza#numero de autorizacion de la incapacidad por enfermedad general
                text_liq[58]="0".rjust(9,'0') #no se utiliza#valor de la incapacidad por enfermedad general
                
                text_liq[59]=''.ljust(15,' ') #no se utiliza#numero de autorizacion de la licencia de maternidad
                text_liq[60]="0".rjust(9,'0') #no se utiliza#valor de la incapacidad por licencia de maternidad
                
                total_arl = int("{:09.0f}".format(rule(slip,'APORTESARL','total')))
                text_liq[61]="{:01.7f}".format(rule(slip,'APORTESARL','rate'))
                
                centro_trabajo = ''
                if slip.contract_id.analytic_account_id and slip.contract_id.analytic_account_id.centro_trabajo_id:
                    centro_trabajo = str(slip.contract_id.analytic_account_id.centro_trabajo_id.code)
                
                text_liq[62]=centro_trabajo.rjust(9,'0')
                text_liq[63]="{:09.0f}".format(total_arl)
                
                arl2 = slip.contract_id.arl
                if not arl2:
                    arl2 = arl
                if not arl2.codigo_arl:
                    raise osv.except_osv(_('Error!'),_("El tercero de la ARL '%s' no tiene codigo de ARL configurado!") % (arl.name,))
                
                if arl2.id not in all_arl:
                    all_arl[arl2.id] = {'arl':arl2,'total': total_arl,'base_aportes': base_aportes,'cantidad': 1}
                else:
                    all_arl[arl2.id]['total'] += total_arl
                    all_arl[arl2.id]['base_aportes'] += base_aportes
                    all_arl[arl2.id]['cantidad'] += 1
                
                text_liq[64]="{:01.5f}".format(rule(slip,'CCF','rate'))
                text_liq[65]="{:09.0f}".format(rule(slip,'CCF','total'))
                
                text_liq[66]="{:01.5f}".format(rule(slip,'SENA','rate'))
                text_liq[67]="{:09.0f}".format(rule(slip,'SENA','total'))
                
                text_liq[68]="{:01.5f}".format(rule(slip,'ICBF','rate'))
                text_liq[69]="{:09.0f}".format(rule(slip,'ICBF','total'))
                
                text_liq[70]="{:01.5f}".format(rule(slip,'ESAP','rate'))    #TODO REGLA
                text_liq[71]="{:09.0f}".format(rule(slip,'ESAP','total'))  #TODO REGLA
                
                text_liq[72]="{:01.5f}".format(rule(slip,'MEN','rate'))    #TODO REGLA
                text_liq[73]="{:09.0f}".format(rule(slip,'MEN','total'))   #TODO REGLA
                
                text_liq[74]="".rjust(18,' ') #desconocido no referenciado en ningun lado? #TOCHECK
                text_liq[74]+="S"   #cotizante exonerado de pago de aporte de parafiscales y salud ley 1607 2012, S o N #TODO    #RES 20130425
                                    #El valor podra ser S cuando no supere 10 salario minimos y el campo 33 se diligencie con S del articulo 3 de la  RES 1747 #TOCHECK #TODO
                
                text_liq[75]+=arl2.codigo_arl.ljust(6,' ')

                if not slip.contract_id.riesgo:
                    raise osv.except_osv(_('Error!'),_("El contrato '%s' no tiene configurado el Riesgo de ARL!") % (slip.contract_id.name,))
                
                text_liq[76]+=slip.contract_id.riesgo.name.ljust(1,'0')

                # Ajustes segun Resolucion 2388 de 2016
                text_liq[79]=' ' 
                if slip.ing:
                    text_liq[80]=str(slip.contract_id.date_start  or '')
                else:   
                    text_liq[80]=''.ljust(10,' ')
       
                if slip.ret:
                    text_liq[81]=str(slip.contract_id.date_end or '') 
                else:   
                    text_liq[81]=''.ljust(10,' ')
  
                if slip.vsp:
                    text_liq[82]=str(run.date_start or '')
                else:   
                    text_liq[82]=''.ljust(10,' ')          

                #   Suspension temporal del contrato --SLN
                if slip.sln:
                    for slips in run.slip_ids:
                        if slips.sln:
                            continue
                    text_liq[83]=str(slip.leave_ids.date_from  or '')[0:10]
                    text_liq[84]=str(slip.leave_ids.date_to or '')[0:10]  
                #10 espacios para fecha de sln primera linea (VARIACION DE SALARIOS) 
                text_liq[83]=''.ljust(10,' ')  
                text_liq[84]=''.ljust(10,' ')
                #10 espacios para fecha de ige primera linea (ENFERMEDAD GENERAL)
                text_liq[85]=''.ljust(10,' ')
                text_liq[86]=''.ljust(10,' ')
                #10 espacios para fecha de lma primera linea (LICENCIA DE MATERNIDAD)
                text_liq[87]=''.ljust(10,' ')
                text_liq[88]=''.ljust(10,' ')
                text_liq[89]=''.ljust(10,' ')
                text_liq[90]=''.ljust(10,' ')
                #10 espacios para fecha de VCT primera linea (Variacion centros de produccion - VCT) PENDIENTE POR DEFINIR *
                text_liq[91]=''.ljust(10,' ')
                text_liq[92]=''.ljust(10,' ')
                #10 espacios para fecha de IRP primera linea (Retiro -- IRP)
                text_liq[93]=''.ljust(10,' ')
                text_liq[94]=''.ljust(10,' ')
                #10 espacios para IBC OTROS PENDIENTE POR DEFINIR * (correciones)
                # text_liq[95]=''.ljust(10,' ')                  

                #Horas trabajadas
                # for horas in slip.worked_days_line_ids.filtered(lambda x: x.code in ['WORK100']):
                #     # text_liq[77]=' '
                #     text_liq[96]=str(horas.number_of_hours  or '')[0:3].rjust(12,'0')
                #     # 000000000300
                #     text_liq[97]=''.ljust(10,' ')               
                text_liq[96]=str(int(dias*slip.contract_id.working_hours.hours_payslip)).rjust(12,'0')
                # 000000000300
                text_liq[97]=''.ljust(10,' ')             

                #se agrega la linea original
                for x in text_liq:
                    text_final+=x
                text_final+=line_end

                # VACACIONES, Licencia remunerada
                _logger.info('leaves')
                if slip.leave_ids:
                    for x in  slip.leave_ids:
                        #text_liq[46]="{:01.5f}".format(0)
                        text_liq[46]="{:01.5f}".format(rule(slip,'COT_PENSION','rate'))
                        text_liq[47]="{:09.0f}".format(0)
                        text_liq[48]="{:09.0f}".format(0) #TODO REGLA
                        text_liq[49]="{:09.0f}".format(0) #TODO REGLA
                        text_liq[50]="0".rjust(9,'0') #espacio para sumatoria por el otro sistema
                        text_liq[51]="{:09.0f}".format(0)
                        text_liq[52]="{:09.0f}".format(0)
                        text_liq[53]="{:09.0f}".format(0) #valor no retenido por aportes voluntarios #TODO REGLA
                        text_liq[54]="{:01.5f}".format(0)
                        text_liq[55]="{:09.0f}".format(0)
                        text_liq[56]="{:09.0f}".format(0)

                        text_liq[61]="{:01.7f}".format(0)
                        text_liq[62]=''.rjust(9,'0')
                        text_liq[63]="{:01.5f}".format(0)
                        text_liq[63]="{:09.0f}".format(0)

                        text_liq[64]="{:01.5f}".format(0)
                        text_liq[65]="{:09.0f}".format(0)
                        text_liq[66]="{:01.5f}".format(0)
                        text_liq[67]="{:09.0f}".format(0)
                        text_liq[68]="{:01.5f}".format(0)
                        text_liq[69]="{:09.0f}".format(0)
                        text_liq[70]="{:01.5f}".format(0)    #TODO REGLA
                        text_liq[71]="{:09.0f}".format(0)  #TODO REGLA
                        text_liq[72]="{:01.5f}".format(0)    #TODO REGLA
                        text_liq[73]="{:09.0f}".format(0)   #TODO REGLA
                        text_liq[85]=''.ljust(10,' ')
                        text_liq[86]=''.ljust(10,' ')
                        text_liq[87]=''.ljust(10,' ')
                        text_liq[88]=''.ljust(10,' ')
                        text_liq[89]=''.ljust(10,' ')
                        text_liq[90]=''.ljust(10,' ')
                        text_liq[93]=''.ljust(10,' ')
                        text_liq[94]=''.ljust(10,' ')
                        text_liq[82]=''.ljust(10,' ')
                        dias = 0
                        for y in slip.leave_days_ids:
                            if x.holiday_status_id.id == y.holiday_status_id.id:
                                dias+=y.days_payslip
                        text_liq[96]=str(int(dias*slip.contract_id.working_hours.hours_payslip)).rjust(12,'0')
                        bap = round((base_aportes*dias)/30,-3) or 0.0
                        #  Incapacidad temporal por licencia de maternidad -- LMA
                        if x.holiday_status_id.code in ('LICENCIA_MATERNIDAD','LMA'):
                            #se marcan las x en novedades en  la nueva linea
                            text_liq[15]=''.ljust(1,' ')
                            text_liq[16]=''.ljust(1,' ')
                            text_liq[17]=''.ljust(1,' ')
                            text_liq[18]=''.ljust(1,' ')
                            text_liq[19]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[20]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[21]=''.ljust(1,' ')
                            text_liq[22]=''.ljust(1,' ')
                            text_liq[23]=''.ljust(1,' ')
                            text_liq[24]=''.ljust(1,' ') #TOREWORK X o C #RES 20120321
                            text_liq[25]=''.ljust(1,' ')
                            text_liq[26]=nov(slip.lma)
                            text_liq[27]=''.ljust(1,' ')
                            text_liq[28]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[29]=''.ljust(1,' ')
                            text_liq[30]=str(slip.irp).rjust(2,'0')

                            if not x.date_from or not x.date_to:
                                raise Warning('El codigo de la incapacidad por linencia de materniadad no esta definido como LICENCIA_MATERNIDAD o LMA')

                            # los dias estan fueras del periodo
                            if int(str(slip.payslip_period_id.start_date)[5:7]) > int(str(x.date_from[5:7])):
                            	text_liq[87]=str(slip.payslip_period_id.start_date or '')[0:10].ljust(10,' ')
                            else:
                            	text_liq[87]=str(x.date_from or '')[0:10].ljust(10,' ')

                            if int(str(slip.payslip_period_id.end_date)[5:7]) < int(str(x.date_to[5:7])):
                            	text_liq[88]=str(slip.payslip_period_id.end_date or '')[0:10].ljust(10,' ')
                            else:
                            	text_liq[88]=str(x.date_to or '')[0:10].ljust(10,' ')

                            #dias cotizados por ausencia
                            for nbap in range(36,40):
                                text_liq[nbap]="{:02.0f}".format(dias)
                            #proporcion de base de aportes en funcion de dias de ausencia
                            for nbap in range(42,46):
                                text_liq[nbap]="{:09.0f}".format(bap)
                        #  Incapacidad temporal por enfermedad general -- IGE
                        if x.holiday_status_id.code in ('INCAPACIDAD_ENF_GENERAL','IGE'):
                            #se marcan las x en novedades en  la nueva linea
                            text_liq[15]=''.ljust(1,' ')
                            text_liq[16]=''.ljust(1,' ')
                            text_liq[17]=''.ljust(1,' ')
                            text_liq[18]=''.ljust(1,' ')
                            text_liq[19]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[20]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[21]=''.ljust(1,' ')
                            text_liq[22]=''.ljust(1,' ')
                            text_liq[23]=''.ljust(1,' ')
                            text_liq[24]=''.ljust(1,' ') #TOREWORK X o C #RES 20120321
                            text_liq[25]=nov(slip.ige)
                            text_liq[26]=''.ljust(1,' ')
                            text_liq[27]=''.ljust(1,' ')
                            text_liq[28]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[29]=''.ljust(1,' ')
                            text_liq[30]=str(slip.irp).rjust(2,'0')

                            if not x.date_from or not x.date_to:
                                raise Warning('El codigo de la incapacidad por enfermedad general no esta definido como INCAPACIDAD_ENF_GENERAL o IGE')

                            # if dias < x.number_of_days_in_payslip and str(slip.payslip_period_id.start_date)[5:7] != str(x.date_from):
                            #     text_liq[85]=str(slip.payslip_period_id.start_date or '')[0:10].ljust(10,' ')
                            # if dias < x.number_of_days_in_payslip and str(slip.payslip_period_id.end_date)[5:7] != str(x.date_to): 
                            #     text_liq[86]=str(slip.payslip_period_id.end_date or '')[0:10].ljust(10,' ')
                            # else:
                            #     text_liq[85]=str(x.date_from or '')[0:10].ljust(10,' ')
                            #     text_liq[86]=str(x.date_to or '')[0:10].ljust(10,' ')

                            # los dias estan fueras del periodo
                            if int(str(slip.payslip_period_id.start_date)[5:7]) > int(str(x.date_from[5:7])):
                            	text_liq[85]=str(slip.payslip_period_id.start_date or '')[0:10].ljust(10,' ')
                            else:
                            	text_liq[85]=str(x.date_from or '')[0:10].ljust(10,' ')

                            if int(str(slip.payslip_period_id.end_date)[5:7]) < int(str(x.date_to[5:7])):
                            	text_liq[86]=str(slip.payslip_period_id.end_date or '')[0:10].ljust(10,' ')
                            else:
                            	text_liq[86]=str(x.date_to or '')[0:10].ljust(10,' ')
                            
                            #dias cotizados por ausencia
                            for nbap in range(36,40):
                                text_liq[nbap]="{:02.0f}".format(dias)
                            #proporcion de base de aportes en funcion de dias de ausencia
                            for nbap in range(42,46):
                                text_liq[nbap]="{:09.0f}".format(bap)
                        #  Incapacidad temporal por enfermedad laboral -- IRP
                        if x.holiday_status_id.code in ('AT/EP','IRP'):
                            #se marcan las x en novedades en  la nueva linea
                            text_liq[15]=''.ljust(1,' ')
                            text_liq[16]=''.ljust(1,' ')
                            text_liq[17]=''.ljust(1,' ')
                            text_liq[18]=''.ljust(1,' ')
                            text_liq[19]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[20]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[21]=''.ljust(1,' ')
                            text_liq[22]=''.ljust(1,' ')
                            text_liq[23]=''.ljust(1,' ')
                            text_liq[24]=''.ljust(1,' ') #TOREWORK X o C #RES 20120321
                            text_liq[25]=''.ljust(1,' ')
                            text_liq[26]=''.ljust(1,' ')
                            text_liq[27]=''.ljust(1,' ')
                            text_liq[28]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[29]=''.ljust(1,' ')
                            text_liq[30]=str(slip.irp).rjust(2,'0')

                            if not x.date_from or not x.date_to:
                                raise Warning('El codigo de la incapacidad por AT/EP no esta definido como AT/EP o IRP')

                            # if dias < x.number_of_days_in_payslip and str(slip.payslip_period_id.start_date)[5:7] != str(x.date_from):
                            #     text_liq[93]=str(slip.payslip_period_id.start_date or '')[0:10].ljust(10,' ')
                            # elif dias < x.number_of_days_in_payslip and str(slip.payslip_period_id.end_date)[5:7] != str(x.date_to): 
                            #     text_liq[94]=str(slip.payslip_period_id.end_date or '')[0:10].ljust(10,' ')
                            # else:
                            #     text_liq[93]=str(x.date_from or '')[0:10].ljust(10,' ')
                            #     text_liq[94]=str(x.date_to or '')[0:10].ljust(10,' ')

                            # los dias estan fueras del periodo
                            if int(str(slip.payslip_period_id.start_date)[5:7]) > int(str(x.date_from[5:7])):
                            	text_liq[93]=str(slip.payslip_period_id.start_date or '')[0:10].ljust(10,' ')
                            else:
                            	text_liq[93]=str(x.date_from or '')[0:10].ljust(10,' ')

                            if int(str(slip.payslip_period_id.end_date)[5:7]) < int(str(x.date_to[5:7])):
                            	text_liq[94]=str(slip.payslip_period_id.end_date or '')[0:10].ljust(10,' ')
                            else:
                            	text_liq[94]=str(x.date_to or '')[0:10].ljust(10,' ')

                            #dias cotizados por ausencia
                            for nbap in range(36,40):
                                text_liq[nbap]="{:02.0f}".format(dias)
                            #proporcion de base de aportes en funcion de dias de ausencia
                            for nbap in range(42,46):
                                text_liq[nbap]="{:09.0f}".format(bap)
                        # Incapacidad Vacaciones
                        if x.holiday_status_id.code == 'VAC':
                            # if dias < x.number_of_days: 
                            #     text_liq[89]=str(slip.payslip_period_id.start_date  or ''.ljust(10,' '))[0:10]
                            #     text_liq[90]=str(slip.payslip_period_id.end_date or '')[0:10].ljust(10,' ')
                            # else:
                            #     text_liq[89]=str(x.date_from  or ''.ljust(10,' '))[0:10]
                            #     text_liq[90]=str(x.date_to or '')[0:10].ljust(10,' ')

                            # los dias estan fueras del periodo
                            if int(str(slip.payslip_period_id.start_date)[5:7]) > int(str(x.date_from[5:7])):
                            	text_liq[89]=str(slip.payslip_period_id.start_date or '')[0:10].ljust(10,' ')
                            else:
                            	text_liq[89]=str(x.date_from or '')[0:10].ljust(10,' ')

                            if int(str(slip.payslip_period_id.end_date)[5:7]) < int(str(x.date_to[5:7])):
                            	text_liq[90]=str(slip.payslip_period_id.end_date or '')[0:10].ljust(10,' ')
                            else:
                            	text_liq[90]=str(x.date_to or '')[0:10].ljust(10,' ')
                            
                           #se marcan las x en novedades en  la nueva linea
                            text_liq[15]=''.ljust(1,' ')
                            text_liq[16]=''.ljust(1,' ')
                            text_liq[17]=''.ljust(1,' ')
                            text_liq[18]=''.ljust(1,' ')
                            text_liq[19]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[20]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[21]=''.ljust(1,' ')
                            text_liq[22]=''.ljust(1,' ')
                            text_liq[23]=''.ljust(1,' ')
                            text_liq[24]=''.ljust(1,' ') #TOREWORK X o C #RES 20120321
                            text_liq[25]=''.ljust(1,' ')
                            text_liq[26]=''.ljust(1,' ')
                            text_liq[27]=nov(slip.vac)
                            text_liq[28]=''.ljust(1,' ') #no aplica para extranjero
                            text_liq[29]=''.ljust(1,' ')
                            text_liq[30]=str(slip.irp).rjust(2,'0')

                            #dias cotizados por ausencia
                            for nbap in range(36,40):
                                text_liq[nbap]="{:02.0f}".format(dias)
                            #proporcion de base de aportes en funcion de dias de ausencia
                            for nbap in range(42,46):
                                text_liq[nbap]="{:09.0f}".format(bap)
                            # #Novedades
                            # for num in range(15,30):
                            #     if num == 27:
                            #         text_liq[27]=nov(slip.vac)
                            #     else:
                            #         text_liq[27]=''.ljust(1,' ')                       
                        for x in text_liq:
                            text_final+=x
                        text_final+=line_end



        file_text = base64.b64encode(text_final)
        file_name = str(strip_accents(final_file_name + '.txt'))
        self.write(cr, uid, ids,{'name':file_name,'file_text': file_text,})
        active_pool.write(cr, uid, context.get('active_ids'),{'file_name':file_name,'file_text': file_text,'time_of_process': self.browse(cr, uid, ids)[0].date})
        
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': self._name,
            'target': 'new',
            'context': context,
            'res_id': ids[0]
        }
        

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
            

