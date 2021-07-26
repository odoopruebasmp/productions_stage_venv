# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
import openerp.netsvc
from dateutil.rrule import rrule, DAILY
import time
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval
from openerp.addons.edi import EDIMixin
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from .hr_payroll_concept import CATEGORIES, PARTNER_TYPE

class hr_payslip_prestamo_cuota(osv.osv):
    _name = "hr.payslip.prestamo.cuota"
    _description = "Prestamo Cuota Payslip"
    _columns = {
        'category_id': fields.many2one('hr.payroll.prestamo.category', 'Categoria', required=True,readonly=True),
        'cuota': fields.float("Cuota", digits_compute= dp.get_precision('Account'),readonly=True),
        'deuda': fields.float("Deuda", digits_compute= dp.get_precision('Account'),readonly=True),
        'payslip_id': fields.many2one('hr.payslip', 'Payslip', required=True, ondelete='cascade',readonly=True),
    }

class hr_payroll_prestamo_cuota(osv.osv, EDIMixin):
    _name = "hr.payroll.prestamo.cuota"
    _description = "Prestamo Cuota"
    _columns = {
        'payslip_id': fields.many2one('hr.payslip', 'Nomina que pago',readonly=True),
        'cuota': fields.float("Cuota", required=True, digits_compute= dp.get_precision('Account'),readonly=True),
        'prestamo_id': fields.many2one('hr.payroll.prestamo', 'Prestamo', required=True, ondelete="cascade",readonly=True),
        'date': fields.date('Fecha', help="Fecha en la que se pagara", required=True,readonly=True),
        'contract_id': fields.related('prestamo_id','contract_id',type="many2one",relation="hr.contract",string="Contrato",readonly=True,store=True),
        'company_id': fields.related('contract_id','company_id',type="many2one",relation="res.company",string="Compania",readonly=True,store=True),
        'category_id': fields.related('prestamo_id','category_id',type="many2one",relation="hr.payroll.prestamo.category",string="Categoria",readonly=True,store=True),
        'deuda': fields.related('prestamo_id','deuda',type="float",string="Deuda",readonly=True, digits_compute= dp.get_precision('Account')),
        'name': fields.related('prestamo_id','name',type="char",string="Descripción",readonly=True),
        'numero_cuotas': fields.related('prestamo_id','numero_cuotas',type="integer",string="Numero de Cuotas",readonly=True),
        'state': fields.related('prestamo_id', 'state', type="char",string="Estado", readonly=True, store=True),
    }
    
class hr_payroll_prestamo(osv.osv, EDIMixin):
    _name = "hr.payroll.prestamo"
    _description = "Prestamo Empleado"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    
    def _get_contract(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for prestamo in self.browse(cr, uid, ids, context):
            res[prestamo.id] = self.pool.get('hr.employee').get_contract(cr, uid, prestamo.employee_id, prestamo.request_date, context)
        return res
        
    def _employee_get(obj, cr, uid, context=None):
        if context is None:
            context = {}
        ids = obj.pool.get('hr.employee').search(cr, uid, [('user_id', '=', uid)], context=context)
        if ids:
            return ids[0]
        else:
            raise osv.except_osv(_('Advertencia !'),_("Su usuario no esta vinculado a ningun empleado"))
        return False
        
    def _compute_cuota(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for prestamo in self.browse(cr, uid, ids, context):
            res[prestamo.id] = prestamo.valor/prestamo.numero_cuotas
        return res
        
    def _compute_deuda(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for prestamo in self.browse(cr, uid, ids, context):
            if prestamo.cuotas_ids:
                deuda = prestamo.valor
                for cuota in prestamo.cuotas_ids:
                    if cuota.payslip_id:
                        deuda -= cuota.cuota
                res[prestamo.id] = deuda
        return res
    
    def _no_amount(self, cr, uid, ids, context=None):
        for prestamo in self.browse(cr, uid, ids, context=context):
            if prestamo.numero_cuotas == 0.00 or prestamo.valor == 0.0:
                return False
        return True
        
    def _no_lines(self, cr, uid, ids, context=None):
        for prestamo in self.browse(cr, uid, ids, context=context):
            if prestamo.state=='validated' and not prestamo.cuotas_ids:
                return False
        return True
    
    def _get_cuota_line(self, cr, uid, ids, context=None):
        ids = []
        for line in self.pool.get('hr.payroll.prestamo.cuota').browse(cr, uid, ids, context=context):
            ids.append(line.prestamo_id.id)
        
        return ids
    
    def _is_done(self, cr, uid, ids, name, args, context=None):
        result = {}
        done = False
        wf_service = openerp.netsvc.LocalService("workflow")
        cuota_pool = self.pool.get('hr.payroll.prestamo.cuota')
        for prestamo in self.browse(cr, uid, ids, context=context):
            done = True
            for cuota in prestamo.cuotas_ids:
                if not cuota.payslip_id:
                    done = False
                    break
                    
            if done:
                wf_service.trg_validate(uid, 'hr.payroll.prestamo', prestamo.id, 'done', cr)
            else:
                wf_service.trg_validate(uid, 'hr.payroll.prestamo', prestamo.id, 'cancel_done', cr)
        result[prestamo.id] = done
        return result
    
    _columns = {
        'payslip_id': fields.many2one('hr.payslip', 'Pagado en nomina', readonly=True, states={'draft': [('readonly', False)]}),
        'moneda_local': fields.related('company_id','currency_id',type="many2one",relation="res.currency",string="Moneda Local",readonly=True,store=True),
        'request_date': fields.date('Fecha de Solicitud', required=True, help="Fecha en la que se pidio el prestamo", readonly=True, states={'draft': [('readonly', False)]}),
        'date': fields.date('Fecha del Prestamo', help="Fecha en la cual el prestamo fue efectivo", readonly=True, states={'confirmed': [('readonly', False)], 'draft': [('readonly', False)]}),
        'approve_date': fields.date('Fecha de Aprobacion', help="Fecha en la que se aprobo la novedad, dejela vacia para que se llene automaticamente", readonly=True, states={'confirmed': [('readonly', False)], 'draft': [('readonly', False)]}),
        'category_id': fields.many2one('hr.payroll.prestamo.category', 'Categoria', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'employee_id': fields.many2one('hr.employee', 'Empleado', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'company_id': fields.related('contract_id','company_id',type="many2one",relation="res.company",string="Compania",readonly=True,store=True),
        'contract_id': fields.function(_get_contract, type="many2one", relation='hr.contract', string="Contrato", store=True), 
        'valor' : fields.float("Valor", digits_compute= dp.get_precision('Account'), readonly=True, states={'draft': [('readonly', False)]}),
        'numero_cuotas' : fields.integer("Numero de Cuotas Pactado", readonly=False, states={'done': [('readonly', True)]}),
        'cuota': fields.function(_compute_cuota, type="float", string="Cuota", digits_compute= dp.get_precision('Account'), store=True),
        'deuda': fields.function(_compute_deuda, type="float", string="Deuda Remanente", digits_compute= dp.get_precision('Account'), store=True),
        'description': fields.text('Descripcion', readonly=True, states={'draft': [('readonly', False)]}),
        'name': fields.char('Codigo',size=64,readonly=True),
        'cuotas_ids':fields.one2many('hr.payroll.prestamo.cuota', 'prestamo_id', 'Cuotas'), 
        'done': fields.function(_is_done, type="boolean", string="Pagado", store={
                'hr.payroll.prestamo': (lambda self, cr, uid, ids, c={}: ids, None,50),
                'hr.payroll.prestamo.cuota': (_get_cuota_line, None, 50),
            }),
        'state':fields.selection([('draft', 'Borrador'), 
                                  ('confirmed', 'Confirmada'), 
                                  ('validated', 'Validada'), 
                                  ('refused', 'Rechazada'), 
                                  ('cancelled', 'Cancelada'), 
                                  ('done', 'Pagado'), 
                                  ], 'State', select=True, readonly=True)
    }
    
    _defaults = {
        'request_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        'date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state': 'draft',
        'employee_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).employee_id and self.pool.get('res.users').browse(cr, uid, uid, c).employee_id.id or False,
    }
    
    _constraints = [
        (_no_amount, 'No se puede ingresar un prestamo sin cuotas o valor 0', ['numero_cuotas']),
        (_no_lines, 'No puede validar una sin calcular las cuotas', ['cuotas_ids']),
    ]
    
    _track = {
        'state': {
            'hr_payroll_extended.mt_prestamo_new': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'draft',
            'hr_payroll_extended.mt_prestamo_confirmada': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'confirmed',
            'hr_payroll_extended.mt_prestamo_validada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'validated',
            'hr_payroll_extended.mt_prestamo_rechazada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'refused',
            'hr_payroll_extended.mt_prestamo_cancelada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelled',
            'hr_payroll_extended.mt_prestamo_pagada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'done',
        },
    }
    
    def draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'draft'})
        return True
    
    def confirm(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'confirmed'})
        return True
        
    def validate(self, cr, uid, ids, context=None):
        cuotas_obj = self.pool.get('hr.payroll.prestamo.cuota')
        for prestamo in self.browse(cr, uid, ids, context):
            if not prestamo.approve_date:
                self.write(cr, uid, ids, {'approve_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)})
        self.write(cr, uid, ids, {'state': 'validated'})
        self.calcular_button(cr, uid, ids, context)
        return True
    
    def refuse(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'refused'})
        return True
    
    def done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'done'})
        return True
        
    def cancel(self, cr, uid, ids, context=None):
        cuotas_obj = self.pool.get('hr.payroll.prestamo.cuota')
        for prestamo in self.browse(cr, uid, ids, context):
            for cuota in prestamo.cuotas_ids:
                if not cuota.payslip_id:
                    cuotas_obj.unlink(cr, SUPERUSER_ID, cuota.id, context=context)
        self.write(cr, uid, ids , {'state':'cancelled'})
        return True
    
    def calcular_button(self, cr, uid, ids, context=None):
        cuotas_obj = self.pool.get('hr.payroll.prestamo.cuota')
        for prestamo in self.browse(cr, uid, ids, context):
            if not prestamo.date:
                raise osv.except_osv(_('Error!'),_('Tiene que llenar la fecha en la que se dio el prestamo!'))
            if prestamo.cuotas_ids:
                for cuota in prestamo.cuotas_ids:
                    cuotas_obj.unlink(cr, SUPERUSER_ID, cuota.id, context=context)
            fecha = datetime.strptime(prestamo.date[0:10], '%Y-%m-%d')
            day = fecha.day
            month = fecha.month
            year = fecha.year
            if day > 28:
                day = 28
            for x in range(1, prestamo.numero_cuotas+1):
                depreciation_date = (datetime(year, month, day) + relativedelta(months=x))
                cuota_mensual = prestamo.cuota
                if x == prestamo.numero_cuotas:
                    cuota_mensual += prestamo.valor-(prestamo.cuota*prestamo.numero_cuotas)
                cuotas_obj.create(cr, uid, {'prestamo_id': prestamo.id, 'cuota': cuota_mensual, 'date': depreciation_date}, context=context)
        return True
        
    def unlink(self, cr, uid, ids, context=None):
        for prestamo in self.browse(cr, uid, ids, context=context):
            if prestamo.state not in  ['draft','cancelled']:
                raise osv.except_osv(_('Error!'),_('No puede borrar un prestamo que no esta en borrador o cancelado!'))
        return super(hr_payroll_prestamo, self).unlink(cr, uid, ids, context)
        
    def write(self, cr, uid, ids, vals, context=None):
        
        
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
        result = super(hr_payroll_prestamo, self).write(cr, uid, ids, vals, context=context)
        
        return result
    
    def create(self, cr, uid, vals, context=None):
        #agrega follower
        if context is None:
            context = {}
        
        #agrega numero de secuencia
        vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'payroll.prestamos.number') or '/'
        
        #metodo padre
        result = super(hr_payroll_prestamo, self).create(cr, uid, vals, context=context)
        
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
    
class hr_payroll_prestamo_category(osv.osv):
    _name = "hr.payroll.prestamo.category"
    _description = "Categoria del prestamo"
    _columns = {
        'name': fields.char('Nombre', size=64, required=True, translate=True),
        'code': fields.char('Codigo', size=16, required=True),
        'analytic_account_id': fields.property(
            type='many2one',
            relation='account.analytic.account',
            string="Centro Costo",
             
            help="Sera usada para causar el credito y debito de las cuotas del prestamo"),
        'account_credit': fields.property(
            type='many2one',
            relation='account.account',
            string="Cuenta Credito",
             
            help="Sera usada para causar el credito de las cuotas del prestamo"),
        'account_debit': fields.property(
            type='many2one',
            relation='account.account',
            string="Cuenta Debito",
             
            help="Sera usada para causar el debito de las cuotas del prestamo"),
        
        'descripcion': fields.text('Descripcion'),
        'concept_category': fields.selection(CATEGORIES, 'Categoria de concepto', required=True),
        'partner_type': fields.selection(PARTNER_TYPE, 'Tipo de tercero'),
        'partner_other': fields.many2one('res.partner', 'Otro Tercero'),
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
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codgigo tiene que ser unico!'),
    ]
