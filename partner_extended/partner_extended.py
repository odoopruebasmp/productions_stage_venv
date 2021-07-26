# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp import models, api
from openerp import fields as fields2
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
import openerp.netsvc
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil import relativedelta, parser
import openerp.tools
import openerp.addons.decimal_precision as dp
from openerp.addons.base.res.res_partner import res_partner as res_partner_padre
from openerp.tools.safe_eval import safe_eval as eval
import re

POSTAL_ADDRESS_FIELDS2 = ('street', 'street2', 'zip', 'city', 'state_id', 'country_id', 'city_id')
ADDRESS_FIELDS2 = POSTAL_ADDRESS_FIELDS2 + ('email', 'phone', 'fax', 'mobile', 'website', 'lang')

class res_partner_api(models.Model):
    _inherit = "res.partner"
    
    @api.one
    @api.depends('birth_date')
    def _get_age_number(self):
        if self.birth_date:
            today = date.today()
            born = datetime.strptime(self.birth_date, DEFAULT_SERVER_DATE_FORMAT).date()
            self.age_number = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        else:
            self.age_number = 0
    
    @api.one
    @api.depends('parent_id')
    def _compute_entidad_comercial(self):
        if self.parent_id:
            self.entidad_comercial = False
        else:
            self.entidad_comercial = True
    
    referencias_ids = fields2.One2many('res.partner.parentesco.partner', 'partner1_id', string='Referencias')
    birth_date = fields2.Date(string='Fecha Nacimiento')
    age_number = fields2.Integer(string='Edad', compute='_get_age_number', readonly=True, store=True)
    city_id = fields2.Many2one('res.city','Ciudad', domain="[('provincia_id','=',state_id)]")
    state_id = fields2.Many2one("res.country.state", string='Fed. State', domain="[('country_id','=',country_id)]")
    partner_sexo = fields2.Many2one('partner.sexo', string='Genero')
    entidad_comercial = fields2.Boolean(compute='_compute_entidad_comercial')
    ocupacion_id = fields2.Many2one('res.partner.ocupacion',string='Ocupacion')
    estado_civil_id = fields2.Many2one('res.partner.estado_civil',string='Estado Civil')
    numero_empleados = fields2.Integer(string='Numero Empleados')
    type = fields2.Selection([('default', 'Empresa'),('invoice', 'Direccion Factura'),('delivery', 'Direccion Entrega'),('contact', 'Persona/Contacto'),('sucursal', 'Sucursal'),('other', 'Other')], string='Tipo', default='contact')
    
    @api.multi
    def onchange_type(self, is_company):
        res = super(res_partner_api, self).onchange_type(is_company)
        if is_company:
            res['value']['type'] = 'default'
        else:
            res['value']['type'] = 'contact'
        return res
    
    
class res_partner_ocupacion(models.Model):
    _name = "res.partner.ocupacion"
    _description = "Estado civil"
    
    name = fields2.Char(string='Nombre', required=True)
    description = fields2.Char(string='Descripcion')
    
class res_partner_estado_civil(models.Model):
    _name = "res.partner.estado_civil"
    _description = "Estado civil"
    
    name = fields2.Char(string='Nombre', required=True)
    description = fields2.Char(string='Descripcion')
    
class res_partner_parentesco_partner(models.Model):
    _name = "res.partner.parentesco.partner"
    _description = "Parentesco"
    
    #partner2 es el parentesco del partner1
    #Ejemplo: partner2 es el padre del partner1
    partner1_id = fields2.Many2one('res.partner', string='Tercero', required=True)
    partner2_id = fields2.Many2one('res.partner', string='Tercero', required=True)
    parentesco_id = fields2.Many2one('res.partner.parentesco', string='Parentesco', required=True)
    inverso_partner_id = fields2.Many2one('res.partner.parentesco.partner', string='Parentesco Inverso', help="Al crear una relacion de parentesco para un tercero, se creara automaticamente la inversa el otro Ejemplo: El inverso de Hijo es Padre")
    
    @api.model
    def create(self, vals):
        partner1 = super(res_partner_parentesco_partner, self).create(vals)
        if partner1.parentesco_id.inverso_id and not partner1.inverso_partner_id:
            partner2 = super(res_partner_parentesco_partner, self).create({'partner1_id':partner1.partner2_id.id,'partner2_id':partner1.partner1_id.id,'parentesco_id':partner1.parentesco_id.inverso_id.id,'inverso_partner_id':partner1.id})
            partner1.inverso_partner_id = partner2.id
        return partner1
    
class res_partner_parentesco(models.Model):
    _name = "res.partner.parentesco"
    _description = "Parentesco"
    
    name = fields2.Char(string='Nombre', required=True)
    description = fields2.Char(string='Descripcion')
    inverso_id = fields2.Many2one('res.partner.parentesco', string='Parentesco Inverso', help="Ejemplo: El inverso de Hijo es Padre")
    
class res_city(osv.osv):
    _name = "res.city"

    _columns = {
        'name' : fields.char('Nombre', size=128, required=True),
        'code' : fields.char('Codigo', size=10, required=True),
        'provincia_id' : fields.many2one('res.country.state', 'Provincia', required=True),
    }

class res_country(models.Model):
    _inherit = "res.country"

    code = fields2.Char(string='Codigo', required=True)
    
    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=100):
        ids = self.search(cr, uid, [('name', operator, name)], context=context)
        if ids:
            locations = self.name_get(cr, uid, ids, context=context)
            return sorted(locations, key=lambda (id, name): ids.index(id))


class res_country_state(osv.osv):
    _inherit = "res.country.state"

    _columns = {
        'code' : fields.char('Codigo', size=10, required=True),
    }

class partner_sexo(osv.osv):
    _name = "partner.sexo"
    _description = "Sexo"
    
    _columns = {
        'name' : fields.char('Sexo', size=10),
    }
partner_sexo()

class res_users(osv.osv):
    _inherit = "res.users"
    
    #funciones para crear un one2one entre user y partner
    def create(self, cr, uid, vals, context=None):
        res = super(res_users, self).create(cr, uid, vals, context=context)
        partner_id = vals.get('partner_id')
        if partner_id:
            partner_obj = self.pool.get('res.partner')
            partner_obj.write(cr, uid, [partner_id], {'system_user_id': res}, context=context)  
        return res
    def write(self, cr, uid, ids, vals, context=None):
        partner_id = vals.get('partner_id')
        if partner_id:
            partner_obj = self.pool.get('res.partner')
            partner_obj.write(cr, uid, [partner_id], {'system_user_id': ids[0]}, context=context)
        return super(res_users, self).write(cr, uid, ids, vals, context=context)
    

class res_document_type(osv.osv):
    _name = "res.document.type"
    
    _columns = {
        'name' : fields.char('Nombre', size=128, required=True),
        'code' : fields.char('Codigo', size=2, required=True),
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codigo tiene que ser unico!'),
    ]
    
class res_partner(osv.osv):
    _inherit = "res.partner"
    
    _columns = {
        'ref_type': fields.many2one('res.document.type','Tipo de Documento'),
        'system_user_id': fields.many2one('res.users','Usuario OpenERP', readonly=True),
        'primer_apellido' : fields.char('Primer Apellido', size=128),
        'segundo_apellido' : fields.char('Segundo Apellido', size=128),
        'primer_nombre' : fields.char('Primer Nombre', size=128),
        'otros_nombres' : fields.char('Otros Nombres', size=128),
        'ref': fields.char('Reference', size=64, select=1),
        'eslocal' : fields.boolean('Local'),
    }
    
    _sql_constraints = [
        ('ref_uniq', 'unique(ref)', 'El documento no puede ser repetido'),
    ]
    
    def onchange_atrb(self, cr , uid, ids, primer_nombre, otros_nombres, primer_apellido, segundo_apellido, context = None):
        return {'value': {'name' : (primer_nombre and primer_nombre+" " or '') + (otros_nombres and otros_nombres+" " or '') + (primer_apellido and primer_apellido or '') + (segundo_apellido and " "+segundo_apellido+" " or '') }}
    
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if type(ids) == int:
            ids = [ids]
        if not len(ids):
            return []
        def _name_get(d):
            name = d.get('name','')
            code = d.get('ref',False)
            company = d.get('company', False)
            if code:
                name = '[%s] %s' % (code,name)
            if company:
                name = '%s (%s)' % (name, company)
            return (d['id'], name)

        result = []
        for partner in self.browse(cr, user, ids, context=context):
            #workaround INC-0000005020 para LP_CO
            try:
                mydict = {
                          'id': partner.id,
                          'name': partner.name,
                          'ref': partner.ref,
                          'company': partner.parent_id.name
                          }
            except:
                mydict = {'id': partner.id}
            result.append(_name_get(mydict))
        return result
    
    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            ids = self.search(cr, user, [('ref','=',name)]+ args, limit=limit, context=context)
            if not ids:
                ids = set()
                ids.update(self.search(cr, user, args + [('ref',operator,name)], limit=limit, context=context))
                if len(ids) < limit:
                    ids.update(self.search(cr, user, args + [('name',operator,name)], limit=(limit-len(ids)), context=context))
                ids = list(ids)
            if not ids:
                ptrn = re.compile('(\[(.*?)\])')
                res = ptrn.search(name)
                if res:
                    ids = self.search(cr, user, [('ref','=', res.group(2))] + args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result
    
    def onchange_country(self, cr, uid, ids, country_id, context = None):
        res = {'value' :{'eslocal': False}}
        period_obj = self.pool.get("payslip.period")
        user_obj = self.pool.get("res.users")#FR123
        usuario = user_obj.browse(cr, uid, [uid], context)[0]
        print "1111111111"
        if country_id and usuario.company_id.country_id.id == country_id:
            res.get('value').update({'eslocal': True})
        print res
        return res
    #solo se cambia el POSTAL_ADDRESS_FIELDS2
    def update_address(self, cr, uid, ids, vals, context=None):
        addr_vals = dict((key, vals[key]) for key in POSTAL_ADDRESS_FIELDS2 if key in vals)
        if addr_vals:
            return super(res_partner_padre, self).write(cr, uid, ids, addr_vals, context)
    
    #solo se cambia el ADDRESS_FIELDS2
    def onchange_address(self, cr, uid, ids, use_parent_address, parent_id, context=None):
        def value_or_id(val):
            """ return val or val.id if val is a browse record """
            return val if isinstance(val, (bool, int, long, float, basestring)) else val.id

        if use_parent_address and parent_id:
            parent = self.browse(cr, uid, parent_id, context=context)
            return {'value': dict((key, value_or_id(parent[key])) for key in ADDRESS_FIELDS2)}
        return {}
    
    #solo se cambia el ADDRESS_FIELDS2
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        # Update parent and siblings records
        if vals.get('parent_id'):
            if 'use_parent_address' in vals:
                use_parent_address = vals['use_parent_address']
            else:
                use_parent_address = self.default_get(cr, uid, ['use_parent_address'], context=context)['use_parent_address']

            if use_parent_address:
                domain_siblings = [('parent_id', '=', vals['parent_id']), ('use_parent_address', '=', True)]
                update_ids = [vals['parent_id']] + self.search(cr, uid, domain_siblings, context=context)
                self.update_address(cr, uid, update_ids, vals, context)

                # add missing address keys
                onchange_values = self.onchange_address(cr, uid, [], use_parent_address,
                                                        vals['parent_id'], context=context).get('value') or {}
                vals.update(dict((key, value)
                            for key, value in onchange_values.iteritems()
                            if key in ADDRESS_FIELDS2 and key not in vals))

        return super(res_partner, self).create(cr, uid, vals, context=context)
#