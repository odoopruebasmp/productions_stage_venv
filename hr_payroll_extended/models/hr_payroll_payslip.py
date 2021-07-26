# -*- coding: utf-8 -*-
from openerp import models, fields, api, modules
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp.addons.avancys_orm import avancys_orm
from calendar import monthrange
from openerp.exceptions import Warning
from .hr_payroll_concept import days360


CONTRACT_SECTION = [('administrativa', 'Administrativa'),
                    ('comercial', 'Comercial'),
                    ('operativa', 'Operativa')]

CONTRACT_TERM = [('fijo', 'Fijo'), ('indefinido', 'Indefinido'), ('obralabor', 'Obra Labor')]

CONTRACT_CLASS = [('reg', 'Regular'), ('apr', 'Aprendiz'), ('int', 'Integral')]


def get_ids(data):
    if len(data) > 1:
        ids = tuple(data)
    elif len(data) == 1:
        ids = (data[0], 0)
    else:
        ids = (0, False)
    return ids


class HrSalaryRule(models.Model):
    _name = "hr.salary.rule"
    _inherit = ['hr.salary.rule', 'mail.thread']

    amount_python_compute = fields.Text(
        'Python Code', track_visibility='onchange')


class HrEmployeeJobLog(models.Model):
    _name = 'hr.employee.job.log'

    prev_job = fields.Many2one('hr.job', 'Cargo previo')
    new_job = fields.Many2one('hr.job', 'Cargo nuevo')
    date = fields.Date('Fecha de cambio')
    employee_id = fields.Many2one('hr.employee', 'Empleado')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    job_log = fields.One2many('hr.employee.job.log', 'employee_id', string='Cambio de cargos')

    @api.multi
    def write(self, vals):
        for employee in self:
            if vals.get('job_id', False):
                log = {
                    'new_job': vals.get('job_id'),
                    'date': datetime.strftime(datetime.now(), '%Y-%m-%d'),
                    'employee_id': employee.id,
                    'prev_job': employee.job_id.id,
                }
                avancys_orm.direct_create(self._cr, self._uid, 'hr_employee_job_log', [log])
        return super(HrEmployee, self).write(vals)


class HrContractRtfLog(models.Model):
    _name = 'hr.contract.rtf.log'

    name = fields.Char('Descripcion')
    value = fields.Char('Detalle')
    contract_id = fields.Many2one('hr.contract', 'Contrato')


class HrContractAnalyticLog(models.Model):
    _name = 'hr.contract.analytic.log'

    analytic_account_id = fields.Many2one('account.analytic.account', 'Nuevo Centro de Costo')
    date = fields.Date('Fecha de cambio')
    contract_id = fields.Many2one('hr.contract', 'Contrato')
    prev_analytic_id = fields.Many2one('account.analytic.account', 'Previo Centro de Costo')


class HrContractExtension(models.Model):
    _name = 'hr.contract.extension'
    _order = 'sequence'

    contract_id = fields.Many2one('hr.contract', 'Contrato')
    sequence = fields.Integer('Numero de prorroga')
    date_from = fields.Date('Fecha inicio prorroga')
    date_to = fields.Date('Fecha fin prorroga')


class HrContract(models.Model):
    _inherit = 'hr.contract'

    state = fields.Selection([('in_progress', 'Progreso'), ('done', 'Terminado')],
                             default="in_progress", string='Estado')
    ded_dependents = fields.Boolean('Dependientes')
    ded_living = fields.Float('Deduccion por intereses vivienda')
    ded_prepaid = fields.Float('Deduccion por medicina prepagada')
    pending_vac = fields.Float('Dias pendientes de vacaciones')
    vac_book = fields.One2many('hr.vacation.book', 'contract_id', string="Libro de vacaciones")
    fix_end = fields.Date('Fecha finalizacion')
    smmlv = fields.Boolean('Devenga salario minimo')
    apr_prod_date = fields.Date('Fecha de cambio a etapa productiva',
                                help="Marcar unicamente cuando el aprendiz pase a etapa productiva")
    ded_limit = fields.Boolean('Limitar deducciones al 50% de los devengos')
    rtf_log = fields.One2many('hr.contract.rtf.log', 'contract_id', string="Calculo tarifa RTFP2")
    analytic_log = fields.One2many('hr.contract.analytic.log', 'contract_id', string="Cambios de centro de costo")
    deadline = fields.Integer('Dias para vencimiento', compute="get_deadline")
    extension_ids = fields.One2many('hr.contract.extension', 'contract_id', string="Prorrogas")
    term = fields.Selection(CONTRACT_TERM, 'Termino', related="type_id.term", store=True)
    part_time = fields.Boolean('Tiempo parcial')
    high_risk = fields.Boolean('Alto riesgo', help="Decreto 2090 de 2003")

    @api.multi
    def extend_contract(self):
        for k in self:
            if k.extension_ids:
                last = k.extension_ids.sorted(key=lambda r: r.sequence)[-1]
                k.fix_end = last.date_to
                if last.sequence > 3:
                    to_ext = days360(last.date_from, last.date_to)
                    if to_ext < 360:
                        raise Warning("No es posible realizar una prorroga por un periodo "
                                      "inferior a un año despues de tener 3 o más prorrogas")
            else:
                raise Warning("Para prorrogar el contrato se requiere que se registre la prorroga en el contrato")

    @api.depends('fix_end')
    def get_deadline(self):
        now = datetime.strftime(datetime.now(), "%Y-%m-%d")
        for k in self:
            k.deadline = days360(now, k.fix_end) if k.fix_end and not k.date_end else 0

    @api.multi
    def write(self, vals):
        for contract in self:
            if vals.get('analytic_account_id', False):
                log = {
                    'analytic_account_id': vals.get('analytic_account_id'),
                    'date': datetime.strftime(datetime.now(), '%Y-%m-%d'),
                    'contract_id': contract.id,
                    'prev_analytic_id': contract.analytic_account_id.id,
                }
                avancys_orm.direct_create(self._cr, self._uid, 'hr_contract_analytic_log', [log])
            if vals.get('fix_end', False):
                if contract.extension_ids:
                    last = contract.extension_ids.sorted(key=lambda r: r.sequence)[-1]
                    vals['fix_end'] = last.date_to
                    if len(contract.extension_ids) > 3:
                        to_ext = days360(last.date_from, last.date_to)
                        if to_ext < 360:
                            raise Warning("No es posible realizar una prorroga por un periodo "
                                          "inferior a un año despues de tener 3 o más prorrogas")
        return super(HrContract, self).write(vals)

    @api.model  # TODO remove after two months and set state to default='in_progress'
    def act_state(self):
        self.env.cr.execute("UPDATE hr_contract SET state='in_progress' WHERE separation_type is Null")
        self.env.cr.execute("UPDATE hr_contract SET state='done' WHERE separation_type is not Null")

    @api.one
    @api.onchange('date_end', 'contract_days', 'date_start')
    def _compute_contract_days(self):
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

        if self._context['field_onchange'] == 'contract_days':
            if self.contract_days > 0:
                months = int(self.contract_days / 30)
                days = self.contract_days - (30 * months)
                start = datetime.strptime(self.date_start, '%Y-%m-%d')
                date_end = start + relativedelta(months=months) + relativedelta(days=days)
                self.date_end = date_end
            else:
                self.date_end = False

        elif self._context['field_onchange'] == 'date_start':
            self.date_end, self.contract_days = False, False

        else:
            if self.date_end:
                month = monthdelta(datetime.strptime(self.date_start, '%Y-%m-%d'),
                                   datetime.strptime(self.date_end, '%Y-%m-%d'))
                end = int(self.date_end[8:10])
                start = int(self.date_start[8:10])
                if start > end:
                    days = (30 - int(start) + int(end))
                else:
                    days = int(end) - int(start)
                self.contract_days = 0
                self.contract_days = month * 30 + days
            else:
                self.contract_days = 0

    @api.model  # TODO remove after two months and set state to default='in_progress'
    def act_state(self):
        dt_now = str(datetime.now())[:10]
        self.env.cr.execute("UPDATE hr_contract SET state='in_progress' WHERE date_end is Null or date_end >= '%s' "
                            "AND state != 'done'" % dt_now)
        self.env.cr.execute("UPDATE hr_contract SET state='done' WHERE date_end < '%s'" % dt_now)

    @api.multi
    def compute_rtf2(self):
        hp = self.env['hr.payslip']
        log_data = []
        # noinspection PyTypeChecker
        for k in self:
            self._cr.execute("DELETE FROM hr_contract_rtf_log where contract_id = {k}".format(k=k.id))
            log = []
            # Definir fechas
            date = datetime.now().date()
            seg = 1 if date.month < 6 or date.month == 12 else 2
            if seg == 1:
                year = date.year - 1 if date.month == 12 else date.year - 2
                ref_date_from = str(year) + '-12-01'
                if k.date_start > ref_date_from:
                    ref_date_from = k.date_start
                ref_date_to = str(year + 1) + '-11-30'
            else:
                year = date.year - 1
                ref_date_from = str(year) + '-06-01'
                if k.date_start > ref_date_from:
                    ref_date_from = k.date_start
                ref_date_to = str(year + 1) + '-05-31'

            log += [('FECHA INICIO', ref_date_from)]
            log += [('FECHA FIN', ref_date_to)]

            uvt = self.env['variables.economicas'].getValue('UVT', ref_date_to) or 0.0
            log += [('VALOR UVT', uvt)]

            days = days360(ref_date_from, ref_date_to)
            log += [('DIAS INTERVALO', days)]

            earn_itv = hp.get_interval_category('earnings', ref_date_from, ref_date_to, contract=k.id)
            o_earn_itv = hp.get_interval_category('o_earnings', ref_date_from, ref_date_to, contract=k.id)
            o_sal_itv = hp.get_interval_category('o_salarial_earnings', ref_date_from, ref_date_to, contract=k.id)
            comp_itv = hp.get_interval_category('comp_earnings', ref_date_from, ref_date_to, contract=k.id)
            o_rights_itv = hp.get_interval_category('o_rights', ref_date_from, ref_date_to, contract=k.id)
            nt_earn_itv = hp.get_interval_category('non_taxed_earnings', ref_date_from, ref_date_to, contract=k.id)

            earn = sum([x[1] for x in earn_itv])
            o_earn = sum([x[1] for x in o_earn_itv])
            o_sal = sum([x[1] for x in o_sal_itv])
            comp = sum([x[1] for x in comp_itv])
            o_rigths = sum([x[1] for x in o_rights_itv])
            nt_earn = sum([x[1] for x in nt_earn_itv])

            log += [('1.DEVENGOS', earn)]
            log += [('2.OTROS DEVENGOS', o_earn)]
            log += [('3.OTROS INGRESOS SALARIALES', o_sal)]
            log += [('4.INGRESOS COMPLEMENTARIOS', comp)]
            log += [('5.OTROS DERECHOS', o_rigths)]
            log += [('6.INGRESOS NO GRAVADOS', nt_earn)]

            taxed_inc = earn + o_earn + o_sal + comp + o_rigths + nt_earn
            log += [('7.INGRESOS TOTALES [1+2+3+4+5+6]', taxed_inc)]

            payslips_q = ("SELECT hp.id FROM hr_payslip hp "
                          "INNER JOIN payslip_period pp ON pp.id = hp.payslip_period_id "
                          "WHERE pp.start_period BETWEEN '{sd}' AND '{ed}' "
                          "AND hp.contract_id = {k} ".format(sd=ref_date_from, ed=ref_date_to, k=k.id))
            payslips_ids = avancys_orm.fetchall(self._cr, payslips_q)
            log += [('NOMINAS EN PERIODO', len(payslips_ids))]

            payslips = hp.browse([x[0] for x in payslips_ids]) if payslips_ids else []

            tax_cat_ls = ['earnings', 'o_earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights']
            untaxed_inc = 0  # Ingresos no gravados
            ing_no_const = 0  # Ingresos no constitutivos de renta
            vol_cont = 0  # Aportes voluntarios de pension y afc
            ap_vol = 0
            afc = 0

            for p in payslips:
                for c in p.concept_ids:
                    is_ded = True if c.category == 'deductions' else False
                    is_reg = True if c.origin == 'regular' else False
                    is_ex = True if c.ex_rent else False
                    is_afc = True if c.afc else False
                    if is_ded and is_reg and c.code != 'RTEFTE':
                        ing_no_const += c.total
                    if is_ded and is_ex:
                        ap_vol += c.total
                        vol_cont += c.total
                    if is_ded and is_afc:
                        afc += c.total
                        vol_cont += c.total
                    if c.category in tax_cat_ls and is_ex:
                        untaxed_inc += c.total

            log += [('8.INGRESOS EXENTOS', untaxed_inc)]
            log += [('9.INGRESOS NO CONSTITUTIVOS DE RENTA', ing_no_const)]
            log += [('10.APORTES VOLUNTARIOS PENSION', ap_vol)]
            log += [('11.AFC', afc)]

            net_income = taxed_inc - ing_no_const
            log += [('12.INGRESOS NETOS [7-9]', net_income)]

            dep_base = taxed_inc * 0.1
            if k.ded_dependents:
                ded_depend = dep_base if dep_base <= 32 * uvt else 32 * uvt
                ded_depend = ded_depend
            else:
                ded_depend = 0
            log += [('13.DEDUCCION DEPENDIENTES', ded_depend)]

            # Medicina prepagada
            base_mp = k.ded_prepaid
            ded_mp = base_mp if base_mp <= 16 * uvt else 16 * uvt
            ded_mp = ded_mp

            log += [('14.DEDUCCION MEDICINA PREPAGADA', ded_mp)]

            # Deducion por vivienda
            base_liv = k.ded_living
            ded_liv = base_liv if base_liv <= 100 * uvt else 100 * uvt
            ded_liv = ded_liv
            log += [('15.DEDUCCION POR INT DE VIVIENDA', ded_liv)]

            total_deduct = ded_depend + ded_mp + ded_liv
            log += [('16.TOTAL DEDUCIBLES [13+14+15]', total_deduct)]

            # Aportes voluntarios
            vol_cont = vol_cont if vol_cont <= net_income * 0.3 else net_income * 0.3
            log += [('17.TOTAL DEDUCIBLES VOLUNTARIOS', vol_cont)]

            # Top25 deducible por ley de los ingresos - deducciones existentes
            base25 = (net_income - total_deduct - vol_cont) * 0.25
            top25 = base25 if base25 <= 240 * uvt else 240 * uvt
            log += [('18.TOP 25% [(12-16-17)*25% o 240 UVT]', top25)]

            # Top40
            base40 = net_income * 0.4
            baserex = total_deduct + vol_cont + top25
            rent_ex = baserex if baserex <= base40 else base40
            log += [('19.RENTA EXENTA [16+17+18 o 12x40%]', rent_ex)]

            brtf = net_income - rent_ex
            log += [('20.BASE RETENCION GLOBAL [12-19]', brtf)]
            if days == 360:
                factor = 13
            else:
                factor = days / 30
            log += [('21.FACTOR MES [13:360, days/30]', factor)]

            brtf_month = brtf / factor if factor else 0
            log += [('22.BASE RTF MES [20/21]', brtf_month)]

            b_uvt = brtf_month / uvt if uvt else 0
            log += [('23.BASE UVT [22/UVT]', b_uvt)]

            rate = 0
            adj = 0
            step = 0
            if 87 < b_uvt <= 145:
                rate = 19
                step = 87
            elif 145 < b_uvt <= 335:
                rate = 28
                adj = 11
                step = 145
            elif 335 < b_uvt <= 640:
                rate = 33
                adj = 64
                step = 335
            elif 640 < b_uvt <= 945:
                rate = 35
                adj = 165
                step = 640
            elif 945 < b_uvt <= 2300:
                rate = 37
                adj = 272
                step = 945
            elif b_uvt > 2300:
                rate = 39
                adj = 773
                step = 2300

            conv = ((b_uvt - step) * rate / 100) + adj
            log += [('24.UVT APLICACION TABLA', conv)]
            rtf = conv * uvt
            log += [('25.RETENCION APLICACION [24xUVT]', rtf)]
            if b_uvt and uvt:
                rate_p2 = rtf * 100 / b_uvt / uvt
            else:
                rate_p2 = 0
            k.rtf_rate = rate_p2
            avancys_orm.direct_update(self._cr, 'hr_contract', {'rtf_rate': rate_p2}, ('id', k.id))
            log += [('26.PORCENTAJE CALCULADO [25/23/UVT]', rate_p2)]

            for line in log:
                log_data.append({
                    'name': line[0],
                    'value': line[1],
                    'contract_id': k.id
                })
        avancys_orm.direct_create(self._cr, self._uid, 'hr_contract_rtf_log', log_data, progress=True)
        return

    @api.multi
    def contract_return(self):
        slip = self.env['hr.payslip'].search([('contract_id', '=', self.id), ('tipo_nomina.code', 'ilike', '%iquidac%'),
                                              ('payslip_period_id', '=', self.payslip_period_id.id)])
        if len(slip) > 1:
            raise Warning("Existe mas de una nómina de tipo liquidación para este contrato en el periodo de "
                          "liquidación. Por favor validar.")
        if slip.state != 'draft':
            raise Warning(u"No es posible reintegrar el contrato hasta que la nómina de liquidación asociada, %s, se "
                          "encuentre en estado borrador. Por favor validar." % slip.number)
        self._cr.execute("DELETE from hr_payslip where id = {id}".format(id=slip.id))
        self.write({
            'state': 'in_progress',
            'date_end': None,
            'payslip_period_id': None,
            'separation_type': None
            })

    @api.multi
    def get_sus_per(self):
        vac_book_q = ("SELECT vb.enjoyed, vb.payed, vb.licences "
                      "FROM hr_vacation_book vb "
                      "INNER JOIN hr_contract hc ON hc.id = vb.contract_id "
                      "WHERE hc.id = {c}".format(c=self.id))
        data = avancys_orm.fetchall(self._cr, vac_book_q)
        lic = 0
        for x in data:
            lic += x[2] or 0
        return lic

    @api.multi
    def get_pend_vac(self, context=None, date_calc=False, sus=0):
        if date_calc:
            # noinspection PyTypeChecker
            date_calc = datetime.strptime(date_calc, "%Y-%m-%d")
        else:
            date_calc = datetime.now()
        vac_book_q = ("SELECT vb.enjoyed, vb.payed, vb.licences "
                      "FROM hr_vacation_book vb "
                      "INNER JOIN hr_contract hc ON hc.id = vb.contract_id "
                      "WHERE hc.id = {c}".format(c=self.id))
        data = avancys_orm.fetchall(self._cr, vac_book_q)
        lic = sus
        taken = 0
        for x in data:
            lic += x[2] or 0
            taken += (x[0] or 0) + (x[1] or 0)
        k_dt_start = self.date_start
        dt_end = datetime.strftime(date_calc, '%Y-%m-%d')
        days = days360(k_dt_start, dt_end)
        days_wo_lic = days - lic
        if not self.high_risk:
            dv_total = float(days_wo_lic) * 15 / 360
        else:
            dv_total = float(days_wo_lic) * 30 / 360
        dv_pend = dv_total - taken

        # self.pending_vac = dv_pend
        return dv_pend

    @api.multi
    def get_pend_vac_upd(self, context=None, date_calc=False, sus=0):
        for k in self:
            if k.state != 'in_progress':
                raise Warning("No es posible realizar esta accion con un contrato finalizado")
            if k.type_id.type_class == 'apr':
                raise Warning("Los contratos de aprendiz no cuentan con esta funcionalidad")
            dv_pend = k.get_pend_vac(context=context, date_calc=date_calc, sus=sus)
            k.pending_vac = dv_pend



class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    @api.onchange('payslip_period')
    def act_dates(self):
        self.date_start, self.date_end = self.payslip_period.start_period, self.payslip_period.end_period

    @api.multi
    def generate_payslips(self):
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'hr.payslip.employees',
        }

    @api.multi
    def close_run(self):
        self._cr.execute("SELECT id from hr_payslip where payslip_run_id = {id} and state in ('draft')".format(
            id=self.id))
        slips2comp = self.env['hr.payslip'].browse(x[0] for x in self._cr.fetchall())
        slips2comp.close_slip()
        # noinspection PyAttributeOutsideInit
        self.state = 'close'
        return True

    @api.multi
    def draft_run(self):
        self.slip_ids.draft_slip()
        # noinspection PyAttributeOutsideInit
        self.state = 'draft'

    @api.multi
    def reckon_run(self):
        self._cr.execute("SELECT id from hr_payslip where payslip_run_id = {id} and state in ('draft')".format(
            id=self.id))
        slips2comp = self.env['hr.payslip'].browse(x[0] for x in self._cr.fetchall())
        slips2comp.compute_slip()
        avancys_orm.direct_update(self._cr, 'hr_payslip',
                                  {'payslip_run_id': self.id}, ('id', [x.id for x in slips2comp]))


class HrPayslipEmployees(models.Model):
    _inherit = 'hr.payslip.employees'

    @api.multi
    def reckon_employee_run(self):
        run = self.env['hr.payslip.run'].browse(self.env.context['active_id'])
        slip_ids = []

        # Iteracion en contratos del wizard
        for contract in self.contract_ids:

            if not run.tipo_nomina:
                raise Warning("Tiene que selecionar el tipo de nomina.")


            slip_ids.append({
                'employee_id': contract.employee_id.id,
                'name': "Nomina de " + contract.name,
                'struct_id': False,
                'contract_id': contract.id,
                'payslip_run_id': run.id,
                'date_from': run.payslip_period.start_date,
                'date_to': run.payslip_period.end_date,
                'start_period': run.payslip_period.start_period,
                'end_period': run.payslip_period.end_period,
                'liquid_date': run.date,
                'liquidacion_date': run.date_liquidacion,
                'credit_note': run.credit_note,
                'payslip_period_id': run.payslip_period.id,
                'journal_id': run.journal_id.id,
                'state': 'draft',
                'tipo_nomina': run.tipo_nomina.id,
            })
        orm_fetch = avancys_orm.direct_create(self._cr, self._uid, 'hr_payslip', slip_ids, company=True, progress=True)
        created_slips = self.env['hr.payslip'].browse(x[0] for x in orm_fetch)
        created_slips.compute_slip()

        return True


class HrHolidays(models.Model):
    _inherit = "hr.holidays"

    @api.onchange('holiday_status_id')
    def onchange_holiday_status_id(self):
        if self.holiday_status_id.vacaciones:
            self.vacaciones = True
        else:
            self.vacaciones = False
        if self.holiday_status_id.general_illness:
            self.general_illness = True
        else:
            self.general_illness = False
        if self.holiday_status_id.general_illness_ext:
            self.general_illness_ext = True
        else:
            self.general_illness_ext = False


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    bank_id = fields.Many2one('res.bank', 'Banco')


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.multi
    def reckon_rules(self):
        self.compute_sheet()

    @api.multi
    def reckon_extrahours(self):

        self._cr.execute("DELETE from hr_payslip_extrahours where payslip_id = {payslip}".format(payslip=self.id))
        extras = {}
        if self.tipo_nomina.code in ('Nomina', 'Vacaciones', 'Liquidacion'):
            for extra in self.extrahours_ids:
                if extra.type_id.name in extras:
                    extras[extra.type_id.name]['cantidad'] += round(extra.duracion, 2)
                    extras[extra.type_id.name]['total'] += extra.total
                    extras[extra.type_id.name]['valor'] = extras[extra.type_id.name]['total']/extras[extra.type_id.name]['cantidad']
                else:
                    extras[extra.type_id.name] = {
                        'type_id': extra.type_id.id,
                        'valor': extra.total/extra.duracion,
                        'cantidad': extra.duracion,
                        'total': extra.total,
                        'payslip_id': self.id,
                    }
        valores = [value for key, value in extras.items()]
        avancys_orm.direct_create(self._cr, self._uid, 'hr_payslip_extrahours', valores)
        return True

    @api.multi
    def reckon_novedades(self):

        self._cr.execute("DELETE FROM hr_payslip_novedades WHERE payslip_id = {payslip}".format(payslip=self.id))
        novedades = {}
        if self.tipo_nomina.code in ('Nomina', 'Vacaciones', 'Liquidacion', 'Vacaciones Dinero'):
            for novedad in self.novedades_ids:
                if novedad.category_id.name in novedades:
                    novedades[novedad.category_id.name]['cantidad'] += novedad.cantidad
                    novedades[novedad.category_id.name]['total'] += novedad.total
                else:
                    novedades[novedad.category_id.name] = {
                        'category_id': novedad.category_id.id,
                        'cantidad': novedad.cantidad,
                        'total': novedad.total,
                        'payslip_id': self.id,
                    }
        valores = [value for key, value in novedades.items()]
        avancys_orm.direct_create(self._cr, self._uid, 'hr_payslip_novedades', valores)
        return True

    @api.multi
    def reckon_loans(self):

        self._cr.execute("DELETE FROM hr_payslip_prestamo_cuota WHERE payslip_id = {payslip}".format(payslip=self.id))
        prestamos = {}
        if self.tipo_nomina.code in ('Nomina', 'Vacaciones', 'Liquidacion'):
            for prestamo in self.prestamos_ids:
                if prestamo.category_id.name in prestamos:
                    prestamos[prestamo.category_id.name]['deuda'] += prestamo.deuda
                    prestamos[prestamo.category_id.name]['cuota'] += prestamo.cuota
                else:
                    prestamos[prestamo.category_id.name] = {
                        'category_id': prestamo.category_id.id,
                        'deuda': prestamo.deuda,
                        'cuota': prestamo.cuota,
                        'payslip_id': self.id,
                    }
            valores = [value for key, value in prestamos.items()]
            avancys_orm.direct_create(self._cr, self._uid, 'hr_payslip_prestamo_cuota', valores)
        return True

    @api.multi
    def reckon_obligaciones(self):

        obligaciones_line = []
        bmt = self.payslip_period_id.bm_type if self.payslip_period_id.bm_type else 'both'
        for line in self.obligaciones_ids:
            if not line.manual:
                obligaciones_line.append(line.id)
        self._cr.execute("DELETE FROM hr_payslip_obligacion_tributaria_line "
                         "WHERE payslip_id = {payslip}".format(payslip=self.id))

        if self.tipo_nomina.code in ('Nomina', 'Vacaciones', 'Liquidacion'):
            dum = 'second' if bmt == 'both' else 'both'
            self._cr.execute("SELECT id from hr_payroll_obligacion_tributaria "
                             "WHERE state = 'validated' "
                             "AND contract_id = {contract} "
                             "AND date_from <= '{date_to}' "
                             "AND (date_to >= '{date_from}' OR date_to is Null)"
                             "AND (bm_type = '{bmt}' OR bm_type = 'both' OR bm_type='{dum}') "
                             "ORDER BY category_id DESC".format(
                                  contract=self.contract_id.id, date_from=self.date_from, date_to=self.date_to,
                                  bmt=bmt, dum=dum))

            obl_vl = self._cr.fetchall()
            valores = []
            if obl_vl and self.tipo_nomina.code in ('Nomina', 'Vacaciones', 'Liquidacion'):
                obligaciones = self.env['hr.payroll.obligacion.tributaria'].browse(x[0] for x in obl_vl)
                for obliga in obligaciones:
                    valores.append({
                        'obligacion_id': obliga.id,
                        'valor': obliga.valor,
                        'payslip_id': self.id,
                        'manual': False,
                    })
                avancys_orm.direct_create(self._cr, self._uid, 'hr_payslip_obligacion_tributaria_line', valores)
        return True

    @api.multi
    def close_slip_old(self):

        i, j = 0, len(self)
        bar = avancys_orm.progress_bar(i, j)
        # noinspection PyTypeChecker
        for slip in self:

            # Causacion ---------------------------------------------------------------------------------------------

            try:
                if slip.ref_currency_rate and slip.ref_currency_id:
                    ref_currency_rate = slip.ref_currency_rate
                    ref_currency_id = slip.ref_currency_id.id
            except AttributeError:
                ref_currency_rate = 1
                ref_currency_id = False
            narration = 'Nomina de {emp}'.format(emp=slip.employee_id.name.encode('utf-8'))
            if slip.move_name:
                name = slip.move_name
            else:
                journal_seq = slip.journal_id.sequence_id
                name = self.env['ir.sequence'].next_by_id(journal_seq.id)
            account_period = self.env['account.period'].find(slip.liquid_date)[0]

            move_data = {
                'narration': narration,
                'date': slip.liquid_date,
                'name': name,
                'ref': slip.number,
                'journal_id': slip.journal_id.id,
                'period_id': account_period.id,
                'partner_id': slip.employee_id.partner_id.id,
                'payslip_run_id': slip.payslip_run_id.id,
                'state': 'posted'
            }

            move_id = avancys_orm.direct_create(self._cr, self._uid, 'account_move', [move_data], company=True)[0][0]
            struct_ids = get_ids(slip.contract_id.type_id.structures._ids)
            self._cr.execute("""SELECT id from hr_payroll_structure where tipo_nomina = {nom_type} and id in {ids}
                """.format(nom_type=slip.tipo_nomina.id, ids=struct_ids))
            structure = self._cr.fetchall()
            if structure:
                structure = structure[0][0]
            else:
                raise Warning("No existe una estructura salaria definida para este tipo de contrato y tipo de nomina")

            move_line_data = []
            for slip_line in slip.line_ids:
                credit_account_id, debit_account_id, analytic_account_id = False, False, False
                if slip_line.salary_rule_id == self.env.user.company_id.dummy_salary_rule:
                    self._cr.execute("SELECT hcsa.id, nov.code, cf.code FROM hr_concept_structure_account hcsa "
                                     "LEFT JOIN hr_payroll_obligacion_tributaria_category cf "
                                     "    ON cf.id = hcsa.obligacion_category_id "
                                     "LEFT JOIN hr_payroll_novedades_category nov "
                                     "    ON nov.id = hcsa.novedad_category_id "
                                     "WHERE (nov.id =  hcsa.novedad_category_id "
                                     "    OR cf.id = hcsa.obligacion_category_id) "
                                     "AND (nov.code = '{rule_code}' "
                                     "    OR cf.code = '{rule_code}')".format(rule_code=slip_line.code))
                    structure_line = self._cr.fetchall()
                    if structure_line:
                        s_ids = [x[0] for x in structure_line]
                        self._cr.execute("SELECT c.id "
                                         "FROM hr_concept_structure_account c "
                                         "INNER JOIN hr_payroll_structure s on s.id = c.structure_id "
                                         "WHERE c.id in {s_ids} "
                                         "AND s.id = {struc_emp}".format(s_ids=tuple(s_ids),
                                                                         struc_emp=slip.contract_id.struct_id.id))
                        uniq_struct_id = self._cr.fetchall()
                        structure_line_id = self.env['hr.concept.structure.account'].browse(uniq_struct_id[0][0])
                        credit_account_id = structure_line_id.account_credit_structure_property
                        debit_account_id = structure_line_id.account_debit_structure_property
                        analytic_account_id = structure_line_id.analytic_account_id_structure_property
                        rule_partner = slip.employee_id.partner_id.id
                    else:
                        # Es probablemente un prestamo
                        self._cr.execute("SELECT id "
                                         "FROM hr_payroll_prestamo_category "
                                         "WHERE code = '{rule_code}'".format(rule_code=slip_line.code))
                        prestamo = self._cr.fetchall()
                        if prestamo:
                            pr_ct = self.env['hr.payroll.prestamo.category'].browse(prestamo[0][0])
                            credit_account_id = pr_ct.account_credit
                            debit_account_id = pr_ct.account_debit
                            rule_partner = slip.employee_id.partner_id.id

                else:
                    self._cr.execute("SELECT id FROM hr_payroll_structure_accounts "
                                     "WHERE salary_rule_id = {srule} and structure_id = {structure}".format(
                                            srule=slip_line.salary_rule_id.id, structure=structure))
                    structure_line = self._cr.fetchall()
                    if structure_line:
                        structure_line = structure_line[0][0]
                    else:
                        continue
                    structure_line_id = self.env['hr.payroll.structure.accounts'].browse(structure_line)
                    credit_account_id = structure_line_id.account_credit_structure_property
                    debit_account_id = structure_line_id.account_debit_structure_property
                    analytic_account_id = structure_line_id.analytic_account_id_structure_property

                    tipo_tercero = slip_line.salary_rule_id.tipo_tercero

                    if tipo_tercero == 'eps':
                        rule_partner = slip.contract_id.eps.id
                    elif tipo_tercero == 'arl':
                        rule_partner = slip.contract_id.arl.id
                    elif tipo_tercero == 'cesantias':
                        rule_partner = slip.contract_id.cesantias.id
                    elif tipo_tercero == 'pensiones':
                        rule_partner = slip.contract_id.pensiones.id
                    elif tipo_tercero == 'cajacomp':
                        rule_partner = slip.contract_id.cajacomp.id
                    else:
                        rule_partner = slip.employee_id.partner_id.id

                precision = self.env['decimal.precision'].precision_get('Payroll')
                amount = round(slip_line.total, precision)
                amount_currency = (amount / ref_currency_rate) if ref_currency_rate > 1 else 0

                account_tax_id = slip_line.salary_rule_id.account_tax_id and slip_line.salary_rule_id.account_tax_id.id

                if credit_account_id:
                    account_id = credit_account_id
                    analytic_id, customer_id = False, False
                    if not analytic_account_id and slip.contract_id.analytic_account_id:
                        analytic_account_id = slip.contract_id.analytic_account_id
                    if str(account_id.code[0]) not in ['4', '5', '6']:
                        aa_id = False
                    else:
                        aa_id = analytic_account_id.id if analytic_account_id else False
                        if 'analytic_id' in self.env['account.move.line']._fields:
                            analytic_id = slip.contract_id.analytic_id.id if slip.contract_id.analytic_id else False
                            customer_id = slip.contract_id.customer_id.id if slip.contract_id.customer_id else False

                    line_data = {
                        'name': slip_line.name,
                        'ref1': slip_line.code,
                        'date': slip.liquid_date,
                        'ref': slip.number,
                        'partner_id': rule_partner,
                        'account_id': account_id.id,
                        'journal_id': slip.journal_id.id,
                        'period_id': account_period.id,
                        'debit': 0,
                        'credit': amount,
                        'analytic_account_id': aa_id,
                        'tax_code_id': account_tax_id or False,
                        'tax_amount': account_tax_id and amount or 0,
                        'payslip_run_id': slip.payslip_run_id.id,
                        'move_id': move_id,
                        'amount_currency': amount_currency,
                        'currency_id': ref_currency_id,
                        'state': 'valid',
                        'date_maturity': slip.liquid_date
                    }
                    if analytic_id or customer_id:
                        line_data['analytic_id'] = analytic_id
                        line_data['customer_id'] = customer_id
                    move_line_data.append(line_data)
                if debit_account_id:
                    account_id = debit_account_id
                    analytic_id, customer_id = False, False
                    if not analytic_account_id and slip.contract_id.analytic_account_id:
                        analytic_account_id = slip.contract_id.analytic_account_id
                    if str(account_id.code[0]) not in ['4', '5', '6']:
                        aa_id = False
                    else:
                        aa_id = analytic_account_id.id if analytic_account_id else False
                        if 'analytic_id' in self.env['account.move.line']._fields:
                            analytic_id = slip.contract_id.analytic_id.id if slip.contract_id.analytic_id else False
                            customer_id = slip.contract_id.customer_id.id if slip.contract_id.customer_id else False

                    line_data = {
                        'name': slip_line.name,
                        'ref1': slip_line.code,
                        'date': slip.liquid_date,
                        'ref': slip.number,
                        'partner_id': rule_partner,
                        'account_id': account_id.id,
                        'journal_id': slip.journal_id.id,
                        'period_id': account_period.id,
                        'debit': amount,
                        'credit': 0,
                        'analytic_account_id': aa_id,
                        'tax_code_id': account_tax_id or False,
                        'tax_amount': account_tax_id and amount or 0,
                        'payslip_run_id': slip.payslip_run_id.id,
                        'move_id': move_id,
                        'amount_currency': amount_currency,
                        'currency_id': ref_currency_id,
                        'state': 'valid',
                        'date_maturity': slip.liquid_date
                    }
                    if analytic_id or customer_id:
                        line_data['analytic_id'] = analytic_id
                        line_data['customer_id'] = customer_id
                    move_line_data.append(line_data)
            move_line_ids = avancys_orm.direct_create(self._cr, self._uid, 'account_move_line', move_line_data,
                                                      company=True)
            debcreddif = False
            if move_line_ids:
                self._cr.execute("SELECT sum(debit), sum(credit) from account_move_line where move_id = {move}".format(
                    move=move_id))
                sums = self._cr.fetchall()
                if sums:
                    debcreddif = sums[0][0] - sums[0][1]

            if debcreddif:
                if debcreddif > 0:
                    account_id = slip.journal_id.default_credit_account_id
                    direction = 'credit'
                else:
                    account_id = slip.journal_id.default_debit_account_id
                    direction = 'debit'
                analytic_account_id = slip.contract_id.analytic_account_id
                analytic_id, customer_id = False, False
                if str(account_id.code[0]) not in ['4', '5', '6']:
                    analytic_account_id = False
                else:
                    analytic_account_id = analytic_account_id.id
                    if 'analytic_id' in self.env['account.move.line']._fields:
                        analytic_id = slip.contract_id.analytic_id.id if slip.contract_id.analytic_id else False
                        customer_id = slip.contract_id.customer_id.id if slip.contract_id.customer_id else False

                line_data = {
                    'name': 'Movimiento de ajuste',
                    'date': slip.liquid_date,
                    'ref': slip.number,
                    'partner_id': slip.employee_id.partner_id.id,
                    'account_id': account_id.id,
                    'journal_id': slip.journal_id.id,
                    'period_id': account_period.id,
                    'debit': abs(debcreddif) if direction == 'debit' else 0.0,
                    'credit': abs(debcreddif) if direction == 'credit' else 0.0,
                    'analytic_account_id': analytic_account_id,
                    'tax_code_id': False,
                    'tax_amount': 0,
                    'move_id': move_id,
                    'amount_currency': False,
                    'payslip_run_id': slip.payslip_run_id.id,
                    'currency_id': ref_currency_id,
                    'state': 'valid',
                    'date_maturity': slip.liquid_date
                }
                if analytic_id or customer_id:
                    line_data['analytic_id'] = analytic_id
                    line_data['customer_id'] = customer_id

                avancys_orm.direct_create(self._cr, self._uid, 'account_move_line', [line_data],
                                                        company=True)

            # Contabilidad analitica --------------------------------------------------------------------------------

            self._cr.execute("SELECT state from ir_module_module where name = 'hr_roster'")
            roster = self._cr.fetchall()
            if roster and roster[0][0] != 'installed':

                analytic_lines_data = []
                for line_id in move_line_ids:
                    line = self.env['account.move.line'].browse(line_id[0])
                    if line.analytic_account_id:
                        analytic_line = {
                            'account_id': line.analytic_account_id.id,
                            'date': line.date,
                            'name': line.name,
                            'ref': slip.number,
                            'move_id': line_id[0],
                            'journal_id': slip.journal_id.analytic_journal_id.id,
                            'general_account_id': line.account_id.id,
                            'amount': line.credit - line.debit,
                        }
                        analytic_lines_data.append(analytic_line)
                analytic_line_ids = avancys_orm.direct_create(self._cr, self._uid, 'account_analytic_line',
                                                              analytic_lines_data, company=True)

            avancys_orm.direct_update(self._cr, 'hr_payslip', {'move_id': move_id, 'state': 'posted'}, ('id', slip.id))

            # Cierre de nomina --------------------------------------------------------------------------------------

            # Prestamos: Se relacionan con el slip directamente si el slip no tiene el atributo credit_note
            for prestamo in slip.prestamos_ids:
                if slip.credit_note:
                    avancys_orm.direct_update(self._cr, 'hr_payroll_prestamo_cuota', {'payslip_id': False},
                                              ('id', prestamo.id))
                else:
                    avancys_orm.direct_update(self._cr, 'hr_payroll_prestamo_cuota', {'payslip_id': slip.id},
                                              ('id', prestamo.id))

            # Novedades: Se relacionan con el slip directamente si el slip no tiene el atributo credit_note
            for novedad in slip.novedades_ids:
                if slip.credit_note:
                    avancys_orm.direct_update(self._cr, 'hr_payroll_novedades',
                                              {'state': 'validated', 'payslip_id': False}, ('id', novedad.id))
                else:
                    avancys_orm.direct_update(self._cr, 'hr_payroll_novedades',
                                              {'state': 'done', 'payslip_id': slip.id}, ('id', novedad.id))

            # Extras: Se relacionan con el slip y se pasan a estado pagado
            for extra in slip.extrahours_ids:
                avancys_orm.direct_update(self._cr, 'hr_payroll_extrahours', {'payslip_id': slip.id, 'state': 'paid'},
                                          ('id', extra.id))

            # Ausencias: Se pasan a pagadas unicamente si termina dentro del periodo de la nomina
            for holiday in slip.leave_ids:
                if holiday.holiday_status_id.code == 'VAC':
                    avancys_orm.direct_update(self._cr, 'hr_holidays', {'payslip_id': slip.id, 'state': 'paid'},
                                              ('id', holiday.id))
                    for days_line in holiday.line_ids:
                        avancys_orm.direct_update(self._cr, 'hr_holidays_days',
                                                  {'payslip_id': slip.id, 'state': 'paid'},
                                                  ('id', days_line.id))
                elif holiday.date_to < slip.payslip_period_id.end_period:
                    avancys_orm.direct_update(self._cr, 'hr_holidays', {'payslip_id': slip.id, 'state': 'paid'},
                                              ('id', holiday.id))
            for leave in slip.leave_days_ids:
                if not leave.payslip_id:
                    avancys_orm.direct_update(self._cr, 'hr_holidays_days', {'payslip_id': slip.id, 'state': 'paid'},
                                              ('id', leave.id))
            # Obligaciones
            for obli in slip.obligaciones_ids:
                if obli.obligacion_id.date_to < slip.payslip_period_id.end_period:
                    avancys_orm.direct_update(self._cr, 'hr_payroll_obligacion_tributaria', {'state': 'done'},
                                              ('id', obli.obligacion_id.id))
            # Anticipos
            for ant in slip.advance_ids:
                avancys_orm.direct_update(self._cr, 'hr_payroll_advance', {'payslip_id': slip.id, 'state': 'paid'},
                                          ('id', ant.id))

            avancys_orm.direct_update(self._cr, 'hr_payslip', {'state': 'done'}, ('id', slip.id))
            i += 1
            bar = avancys_orm.progress_bar(i, j, bar, slip.id)
        return True

    @api.multi
    def close_slip(self):

        i, j = 0, len(self)
        bar = avancys_orm.progress_bar(i, j)
        # noinspection PyTypeChecker
        for slip in self:
            if slip.state == 'draft':
                # Causacion -------------------------------------------------------------------------------------------
                ref_currency_rate = 1
                ref_currency_id = False
                try:
                    if slip.ref_currency_rate and slip.ref_currency_id:
                        ref_currency_rate = slip.ref_currency_rate
                        ref_currency_id = slip.ref_currency_id.id
                except AttributeError:
                    ref_currency_rate = 1
                    ref_currency_id = False
                narration = 'Nomina de {emp}'.format(emp=slip.employee_id.name.encode('utf-8'))
                if slip.move_name:
                    name = slip.move_name
                else:
                    journal_seq = slip.journal_id.sequence_id
                    name = self.env['ir.sequence'].next_by_id(journal_seq.id)
                account_period = self.env['account.period'].find(slip.liquid_date)[0]

                move_data = {
                    'narration': narration,
                    'date': slip.liquid_date,
                    'name': name,
                    'ref': slip.number,
                    'journal_id': slip.journal_id.id,
                    'period_id': account_period.id,
                    'partner_id': slip.employee_id.partner_id.id,
                    'payslip_run_id': slip.payslip_run_id.id,
                    'state': 'posted'
                }

                move_id = avancys_orm.direct_create(self._cr, self._uid, 'account_move', [move_data], company=True)[0][0]

                move_line_data = []
                for c_line in slip.concept_ids:
                    if c_line.total >= 0:
                        debit_account, credit_account, partner_type, partner_other = c_line.get_accounts()
                    else:
                        # Se voltea la contabilidad para permitir generar asientos para conceptos negativos
                        credit_account, debit_account, partner_type, partner_other = c_line.get_accounts()

                    if partner_type == 'eps':
                        c_partner = slip.employee_id.contract_id.eps.id
                    elif partner_type == 'arl':
                        c_partner = slip.employee_id.contract_id.arl.id
                    elif partner_type == 'caja':
                        c_partner = slip.employee_id.contract_id.cajacomp.id
                    elif partner_type == 'cesantias':
                        c_partner = slip.employee_id.contract_id.cesantias.id
                    elif partner_type == 'pensiones':
                        c_partner = slip.employee_id.contract_id.pensiones.id
                    elif partner_type == 'other':
                        c_partner = partner_other
                    else:
                        c_partner = slip.employee_id.partner_id.id

                    precision = self.env['decimal.precision'].precision_get('Payroll')
                    amount = round(abs(c_line.total), precision)
                    amount_currency = (amount / ref_currency_rate) if ref_currency_rate > 1 else 0

                    if debit_account not in [None, False] and amount:
                        account_id = self.env['account.account'].browse(debit_account)
                        analytic_account_id = slip.contract_id.analytic_account_id
                        analytic_id, customer_id = False, False
                        if str(account_id.code[0]) not in ['4', '5', '6', '7']:
                            aa_id = False
                        else:
                            aa_id = analytic_account_id.id if analytic_account_id else False
                            if 'analytic_id' in self.env['account.move.line']._fields:
                                analytic_id = slip.contract_id.analytic_id.id if slip.contract_id.analytic_id else False
                                customer_id = slip.contract_id.customer_id.id if slip.contract_id.customer_id else False
                                if not aa_id or not analytic_id or not customer_id:
                                    raise Warning("No se ha definido la parametrizacion analitica "
                                                  "para el colaborador {emp}".format(emp=slip.employee_id.name))
                        line_data = {
                            'name': c_line.name,
                            'ref1': c_line.code,
                            'date': slip.liquid_date,
                            'ref': slip.number,
                            'partner_id': c_partner,
                            'account_id': account_id.id,
                            'journal_id': slip.journal_id.id,
                            'period_id': account_period.id,
                            'debit': amount,
                            'credit': 0,
                            'analytic_account_id': aa_id,
                            'tax_code_id': False,
                            'tax_amount': 0,
                            'payslip_run_id': slip.payslip_run_id.id,
                            'move_id': move_id,
                            'amount_currency': amount_currency,
                            'bank_id': slip.employee_id.partner_id.default_bank_id.bank.id if slip.employee_id.partner_id.default_bank_id else False,
                            'currency_id': ref_currency_id,
                            'state': 'valid',
                            'date_maturity': slip.liquid_date
                        }
                        if analytic_id or customer_id:
                            line_data['analytic_id'] = analytic_id
                            line_data['customer_id'] = customer_id
                        move_line_data.append(line_data)

                    if credit_account not in [None, False] and amount:
                        account_id = self.env['account.account'].browse(credit_account)
                        analytic_account_id = slip.contract_id.analytic_account_id
                        analytic_id, customer_id = False, False
                        if str(account_id.code[0]) not in ['4', '5', '6', '7']:
                            aa_id = False
                        else:
                            aa_id = analytic_account_id.id if analytic_account_id else False
                            if 'analytic_id' in self.env['account.move.line']._fields:
                                analytic_id = slip.contract_id.analytic_id.id if slip.contract_id.analytic_id else False
                                customer_id = slip.contract_id.customer_id.id if slip.contract_id.customer_id else False
                                if not aa_id or not analytic_id or not customer_id:
                                    raise Warning("No se ha definido la parametrizacion analitica "
                                                  "para el colaborador {emp}".format(emp=slip.employee_id.name))

                        line_data = {
                            'name': c_line.name,
                            'ref1': c_line.code,
                            'date': slip.liquid_date,
                            'ref': slip.number,
                            'partner_id': c_partner,
                            'account_id': account_id.id,
                            'journal_id': slip.journal_id.id,
                            'period_id': account_period.id,
                            'payslip_run_id': slip.payslip_run_id.id,
                            'debit': 0,
                            'credit': amount,
                            'analytic_account_id': aa_id,
                            'tax_code_id': False,
                            'tax_amount': 0,
                            'move_id': move_id,
                            'amount_currency': amount_currency,
                            'bank_id': slip.employee_id.partner_id.default_bank_id.bank.id if slip.employee_id.partner_id.default_bank_id else False,                            'currency_id': ref_currency_id,
                            'state': 'valid',
                            'date_maturity': slip.liquid_date
                        }
                        if analytic_id or customer_id:
                            line_data['analytic_id'] = analytic_id
                            line_data['customer_id'] = customer_id
                        if line_data['partner_id'] is False:
                            raise Warning("No se ha especificado un tercero para el concepto "
                                          "{cline} en la nomina {nom}".format(cline=c_line, nom=slip.name))
                        move_line_data.append(line_data)

                move_line_ids = avancys_orm.direct_create(self._cr, self._uid, 'account_move_line', move_line_data,
                                                          company=True)
                debcreddif = False
                if move_line_ids:
                    self._cr.execute("SELECT sum(debit), sum(credit) from account_move_line where move_id = {move}".format(
                        move=move_id))
                    sums = self._cr.fetchall()
                    if sums:
                        debcreddif = sums[0][0] - sums[0][1]

                if debcreddif:
                    if debcreddif > 0:
                        account_id = slip.journal_id.default_credit_account_id
                        direction = 'credit'
                    else:
                        account_id = slip.journal_id.default_debit_account_id
                        direction = 'debit'
                    analytic_id, customer_id = False, False
                    analytic_account_id = slip.contract_id.analytic_account_id
                    if str(account_id.code[0]) not in ['4', '5', '6', '7']:
                        analytic_account_id = False
                    else:
                        analytic_account_id = analytic_account_id.id
                        if 'analytic_id' in self.env['account.move.line']._fields:
                            analytic_id = slip.contract_id.analytic_id.id if slip.contract_id.analytic_id else False
                            customer_id = slip.contract_id.customer_id.id if slip.contract_id.customer_id else False

                    line_data = {
                        'name': 'Movimiento de ajuste nomina %s' % slip.number,
                        'date': slip.liquid_date,
                        'ref': slip.number,
                        'partner_id': slip.employee_id.partner_id.id,
                        'account_id': account_id.id,
                        'journal_id': slip.journal_id.id,
                        'period_id': account_period.id,
                        'debit': abs(debcreddif) if direction == 'debit' else 0.0,
                        'credit': abs(debcreddif) if direction == 'credit' else 0.0,
                        'payslip_run_id': slip.payslip_run_id.id,
                        'analytic_account_id': analytic_account_id,
                        'bank_id': slip.employee_id.partner_id.default_bank_id.bank.id if slip.employee_id.partner_id.default_bank_id else False,                        'tax_code_id': False,
                        'tax_amount': 0,
                        'move_id': move_id,
                        'amount_currency': False,
                        'currency_id': ref_currency_id,
                        'state': 'valid',
                        'date_maturity': slip.liquid_date
                    }
                    if analytic_id or customer_id:
                        line_data['analytic_id'] = analytic_id
                        line_data['customer_id'] = customer_id
                    if line_data['partner_id'] is False:
                        raise Warning("No se ha especificado un tercero para el concepto "
                                      "{cline} en la nomina {nom}".format(cline=c_line, nom=slip.name))

                    avancys_orm.direct_create(self._cr, self._uid, 'account_move_line', [line_data], company=True)

                # Contabilidad analitica --------------------------------------------------------------------------------

                self._cr.execute("SELECT state from ir_module_module where name = 'hr_roster'")
                roster = self._cr.fetchall()
                if roster and roster[0][0] != 'installed':

                    analytic_lines_data = []
                    for line_id in move_line_ids:
                        line = self.env['account.move.line'].browse(line_id[0])
                        if line.analytic_account_id:
                            analytic_line = {
                                'account_id': line.analytic_account_id.id,
                                'date': line.date,
                                'name': line.name,
                                'ref': slip.number,
                                'move_id': line_id[0],
                                'journal_id': slip.journal_id.analytic_journal_id.id,
                                'general_account_id': line.account_id.id,
                                'amount': line.credit - line.debit,
                            }
                            analytic_lines_data.append(analytic_line)
                    avancys_orm.direct_create(self._cr, self._uid, 'account_analytic_line',
                                              analytic_lines_data, company=True)

                avancys_orm.direct_update(self._cr, 'hr_payslip',
                                          {'move_id': move_id, 'move_name': name, 'state': 'posted'}, ('id', slip.id))

                # Cierre de nomina --------------------------------------------------------------------------------------

                # Prestamos: Se relacionan con el slip directamente si el slip no tiene el atributo credit_note
                for prestamo in slip.prestamos_ids:
                    if slip.credit_note:
                        avancys_orm.direct_update(self._cr, 'hr_payroll_prestamo_cuota', {'payslip_id': False},
                                                  ('id', prestamo.id))
                    else:
                        avancys_orm.direct_update(self._cr, 'hr_payroll_prestamo_cuota', {'payslip_id': slip.id},
                                                  ('id', prestamo.id))

                # Novedades: Se relacionan con el slip directamente si el slip no tiene el atributo credit_note
                for novedad in slip.novedades_ids:
                    if slip.credit_note:
                        avancys_orm.direct_update(self._cr, 'hr_payroll_novedades',
                                                  {'state': 'validated', 'payslip_id': False}, ('id', novedad.id))
                    else:
                        avancys_orm.direct_update(self._cr, 'hr_payroll_novedades',
                                                  {'state': 'done', 'payslip_id': slip.id}, ('id', novedad.id))

                # Extras: Se relacionan con el slip y se pasan a estado pagado
                for extra in slip.extrahours_ids:
                    avancys_orm.direct_update(self._cr, 'hr_payroll_extrahours', {'payslip_id': slip.id, 'state': 'paid'},
                                              ('id', extra.id))

                # Ausencias: Se pasan a pagadas unicamente si termina dentro del periodo de la nomina
                for holiday in slip.leave_ids:
                    if holiday.holiday_status_id.vacaciones and not self.env.user.company_id.fragment_vac:
                        if not holiday.payslip_id:
                            avancys_orm.direct_update(self._cr, 'hr_holidays', {'payslip_id': slip.id, 'state': 'paid'},
                                                      ('id', holiday.id))
                        for days_line in holiday.line_ids:
                            if not days_line.payslip_id:
                                avancys_orm.direct_update(self._cr, 'hr_holidays_days',
                                                          {'payslip_id': slip.id, 'state': 'paid'},
                                                          ('id', days_line.id))
                        enjoyed = holiday.number_of_days_temp
                        vac_book = {
                            'enjoyed': enjoyed,
                            'payed': holiday.payed_vac if holiday.payed_vac > 0 else 0,
                            'payslip_id': slip.id,
                            'contract_id': slip.contract_id.id
                        }
                        avancys_orm.direct_create(self._cr, self._uid, 'hr_vacation_book', [vac_book])

                    elif holiday.date_to <= slip.payslip_period_id.end_period:
                        avancys_orm.direct_update(self._cr, 'hr_holidays', {'payslip_id': slip.id, 'state': 'paid'},
                                                  ('id', holiday.id))
                        for day in holiday.line_ids:
                            avancys_orm.direct_update(self._cr, 'hr_holidays_days',
                                                      {'payslip_id': slip.id, 'state': 'paid'},
                                                      ('id', day.id))
                        if holiday.holiday_status_id.vacaciones:
                            vac_book = {
                                'payed': holiday.payed_vac,
                                'payslip_id': slip.id,
                                'contract_id': slip.contract_id.id
                            }
                            avancys_orm.direct_create(self._cr, self._uid, 'hr_vacation_book', [vac_book])
                        if holiday.holiday_status_id.no_payable:
                            vac_book = {
                                'licences': holiday.number_of_days_in_payslip,
                                'payslip_id': slip.id,
                                'contract_id': slip.contract_id.id
                            }
                            avancys_orm.direct_create(self._cr, self._uid, 'hr_vacation_book', [vac_book])

                    if holiday.holiday_status_id.vacaciones and self.env.user.company_id.fragment_vac:
                        enjoyed = 0
                        for leave in slip.leave_days_ids:
                            if not leave.payslip_id:
                                avancys_orm.direct_update(self._cr, 'hr_holidays_days', {'payslip_id': slip.id, 'state': 'paid'},
                                                          ('id', leave.id))
                                if leave.holiday_status_id.vacaciones:
                                    enjoyed += leave.days_assigned
                        if enjoyed:
                            vac_book = {
                                'enjoyed': enjoyed,
                                'payslip_id': slip.id,
                                'payed': 0,
                                'contract_id': slip.contract_id.id
                            }
                            avancys_orm.direct_create(self._cr, self._uid, 'hr_vacation_book', [vac_book])
                        if holiday.payed_vac:
                            vac_book = {
                                'payed': holiday.payed_vac,
                                'payslip_id': slip.id,
                                'contract_id': slip.contract_id.id
                            }
                            avancys_orm.direct_create(self._cr, self._uid, 'hr_vacation_book', [vac_book])

                # Obligaciones
                for obli in slip.obligaciones_ids:
                    if obli.obligacion_id.date_to <= slip.payslip_period_id.end_period:
                        avancys_orm.direct_update(self._cr, 'hr_payroll_obligacion_tributaria', {'state': 'done'},
                                                  ('id', obli.obligacion_id.id))
                # Anticipos
                for ant in slip.advance_ids:
                    avancys_orm.direct_update(self._cr, 'hr_payroll_advance', {'payslip_id': slip.id, 'state': 'paid'},
                                              ('id', ant.id))

                avancys_orm.direct_update(self._cr, 'hr_payslip', {'state': 'done'}, ('id', slip.id))

                # Cierre de contratos
                if slip.tipo_nomina.code == 'Liquidacion':
                    slip.contract_id.state = 'done'

            i += 1
            bar = avancys_orm.progress_bar(i, j, bar, slip.id)

        return True

    @api.multi
    def draft_slip(self):
        i, j = 0, len(self)
        bar = avancys_orm.progress_bar(i, j)
        # noinspection PyTypeChecker
        for slip in self:
            if slip.move_id.period_id.state == 'done':
                raise Warning("El periodo del movimiento contable a reversar ya se encuentra cerrado")
            if slip.state == 'done':
                # Reversion contable
                for ml in slip.move_id.line_id:
                    if ml.reconcile_id or ml.reconcile_partial_id:
                        raise Warning("No es posible reversar una nomina con asiento conciliado")
                if slip.move_id:
                    avancys_orm.direct_delete(slip, 'move_id', slip.move_id)
                # Prestamos
                self._cr.execute("UPDATE hr_payroll_prestamo_cuota "
                                 "SET payslip_id = Null "
                                 "WHERE payslip_id = {pid}".format(pid=slip.id))
                # Novedades
                self._cr.execute("UPDATE hr_payroll_novedades "
                                 "SET payslip_id = Null, state= 'validated' "
                                 "WHERE payslip_id = {pid}".format(pid=slip.id))
                # Extras
                self._cr.execute("UPDATE hr_payroll_extrahours "
                                 "SET payslip_id = Null, state= 'validated' "
                                 "WHERE payslip_id = {pid}".format(pid=slip.id))
                # Ausencias
                self._cr.execute("UPDATE hr_holidays "
                                 "SET payslip_id = Null, state= 'validate' "
                                 "WHERE payslip_id = {pid}".format(pid=slip.id))
                self._cr.execute("UPDATE hr_holidays_days "
                                 "SET payslip_id = Null, state= 'validate' "
                                 "WHERE payslip_id = {pid}".format(pid=slip.id))
                self._cr.execute("UPDATE hr_payslip set state = 'draft' where id = {mid}".format(mid=slip.id))
                # Dias de vacaciones
                self._cr.execute("DELETE FROM hr_vacation_book WHERE payslip_id = {pid}".format(pid=slip.id))

                # Obligaciones
                for obli in slip.obligaciones_ids:
                    avancys_orm.direct_update(self._cr, 'hr_payroll_obligacion_tributaria', {'state': 'validated'},
                                              ('id', obli.obligacion_id.id))
                # Anticipos
                self._cr.execute("UPDATE hr_payroll_advance "
                                 "SET payslip_id = Null, state= 'to_discount' "
                                 "WHERE payslip_id = {pid}".format(pid=slip.id))

                # Apertura de contratos
                if slip.tipo_nomina.code == 'Liquidacion':
                    slip.contract_id.state = 'in_progress'

            self._cr.execute("UPDATE hr_payslip set state = 'draft' where id = {mid}".format(mid=slip.id))
            if slip.payslip_run_id and slip.payslip_run_id.state != 'draft':
                slip.payslip_run_id.state = 'draft'
            i += 1
            bar = avancys_orm.progress_bar(i, j, bar, slip.id)


class HrContractType(models.Model):
    _inherit = "hr.contract.type"

    name = fields.Char(compute="get_name", store=True)
    term = fields.Selection(CONTRACT_TERM, 'Termino', required=True)
    type_class = fields.Selection(CONTRACT_CLASS, 'Clase', required=True)
    section = fields.Selection(CONTRACT_SECTION, 'Estructura', required=True)

    @api.depends('term', 'type_class', 'section')
    def get_name(self):
        for k in self:
            if k.term and k.type_class and k.section:
                k.name = k.type_class.upper() + ' ' + k.term.upper() + ' ' + k.section.upper()
