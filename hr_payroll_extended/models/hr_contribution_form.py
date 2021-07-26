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
    # ('Y', '[Y] Planilla independientes empresas'),
    # ('A', '[A] Planilla cotizantes con novedad de ingreso'),
    # ('S', '[S] Planilla empleados de servicio domestico'),
    # ('M', '[M] Planilla mora'),
    # ('N', '[N] Planilla correcciones'),
    # ('H', '[H] Planilla madres sustitutas'),
    # ('T', '[T] Planilla empleados entidad beneficiaria del sistema general de participaciones'),
    # ('F', '[F] Planilla pago aporte patronal faltante'),
    # ('J', '[J] Planilla para pago seguridad social en cumplimiento de sentencia digital'),
    # ('X', '[X] Planilla para pago empresa liquidada'),
    # ('U', '[U] Planilla de uso UGPP para pagos por terceros'),
    # ('K', '[K] Planilla estudiantes')
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


def rp1(value):
    if value - round(value) > 0.0001:
        res = round(value) + 1
    else:
        res = round(value)
    return res

class HrContributionFormLine(models.Model):
    _name = 'hr.contribution.form.line'

    contribution_id = fields.Many2one('hr.contribution.form', 'Autoliquidacion', ondelete="CASCADE")
    employee_id = fields.Many2one('hr.employee', 'Empleado')
    contract_id = fields.Many2one('hr.contract', 'Contrato')
    leave_id = fields.Many2one('hr.holidays', 'Ausencia')
    main = fields.Boolean('Linea principal')

    # Campos PILA
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
    vac = fields.Selection([('X', 'X'), ('L', 'L')], 'VAC', help='Vacaciones/LR')
    avp = fields.Boolean('AVP', help='Aporte voluntario de pension')
    vct = fields.Boolean('VCT', help='Variacion de centros de trabajo')
    irl = fields.Float('IRL', help='Dias de incapacidad por accidente de trabajo o enfermedad laboral')

    afp_code = fields.Char('Codigo AFP')
    afp_to_code = fields.Char('Codigo AFP a la cual se traslada')
    eps_code = fields.Char('Codigo EPS')
    eps_to_code = fields.Char('Codigo EPS a la cual se traslada')
    ccf_code = fields.Char('Codigo CCF')

    pens_days = fields.Integer('Dias cotizados pension')
    eps_days = fields.Integer('Dias cotizados EPS')
    arl_days = fields.Integer('Dias cotizados ARL')
    ccf_days = fields.Integer('Dias cotizados CCF')

    wage = fields.Integer('Salario basico')
    int_wage = fields.Boolean('Salario integral')

    pens_ibc = fields.Float('IBC pension')
    eps_ibc = fields.Float('IBC EPS')
    arl_ibc = fields.Float('IBC ARL')
    ccf_ibc = fields.Float('IBC CCF')
    global_ibc = fields.Float('IBC Global')

    pens_rate = fields.Float('Tarifa pension')
    pens_cot = fields.Float('Cotizacion pension')
    ap_vol_contributor = fields.Float('Aportes voluntarios del afiliado')
    ap_vol_company = fields.Float('Aportes voluntarios del aportante')
    pens_total = fields.Float('Aportes totales de pension')

    fsol = fields.Float('Aportes a fondo de solidaridad')
    fsub = fields.Float('Aportes a fondo de subsistencia')
    ret_cont_vol = fields.Float('Valor no retenido por aportes voluntarios')

    eps_rate = fields.Float('Tarifa EPS')
    eps_cot = fields.Float('Cotizacion EPS')
    ups = fields.Float('Total UPS')
    aus_auth = fields.Char('Numero de autorizacion de incapacidad')
    gd_amount = fields.Float('Valor de la incapacidad EG')
    mat_auth = fields.Char('Numero de autorizacion de licencia')
    mat_amount = fields.Float('Valor de licencia')

    arl_rate = fields.Float('Tarifa ARL')
    work_center = fields.Char('Centro de trabajo')
    arl_cot = fields.Float('Cotizacion ARL')

    ccf_rate = fields.Float('Tarifa CCF')
    ccf_cot = fields.Float('Cotizacion CCF')
    sena_rate = fields.Float('Tarifa SENA')
    sena_cot = fields.Float('Cotizacion SENA')
    icbf_rate = fields.Float('Tarifa ICBF')
    icbf_cot = fields.Float('Cotizacion ICBF')
    esap_rate = fields.Float('Tarifa ESAP')
    esap_cot = fields.Float('Cotizacion ESAP')
    men_rate = fields.Float('Tarifa MEN')
    men_cot = fields.Float('Cotizacion MEN')
    exonerated = fields.Boolean('Exonerado de aportes')

    arl_code = fields.Char('Codigo ARL')
    arl_risk = fields.Char('Clase de riesgo')
    k_start = fields.Date('Fecha de ingreso')
    k_end = fields.Date('Fecha de retiro')
    vsp_start = fields.Date('Fecha de inicio de VSP')

    sln_start = fields.Date('Inicio licencia no remunerada')
    sln_end = fields.Date('Fin licencia no remunerada')
    ige_start = fields.Date('Inicio incapacidad EG')
    ige_end = fields.Date('Fin incapacidad EG')
    lma_start = fields.Date('Inicio licencia maternidad')
    lma_end = fields.Date('Fin licencia maternidad')
    vac_start = fields.Date('Inicio vacaciones')
    vac_end = fields.Date('Fin vacaciones')
    vct_start = fields.Date('Inicio cambio centro de trabajo')
    vct_end = fields.Date('Fin cambio de centro de trabajo')
    atep_start = fields.Date('Inicio ATEP')
    atep_end = fields.Date('Fin ATEP')
    other_ibc = fields.Float('IBC otros parafiscales')
    w_hours = fields.Integer('Horas laboradas')


class HrContributionForm(models.Model):
    _name = 'hr.contribution.form'

    name = fields.Char('Nombre')
    period_id = fields.Many2one('payslip.period', 'Periodo', domain=[('schedule_pay', '=', 'monthly')])
    group_id = fields.Many2one('hr.contract.group', 'Grupo de contratos')
    form_type = fields.Selection(FORM_TYPES, 'Tipo de planilla')
    branch_code = fields.Char('Codigo de sucursal')
    presentation = fields.Char('Presentacion', size=1, default='U')
    contract_ids = fields.Many2many('hr.contract', 'pila_contract_rel', 'pila_id', 'contract_id')
    state = fields.Selection(FORM_STATES, 'Estado', default='draft')
    file = fields.Binary('Archivo plano', readonly=True)
    form_line_ids = fields.One2many('hr.contribution.form.line', 'contribution_id', string='Detalle')
    error_log = fields.Text('Reporte de errores')

    @api.multi
    def calculate_pila(self):
        error_log = ""
        self._cr.execute("DELETE FROM hr_contribution_form_line where contribution_id = %s" % self.id)
        emp_lsq = ("SELECT hc.employee_id, hc.id FROM pila_contract_rel rel "
                   "INNER JOIN hr_contract hc ON rel.contract_id = hc.id "
                   "WHERE rel.pila_id = {pila} "
                   "GROUP BY hc.employee_id, hc.id".format(pila=self.id))
        emp_ls = orm.fetchall(self._cr, emp_lsq)
        payslip_obj = self.env['hr.payslip']
        start_period = self.period_id.start_period
        end_period = self.period_id.end_period
        i, j = 0, len(emp_ls)
        bar = orm.progress_bar(i, j)
        lines = []
        for emp in emp_ls:
            contract_id = self.env['hr.contract'].browse(emp[1])
            retired = True if contract_id.fiscal_subtype_id.code not in ['00', False] \
                              or contract_id.fiscal_type_id.code in ('12', '19') else False
            apr = contract_id.fiscal_type_id.code in ('12', '19')
            apr_lect = contract_id.fiscal_type_id.code == '12'
            pslp_query = "SELECT hp.id from hr_payslip hp " \
                         "INNER JOIN payslip_period pp ON pp.id = hp.payslip_period_id " \
                         "WHERE hp.contract_id = {contract} " \
                         "AND pp.start_period::VARCHAR like '{month}%' ".format(
                contract=contract_id.id, month=start_period[0:7])
            pslp_query = orm.fetchall(self._cr, pslp_query)
            payslips_month = self.env['hr.payslip'].browse([x[0] for x in pslp_query] if pslp_query else False)
            leaves = {}
            leave_days = []
            w102, w_hours, days_lma, nr_l = 0, 0, 0, 0
            prev_post = 0
            ms_flag = False
            ref_payslip = False
            for payslip in payslips_month:
                tipo_nomina = payslip.tipo_nomina.code
                bmt = payslip.payslip_period_id.bm_type
                sch_pay = payslip.payslip_period_id.schedule_pay
                mont_sec = sch_pay == 'monthly' or bmt == 'second'

                if (tipo_nomina == 'Nomina' and mont_sec) or tipo_nomina == 'Liquidacion':
                    ms_flag = True
                    if tipo_nomina == 'Liquidacion' or not ref_payslip:
                        ref_payslip = payslip
                    elif ref_payslip.tipo_nomina.code != 'Liquidacion':
                        ref_payslip = payslip

                if payslip.tipo_nomina.code in ('Nomina', 'Otros', 'Vacaciones', 'Liquidacion'):
                    wd = orm.fetchall(self._cr, "SELECT number_of_days, number_of_hours "
                                                "FROM hr_payslip_worked_days "
                                                "WHERE payslip_id = %s AND code = 'WORK102'" % payslip.id)
                    prev_sq = orm.fetchall(self._cr, "SELECT hpwd.number_of_days, hpwd.number_of_hours "
                                                     "FROM hr_payslip_worked_days hpwd "
                                                     "LEFT JOIN hr_payslip hp on hp.id = hpwd.payslip_id "
                                                     "LEFT JOIN payslip_period pp on pp.id = hp.payslip_period_id "
                                                     "LEFT JOIN hr_payslip_type hpt on hp.tipo_nomina = hpt.id "
                                                     "WHERE hpwd.payslip_id = %s "
                                                     "AND pp.bm_type = 'second' "
                                                     "AND hpt.code != 'Liquidacion'"
                                                     "AND pp.bm_type = 'second' "
                                                     "AND hpwd.code = 'PREV_PAYS'" % payslip.id)
                    wd_per = (wd[0][0] if wd else 0) - (prev_sq[0][0] if prev_sq else 0)
                    w102 += wd_per
                    prev_post += (prev_sq[0][0] if prev_sq else 0)
                for leave in payslip.leave_days_ids:
                    if leave.state == 'paid':
                        if leave.holiday_status_id.code == 'VAC_PAGAS':
                            continue
                        feb28 = False
                        if leave.name[5:12] == '02-28' and leave.holiday_id.date_to[0:10] > leave.name:
                            feb28 = True
                        if leave.holiday_status_id.maternal_lic or leave.holiday_status_id.paternal_lic:
                            days_lma += leave.days_payslip + (2 if feb28 else 0)
                        if leave.holiday_status_id.no_payable:
                            nr_l += leave.days_payslip + (2 if feb28 else 0)

                        if leave.holiday_id not in leaves:
                            if not leave.name[-2:] == '31':
                                leaves[leave.holiday_id] = [leave.days_payslip + (2 if feb28 else 0), leave.name, leave.name]
                                leave_days.append(leave.id)
                        else:
                            if leave.id not in leave_days and not leave.name[-2:] == '31':
                                leaves[leave.holiday_id][0] += leave.days_payslip + (2 if feb28 else 0)
                                if leaves[leave.holiday_id][1] > leave.name:
                                    leaves[leave.holiday_id][1] = leave.name
                                if leaves[leave.holiday_id][2] < leave.name:
                                    leaves[leave.holiday_id][2] = leave.name
                                leave_days.append(leave.id)
            if not ms_flag:
                error_log += (u"No se encontró una nomina de segunda quincena, mensual o "
                              u"de liquidacion para el empleado %s. CC %s \n" % (contract_id.employee_id.name,
                                                                                 contract_id.name))
                continue

            # Generacion de lineas
            fl = []
            if w102:
                fl.append('main')
            fl += [k for k in leaves]

            # IBC GLOBAL #####
            ibs_data = ref_payslip.get_payslip_concept('IBS')
            ibl_data = ref_payslip.get_payslip_concept('IBL')
            ibp_data = ref_payslip.get_payslip_concept('IBP')
            # Dias cotizados
            days_dict = payslip_obj.collect_days(start_period, end_period, contract=contract_id.id)
            int_days_mes = days_dict['WORK101'] if 'WORK101' in days_dict else 0
            ded_inicio = days_dict['DED_INICIO'] if 'DED_INICIO' in days_dict else 0
            ded_fin = days_dict['DED_FIN'] if 'DED_FIN' in days_dict else 0
            dc = ['BASICO', 'VAC_DISF']
            days_payed = 0
            # Dias trabajados menos ausencias pagas en otras nominas
            for concept in dc:
                days_concepts_itv = payslip_obj.get_interval_concept_qty(concept, start_period, end_period,
                                                                         contract=contract_id.id)
                days_concept = sum([x[2] for x in days_concepts_itv])
                days_payed += days_concept
            eff_days = int_days_mes - ded_inicio - ded_fin
            if not self.env.user.company_id.fragment_vac:
                eff_days = days_payed if days_payed > eff_days else eff_days
            e_v = self.env['variables.economicas']
            smmlv = e_v.getValue('SMMLV', end_period) or 0.0
            ibs_day = ibs_data.total / eff_days if eff_days else 0
            days_ibl = days_dict['WORK102'] - prev_post
            ibp_day = ibp_data.total / eff_days if eff_days else 0

            ibl_day = ibl_data.total / days_ibl if days_ibl else 0
            # global_ibc = ibp_day * days_dict['WORK102'] if 'WORK102' in days_dict else 0
            global_ibc = ibp_day * eff_days

            # for leave in leaves:
            #     ibs_pm = leave.get_eff_ibs()
            #     ibs_aus_day = ibs_pm[0] / ibs_pm[1]
            #     ibs_aus_day = ibs_aus_day if ibs_aus_day >= smmlv / 30 else smmlv / 30
            #     global_ibc += ibs_aus_day * leaves[leave][0]

            for line in fl:
                leave_type = False
                if isinstance(line, basestring) and line == 'main':
                    leave_id = False
                    main = True
                else:
                    lstart = leaves[line][1]
                    lend = leaves[line][2]
                    leave_id = line.id
                    leave_type = line.holiday_status_id
                    main = False

                # Novedad de ingreso
                ing = start_period <= contract_id.date_start <= end_period

                # Novedad de retiro
                ret = (start_period <= contract_id.date_end <= end_period) and main
                ret = 'X' if ret else ''

                # Variacion salario permanente
                wage_change_q = ("SELECT id, date "
                                 "FROM hr_contract_salary_change "
                                 "WHERE contract_id = {c} "
                                 "AND date BETWEEN '{df}' AND '{dt}'".format(
                                    c=contract_id.id, df=start_period, dt=end_period))
                wage_change = orm.fetchall(self._cr, wage_change_q)
                vsp = False
                if wage_change:
                    for wc in wage_change:
                        if wc[1] != start_period:
                            vsp = True
                            vsp_date = wc[1]

                # Variacion transitoria de salario
                is_itv = payslip_obj.get_interval_category('earnings', start_period, end_period, exclude=('BASICO',),
                                                           contract=contract_id.id)
                comp_itv = payslip_obj.get_interval_category('comp_earnings', start_period, end_period,
                                                             contract=contract_id.id)
                os_itv = payslip_obj.get_interval_category('o_salarial_earnings', start_period, end_period,
                                                           contract=contract_id.id)
                if (is_itv or comp_itv or os_itv) and not contract_id.part_time and main:
                    vst = True
                else:
                    vst = False

                # Indicador de licencia no remunerada
                sln = not main and leave_type.no_payable

                # Indicador novedad por incapacidad eg
                ige = not main and not sln and leave_type.general_illness

                # Indicador novedad por licencia de maternidad o paternidad
                lma = not main and (leave_type.maternal_lic or leave_type.paternal_lic) and not sln

                # Indicador por vacaciones
                vac = 'X' if not main and leave_type.vacaciones and not sln \
                    else 'L' if not main and not leave_type.vacaciones \
                                and not (leave_type.maternal_lic or leave_type.paternal_lic) \
                                and not leave_type.general_illness and not leave_type.atep and not sln else ''

                # Indicador aporte voluntario pension
                avp_itv = payslip_obj.get_interval_avp(start_period, end_period, contract=contract_id.id)
                if avp_itv and not retired:
                    avp = True
                else:
                    avp = False

                # Dias de incapacidad ATEP
                if not main and leave_type.atep and not sln:
                    irl = leaves[line][0]
                else:
                    irl = 0

                # Codigos administradoras
                afp_code = contract_id.pensiones.codigo_afp if not retired else False
                eps_code = contract_id.eps.codigo_eps
                ccf_code = contract_id.cajacomp.codigo_ccf if not apr else False

                if not retired:
                    pens_days = days_dict['WORK102'] - prev_post if main else leaves[line][0]
                else:
                    pens_days = 0
                eps_days = days_dict['WORK102'] - prev_post if main else leaves[line][0]
                if main:
                    arl_days = days_dict['WORK102'] - prev_post if not apr_lect else 0
                else:
                    arl_days = leaves[line][0] if not apr_lect else 0
                if main:
                    ccf_days = days_dict['WORK102'] - prev_post if not apr else 0
                else:
                    ccf_days = leaves[line][0] if not apr else 0

                w_hours = eps_days * 8

                # Salario

                ibs_day = ibs_day if ibs_day >= smmlv / 30 else smmlv / 30
                ibl_day = ibl_day if ibl_day >= smmlv / 30 else smmlv / 30
                ibs_aus_day = 0
                wage = contract_id.wage if contract_id.wage >= smmlv else smmlv
                int_wage = contract_id.type_id.type_class == 'int'

                # IBC MES ANTERIOR DE AUSENCIA, REUTILIZAR SIEMPRE QUE SEA NECESARIO
                if not main:
                    try:
                        ibs_pm = line.get_eff_ibs()
                    except Warning:
                        error_log += "Error con ausencia de contrato {c} \n".format(c=contract_id.name)
                        continue
                    ibs_aus_day = ibs_pm[0] / ibs_pm[1] if ibs_pm[1] else 0
                    ibs_aus_day = ibs_aus_day if ibs_aus_day >= smmlv / 30 else smmlv / 30

                if main:
                    pens_ibc = rp1(ibl_day * pens_days if not retired and not apr else 0)
                else:
                    pens_ibc = rp1(ibs_aus_day * pens_days if not retired and not apr else 0)

                # IBC EPS
                if main:
                    eps_ibc = rp1(ibl_day * eps_days)
                else:
                    eps_ibc = rp1(ibs_aus_day * eps_days)

                # IBC ARL
                if main:
                    arl_ibc = rp1(ibl_day * arl_days if not apr_lect else 0)
                else:
                    arl_ibc = rp1(ibs_aus_day * arl_days if not apr_lect else 0)

                # IBC CCF
                if main:
                    ccf_ibc = rp1(ibp_day * ccf_days if not apr else 0)
                else:
                    ccf_ibc = rp1(ibp_day * ccf_days if not apr else 0)

                # Tarifa de pension van en cero solo si es pensionado y 12 si es no remunerasdo
                pens_rate = self.env.user.company_id.percentage_total/100
                if contract_id.high_risk:
                    pens_rate = 0.26
                if not main and leave_type.no_payable:
                    if contract_id.high_risk:
                        pens_rate = 0.22
                    else:
                        pens_rate = self.env.user.company_id.percentage_employer/100
                pens_rate = pens_rate if not retired and not apr else 0

                # Cotizacion de pension
                pens_cot = rp(pens_ibc * pens_rate)

                # Aporte voluntario
                if avp:
                    ap_vol_contributor = sum([x[1] for x in avp_itv]) if not retired else 0
                else:
                    ap_vol_contributor = 0

                # Total pensiones
                pens_total = rp(pens_cot + ap_vol_contributor)

                # Fondo de solidaridad
                fsol = rp(pens_ibc * 0.005 if global_ibc >= 4 * smmlv and not retired else 0)

                # Fondo de subsistencia
                fsrate = 0
                if global_ibc > 4 * smmlv:
                    fsrate += 0.005
                if 16 * smmlv <= global_ibc <= 17 * smmlv:
                    fsrate += 0.002
                elif 17 * smmlv <= global_ibc <= 18 * smmlv:
                    fsrate += 0.004
                elif 18 * smmlv <= global_ibc <= 19 * smmlv:
                    fsrate += 0.006
                elif 19 * smmlv <= global_ibc <= 20 * smmlv:
                    fsrate += 0.008
                elif pens_ibc > 20 * smmlv:
                    fsrate += 0.01
                fsub = rp(pens_ibc * fsrate if not retired else 0)

                ret_cont_vol_itv = payslip_obj.get_interval_concept('RET_CTG_DIF_FVP', start_period, end_period,
                                                                    contract=contract_id.id)
                ret_cont_vol = sum([x[1] for x in ret_cont_vol_itv]) if avp else 0

                # Tarifa EPS
                eps_rate = 0.04
                if global_ibc >= 10 * smmlv or int_wage or apr:
                    eps_rate = 0.125
                if not main and leave_type.no_payable:
                    eps_rate = 0

                # Cotizacion EPS
                eps_cot = rp(eps_ibc * eps_rate)

                # Autorizacion de incapacidad
                # aus_auth = line.no_incapacidad if not main and leave_type.general_illness else False
                aus_auth, mat_auth = False, False  # Campo exclusivo de aportes en linea.
                # mat_auth = line.no_incapacidad if not main and (leave_type.maternal_lic or leave_type.paternal_lic) \
                #     else False

                # Tarifa ARL
                arl_rate = contract_id.pct_arp/100 if main and not apr_lect else 0

                # Cotizacion ARL
                arl_cot = rp(arl_ibc * arl_rate)

                # Tarifa CCF
                if (main or leave_type.paternal_lic or leave_type.maternal_lic) and not apr:
                    ccf_rate = 0.04
                else:
                    ccf_rate = 0

                # Cotizacion CCF
                ccf_cot = rp(ccf_ibc * ccf_rate)

                # Tarifa SENA
                sena_rate = 0.02 if global_ibc >= 10 * smmlv or int_wage else 0
                if sln:
                    sena_rate = 0

                # Cotizacion SENA
                sena_cot = rp(ccf_ibc * sena_rate)

                # Tarifa ICBF
                icbf_rate = 0.03 if global_ibc >= 10 * smmlv or int_wage else 0
                if sln:
                    icbf_rate = 0

                # Cotizacion ICBF
                icbf_cot = rp(ccf_ibc * icbf_rate)

                # Indicador de exonerabilidad
                exonerated = global_ibc < 10 * smmlv and not int_wage and not apr

                # Codigo ARL
                arl_code = contract_id.arl.codigo_arl if not apr_lect else False

                # Riesgo ARL
                arl_risk = contract_id.riesgo.name if not apr_lect else False

                # Datos de contrato
                k_start = contract_id.date_start if ing else False
                k_end = contract_id.date_end if ret else False

                # Fechas de novedades
                vsp_start = vsp_date if vsp else False

                sln_start = lstart if not main and sln else False
                sln_end = lend if not main and sln else False

                ige_start = lstart if not main and ige else False
                ige_end = lend if not main and ige else False

                lma_start = lstart if not main and lma else False
                lma_end = lend if not main and lma else False

                vac_start = lstart if not main and vac else False
                vac_end = lend if not main and vac else False

                atep = leave_type.atep if not main else False
                atep_start = lstart if not main and atep else False
                atep_end = lend if not main and atep else False

                # IBC de otros parafiscales
                other_ibc = ccf_ibc if not exonerated else 0

                data = {
                    'contribution_id': self.id,
                    'employee_id': emp[0],
                    'contract_id': contract_id.id,
                    'leave_id': leave_id,
                    'main': main,
                    'ing': ing,
                    'ret': ret,
                    'tde': False,  # TODO
                    'tae': False,  # TODO
                    'tdp': False,  # TODO
                    'tap': False,  # TODO
                    'vsp': vsp,
                    'fixes': False,  # TODO
                    'vst': vst,
                    'sln': sln,
                    'ige': ige,
                    'lma': lma,
                    'vac': vac,
                    'avp': avp,
                    'vct': False,  # TODO
                    'irl': irl,
                    'afp_code': afp_code,
                    'afp_to_code': False,  # TODO
                    'eps_code': eps_code,
                    'eps_to_code': False,  # TODO
                    'ccf_code': ccf_code,
                    'pens_days': pens_days,
                    'eps_days': eps_days,
                    'arl_days': arl_days,
                    'ccf_days': ccf_days,
                    'wage': wage,
                    'int_wage': int_wage,
                    'pens_ibc': pens_ibc,
                    'eps_ibc': eps_ibc,
                    'arl_ibc': arl_ibc,
                    'ccf_ibc': ccf_ibc,
                    'global_ibc': global_ibc,
                    'pens_rate': pens_rate,
                    'pens_cot': pens_cot,
                    'ap_vol_contributor': ap_vol_contributor,
                    'ap_vol_company': 0,  # TODO
                    'pens_total': pens_total,
                    'fsol': fsol,
                    'fsub': fsub,
                    'ret_cont_vol': ret_cont_vol,
                    'eps_rate': eps_rate,
                    'eps_cot': eps_cot,
                    'ups': 0,  # TODO
                    'aus_auth': aus_auth,
                    'gd_amohnt': False,  # TODO
                    'mat_auth': mat_auth,
                    'arl_rate': arl_rate,
                    'workcenter': False,  # TODO
                    'arl_cot': arl_cot,
                    'ccf_rate': ccf_rate,
                    'ccf_cot': ccf_cot,
                    'sena_rate': sena_rate,
                    'sena_cot': sena_cot,
                    'icbf_rate': icbf_rate,
                    'icbf_cot': icbf_cot,
                    'esap_rate': 0,  # TODO
                    'esap_cot': 0,  # TODO
                    'men_rate': 0,  # TODO
                    'men_cot': 0,  # TODO
                    'exonerated': exonerated,
                    'arl_code': arl_code,
                    'arl_risk': arl_risk,
                    'k_start': k_start,
                    'k_end': k_end,
                    'vsp_start': vsp_start,
                    'sln_start': sln_start,
                    'sln_end': sln_end,
                    'ige_start': ige_start,
                    'ige_end': ige_end,
                    'lma_start': lma_start,
                    'lma_end': lma_end,
                    'vac_start': vac_start,
                    'vac_end': vac_end,
                    'vct_start': False,  # TODO
                    'vct_end': False,  # TODO
                    'atep_start': atep_start,
                    'atep_end': atep_end,
                    'other_ibc': other_ibc,
                    'w_hours': w_hours,
                }
                lines.append(data)
            i += 1
            bar = orm.progress_bar(i, j, bar, emp[0])
        orm.direct_create(self._cr, self._uid, 'hr_contribution_form_line', lines)
        self.error_log = error_log

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
        if self.form_type in ['E']:
            hl[9] = prep_field(" ", size=10)
        else:
            raise Warning("Tipo de planilla no soportada temporalmente")

        # 10: Fecha de planilla de pago asociada a esta planilla
        if self.form_type not in ['N', 'F']:
            hl[10] = prep_field(" ", size=10)
        else:
            raise Warning("Tipo de planilla no soportada temporalmente")

        # 11: Forma de presentacion # TODO temporalmente forma de presentacion unica
        hl[11] = prep_field(self.presentation, size=1)

        # 12: Codigo de sucursal # TODO referente campo 11
        hl[12] = prep_field(self.branch_code, size=10)

        # 13: Nombre de la sucursal
        hl[13] = prep_field(self.branch_code, size=40)

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
        ibp_sum = sum([x.ccf_ibc for x in self.form_line_ids])
        hl[20] = prep_field(int(ibp_sum), align='right', fill='0', size=12)

        # 21: Tipo de aportante
        hl[21] = prep_field("1", size=2)

        # 22: Codigo de operador de informacion
        hl[22] = prep_field(" ", size=2)

        for x in hl:
            total_text += x
        total_text += break_line

        # ----- BODY ----- #
        i, j = 0, len(self.form_line_ids)
        bar = orm.progress_bar(i, j)
        seq = 0
        for l in self.form_line_ids:
            seq += 1
            employee = l.employee_id
            ref_type = employee.partner_id.ref_type.code
            bl = [''] * (98 + 1)
            # 1: Tipo de registro
            bl[1] = '02'
            # 2: Secuencia
            bl[2] = prep_field(seq, align='right', fill='0', size=5)
            # 3: Tipo de documento de cotizante
            bl[3] = prep_field(ref_type, size=2)
            # 4: Numero de identificacion cotizante
            bl[4] = prep_field(employee.partner_id.ref, size=16)
            # 5: Tipo de cotizante
            bl[5] = prep_field(l.contract_id.fiscal_type_id.code, size=2)
            # 6: Subtipo de cotizante
            bl[6] = prep_field(l.contract_id.fiscal_subtype_id.code or '00', size=2)
            # 7: Extranjero no obligado a cotizar pensiones
            foreign = employee.partner_id.country_id.code != 'CO' and ref_type in ('CE', 'PA', 'CD')
            bl[7] = 'X' if foreign else ' '
            # 8: Colombiano en el exterior
            is_col = True if ref_type in ('CC', 'TI') and employee.partner_id.country_id.code == 'CO' else False
            in_ext = False
            if l.contract_id.cuidad_desempeno:
                in_ext = True if l.contract_id.cuidad_desempeno.provincia_id.country_id.code != 'CO' else False
            bl[8] = 'X' if is_col and in_ext else ' '
            # 9: Código del departamento de la ubicación laboral
            bl[9] = prep_field(l.contract_id.cuidad_desempeno.provincia_id.code, size=2)
            # 10: Código del municipio de ubicación laboral
            bl[10] = prep_field(l.contract_id.cuidad_desempeno.code, size=3)
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
            bl[15] = 'X' if l.ing else ' '
            # 16: Retiro
            bl[16] = 'X' if l.ret else ' '
            # 17: Traslasdo desde otra eps
            bl[17] = 'X' if l.tde else ' '
            # 18: Traslasdo a otra eps
            bl[18] = 'X' if l.tae else ' '
            # 19: Traslasdo desde otra administradora de pensiones
            bl[19] = 'X' if l.tdp else ' '
            # 20: Traslasdo a otra administradora de pensiones
            bl[20] = 'X' if l.tap else ' '
            # 21: Variacion permanente del salario
            bl[21] = 'X' if l.vsp else ' '
            # 22: Correcciones
            bl[22] = 'X' if l.fixes else ' '
            # 23: Variacion transitoria del salario
            bl[23] = 'X' if l.vst else ' '
            # 24: Suspension temporal del contrato
            bl[24] = 'X' if l.sln else ' '
            # 25: Incapacidad temporal por enfermedad general
            bl[25] = 'X' if l.ige else ' '
            # 26: Licencia de maternidad o paternidad
            bl[26] = 'X' if l.lma else ' '
            # 27: Vacaciones, licencia remunerada
            bl[27] = l.vac if l.vac else ' '
            # 28: Aporte voluntario
            bl[28] = 'X' if l.avp else ' '
            # 29: Variacion de centro de trabajo
            bl[29] = 'X' if l.vct else ' '
            # 30: Dias de incapacidad por enfermedad laboral
            bl[30] = prep_field("{:02.0f}".format(l.irl), align='right', fill='0', size=2)
            # 31: Codigo de la administradora de fondos de pensiones
            bl[31] = prep_field(l.afp_code, size=6)
            # 32: Codigo de administradora de pensiones a la cual se traslada el afiliado #TODO
            bl[32] = prep_field(l.afp_to_code, size=6)
            # 33: Codigo de EPS a la cual pertenece el afiliado
            bl[33] = prep_field(l.eps_code, size=6)
            # 34: Codigo de eps a la cual se traslada el afiliado
            bl[34] = prep_field(l.eps_to_code, size=6)
            # 35: Código CCF a la cual pertenece el afiliado
            bl[35] = prep_field(l.ccf_code, size=6)
            # 36: Numero de dias cotizados a pension
            bl[36] = prep_field("{:02.0f}".format(l.pens_days), align='right', fill='0', size=2)
            # 37: Numero de dias cotizados a salud
            bl[37] = prep_field("{:02.0f}".format(l.eps_days), align='right', fill='0', size=2)
            # 38: Numero de dias cotizados a ARL
            bl[38] = prep_field("{:02.0f}".format(l.arl_days), align='right', fill='0', size=2)
            # 39: Numero de dias cotizados a CCF
            bl[39] = prep_field("{:02.0f}".format(l.ccf_days), align='right', fill='0', size=2)
            # 40: Salario basico
            bl[40] = prep_field("{:09.0f}".format(l.wage), align='right', fill='0', size=9)
            # 41: Salario integral
            bl[41] = 'X' if l.int_wage else ' '
            # 42: IBC pension
            bl[42] = prep_field("{:09.0f}".format(l.pens_ibc), align='right', fill='0', size=9)
            # 43: IBC salud
            bl[43] = prep_field("{:09.0f}".format(l.eps_ibc), align='right', fill='0', size=9)
            # 44: IBC arl
            bl[44] = prep_field("{:09.0f}".format(l.arl_ibc), align='right', fill='0', size=9)
            # 45: IBC CCF
            bl[45] = prep_field("{:09.0f}".format(l.ccf_ibc), align='right', fill='0', size=9)
            # 46: Tarifa de aporte a pensiones
            bl[46] = prep_field("{:01.5f}".format(l.pens_rate), align='right', fill='0', size=7)
            # 47: Cotizacion pension
            bl[47] = prep_field("{:09.0f}".format(l.pens_cot), align='right', fill='0', size=9)
            # 48: Aportes voluntarios del afiliado
            bl[48] = prep_field("{:09.0f}".format(l.ap_vol_contributor), align='right', fill='0', size=9)
            # 49: Aportes voluntarios del aportante
            bl[49] = prep_field("{:09.0f}".format(l.ap_vol_company), align='right', fill='0', size=9)
            # 50: Total cotizacion pensiones
            bl[50] = prep_field("{:09.0f}".format(l.pens_total), align='right', fill='0', size=9)
            # 51: Aportes a fondo solidaridad
            bl[51] = prep_field("{:09.0f}".format(l.fsol), align='right', fill='0', size=9)
            # 52: Aportes a fondo subsistencia
            bl[52] = prep_field("{:09.0f}".format(l.fsub), align='right', fill='0', size=9)
            # 53: Valor no retenido por aportes voluntarios
            bl[53] = prep_field("{:09.0f}".format(l.ret_cont_vol), align='right', fill='0', size=9)
            # 54: Tarifa de aportes salud
            bl[54] = prep_field("{:01.5f}".format(l.eps_rate), align='right', fill='0', size=7)
            # 55: Aportes salud
            bl[55] = prep_field("{:09.0f}".format(l.eps_cot), align='right', fill='0', size=9)
            # 56: Total UPS adicional
            bl[56] = prep_field("{:09.0f}".format(l.ups), align='right', fill='0', size=9)
            # 57: Numero de autorizacion de incapacidad
            bl[57] = prep_field(l.aus_auth, size=15)
            # 58: Valor de la incapacidad por enf general
            bl[58] = prep_field("{:09.0f}".format(l.gd_amount), align='right', fill='0', size=9)
            # 59: Numero de autorizacion por licencia de maternidad
            bl[59] = prep_field(l.mat_auth, size=15)
            # 60: Valor de licencia de maternidad
            bl[60] = prep_field("{:09.0f}".format(l.mat_amount), align='right', fill='0', size=9)
            # 61: Tarifa de aportes a riesgos laborales
            bl[61] = prep_field("{:01.5f}".format(l.arl_rate), align='right', fill='0', size=9)
            # 62: Centro de trabajo
            bl[62] = prep_field(l.work_center, align='right', fill='0', size=9)
            # 63: Cotizacion obligatoria a riesgos laborales
            bl[63] = prep_field("{:09.0f}".format(l.arl_cot), align='right', fill='0', size=9)
            # 64: Tarifa de aportes CCF
            bl[64] = prep_field("{:01.5f}".format(l.ccf_rate), align='right', fill='0', size=7)
            # 65: Aportes CCF
            bl[65] = prep_field("{:09.0f}".format(l.ccf_cot), align='right', fill='0', size=9)
            # 66: Tarifa SENA
            bl[66] = prep_field("{:01.5f}".format(l.sena_rate), align='right', fill='0', size=7)
            # 67: Aportes SENA
            bl[67] = prep_field("{:09.0f}".format(l.sena_cot), align='right', fill='0', size=9)
            # 68: Tarifa ICBF
            bl[68] = prep_field("{:01.5f}".format(l.icbf_rate), align='right', fill='0', size=7)
            # 69: Aportes ICBF
            bl[69] = prep_field("{:09.0f}".format(l.icbf_cot), align='right', fill='0', size=9)
            # 70: Tarifa ESAP
            bl[70] = prep_field("{:01.5f}".format(l.esap_rate), align='right', fill='0', size=7)
            # 71: Aportes ESAP
            bl[71] = prep_field("{:09.0f}".format(l.esap_cot), align='right', fill='0', size=9)
            # 72: Tarifa MEN
            bl[72] = prep_field("{:01.5f}".format(l.men_rate), align='right', fill='0', size=7)
            # 73: Aportes MEN
            bl[73] = prep_field("{:09.0f}".format(l.men_cot), align='right', fill='0', size=9)
            # 74: Tipo de documento del cotizante principal
            bl[74] = prep_field(' ', size=2)
            # 75: Numero de documento de cotizante principal
            bl[75] = prep_field(' ', size=16)
            # 76: Exonerado de aportes a paraficales y salud
            bl[76] = 'S' if l.exonerated else 'N'
            # 77: Codigo de la administradora de riesgos laborales
            bl[77] = prep_field(l.arl_code, size=6)
            # 78: Clase de riesgo en la cual se encuentra el afiliado
            bl[78] = prep_field(l.arl_risk, size=1)
            # 79: Indicador de tarifa especial de pensiones
            bl[79] = prep_field(' ', size=1)
            # 80: Fecha de ingreso
            bl[80] = prep_field(l.k_start, size=10)
            # 81: Fecha de retiro
            bl[81] = prep_field(l.k_end, size=10)
            # 82: Fecha de inicio de VSP
            bl[82] = prep_field(l.vsp_start, size=10)
            # 83: Fecha de inicio SLN
            bl[83] = prep_field(l.sln_start, size=10)
            # 84: Fecha de fin SLN
            bl[84] = prep_field(l.sln_end, size=10)
            # 85: Fecha de inicio IGE
            bl[85] = prep_field(l.ige_start, size=10)
            # 86: Fecha de fin IGE
            bl[86] = prep_field(l.ige_end, size=10)
            # 87: Fecha de inicio LMA
            bl[87] = prep_field(l.lma_start, size=10)
            # 88: Fecha de fin LMA
            bl[88] = prep_field(l.lma_end, size=10)
            # 89: Fecha de inicio VAC
            bl[89] = prep_field(l.vac_start, size=10)
            # 90: Fecha de fin VAC
            bl[90] = prep_field(l.vac_end, size=10)

            bl[91] = prep_field(l.vct_start, size=10)
            bl[92] = prep_field(l.vct_end, size=10)
            # 93: Fecha de inicio ATEP
            bl[93] = prep_field(l.atep_start, size=10)
            # 94: Fecha de fin ATEP
            bl[94] = prep_field(l.atep_end, size=10)
            # 95: IBC otros parafiscales
            bl[95] = prep_field("{:09.0f}".format(l.other_ibc), align='right', fill='0', size=9)

            # 96: Numero de horas laboradas
            bl[96] = prep_field("{:03.0f}".format(l.w_hours), align='right', fill='0', size=3)

            bl[97] = prep_field('', size=10)

            i += 1
            bar = orm.progress_bar(i, j, bar)
            for x in bl:
                total_text += x
            total_text += break_line

            # decode and generate txt
        final_content = strip_accents(total_text.encode('utf-8', 'replace').decode('utf-8'))
        file_text = base64.b64encode(final_content)

        self.write({'file': file_text})

        return total_text

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

    @api.multi
    def load_pending(self):
        self._cr.execute("DELETE FROM pila_contract_rel where pila_id = %s" % self.id)
        if self.group_id:
            groupwh = " AND hc.group_id = {group} ".format(group=self.group_id.id)
        else:
            groupwh = " "

        calculated = ("SELECT hcfl.contract_id from hr_contribution_form_line hcfl "
                      "LEFT JOIN hr_contribution_form hcf on hcf.id = hcfl.contribution_id "
                      "WHERE hcf.period_id = {period} "
                      "group by hcfl.contract_id".format(period=self.period_id.id))
        clc = tuple([x[0] for x in orm.fetchall(self._cr, calculated)] + [0])


        active = ("SELECT hc.id FROM hr_contract hc "
                  "INNER JOIN hr_payslip hp ON hp.contract_id = hc.id "
                  "WHERE hp.liquidacion_date BETWEEN '{date_from}' AND '{date_to}' "
                  "AND hc.id not in {clc} "
                  "{groupwh} GROUP BY hc.id".format(date_from=self.period_id.start_period,
                                                    date_to=self.period_id.end_period,
                                                    clc=clc,
                                                    groupwh=groupwh))
        ca = [x[0] for x in orm.fetchall(self._cr, active)]

        for contract in ca:
            self._cr.execute("INSERT into pila_contract_rel (pila_id, contract_id) VALUES ({pila}, {contract})".format(
                pila=self.id, contract=contract))
        return True
