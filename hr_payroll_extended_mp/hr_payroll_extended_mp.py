# -*- coding: utf-8 -*-
import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp.addons.edi import EDIMixin
from openerp.osv import fields, osv
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class hr_payroll_prestamo(osv.osv, EDIMixin):
    _inherit = "hr.payroll.prestamo"

    _columns = {
        'type_dicount': fields.selection([('mes', 'Mensual'), ('quince', 'Quincenal')], 'Tipo Descuento',
                                         required=True),
    }

    def calcular_todos(self, cr, uid, ids, context=None):
        prestamos = self.pool.get('hr.payroll.prestamo').search(cr, uid, [('type_dicount', '=', 'quince')],
                                                                context=context)
        c = 0
        for prestamo in prestamos:
            c += 1
            self.pool.get('hr.payroll.prestamo').browse(cr, uid, prestamo, context=context).calcular_button()
            _logger.info('van ' + str(c) + ' de ' + str(len(prestamos)))
        return True

    def calcular_button(self, cr, uid, ids, context=None):
        cuotas_obj = self.pool.get('hr.payroll.prestamo.cuota')
        acumulado = 0
        for prestamo in self.browse(cr, uid, ids, context):
            fecha, cantidad_cuotas = False, 0
            if not prestamo.date:
                raise osv.except_osv(_('Error!'), _('Tiene que llenar la fecha en la que se dio el prestamo!'))
            if prestamo.cuotas_ids:
                for cuota in prestamo.cuotas_ids:
                    if not cuota.payslip_id:
                        cuotas_obj.unlink(cr, SUPERUSER_ID, cuota.id, context=context)
                    else:
                        cantidad_cuotas += 1
                        acumulado += cuota.cuota
                        fecha = datetime.strptime(cuota.date[0:10], '%Y-%m-%d')
            if not fecha:
                fecha = datetime.strptime(prestamo.date[0:10], '%Y-%m-%d')
            elif fecha < datetime.now():
                fecha = datetime.strptime(str(datetime.now())[0:10], '%Y-%m-%d')
            day, month, year = fecha.day, fecha.month, fecha.year
            quote, months_increment = 1, 0
            for x in range(1, prestamo.numero_cuotas - cantidad_cuotas + 1):
                x -= 1
                if prestamo.type_dicount == 'mes':
                    depreciation_date = (datetime(year, month, day) + relativedelta(months=x))
                else:  # quincenal
                    if quote == 1:
                        if fecha.day > 15:
                            quote = 25
                        else:
                            quote = 15
                    else:
                        if quote == 15:
                            quote = 25
                        else:
                            quote = 15
                    depreciation_date = datetime(year, month, quote) + relativedelta(months=months_increment)
                    if quote == 25:#incrementar un mes
                        months_increment += 1

                cuota_mensual = prestamo.cuota
                # _logger.info('acumulado:' + str(acumulado))
                # _logger.info('total:' + str(prestamo.valor))
                # _logger.info(float(prestamo.valor) == float(acumulado))
                # _logger.info('x:' + str(x))
                if x == prestamo.numero_cuotas or float(prestamo.valor) == float(acumulado):
                    cuota_mensual = float(prestamo.valor) - float(
                        acumulado)  # prestamo.valor - (prestamo.cuota * prestamo.numero_cuotas)
                acumulado += cuota_mensual
                cuotas_obj.create(cr, uid,
                                  {'prestamo_id': prestamo.id, 'cuota': cuota_mensual, 'date': depreciation_date},
                                  context=context)
        return True

#
