# -*- coding: utf-8 -*-
from openerp import models, fields, api, sql_db
from openerp.exceptions import Warning


class ResCompany(models.Model):
    _inherit = 'res.company'
    _description = 'Decreto 558 de 2020, cambio de porcentaje de cotizacion al sistema general de pensiones'

    percentage_total = fields.Float(string='Porcentaje de total')
    percentage_employee = fields.Float(string='Porcentaje del empleado', readonly=True)
    percentage_employer = fields.Float(string='Porcentaje del empleador', readonly=True)

    @api.one
    @api.onchange('percentage_total')
    def percentage_total_onchage(self):
        self.compute_percentages()

    @api.one
    @api.constrains('percentage_total')
    def percentage_total_constrains(self):
        self.compute_percentages()

    def compute_percentages(self):
        if self.percentage_total <= 0:
            raise Warning('Debe configurar el Porcentaje de total mayor a 0')
        self.percentage_employee = self.percentage_total * 0.25
        self.percentage_employer = self.percentage_total * 0.75