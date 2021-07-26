# -*- coding: utf-8 -*-
import base64
import logging
import math
import unicodedata
from datetime import datetime, timedelta

from openerp import models, fields, api
from openerp.exceptions import ValidationError

# from openerp.tools.safe_eval import safe_eval as eval

_logger = logging.getLogger('PILA')


class HRConfigCompanyPILA(models.Model):
    _inherit = 'res.company'

    day_pila = fields.Integer(string='Día pago PILA')
    users_pila = fields.Many2many('res.users', string='Usuarios a notificar PILA')


class HRConfigSettingsPILA(models.TransientModel):
    _name = "hr.config.settings.pila"
    _inherit = 'res.config.settings'

    def _set_days_default(self):
        return self.env.user.company_id.day_pila

    def _set_users_default(self):
        return self.env.user.company_id.users_pila

    day_pila = fields.Integer(string='Día pago PILA en el mes', default=_set_days_default)
    users_pila = fields.Many2many('res.users', string='Usuarios a notificar PILA', default=_set_users_default)

    @api.multi
    def execute_pila(self):
        self.env.cr.execute(
            ''' UPDATE res_company SET day_pila = {day} WHERE id = {company_id}'''.format(day=self.day_pila,
                                                                                          company_id=self.env.user.company_id.id))
        self.env.user.company_id.write({'users_pila': [(6, 0, [x.id for x in self.users_pila])]})
        return True

    @api.multi
    def cancel(self):
        return False


class hrPayrollPILA(models.Model):
    _name = "hr.payroll.pila"
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', required=True, default='<NUEVO>', copy=False, readonly=True, index=True,
                       track_visibility='onchange',
                       help='Este campo indica la secuencia de la planila de aportes, para identificarlas en el tiempo.')
    slip_ids = fields.One2many('hr.payslip', 'pila_id', string='Nominas', copy=False, readonly=False,
                               help='En este campo se deben indicar las nóminas a los cuales se va a realizar la planilla de aportes.')
    payslip_period_id = fields.Many2one('payslip.period', string='Periodo de nómina', required=True, readonly=False,
                                        copy=False, index=True, domain="[('schedule_pay','=','monthly')]",
                                        help='Este campo indica los periodos mensuales en el que se va a generar la planilla de aportes.')
    notes = fields.Text(string='Notas', copy=True,
                        help='En este campo se puede indicar una nota para describir alguna observación sobre la planilla de aportes.')
    file = fields.Binary(string='Archivo TXT', readonly=True, copy=False,
                         help='Este campo almacenará el archivo de PILA generado.')
    file_name = fields.Char(size=64, string='Archivo Plano', track_visibility='onchange')
    type = fields.Many2one('hr.planilla.type', string='Tipo de planilla', required=True,
                           copy=True, help='Este campo indica la planilla de aportes',
                           index=True, track_visibility='onchange')
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Realizado'), ('cancel', 'Cancelado')], string='Estado',
                             index=True, track_visibility='onchange',
                             default='draft',
                             help='Campo que indica los estados de la planilla de aportes, inicialmente se crea en borrador y posteriormente se pasa a realizado cuando ya va a ser la definitiva.')

    _sql_constraints = [
        ('pila_uniq', 'unique(payslip_period_id,type)',
         'Solo debe existeir una planilla de aportes por periodo y tipo.'), ]

    @api.model
    def generate_notification(self):
        self._generate_notification()

    @api.multi
    def _generate_notification(self):
        title = 'PAGO PILA'
        _logger.info('prueba')
        for user in self.env.user.company_id.users_pila:
            # buscar notificaciones por usuario
            self.env.cr.execute(
                " SELECT count(*) FROM avancys_notification WHERE tittle = '{title}' AND state = 'pending' AND user_id = {user_id}".format(
                    title=title, user_id=user.id))
            ids = self.env.cr.dictfetchone()
            _logger.info(ids.get('count', False))
            if ids.get('count', 0) == 0:
                day = self.env.user.company_id.day_pila
                date_limit = datetime(datetime.now().year, datetime.now().month + 1, day)
                for x in range(1, 4):
                    date = date_limit - timedelta(days=x) + timedelta(hours=5)
                    self.env.cr.execute(''' INSERT INTO avancys_notification(user_id,tittle,notification,date,state) 
                        values({user_id},'{title}','{notification}','{date}','{state}')'''.format(user_id=user.id,
                                                                                                  title=title,
                                                                                                  notification='Recuerde que debe pagar PILA antes de ' + date_limit.strftime(
                                                                                                      "%Y-%m-%d"),
                                                                                                  date=date,
                                                                                                  state='pending'))
        return False

    @api.model
    def create(self, vals):
        sequence_id = self.env['ir.sequence'].search([('code', '=', 'hr.payroll.pila')])
        name = self.env['ir.sequence'].next_by_id(sequence_id.id)
        if name:
            vals.update({'name': name})
        res = super(hrPayrollPILA, self).create(vals)
        _logger.info(vals)
        return res

    @api.multi
    def generate_file(self):
        if not self.slip_ids:
            raise ValidationError('Debe agregar nóminas antes de generar el archivo.')
        actual = str(datetime.now()).replace('-', '').replace(':', '').replace('.', '').replace(' ', '')
        final_file_name = 'PLANILLA APORTES ' + actual
        text_final = ''
        line_end = '\r\n'  # CRLF

        def nov(option):
            return option and 'X' or ' '

        def rule(slip, code, property):
            result = 0
            for line in slip.details_by_salary_rule_category:
                if line.code == code:
                    if property == 'quantity':
                        result = line.quantity
                    elif property == 'rate':
                        result = line.rate / 100
                    elif property == 'amount':
                        result = line.amount
                    else:
                        result = line.total
                    break
            return result

        def strip_accents(s):
            new_string = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
            new_string = new_string.encode('ascii', 'replace').replace('?', ' ')
            return new_string

        def roundup(x, factor):
            x = int(x or 0.0)
            result = 0
            if int(x or 0) % factor != 0:
                result = int(math.ceil(float(x or 0) / factor)) * factor
            else:
                result = x
            return result

        class Struct:
            def __init__(self, **entries):
                self.__dict__.update(entries)

        def get_leave_period(self, slip, type):
            result = {'date_from': '', 'date_to': ''}

            for slips in slip.contract_id.slip_ids.filtered(
                    lambda x: x.payslip_period_id.start_period[0:7] == slip.payslip_period_id.start_period[0:7]):
                for leave in slips.leave_ids.filtered(lambda y: y.holiday_status_id.code in type):
                    if leave.date_from > slip.payslip_period_id.start_period[0:8] + '01':
                        result.update({'date_from': leave.date_from[0:10]})
                    else:
                        result.update({'date_from': slip.payslip_period_id.start_period[0:8] + '01'})
                    if leave.date_to < slip.payslip_period_id.end_period[0:10]:
                        result.update({'date_to': leave.date_to[0:10]})
                    else:
                        result.update({'date_to': slip.payslip_period_id.end_period[0:10]})
            return result

        def get_lines(slip, key, sln, lma, ige, vac, irl):
            dias, ibcpension, ibceps, ibcarl, ibcccf, cot_pen = '', '', '', '', '', ''
            cotfonsol, cotfonsub, cotarl, cotccf = '', '', '', ''
            cotsena, coticbf, cotesap, cotmen = '', '', '', ''
            cotarl = 0
            tararl, tarccf = 0.0, 0.0
            date_from, date_to = '', ''
            date_vsp, date_vct = '', ''
            if key > 0:  # otras lineas
                ing, ret, tde, tae, tdp, tap, vsp, correcciones, vst, avp, vct = \
                    False, False, False, False, False, False, False, False, slip.vst if slip.contract_id.fiscal_type_id.code not in ('12') else False, False, False
                if vac:
                    dias = str(rule(slip, 'DIAS_VACACIONES', 'total')).replace('.0', '')
                    if len(str(dias)) > 1:
                        dias = str(dias)[1:]

                    # IBC
                    ibcpension = str(int(rule(slip, 'IBC_LINEPENVAC', 'total')))
                    ibceps = str(int(rule(slip, 'IBC_LINEEPSVAC', 'total')))
                    ibcarl = str(int(rule(slip, 'IBC_LINEARLVAC', 'total')))
                    ibcccf = str(int(rule(slip, 'IBC_LINECCFVAC', 'total')))
                    cotpen = rule(slip, 'COT_PENVAC', 'total')
                    cotfonsol = rule(slip, 'COT_FONSOLVAC', 'total')
                    cotfonsub = rule(slip, 'COT_FONSUBVAC', 'total')
                    coteps = rule(slip, 'COT_EPSVAC', 'total')
                    cotccf = rule(slip, 'COT_CCFVAC', 'total')
                    cotsena = rule(slip, 'COTSENAVAC', 'total')
                    coticbf = rule(slip, 'COTICBFVAC', 'total')
                    tareps = rule(slip, 'TAREPS', 'total')

                    dates = get_leave_period(self, slip, ['VAC'])
                    date_from = dates.get('date_from')
                    date_to = dates.get('date_to')
                if ige:
                    dias = str(rule(slip, 'DIAS_IGE', 'total')).replace('.0', '')
                    if len(str(dias)) > 1:
                        dias = str(dias)[1:]

                    # IBC
                    ibcpension = str(int(rule(slip, 'IBC_LINEPENIGE', 'total')))
                    ibceps = str(int(rule(slip, 'IBC_LINEEPSIGE', 'total')))
                    ibcarl = str(int(rule(slip, 'IBC_LINEARLIGE', 'total')))
                    ibcccf = str(int(rule(slip, 'IBC_LINECCFIGE', 'total')))
                    cotpen = rule(slip, 'COT_PENIGE', 'total')
                    coteps = rule(slip, 'COT_EPSIGE', 'total')
                    cotccf = rule(slip, 'COT_CCFIGE', 'total')
                    cotfonsol = rule(slip, 'COT_FONSOLIGE', 'total')
                    cotfonsub = rule(slip, 'COT_FONSUBIGE', 'total')
                    tareps = rule(slip, 'TAREPS', 'total')

                    dates = get_leave_period(self, slip,
                                             ['PIEGM180','INCAPACIDAD_ENF_GENERAL', 'PRORROGA_INCAPACIDAD_ENF_GENERAL',
                                              'INCAPACIDADMENOR90', 'INCAPACIDADMAYOR180', 'INCAPACIDADMENOR180'])
                    date_from = dates.get('date_from')
                    date_to = dates.get('date_to')
                if sln:
                    dias = str(rule(slip, 'DIAS_SLN', 'total')).replace('.0', '')
                    if len(str(dias)) > 1:
                        dias = str(dias)[1:]

                    # IBC
                    ibcpension = str(int(rule(slip, 'IBC_LINEPENSLN', 'total')))
                    ibceps = str(int(rule(slip, 'IBC_LINEEPSSLN', 'total')))
                    ibcarl = str(int(rule(slip, 'IBC_LINEARLSLN', 'total')))
                    ibcccf = str(int(rule(slip, 'IBC_LINECCFSLN', 'total')))
                    cotpen = rule(slip, 'COT_PENSLN', 'total')
                    coteps = 0
                    cotccf = rule(slip, 'COT_CCFSLN', 'total')
                    cotfonsol = rule(slip, 'COT_FONSOLSLN', 'total')
                    cotfonsub = rule(slip, 'COT_FONSUBSLN', 'total')
                    tareps = 0

                    dates = get_leave_period(self, slip, ['LICENCIA_NO_REMUNERADA', 'SUSPENSION'])
                    date_from = dates.get('date_from')
                    date_to = dates.get('date_to')
                if irl:
                    dias = str(rule(slip, 'DIAS_IRL', 'total')).replace('.0', '')
                    if len(str(dias)) > 1:
                        dias = str(dias)[1:]

                    # IBC
                    ibcpension = str(int(rule(slip, 'IBC_LINEPENIRL', 'total')))
                    ibceps = str(int(rule(slip, 'IBC_LINEEPSIRL', 'total')))
                    ibcarl = str(int(rule(slip, 'IBC_LINEARLIRL', 'total')))
                    ibcccf = str(int(rule(slip, 'IBC_LINECCFIRL', 'total')))
                    cotpen = rule(slip, 'COT_PENIRL', 'total')
                    coteps = rule(slip, 'COT_EPSIRL', 'total')
                    cotccf = rule(slip, 'COT_CCFIRL', 'total')
                    tararl = str(rule(slip, 'TARARL', 'total') / 100000.0) if cotarl > 0 else '0.0'
                    tareps = rule(slip, 'TAREPS', 'total')
                    irl = str(dias)[0:2]

                    dates = get_leave_period(self, slip, ['INCAPACIDAD_ATEP_ARL','AT/EP'])
                    date_from = dates.get('date_from')
                    date_to = dates.get('date_to')
                if lma:
                    dias = str(rule(slip, 'DIAS_LMA', 'total')).replace('.0', '')
                    if len(str(dias)) > 1:
                        dias = str(dias)[1:]

                    # IBC
                    ibcpension = str(int(rule(slip, 'IBC_LINEPENLMA', 'total')))
                    ibceps = str(int(rule(slip, 'IBC_LINEEPSLMA', 'total')))
                    ibcarl = str(int(rule(slip, 'IBC_LINEARLLMA', 'total')))
                    ibcccf = str(int(rule(slip, 'IBC_LINECCFLMA', 'total')))
                    cotpen = rule(slip, 'COT_PENLMA', 'total')
                    coteps = rule(slip, 'COT_EPSLMA', 'total')
                    cotccf = rule(slip, 'COT_CCFLMA', 'total')
                    tararl = str(rule(slip, 'TARARL', 'total') / 100000.0) if cotarl > 0 else '0.0'
                    tareps = rule(slip, 'TAREPS', 'total')
                    irl = str(dias)[0:2]

                    dates = get_leave_period(self, slip, ['LICENCIA_MATERNIDAD','LICENCIA_PATERNIDAD'])
                    date_from = dates.get('date_from')
                    date_to = dates.get('date_to')
            else:  # primera linea
                ing, ret, tde, tae, tdp, tap, vsp, correcciones, vst, avp, vct = \
                    slip.ing, slip.ret, slip.tde, slip.tae, slip.tdp, slip.tap, slip.vsp, slip.correcciones, slip.vst if slip.contract_id.fiscal_type_id.code not in ('12') else False, slip.avp, slip.vct
                dias = str(rule(slip, 'DIAS_LINEA0', 'total')).replace('.0', '')
                if len(str(dias)) > 1:
                    dias = str(dias)[1:]
                # IBC estan iguales porque como se toma la proporcion de los dias, los cuatro ibc seran iguales cuando apliquen, ejemplo: para sena no aplican todos los ibc
                ibcpension = str(int(rule(slip, 'IBC_LINEPEN0', 'total')))
                ibceps = str(int(rule(slip, 'IBC_LINEEPS0', 'total')))
                ibcarl = str(int(rule(slip, 'IBC_LINEARL0', 'total')))
                ibcccf = str(int(rule(slip, 'IBC_LINECCF0', 'total')))

                cotpen = rule(slip, 'COT_LINEPEN0', 'total')
                cotfonsol = rule(slip, 'COT_FONSOL', 'total')
                cotfonsub = rule(slip, 'COT_FONSUB', 'total')
                coteps = rule(slip, 'COT_LINEEPS0', 'total')
                cotarl = rule(slip, 'COT_ARL', 'total')
                cotccf = rule(slip, 'COT_LINECCF0', 'total')
                cotsena = rule(slip, 'COTSENA', 'total')
                coticbf = rule(slip, 'COTICBF', 'total')
                cotesap = rule(slip, 'COTESAP', 'total')
                cotmen = rule(slip, 'COTMEN', 'total')
                tararl = str(rule(slip, 'TARARL', 'total') / 100000.0) if cotarl > 0 else '0.0'
                tareps = rule(slip, 'TAREPS', 'total')
                tarccf = rule(slip, 'TARCCF', 'total')

                if ing:
                    date_from = slip.contract_id.date_start[0:10]
                if ret:
                    date_to = slip.contract_id.date_end[0:10]
                if vsp:
                    date_vsp = slip.payslip_period_id.start_period[0:10]
                if vct:
                    date_vct = slip.payslip_period_id.start_period[0:10]

            return {'dias': dias,
                    'ibcpension': ibcpension.rjust(9, '0'),
                    'ibceps': ibceps.rjust(9, '0'),
                    'ibcarl': ibcarl.rjust(9, '0'),
                    'ibcccf': ibcccf.rjust(9, '0'),
                    'tarpen': str(rule(slip, 'TARPEN', 'total') / 100.0).ljust(7, '0'),
                    'cotpen': str(roundup(cotpen, 100)).rjust(9, '0'),
                    'apovol': ''.rjust(9, '0'),
                    'totpen': str(roundup(cotpen, 100)).rjust(9, '0'),
                    'cotfonsol': str(roundup(cotfonsol, 100)).rjust(9, '0'),
                    'cotfonsub': str(roundup(cotfonsub, 100)).rjust(9, '0'),
                    'valnotret': ''.rjust(9, '0'),
                    'tareps': str(tareps / 1000.0).ljust(7, '0'),
                    'coteps': str(roundup(coteps, 100)).rjust(9, '0'),
                    'upc': ''.rjust(9, '0'),
                    'tararl': str(tararl).ljust(9, '0'),
                    'cotarl': str(roundup(cotarl, 100)).rjust(9, '0'),
                    'tarccf': str(tarccf / 1000.0).ljust(7, '0'),
                    'cotccf': str(roundup(cotccf, 100)).rjust(9, '0'),
                    'tarsena': str(rule(slip, 'TARSENA', 'total') / 100.0).ljust(7, '0'),
                    'cotsena': str(roundup(cotsena, 100)).rjust(9, '0'),
                    'taricbf': str(rule(slip, 'TARICBF', 'total') / 100.0).ljust(7, '0'),
                    'coticbf': str(roundup(coticbf, 100)).rjust(9, '0'),
                    'taresap': str(rule(slip, 'TARESAP', 'total') / 1000.0).ljust(7, '0'),
                    'cotesap': str(roundup(cotesap, 100)).rjust(9, '0'),
                    'tarmen': str(rule(slip, 'TARMEN', 'total') / 100.0).ljust(7, '0'),
                    'cotmen': str(roundup(cotmen, 100)).rjust(9, '0'),
                    'exonerado': rule(slip, 'EXON', 'total'),
                    'horlab': str(int(rule(slip, 'HORLAB', 'total'))).rjust(3, '0'),
                    'slip': slip, 'ing': ing, 'ret': ret,
                    'tde': tde, 'tae': tae, 'tdp': tdp, 'tap': tap, 'vsp': vsp, 'correcciones': correcciones,
                    'vst': vst, 'sln': sln, 'lma': lma, 'ige': ige, 'vac': vac, 'avp': avp, 'vct': vct,
                    'irl': irl or '',
                    'date_from': date_from,
                    'date_to': date_to, 'date_vsp': date_vsp or '',
                    'date_vct': date_vct or ''}

        text_enc = [''] * 23
        text_enc[1] = '01'
        text_enc[2] = '1'  # 2A: lo genera automaticamente el operador de informacion, 1 ELEC, 2 Asistida, #RES 20080625
        text_enc[3] = '0001'  # 2B secuencia
        text_enc[4] = strip_accents(self.env.user.company_id.name).upper().ljust(200, ' ')
        if not self.env.user.company_id.partner_id.ref or not self.env.user.company_id.partner_id.ref_type:
            raise ValidationError(
                "El tercero '%s' no esta correctamente configurado, no tiene documento!" % self.env.user.company_id.partner_id.name)
        text_enc[5] = self.env.user.company_id.partner_id.ref_type.code.ljust(2, ' ')
        text_enc[6] = self.env.user.company_id.partner_id.ref.ljust(16, ' ')
        text_enc[7] = str(self.env.user.company_id.partner_id.dev_ref)
        if not self.type:
            raise ValidationError(
                "El tipo de nomina '%s' no tiene configurado tipo de planilla!" % self.type.name)
        text_enc[8] = self.type.code.ljust(1, ' ')
        text_enc[9] = ''.ljust(10,
                               ' ')  # Numero de la planilla asociada a esta planilla, solo aplica en N,F(del periodo) y A(numero de tipo E)
        text_enc[10] = ''.ljust(10, ' ')  # Fecha de pago Planilla asociada a esta planilla. (AAAA-MM-DD).
        text_enc[11] = 'U'  # Forma de presentacion. U=Unica #TOREWORK
        text_enc[12] = ''.ljust(10, ' ')  # Codigo de la Sucursal
        text_enc[13] = ''.ljust(40, ' ')  # Nombre de la Sucursal

        arl = self.env.user.company_id.arl_id
        if not arl:
            raise ValidationError("La Compania '%s' no tiene ARL configurada!" % self.env.user.company_id.name)
        if not arl.codigo_arl:
            raise ValidationError("El tercero de la ARL '%s' no tiene codigo de ARL configurado!" % arl.name)

        text_enc[14] = arl.codigo_arl.ljust(6, ' ')
        text_enc[15] = self.payslip_period_id.start_period[0:7].ljust(7,
                                                                      ' ')  # Periodo de Pago diferente a salud #se genera automaticamente #RES 20080625 #TOCHECK

        month = self.payslip_period_id.start_period[5:7]
        anio = int(self.payslip_period_id.start_period[0:4])
        if month == '12':
            month = str(anio + 1) + '-01'
        else:
            month = self.payslip_period_id.start_period[0:5] + str(int(month) + 1).rjust(2, '0')
        text_enc[16] = month.ljust(7, ' ')  # Periodo de Pago para salud
        text_enc[17] = ''.ljust(10,
                                ' ')  # Numero de radicacion o de la Planilla, asignado por el operador de informacion
        text_enc[18] = ''.ljust(10, ' ')  # Fecha de Pago

        # contar cantidad de empleados
        employee = []
        total_ibc = 0
        for slip in self.slip_ids:
            if slip.employee_id.id not in employee:
                employee.append(slip.employee_id.id)
            #if slip.tipo_nomina.code == 'PILA':
            #    total_ibc += rule(slip, 'IBCPF', 'total')
        text_enc[19] = str(len(employee)).rjust(5, '0')  # Numero de empleados

        text_enc[20] = "0" #.format(total_ibc).rjust(12,'0')  # valor total de la nomina. sumatoria de la IBC #TOCHECK
        text_enc[21] = '1'.rjust(2, '0')  # tipo de aportante, 1 para Empleador
        text_enc[22] = '0'.rjust(2, '0')  # codigo del operador de informacion

        #for x in text_enc:
        #    text_final += x
        #text_final += line_end

        # Recorre nominas para unificar nominas por contrato, agregando una linea adicional por cada novedad (licencia, incapacidad, etc.)
        slips = {}
        for slip in self.slip_ids:
            # crear el diccionario del contrato si no existe
            key, lines = 0, {}
            if slip.contract_id.id not in slips.keys():  # crear el diccionario por primera vez
                # Diccionario primera linea
                if float(rule(slip, 'DIAS_LINEA0', 'total')) > 100000000:
                    lines[key] = get_lines(slip, key, False, False, False, False,
                                           False)  # params: slip, key, sln, lma, ige, vac, irl

                # Diccionario contrato
                slips[slip.contract_id.id] = {
                    'employee': slip.employee_id,
                    'contract': slip.contract_id,
                    'lines': lines,
                }
            else:  # actualizar los valores en la primera linea de cada contrato
                if float(rule(slip, 'DIAS_LINEA0', 'total')) > 100000000:
                    slips[slip.contract_id.id]['lines'][0] = get_lines(slip, key, False, False, False,
                                                                       False, False)  # params: slip, key, sln, lma, ige, vac, irl

            # Incrementar el key para otras lineas
            if type(slips.get(slip.contract_id.id)) == dict and slip.contract_id.id in slips.keys():
                key = len(slips.get(slip.contract_id.id).get('lines')) + 1

            ######## VACACIONES ########
            # if slip.vac:  # Vacaciones
            if float(rule(slip, 'DIAS_VACACIONES', 'total')) > 100000000:
                if 'vac' not in slips[slip.contract_id.id]['lines'].keys():
                    slips[slip.contract_id.id]['lines']['vac'] = get_lines(slip, key, False, False, False,
                                                                           True,
                                                                           False)  # params: slip, key, sln, lma, ige, vac, irl
                else:
                    slips[slip.contract_id.id]['lines']['vac'].update(get_lines(slip, key, False, False, False,
                                                                                True,
                                                                                False))  # params: slip, key, sln, lma, ige, vac, irl
            ######## IGE ########
            # if slip.ige:  # IGE
            if float(rule(slip, 'DIAS_IGE', 'total')) > 100000000:
                if 'ige' not in slips[slip.contract_id.id]['lines'].keys():
                    slips[slip.contract_id.id]['lines']['ige'] = get_lines(slip, key, False, False, True,
                                                                           False,
                                                                           False)  # params: slip, key, sln, lma, ige, vac, irl
                else:
                    slips[slip.contract_id.id]['lines']['ige'].update(get_lines(slip, key, False, False, True,
                                                                                False,
                                                                                False))  # params: slip, key, sln, lma, ige, vac, irl

            ######## SLN ########
            # if slip.ige:  # SLN
            if float(rule(slip, 'DIAS_SLN', 'total')) > 100000000:
                if 'sln' not in slips[slip.contract_id.id]['lines'].keys():
                    slips[slip.contract_id.id]['lines']['sln'] = get_lines(slip, key, True, False, False,
                                                                           False,
                                                                           False)  # params: slip, key, sln, lma, ige, vac, irl
                else:
                    slips[slip.contract_id.id]['lines']['sln'].update(get_lines(slip, key, True, False, False,
                                                                                False))  # params: slip, key, sln, lma, ige, vac, irl

            ######## IRL / IRP ########
            if float(rule(slip, 'DIAS_IRL', 'total')) > 100000000:
                if 'irl' not in slips[slip.contract_id.id]['lines'].keys():
                    slips[slip.contract_id.id]['lines']['irl'] = get_lines(slip, key, False, False, False,
                                                                           False,
                                                                           True)  # params: slip, key, sln, lma, ige, vac, irl
                else:
                    slips[slip.contract_id.id]['lines']['irl'].update(get_lines(slip, key, False, False, False,
                                                                                False,
                                                                                True))  # params: slip, key, sln, lma, ige, vac, irl

            ######## LMA ########
            if float(rule(slip, 'DIAS_LMA', 'total')) > 100000000:
                if 'lma' not in slips[slip.contract_id.id]['lines'].keys():
                    slips[slip.contract_id.id]['lines']['lma'] = get_lines(slip, key, False, True, False,
                                                                           False,
                                                                           False)  # params: slip, key, sln, lma, ige, vac, irl
                else:
                    slips[slip.contract_id.id]['lines']['lma'].update(get_lines(slip, key, False, True, False,
                                                                                False,
                                                                                False))  # params: slip, key, sln, lma, ige, vac, irl
        # Lineas
        text_line = [''] * 687
        c = 0
        valnom = 0
        for pay in slips:
            payslip = Struct(**slips.get(pay))  # convertir dict en objeto
            text_line[1] = '02'

            text_line[3] = (payslip.employee.partner_id.ref_type.code or '').ljust(2, ' ')
            text_line[4] = (payslip.employee.partner_id.ref or '').ljust(16, ' ')
            text_line[5] = (payslip.contract.fiscal_type_id.code or '').rjust(2, '0')
            text_line[6] = (payslip.contract.fiscal_subtype_id.code or '').rjust(2, '0')

            # Extranjero no obligado a cotizar a pensiones
            ref_type_code = (payslip.employee.partner_id.ref_type.code or '')
            country_code = (payslip.contract.cuidad_desempeno.provincia_id.country_id.code or '')
            country_partner_code = (payslip.employee.partner_id.country_id.code or '')
            text_line[7] = 'X' if ref_type_code in (
                'CE', 'PA', 'CD') and country_partner_code != 'CO' else ' '

            # Colombiano en el exterior
            city = payslip.employee.partner_id.city_id.code
            state = payslip.employee.partner_id.state_id.code
            if payslip.contract.cajacomp:
                city = payslip.contract.cajacomp.city_id.code
                state = payslip.contract.cajacomp.state_id.code
            text_line[8] = 'X' if ref_type_code in ('CC','TI') and payslip.contract.cuidad_desempeno and payslip.contract.cuidad_desempeno.provincia_id.country_id.code != 'CO' and country_partner_code == 'CO' else ' '
            text_line[9] = (state or '').rjust(2,'0') #(payslip.contract.cuidad_desempeno.provincia_id.code or '').rjust(2, ' ')
            text_line[10] = (city or '').rjust(3,'0') #(payslip.contract.cuidad_desempeno.code or ' ').rjust(3, ' ')
            text_line[11] = (payslip.employee.partner_id.primer_apellido or ' ').upper().ljust(20, ' ')
            text_line[12] = (payslip.employee.partner_id.segundo_apellido or ' ').upper().ljust(30, ' ')
            text_line[13] = (payslip.employee.partner_id.primer_nombre or ' ').upper().ljust(20, ' ')
            text_line[14] = (payslip.employee.partner_id.otros_nombres or ' ').upper().ljust(30, ' ')

            # leaves
            for lines in payslip.lines:
                c += 1

                # convertir diccionario lineas en objeto
                line = Struct(**payslip.lines.get(lines))

                # incrementar nro de linea
                text_line[2] = str(c).rjust(5, '0')

                # INDICADORES X
                text_line[15] = nov(line.ing)
                text_line[16] = nov(line.ret)
                text_line[17] = nov(line.tde)
                text_line[18] = nov(line.tae)
                text_line[19] = nov(line.tdp)
                text_line[20] = nov(line.tap)
                text_line[21] = nov(line.vsp)
                text_line[22] = nov(line.correcciones)
                text_line[23] = nov(line.vst)
                text_line[24] = nov(line.sln)
                text_line[25] = nov(line.ige)
                text_line[26] = nov(line.lma)
                text_line[27] = nov(line.vac)
                text_line[28] = nov(line.avp)
                text_line[29] = nov(line.vct)
                text_line[30] = str(line.irl).rjust(2, '0')

                text_line[31] = (payslip.contract.pensiones.codigo_afp or ' ').ljust(6, ' ')
                text_line[32] = ''.rjust(6, ' ')
                text_line[33] = (payslip.contract.eps.codigo_eps or ' ').ljust(6, ' ')
                text_line[34] = ''.rjust(6, ' ')
                text_line[35] = (payslip.contract.cajacomp.codigo_ccf or ' ').ljust(6, ' ')

                text_line[36] = str(line.dias)[0:2]
                text_line[37] = str(line.dias)[2:4]
                text_line[38] = str(line.dias)[4:6]
                text_line[39] = str(line.dias)[6:8]

                # SUELDO DEL CONTRATO
                text_line[40] = "{:09.0f}".format(payslip.contract.wage).rjust(9, '0')

                # INDICADOR CONTRATO INTEGRAL
                text_line[41] = 'X' if payslip.contract.type_id.clase == 'integral' and int(
                    line.exonerado) != 1 else ' '

                # IBC
                text_line[42] = str(line.ibcpension)
                text_line[43] = str(line.ibceps)
                text_line[44] = str(line.ibcarl)
                text_line[45] = str(line.ibcccf)
                valnom+=float(line.ibcccf)
                text_line[46] = str(line.tarpen)
                text_line[47] = str(line.cotpen)
                text_line[48] = str(line.apovol)
                text_line[49] = str(line.apovol)
                text_line[50] = str(line.totpen)
                text_line[51] = str(line.cotfonsol)
                text_line[52] = str(line.cotfonsub)
                text_line[53] = str(line.valnotret)
                text_line[54] = str(line.tareps)
                text_line[55] = str(line.coteps)
                text_line[56] = str(line.upc)
                text_line[57] = ''.rjust(15, ' ')
                text_line[58] = ''.rjust(9, '0')
                text_line[59] = ''.rjust(15, ' ')
                text_line[60] = ''.rjust(9, '0')
                text_line[61] = str(line.tararl)
                text_line[62] = ''.rjust(9, '0')
                text_line[63] = str(line.cotarl)
                text_line[64] = str(line.tarccf)
                text_line[65] = str(line.cotccf)
                text_line[66] = str(line.tarsena)
                text_line[67] = str(line.cotsena)
                text_line[68] = str(line.taricbf)
                text_line[69] = str(line.coticbf)
                text_line[70] = str(line.taresap)
                text_line[71] = str(line.cotesap)
                text_line[72] = str(line.tarmen)
                text_line[73] = str(line.cotmen)
                text_line[74] = ''.rjust(2, ' ')
                text_line[75] = ''.rjust(16, ' ')
                text_line[76] = 'S' if int(line.exonerado) == 1 else 'N'
                text_line[77] = str(payslip.contract.arl.codigo_arl or '').ljust(6, ' ')
                text_line[78] = ''.rjust(1, ' ')
                text_line[79] = ''.rjust(1, ' ')
                text_line[80] = (line.date_from if line.ing else '').rjust(10, ' ')
                text_line[81] = (line.date_to if line.ret else '').rjust(10, ' ')
                text_line[82] = (line.date_vsp if line.vsp else '').rjust(10, ' ')
                text_line[83] = (line.date_from if line.sln else '').rjust(10, ' ')
                text_line[84] = (line.date_to if line.sln else '').rjust(10, ' ')
                text_line[85] = (line.date_from if line.ige else '').rjust(10, ' ')
                text_line[86] = (line.date_to if line.ige else '').rjust(10, ' ')
                text_line[87] = (line.date_from if line.lma else '').rjust(10, ' ')
                text_line[88] = (line.date_to if line.lma else '').rjust(10, ' ')
                text_line[89] = (line.date_from if line.vac else '').rjust(10, ' ')
                text_line[90] = (line.date_to if line.vac else '').rjust(10, ' ')
                text_line[91] = (line.date_vct if line.vct else '').rjust(10, ' ')
                text_line[92] = (line.date_vct if line.vct else '').rjust(10, ' ')
                text_line[93] = (line.date_from if line.irl else '').rjust(10, ' ')
                text_line[94] = (line.date_to if line.irl else '').rjust(10, ' ')
                text_line[95] = str(line.ibcccf) if int(line.exonerado) != 1 else ''.rjust(9, '0')
                text_line[96] = str(line.horlab)
                text_line[97] = ''.rjust(10, ' ')

                for x in text_line:
                    text_final += x
                text_final += line_end
        text_enc[20] = "{:012.0f}".format(valnom).rjust(12,'0')
        text_final_header = ''
        for x in text_enc:
            text_final_header += x
        text_final_header += line_end
        text = text_final_header + text_final 
        file_text = base64.b64encode(text.encode('utf-8'))
        file_name = str(final_file_name + '.txt')
        self.write({'file': file_text, 'file_name': file_name})
        return True

    @api.multi
    def done(self):
        if not self.file:
            raise ValidationError('Debe generar el archivo antes de pasar el estado a realizado.')
        self.state = 'done'
        return True

    @api.multi
    def cancel(self):
        self.state = 'cancel'
        return True

    @api.multi
    def set_to_draft(self):
        self.state = 'draft'
        return True

    @api.multi
    def add_slip(self):
        self.file = False
        # quitar relacion nomina - pila
        sql = " UPDATE hr_payslip SET pila_id = NULL WHERE pila_id is null and date_from >= '{start_date}' AND date_to <= '{end_date}' ".format(
            start_date=self.payslip_period_id.start_date, end_date=self.payslip_period_id.end_date,
            pila_id=self.id)
        self.env.cr.execute(sql)
        # actualizar relacion nomina - pila
        self.env.cr.execute(''' UPDATE hr_payslip 
                                    SET pila_id = {pila_id} 
                                        WHERE pila_id is null 
                                        AND date_from >= '{start_date}' 
                                        AND date_to <= '{end_date}' 
                                        	AND ((payslip_period_id IN (SELECT id 
                                                        FROM payslip_period  
                                                            WHERE (schedule_pay = 'monthly' OR (schedule_pay = 'bi-monthly' 
                                                            AND substring(start_date::varchar, 9, 10)::integer > 15))
                                                    ) AND tipo_nomina IN (SELECT id FROM hr_payslip_type WHERE code in ('PILA')))
                                        OR tipo_nomina IN (SELECT id FROM hr_payslip_type WHERE code in ('Liquidacion')))'''.format(
            start_date=self.payslip_period_id.start_date,
            end_date=self.payslip_period_id.end_date,
            pila_id=self.id))
        self.env.cr.commit()
        return True


class hrPayslipPILA(models.Model):
    _inherit = 'hr.payslip'

    pila_id = fields.Many2one('hr.payroll.pila', string='PILA', copy=False, required=False, readonly=False)
