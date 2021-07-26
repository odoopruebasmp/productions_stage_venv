# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
import openerp.netsvc
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil import relativedelta, parser
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval
from openerp.addons.edi import EDIMixin
from calendar import monthrange
from openerp import models, api, _, fields as fields2

class res_company(osv.osv):
    _inherit = "res.company"
    
    _columns = {
        'arl_id': fields.many2one('res.partner', 'ARL', domain="[('arl','=','True')]", help="ARL Empresarial", required=True),
    }

class retencion_fuente_period(osv.osv):
    _name = "hr.contract.retencion.period"
    
    _columns = {
        'date_from': fields.date('Fecha desde',required=True),
        'date_to': fields.date('Fecha hasta',required=True),
        'name': fields.char('Nombre',size=64,required=True),
    }

class retencion_fuente_dos(osv.osv):
    _name = "hr.contract.retencion.dos"
    
    _columns = {
        'period_id': fields.many2one('hr.contract.retencion.period', 'Periodo que Aplica',required=True),
        'contract_id': fields.many2one('hr.contract', 'Contrato',required=True),
        'valor_porcentaje': fields.float('Porcentaje(%)', digits_compute= dp.get_precision('Payroll Rate'),required=True),
        'aplica': fields.boolean('Aplicar'),
    }

class hr_holidays_status_incapacity(osv.osv):
    _name = "hr.holidays.status.incapacity"
    _description = "Diagnostico"

    _columns = {
        'name':fields.char("Descripcion" , size = 128 , required = True),
        'code':fields.char("codigo" , size = 32 , required = True),
    }

class hr_salary_rule(osv.osv):
    _inherit = 'hr.salary.rule'
    
    _columns = {
        'tipo_retefuente': fields.selection([('minima', 'Minima'),('tradicional', 'Tradicional'),], 'Tipo Retefuente',help='Dejar vacio si esto no esta una regla de Retefuente'),
        'tipo_tercero': fields.selection((('empleado','Empleado'), ('eps','EPS'), ('arl','ARL'), ('cesantias','Fondo Cesantias'), ('pensiones','Fondo Pensiones'), ('cajacomp','CCF'), ('otros','Otros')),'Tipo'),
        'partner_contable_id':fields.many2one('res.partner','Tercero Contable'),
    }
    
    def compute_rule(self, cr, uid, rule_id, localdict, context=None):
        rule = self.browse(cr, uid, rule_id, context=context)
        amount, qty, rate = super(hr_salary_rule, self).compute_rule(cr, uid, rule_id, localdict, context=context)
        if rule.tipo_retefuente:
            retef = self.pool.get('variables.economicas.retefuente')
            payslip = localdict['payslip']
            if amount == 'na':
                return amount, qty, rate
            tot_rule = amount * qty * rate / 100.0
            valor = retef.get_valor_pesos( cr, uid, payslip.start_period, tot_rule, context=context)[rule.tipo_retefuente]
            return valor, 1, 100.0
        else:
            return amount, qty, rate

class hr_contract_eps_change(osv.osv):
    _name = 'hr.contract.eps.change'
    _order = 'date desc'
    _rec_name = "date"

    _columns = {
        'contract_id':fields.many2one('hr.contract','Contrato', required=True),
        'eps':fields.many2one('res.partner','EPS', domain="[('eps','=','True')]", required=True),
        'user_id':fields.many2one('res.users','Responsable', required=True, readonly=True),
        'date':fields.datetime('Fecha', required=True),
    }
    
    _defaults = {
        'date': lambda *args: time.strftime('%Y-%m-%d %H:%M:%S'),
        'user_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id,
    }
    
class hr_contract_cesantias_change(osv.osv):
    _name = 'hr.contract.cesantias.change'
    _order = 'date desc'
    _rec_name = "date"

    _columns = {
        'contract_id':fields.many2one('hr.contract','Contrato', required=True),
        'cesantias':fields.many2one('res.partner','Fondo Cesantias', domain="[('afp','=','True')]", required=True),
        'user_id':fields.many2one('res.users','Responsable', required=True, readonly=True),
        'date':fields.datetime('Fecha', required=True),
    }
    
    _defaults = {
        'date': lambda *args: time.strftime('%Y-%m-%d %H:%M:%S'),
        'user_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id,
    }
    
class hr_contract_pensiones_change(osv.osv):
    _name = 'hr.contract.pensiones.change'
    _order = 'date desc'
    _rec_name = "date"

    _columns = {
        'contract_id':fields.many2one('hr.contract','Contrato', required=True),
        'pensiones':fields.many2one('res.partner','Fondo Pensiones', domain="[('afp','=','True')]", required=True),
        'user_id':fields.many2one('res.users','Responsable', required=True, readonly=True),
        'date':fields.datetime('Fecha', required=True),
    }
    
    _defaults = {
        'date': lambda *args: time.strftime('%Y-%m-%d %H:%M:%S'),
        'user_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id,
    }

#===============================================================================
# HR CONTRACT RISK CLASS
#===============================================================================
class hr_contract_risk(osv.osv):
    _name = 'hr.contract.risk'
    _description = 'Contract Risk'
    _columns = {
        'name': fields.char('riesgo', size=250),
        'pct_risk':fields.float('porcentaje de riesgo', digits=(16,6)),
    }
hr_contract_risk()


class hr_fiscal_subtype(osv.osv):
    _name = "hr.fiscal.subtype"
    _description = "Tipo de cotizante"
    
    _columns = {
        'name': fields.char('Nombre', size=64, required=True),
        'code': fields.char('Codigo', size=64, required=True),
        'note': fields.text('Notas'),
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codgigo tiene que ser unico!'),
    ]

class hr_contract(osv.osv):
    _inherit = "hr.contract"
        
    def _calculo_vacaciones_pendientes(self, cr, uid, ids, name, args, context=None):
        res = {}
        for contract in self.browse(cr, uid, ids, context=context):
            vacas = 0
            for line in contract.leave_ids:
                if line.holiday_status_id.vacaciones and (line.state=='validate' or line.state=='paid'):
                    
                    vacas += line.number_of_days
                    
            res[contract.id] = vacas
        return res
    
    def _last_eps_assigned(self, cr, uid, ids, context=None):
        result = {}
        for assign in self.pool.get('hr.contract.eps.change').browse(cr, uid, ids, context=context):
            if assign.contract_id:
                result[assign.contract_id.id] = assign.eps.id
        return result.keys()
        
    def _last_cesantias_assigned(self, cr, uid, ids, context=None):
        result = {}
        for assign in self.pool.get('hr.contract.cesantias.change').browse(cr, uid, ids, context=context):
            if assign.contract_id:
                result[assign.contract_id.id] = assign.cesantias.id
        return result.keys()
    
    def _last_pensiones_assigned(self, cr, uid, ids, context=None):
        result = {}
        for assign in self.pool.get('hr.contract.pensiones.change').browse(cr, uid, ids, context=context):
            if assign.contract_id:
                result[assign.contract_id.id] = assign.pensiones.id
        return result.keys()
    
    _columns = {
        'fiscal_type_id': fields.many2one('hr.fiscal.type', "Tipo de Cotizante", required=True),
        'fiscal_subtype_id': fields.many2one('hr.fiscal.subtype', "Subtipo de Cotizante"),
        'eps_historic_ids':fields.one2many('hr.contract.eps.change','contract_id','EPS'),
        'eps' : fields.related('eps_historic_ids', 'eps', string = 'EPS', type='many2one', relation ='res.partner',
                    store ={
                    'hr.contract.eps.change': (_last_eps_assigned, ['user_id', 'date', 'eps'], 10),
                    }, domain="[('eps','=','True')]", readonly=True),
        'cesantias_historic_ids':fields.one2many('hr.contract.cesantias.change','contract_id','Fondo Cesantias'),
        'cesantias' : fields.related('cesantias_historic_ids', 'cesantias', string = 'Fondo Cesantias', type='many2one', relation ='res.partner',
                    store ={
                    'hr.contract.cesantias.change': (_last_cesantias_assigned, ['user_id', 'date', 'cesantias'], 10),
                    }, domain="[('afp','=','True')]", readonly=True),
        'pensiones_historic_ids':fields.one2many('hr.contract.pensiones.change','contract_id','Fondo Pensiones'),
        'pensiones' : fields.related('pensiones_historic_ids', 'pensiones', string = 'Fondo Pensiones', type='many2one', relation ='res.partner',
                    store ={
                    'hr.contract.pensiones.change': (_last_pensiones_assigned, ['user_id', 'date', 'pensiones'], 10),
                    }, domain="[('afp','=','True')]", readonly=True),
        'cajacomp': fields.many2one('res.partner', 'CCF', domain="[('cajacomp','=','True')]", help="Caja Compensacion"),
        'arl': fields.many2one('res.partner', 'ARL', domain="[('arl','=','True')]", help="ARL en el caso que el empleado sea independiente"),
        'dias_vacaciones_pendientes': fields.function(_calculo_vacaciones_pendientes, type='float', string='Vacaciones Pendientes'),
        'retencion_dos_ids': fields.one2many('hr.contract.retencion.dos', 'contract_id', 'Retencion en la Fuente P2'),
        'fondo_cesantia': fields.many2one('res.partner', 'fondo_cesantia', domain="[('fondo_cesantia','=','True')]", help="Fondo de cesantia"),
        'bono': fields.float('bono'),
        'riesgo': fields.many2one('hr.contract.risk', 'riesgo'),
        'pct_arp': fields.related('riesgo', 'pct_risk', string = 'Porcentaje Riesgo', type='float',store=True, digits=(16,6)),
        'p2': fields.boolean('Aplica procedimiento 2?'),
        'declarante': fields.boolean('Declarante'),
        'promedio_p2': fields.float('Promedio salud ano anterior'),
        'termino': fields.char('termino'),
    }

class hr_contract_api(models.Model):
    _inherit = "hr.contract"
    
    reform = fields2.Selection([('anterior', 'Regimen Anterior')], string='Ley de reforma', required=False)
   
class hr_holidays_vacaciones(osv.osv):
    _inherit = "hr.holidays.status"
    
    def asignacion_vacaciones(self, cr, uid, dias=False, context=None):
        contract_obj = self.pool.get('hr.contract')
        holiday_obj = self.pool.get('hr.holidays')
        holidayStatus_obj = self.pool.get('hr.holidays.status')
        wf_service = openerp.netsvc.LocalService("workflow")
        vacaciones_id = holidayStatus_obj.search(cr, uid, [('name', '=', 'Vacaciones')], context=context)
        dias = dias or 15
        if not vacaciones_id:
            raise osv.except_osv(_('Error!'),_('El tipo de ausencia Vacaciones no esta parametrizado!'))
        vacaciones_id = vacaciones_id[0]
        fecha_hoy = fecha_desde = datetime.now()
        fecha_desde = fecha_hasta = fecha_hoy.strftime(DEFAULT_SERVER_DATE_FORMAT)
        contract_ids = contract_obj.search(cr, uid, ['|', ('date_end', '>=', fecha_hasta), ('date_end', '=', False), ('termino', '=', 'indefinido'), ('date_start', '<=', fecha_desde)], context=context, order='company_id asc')
        if contract_ids:
            for contract in contract_ids:
                contract = contract_obj.browse(cr, uid, contract, context)
                empleado = contract.employee_id
                contrato_fecha = datetime.strptime(contract.date_start,"%Y-%m-%d")
                borrar_ids = holiday_obj.search(cr, uid, [('employee_id', '=', empleado.id), ('type', '=', 'add'), ('holiday_status_id', '=', vacaciones_id)], context=context)
                for borrar in borrar_ids:
                    holiday_obj.write(cr, uid, [borrar] ,{'date_from':False})
                holiday_obj.set_to_draft(cr, uid, borrar_ids, context=None)
                holiday_obj.unlink(cr, uid, borrar_ids, context)
                aun_hay = True
                anios=0
                vacaciones = []
                while(aun_hay):
                    anios+=1
                    fecha_to = (contrato_fecha+relativedelta.relativedelta(years=anios))
                    if fecha_to <= fecha_hoy:
                        days = dias
                        fecha_from = contrato_fecha+relativedelta.relativedelta(years=anios-1)
                        data = {
                            'holiday_status_id': vacaciones_id,
                            'employee_id': empleado.id,
                            'contract_id': contract.id,
                            'name': 'asignacion de vacaciones anual',
                            'number_of_days': days,
                            'number_of_days_dummy': days,
                            'number_of_days_temp': days,
                            'holiday_type': 'employee',
                            'state': 'validate',
                            'type': 'add',
                            'date_from': fecha_from,
                            'date_to': fecha_to-relativedelta.relativedelta(days=1),
                            }
                        holiday = holiday_obj.create(cr, uid, data, context)
                        vacaciones.append(holiday)
                        wf_service.trg_validate(uid, 'hr.holidays', holiday, 'confirm', cr)
                        wf_service.trg_validate(uid, 'hr.holidays', holiday, 'validate', cr)
                        holiday_obj.write(cr, uid, [holiday] ,{'approve_date':fecha_to})
                    else:
                        aun_hay=False
        return True
    
    def asignacion_vacaciones_totales(self, cr, uid, context=None):
        contract_obj = self.pool.get('hr.contract')
        holiday_obj = self.pool.get('hr.holidays')
        holidayStatus_obj = self.pool.get('hr.holidays.status')
        wf_service = openerp.netsvc.LocalService("workflow")
        aun_hay = True
        fecha = fecha_desde = datetime.now()
        fecha_hasta = fecha.strftime(DEFAULT_SERVER_DATE_FORMAT)
        anios=0
        while(aun_hay):
            anios+=1
            contract_ids = contract_obj.search(cr, uid, ['|', ('date_end', '<=', fecha_hasta), ('date_end', '=', False), ('termino', '=', 'indefinido')], context=context, order='company_id asc')
            if not contract_ids:
                aun_hay=False
            else:
                for contract in contract_ids:
                    contract = contract_obj.browse(cr, uid, contract, context)
                    empleado = contract.employee_id
                    vacaciones_id = holidayStatus_obj.search(cr, uid, [('name', '=', 'Vacaciones')], context=context)
                    if not vacaciones_id:
                        raise osv.except_osv(_('Error!'),_('El tipo de ausencia Vacaciones no esta parametrizado!'))
                    vacaciones_id = vacaciones_id[0]
                    borrar_ids = holiday_obj.search(cr, uid, [('employee_id', '=', empleado.id), ('type', '=', 'add'), ('holiday_status_id', '=', vacaciones_id)], context=context)
                    
                    holiday_obj.unlink(cr, uid, borrar_ids, context)
                    days = anios*15
                    data = {
                        'holiday_status_id': vacaciones_id,
                        'employee_id': empleado.id,
                        'name': 'vacaciones totales permitidas',
                        'number_of_days': days,
                        'number_of_days_dummy': days,
                        'number_of_days_temp': days,
                        'holiday_type': 'employee',
                        'state': 'validate',
                        'type': 'add',
                        'approve_date': fecha_hasta,
                        }
                    holiday = holiday_obj.create(cr, uid, data, context)
                    wf_service.trg_validate(uid, 'hr.holidays', holiday, 'confirm', cr)
                    wf_service.trg_validate(uid, 'hr.holidays', holiday, 'validate', cr)
        return True
        
#de hr contract_extended_co
class res_partner(osv.osv):
    _inherit = "res.partner"
    
    _columns = {
        'eps': fields.boolean('Entidad Promotora Salud (EPS)'),
        'arl': fields.boolean('Sistema Risgos laborales (ARL)'),
        'afp': fields.boolean('Administradora Fondos Pensiones y Cesantias (AFP)'),
        'cajacomp': fields.boolean('Caja Compensacion Familiar (CCF)'),
        'codigo_eps' : fields.char('Codigo EPS', size=6),
        'codigo_arl' : fields.char('Codigo Ministerio', size=6),
        'codigo_afp' : fields.char('Codigo Pension', size=6),
        'codigo_ccf' : fields.char('Codigo CCF', size=6),
    }


class hr_payslip(osv.osv):
    _inherit = 'hr.payslip'
    
    def get_partner_process_sheet(self, cr, uid, line, slip, context=None):

        partner_id = slip.employee_id.partner_id.id
        if line.salary_rule_id.tipo_tercero == 'eps':
            partner_id = slip.contract_id.eps.id
        elif line.salary_rule_id.tipo_tercero == 'arl':
            partner_id = slip.contract_id.arl.id
        elif line.salary_rule_id.tipo_tercero == 'pensiones':
            partner_id = slip.contract_id.pensiones.id
        elif line.salary_rule_id.tipo_tercero == 'cesantias':
            partner_id = slip.contract_id.cesantias.id
        elif line.salary_rule_id.tipo_tercero == 'cajacomp':
            partner_id = slip.contract_id.cajacomp.id
        elif line.salary_rule_id.tipo_tercero == 'fondo_cesantia':
            partner_id = slip.contract_id.fondo_cesantia.id
        elif line.salary_rule_id.tipo_tercero == 'otros':
            partner_id = line.salary_rule_id.partner_contable_id.id
            
        return partner_id
      
class hr_holidays(osv.osv):
    _inherit = "hr.holidays"
        
    _columns = {
        'no_incapacidad': fields.char('Numero Autorizacion EPS' ,size=64, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'incapacity': fields.many2one('hr.holidays.status.incapacity', 'Incapacity', help="Incapacidad"),
        'at_date': fields.date('Fecha de referencia'),

    }
    
