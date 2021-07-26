# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
import openerp.netsvc
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil import relativedelta, parser
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval
from openerp.addons.edi import EDIMixin
from .hr_payroll_concept import CATEGORIES, PARTNER_TYPE, FORTNIGHT_AP


class hr_payslip_obligacion_tributaria_line(osv.osv):
    _name = "hr.payslip.obligacion.tributaria.line"
    _description = "Obligacion Tributaria Payslip"
    _columns = {
        'obligacion_id': fields.many2one('hr.payroll.obligacion.tributaria', 'Concepto Fijo', required=True, ondelete='cascade', index=True),
        'payslip_id': fields.many2one('hr.payslip', 'Nomina', required=True, ondelete='cascade', index=True),
        'valor': fields.float("Valor", required=True,readonly=True),
        'payslip_period_id': fields.related('payslip_id','payslip_period_id',type="many2one",relation="payslip.period",string="Periodo",readonly=True),
        'category_id': fields.related('obligacion_id','category_id',type="many2one",relation="hr.payroll.obligacion.tributaria.category",string="Categoria",readonly=True),
        'manual': fields.boolean('Manual',),
    }
    
    _defaults = {
        'manual': True,
    }

class hr_payroll_obligacion_tributaria(osv.osv, EDIMixin):
    _name = "hr.payroll.obligacion.tributaria"
    _description = "Concepto Fijo"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    
    def _get_contract(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for obligacion in self.browse(cr, uid, ids, context):
            if obligacion.date_to:
                res[obligacion.id] = self.pool.get('hr.employee').get_contract(cr, uid, obligacion.employee_id,
                                                                               obligacion.date_to, context)
            else:
                today = datetime.now()
                res[obligacion.id] = self.pool.get('hr.employee').get_contract(cr, uid, obligacion.employee_id,
                                                                               today, context)
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

    def _get_name(self, cr, uid, ids, name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.category_id.name or ''
        return res
    
    _columns = {
        'name': fields.function(_get_name, type='char', string='Concepto fijo', store=True),
        'company_id': fields.related('contract_id','company_id',type="many2one",relation="res.company",string="Compañia",readonly=True,store=True),
        'moneda_local': fields.related('company_id','currency_id',type="many2one",relation="res.currency",string="Moneda Local",readonly=True,store=True),
        'date_from': fields.date('Fecha Inicio', required=True, help="Fecha en la que empieza a aplicar para el contrato",readonly=True ,states={'draft': [('readonly', False)]}),
        'date_to': fields.date('Fecha Final', help="Fecha en la que termina de aplicar para el contrato",readonly=True ,states={'draft': [('readonly', False)]}),
        'approve_date': fields.date('Fecha de aprobacion', help="Fecha en la que se aprobo, dejela vacia para que se llene automaticamente", readonly=True, states={'confirmed': [('readonly', False)], 'draft': [('readonly', False)]}),
        'category_id': fields.many2one('hr.payroll.obligacion.tributaria.category', 'Categoria', required=True, readonly=True ,states={'draft': [('readonly', False)]}),
        'employee_id': fields.many2one('hr.employee', 'Empleado', required=True, readonly=True ,states={'draft': [('readonly', False)]}),
        'line_ids':fields.one2many('hr.payslip.obligacion.tributaria.line', 'obligacion_id', 'Aplicadas en', readonly=True),
        'contract_id': fields.function(_get_contract, type="many2one", relation='hr.contract', string="Contrato", store=True),
        'valor' : fields.float("Valor", readonly=True ,states={'draft': [('readonly', False)]}),
        'description': fields.text('Descripcion', readonly=True, states={'draft': [('readonly', False)]}),
        'bm_type': fields.selection(FORTNIGHT_AP, 'Aplicable para'),
        'state':fields.selection([('draft', 'Borrador'),
                                  ('confirmed', 'Confirmada'),
                                  ('validated', 'Valida'),
                                  ('refused', 'Rechazada'),
                                  ('cancelled', 'Cancelada'),
                                  ('done', 'Pagada'),
                                  ], 'State', select=True, readonly=True)
    }
    
    _defaults = {
        'state': 'draft',
        'employee_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).employee_id and self.pool.get('res.users').browse(cr, uid, uid, c).employee_id.id or False,
    }
    
    _track = {
        'state': {
            'hr_payroll_extended.mt_obligacion_new': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'draft',
            'hr_payroll_extended.mt_obligacion_confirmada': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'confirmed',
            'hr_payroll_extended.mt_obligacion_validada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'validated',
            'hr_payroll_extended.mt_obligacion_rechazada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'refused',
            'hr_payroll_extended.mt_obligacion_cancelada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelled',
        },
    }

    def draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'draft'})
        return True
    
    def confirm(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'confirmed'})
        return True
        
    def validate(self, cr, uid, ids, context=None):
        for obligacion in self.browse(cr, uid, ids, context):
            if not obligacion.approve_date:
                self.write(cr, uid, ids, {'approve_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)})
        self.write(cr, uid, ids, {'state': 'validated'})
        return True
    
    def refuse(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'refused'})
        return True
    
    def done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'done'})
        return True
        
    def cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids , {'state':'cancelled'})
        return True
        
    def unlink(self, cr, uid, ids, context=None):
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.state not in  ['draft','cancelled']:
                raise osv.except_osv(_('Advertencia!'),_('No puede borrar una obligacion tributaria que no esta en borrador o cancelada!'))
        return super(hr_payroll_obligacion_tributaria, self).unlink(cr, uid, ids, context)
        
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
        result = super(hr_payroll_obligacion_tributaria, self).write(cr, uid, ids, vals, context=context)
        
        return result
    
    def create(self, cr, uid, vals, context=None):
        #agrega follower
        if context is None:
            context = {}
        
        #metodo padre
        result = super(hr_payroll_obligacion_tributaria, self).create(cr, uid, vals, context=context)
        
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
        
        vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'payroll.obligaciones.number') or '/'
        
        
                
        return result 

class hr_payroll_obligacion_tributaria_category(osv.osv):
    _name = "hr.payroll.obligacion.tributaria.category"
    _description = "Categoria de la obligacion tributaria"
    _columns = {
        'rules_account_ids':fields.one2many('hr.concept.structure.account', 'obligacion_category_id', 'Estructura de Cuentas'),
        'name': fields.char('Nombre', size=64, required=True, translate=True),
        'code': fields.char('Codigo', size=16, required=True),
        'descripcion': fields.text('Descripcion'),
        'worked_days_depends': fields.boolean('Depende de dias trabajados'),
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
        'ex_rent': fields.boolean('Exento de retencion'),
        'ded_rent': fields.boolean('Aporte voluntario'),
        'afc': fields.boolean('AFC'),
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codgigo tiene que ser unico!'),
    ]