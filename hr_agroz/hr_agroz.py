# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
# from openerp.tools.translate import _
from openerp import addons
from openerp import SUPERUSER_ID
import itertools
from dateutil.relativedelta import relativedelta
from lxml import etree
from openerp import models, fields, api, _
from openerp.osv import osv, fields as fields2
from openerp.exceptions import except_orm, Warning, RedirectWarning
import openerp.addons.decimal_precision as dp
import math



class res_partner(osv.Model):    
    _inherit = "res.partner"
    _columns = {
        'lugar_exp':fields2.many2one('res.city', string='Lugar de Expedicion'),        
    }
   
class hr_job(osv.Model):    
    _inherit = "hr.job"
    _columns = {
        'criticidad':fields2.selection([('critico', 'Critico'), ('critico_medio', 'Critico Medio'), ('no_critico', 'No Critico')], "Criticidad"),
    }
    
class hr_contract(osv.Model):
    _inherit = "hr.contract"
    
    def _cantidad(self, cr, uid, ids, name, args, context=None):
        res = {}
        today = datetime.now()  
        today = today.strftime('%Y-%m-%d')
        for contract in self.browse(cr, uid, ids, context=context):            
            if contract.date_end:
                date_end= contract.date_end
                date_end = datetime.strptime(date_end, DEFAULT_SERVER_DATE_FORMAT).date()
                today = datetime.strptime(today, DEFAULT_SERVER_DATE_FORMAT).date()
                cant= (date_end - today).days
                res[contract.id] = cant
            else:
                res[contract.id] = 0                
            
        return res
    
    _columns = {
        'a_vercer':fields2.function(_cantidad, string='Dias para vencer', type='integer', store=True, readonly=True),
        'termino':fields2.char('Termino'),
        'dotacion_ids': fields2.one2many('hr.dotacion', 'dotacion_id', 'Dotaciones'),
    }
    
    
class hr_employee(osv.Model):
    _inherit = "hr.employee"
    
    _columns = {
        'lugar_exp': fields2.related('partner_id', 'lugar_exp', type="many2one", relation="res.city", string="Lugar de expedicion", readonly=True),
        'write_date': fields2.datetime('Fecha', readonly=True),
        'adj_ced': fields2.binary("Cedula"),
        'adj_hv': fields2.binary("H.V."),
        'adj_lm': fields2.binary("L. Militar"),
        'adj_db': fields2.binary("D. Bachiller"),
        'adj_pj': fields2.binary("P. Judicial"),
        'adj_ps': fields2.binary("P. Psicotecnicas"),
        'adj_ee': fields2.binary("E. Especifico"),        
        'adj_adp': fields2.binary("A. Datos personales"),
        'adj_fh': fields2.binary("F. Huella"),
        'adj_ri': fields2.binary("R. Induccion"),
        'date_vis_ini': fields2.datetime("A. Datos personales"),
        'date_vis_end': fields2.datetime("F. Huella"),
        'visita': fields2.binary("V. Domiciliaria"),
        'adj_obser': fields2.text("Observaciones"),
        'codigo': fields2.char("Codigo Interno", required=True, size=15),
        'capacitacion_id': fields2.one2many('hr.capacitaciones', 'capacitacion_id', 'Capacitaciones'),
        'referencias_ids': fields2.one2many('hr.referencias', 'referencias_id', 'Capacitaciones'),
        'familiar_ids': fields2.one2many('hr.familiar', 'familiar_id', 'Informacion Familiar'),
        'type_employee': fields2.selection([('interno', 'Interno'),('externo', 'Externo')], "Tipo de Empleado", required=True),        
        'temp_date_ini': fields2.datetime("Fecha de Ingreso"),
        'temp_date_start': fields2.datetime("Fecha Primer Ingreso"),
        'temp_salario': fields2.float("Asignacion salarial"),
        'temp_arl': fields2.many2one('res.partner', 'ARL'),
        'temp_eps': fields2.many2one('res.partner', 'EPS'),
        'temp_ccf': fields2.many2one('res.partner', 'CCF'),
        'temp_empresa': fields2.many2one('res.partner', 'Temporal'),        
    }
    
    _sql_constraints = [('codigo_uniq', 'unique(codigo)', 'El código del empleado ya se encuentra asignado'),]
    

class hr_capacitaciones(osv.Model):
    _name = "hr.capacitaciones"
    _columns = {
        'type': fields2.selection([('bachiller', 'Bachiller'), ('profesional', 'Profesional'), ('posgrado', 'Posgrado'), ('curso', 'Curso'), ('diplomado', 'Diplomado'), ('tecnologia', 'Tecnologia'), ('tecnico', 'Tecnico')], "Tipo de programa", required=True),
        'name': fields2.char('Nombre', size=40, required=True),
        'partner_id': fields2.many2one('res.partner', 'Institucion'),
        'size': fields2.integer('Duracion', help="Horas", required=True),
        'date_start': fields2.datetime("Fecha de inicio", required=True),
        'date_stop': fields2.datetime("Fecha de Finalizacion"),
        'adj_capacitacion': fields2.binary('Soporte Fisico'),
        'capacitacion_id': fields2.many2one('hr.employee', 'Empleado'),
        }
    
    

class hr_referencias(osv.Model):
    _name = "hr.referencias"
    _columns = {
        'type': fields2.selection([('laboral', 'Laboral'), ('personal', 'Personal')], "Tipo de referencia", required=True),
        'name': fields2.char('Nombre', size=40, required=True),
        'tele': fields2.char('Telefono', size=20, required=True),
        'rela': fields2.char('Relacion', size=40, required=True),
        'referencias_id': fields2.many2one('hr.employee', 'Empleado'),
        }

class hr_familiar(osv.Model):
    _name = "hr.familiar"
    _columns = {
        'name': fields2.char('Nombre', size=40, required=True),
        'type_id': fields2.many2one('res.document.type', 'Tipo de Documento', required=True),
        'document': fields2.char('Documento', required=True),
        'parent': fields2.char('Parentesco', required=True),
        'date': fields2.date('Fecha de Nacimineto', required=True),
        'familiar_id': fields2.many2one('hr.employee', 'Empleado'),
        }

class hr_dotacion(osv.Model):
    _name = "hr.dotacion"
    _columns = {
        'name': fields2.char('Nombre', size=40, required=True),
        'product_id': fields2.many2one('product.product', 'Producto', required=True),
        'document': fields2.char('Cantidad', required=True),
        'prodlot_id': fields2.many2one('stock.production.lot', 'Serial'),
        'dotacion_id': fields2.many2one('hr.contract', 'Contrato'),
        }
#
