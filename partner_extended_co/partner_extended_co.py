# -*- coding: utf-8 -*-
from openerp.osv import osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
from openerp import models, api
from openerp import fields
import openerp.netsvc
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil import relativedelta, parser
import openerp.tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.addons.base.res.res_partner import res_partner as res_partner_padre
from openerp.tools.safe_eval import safe_eval as eval

class res_document_type(models.Model):
    _inherit = "res.document.type"
    
    code_dian=fields.Char('Codigo DIAN', size=2)
    
    _sql_constraints = [
        ('code_dian_uniq', 'unique(code_dian)', 'El Codigo DIAN tiene que ser unico!'),
    ]

class res_partner(models.Model):
    _inherit = "res.partner"
    
    @api.one
    @api.depends('is_company')
    def _get_type(self):
        if self.is_company:
            self.tipo_tercero = 'Persona Juridica'
        else:
            self.tipo_tercero = 'Persona Natural'
    
    @api.one
    @api.depends('ref')
    def _compute_dev_ref(self):
        iPrimos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        partner = self
        iChequeo = iResiduo = DigitoNIT = 0
        sTMP = sTmp1 = sTMP2  = ''
        if partner.ref:
            try:
                dev_ref = partner.ref.strip()
                for i in range(0, len(dev_ref)):
                    sTMP = dev_ref[len(dev_ref)-(i +1)]
                    iChequeo = iChequeo + (int(sTMP) * iPrimos[i])
                iResiduo = iChequeo % 11
                if iResiduo <= 1:
                    if iResiduo == 0:
                        DigitoNIT = 0
                    if iResiduo == 1:
                        DigitoNIT = 1
                else:
                    DigitoNIT = 11 - iResiduo
            except:
                pass
        self.dev_ref = str(DigitoNIT)
    
    tipo_tercero=fields.Char(string='Tipo Tercero', compute='_get_type', store=True)
    formato=fields.Boolean('Formato de Vinculacion')
    certificadobancario=fields.Boolean('Certificado Bancario')
    licencias=fields.Boolean('Licencias Vigencia f Cetificado BASC')
    certificadoiso=fields.Boolean('Certificado ISO:9001 Vigencia')
    acuerdoseguridad=fields.Boolean('Acuerdo Seguridad')
    inscripcion=fields.Boolean('Inscripcion')
    visitainstalacion=fields.Boolean('Visita Instalacion')
    verificacionlclinton=fields.Boolean('Verificacion L.Clinton')
    controloria=fields.Boolean('Controloria')
    procuradoria=fields.Boolean('Procuraduria')
    requisitosbasq=fields.Boolean('Requisitos BASQ')
    camaradecomercio=fields.Boolean('Camara de Comercio')
    rut=fields.Boolean('RUT')
    dev_ref=fields.Integer(compute="_compute_dev_ref", size=1, string="Digito Verificacion", store=True)
    
    _sql_constraints = [
        ('ref_uniq', 'unique(ref)', 'El documento no puede ser repetido'),
    ]
    
#