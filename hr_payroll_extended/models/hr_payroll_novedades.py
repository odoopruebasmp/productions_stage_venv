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
from .hr_payroll_concept import CATEGORIES, PARTNER_TYPE
from openerp import models, api
from openerp import fields as fields2
from openerp.addons.avancys_orm import avancys_orm as orm



class hr_payslip_novedades(osv.osv):
    _name = "hr.payslip.novedades"
    _description = "Novedades Payslip"
    _columns = {
        'category_id': fields.many2one('hr.payroll.novedades.category', 'Categoria', required=True, index=True),
        'cantidad': fields.float("Cantidad",readonly=True),
        'total': fields.float("Total",readonly=True),
        'payslip_id': fields.many2one('hr.payslip', 'Payslip', required=True, ondelete='cascade', index=True),
    }

class hr_payroll_novedades(osv.osv, EDIMixin):
    _name = "hr.payroll.novedades"
    _description = "Novedades"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    
    def _get_contract(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for novedad in self.browse(cr, uid, ids, context):
            res[novedad.id] = self.pool.get('hr.employee').get_contract(cr, uid, novedad.employee_id, novedad.date, context)
        return res
    
    def _compute_price(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for novedad in self.browse(cr, uid, ids, context):
            res[novedad.id] = novedad.valor*novedad.cantidad
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
    
    def _no_amount(self, cr, uid, ids, context=None):
        for novedad in self.browse(cr, uid, ids, context=context):
            if novedad.cantidad <= 0 or novedad.valor == 0.0:
                return False
        return True
    
    _columns = {
        'payslip_id': fields.many2one('hr.payslip', 'Pagado en nomina', readonly=True),
        'payslip_neto_id': fields.many2one('hr.payslip', 'Creado en la nomina', readonly=True),
        'moneda_local': fields.related('company_id','currency_id',type="many2one",relation="res.currency",string="Moneda Local",readonly=True,store=True),
        'date': fields.date('Fecha', required=True, help="Fecha en la que aplica la novedad para el empleado", readonly=True, states={'draft': [('readonly', False)]}),
        'approve_date': fields.date('Fecha de aprobacion', readonly=True, help="Fecha en la que se aprobo la novedad, dejela vacia para que se llene automaticamente", states={'confirmed': [('readonly', False)], 'draft': [('readonly', False)]}),
        'category_id': fields.many2one('hr.payroll.novedades.category', 'Categoria', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'employee_id': fields.many2one('hr.employee', 'Empleado', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'company_id': fields.related('contract_id','company_id',type="many2one",relation="res.company",string="Compañia",readonly=True,store=True),
        'contract_id': fields.function(_get_contract, type="many2one", relation='hr.contract', string="Contrato", store=True),
        'valor' : fields.float("Valor", readonly=True, states={'draft': [('readonly', False)]}),
        'cantidad' : fields.float("Cantidad", readonly=True, states={'draft': [('readonly', False)]}),
        'total': fields.function(_compute_price, type="float", string="Total", digits_compute= dp.get_precision('Product Price'), store=True),
        'description': fields.text('Descripcion', readonly=True, states={'draft': [('readonly', False)]}),
        'name': fields.char('Codigo',size=64,readonly=True),
        'neto': fields.boolean('Regla del Neto a Pagar'),
        'state':fields.selection([('draft', 'Borrador'), 
                                  ('confirmed', 'Confirmada'), 
                                  ('validated', 'Validada'), 
                                  ('refused', 'Rechazada'), 
                                  ('cancelled', 'Cancelada'), 
                                  ('done', 'Pagada'), 
                                  ], 'State', select=True, readonly=True)
    }
    
    _defaults = {
        'date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state': 'draft',
        'employee_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).employee_id and self.pool.get('res.users').browse(cr, uid, uid, c).employee_id.id or False,
    }
    
    _track = {
        'state': {
            'hr_payroll_extended.mt_novedad_new': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'draft',
            'hr_payroll_extended.mt_novedad_confirmada': lambda self, cr, uid, obj, ctx=None:  obj['state'] == 'confirmed',
            'hr_payroll_extended.mt_novedad_validada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'validated',
            'hr_payroll_extended.mt_novedad_rechazada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'refused',
            'hr_payroll_extended.mt_novedad_cancelada': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancelled',
        },
    }
    
    _constraints = [
        (_no_amount, 'No se puede ingresar un valor 0 o una cantidad negativa o igual a 0', ['valor']),
    ]
    
    def draft(self, cr, uid, ids, context=None):
        cr.execute("UPDATE hr_payroll_novedades SET state = 'draft' WHERE ID = {id}".format(id=ids[0]))
        return True
    
    def confirm(self, cr, uid, ids, context=None):
        cr.execute("UPDATE hr_payroll_novedades SET state = 'confirmed' WHERE ID = {id}".format(id=ids[0]))
        return True
        
    def validate(self, cr, uid, ids, context=None):
        for horanovedad in self.browse(cr, uid, ids, context):
            if not horanovedad.approve_date:
                cr.execute("UPDATE hr_payroll_novedades SET approve_date = '{date}' WHERE ID = {id}".format(
                    id=ids[0], date=datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)))
            cr.execute("UPDATE hr_payroll_novedades SET state = 'validated' WHERE ID = {id}".format(id=ids[0]))
        return True
    
    def refuse(self, cr, uid, ids, context=None):
        cr.execute("UPDATE hr_payroll_novedades SET state = 'refused' WHERE ID = {id}".format(id=ids[0]))
        return True
    
    def done(self, cr, uid, ids, context=None):
        cr.execute("UPDATE hr_payroll_novedades SET state = 'done' WHERE ID = {id}".format(id=ids[0]))
        return True
        
    def cancel(self, cr, uid, ids, context=None):
        cr.execute("UPDATE hr_payroll_novedades SET state = 'cancelled' WHERE ID = {id}".format(id=ids[0]))
        return True
        
    def unlink(self, cr, uid, ids, context=None):
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.state not in  ['draft','cancelled']:
                raise osv.except_osv(_('Error!'),_('No puede borrar una novedad que no esta en borrador o cancelada!'))
        return super(hr_payroll_novedades, self).unlink(cr, uid, ids, context)
        
    # def write(self, cr, uid, ids, vals, context=None):
    #     #agrega los followers por defecto
    #     if 'employee_id' in vals:
    #         for req in self.browse(cr, uid, ids, context=context):
    #             empleado = self.pool.get('hr.employee').browse(cr, uid, vals.get('employee_id'), context=context)
    #             if empleado.partner_id not in req.message_follower_ids:
    #                 message_follower_ids = []
    #                 message_follower_ids += req.message_follower_ids
    #                 message_follower_ids.append(empleado.partner_id)
    #                 vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
    #                 if empleado.parent_id.partner_id not in req.message_follower_ids:
    #                     message_follower_ids += req.message_follower_ids
    #                     message_follower_ids.append(empleado.partner_id)
    #                     vals.update({'message_follower_ids': [(6, 0,[x.id for x in message_follower_ids])]})
    #
    #      #llama al metodo padre
    #     result = super(hr_payroll_novedades, self).write(cr, uid, ids, vals, context=context)
    #    return result
    
    def create(self, cr, uid, vals, context=None):
        #agrega follower
        if context is None:
            context = {}
        
        #agrega numero de secuencia
        vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'payroll.novedades.number') or '/'
        
        #metodo padre
        result = super(hr_payroll_novedades, self).create(cr, uid, vals, context=context)
        
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


class hr_payroll_novedades_category(osv.osv):
    _name = "hr.payroll.novedades.category"
    _description = "Categoria de la novedad"
    _columns = {
        'name': fields.char('Nombre', size=64, required=True, translate=True),
        'code': fields.char('Codigo', size=16, required=True),
        'descripcion': fields.text('Descripcion'),
        'rules_account_ids': fields.one2many('hr.concept.structure.account', 'novedad_category_id', 'Estructura de Cuentas'),
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
        'ex_rent': fields.boolean('Ingreso exento de retencion'),
        'ded_rent': fields.boolean('Aporte voluntario'),
        'afc': fields.boolean('AFC'),
        'hour_novelty': fields.boolean('Novedad por horas'),
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codgigo tiene que ser unico!'),
    ]


class HourNovelty(models.Model):
    _name = 'hour.novelty'

    employee_id = fields2.Many2one('hr.employee', 'Empleado')
    contract_id = fields2.Many2one('hr.contract', 'Contrato', compute="get_contract")
    date = fields2.Date('Fecha', default=datetime.now())
    hours = fields2.Float('Horas a descontar')
    wage = fields2.Float('Salario', compute="get_contract")
    days_month = fields2.Integer('Intensidad horaria mensual', default=240)
    amount = fields2.Float('Total a deducir', compute="get_deduction", store=True)
    state = fields2.Selection([('draft', 'Borrador'), ('validated', 'Validado')], string="Estado", default="draft")
    novelty_category = fields2.Many2one('hr.payroll.novedades.category', 'Tipo de novedad',
                                        domain=[('hour_novelty', '=', True), ('concept_category', '=', 'deductions')])
    novelty_id = fields2.Many2one('hr.payroll.novedades', 'Novedad')

    @api.one
    @api.onchange('employee_id', 'date')
    def get_contract(self):
        if self.employee_id and self.date:
            self.contract_id = self.env['hr.employee'].get_contract(self.employee_id, self.date)
            self.wage = self.contract_id.wage
        else:
            self.contract_id = False
            self.wage = 0

    @api.one
    @api.depends('wage', 'days_month', 'hours')
    def get_deduction(self):
        for rec in self:
            rec.amount = rec.wage / rec.days_month * rec.hours

    @api.multi
    def cancel(self):
        if self.novelty_id.state == 'done':
            raise Warning("No es posible eliminar una novedad en estado pagada")
        delete_nov = ("DELETE FROM hr_payroll_novedades where id = {nov}".format(nov=self.novelty_id.id))
        self._cr.execute(delete_nov)
        self.state = 'draft'

    @api.multi
    def create_novelty(self):
        name = self.env['ir.sequence'].get('payroll.novedades.number')
        novedad_data = {
            'name': name,
            'employee_id': self.employee_id.id,
            'date': self.date,
            'valor': self.wage / self.days_month,
            'cantidad': self.hours,
            'total': self.amount,
            'moneda_local': self.env.user.company_id.currency_id.id,
            'category_id': self.novelty_category.id,
            'contract_id': self.contract_id.id,
            'approve_date': self.date,
            'state': 'validated',
        }
        nov = orm.direct_create(self._cr, self._uid, 'hr_payroll_novedades', [novedad_data], company=True)[0][0]
        self.novelty_id = self.env['hr.payroll.novedades'].browse(nov)
        self.state = 'validated'

    # noinspection PyTypeChecker
    @api.multi
    def massive_novelty(self):
        for hn in self:
            hn.create_novelty()
        return
