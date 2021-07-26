# -*- coding: utf-8 -*-

import time
from datetime import datetime
import openerp
from openerp import models, fields, api
import openerp.addons.decimal_precision as dp
from openerp.exceptions import Warning
from openerp.addons.avancys_tools import report_tools
from openerp.addons.avancys_orm import avancys_orm as orm


#CERTIFICADOS DE RETENCION
class print_certificado_retencion_line(models.Model):
    _name = "print.certificado.retencion.line"

    name = fields.Char(string='Name', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañia', required=True, readonly=True)
    base_amount = fields.Float(string='Base', digits=dp.get_precision('Account'), readonly=True)
    tax_amount = fields.Float(string='Retenido', digits=dp.get_precision('Account'), readonly=True)
    account_id = fields.Many2one('account.account', string='Cuenta/Impuesto', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Tercero', readonly=True)
    count = fields.Integer(string="Movimientos", readonly=True)
    certificado_print_id = fields.Many2one('print.certificado.retencion', string='Certificado')
    invoice_ids = fields.Char(string='Facturas', readonly=True)
    porcentaje = fields.Float(string='Porcentaje', digits=dp.get_precision('Payroll Rate'), readonly=True)
    tax_amount_parent = fields.Float(string='Base Padre', digits=dp.get_precision('Account'), readonly=True)
    note = fields.Char(string='Descripcion', readonly=True)

    tax_id = fields.Many2one('account.tax', string='Id_Impuesto', readonly=True)

    def view_invoice(self, cr, uid, ids, context=None):
        context = dict(context or {})
        line = self.browse(cr, uid, ids, context=context)


        invoice_ids = [int(e) if e.isdigit() else e for e in line.invoice_ids.split(',')]

        domain = [('id','in',invoice_ids)]
        return {
                'domain': domain,
                'name': 'Invoice',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.invoice',
                'type': 'ir.actions.act_window'
            }

class print_certificado_retencion(models.Model):
    _name = "print.certificado.retencion"
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    @api.one
    @api.depends('certificado_ids')
    def _total(self):
        if self.certificado_ids:
            amount = 0.0
            for line in self.certificado_ids:
                amount+=line.tax_amount
            self.amount_total = amount

    @api.one
    @api.depends('amount_total')
    def _total_text(self):
        amount = self.amount_total
        self.amount_total_text = report_tools.avancys_amount_to_text_decimal(amount)

    company_id = fields.Many2one('res.company', string='Compañia', required=True, readonly=True)
    cert_id = fields.Many2one('certidicado.report.retencion', string='Certificado', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Tercero', required=True, readonly=True)
    city_id = fields.Many2one('res.city', string='Ciudad', readonly=True)
    certificado_ids = fields.One2many('print.certificado.retencion.line', 'certificado_print_id', string='Certificado', readonly=True)
    periodo_id = fields.Many2one('certidicado.report.retencion.periodicidad', string='Periodo', required=True, readonly=True)
    state = fields.Selection([('Nuevo', 'Nuevo'),('Impreso', 'Impreso')], string='Estado', required=True, default='Nuevo', readonly=True)
    amount_total = fields.Float(string='amount', digits=dp.get_precision('Account'), compute="_total", readonly=True)
    amount_total_text = fields.Char(string='amount_text', compute="_total_text")

class certidicado_report_retencion(models.Model):
    _name = 'certidicado.report.retencion'

    name = fields.Char(string='Nombre', required=True)
    title = fields.Char(string='Titulo', required=True)
    description = fields.Text(string='Notas')
    line_ids = fields.One2many('certidicado.report.retencion.line', 'line_id', string='Lineas de Impuestos', required=True)
    city_id_1 = fields.Many2one('res.city', string='Ciudad donde se practico')
    city_id_2 = fields.Many2one('res.city', string='Ciudad donde se consigno')
    type_report = fields.Selection([('Mensual', 'Mensual'),('Bimestral', 'Bimestral'),('Trimestral', 'Trimestral'),('Semestral', 'Semestral'),('Anual', 'Anual')], string='Periodicidad', required=True, default='Anual')
    impuesto_compuesto = fields.Boolean(string='Impuesto Compuesto', default=False)
    type = fields.Selection([('Certificado', 'Certificado'),('Declaracion', 'Declaracion')], string='Tipo', required=True, default='Declaracion')
    is_ica = fields.Boolean(string='Impuesto ICA', default=False)

    @api.onchange('is_ica')
    def compute_city(self):
        if self.is_ica:
            self.city_id_1 = None
            self.city_id_2 = None


class certidicado_report_retencion_line(models.Model):
    _name = 'certidicado.report.retencion.line'

    @api.one
    @api.depends('tax_id')
    def _amount(self):
        if self.tax_id:
            self.porcentaje = self.tax_id.amount * 100

    name = fields.Char(string='Nombre', required=True)
    tax_id = fields.Many2one('account.tax', string='Impuesto', required=True)
    compuesto_id = fields.Many2one('account.tax', string='Impuesto Padre', related='tax_id.parent_id', readonly=True)
    account_id = fields.Many2one('account.account', string='Cuentas de Impuestos', domain = [('type','!=','view')], required=True)
    line_id = fields.Many2one('certidicado.report.retencion', string='Parent')
    porcentaje = fields.Float(string='Porcentaje', digits=dp.get_precision('Payroll Rate'), compute="_amount", readonly=True)
    ciudad_tercero = fields.Char(string='Ciudad')

class certidicado_report_retencion_periodicidad(models.Model):
    _name = 'certidicado.report.retencion.periodicidad'

    name = fields.Char(string='Nombre', required=True)
    type_report = fields.Selection([('Mensual', 'Mensual'),('Bimestral', 'Bimestral'),('Trimestral', 'Trimestral'),('Semestral', 'Semestral'),('Anual', 'Anual')], string='Periodicidad', required=True, default='Anual')
    date_start = fields.Date(string='Desde', required=True)
    date_end = fields.Date(string='Hasta', required=True)


class wizard_certificado_retencion(models.TransientModel):
    _name = "wizard.certificado.retencion"

    company_id = fields.Many2one('res.company', string='Compañia', required=True)
    cert_id = fields.Many2one('certidicado.report.retencion', string='Certificado', required=True)
    type_report = fields.Selection([('Mensual', 'Mensual'),('Bimestral', 'Bimestral'),('Trimestral', 'Trimestral'),('Semestral', 'Semestral'),('Anual', 'Anual')], related="cert_id.type_report", string='Periodicidad', readonly=True)
    periodo_id = fields.Many2one('certidicado.report.retencion.periodicidad', string='Periodo', required=True)
    partner_ids = fields.Many2many('res.partner', string='Terceros')

    @api.multi
    def print_report(self):

        self._cr.execute(''' DELETE FROM print_certificado_retencion_line WHERE create_uid = %s''' % self.env.uid)
        self._cr.execute(''' DELETE FROM print_certificado_retencion WHERE create_uid = %s''' % self.env.uid)

        datas = {}
        dict={}
        l_ids= []
        tax_amount_parent = 0.0
        account_obj = self.env['account.account']
        partner_obj = self.env['res.partner']

        account_ids = tuple([x.account_id.id for x in self.cert_id.line_ids])

        if self.partner_ids:
            partner_ids = tuple([x.id for x in self.partner_ids])
        else:
            partner_ids = tuple([x.id for x in partner_obj.search([('supplier','=',True)])])

        date_start = self.periodo_id.date_start
        date_end = self.periodo_id.date_end


        self._cr.execute('''SELECT 
                                aml.account_id, 
                                aml.partner_id,
                                SUM(aml.base_amount),
                                SUM(aml.tax_amount),
                                COUNT(aml.*),
                                string_agg(ai.id::varchar,',')
                            FROM 
                                account_move_line aml
                                left join account_invoice ai on ai.move_id = aml.move_id
                            WHERE  
                                aml.account_id in %s AND aml.partner_id in %s
                                AND (aml.date >= %s AND aml.date <= %s AND aml.state = 'valid')
                            GROUP BY
                                aml.account_id, 
                                aml.partner_id''',
                    (account_ids,partner_ids,date_start,date_end))
        result = self._cr.fetchall()
        for res in result:
            account_id=res[0],
            partner_id=res[1]
            base_amount=res[2]
            tax_amount=res[3]
            count=res[4]
            invoice_ids=res[5] or ''

            line = self.env['certidicado.report.retencion.line'].search([('line_id','=',self.cert_id.id),('account_id','=',account_id)])
            if self.cert_id.impuesto_compuesto:
                if not line.compuesto_id:
                    raise osv.except_osv(_('Error !'), _("El certificado '%s' esta configurado como Impuesto Compuesto, el impuesto '%s'  debe tener un impuesto padre asociado") % (self.cert_id.name,line.tax_id.name))
                tax_amount_parent = base_amount/line.compuesto_id.amount

            if self.cert_id.is_ica:
                tax_id = self.env['account.tax'].search([('account_collected_id', '=', account_id)])
                city_taxes = '(' + ','.join([str(c.id) for c in tax_id] or ['0'])  + ')'
                city = "SELECT ciudad FROM account_tax WHERE id in {taxes} GROUP BY ciudad".format(taxes=city_taxes)
                self._cr.execute(city)
                check = self._cr.fetchall()
                if len(check) > 1:
                    raise osv.except_osv(_('Error !'), _("Al menos 2 impuestos configurados en el reporte contienen la misma cueta contable y no pertenecen a la misma ciudad. Los ids de estos impuestos son: %s ") % (city_id))
                else:
                    city_id=check[0][0]
                key=str(partner_id)+str(city_id)

            else:
                key = partner_id

            if key in dict:
                certificado_print_id = dict[key]['certificado_print_id']

                for l in line:
                    self._cr.execute('''INSERT INTO print_certificado_retencion_line (create_uid,name,tax_id,note,tax_amount_parent,porcentaje,invoice_ids,company_id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                    (self.env.uid,l.name,l.tax_id.id,l.tax_id.name,tax_amount_parent,abs(l.porcentaje or 0.0),invoice_ids,self.company_id.id,certificado_print_id,partner_id,account_id,abs(base_amount or 0.0),abs(tax_amount or 0.0),count))
                    break
            else:
                if self.cert_id.is_ica:
                    self._cr.execute('''INSERT INTO print_certificado_retencion (create_uid,state,periodo_id,company_id,partner_id,city_id,cert_id) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                    (self.env.uid,'Nuevo',self.periodo_id.id,self.company_id.id,partner_id,city_id,self.cert_id.id))
                    certificado_print_id = self._cr.fetchone()[0]
                    dict[key] ={'certificado_print_id': certificado_print_id}
                else:
                    self._cr.execute('''INSERT INTO print_certificado_retencion (create_uid,state,periodo_id,company_id,partner_id,cert_id) VALUES 
                    (%s,%s,%s,%s,%s,%s) RETURNING id''',
                    (self.env.uid, 'Nuevo', self.periodo_id.id, self.company_id.id, partner_id, self.cert_id.id))
                    certificado_print_id = self._cr.fetchone()[0]
                    dict[key] = {'certificado_print_id': certificado_print_id}

                for l in line:
                    self._cr.execute('''INSERT INTO print_certificado_retencion_line (create_uid,name,tax_id,note,tax_amount_parent,porcentaje,invoice_ids,company_id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                    (self.env.uid,l.name,l.tax_id.id,l.tax_id.name,tax_amount_parent,abs(l.porcentaje or 0.0),invoice_ids,self.company_id.id,certificado_print_id,partner_id,account_id,abs(base_amount or 0.0),abs(tax_amount or 0.0),count))
                    break

        domain = [('create_uid', '=', self.env.uid)]

        return {
            'domain': domain,
            'name': 'Certificados de Retencion',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'print.certificado.retencion',
            'type': 'ir.actions.act_window'
                }

    def send_report(self, cr, uid, ids, context=None):

        cr.execute(''' DELETE FROM print_certificado_retencion_line WHERE create_uid = %s''' % uid)
        cr.execute(''' DELETE FROM print_certificado_retencion WHERE create_uid = %s''' % uid)

        datas = {}
        dict={}
        l_ids= []
        tax_amount_parent = 0.0

        certificado_obj = self.pool.get('print.certificado.retencion')
        account_obj = self.pool.get('account.account')
        partner_obj = self.pool.get('res.partner')
        template_obj = self.pool.get('email.template')
        ir_model_data = self.pool.get('ir.model.data')
        compose_data = self.pool.get('mail.compose.message')

        for report in self.browse(cr, uid, ids, context=context):

            account_ids = tuple([x.account_id.id for x in report.cert_id.line_ids])

            if report.partner_ids:
                partner_ids = tuple([x.id for x in report.partner_ids])
            else:
                partner_ids = tuple(partner_obj.search(cr, uid, [('supplier','=',True)], context=context))

            date_start = report.periodo_id.date_start
            date_end = report.periodo_id.date_end

            cr.execute('''SELECT 
                                aml.account_id, 
                                aml.partner_id,
                                SUM(aml.base_amount),
                                SUM(aml.tax_amount),
                                COUNT(aml.*),
                                string_agg(ai.id::varchar,',')
                            FROM 
                                account_move_line aml
                                left join account_invoice ai on ai.move_id = aml.move_id
                            WHERE  
                                aml.account_id in %s AND aml.partner_id in %s
                                AND (aml.date >= %s AND aml.date <= %s AND aml.state = 'valid')
                            GROUP BY
                                aml.account_id, 
                                aml.partner_id''',
                    (account_ids,partner_ids,date_start,date_end))
            result = cr.fetchall()

            for res in result:
                account_id=res[0],
                partner_id=res[1]
                base_amount=res[2]
                tax_amount=res[3]
                count=res[4]
                invoice_ids=res[5] or ''

                line = self.pool.get('certidicado.report.retencion.line').search(cr, uid, [('line_id','=',report.cert_id.id),('account_id','=',account_id)], context=context)
                line = self.pool.get('certidicado.report.retencion.line').browse(cr, uid, line, context=context)
                if report.cert_id.impuesto_compuesto:
                    if not line.compuesto_id:
                        raise osv.except_osv(_('Error !'), _("El certificado '%s' esta configurado como Impuesto Compuesto, el impuesto '%s'  debe tener un impuesto padre asociado") % (report.cert_id.name,line.tax_id.name))
                    tax_amount_parent = base_amount/line.compuesto_id.amount
                key=partner_id
                if key in dict:
                    certificado_print_id = dict[key]['certificado_print_id']
                    for l in line:
                        cr.execute('''INSERT INTO print_certificado_retencion_line (create_uid,note,tax_amount_parent,porcentaje,invoice_ids,company_id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        (uid,l.tax_id.name,tax_amount_parent,l.porcentaje,invoice_ids,report.company_id.id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count))
                        break
                else:
                    cr.execute('''INSERT INTO print_certificado_retencion (create_uid,state,periodo_id,company_id,partner_id,cert_id) VALUES 
                    (%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                    (uid,'Nuevo',report.periodo_id.id,report.company_id.id,partner_id,report.cert_id.id))
                    certificado_print_id = cr.fetchone()[0]
                    dict[key] ={'certificado_print_id': certificado_print_id}
                    for l in line:
                        cr.execute('''INSERT INTO print_certificado_retencion_line (create_uid,note,tax_amount_parent,porcentaje,invoice_ids,company_id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count) VALUES 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                        (uid,l.tax_id.name,tax_amount_parent,l.porcentaje,invoice_ids,report.company_id.id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count))
                        break

                    try:
                        template_id = ir_model_data.get_object_reference(cr, uid, 'report_odoo_extended', 'email_template_certificado_retencion')[1]
                    except ValueError:
                        template_id = False
                    ctx = {
                        'default_model': 'print.certificado.retencion',
                        'default_res_id': certificado_print_id,
                        'default_use_template': bool(template_id),
                        'default_template_id': template_id,
                        'default_composition_mode': 'comment',
                        'mark_so_as_sent': True,
                        'lang': 'es_CO',
                        'tz': 'America/Bogota',
                        'uid': uid,
                    }
                    values = self.pool.get('mail.compose.message').generate_email_for_composer(cr, uid, template_id, certificado_print_id, context=ctx)
                    compose_id = self.pool.get('mail.compose.message').create(cr, uid, values, context=ctx)
                    self.pool.get('mail.compose.message').write(cr, uid, compose_id, {'partner_ids': [(6, 0, [partner_id])]}, context=context)
                    self.pool.get('mail.compose.message').send_mail(cr, uid, [compose_id], context=ctx)

        domain = [('create_uid', '=', uid)]

        return {
            'domain': domain,
            'name': 'Certificados de Retencion',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'print.certificado.retencion',
            'type': 'ir.actions.act_window'
                }












    ###################################
    ######DECLARACION DE IMPUESTOS#####
    ###################################

class certificado_tax(models.Model):
    _name = "certificado.tax"
    _inherit = ['mail.thread', 'ir.needaction_mixin']


    @api.one
    @api.depends('certificado_line_ids')
    def _count(self):
        res = []
        if self.certificado_line_ids:
            self.count_line = len(self.certificado_line_ids)

    @api.one
    @api.depends('certificado_line_ids', 'state')
    def _total(self):
        if self.certificado_line_ids:
            amount = 0.0
            base = 0.0
            for line in self.certificado_line_ids:
                amount+=line.tax_amount
                base+=line.base_amount
            self.amount_total = amount
            self.base_total = base

    name = fields.Char(string='Name', readonly=True)
    count_line=fields.Integer(string='Detalle', compute="_count")
    company_id = fields.Many2one('res.company', string='Compañia', required=True, readonly=True)
    cert_id = fields.Many2one('certidicado.report.retencion', string='Formulario', required=True, readonly=True)
    periodo_id = fields.Many2one('certidicado.report.retencion.periodicidad', string='Periodo', required=True, readonly=True)
    state = fields.Selection([('Borrador', 'Borrador'),('Asentado', 'Asentado')], string='Estado', readonly=True)
    amount_total = fields.Float(string='Impuesto', digits=dp.get_precision('Account'), compute="_total", readonly=True, store=True)
    base_total = fields.Float(string='Base', digits=dp.get_precision('Account'), compute="_total", readonly=True, store=True)
    certificado_ids = fields.One2many('print.certificado.tax', 'certificado_id', string='Terceros', readonly=True)
    certificado_line_ids = fields.One2many('print.certificado.tax.line', 'certificado_id', string='Detalle', readonly=True)

    def view_detalle(self, cr, uid, ids, context=None):
        context = dict(context or {})
        inv=[]
        for line in self.browse(cr, uid, ids, context=context).certificado_line_ids:
            inv.append(line.id)


        domain = [('id','in',inv)]
        return {
                'domain': domain,
                'name': 'Detalle',
                'view_type': 'form',
                'view_mode': 'graph,tree,form',
                'view_id': False,
                'res_model': 'print.certificado.tax.line',
                'type': 'ir.actions.act_window'
            }

class print_certificado_tax_line(models.Model):
    _name = "print.certificado.tax.line"

    name = fields.Char(string='Name', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañia', required=True, readonly=True)
    base_amount = fields.Float(string='Base', digits=dp.get_precision('Account'), readonly=True)
    tax_amount = fields.Float(string='Impuesto', digits=dp.get_precision('Account'), readonly=True)
    account_id = fields.Many2one('account.account', string='Cuenta/Impuesto', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Tercero', readonly=True)
    count = fields.Integer(string="Movimientos", readonly=True)
    certificado_print_id = fields.Many2one('print.certificado.tax', string='Certificado')
    invoice_ids = fields.Char(string='Facturas', readonly=True)
    porcentaje = fields.Float(string='Porcentaje', digits=dp.get_precision('Payroll Rate'), readonly=True)
    tax_amount_parent = fields.Float(string='Base Padre', digits=dp.get_precision('Account'), readonly=True)
    note = fields.Char(string='Descripcion', readonly=True)
    certificado_id = fields.Many2one('certificado.tax', string='Certificado', required=True, readonly=True)

    def view_invoice(self, cr, uid, ids, context=None):
        context = dict(context or {})
        line = self.browse(cr, uid, ids, context=context)


        invoice_ids = [int(e) if e.isdigit() else e for e in line.invoice_ids.split(',')]

        domain = [('id','in',invoice_ids)]
        return {
                'domain': domain,
                'name': 'Invoice',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.invoice',
                'type': 'ir.actions.act_window'
            }

class print_certificado_tax(models.Model):
    _name = "print.certificado.tax"
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    @api.one
    @api.depends('certificado_ids')
    def _total(self):
        if self.certificado_ids:
            amount = 0.0
            base = 0.0
            for line in self.certificado_ids:
                amount+=line.tax_amount
                base+=line.base_amount
            self.amount_total = amount
            self.base_total = base

    company_id = fields.Many2one('res.company', string='Compañia', required=True, readonly=True)
    cert_id = fields.Many2one('certidicado.report.retencion', string='Certificado', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Tercero', required=True, readonly=True)
    certificado_ids = fields.One2many('print.certificado.tax.line', 'certificado_print_id', string='Certificado', readonly=True)
    periodo_id = fields.Many2one('certidicado.report.retencion.periodicidad', string='Periodo', required=True, readonly=True)
    state = fields.Selection([('Borrador', 'Borrador'),('Asentado', 'Asentado')], string='Estado', required=True, default='Borrador', readonly=True)
    amount_total = fields.Float(string='amount', digits=dp.get_precision('Account'), compute="_total", readonly=True)
    base_total = fields.Float(string='Base', digits=dp.get_precision('Account'), compute="_total", readonly=True)
    certificado_id = fields.Many2one('certificado.tax', string='Certificado', required=True, readonly=True)

class wizard_certificado_tax(models.TransientModel):
    _name = "wizard.certificado.tax"

    company_id = fields.Many2one('res.company', string='Compañia', required=True)
    cert_id = fields.Many2one('certidicado.report.retencion', string='Formulario', required=True)
    type_report = fields.Selection([('Mensual', 'Mensual'),('Bimestral', 'Bimestral'),('Trimestral', 'Trimestral'),('Semestral', 'Semestral'),('Anual', 'Anual')], related="cert_id.type_report", string='Periodicidad', readonly=True)
    periodo_id = fields.Many2one('certidicado.report.retencion.periodicidad', string='Periodo', required=True)
    partner_ids = fields.Many2many('res.partner', string='Terceros')

    @api.multi
    def print_report(self):

        self._cr.execute(''' DELETE FROM print_certificado_tax_line''')
        self._cr.execute(''' DELETE FROM print_certificado_tax''')
        self._cr.execute(''' DELETE FROM certificado_tax''')

        datas = {}
        dict={}
        l_ids= []
        tax_amount_parent = 0.0
        account_obj = self.env['account.account']
        partner_obj = self.env['res.partner']

        account_ids = tuple([x.account_id.id for x in self.cert_id.line_ids])

        if self.partner_ids:
            partner_ids = tuple([x.id for x in self.partner_ids])
        else:
            partner_ids = tuple([x.id for x in partner_obj.search([('supplier','=',True),('customer','=',True)])])

        date_start = self.periodo_id.date_start
        date_end = self.periodo_id.date_end

        self._cr.execute('''INSERT INTO certificado_tax (name,periodo_id,company_id,cert_id) VALUES 
        (%s,%s,%s,%s) RETURNING id''' ,
        (self.cert_id.title,self.periodo_id.id,self.company_id.id,self.cert_id.id))
        certificado_id = self._cr.fetchone()[0]

        self._cr.execute('''SELECT 
                                aml.account_id, 
                                aml.partner_id,
                                SUM(aml.base_amount),
                                SUM(aml.tax_amount),
                                COUNT(aml.*),
                                string_agg(ai.id::varchar,',')
                            FROM 
                                account_move_line aml
                                left join account_invoice ai on ai.move_id = aml.move_id
                            WHERE  
                                aml.account_id in %s AND aml.partner_id in %s
                                AND (aml.date >= %s AND aml.date <= %s AND aml.state = 'valid')
                            GROUP BY
                                aml.account_id, 
                                aml.partner_id''',
                    (account_ids,partner_ids,date_start,date_end))
        result = self._cr.fetchall()
        for res in result:
            account_id=res[0],
            partner_id=res[1]
            base_amount=res[2]
            tax_amount=res[3]
            count=res[4]
            invoice_ids=res[5] or ''

            line = self.env['certidicado.report.retencion.line'].search([('line_id','=',self.cert_id.id),('account_id','=',account_id)])
            if self.cert_id.impuesto_compuesto:
                if not line.compuesto_id:
                    raise osv.except_osv(_('Error !'), _("El certificado '%s' esta configurado como Impuesto Compuesto, el impuesto '%s'  debe tener un impuesto padre asociado") % (self.cert_id.name,line.tax_id.name))
                tax_amount_parent = base_amount/line.compuesto_id.amount
            key=partner_id
            if key in dict:
                certificado_print_id = dict[key]['certificado_print_id']
                self._cr.execute('''INSERT INTO print_certificado_tax_line (certificado_id,name,note,tax_amount_parent,porcentaje,invoice_ids,company_id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                (certificado_id,line.name,line.tax_id.name,tax_amount_parent,abs(line.porcentaje or 0.0),invoice_ids,self.company_id.id,certificado_print_id,partner_id,account_id,abs(base_amount or 0.0),abs(tax_amount or 0.0),count))
            else:
                self._cr.execute('''INSERT INTO print_certificado_tax (certificado_id,state,periodo_id,company_id,partner_id,cert_id) VALUES 
                (%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                (certificado_id,'Nuevo',self.periodo_id.id,self.company_id.id,partner_id,self.cert_id.id))
                certificado_print_id = self._cr.fetchone()[0]
                dict[key] ={'certificado_print_id': certificado_print_id}
                self._cr.execute('''INSERT INTO print_certificado_tax_line (certificado_id,name,note,tax_amount_parent,porcentaje,invoice_ids,company_id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count) VALUES 
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                (certificado_id,line.name,line.tax_id.name,tax_amount_parent,abs(line.porcentaje or 0.0),invoice_ids,self.company_id.id,certificado_print_id,partner_id,account_id,abs(base_amount or 0.0),abs(tax_amount or 0.0),count))

        self.env['certificado.tax'].browse(certificado_id).state = 'Borrador'
        return {
            'name': 'Declaracion de Impuestos',
            'view_type': 'form',
            'view_mode': 'tree,form,graph',
            'view_id': False,
            'res_model': 'certificado.tax',
            'type': 'ir.actions.act_window'
                }




    def send_report(self, cr, uid, ids, context=None):

        cr.execute(''' DELETE FROM print_certificado_retencion_line''')
        cr.execute(''' DELETE FROM print_certificado_retencion''')

        datas = {}
        dict={}
        l_ids= []
        tax_amount_parent = 0.0

        certificado_obj = self.pool.get('print.certificado.tax')
        account_obj = self.pool.get('account.account')
        partner_obj = self.pool.get('res.partner')
        template_obj = self.pool.get('email.template')
        ir_model_data = self.pool.get('ir.model.data')
        compose_data = self.pool.get('mail.compose.message')

        for report in self.browse(cr, uid, ids, context=context):

            account_ids = tuple([x.account_id.id for x in report.cert_id.line_ids])

            if report.partner_ids:
                partner_ids = tuple([x.id for x in report.partner_ids])
            else:
                partner_ids = tuple(partner_obj.search(cr, uid, [('supplier','=',True)], context=context))

            date_start = report.periodo_id.date_start
            date_end = report.periodo_id.date_end

            cr.execute('''SELECT 
                                aml.account_id, 
                                aml.partner_id,
                                SUM(aml.base_amount),
                                SUM(aml.tax_amount),
                                COUNT(aml.*),
                                string_agg(ai.id::varchar,',')
                            FROM 
                                account_move_line aml
                                left join account_invoice ai on ai.move_id = aml.move_id
                            WHERE  
                                aml.account_id in %s AND aml.partner_id in %s
                                AND (aml.date >= %s AND aml.date <= %s AND aml.state = 'valid')
                            GROUP BY
                                aml.account_id, 
                                aml.partner_id''',
                    (account_ids,partner_ids,date_start,date_end))
            result = cr.fetchall()

            for res in result:
                account_id=res[0],
                partner_id=res[1]
                base_amount=res[2]
                tax_amount=res[3]
                count=res[4]
                invoice_ids=res[5] or ''

                line = self.pool.get('certidicado.report.retencion.line').search(cr, uid, [('line_id','=',report.cert_id.id),('account_id','=',account_id)], context=context)
                line = self.pool.get('certidicado.report.retencion.line').browse(cr, uid, line, context=context)
                if report.cert_id.impuesto_compuesto:
                    if not line.compuesto_id:
                        raise osv.except_osv(_('Error !'), _("El certificado '%s' esta configurado como Impuesto Compuesto, el impuesto '%s'  debe tener un impuesto padre asociado") % (report.cert_id.name,line.tax_id.name))
                    tax_amount_parent = base_amount/line.compuesto_id.amount
                key=partner_id
                if key in dict:
                    certificado_print_id = dict[key]['certificado_print_id']
                    cr.execute('''INSERT INTO print_certificado_retencion_line (note,tax_amount_parent,porcentaje,invoice_ids,company_id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                    (line.tax_id.name,tax_amount_parent,line.porcentaje,invoice_ids,report.company_id.id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count))
                else:
                    cr.execute('''INSERT INTO print_certificado_retencion (state,periodo_id,company_id,partner_id,cert_id) VALUES 
                    (%s,%s,%s,%s,%s) RETURNING id''' ,
                    ('Nuevo',report.periodo_id.id,report.company_id.id,partner_id,report.cert_id.id))
                    certificado_print_id = cr.fetchone()[0]
                    dict[key] ={'certificado_print_id': certificado_print_id}
                    cr.execute('''INSERT INTO print_certificado_retencion_line (note,tax_amount_parent,porcentaje,invoice_ids,company_id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count) VALUES 
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''' ,
                    (line.tax_id.name,tax_amount_parent,line.porcentaje,invoice_ids,report.company_id.id,certificado_print_id,partner_id,account_id,base_amount,tax_amount,count))

                    try:
                        template_id = ir_model_data.get_object_reference(cr, uid, 'report_odoo_extended', 'email_template_certificado_retencion')[1]
                    except ValueError:
                        template_id = False
                    ctx = {
                        'default_model': 'print.certificado.tax',
                        'default_res_id': certificado_print_id,
                        'default_use_template': bool(template_id),
                        'default_template_id': template_id,
                        'default_composition_mode': 'comment',
                        'mark_so_as_sent': True,
                        'lang': 'es_CO',
                        'tz': 'America/Bogota',
                        'uid': uid,
                    }
                    print "111111111111"
                    print template_id
                    print ""
                    values = self.pool.get('mail.compose.message').generate_email_for_composer(cr, uid, template_id, certificado_print_id, context=ctx)
                    compose_id = self.pool.get('mail.compose.message').create(cr, uid, values, context=ctx)
                    self.pool.get('mail.compose.message').write(cr, uid, compose_id, {'partner_ids': [(6, 0, [partner_id])]}, context=context)
                    self.pool.get('mail.compose.message').send_mail(cr, uid, [compose_id], context=ctx)

        return {
            'name': 'Declaracion de Impuestos',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'print.certificado.tax',
            'type': 'ir.actions.act_window'
                }







    ##############################################
    ######CERTIFICADO DE INGRESOS Y RETENCION#####
    ##############################################


class certificado_report_ingresos(models.Model):
    _name = 'certificado.report.ingresos'

    name = fields.Char(string='Nombre', required=True)
    num = fields.Char(string='Numero Formulario', required=True, default="220")
    company_id = fields.Many2one('res.company', string='Compania', required=True)
    partner_id = fields.Many2one('res.partner', related='company_id.partner_id', string='Tercero', readonly=True)
    ref = fields.Char(string='Nit', related="partner_id.ref", readonly=True)
    dev_ref = fields.Integer(string='Digito Verificacion', related='partner_id.dev_ref', readonly=True)
    title = fields.Char(string='Titulo', required=True, default="Certificado deIngresos y Retencion para PersonasNaturales Empleados Año Gravable 2016")
    description = fields.Text(string='Descripcion')
    conceptos_ids = fields.One2many('certificado.report.ingresos.line', 'line_id', string='Linea de Conceptos', required=True)
    city_id = fields.Many2one('res.city', string='Ciudad donde se practico')


class certificado_report_ingresos_line(models.Model):
    _name = 'certificado.report.ingresos.line'

    name = fields.Char(string='Nombre', required=True)
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type',  '!=', 'view')])
    concepts = fields.Char('Conceptos de nomina',
                           help="Conceptos de nomina en mayusculas separado por comas sin espacios")
    line_id = fields.Many2one('certificado.report.ingresos', string='Parent')
    description = fields.Char(string='Descripcion')
    sequence = fields.Integer(string="Secuencia")
    type = fields.Selection([('ingreso', 'Ingreso'),('ingreso', 'Ingreso'),('aporte', 'Aporte'),('retencion', 'Retencion'),('pension', 'Pension')], string='Tipo')
    amount = fields.Float(string='Valor %', digits=dp.get_precision('Account'))


class certificado_ingresos(models.Model):
    _name = "certificado.ingresos"
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    name = fields.Char(string='Name', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañia', required=True, readonly=True)
    cert_id = fields.Many2one('certificado.report.ingresos', string='Formulario', required=True, readonly=True)
    state = fields.Selection([('Borrador', 'Borrador'),('Asentado', 'Asentado')], string='Estado', readonly=True)
    account_year_id = fields.Many2one('account.fiscalyear', string='Ejercicio', readonly=True)
    certificado_ids = fields.One2many('certificado.ingresos.line', 'certificado_id', string='Terceros', readonly=True)


class certificado_ingresos_line(models.Model):
    _name = "certificado.ingresos.line"
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    company_id = fields.Many2one('res.company', string='Compañia', required=True, readonly=True)
    name = fields.Many2one('hr.employee', string='Empleado', readonly=True)
    certificado_id = fields.Many2one('certificado.ingresos', string='Certificado', required=True, readonly=True)
    items_ids = fields.One2many('certificado.ingresos.line.item', 'parent_id', string='Cert Ing Ret', readonly=True)
    cert_id = fields.Many2one('certificado.report.ingresos', string='Formulario', required=True, readonly=True)
    account_year_id = fields.Many2one('account.fiscalyear', string='Ejercicio', readonly=True)
    date_from = fields.Date('Desde')
    date_to = fields.Date('Hasta')


class certificado_ingresos_line_item(models.Model):
    _name = "certificado.ingresos.line.item"

    name = fields.Char(string='Name', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañia', required=True, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', readonly=True)
    certificado_id = fields.Many2one('certificado.ingresos', string='Certificado', required=True, readonly=True)
    concepto_id = fields.Many2one('certificado.report.ingresos.line', string='Conceptos', readonly=True)
    amount = fields.Float(string='amount', digits=dp.get_precision('Account'),readonly=True)
    parent_id = fields.Many2one('certificado.ingresos.line', string='Parent', readonly=True)
    move_ids = fields.Text(string="Movimientos", readonly=True)

    def view_moves(self, cr, uid, ids, context=None):
        context = dict(context or {})
        line = self.browse(cr, uid, ids, context=context)

        move_ids = [int(e) if e.isdigit() else e for e in line.move_ids.split(',')]

        domain = [('id','in',move_ids)]
        return {
                'domain': domain,
                'name': 'Invoice',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'hr.payslip.concept',
                'type': 'ir.actions.act_window'
            }


class wizard_certificado_ingresos(models.TransientModel):
    _name = "wizard.certificado.ingresos"

    cert_id = fields.Many2one('certificado.report.ingresos', string='Formulario', required=True)
    employee_ids = fields.Many2many('hr.employee', string='Empleados')
    account_year_id = fields.Many2one('account.fiscalyear', string='Ejercicio', required=True)

    @api.multi
    def print_report(self, send=False):
        self._cr.execute("DELETE FROM certificado_ingresos_line_item")
        self._cr.execute("DELETE FROM certificado_ingresos_line")
        self._cr.execute("DELETE FROM certificado_ingresos")

        cert_data = {
            'name': self.cert_id.title,
            'account_year_id': self.account_year_id.id,
            'cert_id': self.cert_id.id,
            'state': 'Borrador'
        }
        certif_id = orm.direct_create(self._cr, self._uid, 'certificado_ingresos', [cert_data], company=True)[0][0]

        if self.employee_ids:
            employee_ids = tuple([x.id for x in self.employee_ids])
        else:
            employee_ids = tuple([x.id for x in self.env['hr.employee'].search([])])

        date_start = self.account_year_id.date_start
        date_end = self.account_year_id.date_stop
        cert_items = []
        for employee in employee_ids:

            contracts_sql = ("SELECT id, date_start, date_end "
                             "from hr_contract "
                             "where employee_id = {emp} "
                             "order by date_start".format(emp=employee))

            contracts = orm.fetchall(self._cr, contracts_sql)
            if contracts:
                start = contracts[0][1]
                if not (self.account_year_id.date_start <= start <= self.account_year_id.date_stop):
                    start = self.account_year_id.date_start

                end = contracts[-1][2]
                if end:
                    if not (self.account_year_id.date_start <= end <= self.account_year_id.date_stop):
                        end = self.account_year_id.date_stop
                else:
                    end = self.account_year_id.date_stop

            else:
                start = self.account_year_id.date_start
                end = self.account_year_id.date_stop

            cert_line_data = {
                'name': employee,
                'certificado_id': certif_id,
                'cert_id': self.cert_id.id,
                'account_year_id': self.account_year_id.id,
                'date_from': start,
                'date_to': end,
            }

            cert_line = orm.direct_create(
                self._cr, self._uid, 'certificado_ingresos_line', [cert_line_data], company=True)[0][0]

            for concepto in self.cert_id.conceptos_ids.sorted(key=lambda y: y.sequence):
                cnpt_str = str(concepto.concepts)
                concepts = tuple([x.strip() for x in cnpt_str.split(',')])
                if len(concepts) == 1:
                    concepts = tuple([concepts[0], 'FALSE'])
                tot_concept = []
                if concepts:
                    sum_qry = ("SELECT hpc.employee_id, sum(hpc.total), count(hpc.id), string_agg(hpc.id::varchar,',') "
                               "FROM hr_payslip_concept hpc "
                               "INNER JOIN hr_payslip hp ON hp.id = hpc.payslip_id "
                               "WHERE hpc.employee_id = {emp} "
                               "AND hp.state = 'done' "
                               "AND hpc.date BETWEEN '{start}' and '{end}' "
                               "AND hpc.code in {concepts} "
                               "GROUP BY hpc.employee_id".format(emp=employee, start=date_start, end=date_end,
                                                                 concepts=concepts))
                    tot_concept = orm.fetchall(self._cr, sum_qry)

                if tot_concept:

                    cert_items.append({
                        'name': concepto.name,
                        'employee_id': employee,
                        'certificado_id': certif_id,
                        'concepto_id': concepto.id,
                        'amount': tot_concept[0][1],
                        'parent_id': cert_line,
                        'move_ids': tot_concept[0][3]
                    })

        orm.direct_create(self._cr, self._uid, 'certificado_ingresos_line_item',
                          cert_items, company=True, progress=True)

        if send is not False:
            return {
                'domain': [('id', '=', certif_id)],
                'name': 'Certificado de Ingresos y Retencion',
                'view_type': 'form',
                'view_mode': 'tree,form,graph',
                'view_id': False,
                'res_model': 'certificado.ingresos',
                'type': 'ir.actions.act_window'
            }
        else:
            return {
                'certif_id': certif_id,
            }

    def send_report(self, cr, uid, ids, context=None):
        res = self.print_report(cr, uid, ids, context)
        ir_model_data = self.pool.get('ir.model.data')
        certificado = self.pool.get('certificado.ingresos').browse(cr, uid, res['certif_id'], context=context)

        for cert in certificado.certificado_ids:
            try:
                template_id = ir_model_data.get_object_reference(cr, uid, 'report_odoo_extended',
                                                                 'email_template_certificado_ingresos')[1]
            except ValueError:
                template_id = False
            ctx = {
                'default_model': 'certificado.ingresos.line',
                'default_res_id': cert.id,
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_composition_mode': 'comment',
                'mark_so_as_sent': True,
                'lang': 'es_CO',
                'tz': 'America/Bogota',
                'uid': uid,
            }
            values = self.pool.get('mail.compose.message').generate_email_for_composer(cr, uid, template_id, cert.id,
                                                                                       context=ctx)
            compose_id = self.pool.get('mail.compose.message').create(cr, uid, values, context=ctx)
            self.pool.get('mail.compose.message').write(cr, uid, compose_id,
                                                        {'partner_ids': [(6, 0, [cert.name.partner_id.id])]},
                                                        context=context)
            self.pool.get('mail.compose.message').send_mail(cr, uid, [compose_id], context=ctx)

        return {
            'domain': [('id', '=', res['certif_id'])],
            'name': 'Certificado de Ingresos y Retencion',
            'view_type': 'form',
            'view_mode': 'tree,form,graph',
            'view_id': False,
            'res_model': 'certificado.ingresos',
            'type': 'ir.actions.act_window'
        }
#
