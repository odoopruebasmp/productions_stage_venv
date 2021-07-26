# -*- coding: utf-8 -*-
from datetime import datetime
import calendar
from calendar import monthrange as mr
import requests
import math
import os
from openerp import models, fields, api, sql_db
from openerp.addons.avancys_orm import avancys_orm as orm
from openerp.exceptions import Warning
from dateutil.relativedelta import relativedelta

CATEGORIES = [
    ('earnings', 'DEVENGADO'),
    ('o_earnings', 'OTROS DEVENGOS'),
    ('o_salarial_earnings', 'OTROS DEVENGOS SALARIALES'),
    ('o_rights', 'OTROS DERECHOS'),
    ('comp_earnings', 'INGRESOS COMPLEMENTARIOS'),
    ('non_taxed_earnings', 'INGRESOS NO GRAVADOS'),
    ('deductions', 'DEDUCCIONES'),
    ('contributions', 'APORTES'),
    ('provisions', 'PROVISIONES'),
    ('subtotals', 'SUBTOTALES'),
]

CONCEPT_LIST = [
    ('BASICO', 'SUELDO BASICO', 'earnings', ['reg', 'int', 'apr']),
    ('AUX_TRANS', 'SUBSIDIO DE TRANSPORTE', 'earnings', ['reg', 'apr']),
    ('EG_B2', 'INC ENFGENERAL 1-2', 'o_rights', ['reg', 'int', 'apr']),
    ('EG_B90', 'INC ENFGENERAL 3-90', 'o_rights', ['reg', 'int', 'apr']),
    ('EG_B180', 'INC ENFGENERAL 90-180', 'o_rights', ['reg', 'int', 'apr']),
    ('EG_A180', 'INC ENFGENERAL 180+', 'o_rights', ['reg', 'int', 'apr']),
    ('ATEP', 'INC ATEP 1 DIA', 'o_rights', ['reg', 'int', 'apr']),
    ('ATEP_P2', 'INC ATEP 1 DIA', 'o_rights', ['reg', 'int', 'apr']),
    ('MAT_LIC', 'LICENCIA DE MATERNIDAD', 'o_rights', ['reg', 'int', 'apr']),
    ('PAT_LIC', 'LICENCIA DE PATERNIDAD', 'o_rights', ['reg', 'int', 'apr']),
    ('VAC_DISF', 'VACACIONES DISFRUTADAS', 'o_rights', ['reg', 'int', 'apr']),
    ('VAC_PAG', 'VACACIONES EN DINERO', 'o_rights', ['reg', 'int', 'apr']),
    ('PRIMA', 'PRIMA', 'o_rights', ['reg']),
    ('CES', 'CESANTIAS', 'o_rights', ['reg']),
    ('ICES', 'INTERESES DE CESANTIAS', 'o_rights', ['reg']),
    ('CES_PART', 'CESANTIAS PARCIALES', 'o_rights', ['reg']),
    ('ICES_PART', 'CESANTIAS PARCIALES', 'o_rights', ['reg']),
    ('CESLY', 'CESANTIAS AÑO ANTERIOR', 'o_rights', ['reg']),
    ('ICESLY', 'INTERESES CESANTIAS AÑO ANTERIOR', 'o_rights', ['reg']),
    ('VAC_LIQ', 'VACACIONES LIQUIDACION', 'o_rights', ['reg', 'int']),
    ('CES_LIQ', 'CESANTIAS LIQUIDACION', 'non_taxed_earnings', ['reg']),
    ('ICES_LIQ', 'INTERESES CESANTIAS LIQUIDACION', 'non_taxed_earnings', ['reg']),
    ('INDEM', 'INDEMNIZACION', 'non_taxed_earnings', ['reg', 'int']),
    ('PRIM_LIQ', 'PRIMA LIQUIDACION', 'o_rights', ['reg']),
    ('IBD', 'INGRESO BASE DEDUCCIONES', 'subtotals', ['reg', 'int']),
    ('IBL', 'INGRESO BASE LABORADO', 'subtotals', ['reg', 'int', 'apr']),
    ('IBS', 'INGRESO BASE SEGURIDAD SOCIAL', 'subtotals', ['reg', 'int', 'apr']),
    ('IBP', 'INGRESO BASE PARAFISCALES', 'subtotals', ['reg', 'int']),
    ('IBR', 'INGRESO BASE RIESGOS', 'subtotals', ['reg', 'int', 'apr']),
    ('DED_PENS', 'DEDUCCION PENSION', 'deductions', ['reg', 'int']),
    ('FOND_SOL', 'FONDO DE SOLIDARIDAD', 'deductions', ['reg', 'int']),
    ('FOND_SUB', 'FONDO DE SUBSISTENCIA', 'deductions', ['reg', 'int']),
    ('DED_EPS', 'DEDUCCION SALUD', 'deductions', ['reg', 'int']),
    ('ANT', 'ANTICIPOS VENCIDOS', 'deductions', ['reg', 'int', 'apr']),
    ('BRTF', 'BASE RETENCION EN LA FUENTE', 'subtotals', ['reg', 'int']),
    ('RTEFTE', 'RETENCION EN LA FUENTE', 'deductions', ['reg', 'int']),
    ('RTF_PRIMA', 'RETENCION EN LA FUENTE PRIMA', 'deductions', ['reg']),
    ('RTF_INDEM', 'RETENCION EN LA FUENTE INDEMNIZACION', 'deductions', ['reg', 'int']),
    ('NETO', 'NETO A PAGAR', 'subtotals', ['reg', 'int', 'apr']),
    ('TOT_DEV', 'TOTAL DEVENGADO', 'subtotals', ['reg', 'int', 'apr']),
    ('TOT_DED', 'TOTAL DEDUCCIONES', 'subtotals', ['reg', 'int', 'apr']),
    ('NETO_CES', 'NETO A PAGAR CESANTIAS', 'subtotals', ['reg']),
    ('NETO_LIQ', 'NETO A PAGAR LIQUIDACION', 'subtotals', ['reg', 'int']),
    ('AP_PENS', 'APORTES PENSION', 'contributions', ['reg', 'int']),
    ('AP_EPS', 'APORTES SALUD', 'contributions', ['reg', 'int', 'apr']),
    ('AP_CCF', 'CAJA DE COMPENSACION', 'contributions', ['reg', 'int']),
    ('AP_ARL', 'APORTES ARL', 'contributions', ['reg', 'apr', 'int']),
    ('AP_SENA', 'APORTES SENA', 'contributions', ['reg', 'int']),
    ('AP_ICBF', 'APORTES ICBF', 'contributions', ['reg', 'int']),
    ('PRV_CES', 'PROVISION CESANTIAS', 'provisions', ['reg']),
    ('PRV_ICES', 'PROVISION INTERESES CESANTIAS', 'provisions', ['reg']),
    ('PRV_PRIM', 'PROVISION PRIMA', 'provisions', ['reg']),
    ('PRV_VAC', 'PROVISION VACACIONES', 'provisions', ['reg', 'int']),
    ('RET_CTG_AFC', 'RETENCION CONTINGENTE AFC', 'subtotals', ['reg', 'int']),
    ('RET_CTG_DIF_AFC', 'DIFERENCIA RETENCION CONTINGENTE AFC', 'subtotals', ['reg', 'int']),
    ('RET_CTG_FVP', 'RETENCION CONTINGENTE FONDO VOLUNTARIO', 'subtotals', ['reg', 'int']),
    ('RET_CTG_DIF_FVP', 'DIFERENCIA RETENCION CONTINGENTE FONDO VOLUNTARIO', 'subtotals', ['reg', 'int']),
    ('COSTO', 'COSTO NOMINA', 'subtotals', ['reg', 'int', 'apr']),

]

PARTNER_TYPE = [
    ('eps', 'EPS'),
    ('arl', 'ARL'),
    ('cesantias', 'CESANTIAS'),
    ('pensiones', 'PENSIONES'),
    ('caja', 'CAJA DE COMPENSACION'),
    ('other', 'OTRO'),
]

CONCEPT_ORIGIN = [
    ('regular', 'Regular'),
    ('hour', 'Horas Extra'),
    ('new', 'Novedad'),
    ('fixed', 'Concepto fijo'),
    ('leave', 'Ausencia'),
    ('loan', 'Prestamo'),
    ('import', 'Migracion'),
]

FORTNIGHT_AP = {
    ('first', 'Primera quincena'),
    ('second', 'Segunda quincena o Mensual'),
    ('both', 'Todas')
}

try:
    api_key = open('/opt/api_avancys', 'rw').read().strip('\n')
except IOError:
    api_key = 'AvancysAPI20100915'

api_host = os.environ.get('AVANCYS_API_HOST', '') or '181.143.148.61'
RESPONSE = requests.get("http://{ah}:5002/nominaapi/{k}".format(k=api_key, ah=api_host)).json()

lr = eval(RESPONSE['data'][1]['exec'])


def clear_concepts():
    return {
            'earnings': 0,
            'o_earnings': 0,
            'o_salarial_earnings': 0,
            'o_rights': 0,
            'comp_earnings': 0,
            'non_taxed_earnings': 0,
            'deductions': 0,
            'contributions': 0,
            'provisions': 0,
            'subtotals': 0
            }


def monthrange(year=None, month=None):
    today = datetime.today()
    y = year or today.year
    m = month or today.month
    return y, m, calendar.monthrange(y, m)[1]


def get_ids(data):
    if len(data) > 1:
        ids = tuple(data)
    elif len(data) == 1:
        ids = (data[0], 0)
    else:
        ids = (0, False)
    return ids


def days360(start_date, end_date, method_eu=True):

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    start_day = start_date.day
    start_month = start_date.month
    start_year = start_date.year
    end_day = end_date.day
    end_month = end_date.month
    end_year = end_date.year

    if (
        start_day == 31 or
        (
            method_eu is False and
            start_month == 2 and (
                start_day == 29 or (
                    start_day == 28 and
                    calendar.isleap(start_year) is False
                )
            )
        )
    ):
        start_day = 30

    if end_day == 31:
        if method_eu is False and start_day != 30:
            end_day = 1

            if end_month == 12:
                end_year += 1
                end_month = 1
            else:
                end_month += 1
        else:
            end_day = 30
    if end_month == 2 and end_day in (28, 29):
        end_day = 30

    return (
        end_day + end_month * 30 + end_year * 360 -
        start_day - start_month * 30 - start_year * 360 + 1
    )


def dt2f(date):
    f = date[0:4] + date[5:7] + date[8:10] if date else 0
    return f


class HrConcept(models.Model):
    _name = 'hr.concept'

    name = fields.Char('Nombre', required=True)
    code = fields.Char('Codigo', required=True)
    category = fields.Selection(CATEGORIES, 'Categoria')
    partner_type = fields.Selection(PARTNER_TYPE, 'Tipo de tercero')
    fortnight_ap = fields.Selection(FORTNIGHT_AP, 'Aplicable para', help="Aplica para periodos quincenales")
    partner_other = fields.Many2one('res.partner', 'Otro Tercero')
    reg_adm_debit = fields.Many2one('account.account', 'Debito Regular Administrativo')
    reg_adm_credit = fields.Many2one('account.account', 'Credito Regular Administrativo')
    reg_com_debit = fields.Many2one('account.account', 'Debito Regular Comercial')
    reg_com_credit = fields.Many2one('account.account', 'Credito Regular Comercial')
    reg_ope_debit = fields.Many2one('account.account', 'Debito Regular Operativa')
    reg_ope_credit = fields.Many2one('account.account', 'Credito Regular Operativa')
    int_adm_debit = fields.Many2one('account.account', 'Debito Integral Administrativo')
    int_adm_credit = fields.Many2one('account.account', 'Credito Integral Administrativo')
    int_com_debit = fields.Many2one('account.account', 'Debito Integral Comercial')
    int_com_credit = fields.Many2one('account.account', 'Credito Integral Comercial')
    int_ope_debit = fields.Many2one('account.account', 'Debito Integral Operativa')
    int_ope_credit = fields.Many2one('account.account', 'Credito Integral Operativa')
    apr_adm_debit = fields.Many2one('account.account', 'Debito Aprendiz Administrativo')
    apr_adm_credit = fields.Many2one('account.account', 'Credito Aprendiz Administrativo')
    apr_com_debit = fields.Many2one('account.account', 'Debito Aprendiz Comercial')
    apr_com_credit = fields.Many2one('account.account', 'Credito Aprendiz Comercial')
    apr_ope_debit = fields.Many2one('account.account', 'Debito Aprendiz Operativa')
    apr_ope_credit = fields.Many2one('account.account', 'Credito Aprendiz Operativa')
    documentation = fields.Html('Documentacion')

    @api.multi
    def translate_category(self, category):
        res = False
        for cat in CATEGORIES:
            if cat[1] == category:
                res = cat[0]
        return res


class HrPayslipType(models.Model):
    _inherit = 'hr.payslip.type'

    concept_ids = fields.Many2many('hr.concept', 'paysliptype_concept_rel', 'type_id', 'concept_id', string='Conceptos')


class HrVacationBook(models.Model):
    _name = 'hr.vacation.book'

    payslip_id = fields.Many2one('hr.payslip', 'Nomina')
    licences = fields.Float('Suspensiones')
    enjoyed = fields.Float('Dias disfrutados')
    payed = fields.Float('Dias pagados')
    contract_id = fields.Many2one('hr.contract', 'Contracto')


class HrConceptLog(models.Model):
    _name = 'hr.concept.log'
    _description = 'Log de computacion'

    name = fields.Char('Descripcion')
    value = fields.Float('Valor')
    concept_id = fields.Many2one('hr.payslip.concept', 'Concepto', ondelete="CASCADE")
    code = fields.Char('Codigo')
    period_id = fields.Many2one('payslip.period', 'Periodo')
    employee_id = fields.Many2one('hr.employee', 'Empleado')


class HrPayslipConcept(models.Model):
    _name = 'hr.payslip.concept'
    _order = 'category asc'

    name = fields.Char('Nombre', required=True)
    concept_id = fields.Many2one('hr.concept', 'Concepto')
    payslip_id = fields.Many2one('hr.payslip', 'Nomina', ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', 'Empleado')
    period_id = fields.Many2one('payslip.period', 'Periodo')
    contract_id = fields.Many2one('hr.contract', 'Contrato', index=True)
    run_id = fields.Many2one('hr.payslip.run', 'Lote de nomina')
    category = fields.Selection(CATEGORIES, 'Categoria')
    code = fields.Char('Codigo', required=True)
    qty = fields.Float('Cantidad', digits=(12, 2))
    rate = fields.Float('Tasa')
    amount = fields.Float('Valor')
    total = fields.Float('Total')
    origin = fields.Selection(CONCEPT_ORIGIN, 'Origen')
    ex_rent = fields.Boolean('Aporte voluntario o ingreso exento de renta')
    afc = fields.Boolean('AFC')
    computation = fields.Html('Log computación')
    concept_log = fields.One2many('hr.concept.log', 'concept_id', string="Log de auditoria")
    date = fields.Date('Fecha contabilizacion')

    @api.multi
    def get_accounts(self):
        debit_account, credit_account, partner_type = False, False, False
        type_class = self.payslip_id.contract_id.type_id.type_class
        section = self.payslip_id.contract_id.type_id.section
        debit_field = type_class[0:3] + "_" + section[0:3] + "_debit"
        credit_field = type_class[0:3] + "_" + section[0:3] + "_credit"
        partner_w = ""
        partner_other = False
        if self.origin == 'regular':
            table = 'hr_concept'
            partner_w = ', partner_other'
            if self.concept_id:
                where = "id = {id} ".format(id=self.concept_id.id)
            elif self.code:
                where = "code = '{code}' ".format(code=self.code)
            else:
                raise Warning("Concepto %s no encontrado, es necesario actualizar el modulo" % self.code)
        elif self.origin == 'hour':
            table = 'hr_payroll_extrahours_type'
            where = "code = '{code}'".format(code=self.code)
        elif self.origin == 'new':
            table = 'hr_payroll_novedades_category'
            where = "code = '{code}'".format(code=self.code)
            partner_w = ', partner_other'
        elif self.origin == 'fixed':
            table = 'hr_payroll_obligacion_tributaria_category'
            where = "code = '{code}'".format(code=self.code)
            partner_w = ', partner_other'
        elif self.origin == 'leave':
            table = 'hr_holidays_status'
            where = "code = '{code}'".format(code=self.code)
        elif self.origin == 'loan':
            table = 'hr_payroll_prestamo_category'
            where = "code = '{code}'".format(code=self.code)
            partner_w = ', partner_other'
        else:
            return None, None, False, False

        aq = "SELECT {d}, {c}, partner_type {pw} FROM {t} WHERE {w}".format(
            d=debit_field, c=credit_field, t=table, w=where, pw=partner_w)
        accounts = orm.fetchall(self._cr, aq)
        if accounts:
            debit_account = accounts[0][0]
            credit_account = accounts[0][1]
            partner_type = accounts[0][2]
            if len(accounts[0]) == 4:
                partner_other = accounts[0][3]

        return debit_account, credit_account, partner_type, partner_other


class ResCompany(models.Model):
    _inherit = 'res.company'

    simple_provisions = fields.Boolean('Calculo de provisiones simple',
                                       help="Permite calcular las provisiones basados en el metodo de porcentaje y no "
                                            "en consolidacion")
    rtf_projection = fields.Boolean('Calculo de retencion en la fuente proyectada en primera quincena')
    ded_round = fields.Boolean('Redondeo de deducciones EPS,PEN,FSO')
    rtf_round = fields.Boolean('Redondeo de retencion en la fuente')
    aux_apr_prod = fields.Boolean('Auxilio de transporte a aprendices en etapa productiva')
    fragment_vac = fields.Boolean('Vacaciones fragmentadas')
    prv_vac_cpt = fields.Boolean('Provision de vacaciones por conceptos')
    aux_prst = fields.Boolean('Incorporacion de auxilio de transporte en prestaciones sin promediar')
    aus_prev = fields.Boolean('Pago de ausencias de periodos anteriores')
    nonprofit = fields.Boolean('Empresa sin animo de lucro',
                               help="Salta las validaciones de topes para pago de parafiscales")
    image_certification = fields.Binary('Firma ceritificaciones laborales')


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    concept_ids = fields.One2many('hr.payslip.concept', 'payslip_id', string="Conceptos")
    earning_ids = fields.One2many('hr.payslip.concept', string="Devengos", compute="_get_categ_list")
    deduction_ids = fields.One2many('hr.payslip.concept', string="Deducciones", compute="_get_categ_list")
    contribution_ids = fields.One2many('hr.payslip.concept', string="Aportes", compute="_get_categ_list")
    provision_ids = fields.One2many('hr.payslip.concept', string="Provisiones", compute="_get_categ_list")
    other_ids = fields.One2many('hr.payslip.concept', string="Otros", compute="_get_categ_list")
    force_ibc = fields.Float('Forzar IBC', help="Para efectos de migración estipular el valor del IBC del periodo para "
                                                "ser tenido en cuenta en la liquidación de ausencias")
    neto = fields.One2many('hr.payslip.concept', string="Neto a pagar", compute="_get_categ_list")

    # Para ser utilizada en qweb
    @api.multi
    def days360(self, start_date, end_date, method_eu=True):

        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

        start_day = start_date.day
        start_month = start_date.month
        start_year = start_date.year
        end_day = end_date.day
        end_month = end_date.month
        end_year = end_date.year

        if (
                start_day == 31 or
                (
                        method_eu is False and
                        start_month == 2 and (
                                start_day == 29 or (
                                    start_day == 28 and
                                    calendar.isleap(start_year) is False
                                )
                        )
                )
        ):
            start_day = 30

        if end_day == 31:
            if method_eu is False and start_day != 30:
                end_day = 1

                if end_month == 12:
                    end_year += 1
                    end_month = 1
                else:
                    end_month += 1
            else:
                end_day = 30
        if end_month == 2 and end_day in (28, 29):
            end_day = 30

        return (
                end_day + end_month * 30 + end_year * 360 -
                start_day - start_month * 30 - start_year * 360 + 1
        )

    @api.one
    @api.depends('concept_ids')
    def _get_categ_list(self):
        if self.ids:
            earnings = orm.fetchall(self._cr, "SELECT id FROM hr_payslip_concept "
                                              "WHERE category in ('earnings', 'o_earnings', 'o_salarial_earnings', "
                                              "'comp_earnings', 'non_taxed_earnings', 'o_rights') "
                                              "and payslip_id = {p} ORDER BY category, code".format(p=self.id))
            if earnings:
                earnings = [x[0] for x in earnings]
            else:
                earnings = []
            self.earning_ids = self.env['hr.payslip.concept'].browse(earnings)

            deductions = orm.fetchall(self._cr, "SELECT id FROM hr_payslip_concept "
                                                "WHERE category = 'deductions' and payslip_id = {p}".format(p=self.id))
            if deductions:
                deductions = [x[0] for x in deductions]
            else:
                deductions = []
            self.deduction_ids = self.env['hr.payslip.concept'].browse(deductions)

            contributions = orm.fetchall(self._cr, "SELECT id FROM hr_payslip_concept "
                                                   "WHERE category = 'contributions' and payslip_id={p}".format(p=self.id))
            if contributions:
                contributions = [x[0] for x in contributions]
            else:
                contributions = []
            self.contribution_ids = self.env['hr.payslip.concept'].browse(contributions)

            provisions = orm.fetchall(self._cr, "SELECT id FROM hr_payslip_concept "
                                                   "WHERE category = 'provisions' and payslip_id={p}".format(p=self.id))
            if provisions:
                provisions = [x[0] for x in provisions]
            else:
                provisions = []
            self.provision_ids = self.env['hr.payslip.concept'].browse(provisions)

            others = orm.fetchall(self._cr, "SELECT id FROM hr_payslip_concept "
                                            "WHERE category not in ('provisions','contributions', 'deductions', "
                                            "'earnings', 'o_earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights', "
                                            "'non_taxed_earnings')  and payslip_id={p} and code != 'NETO'"
                                            "ORDER BY category, code".format(p=self.id))
            if others:
                others = [x[0] for x in others]
            else:
                others = []
            self.other_ids = self.env['hr.payslip.concept'].browse(others)

            neto = orm.fetchall(self._cr, "SELECT id FROM hr_payslip_concept "
                                          "WHERE code in ('NETO', 'NETO_CES', 'NETO_LIQ') "
                                          "AND payslip_id={p}".format(p=self.id))
            if neto:
                neto = [x[0] for x in neto]
            else:
                neto = []
            self.neto = self.env['hr.payslip.concept'].browse(neto)

    @api.multi
    def unlink(self):
        for payslip in self:
            if payslip.tipo_nomina.code == 'Liquidacion':
                raise Warning("No es posible borrar una nomina de tipo liquidacion."
                              "Debe hacerlo desde el contrato a través del botón 'Reintegrar Contrato'")

        res = super(HrPayslip, self).unlink()
        return res

    @api.model
    def reset_globals(self):
        # noinspection PyGlobalUndefined
        global lr
        lr = eval(RESPONSE['data'][1]['exec'])

    @api.multi
    def compute_slip(self):
        self_ids = get_ids(self._ids)
        query_s2comp = """
            SELECT id from hr_payslip where id in {ids} and state in ('draft', 'verify')
        """.format(ids=self_ids)
        slips2comp = self.browse(x[0] for x in orm.fetchall(self._cr, query_s2comp))
        i, j = 0, len(slips2comp)
        bar = orm.progress_bar(i, j)
        sequence_obj = self.env['ir.sequence']

        for slip in slips2comp:
            # Validacion de duplicidad en trikey emp-tipo-periodo
            constraint = ("SELECT id FROM hr_payslip "
                          "WHERE employee_id = {e} AND payslip_period_id = {p} "
                          "AND tipo_nomina = {t} AND id != {i}".format(e=slip.employee_id.id,
                                                                       p=slip.payslip_period_id.id,
                                                                       t=slip.tipo_nomina.id,
                                                                       i=slip.id))
            duplicated = orm.fetchall(self._cr, constraint)
            if duplicated and slip.tipo_nomina.code not in ('Vacaciones', 'Liquidacion', 'Otros'):
                raise Warning(u"No puede existir mas de una nomina del "
                              u"mismo tipo y periodo para el empleado {e}".format(e=slip.employee_id.name))

            number = slip.number or sequence_obj.get('salary.slip')
            name = 'Nomina de ' + str(slip.contract_id.name.encode('utf-8'))
            orm.direct_update(self._cr, 'hr_payslip', {'number': number, 'name': name}, ('id', slip.id))

            slip.reckon_extrahours()
            slip.reckon_novedades()
            slip.reckon_loans()
            slip.reckon_obligaciones()

            # Calculo de embargos dependiendo si existe el modulo
            embargos = orm.fetchall(self._cr, "SELECT state from ir_module_module where name = 'hr_payroll_embargos'")
            if embargos and embargos[0][0] == 'installed':
                slip.compute_embargos()

            # Calculo de distribucion analitica para turnos
            roster = orm.fetchall(self._cr, "SELECT state from ir_module_module where name = 'hr_roster'")
            if roster and roster[0][0] == 'installed':
                slip.compute_dist()

            # Calculando worked days
            worked_days_line_ids = slip.get_worked_day_lines()
            self._cr.execute("DELETE from hr_payslip_worked_days where payslip_id = {pid}".format(pid=slip.id))
            for worked_day in worked_days_line_ids:
                worked_day['payslip_id'] = slip.id
            orm.direct_create(self._cr, self._uid, 'hr_payslip_worked_days', worked_days_line_ids)
            slip.compute_concepts()
            i += 1
            bar = orm.progress_bar(i, j, bar, slip.id)

        return True

    @api.multi
    def compute_concepts(self):
        #########################################
        #          Variables generales          #
        #########################################

        p_daysq = orm.fetchall(self._cr, "SELECT code, number_of_days "
                                         "FROM hr_payslip_worked_days "
                                         "WHERE payslip_id = %s" % self.id)
        p_days = {}
        if p_daysq:
            for d in p_daysq:
                p_days[d[0]] = d[1]

        wd = orm.fetchall(self._cr, "SELECT number_of_days "
                                    "FROM hr_payslip_worked_days "
                                    "WHERE payslip_id = %s AND code = 'WORK102'" % self.id)
        if wd:
            wd = wd[0][0]
        else:
            wd = 0.0
        bmt = self.payslip_period_id.bm_type
        sch_pay = self.payslip_period_id.schedule_pay
        contract = self.contract_id
        period = self.payslip_period_id
        first_fortnight = False
        ff_category = clear_concepts()

        # Dias trabajados en el mismo periodo de otras nominas
        wd_oq = ("SELECT number_of_days "
                 "FROM hr_payslip_worked_days wd "
                 "INNER JOIN hr_payslip hp ON hp.id = wd.payslip_id "
                 "INNER JOIN payslip_period pp on pp.id = hp.payslip_period_id "
                 "INNER JOIN hr_payslip_type hpt on hpt.id = hp.tipo_nomina "
                 "WHERE pp.start_period::VARCHAR like '{month}%' "
                 "AND hp.contract_id = {contract} "
                 "AND hp.id != {payslip} "
                 "AND hpt.code in ('Nomina', 'Otros') "
                 "AND wd.code = 'WORK102'".format(
            month=self.payslip_period_id.start_period[0:7],
            contract=contract.id,
            payslip=self.id))
        wd_other = orm.fetchall(self._cr, wd_oq)

        wd_month = wd + sum([x[0] for x in wd_other])
        # datos de primera quincena si la actual es segunda quincena
        if sch_pay == 'bi-monthly' and bmt == 'second':
            ff_query = "SELECT hp.id from hr_payslip hp " \
                       "INNER JOIN payslip_period pp ON pp.id = hp.payslip_period_id " \
                       "WHERE hp.contract_id = {contract} " \
                       "AND pp.start_period::VARCHAR like '{month}%' " \
                       "AND pp.bm_type = 'first' and pp.schedule_pay = 'bi-monthly'".format(
                contract=contract.id, month=period.start_period[0:7])
            ff = orm.fetchall(self._cr, ff_query)
            if ff:
                # Si existe una primera quincena se asigna variable y totaliza categorias para calculos futuros
                first_fortnight = self.env['hr.payslip'].browse(ff[0][0])
                ff_cat_query = "SELECT category, sum(total) as total " \
                               "FROM hr_payslip_concept " \
                               "WHERE payslip_id = {ff} GROUP BY category".format(ff=ff[0][0])
                ff_category_sql = orm.dictfetchall(self._cr, ff_cat_query)
                for ff_cat in ff_category_sql:
                    if ff_cat['category'] in ff_category:
                        ff_category[ff_cat['category']] += ff_cat['total']
                    else:
                        ff_category[ff_cat['category']] = ff_cat['total']
                # wd_ff = orm.fetchall(self._cr, "SELECT number_of_days "
                #                                "FROM hr_payslip_worked_days "
                #                                "WHERE payslip_id = %s AND code = 'WORK102'" % ff[0][0])
                # if wd_ff:
                #     wd_ff = wd_ff[0][0]
                # else:
                #     wd_ff = 0.0
                # wd_month += wd_ff

        pslp_query = "SELECT hp.id from hr_payslip hp " \
                     "INNER JOIN payslip_period pp ON pp.id = hp.payslip_period_id " \
                     "WHERE hp.contract_id = {contract} " \
                     "AND pp.start_period <= '{end}%' " \
                     "AND pp.end_period >= '{start}%' " \
                     "AND hp.id != {p}".format(contract=contract.id,
                                               start=period.start_period[0:7] + '-01',
                                               end=period.end_period,
                                               p=self.id)
        pslp_query = orm.fetchall(self._cr, pslp_query)
        payslips_month = self.env['hr.payslip'].browse([x[0] for x in pslp_query] if pslp_query else False)
        contract_class = contract.type_id.type_class
        e_v = self.env['variables.economicas']
        aux_ev = e_v.getValue('AUXTRANSPORTE', self.liquidacion_date) or 0.0
        sal_min_ev = e_v.getValue('SMMLV', self.liquidacion_date) or 0.0
        wage = contract.wage if not contract.smmlv else sal_min_ev
        uvt = e_v.getValue('UVT', self.liquidacion_date) or 0.0
        slip_type = self.tipo_nomina.code
        company = self.company_id

        # Limpieza de conceptos previos
        concepts = {}
        categories = clear_concepts()

        # IBC
        # ibcma = self.ibcma(self.liquidacion_date, contract=contract.id) if self.leave_ids else False

        self._cr.execute("DELETE FROM hr_payslip_concept WHERE payslip_id = %s" % self.id)

        #########################################
        #         Inicializacion dict           #
        #########################################

        ld = {
            'p_days': p_days,  # Detalle de dias de la nomina en curso
            'wd': wd,  # Dias trabajados del periodo de la nomina
            'sch_pay': sch_pay,  # Pago programado (mensual o quincenal)
            'bmt': bmt,  # Tipo de quincena
            'categories': categories,  # Acumulado de categorias, actualizable despues de cada calculo
            'concepts': concepts,  # Conceptos planos
            'contract': contract,
            'period': period,  # Periodo de nomina completo payslip.period
            'payslips_month': payslips_month,  # Nominas generadas del mismo empleado y mismo mes exceptuando el self
            'first_fortnight': first_fortnight,  # payslip correspondiente a primera quincena cuando aplique
            'ff_category': ff_category,  # Acumulado de categorias para la primera quincena si existe
            'wd_month': wd_month,  # Dias trabajados en el mes
            'wage': wage,
            'contract_class': contract_class,
            'aux_ev': aux_ev,
            'sal_min_ev': sal_min_ev,  # Salario minimo desde variables economicas
            'uvt': uvt,
            'slip_type': slip_type,
            'company': company,
        }

        #########################################
        #            Virtualizacion             #
        #########################################

        # Novedades
        p_ids = list([x.id for x in self.novedades_ids])
        p_ids.append(0)
        if len(p_ids) > 1:
            p_query = ("SELECT hpnc.code, sum(hpn.total), hpnc.concept_category, hpnc.name, sum(hpn.cantidad), "
                       "hpnc.ex_rent OR hpnc.ded_rent, hpnc.afc "
                       "FROM hr_payroll_novedades hpn "
                       "INNER JOIN hr_payroll_novedades_category hpnc ON hpn.category_id = hpnc.id "
                       "WHERE hpn.id in {ids} "
                       "GROUP BY hpnc.id".format(ids=tuple(p_ids)))
            tot_nov = orm.fetchall(self._cr, p_query)
            if tot_nov:
                for nov in tot_nov:
                    if nov[2] is None:
                        raise Warning("La categoria de la novedad {nov} no tiene definida "
                                      "una categoria de concepto".format(nov=nov[0]))
                    res = nov[1]/nov[4], nov[4], 100
                    concept, category, cname, origin, ex_rent, afc = nov[0], nov[2], nov[3], 'new', nov[5], nov[6] or False
                    if concept in CONCEPT_LIST:
                        raise Warning(u"La categoria de la noviedad {c} tiene un codigo reservado, "
                                      u"por favor asigne otro".format(c=concept))
                    ld['concepts'][concept] = self.prep_concept(concept, category, cname, res,
                                                                origin=origin, ex_rent=ex_rent, afc=afc)
                    ld['categories'] = self.subt_cat(ld['concepts'][concept], categories)

        # Prestamos
        p_ids = list([x.id for x in self.prestamos_ids])
        p_ids.append(0)
        if len(p_ids) > 1:
            p_query = "SELECT hpcc.code, sum(hpc.cuota), hpcc.concept_category, hpcc.name " \
                      "FROM hr_payroll_prestamo_cuota hpc " \
                      "INNER JOIN hr_payroll_prestamo_category hpcc ON hpc.category_id = hpcc.id " \
                      "WHERE hpc.id in {ids} " \
                      "GROUP BY hpcc.id".format(ids=tuple(p_ids))

            tot_pre = orm.fetchall(self._cr, p_query)
            if tot_pre:
                for pres in tot_pre:
                    if pres[2] is None:
                        raise Warning("La categoria del prestamo {nov} no tiene definida "
                                      "una categoria de concepto".format(nov=pres[0]))
                    res = pres[1], 1, 100
                    concept, category, cname, origin = pres[0], pres[2], pres[3], 'loan'
                    if concept in CONCEPT_LIST:
                        raise Warning(u"La categoria de prestamo {c} tiene un codigo reservado, "
                                      u"por favor asigne otro".format(c=concept))
                    ld['concepts'][concept] = self.prep_concept(concept, category, cname, res, origin=origin)
                    ld['categories'] = self.subt_cat(ld['concepts'][concept], categories)

        # Conceptos fijos
        p_idsq = orm.fetchall(self._cr, "SELECT id from hr_payslip_obligacion_tributaria_line "
                                        "WHERE payslip_id = {id}".format(id=self.id))
        p_ids = list(x[0] for x in p_idsq)
        p_ids.append(0)
        if len(p_ids) > 1:
            c_query = ("SELECT otc.code, sum(otl.valor), otc.concept_category, otc.name, otc.worked_days_depends, "
                       "otc.ex_rent OR otc.ded_rent, otc.afc "
                       "FROM hr_payslip_obligacion_tributaria_line otl "
                       "INNER JOIN hr_payroll_obligacion_tributaria ot ON ot.id = otl.obligacion_id "
                       "INNER JOIN hr_payroll_obligacion_tributaria_category otc ON otc.id = ot.category_id "
                       "WHERE otl.id in {ids} "
                       "GROUP BY otc.id".format(ids=tuple(p_ids)))
            tot_con = orm.fetchall(self._cr, c_query)
            if not tot_con:
                # EJECUTAR CON CURSOR NUEVO CUANDO LOS DATOS NO SON VISIBLES CON EL MISMO CURSOR
                new_cr = sql_db.db_connect(self._cr.dbname).cursor()
                with api.Environment.manage():
                    new_cr.execute(c_query)
                    tot_con = new_cr.fetchall()
                    new_cr.close()

            if tot_con:
                for con in tot_con:
                    paid_q = self.get_interval_concept(con[0], period.start_period, period.end_period)
                    if paid_q:
                        continue
                    if con[2] is None:
                        raise Warning("La categoria del concepto fijo {nov} no tiene definida "
                                      "una categoria de concepto".format(nov=con[0]))
                    worked_depends = con[4]
                    if worked_depends:
                        if 'WORK101' in p_days:
                            c_amount = con[1] / 30
                            res = c_amount, wd, 100
                            if c_amount == 0:
                                continue
                        else:
                            continue
                    else:
                        res = con[1], 1, 100, 'fixed'

                    concept, category, cname, origin, ex_rent, afc = con[0], con[2], con[3], 'fixed', con[5], con[6] or False
                    if concept in CONCEPT_LIST:
                        raise Warning(u"La categoria de concepto fijo {c} tiene un codigo reservado, "
                                      u"por favor asigne otro".format(c=concept))
                    ld['concepts'][concept] = self.prep_concept(concept, category, cname, res,
                                                                origin=origin, ex_rent=ex_rent, afc=afc)
                    ld['categories'] = self.subt_cat(ld['concepts'][concept], categories)

        # Horas extra
        p_ids = list([x.id for x in self.extrahours_ids])
        p_ids.append(0)
        if len(p_ids) > 1:
            e_query = "SELECT hpec.code, sum(hpe.total), hpec.concept_category, hpec.name, sum(hpe.duracion), " \
                      "hpec.skip_payment " \
                      "FROM hr_payroll_extrahours hpe " \
                      "INNER JOIN hr_payroll_extrahours_type hpec ON hpe.type_id = hpec.id " \
                      "WHERE hpe.id in {ids} " \
                      "GROUP BY hpec.id".format(ids=tuple(p_ids))
            tot_he = orm.fetchall(self._cr, e_query)
            if tot_he:
                for hext in tot_he:
                    if hext[5]:
                        continue
                    if hext[2] is None:
                        raise Warning("El tipo de hora extra {hext} no tiene definida "
                                      "una categoria de concepto".format(hext=hext[0]))
                    res = hext[1] / hext[4], hext[4], 100
                    concept, category, cname, origin = hext[0], hext[2], hext[3], 'hour'
                    if concept in CONCEPT_LIST:
                        raise Warning(u"El tipo de hora extra {c} tiene un codigo reservado, "
                                      u"por favor asigne otro".format(c=concept))
                    ld['concepts'][concept] = self.prep_concept(concept, category, cname, res, origin=origin)
                    ld['categories'] = self.subt_cat(ld['concepts'][concept], categories)

        # Ausencias, no se puede realizar por sql dada la naturaleza de campo function de los leaves
        """
        Se calculan automaticamente todas las ausencias que no sean de tipo enfermedad general ni vacaciones 
        ya que este calculo se realiza posteriormente en conceptos individuales. No se incluyen porque tienen un 
        tratamiento contable diferente dependiendo de varias situaciones
        """
        leave_data = {}
        if self.leave_ids:
            ord_leave_days = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                                                    and not x.holiday_status_id.general_illness
                                                                    and not x.holiday_status_id.maternal_lic
                                                                    and not x.holiday_status_id.paternal_lic
                                                                    and not x.holiday_status_id.atep
                                                                    and not x.holiday_status_id.vacaciones)
            # Ausencias dentro del periodo #########
            for lday in ord_leave_days:
                aust = lday.holiday_id.holiday_status_id
                calc_type = 'ibc' if aust.ibc else 'wage'
                if calc_type == 'ibc':
                    base = lday.holiday_id._ibc()[0] * 30
                else:
                    base = contract.wage
                if aust.no_payable:
                    base = 0
                if aust.code not in leave_data:
                    leave_data[aust.code] = {
                        'code': aust.code,
                        'total': lday.days_payslip * base / 30,
                        'category': aust.concept_category,
                        'name': aust.name,
                        'qty': lday.days_payslip,
                        'ex_rent': aust.ex_rent,
                    }
                else:
                    leave_data[aust.code]['total'] += lday.days_payslip * base / 30
                    leave_data[aust.code]['qty'] += lday.days_payslip

            # Ausencias de otros periodos ##################
            for leave in self.leave_ids.filtered(lambda x: not x.holiday_status_id.general_illness
                                                 and not x.holiday_status_id.maternal_lic
                                                 and not x.holiday_status_id.paternal_lic
                                                 and not x.holiday_status_id.atep
                                                 and not x.holiday_status_id.vacaciones):
                aust = leave.holiday_status_id
                if leave.holiday_status_id.sub_wd:
                    for leave_day in leave.line_ids:
                        prev_period = leave_day.name[5:7] < period.start_period[5:7]
                        not_payed = leave_day.state == 'validate'
                        if prev_period and not_payed:
                            calc_type = 'ibc' if aust.ibc else 'wage'
                            if calc_type == 'ibc':
                                base = leave._ibc()[0] * 30
                            else:
                                base = contract.wage
                            if aust.no_payable:
                                base = 0
                            if aust.code not in leave_data:
                                leave_data[aust.code] = {
                                    'code': aust.code,
                                    'total': leave_day.days_payslip * base / 30,
                                    'category': aust.concept_category,
                                    'name': aust.name,
                                    'qty': leave_day.days_payslip,
                                    'ex_rent': aust.ex_rent,
                                }
                            else:
                                leave_data[aust.code]['total'] += leave_day.days_payslip * base / 30
                                leave_data[aust.code]['qty'] += leave_day.days_payslip

            if leave_data:
                for aust in leave_data:
                    if not leave_data[aust]['category']:
                        raise Warning("El tipo de ausencia {aust} no tiene definida "
                                      "una categoria de concepto".format(aust=leave_data[aust]['code']))
                    if leave_data[aust]['qty'] == 0:
                        raise Warning("Una de las ausencias %s no tiene dias asignados" % self.leave_ids)
                    res = leave_data[aust]['total'] / leave_data[aust]['qty'], leave_data[aust]['qty'], 100
                    concept, category, origin = leave_data[aust]['code'], leave_data[aust]['category'], 'leave'
                    ex_rent = leave_data[aust]['ex_rent']
                    cname = leave_data[aust]['name']
                    if concept in CONCEPT_LIST:
                        raise Warning(u"El tipo de ausencia {c} tiene un codigo reservado, "
                                      u"por favor asigne otro".format(c=concept))
                    ld['concepts'][concept] = self.prep_concept(concept, category, cname, res,
                                                                origin=origin, ex_rent=ex_rent)
                    ld['categories'] = self.subt_cat(ld['concepts'][concept], categories)

        #########################################
        #         Calculo de conceptos          #
        #########################################
        # time_report = {}
        for i in CONCEPT_LIST:
            # time_start = datetime.now()
            concept, cname, category, ap_class = [x for x in i]
            class_cond = True if contract_class in ap_class else False
            calculated = True
            type_concept = False
            bm_cond = False
            # Por rendimiento se plantea condicionales en secuencia
            if class_cond:
                calculated = True if concept in ld['concepts'] else False

            # Se verifica que el concepto este relacionado al tipo de nomina que se va a calcular para omitir el calculo
            if not calculated:
                tc_qry = ("SELECT pcrel.concept_id, hc.fortnight_ap FROM paysliptype_concept_rel pcrel "
                          "INNER JOIN hr_concept hc ON pcrel.concept_id = hc.id "
                          "WHERE hc.code = '{concept}' "
                          "AND pcrel.type_id = {type} ".format(concept=concept, type=self.tipo_nomina.id))
                type_concept = orm.fetchall(self._cr, tc_qry)
            # Se verifica que el concepto aplique para el tipo de quincena en caso de ser quincenal
            if type_concept:
                if sch_pay == 'bi-monthly':
                    if type_concept[0][1] == 'both' or type_concept[0][1] == bmt:
                        bm_cond = True
                elif sch_pay == 'monthly':
                    bm_cond = True
            if bm_cond:
                res = eval('self._' + str(concept).lower() + '(ld)')
                if res[3] != 'na':
                    ld['concepts'][concept] = self.prep_concept(concept, category, cname, res, name=res[3],
                                                                origin=res[4], total=res[5], comp=res[6], logtxt=res[7])
                    ld['categories'] = self.subt_cat(ld['concepts'][concept], categories)

            # time_end = datetime.now()
            # time_report[i[0]] = (time_end - time_start).microseconds

            self.reset_globals()

        # for concept in time_report:
        #     print("{c}|{t}".format(c=concept, t=time_report[concept]))

        #########################################
        #         Creacion de conceptos         #
        #########################################

        for x in ld['concepts']:
            log = []
            if 'computation_obj' in ld['concepts'][x] and ld['concepts'][x]['computation_obj'] != '':
                for comp in ld['concepts'][x]['computation_obj']:
                    log_data = {
                        'name': comp[0],
                        'value': comp[1],
                        'concept_id': False,
                        'code': ld['concepts'][x]['code'],
                        'employee_id': ld['concepts'][x]['employee_id'],
                        'period_id': ld['concepts'][x]['period_id'],
                    }
                    log.append(log_data)
            ld['concepts'][x].pop('computation_obj', None)
            concept_id = orm.direct_create(self._cr, self._uid, 'hr_payslip_concept', [ld['concepts'][x]])[0][0]
            for log_data in log:
                log_data['concept_id'] = concept_id
            orm.direct_create(self._cr, self._uid, 'hr_concept_log', log)

        # orm.direct_create(self._cr, self._uid, 'hr_payslip_concept', [ld['concepts'][x] for x in ld['concepts']])

        return True

    @api.multi
    def get_concept(self, code):
        concept = orm.dictfetchall(self._cr, "SELECT id, code, name, category FROM hr_concept WHERE code = '%s'" % code)
        return concept

    @api.multi
    def prep_concept(self, concept, category, cname, data, name="", origin='regular',
                     total='', ex_rent=False, comp='', afc=False, logtxt=''):
        hc = self.get_concept(concept.upper())
        ex_rent = False if ex_rent in (None, False) else True
        if total == '':
            total = data[0] * data[1] * data[2] / 100
        else:
            total = total
        if hc:
            hc = hc[0]
            res = {
                'concept_id': hc['id'],
                'payslip_id': self.id,
                'employee_id': self.employee_id.id,
                'contract_id': self.contract_id.id,
                'run_id':  self.payslip_run_id.id if self.payslip_run_id else False,
                'period_id': self.payslip_period_id.id,
                'date': self.liquid_date,
                'code': hc['code'],
                'name': name or hc['name'],
                'category': hc['category'],
                'amount': data[0],
                'qty': data[1],
                'rate': data[2],
                'origin': origin,
                'total': total,
                'ex_rent': ex_rent,
                'afc': afc,
                'computation_obj': comp,
                'computation': logtxt,
            }
        else:
            res = {
                'concept_id': False,
                'payslip_id': self.id,
                'employee_id': self.employee_id.id,
                'contract_id': self.contract_id.id,
                'run_id': self.payslip_run_id.id if self.payslip_run_id else False,
                'period_id': self.payslip_period_id.id,
                'date': self.liquid_date,
                'code': concept,
                'name': cname,
                'category': category,
                'amount': data[0],
                'qty': data[1],
                'rate': data[2],
                'origin': origin,
                'total': total,
                'ex_rent': ex_rent,
                'afc': afc,
                'computation_obj': comp,
                'computation': logtxt,
            }
        return res

    @api.multi
    def subt_cat(self, concept, categories):
        for cat in categories:
            if cat == concept['category']:
                categories[cat] += concept['total']
                break
        return categories

    @api.multi
    def get_payslip_concept(self, concept):
        pc = orm.fetchall(self._cr, "SELECT id FROM hr_payslip_concept "
                                    "WHERE code = '{code}' and payslip_id = {p}".format(code=concept, p=self.id))
        return self.env['hr.payslip.concept'].browse([x for x in pc[0]] if pc else False)

    @api.multi
    def get_payslip_concept_total(self, concept):
        pc = orm.fetchall(self._cr, "SELECT total FROM hr_payslip_concept "
                                    "WHERE code = '{code}' and payslip_id = {p}".format(code=concept, p=self.id))
        return pc[0][0] if pc and pc[0][0] is not None else 0

    @api.multi
    def get_payslip_category(self, category):
        pc = orm.fetchall(self._cr, "SELECT sum(total) "
                                    "FROM hr_payslip_concept "
                                    "WHERE category = '{category}' "
                                    "AND payslip_id = {p}".format(category=category, p=self.id))
        return pc[0][0] if pc[0][0] is not None else 0

    @api.multi
    def get_interval_category(self, category, start, end, exclude=(), contract=False):
        exception = ''
        prefetch_q = ("SELECT id FROM hr_payslip_concept "
                      "WHERE category = '{category}' "
                      "AND contract_id = {contract}".format(category=category,contract=contract or self.contract_id.id))
        prefetch = orm.fetchall(self._cr, prefetch_q)

        if prefetch:
            if len(prefetch) > 1:
                pre_ids = tuple([x[0] for x in prefetch])
            else:
                pre_ids = (prefetch[0][0], 0)
            for code in exclude:
                exception += " AND hpc.code != '%s' " % code
            catq = ("SELECT SUBSTRING (hpp.start_period::VARCHAR, 1, 7), sum(hpc.total) "
                    "FROM hr_payslip_concept hpc "
                    "INNER JOIN hr_payslip hp on hpc.payslip_id = hp.id "
                    "INNER JOIN payslip_period hpp ON hpp.id = hp.payslip_period_id "
                    "WHERE hpp.end_period >= '{start}' "
                    "AND hpp.start_period <= '{end}' "
                    "{exception} "
                    "AND hpc.id IN {prefetch} "
                    "GROUP BY SUBSTRING (hpp.start_period::VARCHAR, 1, 7)".format(
                        start=start,
                        end=end,
                        prefetch=pre_ids,
                        exception=exception))
            res = orm.fetchall(self._cr, catq)
        else:
            res = prefetch
        return res

    @api.multi
    def get_wage(self):
        lwq = ("SELECT wage from hr_contract_salary_change "
               "WHERE contract_id = {c} "
               "AND date <= '{dt}' "
               "ORDER BY date desc LIMIT 1".format(c=self.contract_id.id, dt=self.payslip_period_id.end_period))
        lw = orm.fetchone(self._cr, lwq)
        if lw:
            wage = lw[0]
        else:
            wage = self.contract_id.wage
        return wage

    @api.multi
    def get_interval_concept(self, concept, start, end, contract=False):
        catq = ("SELECT SUBSTRING (hpp.start_period::VARCHAR, 1, 7), sum(hpc.total) "
                "FROM hr_payslip_concept hpc "
                "INNER JOIN hr_payslip hp on hpc.payslip_id = hp.id "
                "INNER JOIN payslip_period hpp ON hpp.id = hp.payslip_period_id "
                "WHERE hpc.code = '{concept}' "
                "AND hpp.end_period >= '{start}' "
                "AND hpp.start_period <= '{end}' "
                "AND hpc.contract_id = {contract} "
                "GROUP BY SUBSTRING (hpp.start_period::VARCHAR, 1, 7)".format(
                    start=start,
                    end=end,
                    contract=self.contract_id.id if not contract else contract,
                    concept=concept))
        res = orm.fetchall(self._cr, catq)
        return res

    @api.multi
    def get_interval_avp(self, start, end, contract=False):
        catq = ("SELECT SUBSTRING (hpp.start_period::VARCHAR, 1, 7), sum(hpc.total) "
                "FROM hr_payslip_concept hpc "
                "INNER JOIN hr_payslip hp on hpc.payslip_id = hp.id "
                "INNER JOIN payslip_period hpp ON hpp.id = hp.payslip_period_id "
                "WHERE hpc.ex_rent = 't' "
                "AND hpp.end_period >= '{start}' "
                "AND hpp.start_period <= '{end}' "
                "AND hpc.contract_id = {contract} "
                "GROUP BY SUBSTRING (hpp.start_period::VARCHAR, 1, 7)".format(
                    start=start, end=end, contract=self.contract_id.id if not contract else contract))
        res = orm.fetchall(self._cr, catq)
        return res

    @api.multi
    def get_interval_concept_qty(self, concept, start, end, contract=False):
        catq = ("SELECT SUBSTRING (hpp.start_period::VARCHAR, 1, 7), sum(hpc.total), sum(hpc.qty) "
                "FROM hr_payslip_concept hpc "
                "INNER JOIN hr_payslip hp on hpc.payslip_id = hp.id "
                "INNER JOIN payslip_period hpp ON hpp.id = hp.payslip_period_id "
                "WHERE hpc.code = '{concept}' "
                "AND hpp.end_period >= '{start}' "
                "AND hpp.start_period <= '{end}' "
                "AND hpc.contract_id = {contract} "
                "GROUP BY SUBSTRING (hpp.start_period::VARCHAR, 1, 7)".format(
                    start=start,
                    end=end,
                    contract=self.contract_id.id if not contract else contract,
                    concept=concept))
        res = orm.fetchall(self._cr, catq)
        return res

    @api.multi
    def collect_days(self, start, end, contract=False):
        collectq = ("SELECT wd.code, sum(wd.number_of_days) "
                   "FROM hr_payslip_worked_days wd "
                   "INNER JOIN hr_payslip hp on hp.id = wd.payslip_id "
                   "INNER JOIN payslip_period hpp ON hpp.id = hp.payslip_period_id "
                   "AND hpp.end_period >= '{start}' "
                   "AND hpp.start_period <= '{end}' "
                   "WHERE hp.contract_id = {contract} "
                   "GROUP BY wd.code".format(start=start, end=end, contract=self.contract_id.id or contract))
        collect = orm.fetchall(self._cr, collectq)
        res = {}
        for day in range(0, len(collect)):
            res[collect[day][0]] = collect[day][1]
        return res

    @api.multi
    def global_ibc(self):
        return

    @api.multi
    def ibcma(self, date, contract=False):
        ref_date = datetime.strptime(date, "%Y-%m-%d") - relativedelta(months=1)
        month = datetime.strftime(ref_date, "%Y-%m")
        start = month + '-01'
        max_days = mr(int(month[0:4]), int(month[5:7]))[1]
        end = month + '-' + str(max_days)
        days_dict = self.collect_days(start, end, contract=contract)
        int_days_mes = days_dict['WORK101'] if 'WORK101' in days_dict else 0
        wage = self.env['hr.contract'].browse(contract or self.contract_id.id).wage
        smmlv = self.env['variables.economicas'].getValue('SMMLV', date)

        ded_inicio = days_dict['DED_INICIO'] if 'DED_INICIO' in days_dict else 0
        ded_fin = days_dict['DED_FIN'] if 'DED_FIN' in days_dict else 0
        eff_days = int_days_mes - ded_inicio - ded_fin
        if eff_days > 30:
            eff_days = 30

        earn_itv = self.get_interval_category('earnings', start, end, contract=contract)
        osal_itv = self.get_interval_category('o_salarial_earnings', start, end, contract=contract)
        comp_itv = self.get_interval_category('comp_earnings', start, end, contract=contract)
        orig_exc = ('VAC_PAG', 'VAC_LIQ', 'PRIMA', 'PRIMA_LIQ')
        orig_itv = self.get_interval_category('o_rights', start, end, exclude=orig_exc, contract=contract)
        oear_itv = self.get_interval_category('o_earnings', start, end, contract=contract)
        oear = sum([x[1] for x in oear_itv])
        # Vacaciones y prima

        sal = sum([x[1] for x in earn_itv]) + sum([x[1] for x in osal_itv]) + sum([x[1] for x in comp_itv]) + sum(
            [x[1] for x in orig_itv])
        top40 = (sal + oear) * 0.4
        # Validacion tope 40
        if oear > top40:
            base = sal + oear - top40
        else:
            base = sal

        # Valor ibc diario para comparaciones con smlv
        if eff_days:
            day_base = base / eff_days
        else:
            day_base = wage / 30

        if day_base < smmlv / 30:
            day_base = smmlv / 30

        if day_base > 25 * smmlv / 30:
            day_base = 25 * smmlv / 30
        ibs = day_base * eff_days

        return day_base, eff_days, ibs

    @api.multi
    def get_suspensions(self, start, end, contract=False):
        iquery = ("SELECT sum(hhd.days_payslip) FROM hr_holidays_days hhd "
                  "INNER JOIN hr_holidays_status hhs ON hhs.id = hhd.holiday_status_id "
                  "AND hhd.name >= '{start}' "
                  "AND hhd.name <= '{end}' "
                  "AND hhd.contract_id = {contract} "
                  "AND state in ('validate', 'paid') "
                  "AND hhs.no_payable".format(start=start, end=end, contract=self.contract_id.id))
        susp = orm.fetchall(self._cr, iquery)
        return susp[0][0] if susp[0][0] is not None else 0

    @api.multi
    def get_prst(self, date_start, date_end, ld, include=False, prst='False', nocesly=False):
        # Definiendo los dias de salario a calcular
        e_v = self.env['variables.economicas']
        plain_days = days360(date_start, date_end)
        days = plain_days

        # if not (date_start <= self.payslip_period_id.start_period <= date_end):
        #     include = False

        # Restando dias de licencia de maternidad que es tenido en cuenta como un ingreso separado
        mat_lic = self.get_interval_concept_qty('MAT_LIC', date_start, date_end)
        a_mat_lic_qty = ld['concepts']['MAT_LIC']['qty'] if 'MAT_LIC' in ld['concepts'] else 0 if include else 0
        days_mat = sum([x[2] for x in mat_lic]) + a_mat_lic_qty
        days -= days_mat

        susp = self.get_suspensions(date_start, date_end)
        days -= susp

        # Para dias negativos
        days = days if days > 0 else 0

        # Buscando cambios de salario en los ultimos 3 meses de referencia
        if datetime.strptime(date_end, "%Y-%m-%d").month >= 3:
            dt_wc = datetime.strptime(date_end, "%Y-%m-%d") - relativedelta(months=3)
        else:
            dt_wc = datetime.strptime(date_end[0:4] + "-01-01", "%Y-%m-%d")
        wcd = datetime.strftime(dt_wc, "%Y-%m-%d")
        wage_change_q = ("SELECT id "
                         "FROM hr_contract_salary_change "
                         "WHERE contract_id = {c} "
                         "AND date > '{df} 05:00:00' "
                         "AND date <= '{dt} 19:00:00'".format(
                            c=ld['contract'].id, df=wcd, dt=date_end))
        wage_change = orm.fetchall(self._cr, wage_change_q)

        # En prima siempre se toma el devengado promedio
        if prst == 'prima':
            wage_change = True

        # Calculo de salario
        a_basic = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0 if include else 0

        if not wage_change:
            wc = 0
            lwq = ("SELECT wage from hr_contract_salary_change "
                   "WHERE contract_id = {c} "
                   "AND date <= '{dt} 05:00:00' "
                   "ORDER BY date desc LIMIT 1".format(c=ld['contract'].id, dt=date_end))
            lw = orm.fetchone(self._cr, lwq)
            if lw:
                wage = lw[0]
            else:
                wage = ld['wage']
            twage = wage * days / 30

        else:
            wc = 1
            wage_q = ("SELECT date, wage "
                      "FROM hr_contract_salary_change "
                      "WHERE contract_id = {c} "
                      "AND date BETWEEN '{df}' AND '{dt}' ORDER BY date ASC".format(
                c=ld['contract'].id, df=date_start, dt=date_end))
            segments = orm.fetchall(self._cr, wage_q)
            date_step = date_start
            wag_seg = []
            count = 0
            for seg in segments:
                count += 1
                if len(segments) > count:
                    next_dt = datetime.strptime(segments[count][0][0:10], "%Y-%m-%d") - relativedelta(days=1)
                    next_dt = datetime.strftime(next_dt, "%Y-%m-%d")
                else:
                    next_dt = date_end
                ds_e = seg[0][0:10]
                if date_step == date_start and count == 1:
                    rwq = ("SELECT wage from hr_contract_salary_change "
                           "WHERE contract_id = {c} "
                           "AND date <= '{dt}' "
                           "ORDER BY date desc LIMIT 1".format(c=ld['contract'].id, dt=date_step))
                    rw = orm.fetchone(self._cr, rwq)
                    if rw:
                        ref_wag = rw[0]
                    else:
                        ref_wag = ld['wage']
                    if date_step != ds_e:
                        dt_dum = datetime.strptime(ds_e, "%Y-%m-%d") - relativedelta(days=1)
                        dum_next = datetime.strftime(dt_dum, "%Y-%m-%d")
                        wag_seg.append((date_step, dum_next, ref_wag))
                    wag_seg.append((ds_e, next_dt, seg[1]))
                    date_step = ds_e
                else:
                    wag_seg.append((ds_e, next_dt, seg[1]))
                    date_step = ds_e

            twage = 0
            segments = len(wag_seg)
            s = 1
            for sgmt in wag_seg:
                if s == segments:
                    susp_to_appy = susp
                else:
                    susp_to_appy = 0
                itv = days360(sgmt[0], sgmt[1], method_eu=True) - susp_to_appy - days_mat
                sal_seg = sgmt[2] * itv / 30
                twage += sal_seg
                s += 1
            if not twage:
                lwq = ("SELECT wage from hr_contract_salary_change "
                       "WHERE contract_id = {c} "
                       "AND date <= '{dt} 05:00:00' "
                       "ORDER BY date desc LIMIT 1".format(c=ld['contract'].id, dt=date_end))
                lw = orm.fetchone(self._cr, lwq)
                if lw:
                    wage = lw[0]
                else:
                    if self.contract_id.smmlv:
                        e_v = self.env['variables.economicas']
                        wage = e_v.getValue('SMMLV', date_end) or 0.0
                    else:
                        wage = ld['wage']
                twage = wage * days / 30
        if ld['contract'].part_time:
            twage = 0
        # Salario variable
        # Licencias de maternidad
        a_mat_lic = ld['concepts']['MAT_LIC']['total'] if 'MAT_LIC' in ld['concepts'] else 0 if include else 0
        ml_amount = sum([x[1] for x in mat_lic]) + a_mat_lic

        # Aux de transporte
        if self.env.user.company_id.aux_prst:
            aux_ev = e_v.getValue('AUXTRANSPORTE', date_end + " 05:00:00") or 0.0
            aux = aux_ev * days / 30
            days_aux = days
        else:
            a_aux = ld['concepts']['AUX_TRANS']['total'] if 'AUX_TRANS' in ld['concepts'] else 0 if include else 0
            days_aux_a = ld['concepts']['AUX_TRANS']['qty'] if 'AUX_TRANS' in ld['concepts'] else 0 if include else 0
            days_aux_o = self.get_interval_concept_qty('AUX_TRANS', date_start, date_end)
            days_aux = sum([x[2] for x in days_aux_o]) + days_aux_a
            aux_itv = self.get_interval_concept('AUX_TRANS', date_start, date_end)
            aux = sum([x[1] for x in aux_itv]) + (a_aux if include else 0)

        # Horas Extra
        a_eh = ld['categories']['comp_earnings'] if include else 0
        extra_itv = self.get_interval_category('comp_earnings', date_start, date_end)
        a_rn = ld['categories']['o_salarial_earnings'] if include else 0
        rn_itv = self.get_interval_category('o_salarial_earnings', date_start, date_end)
        extra = sum([x[1] for x in extra_itv]) + sum([x[1] for x in rn_itv]) + a_eh + a_rn

        # Ingresos salariales
        a_is = ld['categories']['earnings'] - a_basic if include else 0
        is_itv = self.get_interval_category('earnings', date_start, date_end, exclude=('BASICO',))
        sal_inc = sum([x[1] for x in is_itv]) + a_is

        # Total variables
        total_variable = ml_amount + extra + sal_inc
        total_fix = aux
        if self.env.user.company_id.aux_prst:
            salmin = e_v.getValue('SMMLV', date_end) or 0.0
            if days and (twage + sal_inc) * 30 / days > 2 * salmin:
                total_fix = 0
            else:
                total_fix = aux
        # Base de ingresos
        if (days + days_mat) < 30:
            total = twage + total_fix
        else:
            total = twage + total_variable + total_fix

        # Base de calculo
        if days:
            if days == days_aux or (days + days_mat) >= 30:
                base = total * 360 / days / 360 * 30 if days else 0
            else:
                base = (total - total_fix) * 360 / days / 360 * 30 if days else 0
                base += total_fix * 360 / days_aux / 360 * (30 - days + days_aux) if days_aux else 0
            if (days + days_mat) < 30:
                base += total_variable
        else:
            base = 0

        # Prestacion
        pres = base * days / 360

        # Prest parciales
        # Prest parciales en intervalo de referencia
        t_part = 0
        if prst == 'ces':
            part = self.get_interval_concept('CES_PART', date_start, date_end)
            cesly = self.get_interval_concept('CESLY', date_start, date_end) if not nocesly else []
            t_part = sum([x[1] for x in part]) + sum([x[1] for x in cesly])
        elif prst == 'prima':
            part = self.get_interval_concept('PRIMA', date_start, date_end)
            t_part = sum([x[1] for x in part])

        net_pres = pres - t_part
        logtxt = "<b>Extras: </b> %s, %s <br/>" % (extra_itv, a_eh)
        logtxt += "<b>Recargos: </b> %s, %s<br/>" % (rn_itv, a_rn)
        logtxt += "<b>Ingresos salariales: </b> %s, %s<br/>" % (is_itv, a_is)

        res = {
            'pres': pres,
            'days': days,
            'plain_days': plain_days,
            'net_pres': net_pres,
            'base': base,
            'twage': twage,
            'total_variable': total_variable,
            'total_fix': total_fix,
            'days_mat': days_mat,
            'wc': wc,
            'partials': t_part,
            'susp': susp,
            'log': logtxt,
        }

        return res

    ############################################################################
    # ------------------- CALCULO DE CONCEPTOS INDIVIDUALES -------------------#
    ############################################################################
    @api.multi
    def _basico(self, ld):
        """
        Sueldo basico
        :param ld:
        :return: Valor de salario asignado en el contrato y depende de los dias trabajados en el periodo
        Varia el nombre del concepto dependiendo del tipo de contrato y el rate cambia unicamente cuando es tipo
        aprendiz lectivo
        """
        if not ld['contract'].part_time:
            lr[0] = ld['wage'] / 30
            lr[1] = ld['wd'] - (ld['p_days']['PREV_AUS'] if 'PREV_AUS' in ld['p_days'] else 0)
            name = ''
            if ld['contract_class'] == 'reg':
                name = 'SUELDO BASICO'
            elif ld['contract_class'] == 'int':
                name = 'SUELDO BASICO INTEGRAL'
            elif ld['contract_class'] == 'apr':
                if ld['contract'].fiscal_type_id.code == '12':
                    name = 'CUOTA DE SOSTENIMIENTO LECTIVO'
                    lr[2] = 50
                elif ld['contract'].fiscal_type_id.code == '19':
                    start_period = ld['period'].start_period
                    end_period = ld['period'].end_period
                    name = 'CUOTA DE SOSTENIMIENTO PRODUCTIVO'
                    if start_period < ld['contract'].apr_prod_date <= end_period:
                        diff = days360(ld['contract'].apr_prod_date, end_period)
                        if diff:
                            lec_wd = ld['wd'] - diff
                            lect_amount = ld['wage'] * lec_wd / (2 * 30)
                            prod_amount = ld['wage'] * diff / 30
                            amount = lect_amount + prod_amount
                            lr[5] = amount
            else:
                raise Warning("El tipo del contrato %s no tiene definida una clase" % ld['contract'].name)
            lr[3] = name
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _aux_trans(self, ld):
        """
        Subsidio de transporte
        :param ld:
        :return: Valor de auxilio de transporte definido en variables economicas por los dias trabajados en
        el mes o periodo.
        Tambien omite el calculo si en el contrato está marcada la opcion skip_aux_trans
        Si el valor de la categoria de devengados supera el valor de dos salarios minimos se omite el pago
        """
        aux_trans_q = ("SELECT id "
                       "from hr_concept "
                       "where code = 'AUX_TRANS'")

        aux_trans_id = orm.fetchall(self._cr, aux_trans_q)[0][0]
        aux_trans = self.env['hr.concept'].browse(aux_trans_id)
        sec_pol = aux_trans.fortnight_ap == 'second'

        paid_days = 0
        skip_aux = ld['contract'].skip_aux_trans
        c_class = ld['contract_class']
        sch_pay = ld['sch_pay']
        bmt = ld['bmt']

        apr_prod = ld['contract'].fiscal_type_id.code == '19'
        if ld['wd'] != 0 and not skip_aux:
            earnings = ld['categories']['earnings']
            basic = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0
            prev_earn = sum([p.get_payslip_category('earnings') for p in ld['payslips_month']])
            prev_aux = sum([p.get_payslip_concept_total('AUX_TRANS') for p in ld['payslips_month']])
            paid_days = sum([p.get_payslip_concept('AUX_TRANS').qty for p in ld['payslips_month']])
            earnings += prev_earn - prev_aux
            if sch_pay == 'bi-monthly' and bmt == 'first':
                earnings += basic
            if earnings >= 2 * ld['sal_min_ev'] or ld['wage'] > 2 * ld['sal_min_ev']:
                res = False
            else:
                res = True
        else:
            res = False

        if self.env.user.company_id.aux_apr_prod:
            policy_val = c_class == 'reg' or (c_class == 'apr' and apr_prod)
        else:
            policy_val = c_class == 'reg'

        if res and policy_val and not ld['contract'].part_time:
            lr[0] = ld['aux_ev'] / 30
            if sch_pay == 'bi-monthly' and bmt == 'second' and sec_pol:
                lr[1] = ld['wd_month'] - paid_days - (ld['p_days']['PREV_AUS'] if 'PREV_AUS' in ld['p_days'] else 0)
            else:
                lr[1] = ld['wd'] - (ld['p_days']['PREV_AUS'] if 'PREV_AUS' in ld['p_days'] else 0)
            if ld['contract'].fiscal_type_id.code == '19':
                start_period = ld['period'].start_period
                end_period = ld['period'].end_period
                if start_period < ld['contract'].apr_prod_date <= end_period:
                    diff = days360(ld['contract'].apr_prod_date, end_period)
                    lr[1] = diff
        elif ld['contract'].part_time:
            lr[0] = ld['aux_ev'] / 30
            event = ld['concepts']['EVENTOS']['qty'] if 'EVENTOS' in ld['concepts'] else 0
            if event:
                lr[1] = event
            else:
                lr[3] = 'na'

        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _eg_b2(self, ld):
        """
        Enfermedad general de 1 y 2 dias
        :param ld:
        :return: Valor a pagar por ausencias de tipo enfermedad general que tengan entre 1 y 2 dias
        """
        # Se realiza por orm ya que este campo es un compute sin afectacion en base de datos
        eg_b2_days = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                                  and x.holiday_status_id.general_illness and 0 < x.sequence <= 2)
        lday_holiday = False
        base, amount, qty = 0, 0, 0
        for lday in eg_b2_days:
            if lday.holiday_id != lday_holiday:
                calc_type = 'ibc' if lday.holiday_status_id.ibc else 'wage'
                base = lday.holiday_id._ibc()[0] * 30 if calc_type == 'ibc' else ld['wage']
                lday_holiday = lday.holiday_id
            amount += base / 30
            qty += lday.days_payslip
            if lday.name[5:12] == '02-28' and lday.holiday_id.date_to[0:10] > lday.name:
                qty += 2
                amount += 2 * base / 30
            if lday.name[5:12] == '02-28' and ld['wd'] == 0:
                qty += 2
                amount += 2 * base / 30

        if self.env.user.company_id.aus_prev:
            for leave in self.leave_ids.filtered(lambda x: x.holiday_status_id.general_illness):
                for leave_day in leave.line_ids.filtered(lambda x: 0 < x.sequence <= 2):
                    prev_period = leave_day.name < ld['period'].start_period
                    not_payed = leave_day.state == 'validate'
                    appv_per = ld['period'].start_period <= leave.approve_date <= ld['period'].end_period
                    if prev_period and not_payed and appv_per:
                        if leave_day.holiday_id != lday_holiday:
                            calc_type = 'ibc' if leave_day.holiday_status_id.ibc else 'wage'
                            base = leave._ibc()[0] * 30 if calc_type == 'ibc' else ld['wage']
                            lday_holiday = leave
                        amount += base / 30
                        qty += leave_day.days_payslip

        if qty:
            lr[0] = amount / qty
            lr[1] = qty
            lr[2] = lday_holiday.holiday_status_id.gi_b2
            vit_min = ld['sal_min_ev'] / 30
            lr[5] = '' if lr[0] * lr[1] * lr[2] / 100 > vit_min * lr[1] else vit_min * lr[1]
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _eg_b90(self, ld):
        """
        Enfermedad general de 3 y 90 dias
        :param ld:
        :return: Valor a pagar por ausencias de tipo enfermedad general que tengan entre 3 y 90 dias
        """
        # Se realiza por orm ya que este campo es un compute sin afectacion en base de datos
        eg_b90_days = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                                   and x.holiday_status_id.general_illness and 3 <= x.sequence <= 90)
        lday_holiday = False
        base, amount, qty = 0, 0, 0
        for lday in eg_b90_days:
            if lday.name[8:10] == '31':
                continue
            if lday.holiday_id != lday_holiday:
                base = lday.holiday_id._ibc()[0] * 30
                lday_holiday = lday.holiday_id
            amount += base / 30
            qty += lday.days_payslip
            if lday.name[5:12] == '02-28' and lday.holiday_id.date_to[0:10] > lday.name:
                qty += 2
                amount += 2 * base / 30
            if lday.name[5:12] == '02-28' and ld['wd'] == 0:
                qty += 2
                amount += 2 * base / 30

        if self.env.user.company_id.aus_prev:
            for leave in self.leave_ids.filtered(lambda x: x.holiday_status_id.general_illness):
                for leave_day in leave.line_ids.filtered(lambda x: 3 <= x.sequence <= 90):

                    prev_period = leave_day.name < ld['period'].start_period
                    not_payed = leave_day.state == 'validate'
                    appv_per = ld['period'].start_period <= leave.approve_date <= ld['period'].end_period
                    if prev_period and not_payed and leave_day.name[-2:] != '31' and appv_per:
                        if leave_day.holiday_id != lday_holiday:
                            calc_type = 'ibc' if leave_day.holiday_status_id.ibc else 'wage'
                            base = leave._ibc()[0] * 30 if calc_type == 'ibc' else ld['wage']
                            lday_holiday = leave
                        amount += base / 30
                        qty += leave_day.days_payslip

        if qty:
            lr[0] = amount / qty
            lr[1] = qty
            lr[2] = lday_holiday.holiday_status_id.gi_b90
            vit_min = ld['sal_min_ev'] / 30
            lr[5] = '' if lr[0] * lr[1] * lr[2] / 100 > vit_min * lr[1] else vit_min * lr[1]
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _eg_b180(self, ld):
        """
        Enfermedad general de 90 y 180 dias
        :param ld:
        :return: Valor a pagar por ausencias de tipo enfermedad general que tengan entre 90 y 180 dias
        """
        # Se realiza por orm ya que este campo es un compute sin afectacion en base de datos
        eg_b180_days = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                                    and x.holiday_status_id.general_illness and 90 < x.sequence <= 180)
        lday_holiday = False
        base, amount, qty = 0, 0, 0
        for lday in eg_b180_days:
            if lday.holiday_id != lday_holiday:
                base = lday.holiday_id._ibc()[0] * 30
                lday_holiday = lday.holiday_id
            amount += base / 30
            qty += lday.days_payslip
            if lday.name[5:12] == '02-28' and lday.holiday_id.date_to[0:10] > lday.name:
                qty += 2
                amount += 2 * base / 30
            if lday.name[5:12] == '02-28' and ld['wd'] == 0:
                qty += 2
                amount += 2 * base / 30

        if self.env.user.company_id.aus_prev:
            for leave in self.leave_ids.filtered(lambda x: x.holiday_status_id.general_illness):
                for leave_day in leave.line_ids.filtered(lambda x: 90 < x.sequence <= 180):

                    prev_period = leave_day.name < ld['period'].start_period
                    not_payed = leave_day.state == 'validate'
                    appv_per = ld['period'].start_period <= leave.approve_date <= ld['period'].end_period
                    if prev_period and not_payed and appv_per:
                        if leave_day.holiday_id != lday_holiday:
                            calc_type = 'ibc' if leave_day.holiday_status_id.ibc else 'wage'
                            base = leave._ibc()[0] * 30 if calc_type == 'ibc' else ld['wage']
                            lday_holiday = leave
                        amount += base / 30
                        qty += leave_day.days_payslip
        if qty:
            lr[0] = amount / qty
            lr[1] = qty
            lr[2] = lday_holiday.holiday_status_id.gi_b180
            vit_min = ld['sal_min_ev'] / 30
            lr[5] = '' if lr[0] * lr[1] * lr[2] / 100 > vit_min * lr[1] else vit_min * lr[1]
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _eg_a180(self, ld):
        """
        Enfermedad general de mas de 180 dias
        :param ld:
        :return: Valor a pagar por ausencias de tipo enfermedad general que tengan de 180 dias en adelante
        """
        # Se realiza por orm ya que este campo es un compute sin afectacion en base de datos
        eg_a180_days = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                                    and x.holiday_status_id.general_illness and x.sequence > 180)
        lday_holiday = False
        base, amount, qty = 0, 0, 0
        for lday in eg_a180_days:
            if lday.holiday_id != lday_holiday:
                base = lday.holiday_id._ibc()[0] * 30
                lday_holiday = lday.holiday_id
            amount += base / 30
            qty += lday.days_payslip
            if lday.name[5:12] == '02-28' and lday.holiday_id.date_to[0:10] > lday.name:
                qty += 2
                amount += 2 * base / 30
            if lday.name[5:12] == '02-28' and ld['wd'] == 0:
                qty += 2
                amount += 2 * base / 30

        if self.env.user.company_id.aus_prev:
            for leave in self.leave_ids.filtered(lambda x: x.holiday_status_id.general_illness):
                for leave_day in leave.line_ids.filtered(lambda x: x.sequence > 180):

                    prev_period = leave_day.name < ld['period'].start_period
                    not_payed = leave_day.state == 'validate'
                    appv_per = ld['period'].start_period <= leave.approve_date <= ld['period'].end_period
                    if prev_period and not_payed and appv_per:
                        if leave_day.holiday_id != lday_holiday:
                            calc_type = 'ibc' if leave_day.holiday_status_id.ibc else 'wage'
                            base = leave._ibc()[0] * 30 if calc_type == 'ibc' else ld['wage']
                            lday_holiday = leave
                        amount += base / 30
                        qty += leave_day.days_payslip
        if qty:
            lr[0] = amount / qty
            lr[1] = qty
            lr[2] = lday_holiday.holiday_status_id.gi_a180
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _ant(self, ld):
        ants = self.advance_ids.filtered(lambda x: x.state == 'to_discount')
        total = sum([x.remaining for x in ants])
        if total:
            lr[0] = total
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _atep(self, ld):
        """
        Incapacidad por accidente de trabajo del primer dia
        :param ld:
        :return: Valor a pagar por ausencias de tipo atep por el primer dia
        """
        # Se realiza por orm ya que este campo es un compute sin afectacion en base de datos
        atep_days = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                                 and x.holiday_status_id.atep and x.sequence == 1)
        lday_holiday = False
        base, amount, qty = 0, 0, 0
        for lday in atep_days:
            if lday.holiday_id != lday_holiday:
                calc_type = 'ibc' if lday.holiday_status_id.ibc else 'wage'
                base = lday.holiday_id._ibc()[0] * 30 if calc_type == 'ibc' else ld['wage']
                lday_holiday = lday.holiday_id
            amount += base / 30
            qty += lday.days_payslip
            if lday.name[5:12] == '02-28' and lday.holiday_id.date_to[0:10] > lday.name:
                qty += 2
                amount += 2 * base / 30
            if lday.name[5:12] == '02-28' and ld['wd'] == 0:
                qty += 2
                amount += 2 * base / 30

        if self.env.user.company_id.aus_prev:
            for leave in self.leave_ids.filtered(lambda x: x.holiday_status_id.atep):
                for leave_day in leave.line_ids.filtered(lambda x: x.sequence == 1):

                    prev_period = leave_day.name < ld['period'].start_period
                    not_payed = leave_day.state == 'validate'
                    appv_per = ld['period'].start_period <= leave.approve_date <= ld['period'].end_period
                    if prev_period and not_payed and appv_per:
                        if leave_day.holiday_id != lday_holiday:
                            calc_type = 'ibc' if leave_day.holiday_status_id.ibc else 'wage'
                            base = leave._ibc()[0] * 30 if calc_type == 'ibc' else ld['wage']
                            lday_holiday = leave
                        amount += base / 30
                        qty += leave_day.days_payslip

        if qty:
            lr[0] = amount / qty
            lr[1] = qty
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _atep_p2(self, ld):
        """
        Incapacidad por accidente de trabajo del primer dia
        :param ld:
        :return: Valor a pagar por ausencias de tipo atep por el primer dia
        """
        # Se realiza por orm ya que este campo es un compute sin afectacion en base de datos
        atep_days = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                                 and x.holiday_status_id.atep and x.sequence > 1)
        lday_holiday = False
        base, amount, qty = 0, 0, 0
        for lday in atep_days:
            if lday.holiday_id != lday_holiday:
                base = lday.holiday_id._ibc()[0] * 30
                lday_holiday = lday.holiday_id
            amount += base / 30 if lday.days_payslip else 0
            qty += lday.days_payslip
            if lday.name[5:12] == '02-28' and lday.holiday_id.date_to[0:10] > lday.name:
                qty += 2
                amount += 2 * base / 30
            if lday.name[5:12] == '02-28' and ld['wd'] == 0:
                qty += 2
                amount += 2 * base / 30

        if self.env.user.company_id.aus_prev:
            for leave in self.leave_ids.filtered(lambda x: x.holiday_status_id.atep):
                for leave_day in leave.line_ids.filtered(lambda x: x.sequence > 1):

                    prev_period = leave_day.name < ld['period'].start_period
                    not_payed = leave_day.state == 'validate'
                    appv_per = ld['period'].start_period <= leave.approve_date <= ld['period'].end_period
                    if prev_period and not_payed and appv_per:
                        if leave_day.holiday_id != lday_holiday:
                            calc_type = 'ibc' if leave_day.holiday_status_id.ibc else 'wage'
                            base = leave._ibc()[0] * 30 if calc_type == 'ibc' else ld['wage']
                            lday_holiday = leave
                        amount += base / 30
                        qty += leave_day.days_payslip
        if qty:
            lr[0] = amount / qty
            lr[1] = qty
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _mat_lic(self, ld):
        """
        Enfermedad general de 1 y 2 dias
        :param ld:
        :return:
        """
        # Se realiza por orm ya que este campo es un compute sin afectacion en base de datos
        lic = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                           and x.holiday_status_id.maternal_lic)

        avr = ld['wage']
        if len(lic) > 0:
            # Calculo de promedio de ingresos en caso de que la ausencia no se calcule con IBC
            ref_to_date = datetime.strftime(datetime.strptime(
                lic[0].holiday_id.date_from[0:10], "%Y-%m-%d") - relativedelta(months=1), "%Y-%m-%d")
            day_to = monthrange(int(ref_to_date[0:4]), int(ref_to_date[5:7]))[2]
            ref_to_date = str(ref_to_date[0:8]) + str(day_to)

            k_dt_start = ld['contract'].date_start
            ref_date = datetime.strftime(datetime.strptime(
                ref_to_date[0:8] + "01", "%Y-%m-%d") - relativedelta(months=11), "%Y-%m-%d")
            if ref_date < k_dt_start:
                ref_date = k_dt_start

            days_itval = days360(ref_date, ref_to_date)
            if days_itval > 360:
                days_itval = 360

            # Calculo de acumulados
            earnings = self.get_interval_category('earnings', ref_date, ref_to_date, exclude=('BASICO',))

            # Informacion de propia nomina
            a_basico = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0
            a_earnings = ld['categories']['earnings'] - a_basico

            # Promedios del periodo
            t_earnings = (sum([x[1] for x in earnings]) + a_earnings) * 30 / days_itval

            avr = ld['wage'] + t_earnings
        flag = 0
        lday_holiday = False
        base, amount, qty = 0, 0, 0
        for lday in lic:
            if lday.days_payslip:
                if lday.holiday_id != lday_holiday:
                    if lday.holiday_status_id.ibc:
                        flag = 1
                        base = lday.holiday_id._ibc()[0] * 30
                    else:
                        base = avr
                    lday_holiday = lday.holiday_id
                amount += base / 30
            qty += lday.days_payslip
            if lday.name[5:12] == '02-28' and lday.holiday_id.date_to[0:10] > lday.name:
                qty += 2
                amount += 2 * base / 30
            if lday.name[5:12] == '02-28' and ld['wd'] == 0:
                qty += 2
                amount += 2 * base / 30
        if self.env.user.company_id.aus_prev:
            for leave in self.leave_ids.filtered(lambda x: x.holiday_status_id.maternal_lic):
                appv_per = ld['period'].start_period <= leave.approve_date <= ld['period'].end_period
                for leave_day in leave.line_ids:
                    prev_period = leave_day.name[5:7] < ld['period'].start_period[5:7]
                    not_payed = leave_day.state == 'validate'
                    if prev_period and not_payed and appv_per:
                        amount += base / 30
                        qty += leave_day.days_payslip
        if qty:
            lr[0] = amount / qty
            lr[1] = qty

            # Generacion de computation log
            log = [('METODO DE CALCULO IBC', flag)]
            lr[6] = log
        else:
            lr[3] = 'na'

        return lr

    @api.multi
    def _pat_lic(self, ld):
        """
        Enfermedad general de 1 y 2 dias
        :param ld:
        :return: Valor a pagar por ausencias de tipo enfermedad general que tengan entre 1 y 2 dias
        """
        # Se realiza por orm ya que este campo es un compute sin afectacion en base de datos
        lic = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                           and x.holiday_status_id.paternal_lic)

        avr = ld['wage']
        if len(lic) > 0 and lic[0].holiday_status_id.ibc:
            # Calculo de promedio de ingresos en caso de que la ausencia no se calcule con IBC
            ref_to_date = datetime.strftime(datetime.strptime(
                lic[0].holiday_id.date_from[0:10], "%Y-%m-%d") - relativedelta(months=1), "%Y-%m-%d")
            day_to = monthrange(int(ref_to_date[0:4]), int(ref_to_date[5:7]))[2]
            ref_to_date = str(ref_to_date[0:8]) + str(day_to)

            k_dt_start = ld['contract'].date_start
            ref_date = datetime.strftime(datetime.strptime(
                ref_to_date[0:8] + "01", "%Y-%m-%d") - relativedelta(months=11), "%Y-%m-%d")
            if ref_date < k_dt_start:
                ref_date = k_dt_start

            days_itval = days360(ref_date, ref_to_date)
            if days_itval > 360:
                days_itval = 360

            # Calculo de acumulados
            earnings = self.get_interval_category('earnings', ref_date, ref_to_date, exclude=('BASICO',))

            # Informacion de propia nomina
            a_basico = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0
            a_earnings = ld['categories']['earnings'] - a_basico

            # Promedios del periodo
            t_earnings = (sum([x[1] for x in earnings]) + a_earnings) * 30 / days_itval

            avr = ld['wage'] + t_earnings
        flag = 0
        lday_holiday = False
        base, amount, qty = 0, 0, 0
        for lday in lic:
            if lday.holiday_id != lday_holiday:
                if lday.holiday_status_id.ibc:
                    flag = 1
                    base = lday.holiday_id._ibc()[0] * 30
                else:
                    base = avr
                lday_holiday = lday.holiday_id
            amount += base / 30
            qty += lday.days_payslip
            if lday.name[5:12] == '02-28' and lday.holiday_id.date_to[0:10] > lday.name:
                qty += 2
                amount += 2 * base / 30
            if lday.name[5:12] == '02-28' and ld['wd'] == 0:
                qty += 2
                amount += 2 * base / 30
        if self.env.user.company_id.aus_prev:
            for leave in self.leave_ids.filtered(lambda x: x.holiday_status_id.paternal_lic):
                for leave_day in leave.line_ids:
                    prev_period = leave_day.name[5:7] < ld['period'].start_period[5:7]
                    not_payed = leave_day.state == 'validate'
                    appv_per = ld['period'].start_period <= leave.approve_date <= ld['period'].end_period
                    if prev_period and not_payed and appv_per:
                        amount += base / 30
                        qty += leave_day.days_payslip
        if qty:
            lr[0] = amount / qty
            lr[1] = qty

            # Generacion de computation log
            log = [('METODO DE CALCULO IBC', flag)]
            lr[6] = log
        else:
            lr[3] = 'na'

        return lr

    @api.multi
    def _vac_disf(self, ld):
        if self.env.user.company_id.fragment_vac:
            payslip_vac = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                                       and x.holiday_status_id.vacaciones
                                                       and x.holiday_status_id.code != 'VAC_PAGAS')
            qty = 0
            for lday in payslip_vac:
                qty += lday.days_payslip
                if lday.name[5:12] == '02-28' and lday.holiday_id.date_to[0:10] > lday.name:
                    qty += 2
                aus = lday.holiday_id
        else:
            payslip_vac = self.leave_ids.filtered(lambda x: x.state == 'validate'
                                                  and x.holiday_status_id.vacaciones)
            qty = 0
            aus = self.env['hr.holidays']
            for leave_id in payslip_vac:
                qty += leave_id.number_of_days_in_payslip
                aus = leave_id
                if leave_id.date_from[5:7] == '02' and leave_id.date_to[0:10] > leave_id.date_from[0:4] + '-02-28':
                    qty += 2

        if qty:
            ref_to_date = datetime.strftime(datetime.strptime(
                ld['period'].start_period, "%Y-%m-%d") - relativedelta(months=1), "%Y-%m-%d")
            day_to = monthrange(int(ref_to_date[0:4]), int(ref_to_date[5:7]))[2]
            ref_to_date = str(ref_to_date[0:8]) + str(day_to)

            k_dt_start = ld['contract'].date_start
            ref_date = datetime.strftime(datetime.strptime(
                ref_to_date[0:8] + "01", "%Y-%m-%d") - relativedelta(months=11), "%Y-%m-%d")
            if ref_date < k_dt_start:
                ref_date = k_dt_start

            days_itval = days360(ref_date, ref_to_date)
            if days_itval > 360:
                days_itval = 360

            # Calculo de acumulados
            earnings = self.get_interval_category('earnings', ref_date, ref_to_date, exclude=('BASICO',))
            if aus.special_vac_base:
                comp_earnings = self.get_interval_category('comp_earnings', ref_date, ref_to_date)
                comp_earnings = sum([x[1] for x in comp_earnings])
                o_salarial_earnings = self.get_interval_category('o_salarial_earnings', ref_date, ref_to_date)
                t_o_salarial_earnings = sum([x[1] for x in o_salarial_earnings])
            else:
                comp_earnings = 0
                o_salarial_earnings = self.get_interval_category('o_salarial_earnings', ref_date, ref_to_date)
                t_o_salarial_earnings = sum([x[1] for x in o_salarial_earnings])

            # Informacion de propia nomina
            a_basico = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0
            a_earnings = ld['categories']['earnings'] - a_basico
            if aus.special_vac_base:
                a_comp_earnings = ld['categories']['comp_earnings']
                a_o_salarial_earnings = ld['categories']['o_salarial_earnings']
            else:
                a_comp_earnings, a_o_salarial_earnings = 0, 0

            # Promedios del periodo
            if days_itval:
                t_earnings = (sum([x[1] for x in earnings])) * 30 / days_itval
                t_comp_earnings = (comp_earnings + a_comp_earnings) * 30 / days_itval
                t_other = (t_o_salarial_earnings + a_o_salarial_earnings) * 30 / days_itval
            else:
                t_earnings = 0
                t_comp_earnings = 0
                t_other = 0


            if aus.special_vac_base:
                avr = ld['wage'] + t_earnings + t_comp_earnings + t_other
            else:
                avr = ld['wage'] + t_earnings + t_other

            lr[0] = avr / 30
            lr[1] = qty

            # Generacion de computation log
            log = [
                ('SALARIO', ld['wage']),
                ('FECHA INICIO', dt2f(ref_date)),
                ('FECHA FIN', dt2f(ref_to_date)),
                ('PROMEDIO DEVENGOS', t_earnings),
                ('PROMEDIO INGRESOS COMPLEMENTARIOS', t_comp_earnings),
                ('PROMEDIO OTROS INGRESOS SALARIALES', t_other),
                ('BASE', avr),
                ('DIAS DE REFERENCIA', days_itval)
            ]
            lr[6] = log

            # Historicos
            hist = "<b>Devengados:</b> %s <br/>" % earnings
            hist += "<b>Complementarios:</b> %s <br/>" % comp_earnings
            hist += "<b>Otros ingresos salariales:</b> %s <br/>" % o_salarial_earnings
            lr[7] = hist
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _vac_pag(self, ld):
        payslip_vac = self.leave_ids.filtered(lambda x: x.state == 'validate'
                                                and x.holiday_status_id.vacaciones
                                                and x.at_date >= ld['period'].start_period)
        qty = 0
        for aus in payslip_vac:
            qty += aus.payed_vac

        if qty:
            ref_to_date = datetime.strftime(datetime.strptime(
                ld['period'].start_period, "%Y-%m-%d") - relativedelta(months=1), "%Y-%m-%d")
            day_to = monthrange(int(ref_to_date[0:4]), int(ref_to_date[5:7]))[2]
            ref_to_date = str(ref_to_date[0:8]) + str(day_to)

            k_dt_start = ld['contract'].date_start
            ref_date = datetime.strftime(datetime.strptime(
                ref_to_date[0:8] + "01", "%Y-%m-%d") - relativedelta(months=11), "%Y-%m-%d")
            if ref_date < k_dt_start:
                ref_date = k_dt_start

            days_itval = days360(ref_date, ref_to_date)
            if days_itval > 360:
                days_itval = 360

            # Calculo de acumulados
            earnings = self.get_interval_category('earnings', ref_date, ref_to_date, exclude=('BASICO',))
            comp_earnings = self.get_interval_category('comp_earnings', ref_date, ref_to_date)
            o_salarial_earnings = self.get_interval_category('o_salarial_earnings', ref_date, ref_to_date)

            # Informacion de propia nomina
            a_basico = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0
            a_earnings = ld['categories']['earnings'] - a_basico
            a_comp_earnings = ld['categories']['comp_earnings']
            a_o_salarial_earnings = ld['categories']['o_salarial_earnings']

            # Promedios del periodo
            t_earnings = (sum([x[1] for x in earnings]) + a_earnings) * 30 / days_itval
            t_comp_earnings = (sum([x[1] for x in comp_earnings]) + a_comp_earnings) * 30 / days_itval
            t_other = (sum([x[1] for x in o_salarial_earnings]) + a_o_salarial_earnings) * 30 / days_itval

            avr = ld['wage'] + t_earnings + t_comp_earnings + t_other

            lr[0] = avr / 30
            lr[1] = qty

            # Generacion de computation log
            log = [
                ('SALARIO', ld['wage']),
                ('FECHA INICIO', dt2f(ref_date)),
                ('FECHA FIN', dt2f(ref_to_date)),
                ('PROMEDIO DEVENGOS', t_earnings),
                ('PROMEDIO INGRESOS COMPLEMENTARIOS', t_comp_earnings),
                ('PROMEDIO OTROS INGRESOS SALARIALES', t_other),
                ('BASE', avr),
                ('DIAS DE REFERENCIA', days_itval)
            ]
            lr[6] = log

            # Historicos
            hist = "<b>Devengados:</b> %s <br/>" % earnings
            hist += "<b>Complementarios:</b> %s <br/>" % comp_earnings
            hist += "<b>Otros ingresos salariales:</b> %s <br/>" % o_salarial_earnings
            lr[7] = hist

        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _prima(self, ld):
        if ld['period'].start_period[5:7] in ['06', '12']:
            # Calculo de fechas de referencia para calculos
            k_dt_start = ld['contract'].date_start
            ref_month = '01' if int(ld['period'].start_period[5:7]) <= 6 else '07'
            ref_date = ld['period'].start_period[0:4] + '-' + ref_month + '-01'
            if ref_date < k_dt_start:
                ref_date = k_dt_start
            ref_to_date = datetime.strftime(datetime.strptime(
                ld['period'].end_period, "%Y-%m-%d"), "%Y-%m-%d")
            day_to = monthrange(int(ref_to_date[0:4]), int(ref_to_date[5:7]))[2]
            ref_to_date = str(ref_to_date[0:8]) + str(day_to if day_to < 31 else 30)

            prima_data = self.get_prst(ref_date, ref_to_date, ld, include=True, prst='prima')

            log = [
                ('FECHA DESDE', dt2f(ref_date)),
                ('FECHA HASTA', dt2f(ref_to_date)),
                ('DIAS LABORADOS', prima_data['days']),
                ('DIAS DE LICENCIA', prima_data['days_mat']),
                ('DIAS DE SUSPENSION', prima_data['susp']),
                ('CAMBIO DE SALARIO', prima_data['wc']),
                ('TOTAL SALARIO', prima_data['twage']),
                ('TOTAL VARIABLE', prima_data['total_variable']),
                ('TOTAL FIJO', prima_data['total_fix']),
                ('BASE', prima_data['base']),
                ('NETO PRIMA A LA FECHA', prima_data['pres']),
                ('PARCIALES', prima_data['partials']),
            ]

            lr[0] = prima_data['net_pres']
            lr[6] = log
            lr[7] = prima_data['log']
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _ces_part(self, ld):
        # Calculo de fechas de referencia para calculos
        k_dt_start = ld['contract'].date_start
        ref_month = '01'
        ref_date = ld['period'].start_period[0:4] + '-' + ref_month + '-01'
        if ref_date < k_dt_start:
            ref_date = k_dt_start
        ref_to_date = datetime.strftime(datetime.strptime(
            self.liquidacion_date, "%Y-%m-%d"), "%Y-%m-%d")
        ref_to_date = str(ref_to_date[0:8]) + str(ref_to_date[8:10] if int(ref_to_date[8:10]) < 31 else 30)

        ces_data = self.get_prst(ref_date, ref_to_date, ld, include=False, prst='ces')

        log = [
            ('FECHA DESDE', dt2f(ref_date)),
            ('FECHA HASTA', dt2f(ref_to_date)),
            ('DIAS LABORADOS', ces_data['days']),
            ('DIAS DE LICENCIA', ces_data['days_mat']),
            ('DIAS DE SUSPENSION', ces_data['susp']),
            ('CAMBIO DE SALARIO', ces_data['wc']),
            ('TOTAL SALARIO', ces_data['twage']),
            ('TOTAL VARIABLE', ces_data['total_variable']),
            ('TOTAL FIJO', ces_data['total_fix']),
            ('BASE', ces_data['base']),
            ('NETO CESANTIAS A LA FECHA', ces_data['pres']),
            ('PARCIALES', ces_data['partials']),
        ]

        lr[0] = ces_data['net_pres']
        lr[6] = log
        lr[7] = ces_data['log']

        return lr

    @api.multi
    def _cesly(self, ld):
        # Calculo de fechas de referencia para calculos
        k_dt_start = ld['contract'].date_start
        ref_year = int(ld['period'].start_period[0:4]) - 1
        ref_month = '01'
        ref_date = str(ref_year) + '-' + ref_month + '-01'
        if ref_date < k_dt_start:
            ref_date = k_dt_start

        ref_to_month = '12'
        ref_to_date = str(ref_year) + '-' + ref_to_month + '-30'

        ces_data = self.get_prst(ref_date, ref_to_date, ld, include=False, prst='ces')

        log = [
            ('FECHA DESDE', dt2f(ref_date)),
            ('FECHA HASTA', dt2f(ref_to_date)),
            ('DIAS LABORADOS', ces_data['days']),
            ('DIAS DE LICENCIA', ces_data['days_mat']),
            ('DIAS DE SUSPENSION', ces_data['susp']),
            ('CAMBIO DE SALARIO', ces_data['wc']),
            ('TOTAL SALARIO', ces_data['twage']),
            ('TOTAL VARIABLE', ces_data['total_variable']),
            ('TOTAL FIJO', ces_data['total_fix']),
            ('BASE', ces_data['base']),
            ('NETO CESANTIAS A LA FECHA', ces_data['pres']),
            ('PARCIALES', ces_data['partials']),
        ]

        lr[0] = ces_data['net_pres']
        lr[6] = log
        lr[7] = ces_data['log']

        return lr

    @api.multi
    def _ces(self, ld):
        # Calculo de fechas de referencia para calculos
        k_dt_start = ld['contract'].date_start
        ref_year = int(ld['period'].start_period[0:4]) - 1
        ref_month = '01'
        ref_date = str(ref_year) + '-' + ref_month + '-01'
        if ref_date < k_dt_start:
            ref_date = k_dt_start

        ref_to_month = '12'
        ref_to_date = str(ref_year) + '-' + ref_to_month + '-30'
        # Parciales desde enero a la fecha de pago
        ref_end_period = ld['period'].end_period
        ref_jan_date = ld['period'].start_period[0:4] + '-01-01'

        ces_part, cesly = [], []
        if ref_end_period[5:7] in ('01', '02'):
            ces_part = self.get_interval_concept('CES_PART', ref_jan_date, ref_end_period)
            cesly = self.get_interval_concept('CESLY', ref_jan_date, ref_end_period)
        t_ces_part = sum([x[1] for x in ces_part]) + sum([x[1] for x in cesly])

        ces_data = self.get_prst(ref_date, ref_to_date, ld, include=False, prst='ces')

        log = [
            ('FECHA DESDE', dt2f(ref_date)),
            ('FECHA HASTA', dt2f(ref_to_date)),
            ('DIAS LABORADOS', ces_data['days']),
            ('DIAS DE LICENCIA', ces_data['days_mat']),
            ('DIAS DE SUSPENSION', ces_data['susp']),
            ('CAMBIO DE SALARIO', ces_data['wc']),
            ('TOTAL SALARIO', ces_data['twage']),
            ('TOTAL VARIABLE', ces_data['total_variable']),
            ('TOTAL FIJO', ces_data['total_fix']),
            ('BASE', ces_data['base']),
            ('NETO CESANTIAS A LA FECHA', ces_data['pres']),
            ('PARCIALES', ces_data['partials']),
            ('PARCIALES AÑO EN CURSO', t_ces_part)
        ]

        lr[0] = ces_data['net_pres'] - t_ces_part
        lr[6] = log
        lr[7] = ces_data['log']

        return lr

    @api.multi
    def _icesly(self, ld):
        # Calculo de fechas de referencia para calculos
        k_dt_start = ld['contract'].date_start
        ref_year = int(ld['period'].start_period[0:4]) - 1
        ref_month = '01'
        ref_date = str(ref_year) + '-' + ref_month + '-01'
        if ref_date < k_dt_start:
            ref_date = k_dt_start

        ref_to_month = '12'
        ref_to_date = str(ref_year) + '-' + ref_to_month + '-31'

        ref_end_period = ld['period'].end_period
        ref_jan_date = ld['period'].start_period[0:4] + '-01-01'

        ces_data = self.get_prst(ref_date, ref_to_date, ld, include=False, prst='ces')

        ices = ces_data['pres'] * 0.12 / 360 * (ces_data['days'] + ces_data['days_mat'])

        icesly = []
        if ref_end_period[5:7] in ('01', '02'):
            ices_part = self.get_interval_concept('ICES_PART', ref_date, ref_end_period)
            icesly = self.get_interval_concept('ICESLY', ref_jan_date, ref_end_period)
        else:
            ices_part = self.get_interval_concept('ICES_PART', ref_date, ref_to_date)
            icesly = self.get_interval_concept('ICESLY', ref_date, ref_to_date)
        t_ices_part = sum([x[1] for x in ices_part]) + sum([x[1] for x in icesly])

        net_ices = ices - t_ices_part

        log = [
            ('FECHA DESDE', dt2f(ref_date)),
            ('FECHA HASTA', dt2f(ref_to_date)),
            ('DIAS LABORADOS', ces_data['days']),
            ('DIAS DE LICENCIA', ces_data['days_mat']),
            ('DIAS DE SUSPENSION', ces_data['susp']),
            ('CAMBIO DE SALARIO', ces_data['wc']),
            ('TOTAL SALARIO', ces_data['twage']),
            ('TOTAL VARIABLE', ces_data['total_variable']),
            ('TOTAL FIJO', ces_data['total_fix']),
            ('BASE', ces_data['base']),
            ('NETO CESANTIAS A LA FECHA', ces_data['pres']),
            ('PARCIALES', t_ices_part),
        ]

        if net_ices > 0:
            lr[0] = ces_data['pres']
            lr[5] = net_ices
            lr[6] = log
            lr[7] = ces_data['log']
        else:
            lr[3] = 'na'

        return lr

    @api.multi
    def _ices_part(self, ld):
        # Calculo de fechas de referencia para calculos
        k_dt_start = ld['contract'].date_start
        ref_month = '01'
        ref_date = ld['period'].start_period[0:4] + '-' + ref_month + '-01'
        if ref_date < k_dt_start:
            ref_date = k_dt_start
        ref_to_date = datetime.strftime(datetime.strptime(
            self.liquidacion_date, "%Y-%m-%d"), "%Y-%m-%d")
        ref_to_date = str(ref_to_date[0:8]) + str(ref_to_date[8:10])
        days = days360(ref_date, ref_to_date)
        ces_part = ld['concepts']['CES_PART']['total'] if 'CES_PART' in ld['concepts'] else 0
        if ces_part:
            ices = ces_part * 0.12 * days / 360
            lr[0] = ices
            log = [
                ('FECHA DESDE', dt2f(ref_date)),
                ('FECHA HASTA', dt2f(ref_to_date)),
                ('DIAS LABORADOS', days),
                ('BASE', ces_part),
            ]
            lr[6] = log
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _ices_part2(self, ld):
        # Calculo de fechas de referencia para calculos
        k_dt_start = ld['contract'].date_start
        ref_month = '01'
        ref_date = ld['period'].start_period[0:4] + '-' + ref_month + '-01'
        if ref_date < k_dt_start:
            ref_date = k_dt_start
        ref_to_date = datetime.strftime(datetime.strptime(
            self.liquidacion_date, "%Y-%m-%d"), "%Y-%m-%d")
        ref_to_date = str(ref_to_date[0:8]) + str(ref_to_date[8:10])

        ces_data = self.get_prst(ref_date, ref_to_date, ld, include=False, prst='ces')

        ices = ces_data['pres'] * 0.12 / 360 * (ces_data['days'] + ces_data['days_mat'])

        ices_part = self.get_interval_concept('ICES_PART', ref_date, ref_to_date)
        t_ices_part = sum([x[1] for x in ices_part])

        net_ices = ices - t_ices_part

        log = [
            ('FECHA DESDE', dt2f(ref_date)),
            ('FECHA HASTA', dt2f(ref_to_date)),
            ('DIAS LABORADOS', ces_data['days']),
            ('DIAS DE LICENCIA', ces_data['days_mat']),
            ('DIAS DE SUSPENSION', ces_data['susp']),
            ('CAMBIO DE SALARIO', ces_data['wc']),
            ('TOTAL SALARIO', ces_data['twage']),
            ('TOTAL VARIABLE', ces_data['total_variable']),
            ('BASE', ces_data['base']),
            ('NETO CESANTIAS A LA FECHA', ces_data['pres']),
            ('PARCIALES', t_ices_part),
        ]

        if net_ices > 0:
            lr[0] = ces_data['pres']
            lr[5] = net_ices
            lr[6] = log
            lr[7] = ces_data['log']
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _vac_liq(self, ld):
        k_dt_start = ld['contract'].date_start
        ref_date = datetime.strftime(datetime.strptime(
            ld['period'].start_period, "%Y-%m-%d") - relativedelta(months=12), "%Y-%m-%d")
        if ref_date < k_dt_start:
            ref_date = k_dt_start
        ref_to_date = ld['contract'].date_end or ld['period'].end_period
        ref_to_date = str(ref_to_date[0:8]) + str(ref_to_date[8:10] if int(ref_to_date[8:10]) < 31 else 30)
        sus_lic = self.leave_days_ids.filtered(lambda x: x.state == 'validate' and x.holiday_status_id.no_payable)
        qty_sus = 0
        for aus in sus_lic:
            qty_sus += aus.days_assigned

        qty = ld['contract'].get_pend_vac(date_calc=ref_to_date, sus=qty_sus)
        qty = 0 if qty < 0 else qty

        sus_vac_book = ld['contract'].get_sus_per()
        if qty:
            days_itval = days360(ref_date, ref_to_date)
            if days_itval > 360:
                days_itval = 360

            payslip_vac = self.leave_days_ids.filtered(lambda x: x.state == 'validate'
                                                                 and x.holiday_status_id.vacaciones)
            qty_disf = 0
            for aus in payslip_vac:
                qty_disf += aus.days_assigned

            payed_per = ld['concepts']['VAC_PAG']['qty'] if 'VAC_PAG' in ld['concepts'] else 0

            qty -= (qty_disf + payed_per)

            # Calculo de acumulados
            earnings = self.get_interval_category('earnings', ref_date, ref_to_date, ('BASICO',))
            comp_earnings = self.get_interval_category('comp_earnings', ref_date, ref_to_date)
            o_salarial_earnings = self.get_interval_category('o_salarial_earnings', ref_date, ref_to_date)

            # Informacion de propia nomina
            a_basico = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0
            a_earnings = ld['categories']['earnings'] - a_basico
            a_comp_earnings = ld['categories']['comp_earnings']
            a_o_salarial_earnings = ld['categories']['o_salarial_earnings']

            # Promedios del periodo
            if days_itval >= 30:
                t_earnings = (sum([x[1] for x in earnings]) + a_earnings) * 30 / days_itval
                t_comp_earnings = (sum([x[1] for x in comp_earnings]) + a_comp_earnings) * 30 / days_itval
                t_other = (sum([x[1] for x in o_salarial_earnings]) + a_o_salarial_earnings) * 30 / days_itval
            else:
                t_earnings = (sum([x[1] for x in earnings]) + a_earnings)
                t_comp_earnings = (sum([x[1] for x in comp_earnings]) + a_comp_earnings)
                t_other = (sum([x[1] for x in o_salarial_earnings]) + a_o_salarial_earnings)

            avr = ld['wage'] + t_earnings + t_comp_earnings + t_other
            if ld['contract'].part_time:
                avr -= ld['wage']

            # Generacion de computation log
            log = [
                ('SALARIO', ld['wage']),
                ('FECHA INICIO', dt2f(ref_date)),
                ('FECHA FIN', dt2f(ref_to_date)),
                ('PROMEDIO DEVENGOS', t_earnings),
                ('PROMEDIO INGRESOS COMPLEMENTARIOS', t_comp_earnings),
                ('PROMEDIO OTROS INGRESOS SALARIALES', t_other),
                ('BASE', avr),
                ('DIAS REFERENCIA SIN LICENCIAS', days_itval),
                ('LICENCIAS/SUSPENSIONES NOMINA', qty_sus),
                ('LICENCIAS/SUSPENSIONES LIBRO VACACIONES', sus_vac_book),
                ('DIAS VACACIONES LIQUIDADOS', qty)
            ]
            lr[6] = log

            lr[0] = avr / 30
            lr[1] = qty
        else:
            lr[3] = 'na'

        return lr

    @api.multi
    def _ces_liq(self, ld):
        # Calculo de fechas de referencia para calculos
        k_dt_start = ld['contract'].date_start
        ref_month = '01'
        ces_year = int(ld['period'].start_period[0:4])
        double_liq = 0
        if ld['period'].start_period[5:7] in ('01', '02') and k_dt_start[0:4] < ces_year:
            ces = self.get_interval_concept_qty('NETO_CES', ld['period'].start_period[0:4] + '-' + ref_month + '-01',
                                                ld['contract'].date_end)
            if not ces:
                ces_year = int(ld['period'].start_period[0:4]) - 1
                double_liq = 1
        ref_date = str(ces_year) + '-' + ref_month + '-01'
        if ref_date < k_dt_start:
            ref_date = k_dt_start
        ref_to_date = datetime.strftime(datetime.strptime(
            ld['contract'].date_end, "%Y-%m-%d"), "%Y-%m-%d")
        if double_liq:
            ref_to_date = str(ces_year) + '-' + '12-31'
        else:
            ref_to_date = str(ref_to_date[0:8]) + str(ref_to_date[8:10] if int(ref_to_date[8:10]) < 31 else 30)

        ces_data = self.get_prst(ref_date, ref_to_date, ld, include=True, prst='ces', nocesly=True)
        ref_date_ny, ref_to_date_ny = False, False
        if double_liq:
            ref_date_ny = str(ces_year + 1) + '-' + '01-01'
            ref_to_date_ny = datetime.strftime(datetime.strptime(
                ld['contract'].date_end, "%Y-%m-%d"), "%Y-%m-%d")
            ref_to_date_ny = str(ref_to_date_ny[0:8]) + str(ref_to_date_ny[8:10] if int(ref_to_date_ny[8:10]) < 31 else 30)
            ces_data_ny = self.get_prst(ref_date_ny, ref_to_date_ny, ld, include=True, prst='ces', nocesly=True)
            for key in ces_data:
                ces_data[key] += ces_data_ny[key]

        log = [
            ('FECHA DESDE', dt2f(ref_date)),
            ('FECHA HASTA', dt2f(ref_to_date)),
            ('DIAS LABORADOS', ces_data['days']),
            ('LIQUIDACION DUAL', double_liq),
            ('FECHA SECUNDARIA INICIO', dt2f(ref_date_ny)),
            ('FECHA SECUNDARIO FIN', dt2f(ref_to_date_ny)),
            ('DIAS DE LICENCIA', ces_data['days_mat']),
            ('DIAS DE SUSPENSION', ces_data['susp']),
            ('CAMBIO DE SALARIO', ces_data['wc']),
            ('TOTAL SALARIO', ces_data['twage']),
            ('TOTAL VARIABLE', ces_data['total_variable']),
            ('TOTAL FIJO', ces_data['total_fix']),
            ('BASE', ces_data['base']),
            ('NETO CESANTIAS A LA FECHA', ces_data['pres']),
            ('PARCIALES', ces_data['partials']),
        ]

        lr[0] = ces_data['net_pres']
        lr[6] = log
        lr[7] = ces_data['log']

        return lr

    @api.multi
    def _ices_liq(self, ld):
        # Calculo de fechas de referencia para calculos
        k_dt_start = ld['contract'].date_start
        ref_month = '01'
        ces_year = int(ld['period'].start_period[0:4])
        double_liq = 0
        if ld['period'].start_period[5:7] in ('01', '02') and k_dt_start[0:4] < ces_year:
            ces = self.get_interval_concept_qty('NETO_CES', ld['period'].start_period[0:4] + '-' + ref_month + '-01',
                                                ld['contract'].date_end)
            if not ces:
                ces_year = int(ld['period'].start_period[0:4]) - 1
                double_liq = 1
        ref_date = str(ces_year) + '-' + ref_month + '-01'
        if ref_date < k_dt_start:
            ref_date = k_dt_start
        ref_to_date = datetime.strftime(datetime.strptime(
            ld['contract'].date_end, "%Y-%m-%d"), "%Y-%m-%d")
        if double_liq:
            ref_to_date = str(ces_year) + '-' + '12-31'
        else:
            ref_to_date = str(ref_to_date[0:8]) + str(ref_to_date[8:10] if int(ref_to_date[8:10]) < 31 else 30)

        ces_data = self.get_prst(ref_date, ref_to_date, ld, include=True, prst='ces')
        ref_date_ny, ref_to_date_ny = False, False
        if double_liq:
            ref_date_ny = str(ces_year + 1) + '-' + '01-01'
            ref_to_date_ny = datetime.strftime(datetime.strptime(
                ld['contract'].date_end, "%Y-%m-%d"), "%Y-%m-%d")
            ref_to_date_ny = str(ref_to_date_ny[0:8]) + str(
                ref_to_date_ny[8:10] if int(ref_to_date_ny[8:10]) < 31 else 30)
            ces_data_ny = self.get_prst(ref_date_ny, ref_to_date_ny, ld, include=True, prst='ces')
            for key in ces_data:
                ces_data[key] += ces_data_ny[key]

        ices = ces_data['pres'] * 0.12 / 360 * (ces_data['days'] + ces_data['days_mat'])

        ices_part = self.get_interval_concept('ICES_PART', ref_date, ref_to_date_ny or ref_to_date)
        if ref_to_date_ny:
            icesly = self.get_interval_concept('ICESLY', ref_date, ref_to_date_ny or ref_to_date)
        else:
            icesly = []
        t_ices_part = sum([x[1] for x in ices_part]) + sum([x[1] for x in icesly])

        net_ices = ices - t_ices_part

        log = [
            ('FECHA DESDE', dt2f(ref_date)),
            ('FECHA HASTA', dt2f(ref_to_date)),
            ('DIAS LABORADOS', ces_data['days']),
            ('LIQUIDACION DUAL', double_liq),
            ('FECHA SECUNDARIA INICIO', dt2f(ref_date_ny)),
            ('FECHA SECUNDARIO FIN', dt2f(ref_to_date_ny)),
            ('DIAS DE LICENCIA', ces_data['days_mat']),
            ('DIAS DE SUSPENSION', ces_data['susp']),
            ('CAMBIO DE SALARIO', ces_data['wc']),
            ('TOTAL SALARIO', ces_data['twage']),
            ('TOTAL VARIABLE', ces_data['total_variable']),
            ('BASE', ces_data['base']),
            ('NETO CESANTIAS A LA FECHA', ces_data['pres']),
            ('PARCIALES', t_ices_part),
        ]

        if net_ices > 0:
            lr[0] = ces_data['pres']
            lr[5] = net_ices
            lr[6] = log
            lr[7] = ces_data['log']
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _prim_liq(self, ld):
        # Calculo de fechas de referencia para calculos
        k_dt_start = ld['contract'].date_start
        ref_month = '01' if int(ld['period'].start_period[5:7]) <= 6 else '07'
        ref_date = ld['period'].start_period[0:4] + '-' + ref_month + '-01'
        if ref_date < k_dt_start:
            ref_date = k_dt_start
        ref_to_date = datetime.strftime(datetime.strptime(ld['contract'].date_end, "%Y-%m-%d"), "%Y-%m-%d")
        ref_to_date = str(ref_to_date[0:8]) + str(ref_to_date[8:10] if int(ref_to_date[8:10]) < 31 else 30)

        prima_data = self.get_prst(ref_date, ref_to_date, ld, include=True, prst='prima')

        log = [
            ('FECHA DESDE', dt2f(ref_date)),
            ('FECHA HASTA', dt2f(ref_to_date)),
            ('DIAS LABORADOS', prima_data['days']),
            ('DIAS DE LICENCIA', prima_data['days_mat']),
            ('DIAS DE SUSPENSION', prima_data['susp']),
            ('CAMBIO DE SALARIO', prima_data['wc']),
            ('TOTAL SALARIO', prima_data['twage']),
            ('TOTAL VARIABLE', prima_data['total_variable']),
            ('TOTAL FIJO', prima_data['total_fix']),
            ('BASE', prima_data['base']),
            ('NETO PRIMA A LA FECHA', prima_data['pres']),
            ('PARCIALES', prima_data['partials']),
        ]

        lr[0] = prima_data['net_pres']
        lr[6] = log
        lr[7] = prima_data['log']

        return lr

    @api.multi
    def _indem(self, ld):
        term = ld['contract'].type_id.term
        if ld['contract'].separation_type == 'retnotjuscau':
            if term in ['fijo', 'obralabor']:
                if not ld['contract'].fix_end:
                    raise Warning("No se ha definido una fecha final de contrato a termino fijo u obra labor.")
                not_payed = days360(ld['contract'].date_end, ld['contract'].fix_end) - 1
                if not_payed > 0:
                    lr[0] = ld['concepts']['VAC_LIQ']['amount'] if 'VAC_LIQ' in ld['concepts'] else ld['wage'] / 30
                    lr[1] = not_payed
                else:
                    lr[3] = 'na'
            else:
                base = ld['concepts']['VAC_LIQ']['amount'] * 30 if 'VAC_LIQ' in ld['concepts'] else 0
                if not ld['contract'].date_start:
                    raise Warning("El contrato a liquidar {c} no tiene la fecha de inicio necesario para calcular la "
                                  "indemnizacion".format(c=ld['contract'].name))
                if not ld['contract'].date_end:
                    raise Warning("El contrato a liquidar {c} no tiene la fecha de liquidacion necesario para calcular "
                                  "la indemnizacion".format(c=ld['contract'].name))
                k_dur = float(days360(ld['contract'].date_start, ld['contract'].date_end))
                if base <= 10 * ld['sal_min_ev']:
                    if k_dur <= 360:
                        qty = 30
                    else:
                        qty = 30 + (k_dur - 360) * 20 / 360
                else:
                    if k_dur <= 360:
                        qty = 20
                    else:
                        qty = 30 + (k_dur - 360) * 15 / 360
                log = [('DURACION DE CONTRATO', k_dur)]
                lr[6] = log

                lr[0] = base / 30
                lr[1] = qty
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _ibd(self, ld):
        """
        Ingreso base de deducciones
        :param ld:
        :return: Valor de ingresos que sirven para el pago de prestaciones sociales. Tiene en cuenta el tope del 40%
        de los ingresos no salariales que al sobrepasarlos harian parte de los ingresos base.
        Tambien contempla que la politica de deducciones en primera quincena para no aplicar el calculo si es primera
        quincena y se tiene en cuenta que nunca se cotice por debajo del salario minimo en nominas mensuales o de
        segunda quincena, ajustando el valor y para primera quincena llevandola siempre a un salario minimo.
        """
        sal_earnings = (ld['categories']['earnings'] + ld['categories']['o_salarial_earnings'] +
                        ld['categories']['comp_earnings'] + ld['categories']['o_rights'])

        vac_pag = ld['concepts']['VAC_PAG']['total'] if 'VAC_PAG' in ld['concepts'] else 0
        vac_liq = ld['concepts']['VAC_LIQ']['total'] if 'VAC_LIQ' in ld['concepts'] else 0
        prima = ld['concepts']['PRIMA']['total'] if 'PRIMA' in ld['concepts'] else 0
        prim_liq = ld['concepts']['PRIM_LIQ']['total'] if 'PRIM_LIQ' in ld['concepts'] else 0
        vac_pag_prev = sum([p.get_payslip_concept_total('VAC_PAG') for p in ld['payslips_month']])
        vac_liq_prev = sum([p.get_payslip_concept_total('VAC_LIQ') for p in ld['payslips_month']])
        prima_prev = sum([p.get_payslip_concept_total('PRIMA') for p in ld['payslips_month']])
        prim_liq_prev = sum([p.get_payslip_concept_total('PRIM_LIQ') for p in ld['payslips_month']])

        sal_earnings -= (vac_pag + vac_liq + vac_pag_prev + vac_liq_prev)
        sal_earnings -= (prima + prim_liq + prima_prev + prim_liq_prev)

        prev_earn = sum([p.get_payslip_category('earnings') for p in ld['payslips_month']])
        prev_o_sal_earn = sum([p.get_payslip_category('o_salarial_earnings') for p in ld['payslips_month']])
        prev_comp_earn = sum([p.get_payslip_category('comp_earnings') for p in ld['payslips_month']])
        prev_o_rights = sum([p.get_payslip_category('o_rights') for p in ld['payslips_month']])

        ff_earnings = prev_earn + prev_o_sal_earn + prev_comp_earn + prev_o_rights

        sal_earnings += ff_earnings
        o_earnings = (ld['categories']['o_earnings'])
        ff_o_earnings = sum([p.get_payslip_category('o_earnings') for p in ld['payslips_month']])
        o_earnings += ff_o_earnings

        # TOP40
        top40 = (sal_earnings + o_earnings) * 0.4
        if o_earnings > top40:
            amount = sal_earnings + o_earnings - top40
        else:
            amount = sal_earnings

        if ld['contract_class'] == 'int':
            amount = amount * 0.7

        # TOP25
        if amount > 25 * ld['sal_min_ev']:
            amount = 25 * ld['sal_min_ev']

        lr[0] = amount

        # Generacion de computation log
        log = [
            ('INGRESOS SALARIALES', sal_earnings),
            ('INGRESOS SALARIALES PREVIOS', ff_earnings),
            ('OTROS INGRESOS', o_earnings),
            ('OTROS INGRESOS PREVIOS', ff_o_earnings),
            ('VALOR TOPE 40', top40)
        ]
        lr[6] = log
        return lr

    @api.multi
    def _ibl(self, ld):
        """
        Ingreso base laborado: Necesario para PILA
        :param ld:
        :return:
        """
        ibd = ld['concepts']['IBD']['total'] if 'IBD' in ld['concepts'] else 0
        o_rights = ld['categories']['o_rights']
        prev_o_rights = sum([p.get_payslip_category('o_rights') for p in ld['payslips_month']])
        vac_pag = ld['concepts']['VAC_PAG']['total'] if 'VAC_PAG' in ld['concepts'] else 0
        vac_liq = ld['concepts']['VAC_LIQ']['total'] if 'VAC_LIQ' in ld['concepts'] else 0
        prima = ld['concepts']['PRIMA']['total'] if 'PRIMA' in ld['concepts'] else 0
        prim_liq = ld['concepts']['PRIM_LIQ']['total'] if 'PRIM_LIQ' in ld['concepts'] else 0
        vac_pag_prev = sum([p.get_payslip_concept_total('VAC_PAG') for p in ld['payslips_month']])
        vac_liq_prev = sum([p.get_payslip_concept_total('VAC_LIQ') for p in ld['payslips_month']])
        prima_prev = sum([p.get_payslip_concept_total('PRIMA') for p in ld['payslips_month']])
        prim_liq_prev = sum([p.get_payslip_concept_total('PRIM_LIQ') for p in ld['payslips_month']])

        aus_amount = o_rights + prev_o_rights - vac_pag - vac_liq - prima - prim_liq - vac_pag_prev - vac_liq_prev - \
                     prima_prev - prim_liq_prev

        amount = ibd - aus_amount
        lr[0] = amount
        return lr

    @api.multi
    def _ibs(self, ld):
        """
        Ingreso base de cotizacion
        :param ld:
        :return:
        """
        ibd = ld['concepts']['IBD']['total'] if 'IBD' in ld['concepts'] else 0
        vac_disf_act = ld['concepts']['VAC_DISF'] if 'VAC_DISF' in ld['concepts'] else False
        mrang_start = ld['period'].start_period[0:7] + "-01"
        mrang_end = ld['period'].end_period

        vac_disf_itv = self.get_interval_concept('VAC_DISF', mrang_start, mrang_end)
        vac_disf = sum([x[1] for x in vac_disf_itv])
        col_days = self.collect_days(mrang_start, mrang_end)
        work101 = col_days['WORK101'] if 'WORK101' in col_days else 0

        ded_inicio = col_days['DED_INICIO'] if 'DED_INICIO' in col_days else 0
        ded_fin = col_days['DED_FIN'] if 'DED_FIN' in col_days else 0
        effective = work101 - ded_inicio - ded_fin

        vac_nom = col_days['VAC'] if 'VAC' in col_days else 0

        val_fix = 0
        if (vac_disf_act or vac_disf) and vac_nom:
            aus_vac = self.leave_ids.filtered(lambda x: x.state == 'validate' and x.holiday_status_id.vacaciones)
            ibs_vac = (aus_vac._ibc()[0] * 30) if aus_vac else 0
            vac_pay = (vac_disf_act['total'] if vac_disf_act else 0) + vac_disf
            sal_pay = ibs_vac * vac_nom / 30
            val_fix = vac_pay - sal_pay

        day_value = (ibd - val_fix) / effective if effective else 0
        day_value = day_value if day_value >= ld['sal_min_ev'] / 30 else ld['sal_min_ev'] / 30
        lr[0] = day_value
        lr[1] = effective

        return lr

    @api.multi
    def _ibs_bk(self, ld):
        """
        Ingreso base de cotizacion
        :param ld:
        :return:
        """
        sch_pay = ld['sch_pay']
        ibd = ld['concepts']['IBD']['total'] if 'IBD' in ld['concepts'] else 0
        work_101 = ld['wd_month']
        ded = ld['p_days']['DED_INICIO'] if 'DED_INICIO' in ld['p_days'] else 0
        ded += ld['p_days']['DED_FIN'] if 'DED_FIN' in ld['p_days'] else 0
        vac_disf = ld['concepts']['VAC_DISF'] if 'VAC_DISF' in ld['concepts'] else False
        vac_nom = ld['p_days']['VAC'] if 'VAC' in ld['p_days'] else 0
        val_fix = 0
        if vac_disf and vac_nom:
            aus_vac = self.leave_ids.filtered(lambda x: x.state == 'validate' and x.holiday_status_id.vacaciones)
            ibs_vac = (aus_vac._ibc()[0] * 30) if aus_vac else 0
            vac_pay = vac_disf['total']
            sal_pay = ibs_vac * vac_nom / 30
            val_fix = vac_pay - sal_pay
        susp = self.get_suspensions(ld['period'].start_period, ld['period'].end_period)

        net_wkd_d = work_101 - ded
        if sch_pay == 'bi-monthly' and ld['bmt'] == 'first':
            ibs = ibd - val_fix if ibd - val_fix > ld['sal_min_ev'] / 2 else ld['sal_min_ev'] * net_wkd_d / (2 * 15)
        else:
            if net_wkd_d - susp == 0:
                day = 0
            else:
                day = (ibd - val_fix) / (net_wkd_d - susp)
            ibs = day * 30 if day * 30 > ld['sal_min_ev'] else ld['sal_min_ev'] * net_wkd_d / 30
        if net_wkd_d + ded != 0:
            amount = ibs / (net_wkd_d + ded)
        else:
            amount = 0
        lr[0] = amount
        lr[1] = net_wkd_d
        return lr

    @api.multi
    def _ibp(self, ld):
        """
        Ingreso base de parafiscales
        :param ld:
        :return:
        """
        sal_earnings = (ld['categories']['earnings'] + ld['categories']['o_salarial_earnings'] +
                        ld['categories']['comp_earnings'])

        prev_earn = sum([p.get_payslip_category('earnings') for p in ld['payslips_month']])
        prev_o_sal_earn = sum([p.get_payslip_category('o_salarial_earnings') for p in ld['payslips_month']])
        prev_comp_earn = sum([p.get_payslip_category('comp_earnings') for p in ld['payslips_month']])

        ff_earnings = prev_earn + prev_o_sal_earn + prev_comp_earn

        sal_earnings += ff_earnings

        mat_lic = ld['concepts']['MAT_LIC']['total'] if 'MAT_LIC' in ld['concepts'] else 0
        pat_lic = ld['concepts']['PAT_LIC']['total'] if 'PAT_LIC' in ld['concepts'] else 0
        mat_lic_prev = sum([p.get_payslip_concept_total('MAT_LIC') for p in ld['payslips_month']])
        pat_lic_prev = sum([p.get_payslip_concept_total('PAT_LIC') for p in ld['payslips_month']])
        vac_pag = ld['concepts']['VAC_PAG']['total'] if 'VAC_PAG' in ld['concepts'] else 0
        vac_liq = ld['concepts']['VAC_LIQ']['total'] if 'VAC_LIQ' in ld['concepts'] else 0
        vac_disf = ld['concepts']['VAC_DISF']['total'] if 'VAC_DISF' in ld['concepts'] else 0
        vac_pag_prev = sum([p.get_payslip_concept_total('VAC_PAG') for p in ld['payslips_month']])
        vac_liq_prev = sum([p.get_payslip_concept_total('VAC_LIQ') for p in ld['payslips_month']])
        vac_disf_prev = sum([p.get_payslip_concept_total('VAC_DISF') for p in ld['payslips_month']])
        amount = sal_earnings + mat_lic + pat_lic + mat_lic_prev + pat_lic_prev
        amount += vac_pag + vac_liq + vac_pag_prev + vac_liq_prev + vac_disf + vac_disf_prev

        o_earnings = (ld['categories']['o_earnings'])
        ff_o_earnings = sum([p.get_payslip_category('o_earnings') for p in ld['payslips_month']])
        o_earnings += ff_o_earnings

        top40 = (amount + o_earnings) * 0.4
        if o_earnings > top40:
            amount = amount + o_earnings - top40

        if ld['contract_class'] == 'int':
            lr[0] = amount * 0.7
        else:
            lr[0] = amount
        return lr

    @api.multi
    def _ibr(self, ld):
        """
        Ingreso base de riesgos
        :param ld:
        :return:
        """
        sal_earnings = (ld['categories']['earnings'] + ld['categories']['o_salarial_earnings'] +
                        ld['categories']['comp_earnings'])

        prev_earn = sum([p.get_payslip_category('earnings') for p in ld['payslips_month']])
        prev_o_sal_earn = sum([p.get_payslip_category('o_salarial_earnings') for p in ld['payslips_month']])
        prev_comp_earn = sum([p.get_payslip_category('comp_earnings') for p in ld['payslips_month']])

        ff_earnings = prev_earn + prev_o_sal_earn + prev_comp_earn

        sal_earnings += ff_earnings
        o_earnings = (ld['categories']['o_earnings'])
        ff_o_earnings = sum([p.get_payslip_category('o_earnings') for p in ld['payslips_month']])
        o_earnings += ff_o_earnings

        # TOP40
        top40 = (sal_earnings + o_earnings) * 0.4
        if o_earnings > top40:
            amount = sal_earnings + o_earnings - top40
        else:
            amount = sal_earnings

        if ld['contract_class'] == 'int':
            amount = amount * 0.7

        # TOP25
        if amount > 25 * ld['sal_min_ev']:
            amount = 25 * ld['sal_min_ev']

        # Cancelacion de calculo para aprendices
        apr_type = ld['contract'].fiscal_type_id.code
        if ld['contract_class'] == 'apr' and apr_type != '19':
            lr[3] = 'na'

        lr[0] = amount / ld['wd_month'] if ld['wd_month'] else 0
        lr[1] = ld['wd_month']

        return lr

    @api.multi
    def _ded_pens(self, ld):
        """
        Deduccion de pension
        :param ld:
        :return: Valor a deducir al empleado correspondiente a pension, debe contemplear lo que ya se haya descontado
        en quincenas anteriores y se descuenta tambien de la base el valor de las incapacidades mayores a 180 dias
        El valor es el 4% del ibc, con el cambio del decreto 558 de 2020 se consulta en politicas de nomina
        """
        retired = True if ld['contract'].fiscal_subtype_id.code not in ['00', False] else False
        if not retired:
            prev_ded = sum([p.get_payslip_concept_total('DED_PENS') for p in ld['payslips_month']])
            ibd = ld['concepts']['IBD']['total'] if 'IBD' in ld['concepts'] else 0
            lr[0] = ibd
            lr[2] = self.env.user.company_id.percentage_employee
            if self.env.user.company_id.ded_round:
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = int(math.ceil(amount / 100.0)) * 100 - prev_ded
            else:
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = amount - prev_ded
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _fond_sol(self, ld):
        """
        Deduccion de fondo de solidaridad
        :param ld:
        :return: Valor correspondiente al 0.5% del ibc si el ibc supera los 4 salarios minimos, debe contemplear si se
        ha realizado esta deduccion en otras nominas del mismo mes
        """

        ibd = ld['concepts']['IBD']['total'] if 'IBD' in ld['concepts'] else 0
        if ibd > 4 * ld['sal_min_ev']:
            retired = True if ld['contract'].fiscal_subtype_id.code not in ['00', False] else False
            if not retired:
                prev_ded = sum([p.get_payslip_concept_total('FOND_SOL') for p in ld['payslips_month']])
                lr[0] = ibd
                lr[2] = 0.5
                if self.env.user.company_id.ded_round:
                    amount = lr[0] * lr[1] * lr[2] / 100 - prev_ded
                    lr[5] = int(math.ceil(amount / 100.0)) * 100
                else:
                    amount = lr[0] * lr[1] * lr[2] / 100 - prev_ded
                    lr[5] = amount
            else:
                lr[3] = 'na'
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _fond_sub(self, ld):
        """
        Deduccion de fondo de subsistencia
        :param ld:
        :return:
        """
        ibd = ld['concepts']['IBD']['total'] if 'IBD' in ld['concepts'] else 0
        sal_min = ld['sal_min_ev']
        prev_ded = sum([p.get_payslip_concept_total('FOND_SUB') for p in ld['payslips_month']])
        retired = True if ld['contract'].fiscal_subtype_id.code not in ['00', False] else False
        rate = 0
        if not retired:
            if ibd > 4 * ld['sal_min_ev']:
                rate += 0.5
            if 16 * sal_min <= ibd <= 17 * sal_min:
                rate += 0.2
            elif 17 * sal_min <= ibd <= 18 * sal_min:
                rate += 0.4
            elif 18 * sal_min <= ibd <= 19 * sal_min:
                rate += 0.6
            elif 19 * sal_min <= ibd <= 20 * sal_min:
                rate += 0.8
            elif ibd > 20 * sal_min:
                rate += 1
        if rate:
            lr[0] = ibd
            lr[2] = rate
            if self.env.user.company_id.ded_round:
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = int(math.ceil(amount / 100.0)) * 100 - prev_ded
            else:
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = amount - prev_ded
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _ded_eps(self, ld):
        """
        Deduccion de salud
        :param ld:
        :return: Valor a deducir al empleado correspondiente a salud, debe contemplear lo que ya se haya descontado
        en quincenas anteriores y se descuenta tambien de la base el valor de las incapacidades mayores a 180 dias
        El valor es el 4% del ibc
        """
        prev_ded = sum([p.get_payslip_concept_total('DED_EPS') for p in ld['payslips_month']])
        ibd = ld['concepts']['IBD']['total'] if 'IBD' in ld['concepts'] else 0
        lr[0] = ibd
        lr[2] = 4
        if self.env.user.company_id.ded_round:
            amount = lr[0] * lr[1] * lr[2] / 100
            lr[5] = int(math.ceil(amount/100.0))*100 - prev_ded
        else:
            amount = lr[0] * lr[1] * lr[2] / 100
            lr[5] = amount - prev_ded
        return lr

    @api.multi
    def _brtf(self, ld):
        """
        Base retencion en la fuente
        :param ld:
        :return:
        """
        taxed_inc = (ld['categories']['earnings'] + ld['categories']['o_earnings'] +
                     ld['categories']['o_salarial_earnings'] + ld['categories']['comp_earnings'] +
                     ld['categories']['o_rights'])

        prev_earn = sum([p.get_payslip_category('earnings') for p in ld['payslips_month']])
        prev_o_sal_earn = sum([p.get_payslip_category('o_earnings') for p in ld['payslips_month']])
        prev_o_earn = sum([p.get_payslip_category('o_salarial_earnings') for p in ld['payslips_month']])
        prev_comp_earn = sum([p.get_payslip_category('comp_earnings') for p in ld['payslips_month']])
        prev_o_rights = sum([p.get_payslip_category('o_rights') for p in ld['payslips_month']])

        taxed_inc += prev_earn + prev_o_sal_earn + prev_o_earn + prev_comp_earn + prev_o_rights

        prima = ld['concepts']['PRIMA']['total'] if 'PRIMA' in ld['concepts'] else 0
        prim_liq = ld['concepts']['PRIM_LIQ']['total'] if 'PRIM_LIQ' in ld['concepts'] else 0
        prima_prev = sum([p.get_payslip_concept_total('PRIMA') for p in ld['payslips_month']])
        prim_liq_prev = sum([p.get_payslip_concept_total('PRIM_LIQ') for p in ld['payslips_month']])

        if not ld['contract'].p2:
            taxed_inc -= (prima + prim_liq + prima_prev + prim_liq_prev)

        sch_pay = ld['sch_pay']
        bmt = ld['bmt']

        # Proyeccion de retencion en la fuente con el 50% de salario
        rtfprj = self.env.user.company_id.rtf_projection
        if rtfprj and sch_pay == 'bi-monthly' and bmt == 'first' and ld['slip_type'] != 'Liquidacion':
            taxed_inc += ld['wage']/2

        tax_cat_ls = ['earnings', 'o_earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights']
        uvt = ld['uvt']
        contract = ld['contract']

        untaxed_inc = 0  # Ingresos no gravados
        ing_no_const = 0  # Ingresos no constitutivos de renta
        vol_cont = 0  # Aportes voluntarios de pension y afc
        ap_vol = 0
        afc = 0

        for c in ld['concepts']:
            is_ded = True if ld['concepts'][c]['category'] == 'deductions' else False
            is_reg = True if ld['concepts'][c]['origin'] == 'regular' else False
            is_ex = True if ld['concepts'][c]['ex_rent'] else False
            is_afc = True if ld['concepts'][c]['afc'] else False
            if is_ded and is_reg:
                ing_no_const += ld['concepts'][c]['total']
            if is_ded and is_ex:
                vol_cont += ld['concepts'][c]['total']
                ap_vol += ld['concepts'][c]['total']
            if is_ded and is_afc:
                vol_cont += ld['concepts'][c]['total']
                afc += ld['concepts'][c]['total']
            if ld['concepts'][c]['category'] in tax_cat_ls and is_ex:
                untaxed_inc += ld['concepts'][c]['total']

        # Validacion de nominas del periodo
        for p in ld['payslips_month']:
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

        if rtfprj and sch_pay == 'bi-monthly' and bmt == 'first' and ld['slip_type'] != 'Liquidacion':
            # Proyeccion de deducciones de la segunda quincena
            ing_no_const += ld['wage'] * 0.09 / 2

        net_income = taxed_inc - ing_no_const
        # Descarte por derecha si el ingreso no es considerable
        discard = True if net_income == 0 else False

        if not discard:
            # Rentas exentas
            # #### Deducibles ##### #
            # Dependientes
            dep_base = taxed_inc * 0.1
            if contract.ded_dependents:
                ded_depend = dep_base if dep_base <= 32 * uvt else 32 * uvt
                ded_depend = ded_depend
            else:
                ded_depend = 0

            # Medicina prepagada
            base_mp = contract.ded_prepaid
            ded_mp = base_mp if base_mp <= 16 * uvt else 16 * uvt
            ded_mp = ded_mp

            # Deducion por vivienda
            base_liv = contract.ded_living
            ded_liv = base_liv if base_liv <= 100 * uvt else 100 * uvt
            ded_liv = ded_liv

            total_deduct = ded_depend + ded_mp + ded_liv

            # Aportes voluntarios
            vol_cont = vol_cont if vol_cont <= net_income * 0.3 else net_income * 0.3

            # Top25 deducible por ley de los ingresos - deducciones existentes
            base25 = (net_income - total_deduct - vol_cont) * 0.25
            top25 = base25 if base25 <= 240 * uvt else 240 * uvt

            # Top40
            base40 = net_income * 0.4
            baserex = total_deduct + vol_cont + top25
            rent_ex = baserex if baserex <= base40 else base40

            lr[0] = net_income - rent_ex

            # Generacion de computation log
            log = [('INGRESOS GRAVADOS', taxed_inc),
                   ('INGRESOS NO CONSTITUTIVOS', ing_no_const),
                   ('INGRESOS NETOS', net_income),
                   ('DEDUCIBLES', total_deduct),
                   ('DEPENDIENTES', ded_depend),
                   ('MEDICINA PREPAGADA', ded_mp),
                   ('INTERESES DE VIVIENDA', ded_liv),
                   ('APORTES VOLUNTARIOS', vol_cont),
                   ('DEDUCCION 25%', top25),
                   ('RENTAS EXENTAS', rent_ex),
                   ('BASE RETENCION', net_income - rent_ex)
                   ]

            lr[6] = log
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _rtefte(self, ld):
        """
        Retencion en la fuente
        :param ld:
        :return:
        """
        uvt = ld['uvt']
        brtf = ld['concepts']['BRTF']['total'] if 'BRTF' in ld['concepts'] else 0
        b_uvt = 0
        if brtf:
            if ld['contract'].p2:
                rtf_rate = ld['contract'].rtf_rate
            else:
                basic = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0
                vac_disf = ld['concepts']['VAC_DISF']['qty'] if 'VAC_DISF' in ld['concepts'] else 0
                pre_vac = sum([p.get_payslip_concept('VAC_DISF').qty for p in ld['payslips_month']])
                vac_disf += pre_vac
                pre_basic = sum([p.get_payslip_concept_total('BASICO') for p in ld['payslips_month']])
                basic += pre_basic
                adjust, ded_pen, ded_eps, ded_fon, ded_fsu = 0, 0, 0, 0, 0
                wd = ld['wd_month'] + vac_disf

                # Replantear retencion proyectada ya que genera inconvenientes con las ausencias y
                # dispara las proyecciones siempre
                # if wd < 30:
                #     day_diff = 30 - wd
                #     adjust = basic * day_diff / wd
                #     ded_pen = ld['concepts']['DED_PENS']['total'] * day_diff/wd if 'DED_PENS' in ld['concepts'] else 0
                #     ded_eps = ld['concepts']['DED_EPS']['total'] * day_diff/wd if 'DED_EPS' in ld['concepts'] else 0
                #     ded_fon = ld['concepts']['FOND_SOL']['total'] * day_diff/wd if 'FOND_SOL' in ld['concepts'] else 0
                #     ded_fsu = ld['concepts']['FOND_SUB']['total'] * day_diff/wd if 'FOND_SUB' in ld['concepts'] else 0

                proj_base = brtf + adjust - ded_pen - ded_eps - ded_fon - ded_fsu
                b_uvt = proj_base / uvt
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

                conv = ((b_uvt - step) * rate/100) + adj
                rtf = conv * uvt
                rtf_rate = rtf * 100 / brtf
            prev_rtf = sum([p.get_payslip_concept_total('RTEFTE') for p in ld['payslips_month']])
            if not rtf_rate:
                if prev_rtf:
                    lr[2] = rtf_rate
                    lr[0] = brtf
                    lr[5] = prev_rtf * -1
                else:
                    lr[3] = 'na'
            else:
                lr[2] = rtf_rate
                lr[0] = brtf

                rtf_month = lr[0] * lr[1] * lr[2] / 100
                if prev_rtf > 0:
                    if self.env.user.company_id.rtf_round:
                        lr[5] = round(rtf_month - prev_rtf, -2)
                    else:
                        lr[5] = rtf_month - prev_rtf
                else:
                    lr[5] = round(rtf_month, -2)

                # Generacion de computation log
                log = [('RETENCION CALCULADA MES', rtf_month),
                       ('RETENCION YA APLICADA', prev_rtf),
                       ('BASE UVT', b_uvt)
                       ]
                lr[6] = log

        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _rtf_prima(self, ld):
        prima = ld['concepts']['PRIMA']['amount'] if 'PRIMA' in ld['concepts'] else 0
        uvt = ld['uvt']
        b_uvt = 0
        if prima:
            # Deduccion del 25% de ley
            ing_base = prima - (prima * 0.25)
            if ld['contract'].p2:
                rtf_rate = ld['contract'].rtf_rate
            else:
                b_uvt = ing_base / uvt
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
                rtf = conv * uvt
                rtf_rate = rtf * 100 / ing_base
            prev_rtf = sum([p.get_payslip_concept_total('RTF_PRIMA') for p in ld['payslips_month']])
            if not rtf_rate:
                if prev_rtf:
                    lr[2] = rtf_rate
                    lr[0] = ing_base
                    lr[5] = prev_rtf * -1
                else:
                    lr[3] = 'na'
            else:
                lr[2] = rtf_rate
                lr[0] = ing_base

                rtf_month = lr[0] * lr[1] * lr[2] / 100
                if prev_rtf > 0:
                    if self.env.user.company_id.rtf_round:
                        lr[5] = round(rtf_month - prev_rtf, -2)
                    else:
                        lr[5] = rtf_month - prev_rtf
                else:
                    lr[5] = round(rtf_month, -2)

                # Generacion de computation log
                log = [('RETENCION CALCULADA MES', rtf_month),
                       ('RETENCION YA APLICADA', prev_rtf),
                       ('BASE UVT', b_uvt)
                       ]
                lr[6] = log
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _rtf_indem(self, ld):
        indem = ld['concepts']['INDEM']['amount'] if 'INDEM' in ld['concepts'] else 0
        if indem * 30 > 10 * ld['sal_min_ev']:
            lr[0] = indem * 30
            lr[2] = 20
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _neto(self, ld):
        """
        Neto a pagar
        :param ld:
        :return: Valor a pagar al empleado
        """
        total_earnings = (ld['categories']['earnings'] + ld['categories']['o_earnings'] +
                          ld['categories']['o_salarial_earnings'] + ld['categories']['comp_earnings'] +
                          ld['categories']['non_taxed_earnings'] + ld['categories']['o_rights'])
        total_deductions = ld['categories']['deductions']
        ces = ld['concepts']['CES']['total'] if 'CES' in ld['concepts'] else 0
        ces_part = ld['concepts']['CES_PART']['total'] if 'CES_PART' in ld['concepts'] else 0
        cesantias = ces + ces_part
        neto = total_earnings - total_deductions - cesantias
        # neto = 0 if neto < 0 else neto
        lr[0] = neto
        return lr

    @api.multi
    def _neto_liq(self, ld):
        """
        Neto a pagar liquidaciones
        :param ld:
        :return: Valor a pagar al empleado por  liquidacion
        """
        total_earnings = (ld['categories']['earnings'] + ld['categories']['o_earnings'] +
                          ld['categories']['o_salarial_earnings'] + ld['categories']['comp_earnings'] +
                          ld['categories']['non_taxed_earnings'] + ld['categories']['o_rights'])
        total_deductions = ld['categories']['deductions']
        ces = ld['concepts']['CES']['total'] if 'CES' in ld['concepts'] else 0
        ces_part = ld['concepts']['CES_PART']['total'] if 'CES_PART' in ld['concepts'] else 0
        cesantias = ces + ces_part
        neto = total_earnings - total_deductions - cesantias
        # neto = 0 if neto < 0 else neto
        lr[0] = neto
        return lr

    @api.multi
    def _tot_dev(self, ld):
        total_earnings = (ld['categories']['earnings'] + ld['categories']['o_earnings'] +
                          ld['categories']['o_salarial_earnings'] + ld['categories']['comp_earnings'] +
                          ld['categories']['non_taxed_earnings'] + ld['categories']['o_rights'])
        lr[0] = total_earnings
        return lr

    @api.multi
    def _tot_ded(self, ld):
        total_deductions = ld['categories']['deductions']
        if ld['contract'].ded_limit and total_deductions > 0.5 * ld['concepts']['TOT_DEV']['total']:
            if ld['slip_type'] == 'Nomina':
                raise Warning(u"La nomina de {emp} presenta un total de deducciones "
                              u"superior al 50% de los devengos y el contrato esta configurado para limitarlo.".format(
                                emp=self.employee_id.name))
        lr[0] = total_deductions
        return lr

    @api.multi
    def _neto_ces(self, ld):
        """
        Neto a pagar cesantias
        :param ld:
        :return: Valor a pagar al fondo de cesantias
        """
        ces = ld['concepts']['CES']['total'] if 'CES' in ld['concepts'] else 0
        ces_part = ld['concepts']['CES_PART']['total'] if 'CES_PART' in ld['concepts'] else 0

        lr[0] = ces + ces_part
        return lr

    @api.multi
    def _ap_pens(self, ld):
        """
        Aportes a pension
        :param ld:
        :return: Valor de aporte de pension correspondiente al 12% del IBC, se omite en primeras quincenas y se paga si
        el empleado es cotizante normal sin pension
        """
        retired = True if ld['contract'].fiscal_subtype_id.code not in ['00', False] else False
        if not retired:
            prev_ap = sum([p.get_payslip_concept_total('AP_PENS') for p in ld['payslips_month']])
            ibs = ld['concepts']['IBS']['total'] if 'IBS' in ld['concepts'] else 0
            lr[0] = ibs
            if ld['contract'].high_risk:
                lr[2] = 22
            else:
                lr[2] = self.env.user.company_id.percentage_employer
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = amount - prev_ap
            if self.env.user.company_id.ded_round:
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = int(math.ceil(amount / 100.0)) * 100
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _ap_eps(self, ld):
        """
        Aportes en salud
        :param ld:
        :return: Valor de aportes que realiza la empresa en salud, se realiza unicamente en segunda quincena o en
        nominas mensuales, se tiene en cuenta pagos anteriores de estos aportes y retorna el 8.5%
        """
        ibs = ld['concepts']['IBS']['total'] if 'IBS' in ld['concepts'] else 0
        prev_ap = sum([p.get_payslip_concept_total('AP_EPS') for p in ld['payslips_month']])
        if ibs >= 10 * ld['sal_min_ev'] or ld['contract_class'] == 'int' or self.env.user.company_id.nonprofit:
            lr[0] = ibs - prev_ap * 100 / 8.5
            lr[2] = 8.5
            if self.env.user.company_id.ded_round:
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = int(math.ceil(amount / 100.0)) * 100
        elif ld['contract_class'] == 'apr':
            lr[0] = ibs - prev_ap * 100 / 12.5
            lr[2] = 12.5
            if self.env.user.company_id.ded_round:
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = int(math.ceil(amount / 100.0)) * 100
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _ap_ccf(self, ld):
        """
        Aportes a caja de compensacion
        :param ld:
        :return:
        """
        ibp = ld['concepts']['IBP']['total'] if 'IBP' in ld['concepts'] else 0
        prev_ap = sum([p.get_payslip_concept_total('AP_CCF') for p in ld['payslips_month']])
        lr[0] = ibp - prev_ap * 100 / 4
        lr[2] = 4
        if self.env.user.company_id.ded_round:
            amount = lr[0] * lr[1] * lr[2] / 100
            lr[5] = int(math.ceil(amount / 100.0)) * 100
        return lr

    @api.multi
    def _ap_arl(self, ld):
        """
        Aportes riesgos laborales
        :param ld:
        :return: Valor de aportes que realiza la empresa en ARL, se realiza unicamente en segunda quincena o en
        nominas mensuales, se tiene en cuenta pagos anteriores de estos aportes y retorna el porcentaje de riesgo
        asignado en el contrato del empleado
        """
        apr_type = ld['contract'].fiscal_type_id.code
        if (ld['contract_class'] == 'apr' and apr_type == '19') or ld['contract_class'] != 'apr':
            ibr = ld['concepts']['IBR']['total'] if 'IBR' in ld['concepts'] else 0
            prev_ap = sum([p.get_payslip_concept_total('AP_ARL') for p in ld['payslips_month']])
            rate = ld['contract'].pct_arp or ld['contract'].riesgo.pct_risk
            if rate:
                lr[0] = ibr - prev_ap * 100 / rate
            else:
                lr[0] = ibr
            lr[2] = rate
            if self.env.user.company_id.ded_round:
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = int(math.ceil(amount / 100.0)) * 100
        else:
            lr[3] = 'na'

        return lr

    @api.multi
    def _ap_sena(self, ld):
        ibp = ld['concepts']['IBP']['total'] if 'IBP' in ld['concepts'] else 0
        if ibp >= 10 * ld['sal_min_ev'] or ld['contract_class'] == 'int' or self.env.user.company_id.nonprofit:
            prev_ap = sum([p.get_payslip_concept_total('AP_SENA') for p in ld['payslips_month']])
            lr[0] = ibp - prev_ap * 100 / 2
            lr[2] = 2
            if self.env.user.company_id.ded_round:
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = int(math.ceil(amount / 100.0)) * 100
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _ap_icbf(self, ld):
        ibp = ld['concepts']['IBP']['total'] if 'IBP' in ld['concepts'] else 0
        if ibp >= 10 * ld['sal_min_ev'] or ld['contract_class'] == 'int' or self.env.user.company_id.nonprofit:
            prev_ap = sum([p.get_payslip_concept_total('AP_ICBF') for p in ld['payslips_month']])
            lr[0] = ibp - prev_ap * 100 / 3
            lr[2] = 3
            if self.env.user.company_id.ded_round:
                amount = lr[0] * lr[1] * lr[2] / 100
                lr[5] = int(math.ceil(amount / 100.0)) * 100
        else:
            lr[3] = 'na'
        return lr

    @api.multi
    def _prv_prim(self, ld):
        if self.env.user.company_id.simple_provisions:
            earnings = ld['categories']['earnings']
            o_salarial_earnings = ld['categories']['o_salarial_earnings']
            o_rights = ld['categories']['o_rights']
            comp_earnings = ld['categories']['comp_earnings']
            aux_trans = ld['concepts']['AUX_TRANS']['total'] if 'AUX_TRANS' in ld['concepts'] else 0
            prev_earnings = sum([p.get_payslip_category('earnings') for p in ld['payslips_month']])
            prev_o_sal_earn = sum([p.get_payslip_category('o_salarial_earnings') for p in ld['payslips_month']])
            prev_o_rights = sum([p.get_payslip_category('o_rights') for p in ld['payslips_month']])
            prev_comp_earn = sum([p.get_payslip_category('comp_earnings') for p in ld['payslips_month']])
            prev_aux_trans = sum([p.get_payslip_concept_total('AUX_TRANS') for p in ld['payslips_month']])
            prima_prev = sum([p.get_payslip_concept_total('PRIMA') for p in ld['payslips_month']])
            prv_prev = sum([p.get_payslip_concept_total('PRV_PRIM') for p in ld['payslips_month']]) * 100/8.33
            total_earn = (earnings + prev_earnings + o_salarial_earnings + aux_trans + prev_o_sal_earn + o_rights +
                          prev_o_rights + comp_earnings + prev_comp_earn + prev_aux_trans - prima_prev - prv_prev)
            lr[0] = total_earn
            lr[2] = 8.33
        else:
            # Calculo de fechas de referencia para calculos
            k_dt_start = ld['contract'].date_start
            ref_month = '01' if int(ld['period'].start_period[5:7]) <= 6 else '07'
            ref_date = ld['period'].start_period[0:4] + '-' + ref_month + '-01'
            if ref_date < k_dt_start:
                ref_date = k_dt_start
            ref_to_date = datetime.strftime(datetime.strptime(
                ld['period'].end_period, "%Y-%m-%d"), "%Y-%m-%d")
            day_to = monthrange(int(ref_to_date[0:4]), int(ref_to_date[5:7]))[2]
            ref_to_date = str(ref_to_date[0:8]) + str(day_to)
            if ld['contract'].date_end and ld['contract'].date_end < ref_to_date:
                ref_to_date = ld['contract'].date_end

            prima_data = self.get_prst(ref_date, ref_to_date, ld, include=True, prst='prima')

            provs = self.get_interval_concept('PRV_PRIM', ref_date, ref_to_date)
            t_provs = sum([x[1] for x in provs])

            log = [
                ('FECHA DESDE', dt2f(ref_date)),
                ('FECHA HASTA', dt2f(ref_to_date)),
                ('DIAS LABORADOS', prima_data['days']),
                ('DIAS DE LICENCIA', prima_data['days_mat']),
                ('DIAS DE SUSPENSION', prima_data['susp']),
                ('CAMBIO DE SALARIO', prima_data['wc']),
                ('TOTAL SALARIO', prima_data['twage']),
                ('TOTAL VARIABLE', prima_data['total_variable']),
                ('BASE', prima_data['base']),
                ('NETO PRIMA A LA FECHA', prima_data['pres']),
                ('PARCIALES', prima_data['partials']),
                ('PROVISIONES REALIZADAS', t_provs)
            ]
            lr[0] = prima_data['pres'] - t_provs
            lr[6] = log

        return lr

    @api.multi
    def _prv_ces(self, ld):
        if self.env.user.company_id.simple_provisions:
            earnings = ld['categories']['earnings']
            o_salarial_earnings = ld['categories']['o_salarial_earnings']
            o_rights = ld['categories']['o_rights']
            comp_earnings = ld['categories']['comp_earnings']
            aux_trans = ld['concepts']['AUX_TRANS']['total'] if 'AUX_TRANS' in ld['concepts'] else 0
            prev_earnings = sum([p.get_payslip_category('earnings') for p in ld['payslips_month']])
            prev_o_sal_earn = sum([p.get_payslip_category('o_salarial_earnings') for p in ld['payslips_month']])
            prev_o_rights = sum([p.get_payslip_category('o_rights') for p in ld['payslips_month']])
            prev_comp_earn = sum([p.get_payslip_category('comp_earnings') for p in ld['payslips_month']])
            prev_aux_trans = sum([p.get_payslip_concept_total('AUX_TRANS') for p in ld['payslips_month']])
            prima_prev = sum([p.get_payslip_concept_total('PRIMA') for p in ld['payslips_month']])
            prv_prev = sum([p.get_payslip_concept_total('PRV_CES') for p in ld['payslips_month']]) * 100/8.33
            total_earn = (earnings + prev_earnings + o_salarial_earnings + aux_trans + prev_o_sal_earn + o_rights +
                          prev_o_rights + comp_earnings + prev_comp_earn + prev_aux_trans - prima_prev - prv_prev)
            lr[0] = total_earn
            lr[2] = 8.33
        else:
            # Calculo de fechas de referencia para calculos
            k_dt_start = ld['contract'].date_start
            ref_month = '01'
            ref_date = ld['period'].start_period[0:4] + '-' + ref_month + '-01'
            if ref_date < k_dt_start:
                ref_date = k_dt_start
            ref_to_date = datetime.strftime(datetime.strptime(
                ld['period'].end_period, "%Y-%m-%d"), "%Y-%m-%d")
            day_to = monthrange(int(ref_to_date[0:4]), int(ref_to_date[5:7]))[2]
            ref_to_date = str(ref_to_date[0:8]) + str(day_to)
            if ld['contract'].date_end and ld['contract'].date_end < ref_to_date:
                ref_to_date = ld['contract'].date_end

            ces_data = self.get_prst(ref_date, ref_to_date, ld, include=True, prst='ces')

            provs = self.get_interval_concept('PRV_CES', ref_date, ref_to_date)
            t_provs = sum([x[1] for x in provs])

            log = [
                ('FECHA DESDE', dt2f(ref_date)),
                ('FECHA HASTA', dt2f(ref_to_date)),
                ('DIAS LABORADOS', ces_data['days']),
                ('DIAS DE LICENCIA', ces_data['days_mat']),
                ('DIAS DE SUSPENSION', ces_data['susp']),
                ('CAMBIO DE SALARIO', ces_data['wc']),
                ('TOTAL SALARIO', ces_data['twage']),
                ('TOTAL VARIABLE', ces_data['total_variable']),
                ('BASE', ces_data['base']),
                ('NETO CESANTIAS A LA FECHA', ces_data['pres']),
                ('PARCIALES', ces_data['partials']),
                ('PROVISIONES REALIZADAS', t_provs)
            ]
            lr[0] = ces_data['pres'] - t_provs
            lr[6] = log

        return lr

    @api.multi
    def _prv_ices(self, ld):
        if self.env.user.company_id.simple_provisions:
            prv_ces = ld['concepts']['PRV_CES']['total'] if 'PRV_CES' in ld['concepts'] else 0
            lr[0] = prv_ces
            lr[2] = 12
        else:
            # Calculo de fechas de referencia para calculos
            k_dt_start = ld['contract'].date_start
            ref_month = '01'
            ref_date = ld['period'].start_period[0:4] + '-' + ref_month + '-01'
            if ref_date < k_dt_start:
                ref_date = k_dt_start
            ref_to_date = datetime.strftime(datetime.strptime(
                ld['period'].end_period, "%Y-%m-%d"), "%Y-%m-%d")
            day_to = monthrange(int(ref_to_date[0:4]), int(ref_to_date[5:7]))[2]
            ref_to_date = str(ref_to_date[0:8]) + str(day_to)
            if ld['contract'].date_end and ld['contract'].date_end < ref_to_date:
                ref_to_date = ld['contract'].date_end

            ces_data = self.get_prst(ref_date, ref_to_date, ld, include=True, prst='ces')

            ices = ces_data['pres'] * 0.12 / 360 * ces_data['days']

            provs = self.get_interval_concept('PRV_ICES', ref_date, ref_to_date)
            t_provs = sum([x[1] for x in provs])

            prev_ices_itv = self.get_interval_concept('ICES_PART', ref_date, ref_to_date)
            prev_ices = sum([x[1] for x in prev_ices_itv])

            net_ices = ices - t_provs - prev_ices

            lr[0] = ces_data['pres']
            lr[5] = net_ices
            log = [
                ('FECHA DESDE', dt2f(ref_date)),
                ('FECHA HASTA', dt2f(ref_to_date)),
                ('DIAS LABORADOS', ces_data['days']),
                ('DIAS DE LICENCIA', ces_data['days_mat']),
                ('DIAS DE SUSPENSION', ces_data['susp']),
                ('CAMBIO DE SALARIO', ces_data['wc']),
                ('TOTAL SALARIO', ces_data['twage']),
                ('TOTAL VARIABLE', ces_data['total_variable']),
                ('BASE', ces_data['base']),
                ('NETO CESANTIAS', ces_data['pres']),
                ('INTERESES A LA FECHA', ices),
                ('PROVISIONES PREVIAS', t_provs)
            ]
            lr[6] = log

            return lr
        return lr

    @api.multi
    def _prv_vac(self, ld):
        if self.env.user.company_id.simple_provisions:
            earnings = ld['categories']['earnings']
            o_salarial_earnings = ld['categories']['o_salarial_earnings']
            o_rights = ld['categories']['o_rights']
            prev_earnings = sum([p.get_payslip_category('earnings') for p in ld['payslips_month']])
            prev_o_sal_earn = sum([p.get_payslip_category('o_salarial_earnings') for p in ld['payslips_month']])
            prev_o_rights = sum([p.get_payslip_category('o_rights') for p in ld['payslips_month']])
            prima_prev = sum([p.get_payslip_concept_total('PRIMA') for p in ld['payslips_month']])
            prv_prev = sum([p.get_payslip_concept_total('PRV_VAC') for p in ld['payslips_month']]) * 100/4.17
            total_earn = earnings + prev_earnings + o_salarial_earnings + prev_o_sal_earn + o_rights + prev_o_rights - prima_prev - prv_prev
            lr[0] = total_earn
            lr[2] = 4.17
        else:
            k_dt_start = ld['contract'].date_start
            ref_date = datetime.strftime(datetime.strptime(
                ld['period'].start_period[0:8] + '01', "%Y-%m-%d") - relativedelta(months=11), "%Y-%m-%d")
            if ref_date < k_dt_start:
                ref_date = k_dt_start
            ref_to_date = ld['contract'].date_end or ld['period'].end_period
            ref_to_date = str(ref_to_date[0:8]) + str(ref_to_date[8:10] if int(ref_to_date[8:10]) < 31 else 30)

            sus_lic = self.leave_days_ids.filtered(lambda x: x.state == 'validate' and x.holiday_status_id.no_payable)
            qty_sus = 0
            for aus in sus_lic:
                qty_sus += aus.days_assigned
            qty = ld['contract'].get_pend_vac(date_calc=ref_to_date, sus=qty_sus)
            sus_vac_book = ld['contract'].get_sus_per()

            payslip_vac = self.leave_ids.filtered(lambda x: x.state == 'validate'
                                                  and x.holiday_status_id.vacaciones)
            qty_disf = 0
            for aus in payslip_vac:
                qty_disf += aus.number_of_days_temp

            payed_per = ld['concepts']['VAC_PAG']['qty'] if 'VAC_PAG' in ld['concepts'] else 0

            qty -= (qty_disf + payed_per)

            days_itval = days360(ref_date, ref_to_date)
            if days_itval > 360:
                days_itval = 360

            # Calculo de acumulados
            earnings = self.get_interval_category('earnings', ref_date, ref_to_date, ('BASICO',))
            comp_earnings = self.get_interval_category('comp_earnings', ref_date, ref_to_date)
            o_salarial_earnings = self.get_interval_category('o_salarial_earnings', ref_date, ref_to_date)

            # Informacion de propia nomina
            a_basico = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0
            a_earnings = ld['categories']['earnings'] - a_basico
            a_comp_earnings = ld['categories']['comp_earnings']
            a_o_salarial_earnings = ld['categories']['o_salarial_earnings']

            # Promedios del periodo
            t_earnings = (sum([x[1] for x in earnings]) + a_earnings) * 30 / days_itval if days_itval else 0
            t_comp_earnings = (sum([x[1] for x in comp_earnings]) + a_comp_earnings) * 30 / days_itval if days_itval else 0
            # t_comp_earnings = 0
            t_other = (sum([x[1] for x in o_salarial_earnings]) + a_o_salarial_earnings) * 30 / days_itval if days_itval else 0

            rwq = ("SELECT wage from hr_contract_salary_change "
                   "WHERE contract_id = {c} "
                   "AND date <= '{dt}' "
                   "ORDER BY date desc LIMIT 1".format(c=ld['contract'].id, dt=ref_to_date))
            rw = orm.fetchone(self._cr, rwq)
            if rw:
                ref_wag = rw[0]
            else:
                ref_wag = ld['wage']

            avg_other = ref_wag + t_earnings + t_comp_earnings + t_other
            reg_prov = (avg_other * qty / 30)

            if self.env.user.company_id.prv_vac_cpt:
                provs = self.get_interval_concept('PRV_VAC', ref_date, ref_to_date)
                vac_disf_a = ld['concepts']['VAC_DISF']['total'] if 'VAC_DISF' in ld['concepts'] else 0
                vac_pag_a = ld['concepts']['VAC_PAG']['total'] if 'VAC_PAG' in ld['concepts'] else 0
                t_provs = sum([x[1] for x in provs]) - vac_disf_a - vac_pag_a
            else:
                prv_vacq = ("SELECT id "
                            "from hr_concept "
                            "where code = 'PRV_VAC'")

                prv_vac_id = orm.fetchall(self._cr, prv_vacq)[0][0]
                pvc = self.env['hr.concept'].browse(prv_vac_id)

                accounts = (pvc.reg_adm_credit.id, pvc.reg_com_credit.id, pvc.reg_ope_credit.id,
                            pvc.int_adm_credit.id, pvc.int_com_credit.id, pvc.int_ope_credit.id)

                provs_q = ("select rp.ref, he.id, sum(aml.credit) - sum(aml.debit) "
                           "from account_move_line aml "
                           "left join res_partner rp on rp.id = aml.partner_id "
                           "left join hr_employee he on he.codigo = rp.ref "
                           "where aml.state = 'valid' "
                           "and aml.account_id in {accounts} "
                           "and aml.date <= '{date_to}' "
                           "and he.id = {he} "
                           "group by rp.ref, he.id ".format(he=ld['contract'].employee_id.id,
                                                            accounts=accounts, date_to=ref_to_date))
                provs = orm.fetchall(self._cr, provs_q)

                t_provs = provs[0][2] if provs else 0

            log = [
                ('SALARIO', ref_wag),
                ('FECHA INICIO', dt2f(ref_date)),
                ('FECHA FIN', dt2f(ref_to_date)),
                ('PROMEDIO DEVENGOS', t_earnings),
                ('PROMEDIO INGRESOS COMPLEMENTARIOS', t_comp_earnings),
                ('PROMEDIO OTROS INGRESOS SALARIALES', t_other),
                ('DIAS REFERENCIA SIN LICENCIAS', days_itval),
                ('LICENCIAS/SUSPENSIONES NOMINA', qty_sus),
                ('LICENCIAS/SUSPENSIONES LIBRO VACACIONES', sus_vac_book),
                ('DIAS DE VACACIONES PROVISIONADOS', qty),
                ('TOTAL PROVISIONADO A LA FECHA', reg_prov),
                ('PROVISIONES REALIZADAS PREVIAMENTE', t_provs)
            ]
            lr[6] = log

            lr[0] = reg_prov - t_provs

        return lr

    @api.multi
    def _ret_ctg_afc(self, ld):
        # Hack rendimiento

        afc_flag = 0
        for c in ld['concepts']:
            is_ded = True if ld['concepts'][c]['category'] == 'deductions' else False
            is_afc = True if ld['concepts'][c]['afc'] else False
            if is_ded and is_afc:
                afc_flag += ld['concepts'][c]['total']
        for p in ld['payslips_month']:
            for c in p.concept_ids:
                is_ded = True if c.category == 'deductions' else False
                is_afc = True if c.afc else False
                if is_ded and is_afc:
                    afc_flag += c.total
        if not afc_flag:
            rtf = ld['concepts']['RTEFTE']['total'] if 'RTEFTE' in ld['concepts'] else 0
            rtf_rate = ld['concepts']['RTEFTE']['rate'] if 'RTEFTE' in ld['concepts'] else 0
            lr[0] = rtf
            lr[1] = rtf_rate
            return lr

        taxed_inc = (ld['categories']['earnings'] + ld['categories']['o_earnings'] +
                     ld['categories']['o_salarial_earnings'] + ld['categories']['comp_earnings'] +
                     ld['categories']['o_rights'])

        prev_earn = sum([p.get_payslip_category('earnings') for p in ld['payslips_month']])
        prev_o_sal_earn = sum([p.get_payslip_category('o_earnings') for p in ld['payslips_month']])
        prev_o_earn = sum([p.get_payslip_category('o_salarial_earnings') for p in ld['payslips_month']])
        prev_comp_earn = sum([p.get_payslip_category('comp_earnings') for p in ld['payslips_month']])
        prev_o_rights = sum([p.get_payslip_category('o_rights') for p in ld['payslips_month']])

        taxed_inc += prev_earn + prev_o_sal_earn + prev_o_earn + prev_comp_earn + prev_o_rights

        prima = ld['concepts']['PRIMA']['total'] if 'PRIMA' in ld['concepts'] else 0
        prim_liq = ld['concepts']['PRIM_LIQ']['total'] if 'PRIM_LIQ' in ld['concepts'] else 0
        prima_prev = sum([p.get_payslip_concept_total('PRIMA') for p in ld['payslips_month']])
        prim_liq_prev = sum([p.get_payslip_concept_total('PRIM_LIQ') for p in ld['payslips_month']])

        if not ld['contract'].p2:
            taxed_inc -= (prima + prim_liq + prima_prev + prim_liq_prev)

        sch_pay = ld['sch_pay']
        bmt = ld['bmt']

        # Proyeccion de retencion en la fuente con el 50% de salario
        rtfprj = self.env.user.company_id.rtf_projection
        if rtfprj and sch_pay == 'bi-monthly' and bmt == 'first' and ld['slip_type'] != 'Liquidacion':
            taxed_inc += ld['wage'] / 2

        tax_cat_ls = ['earnings', 'o_earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights']
        uvt = ld['uvt']
        contract = ld['contract']

        untaxed_inc = 0  # Ingresos no gravados
        ing_no_const = 0  # Ingresos no constitutivos de renta
        vol_cont = 0  # Aportes voluntarios de pension y afc
        ap_vol = 0
        afc = 0

        for c in ld['concepts']:
            is_ded = True if ld['concepts'][c]['category'] == 'deductions' else False
            is_reg = True if ld['concepts'][c]['origin'] == 'regular' else False
            is_ex = True if ld['concepts'][c]['ex_rent'] else False
            is_afc = True if ld['concepts'][c]['afc'] else False
            if is_ded and is_reg and c != 'RTEFTE':
                ing_no_const += ld['concepts'][c]['total']
            if is_ded and is_ex:
                ap_vol += ld['concepts'][c]['total']
                vol_cont += ld['concepts'][c]['total']
            if is_ded and is_afc:
                afc += ld['concepts'][c]['total']
                vol_cont += ld['concepts'][c]['total']
            if ld['concepts'][c]['category'] in tax_cat_ls and is_ex:
                untaxed_inc += ld['concepts'][c]['total']

        # Validacion de nominas del periodo
        for p in ld['payslips_month']:
            for c in p.concept_ids:
                is_ded = True if c.category == 'deductions' else False
                is_reg = True if c.origin == 'regular' else False
                is_ex = True if c.ex_rent else False
                is_afc = True if c.afc else False
                if is_ded and is_reg and c.code != 'RTEFTE':
                    ing_no_const += c.total
                # TODO add is_afc con mismas caracteristicas
                if is_ded and is_ex:
                    ap_vol += c.total
                    vol_cont += c.total
                if is_ded and is_afc:
                    afc += c.total
                    vol_cont += c.total
                if c.category in tax_cat_ls and is_ex:
                    untaxed_inc += c.total

        if rtfprj and sch_pay == 'bi-monthly' and bmt == 'first' and ld['slip_type'] != 'Liquidacion':
            # Proyeccion de deducciones de la segunda quincena
            if self.env.user.company_id.ded_round:
                ing_no_const += int(math.ceil((ld['wage'] * 0.04 / 2) / 100.0)) * 100
                ing_no_const += int(math.ceil((ld['wage'] * 0.04 / 2) / 100.0)) * 100
                ing_no_const += int(math.ceil((ld['wage'] * 0.01 / 2) / 100.0)) * 100
            else:
                ing_no_const += ld['wage'] * 0.09 / 2

        net_income = taxed_inc - ing_no_const
        # Descarte por derecha si el ingreso no es considerable
        discard = True if net_income == 0 else False

        if not discard:
            # Rentas exentas
            # #### Deducibles ##### #
            # Dependientes
            dep_base = taxed_inc * 0.1
            if contract.ded_dependents:
                ded_depend = dep_base if dep_base <= 32 * uvt else 32 * uvt
                ded_depend = ded_depend
            else:
                ded_depend = 0

            # Medicina prepagada
            base_mp = contract.ded_prepaid
            ded_mp = base_mp if base_mp <= 16 * uvt else 16 * uvt
            ded_mp = ded_mp

            # Deducion por vivienda
            base_liv = contract.ded_living
            ded_liv = base_liv if base_liv <= 100 * uvt else 100 * uvt
            ded_liv = ded_liv

            total_deduct = ded_depend + ded_mp + ded_liv

            # Aportes voluntarios
            vol_cont -= afc

            # Top25 deducible por ley de los ingresos - deducciones existentes
            base25 = (net_income - total_deduct - vol_cont) * 0.25
            top25 = base25 if base25 <= 240 * uvt else 240 * uvt

            # Top40
            base40 = net_income * 0.4
            baserex = total_deduct + vol_cont + top25
            rent_ex = baserex if baserex <= base40 else base40

            brtf = net_income - rent_ex

            uvt = ld['uvt']
            if brtf:
                if ld['contract'].p2:
                    rtf_rate = ld['contract'].rtf_rate
                else:
                    basic = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0
                    vac_disf = ld['concepts']['VAC_DISF']['qty'] if 'VAC_DISF' in ld['concepts'] else 0
                    pre_vac = sum([p.get_payslip_concept('VAC_DISF').qty for p in ld['payslips_month']])
                    vac_disf += pre_vac
                    pre_basic = sum([p.get_payslip_concept_total('BASICO') for p in ld['payslips_month']])
                    basic += pre_basic
                    adjust, ded_pen, ded_eps, ded_fon, ded_fsu = 0, 0, 0, 0, 0

                    proj_base = brtf + adjust - ded_pen - ded_eps - ded_fon - ded_fsu
                    b_uvt = proj_base / uvt
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
                    rtf = conv * uvt
                    rtf_rate = rtf * 100 / brtf
                prev_rtf = sum([p.get_payslip_concept_total('RTEFTE') for p in ld['payslips_month']])
                if not rtf_rate:
                    if prev_rtf:
                        lr[2] = rtf_rate
                        lr[0] = brtf
                        lr[5] = prev_rtf * -1
                    else:
                        lr[3] = 'na'
                else:
                    lr[2] = rtf_rate
                    lr[0] = brtf

                    rtf_month = lr[0] * lr[1] * lr[2] / 100
                    if prev_rtf > 0:
                        if self.env.user.company_id.rtf_round:
                            lr[5] = round(rtf_month - prev_rtf, -2)
                        else:
                            lr[5] = rtf_month - prev_rtf
                    else:
                        lr[5] = round(rtf_month, -2)

                # Generacion de computation log
                log = [('TOTAL APORTES VOLUNTARIOS', afc)]
                lr[6] = log
        return lr

    @api.multi
    def _ret_ctg_dif_afc(self, ld):
        real_rtf = ld['concepts']['RTEFTE']['total'] if 'RTEFTE' in ld['concepts'] else 0
        fict_rtf = ld['concepts']['RET_CTG_AFC']['total'] if 'RET_CTG_AFC' in ld['concepts'] else 0
        lr[0] = fict_rtf - real_rtf
        return lr

    @api.multi
    def _ret_ctg_fvp(self, ld):
        # Hack rendimiento

        ap_vol_flag = 0

        for c in ld['concepts']:
            is_ded = True if ld['concepts'][c]['category'] == 'deductions' else False
            is_ex = True if ld['concepts'][c]['ex_rent'] else False
            if is_ded and is_ex:
                ap_vol_flag += ld['concepts'][c]['total']
        for p in ld['payslips_month']:
            for c in p.concept_ids:
                is_ded = True if c.category == 'deductions' else False
                is_ex = True if c.ex_rent else False
                if is_ded and is_ex:
                    ap_vol_flag += c.total

        if not ap_vol_flag:
            rtf = ld['concepts']['RTEFTE']['total'] if 'RTEFTE' in ld['concepts'] else 0
            rtf_rate = ld['concepts']['RTEFTE']['rate'] if 'RTEFTE' in ld['concepts'] else 0
            lr[0] = rtf
            lr[1] = rtf_rate
            return lr

        taxed_inc = (ld['categories']['earnings'] + ld['categories']['o_earnings'] +
                     ld['categories']['o_salarial_earnings'] + ld['categories']['comp_earnings'] +
                     ld['categories']['o_rights'])

        prev_earn = sum([p.get_payslip_category('earnings') for p in ld['payslips_month']])
        prev_o_sal_earn = sum([p.get_payslip_category('o_earnings') for p in ld['payslips_month']])
        prev_o_earn = sum([p.get_payslip_category('o_salarial_earnings') for p in ld['payslips_month']])
        prev_comp_earn = sum([p.get_payslip_category('comp_earnings') for p in ld['payslips_month']])
        prev_o_rights = sum([p.get_payslip_category('o_rights') for p in ld['payslips_month']])

        taxed_inc += prev_earn + prev_o_sal_earn + prev_o_earn + prev_comp_earn + prev_o_rights

        prima = ld['concepts']['PRIMA']['total'] if 'PRIMA' in ld['concepts'] else 0
        prim_liq = ld['concepts']['PRIM_LIQ']['total'] if 'PRIM_LIQ' in ld['concepts'] else 0
        prima_prev = sum([p.get_payslip_concept_total('PRIMA') for p in ld['payslips_month']])
        prim_liq_prev = sum([p.get_payslip_concept_total('PRIM_LIQ') for p in ld['payslips_month']])

        if not ld['contract'].p2:
            taxed_inc -= (prima + prim_liq + prima_prev + prim_liq_prev)

        sch_pay = ld['sch_pay']
        bmt = ld['bmt']

        # Proyeccion de retencion en la fuente con el 50% de salario
        rtfprj = self.env.user.company_id.rtf_projection
        if rtfprj and sch_pay == 'bi-monthly' and bmt == 'first' and ld['slip_type'] != 'Liquidacion':
            taxed_inc += ld['wage'] / 2

        tax_cat_ls = ['earnings', 'o_earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights']
        uvt = ld['uvt']
        contract = ld['contract']

        untaxed_inc = 0  # Ingresos no gravados
        ing_no_const = 0  # Ingresos no constitutivos de renta
        vol_cont = 0  # Aportes voluntarios de pension y afc
        ap_vol = 0
        afc = 0

        for c in ld['concepts']:
            is_ded = True if ld['concepts'][c]['category'] == 'deductions' else False
            is_reg = True if ld['concepts'][c]['origin'] == 'regular' else False
            is_ex = True if ld['concepts'][c]['ex_rent'] else False
            is_afc = True if ld['concepts'][c]['afc'] else False
            if is_ded and is_reg and c != 'RTEFTE':
                ing_no_const += ld['concepts'][c]['total']
            if is_ded and is_ex:
                ap_vol += ld['concepts'][c]['total']
                vol_cont += ld['concepts'][c]['total']
            if is_ded and is_afc:
                afc += ld['concepts'][c]['total']
                vol_cont += ld['concepts'][c]['total']
            if ld['concepts'][c]['category'] in tax_cat_ls and is_ex:
                untaxed_inc += ld['concepts'][c]['total']

        # Validacion de nominas del periodo
        for p in ld['payslips_month']:
            for c in p.concept_ids:
                is_ded = True if c.category == 'deductions' else False
                is_reg = True if c.origin == 'regular' else False
                is_ex = True if c.ex_rent else False
                is_afc = True if c.afc else False
                if is_ded and is_reg and c.code != 'RTEFTE':
                    ing_no_const += c.total
                # TODO add is_afc con mismas caracteristicas
                if is_ded and is_ex:
                    ap_vol += c.total
                    vol_cont += c.total
                if is_ded and is_afc:
                    afc += c.total
                    vol_cont += c.total
                if c.category in tax_cat_ls and is_ex:
                    untaxed_inc += c.total

        if rtfprj and sch_pay == 'bi-monthly' and bmt == 'first' and ld['slip_type'] != 'Liquidacion':
            # Proyeccion de deducciones de la segunda quincena
            ing_no_const += ld['wage'] * 0.09 / 2

        net_income = taxed_inc - ing_no_const
        # Descarte por derecha si el ingreso no es considerable
        discard = True if net_income == 0 else False

        if not discard:
            # Rentas exentas
            # #### Deducibles ##### #
            # Dependientes
            dep_base = taxed_inc * 0.1
            if contract.ded_dependents:
                ded_depend = dep_base if dep_base <= 32 * uvt else 32 * uvt
                ded_depend = ded_depend
            else:
                ded_depend = 0

            # Medicina prepagada
            base_mp = contract.ded_prepaid
            ded_mp = base_mp if base_mp <= 16 * uvt else 16 * uvt
            ded_mp = ded_mp

            # Deducion por vivienda
            base_liv = contract.ded_living
            ded_liv = base_liv if base_liv <= 100 * uvt else 100 * uvt
            ded_liv = ded_liv

            total_deduct = ded_depend + ded_mp + ded_liv

            # Aportes voluntarios
            vol_cont -= ap_vol

            # Top25 deducible por ley de los ingresos - deducciones existentes
            base25 = (net_income - total_deduct - vol_cont) * 0.25
            top25 = base25 if base25 <= 240 * uvt else 240 * uvt

            # Top40
            base40 = net_income * 0.4
            baserex = total_deduct + vol_cont + top25
            rent_ex = baserex if baserex <= base40 else base40

            brtf = net_income - rent_ex

            uvt = ld['uvt']
            if brtf:
                if ld['contract'].p2:
                    rtf_rate = ld['contract'].rtf_rate
                else:
                    basic = ld['concepts']['BASICO']['total'] if 'BASICO' in ld['concepts'] else 0
                    vac_disf = ld['concepts']['VAC_DISF']['qty'] if 'VAC_DISF' in ld['concepts'] else 0
                    pre_vac = sum([p.get_payslip_concept('VAC_DISF').qty for p in ld['payslips_month']])
                    vac_disf += pre_vac
                    pre_basic = sum([p.get_payslip_concept_total('BASICO') for p in ld['payslips_month']])
                    basic += pre_basic
                    adjust, ded_pen, ded_eps, ded_fon, ded_fsu = 0, 0, 0, 0, 0

                    proj_base = brtf + adjust - ded_pen - ded_eps - ded_fon - ded_fsu
                    b_uvt = proj_base / uvt
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
                    rtf = conv * uvt
                    rtf_rate = rtf * 100 / brtf
                prev_rtf = sum([p.get_payslip_concept_total('RTEFTE') for p in ld['payslips_month']])
                if not rtf_rate:
                    if prev_rtf:
                        lr[2] = rtf_rate
                        lr[0] = brtf
                        lr[5] = prev_rtf * -1
                    else:
                        lr[3] = 'na'
                else:
                    lr[2] = rtf_rate
                    lr[0] = brtf

                    rtf_month = lr[0] * lr[1] * lr[2] / 100
                    if prev_rtf > 0:
                        if self.env.user.company_id.rtf_round:
                            lr[5] = round(rtf_month - prev_rtf, -2)
                        else:
                            lr[5] = rtf_month - prev_rtf
                    else:
                        lr[5] = round(rtf_month, -2)

                # Generacion de computation log
                log = [('TOTAL APORTES VOLUNTARIOS', ap_vol)]
                lr[6] = log
        return lr

    @api.multi
    def _ret_ctg_dif_fvp(self, ld):
        real_rtf = ld['concepts']['RTEFTE']['total'] if 'RTEFTE' in ld['concepts'] else 0
        fict_rtf = ld['concepts']['RET_CTG_FVP']['total'] if 'RET_CTG_FVP' in ld['concepts'] else 0
        lr[0] = fict_rtf - real_rtf
        return lr

    @api.multi
    def _costo(self, ld):
        total_earnings = (ld['categories']['earnings'] + ld['categories']['o_earnings'] +
                          ld['categories']['o_salarial_earnings'] + ld['categories']['comp_earnings'] +
                          ld['categories']['non_taxed_earnings'] + ld['categories']['o_rights'])
        total_contr = ld['categories']['contributions']
        total_prov = ld['categories']['provisions']
        cost = total_earnings + total_contr + total_prov
        lr[0] = cost
        return lr









