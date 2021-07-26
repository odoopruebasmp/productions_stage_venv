# -*- coding: utf-8 -*-
from openerp.osv import osv, fields
import base64
import csv
from datetime import date, datetime, timedelta
from calendar import monthrange
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _

class import_pay_slip(osv.osv_memory):
    _name = 'import.pay.slip'

    _columns = {
        'binary_file': fields.binary('Select File', required=True)
    }

    def import_payslip(self, cr, uid, ids, context=None):
        if context is None:
            context={}
        payroll_obj = self.pool.get('hr.payslip')
        contract_obj = self.pool.get('hr.contract')
        contract_type_obj = self.pool.get('hr.contract.type')
        employee_obj = self.pool.get('hr.employee')
        payslip_run_obj = self.pool.get('hr.payslip.run')
        period_obj = self.pool.get('payslip.period')
        type_obj = self.pool.get('hr.payslip.type')
        rule_categ_obj = self.pool.get('hr.salary.rule.category')
        rule_obj = self.pool.get('hr.salary.rule')
        journal_obj = self.pool.get('account.journal')
        for data in self.browse(cr, uid, ids, context=context):
            csv_content = base64.decodestring(data.binary_file).split('\n')
            lines = csv.reader(csv_content, delimiter=',')
            labels = lines.next()
            day_code_start = 5
            day_code_finish = 10
            rule_code_start = 11
            
            days_code=[]
            rules_objects=[]
            
            for x in range(day_code_start, day_code_finish):
                if labels[x] != 'codigo_dias' and labels[x] != '':
                    days_code.append(labels[x])
                    
            for x in range(rule_code_start, len(labels)):
                if labels[x] != 'codigo_regla' and labels[x] != '':
                    rule_ids = rule_obj.search(cr, uid, [('code', '=', labels[x])])
                    if not rule_ids:
                        raise osv.except_osv(_('Error!'),_('No hay una regla con codigo %s !' % labels[x]) )
                    # if len(rule_ids) > 1:
                        # raise osv.except_osv(_('Error!'),_('Hay mas de una regla con codigo %s !' % labels[x]) )
                    rule = rule_obj.browse(cr, uid, rule_ids[0], context=context)
                    rules_objects.append(rule)
            
            for line in lines:
                if not line:
                    continue
                vals = {}
                contract_ids = contract_obj.search(cr, uid, [('name','=', line[0])])
                if not contract_ids:
                    raise osv.except_osv(_('Error!'),_("No se encontro el empleado '%s' o el contrato '%s'!") % (line[2],line[3],))
                else:
                    contract_data = contract_obj.browse(cr, uid, contract_ids[0], context=context)
                    
                    employee_id = contract_data.employee_id.id
                    payslip_period = period_obj.search(cr, uid, [('name','=', line[1])])
                    payslip_period = payslip_period and payslip_period[0] or False
                    if not payslip_period:
                        raise osv.except_osv(_('Error!'),_('No existe el periodo %s !' % line[1]) )
                    period_data = period_obj.browse(cr, uid, payslip_period,context=context)
                    
                    payslip_type = type_obj.search(cr, uid, [('code','=', line[2])])
                    payslip_type = payslip_type and payslip_type[0] or False
                    if not payslip_type:
                        raise osv.except_osv(_('Error!'),_('No existe un tipo de nomina de codigo %s !' % line[2]) )
                    payslip_type = type_obj.browse(cr, uid, payslip_type,context=context)
                    
                    estructura_liquidacion = contract_type_obj.get_structure_by_slip_type(cr, uid, contract_data.type_id.id, payslip_type.id, context=context)
                    if not estructura_liquidacion:
                        raise osv.except_osv(_('Error!'),_("El contrato '%s' no tiene una estructura para el tipo de nomina '%s' !" % line[0],line[2],) )
                    
                    journal_id = journal_obj.search(cr, uid, [('code','=', line[3])])
                    journal_id = journal_id and journal_id[0] or False
                    if not journal_id:
                        raise osv.except_osv(_('Error!'), _('No existe un diario de codigo %s !' % line[3]) )
                                         
                    worked_days_line_ids = []
                    index_aux = day_code_start-1
                    for code in days_code:
                        index_aux += 1
                        worked_days_line_ids.append((0, 0, {'name': code,
                                                        'code': code,
                                                        'symbol': '',
                                                        'number_of_days': line[index_aux],
                                                        'number_of_hours' : contract_data.working_hours.hours_payslip*float(line[index_aux]),
                                                        'contract_id': contract_data.id}))
                    line_ids = []
                    index_aux = rule_code_start-1
                    for rule in rules_objects:
                        index_aux += 1
                        line_ids.append((0, 0, {'name': rule.name,
                                            'code': rule.code,
                                            'category_id': rule.category_id.id,
                                            'quantity' : 1.0,
                                            'rate': 100,
                                            'amount': line[index_aux],
                                            'contract_id': contract_data.id,
                                            'employee_id': employee_id,
                                            'salary_rule_id': rule.id}))

                    vals.update({'contract_id': contract_data.id,
                                 'employee_id': employee_id,
                                 'struct_id': estructura_liquidacion.id,
                                 'journal_id': journal_id,
                                 'tipo_nomina': payslip_type.id,
                                 'name': "Importacion de Nomina "+datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                                 'payslip_period_id': period_data.id,
                                 'liquid_date': line[4],
                                 'line_ids': line_ids,
                                 'worked_days_line_ids': worked_days_line_ids,
                                 })
                    
                    repeated_ids = payroll_obj.search(cr, uid, [('payslip_period_id','=', period_data.id),('contract_id','=', contract_data.id),('tipo_nomina','=', payslip_type.id),])
                    
                    if repeated_ids:
                        raise osv.except_osv(_('Error!'),
                        _("El contrato '%s' solo puede tener una nomina de un mismo tipo '%s' para un mismo periodo '%s' !" % (contract_data.name,payslip_type.code,period_data.name)) )
                    
                    slip_id = payroll_obj.create(cr, uid, vals, context=context)
                    payroll_obj.write(cr, uid, slip_id,{'state':'done'})
                     
        return {'type': 'ir.actions.act_window_close'}

import_pay_slip()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
