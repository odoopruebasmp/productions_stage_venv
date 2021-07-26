# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp import models, api, _, sql_db
from openerp import fields as fields2
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as DSDF, DEFAULT_SERVER_DATETIME_FORMAT as DSTF, float_compare
from openerp.tools.translate import _
import openerp.netsvc
from datetime import datetime, timedelta
import time
from dateutil.relativedelta import relativedelta
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as s_eval
from openerp.addons.edi import EDIMixin
from openerp import SUPERUSER_ID
import re
from openerp.exceptions import except_orm, Warning
from openerp.addons.avancys_orm import avancys_orm as orm


RETIROS = [('retvoltra', 'Retiro Voluntario del Trabajador'),
           ('terlabcon', 'Terminación de la Labor Contratada'),
           ('canjuscau', 'Cancelación por Justa Causa'),
           ('terconpba', 'Terminación del Contrato en Periodo de Prueba'),
           ('retnotjuscau', 'Retiro sin Justa Causa'),
           ('expplafij', 'Expiracion plazo fijo pactado'),
           ('decunicom', 'Decisión Unilateral de la Compañía'),
           ('fal', 'Fallecimiento'),
           ('pen', 'Pensionado'),
           ('nolab', 'No Laboro'),
           ('termutacu', 'Terminación Mutuo Acuerdo')]


class hr_fiscal_type(osv.osv):
    _name = "hr.fiscal.type"
    _description = "Tipo de cotizante"
    
    _columns = {
        'name': fields.char('Nombre', size=64, required=True),
        'code': fields.char('Codigo', size=64, required=True),
        'note': fields.text('Notas'),
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codigo tiene que ser unico!'),
    ]

class payslip_type(osv.osv):
    _name = "hr.payslip.type"
    _description = "Tipo de nomina"
    
    _columns = {
        'name': fields.char('Nombre', size=64, required=True),
        'code': fields.char('Codigo', size=64, required=True),
        'holiday_status_id': fields.many2one('hr.holidays.status', 'Ausencia que paga',help="Tipo de ausencia que paga"),
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codigo tiene que ser unico!'),
    ]

class res_partner(osv.osv):
    _inherit = 'res.partner'
    
    #funciones para crear un one2one entre employee y partner
    def create(self, cr, uid, vals, context=None):
        res = super(res_partner, self).create(cr, uid, vals, context=context)
        employee_id = vals.get('employee_id')
        if not context:
            context={}
        ctx = context.copy()
        context = ctx
        if employee_id and not context.get('do_not_repeat'):
            context.update({'do_not_repeat':True})
            employee_obj = self.pool.get('hr.employee')
            employee_obj.write(cr, uid, [employee_id], {'partner_id': res}, context=context)  
        return res
        
    def write(self, cr, uid, ids, vals, context=None):
        employee_id = vals.get('employee_id')
        if not context:
            context={}
        ctx = context.copy()
        context = ctx
        if employee_id and not context.get('do_not_repeat'):
            context.update({'do_not_repeat':True})
            employee_obj = self.pool.get('hr.employee')
            partner = self.browse(cr, uid, ids[0],context=context)
            employee_obj.write(cr, uid, [employee_id], {'partner_id': ids[0],'name':partner.name}, context=context)
        partner_name = vals.get('name')
        if partner_name:
            employee_obj = self.pool.get('hr.employee')
            for partner in self.browse(cr, uid, ids, context=context):
                if partner.employee_id:
                    employee_obj.write(cr, uid, [partner.employee_id.id], {'name':partner_name}, context=context)
            
        return super(res_partner, self).write(cr, uid, ids, vals, context=context)
    
    _columns = {
        'employee_id': fields.many2one('hr.employee', 'Informacion de Empleado'),
    }
    
class hr_payslip_worked_days(osv.osv):
    _inherit = 'hr.payslip.worked_days'
    
    _columns = {
        'symbol': fields.char(' ', size=8, required=True),
    }

class resource_resource(osv.osv):
    _inherit = "resource.resource"
    
    _columns = {
        'user_id': fields.related('partner_id', 'system_user_id', type="many2one", relation="res.users", string="Usuario OpenERP", readonly=True, store=True),
        'partner_id': fields.many2one('res.partner', 'Tercero'),
        'name': fields.char('Name', size=128, required=True),
    }

class rh(osv.osv):
    _name = "hr.contract.rh"
    
    _columns = {
        'name' : fields.char('Nombre', size=32),
    }

class hr_employee(osv.osv, EDIMixin):
    _name = 'hr.employee'
    _description = "Empleado"
    _inherit = ['hr.employee', 'mail.thread', 'ir.needaction_mixin']
    
    #funciones para crear un one2one entre employee y partner
    def create(self, cr, uid, vals, context=None):
        res = super(hr_employee, self).create(cr, uid, vals, context=context)
        partner_id = vals.get('partner_id')
        if partner_id and not context.get('do_not_repeat'):
            context.update({'do_not_repeat':True})
            partner_obj = self.pool.get('res.partner')
            partner_obj.write(cr, uid, [partner_id], {'employee_id': res}, context=context)
        return res
    def write(self, cr, uid, ids, vals, context=None):
        partner_id = vals.get('partner_id')
        if partner_id and not context.get('do_not_repeat'):
            context.update({'do_not_repeat':True})
            partner_obj = self.pool.get('res.partner')
            partner = partner_obj.browse(cr, uid, partner_id,context=context)
            vals.update({'user_id':partner.system_user_id.id})
            
            for empleado in self.browse(cr, uid, ids, context=context):
                partner_ids = partner_obj.search(cr, uid, [('employee_id','=',empleado.id)], context=context)
                if partner_ids:
                    partner_obj.write(cr, uid, partner_ids, {'employee_id': False}, context=context)
            
            partner_obj.write(cr, uid, [partner_id], {'employee_id': ids[0]}, context=context)
        return super(hr_employee, self).write(cr, uid, ids, vals, context=context)
    
    _columns = {
        'child_ids': fields.one2many('hr.employee', 'parent_id', 'Subordinados'),
        'nombre_uno': fields.related('partner_id', 'primer_nombre' ,type="char", string="Primer Nombre", readonly=True),
        'nombre_dos': fields.related('partner_id', 'otros_nombres', type="char", string="Otros Nombres", readonly=True),
        'apellido_uno': fields.related('partner_id', 'primer_apellido', type="char", string="Primer Apellido", readonly=True),
        'apellido_dos': fields.related('partner_id', 'segundo_apellido', type="char", string="Segundo Apellido", readonly=True),
        'home_address': fields.related('partner_id', 'street', type="char", string="Direccion Particular", readonly=True),
        'home_phone': fields.related('partner_id', 'phone', type="char", string="Telefono Particular", readonly=True),
        'home_mobile_phone': fields.related('partner_id', 'mobile', type="char", string="Telefono Movil Particular", readonly=True),
        'identification_id': fields.related('partner_id', 'ref', type="char", string="Identificacion", readonly=True),
        'rh': fields.many2one('hr.contract.rh', 'RH'),
        'address_id': fields.many2one('res.partner', 'Working Address'),
        'marital': fields.selection([('single', 'Single'), ('married', 'Married'), ('widower', 'Widower'), ('divorced', 'Divorced'), ('common-law relationship','Union Libre')], 'Marital Status'),
    }

    def update_user(self, cr, uid, ids, context=None):
        users_obj = self.pool.get('res.users')
        for employee in self.browse(cr, uid, ids, context):

            user = users_obj.search(cr, uid, [('partner_id', '=', employee.partner_id.id)])
            if user:
                employee.user_id = users_obj.browse(cr, uid, user)
            else:
                user_data = {
                    'partner_id': employee.partner_id.id,
                    'login': employee.partner_id.email,
                }
                new_user = users_obj.create(cr, uid, [user_data])
                employee.user_id = new_user
        return True
    
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if type(ids) == int:
            ids = [ids]
        if not len(ids):
            return []
        def _name_get(d):
            name = d.get('name','')
            code = d.get('identification_id',False)
            if code:
                name = '[%s] %s' % (code,name)
            return (d['id'], name)

        result = []
        for employee in self.browse(cr, user, ids, context=context):
            try:
                mydict = {
                          'id': employee.id,
                          'name': employee.name,
                          'identification_id': employee.identification_id,
                          }
            except:
                mydict = {'id': employee.id}
            result.append(_name_get(mydict))
        return result
    
    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            partner_obj = self.pool.get('res.partner')
            ids = partner_obj.search(cr, user, [('employee_id','!=',False),('ref','=',name)], limit=limit, context=context)
            if not ids:
                ids = set()
                ids.update(partner_obj.search(cr, user, [('employee_id','!=',False),('ref',operator,name)], limit=limit, context=context))
                if len(ids) < limit:
                    ids.update(partner_obj.search(cr, user, [('employee_id','!=',False),('name',operator,name)], limit=(limit-len(ids)), context=context))
                ids = list(ids)
            if not ids:
                ptrn = re.compile('(\[(.*?)\])')
                res = ptrn.search(name)
                if res:
                    ids = partner_obj.search(cr, user, [('ref','=', res.group(2))] + args, limit=limit, context=context)
            if ids:
                ids = self.search(cr, user, [('partner_id','in',ids)]+ args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result

    def onchange_partner(self, cr , uid, ids, partner_id, context=None):
        partner_obj = self.pool.get('res.partner')
        res = {}
        if partner_id:
            partner = partner_obj.browse(cr, uid, partner_id,context=context)
            res = {'value': {'name' : partner.name}}
        return res
    
    def get_contract(self, cr, uid, employee, date_start, context=None): # TODO
        contract_obj = self.pool.get('hr.contract')
        clause_final = [('employee_id', '=', employee.id), ('date_start', '<=', date_start), '|',
                        ('date_end', '=', False), ('date_end', '>=', date_start)]
        contract_id = contract_obj.search(cr, SUPERUSER_ID, clause_final, context=None)
        if not contract_id:
            raise osv.except_osv(_('Error Configuracion !'),_("El empleado '%s' no tiene un contrato para esa fecha!") % (employee.name,))
        return contract_id[0]
    
    def button_fetch(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'draft'}, context=context)
        return True
    
    def onchange_atrb(self, cr , uid, ids, nombre_uno, nombre_dos, apellido_uno, apellido_dos, context = None):
        return {'value': {'name' : (nombre_uno or '') +" "+ (nombre_dos or '') +" "+ (apellido_uno or '') +" "+ (apellido_dos or '') }}

class hr_contract_salary_change(osv.osv):
    _name = 'hr.contract.salary.change'
    _description = "Cambio de salario"
    _order = 'date desc'
    _rec_name = "date"

    _columns = {
        'contract_id':fields.many2one('hr.contract', 'Contrato', required=True),
        'wage': fields.float("Salario", digits_compute= dp.get_precision('Account'), required=True),
        'user_id':fields.many2one('res.users', 'Responsable', required=True, readonly=True),
        'date':fields.datetime('Fecha', required=True),
    }
    
    _defaults = {
        'date': lambda *args: time.strftime(DSTF),
        'user_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id,
    }
    
class hr_contract_calendar_change(osv.osv):
    _name = 'hr.contract.calendar.change'
    _description = "Cambio de horario"
    _order = 'date desc'
    _rec_name = "date"

    _columns = {
        'contract_id':fields.many2one('hr.contract', 'Contrato', required=True),
        'calendar_id':fields.many2one('resource.calendar', 'Horario Trabajo', required=True),
        'user_id':fields.many2one('res.users', 'Responsable', required=True, readonly=True),
        'date':fields.datetime('Fecha', required=True, readonly=True),
    }
    
    _defaults = {
        'date': lambda *args: time.strftime(DSTF),
        'user_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id,
    }


class hr_contract(osv.osv):
    _inherit = "hr.contract"
    
    def cron_periodo_prueba(self, cr, uid, mail, dias=False, context=None):
        if context is None:
            context = {}
        dias = dias or 15
        fecha = (datetime.now() + timedelta(dias)).strftime(DSDF)
        contract_ids = self.search(cr, uid, [('trial_date_end', '!=', False), ('trial_date_end', '=', fecha)], context=context, order='company_id asc')
        if contract_ids:
            contracts = self.browse(cr, uid, contract_ids, context=context)
            company_id = 0
            companias = []
            for contract in contracts:
                if company_id != contract.company_id.id:
                    companias.append(contract.company_id)
                    company_id = contract.company_id.id
            context["mail"] = mail
            context["contracts"] = contracts
            context["companias"] = companias
            context["fecha"] = fecha
            template_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'hr_payroll_extended', 'periodo_prueba_cron_email_template')[1]
            self.pool.get('email.template').send_mail(cr, uid, template_id, uid, force_send=True, context=context)
        return True
    
    def onchange_employee(self, cr, uid, ids, employee_id, context = None):
        res={}
        if employee_id:
            res = {'value' :{'company_id': False}}
            empleado = self.pool.get('hr.employee').browse(cr, uid, employee_id, context=context)
            if empleado and empleado.company_id:
                res = {'value' :{'company_id': empleado.company_id.id}}
        return res

    def get_all_structures(self, cr, uid, contract, tipo_nomina, context=None):
        """
        @param contract_ids: list of contracts
        @return: the structures linked to the given contracts, ordered by hierachy (parent=False first, then first level children and so on) and without duplicata
        """
        if not tipo_nomina:
            raise osv.except_osv(_("Error !"), _("Tiene que selecionar el tipo de nomina."))
            
        contract_type_obj = self.pool.get('hr.contract.type')
        estructura_salarial = contract_type_obj.get_structure_by_slip_type(cr, uid, contract.type_id.id, tipo_nomina.id, context)
        if not estructura_salarial:
            raise osv.except_osv(_('Error Configuracion !'),_("Contrato '%s' sin estructura laboral definida!") % (contract.name,))
        
        return list(set(self.pool.get('hr.payroll.structure')._get_parent_structure(cr, uid, [estructura_salarial.id], context=context)))

    def _comput_days(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for contract in self.browse(cr, uid, ids, context=context):
            days_work = 0
            days_year = 0
            if contract.date_start and contract.date_end:
                start_date = datetime.strptime(contract.date_start, DSDF)
                end_date = datetime.strptime(contract.date_end, DSDF)
                start_year_date = datetime(datetime.today().year, 1, 1)
                diff_days = end_date - start_date
                days_work = diff_days.days
                diff_days = end_date - start_year_date
                days_year = diff_days.days + 1
            res[contract.id] = {'days_of_work': days_work,
                                'days_of_year': days_year}
        return res
    
    def _last_salary_assigned(self, cr, uid, ids, context=None):
        result = {}
        for assign in self.pool.get('hr.contract.salary.change').browse(cr, uid, ids, context=context):
            if assign.contract_id:
                result[assign.contract_id.id] = assign.wage
        return result.keys()
        
    def _last_calendar_assigned(self, cr, uid, ids, context=None):
        result = {}
        for assign in self.pool.get('hr.contract.calendar.change').browse(cr, uid, ids, context=context):
            if assign.contract_id:
                result[assign.contract_id.id] = assign.calendar_id.id
        return result.keys()
    
    # def _check_date(self, cr, uid, ids, context=None):
        # for contract in self.browse(cr, uid, ids, context=context):
            # contract_ids = self.search(cr, uid, [('date_end', '=', False), ('date_end', '<=', contract.date_end), ('employee_id', '=', contract.employee_id.id), ('id', '<>', contract.id)])
            # contract_ids = self.search(cr, uid, ['|',('date_end', '=', False), ('date_end', '<=', contract.date_end), ('employee_id', '=', contract.employee_id.id), ('id', '<>', contract.id)])
            # if contract_ids:
                # return False
        # return True
        
    def _check_date(self, cr, uid, ids):
        for contract in self.browse(cr, uid, ids):
            if not contract.date_end:
                contract_ids = self.search(cr, uid, [('date_end', '=', False),('employee_id', '=', contract.employee_id.id),('id', '<>', contract.id)])
            else:
                contract_ids = self.search(cr, uid, [('date_start', '<=', contract.date_end), ('date_end', '>=', contract.date_start), ('employee_id', '=', contract.employee_id.id), ('id', '<>', contract.id)])
            if contract_ids:
                return False
        return True

    _columns = {
        'category_ids': fields.many2many('hr.employee.category', 'employee_category_rel', 'emp_id', 'category_id', 'Tags'),
        'fiscal_type_id': fields.many2one('hr.fiscal.type', "Tipo de Cotizante"),
        'wage_historic_ids':fields.one2many('hr.contract.salary.change','contract_id','Salario'),
        'calendar_historic_ids':fields.one2many('hr.contract.calendar.change','contract_id','Horario'),
        'wage': fields.related('wage_historic_ids', 'wage', string = 'Salario', type='float',
                    store ={
                    'hr.contract.salary.change': (_last_salary_assigned, ['date','wage'], 10),
                    }, readonly=True),
        'cuidad_desempeno': fields.many2one('res.city', 'Ciudad desempeno'),
        'cuidad_contract': fields.many2one('res.city', 'Ciudad Contrato'),
        'leave_ids': fields.one2many('hr.holidays', 'contract_id', 'Ausencias', readonly=True),
        'slip_ids': fields.one2many('hr.payslip', 'contract_id', 'Payslips History', readonly=True),
        'payslip_period_id': fields.many2one('payslip.period', "Periodo Liquidacion"),
        'separation_type': fields.selection(RETIROS, 'Tipo de Finalizacion'),
        'days_of_work': fields.function(_comput_days, string="Days of Works", type="integer", store=True, multi="days", help="Days of work, that will calculate days between end date and start date of contract."),
        'days_of_year': fields.function(_comput_days, string="Dias anual", type="integer", store=True, multi="days", help="Days of year that will calculate days from beginning of year to end date of contract."),
        'vacations_calendar_id': fields.many2one('resource.calendar', "Planificacion de Vacaciones", required=True),
        'working_hours': fields.many2one('resource.calendar', "Planificacion de Trabajo", required=True),
        'company_id': fields.many2one('res.company', 'Compania', required=True),
        'days_history': fields.integer('Dias historicos'),
        'skip_aux_trans': fields.boolean('Omitir auxilio de transporte'),
        'rtf_rate': fields.float('Porcentaje de retencion'),
        'schedule_pay': fields.selection([
                            ('weekly', 'Semanal'),
                            ('bi-monthly', 'Quincenal'),
                            ('monthly', 'Mensual'),
                            ('dualmonth', 'Cada 2 Meses'),
                            ('quarterly', 'Cada Cuatro meses'),
                            ('semi-annually', 'Cada 6 Meses'),
                            ('annually', 'Anual'),
                            ], 'Pago Planificado', select=True),
        'contract_days': fields.integer('Dias de contrato'),
    }
    _defaults = {
        'separation_type': '',
        'company_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.id,
    }
    _constraints = [
        (_check_date, 'No puede tener 2 contratos que se sobrelapen!', ['date_start','date_end']),
    ]

    def compute_allocation_leave(self, cr, uid, contract, rule_type, context=None):
        allocation_rule_obj = self.pool.get("hr.holidays.allocation.rule")
        rule_ids = allocation_rule_obj.search(cr, uid, [('allocation_type','=', rule_type)], context=context)
        start_date = datetime.strptime(contract.date_start, DSDF)
        end_date = datetime.strptime(contract.date_end, DSDF)
        diff_date = relativedelta.relativedelta(end_date, start_date)
        diff_months = diff_date.months
        if diff_date.years:
            diff_months += diff_date.years * 12
        no_of_leave = 0
        for rule in allocation_rule_obj.browse(cr, uid, rule_ids, context=context):
            if rule.total_month_to:
                if diff_months >= rule.total_month_from and diff_months < rule.total_month_to:
                    no_of_leave = rule.no_of_leave
                    break
            elif diff_months >= rule.total_month_from:
                no_of_leave = rule.no_of_leave
                break
        return no_of_leave
    
#copia del modulo para poder modificar el campo
class one2many_mod2(fields.one2many):

    def get(self, cr, obj, ids, name, user=None, offset=0, context=None, values=None):
        if context is None:
            context = {}
        if not values:
            values = {}
        res = {}
        for id in ids:
            res[id] = []
        ids2 = obj.pool[self._obj].search(cr, user, [(self._fields_id,'in',ids), ('appears_on_payslip', '=', True)], limit=self._limit)
        for r in obj.pool[self._obj].read(cr, user, ids2, [self._fields_id], context=context, load='_classic_write'):
            key = r[self._fields_id]
            if isinstance(key, tuple):
                # Read return a tuple in the case where the field is a many2one
                # but we want to get the id of this field.
                key = key[0]

            res[key].append( r['id'] )
        return res
        
class hr_payslip(osv.osv, EDIMixin):
    _name = 'hr.payslip'
    _description = "Payslip"
    _inherit = ['hr.payslip', 'mail.thread', 'ir.needaction_mixin']
    _rec_name = 'number'
    
    def get_payslip_lines(self, cr, uid, contract, payslip_id, context):
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = category.code in localdict['categories'].dict and localdict['categories'].dict[category.code] + amount or amount
            return localdict

        class BrowsableObject(object):
            def __init__(self, pool, cr, uid, employee_id, dict):
                self.pool = pool
                self.cr = cr
                self.uid = uid
                self.employee_id = employee_id
                self.dict = dict

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        class InputLine(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""
            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                result = 0.0
                self.cr.execute("SELECT sum(amount) as sum\
                            FROM hr_payslip as hp, hr_payslip_input as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                           (self.employee_id, from_date, to_date, code))
                res = self.cr.fetchone()[0]
                return res or 0.0

        class WorkedDays(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""
            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                result = 0.0
                self.cr.execute("SELECT sum(number_of_days) as number_of_days, sum(number_of_hours) as number_of_hours\
                            FROM hr_payslip as hp, hr_payslip_worked_days as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done'\
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                           (self.employee_id, from_date, to_date, code))
                return self.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[0] or 0.0

            def sum_hours(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[1] or 0.0

        class Payslips(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                self.cr.execute("SELECT sum(case when hp.credit_note = False then (pl.total) else (-pl.total) end)\
                            FROM hr_payslip as hp, hr_payslip_line as pl \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pl.slip_id AND pl.code = %s",
                            (self.employee_id, from_date, to_date, code))
                res = self.cr.fetchone()
                return res and res[0] or 0.0

        #we keep a dict with the result because a value can be overwritten by another rule with the same code
        result_dict = {}
        rules = {}
        categories_dict = {}
        blacklist = []
        payslip_obj = self.pool.get('hr.payslip')
        obj_rule = self.pool.get('hr.salary.rule')
        payslip = payslip_obj.browse(cr, uid, payslip_id, context=context)
        worked_days = {}
        for worked_days_line in payslip.worked_days_line_ids:
            wdl = self.pool.get('hr.payslip.worked_days').browse(cr, uid, [worked_days_line.id],context=context)[0]
            worked_days[wdl.code] = wdl
        inputs = {}
        for input_line in payslip.input_line_ids:
            inputs[input_line.code] = input_line

        categories_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, categories_dict)
        input_obj = InputLine(self.pool, cr, uid, payslip.employee_id.id, inputs)
        worked_days_obj = WorkedDays(self.pool, cr, uid, payslip.employee_id.id, worked_days)
        payslip_obj = Payslips(self.pool, cr, uid, payslip.employee_id.id, payslip)
        rules_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, rules)

        localdict = {'categories': categories_obj, 'rules': rules_obj, 'payslip': payslip_obj, 'worked_days': worked_days_obj, 'inputs': input_obj}
        structure_ids = self.pool.get('hr.contract').get_all_structures(cr, uid, contract, payslip.tipo_nomina,context=context)
        #get the rules of the structure and thier children
        rule_ids = self.pool.get('hr.payroll.structure').get_all_rules(cr, uid, structure_ids, context=context)
        #run the rules by sequence
        sorted_rule_ids = [id for id, sequence in sorted(list(set(rule_ids)), key=lambda x:x[1])]
        employee = contract.employee_id
        localdict.update({'employee': employee, 'contract': contract})
        print("EMPIEZA CON", len(sorted_rule_ids), "REGLAS EMPLOYEE", employee.id, "NOMINA", payslip.id)
        print(sorted_rule_ids)

        # -------------------------------------------------------------------------------------------- #
        # ------------------------------ Virtualizacion de novedades---------------------------------- #
        # -------------------------------------------------------------------------------------------- #

        print "Virtualizacion de reglas de novedades"

        p_ids = list([x.id for x in payslip.novedades_ids])
        p_ids.append(0)
        if len(p_ids) > 1:
            cr.execute("SELECT hpnc.code, sum(hpn.total), hpnc.srule_category_id, hpnc.name, sum(hpn.cantidad) "
                       "FROM hr_payroll_novedades hpn "
                       "INNER JOIN hr_payroll_novedades_category hpnc ON hpn.category_id = hpnc.id "
                       "WHERE hpn.id in {ids} "
                       "GROUP BY hpnc.id".format(ids=tuple(p_ids)))
            tot_nov = cr.fetchall()
            if tot_nov:
                for nov in tot_nov:
                    if nov[2] is None:
                        raise Warning("La categoria de la novedad {nov} no tiene definida "
                                      "una categoria de regla salarial".format(nov=nov[0]))
                    rule_category = self.pool.get('hr.salary.rule.category').browse(cr, uid, nov[2])
                    # Trataimiento como regla para generar lineas de nomina
                    key = str(nov[0]) + '-' + str(contract.id)
                    localdict['result'] = None
                    localdict['result_qty'] = 1.0
                    amount, qty, rate = nov[1], nov[4], 100
                    previous_amount = nov[0] in localdict and localdict[nov[0]] or 0.0
                    # set/overwrite the amount computed for this rule in the localdict
                    tot_rule = amount/qty * qty * rate / 100.0
                    localdict[nov[1]] = tot_rule
                    rules[nov[0]] = self.pool.get('hr.salary.rule')
                    # sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict, rule_category, tot_rule - previous_amount)
                    # create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        'salary_rule_id': payslip.company_id.dummy_salary_rule.id,
                        'contract_id': contract.id,
                        'name': nov[3],
                        'code': nov[0],
                        'category_id': nov[2],
                        'sequence': 1,
                        'appears_on_payslip': True,
                        'condition_select': 'none',
                        'condition_python': u'Result=True',
                        'condition_range': False,
                        'condition_range_min': False,
                        'condition_range_max': False,
                        'amount_select': 'method',
                        'amount_fix': 0.0,
                        'amount_python_compute': u'False',
                        'amount_percentage': False,
                        'amount_percentage_base': False,
                        'register_id': False,
                        'amount': amount/qty,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                        'payslip_run_id': payslip.payslip_run_id.id
                    }

        # -------------------------------------------------------------------------------------------- #
        # ----------------------- Virtualizacion de prestamos ---------------------------------------- #
        # -------------------------------------------------------------------------------------------- #

        print "Virtualizacion de reglas de prestamos"

        p_ids = list([x.id for x in payslip.prestamos_ids])
        p_ids.append(0)
        if len(p_ids) > 1:
            cr.execute("SELECT hpcc.code, sum(hpc.cuota), hpcc.srule_category_id, hpcc.name "
                       "FROM hr_payroll_prestamo_cuota hpc "
                       "INNER JOIN hr_payroll_prestamo_category hpcc ON hpc.category_id = hpcc.id "
                       "WHERE hpc.id in {ids} "
                       "GROUP BY hpcc.id".format(ids=tuple(p_ids)))

            tot_nov = cr.fetchall()
            if tot_nov:
                for nov in tot_nov:
                    if nov[2] is None:
                        raise Warning("La categoria del prestamo {con} no tiene definida "
                                      "una categoria de regla salarial".format(con=nov[0]))
                    rule_category = self.pool.get('hr.salary.rule.category').browse(cr, uid, nov[2])
                    # Trataimiento como regla para generar lineas de nomina
                    key = str(nov[0]) + '-' + str(contract.id)
                    localdict['result'] = None
                    localdict['result_qty'] = 1.0
                    amount, qty, rate = nov[1], 1, 100
                    previous_amount = nov[1] in localdict and localdict[nov[0]] or 0.0
                    # set/overwrite the amount computed for this rule in the localdict
                    tot_rule = amount/qty * qty * rate / 100.0
                    localdict[nov[1]] = tot_rule
                    rules[nov[0]] = self.pool.get('hr.salary.rule')
                    # sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict, rule_category, tot_rule - previous_amount)
                    # create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        'salary_rule_id': payslip.company_id.dummy_salary_rule.id,
                        'contract_id': contract.id,
                        'name': nov[3],
                        'code': nov[0],
                        'category_id': nov[2],
                        'sequence': 1,
                        'appears_on_payslip': True,
                        'condition_select': 'none',
                        'condition_python': u'Result=True',
                        'condition_range': False,
                        'condition_range_min': False,
                        'condition_range_max': False,
                        'amount_select': 'method',
                        'amount_fix': 0.0,
                        'amount_python_compute': u'False',
                        'amount_percentage': False,
                        'amount_percentage_base': False,
                        'register_id': False,
                        'amount': amount,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                        'payslip_run_id': payslip.payslip_run_id.id
                    }

        # -------------------------------------------------------------------------------------------- #
        # ----------------------- Virtualizacion de conceptos fijos ---------------------------------- #
        # -------------------------------------------------------------------------------------------- #

        print "Virtualizacion de reglas de conceptos fijos"

        p_ids = list([x.id for x in payslip.obligaciones_ids])
        p_ids.append(0)
        if len(p_ids) > 1:
            sqlc = ("SELECT otc.code, sum(otl.valor), otc.srule_category_id, otc.name, otc.worked_days_depends "
                    "FROM hr_payslip_obligacion_tributaria_line otl "
                    "INNER JOIN hr_payroll_obligacion_tributaria ot ON ot.id = otl.obligacion_id "
                    "INNER JOIN hr_payroll_obligacion_tributaria_category otc ON otc.id = ot.category_id "
                    "WHERE otl.id in {ids} "
                    "GROUP BY otc.id".format(ids=tuple(p_ids)))
            cr.execute(sqlc)

            tot_nov = cr.fetchall()
            if not tot_nov:

                # EJECUTAR CON CURSOR NUEVO CUANDO LOS DATOS NO SON VISIBLES CON EL MISMO CURSOR
                new_cr = sql_db.db_connect(cr.dbname).cursor()
                with api.Environment.manage():
                    new_cr.execute(sqlc)
                    tot_nov = new_cr.fetchall()
                    new_cr.close()

            if tot_nov:
                for nov in tot_nov:
                    if nov[2] is None:
                        raise Warning("La categoria del concepto fijo {con} no tiene definida "
                                      "una categoria de regla salarial".format(con=nov[0]))
                    rule_category = self.pool.get('hr.salary.rule.category').browse(cr, uid, nov[2])
                    # Trataimiento como regla para generar lineas de nomina
                    key = str(nov[0]) + '-' + str(contract.id)
                    localdict['result'] = None
                    localdict['result_qty'] = 1.0
                    amount, qty, rate = nov[1], 1, 100
                    worked_depends = nov[4]
                    previous_amount = nov[0] in localdict and localdict[nov[0]] or 0.0
                    # set/overwrite the amount computed for this rule in the localdict
                    if worked_depends:
                        amount = amount * worked_days['WORK102'].number_of_days / worked_days['WORK101'].number_of_days
                        if amount == 0:
                            continue
                    tot_rule = amount/qty * qty * rate / 100.0
                    localdict[nov[1]] = tot_rule
                    rules[nov[0]] = self.pool.get('hr.salary.rule')
                    # sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict, rule_category, tot_rule - previous_amount)
                    # create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        'salary_rule_id': payslip.company_id.dummy_salary_rule.id,
                        'contract_id': contract.id,
                        'name': nov[3],
                        'code': nov[0],
                        'category_id': nov[2],
                        'sequence': 1,
                        'appears_on_payslip': True,
                        'condition_select': 'none',
                        'condition_python': u'Result=True',
                        'condition_range': False,
                        'condition_range_min': False,
                        'condition_range_max': False,
                        'amount_select': 'method',
                        'amount_fix': 0.0,
                        'amount_python_compute': u'False',
                        'amount_percentage': False,
                        'amount_percentage_base': False,
                        'register_id': False,
                        'amount': amount,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                        'payslip_run_id': payslip.payslip_run_id.id
                    }

        for rule in obj_rule.browse(cr, uid, sorted_rule_ids, context=context):
            dt1 = datetime.now()
            key = rule.code + '-' + str(contract.id)
            localdict['result'] = None
            localdict['result_qty'] = 1.0
            #check if the rule can be applied
            if obj_rule.satisfy_condition(cr, uid, rule.id, localdict, context=context) and rule.id not in blacklist:
                #compute the amount of the rule
                amount, qty, rate = obj_rule.compute_rule(cr, uid, rule.id, localdict, context=context)  # TODO
                dt2 = datetime.now()
                stsfy = True
                if amount == 'na':
                    # Validacion dentro de la misma regla enviandola como siempre verdadero
                    stsfy = False
                    continue
                #check if there is already a rule computed with that code
                previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                #set/overwrite the amount computed for this rule in the localdict
                tot_rule = amount * qty * rate / 100.0
                localdict[rule.code] = tot_rule
                rules[rule.code] = rule
                #sum the amount for its salary category
                localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
                #create/overwrite the rule in the temporary results
                result_dict[key] = {
                    'salary_rule_id': rule.id,
                    'contract_id': contract.id,
                    'name': rule.name,
                    'code': rule.code,
                    'category_id': rule.category_id.id,
                    'sequence': rule.sequence,
                    'appears_on_payslip': rule.appears_on_payslip,
                    'condition_select': rule.condition_select,
                    'condition_python': rule.condition_python,
                    'condition_range': rule.condition_range,
                    'condition_range_min': rule.condition_range_min,
                    'condition_range_max': rule.condition_range_max,
                    'amount_select': rule.amount_select,
                    'amount_fix': rule.amount_fix,
                    'amount_python_compute': rule.amount_python_compute,
                    'amount_percentage': rule.amount_percentage,
                    'amount_percentage_base': rule.amount_percentage_base,
                    'register_id': rule.register_id.id,
                    'amount': amount,
                    'employee_id': contract.employee_id.id,
                    'quantity': qty,
                    'rate': rate,
                    'payslip_run_id': payslip.payslip_run_id.id
                }
            else:
                #blacklist this rule and its children
                blacklist += [id for id, seq in self.pool.get('hr.salary.rule')._recursive_search_of_rules(cr, uid, [rule], context=context)]
                dt2 = datetime.now()
                stsfy = False
            print rule.id, '|', rule.code, '|', (dt2 - dt1).total_seconds(), '|', stsfy
        result = [value for code, value in result_dict.items()]
        return result
    
    def action_quotation_send(self, cr, uid, ids, context=None):
        if context is None: context = {}
        assert len(ids) == 1, 'This option should only be used for a single id at a time.'
        ir_model_data = self.pool.get('ir.model.data')
        try:
            template_id = ir_model_data.get_object_reference(cr, uid, 'hr_payroll_extended', 'email_template_edi_payslip')[1]
        except ValueError:
            template_id = False
        
        #try:
        #    compose_form_id = ir_model_data.get_object_reference(cr, uid, 'mail', 'email_compose_message_wizard_form')[1]
        #except ValueError:
        #    compose_form_id = False 

        ctx = dict(context)
        ctx.update({
            'default_model': 'hr.payslip',
            'default_res_id': ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'lang': 'es_CO',
            'tz': 'America/Bogota',
            'uid': uid
        })
        object = self.browse(cr, uid, ids, context=ctx)[0]
        values = self.pool.get('mail.compose.message').generate_email_for_composer(cr, uid, template_id, ids[0], context=ctx)
        compose_id = self.pool.get('mail.compose.message').create(cr, uid, values, context=ctx)
        #agregado por wmoreno
        self.pool.get('mail.compose.message').write(cr, uid, compose_id, {'notified_partner_ids':None,'partner_ids': [(6, 0, [x.id for x in [object.employee_id.partner_id]])]}, context=context)
        self.pool.get('mail.compose.message').send_mail(cr, uid, [compose_id], context=ctx)   
        return True
        
    def action_notification_mass_send(self, cr, uid, ids, context=None):
        '''
        This function opens a window to compose an email, with the edi payslip template message loaded by default
        '''
        assert len(ids) == 1, 'This option should only be used for a single id at a time.'
        ir_model_data = self.pool.get('ir.model.data')
        compose_data = self.pool.get('mail.compose.message')
        try:
            template_id = ir_model_data.get_object_reference(cr, uid, 'hr_payroll_extended', 'email_template_edi_payslip')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference(cr, uid, 'mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False 
        res_id = ids[0]
        ctx = {
            'default_model': 'hr.payslip',
            'default_res_id': res_id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'search_default_model_id'
            'mark_so_as_sent': True,
            'lang': 'es_CO',
            'tz': 'America/Bogota',
            'uid': uid,
        }
        
        object = self.browse(cr, uid, ids, context=ctx)[0]
        
        #sacado del onchange_template_id del mail_template mail_compose_message.py
        if template_id:
            # FIXME odo: change the mail generation to avoid attachment duplication
            values = compose_data.generate_email_for_composer(cr, uid, template_id, res_id, context=ctx)
            # transform attachments into attachment_ids
            values['attachment_ids'] = []
            ir_attach_obj = self.pool.get('ir.attachment')
            for attach_fname, attach_datas in values.pop('attachments', []):
                data_attach = {
                    'name': attach_fname,
                    'datas': attach_datas,
                    'datas_fname': attach_fname,
                    'res_model': 'hr.payslip',
                    'res_id': res_id,
                    'type': 'binary',  # override default_type from context, possibly meant for another model!
                }
                attachments = ir_attach_obj.create(cr, uid, data_attach, context=ctx)
                values['attachment_ids'].append(attachments)
        compose_id = compose_data.create(cr, uid, values, context=ctx)
        compose_data.write(cr, uid, compose_id, {'partner_ids': [(6, 0, [x.id for x in [object.employee_id.partner_id]])]}, context=ctx)
        compose_data.write(cr, uid, compose_id, {'attachment_ids': [(6, 0, [x for x in [attachments]])]}, context=ctx)
        compose_data.send_mail(cr, uid, [compose_id], context=ctx)
        
        return True
    
    def _compute_extra_hours(self, cr, uid, ids, name, args, context=None):
        res = {}
        extrahours_obj = self.pool.get('hr.payroll.extrahours')
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.tipo_nomina.code in ('Nomina', 'Liquidacion', 'Otros'):
                res[payslip.id] = extrahours_obj.search(cr, uid, ['|', ('state', '=', 'validated'), ('payslip_id', '=', payslip.id), ('approve_date', '>=', payslip.payslip_period_id.start_date), ('approve_date', '<=', payslip.payslip_period_id.end_date), ('employee_id', '=', payslip.employee_id.id)], order='date_end asc')
            else:
                res[payslip.id] = []
        return res
        
    def _compute_novedades(self, cr, uid, ids, name, args, context=None):
        res = {}
        novedades_obj = self.pool.get('hr.payroll.novedades')
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.tipo_nomina.code in ('Nomina', 'Otros', 'Cesantias Parciales', 'Vacaciones'):
                res[payslip.id] = novedades_obj.search(cr, uid,
                                                       ['|', ('state', '=', 'validated'),
                                                        ('payslip_id', '=', payslip.id),
                                                        ('approve_date', '>=', payslip.payslip_period_id.start_date),
                                                        ('approve_date', '<=', payslip.payslip_period_id.end_date),
                                                        ('employee_id', '=', payslip.employee_id.id)], order='date asc')
            elif payslip.tipo_nomina.code == 'Liquidacion':
                res[payslip.id] = novedades_obj.search(cr, uid,
                                                       ['|', ('state', '=', 'validated'),
                                                        ('payslip_id', '=', payslip.id),
                                                        ('approve_date', '>=', payslip.payslip_period_id.start_period),
                                                        ('approve_date', '<=', payslip.payslip_period_id.end_period),
                                                        ('employee_id', '=', payslip.employee_id.id)], order='date asc')
            else:
                res[payslip.id] = []
        return res
        
    def _compute_prestamos(self, cr, uid, ids, name, args, context=None):
        res = {}
        prestamos_obj = self.pool.get('hr.payroll.prestamo.cuota')
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.tipo_nomina.code in ('Nomina', 'Vacaciones'):
                res[payslip.id] = prestamos_obj.search(cr, uid, ['|',('payslip_id', '=', False),('payslip_id', '=', payslip.id), ('date', '>=', payslip.payslip_period_id.start_date), ('date', '<=', payslip.payslip_period_id.end_date), ('contract_id', '=', payslip.contract_id.id), ('state', '=', 'validated')], order='date asc')
            else:
                res[payslip.id] = []
        return res
        
    def _compute_advances(self, cr, uid, ids, name, args, context=None):
        res = {}
        advance_obj = self.pool.get('hr.payroll.advance')
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.tipo_nomina.code == 'Nomina':
                advances = []

                cr.execute("SELECT id FROM hr_payroll_advance WHERE "
                           "(payslip_id is Null AND state = 'to_discount' AND contract_id = {contract}) OR "
                           "(payslip_id = {payslip} AND state = 'paid' AND contract_id = {contract}) "
                           "order by expire_date".format(contract=payslip.contract_id.id, payslip=payslip.id))
                advances += [x[0] for x in cr.fetchall()]

                # advances += advance_obj.search(cr, uid, [
                #     '|', (('payslip_id', '=', False),
                #           ('state', '=', 'to_discount'), ('contract_id', '=', payslip.contract_id.id)),
                #     (('payslip_id', '=', payslip.id),
                #      ('state', '=', 'paid'), ('contract_id', '=', payslip.contract_id.id))
                # ], order='expire_date asc')

                for x in payslip.advance_total_ids:
                    if x.advance_id.id not in advances:
                        advances += [x.advance_id.id]

                res[payslip.id] = advances
            else:
                res[payslip.id] = []
        return res
    
    def _compute_leaves(self, cr, uid, ids, name, args, context=None):
        res = {}
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.tipo_nomina.code in ('Nomina', 'Vacaciones', 'Vacaciones Dinero', 'Liquidacion'):
                ls = []
                for days in payslip.leave_days_ids:
                    if days.holiday_id.id not in ls:
                        ls.append(days.holiday_id.id)
                sql = ("select hh.id, hh.state, hh.name, hhs.vacaciones from hr_holidays hh "
                       "inner join hr_holidays_status hhs on hhs.id = hh.holiday_status_id "
                       "where approve_date >= '{ppsd}' "
                       "and approve_date <= '{pped}' and contract_id = {contract} "
                       "and state = 'validate' "
                       "and hh.payed_vac > 0 "
                       "and hhs.vacaciones = true".format(contract=payslip.contract_id.id,
                                                          ppsd=payslip.payslip_period_id.start_date,
                                                          pped=payslip.payslip_period_id.end_date))
                payed_vac = orm.fetchall(cr, sql)
                if payed_vac:
                    for aus in payed_vac:
                        ls.append(aus[0])

                sql = ("SELECT hh.id FROM hr_holidays_days hhd "
                       "INNER JOIN hr_holidays hh ON hh.id = hhd.holiday_id "
                       "INNER JOIN hr_holidays_status hhs ON hhs.id = hhd.holiday_status_id "
                       "WHERE ("
                       "    hhd.apply_cut = 't' "
                       "    AND hh.approve_date >= '{ppsd} 05:00:00' "
                       "    AND hh.approve_date <= '{pped} 05:00:00' "
                       "    AND hhs.holiday_valid_date = 't') "
                       "OR ("
                       "    hhd.apply_cut = 'f' "
                       "    AND hh.approve_date >= '{ppsp} 05:00:00' "
                       "    AND hh.approve_date <= '{ppep} 05:00:00' "
                       "    AND hhs.holiday_valid_date = 't') "
                       "AND hhd.contract_id = {contract} "
                       "AND hhd.state in ('paid', 'validate') "
                       "GROUP BY hh.id".format(
                            contract=payslip.contract_id.id,
                            ppsd=payslip.payslip_period_id.start_date,
                            pped=payslip.payslip_period_id.end_date,
                            ppsp=payslip.payslip_period_id.start_period,
                            ppep=payslip.payslip_period_id.end_period))

                iids = list(x[0] for x in orm.fetchall(cr, sql))
                res[payslip.id] = ls + iids
            else:
                res[payslip.id] = []
        return res
    
    def _compute_leave_days(self, cr, uid, ids, name, args, context=None):
        res = {}
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.tipo_nomina.code in ('Nomina', 'Vacaciones', 'Vacaciones Dinero', 'Liquidacion'):
                # Por fecha de inicio
                iquery = ("SELECT hhd.id FROM hr_holidays_days hhd "
                          "INNER JOIN hr_holidays_status hhs ON hhs.id = hhd.holiday_status_id "
                          "WHERE ("
                          "    hhd.apply_cut = 't' "
                          "    AND hhd.name >= '{ppsd}' "
                          "    AND hhd.name <= '{pped}') "
                          "OR ("
                          "    hhd.apply_cut = 'f' "
                          "    AND hhd.name >= '{ppsp}' "
                          "    AND hhd.name <= '{ppep}') "
                          "AND hhd.contract_id = {contract} "
                          "AND hhd.state in ('paid', 'validate')".format(
                            contract=payslip.contract_id.id,
                            ppsd=payslip.payslip_period_id.start_date,
                            pped=payslip.payslip_period_id.end_date,
                            ppsp=payslip.payslip_period_id.start_period,
                            ppep=payslip.payslip_period_id.end_period))
                iids = list(x[0] for x in orm.fetchall(cr, iquery))

                res[payslip.id] = iids
            else:
                res[payslip.id] = []

        return res
    
    def _get_structure(self, cr, uid, ids, name, args, context=None):
        res = {}
        contract_type_obj = self.pool.get('hr.contract.type')
        for payslip in self.browse(cr, uid, ids, context=context):
            res[payslip.id] = False
        return res
    
    _columns = {
        'obligaciones_ids':fields.one2many('hr.payslip.obligacion.tributaria.line', 'payslip_id', 'Obligaciones Tributarias', readonly=True, ondelete='cascade'), 
        'extrahours_total_ids':fields.one2many('hr.payslip.extrahours', 'payslip_id', 'Horas Extra Totales', readonly=True, ondelete='cascade'), 
        'novedades_total_ids':fields.one2many('hr.payslip.novedades', 'payslip_id', 'Novedades Totales',readonly=True, ondelete='cascade'),
        'prestamos_total_ids':fields.one2many('hr.payslip.prestamo.cuota', 'payslip_id', 'Prestamos Totales',readonly=True, ondelete='cascade'),
        'advance_total_ids':fields.one2many('hr.payslip.advance', 'payslip_id', 'Pagos Anticipos', readonly=True, ondelete='cascade', states={'draft': [('readonly', False)]}),
        
        'leave_days_ids': fields.function(_compute_leave_days, relation='hr.holidays.days', type="one2many", string='Detalle de Dias',readonly=True),
        'extrahours_ids': fields.function(_compute_extra_hours, relation='hr.payroll.extrahours', type="one2many", string='Horas Extra Detallada',readonly=True),
        'novedades_ids': fields.function(_compute_novedades, relation='hr.payroll.novedades', type="one2many", string='Novedades Detalladas',readonly=True),
        'prestamos_ids': fields.function(_compute_prestamos, relation='hr.payroll.prestamo.cuota', type="one2many", string='Prestamos Detallados',readonly=True),
        'advance_ids': fields.function(_compute_advances, relation='hr.payroll.advance', type="one2many", string='Anticipos Detallados',readonly=True), 
        'structure_id': fields.function(_get_structure, relation='hr.payroll.structure', type="many2one", string='Estructura Salarial',readonly=True,store=True), 
        
        'leave_ids': fields.function(_compute_leaves, relation='hr.holidays', type="one2many", string='Ausencias'),
        
        'tipo_nomina': fields.many2one('hr.payslip.type', "Tipo", required=True),
        'payslip_period_id': fields.many2one('payslip.period', "Period", states={'draft': [('readonly', False)]}),
        'account_move_id': fields.many2one('account.move', "comprobante"),
        
        'move_name': fields.char('Nombre Comprobante', size=64, readonly=True),
        'id': fields.integer('id', readonly=True),
        'liquid_date':fields.date('Fecha Contabilizacion', states={'draft': [('readonly', False)]}),
        'liquidacion_date':fields.date('Fecha Liquidacion', states={'draft': [('readonly', False)]}),
        'contract_create': fields.boolean('Created from contract'),
        'line_ids': one2many_mod2('hr.payslip.line', 'slip_id', 'Payslip Lines', readonly=True),
        'worked_days_line_ids': fields.one2many('hr.payslip.worked_days', 'payslip_id', 'Payslip Worked Days',
                                                readonly=True)
        }
    
    _defaults = {
        'contract_create': False,
        'liquid_date': datetime.now().strftime(DSDF),
    }

    def cancel_prestamos(self, cr, uid, prestamos_ids, context=None):
        obj_prestamo = self.pool.get('hr.payroll.prestamo.cuota')
        for prestamo in prestamos_ids:
            obj_prestamo.write(cr, SUPERUSER_ID, [prestamo.id], {'payslip_id': False}, context=context)
        return True
        
    def cancel_sheet(self, cr, uid, ids, context=None):
        orm2sql = self.pool.get('avancys.orm2sql')
        obj_novedades = self.pool.get('hr.payroll.novedades')
        move_pool = self.pool.get('account.move')
        wf_service = openerp.netsvc.LocalService("workflow")
        for payslip in self.browse(cr, uid, ids, context=context):
            novedades = obj_novedades.search(cr, uid, [('payslip_neto_id', '=', payslip.id), ('neto', '=', True)], context=context)
            if novedades:
                for novedad in obj_novedades.browse(cr, uid, novedades, context=context):
                    # wf_service.trg_validate(uid, 'hr.payroll.novedades', novedad.id, 'cancel_done', cr)
                    # wf_service.trg_validate(uid, 'hr.payroll.novedades', novedad.id, 'cancel', cr)
                    orm2sql.sqlupdate(cr, 'hr_payroll_novedades', {'state': 'cancelled'}, ('id', novedad.id))
                    cr.execute("DELETE FROM hr_payroll_novedades WHERE id = {id}".format(id=novedad.id))
                    # obj_novedades.unlink(cr, uid, [novedad.id], context=context)
                    
            for novedad in payslip.novedades_ids:
                cr.execute("UPDATE hr_payroll_novedades SET payslip_id=Null, state='validated' WHERE id={id}".format(id=novedad.id))
                # obj_novedades.write(cr, uid, [novedad.id], {'payslip_id': False}, context=context)
                # wf_service.trg_validate(uid, 'hr.payroll.novedades', novedad.id, 'cancel_done', cr)
                
            for extra in payslip.extrahours_ids:
                cr.execute("UPDATE hr_payroll_extrahours SET payslip_id=Null, state='validated' WHERE id={id}".format(
                    id=extra.id))
                # self.pool.get('hr.payroll.extrahours').write(cr, uid, [extra.id], {'payslip_id': '', 'state': 'validated'},context=context)
                # wf_service.trg_validate(uid, 'hr.payroll.extrahours', extra.id, 'paid', cr)
            for leave in payslip.leave_days_ids:
                cr.execute("UPDATE hr_holidays SET payslip_id=Null, state='validated' WHERE id={id}".format(
                    id=leave.id))
                # self.pool.get('hr.holidays').write(cr, uid, [leave.holiday_id.id], {'payslip_id': '', 'state': 'validate'},context=context)

            if payslip.move_id:
                move_pool.button_cancel(cr, uid, [payslip.move_id.id], context=context)
                cr.execute("DELETE FROM account_move WHERE id = {id}".format(id=payslip.move_id.id))
                # move_pool.unlink(cr, uid, [payslip.move_id.id], context=context)
                cr.execute('UPDATE hr_payslip set move_id = Null where id = {id}'.format(id=payslip.id))
                # self.write(cr, uid, [payslip.id], {'move_id':False}, context=context)

        return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
    
    def draft_sheet(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)
    
    def hr_verify_sheet(self, cr, uid, ids, context=None):
        if not context:
            context = {'tz': self.pool.get('res.users').browse(cr, uid, uid, context=context).tz  }
        return self.write(cr, uid, ids, {'state': 'verify'}, context=context)
    
    def compute_sheet(self, cr, uid, ids, context=None):
        sequence_obj = self.pool.get('ir.sequence')
        orm2sql = self.pool.get('avancys.orm2sql')
        for payslip in self.browse(cr, uid, ids, context=context):
            number = payslip.number or sequence_obj.get(cr, uid, 'salary.slip')
            #delete old payslip lines
            cr.execute('''
                DELETE FROM hr_payslip_line
                WHERE slip_id = %s
                ''' % payslip.id)
            if payslip.contract_id:
                #set the list of contract for which the rules have to be applied
                contract = payslip.contract_id
            else:
                raise osv.except_osv(_('Error Configuracion !'),_("El empleado '%s' no tiene un contrato asignado en la nomina!") % (payslip.employee_id.name,))
            lines = [(0,0,line) for line in self.pool.get('hr.payslip').get_payslip_lines(cr, uid, contract, payslip.id, context=context)]
            #self.write(cr, uid, [payslip.id], {'line_ids': lines, 'number': number,}, context=context)
            for line in lines:
                line[2]['slip_id'] = payslip.id
                line[2]['active'] = True
                line[2]['payslip_period_id'] = payslip.payslip_period_id.id
                line[2]['total'] = float(line[2]['quantity']) * line[2]['amount'] * line[2]['rate'] / 100
                orm2sql.sqlcreate(uid, cr, 'hr_payslip_line', [line[2]], company=True)
            name = 'Nomina de ' + str(payslip.contract_id.name.encode('utf-8'))
            orm2sql.sqlupdate(cr, 'hr_payslip', {'number': number, 'name': name}, ('id', payslip.id))
        return True
    
    def compute_prestamos_total(self, cr, uid, ids, context=None):
        res = {}
        if context is None:
            context = {}
        prestamos_obj = self.pool.get('hr.payslip.prestamo.cuota')
        for payslip in self.browse(cr, uid, ids, context=context):
            for pres in payslip.prestamos_total_ids:
                cr.execute("DELETE FROM hr_payslip_prestamo_cuota WHERE id = {id}".format(id=pres.id))
            # prestamos_obj.unlink(cr, uid, [pres.id for pres in payslip.prestamos_total_ids], context=context)
            prestamos = {}
            for prestamo in payslip.prestamos_ids:
                if prestamo.category_id.name in prestamos:
                    prestamos[prestamo.category_id.name]['deuda'] += prestamo.deuda
                    prestamos[prestamo.category_id.name]['cuota'] += prestamo.cuota
                else:
                    prestamos[prestamo.category_id.name] = {
                        'category_id': prestamo.category_id.id,
                        'deuda': prestamo.deuda,
                        'cuota': prestamo.cuota,
                        'payslip_id': payslip.id,
                    }
            valores = [value for key,value in prestamos.items()]
            for val in valores:
                prestamos_obj.create(cr, uid, val, context=context)
        return True
    
    def compute_advance_total_rule(self, cr, uid, payslip, amount, account_id=False, context=None):
        res = {}
        if context is None:
            context = {}
        advance_obj = self.pool.get('hr.payslip.advance')
        
        remove =[]
        manual = []
        manual_obj = {}
        total = 0
        
        #es inecesaria la validacion del estado?
        if payslip.state == 'draft':
            if payslip.advance_total_ids:
                for advancetotal in payslip.advance_total_ids:
                    if advancetotal.manual:
                        manual.append(advancetotal.advance_id.id)
                        manual_obj[advancetotal.advance_id.id] = advancetotal
                    remove.append(advancetotal.id)
                for rid in remove:
                    cr.execute("DELETE FROM hr_payslip_advance WHERE id = {id}".format(id=rid))
                # advance_obj.unlink(cr, uid, remove, context=context)
            if payslip.advance_ids:
                for advance in payslip.advance_ids:
                    vals = {
                        'advance_id': advance.id,
                        'amount_total': advance.remaining,
                        'payslip_id': payslip.id,
                        'account_id': account_id,#TODO
                    }
                    if advance.id not in manual:
                        if advance.remaining <= amount:
                            to_discount = advance.remaining
                        else:
                            to_discount = amount
                        vals['amount_discount'] = to_discount
                    else:
                        vals['amount_discount'] = manual_obj[advance.id].amount_discount
                        vals['manual'] = True

                    if vals['amount_discount'] < 0:
                        vals['amount_discount'] = 0
                    elif vals['amount_discount'] > vals['amount_total']:
                        vals['amount_discount'] = vals['amount_total']
                    elif vals['amount_discount'] > amount:
                        vals['amount_discount'] = amount
                    
                    amount -= vals['amount_discount']
                    total += vals['amount_discount']
                    
                    
                    advance_obj.create(cr, uid, vals, context=context)
                    
        return total
    
    def compute_novedades_total(self, cr, uid, ids, context=None):
        res = {}
        if context is None:
            context = {}
        novedades_obj = self.pool.get('hr.payslip.novedades')
        for payslip in self.browse(cr, uid, ids, context=context):
            for nov in payslip.novedades_total_ids:
                cr.execute("DELETE FROM hr_payslip_novedades WHERE id = {id}".format(id=nov.id))
            # novedades_obj.unlink(cr, uid, [nov.id for nov in payslip.novedades_total_ids], context=context)
            novedades = {}
            for novedad in payslip.novedades_ids:
                if novedad.category_id.name in novedades:
                    novedades[novedad.category_id.name]['cantidad'] += novedad.cantidad
                    novedades[novedad.category_id.name]['total'] += novedad.total
                else:
                    novedades[novedad.category_id.name] = {
                        'category_id': novedad.category_id.id,
                        'cantidad': novedad.cantidad,
                        'total': novedad.total,
                        'payslip_id': payslip.id,
                    }
            valores = [value for key,value in novedades.items()]
            for val in valores:
                novedades_obj.create(cr, uid, val, context=context)
        return True
    
    def compute_extrahours_total(self, cr, uid, ids, context=None):
        res = {}
        if context is None:
            context = {}
        extrahours_obj = self.pool.get('hr.payslip.extrahours')
        for payslip in self.browse(cr, uid, ids, context=context):
            for ex in payslip.extrahours_total_ids:
                cr.execute("DELETE FROM hr_payslip_extrahours WHERE id = {id}".format(id=ex.id))
            # extrahours_obj.unlink(cr, uid,[ex.id for ex in payslip.extrahours_total_ids], context=context)
            extras = {}
            for extra in payslip.extrahours_ids:
                if extra.type_id.name in extras:
                    extras[extra.type_id.name]['cantidad'] += extra.duracion
                    extras[extra.type_id.name]['total'] += extra.total
                    extras[extra.type_id.name]['valor'] = extras[extra.type_id.name]['total']/extras[extra.type_id.name]['cantidad']
                else:
                    extras[extra.type_id.name] = {
                        'type_id': extra.type_id.id,
                        'valor': extra.total/extra.duracion,
                        'cantidad': extra.duracion,
                        'total': extra.total,
                        'payslip_id': payslip.id,
                    }
            valores = [value for key,value in extras.items()]
            for val in valores:
                extrahours_obj.create(cr, uid, val, context=context)
        return True
        
    def compute_obligaciones(self, cr, uid, ids, context=None):
        res = {}
        if context is None:
            context = {}
        obligaciones_obj = self.pool.get('hr.payroll.obligacion.tributaria')
        obligacio_line_obj = self.pool.get('hr.payslip.obligacion.tributaria.line')
        for payslip in self.browse(cr, uid, ids, context=context):
            obligaciones_line = []
            for line in payslip.obligaciones_ids:
                if not line.manual:
                    obligaciones_line.append(line.id)
            for oline in obligaciones_line:
                cr.execute("DELETE FROM hr_payslip_obligacion_tributaria_line WHERE id = {id}".format(id=oline))
            # obligacio_line_obj.unlink(cr, uid, obligaciones_line, context=context)
            las_obligaciones = {}
            obli_aplican = obligaciones_obj.search(cr, uid, [('state', '=', 'validated'), ('contract_id', '=', payslip.contract_id.id), ('date_from', '<=', payslip.payslip_period_id.start_date), ('date_to', '>=', payslip.payslip_period_id.end_date)], order='category_id desc')
            for obliga in obligaciones_obj.browse(cr, uid, obli_aplican, context):
                
                valores = {
                    'obligacion_id': obliga.id,
                    'valor': obliga.valor,
                    'payslip_id': payslip.id,
                    'manual': False,
                }
                obligacio_line_obj.create(cr, uid, valores, context=context)
        return True
    
    def get_partner_process_sheet(self, cr, uid, line, slip, context=None):
        partner_id = slip.employee_id.partner_id.id
        return partner_id
    
    def create_move_line_rules(self, cr, uid, slip, move_id, line, accounts, context=None):
        res = {'debit_sum':0,'credit_sum':0,}
        orm2sql = self.pool.get('avancys.orm2sql')
        debit_account_id = accounts.account_debit_structure_property and accounts.account_debit_structure_property.id
        credit_account_id = accounts.account_credit_structure_property and accounts.account_credit_structure_property.id
        partner_id = self.get_partner_process_sheet(cr, uid, line, slip, context=context)
        period_pool = self.pool.get('account.period')
        amt = round(slip.credit_note and -line.total or line.total,slip.company_id and slip.company_id.currency_id and slip.company_id.currency_id.accuracy or 2)
        timenow = slip.liquid_date
        period_id = period_pool.find(cr, uid, timenow, context=context)[0]
        centro_costo = accounts.analytic_account_id_structure_property and accounts.analytic_account_id_structure_property.id or False
        if not centro_costo and slip.contract_id.analytic_account_id:
            centro_costo = slip.contract_id.analytic_account_id.id

        currency_id = context.get('ref_currency_id',False)
        ref_currency_rate = context.get('ref_currency_rate', 1)

        if debit_account_id:
            amount_currency = (amt / ref_currency_rate) if ref_currency_rate > 1 else 0
            debit_line = {
                'name': line.name,
                'date': timenow,
                'partner_id': partner_id,
                'account_id': debit_account_id,
                'journal_id': slip.journal_id.id,
                'period_id': period_id,
                'debit': amt > 0.0 and amt or 0.0,
                'credit': amt < 0.0 and -amt or 0.0,
                'analytic_account_id': centro_costo,
                'tax_code_id': line.salary_rule_id.account_tax_id and line.salary_rule_id.account_tax_id.id or False,
                'tax_amount': line.salary_rule_id.account_tax_id and amt or 0.0,
                'move_id': move_id,
                'amount_currency': amount_currency,
                'currency_id': currency_id,
                'state': 'draft'
            }
            orm2sql.sqlcreate(uid, cr, 'account_move_line', [debit_line], company=True)
            # move_line_obj.create(cr, uid, debit_line, context=context)
            res['debit_sum'] += debit_line['debit'] - debit_line['credit']
            
        if credit_account_id:
            amount_currency = (-amt / ref_currency_rate) if ref_currency_rate > 1 else 0
            credit_line = {
                'name': line.name,
                'date': timenow,
                'partner_id': partner_id,
                'account_id': credit_account_id,
                'journal_id': slip.journal_id.id,
                'period_id': period_id,
                'debit': amt < 0.0 and -amt or 0.0,
                'credit': amt > 0.0 and amt or 0.0,
                'analytic_account_id':centro_costo,
                'tax_code_id': line.salary_rule_id.account_tax_id and line.salary_rule_id.account_tax_id.id or False,
                'tax_amount': line.salary_rule_id.account_tax_id and amt or 0.0,
                'move_id': move_id,
                'amount_currency': amount_currency,
                'currency_id': currency_id,
                'state': 'draft',
            }
            orm2sql.sqlcreate(uid, cr, 'account_move_line', [credit_line], company=True)
            # move_line_obj.create(cr, uid, credit_line, context=context)
            res['credit_sum'] += credit_line['credit'] - credit_line['debit']
            
        return res
    
    def create_move_line_extra_hours(self, cr, uid, slip, move_id, context=None):
        res = {'debit_sum':0,'credit_sum':0,}
        concept_structure_obj = self.pool.get('hr.concept.structure.account')
        move_line_obj = self.pool.get('account.move.line')
        period_pool = self.pool.get('account.period')
        structure_obj = self.pool.get('hr.payroll.structure')
        for extra in slip.extrahours_total_ids:
            amt = slip.credit_note and -extra.total or extra.total
            amt = round(slip.credit_note and -extra.total or extra.total, slip.company_id and slip.company_id.currency_id and slip.company_id.currency_id.accuracy or 2)
            accounts = concept_structure_obj.get_accounts(cr, uid, extra.type_id, slip.structure_id, context=context)
            if accounts:
                debit_account_id = accounts.account_debit_structure_property and accounts.account_debit_structure_property.id or False
                credit_account_id = accounts.account_credit_structure_property and accounts.account_credit_structure_property.id or False
                if slip.contract_id.analytic_account_id:
                    centro_costo = slip.contract_id.analytic_account_id.id
                else:
                    centro_costo = False
                if not slip.employee_id.partner_id:
                    raise osv.except_osv(_('Error!'),_('El Empleado "%s" no tiene configurado correctamente el tercero en el empleado!')%(slip.employee_id.name))
                partner_id = slip.employee_id.partner_id.id
                partner_id_aux = extra.type_id.partner_id and extra.type_id.partner_id.id or partner_id
                timenow = slip.liquid_date
                period_id = period_pool.find(cr, uid, timenow, context=context)[0]                
                if debit_account_id:
                    debit_line = {
                    'name': extra.type_id.name,
                    'date': timenow,
                    'partner_id': partner_id_aux,
                    'account_id': debit_account_id,
                    'journal_id': slip.journal_id.id,
                    'period_id': period_id,
                    'debit': amt > 0.0 and amt or 0.0,
                    'credit': amt < 0.0 and -amt or 0.0,
                    'analytic_account_id': centro_costo,
                    'move_id': move_id,
                    'ref1': extra.type_id.code,
                }
                    move_line_obj.create(cr, uid, debit_line, context=context)
                    res['debit_sum'] += debit_line['debit'] - debit_line['credit']
                    
                if credit_account_id:
                    credit_line = {
                    'name': extra.type_id.name,
                    'date': timenow,
                    'partner_id': partner_id_aux,
                    'account_id': credit_account_id,
                    'journal_id': slip.journal_id.id,
                    'period_id': period_id,
                    'debit': amt < 0.0 and -amt or 0.0,
                    'credit': amt > 0.0 and amt or 0.0,
                    'analytic_account_id': centro_costo,
                    'move_id': move_id,
                    'ref1': extra.type_id.code,
                }
                    move_line_obj.create(cr, uid, credit_line, context=context)
                    res['credit_sum'] += credit_line['credit'] - credit_line['debit']
        return res
    
    def pago_prestamos(self, cr, uid, slip, period_id, move_id, context=None):
        move_line_obj = self.pool.get('account.move.line')
        res = {'debit_sum':0,'credit_sum':0,}
        for prestamo in slip.prestamos_ids:
            if slip.credit_note:
                self.pool.get('hr.payroll.prestamo.cuota').write(cr, SUPERUSER_ID, [prestamo.id], {'payslip_id': False},context=context)
            else:
                self.pool.get('hr.payroll.prestamo.cuota').write(cr, SUPERUSER_ID, [prestamo.id], {'payslip_id': slip.id},context=context)
        
        for prestamo in slip.prestamos_total_ids:
            amt = slip.credit_note and -prestamo.cuota or prestamo.cuota
            debit_account_id = prestamo.category_id.account_debit.id
            credit_interes_account_id = prestamo.category_id.account_debit.id
            credit_account_id = prestamo.category_id.account_credit.id
            centro_costo = slip.contract_id.analytic_account_id and slip.contract_id.analytic_account_id.id or False
            if prestamo.category_id.analytic_account_id:
                centro_costo = prestamo.category_id.analytic_account_id.id
                    
            partner_id_aux = prestamo.category_id.partner_id and prestamo.category_id.partner_id.id or False
            if not partner_id_aux:
                partner_id_aux = slip.employee_id.partner_id.id
            timenow=slip.liquid_date
            if debit_account_id:
                debit_line = {
                'name': prestamo.category_id.name,
                'date': timenow,
                'partner_id': partner_id_aux,
                'account_id': debit_account_id,
                'journal_id': slip.journal_id.id,
                'period_id': period_id,
                'debit': amt > 0.0 and amt or 0.0,
                'credit': amt < 0.0 and -amt or 0.0,
                'analytic_account_id': centro_costo,
                'move_id': move_id,
                'ref1': prestamo.category_id.code,
            }
                move_line_obj.create(cr, uid, debit_line, context=context)
                res['debit_sum'] += debit_line['debit'] - debit_line['credit']
                
            if credit_account_id:
                credit_line = {
                'name': prestamo.category_id.name,
                'date': timenow,
                'partner_id': partner_id_aux,
                'account_id': credit_account_id,
                'journal_id': slip.journal_id.id,
                'period_id': period_id,
                'debit': amt < 0.0 and -amt or 0.0,
                'credit': amt > 0.0 and amt or 0.0,
                'analytic_account_id': centro_costo,
                'move_id': move_id,
                'ref1': prestamo.category_id.code,
            }
                move_line_obj.create(cr, uid, credit_line, context=context)
                res['credit_sum'] += credit_line['credit'] - credit_line['debit']
        return res

    def onchange_employee_id(self, cr, uid, ids, employee_id, contract_id, context=None):
        res = {
            'value': {
                'contract_id': None, 'journal_id': None, 'payslip_period_id': None
                }
            }
        contract_obj = self.pool.get('hr.contract')
        period_obj = self.pool.get('payslip.period')
        employee_obj = self.pool.get('hr.employee')
        p_period = self.browse(cr, uid, ids, context=context).payslip_period_id
        period_ids = []
        if employee_id:
            if contract_id and contract_id in employee_obj.browse(cr, uid, employee_id).contract_ids.ids:
                contract_ids = [contract_id]
                period_ids = period_obj.search(cr, uid, [('schedule_pay', '=', contract_obj.
                                                          browse(cr, uid, contract_id, context=context).schedule_pay)])
            else:
                if p_period:
                    cond = [('employee_id', '=', employee_id), ('date_start', '<=', p_period.end_date), '|',
                            ('date_end', '>=', p_period.start_date), ('date_end', '=', False)]
                else:
                    dt_now = str(datetime.now())[:10]
                    cond = [('employee_id', '=', employee_id), '|', ('date_end', '>=', dt_now), ('date_end', '=', False)]
                contract_ids = contract_obj.search(cr, uid, cond, context=context)
            if contract_ids:
                k_0 = contract_ids[0]
                k_rec = contract_obj.browse(cr, uid, k_0, context=context)
                period_ids = period_obj.search(cr, uid, [('schedule_pay', '=', k_rec.schedule_pay)])
                res['value'].update({
                    'contract_id': k_rec.id,
                    'journal_id': k_rec.journal_id.id or False
                    })
            res['domain'] = {'contract_id': [('id', 'in', contract_ids)], 'payslip_period_id': [('id', 'in',
                                                                                                 period_ids)]}
        return res
    
    def get_inputs(self, cr, uid, contract, date_from, date_to, tipo_nomina, context=None):
        res = []
        contract_obj = self.pool.get('hr.contract')
        rule_obj = self.pool.get('hr.salary.rule')
        
        structure_ids = contract_obj.get_all_structures(cr, uid, contract, tipo_nomina, context=context)
        rule_ids = self.pool.get('hr.payroll.structure').get_all_rules(cr, uid, structure_ids, context=context)
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]

        for rule in rule_obj.browse(cr, uid, sorted_rule_ids, context=context):
            if rule.input_ids:
                for input in rule.input_ids:
                    inputs = {
                         'name': input.name,
                         'code': input.code,
                         'contract_id': contract.id,
                    }
                    res += [inputs]
        return res
        
    def get_worked_day_lines(self, cr, uid, slip, context=None):
        payslip = self.browse(cr, uid, slip, context=context)
        period = payslip.payslip_period_id
        period_obj = self.pool.get('payslip.period')
        contract = payslip.contract_id
        hp_type = payslip.tipo_nomina.code
        vac = payslip.tipo_nomina.code == 'Vacaciones'

        # String format
        start_period = period.start_period
        end_period = period.end_period
        k_start_date = contract.date_start
        k_end_date = contract.date_end

        # Date format
        dt_sp = datetime.strptime(start_period, DSDF).date()
        dt_ep = datetime.strptime(end_period, DSDF).date()
        dt_ksd = datetime.strptime(k_start_date, DSDF).date()
        dt_ked = datetime.strptime(k_end_date, DSDF).date() if k_end_date else False

        ps_types = ['Nomina', 'Liquidacion']
        if not payslip.company_id.fragment_vac:
            ps_types.append('Vacaciones')

        res = []

        # Validacion para saber si es la segunda nomina realizada en el mismo periodo
        dslip_per_q = ("SELECT hp.id FROM hr_payslip hp "
                       "LEFT JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                       "WHERE hp.payslip_period_id = {period} "
                       "AND hp.id != {payslip} "
                       "AND hpt.code in ('Nomina', 'Vacaciones') "
                       "AND contract_id = {contract}".format(
                            period=payslip.payslip_period_id.id,
                            payslip=payslip.id, contract=payslip.contract_id.id))
        dslip = orm.fetchall(cr, dslip_per_q)

        if hp_type in ps_types:
            w_days = {
                'name': "Dias Laborables",
                'sequence': 1,
                'code': 'WORK101',
                'symbol': '',
                'number_of_days': 0.0,
                'number_of_hours': 0.0,
                'contract_id': contract.id
            }
            paid_rest = {
                'name': _("Descanso Remunerado"),
                'sequence': 4,
                'code': 'DESCANSO_REMUNERADO',
                'symbol': '+',
                'number_of_days': 0.0,
                'number_of_hours': 0.0,
                'contract_id': contract.id
            }

            calendar = contract.working_hours
            w_hours = calendar.hours_payslip
            sch_pay = payslip.payslip_period_id.schedule_pay
            bm_type = payslip.payslip_period_id.bm_type
            lab_days = period_obj.get_schedule_days(cr, uid, sch_pay, context=context)
            w_days['number_of_days'] = lab_days
            w_days['number_of_hours'] = w_hours * lab_days

            # Dias trabajados, en principio se deben asumir iguales a los laborables
            worked = lab_days

            # Deduccion por inicio de contrato
            if dt_ksd > dt_sp:
                if dt_ep >= dt_ksd:
                    ded_start_days = (dt_ksd - dt_sp).days
                else:
                    ded_start_days = lab_days

                ded_start = {
                    'name': _("Deduccion por Inicio de contrato"),
                    'sequence': 2,
                    'code': 'DED_INICIO',
                    'symbol': '-',
                    'number_of_days': ded_start_days,
                    'number_of_hours': ded_start_days * w_hours,
                    'contract_id': contract.id
                }
                res += [ded_start]
                worked -= ded_start_days

            # Deduccion por fin de contrato
            if dt_ked and dt_ked <= dt_ep:
                ded_end_days = (dt_ep - dt_ked).days
                if dt_ep.day == 31 and ded_end_days:
                    ded_end_days -= 1
                if dt_ked.month == 2:
                    ded_end_days += 2

                if period.bm_type:
                    bmt_wh = "AND pp.bm_type = '{bm_type}' ".format(bm_type=period.bm_type)
                else:
                    bmt_wh = ""

                # ot_dedfin = ("SELECT wd.number_of_days, hp.id, pp.bm_type "
                #              "FROM hr_payslip_worked_days wd "
                #              "INNER JOIN hr_payslip hp ON hp.id = wd.payslip_id "
                #              "INNER JOIN payslip_period pp on pp.id = hp.payslip_period_id "
                #              "LEFT JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                #              "WHERE pp.start_date::VARCHAR like '{month}%' "
                #              "{bmt_wh} "
                #              "AND pp.schedule_pay = '{sch_pay}' "
                #              "AND hp.contract_id = {contract} "
                #              "AND hp.id != {payslip} "
                #              "AND wd.code = 'DED_FIN' "
                #              "AND hpt.code in ('Vacaciones', 'Nomina')".format(
                #                 month=payslip.payslip_period_id.start_period[0:7],
                #                 contract=contract.id,
                #                 sch_pay=sch_pay,
                #                 bmt_wh=bmt_wh,
                #                 payslip=payslip.id))
                # df_other_data = orm.fetchall(cr, ot_dedfin)
                # df_other = sum([x[0] for x in df_other_data])
                #
                # ded_end_days -= df_other
                if ded_end_days:
                    ded_end = {
                        'name': _("Deduccion por fin de contrato"),
                        'sequence': 2,
                        'code': 'DED_FIN',
                        'symbol': '-',
                        'number_of_days': ded_end_days,
                        'number_of_hours': ded_end_days * w_hours,
                        'contract_id': contract.id
                    }

                    if dt_ep.month == 2 and (sch_pay == 'bi-monthly' and bm_type == 'second' or sch_pay == 'monthtly'):
                        ded_end['number_of_days'] += 2
                        ded_end['number_of_hours'] += 2 * w_hours
                        worked -= 2

                    res += [ded_end]

                worked -= ded_end_days

                dom31 = end_period[8:10] == '31' and datetime.strptime(end_period, "%Y-%m-%d").weekday() == 6
                apr = contract.type_id.type_class == 'apr'
                undef = contract.type_id.term == 'indefinido'

                l_kw_day = int(calendar.attendance_ids[-1].dayofweek)
                if dt_ked.weekday() == l_kw_day and undef and not apr:
                    days_workable = len(set([x.dayofweek for x in calendar.attendance_ids]))
                    if days_workable == 5:
                        c_day = 2
                        if dom31 and k_end_date[8:10] == '29':
                            c_day = 1
                    elif days_workable == 7:
                        c_day = 0
                    else:  # 6 days of week
                        c_day = 1
                    paid_rest['number_of_days'] = c_day
                    paid_rest['number_of_hours'] = c_day * w_hours
                    worked += c_day
                    res += [paid_rest]

            leaves_worked_lines = {}
            days_total = (dt_ep - dt_sp).days + 1
            days_payslip_total = 0

            feb_fix = sch_pay == 'bi-monthly' and bm_type == 'second' and dt_ep.month == 2 and payslip.tipo_nomina.code == 'Nomina'

            # Ausencias
            prev_pays = {
                'name': _("Dias liquidados en otras nominas"),
                'sequence': 3,
                'code': 'PREV_PAYS',
                'symbol': '-',
                'number_of_days': 0,
                'number_of_hours': 0,
                'contract_id': contract.id
            }
            prev_aus = {
                'name': _("Ausencias de otros periodos"),
                'sequence': 3,
                'code': 'PREV_AUS',
                'symbol': '+',
                'number_of_days': 0,
                'number_of_hours': 0,
                'contract_id': contract.id
            }

            if payslip.company_id.aus_prev:
                for leave in payslip.leave_ids:
                    if leave.holiday_status_id.sub_wd:
                        for leave_day in leave.line_ids:
                            prev_period = leave_day.name < start_period
                            not_payed = leave_day.state == 'validate'
                            if start_period <= leave.approve_date <= end_period:
                                if prev_period and not_payed:
                                    prev_pays['number_of_days'] += leave_day.days_payslip
                                    prev_pays['number_of_hours'] += leave_day.days_payslip * w_hours

                                    prev_aus['number_of_days'] += leave_day.days_payslip
                                    prev_aus['number_of_hours'] += leave_day.days_payslip * w_hours

            # Ausencias por dias
            for leave in payslip.leave_days_ids:
                feb28 = False
                if leave.state == 'paid' and dslip:
                    continue
                app_31 = True if leave.holiday_status_id.apply_payslip_pay_31 else False
                if leave.days_payslip > 0:
                    days_payslip = leave.days_payslip
                    hours_payslip = leave.hours_payslip
                    if leave.holiday_status_id.sub_wd and leave.state == "validate":
                        key = (leave.holiday_status_id.id, '-')
                        days_payslip_total += days_payslip
                        if int(days_total) == int(days_payslip_total) and not feb_fix:
                            if not app_31:
                                days_payslip += lab_days - days_payslip_total
                                hours_payslip += w_hours * (lab_days - days_payslip_total)
                        if app_31 and leave.name[-2:] == '31':
                            pass
                        else:
                            worked -= days_payslip
                        if leave.name[5:12] == '02-28' and leave.holiday_id.date_to[0:10] > leave.name:
                            worked -= 2
                            feb28 = True
                        if key not in leaves_worked_lines:
                            l_hol_name = leave.holiday_status_id.name
                            name = (u"Días %s") % l_hol_name.capitalize()
                            leaves_worked_lines[key] = {
                                'name': name,
                                'sequence': 4,
                                'code': (leave.holiday_status_id.code or 'nocode'),
                                'symbol': '-',
                                'number_of_days': days_payslip + (2 if feb28 else 0),
                                'number_of_hours': hours_payslip + (2 * w_hours if feb28 else 0),
                                'contract_id': contract.id,
                            }
                        else:
                            leaves_worked_lines[key]['number_of_days'] += days_payslip + (2 if feb28 else 0)
                            leaves_worked_lines[key]['number_of_hours'] += hours_payslip + (2 * w_hours if feb28 else 0)

                if leave.holiday_status_id.vacaciones and leave.state == 'paid':
                    prev_pays['number_of_days'] += leave.days_payslip
                    prev_pays['number_of_hours'] += leave.days_payslip * w_hours
                    worked -= leave.days_payslip

            # Ausencias, completa, caso especial febrero
            if dt_ep.month == 2 and (sch_pay == 'bi-monthly' and bm_type == 'second' or sch_pay == 'monthtly'):
                for leave in payslip.leave_ids.filtered(
                        lambda p: (datetime.strptime(p.date_from, DSTF) - timedelta(hours=5)).month == 2
                                   and (datetime.strptime(p.date_from, DSTF) - timedelta(hours=5)).month != 2):
                    key = (leave.holiday_status_id.id, '-')
                    leaves_worked_lines[key]['number_of_days'] += 2
                    leaves_worked_lines[key]['number_of_hours'] += w_hours * 2
                    worked -= 2
            if sch_pay == 'bi-monthly' and bm_type == 'second' and dt_ep.month == 2 and payslip.tipo_nomina.code == 'Nomina':
                for leave in leaves_worked_lines:
                    if leaves_worked_lines[leave]['number_of_days'] > 15:
                        worked += leaves_worked_lines[leave]['number_of_days'] - 15
                        leaves_worked_lines[leave]['number_of_days'] -= leaves_worked_lines[leave]['number_of_days'] - 15
                        leaves_worked_lines[leave]['number_of_days'] -= (leaves_worked_lines[leave]['number_of_days'] - 15) * w_hours
                if worked < 0:
                    worked = 0

            leaves_worked_lines = [value for key, value in leaves_worked_lines.items()]

            # Dias pagados en otras nominas
            if period.bm_type:
                bmt_wh = "AND pp.bm_type = '{bm_type}' ".format(bm_type=period.bm_type)
            else:
                bmt_wh = " "

            if sch_pay == 'monthly':
                sch_wh = " "
            else:
                sch_wh = "AND pp.schedule_pay = '{sch_pay}' ".format(sch_pay=sch_pay)

            ot_wd = ("SELECT wd.number_of_days, hp.id, pp.bm_type, wd.symbol, wd.code "
                     "FROM hr_payslip_worked_days wd "
                     "INNER JOIN hr_payslip hp ON hp.id = wd.payslip_id "
                     "INNER JOIN payslip_period pp on pp.id = hp.payslip_period_id "
                     "LEFT JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                     "WHERE pp.start_period::VARCHAR like '{month}%' "
                     " {bmt_wh} "
                     " {sch_wh} "
                     "AND hp.contract_id = {contract} "
                     "AND hp.id != {payslip} "
                     "AND wd.code not in ('WORK101', 'DESCANSO_REMUNERADO') "
                     "AND hpt.code in ('Vacaciones', 'Nomina')".format(
                            month=payslip.payslip_period_id.start_period[0:7],
                            contract=contract.id,
                            bmt_wh=bmt_wh,
                            sch_wh=sch_wh,
                            payslip=payslip.id))
            wd_other_data = orm.fetchall(cr, ot_wd)
            types = [x[2] for x in wd_other_data]
            # AJUSTE CUANDO EXISTE NOMINAS QUINCENALES, DE VACACIONES MENSUALES Y DE LOQUIDACION MENSUAL EN EL MISMO MES
            # !!!!!!!!
            if None in types and 'first' in types and 'second' in types:
                wd_other = sum([x[0] if x[2] is None or (x[2] == 'second' and x[4] == 'WORK102') else 0 for x in wd_other_data])
            else:
                wd_plus = sum([x[0] if x[3] in ('+', '') else 0 for x in wd_other_data])
                wd_prev = sum([x[0] if x[4] in ('PREV_AUS', 'PREV_PAYS') else 0 for x in wd_other_data])
                wd_minus = sum([x[0] if x[3] == '-' and x[4] not in ('DED_INICIO', 'DED_FIN') else 0 for x in wd_other_data])

                wd_other = wd_plus + wd_minus - wd_prev
            # #############################################

            if wd_other:
                prev_pays['number_of_days'] += wd_other
                prev_pays['number_of_hours'] += wd_other * w_hours
                worked -= wd_other

            if not payslip.company_id.fragment_vac:
                vac_flag, vac_end = False, False
                if vac:
                    for leave in payslip.leave_ids:
                        ldt = datetime.strptime(leave.date_to[0:10], DSDF).date()
                        if leave.holiday_status_id.vacaciones and ldt < dt_ep:
                            vac_flag = True
                            vac_end = ldt

                if vac_flag and vac_end:
                    fix = 1 if dt_ep.day == 31 else 0
                    wd_vacnom = (dt_ep - vac_end).days - fix
                    worked -= wd_vacnom
                    worked = 0 if worked < 0 else worked

            wd_days = {
                'name': _("Días Trabajados"),
                'sequence': 5,
                'code': 'WORK102',
                'symbol': '',
                'number_of_days': worked,
                'number_of_hours': worked * w_hours,
                'contract_id': contract.id
            }
            res += [wd_days, w_days] + leaves_worked_lines
            if prev_aus['number_of_days'] > 0:
                res += [prev_aus]
            if prev_pays['number_of_days'] > 0:
                res += [prev_pays]
        return res

    def get_worked_day_linesbk(self, cr, uid, slip, context=None):
        k_obj = self.pool.get('hr.contract')
        payslip_period_obj = self.pool.get('payslip.period')
        payslip = self.browse(cr, uid, slip, context=context)
        contract = payslip.contract_id
        vac = payslip.tipo_nomina.code == 'Vacaciones'
        res = []

        w_days = {
             'name': _("Días Laborables"),
             'sequence': 1,
             'code': 'WORK101',
             'symbol': '',
             'number_of_days': 0.0,
             'number_of_hours': 0.0,
             'contract_id': contract.id
            }

        k_deduct = {
             'name': _("Deduccion por Inicio o Fin de contrato"),
             'sequence': 2,
             'code': 'DEDUCCION_CONTRATO',
             'symbol': '-',
             'number_of_days': 0,
             'number_of_hours': 0,
             'contract_id': contract.id
            }

        k_integ = {  # TODO
             'name': _("Dias por Inicio del contrato"),
             'sequence': 2,
             'code': 'CONTRATO_INICIO',
             'symbol': '+',
             'number_of_days': 0,
             'number_of_hours': 0,
             'contract_id': contract.id
            }

        prev_pays = {
             'name': _("Dias de Trabajo pagados en Otras Nominas"),
             'sequence': 3,
             'code': 'PAGOS_ANTERIORES',
             'symbol': '-',
             'number_of_days': 0,
             'number_of_hours': 0,
             'contract_id': contract.id
            }

        paid_rest = {
            'name': _("Dencanso Remunerado"),
            'sequence': 4,
            'code': 'DESCANSO_REMUNERADO',
            'symbol': '+',
            'number_of_days': 0.0,
            'number_of_hours': 0.0,
            'contract_id': contract.id
            }

        wd_days = {
             'name': _("Días Trabajados"),
             'sequence': 5,
             'code': 'WORK102',
             'symbol': '',
             'number_of_days': 0.0,
             'number_of_hours': 0.0,
             'contract_id': contract.id
            }

        # Para liquidaciones
        if contract.separation_type == 'fired':
            notice_day = k_obj.compute_allocation_leave(cr, uid, contract, 'notice', context)
            notice = {
                 'name': _("Dias para el periodo de aviso."),
                 'sequence': 0,
                 'code': 'AVISO',
                 'number_of_days': notice_day,
                 'number_of_hours': 0.0,
                 'contract_id': contract.id
                }

            severance_day = k_obj.compute_allocation_leave(cr, uid, contract, 'severance', context)
            severance = {
                 'name': _("Días de Indemnización."),
                 'sequence': 9,
                 'code': 'INDEMN',
                 'symbol': '+',
                 'number_of_days': severance_day,
                 'number_of_hours': 0.0,
                 'contract_id': contract.id
                }
            res += [severance]
            res += [notice]
        
        # ********************************** Work In Time WORK101******************************
        calendar = contract.working_hours
        w_hours = calendar.hours_payslip
        sp_to_check = 'bi-monthly' if payslip.payslip_period_id.bm_type == 'first' else 'monthly'
        dias_dif = payslip_period_obj.get_schedule_days(cr, uid, sp_to_check, context=context)
        w_days['number_of_days'] = dias_dif
        w_days['number_of_hours'] = w_hours * w_days['number_of_days']
        
        # ************************************** WORK102 *********************************
        wd_days['number_of_days'] += w_days['number_of_days']
        wd_days['number_of_hours'] += w_days['number_of_hours']

        k_dt_strt = datetime.strptime(contract.date_start, DSDF).date()
        k_dt_end = datetime.strptime(contract.date_end, DSDF).date() if contract.date_end else False
        dt_strt_period = datetime.strptime(payslip.payslip_period_id.start_period, DSDF).date()
        dt_end_period = datetime.strptime(payslip.payslip_period_id.end_period, DSDF).date()
        vac_flag, vac_end, diff_vac = False, 0, 0
        if vac:
            for leave in payslip.leave_ids:
                ldt = datetime.strptime(leave.date_to[0:10], DSDF).date()
                if leave.holiday_status_id.vacaciones and ldt < dt_end_period:
                    vac_flag = True
                    vac_end = ldt

        wd_nod = wd_days['number_of_days']

        # Dias trabajables del mes liquidados en otras nominas
        diff_to_apply = 0
        ded_to_apply = 0
        if payslip.payslip_period_id.schedule_pay == 'monthly' or payslip.payslip_period_id.bm_type == 'second' or \
                payslip.tipo_nomina.code == 'Liquidacion':
            wd_oq = ("SELECT wd.number_of_days, hp.id, pp.bm_type "
                     "FROM hr_payslip_worked_days wd "
                     "INNER JOIN hr_payslip hp ON hp.id = wd.payslip_id "
                     "INNER JOIN payslip_period pp on pp.id = hp.payslip_period_id "
                     "LEFT JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                     "WHERE pp.start_date::VARCHAR like '{month}%' "
                     "AND hp.contract_id = {contract} "
                     "AND hp.id != {payslip} "
                     "AND wd.code = 'WORK101' AND hpt.code in ('Nomina')".format(
                        month=payslip.payslip_period_id.start_period[0:7],
                        contract=contract.id,
                        payslip=payslip.id))
            wd_other = orm.fetchall(cr, wd_oq)
            diff_to_apply = sum([x[0] if x[2] != 'second' else x[0]/2 for x in wd_other])

            wdvac = ("SELECT wd.number_of_days, hp.id, pp.bm_type "
                     "FROM hr_payslip_worked_days wd "
                     "INNER JOIN hr_payslip hp ON hp.id = wd.payslip_id "
                     "INNER JOIN payslip_period pp on pp.id = hp.payslip_period_id "
                     "LEFT JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                     "WHERE pp.start_date::VARCHAR like '{month}%' "
                     "AND hp.contract_id = {contract} "
                     "AND hp.id != {payslip} "
                     "AND wd.code = 'WORK102' AND hpt.code in ('Vacaciones')".format(
                        month=payslip.payslip_period_id.start_period[0:7],
                        contract=contract.id,
                        payslip=payslip.id))
            wd_vac = orm.fetchall(cr, wdvac)
            diff_vac = sum([x[0] if x[2] != 'second' else x[0] / 2 for x in wd_vac])

            ded_oq = ("SELECT wd.number_of_days, hp.id, pp.bm_type "
                      "FROM hr_payslip_worked_days wd "
                      "INNER JOIN hr_payslip hp ON hp.id = wd.payslip_id "
                      "INNER JOIN payslip_period pp on pp.id = hp.payslip_period_id "
                      "LEFT JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                      "WHERE pp.start_date::VARCHAR like '{month}%' "
                      "AND hp.contract_id = {contract} "
                      "AND hp.id != {payslip} "
                      "AND wd.code = 'DEDUCCION_CONTRATO' AND hpt.code in ('Nomina')".format(
                        month=payslip.payslip_period_id.start_period[0:7],
                        contract=contract.id,
                        payslip=payslip.id))
            ded_other = orm.fetchall(cr, ded_oq)
            ded_to_apply = sum([x[0] for x in ded_other])

            otherc = ("SELECT number_of_days, hp.id "
                      "FROM hr_payslip_worked_days wd "
                      "INNER JOIN hr_payslip hp ON hp.id = wd.payslip_id "
                      "INNER JOIN payslip_period pp on pp.id = hp.payslip_period_id "
                      "WHERE pp.start_date::VARCHAR like '{month}%' "
                      "AND hp.contract_id = {contract} "
                      "AND hp.id != {payslip} "
                      "AND code not in ('WORK101','WORK102','DEDUCCION_CONTRATO') AND hp.id in "
                      "(select hp.id FROM hr_payslip hp "
                      "INNER JOIN hr_payslip_concept hpc ON hpc.payslip_id = hp.id "
                      "WHERE hpc.code in ('BASICO','MAT_LIC','PAT_LIC') "
                      "AND hp.contract_id = {contract} "
                      "AND hp.id != {payslip})".format(
                        month=payslip.payslip_period_id.start_period[0:7],
                        contract=contract.id,
                        payslip=payslip.id))
            other_apply = orm.fetchall(cr, otherc)
            other_apply = sum([x[0] for x in other_apply])

            w102_oq = ("SELECT wd.number_of_days, hp.id, pp.bm_type "
                     "FROM hr_payslip_worked_days wd "
                     "INNER JOIN hr_payslip hp ON hp.id = wd.payslip_id "
                     "INNER JOIN payslip_period pp on pp.id = hp.payslip_period_id "
                     "LEFT JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                     "WHERE pp.start_date::VARCHAR like '{month}%' "
                     "AND hp.contract_id = {contract} "
                     "AND hp.id != {payslip} "
                     "AND wd.code = 'WORK102' AND hpt.code in ('Nomina')".format(
                        month=payslip.payslip_period_id.start_date[0:7],
                        contract=contract.id,
                        payslip=payslip.id))
            w102_o = orm.fetchall(cr, w102_oq)
            w102_o = sum([x[0] for x in w102_o])

        wd_nod -= diff_to_apply
        wd_nod2 = 0
        # Se le restan los dias que no trabajo dependiendo el inicio y final del contrato
        b = False
        doble_ded = False
        dt_start_ck = datetime.strptime(payslip.payslip_period_id.start_date[0:8] + '01', DSDF).date()
        k_ded = 0
        if k_dt_end and dt_strt_period <= k_dt_end < dt_end_period:
            # Deduccion por fin de contrato dentro del periodo
            wd_nod2 = (k_dt_end - dt_start_ck).days + 1
            b = True

        if k_dt_strt and dt_start_ck < k_dt_strt <= dt_end_period:
            # Deduccion por inicio de contrato dentro del periodo
            wd_nod2 = wd_nod2 - (k_dt_strt - dt_start_ck).days
            if not b:
                wd_nod2 += ded_to_apply
                if (k_dt_strt - dt_start_ck).days == ded_to_apply:
                    b = False
                else:
                    b = True
            else:
                doble_ded = True

        if b:
            k_deduct['number_of_days'] = w_days['number_of_days'] - wd_nod2
            k_deduct['number_of_hours'] = w_hours * k_deduct['number_of_days']
            k_ded = w_days['number_of_days'] - wd_nod2
            res += [k_deduct]

            l_kw_day = int(calendar.attendance_ids[-1].dayofweek)
            if k_dt_end and k_dt_end.weekday() == l_kw_day:
                if len(set([x.dayofweek for x in calendar.attendance_ids])) == 5:
                    c_day = 2
                else:  # 6 days of week
                    c_day = 1
                paid_rest['number_of_days'] = c_day
                paid_rest['number_of_hours'] = c_day * w_hours
                wd_nod += c_day
                res += [paid_rest]
        wd_vacnom = 0
        if vac_flag:
            wd_vacnom = (dt_end_period - vac_end).days
            prev_pays['number_of_days'] = wd_vacnom
            prev_pays['number_of_hours'] = wd_vacnom * w_hours
            res += [prev_pays]

        leaves_worked_lines = {}
        if payslip.payslip_period_id.schedule_pay == 'monthly' or payslip.payslip_period_id.bm_type == 'second':
            days_total = (dt_end_period - dt_start_ck).days + 1
        else:
            days_total = (dt_end_period - dt_strt_period).days + 1
        days_payslip_total = 0

        # Ausencias, parcial
        for leave in payslip.leave_days_ids:
            app_31 = True if leave.holiday_status_id.apply_payslip_pay_31 else False
            if leave.days_payslip > 0:
                days_payslip = leave.days_payslip
                hours_payslip = leave.hours_payslip
                if leave.holiday_status_id.sub_wd:
                    key = (leave.holiday_status_id.id, '-')
                    days_payslip_total += days_payslip
                    if int(days_total) == int(days_payslip_total):
                        days_payslip += dias_dif - days_payslip_total
                        hours_payslip += w_hours * (dias_dif - days_payslip_total)
                    if app_31 and leave.name[-2:] == '31':
                        pass
                    else:
                        wd_nod -= days_payslip
                    if key not in leaves_worked_lines:
                        l_hol_name = leave.holiday_status_id.name
                        name = (u"Días %s") % l_hol_name.capitalize()
                        leaves_worked_lines[key] = {
                            'name': name,
                            'sequence': 4,
                            'code': (leave.holiday_status_id.code or 'nocode'),
                            'symbol': '-',
                            'number_of_days': days_payslip,
                            'number_of_hours': hours_payslip,
                            'contract_id': contract.id,
                        }
                    else:
                        leaves_worked_lines[key]['number_of_days'] += days_payslip
                        leaves_worked_lines[key]['number_of_hours'] += hours_payslip

        # Ausencias, completa, caso especial febrero
        for leave in payslip.leave_ids.filtered(lambda p: (datetime.strptime(p.date_from, DSTF) - timedelta(hours=5)).month == 2
                                                          and (datetime.strptime(p.date_from, DSTF) - timedelta(hours=5)).month != 2):
            key = (leave.holiday_status_id.id, '-')
            leaves_worked_lines[key]['number_of_days'] += 2
            leaves_worked_lines[key]['number_of_hours'] += w_hours * 2
            wd_nod -= 2

        leaves_worked_lines = [value for key, value in leaves_worked_lines.items()]
        if not doble_ded:
            wd_days['number_of_days'] = wd_nod - k_ded - wd_vacnom - diff_vac
            wd_days['number_of_hours'] = (wd_nod - k_ded - wd_vacnom - diff_vac) * w_hours
        else:
            wd_days['number_of_days'] = 30 - w102_o - k_ded - wd_vacnom - diff_vac
            wd_days['number_of_hours'] = (30 - w102_o - k_ded - wd_vacnom - diff_vac) * w_hours
        res += [w_days, wd_days] + leaves_worked_lines
        return res


class payslip_period(osv.osv):
    _name = "payslip.period"
    _description = "Payslip period"
    
    def get_schedule_days(self, cr, uid, schedule_pay, context=None):
        dias_dif = 0
        if schedule_pay == 'weekly':
            dias_dif = 7
        elif schedule_pay == 'bi-monthly':
            dias_dif = 15
        elif schedule_pay == 'monthly':
            dias_dif = 30
        elif schedule_pay == 'dualmonth':
            dias_dif = 60
        elif schedule_pay == 'quarterly':
            dias_dif = 120
        elif schedule_pay == 'semi-annually':
            dias_dif = 180
        elif schedule_pay == 'annually':
            dias_dif = 360
            
        return dias_dif
    
    _columns = {
                'name': fields.char("Nombre", size=32 , required=True),
                'start_date': fields.date("Comienzo de Corte", required=True),
                'end_date': fields.date("Fin de Corte", required=True),
                'start_period': fields.date("Comienzo del Periodo", required=True),
                'end_period': fields.date("Fin del Periodo", required=True),
                'bm_type': fields.selection([('first', 'Primera quincena'), ('second', 'Segunda quincena')],
                                            'Tipo quincena'),
                'schedule_pay': fields.selection([
                    ('weekly', 'Semanal'),
                    ('bi-monthly', 'Quincenal'),
                    ('monthly', 'Mensual'),
                    ('dualmonth', 'Cada 2 Meses'),
                    ('quarterly', 'Cada Cuatro meses'),
                    ('semi-annually', 'Cada 6 Meses'),
                    ('annually', 'Anual'),
                    ], 'Pago Planificado', select=True, required=True),
    }    
 
class hr_payroll_run(osv.osv, EDIMixin):
    _name = 'hr.payslip.run'
    _inherit = ['hr.payslip.run', 'mail.thread', 'ir.needaction_mixin']
    
    _columns = {
        'payslip_period':fields.many2one("payslip.period", "Periodo" ),
        'analytic_account_id':fields.many2one("account.analytic.account", "Centro de Costo" ),
        'city_id':fields.many2one("res.city", "Ciudad Desempeno"),
        'company_id':fields.many2one('res.company', 'Company' ),
        'date_start': fields.related('payslip_period','start_date',type="date",string="Fecha Desde",readonly=True,store=True),
        'date_end': fields.related('payslip_period','end_date',type="date",string="Fecha Hasta",readonly=True,store=True),
        'start_period': fields.related('payslip_period','start_period',type="date",string="Inicio Periodo",readonly=True,store=True),
        'end_period': fields.related('payslip_period','end_period',type="date",string="Fin de Periodo",readonly=True,store=True),
        'bank_id': fields.many2one('res.bank', string="Banco"),
        'date': fields.date('Fecha Contabilizacion'),
        'date_liquidacion': fields.date('Fecha Liquidacion'),
        'tipo_nomina': fields.many2one('hr.payslip.type', "Tipo", required=True),
    }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.id,
        }
    
    def action_quotation_send(self, cr, uid, ids, context=None):
        payslip_pool = self.pool.get('hr.payslip')
        for run in self.browse(cr, uid, ids, context=context).slip_ids:
            payslip_pool.action_quotation_send(cr, uid, [run.id], context=context)
        return True
    
    def draft_payslip_run(self, cr, uid, ids, context=None):
        # payslip_pool = self.pool.get('hr.payslip')
        # wf_service = openerp.netsvc.LocalService("workflow")
        for run in self.browse(cr, uid, ids, context=context):
            for payslip in run.slip_ids:
                if payslip.state not in ['done','verify']:
                    continue
                payslip.cancel_sheet()
                payslip.draft_sheet()
        res=super(hr_payroll_run, self).draft_payslip_run(cr, uid, ids, context=context)
        return res
    
    def onchange_date(self, cr, uid, ids, date_start , date_end , context = None):
        res = {'value' :{'payslip_period': False}}
        period_obj = self.pool.get("payslip.period")
        if date_start and date_end:
            period_ids = period_obj.search(cr, uid, [('start_date','=', date_start) , ('end_date','=', date_end)] , context = context)
            if period_ids:
                res.get('value').update({'payslip_period': period_ids[0]})
        return res
    
    def onchange_period(self, cr , uid, ids, payslip_period , context = None):
        period_obj = self.pool.get("payslip.period")
        res = {'value': {'date_start': False, 'date_end': False}}
        if payslip_period:
            period_data = period_obj.browse(cr, uid, payslip_period, context=context)
            res['value'].update({'date_start': period_data.start_date ,'date_end': period_data.end_date })
        return res

    def copy(self, cr, uid, slip_id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        default.update({'slip_ids': [], 'state': 'draft'})
        return super(hr_payroll_run, self).copy(cr, uid, slip_id, default, context=context)


class hr_salary_rule(osv.osv):
    _inherit = ['hr.salary.rule']

    _columns = {
        'rules_account_ids': fields.one2many('hr.payroll.structure.accounts', 'salary_rule_id',
                                             string='Relacion Regla Estructura Cuentas'),
        'anticipos': fields.boolean('Regla de Anticipos'),
        'neto': fields.boolean('Regla del Neto a Pagar'),
        'salvaguarda': fields.float('% Salvaguarda', digits_compute= dp.get_precision('Account')),
        'novedad_category_id': fields.many2one('hr.payroll.novedades.category', 'Categoria Novedad', ondelete='cascade',
                                               select=True),
        'amount_select': fields.selection([('percentage', 'Percentage (%)'), ('fix', 'Fixed Amount'),
                                           ('code', 'Python Code'), ('method', 'Método')], string='Amount Type',
                                          select=True, required=True, help="The computation method for the rule "
                                                                           "amount."),
        }

    def compute_rule(self, cr, uid, rule_id, localdict, context=None):
        """
        :param rule_id: id of rule to compute
        :param localdict: dictionary containing the environement in which to compute the rule
        :return: returns a tuple build as the base/amount computed, the quantity and the rate
        :rtype: (float, float, float)
        """
        rule = self.browse(cr, uid, rule_id, context=context)
        if rule.amount_select == 'fix':
            try:
                res = rule.amount_fix, s_eval(rule.quantity, localdict), 100.0
            except:
                raise osv.except_osv(_('Error!'), _('Wrong quantity defined for salary rule %s (%s).') % (rule.name,
                                                                                                          rule.code))
        elif rule.amount_select == 'percentage':
            try:
                res = s_eval(rule.amount_percentage_base, localdict), s_eval(rule.quantity, localdict), rule.amount_percentage
            except:
                raise osv.except_osv(_('Error!'), _('Wrong percentage base or quantity defined for salary rule %s '
                                                    '(%s).') % (rule.name, rule.code))
        elif rule.amount_select == 'code':
            try:
                python_code = rule.amount_python_compute
                s_eval(python_code, localdict, mode='exec', nocopy=True)
                res = localdict['result'], 'result_qty' in localdict and localdict['result_qty'] or 1.0, \
                      'result_rate' in localdict and localdict['result_rate'] or 100.0
            except:
                raise osv.except_osv(_('Error!'), _('Codigo Erroneo para el contrato %s en la regla (%s).') % (
                    localdict['contract'].name, rule.code))
        else:
            self.reset_globals(cr, uid, context)
            res = eval('self._' + str(rule.code).lower() + '(cr, uid, rule_id, localdict, context=context)')
        # Regla de anticipos
        if rule.anticipos:
            payslip = localdict['payslip']
            amount, qty, rate = res
            tot_rule = amount * qty * rate / 100.0
            account_id = False  # TODO
            total = self.pool.get('hr.payslip').compute_advance_total_rule(cr, uid, payslip, tot_rule,
                                                                           account_id=account_id, context=context)
            res = total, 1, 100.0
        
        return res

class hr_payslip_line(osv.osv):

    _inherit = 'hr.payslip.line'
    
    _columns = { 
        'payslip_period_id': fields.related('slip_id', 'payslip_period_id', relation="payslip.period",type='many2one', string='Periodo', store=True),
        'payslip_run_id': fields.related('slip_id', 'payslip_run_id', relation="hr.payslip.run", type='many2one', string='Procesamiento Nomina', store=True),
    }
    
class hr_payroll_structure_cuentas(osv.osv):

    _name = 'hr.payroll.structure.accounts'
    _description = 'Cuentas Estructuras'
    
    _columns = { 
        'structure_id': fields.many2one('hr.payroll.structure', 'Estructura Salarial', required=True, ondelete='cascade', select=True),
        'salary_rule_id': fields.many2one('hr.salary.rule', 'Regla salarial',required=True, select=True),
        'parent_id': fields.related('structure_id', 'parent_id', relation="hr.payroll.structure",type='many2one', string='Padre', store=True),
        'utilizar_cuenta_padre': fields.boolean('En padre'),
        'analytic_journal_id_structure_property': fields.property(type='many2one',relation='account.analytic.journal',string="Diario analitico", help="Esta diario analitico sera usada al momento de validar una nomina"),
        'analytic_account_id_structure_property': fields.property(type='many2one',relation='account.analytic.account',string="Centro Costo", help="Esta cuenta analitica sera usada al momento de validar una nomina"),
        'account_credit_structure_property': fields.property(type='many2one',relation='account.account',string="Cuenta Credito", help="Esta cuenta credito sera usada al momento de validar una nomina"),
        'account_debit_structure_property': fields.property(type='many2one',relation='account.account',string="Cuenta Debito", help="Esta cuenta debito sera usada al momento de validar una nomina"),
    }

class hr_payroll_structure(osv.osv):
    _inherit = 'hr.payroll.structure'
    
    def check_repetidos(self, cr, uid, ids, context=None):
        for estructura in self.browse(cr, uid, ids, context=context):
            for cuenta_regla in estructura.rules_account_ids:
                repetidos_ids = self.pool.get('hr.payroll.structure.accounts').search(cr, uid, [('structure_id', '=', cuenta_regla.structure_id.id),('salary_rule_id', '=', cuenta_regla.salary_rule_id.id),('id', '<>', cuenta_regla.id)],context=context)
                
                if repetidos_ids:
                    return False
        return True
    
    _columns = {
        'oblicaciones_account_ids':fields.one2many('hr.concept.structure.account', 'structure_id', 'Cuentas Conceptos Fijos', domain=[('obligacion_category_id','!=',False)]),
        'novedades_account_ids':fields.one2many('hr.concept.structure.account', 'structure_id', 'Cuentas de Novedades', domain=[('novedad_category_id','!=',False)]),
        'extra_account_ids':fields.one2many('hr.concept.structure.account', 'structure_id', 'Cuentas de Horas Extra', domain=[('extra_hour_type_id','!=', False)]),
        'rules_account_ids':fields.one2many('hr.payroll.structure.accounts', 'structure_id', 'Relacion Regla Estructura Cuentas'),
        'company_id':fields.many2one('res.company', 'Company' ),
        'tipo_nomina': fields.many2one('hr.payslip.type', "Tipo"),
        'contract_types': fields.many2many('hr.contract.type', 'structure_contract_type_rel', 'structure_id', 'contract_type_id', 'Tipo contrato al que aplica'),
        'parent_id':fields.many2one('hr.payroll.structure', 'Parent'),
    }
    
    _defaults = {
        'parent_id': False,
    }
    
    _constraints = [
        (check_repetidos, 'No pueden haber reglas que se repitan dentro de la misma estructura', ['rules_account_ids']),
    ]
    
    def get_account_from_rule(self, cr, uid, structure_id, rule, context=None):
        res = False
        for rule_accounts in structure_id.rules_account_ids:
            if rule_accounts.salary_rule_id == rule:    
                if not rule_accounts.utilizar_cuenta_padre:
                    res = rule_accounts
                else:
                    res = self.get_account_from_rule(cr, uid, rule_accounts.parent_id, rule, context=context)
                break
        return res
    
    def button_compute_rules(self, cr, uid, ids, context=None):
        for structure in self.browse(cr, uid, ids, context=context):
            obj_structure_accounts = self.pool.get('hr.payroll.structure.accounts')
            regla_en_cuentas = []
            regla_en_cuentas_borrar = []
            padre = structure.parent_id
            reglas = structure.rule_ids
            
            while padre:
                reglas += padre.rule_ids
                padre = padre.parent_id
            
            for accountrule in structure.rules_account_ids:
                cuentaregla = accountrule.salary_rule_id
                if cuentaregla in reglas:
                    regla_en_cuentas.append(cuentaregla.id)
                else:
                    regla_en_cuentas_borrar.append(accountrule.id)
            
            for rule in structure.rule_ids:
                if rule.id not in regla_en_cuentas:
                    obj_structure_accounts.create(cr, uid, {'structure_id': structure.id,'salary_rule_id': rule.id,}, context=context)
            for rborrar in regla_en_cuentas_borrar:
                cr.execute("DELETE FROM hr_payroll_structure_accounts WHERE id = {id}".format(id=rborrar))
            # obj_structure_accounts.unlink(cr, uid, regla_en_cuentas_borrar, context=context)
            
        return True

class hr_novedades_cuentas(osv.osv):
    _name = 'hr.concept.structure.account'
    _description = 'Cuentas Estructuras Otros Conceptos'
    
    def get_accounts(self, cr, uid, object, structure, context=None):
        res=False
        for accounts in object.rules_account_ids:
            if accounts.structure_id == structure:
                res = accounts
                break
        return res
    
    _columns = { 
        'structure_id': fields.many2one('hr.payroll.structure', 'Estructura Salarial', required=True, ondelete='cascade', select=True),
        'extra_hour_type_id': fields.many2one('hr.payroll.extrahours.type', 'Categoria Hora Extra', ondelete='cascade', select=True),
        'novedad_category_id': fields.many2one('hr.payroll.novedades.category', 'Categoria Novedad', ondelete='cascade', select=True),
        'obligacion_category_id': fields.many2one('hr.payroll.obligacion.tributaria.category', 'Concepto Fijo', ondelete='cascade', select=True),
        'analytic_journal_id_structure_property': fields.property(type='many2one',relation='account.analytic.journal',string="Diario analitico",  help="Esta diario analitico sera usada al momento de validar una nomina"),
        'analytic_account_id_structure_property': fields.property(type='many2one',relation='account.analytic.account',string="Centro Costo",  help="Esta cuenta analitica sera usada al momento de validar una nomina"),
        'account_credit_structure_property': fields.property(type='many2one',relation='account.account',string="Cuenta Credito",  help="Esta cuenta credito sera usada al momento de validar una nomina"),
        'account_debit_structure_property': fields.property(type='many2one',relation='account.account',string="Cuenta Debito",  help="Esta cuenta debito sera usada al momento de validar una nomina"),
    }
        
class account_move(models.Model):
    _inherit = "account.move"
    _columns = {
        'payslip_run_id': fields.many2one('hr.payslip.run', 'Procesamiento de nomina',help="Documento del procesamiento de nómina"),
    }

class account_move_line(models.Model):
    _inherit = "account.move.line"
    
    payslip_run_id=fields2.Many2one('hr.payslip.run', string='Procesamiento Nomina', related='move_id.payslip_run_id', store=True)
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
