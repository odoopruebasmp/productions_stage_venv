# -*- coding: utf-8 -*-
from datetime import datetime
import calendar
from openerp import models, fields, api, sql_db
from openerp.addons.avancys_orm import avancys_orm as orm
from openerp.exceptions import Warning
from dateutil.relativedelta import relativedelta
import unicodedata
import base64
import math


FORM_TYPES = [
    ('E', '[E] Planilla empleados empresas'),
    ('Y', '[Y] Planilla independientes empresas'),
    ('A', '[A] Planilla cotizantes con novedad de ingreso'),
    ('S', '[S] Planilla empleados de servicio domestico'),
    ('M', '[M] Planilla mora'),
    ('N', '[N] Planilla correcciones'),
    ('H', '[H] Planilla madres sustitutas'),
    ('T', '[T] Planilla empleados entidad beneficiaria del sistema general de participaciones'),
    ('F', '[F] Planilla pago aporte patronal faltante'),
    ('J', '[J] Planilla para pago seguridad social en cumplimiento de sentencia digital'),
    ('X', '[X] Planilla para pago empresa liquidada'),
    ('U', '[U] Planilla de uso UGPP para pagos por terceros'),
    ('K', '[K] Planilla estudiantes')
]

FORM_STATES = [
    ('draft', 'Borrador'),
    ('closed', 'Cerrada')
]


def strip_accents(s):
    new_string = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    new_string = new_string.encode('ascii', 'replace').replace('?', ' ')
    return new_string


def prep_field(s, align='left', size=0, fill=' ', date=False):
    if s in [False, None]:
        s = ''
    if date:
        s = datetime.strftime(s, "%Y-%m-%d")
    if align == 'right':
        s = str(s)[0:size].rjust(size, str(fill))
    elif align == 'left':
        s = str(s)[0:size].ljust(size, str(fill))

    return s


def rp(value):
    if round(value, 0) % 100.0 >= 1:
        val = int(math.ceil(value / 100.0)) * 100
    else:
        val = round(value, 0)
    return val


class HrContributionFormLine(models.Model):
    _name = 'hr.contribution.form.line'

    contribution_id = fields.Many2one('hr.contribution.form', 'Autoliquidacion')
    employee_id = fields.Many2one('hr.employee', 'Empleado')
    leave_ids = fields.One2many('hr.contribution.line.leave', 'line_id', string="Ausencias")
    ing = fields.Selection([('X', 'X'), ('R', 'R'), ('C', 'C')], 'ING', help='Ingreso')
    ret = fields.Selection([('P', 'P'), ('R', 'R'), ('C', 'C'), ('X', 'X')], 'RET', help='Retiro')
    tde = fields.Boolean('TDE', help='Traslado desde otra EPS o EOC')
    tae = fields.Boolean('TAE', help='Traslado a otra EPS o EOC')
    tdp = fields.Boolean('TDP', help='Traslado desde otra administradora de pensiones')
    tap = fields.Boolean('TAP', help='Traslado a otra administradora de pensiones')
    vsp = fields.Boolean('VSP', help='Variacion permanente de salario')
    fixes = fields.Selection([('A', 'A'), ('C', 'C')], 'Correcciones')
    vst = fields.Boolean('VST', help='Variacion transitoria de salario')
    sln = fields.Boolean('SLN', help='Licencia no remunerada o suspension temporal del contrato')
    ige = fields.Boolean('IGE', help='Incapacidad general')
    lma = fields.Boolean('LMA', help='Licencia de maternidad o paternidad')
    vac = fields.Boolean('VAC', help='Vacaciones')
    avp = fields.Boolean('AVP', help='Aporte voluntario de pension')
    vct = fields.Boolean('VCT', help='Variacion de centros de trabajo')
    irl = fields.Float('IRL', help='Dias de incapacidad por accidente de trabajo o enfermedad laboral')
    days_pens = fields.Float('Dias pension')
    days_eps = fields.Float('Dias salud')
    days_arl = fields.Float('Dias ARL')
    days_ccf = fields.Float('Dias CCF')
    wage = fields.Float('Salario basico')
    int_wage = fields.Boolean('Integral')
    ibs = fields.Float('IBC para salud y pension')
    ibr = fields.Float('IBC para riesgos profesionales')
    ibp = fields.Float('IBC para CCF')
    pens_rate = fields.Float('Tarifa de aportes de pension')
    ap_pens = fields.Float('Cotizacion obligatoria de pension')
    afc = fields.Float('Aporte voluntario de pension')
    total_pension = fields.Float('Total aportado a fondo de pensiones')
    fon_sol = fields.Float('Fondo de solidaridad')
    fon_sub = fields.Float('Fondeo de subsistencia')
    eps_rate = fields.Float('Tarifa de aportes de salud')
    ap_eps = fields.Float('Cotizacion obligatoria de salud')
    arl_rate = fields.Float('Tarifa de aportes a riesgos laborales')
    ap_arl = fields.Float('Cotizacion de riesgos laborales')
    ccf_rate = fields.Float('Tarifa de aportes a CCF')
    ap_ccf = fields.Float('Cotizacion a CCF')
    sena_rate = fields.Float('Tarifa de aportes SENA')
    ap_sena = fields.Float('Aportes SENA')
    icbf_rate = fields.Float('Tarifa aportes ICBF')
    ap_icbf = fields.Float('Aportes ICBF')
    cot_1607 = fields.Boolean('Cotizante exonerado de pago de aportes')
    w102 = fields.Float('Dias trabajados')
    exonerado = fields.Boolean('Exonerado de aporte de EPS y parafiscales')
    vsp_date = fields.Date('Fecha de inicio VSP')
    wd_hours = fields.Float('Horas laboradas')


class HrContributionLineLeave(models.Model):
    _name = 'hr.contribution.line.leave'

    holiday_id = fields.Many2one('hr.holidays', 'Ausencia')
    holiday_status_id = fields.Many2one('hr.holidays.status', 'Tipo de ausencia')
    days = fields.Float('Dias')
    date_from = fields.Date('Fecha inicio')
    date_to = fields.Date('Fecha final')
    line_id = fields.Many2one('hr.contribution.form.line', 'Detalle Pila')


class HrContributionForm(models.Model):
    _name = 'hr.contribution.form'

    name = fields.Char('Nombre')
    period_id = fields.Many2one('payslip.period', 'Periodo', domain=[('schedule_pay', '=', 'monthly')])
    group_id = fields.Many2one('hr.contract.group', 'Grupo de contratos')
    form_type = fields.Selection(FORM_TYPES, 'Tipo de planilla')
    contract_ids = fields.Many2many('hr.contract', 'pila_contract_rel', 'pila_id', 'contract_id')
    state = fields.Selection(FORM_STATES, 'Estado', default='draft')
    file = fields.Binary('Archivo plano', readonly=True)
    form_line_ids = fields.One2many('hr.contribution.form.line', 'contribution_id', string='Detalle')

    @api.multi
    def calculate_pila(self):
        self._cr.execute("DELETE FROM hr_contribution_form_line where contribution_id = %s" % self.id)
        emp_lsq = ("SELECT hc.employee_id, hc.id FROM pila_contract_rel rel "
                   "INNER JOIN hr_contract hc ON rel.contract_id = hc.id "
                   "WHERE rel.pila_id = {pila} "
                   "GROUP BY hc.employee_id, hc.id".format(pila=self.id))
        emp_ls = orm.fetchall(self._cr, emp_lsq)

        i, j = 0, len(emp_ls)
        bar = orm.progress_bar(i, j)

        for emp in emp_ls:
            line_data = []
            contract_id = self.env['hr.contract'].browse(emp[1])

            # Validacion de ingreso
            ing = False
            if contract_id.date_start[0:7] == self.period_id.end_period[0:7]:
                if contract_id.fiscal_type_id.code == '03':
                    ing = 'R'
                else:
                    ing = 'X'

            # Validacion de retiro
            ret = False
            if contract_id.date_end:
                if contract_id.date_end[0:7] == self.period_id.end_period[0:7]:
                    if contract_id.fiscal_type_id.code == '03':
                        ret = 'R'
                    else:
                        ret = 'X'

            vsp = False
            vsp_date = False
            for changes in contract_id.wage_historic_ids.filtered(
                    lambda x: str(x.date)[0:7] == str(self.period_id.end_period)[0:7]):
                if changes.date[8:] != '01' and not ing:
                    vsp_date = changes.date[0:10]
                    vsp = True

            pslp_query = "SELECT hp.id from hr_payslip hp " \
                         "INNER JOIN payslip_period pp ON pp.id = hp.payslip_period_id " \
                         "WHERE hp.contract_id = {contract} " \
                         "AND pp.start_period::VARCHAR like '{month}%' ".format(
                            contract=contract_id.id, month=self.period_id.start_period[0:7])
            pslp_query = orm.fetchall(self._cr, pslp_query)
            payslips_month = self.env['hr.payslip'].browse([x[0] for x in pslp_query] if pslp_query else False)

            vac, ige, irl, lma, sln, avp = False, False, 0, False, False, False
            nr_l, w102, wd_hours, days_lma = 0, 0, 0, 0
            ap_pens, ap_eps, ap_arl, ap_ccf, ap_sena, ap_icbf, afc_total = 0, 0, 0, 0, 0, 0, 0
            fond_sol, fond_sub = 0, 0
            leaves = {}
            pens_rate, eps_rate, arl_rate, ccf_rate, sena_rate, icbf_rate = 0, 0, 0, 0, 0, 0
            pf_flag = True
            leave_days = []
            for payslip in payslips_month:
                for leave in payslip.leave_days_ids:
                    if leave.holiday_status_id.vacaciones:
                        vac = True
                    if leave.holiday_status_id.general_illness:
                        ige = True
                    if leave.holiday_status_id.atep:
                        irl += leave.days_payslip
                    if leave.holiday_status_id.maternal_lic or leave.holiday_status_id.paternal_lic:
                        lma = True
                        days_lma += leave.days_payslip
                    if leave.holiday_status_id.no_payable:
                        sln = True

                    if leave.holiday_id not in leaves:
                        if not leave.name[-2:] == '31':
                            leaves[leave.holiday_id] = [leave.days_payslip, leave.name, leave.name]
                            leave_days.append(leave.id)
                    else:
                        if leave.id not in leave_days and not leave.name[-2:] == '31':
                            leaves[leave.holiday_id][0] += leave.days_payslip
                            if leaves[leave.holiday_id][1] > leave.name:
                                leaves[leave.holiday_id][1] = leave.name
                            if leaves[leave.holiday_id][2] < leave.name:
                                leaves[leave.holiday_id][2] = leave.name
                            leave_days.append(leave.id)

                for novedad in payslip.novedades_ids:
                    if novedad.category_id.ded_rent:
                        avp = True
                        afc_total += novedad.total

                if payslip.tipo_nomina.code in ('Nomina', 'Otros', 'Vacaciones', 'Liquidacion'):
                    wd = orm.fetchall(self._cr, "SELECT number_of_days, number_of_hours "
                                                "FROM hr_payslip_worked_days "
                                                "WHERE payslip_id = %s AND code = 'WORK102'" % payslip.id)
                    w102 += wd[0][0] if wd else 0
                    wd_hours += wd[0][1] if wd else 0
                ap_pens_c = payslip.get_payslip_concept('AP_PENS')
                ded_pens_c = payslip.get_payslip_concept('DED_PENS')
                retired = True if payslip.contract_id.fiscal_subtype_id.code not in ['00', False] or \
                                  payslip.contract_id.fiscal_type_id.code in ('12', '19') else False

                pens_rate = 16 if not retired else 0
                ap_pens += ap_pens_c.total + ded_pens_c.total

                ap_eps_c = payslip.get_payslip_concept('AP_EPS')
                ded_eps_c = payslip.get_payslip_concept('DED_EPS')
                if ded_eps_c.rate:
                    eps_rate = 4
                if ap_eps_c.rate:
                    pf_flag = False
                    eps_rate = 12.5
                ap_eps += ap_eps_c.total + ded_eps_c.total

                ap_arl_c = payslip.get_payslip_concept('AP_ARL')
                if ap_arl_c.rate:
                    arl_rate = ap_arl_c.rate
                ap_arl += ap_arl_c.total

                ap_ccf_c = payslip.get_payslip_concept('AP_CCF')
                if ap_ccf_c.rate:
                    ccf_rate = ap_ccf_c.rate
                ap_ccf += ap_ccf_c.total

                ap_sena_c = payslip.get_payslip_concept('AP_SENA')
                if ap_sena_c.rate:
                    pf_flag = False
                    sena_rate = ap_sena_c.rate
                ap_sena += ap_sena_c.total

                ap_icbf_c = payslip.get_payslip_concept('AP_ICBF')
                if ap_icbf_c.rate:
                    pf_flag = False
                    icbf_rate = ap_icbf_c.rate
                ap_icbf += ap_icbf_c.total

                fond_sol += payslip.get_payslip_concept_total('FOND_SOL')
                fond_sub += payslip.get_payslip_concept_total('FOND_SUB')

            ibs, ibr, ibp = 0, 0, 0
            days_ss, days_arl, days_ccf = 0, 0, 0

            for payslip in payslips_month:
                tipo_nomina = payslip.tipo_nomina.code
                bmt = payslip.payslip_period_id.bm_type
                sch_pay = payslip.payslip_period_id.schedule_pay
                mont_sec = sch_pay == 'monthly' or bmt == 'second'
                if (tipo_nomina == 'Nomina' and mont_sec) or tipo_nomina == 'Liquidacion':

                    mrang_start = payslip.payslip_period_id.start_period[0:7] + "-01"
                    mrang_end = payslip.payslip_period_id.end_period
                    col_days = payslip.collect_days(mrang_start, mrang_end)

                    w101 = col_days['WORK101'] if 'WORK101' in col_days else 0
                    days_ss = w101 - nr_l
                    days_arl = w102
                    days_ccf = w102 + days_lma
                    # Se toma el IBL ya que es para la generacion de la primera linea
                    ibs = payslip.get_payslip_concept_total('IBL') or payslip.get_payslip_concept_total('IBS')
                    ibr = payslip.get_payslip_concept_total('IBR')
                    ibp = payslip.get_payslip_concept_total('IBP')

            wage = contract_id.wage
            int_wage = True if contract_id.type_id.type_class == 'int' else False
            vst = wage != ibs

            line_data.append({
                'contribution_id': self.id,
                'employee_id': emp[0],
                'ing': ing,
                'ret': ret,
                'vsp': vsp,
                'vac': vac,
                'ige': ige,
                'irl': irl,
                'lma': lma,
                'sln': sln,
                'avp': avp,
                'vst': vst,
                'days_pens': days_ss,
                'days_eps': days_ss,
                'days_arl': days_arl,
                'days_ccf': days_ccf,
                'wage': wage,
                'int_wage': int_wage,
                'ibs': ibs,
                'ibr': ibr,
                'ibp': ibp,
                'w102': w102,
                'pens_rate': pens_rate,
                'ap_pens': ap_pens,
                'afc': afc_total,
                'total_pension': ap_pens + afc_total,
                'fon_sol': fond_sol,
                'fon_sub': fond_sub,
                'eps_rate': eps_rate,
                'ap_eps': ap_eps,
                'arl_rate': arl_rate,
                'ap_arl': ap_arl,
                'ccf_rate': ccf_rate,
                'ap_ccf': ap_ccf,
                'sena_rate': sena_rate,
                'ap_sena': ap_sena,
                'icbf_rate': icbf_rate,
                'ap_icbf': ap_icbf,
                'wd_hours': wd_hours,
                'vsp_date': vsp_date,
                'exonerado': pf_flag,
            })
            ctbr_line = orm.direct_create(self._cr, self._uid, 'hr_contribution_form_line', line_data)[0][0]
            leave_data = []
            for l in leaves:
                leave_data.append({
                    'holiday_id': l.id,
                    'days': leaves[l][0],
                    'holiday_status_id': l.holiday_status_id.id,
                    'line_id': ctbr_line,
                    'date_from': leaves[l][1],
                    'date_to': leaves[l][2],
                })
            orm.direct_create(self._cr, self._uid, 'hr_contribution_line_leave', leave_data)
            i += 1
            bar = orm.progress_bar(i, j, bar, emp[0])

        return True

    @api.multi
    def generate_pila(self):
        total_text = ''
        break_line = '\r\n'
        # ----- HEADER ----- #
        hl = [''] * (22 + 1)
        # 1: Tipo de registro
        hl[1] = '01'

        # 2: Modalidad de la planilla
        hl[2] = '1'

        # 3: Secuencia # TODO Está generando el 0001 pero se debe validar que siempre sea el mismo
        hl[3] = '0001'

        # 4: Nombre o razon social del aportante
        hl[4] = prep_field(self.env.user.company_id.partner_id.name, size=200)

        # 5: Tipo de documento del aportante # TODO Asignado directamente tipo de documento NIT
        hl[5] = 'NI'

        # 6: Numero de identificacion del aportante
        hl[6] = prep_field(self.env.user.company_id.partner_id.ref, size=16)

        # 7: Digito de verificacion
        hl[7] = str(self.env.user.company_id.partner_id.dev_ref)

        # 8: Tipo de planilla
        hl[8] = self.form_type

        # 9: Numero de la planilla asociada a esta planilla # TODO revisar casos de planillas N y F
        if self.form_type not in ['N', 'F']:
            hl[9] = prep_field(" ", size=10)
        else:
            raise Warning("Tipo de planilla no soportada temporalmente")

        # 10: Fecha de planilla de pago asociada a esta planilla
        if self.form_type not in ['N', 'F']:
            hl[10] = prep_field(" ", size=10)
        else:
            raise Warning("Tipo de planilla no soportada temporalmente")

        # 11: Forma de presentacion # TODO temporalmente forma de presentacion unica
        hl[11] = 'U'

        # 12: Codigo de sucursal # TODO referente campo 11
        hl[12] = prep_field(" ", size=10)

        # 13: Nombre de la sucursal
        hl[13] = prep_field(" ", size=40)

        # 14: Código de la ARL a la cual el aportante se encuentra afiliado

        hl[14] = prep_field(self.env.user.company_id.arl_id.codigo_arl, size=6)

        # 15: Período de pago para los sistemas diferentes al de salud
        hl[15] = prep_field(self.period_id.start_period[0:7], size=7)

        # 16: Período de pago para el sistema de salud.
        pay_ref_date = datetime.strptime(self.period_id.start_period, "%Y-%m-%d") + relativedelta(months=1)
        pay_month = datetime.strftime(pay_ref_date, "%Y-%m")
        hl[16] = prep_field(pay_month, size=7)

        # 17: Número de radicación o de la Planilla Integrada de Liquidación de Aportes. (Asignado por el sistema)
        hl[17] = prep_field(" ", size=10)

        # 18: Fecha de pago (aaaa-mm-dd) (Asignado por el siustema)
        hl[18] = prep_field(" ", size=10)

        # 19: Numero total de empleados
        emp_count_q = ("SELECT count(hc.employee_id) FROM pila_contract_rel rel " 
                       "INNER JOIN hr_contract hc on hc.id = rel.contract_id "
                       "INNER JOIN hr_employee he on he.id = hc.employee_id "
                       "WHERE rel.pila_id = {pila} "
                       "GROUP by hc.employee_id".format(pila=self.id))
        emp_count = orm.fetchall(self._cr, emp_count_q)
        hl[19] = prep_field(len(emp_count), align='right', fill='0', size=5)

        # 20: Valor total de la nomina
        ibp_sum_q = ("SELECT sum(total) FROM hr_payslip_concept hpc "
                     "INNER JOIN pila_contract_rel rel on rel.contract_id = hpc.contract_id "
                     "INNER JOIN hr_payslip hp on hp.id = hpc.payslip_id "
                     "INNER JOIN payslip_period pp on pp.id = hp.payslip_period_id "
                     "WHERE rel.pila_id = {pila} "
                     "AND hpc.code = 'IBP' "
                     "AND pp.start_period between '{start}' and '{end}'".format(
                        pila=self.id,
                        start=self.period_id.start_period,
                        end=self.period_id.end_period))
        ibp_sum = orm.fetchall(self._cr, ibp_sum_q)[0][0] or 0
        hl[20] = prep_field(int(ibp_sum), align='right', fill='0', size=12)

        # 21: Tipo de aportante
        hl[21] = prep_field("1", size=2)

        # 22: Codigo de operador de informacion
        hl[22] = prep_field(" ", size=2)

        for x in hl:
            total_text += x
        total_text += break_line

        # ----- BODY ----- #
        seq = 0
        i, j = 0, len(self.form_line_ids)
        bar = orm.progress_bar(i, j)
        for line in self.form_line_ids:
            bl = [''] * (98 + 1)
            employee = line.employee_id
            ref_type = employee.partner_id.ref_type.code
            contracts = self.contract_ids.filtered(lambda k: k.employee_id.id == employee.id)

            for contract in contracts:
                retired = True if contract.fiscal_subtype_id.code not in ['00', False] \
                                  or contract.fiscal_type_id.code in ('12', '19') else False
                lectivo = True if contract.fiscal_type_id.code == '12' else False
                # 1: Tipo de registro
                bl[1] = '02'

                # 2: Secuencia
                seq += 1
                bl[2] = prep_field(seq, align='right', fill='0', size=5)

                # 3: Tipo de documento de cotizante
                bl[3] = prep_field(ref_type, size=2)

                # 4: Numero de identificacion cotizante
                bl[4] = prep_field(employee.partner_id.ref, size=16)

                # 5: Tipo de cotizante
                bl[5] = prep_field(contract.fiscal_type_id.code, size=2)

                # 6: Subtipo de cotizante
                bl[6] = prep_field(contract.fiscal_subtype_id.code or '00', size=2)

                # 7: Extranjero no obligado a cotizar pensiones
                foreign = employee.partner_id.country_id.code != 'CO' and ref_type in ('CE', 'PA', 'CD')
                bl[7] = 'X' if foreign else ' '

                # 8: Colombiano en el exterior
                is_col = True if ref_type in ('CC', 'TI') and employee.partner_id.country_id.code == 'CO' else False
                in_ext = False
                if contract.cuidad_desempeno:
                    in_ext = True if contract.cuidad_desempeno.provincia_id.country_id.code != 'CO' else False
                bl[8] = 'X' if is_col and in_ext else ' '

                # 9: Código del departamento de la ubicación laboral
                bl[9] = prep_field(contract.cuidad_desempeno.provincia_id.code or '', size=2)

                # 10: Código del municipio de ubicación laboral
                bl[10] = prep_field(contract.cuidad_desempeno.code or '', size=3)

                # 11: Primer apellido
                if employee.partner_id.primer_apellido:
                    pap = strip_accents(employee.partner_id.primer_apellido.upper())
                    bl[11] = prep_field(pap, size=20)
                else:
                    bl[11] = prep_field(' ', size=20)

                # 12: Segundo apellido
                if employee.partner_id.segundo_apellido:
                    sap = strip_accents(employee.partner_id.segundo_apellido.upper())
                    bl[12] = prep_field(sap, size=30)
                else:
                    bl[12] = prep_field(' ', size=30)

                # 13: Primer nombre
                if employee.partner_id.primer_nombre:
                    pno = strip_accents(employee.partner_id.primer_nombre.upper())
                    bl[13] = prep_field(pno, size=20)
                else:
                    bl[13] = prep_field(' ', size=20)

                # 14: Segundo nombre
                if employee.partner_id.otros_nombres:
                    sno = strip_accents(employee.partner_id.otros_nombres.upper())
                    bl[14] = prep_field(sno, size=30)
                else:
                    bl[14] = prep_field(' ', size=30)

                # 15: Ingreso
                bl[15] = line.ing or ' '

                # 16: Retiro
                bl[16] = line.ret or ' '

                # 17: Traslasdo desde otra eps
                bl[17] = 'X' if line.tde else ' '

                # 18: Traslasdo a otra eps
                bl[18] = 'X' if line.tae else ' '

                # 19: Traslasdo desde otra administradora de pensiones
                bl[19] = 'X' if line.tdp else ' '

                # 20: Traslasdo a otra administradora de pensiones
                bl[20] = 'X' if line.tap else ' '

                # 21: Variacion permanente del salario
                bl[21] = 'X' if line.vsp else ' '

                # 22: Correcciones
                bl[22] = line.fixes or ' '

                # 23: Variacion transitoria del salario
                bl[23] = 'X' if line.vst else ' '

                # 24: Suspension temporal del contrato
                bl[24] = 'X' if line.sln else ' '

                # 25: Incapacidad temporal por enfermedad general
                bl[25] = 'X' if line.ige else ' '

                # 26: Licencia de maternidad o paternidad
                bl[26] = 'X' if line.lma else ' '

                # 27: Vacaciones, licencia remunerada
                bl[27] = 'X' if line.vac else ' '

                # 28: Aporte voluntario
                bl[28] = 'X' if line.avp else ' '

                # 29: Variacion de centro de trabajo
                bl[29] = 'X' if line.vct else ' '

                # 30: Dias de incapacidad por enfermedad laboral
                bl[30] = '00'

                # 31: Codigo de la administradora de fondos de pensiones
                afp = contract.pensiones
                codigo_afp = ''
                if afp and not retired:
                    codigo_afp = afp.codigo_afp
                    if not codigo_afp:
                        raise Warning("El tercero de la AFP '%s' no tiene codigo de AFP configurado!" % afp.name)
                bl[31] = prep_field(codigo_afp or '', size=6)

                # 32: Codigo de administradora de pensiones a la cual se traslada el afiliado #TODO
                bl[32] = prep_field(' ', size=6)

                # 33: Codigo de EPS a la cual pertenece el afiliado
                eps = contract.eps
                if not eps:
                    raise Warning("El contrato '%s' no tiene EPS configurado!" % contract.name)
                if not eps.codigo_eps:
                    raise Warning("El tercero de la EPS '%s' no tiene codigo de EPS configurado!" % eps.name)
                bl[33] = prep_field(eps.codigo_eps or '', size=6)

                # 34: Codigo de eps a la cual se traslada el afiliado #TODO
                bl[34] = prep_field(' ', size=6)

                # 35: Código CCF a la cual pertenece el afiliado
                ccf = contract.cajacomp
                codigo_ccf = ''
                if ccf and line.ccf_rate:
                    codigo_ccf = ccf.codigo_ccf
                    if not codigo_ccf:
                        raise Warning("El tercero de la CCF '%s' no tiene codigo de CCF configurado!" % ccf.name)
                bl[35] = prep_field(codigo_ccf or '', size=6)

                # 36: Numero de dias cotizados a pension

                bl[36] = prep_field("{:02.0f}".format(line.w102 if not retired else 0), align='right', fill='0', size=2)

                # 37: Numero de dias cotizados a salud
                bl[37] = prep_field("{:02.0f}".format(line.w102), align='right', fill='0', size=2)

                # 38: Numero de dias cotizados a ARL
                bl[38] = prep_field("{:02.0f}".format(line.w102), align='right', fill='0', size=2)

                # 39: Numero de dias cotizados a CCF
                bl[39] = prep_field("{:02.0f}".format(line.w102), align='right', fill='0', size=2)

                # 40: Salario basico
                bl[40] = prep_field("{:09.0f}".format(line.wage), align='right', fill='0', size=9)

                # 41: Salario integral
                bl[41] = 'X' if line.int_wage else ' '

                total_aus = 0
                for leave in line.leave_ids:
                    total_aus += leave.days

                # 42: IBC pension
                bl[42] = prep_field("{:09.0f}".format(line.ibs if not retired else 0), align='right', fill='0', size=9)

                # 43: IBC salud
                bl[43] = prep_field("{:09.0f}".format(line.ibs), align='right', fill='0', size=9)

                # 44: IBC arl
                bl[44] = prep_field("{:09.0f}".format(line.ibr), align='right', fill='0', size=9)

                # 45: IBC CCF
                # Calculo de vacaciones en nominas del periodo
                vac_conc = ['VAC_DISF', 'VAC_PAG', 'VAC_LIQ']
                hp = self.env['hr.payslip']
                vac_base = 0
                for conc in vac_conc:
                    vac_disf = hp.get_interval_concept(conc, self.period_id.start_period, self.period_id.end_period,
                                                       contract=contract.id)
                    if vac_disf:
                        vac_base += vac_disf[0][1]
                bl[45] = prep_field("{:09.0f}".format(line.ibp - vac_base), align='right', fill='0', size=9)

                # 46: Tarifa de aporte a pensiones
                bl[46] = prep_field("{:01.5f}".format(line.pens_rate/100 if not retired else 0),
                                    align='right', fill='0', size=7)

                # 47: Cotizacion pension
                cot_pens = rp(line.pens_rate * line.ibs / 100)
                bl[47] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)

                # 48: Aportes voluntarios del afiliado
                bl[48] = prep_field(0, align='right', fill='0', size=9)

                # 49: Aportes voluntarios del aportante. TODO
                bl[49] = prep_field(0, align='right', fill='0', size=9)

                # 50: Total cotizacion pensiones
                bl[50] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)

                # 51: Aportes a fondo solidaridad
                bl[51] = prep_field("{:09.0f}".format(line.fon_sol), align='right', fill='0', size=9)

                # 52: Aportes a fondo subsistencia
                bl[52] = prep_field("{:09.0f}".format(line.fon_sub), align='right', fill='0', size=9)

                # 53: Valor no retenido por aportes voluntarios TODO
                bl[53] = prep_field(0, align='right', fill='0', size=9)

                # 54: Tarifa de aportes salud
                bl[54] = prep_field("{:01.5f}".format(line.eps_rate/100), align='right', fill='0', size=7)

                # 55: Aportes salud
                cot_eps = rp(line.eps_rate * line.ibs / 100)
                bl[55] = prep_field("{:09.0f}".format(cot_eps), align='right', fill='0', size=9)

                # 56: Total UPS adicional TODO
                bl[56] = prep_field(0, align='right', fill='0', size=9)

                # 57: Numero de autorizacion de incapacidad
                bl[57] = prep_field(' ', size=15)

                # 58: Valor de la incapacidad por enf general
                bl[58] = prep_field(0, align='right', fill='0', size=9)

                # 59: Numero de autorizacion por licencia de maternidad
                bl[59] = prep_field(' ', size=15)

                # 60: Valor de licencia de maternidad
                bl[60] = prep_field(0, align='right', fill='0', size=9)

                # 61: Tarifa de aportes a riesgos laborales
                bl[61] = prep_field("{:01.5f}".format(line.arl_rate/100), align='right', fill='0', size=9)

                # 62: Centro de trabajo
                bl[62] = prep_field(0, align='right', fill='0', size=9)

                # 63: Cotizacion obligatoria a riesgos laborales
                bl[63] = prep_field("{:09.0f}".format(rp(line.ibr*line.arl_rate/100)), align='right', fill='0', size=9)

                # 64: Tarifa de aportes CCF
                bl[64] = prep_field("{:01.5f}".format(line.ccf_rate/100), align='right', fill='0', size=7)

                # 65: Aportes CCF
                bl[65] = prep_field("{:09.0f}".format(rp((line.ibp - vac_base) * 0.04)), align='right', fill='0', size=9)

                # 66: Tarifa SENA
                bl[66] = prep_field("{:01.5f}".format(line.sena_rate/100), align='right', fill='0', size=7)

                # 67: Aportes SENA
                bl[67] = prep_field("{:09.0f}".format(rp(line.ap_sena)), align='right', fill='0', size=9)

                # 68: Tarifa ICBF
                bl[68] = prep_field("{:01.5f}".format(line.icbf_rate/100), align='right', fill='0', size=7)

                # 69: Aportes ICBF
                bl[69] = prep_field("{:09.0f}".format(rp(line.ap_icbf)), align='right', fill='0', size=9)

                # 70: Tarifa ESAP
                bl[70] = prep_field("{:01.5f}".format(0), align='right', fill='0', size=7)

                # 71: Aportes ESAP
                bl[71] = prep_field("{:09.0f}".format(0), align='right', fill='0', size=9)

                # 72: Tarifa MEN
                bl[72] = prep_field("{:01.5f}".format(0), align='right', fill='0', size=7)

                # 73: Aportes MEN
                bl[73] = prep_field("{:09.0f}".format(0), align='right', fill='0', size=9)

                # 74: Tipo de documento del cotizante principal
                bl[74] = prep_field(' ', size=2)

                # 75: Numero de documento de cotizante principal
                bl[75] = prep_field(' ', size=16)

                # 76: Exonerado de aportes a paraficales y salud
                bl[76] = 'S' if line.exonerado else 'N'

                # 77: Codigo de la administradora de riesgos laborales

                bl[77] = prep_field(str(contract.arl.codigo_arl or ' ') if not lectivo else ' ', size=6)

                # 78: Clase de riesgo en la cual se encuentra el afiliado
                bl[78] = prep_field(str(contract.riesgo.name or ' '), size=1)

                # 79: Indicador de tarifa especial de pensiones
                bl[79] = prep_field(' ', size=1)

                # 80: Fecha de ingreso
                bl[80] = prep_field(contract.date_start if line.ing else ' ', size=10)

                # 81: Fecha de retiro
                bl[81] = prep_field(contract.date_end if line.ret else ' ', size=10)

                # 82: Fecha de inicio de VSP
                bl[82] = prep_field(line.vsp_date if line.vsp else ' ', size=10)

                # ---- DATOS VARIABLES POR AUSENCIAS ----
                bl[83] = prep_field('', size=10)
                bl[84] = prep_field('', size=10)
                bl[85] = prep_field('', size=10)
                bl[86] = prep_field('', size=10)
                bl[87] = prep_field('', size=10)
                bl[88] = prep_field('', size=10)
                bl[89] = prep_field('', size=10)
                bl[90] = prep_field('', size=10)
                bl[91] = prep_field('', size=10)
                bl[92] = prep_field('', size=10)
                bl[93] = prep_field('', size=10)
                bl[94] = prep_field('', size=10)
                bl[95] = prep_field("{:09.0f}".format(0 if line.exonerado else line.ibp),
                                    align='right', fill='0', size=9)

                # 96: Numero de horas laboradas
                bl[96] = prep_field("{:03.0f}".format(line.wd_hours), align='right', fill='0', size=3)

                bl[97] = prep_field('', size=10)

                # ----- Ajuste de indicadores ------
                if line.leave_ids:
                    bl[24] = ' '
                    bl[25] = ' '
                    bl[26] = ' '
                    bl[27] = ' '
                    bl[30] = '00'
                    if line.w102:
                        for x in bl:
                            total_text += x
                        total_text += break_line
                    else:
                        seq -= 1
                else:
                    if line.w102:
                        for x in bl:
                            try:
                                total_text += x.decode("utf-8", errors="ignore")
                            except:
                                raise Warning(x)
                        total_text += break_line
                    else:
                        seq -= 1

                # Generacion de lineas por ausencias
                for leave in line.leave_ids:

                    seq += 1
                    bl[2] = prep_field(seq, align='right', fill='0', size=5)

                    bl[24] = ' '
                    bl[25] = ' '
                    bl[26] = ' '
                    bl[27] = ' '
                    bl[30] = '00'
                    bl[96] = prep_field("{:03.0f}".format(0), align='right', fill='0', size=3)

                    # Reset de fechas
                    bl[83] = prep_field('', size=10)
                    bl[84] = prep_field('', size=10)
                    bl[85] = prep_field('', size=10)
                    bl[86] = prep_field('', size=10)
                    bl[87] = prep_field('', size=10)
                    bl[88] = prep_field('', size=10)
                    bl[89] = prep_field('', size=10)
                    bl[90] = prep_field('', size=10)
                    bl[91] = prep_field('', size=10)
                    bl[92] = prep_field('', size=10)
                    bl[93] = prep_field('', size=10)
                    bl[94] = prep_field('', size=10)

                    if leave.holiday_status_id.no_payable:
                        # Indicador de SLN
                        bl[24] = 'X'
                        # 37: Numero de dias cotizados a pension
                        bl[36] = prep_field("{:02.0f}".format(leave.days if not retired else 0),
                                            align='right', fill='0', size=2)
                        # 37: Numero de dias cotizados a salud
                        bl[37] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 38: Numero de dias cotizados a ARL
                        bl[38] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 39: Numero de dias cotizados a CCF
                        bl[39] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)

                        # 42: IBC pension
                        if not retired:
                            bl[42] = prep_field("{:09.0f}".format(
                                leave.holiday_id.get_ibs() * leave.days / line.days_pens),
                                align='right', fill='0', size=9)
                        else:
                            bl[42] = prep_field("{:09.0f}".format(0), align='right', fill='0', size=9)

                        # 43: IBC salud
                        bl[43] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 44: IBC arl
                        bl[44] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 45: IBC CCF
                        bl[45] = prep_field("{:09.0f}".format(0), align='right', fill='0', size=9)

                        # 46: Tarifa de aporte a pensiones
                        bl[46] = prep_field("{:01.5f}".format(0.12 if not retired else 0),
                                            align='right', fill='0', size=7)
                        # 47: Cotizacion pension
                        cot_pens = rp(leave.holiday_id.get_ibs() * leave.days * 0.12 / line.days_pens) if not retired else 0
                        bl[47] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)
                        # 50: Total cotizacion pensiones
                        bl[50] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)
                        # 54: Tarifa de aportes salud
                        eps_rate = 0
                        bl[54] = prep_field("{:01.5f}".format(eps_rate), align='right', fill='0', size=7)
                        # 55: Aportes salud
                        cot_eps = 0
                        bl[55] = prep_field("{:09.0f}".format(cot_eps), align='right', fill='0', size=9)
                        # 61: Tarifa de aportes a riesgos laborales
                        bl[61] = prep_field("{:01.5f}".format(0), align='right', fill='0', size=9)
                        # 63: Cotizacion obligatoria a riesgos laborales
                        cot_arl = 0
                        bl[63] = prep_field("{:09.0f}".format(cot_arl), align='right', fill='0', size=9)
                        # 64: Tarifa de aportes CCF
                        bl[64] = prep_field("{:01.5f}".format(0), align='right', fill='0', size=7)
                        # 65: Aportes CCF
                        cot_ccf = 0
                        bl[65] = prep_field("{:09.0f}".format(cot_ccf), align='right', fill='0', size=9)

                        # 83: Fecha de inicio SLN
                        bl[83] = prep_field(leave.date_from, size=10)
                        # 84: Fecha de fin SLN
                        bl[84] = prep_field(leave.date_to, size=10)

                    if leave.holiday_status_id.general_illness:
                        # Indicador de IGE
                        bl[25] = 'X'
                        # 37: Numero de dias cotizados a pension
                        bl[36] = prep_field("{:02.0f}".format(leave.days if not retired else 0),
                                            align='right', fill='0', size=2)
                        # 37: Numero de dias cotizados a salud
                        bl[37] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 38: Numero de dias cotizados a ARL
                        bl[38] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 39: Numero de dias cotizados a CCF
                        bl[39] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)

                        # 42: IBC pension
                        if not retired:
                            bl[42] = prep_field("{:09.0f}".format(
                                leave.holiday_id.get_ibs() * leave.days / line.days_pens),
                                align='right', fill='0', size=9)
                        else:
                            bl[42] = prep_field("{:09.0f}".format(0), align='right', fill='0', size=9)
                        # 43: IBC salud
                        bl[43] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 44: IBC arl
                        bl[44] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 45: IBC CCF
                        bl[45] = prep_field("{:09.0f}".format(0),
                                            align='right', fill='0', size=9)
                        # 46: Tarifa de aporte a pensiones
                        bl[46] = prep_field("{:01.5f}".format(line.pens_rate / 100), align='right', fill='0', size=7)

                        # 47: Cotizacion pension
                        cot_pens = rp(leave.holiday_id.get_ibs() * leave.days * 0.16 / line.days_pens) if not retired else 0
                        bl[47] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)
                        # 50: Total cotizacion pensiones
                        bl[50] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)
                        # 54: Tarifa de aportes salud
                        eps_rate = 0.04
                        bl[54] = prep_field("{:01.5f}".format(eps_rate), align='right', fill='0', size=7)
                        # 55: Aportes salud
                        cot_sal = rp(leave.holiday_id.get_ibs() * leave.days * eps_rate / line.days_eps)
                        bl[55] = prep_field("{:09.0f}".format(cot_sal), align='right', fill='0', size=9)
                        # 61: Tarifa de aportes a riesgos laborales
                        bl[61] = prep_field("{:01.5f}".format(0), align='right', fill='0', size=9)
                        # 63: Cotizacion obligatoria a riesgos laborales
                        cot_arl = 0
                        bl[63] = prep_field("{:09.0f}".format(cot_arl), align='right', fill='0', size=9)
                        # 64: Tarifa de aportes CCF
                        bl[64] = prep_field("{:01.5f}".format(0), align='right', fill='0', size=7)
                        # 65: Aportes CCF
                        cot_ccf = 0
                        bl[65] = prep_field("{:09.0f}".format(cot_ccf), align='right', fill='0', size=9)

                        # 85: Fecha de inicio IGE
                        bl[85] = prep_field(leave.date_from, size=10)
                        # 86: Fecha de fin IGE
                        bl[86] = prep_field(leave.date_to, size=10)

                    if leave.holiday_status_id.maternal_lic or leave.holiday_status_id.paternal_lic:
                        # Indicador de LMA
                        bl[26] = 'X'
                        # 37: Numero de dias cotizados a pension
                        bl[36] = prep_field("{:02.0f}".format(leave.days if not retired else 0),
                                            align='right', fill='0', size=2)
                        # 37: Numero de dias cotizados a salud
                        bl[37] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 38: Numero de dias cotizados a ARL
                        bl[38] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 39: Numero de dias cotizados a CCF
                        bl[39] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)

                        # 42: IBC pension
                        if not retired:
                            bl[42] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_pens),
                                                align='right', fill='0', size=9)
                        else:
                            bl[42] = prep_field("{:09.0f}".format(0), align='right', fill='0', size=9)
                        # 43: IBC salud
                        bl[43] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 44: IBC arl
                        bl[44] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 45: IBC CCF
                        ibc_ccf = leave.holiday_id.get_ibs() * leave.days / line.days_ccf
                        bl[45] = prep_field("{:09.0f}".format(ibc_ccf), align='right', fill='0', size=9)
                        # 46: Tarifa de aporte a pensiones
                        bl[46] = prep_field("{:01.5f}".format(line.pens_rate / 100), align='right', fill='0', size=7)

                        # 47: Cotizacion pension
                        cot_pens = rp(leave.holiday_id.get_ibs() * leave.days * 0.16 / line.days_pens) if not retired else 0
                        bl[47] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)
                        # 50: Total cotizacion pensiones
                        bl[50] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)
                        # 54: Tarifa de aportes salud
                        eps_rate = 0.04
                        bl[54] = prep_field("{:01.5f}".format(eps_rate), align='right', fill='0', size=7)
                        # 55: Aportes salud
                        cot_eps = rp(leave.holiday_id.get_ibs() * leave.days * eps_rate / line.days_eps)
                        bl[55] = prep_field("{:09.0f}".format(cot_eps), align='right', fill='0', size=9)
                        # 61: Tarifa de aportes a riesgos laborales
                        bl[61] = prep_field("{:01.5f}".format(0), align='right', fill='0', size=9)
                        # 63: Cotizacion obligatoria a riesgos laborales
                        cot_arl = 0
                        bl[63] = prep_field("{:09.0f}".format(cot_arl), align='right', fill='0', size=9)
                        # 65: Aportes CCF
                        cot_ccf = rp(leave.days * line.ccf_rate * ibc_ccf / 30 / 100)
                        bl[65] = prep_field("{:09.0f}".format(cot_ccf), align='right', fill='0', size=9)

                        # 87: Fecha de inicio LMA
                        bl[87] = prep_field(leave.date_from, size=10)
                        # 88: Fecha de fin LMA
                        bl[88] = prep_field(leave.date_to, size=10)
                        # 96: Numero de horas laboradas
                        bl[96] = prep_field("{:03.0f}".format(leave.days*8), align='right', fill='0', size=3)

                    if leave.holiday_status_id.vacaciones:
                        # Indicador de VAC
                        bl[27] = 'X'
                        # 37: Numero de dias cotizados a pension
                        bl[36] = prep_field("{:02.0f}".format(leave.days if not retired else 0), align='right', fill='0', size=2)
                        # 37: Numero de dias cotizados a salud
                        bl[37] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 38: Numero de dias cotizados a ARL
                        bl[38] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 39: Numero de dias cotizados a CCF
                        bl[39] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)

                        # 42: IBC pension
                        if not retired:
                            bl[42] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_pens),
                                                align='right', fill='0', size=9)
                        else:
                            bl[42] = prep_field("{:09.0f}".format(0), align='right', fill='0', size=9)
                        # 43: IBC salud
                        bl[43] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 44: IBC arl
                        bl[44] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 45: IBC CCF
                        bl[45] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 46: Tarifa de aporte a pensiones
                        bl[46] = prep_field("{:01.5f}".format(line.pens_rate / 100), align='right', fill='0', size=7)

                        # 47: Cotizacion pension
                        cot_pens = rp(leave.holiday_id.get_ibs() * leave.days * 0.16 / line.days_pens) if not retired else 0
                        bl[47] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)
                        # 50: Total cotizacion pensiones
                        bl[50] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)
                        # 54: Tarifa de aportes salud
                        eps_rate = 0.04
                        bl[54] = prep_field("{:01.5f}".format(eps_rate), align='right', fill='0', size=7)
                        # 55: Aportes salud
                        cot_eps = rp(leave.holiday_id.get_ibs() * leave.days * eps_rate / line.days_eps)
                        bl[55] = prep_field("{:09.0f}".format(cot_eps), align='right', fill='0', size=9)
                        # 61: Tarifa de aportes a riesgos laborales
                        bl[61] = prep_field("{:01.5f}".format(0), align='right', fill='0', size=9)
                        # 63: Cotizacion obligatoria a riesgos laborales
                        cot_arl = 0
                        bl[63] = prep_field("{:09.0f}".format(cot_arl), align='right', fill='0', size=9)
                        # 65: Aportes CCF
                        cot_ccf = rp((leave.holiday_id.get_ibs() * leave.days / line.days_eps) * 0.04)
                        bl[65] = prep_field("{:09.0f}".format(cot_ccf), align='right', fill='0', size=9)

                        # 89: Fecha de inicio VAC
                        bl[89] = prep_field(leave.date_from, size=10)
                        # 90: Fecha de fin VAC
                        bl[90] = prep_field(leave.date_to, size=10)
                        # 96: Numero de horas laboradas
                        bl[96] = prep_field("{:03.0f}".format(leave.days * 8), align='right', fill='0', size=3)

                    if leave.holiday_status_id.atep:
                        # Indicador de IRL
                        bl[30] = prep_field("{:02.0f}".format(leave.days if not retired else 0), align='right', fill='0', size=2)
                        # 37: Numero de dias cotizados a pension
                        bl[36] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 37: Numero de dias cotizados a salud
                        bl[37] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 38: Numero de dias cotizados a ARL
                        bl[38] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)
                        # 39: Numero de dias cotizados a CCF
                        bl[39] = prep_field("{:02.0f}".format(leave.days), align='right', fill='0', size=2)

                        # 42: IBC pension
                        if not retired:
                            bl[42] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_pens),
                                                align='right', fill='0', size=9)
                        else:
                            bl[42] = prep_field("{:09.0f}".format(0), align='right', fill='0', size=9)
                        # 43: IBC salud
                        bl[43] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 44: IBC arl
                        bl[44] = prep_field("{:09.0f}".format(leave.holiday_id.get_ibs() * leave.days / line.days_eps),
                                            align='right', fill='0', size=9)
                        # 45: IBC CCF
                        bl[45] = prep_field("{:09.0f}".format(0),
                                            align='right', fill='0', size=9)
                        # 46: Tarifa de aporte a pensiones
                        bl[46] = prep_field("{:01.5f}".format(line.pens_rate / 100), align='right', fill='0', size=7)

                        # 47: Cotizacion pension
                        cot_pens = rp(leave.holiday_id.get_ibs() * leave.days * 0.16 / line.days_pens) if not retired else 0
                        bl[47] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)
                        # 50: Total cotizacion pensiones
                        bl[50] = prep_field("{:09.0f}".format(cot_pens), align='right', fill='0', size=9)
                        # 54: Tarifa de aportes salud
                        eps_rate = 0.04
                        bl[54] = prep_field("{:01.5f}".format(eps_rate), align='right', fill='0', size=7)
                        # 55: Aportes salud
                        cot_eps = rp(leave.holiday_id.get_ibs() * leave.days * eps_rate / line.days_eps)
                        bl[55] = prep_field("{:09.0f}".format(cot_eps), align='right', fill='0', size=9)
                        # 61: Tarifa de aportes a riesgos laborales
                        bl[61] = prep_field("{:01.5f}".format(0), align='right', fill='0', size=9)
                        # 63: Cotizacion obligatoria a riesgos laborales
                        cot_arl = 0
                        bl[63] = prep_field("{:09.0f}".format(cot_arl), align='right', fill='0', size=9)
                        # 64: Tarifa de aportes CCF
                        bl[64] = prep_field("{:01.5f}".format(0), align='right', fill='0', size=7)
                        # 65: Aportes CCF
                        cot_ccf = 0
                        bl[65] = prep_field("{:09.0f}".format(cot_ccf), align='right', fill='0', size=9)

                        # 93: Fecha de inicio ATEP
                        bl[93] = prep_field(leave.date_from, size=10)
                        # 94: Fecha de fin ATEP
                        bl[94] = prep_field(leave.date_to, size=10)

                    for x in bl:
                        total_text += x
                    total_text += break_line
            i += 1
            bar = orm.progress_bar(i, j, bar, line.id)
        # ----- FOOTER -----#

        # decode and generate txt
        final_content = strip_accents(total_text.encode('utf-8', 'replace').decode('utf-8'))
        file_text = base64.b64encode(final_content)

        self.write({'file': file_text})

        return hl

    @api.multi
    def load_contract(self):
        self._cr.execute("DELETE FROM pila_contract_rel where pila_id = %s" % self.id)
        if self.group_id:
            groupwh = " AND hc.group_id = {group} ".format(group=self.group_id.id)
        else:
            groupwh = " "
        active = ("SELECT hc.id FROM hr_contract hc "
                  "INNER JOIN hr_payslip hp ON hp.contract_id = hc.id "
                  "WHERE hp.liquidacion_date BETWEEN '{date_from}' AND '{date_to}' "
                  "{groupwh} GROUP BY hc.id".format(date_from=self.period_id.start_period,
                                                                    date_to=self.period_id.end_period,
                                                                    groupwh=groupwh))
        ca = [x[0] for x in orm.fetchall(self._cr, active)]

        for contract in ca:
            self._cr.execute("INSERT into pila_contract_rel (pila_id, contract_id) VALUES ({pila}, {contract})".format(
                pila=self.id, contract=contract))
        return True






