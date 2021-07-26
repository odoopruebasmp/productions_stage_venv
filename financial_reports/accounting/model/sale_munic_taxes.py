# -*- coding: utf-8 -*-
from datetime import datetime
from openerp import models, fields, api, _
from openerp.exceptions import Warning

class FinancialSaleMunicTaxes(models.Model):
    _name = "fpa.sale.munic.taxes"

    date = fields.Datetime(string="Fecha")
    date_from = fields.Date(string="Fecha Inicial")
    date_to = fields.Date(string="Fecha Final")
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    estado = fields.Selection([('draft', 'Borrador'), ('open', 'Abierto(a)'), ('paid', 'Pagada'),
                                  ('cancel', 'Cancelado(a)'), ('all', 'Todos')], string='Estado',
                                 help='Estado de las facturas')
    chart_account_id = fields.Boolean(string="Control NO plan contable")
    tot_value_f = fields.Float(string='Valor Total INV')
    tot_iva_f = fields.Float(string='Valor Total IVA INV')
    tot_auto_f = fields.Float(string='Valor Total AUTO INV')
    tot_value_n = fields.Float(string='Valor Total NC')
    tot_iva_n = fields.Float(string='Valor Total IVA NC')
    tot_auto_n = fields.Float(string='Valor Total AUTO NC')

class FinancialSaleMunicTaxesLine(models.Model):
    _name = "fpa.sale.munic.taxes.line"

    invoice_id = fields.Many2one('account.invoice', 'Número', ondelete='cascade', index=True)
    invoice_date = fields.Date('Fecha')
    analytic_acc_id = fields.Many2one('account.analytic.account', 'Cuenta Analítica', ondelete='cascade', index=True)
    munic_id = fields.Many2one('res.city', 'Municipio', ondelete='cascade')
    munic_cod = fields.Char('Cód. Municipio')
    tipo_acc = fields.Selection([('sale', 'Venta'), ('serv','Servicio')], string='Tipo Acción')
    partner_id = fields.Many2one('res.partner', 'Cliente', ondelete='cascade', index=True)
    partner_nit = fields.Char('NIT Cliente')
    invoice_value = fields.Float('Valor')
    invoice_tax = fields.Float('IVA')
    invoice_auto = fields.Float('Auto RETE')
    header_id = fields.Many2one('fpa.sale.munic.taxes', 'Encabezado')
    tipo_doc = fields.Selection([('out_refund','NC'),('out_invoice','FAC')], string='Tipo')
    inv_state = fields.Char('Estado')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte', index=True)
    company_id = fields.Many2one('res.company', string='Compañia', index=True)
    user_id = fields.Many2one('res.users', string='Usuario', index=True)

class FinancialSaleMunicTaxesWizard(models.TransientModel):
    _name = "fpa.sale.munic.taxes.wizard"


    @api.multi
    def _get_domain(self):
        country_id = self.env.user.company_id.country_id.id
        self.env.cr.execute('SELECT id FROM res_country_state WHERE country_id = {cid}'.format(cid=country_id))
        prov_ids = self.env.cr.fetchall()
        prov_ids = tuple([x[0] for x in prov_ids])
        return [('provincia_id', 'in', prov_ids)]

    date_from = fields.Date(string="Fecha Inicial", required=True, help='Fecha inicial de consulta, el informe retornará'
                            ' las Facturas o N.C. desde esta fecha.')
    date_to = fields.Date(string="Fecha Final", required=True, help='Fecha final de consulta, el informe retornará las '
                            'Facturas o N.C.hasta esta fecha.')
    period_id = fields.Many2one('account.period', 'Periodo')
    product_type = fields.Selection([('product', 'Almacenable'), ('consu', 'Consumible'),('service', 'Servicio')],
                                    string='Tipo de Producto')
    partner_ids = fields.Many2many('res.partner', string='Terceros', domain=[('customer', '=', True)],
                                   help='Tercero asociado a las Facturas/N.C. a consultar. Deje el campo vacío para Todos')
    munic_ids = fields.Many2many('res.city', string='Municipios', domain=_get_domain, help='Municipio donde se '
                                    'vendió o prestó el servicio. Deje el campo vacío para Todos')
    analy_ids = fields.Many2many('account.analytic.account', string='Cuentas Analíticas', help='Cuenta analítica donde '
                                       'se vendió o prestó el servicio. Deje el campo vacío para Todos')
    user_id = fields.Many2one('res.users', string='Usuario', help='Usuario que ejecuta la consulta.')
    inv_state = fields.Selection([('draft', 'Borrador'), ('open', 'Abierto(a)'), ('paid', 'Pagada'),
                                  ('cancel', 'Cancelado(a)')], string='Estado', help='Estado de la factura. Vació para todos')

    @api.one
    @api.constrains('date_from', 'date_to')
    def _validar_fechas(self):
        if self.date_from > self.date_to:
            raise Warning(_('Error en las fechas!'), _("Las fechas planificadas estan mal configuradas"))

    @api.multi
    def generar(self):
        dvalf = {}
        dvaln = {}
        tot_value_f, tot_iva_f, tot_auto_f = 0, 0, 0
        tot_value_n, tot_iva_n, tot_auto_n = 0, 0, 0

        self.env.cr.execute('SELECT count(*) FROM fpa_sale_munic_taxes_line')
        count = self.env.cr.fetchone()[0]
        # reporte
        financial_reports = self.env['fpa.financial.reports'].browse(self._context['active_id'])
        fin_id = financial_reports.id
        com_id = self.env.user.company_id.id
        use_id = self._uid

        # truncate a la tabla cuando sean mas de 1 millón de registros, para que no tarde tanto eliminando las lineas antes de crear las nuevas
        if count > 1000000:
            self.env.cr.execute('TRUNCATE fpa_sale_munic_taxes_line')
        else:
            self.env.cr.execute('DELETE FROM fpa_sale_munic_taxes_line WHERE financial_id = %s AND company_id = %s AND '
                                'user_id = %s' % (fin_id, com_id, use_id))

        self.env.cr.execute('DELETE FROM fpa_sale_munic_taxes WHERE financial_id = %s AND company_id = %s AND '
                            'user_id = %s' % (fin_id, com_id, use_id))

        estado = 'all' if not self.inv_state else self.inv_state
        # Agrega encabezado con parametros indicados por el usuario
        self.env.cr.execute("INSERT INTO fpa_sale_munic_taxes (date, date_from, date_to, company_id, user_id, "
                            "financial_id, estado) VALUES ('{date}', '{date_from}', '{date_to}', {company_id}, "
                            "{user_id}, {financial_id}, '{sta}') RETURNING ID".format(date=datetime.now(),
                                date_from=self.date_from, date_to=self.date_to,company_id=com_id,
                                user_id=use_id, financial_id=fin_id, sta=estado))
        try:
            header_id = self.env.cr.fetchone()[0]
        except ValueError:
            header_id = False

        #Facturas de Venta o NC
        inv_sale = ('out_refund', 'out_invoice')
        where = "ai.company_id = {cid} AND ai.date_invoice BETWEEN '{din}' AND '{dif}' AND ai.type in {typ}"\
                .format(cid=com_id, din=self.date_from, dif=self.date_to, typ=inv_sale)

        if self.partner_ids:
            if len(self.partner_ids.ids) > 1:
                where += " AND ai.partner_id IN {pid}".format(pid=tuple(self.partner_ids.ids))
            else:
                where += " AND ai.partner_id = {pid}".format(pid=self.partner_ids.ids[0])
        if self.munic_ids:
            if len(self.munic_ids.ids) > 1:
                where += " AND ai.munic_id IN {mid}".format(mid=tuple(self.munic_ids.ids))
            else:
                where += " AND ai.munic_id = {mid}".format(mid=self.munic_ids.ids[0])
        if self.period_id:
            where += " AND ai.period_id = {pi}".format(pi=self.period_id.id)
        if self.inv_state:
            where += " AND ai.state = '{sta}'".format(sta=self.inv_state)
        if self.analy_ids:
            if len(self.analy_ids.ids) > 1:
                where += " AND ail.account_analytic_id IN {aca}".format(aca=tuple(self.analy_ids.ids))
            else:
                where += " AND ail.account_analytic_id = {aca}".format(aca=self.analy_ids.ids[0])
        if self.product_type:
            where += " AND pt.type = '{typ}'".format(typ=self.product_type)

        sql = "SELECT ai.id,ai.date_invoice,ail.account_analytic_id,ai.munic_id,ai.munic_cod,ai.partner_id,rp.ref,ai.amount_total,ai.state,ai.type,pt.type " \
              "FROM account_invoice_line ail " \
              "INNER JOIN account_invoice ai ON ail.invoice_id = ai.id " \
              "INNER JOIN product_product pp ON ail.product_id = pp.id " \
              "INNER JOIN product_template pt ON pp.product_tmpl_id  = pt.id " \
              "INNER JOIN res_partner rp ON ail.partner_id  = rp.id " \
              "WHERE {wh}".format(wh=where)
        self.env.cr.execute(sql)
        lines = self.env.cr.fetchall()

        for l in lines:
            inv = self.env['account.invoice'].browse(l[0])
            invoice_tax = 0
            invoice_auto = 0
            for imp in inv.tax_line:
                if imp.amount > 0:
                    for rt in ['RETE', 'RTE', 'R/te']:
                        if rt in imp.name2:
                            invoice_auto += imp.amount
                    if 'IVA' in imp.name2:
                        invoice_tax += imp.amount
            prod_typ = l[-1]
            accion = 'serv' if prod_typ == 'service' else 'sale'
            mid = l[3]
            mco = l[4]
            if not mid:
                mid = "Null"
                mco = ''

            self.env.cr.execute("INSERT INTO fpa_sale_munic_taxes_line (invoice_id,invoice_date,analytic_acc_id,munic_id,"
                             "munic_cod,tipo_acc,partner_id,partner_nit,invoice_value,invoice_tax,invoice_auto,header_id,"
                             "tipo_doc,inv_state,financial_id,company_id,user_id) VALUES ({iid},'{idt}',{aid},{mid},'{mco}',"
                             "'{tac}',{pid},'{pni}',{ivl},{iva},{iau},{hid},'{tip}','{ist}',{fid},{cip},{uid})"
                             .format(iid=l[0],idt=l[1],aid=l[2],mid=mid,mco=mco,tac=accion,pid=l[5],pni=l[6],
                             ivl=l[7],iva=invoice_tax,iau=invoice_auto,hid=header_id,tip=l[9],ist=l[8],fid=fin_id,
                             cip=com_id,uid=use_id))
            kval = (l[0])
            if l[9] == 'out_invoice':
                if kval not in dvalf:
                    dvalf[kval] = [l[7], invoice_tax, invoice_auto]
            else:
                if kval not in dvaln:
                    dvaln[kval] = [l[7], invoice_tax, invoice_auto]

        for t in dvalf.values():
            tot_value_f += t[0]
            tot_iva_f += t[1]
            tot_auto_f += t[2]

        for t in dvaln.values():
            tot_value_n += t[0]
            tot_iva_n += t[1]
            tot_auto_n += t[2]

        self.env.cr.execute("UPDATE fpa_sale_munic_taxes SET (tot_value_f,tot_iva_f,tot_auto_f,tot_value_n,tot_iva_n,tot_auto_n)"
                            " = ({tv},{ti},{ta},{tvn},{tin},{tan}) WHERE "
                            "id = {id}".format(tv=tot_value_f,ti=tot_iva_f,ta=tot_auto_f,tvn=tot_value_n,tin=tot_iva_n,tan=tot_auto_n,id=header_id))

        return financial_reports.view_function(generate=False)
