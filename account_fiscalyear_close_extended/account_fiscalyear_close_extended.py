# -*- coding: utf-8 -*-
from openerp.osv import osv
from openerp.tools.translate import _
from openerp import models, fields, api
from openerp.exceptions import ValidationError, Warning
from datetime import datetime
import logging
import itertools

_logger = logging.getLogger('CIERRE FISCAL')


class account_period(models.Model):
    _inherit = "account.period"

    def action_draft(self, cr, uid, ids, context=None):
        mode = 'draft'

        group = self.pool.get('res.groups').search(cr, uid, [('name', '=', 'Ejecucion global - Cierre')],
                                                   context=context)
        group = self.pool.get('res.groups').browse(cr, uid, group, context=context)
        if not group:
            raise osv.except_osv(_("Error!"),
                                 _("Debe contar con un grupo de permisos con nombre 'Ejecucion global - Cierre'"))
        else:
            if not uid in [x.id for x in group.users]:
                raise osv.except_osv(_("Error!"), _(
                    "Debe pertenecer al grupo de permisos con nombre 'Ejecucion global - Cierre' para realizar este tipo de operacion."))

        for period in self.browse(cr, uid, ids):
            if period.fiscalyear_id.state == 'done':
                raise osv.except_osv(_('Warning!'),
                                     _('You can not re-open a period which belongs to closed fiscal year'))
        date = datetime.now()
        cr.execute("update account_journal_period set write_uid=%s, write_date=%s, state=%s where period_id in %s",
                   (uid, str(date), mode, tuple(ids),))
        cr.execute("update account_period set write_uid=%s, write_date=%s, state=%s where id in %s",
                   (uid, str(date), mode, tuple(ids),))
        self.invalidate_cache(cr, uid, context=context)
        return True


class account_period_close(models.TransientModel):
    _inherit = "account.period.close"

    # SE COPIA Y SOBREESCRIBE LA FUNCION DE addons/account/wizard/account_period_close
    def data_save(self, cr, uid, ids, context=None):
        account_move_obj = self.pool.get('account.move')
        account_move_line_obj = self.pool.get('account.move.line')
        account_invoice_obj = self.pool.get('account.invoice')
        mode = 'done'
        for form in self.read(cr, uid, ids, context=context):
            if form['sure']:
                for id in context['active_ids']:

                    # VALIDACIONES
                    group = self.pool.get('res.groups').search(cr, uid, [('name', '=', 'Ejecucion global - Cierre')],
                                                               context=context)
                    group = self.pool.get('res.groups').browse(cr, uid, group, context=context)
                    if not group:
                        raise osv.except_osv(_("Error!"), _(
                            "Debe contar con un grupo de permisos con nombre 'Ejecucion global - Cierre'"))
                    else:
                        if not uid in [x.id for x in group.users]:
                            raise osv.except_osv(_("Error!"), _(
                                "Debe pertenecer al grupo de permisos con nombre 'Ejecucion global - Cierre' para realizar este tipo de operacion."))

                    account_move_ids = account_move_obj.search(cr, uid,
                                                               [('period_id', '=', id), ('state', '!=', "posted")],
                                                               context=context)
                    if account_move_ids:
                        raise osv.except_osv(_('Accion Invalida!'), _(
                            'No es posible cerrar un periodo que contenga Asientos en estado NO ASENTADOS, por favor validar'))

                    account_move_line_ids = account_move_line_obj.search(cr, uid, [('period_id', '=', id),
                                                                                   ('state', '!=', "valid")],
                                                                         context=context)
                    if account_move_line_ids:
                        raise osv.except_osv(_('Accion Invalida!'), _(
                            'No es posible cerrar un periodo que contenga Movimientos en estado DESCUADRADO, por favor validar'))

                    invoice_ids = account_invoice_obj.search(cr, uid, [('period_id', '=', id), ('state', '=', "draft"),
                                                                       ('type', '=', "out_invoice")], context=context)
                    if invoice_ids:
                        raise osv.except_osv(_('Accion Invalida!'), _(
                            'No es posible cerrar un periodo que contenga Facturas de Venta en estado BORRADOR, por favor debe validar o cancelar estos documentos.'))

                    invoice_ids = account_invoice_obj.search(cr, uid, [('period_id', '=', id), ('state', '=', "draft"),
                                                                       ('type', '=', "out_refund")], context=context)
                    if invoice_ids:
                        raise osv.except_osv(_('Accion Invalida!'), _(
                            'No es posible cerrar un periodo que contenga Devolucion de Venta en estado BORRADOR, por favor debe validar o cancelar estos documentos.'))

                    invoice_ids = account_invoice_obj.search(cr, uid, [('period_id', '=', id), ('state', '=', "draft"),
                                                                       ('type', '=', "in_invoice")], context=context)
                    if invoice_ids:
                        raise osv.except_osv(_('Accion Invalida!'), _(
                            'No es posible cerrar un periodo que contenga Facturas de Compra en estado BORRADOR, por favor debe validar o cancelar estos documentos.'))

                    invoice_ids = account_invoice_obj.search(cr, uid, [('period_id', '=', id), ('state', '=', "draft"),
                                                                       ('type', '=', "in_refund")], context=context)
                    if invoice_ids:
                        raise osv.except_osv(_('Accion Invalida!'), _(
                            'No es posible cerrar un periodo que contenga Devolucion de Compra en estado BORRADOR, por favor debe validar o cancelar estos documentos.'))

                    date = datetime.now()
                    cr.execute('update account_period set write_uid=%s, write_date=%s,state=%s where id=%s',
                               (uid, str(date), mode, id))
                    self.invalidate_cache(cr, uid, context=context)
        return {'type': 'ir.actions.act_window_close'}


class res_company_extended(models.Model):
    _inherit = "res.company"

    account_pg_pyg_id = fields.Many2one(
        'account.account', string='Cuenta PYG Centralización')
    account_pg_pyg_niff_id = fields.Many2one(
        'account.account', string='Cuenta PYG NIIF Centralización')
    account_pg_perdida_niif_id = fields.Many2one(
        'account.account', string='Pérdida del Ejercicio NIIF')
    account_pg_ganancia_niif_id = fields.Many2one(
        'account.account', string='Ganancia del Ejercicio NIIF')


class account_journal_extended(models.Model):
    _inherit = "account.journal"

    account_pg_pyg_id = fields.Many2one(
        'account.account', string='Cuenta PYG Centralización')
    account_pg_pyg_niff_id = fields.Many2one(
        'account.account', string='Cuenta PYG NIIF Centralización')
    account_pg_perdida_niif_id = fields.Many2one(
        'account.account', string='Pérdida del Ejercicio NIIF')
    account_pg_ganancia_niif_id = fields.Many2one(
        'account.account', string='Ganancia del Ejercicio NIIF')


class account_fiscalyear_close(models.Model):
    _name = 'account.move.close'

    name = fields.Char(string='Nombre', readonly=True)
    state = fields.Selection([('draft', 'No Asentada'), ('done', 'Asentada'), ('cancel', 'Cancelado')], 'Estado')
    ref = fields.Char(string='Ref', readonly=True)
    period_id = fields.Many2one('account.period', 'Periodo', readonly=True)
    fy_id = fields.Many2one('account.fiscalyear', 'Anio Fiscal')
    date = fields.Date(string='Fecha', readonly=True)
    journal_id = fields.Many2one('account.journal', 'Diario', readonly=True)
    company_id = fields.Many2one('res.company', 'Compañia', readonly=True)
    account_move_id = fields.Many2one('account.move', 'Comprobante contable', readonly=True)
    line_ids = fields.One2many(
        'account.move.close.line', 'move_id', string='Lineas')

    @api.one
    def done(self):
        self.state = 'done'
        # Cierre
        cierre = self.env['account.fiscalyear.openperiod'].create({
            'fy_id': self.fy_id.id,
            # 'fy2_id':self.period_id.fiscalyear_id.id,
            'journal_id': self.journal_id.id,
            'period_id': self.period_id.id,
            'report_name': 'CIERRE'})
        return cierre.close_period_extended(definitivo=True)

    @api.one
    def cancel(self):
        self.state = 'cancel'
        self.move_id.button_cancel()
        return True

    @api.multi
    def export(self):
        pass


class account_fiscalyear_close_line(models.Model):
    _name = 'account.move.close.line'

    debit = fields.Float(digits=(32, 4), string="Débito", readonly=True)
    credit = fields.Float(digits=(32, 4), string="Crédito", readonly=True)
    saldo = fields.Float(digits=(32, 4), string="Saldo", readonly=True)
    name = fields.Char(string='Nombre', readonly=True, index=True)
    ref1 = fields.Char(string='Ref1', readonly=True, index=True)
    ref2 = fields.Char(string='Ref2', readonly=True, index=True)
    date = fields.Date(string='Fecha', readonly=True, index=True)
    date_maturity = fields.Date(string='Fecha de vencimiento', readonly=True)
    state = fields.Char(string='Estado', readonly=True)
    move_id = fields.Many2one(
        'account.move.close', string='Move', required=True, ondelete="cascade")
    journal_id = fields.Many2one('account.journal', 'Diario', readonly=True, index=True)
    partner_id = fields.Many2one('res.partner', 'Tercero', readonly=True, index=True)
    period_id = fields.Many2one('account.period', 'Periodo', readonly=True, index=True)
    account_id = fields.Many2one('account.account', 'Cuenta', readonly=True)
    account_niif_id = fields.Many2one('account.account', 'Cuenta NIIF', readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Cuenta Analítica', readonly=True)
    amount_currency = fields.Float(string="Monto moneda", readonly=True)
    company_id = fields.Many2one('res.company', 'Compañia', readonly=True, index=True)
    not_map = fields.Boolean(string='No mapear niif', default=False)


class account_fiscalyear_close_account(models.TransientModel):
    _name = 'account.fiscalyear.close.account'

    account_ids = fields.Many2many('account.account', domain="[('type','!=','view'),('debit','>',0),('credit','>',0)]",
                                   required=True, help="Seleccione las cuentas contables que necesite cerrar.")
    account_id = fields.Many2one('account.account', 'Cuenta destino', domain="[('type','!=','view')]", required=True,
                                 help="Seleccione la cuenta contable que llevará el saldo del cierre.")
    partner_id = fields.Many2one('res.partner', 'Tercero', required=True,
                                 help="Seleccione el tercero que estará asociado al movimiento contables del saldo.")
    journal_id = fields.Many2one('account.journal', 'Diario', required=True,
                                 help="Seleccione el diario con el que se va a realizar el asiento de cierre.")
    period_id = fields.Many2one('account.period', 'Periodo', required=True,
                                help="Seleccione el periodo con el que se va a realizar el asiento de cierre.")
    analytic_account_id = fields.Many2one('account.analytic.account', 'Cuenta analitica', required=False,
                                          help="Seleccione una cuenta analitica si necesita que el saldo este asociado a una cuenta analitic especifica.")
    date_maturity = fields.Date(string='Fecha de vencimiento',
                                help="Indique la fecha de vencimiento para el apunte contable del saldo.",
                                required=True)
    name = fields.Char(string='Descripción', required=True,
                       help="Indique la descripción con la que se va a realizar el asiento.")
    detail = fields.Boolean(string='Detalle', default=False,
                            help='Seleccione esta opción si desea realizar el cierre de las cuentas respetando el detalle por tercero.')
    partner = fields.Boolean(string='Por tercero', default=False,
                             help='Seleccione esta opción si desea cerras las cuentas por terceros.')
    date_from = fields.Date(string='Desde', required=True, help='Seleccione la fecha inicial')
    date_to = fields.Date(string='Hasta', required=True, help='Seleccione la fecha inicial')

    @api.multi
    def close_account(self):
        if self.partner:  # CIERRE DE CUENTAS Y TERCERO
            group = 'account_id, partner_id '
            field = group
        else:  # CIERRE DE CUENTAS
            group = ' account_id '
            field = group+', {partner_id} '.format(partner_id=self.partner_id.id)
        # crear asiento contable
        cop_id = self.env.user.company_id.id
        move_id = self.env['account.move'].create({'period_id': self.period_id.id,
                                   'name': str(self.name.encode('ascii', 'ignore').decode('ascii')),
                                   'state': str('draft'),
                                   'journal_id': self.journal_id.id,
                                   'date': self.period_id.date_stop})
        insert = "INSERT INTO account_move_line (debit, credit, account_id, partner_id, date, name, journal_id, " \
                 "move_id, period_id, date_maturity,create_uid,create_date,write_date,write_uid,company_id) " \
                                    "SELECT " \
                                        "(CASE WHEN sf<0 THEN -1*sf ELSE 0 END) as debit, " \
                                        "(CASE WHEN sf>0 THEN sf ELSE 0 END) as credit "
        where = ''' aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
        # cerrar cuentas
        self.env.cr.execute("{insert},{field},'{date}','{name}',{journal_id},{move_id},{period_id},'{date_maturity}', "
                            "{cid},'{cdt}','{wdt}',{wid},{cop}"
                            "FROM "
                                "(SELECT SUM(aml.debit-aml.credit) as sf, {field} FROM account_move_line aml WHERE {where} "
                                "AND aml.state = 'valid' AND aml.company_id = {company_id} "
                                "AND aml.date BETWEEN '{date_from}' AND '{date_to}' "
                                "GROUP BY {group} HAVING SUM(aml.debit-aml.credit) != 0) AS A".format(
            company_id=cop_id, date_from=self.date_from, date_to=self.date_to,
            where=where, date=self.period_id.date_stop, name=self.name, journal_id=self.journal_id.id,
            period_id=self.period_id.id, date_maturity=self.date_maturity, group=group, field=field, insert=insert,
            move_id=move_id.id, cid=self._uid, cdt=datetime.now(), wdt=datetime.now(), wid=self._uid, cop=cop_id))

        # contrapartida
        where = ''' aml.move_id = {move_id} '''.format(move_id=move_id.id)
        self.env.cr.execute("{insert}, {account_id},{partner_id},'{date}','{name}',{journal_id},{move_id},{period_id},"
                            "'{date_maturity}',{cid},'{cdt}','{wdt}',{wid},{cop}"
                            "FROM (SELECT SUM(aml.debit-aml.credit) as sf FROM account_move_line aml "
                                "WHERE {where}) AS A".format(company_id=self.env.user.company_id.id, date_from=self.date_from,
                 date_to=self.date_to,where=where, date=self.period_id.date_stop, name=self.name, journal_id=self.journal_id.id,
                 partner_id=self.partner_id.id, account_id=self.account_id.id, period_id=self.period_id.id,
                 date_maturity=self.date_maturity, insert=insert, move_id=move_id.id, cid=self._uid, cdt=datetime.now(),
                 wdt=datetime.now(), wid=self._uid, cop=cop_id))
        #asentar comprobantes
        self.env.cr.execute("UPDATE account_move SET state = 'posted', company_id = {cid} WHERE id = {move_id}"
                            .format(move_id=move_id.id, cid=cop_id))
        self.env.cr.execute("UPDATE account_move_line SET state = 'valid', company_id = {cid} WHERE move_id = {move_id}"
                            .format(move_id=move_id.id, cid=cop_id))
        return {
            'domain': [('id', 'in', [move_id.id])],
            'name': 'Asiento de cierre',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'account.move',
            'type': 'ir.actions.act_window'
        }


class account_fiscalyear_close_wiz(models.TransientModel):
    _name = "account.fiscalyear.openperiod"

    @api.multi
    def _get_company_config(self):
        return self.env['res.users'].browse(self._uid).company_id.config_analytic_global

    fy_id = fields.Many2one('account.fiscalyear', 'Año fiscal a cerrar', required=True,
                            help="Seleccione el año fiscal a cerrar")
    # fy2_id = fields.Many2one('account.fiscalyear', 'Nuevo año fiscal', required=True)
    journal_id = fields.Many2one('account.journal', 'Diario de cierre', domain="[('type','=','situation')]",
                                 required=True,
                                 help='The best practice here is to use a journal dedicated to contain the opening entries of all fiscal years. Note that you should define it with default debit/credit accounts, of type \'situation\' and with a centralized counterpart.')
    journal_niif_id = fields.Many2one('account.journal', 'Diario de cierre (NIIF)',
                                      domain="[('type','=','situation'),('niif','=',True)]", required=False,
                                      help='The best practice here is to use a journal dedicated to contain the opening entries of all fiscal years. Note that you should define it with default debit/credit accounts, of type \'situation\' and with a centralized counterpart.')
    period_id = fields.Many2one('account.period', 'Periodo de cierre', required=True)
    report_name = fields.Char('Nombre del asiento', required=True, help="Give name of the new entries",
                              default='CIERRE', readonly=True)
    glob_analytic = fields.Boolean(string='Contabilidad Analítica Global', default=_get_company_config)
    analytic_id = fields.Many2one('account.analytic.account', 'Cuenta Analítica',
                                  help="Cuenta analítica para las líneas de CIERRE y RESULTADO")

    # ASIENTO DE CIERRE
    @api.one
    def close_period_extended(self, definitivo):
        orm2sql = self.env['avancys.orm2sql']
        start = datetime.now()
        company_id = self.env.user.company_id.id

        ###Movimientos en Borrados
        self.env.cr.execute(
            "SELECT count(*) FROM account_move WHERE state='draft' AND date BETWEEN '%s' AND '%s' AND company_id = %s " % (
                self.fy_id.date_start, self.fy_id.date_stop, self.journal_id.company_id.id))
        count = self.env.cr.fetchone()
        if count:
            if count[0] > 0:
                raise Warning(
                    "Existen movimientos contables en borrador, por favor elimine o asiente los comprobantes para poder ejecutar el proceso")

        ###Lineas en borrador
        self.env.cr.execute(
            "SELECT count(*) FROM account_move_line WHERE state='draft' AND date BETWEEN '{date_start}' AND '{date_stop}' AND company_id = {company_id} ".format(
                date_start=self.fy_id.date_start, date_stop=self.fy_id.date_stop,
                company_id=company_id))
        count = self.env.cr.fetchone()
        if count:
            if count[0] > 0:
                raise Warning(
                    "Existen movimientos (lineas) contables en borrador, por favor elimine o asiente los comprobantes para poder ejecutar el proceso")

        chart_account = self.env['account.account'].search([('parent_zero', '=', None)])
        if definitivo != True:
            definitivo = False

        if not definitivo:
            modelo = 'account_move_close'
            modelo_line = 'account_move_close_line'
            state = 'draft'
            statel = state
            self.env.cr.execute(" DELETE FROM " + modelo + " WHERE company_id = {company_id} and period_id ={period_id}".format(
                    company_id=company_id, period_id=self.period_id.id))
            self.env.cr.execute(" DELETE FROM " + modelo_line + " WHERE company_id = {company_id} and period_id ={period_id}".format(
                            company_id=company_id, period_id=self.period_id.id))
        else:
            modelo = "account_move"
            state = 'posted'
            statel = 'valid'
            modelo_line = 'account_move_line'

        for chart_account_id in chart_account:
            ultima_fecha = datetime.strptime(self.period_id.date_start, '%Y-%m-%d')
            account_niif = 'NULL'

            if chart_account_id.niif:
                name = self.report_name + ' NIIF ' + self.fy_id.name
                journal = self.journal_niif_id
                partner_id = self.journal_niif_id.company_id.partner_id.id
                account_fiscal = 'aml.account_niif_id'
                account_fiscal2 = 'anl.account_niif_id'
                account_niif = 'account_niif_id'
                condition = " COALESCE(aml.account_niif_id, aml.account_id) = aa.id AND aa.niif is TRUE  "
                condition2 = "COALESCE(anl.account_niif_id, anl.general_account_id) = aa.id AND aa.niif is TRUE"
            else:
                name = self.report_name + ' FISCAL ' + self.fy_id.name
                condition = " aml.account_id = aa.id "
                condition2 = " anl.general_account_id = aa.id"
                account_fiscal = 'aml.account_id'
                account_fiscal2 = 'anl.general_account_id'
                journal = self.journal_id
                partner_id = self.journal_id.company_id.partner_id.id

            # crea movimiento de cierre
            move_vals = {
                'period_id': self.period_id.id,
                'journal_id': journal.id,
                'date': str(ultima_fecha.date()),
                'ref': '',
                'name': name,
                'state': state,
            }
            move_id = orm2sql.sqlcreate(self._uid, self._cr, modelo, [move_vals], company=True)[0][0]

            # Gastos + Costos // Ingreso
            for typ in ['expense', 'income']:
                tipos = 'GASTOS' if typ == 'expense' else 'INGRESOS'
                sql = " INSERT INTO " + modelo_line + " (debit, credit, name, date, move_id, journal_id, period_id, account_id, " \
                      " amount_currency, company_id, state, partner_id, account_niif_id, not_map) " \
                      " SELECT * FROM (SELECT (CASE WHEN SUM(aml.credit-aml.debit)>0 THEN SUM(aml.credit-aml.debit)::numeric " \
                      "ELSE 0 END) as debit, (CASE WHEN SUM(aml.debit-aml.credit)>0 THEN SUM(aml.debit-aml.credit)::numeric " \
                      "ELSE 0 END) as credit, '{tipos}', '{ultima_fecha}'::date,{move_id},{journal},{period_id}, {account_fiscal}, " \
                      "round(sum(aml.amount_currency),4) as amount_currency, {company_id}, '{statel}', aml.partner_id, " \
                      "{account_niif}::integer, True FROM account_move_line aml inner join " \
                      "account_account aa on {condition} inner join account_account_type aat on aat.id = aa.user_type " \
                      "and aat.report_type = '{typ}' and close_method = 'none' inner join account_period ap on " \
                      "ap.id = aml.period_id and ap.special IS FALSE WHERE aml.company_id = {company_id} " \
                      " and ((aml.date >= '{date_start}'::date and aml.date <= '{date_stop}'::date)) " \
                      " and aa.parent_zero = {chart_account_id} group by aml.account_id, aml.account_niif_id, " \
                      "aml.currency_id, aml.company_id, aml.partner_id) as tipo " \
                      " WHERE tipo.debit>0 or tipo.credit>0".format(
                        ultima_fecha=ultima_fecha, move_id=move_id, journal=journal.id, period_id=self.period_id.id,
                        company_id=company_id, account_fiscal=account_fiscal, statel=statel,
                        account_niif=account_niif, condition=condition, date_start=self.fy_id.date_start,
                        date_stop=self.fy_id.date_stop, chart_account_id=chart_account_id.id, typ=typ, tipos=tipos)
                self.env.cr.execute(sql)

            self.env.cr.execute(
                " SELECT name, round(sum(debit)::numeric,4) as debit, round(sum(credit)::numeric,4) as credit"
                " FROM " + modelo_line + " where move_id ={move_id} GROUP BY name".format(
                    move_id=move_id))
            move_line_id = self.env.cr.fetchall()

            #Centralizado
            if chart_account_id.niif:
                cuentapyg = self.journal_niif_id.account_pg_pyg_niff_id.id or self.journal_niif_id.company_id.account_pg_pyg_niff_id.id
            else:
                cuentapyg = self.journal_id.account_pg_pyg_id.id or self.journal_id.company_id.account_pg_pyg_id.id
            if not cuentapyg:
                raise Warning(('Configuración'), (
                    "Se debe configurar la cuenta de ganancias y perdidas (Cierre) en el diario o compañía."))
            for line in move_line_id:
                saldo = float(line[1]) - float(line[2])
                typ = 'expense' if line[0] == 'GASTOS' else 'income'
                if saldo > 0:
                    sql = "INSERT INTO " + modelo_line + " (debit, credit, name, date, move_id, journal_id, period_id, account_id, " \
                            " company_id, state, partner_id, not_map, account_niif_id) " \
                            "VALUES (0,{saldo},'{name}','{ultima_fecha}',{move_id}," \
                            "{journal},{period_id},{cuentapyg},{company_id},'{statel}'," \
                            "{partner_id}, True, {account_niif}) RETURNING id".format(
                            saldo=repr(saldo), ultima_fecha=ultima_fecha, move_id=move_id, journal=journal.id,
                            period_id=self.period_id.id, cuentapyg=cuentapyg, company_id=company_id,
                            statel=statel, partner_id=partner_id, account_niif=cuentapyg, name='CENTRALIZADO ' + line[0])
                    self.env.cr.execute(sql)
                    mv_cent_id = self.env.cr.fetchone()[0]

                    if definitivo and self.glob_analytic:
                        for sing in ['>', '<']:
                            sql = " INSERT INTO account_analytic_line (amount, name, date, move_id, period_id, journal_id, account_id," \
                                  " amount_currency, company_id, partner_id, general_account_id, account_niif_id) " \
                                  "SELECT -1*amount as amt,tipos,date,mov,pid,journal_id,account_id,amount_currency,cpn,partner_id,acc_fisc,account_niif_id " \
                                  "FROM (SELECT (SUM(amount)) AS amount, '{tipos}' as tipos, " \
                                  "'{ultima_fecha}'::date,{move_id} as mov,{pid} as pid,anl.journal_id,anl.account_id, " \
                                  "round(sum(anl.amount_currency),4) as amount_currency,{company_id} as cpn, anl.partner_id, {acc_fisc} as acc_fisc,anl.account_niif_id " \
                                  "FROM account_analytic_line anl INNER JOIN" \
                                  " account_account aa ON {condition} INNER JOIN account_account_type aat ON aat.id = aa.user_type " \
                                  "AND aat.report_type = '{typ}' AND close_method = 'none' INNER JOIN account_period ap ON " \
                                  "ap.id = anl.period_id AND ap.special IS FALSE WHERE anl.company_id = {company_id} " \
                                  "AND ((anl.date >= '{date_start}'::date AND anl.date <= '{date_stop}'::date)) " \
                                  "AND aa.parent_zero = {chart_account_id} GROUP BY anl.account_id, " \
                                  "anl.company_id, anl.partner_id, {acc_fisc}, anl.journal_id,anl.account_niif_id) AS tipo " \
                                  "WHERE tipo.amount {sing} 0".format(acc_fisc=account_fiscal2,
                                    ultima_fecha=ultima_fecha, move_id=mv_cent_id, pid=self.period_id.id, sing=sing,
                                    company_id=company_id, condition=condition2, date_start=self.fy_id.date_start,
                                    date_stop=self.fy_id.date_stop, chart_account_id=chart_account_id.id, typ=typ, tipos='CENTRALIZADO ' + line[0])
                            self.env.cr.execute(sql)

                if saldo < 0:
                    sql = "INSERT INTO " + modelo_line + " (debit, credit, name, date, move_id, journal_id, period_id, account_id," \
                                "company_id, state, partner_id, not_map,account_niif_id) " \
                                "VALUES ({saldo}, 0, '{name}','{ultima_fecha}',{move_id},{journal}," \
                                "{period_id},{cuentapyg},{company_id},'{statel}',{partner_id}, True," \
                                "{account_niif}) RETURNING id".format( saldo=repr(abs(saldo)),
                                line=line[0], ultima_fecha=ultima_fecha, move_id=move_id, journal=journal.id, period_id=self.period_id.id,
                                cuentapyg=cuentapyg, company_id=company_id, statel=statel, partner_id=partner_id,
                                name='CENTRALIZADO ' + line[0], account_niif=cuentapyg)
                    self.env.cr.execute(sql)
                    mv_cent_id = self.env.cr.fetchone()[0]

                    if definitivo and self.glob_analytic:
                        for sing in ['>', '<']:
                            sql = " INSERT INTO account_analytic_line (amount, name, date, move_id, period_id, journal_id, account_id," \
                                  " amount_currency, company_id, partner_id, general_account_id, account_niif_id) " \
                                  "SELECT -1*amount as amt,tipos,date,mov,pid,journal_id,account_id,amount_currency,cpn,partner_id,acc_fisc,account_niif_id " \
                                  "FROM (SELECT (SUM(amount)) AS amount, '{tipos}' as tipos, " \
                                  "'{ultima_fecha}'::date,{move_id} as mov,{pid} as pid,anl.journal_id,anl.account_id, " \
                                  "round(sum(anl.amount_currency),4) as amount_currency,{company_id} as cpn, anl.partner_id, {acc_fisc} as acc_fisc,anl.account_niif_id " \
                                  "FROM account_analytic_line anl INNER JOIN" \
                                  " account_account aa ON {condition} INNER JOIN account_account_type aat ON aat.id = aa.user_type " \
                                  "AND aat.report_type = '{typ}' AND close_method = 'none' INNER JOIN account_period ap ON " \
                                  "ap.id = anl.period_id AND ap.special IS FALSE WHERE anl.company_id = {company_id} " \
                                  "AND ((anl.date >= '{date_start}'::date AND anl.date <= '{date_stop}'::date)) " \
                                  "AND aa.parent_zero = {chart_account_id} GROUP BY anl.account_id, " \
                                  "anl.company_id, anl.partner_id, {acc_fisc}, anl.journal_id,anl.account_niif_id) AS tipo " \
                                  "WHERE tipo.amount {sing} 0".format(acc_fisc=account_fiscal2,
                                      ultima_fecha=ultima_fecha, move_id=mv_cent_id, pid=self.period_id.id, sing=sing,
                                      company_id=company_id, condition=condition2, date_start=self.fy_id.date_start,
                                      date_stop=self.fy_id.date_stop, chart_account_id=chart_account_id.id, typ=typ, tipos='CENTRALIZADO ' + line[0])
                            self.env.cr.execute(sql)

            # Utilidad del Ejercicio
            debit = 0
            credit = 0
            self.env.cr.execute(
                " SELECT sum(debit) - sum(credit) as credit FROM " + modelo_line + " where name like 'CENTRALIZADO%' AND move_id ={move_id}".format(
                    move_id=move_id))
            utilidad = self.env.cr.fetchone()
            saldo = utilidad[0]

            if saldo > 0:
                debit = saldo
                if chart_account_id.niif:
                    cuenta = self.journal_niif_id.account_pg_perdida_niif_id.id or self.journal_niif_id.company_id.account_pg_perdida_niif_id.id
                    cuenta_niif = cuenta
                else:
                    cuenta = self.journal_id.loss_account_id.id or self.journal_id.company_id.account_pg_perdida_id.id
                    self._cr.execute(
                        " SELECT child_id FROM account_account_consol_rel WHERE parent_id = {parent_id}".format(
                            parent_id=cuenta))
                    cuenta_niif = self._cr.fetchone()
                    if cuenta_niif:
                        cuenta_niif = cuenta_niif[0]
            else:
                credit = abs(saldo or 0.0) if saldo < 0 else 0
                if chart_account_id.niif:
                    cuenta = self.journal_niif_id.account_pg_ganancia_niif_id.id or self.journal_niif_id.company_id.account_pg_ganancia_niif_id.id
                    cuenta_niif = cuenta
                else:
                    cuenta = self.journal_id.profit_account_id.id or self.journal_id.company_id.account_pg_ganancia_id.id
                    self._cr.execute(
                        " SELECT child_id FROM account_account_consol_rel WHERE parent_id ={parent_id}".format(
                            parent_id=cuenta))
                    cuenta_niif = self._cr.fetchone()
                    if cuenta_niif:
                        cuenta_niif = cuenta_niif[0]
            if not cuenta:
                raise Warning(u'Se debe configurar la cuenta de Ganancias y Pérdidas (36) en el diario o compañía.')

            if not cuenta_niif and self.journal_niif_id and chart_account_id.niif:
                raise Warning(u'Se deben configurar las cuenta de Ganancias y Pérdidas NIIF (N36) consolidadas, por '
                              u'favor revise la parametrización en el diario %s o en la compañía, según corresponda' %
                              self.journal_id.name)

            if debit > 0 or credit > 0:
                #Resultado y cierre
                self.env.cr.execute(
                    " INSERT INTO " + modelo_line + " (debit, credit, name, date, move_id, journal_id, period_id, account_id, " \
                                                    " company_id, state, partner_id,account_niif_id, not_map) " \
                                                    " VALUES ({debit}, {credit}, 'RESULTADO', '{ultima_fecha}',{move_id},{journal}," \
                                                    "{period_id},{cuenta},{company_id},'{statel}',{partner_id},{cuenta_niif},True) RETURNING id".format(
                        debit=debit, credit=credit, ultima_fecha=ultima_fecha, move_id=move_id, journal=journal.id,
                        period_id=self.period_id.id, cuenta=cuenta,company_id=company_id, statel=statel,
                        partner_id=partner_id, cuenta_niif=cuenta_niif or 'NULL'))
                mv_res_id = self.env.cr.fetchone()[0]
                if definitivo and self.glob_analytic:
                    analy_journal = journal.analytic_journal_id.id
                    if not analy_journal:
                        raise Warning("Por favor asigne o cree un diario analítico para el diario {jou}".format(jou=journal.name))
                    self.env.cr.execute("SELECT id FROM account_analytic_account LIMIT 1")
                    analy_id = self.env.cr.fetchone()[0]
                    self.env.cr.execute("INSERT INTO account_analytic_line (amount, name, date, move_id, period_id, "
                                        "journal_id, account_id, company_id, partner_id, "
                                        "general_account_id, account_niif_id) VALUES ({amn},'RESULTADO','{dat}',{mid},{pid},"
                                        "{jid},{aci},{cip},{par},{gid},{acn})".format(amn=debit-credit, dat=ultima_fecha,
                                            mid=mv_res_id, pid=self.period_id.id, jid=analy_journal,
                                            aci=analy_id, cip=company_id, par=partner_id, gid=cuenta, acn=cuenta_niif or 'Null'))
                self.env.cr.execute(
                    " INSERT INTO " + modelo_line + " (credit,debit, name, date, move_id, journal_id, period_id, account_id, " \
                                                    " company_id, state, partner_id,account_niif_id, not_map) " \
                                                    " VALUES ({debit}, {credit}, 'CIERRE', '{ultima_fecha}',{move_id},{journal}," \
                                                    "{period_id},{cuenta},{company_id},'{statel}',{partner_id},{cuenta_niif},True)".format(
                        debit=debit, credit=credit, ultima_fecha=ultima_fecha, move_id=move_id, journal=journal.id,
                        period_id=self.period_id.id, cuenta=cuentapyg,company_id=company_id, statel=statel,
                        partner_id=partner_id, cuenta_niif=cuentapyg or 'NULL'))

            self.env.cr.execute(
                " DELETE FROM " + modelo_line + " WHERE move_id = {move_id} and debit = 0 and credit = 0 ".format(
                    move_id=move_id))
            obj_acc_journal_period = self.env['account.journal.period']
            ids = obj_acc_journal_period.search([('journal_id', '=', journal.id), ('period_id', '=', self.period_id.id)])
            if not ids:
                #Journal Periodo
                ids = obj_acc_journal_period.create({
                    'name': (self.journal_id.name or '') + ':' + (self.period_id.code or ''),
                    'journal_id': journal.id,
                    'period_id': self.period_id.id
                })
                self.fy_id.write({'end_journal_period_id': ids.id})

            if definitivo:
                if not chart_account_id.niif:
                    self.env.cr.execute("UPDATE account_move_line SET account_niif_id = Null WHERE move_id = {mid}".format(mid=move_id))
                    self.env.cr.execute("UPDATE account_analytic_line SET account_niif_id = Null WHERE move_id IN "
                                        "(SELECT id FROM account_move_line WHERE move_id = {mid})".format(mid=move_id))
                move = self.env['account.move.close'].search(
                    [('journal_id', '=', self.journal_id.id), ('name', '=', 'CIERRE' + name)], limit=1)
                move.write({'account_move_id': move_id})
                # create the journal.period object and link it to the old fiscalyear
                obj_acc_fiscalyear = self.env['account.fiscalyear']
                obj_acc_journal_period = self.env['account.journal.period']
                period = self.period_id
                new_period = self.period_id.id
                new_journal = self.journal_id
                old_fyear = self.fy_id
                ids = obj_acc_journal_period.search(
                    [('journal_id', '=', new_journal.id), ('period_id', '=', new_period)])
                if not ids:
                    ids = [obj_acc_journal_period.create(
                        {'name': (new_journal.name or '') + ':' + (period.code or ''), 'journal_id': new_journal.id,
                         'period_id': period.id})]
                self.env.cr.execute('UPDATE account_fiscalyear '
                                    'SET end_journal_period_id = {period_id} '
                                    'WHERE id = {id}'.format(period_id=ids[0].id, id=old_fyear.id))
                obj_acc_fiscalyear.invalidate_cache(['end_journal_period_id'], [old_fyear.id])

            if not definitivo:
                self.env.cr.execute(''' UPDATE account_move_close_line SET saldo = debit-credit ''')
            _logger.debug("Finalizo en: {time} ".format(time=str(datetime.now() - start)))
        return True


class account_fiscalyear_asentar(models.TransientModel):
    _name = 'account.fiscalyear.asentar'

    fy_id = fields.Many2one('account.fiscalyear', string='Año fiscal', required=True,
                            help="Año fiscal al cual desea realizar asentar los comprobantes de cierre")

    @api.one
    def asentar(self):
        # Cierre
        move_close = self.env['account.move.close'].search(
            [('date', '>=', self.fy_id.date_start), ('date', '<=', self.fy_id.date_stop), ('state', '=', 'draft')])
        journal_id = None
        journal_niif_id = 'No Aplica' if not self.env['account.account'].search([('niif', '=', True)], limit=1) else None
        period_id = None
        for move in move_close:
            if move.journal_id.niif:
                journal_niif_id = move.journal_id.id
            else:
                journal_id = move.journal_id.id
            move.state = 'done'
            period_id = move.period_id.id
        if not (journal_id and journal_niif_id and period_id):
            raise Warning("No hay movimientos contables para asentar en este año ")
        cierre = self.env['account.fiscalyear.openperiod'].create({
            'fy_id': self.fy_id.id,
            'journal_id': journal_id,
            'journal_niif_id': journal_niif_id if journal_niif_id != 'No Aplica' else None,
            'period_id': period_id,
            'report_name': 'CIERRE'})
        cierre.close_period_extended(definitivo=True)
        return True


class account_fiscalyear_close_state_extended(models.TransientModel):
    _inherit = "account.fiscalyear.close.state"

    seguro = fields.Boolean(string='¿Seguro?')
