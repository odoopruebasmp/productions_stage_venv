# -*- coding: utf-8 -*-
import logging
import time
from calendar import monthrange
from datetime import datetime, timedelta
from operator import itemgetter
from dateutil.relativedelta import relativedelta

import openerp.addons.decimal_precision as dp
from openerp.addons.base.res.res_partner import _tz_get
from openerp.osv import fields, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as DSDF, DEFAULT_SERVER_DATETIME_FORMAT as DSTF
from openerp.tools.translate import _
from pytz import timezone
from openerp.addons.avancys_orm import avancys_orm as orm
from .hr_payroll_concept import CATEGORIES, PARTNER_TYPE
from openerp.exceptions import Warning


_logger = logging.getLogger(__name__)


class hr_holidays(osv.osv):
    _inherit = "hr.holidays"
    _order = 'date_from desc'

    def _compute_all(self, cr, uid, ids, name, args, context=None):
        res = {}
        for leave in self.browse(cr, uid, ids, context=context):
            if leave.apply_payslip_pay_31:
                add31 = True
            else:
                add31 = False
            if leave.number_of_days_dummy:
                res[leave.id] = {
                    'number_of_hours_in_payslip': 0.0,
                    'number_of_hours': 0.0,
                    'number_of_days_in_payslip': 0.0,
                    'number_of_days_temp': leave.number_of_days_dummy
                }
            else:
                res[leave.id] = {
                    'number_of_hours_in_payslip': 0.0,
                    'number_of_hours': 0.0,
                    'number_of_days_in_payslip': 0.0,
                    'number_of_days_temp': 0.0
                }
                for days in leave.line_ids:
                    if add31 and days.name[-2:] == '31':
                        res[leave.id]['number_of_hours_in_payslip'] += 1
                        res[leave.id]['number_of_hours'] += days.hours_assigned
                        res[leave.id]['number_of_days_in_payslip'] += 1
                        res[leave.id]['number_of_days_temp'] += days.days_assigned
                    else:
                        res[leave.id]['number_of_hours_in_payslip'] += days.hours_payslip
                        res[leave.id]['number_of_hours'] += days.hours_assigned
                        res[leave.id]['number_of_days_in_payslip'] += days.days_payslip
                        res[leave.id]['number_of_days_temp'] += days.days_assigned

        return res

    def _factor_inv_write(self, cr, uid, holiday_id, name, value, arg, context=None):
        return self.write(cr, uid, [holiday_id], {'number_of_days_dummy': value}, context=context)

    def _get_contract(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for leave in self.browse(cr, uid, ids, context=context).filtered(lambda x: x.date_from):
            res[leave.id] = self.pool.get('hr.employee').get_contract(cr, uid, leave.employee_id, leave.date_from,
                                                                      context=context)
        return res

    def _check_date(self, cr, uid, ids, context=None):
        # if context is None:
        #     context = {}
        # for holiday in self.browse(cr, uid, ids, context=context):
        #     if holiday.type == 'remove' and holiday.state not in ['draft', 'cancel', 'refuse']:
        #         holiday_ids = self.search(cr, uid,
        #                                   [('date_from', '<=', holiday.date_to), ('date_to', '>=', holiday.date_from),
        #                                    ('employee_id', '=', holiday.employee_id.id), (
        #                                        'id', '<>', holiday.id), ('type', '=', 'remove'),
        #                                    ('state', 'not in', ['draft', 'cancel', 'refuse'])], context=context)
        #         if holiday_ids:
        #             return False
        return True

    def _get_workdays_id(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for leave in self.browse(cr, uid, ids, context=context):
            if leave.contract_id:
                working_hours = False

                if leave.holiday_status_id.vacaciones:
                    if leave.contract_id.vacations_calendar_id:
                        working_hours_primary = leave.contract_id.vacations_calendar_id
                    else:
                        raise osv.except_osv(
                            _('Error Configuracion!'), _("Contrato sin horario vacaciones definido"))
                else:
                    if leave.contract_id.working_hours:
                        working_hours_primary = leave.contract_id.working_hours
                    else:
                        raise osv.except_osv(
                            _('Error Configuracion!'), _("Contrato sin horario laboral definido"))

                if leave.holiday_status_id and leave.holiday_status_id.working_hours_id:
                    working_hours = leave.holiday_status_id.working_hours_id
                else:
                    working_hours = working_hours_primary

                res[leave.id] = working_hours.id
        return res

    def _get_workdays_slip_id(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for leave in self.browse(cr, uid, ids, context=context):
            if leave.contract_id:
                working_hours = False
                if leave.holiday_status_id.vacaciones:
                    if leave.contract_id.vacations_calendar_id:
                        working_hours_primary = leave.contract_id.vacations_calendar_id
                    else:
                        raise osv.except_osv(
                            _('Error Configuracion!'), _("Contrato sin horario vacaciones definido"))
                else:
                    if leave.contract_id.working_hours:
                        working_hours_primary = leave.contract_id.working_hours
                    else:
                        raise osv.except_osv(
                            _('Error Configuracion!'), _("Contrato sin horario laboral definido"))

                if leave.holiday_status_id and leave.holiday_status_id.working_hours_slip_id:
                    working_hours = leave.holiday_status_id.working_hours_slip_id
                else:
                    working_hours = working_hours_primary

                res[leave.id] = working_hours.id
        return res

    def _compute_number_of_hours(self, cr, uid, ids, name, args, context=None):
        res = {}
        for leave in self.browse(cr, uid, ids, context=context):
            sum = 0
            for days in leave.line_ids:
                sum += days.hours_assigned
            res[leave.id] = sum
        return res

    def _compute_number_of_hours_payslip(self, cr, uid, ids, name, args, context=None):
        res = {}
        for leave in self.browse(cr, uid, ids, context=context):
            sum = 0
            for days in leave.line_ids:
                sum += days.hours_payslip
            res[leave.id] = sum
        return res

    _columns = {
        'state': fields.selection([('draft', 'Borrador'),
                                   ('confirm', 'Confirmada'),
                                   ('validate', 'Validada'),
                                   ('refuse', 'Rechazada'),
                                   ('cancel', 'Cancelada'),
                                   ('paid', 'Pagada'),
                                   ('validate1', 'Segunda Validacion'),
                                   ], 'Estado', readonly=True),
        'approve_date': fields.datetime('Aprobacion', readonly=True,
                                        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]}),
        'create_date': fields.datetime('Creacion', readonly=True, select=True),
        'date_from': fields.datetime('Desde', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_to': fields.datetime('Hasta', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'payslip_id': fields.many2one('hr.payslip', 'Pagado en nomina', readonly=True),
        'allocation_rule_id': fields.many2one('hr.holidays.allocation.rule', 'Leave Allocation Rule'),
        'type_name': fields.related('holiday_status_id', 'name', type='char', string='Nambre del tipo'),
        'company_id': fields.related('contract_id', 'company_id', type='many2one', relation="res.company",
                                     string='Company', readonly=True, store=True),
        'number_of_days_dummy': fields.float('Number of Days', readonly=True, states={'draft': [('readonly', False)]}),
        'number_of_days_temp': fields.function(_compute_all, fnct_inv=_factor_inv_write, multi='all',
                                               string='Dias en ausencia', type="float", readonly=True,
                                               states={'draft': [('readonly', False)]}, store=True),
        'number_of_days_in_payslip': fields.function(_compute_all, string='Dias en nomina', multi='all'),
        'number_of_hours_in_payslip': fields.function(_compute_all, string='Horas en nomina', multi='all'),
        'number_of_hours': fields.function(_compute_all, string='Horas de ausencia', multi='all'),
        'name': fields.char('Codigo', readonly=True),
        'employee_id': fields.many2one('hr.employee', 'Empleado', required=True, readonly=True,
                                       states={'draft': [('readonly', False)]}),
        'holiday_status_id': fields.many2one("hr.holidays.status", "Leave Type", required=True, readonly=True,
                                             states={'draft': [('readonly', False)]}),
        'vacaciones': fields.related('holiday_status_id', 'vacaciones', type='boolean', string='Vacaciones'),
        'payed_vac': fields.float('Vacaciones en dinero'),
        'special_vac_base': fields.boolean('Disfrutadas con todo'),
        'contract_id': fields.function(_get_contract, type="many2one", relation='hr.contract', string="Contrato",
                                       store=True),
        'working_hours_id': fields.function(_get_workdays_id, type="many2one", relation='resource.calendar',
                                            string="Horario para ausencia"),
        'working_hours_slip_id': fields.function(_get_workdays_slip_id, type="many2one", relation='resource.calendar',
                                                 string="Horario para nomina"),
        'line_ids': fields.one2many('hr.holidays.days', 'holiday_id', 'Ausencias', readonly=True, ondelete='cascade'),
        'apply_cut': fields.related('holiday_status_id', 'apply_cut', type='boolean', string='Aplica en corte?',
                                    readonly=True, store=True),
        'dummy': fields.boolean('Actualizacion'),
        'apply_payslip_pay_31': fields.boolean('Paga dia 31 en nomina'),
        'absence_id': fields.many2one('hr.holidays', string="Ausencia a prorrogar",
                                      domain="['|', ('general_illness', '=', True), ('atep', '=', True), ('employee_id', '=', employee_id)]"),
        'general_illness_ext': fields.related('holiday_status_id', 'general_illness_ext', type='boolean',
                                              string='Prorroga Enfermedad general'),
        'general_illness': fields.related('holiday_status_id', 'general_illness', type='boolean',
                                          string='Enfermedad general'),
        'atep': fields.related('holiday_status_id', 'atep', type='boolean', string='ATEP'),
        'ibc': fields.float('Forzar IBC ausencia'),
        'pay_out_slip': fields.boolean('Pagar fuera de periodo', help="Permite al sistema calcular los dias ")
    }

    _constraints = [
        (_check_date, 'No puede tener 2 ausencias que se sobrelapen!',
         ['date_from', 'date_to']),
    ]

    _defaults = {
        'state': 'draft',
    }

    _track = {
        'state': {
            'hr_payroll_extended.mt_holidays_new': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'draft',
            'hr_payroll_extended.mt_holidays_confirmed': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'confirm',
            'hr_payroll_extended.mt_holidays_approved': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'validate',
            'hr_payroll_extended.mt_holidays_refused': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'refuse',
            'hr_payroll_extended.mt_holidays_cancel': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancel',
            'hr_payroll_extended.mt_holidays_validate1': lambda self, cr, uid, obj, ctx=None: obj[
                                                                                                  'state'] == 'validate1',
            'hr_payroll_extended.mt_holidays_paid': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'paid',
            },
        }

    def set_for_one_day_payslip(self, cr, uid, ids, context=None):
        calendar_days_pool = self.pool.get('resource.calendar')
        for holiday in self.browse(cr, uid, ids, context=context):
            no_entro = True
            if holiday.state == 'draft':
                schedule = holiday.working_hours_slip_id
                date_from = calendar_days_pool.format_tz_date(
                    cr, uid, schedule, holiday.date_from, date_format=DSTF, context=context)
                date_to = date_from
                day_of_week = date_from.weekday()

                for reg in schedule.attendance_ids:
                    if int(reg.dayofweek) == day_of_week:
                        no_entro = False
                        minute_in = (reg.hour_from * 60) % 60
                        minute_out = (reg.hour_to * 60) % 60
                        date_from = date_from.replace(hour=int(reg.hour_from), minute=int(
                            minute_in), second=0).astimezone(timezone('GMT'))
                        date_to = date_to.replace(hour=int(reg.hour_to), minute=int(
                            minute_out), second=0).astimezone(timezone('GMT'))
                        self.write(cr, uid, [holiday.id], {
                            'date_from': date_from, 'date_to': date_to, }, context=context)
                        self.compute(cr, uid, ids, context=context)
                if no_entro:
                    raise osv.except_osv(_('Error Configuracion!'), _(
                        "Este dia de la semana no esta presente en el horario"))
        return True

    def set_for_one_day(self, cr, uid, ids, context=None):
        calendar_days_pool = self.pool.get('resource.calendar')
        for holiday in self.browse(cr, uid, ids, context=context):
            no_entro = True
            if holiday.state == 'draft':
                schedule = holiday.working_hours_id
                date_from = calendar_days_pool.format_tz_date(
                    cr, uid, schedule, holiday.date_from, date_format=DSTF, context=context)
                date_to = date_from
                day_of_week = date_from.weekday()

                for reg in schedule.attendance_ids:
                    if int(reg.dayofweek) == day_of_week:
                        minute_in = (reg.hour_from * 60) % 60
                        minute_out = (reg.hour_to * 60) % 60
                        date_to = date_to.replace(hour=int(reg.hour_to), minute=int(
                            minute_out), second=0).astimezone(timezone('GMT'))
                        if no_entro:
                            date_from = date_from.replace(hour=int(reg.hour_from), minute=int(
                                minute_in), second=0).astimezone(timezone('GMT'))
                        no_entro = False

                self.write(cr, uid, [holiday.id], {
                    'date_from': date_from, 'date_to': date_to, }, context=context)
                self.compute(cr, uid, ids, context=context)
                if no_entro:
                    raise osv.except_osv(_('Error Configuracion!'), _(
                        "Este dia de la semana no esta presente en el horario"))
        return True

    def holidays_validate(self, cr, uid, ids, context=None):
        for holiday in self.browse(cr, uid, ids, context=context):
            if not holiday.approve_date:
                holiday.approve_date = datetime.now()
        self.write(cr, uid, ids, {'state': 'validate'}, context=context)
        return

    def holidays_confirm(self, cr, uid, ids, context=None):
        self.check_overlap(cr, uid, ids, context=context)
        self.compute(cr, uid, ids, context=context)
        return self.write(cr, uid, ids, {'state': 'confirm'})

    def holidays_refuse(self, cr, uid, ids, context=None):
        for holiday in self.browse(cr, uid, ids, context):
            if holiday.state == 'paid':
                raise Warning('No es posible rechazar una ausencia en estado pagada.')
        self.write(cr, uid, ids, {'state': 'refuse'})
        return

    def holidays_reset(self, cr, uid, ids, context=None):
        for holiday in self.browse(cr, uid, ids, context):
            if holiday.state == 'paid':
                raise Warning('No es posible rechazar una ausencia en estado pagada.')
        return self.write(cr, uid, ids, {'state': 'draft'})

    def create(self, cr, uid, vals, context=None):
        if vals.get('type') == 'add':
            vals['name'] = self.pool.get('ir.sequence').get(
                cr, uid, 'payroll.holiday.number.add') or '/'
        else:
            vals['name'] = self.pool.get('ir.sequence').get(
                cr, uid, 'payroll.holiday.number.remove') or '/'
        if vals.get('contract_id'):
            contract_obj = self.pool.get('hr.contract')
            employee_id = contract_obj.browse(
                cr, uid, vals.get('contract_id'), context=context).employee_id.id
            vals.pop('contract_id')
            vals.update({'employee_id': employee_id})
        return super(hr_holidays, self).create(cr, uid, vals, context=context)

    def get_ibs(self, cr, uid, ids, context=None):
        for holiday in self.browse(cr, uid, ids, context):
            if not holiday.at_date:
                raise Warning("No se ha especificado una fecha de accidente para la ausencia {h}".format(h=holiday.name))
            ref_date = datetime.strptime(holiday.at_date, "%Y-%m-%d") - relativedelta(months=1)
            month = datetime.strftime(ref_date, "%Y-%m")
            query = ("SELECT hpc.total, hpc.qty FROM hr_payslip_concept hpc "
                     "INNER JOIN hr_payslip hp ON hpc.payslip_id = hp.id "
                     "INNER JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                     "INNER JOIN payslip_period pp on hp.payslip_period_id = pp.id "
                     "WHERE pp.start_period::VARCHAR like '{month}%' "
                     "AND ((pp.bm_type = 'second' AND pp.schedule_pay = 'bi-monthly') "
                     "    OR (pp.schedule_pay = 'monthly')) "
                     "AND hpc.code = 'IBS' "
                     "AND hpt.code = 'Nomina' "
                     "AND hp.contract_id = {contract}".format(month=month, contract=holiday.contract_id.id))
            ibs_q = orm.fetchall(cr, query)
            if not ibs_q:
                query = ("SELECT hp.force_ibc, 30 FROM hr_payslip hp "
                         "INNER JOIN payslip_period pp on hp.payslip_period_id = pp.id "
                         "INNER JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                         "WHERE pp.start_period::VARCHAR like '{month}%' "
                         "AND ((pp.bm_type = 'second' and pp.schedule_pay = 'bi-monthly') "
                         "  OR (pp.schedule_pay = 'monthly')) "
                         "AND hpt.code = 'Nomina' "
                         "AND hp.contract_id = {contract}".format(month=month, contract=holiday.contract_id.id))
                ibs_q = orm.fetchall(cr, query)
                if ibs_q:
                    ibs_q = False if not ibs_q[0][0] else ibs_q
            if ibs_q:
                if ibs_q[0][1] == 1:
                    ibs_q = ibs_q[0][0]
                elif ibs_q[0][1] > 1:
                    ibs_q = (ibs_q[0][0] / ibs_q[0][1]) * 30
                else:
                    ibs_q = 0
            else:
                ibs_q = 0
            ibs_q = ibs_q if ibs_q else holiday.contract_id.wage
            return ibs_q

    def get_eff_ibs(self, cr, uid, ids, context=None):
        for holiday in self.browse(cr, uid, ids, context):
            if not holiday.at_date:
                raise Warning("No se ha especificado una fecha de accidente para la ausencia {h}".format(h=holiday.name))
            ref_date = datetime.strptime(holiday.at_date, "%Y-%m-%d") - relativedelta(months=1)
            month = datetime.strftime(ref_date, "%Y-%m")
            start = month + '-01'
            max_days = monthrange(int(month[0:4]), int(month[5:7]))[1]
            end = month + '-' + str(max_days)
            query = ("SELECT hpc.total, hpc.qty, hpc.payslip_id FROM hr_payslip_concept hpc "
                     "INNER JOIN hr_payslip hp ON hpc.payslip_id = hp.id "
                     "INNER JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                     "INNER JOIN payslip_period pp on hp.payslip_period_id = pp.id "
                     "WHERE pp.start_period::VARCHAR like '{month}%' "
                     "AND ((pp.bm_type = 'second' AND pp.schedule_pay = 'bi-monthly') "
                     "    OR (pp.schedule_pay = 'monthly')) "
                     "AND hpc.code = 'IBS' "
                     "AND hpt.code = 'Nomina' "
                     "AND hp.contract_id = {contract}".format(month=month, contract=holiday.contract_id.id))
            ibs_q = orm.fetchall(cr, query)

            if ibs_q:
                days_dict = self.pool.get('hr.payslip').collect_days(cr, uid, [], start, end,
                                                                     contract=holiday.contract_id.id)
                int_days_mes = days_dict['WORK101'] if 'WORK101' in days_dict else 0

                ded_inicio = days_dict['DED_INICIO'] if 'DED_INICIO' in days_dict else 0
                ded_fin = days_dict['DED_FIN'] if 'DED_FIN' in days_dict else 0
                eff_days = int_days_mes - ded_inicio - ded_fin
                ibs = ibs_q[0][0]
            else:
                ibs = holiday.contract_id.wage
                eff_days = 30
            return ibs, eff_days

    def _ibc(self, cr, uid, ids, context=None):
        payslip_obj = self.pool.get('hr.payslip')
        data = 0, 0, 0
        for holiday in self.browse(cr, uid, ids, context):
            if not holiday.at_date:
                raise Warning("No se ha especificado una fecha de referencia "
                              "para la ausencia {h}".format(h=holiday.name))
            if holiday.ibc:
                data = [holiday.ibc / 30, 30, holiday.ibc]
            else:
                contract = holiday.contract_id.id
                data = payslip_obj.ibcma(cr, uid, [], holiday.at_date, contract=contract)
        return data

    def check_overlap(self, cr, uid, ids, context=None):
        for holiday in self.browse(cr, uid, ids, context=context):
            query = ("SELECT hh.id "
                     "FROM hr_holidays hh "
                     "LEFT JOIN hr_holidays_status hs on hs.id = hh.holiday_status_id "
                     "WHERE (hs.overlap = 'f' or hs.overlap is Null) "
                     "AND hh.type != 'add' "
                     "AND hh.contract_id = {contract} "
                     "AND hh.state not in ('draft', 'refuse') "
                     "AND hh.id != {id} "
                     "AND NOT ( "
                     "    (hh.date_from <= '{hfrom}' and hh.date_to <='{hfrom}') "
                     "     OR (hh.date_from >= '{hto}' and hh.date_to >='{hto}'))".format(
                        hfrom=holiday.date_from, hto=holiday.date_to, contract=holiday.contract_id.id, id=holiday.id))
            overlap = orm.fetchall(cr, query)
            # Roster commodity validation
            cr.execute("SELECT state from ir_module_module where name = 'hr_roster'")
            roster = cr.fetchall()
            if roster and roster[0][0] == 'installed' and holiday.employee_id.commodity:
                commodity = True
            else:
                commodity = False
            if overlap and not holiday.holiday_status_id.overlap and not commodity:
                raise Warning("No se puede confirmar una ausencia que se sobrelape o cruce en fechas con otra del "
                              "mismo empleado")

    def compute(self, cr, uid, ids, context=None):
        for holiday in self.browse(cr, uid, ids, context=context):
            # Hack para el calculo de ausencias TODO
            v1 = holiday.compute_holiday()
            v2 = holiday.compute_holiday()

    def compute_holiday(self, cr, uid, ids, context=None):
        holiday_days_pool = self.pool.get('hr.holidays.days')
        calendar_days_pool = self.pool.get('resource.calendar')
        for holiday in self.browse(cr, uid, ids, context=context):
            # para que actualize los otros campos functiones y related
            if holiday.holiday_status_id.full_day:
                new_from = orm.local_date(holiday.date_from[0:10] + " 06:00:00")
                new_to = orm.local_date(holiday.date_to[0:10] + " 18:00:00")
                holiday.date_from = new_from
                holiday.date_to = new_to
            self.write(cr, uid, ids, {'dummy': not holiday.dummy, 'apply_payslip_pay_31': False}, context=context)
            if not holiday.type == 'remove':
                holiday_days_pool.unlink(cr, uid, [x.id for x in holiday.line_ids], context=context)
                continue
            if not holiday.contract_id:
                raise osv.except_osv(_('Error!'), _("La Ausencia no tiene contrato"))
            if not holiday.contract_id.working_hours:
                raise osv.except_osv(_('Error!'), _("El contrato no tiene un horario definido"))

            aband_type = holiday.holiday_status_id
            contract = holiday.contract_id
            if aband_type.force_working_hours:
                calendar = aband_type.working_hours_id
            else:
                calendar = contract.working_hours

            date_from = calendar_days_pool.format_tz_date(
                cr, uid, calendar, holiday.date_from, date_format=DSTF, context=context)
            date_to = calendar_days_pool.format_tz_date(
                cr, uid, calendar, holiday.date_to, date_format=DSTF, context=context)
            if aband_type.vacaciones:
                working_hours = calendar_days_pool.get_working_hours_payroll(
                    cr, uid, contract.vacations_calendar_id, date_from, date_to, context=context)
                working_hours_payslip = calendar_days_pool.get_working_hours_payroll(
                    cr, uid, holiday.working_hours_slip_id, date_from, date_to, context=context)
            else:
                working_hours = calendar_days_pool.get_working_hours_payroll(
                    cr, uid, holiday.working_hours_id, date_from, date_to, context=context)
                working_hours_payslip = calendar_days_pool.get_working_hours_payroll(
                    cr, uid, holiday.working_hours_slip_id, date_from, date_to, context=context)

            l_lines = []
            lines = {}
            for work in working_hours:
                key = work['date']
                add = {'name': work['date'], 'hours_assigned': work['hours'], 'days_assigned': work[
                    'days'], 'hours_payslip': 0, 'days_payslip': 0, 'week_day': work['week_day']}
                lines[key] = add
                l_lines.append(add)

            for work in working_hours_payslip:
                key = work['date']
                if key[8:10] == '31':
                    if aband_type.apply_payslip_pay_31:
                        self.write(cr, uid, holiday.id, {'apply_payslip_pay_31': True}, context=context)
                    continue

                if key not in lines:
                    add = {'name': work['date'], 'hours_assigned': 0, 'days_assigned': 0,
                           'hours_payslip': work['hours'], 'days_payslip': work['days'], 'week_day': work['week_day']}
                    lines[key] = add
                    l_lines.append(add)
                else:
                    lines[key]['hours_payslip'] += work['hours']
                    lines[key]['days_payslip'] += work['days']

            if aband_type.apply_publicholiday and holiday.working_hours_id.public_holidays_id:
                for festivo in holiday.working_hours_id.public_holidays_id.holiday_line_ids:
                    key = festivo.holiday_date
                    if key in lines:
                        lines[key]['hours_assigned'] = 0
                        lines[key]['days_assigned'] = 0

            if aband_type.apply_publicholiday_pay_days and holiday.working_hours_slip_id.public_holidays_id:
                for festivo in holiday.working_hours_slip_id.public_holidays_id.holiday_line_ids:
                    key = festivo.holiday_date
                    if key in lines:
                        lines[key]['hours_payslip'] = 0
                        lines[key]['days_payslip'] = 0

            if aband_type.apply_payslip_pay_31:
                for line in lines:
                    if line[-2:] == '31':
                        lines[line]['hours_payslip'] = 8
                        lines[line]['days_payslip'] = 1

            l_lines = [x for x in sorted(l_lines, key=itemgetter('name'))]

            if aband_type.disc_day_off:
                l_day = datetime.strptime(l_lines[-1]['name'], DSDF).date()
                l_kw_day = int(calendar.attendance_ids[-1].dayofweek)
                l_day = l_day + timedelta(days=abs(l_day.weekday() - l_kw_day))
                if len(set([x.dayofweek for x in calendar.attendance_ids])) == 5:
                    for x in range(1, 3):
                        name = l_day + timedelta(days=x)
                        add = {
                            'name': name,
                            'hours_assigned': calendar.hours_payslip,
                            'days_assigned': 1,
                            'hours_payslip': calendar.hours_payslip,
                            'days_payslip': 1,
                            'week_day': str(name.weekday())
                        }
                        l_lines.append(add)
                else:  # 6 days of week
                    name = l_day + timedelta(days=1)
                    add = {
                        'name': name,
                        'hours_assigned': calendar.hours_payslip,
                        'days_assigned': 1,
                        'hours_payslip': calendar.hours_payslip,
                        'days_payslip': 1,
                        'week_day': str(name.weekday())
                    }
                    l_lines.append(add)

            holiday_days_pool.unlink(cr, uid, [x.id for x in holiday.line_ids], context=context)

            sequence = 0
            if holiday.absence_id:
                seq_query = orm.fetchall(cr, "SELECT sequence FROM hr_holidays_days "
                                             "WHERE holiday_id = {h} "
                                             "ORDER BY sequence DESC LIMIT 1".format(h=holiday.absence_id.id))
                if seq_query:
                    sequence = int(seq_query[0][0])

            for vals in l_lines:
                sequence += 1
                vals.update({'holiday_id': holiday.id, 'sequence': sequence})
                holiday_days_pool.create(cr, uid, vals, context=context)
        return True


class hr_holidays_days(osv.osv):
    _name = "hr.holidays.days"
    _description = "Dias de Ausencia"

    def _last_state_change(self, cr, uid, ids, context=None):
        result = {}
        for assign in self.pool.get('hr.holidays').browse(cr, uid, ids, context=context):
            for line in assign.line_ids:
                result[line.id] = assign.state
        return result.keys()

    def _get_leave_days_from_status(self, cr, uid, ids, context=None):
        move = {}
        leave_days = []
        for r in self.pool.get('hr.holidays.status').browse(cr, uid, ids, context=context):
            leave_days += self.pool.get('hr.holidays.days').search(
                cr, uid, [('holiday_status_id', '=', r.id)], context=context)
        return leave_days

    def _apply_cut(self, cr, uid, ids, name, args, context=None):
        result = {}
        for day_leave in self.browse(cr, uid, ids, context=context):
            result[day_leave.id] = day_leave.holiday_status_id.apply_cut
        return result

    _columns = {
        'name': fields.date('Fecha'),
        'hours_assigned': fields.float('Horas de asignacion', digits_compute=dp.get_precision('Hours'), readonly=True),
        'hours_payslip': fields.float('Horas en nomina', digits_compute=dp.get_precision('Hours'), readonly=True),
        'days_assigned': fields.float('Dias de asignacion', digits_compute=dp.get_precision('Days'), readonly=True),
        'days_payslip': fields.float('Dias en nomina', digits_compute=dp.get_precision('Days'), readonly=True),
        'sequence': fields.float('#', digits_compute=dp.get_precision('Sequence'), readonly=True),
        'holiday_id': fields.many2one('hr.holidays', 'Ausencia', required=True, ondelete='cascade'),
        'payslip_id': fields.many2one('hr.payslip', 'Pagado en Nomina', readonly=True),
        'week_day': fields.selection([('0', 'Lunes'),
                                      ('1', 'Martes'),
                                      ('2', 'Miercoles'),
                                      ('3', 'Jueves'),
                                      ('4', 'Viernes'),
                                      ('5', 'Sabado'),
                                      ('6', 'Domingo'),
                                      ], 'Dia Semana', readonly=True),
        'state': fields.related('holiday_id', 'state', type='char', string='Estado', readonly=True,
                                store={'hr.holidays': (_last_state_change, ['state'], 10), }),
        'contract_id': fields.related('holiday_id', 'contract_id', type='many2one', relation="hr.contract",
                                      string='Contrato', readonly=True, store=True),
        'holiday_status_id': fields.related('holiday_id', 'holiday_status_id', type='many2one',
                                            relation="hr.holidays.status", string='Tipo', readonly=True, store=True),
        'apply_cut': fields.function(_apply_cut, string='Aplica en corte?', type="boolean",
                                     store={
                                         'hr.holidays.days': (lambda self, cr, uid, ids, c={}: ids, None, 50),
                                         'hr.holidays.status': (_get_leave_days_from_status, ['apply_cut'], 50),
                                     }),
    }


class hr_holidays_status(osv.osv):
    _inherit = "hr.holidays.status"

    _columns = {
        'partner_type': fields.selection(PARTNER_TYPE, 'Tipo de tercero'),
        'concept_category': fields.selection(CATEGORIES, 'Categoria de concepto', required=True),
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
        'ex_rent': fields.boolean('Exento de retencion'),
        'working_hours_id': fields.many2one('resource.calendar', 'Dias para Ausencia'),
        'force_working_hours': fields.boolean('Forzar horario para ausencia'),
        'working_hours_slip_id': fields.many2one('resource.calendar', 'Dias para Nomina'),
        'apply_publicholiday': fields.boolean('Aplica festivos'),
        'apply_publicholiday_pay_days': fields.boolean('Aplica Festivos en dias nomina'),
        'sub_wd': fields.boolean('Resta en dias Trabajados'),
        'no_payable': fields.boolean('No pagable en nomina'),
        'general_illness': fields.boolean('Enfermedad general'),
        'general_illness_ext': fields.boolean('Prorroga a incapacidad'),
        'maternal_lic': fields.boolean('Licencia de maternidad'),
        'paternal_lic': fields.boolean('Licencia de paternidad'),
        'gi_b2': fields.float('Porcentaje a reconocer por enfermedad de 1 y 2 dias'),
        'gi_b90': fields.float('Porcentaje a reconocer por enfermedad de 3 a 90 dias'),
        'gi_b180': fields.float('Porcentaje a reconocer por enfermedad de 91 a 180 dias'),
        'gi_a180': fields.float('Porcentaje a reconocer por enfermedad de 181 días en adelante'),
        'atep': fields.boolean('Incapacidad AT-EP'),
        'ibc': fields.boolean('Calcular con IBC', help="Marcar si debe calcularse la ausencia con el IBC, "
                                                       "no marcar si se calcula en base al salario"),
        'holiday_valid_date': fields.boolean('Asociar a nomina con fecha de validación'),
        'apply_payslip_pay_31': fields.boolean('Paga dia 31 en nomina'),
        'complete_pay': fields.boolean('Pago completo',
                                       help="Pagar por completo en una nomina sin importar el fin de la ausencia"),
        'apply_cut': fields.boolean('Aplica en corte (si), Aplica en Periodo(no)'),
        'vacaciones': fields.boolean('Vacaciones'),
        'code': fields.char("Codigo", size=32, required=True),
        'disc_day_off': fields.boolean("Descuento Día Descanso", help='Marcar este check cuando este tipo de ausencias '
                                                                      'debe descontar el día de descanso obligatorio'),
        'overlap': fields.boolean('Permitir sobrelapamiento de fechas'),
        'full_day': fields.boolean('Ausencia de dia completo'),
        }


class hr_holiday_public(osv.osv):
    '''
        This class stores a list of public holidays
    '''
    _name = 'hr.holiday.public'

    _description = 'Public holidays'

    _columns = {
        'name': fields.char('Holiday', size=128, required=True, help='Name of holiday list'),
        'holiday_line_ids': fields.one2many('hr.holiday.lines', 'holiday_id', 'Holidays'),
        'state': fields.selection([('draft', 'Draft'),
                                   ('confirmed', 'Confirmed'),
                                   ('validated', 'Validated'),
                                   ('refused', 'Refused'),
                                   ('cancelled', 'Cancelled'),
                                   ], 'State', select=True, readonly=True)
    }

    _defaults = {
        'state': 'draft',
    }

    def setstate_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'draft'}, context=context)
        return True

    def setstate_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'cancelled'}, context=context)
        return True

    def setstate_validate(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'validated'}, context=context)
        return True

    def setstate_refuse(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'refused'}, context=context)
        return True

    def setstate_confirm(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'confirmed'}, context=context)
        return True


class hr_holiday_lines(osv.osv):
    '''
       This model stores holiday lines
    '''
    _name = 'hr.holiday.lines'

    _description = 'Holiday Lines'

    _columns = {
        'holiday_date': fields.date('Date', help='Holiday date', required=True),
        'name': fields.char('Reason', size=128, help='Reason for holiday'),
        'day': fields.selection([('0', 'Lunes'),
                                 ('1', 'Martes'),
                                 ('2', 'Miercoles'),
                                 ('3', 'Jueves'),
                                 ('4', 'Viernes'),
                                 ('5', 'Sabado'),
                                 ('6', 'Domingo'),
                                 ], 'Dia Semana'),
        'holiday_id': fields.many2one('hr.holiday.public', 'Holiday List', help='Holiday list'),
        'state': fields.related('holiday_id', 'state', type="char", size=10, string="State")
    }

    _sql_constraints = [
        ('date_uniq', 'unique(holiday_date)',
         'There is already a Public Holiday defined for this date!'),
    ]

    def onchange_holiday_date(self, cr, uid, ids, holiday_date, context=None):
        if holiday_date:
            parsed_date = datetime.strptime(
                holiday_date, DSDF)
            day = parsed_date.weekday()
            return {'value': {'day': str(day)}}
        else:
            return {'value': {}}


class hr_holidays_allocation_rule(osv.osv):
    _name = "hr.holidays.allocation.rule"
    _description = "Allocation Rule Holiday"

    def _compute_total_months(self, cr, uid, ids, field, name, context=None):
        res = {}
        for rule in self.browse(cr, uid, ids, context=context):
            res[rule.id] = {'total_month_from': round(12 * rule.year_from, 2) + rule.month_from,
                            'total_month_to': round(12 * rule.year_to or 0, 2) + rule.month_to or 0}
        return res

    _columns = {
        'name': fields.char('Name', size=256, required=True),
        'year_from': fields.float('Year From'),
        'month_from': fields.integer('Month From'),
        'total_month_from': fields.function(_compute_total_months, string='Total Months From', type="float",
                                            multi="month"),
        'year_to': fields.float('Year To'),
        'month_to': fields.integer('Month To'),
        'total_month_to': fields.function(_compute_total_months, string='Total Months To', type="float", multi="month"),
        'no_of_leave': fields.float('No. Of Leaves.', required=True),
        'repeated_year': fields.boolean('Repeated Every Year'),
        'leave_type_id': fields.many2one('hr.holidays.status', 'Leave Type'),
        'allocation_type': fields.selection(
            [('leave', 'Leave Allocation'), ('notice', 'Notice Period'), ('severance', 'Severance')], 'Allocation Type',
            required=True)
    }

    _defaults = {
        'allocation_type': 'leave',
    }

    def compute_allocation_leave(self, cr, uid, date=False, context={}):
        # obtener contractos que cumplen un mes hoy
        if not date:
            date = datetime.now()
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context).company_id
        sql = ''' SELECT id 
                           FROM hr_contract 
                               WHERE company_id = {company_id} 
                               AND date_start < '{date}'::timestamp
                               AND extract(days from date_start) = extract(days from '{date}'::timestamp) 
                               AND extract(month from date_start) != extract(month from '{date}'::timestamp)
                               AND id IN (SELECT id 
    									FROM hr_contract 
    										WHERE company_id = {company_id}
    										AND (date_end >='{date}'::timestamp OR date_end is null)
    										AND type_id IN (SELECT id 
    													FROM hr_contract_type 
    														WHERE name NOT LIKE '%SENA%'))
                               AND id NOT in (SELECT contract_id 
                                               FROM hr_holidays 
                                                   WHERE allocation_rule_id IS NOT NULL 
                                                   AND substring(date_from::varchar,0,11) = '{date2}')'''.format(
            date=date, date2=str(date)[0:10], company_id=company_id.id)
        _logger.debug(sql)
        cr.execute(sql)
        contract_ids = cr.dictfetchall()
        date = date + timedelta(hours=5)
        if len(contract_ids) > 0:
            holiday_status_obj = self.pool.get('hr.holidays.status')
            contract_obj = self.pool.get("hr.contract")
            # obtener dias para asignacion
            cr.execute(
                ''' SELECT no_of_leave, leave_type_id, name, id, now()
                        FROM hr_holidays_allocation_rule 
                            WHERE leave_type_id IS NOT NULL LIMIT 1''')
            allocation_ids = cr.dictfetchall()
            if not allocation_ids:
                raise osv.except_osv(_('Error!'), _("Debe registrar al menos una regla de ausencias."))
            else:
                allocation_ids = allocation_ids[0]
            no_of_leave = allocation_ids.get('no_of_leave', None)
            leave_type_id = allocation_ids.get('leave_type_id', None)
            allocation_id = allocation_ids.get('id', None)
            holiday_status_obj.browse(cr, uid, leave_type_id, context=context)
            c = 0
            _logger.debug('date: {}'.format(date))
            for contract in contract_ids:
                c += 1
                _logger.debug('{uno} de {len}'.format(uno=c, len=len(contract_ids)))
                contracts = contract_obj.browse(cr, uid, contract.get('id', None), context)
                # holiday_id = holiday_obj.create(cr, uid, {'name': name,
                #                                           'holiday_type': 'employee',
                #                                           'type': 'add',
                #                                           'date_from': date,
                #                                           'date_to': date + timedelta(
                #                                               days=int(no_of_leave)),
                #                                           'employee_id': contracts.employee_id.id,
                #                                           'holiday_status_id': leave_type_id,
                #                                           'number_of_days_dummy': no_of_leave,
                #                                           'number_of_days_temp': no_of_leave,
                #                                           'allocation_rule_id': allocation_id}, context=context)
                cr.execute(''' INSERT INTO hr_holidays(create_date,write_uid,holiday_status_id,create_uid,employee_id,user_id,
                                                                    date_from,message_last_post,holiday_type,state,type,write_date,date_to,
                                                                    number_of_days,allocation_rule_id,contract_id,company_id,number_of_days_dummy,
                                                                    dummy,apply_cut,approve_date,apply_payslip_pay_31,number_of_days_temp) VALUES
                                                                    ('{date_from}',{user},{holiday_status_id},{user},{employee_id},{user},
                                                                    '{date_from}','{date_from}','employee','validate','add','{date_from}','{date_to}',
                                                                    {number_of_days},{allocation_rule_id},{contract_id},{company_id},{number_of_days},
                                                                    True,False,'{date_to}',False,{number_of_days}) RETURNING id'''.format(
                    date_from=date, date_to=date + timedelta(days=int(no_of_leave)), user=uid,
                    holiday_status_id=leave_type_id, employee_id=contracts.employee_id.id,
                    number_of_days=no_of_leave, allocation_rule_id=allocation_id,
                    contract_id=contracts.id, company_id=company_id.id))
                holiday_id = cr.fetchone()[0]

                # create workflow
                wkf_id = self.pool['ir.model.data'].get_object_reference(cr, uid, 'hr_holidays', 'wkf_holidays')[1]
                cr.execute(''' INSERT INTO wkf_instance (res_type,uid,wkf_id,state,res_id) 
                                    VALUES ('hr.holidays', {user}, {wkf_id}, 'active', {holiday_id}) RETURNING id'''.format(
                    user=uid,
                    holiday_id=holiday_id,
                    wkf_id=wkf_id))
                inst_id = cr.fetchone()[0]
                act_id = self.pool['ir.model.data'].get_object_reference(cr, uid, 'hr_holidays', 'act_validate')[1]
                cr.execute(''' INSERT INTO wkf_workitem (act_id,inst_id,state) 
                                    VALUES ({act_id}, {inst_id}, 'complete')'''.format(act_id=act_id,
                                                                                       inst_id=inst_id))
        return True


class resource_calendar_type(osv.osv):
    _name = "resource.calendar.type"

    _columns = {
        'name': fields.char('Nombre', size=128, required=True),
    }


class resource_calendar_attendance(osv.osv):
    _inherit = "resource.calendar.attendance"

    _columns = {
        'is_half_day': fields.boolean('Medio dia?'),
        'hours_payslip': fields.float('Horas para un dia', digits_compute=dp.get_precision('Hours'), ),
    }


class hr_contract(osv.osv):
    _inherit = "hr.contract"

    _columns = {
        'calendar_type': fields.related('working_hours', 'calendar_type', type='many2one',
                                        relation='resource.calendar.type', string='Tipo Horario', readonly=True),
    }


class resource_attendance(osv.osv):
    _inherit = "resource.calendar"

    _columns = {
        'tz': fields.selection(_tz_get, 'Timezone', size=64),
        'hours_payslip': fields.float('Horas para un dia', digits_compute=dp.get_precision('Hours'), ),
        'public_holidays_id': fields.many2one('hr.holiday.public', 'Festivos'),
        'calendar_type': fields.many2one('resource.calendar.type', 'Tipo Horario'),
    }

    def get_working_hours_payroll(self, cr, uid, schedule, date_from, date_to, context=None):
        res = []
        nb_of_days = (date_to - date_from).days + 1
        enfebrero = []
        ajuste = False
        for day in range(0, nb_of_days):
            dateinit = date_from + timedelta(days=day)
            if day > 0:
                hour_from = 0.0
            else:
                hour_from = float(dateinit.hour) + float(dateinit.minute) / 60.0

            if day + 1 != nb_of_days:
                hour_to = 24
            else:
                hour_to = float(date_to.hour) + float(date_to.minute) / 60.0

            day_of_week = dateinit.weekday()
            working_hours = 0
            for reg in schedule.attendance_ids:
                if int(reg.dayofweek) == day_of_week:
                    from_hour = hour_from
                    to_hour = hour_to
                    if from_hour < reg.hour_to:
                        if from_hour < reg.hour_from:
                            from_hour = reg.hour_from
                        if to_hour > reg.hour_to:
                            to_hour = reg.hour_to
                        working_hours += to_hour - from_hour

            if working_hours < 0:
                continue

            working_days = schedule.hours_payslip and working_hours / \
                           schedule.hours_payslip or 0
            date = dateinit.strftime(DSDF)
            res.append({'date': date, 'hours': working_hours,
                        'days': working_days, 'week_day': str(day_of_week)})

        return res

    def format_tz_date(self, cr, uid, calendar, date, date_format=False, context=None):
        '''
        Arguments:
        date_format: if there is date_format it means that the date is in string format, otherwise is an python date object
        '''
        if not calendar.tz:
            raise osv.except_osv(_('Error Configuracion!'), _(
                "El Horario '%s' no tiene una zona horaria configurada") % (calendar.name))
        ctx = context.copy()
        ctx.update({'tz': calendar.tz})

        if date_format:
            date = datetime.strptime(date, date_format)

        date = fields.datetime.context_timestamp(
            cr, uid, date, context=ctx)

        return date

    def monthdelta(d1, d2):
        delta = 0
        while True:
            mdays = monthrange(d1.year, d1.month)[1]
            d1 += timedelta(days=mdays)
            if d1 <= d2:
                delta += 1
            else:
                break
        return delta
#
