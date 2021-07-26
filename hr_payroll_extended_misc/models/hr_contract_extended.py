# -*- coding: utf-8 -*-
import logging

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError

# from openerp.tools.safe_eval import safe_eval as eval

_logger = logging.getLogger('HR CONTRACT EXTENDED')

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


# RETIROS MASIVOS
class hrDismissalMassive(models.Model):
    _name = 'dismissal.massive.wizard'

    payslip_period_id = fields.Many2one('payslip.period', string='Periodo Liquidacion', required=True,
                                        help='Este campo permite indicar el periodo en el cual se realizará la liquidación de los contratos seleccionados.')
    journal_id = fields.Many2one('account.journal', string='Diario de nómina', required=True,
                                 help='Seleccione el diario, si desea que creen las nóminas con este diario.')
    date_end = fields.Date(string='Fecha de finalización', required=False,
                           help='Este campo permite indicar le fecha de culminación de contrato, para los casos en el que todos tengan la misma fecha. Si no es marcado, debe indicar las fechas manualmente.')
    separation_type = fields.Selection(RETIROS, string='Tipo de Finalizacion',
                                       required=True,
                                       help='Este campo permite indicar el tipo de separación que se actualizará en los contratos seleccionados. Dependiente de este tipo se realizará al cálculo de la indemnización en la nómina tipo liquidación.')

    @api.multi
    def dismissal_massive(self):
        active_ids = self.env.context.get('active_ids', False)
        if active_ids:
            contract_ids = self.env['hr.contract'].browse(active_ids)
            tipo_liquidacion = self.env['hr.payslip.type'].search([('code', '=', "Liquidacion")])
            if not tipo_liquidacion:
                raise ValidationError('No hay un tipo de nomina con codigo Liquidacion')
            results = {
                'payslip_period': self.payslip_period_id.id,
                'name': 'Liquidacion de %s' % self.payslip_period_id.name,
                'date_liquidacion': self.payslip_period_id.end_date,
                'date': self.payslip_period_id.end_date,
                'journal_id': self.journal_id.id,
                'tipo_nomina': tipo_liquidacion.id}
            payslip_run_id = self.env['hr.payslip.run'].create(results)
            for contract in contract_ids:
                # actualizar contrato con datos de culminacion
                contract.write({'journal_id': self.journal_id.id, 'payslip_period_id': self.payslip_period_id.id,
                                'separation_type': self.separation_type})
                # crear nominas tipo liquidacion para cada contrato
                contract.create_payslip(payslip_run_id.id)
                # self.env['hr.payslip.run'].create({})
                # self.env.cr.execute(
                #     " UPDATE hr_contract SET journal_id=%s,write_uid=%s,write_date=now(),date_end='%s',payslip_period_id = %s, separation_type = '%s' WHERE id IN (%s)" % (
                #         self.journal_id.id, self.env.user.id, self.date_end, self.payslip_period_id.id,
                #         self.separation_type,
                #         ','.join(str(x) for x in active_ids)))

        else:
            raise ValidationError('Debe seleccionar al menos un contrato.')
        return True


class hrContractGroup(models.Model):
    _name = "hr.contract.group"

    name = fields.Char(string='Nombre de grupo', required=True,
                       help='Este campo debe contener el nombre de los grupos de contratos que se necesita para filtrar los empleados en el procesamiento de nómina.')


class hrContractExtended(models.Model):
    _inherit = "hr.contract"

    deductible_id = fields.One2many('hr.deductible', 'contract_id', string='Deducible')

    @api.onchange('job_id')
    def _change_job(self):
        if self.job_id.risk_id:
            self.riesgo = self.job_id.risk_id

    @api.model
    def create(self, vals):
        employee_id = vals.get('employee_id', False)
        vals['name'] = self._get_name(employee_id)
        # validar que no se pueda crear un contrato cuando ya se tiene uno activo
        self.env.cr.execute(
            ''' SELECT count(id) FROM hr_contract WHERE employee_id = {employee_id} AND (date_end IS NULL OR date_end > now())'''.format(
                employee_id=employee_id))
        datos = self.env.cr.fetchone()[0]
        _logger.info(datos)
        if datos > 0:
            raise ValidationError(
                'El empleado del contrato {employee_id} ya tiene un contrato activo.'.format(
                    employee_id=vals.get('name', False)))
        res = super(hrContractExtended, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        if vals.get('employee_id', False):
            vals['name'] = self._get_name(vals.get('employee_id', False))

        # validar que no se pueda crear un contrato cuando ya se tiene uno activo
        self.env.cr.execute(
            '''SELECT count(id) FROM hr_contract WHERE employee_id = {employee_id} AND (date_end IS NULL OR date_end > now())'''.format(
                employee_id=vals.get('employee_id', self.employee_id.id)))
        datos = self.env.cr.fetchone()[0]
        _logger.info(datos)
        if datos > 1:
            raise ValidationError(
                'El empleado del contrato {employee_id} ya tiene un contrato activo.'.format(
                    employee_id=vals.get('name', self.name)))
        return super(hrContractExtended, self).write(vals)

    @api.multi
    def _get_name(self, employee):
        name = '<NUEVO>'
        if employee and employee != self.employee_id.id:
            self.env.cr.execute(" SELECT COUNT(*) FROM hr_contract WHERE employee_id = %s " % employee)
            count = self.env.cr.fetchone()
            if count:
                count = count[0]
                self.env.cr.execute(" SELECT ref FROM res_partner WHERE employee_id = %s " % employee)
                ref = self.env.cr.fetchone()
                if ref:
                    ref = ref[0]
                    name = ref + ' - C' + str(int(count + 1)).rjust(2, '0')
        return name

    name = fields.Char(string='Nro.', default='<NUEVO>', readonly=True,
                       help='Este campo indica la referencia o nombre del contrato con el cual podrá ser identificado posteriormente.')
    group_id = fields.Many2one('hr.contract.group', string='Grupo de contrato',
                               help='Esta campo permite agrupar los contratos, según se va a calcular la nómina. Sirve para grupos que no sea por banco, centro de costo y/o ciudad de desempeño.')

    # @api.model
    # def update_a_vencer(self):
    #     self._update_a_vencer()

    # @api.multi
    # def _update_a_vencer(self):
    #     self.env.cr.execute(
    #         ''' UPDATE hr_contract SET a_vercer = extract(days from (date_end-now())) WHERE date_end>now() ''')
    #     return True

    @api.multi
    def create_payslip(self):
        payslip_type_obj = self.env['hr.payslip.type']
        payslip_obj = self.env['hr.payslip']
        tipo_liquidacion = payslip_type_obj.search([('code', '=', "Liquidacion")])
        res = None
        if not tipo_liquidacion:
            raise ValidationError('No hay un tipo de nomina con codigo Liquidacion')
        for contract in self:
            if not contract.separation_type:
                raise ValidationError('El "Tipo de Finalizacion" no es especificada en el contrato !')
            if not contract.date_end:
                raise ValidationError('La "Fecha de Finalizacion" de contrato no esta especificada !')
            if not contract.journal_id:
                raise ValidationError('El "Diario" de nomina no esta especificado !')
            if not contract.payslip_period_id:
                raise ValidationError('El Periodo no esta definido para la liquidacion !')

            total_income = 0.0
            last_salary = 0.0

            payslip_ids = payslip_obj.search([('contract_id', '=', contract.id), ('state', '=', 'done')],
                                             limit=24, order="date_from desc")
            for payslip in payslip_ids:  # payslip_obj.browse(payslip_ids):
                for line in payslip.line_ids:
                    if line.category_id and line.category_id.code and line.category_id.code.lower() == "neto":
                        total_income += line.total
                        if not last_salary:
                            last_salary = line.total
            notes = """Dia de inicio de Contrato            :- %s
    Dia final del contrato              :- %s
    Total(Ultimos 12 meses) :- %s
    Salario Mensual                       :- %s
    Salario diario                            :- %s
    Ultimo Salario                             :- %s""" % (
                contract.date_start, contract.date_end, total_income, round(total_income / 12, 2),
                round((total_income / 12) / 23.83, 2), last_salary)
            results = {
                'employee_id': contract.employee_id and contract.employee_id.id or False,
                'payslip_period_id': contract.payslip_period_id.id,
                'contract_id': contract.id,
                'name': _('Liquidacion de %s') % (contract.employee_id.name),
                'note': notes,
                'contract_create': True,
                'liquidacion_date': self.payslip_period_id.end_date,
                'journal_id': contract.journal_id.id,
                'tipo_nomina': tipo_liquidacion.id,
            }
            _logger.info('------------------------')
            _logger.info(results)
            res_id = payslip_obj.create(results)
            res_id.compute_slip()
            contract.state = 'done'
            contract.pending_vac = 0
        return {
            'name': _("Pay Slips"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'hr.payslip',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'res_id': res_id.id,
            'target': 'current',
            'context': self.env.context,
        }


class HrHolidays(models.Model):
    _inherit = 'hr.holidays'

    group_id = fields.Many2one('hr.contract.group', string='Grupo de contrato')


class HrPayrollNovedades(models.Model):
    _inherit = 'hr.payroll.novedades'

    group_id = fields.Many2one('hr.contract.group', string='Grupo de contrato')


class HRPayslipEmployeesExtended(models.TransientModel):
    _inherit = 'hr.payslip.employees'

    @api.multi
    def _default_get(self):
        res = [('id', 'in', '[]')]
        if 'active_id' in self._context and self._context['active_id']:
            payslip_run_id = self.env['hr.payslip.run'].browse(self._context.get('active_id', False))

            if not payslip_run_id.date_liquidacion:
                raise ValidationError('Debe indicar la fecha de liquidación.')

            if not payslip_run_id.date:
                raise ValidationError('Debe indicar la fecha de contabilización.')

            if not payslip_run_id.tipo_nomina:
                raise ValidationError('Debe indicar el tipo de nómina.')

            bank_id = payslip_run_id.bank_id.id or None
            analytic_account_id = payslip_run_id.analytic_account_id.id or None
            cuidad_desempeno = payslip_run_id.city_id.id or None

            group_id = payslip_run_id.group_id.id
            schedule_pay = payslip_run_id.payslip_period.schedule_pay or None
            if payslip_run_id.tipo_nomina.name in ('liquidacion', 'Vacaciones', 'Vacaciones Dinero'):
                schedule_pay = None

            # condición para solo contrados en estado terminado
            where = " AND hc.state='in_progress'"

            # contractos agregados anteriormente al procesamiento
            if payslip_run_id.slip_ids:
                where += ' AND hc.id not in (%s)' % (','.join(str(slip.contract_id.id) for slip in payslip_run_id.slip_ids))

            # agregar condicion de inicio y culminacion de contrato
            where += " AND (hc.date_end is NULL OR (hc.date_end >= '{start_period}' AND hc.date_start <= '{end_period}'))".format(
                start_period=payslip_run_id.payslip_period.start_period,
                end_period=payslip_run_id.payslip_period.end_period)

            # contratos de la compañia actual
            where += ' AND hc.company_id = {company_id} '.format(company_id=self.env.user.company_id.id)

            # filtro por banco
            if bank_id:
                where += " AND rpb.bank = {bank_id} "

            # filtro por cuenta analitica
            if analytic_account_id:
                where += " AND hc.analytic_account_id = {analytic_account_id} "

            # filtro por ciudad de desempeño
            if cuidad_desempeno:
                where += " AND hc.cuidad_desempeno = {cuidad_desempeno} "

            # filtro por periodicidad de pago
            if schedule_pay:
                where += " AND hc.schedule_pay = '{schedule_pay}' "

            # filtro por grupo
            if group_id:
                where += " AND hc.group_id = {group_id} "
            # agregar contratos de colaboradores con ausencias en el periodo relacionada con la ausencia de la nómina
            if payslip_run_id.tipo_nomina.holiday_status_id:
                where_leave = ' '
                if payslip_run_id.tipo_nomina.holiday_status_id.apply_cut == True:
                    # agregar condicion de inicio y culminacion de contrato
                    where_leave += " AND approve_date BETWEEN '{date_from}' AND '{date_to}' AND (date_from >= '{date_from}' AND date_from <= '{date_to}')".format(
                        date_from=payslip_run_id.payslip_period.start_date,
                        date_to=payslip_run_id.payslip_period.start_date)
                else:
                    where_leave += " AND approve_date BETWEEN '{start_period}' AND '{end_period}' AND (date_from >= '{start_period}' AND date_from <= '{end_period}')".format(
                        start_period=payslip_run_id.payslip_period.start_date,
                        end_period=payslip_run_id.payslip_period.end_period)
                where_leave += " AND state = 'validate' AND type = 'remove' AND holiday_status_id = {holiday_status_id} AND company_id = {company_id} ".format(
                    holiday_status_id=payslip_run_id.tipo_nomina.holiday_status_id.id,
                    company_id=self.env.user.company_id.id)
                # agregar contratos con ausencias asociada al tipo de nómina
                where += " AND hc.id IN (SELECT contract_id FROM hr_holidays WHERE 1=1 {where_leave})".format(
                    where_leave=where_leave)
                _logger.info(where_leave)

            # sustituir filtros en where
            where = where.format(
                analytic_account_id=analytic_account_id,
                cuidad_desempeno=cuidad_desempeno,
                bank_id=bank_id,
                group_id=group_id,
                schedule_pay=schedule_pay)

            ids = False
            # obtener ids de contratos
            sql = ''' SELECT hc.id FROM hr_contract hc
                        INNER JOIN hr_employee he ON he.id = hc.employee_id
                        LEFT JOIN res_partner_bank rpb ON rpb.id = he.bank_account_id
                        WHERE 1=1 
                        {where} '''.format(where=where)
            self.env.cr.execute(sql)
            res = [('id', 'in', [x[0] for x in self.env.cr.fetchall()])]
        return res

    contract_ids = fields.Many2many('hr.contract', 'hr_contract_group_rel', 'payslip_id', 'contract_id', 'Contratos',
                                    domain=_default_get)


class HRFamiliarExtendedDependientes(models.Model):
    _inherit = 'hr.familiar'

    depends = fields.Boolean(string='¿Dependiente?', default=True, help='Permite indicar que esta persona es un dependiente del colaborador.')
    handicapped = fields.Boolean(string='¿Discapacitado?', default=True, help='Permite indicar que esta persona es discapacitada.')


class HRTypeDeductible(models.Model):
    _name = 'hr.type.deductible'

    code = fields.Char(string='Código', required=True, help='Este código es usado en las reglas salariales, para identificar el tipo de deducible.')
    name = fields.Char(string='Nombre', required=True, help='Permite identificar el tipo de deducible para los usuarios de nómina.')
    tope_uvt = fields.Float(string='Tope (UVT)',required=True, defualt=0.0)
    tope_amount = fields.Float(string='Tope (Monto)', required=True, defualt=0.0)

class HRDeductible(models.Model):
    _name = 'hr.deductible'

    type = fields.Many2one('hr.type.deductible', string='Tipo', required=True, help='Permite identificar el tipo de deducibles, para el cálculo en las reglas salariales de retención en la fuente.')
    amount = fields.Float(string='Monto (Mensual)', required=True, help='Permite indicar el monto que sera usado en las reglas salariales para calcular la retención en la fuente.')
    contract_id = fields.Many2one('hr.contract', string='Deducibles', help='Es la relación de los deducible con los contratos.')
