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
from .hr_payroll_concept import CATEGORIES, PARTNER_TYPE
def hours_time_string(hours):
    """ convert a number of hours (float) into a string with format '%H:%M' """
    minutes = int(round(hours * 60))
    return "%02d:%02d" % divmod(minutes, 60)

class hr_payslip_extrahours(osv.osv):
    _name = "hr.payslip.extrahours"
    _description = "Horas Extra Payslip"
    
    _columns = {
        'type_id': fields.many2one('hr.payroll.extrahours.type', 'Tipo', index=True),
        'valor': fields.float("Valor Unitario",readonly=True),
        'cantidad': fields.float("Cantidad",readonly=True),
        'total': fields.float("Total",readonly=True),
        'payslip_id': fields.many2one('hr.payslip', 'Payslip', required=True, ondelete='cascade', index=True),
    }

#Categoria o tipo de hora extra
class hr_payroll_extrahours_type(osv.osv):
    _name = "hr.payroll.extrahours.type"
    _description = "Tipo de Horas Extra"
    _columns = {
        'rules_account_ids':fields.one2many('hr.concept.structure.account', 'extra_hour_type_id', 'Estructura de Cuentas'),
        'horario': fields.one2many('hr.payroll.extrahours.type.time', 'hr_payroll_extrahours_type_id', 'Horario'),
        'multiplicador': fields.float('Factor', required=True, digits_compute= dp.get_precision('Payroll Rate')),
        'contract_types': fields.many2many('hr.contract.type', 'extra_type_contract_type', 'extra_type_id', 'contract_type_id', 'Contratos que aplican'),
        'name': fields.char('Nombre', size=64, required=True),
        'code': fields.char('Codigo', size=64, required=True),
        'descripcion': fields.text('Descripcion'),
        'python_code': fields.text('Codigo Python', required=True),
        'partner_type': fields.selection(PARTNER_TYPE, 'Tipo de tercero'),
        'concept_category': fields.selection(CATEGORIES, 'Categoria de concepto', required=True),
        'skip_payment': fields.boolean('Omitir calculo en nomina'),
        'reg_adm_debit': fields.many2one('account.account', 'Debito Regular Administrativo'),
        'reg_adm_credit': fields.many2one('account.account', 'Credito Regular Administrativo'),
        'reg_com_debit': fields.many2one('account.account', 'Debito Regular Comercial'),
        'reg_com_credit': fields.many2one('account.account', 'Credito Regular Comercial'),
        'reg_ope_debit': fields.many2one('account.account', 'Debito Regular Operativa'),
        'reg_ope_credit': fields.many2one('account.account', 'Credito Regular Operativa'),
        'int_adm_debit': fields.many2one('account.account', 'Debito Integral Administrativo'),
        'int_adm_credit': fields.many2one('account.account', 'Credito Integral Administrativo'),
        'int_com_debit': fields.many2one('account.account', 'Debito Integral Comercial'),
        'int_com_credit': fields.many2one('account.account', 'Credito Integral Comercial'),
        'int_ope_debit': fields.many2one('account.account', 'Debito Integral Operativa'),
        'int_ope_credit': fields.many2one('account.account', 'Credito Integral Operativa'),
        'apr_adm_debit': fields.many2one('account.account', 'Debito Aprendiz Administrativo'),
        'apr_adm_credit': fields.many2one('account.account', 'Credito Aprendiz Administrativo'),
        'apr_com_debit': fields.many2one('account.account', 'Debito Aprendiz Comercial'),
        'apr_com_credit': fields.many2one('account.account', 'Credito Aprendiz Comercial'),
        'apr_ope_debit': fields.many2one('account.account', 'Debito Aprendiz Operativa'),
        'apr_ope_credit': fields.many2one('account.account', 'Credito Aprendiz Operativa'),
    }
    
    _defaults = {
        'python_code':  '''
# Available variables:
# extra: hr.payslip.extrahours object
# ---------------------------------------
result = extra.contract_id.wage*extra.type_id.multiplicador/30/8
                        ''',
     }
    
    def check_horario(self, cr, uid, ids, context=None):
        for type in self.browse(cr, uid, ids, context):
            for horario1 in type.horario:
                for horario2 in type.horario:
                    if horario1.diasemana == horario2.diasemana:
                        if (horario2.hour_from > horario1.hour_from and horario2.hour_from < horario1.hour_to) or (horario2.hour_to > horario1.hour_from and horario2.hour_to < horario1.hour_to):
                                return False
        return True
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codgigo tiene que ser unico!'),
    ]
    
    _constraints = [
        (check_horario, 'Hay fechas que se sobrelapan dentro de este registro', ['horario']),
    ]

#Lineas del horario del tipo de hora extra
class hr_payroll_extrahours_type_time(osv.osv):
    _name = "hr.payroll.extrahours.type.time"
    _description = "Calendario de Horas Extra"
    _columns = {
        'hr_payroll_extrahours_type_id': fields.many2one('hr.payroll.extrahours.type', 'Tipo de Hora Extra'),
        # 'date_start': fields.datetime('Comienza', required=True),
        # 'date_end': fields.datetime('Finaliza', required=True),
        'hour_from' : fields.float('Desde', required=True, help="Start and End time of working.", select=True),
        'hour_to' : fields.float("Hasta", required=True),
        'diasemana':fields.selection([('0', 'Lunes'), 
                                  ('1', 'Martes'), 
                                  ('2', 'Miercoles'), 
                                  ('3', 'Jueves'), 
                                  ('4', 'Viernes'),
                                  ('5', 'Sabado'), 
                                  ('6', 'Domingo'), 
                                  ], 'Dia de la Semana', required=True)
    } 

#guarda las horas extra del empleado
class hr_payroll_extrahours(osv.osv, EDIMixin):
    _name = "hr.payroll.extrahours"
    _description = "Horas Extra"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    
    def _employee_get(obj, cr, uid, context=None):
        if context is None:
            context = {}
        ids = obj.pool.get('hr.employee').search(cr, uid, [('user_id', '=', uid)], context=context)
        if ids:
            return ids[0]
        else:
            raise osv.except_osv(_('Advertencia !'),_("Su usuario no esta vinculado a ningun empleado"))
        return False
    
    def _get_contract(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for extra in self.browse(cr, uid, ids, context):
            res[extra.id] = self.pool.get('hr.employee').get_contract(cr, uid, extra.employee_id, extra.date_start, context)
        return res
    
    def _compute_price(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for extra in self.browse(cr, uid, ids, context):
            res[extra.id] = extra.duracion*extra.contract_id.wage*extra.type_id.multiplicador/30/8#TODO cambiar formula a una dinamica para que aplique segun el periodo que trabaja
        return res
    
    def check_date_end(self, cr, uid, ids, context=None):
        for horaextra in self.browse(cr, uid, ids, context):
            if horaextra.date_start >= horaextra.date_end:
                return False
        return True
        
    def check_duracion(self, cr, uid, ids, context=None):
        for horaextra in self.browse(cr, uid, ids, context):
            if horaextra.duracion <= 0:
                return False
        return True

    def check_horario(self, cr, uid, ids, context=None):
        for horaextra in self.browse(cr, uid, ids, context):
            print "TODO check_horario"
        return True
        
    def onchange_duracion(self, cr , uid, ids, duracion, date_end, date_start, context = None):
        if duracion:
            var_duracion = duracion
            var_date_end = duracion
        return {'value': {'date_end': var_date_end}}
        
    def _check_date(self, cr, uid, ids):
        for extra in self.browse(cr, uid, ids):
            extra_ids = self.search(cr, uid, [('date_start', '<', extra.date_end), ('date_end', '>', extra.date_start), ('employee_id', '=', extra.employee_id.id), ('id', '<>', extra.id)])
            extra_ids += self.search(cr, uid, [('date_start', '=', extra.date_end), ('date_end', '=', extra.date_start), ('employee_id', '=', extra.employee_id.id), ('id', '<>', extra.id)])
            if extra_ids:
                return False
        return True
    
    _columns = {
        'payslip_id': fields.many2one('hr.payslip', 'Pagado en nomina', readonly=True),
        'moneda_local': fields.related('company_id','currency_id',type="many2one",relation="res.currency",string="Moneda Local",readonly=True,store=True),
        'date_start': fields.datetime('Comienza', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_end': fields.datetime('Finaliza', help="llene solo la duracion o la fecha final", readonly=True, states={'draft': [('readonly', False)]}),
        'approve_date': fields.date('Fecha de aprobacion', help="Fecha en la que se aprobo la hora extra, dejela vacia para que se llene automaticamente", readonly=True, states={'confirmed': [('readonly', False)], 'draft': [('readonly', False)]}),
        'duracion' : fields.float("Duracion", help="llene solo la duracion o fecha final", readonly=True, states={'draft': [('readonly', False)]}),
        'type_id': fields.many2one('hr.payroll.extrahours.type', 'Tipo', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'employee_id': fields.many2one('hr.employee', 'Empleado', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'company_id': fields.related('contract_id','company_id',type="many2one",relation="res.company",string="Compania",readonly=True,store=True),
        'contract_id': fields.many2one('hr.contract', 'Contrato', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'contract_id_2': fields.many2one('hr.contract', 'Contrato', required=True, readonly=True),
        'unit': fields.float("Valor Unitario", digits_compute=dp.get_precision('Account'), readonly=True),
        'total': fields.float("Total", digits_compute=dp.get_precision('Account'), readonly=True),
        'description': fields.text('Descripcion', readonly=True, states={'draft': [('readonly', False)]}),
        'name': fields.char('Codigo',size=64,readonly=True),
        'account_analytic_id': fields.many2one('account.analytic.account', 'Centro de Costo'),
        'state':fields.selection([('draft', 'Borrador'), 
                                  ('confirmed', 'Confirmada'), 
                                  ('validated', 'Validada'), 
                                  ('refused', 'Rechazada'), 
                                  ('cancelled', 'Cancelada'), 
                                  ('paid', 'Pagada'), 
                                  ], 'Estado', select=True, readonly=True)
    }
    
    _defaults = {
        'date_start': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'state': 'draft',
        'employee_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).employee_id and self.pool.get('res.users').browse(cr, uid, uid, c).employee_id.id or False,
    }
    
    _constraints = [
        (check_horario, 'Hay fechas que se sobrelapan dentro de este registro', ['horario']),
        (check_date_end, 'La fecha final debe ser mayor a la inicial', ['date_end']),
        (check_duracion, 'La duracion debe ser mayor a 0', ['duracion']),
        (_check_date, 'No puede tener 2 horas extra que se sobrelapen para el mismo empleado!', ['date_start','date_end']),
    ]
    
    _track = {
        'state': {
            'hr_payroll_extended.mt_horaextra_new': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'draft',
            'hr_payroll_extended.mt_horaextra_confirmada': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'confirmed',
            'hr_payroll_extended.mt_horaextra_validada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'validated',
            'hr_payroll_extended.mt_horaextra_rechazada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'refused',
            'hr_payroll_extended.mt_horaextra_cancelada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelled',
        },
    }
    
    def draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'draft'})
        return True
    
    def confirm(self, cr, uid, ids, context=None):
        self.compute_value(cr, uid, ids, context=context)
        self.write(cr, uid, ids , {'state':'confirmed'})
        return True
        
    def validate(self, cr, uid, ids, context=None):
        for horaextra in self.browse(cr, uid, ids, context):
            if not horaextra.approve_date:
                self.write(cr, uid, [horaextra.id], {'approve_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)})
        self.write(cr, uid, ids , {'state':'validated'})
        return True
    
    def refuse(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'refused'})
        return True
    
    def done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'done'})
        return True
        
    def cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'cancelled'})
        return True
    
    def onchange_employee(self, cr , uid, ids, employee_id, date_start, context=None):
        value = {}
        if employee_id and date_start:
            empleado = self.pool.get('hr.employee').browse(cr, uid, employee_id, context)
            contract_id = self.pool.get('hr.employee').get_contract(cr, uid, empleado, date_start, context)
            contrato = self.pool.get('hr.contract').browse(cr, uid, contract_id, context)
            value['contract_id'] = contrato.id
            value['contract_id_2'] = contrato.id
            
        return {'value': value}
    
    def onchange_dates(self, cr, uid, ids, date_start, duracion=False, date_end=False,employee_id=False,type_id=False,dura2=False,context=None):
        """Returns duracion and/or end date based on values passed
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user's ID for security checks,
        @param ids: List of calendar event's IDs.
        @param date_start: Starting date
        @param duracion: duracion between start date and end date
        @param date_end: Ending Datee
        @param context: A standard dictionary for contextual values
        """
        if context is None:
            context = {}

        value = {}
        if not date_start:
            return value
        if not date_end and not duracion:
            duracion = 1.00
            value['duracion'] = duracion
        start = datetime.strptime(date_start, "%Y-%m-%d %H:%M:%S")
        if date_end and not duracion:
            end = datetime.strptime(date_end, "%Y-%m-%d %H:%M:%S")
            diff = end - start
            duracion = float(diff.days)* 24 + (float(diff.seconds) / 3600)
            value['duracion'] = round(duracion, 2)
        elif not date_end:
            end = start + timedelta(hours=duracion)
            value['date_end'] = end.strftime("%Y-%m-%d %H:%M:%S")
        elif date_end and duracion:
            # we have both, keep them synchronized:
            # set duracion based on date_end (arbitrary decision: this avoid
            # getting dates like 06:31:48 instead of 06:32:00)
            end = datetime.strptime(date_end, "%Y-%m-%d %H:%M:%S")
            diff = end - start
            duracion = float(diff.days)* 24 + (float(diff.seconds) / 3600)
            value['duracion'] = round(duracion, 2)

        return {'value': value}
        
    def unlink(self, cr, uid, ids, context=None):
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.state not in  ['draft','cancelled']:
                raise osv.except_osv(_('Advertencia!'),_('No puede borrar una hora extra que no esta en borrador o cancelada!'))
        return super(hr_payroll_extrahours, self).unlink(cr, uid, ids, context)
    
    def write(self, cr, uid, ids, vals, context=None):
        #valores readonly
        if vals.get('contract_id'):
            vals['contract_id_2'] = vals.get('contract_id')
            
        #agrega los followers por defecto
        if 'employee_id' in vals:
            for req in self.browse(cr, uid, ids, context=context):
                empleado = self.pool.get('hr.employee').browse(cr, uid, vals.get('employee_id'), context=context)
                if empleado.partner_id not in req.message_follower_ids:
                    message_follower_ids = []
                    message_follower_ids += req.message_follower_ids
                    message_follower_ids.append(empleado.partner_id)
                    vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
                    if empleado.parent_id.partner_id not in req.message_follower_ids:
                        message_follower_ids += req.message_follower_ids
                        message_follower_ids.append(empleado.partner_id)
                        vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
        
         #llama al metodo padre
        result = super(hr_payroll_extrahours, self).write(cr, uid, ids, vals, context=context)
        
        return result
    
    def create(self, cr, uid, vals, context=None):
        
        #valores readonly
        vals['contract_id_2'] = vals.get('contract_id')
           
        #agrega numero de secuencia
        vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'payroll.extras.number') or '/'
        
        #metodo padre
        result = super(hr_payroll_extrahours, self).create(cr, uid, vals, context=context)
        
        #agrega al empleado como follower
        if 'employee_id' in vals:
            for req in self.browse(cr, uid, [result], context=context):
                empleado = self.pool.get('hr.employee').browse(cr, uid, vals.get('employee_id'), context=context)
                if empleado.partner_id not in req.message_follower_ids:
                    message_follower_ids = []
                    message_follower_ids += req.message_follower_ids
                    message_follower_ids.append(empleado.partner_id)
                    vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
                    if empleado.parent_id and empleado.parent_id.partner_id not in req.message_follower_ids:
                        message_follower_ids += req.message_follower_ids
                        message_follower_ids.append(empleado.partner_id)
                        vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
                self.write(cr, uid, result, vals, context=context)
        
        return result
    
    def compute_value(self, cr, uid, ids, context=None):
        for extra in self.browse(cr, uid, ids, context=context):
            if extra.state != 'paid':
                try:
                    localdict = {'result': 0.0, 'extra': extra,}
                    eval(extra.type_id.python_code, localdict, mode='exec', nocopy=True)
                    result = localdict['result']
                    self.write(cr, uid, [extra.id], {'unit':result,'total':result*extra.duracion}, context=context)
                except:
                    raise osv.except_osv(_('Error!'), _('Calculo Erroneo para la hora extra (%s).')% (extra.name))
        return True
