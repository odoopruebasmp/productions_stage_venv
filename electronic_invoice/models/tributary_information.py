# -*- coding: utf-8 -*-
from openerp import models, fields, api


class TributaryObligations(models.Model):
    _name = 'tributary.obligations'

    code = fields.Char("Código", size=10, required=True)
    name = fields.Char("Nombre", required=True)
    description = fields.Char("Descripción")


class CustomsObligations(models.Model):
    _name = 'customs.obligations'

    code = fields.Char("Código", size=10, required=True)
    name = fields.Char("Nombre", required=True)
    description = fields.Char("Descripción")


class ResPartner(models.Model):
    _inherit = 'res.partner'

    tributary_obligations_ids = fields.Many2many('tributary.obligations', 'tributary_obl_partner_rel',
                                                 string='Responsabilidades Tributarias', help='Seleccione los códigos '
                                                 'correspondientes al campo 53 del formulario Registro Único '
                                                 'Tributario - DIAN')
    customs_obligations_ids = fields.Many2many('customs.obligations', 'customs_obl_partner_rel',
                                               string='Usuarios Aduaneros', help='Seleccione los códigos '
                                               'correspondientes al campo 54 del formulario Registro Único '
                                               'Tributario - DIAN')
