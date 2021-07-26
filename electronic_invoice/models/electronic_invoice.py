# -*- coding: utf-8 -*-
import os
import re
import shutil
import paramiko
import zipfile
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

from openerp import models, fields, api
from openerp.addons import decimal_precision as dp
from openerp.addons.avancys_tools import report_tools
from openerp.tools import config
from openerp.exceptions import Warning
from itertools import groupby
from contextlib import contextmanager

class EiOrderLog(models.Model):
    _name = 'ei.order.log'
    _inherit = 'mail.thread'
    _order = 'transaction_date desc'

    name = fields.Char('Referencia', readonly=True, help='Numero de referencia del archivo')
    transaction_date = fields.Datetime('Fecha de la Transacción', readonly=True, help='Fecha de la Transacción')
    name_file = fields.Char('Nombre del Archivo', readonly=True, help="Nombre del Archivo")
    type_log = fields.Selection([('txt', 'Archivo Txt'), ('xml', 'Archivo Xml'), ('logxml', 'Log XML'),
                                 ('logpdf', 'Log PDF'), ('loghost', 'Error de Conexion'), ('cancel', 'Cancelado'),
                                 ('param', 'Parametrización'), ('none', 'No Aplica')],
                                string='Tipo Registro', readonly=True)
    type_doc = fields.Selection([('lg', 'Log Error'), ('ad', 'Adjunto'), ('rn', 'Aviso de Recibo'),
                                 ('nc', 'Nota Crédito'), ('nd', 'Nota Débito'), ('ei', 'Factura Electronica'),
                                 ('dr', 'Rechazado DIAN'), ('da', 'Aceptado DIAN'), ('ak', 'Acuse de Recibo'),
                                 ('ds', 'Aceptación/Rechazo')], string='Tipo Documento', readonly=True)
    description = fields.Text('Descripción', readonly=True, required=True)
    data = fields.Text('Contenido', readonly=True)
    state = fields.Selection([('open', 'Abierto'), ('close', 'Cerrado')], string='Estado', track_visibility='onchange',
                             readonly=True)
    document_state = fields.Selection([('pending', 'No Transferido'), ('done', 'Emitido'),
                                       ('supplier_rejec', 'Rechazado PT'), ('supplier_accep', 'Aceptado PT'),
                                       ('dian_rejec', 'Rechazado DIAN'), ('dian_accep', 'Aceptado DIAN'),
                                       ('ack_cus', 'Recibido Cliente'), ('cus_rejec', 'Rechazado Cliente'),
                                       ('cus_accep', 'Aceptado Cliente')], string='Estado Documento', readonly=True)
    invoice_id = fields.Many2one('account.invoice', 'Factura', readonly=True)
    picking_id = fields.Many2one('stock.picking', 'Remision', readonly=True)

    @api.multi  # TODO
    def chg_state(self):
        self.state = 'close' if self.state == 'open' else 'open'


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.multi
    def _get_nov_loc(self):
        nov_loc = self.env['stock.location'].search([('name', '=', 'Novedades Factura Electrónica')])
        return nov_loc

    # @api.multi
    # def _get_database_list(self):
    #     self._cr.execute("SELECT d.datname FROM pg_catalog.pg_database d WHERE "
    #                      "pg_catalog.pg_get_userbyid(d.datdba)='%s' ORDER BY datname;" %
    #                      filter(lambda x: 'user' in x, self._cr._cnx.dsn.rsplit(' '))[0].replace(' ', '')[5:])
    #     db_lst = []
    #     for db in self._cr.fetchall():
    #         db_lst.append((db[0], db[0]))
    #     return db_lst

    electronic_invoice = fields.Boolean('Gestión de Factura Electrónica', help='POLÍTICA A NIVEL DE COMPAÑÍA, '
                                        'AFECTACIÓN EN PROCESOS DE FACTURACIÓN. Marque esta casilla si quiere '
                                        'habilitar la Facturación Electrónica.', default=True)
    ei_database = fields.Char(string='Base de Datos', default=lambda self: self.env.cr.dbname,
                              required=True, help='Base de Datos en la cual funcionará la Facturación Electrónica')
    ei_server_type = fields.Selection([('production', u'Producción'), ('test', 'Pruebas')],
                                      string='Ambiente', default='test', required=True,
                                      help='Indicador del tipo de ambiente de Facturación Electrónica que se usará en '
                                           'esta Base de Datos')
    ei_automatic_gen = fields.Boolean('Tarea Automática Generación', help='Marque este check si quiere permitir la '
                                      'ejecución de la tarea automática de generación de Factura Electrónica para '
                                      'aquellas Facturas/Notas Crédito-Débito que apliquen.', default=True)
    ei_automatic_read = fields.Boolean('Tarea Automática Lectura', help='Marque este check si quiere permitir la '
                                       'ejecución de la tarea automática de lectura de archivos relacionados a la '
                                       'Factura Electrónica.', default=True)
    # Servidor
    sftp_url = fields.Char('Dirección', size=25, help='Dirección IP servidor Facturación Electrónica')
    sftp_port = fields.Char('Puerto', size=4, help='Puerto para conexión SFTP en servidor de Facturación Electrónica')
    sftp_user = fields.Char('Usuario', size=25, help='Usuario para conexión SFTP en servidor de Facturación '
                                                     'Electrónica')
    sftp_pwd = fields.Char('Contraseña', size=20, help='Contraseña para conexión SFTP en servidor de Facturación '
                                                       'Electrónica')
    ei_temporal_files = fields.Char('Dirección local transferencia', help='Directorio temporal de transferencia de '
                                                                          'archivos en el servidor local')
    # XML Factura
    ei_write_folder = fields.Char('Escritura Archivos', help='Carpeta salida de archivos necesarios para la '
                                                             'generación de la Factura Electrónica')
    ei_error_folder = fields.Char('Lectura Erróneos', help='Carpeta entrada de archivos error de documentos de '
                                                           'generación de la Factura Electrónica')
    ei_voucher_folder = fields.Char('Lectura Comprobantes', help='Carpeta entrada de comprobantes de Facturación '
                                    'Electrónica necesarios para validar el Documento del sistema')
    ei_dian_result_folder = fields.Char('Lectura Resultado DIAN', help='Carpeta entrada de resultado de validaciones '
                                                                        'realizadas por la DIAN')
    ei_ack_folder = fields.Char('Lectura Acuse Recibo', help='Carpeta entrada de archivos de Acuse Recibo de la '
                                                             'Factura Electrónica del cliente')
    ei_decision_folder = fields.Char('Lectura Aceptación/Rechazo', help='Carpeta entrada de archivos de Aceptación/'
                                                                        'Rechazo de la Factura Electrónica del cliente')
    xml_automatic_generation = fields.Boolean('Generación Automática XML', help='POLÍTICA A NIVEL DE COMPAÑÍA, '
                                              'AFECTACIÓN EN EL PROCESO DE GENERACIÓN DEL XML DE FACTURACIÓN '
                                              'ELECTRÓNICA. Marque esta casilla si quiere que el xml de factura '
                                              'electrónica se genere automáticamente al validar las facturas. '
                                              'Este proceso de generación es independiente al de validación de la '
                                              'factura.')
    send_cus_po = fields.Boolean('Envío OC Cliente', help='Marque esta casilla si quiere permitir el envío del archivo '
                                                          'de órden de compra del cliente, adjunto en el XML de FE')
    send_remission = fields.Boolean('Envío Remisión', help='Marque esta casilla si quiere permitir el envío del '
                                                           'archivo de Remisíon, adjunto en el XML de FE')
    send_cus_att = fields.Boolean('Envío Adjuntos Factura', help='Marque esta casilla si quiere permitir el envío de '
                                        'archivos adjunto de FE desde la vista formulario de las Facturas de Venta y '
                                        'Notas Crédito/Débito de Cliente')
    cts_one_xml = fields.Char('CTS_1', size=20, help='Diligencie este campo según los códigos pactados con Carvajal.'
                                                     'Primero indique el código cuando la factura es NACIONAL, después '
                                                     'separado por el caracter | y sin dejar espacios indique el '
                                                     'código cuando la factura es de EXPORTACIÓN')
    ei_operation_type = fields.Selection([('01', 'Combustibles'), ('02', 'Emisor es Autorretenedor'),
                                          ('03', 'Excluidos y Exentos'), ('04', 'Exportación'), ('05', 'Genérica'),
                                          ('06', 'Genérica con pago anticipado'), ('07', 'Genérica con periodo de facturación'),
                                          ('08', 'Consorcio'), ('09', 'Servicios AIU'), ('10', 'Estandar'),
                                          ('11', 'Mandatos bienes'), ('12', 'Mandatos servicios')],
                                         string='Operación Principal', required=True, default='05',
                                         help='Tipo de Operación principal de la compañía, información necesaria para '
                                              'campo ENC_21 en XML de Facturación Electrónica')
    attach_invoice_xml = fields.Boolean('Adjuntar XML Facturación', help='Marque esta casilla para adjuntar en el '
                                        'documento factura del sistema, la representación en formato XML de la Factura '
                                        'Electrónica.', default=True)
    ubl_upgrade_date = fields.Datetime(string='Fecha de actualuzación')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    electronic_invoice = fields.Boolean('Factura Electrónica', help="Gestión de Factura Electrónica")
    ei_partner_address = fields.Selection([('default', 'Cliente'), ('invoice', 'Direccion Factura'),
                                           ('delivery', 'Direccion Entrega')], string='Direccion',
                                          default='default')

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(ResPartner, self).fields_view_get(
                view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            if not self.env.user.company_id.electronic_invoice and 'nica" invisible="1" modifiers="{&quot;invisible&' \
                                                                   'quot;: true}"' not in res['arch']:
                    res['arch'] = res['arch'].replace('Electr&#243;nica"', 'Electr&#243;nica" invisible="1" modifiers='
                                                                           '"{&quot;invisible&quot;: true}" ')
        return res

    @api.model
    def create(self, vals):
        if vals.get('type', False) == 'delivery' and (len(vals.get('street', '')) > 100 or
                                                      len(vals.get('name', '')) > 100):
            nmn_len, str_len = len(vals['name']), len(vals['street'])
            msg = u'los campos Nombre y Dirección' if nmn_len > 100 and str_len > 100 else 'el campo Nombre' \
                if nmn_len > 100 else u'el campo Dirección'
            raise Warning(u"Por favor ajustar %s de la dirección de entrega:\n- %s.\n\n"
                          u"Su longitud no debe superar 100 caracteres." % (msg, vals.get('name', '')))
        res = super(ResPartner, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        if 'street' in vals or 'name' in vals:
            partners = self.filtered(lambda x: x.type == 'delivery' and (len(x.street) > 100 or len(x.name) > 100))
            if partners:
                msg = 'las direcciones' if len(partners) > 1 else u'la dirección'
                partners = '\n'.join('- %s' % p.name for p in partners)
                raise Warning(u"Por favor revisar los campos Nombre y Dirección de %s de entrega:\n%s\n\n "
                              u"Su longitud no debe superar 100 caracteres." % (msg, partners))
        return res


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    customer_po = fields.Binary('OC Cliente', help='Archivo órden de compra cliente', copy=False)
    cus_po_name = fields.Char('Nombre OC Cliente', copy=False)
    pol_send_cus_po = fields.Boolean('Política Envío OC', related='company_id.send_cus_po', readonly=True)

    @api.multi
    def write(self, vals):
        if 'customer_po' in vals and vals['customer_po']:
            self.env['account.invoice']._check_file_size(vals['cus_po_name'], vals['customer_po'])
        return super(SaleOrder, self).write(vals)

    @api.model
    def create(self, vals):
        if 'customer_po' in vals and vals['customer_po']:
            self.env['account.invoice']._check_file_size(vals['cus_po_name'], vals['customer_po'])
        return super(SaleOrder, self).create(vals)


class ProductUom(models.Model):
    _inherit = 'product.uom'

    ei_uom_code = fields.Char('Código FE', help="Codigo de Unidad de Medida para Facturación Electronica.")


class AccountTaxCode(models.Model):
    _inherit = 'account.tax.code'

    ei_code = fields.Char('Codigo Factura Electronica', help="Codigo de Impuesto para Facturación Electrónica")


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    invoice_resolution = fields.Char('Número de Resolución', help="Número de Resolución para Factura Electrónica")
    invoice_prefix = fields.Char('Prefijo de Factura', help="Prefijo de Factura")
    ei_start_invoice = fields.Integer('Número Inicio de Factura', help="Número de Inicio de Facturación según "
                                                                       "Resolución para Facturación Electrónica")
    ei_end_invoice = fields.Integer('Número Fin de Factura', help="Número de Fin de Facturación según Resolución "
                                                                  "para Facturación Electrónica")
    ei_start_date = fields.Date('Fecha Inicio Resolución', help="Fecha Inicio de Resolución")
    ei_end_date = fields.Date('Fecha Fin Resolución', help="Fecha Fin de Resolución")
    ei_payment_method = fields.Integer(u'Método de Pago', size=2, default=30,
                                       help='Método de Pago especificado por el intermediario para '
                                            'Facturación Electrónica. Ver Tabla 5 en esquema de Diseño. '
                                            'Por defecto se lleva 30, equivalente a Transferencia Crédito')
    not_one_xml = fields.Text('NOT_1', help='Digite el mensaje que llevara la nota principal del campo NOT del XML')
    not_five_xml = fields.Text('NOT_5', help='Mensaje ejemplo -- LA PRESENTE FACTURA DE VENTA SE ASIMILA EN TODOS '
                                             'SUS ASPECTOS...')


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    @api.model
    def create(self, vals):
        if 'name' in vals and len(vals['name'] or '') > 35:
            raise Warning(u"El Lote '{}' no cumple con la longitud máxima permitida para facturación electrónica."
                          u"\n\nLongitud enviada {}\nLongitud permitida 35"
                          .format(vals['name'], len(vals['name'])))
        res = super(StockProductionLot, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        if 'name' in vals and len(vals['name'] or '') > 35:
            raise Warning(u"El Lote '{}' no cumple con la longitud máxima permitida para facturación electrónica."
                          u"\n\nLongitud enviada {}\nLongitud permitida 35"
                          .format(vals['name'], len(vals['name'])))
        res = super(StockProductionLot, self).write(vals)
        return res


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @contextmanager
    def sftp_connection(self, cp, msg, folder):
        sftp, transport = self._sftp_connect(cp, msg, folder)
        try:
            yield (sftp, transport)
        finally:
            sftp.close()
            transport.close()

    @api.multi
    def _sftp_connect(self, cp, msg, folder):
        try:
            os.chdir(cp.ei_temporal_files)
        except (IOError, OSError):
            dct = u"Error en conexión a Ruta temporal de escritura, '%s'. Revisar parametrización en compañía y " \
                  u"existencia en Servidor Local" % cp.ei_temporal_files
            self._create_ei_order_log(self, '', 'loghost', '', dct, '', 'open', self.ei_state if self else '')
            return
        r_host = cp.sftp_url
        r_user = cp.sftp_user
        r_pwd = cp.sftp_pwd
        r_port = int(cp.sftp_port)
        # noinspection PyTypeChecker
        transport = paramiko.Transport((r_host, r_port))
        try:
            transport.connect(username=r_user, password=r_pwd)
        except paramiko.AuthenticationException:
            raise Warning('Error de Autenticación en conexión a servidor de Factura Electrónica, por favor '
                          'validar credenciales')
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.chdir(folder)
        except (IOError, OSError):
            if not msg:
                raise Warning(u"Error en conexión a Ruta de escritura de documento XML, '%s'. Revisar parametrización "
                              u"en compañía o estado servidor SFTP" % cp.ei_write_folder)
            elif 'Error' not in folder:
                dct = u"Error en conexión a Ruta de lectura de %s, '%s'. Revisar parametrización en compañía o estado " \
                      u"servidor SFTP" % (msg, folder)
                self._create_ei_order_log(self, '', 'loghost', '', dct, '', 'open', self.ei_state if self else '')
            return
        return sftp, transport

    @api.multi
    def _calc_invoices(self, typ):
        invoices = self.search([('state', 'in', ['open', 'paid']), ('partner_id.electronic_invoice', '=', True),
                                ('ei_state', '=', 'pending'), ('type', '=', typ), ('number', '!=', False)])
        return invoices

    @api.multi
    def _calc_partner_type(self, partner):
        if partner.ref_type.code in ['NI', 'SI']:
            f_typ = '1'
        else:
            f_typ = '2'
        return f_typ

    @api.multi
    def _check_tax(self, code):
        l_15 = ['11', '25E', '263', '86', '210', '13C', '177', '17C', '15C', '16C', '201',
                '18C']
        return True if code in l_15 else False

    @api.multi
    def _is_withholding(self, code):
        return code in ['05', '06', '07', '01C', '02C', '03C']

    def valid_obligation(self, code):
        return code in  ['O-13', 'O-15', 'O-23', 'O-47', 'R-99-PN', 'ZZ']

    @api.multi
    def _add_sub_element(self, var, tag, lvalue):
        """
        Adiciona cada uno de los sub elementos XML
        :param var: Sub elemento de variable principal ET
        :param tag: Etiqueta que llevaran los sub elementos adicionados
        :param lvalue: Valores correspondientes por posición a cada una de sus respectivas etiquetas
        """
        for p, v in enumerate(lvalue):
            if isinstance(v, list):
                if len(v) == 0:
                    ET.SubElement(var, tag + str(p + 1)).text = ""
                for lv in v:
                    if lv:
                        ET.SubElement(var, tag + str(p+1)).text = str(lv)
            else:
                if v:
                    ET.SubElement(var, tag + str(p+1)).text = str(v) if type(v).__name__ in ['float', 'int'] else v

    @api.multi
    def _create_ei_order_log(self, inv, fname, tl, td, dct, data, st, dst, ol_nam=''):
        self.env['ei.order.log'].sudo().create({
            'name': inv.number if inv and not ol_nam else ol_nam,
            'transaction_date': datetime.now(),
            'name_file': fname,
            'type_log': tl,
            'type_doc': td,
            'description': dct,
            'data': data,
            'state': st,
            'document_state': dst,
            'invoice_id': inv if inv and isinstance(inv, int) else None if not inv else inv.id
            })

    # FE Nacional y de Exportación, Nota Crédito y Nota Débito
    @api.multi
    def _gen_xml_invoice(self):
        def _join_names(names):
            return ' '.join([nm or '' for nm in names]).strip()

        company = self.env.user.company_id
        if not company.electronic_invoice or company.ei_database != self._cr.dbname:
            raise Warning("No es posible generar la representación XML Electrónica, verifique que la compañía tenga "
                          "habilitado el check de Facturación Electrónica y que la base de datos sea la correcta. "
                          "¡Si se están realizando pruebas recuerde configurar los comprobantes contables con la "
                          "resolución de Pruebas - PRUE!")
        inv_type = [self.type] or ['out_invoice', 'out_refund']
        for tp in inv_type:
            if self:
                if self.ei_state in ['pending', 'supplier_rejec', 'dian_rejec']:
                    account_invoices = self
                else:
                    raise Warning('Este documento ya tiene una factura electrónica generada, por favor validar.')
            else:
                account_invoices = self._calc_invoices(tp)
            for inv in account_invoices:
                if not inv.payment_term:
                    raise Warning('Por favor defina el Plazo de Pago del documento')
                co_partner = company.partner_id
                inv_partner = inv.partner_id if not inv.partner_id.parent_id else inv.partner_id.parent_id
                journal = inv.journal_id
                tp = 'ei' if (tp == 'out_invoice' and journal.type == 'sale') else 'nc' if tp == 'out_refund' else 'nd'
                if not inv_partner.electronic_invoice:
                    dct = 'No es posible generar el XML de FE del documento ' + inv.number + '. Por favor revise la ' \
                          u'parametrización del tercero asociado a la factura, verifique que está permitido para ' \
                          u'generación de Factura Electrónica'
                    self._create_ei_order_log(inv, '', 'param', tp, dct, '', 'open', inv.ei_state)
                    continue
                if not (journal.invoice_prefix and journal.ei_start_date):
                    dct = 'No es posible generar el XML de FE del documento ' + inv.number + '. Por favor revise la ' \
                          u'parametrización de Facturación Electrónica del Comprobante relacionado'
                    self._create_ei_order_log(inv, '', 'param', tp, dct, '', 'open', inv.ei_state)
                    continue
                if not company.ei_server_type:
                    raise Warning(u"Debe configurarse en la Compañía el tipo de Ambiente para Facturación Electrónica, "
                                  u"contacte a Soporte")
                if not company.ei_operation_type:
                    raise Warning(u"Debe parametrizar en la Compañía el Tipo de Operación, campo necesario para "
                                  u"Facturación Electrónica, contacte a Soporte")

                param_logs = self.ei_order_log_ids.filtered(lambda x: x.type_log == 'param' and x.state == 'open')
                if param_logs:
                    param_logs.write({'state': 'close'})

                self.env.cr.execute("SELECT incoterm FROM sale_order where name = '%s'" % inv.stock_picking_id.origin)
                inco = self._cr.fetchone()
                inv_n_oc = getattr(inv, 'n_oc', None)
                if inv_n_oc and len(inv_n_oc) > 34:
                    raise Warning(u"Longitud máxima campo No. OC alcanzada, documento con id %s; longitud máxima "
                                  u"permitida 35 caracteres. Por favor verificar." % inv.id)
                lvals_ref = ["", "", ""]
                enc_20 = '1' if company.ei_server_type == 'production' else '2'
                if tp == 'ei':
                    if not journal.ei_payment_method:
                        raise Warning(u"Debe definir el códido del Método de Pago para facturación electrónica en el "
                                      u"Diario %s, por favor ajustar." % journal.name)
                    so_origin = inv.stock_picking_id.origin or ''
                    tp_name = 'FACTURA DE VENTA'
                    enc_1 = 'INVOIC'
                    enc_9 = '02' if inco and inco[0] else '01' if not inv.contingency_invoice else '03'
                    enc_21 = company.ei_operation_type
                    if getattr(company, 'receipt_notice', None) and inv_partner.receipt_notice:
                        if not inv.stock_picking_id.receipt_notice:
                            raise Warning(u"El cliente %s de la factura %s, tiene marcado el check de gestión de Aviso "
                                          "de Recibo, sin embargo la transferencia asociada a la factura, no cuenta con "
                                          "un Aviso de recibo. Por favor validar" % (inv_partner.name, inv.number))
                        # REF
                        p_serv = any('service' == x.product_id.type for x in inv.invoice_line)
                        if not p_serv:
                            lvals_ref = ["ALO", inv.stock_picking_id.receipt_notice,
                                         str(inv.stock_picking_id.document_date)[:10]]
                    if enc_9 == '03':
                        lvals_ref = ['FTC', inv.number.replace('-', ''), inv.date_invoice]
                elif tp == 'nc':
                    inv_n_oc = inv_n_oc or getattr(inv.invoice_out_refund_id, 'n_oc', None)
                    tp_name = 'NOTA CREDITO'
                    enc_1 = 'NC'
                    enc_9 = '91'
                    # REF
                    self.env.cr.execute("SELECT date_invoice FROM account_invoice WHERE number='%s'" % (inv.origin or
                                        inv.invoice_out_refund_id.number))
                    ref_3 = self.env.cr.fetchone()
                    reference = inv.origin or inv.invoice_out_refund_id.number
                    if 'FE' in reference or 'SETT' in reference:
                        ref_1 = 'IV'
                        ref_3 = ref_3[0] if ref_3 else inv.date_invoice
                        enc_21 = '20'
                    else:
                        ref_1 = 'RF1'
                        ref_3 = ref_3[0] if ref_3 else inv.date_invoice
                        enc_21 = '22'
                    lvals_ref = [ref_1, inv.origin or inv.invoice_out_refund_id.number, ref_3]
                else:
                    inv_n_oc = inv_n_oc or getattr(inv.invoice_out_add_id, 'n_oc', None)
                    tp_name = 'NOTA DEBITO'
                    enc_1 = 'ND'
                    enc_9 = '92'
                    # REF
                    self.env.cr.execute("SELECT date_invoice FROM account_invoice WHERE number='%s'" % (inv.origin or
                                        inv.invoice_out_add_id.number))
                    ref_3 = self.env.cr.fetchone()
                    reference = inv.origin or inv.invoice_out_refund_id.number
                    if 'FE' in reference or 'SETT' in reference:
                        ref_1 = 'IV'
                        ref_3 = ref_3[0] if ref_3 else inv.date_invoice
                        enc_21 = '30'
                    else:
                        ref_1 = 'RF1'
                        ref_3 = ref_3[0] if ref_3 else inv.date_invoice
                        enc_21 = '32'
                    lvals_ref = [ref_1, inv.origin or inv.invoice_out_add_id.number, ref_3]

                invoice = ET.Element(tp_name.split(' ')[0])
                

                #hora = str(datetime.strptime(inv.create_date, "%Y-%m-%d %H:%M:%S") - timedelta(hours=5))[11:]
                utc_adj = '-05:00'
                hora = str(datetime.strptime(inv.create_date, "%Y-%m-%d %H:%M:%S"))[11:] + utc_adj
                number = inv.number.replace('-', '')
                currency_name = inv.currency_id.name
                d_ovt = []

                if tp == 'nc':
                    enc_5_description = ': Nota Crédito de Factura Electrónica de Venta'
                elif tp == 'nd':
                    enc_5_description = ': Nota Débito de Factura Electrónica de Venta'
                elif tp == 'ei':
                    enc_5_description = ': Factura Electrónica de Venta'
                else:
                    enc_5_description = ''

                # Informacion Cabecera
                enc = ET.SubElement(invoice, "ENC")
                lvals = [enc_1, co_partner.ref, inv_partner.ref, 'UBL 2.1', 'DIAN 2.1' + enc_5_description, number, inv.date_invoice, hora,
                         enc_9, currency_name, "", "", "", "", str(len(inv.invoice_line)), inv.date_due, "", "",
                         "", enc_20, enc_21, ""]
                self._add_sub_element(enc, 'ENC_', lvals)

                # Identificador Único del Documento
                cuf = ET.SubElement(invoice, "CUF")
                cuf_1 = ''  # TODO Calcular???
                lvals = [cuf_1]
                self._add_sub_element(cuf, 'CUF_', lvals)

                # Informacion Emisor
                emi = ET.SubElement(invoice, "EMI")
                f_typ = self._calc_partner_type(co_partner)
                d_typ = co_partner.ref_type.code_dian
                lvals = [f_typ, co_partner.ref, d_typ, 'No aplica', "", co_partner.name,
                         co_partner.name, "", "", co_partner.street, co_partner.state_id.code, "",
                         co_partner.city_id.name,
                         co_partner.zip or co_partner.state_id.code + co_partner.city_id.code, co_partner.country_id.code, "", "", "",
                         co_partner.state_id.name, "", co_partner.country_id.name, co_partner.dev_ref,
                         co_partner.state_id.code + co_partner.city_id.code, co_partner.name]
                self._add_sub_element(emi, 'EMI_', lvals)

                # Informacion Tributaria, Aduanera y Cambiaria - Emisor
                tac_1 = ';'.join(x.code for x in co_partner.tributary_obligations_ids if self.valid_obligation(x.code))
                # tac_1 += ';' if co_partner.customs_obligations_ids else ''
                # tac_1 += ';'.join(x.code for x in co_partner.customs_obligations_ids)
                if not tac_1:
                    raise Warning('No se encontraron obligaciones del contribuyente\
                        válidas. Verifique en el tercero de la compañia')
                tac = ET.SubElement(emi, "TAC")
                lvals = [tac_1, "", "", "", "", "", "", "", "", "", ""]
                self._add_sub_element(tac, 'TAC_', lvals)

                # Informacion Dirección Fiscal del Emisor
                dfe = ET.SubElement(emi, "DFE")
                lvals = [
                    co_partner.state_id.code + co_partner.city_id.code,
                    co_partner.state_id.code,
                    co_partner.country_id.code,
                    co_partner.zip,
                    co_partner.country_id.name,
                    co_partner.state_id.name,
                    co_partner.city_id.name,
                    co_partner.street or 'na',
                ]
                self._add_sub_element(dfe, 'DFE_', lvals)

                # Informacion Camara de Comercio
                if journal.invoice_resolution:
                    icc = ET.SubElement(emi, "ICC")
                    lvals = ["", "", "", "", "", "", "", "",
                        journal.invoice_prefix
                    ]
                    self._add_sub_element(icc, 'ICC_', lvals)

                # Contacto Emisor
                cde = ET.SubElement(emi, "CDE")
                lvals = ["1", co_partner.name, co_partner.phone, co_partner.email]
                self._add_sub_element(cde, 'CDE_', lvals)

                # Grupo de Detalles Tributarios del Emisor
                gte = ET.SubElement(emi, "GTE")
                lvals = ["01", "IVA"]
                self._add_sub_element(gte, 'GTE_', lvals)

                # Informacion Adquiriente
                adq = ET.SubElement(invoice, "ADQ")
                f_typ = self._calc_partner_type(inv_partner)
                d_typ = inv_partner.ref_type.code_dian
                if inv.partner_id.ei_partner_address == 'default':
                    adq_addr = (
                        inv.partner_id.street,
                        inv.partner_id.city_id.name,
                        inv.partner_id.state_id.code,
                        inv.partner_id.state_id.country_id.code,
                        inv.partner_id.zip,
                        inv.partner_id.state_id.code +\
                        inv.partner_id.city_id.code,
                        inv.partner_id.state_id.name,
                        inv.partner_id.state_id.country_id.name,
                        inv.partner_id.ean_localizacion
                    )
                elif inv.partner_id.ei_partner_address == 'delivery':
                    adq_addr = (
                        inv.partner_shipping_id.street,
                        inv.partner_shipping_id.city_id.name,
                        inv.partner_shipping_id.state_id.code,
                        inv.partner_shipping_id.state_id.country_id.code,
                        inv.partner_shipping_id.zip,
                        inv.partner_shipping_id.city_id.code,
                        inv.partner_shipping_id.state_id.code +\
                        inv.partner_shipping_id.state_id.name,
                        inv.partner_shipping_id.state_id.country_id.code,
                        inv.partner_shipping_id.ean_localizacion
                    )
                else:
                    adq_addr = (
                        inv.partner_invoice_id.street,
                        inv.partner_invoice_id.city_id.name,
                        inv.partner_invoice_id.state_id.code,
                        inv.partner_invoice_id.state_id.country_id.code,
                        inv.partner_invoice_id.zip,
                        inv.partner_invoice_id.state_id.code +\
                        inv.partner_invoice_id.city_id.code,
                        inv.partner_invoice_id.state_id.name,
                        inv.partner_invoice_id.state_id.country_id.name,
                        inv.partner_invoice_id.ean_localizacion
                    )
                lvals = [
                    f_typ, inv_partner.ref, d_typ, 'No aplica', inv_partner.ref,
                    inv_partner.name or '',
                    inv_partner.name or '',
                    (f_typ == '2' and _join_names(
                        [inv_partner.primer_nombre,
                        inv_partner.otros_nombres,
                        inv_partner.primer_apellido,
                        inv_partner.segundo_apellido]
                    ) or ''),
                    "",
                    adq_addr[0], #10
                    adq_addr[2],
                    "",
                    adq_addr[1],
                    adq_addr[4],
                    adq_addr[3],
                    adq_addr[8],
                    "", "",
                    adq_addr[6],
                    "",
                    adq_addr[7], #21
                    str(inv_partner.dev_ref) if type(inv_partner.dev_ref)\
                        is not bool else '',
                    adq_addr[5], inv_partner.ref,
                    d_typ,
                    str(inv_partner.dev_ref) if type(inv_partner.dev_ref) is not bool else ''
                ]
                self._add_sub_element(adq, 'ADQ_', lvals)

                # Informacion Tributaria, Aduanera y Cambiaria - Adquiriente
                tcr = ET.SubElement(adq, "TCR")
                tcr_1 = ';'.join(x.code for x in inv_partner.tributary_obligations_ids if self.valid_obligation(x.code))
                tcr_1 = tcr_1 or 'R-99-PN'
                # tcr_1 += ';'.join(x.code for x in inv_partner.customs_obligations_ids)
                lvals = [tcr_1, "", "", "", "", "", "", "", "", "", ""]
                self._add_sub_element(tcr, 'TCR_', lvals)

                # Información Legal del Adquiriente
                # obligatoria si el cliente es responsable del iva
                dev_ref = inv_partner.dev_ref
                ila = ET.SubElement(adq, "ILA")
                lvals = [
                    inv_partner.name,
                    inv_partner.ref,
                    d_typ,
                    str(dev_ref) if type(dev_ref) is not bool else '',
                    '100'
                ]
                self._add_sub_element(ila, 'ILA_', lvals)

                # Información Dirección Fiscal del Adquiriente
                dfa = ET.SubElement(adq, "DFA")
                lvals = [
                    adq_addr[3],
                    adq_addr[2],
                    adq_addr[4],
                    adq_addr[5],
                    adq_addr[7],
                    adq_addr[6],
                    adq_addr[1],
                    adq_addr[0] or 'na'
                ]
                self._add_sub_element(dfa, 'DFA_', lvals)

                # Contactos Receptor.
                cda = ET.SubElement(adq, "CDA")
                lvals = ['1', inv_partner.name, inv.partner_id.phone, inv.partner_id.email]
                self._add_sub_element(cda, 'CDA_', lvals)

                # Grupo de Detalles Tributarios del Adquiriente
                gta = ET.SubElement(adq, "GTA")
                lvals = (
                    ["01", "IVA"] if adq_addr[3] in ('CO', '169')
                    else ["ZZ", "No aplica"]
                )
                self._add_sub_element(gta, 'GTA_', lvals)

                ei_code_key = 0
                subtax_key = 1

                valid_taxes = filter(
                    lambda t: t[ei_code_key],
                    map(
                    lambda tax: (
                        tax.base_code_id.ei_code or\
                        self.env['account.tax'].search(
                            [('name', '=', tax.name)]
                        )[0].base_code_id.ei_code,
                        tax
                    ),
                    inv.tax_line.filtered(lambda tax: tax.amount != 0)
                ))

                # Dismiss withholdings report taxes only
                reported_taxes = filter(
                    lambda tax: not self._is_withholding(tax[ei_code_key]),
                    valid_taxes
                )
                reported_taxes_name = map(
                    lambda rt: rt[subtax_key].name,
                    reported_taxes
                )
                total_reported_taxes = sum(t[subtax_key].amount for t in\
                    reported_taxes
                )
                taxed_lines = filter(
                    lambda line:
                        set(map(lambda t: t.name, line.invoice_line_tax_id)) &\
                        set(reported_taxes_name),
                    inv.invoice_line
                )
                ref_3 = round(sum(
                    [tl.price_subtotal or 0.0 for tl in taxed_lines]),
                    2)

                # Importes Totales
                if getattr(inv.invoice_line[0], 'discount_line', False):
                    disc = sum([x.discount_line or 0.0 for x in inv.invoice_line])
                else:
                    disc = sum([x.discount or 0.0 for x in inv.invoice_line])
                tot = ET.SubElement(invoice, "TOT")
                # TODO tener en cuenta totales con anticipos
                lvals = [
                    inv.amount_untaxed,
                    currency_name,
                    ref_3 or '0.0',
                    currency_name,
                    inv.amount_untaxed + total_reported_taxes,
                    currency_name,
                    inv.amount_untaxed + total_reported_taxes,
                    currency_name,
                    "", #'{:.3f}'.format(disc),
                    currency_name, "", "", "", "", "", ""]
                self._add_sub_element(tot, 'TOT_', lvals)

                # Total Impuestos
                total_taxes_iva = 0
                for tax in inv.tax_line:
                    ei_code = tax.base_code_id.ei_code
                    if ei_code == '01':
                        total_taxes_iva += abs(tax.amount)



                taxes_codes = sorted(filter(
                    lambda taxc: taxc[0],
                    valid_taxes
                ), key=lambda tc: tc[ei_code_key])

                taxes = [
                    (ei_code, list(tax)) for ei_code, tax in
                    groupby(taxes_codes, lambda tax: tax[ei_code_key])
                ]

                for ei_code, ltax in taxes:
                    tax = filter(
                        lambda t: not self._is_withholding(ei_code) or\
                            not 'auto' in t[subtax_key].name.lower(),
                        ltax
                    )
                    total_amount_per_tax = abs(
                        sum([subtax[subtax_key].amount for subtax in tax])
                    )
                    if total_amount_per_tax == 0.0:
                        continue
                    if self._check_tax(ei_code) and not\
-                            self._is_withholding(ei_code):
                        d_ovt = [
                            ei_code,
                            total_amount_per_tax,
                            currency_name
                        ]
                        continue
                    # tim_1 = 'true' if 'rete' in\
                        # ''.join(map(
                            # lambda subtax: subtax[subtax_key].name.lower(),
                            # tax))\
                        # else 'false'
                    if self._is_withholding(ei_code):
                        continue
                    tim = ET.SubElement(invoice, "TIM")
                    tim_1 = 'true' if self._is_withholding(ei_code) else 'false'
                    tax_rounding = 0.0
                    for sub_tax in tax:
                        subtax = sub_tax[subtax_key]
                        imp_amt = (subtax.amount / subtax.base) * 100
                        if ei_code == '01':
                            imp_amt = round(imp_amt)
                        tax_rounding += (round(imp_amt, 2)/ 100) * subtax.base - abs(subtax.amount)
                    lvals = [
                        tim_1,
                        total_amount_per_tax,
                        currency_name,
                        tax_rounding,
                        currency_name
                    ]
                    self._add_sub_element(tim, 'TIM_', lvals)
                    for sub_tax in tax:
                        subtax = sub_tax[subtax_key]
                        imp = ET.SubElement(tim, "IMP")
                        imp_amt = (subtax.amount / subtax.base) * 100
                        if ei_code == '01':
                            imp_amt = round(imp_amt)
                        num_porc = '{:.2f}'.format(abs(imp_amt))
                        lvals = [
                            ei_code,
                            subtax.base,
                            currency_name,
                            abs(subtax.amount),
                            currency_name,
                            num_porc
                        ]
                        self._add_sub_element(imp, 'IMP_', lvals)



                # Tipo de Cambio
                tdc = ET.SubElement(invoice, "TDC")
                lvals = [currency_name, inv.moneda_local.name, '{:.4f}'.format(inv.tasa_manual),
                         inv.date_invoice, "1.00", "1.00", "", ""]
                self._add_sub_element(tdc, 'TDC_', lvals)

                # Anticipos
                for lpay in inv.payment_ids:
                    ant = ET.SubElement(invoice, "ANT")
                    lvals = [lpay.credit, lpay.currency_id.name or currency_name, lpay.date,
                             "", lpay.ref, lpay.date]
                    self._add_sub_element(ant, 'ANT_', lvals)

                # Descuentos o Cargos
                # if disc > 0:  # TODO check disc value
                #     dsc = ET.SubElement(invoice, "DSC")
                #     lvals = [
                #         "false",
                #         round(100 * disc / (inv.amount_untaxed + disc), 2),
                #         '{:.3f}'.format(disc),
                #         currency_name,
                #         "09",
                #         "",
                #         inv.amount_untaxed + disc,
                #         currency_name,
                #         "",
                #         '1'
                #     ]
                #     self._add_sub_element(dsc, 'DSC_', lvals)

                # Datos Resolución de Numeración de Facturas
                drf = ET.SubElement(invoice, "DRF")
                if journal.invoice_resolution:
                    lvals = [journal.invoice_resolution, journal.ei_start_date, journal.ei_end_date,
                             journal.invoice_prefix or journal.sequence_id.prefix, journal.ei_start_invoice,
                             journal.ei_end_invoice]
                else:
                    lvals = ["", "", "", journal.invoice_prefix or journal.sequence_id.prefix, journal.ei_start_invoice,
                             journal.ei_end_invoice]
                self._add_sub_element(drf, 'DRF_', lvals)

                # Quien Factura -- Comentariado solicitud DIAN 26/07/2021--
                # qfa = ET.SubElement(invoice, "QFA")
                # d_typ = co_partner.ref_type.code_dian
                # f_typ = self._calc_partner_type(co_partner)
                # lvals = [co_partner.ref, d_typ, "2", co_partner.name, "", "", "", co_partner.street,
                #          co_partner.state_id.name, co_partner.city_id.name, co_partner.city_id.name, co_partner.zip,
                #          co_partner.state_id.country_id.code, "", "", f_typ]
                # self._add_sub_element(qfa, 'QFA_', lvals)

                # Informacion Tributaria, Aduanera y Cambiaria - Quien Factura
                qta_1 = [x.code for x in co_partner.tributary_obligations_ids if self.valid_obligation(x.code)]
                qta = ET.SubElement(qfa, "QTA")
                lvals = [qta_1]
                self._add_sub_element(qta, 'QTA_', lvals)

                # A Quien se factura
                aqf = ET.SubElement(invoice, "AQF")
                f_typ = self._calc_partner_type(inv_partner)
                d_typ = inv_partner.ref_type.code_dian

                lvals = [inv_partner.ref, d_typ, (f_typ == '1' and '2' or '0'),
                         (f_typ == '1' and inv_partner.name or ''), "", (f_typ == '2' and inv_partner.name or ''),
                         (f_typ == '2' and _join_names([inv_partner.primer_apellido, inv_partner.segundo_apellido]) or ''),
                         inv_partner.street, inv_partner.state_id.name, inv_partner.city_id.name,
                         inv_partner.city_id.name, "", inv_partner.state_id.country_id.code, "", "", f_typ]
                self._add_sub_element(aqf, 'AQF_', lvals)

                # Informacion Tributaria, Aduanera y Cambiaria - A Quien se Factura
                ata = ET.SubElement(aqf, "ATA")
                lr = []
                for obl in inv_partner.tributary_obligations_ids:
                    lr.append(obl.code)
                for obl in inv_partner.customs_obligations_ids:
                    lr.append(obl.code)
                lvals = [lr or ['R-99-PN']]
                self._add_sub_element(ata, 'ATA_', lvals)

                # Notas de la factura
                if tp == 'ei' and journal.invoice_resolution:
                    msg2 = 'Factura Electronica Res. DIAN ' + journal.invoice_resolution
                elif tp == 'nc':
                    msg2 = 'Nota Credito'
                elif tp == 'nd':
                    msg2 = 'Nota Debito'
                else:
                    msg2 = ''
                msg2 += ": Desde " + str(journal.invoice_prefix) + " " + str(journal.ei_start_invoice) + \
                        " hasta " + str(journal.ei_end_invoice) + " Fecha Res. " + str(journal.ei_start_date)
                msg3 = inv.comment if inv.comment and inv.comment != 'False' else u'Observación'
                amount_msg4 = inv.amount_untaxed + total_taxes_iva
                msg4 = report_tools.avancys_amount_to_text_decimal(amount_msg4, inv_partner.lang)
                lvals = [journal.not_one_xml, msg2, msg3, msg4, journal.not_five_xml or '.', str(inv.amount_untaxed),
                         str(len(inv.invoice_line)), inv.partner_shipping_id.name]
                for l in lvals:
                    nota = ET.SubElement(invoice, "NOT")
                    self._add_sub_element(nota, 'NOT_', [l])

                # Referencia de la Orden de Compra
                if inv_n_oc:
                    orc = ET.SubElement(invoice, "ORC")
                    lvals = [inv_n_oc, "", "", inv_n_oc]
                    self._add_sub_element(orc, 'ORC_', lvals)

                if lvals_ref[0]:
                    ref = ET.SubElement(invoice, "REF")
                    lvals = lvals_ref
                    self._add_sub_element(ref, 'REF_', lvals)

                # Factura Contingencia
                if inv.contingency_invoice and tp == 'ei':
                    crf = ET.SubElement(invoice, "CRF")
                    isdt = datetime.strptime(inv.ci_start_date, "%Y-%m-%d %H:%M:%S") - timedelta(hours=5)
                    iedt = datetime.strptime(inv.ci_end_date, "%Y-%m-%d %H:%M:%S") - timedelta(hours=5)
                    lvals = [inv.ci_transcription, str(datetime.now())[:10], str(isdt)[:10], str(isdt)[11:],
                             str(iedt)[:10], str(iedt)[11:], inv.ci_identifier]
                    self._add_sub_element(crf, 'CRF_', lvals)

                # Informacion de entrega
                ien = ET.SubElement(invoice, "IEN")
                if getattr(inv, 'partner_shipping_id', False):
                    invp_shipping = inv.partner_shipping_id
                else:
                    invp_shipping = inv_partner
                ien_1 = invp_shipping.street
                if ien_1 and len(ien_1) > 100:
                    raise Warning(u"Longitud máxima superada en campo Lugar de Entrega, longitud máxima permitida "
                                  u"100, longitud enviada %s. Factura %s. Por favor ajustar dirección tercero %s" %
                                  (len(ien_1), number, invp_shipping.name))
                ien_12 = invp_shipping.city_id.code
                lvals = [
                    ien_1,
                    invp_shipping.state_id.code,
                    "",
                    invp_shipping.city_id.name,
                    invp_shipping.zip,
                    invp_shipping.country_id.code,
                    "",
                    (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "", "", "",
                    ien_12]
                self._add_sub_element(ien, 'IEN_', lvals)

                # Tiempos de entrega
                inc_code = ""
                inc_name = ""
                if inco and inco[0]:
                    self._cr.execute("SELECT code, name FROM stock_incoterms WHERE id = %s" % inco[0])
                    inc = self._cr.fetchone()
                    inc_code = inc[0]
                    inc_name = inc[1]

                tet = ET.SubElement(invoice, "TET")
                lvals = [inc_name, inc_code, "", ""]
                self._add_sub_element(tet, 'TET_', lvals)

                # Medios de Pago
                if inv.payment_term.line_ids and inv.payment_term.line_ids[0].days > 0:
                    payment_condition, payment_days = 2, inv.payment_term.line_ids[0].days
                else:
                    payment_condition = 1
                mep = ET.SubElement(invoice, "MEP")
                lvals = [journal.ei_payment_method, payment_condition, inv.date_due, "", "", "", "", "", ""]
                self._add_sub_element(mep, 'MEP_', lvals)

                # Información para CT&S
                cts = ET.SubElement(invoice, "CTS")
                cts_1 = company.cts_one_xml.split('|')
                if len(cts_1) > 1:
                    lvals = [cts_1[1] if inco and inco[0] else cts_1[0]]
                else:
                    lvals = [cts_1[0]]
                self._add_sub_element(cts, 'CTS_', lvals)

                # Otros Totales
                ovt = ET.SubElement(invoice, "OVT")
                lvals = d_ovt
                self._add_sub_element(ovt, 'OVT_', lvals)

                if tp in ('nc', 'nd'):
                    cdn = ET.SubElement(invoice, "CDN")
                    if tp == 'nc':
                        lvals = ["5", "Sin Observaciones"]
                    else:
                        lvals = ["4", "Sin Observaciones"]
                    self._add_sub_element(cdn, 'CDN_', lvals)

                    dcn = ET.SubElement(invoice, "DCN")
                    lvals = ["Sin Observaciones"]
                    self._add_sub_element(dcn, 'DCN_', lvals)

                # Líneas de la factura
                moves = []
                for i, line in enumerate(inv.invoice_line):
                    today = datetime.today().strftime('%Y-%m-%d')
                    vat_excemption_config = self.env['vat.excemption.products.config'].search(
                        [('products_ids', '=', line.product_id.id)]
                    ).filtered(
                        lambda vat_conf: (self.date_invoice or today)  in [
                            conf.name for conf in vat_conf.excempted_days_ids]
                    )
                    ite_10 = "Bienes Cubiertos" if vat_excemption_config else ""
                    # Items del documento
                    ite = ET.SubElement(invoice, "ITE")
                    ite_11 = line.product_id.default_code
                    lvals = [str(i+1), "", line.quantity,
                             line.uos_id.ei_uom_code,
                             line.price_subtotal,
                             currency_name, 
                             round(line.price_unit, 2),
                             currency_name, "", ite_10, ite_11, ite_10, "",
                             "", "", "", "", ite_11,
                             line.price_subtotal + line.discount_line,
                             currency_name, line.price_subtotal,
                             currency_name, "", "", "", "",
                             line.quantity,
                             line.uos_id.ei_uom_code,
                             ""]
                    self._add_sub_element(ite, 'ITE_', lvals)

                    # Lote del item
                    moves_line = line.stock_move_ids
                    if tp == 'nc':
                        moves_line = []
                        for mv in inv.invoice_out_refund_id.invoice_line.filtered(lambda l: l.product_id ==
                                                                                            line.product_id):
                            for m in mv.stock_move_ids:
                                moves_line.append(m)
                        if not moves_line:
                            moves_line = line.stock_move_ids

                    for m in moves_line:
                        moves.append(m)
                        nLots = len(m.lot_ids)
                        for l in m.lot_ids:
                            if len(l.name or '') > 35:
                                raise Warning(u"Por favor revisar la línea de factura del tercero {} con producto {}. "
                                              u"El Lote '{}' no cumple con la longitud máximaITE permitida para "
                                              u"facturación electrónica.\n\nLongitud enviada {}\nLongitud permitida 35"
                                              .format(inv_partner.name, line.product_id.default_code, l.name,
                                                      len(l.name)))
                            lot = ET.SubElement(ite, "LOT")
                            lot_name = l.name
                            if nLots > 1:
                                lot_qty = m.quant_ids.filtered(lambda x: x.lot_id.id == l.id)
                                lot_qty = lot_qty and lot_qty[0] and sum([x.qty for x in lot_qty]) or 0
                                lot_name = '{} [qty {}]'.format(lot_name, lot_qty)
                            lvals = [lot_name, l.life_date[:10] if l.life_date else '']
                            self._add_sub_element(lot, 'LOT_', lvals)

                    # Identificación del Artículo o Servicio de acuerdo con un Estándar
                    ref_code_val = getattr(line.product_id, 'ean_codigo', False) or\
                        getattr(line.product_id , 'ean13' , False) or line.product_id.default_code
                    ref_code = '010' if getattr(line.product_id, 'ean_codigo', False) or\
                        getattr(line.product_id, 'ean13', False) else '999'
                    iae = ET.SubElement(ite, "IAE")
                    lvals = [ref_code_val, ref_code, "", ""]
                    if enc_9 == '02':
                        lvals = [line.product_id.tariff_head or "0000000000", "020", "195", ""]
                    self._add_sub_element(iae, 'IAE_', lvals)

                    # Descuentos y cargos del item
                    if line.discount > 0:
                        ide = ET.SubElement(ite, "IDE")
                        p_price = line.price_unit * line.quantity
                        disc_val = round((p_price * line.discount) / 100, 4)
                        lvals = ['false', disc_val, currency_name, "", "", round(line.discount, 3), p_price,
                                 currency_name, "", str(i)]
                        self._add_sub_element(ide, 'IDE_', lvals)

                    # Total impuestos item
                    total = 0
                    for taxs in line.invoice_line_tax_id:
                        a = inv.subtotal_per_tax(line, taxs)
                        calc = taxs.amount * a
                        total += calc

                    per_line_taxes = [
                        (ei_code, list(tax)) for ei_code, tax in
                        groupby(
                            filter(lambda ltax: ltax.base_code_id.ei_code,
                                   line.invoice_line_tax_id),
                            lambda tax: tax.base_code_id.ei_code or '')
                    ]

                    for ei_code, ltax in per_line_taxes:
                        tax = filter(
                            lambda t: not self._is_withholding(ei_code) or\
                                not 'auto' in t.name.lower(),
                            ltax
                        )
                        total_amount_per_tax =\
                            sum([subtax.amount for subtax in tax])
                        if total_amount_per_tax == 0:
                            continue
                        # if self._check_tax(ei_code) and not\
                        #     self._is_withholding(ei_code):
                        #     continue
                        # if self._is_withholding(ei_code):
                        #     continue
                        calc = abs(
                            total_amount_per_tax * (line.price_subtotal)
                        )
                        tii = ET.SubElement(ite, "TII")
                        lvals = [
                            calc,
                            currency_name,
                            'true' if self._is_withholding(ei_code) else 'false',
                            abs(total_amount_per_tax) * line.price_subtotal - calc,
                            currency_name
                        ]
                        self._add_sub_element(tii, 'TII_', lvals)
                        iim = ET.SubElement(tii, "IIM")
                        lvals = [
                            ei_code, calc,
                            currency_name,
                            line.price_subtotal,
                            currency_name, abs(total_amount_per_tax * 100), "",
                            "", "", ""
                        ]
                        self._add_sub_element(iim, 'IIM_', lvals)

                    # DESCRIPCION DEL ITEM
                    dit = ET.SubElement(ite, "DIT")
                    ET.SubElement(dit, "DIT_1").text = ' ' +\
                        line.product_id.name if\
                        line.product_id.name else ''
                    if vat_excemption_config:
                        dit = ET.SubElement(ite, "NTI")
                        ET.SubElement(dit, "NTI_1").text = "Bienes Cubiertos"

                xml_file = ET.ElementTree(invoice)
                # Para evitar problemas en ruta
                inv_num = inv.number.replace('/', '').replace('-', '')
                ei_file = inv_num + datetime.now().strftime('_%d%m%Y%H%M%S%f')[:-3] + '.xml'

                sftp, transport = self._sftp_connect(company, '', company.ei_write_folder)
                xml_file.write(ei_file, encoding='utf-8', xml_declaration=True)

                inv.ei_state = 'done'
                so_f = []
                nf, tmp_file, att_msg = '', None, ''
                att_doc = self.env['ir.attachment'].search([('res_model', '=', 'stock.picking'),
                                        ('res_id', '=', self.stock_picking_id.id)]) if company.send_remission else []
                zip_f1 = None
                if company.send_cus_att and inv.customer_att:
                    tmp_file = open(inv.cus_att_name, 'w')
                    tmp_file.write(inv.customer_att.decode('base64'))
                    tmp_file.close()
                    att_zip = 'anexos_' + ei_file[:-4] + '.zip'
                    zip_f1 = zipfile.ZipFile(att_zip, mode='w')
                    zip_f1.write(inv.cus_att_name, inv.cus_att_name)
                    os.remove(inv.cus_att_name)
                    nf = 'un'

                if att_doc:
                    att_doc = att_doc[-1]
                    tmp_file = open(att_doc.name, 'w')
                    tmp_file.write(att_doc.datas.decode('base64'))
                    tmp_file.close()
                    nf = 'dos'
                    if not zip_f1:
                        att_zip = 'anexos_' + ei_file[:-4] + '.zip'
                        nf = 'un'
                        zip_f1 = zipfile.ZipFile(att_zip, mode='w')
                    zip_f1.write(att_doc.name, att_doc.name)
                    os.remove(att_doc.name)

                if moves and company.send_cus_po:
                    sale_orders = [x.sale_line_id.order_id for x in moves if x.sale_line_id.order_id.cus_po_name]
                    for s_o in set(sale_orders):
                        tmp_file = open(s_o.cus_po_name, 'w')
                        tmp_file.write(s_o.customer_po.decode('base64'))
                        tmp_file.close()
                        so_f.append(s_o.cus_po_name)
                    if so_f:
                        nf = 'tres' if att_doc and inv.customer_att else 'dos'
                        if not att_doc and not inv.customer_att:
                            nf = 'un'
                            att_zip = 'anexos_' + ei_file[:-4] + '.zip'
                            zip_f1 = zipfile.ZipFile(att_zip, mode='w')
                        for sf in so_f:
                            zip_f1.write(sf, sf)
                        map(os.remove, list(set([x for x in so_f])))
                        zip_f1.close()
                        zip_f2 = zipfile.ZipFile(att_zip[7:], mode='w')
                        for sf in [att_zip, ei_file]:
                            zip_f2.write(sf, sf)
                        zip_f2.close()
                        tmp_file = open(ei_file, 'r')
                        map(os.remove, [att_zip, ei_file])
                        ei_file = att_zip[7:]

                if not so_f and (att_doc or inv.customer_att):
                    zip_f1.close()
                    zip_f2 = zipfile.ZipFile(att_zip[7:], mode='w')
                    for sf in [att_zip, ei_file]:
                        zip_f2.write(sf, sf)
                    zip_f2.close()
                    tmp_file = open(ei_file, 'r')
                    map(os.remove, [att_zip, ei_file])
                    ei_file = att_zip[7:]

                if nf:
                    att_msg = u' Se envían {0} archivos adjuntos.'.format(nf) if len(nf) > 2 else \
                        u' Se envía {0} archivo adjunto.'.format(nf)

                tmp_file = tmp_file or open(ei_file, 'r')
                info = tmp_file.read()

                sftp.put(ei_file, ei_file)  # PUT in the server
                self.env['ei.order.log'].sudo().create({
                    'state': 'close',
                    'type_doc': tp,
                    'data': info,
                    'name_file': ei_file,
                    'invoice_id': inv.id,
                    'transaction_date': datetime.now(),
                    'name': inv.number,
                    'type_log': 'xml',
                    'document_state': 'done',
                    'description': 'Se genera el XML de la ' + tp_name + ' ' + inv.number + ' sin novedad.' + att_msg
                    })
                self.env.cr.commit()  # Por el movimiento de archivos
                sftp.close()
                transport.close()

    @api.multi
    def _check_file_size(self, name_file, att_doc):
        nf = name_file
        try:
            os.chdir(self.env.user.company_id.ei_temporal_files)
        except (IOError, OSError):
            raise Warning(u"Error en conexión a Ruta local de transferencia de FE '%s'. Revisar "
                          u"parametrización en Compañía o existencia de carpeta en el servidor local"
                          % self.env.user.company_id.ei_temporal_files)
        tmp_file = open(nf, 'w')
        tmp_file.write(att_doc.decode('base64'))
        tmp_file.close()
        if os.stat(nf).st_size > 1999999:
            os.remove(nf)
            raise Warning('El tamaño del archivo adjunto de Facturación Electrónica excede el máximo permitido, '
                          '2 Mb, por favor validar')
        os.remove(nf)

    electronic_invoice = fields.Boolean('Factura Electronica', related='partner_id.electronic_invoice', readonly=True)
    ei_state = fields.Selection([('pending', 'No Transferido'), ('done', 'Emitido'), ('supplier_rejec', 'Rechazado PT'),
                                 ('supplier_accep', 'Aceptado PT'), ('dian_rejec', 'Rechazado DIAN'),
                                 ('dian_accep', 'Aceptado DIAN'), ('ack_cus', 'Recibido Cliente'),
                                 ('cus_rejec', 'Rechazado Cliente'), ('cus_accep', 'Aceptado Cliente')],
                                string='Estado FE', default='pending', readonly=True, copy=False,
                                help='Estado Factura Electrónica')
    ei_cufe = fields.Char('CUFE', help='Código Único de Factura Electrónica asignado por la DIAN', readonly=True,
                          size=96, track_visibility='onchange', copy=False)
    ei_cude = fields.Char('CUDE', help='Código Único de Notas asignado por la DIAN', readonly=True,
                          size=96, track_visibility='onchange', copy=False, oldname='ei_uuid')
    ei_order_log_ids = fields.One2many('ei.order.log', 'invoice_id', string='Logs FE', readonly=True)
    contingency_invoice = fields.Boolean('Factura de Contingencia', help='Marque este check para indicar que la '
                                                                         'factura es de Contingencia')
    ci_transcription = fields.Char('Identificador Transcripción', size=15, help='Identificador de la transcripción '
                                        'de datos, asignado por el OFE; prefijo, consecutivo')
    ci_start_date = fields.Datetime('Inicio Contingencia')
    ci_end_date = fields.Datetime('Fin Contingencia')
    ci_identifier = fields.Char('Identificador Contingencia', help='Idenficador de la contingencia asignado a la '
                                'anotación hecha por el OFE en su bitacora de contigencias')
    customer_att = fields.Binary('Adjuntos Cliente', help='Archivo adjunto de Facturación Electrónica', copy=False)
    cus_att_name = fields.Char('Nombre Adjunto Cliente', copy=False)
    pol_send_cus_att = fields.Boolean('Política Envío Adj', related='company_id.send_cus_att', readonly=True)

    @api.multi
    def write(self, vals):
        if 'customer_att' in vals and vals['customer_att']:
            self._check_file_size(vals['cus_att_name'], vals['customer_att'])
        return super(AccountInvoice, self).write(vals)

    @api.model
    def create(self, vals):
        if 'customer_att' in vals and vals['customer_att']:
            self._check_file_size(vals['cus_att_name'], vals['customer_att'])
        return super(AccountInvoice, self).create(vals)

    @api.multi
    def ei_write_folder(self):
        if self or self.env.user.company_id.ei_automatic_gen:
            self._gen_xml_invoice()
        return True

    @api.multi
    def ei_read_folder(self):
        if self.env.user.company_id.ei_automatic_read:
            self.ei_account_invoice_documents()
        return True

    @api.multi
    def ei_automatic_acceptance(self):  # FIXME
        company = self.env.user.company_id
        if company.electronic_invoice and company.ei_database == self._cr.dbname:
            dt_chk = str(datetime.now() - timedelta(days=3))[:10]
            cr = self.env.cr
            invoices = []
            if self:
                if self.date_invoice <= dt_chk and self.ei_state == 'ack_cus':
                    invoices = [[self.id]]
            else:
                cr.execute("SELECT id FROM account_invoice WHERE type IN ('out_invoice', 'out_refund') AND "
                           "ei_state='ack_cus' AND date_invoice<='%s'" % dt_chk)
                invoices = cr.fetchall()
            if invoices and invoices[0]:
                dct = u'Se genera la Aceptación Automática del documento '
                for inv in self.browse([x[0] for x in invoices]):
                    self._create_ei_order_log(inv, 'No Aplica', 'none', 'ds', dct + inv.number, '', 'close',
                                              'cus_accep')
                    cr.execute("UPDATE account_invoice SET ei_state='cus_accep' WHERE id=%s" % inv.id)
                    cr.commit()

    @api.multi
    def ei_read_error_folder(self):
        company = self.env.user.company_id
        if company.electronic_invoice and company.ei_database == self._cr.dbname:
            transport = self._sftp_connect(company, u'XML erróneos', company.ei_error_folder)
            if not transport:
                return
            sftp, transport = transport[0], transport[1]

            files = sftp.listdir()
            if self and files:
                files = filter(lambda x: self.number.replace('/', '').replace('-', '') in x, files)

            for fname in files:
                fna = re.split('[_.]+', fname)
                if fna[-1] not in ['log', 'xml']:
                    continue
                self.env.cr.execute("SELECT id,ei_state,number FROM account_invoice WHERE number in %s AND ei_state IN "
                                    "('done', 'supplier_rejec', 'dian_rejec')" % str(tuple([str(x) for x in fna[:-1]])))
                inv = self.env.cr.fetchall()
                if len(inv) > 1:
                    continue
                sftp.get(fname, fname)
                doc = open(fname, "r")
                info = doc.read()
                if inv:
                    data_attach = {
                        'name': fname,
                        'datas_fname': fname,
                        'res_model': 'account.invoice',
                        'res_id': inv[0][0],
                        'mimetype': 'application/' + fna[-1],
                        'file_type': 'application/' + fna[-1],
                        'type': 'binary'
                        }
                    attachment = self.env['ir.attachment'].sudo().create(data_attach)
                    url = self.env['ir.config_parameter'].get_param('web.base.url') + '/web/binary/saveas?model' \
                                                            '=ir.attachment&field=datas&filename_field=name&id=' + \
                                                            str(attachment.id)
                    file_path = attachment._get_path(url)[0].split("/")
                    folder = file_path[0]
                    doct = file_path[1]
                    sftp.get(fname, doct)
                    p = config['data_dir']
                    db = self.env.cr.dbname
                    path = p + '/filestore/' + db + '/'
                    dest = path + folder + '/'
                    final_path = dest + doct
                    if not os.path.exists(dest):
                        shutil.move(doct, final_path)
                        self.env['ir.attachment'].sudo().search([('id', '=', attachment.id)]).write({
                            'store_fname': attachment._get_path(url)[0]
                            })
                    else:
                        shutil.move(doct, final_path)
                        self.env['ir.attachment'].sudo().search([('id', '=', attachment.id)]).write({
                            'store_fname': attachment._get_path(url)[0]
                            })

                        dct = 'Se genera la lectura del archivo de error ' + fname + ' sin novedad.'
                        self._create_ei_order_log(inv[0][0], fname, 'logxml', 'lg', dct, info, 'open', inv[0][1],
                                                  ol_nam=inv[0][2])

                    self.env.cr.execute("UPDATE account_invoice SET ei_state='supplier_rejec' WHERE id=%s" % inv[0][0])
                    sftp.remove(fname)
                else:
                    dct = 'Se genera la lectura del archivo ' + fname + u', no se encontró factura asociada'
                    # noinspection PyTypeChecker
                    self._create_ei_order_log('', fname, 'logxml', 'lg', dct, info, 'open', '')
                    sftp.remove(fname)
                doc.close()
                os.remove(fname)
                self.env.cr.commit()
            sftp.close()
            transport.close()

    @api.multi
    def ei_read_voucher_folder(self):
        company = self.env.user.company_id
        if not (company.electronic_invoice and company.ei_database == self._cr.dbname):
            return
        with self.sftp_connection(company, 'Comprobantes', company.ei_voucher_folder) as (sftp, transport):
            files = sftp.listdir()
            if self:
                if not self.number:
                    sftp.close()
                    transport.close()
                    return
                files = filter(lambda x: self.number.replace('/', '').replace('-', '') in x, files)

            dinv = {}
            linv = []
            file_types = ['pdf', 'xml'] if company.attach_invoice_xml else ['pdf']
            for fname in files:
                add_set = ''
                fna = re.split('[_.]+', fname)
                fna_type = fna[-1]
                if fna_type not in ['pdf', 'xml']:
                    continue
                i_n = [x for x in fna if x in dinv]
                if i_n:
                    inv = dinv[i_n[0]]
                else:
                    self.env.cr.execute("SELECT ai.id,ai.number,ai.type,aj.type FROM account_invoice ai INNER JOIN "
                                        "account_journal aj ON ai.journal_id=aj.id WHERE number in %s AND ei_state IN "
                                        "('done', 'supplier_rejec', 'dian_rejec')" % str(tuple([str(x) for x in fna[:-1]])))
                    inv = self.env.cr.fetchall()
                    if len(inv) > 1:
                        raise Warning('Se encontró mas de una referencia para el documento %s, por favor validar'
                                      % fname)
                    if not inv:
                        continue
                if fna_type in file_types:
                    data_attach = {
                        'name': fname,
                        'datas_fname': fname,
                        'res_model': 'account.invoice',
                        'res_id': inv[0][0],
                        'mimetype': 'application/' + fna_type,
                        'file_type': 'application/' + fna_type,
                        'type': 'binary'
                        }
                    attachment = self.env['ir.attachment'].sudo().create(data_attach)
                    url = self.env['ir.config_parameter'].get_param('web.base.url') + '/web/binary/saveas?model' \
                                                            '=ir.attachment&field=datas&filename_field=name&id=' + \
                                                            str(attachment.id)
                    file_path = attachment._get_path(url)[0].split("/")
                    folder = file_path[0]
                    doc = file_path[1]
                    sftp.get(fname, doc)
                    info = '' if fna_type == 'pdf' else open(doc, "r").read()
                    p = config['data_dir']
                    db = self.env.cr.dbname
                    path = p + '/filestore/' + db + '/'
                    dest = path + folder + '/'
                    final_path = dest + doc

                    shutil.move(doc, final_path)
                    sftp.remove(fname)
                    self.env['ir.attachment'].sudo().search([('id', '=', attachment.id)]).\
                        write({'store_fname': attachment._get_path(url)[0]})
                else:
                    doc = fname
                    sftp.get(fname, doc)
                    info = '' if fna_type == 'pdf' else open(doc, "r").read()
                    sftp.remove(fname)

                t_doc = 'ei' if (inv[0][2] == 'out_invoice' and inv[0][3] == 'sale') else 'nc' \
                    if inv[0][2] == 'out_refund' else 'nd' if (inv[0][2] == 'out_invoice' and inv[0][3] == 'sale_add') \
                    else 'ad'

                if fna_type == 'xml' and fna[0] != 'response':  # TODo imp
                    if t_doc == 'ei':
                        if re.search('">(.*)</cbc:UUID>', info):
                            add_set = ",ei_cufe='" + re.search('">(.*)</cbc:UUID>', info).group(1) + "'"
                        elif re.search('CUFE=(.*)</sts:QRCode>', info):
                            add_set = ",ei_cufe='" + re.search('CUFE=(.*)</sts:QRCode>', info).group(1) + "'"
                    elif t_doc in ['nc', 'nd']:
                        if re.search('CUDE.*">(.*)</cbc:UUID><cbc:Issue', info):
                            add_set = ",ei_cude='" + re.search('CUDE.*">(.*)</cbc:UUID><cbc:Issue', info).group(1) + "'"
                        elif re.search('CUDE=(.*)</sts:QRCode>', info):
                            add_set = ",ei_cude='" + re.search('CUDE=(.*)</sts:QRCode>', info).group(1) + "'"

                dct = 'Se genera la lectura del archivo ' + fname + ' y se adjunta al documento %s, ' \
                                                                    'sin novedad.' % inv[0][1]
                self._create_ei_order_log(inv[0][0], fname, 'log'+fna_type, t_doc, dct, info, 'close', 'supplier_accep',
                                          ol_nam=inv[0][1])
                if not i_n or add_set:
                    dinv[inv[0][1]] = inv
                if add_set:
                    linv.append((inv[0][0], add_set))
                self.env.cr.commit()  # Por el movimiento de archivos
            for i in linv:
                self.env.cr.execute("UPDATE account_invoice SET ei_state='supplier_accep'%s WHERE id=%s"
                                    % (i[1], i[0]))
                self.env.cr.commit()  # Por el movimiento de archivos


    @api.multi
    def ei_read_dian_result_folder(self):
        company = self.env.user.company_id
        if company.electronic_invoice and company.ei_database == self._cr.dbname:
            transport = self._sftp_connect(company, 'Resultado DIAN', company.ei_dian_result_folder)
            if not transport:
                return
            sftp, transport = transport[0], transport[1]

            files = sftp.listdir()
            if self:
                if not self.number:
                    sftp.close()
                    transport.close()
                    return
                files = filter(lambda x: self.number.replace('/', '').replace('-', '') in x, files)

            dinv = {}
            linv = []
            for fname in files:
                fna = re.split('[_.]+', fname)
                fna_type = fna[-1]
                if fna_type != 'xml':
                    continue
                i_n = [x for x in fna if x in dinv]
                if i_n:
                    inv = dinv[i_n[0]]
                else:
                    self.env.cr.execute("SELECT ai.id,ai.number,ai.type,aj.type FROM account_invoice ai INNER JOIN "
                                        "account_journal aj ON ai.journal_id=aj.id WHERE number in %s AND ei_state IN "
                                        "('done', 'supplier_accep')" % str(tuple([str(x) for x in fna[:-1]])))
                    inv = self.env.cr.fetchall()
                    if len(inv) > 1:
                        raise Warning('Se encontró mas de una referencia para el documento %s, por favor validar'
                                      % fname)
                    if not inv:
                        continue

                doc = fname
                sftp.get(fname, doc)
                info = open(doc, "r").read()
                sftp.remove(fname)

                dian_result, st = ('dian_accep', 'close') if re.search('<b:IsValid>(.*)</b:IsValid>', info).group(1) == \
                                                             'true' else ('dian_rejec', 'open')

                dct = u'Se genera la lectura del archivo {} y se adjunta al documento {}, sin novedad.'. \
                    format(fname, inv[0][1])
                self._create_ei_order_log(inv[0][0], fname, 'logxml', 'ds', dct, info, st, dian_result,
                                          ol_nam=inv[0][1])
                linv.append((inv[0][0], dian_result))
            for i in linv:
                self.env.cr.execute("UPDATE account_invoice SET ei_state='{}' WHERE id={}".format(i[1], i[0]))
                self.env.cr.commit()  # Por el movimiento de archivos
            sftp.close()
            transport.close()

    @api.multi
    def ei_read_ack_folder(self):
        company = self.env.user.company_id
        if company.electronic_invoice and company.ei_database == self._cr.dbname:
            transport = self._sftp_connect(company, 'Acuses de Recibo', company.ei_ack_folder)
            if not transport:
                return
            sftp, transport = transport[0], transport[1]

            files = sftp.listdir()
            if self:
                files = filter(lambda x: self.number.replace('/', '').replace('-', '') in x, files)

            dinv = {}
            att_xml = company.attach_invoice_xml
            for fname in files:
                fna = re.split('[_.]+', fname)
                fna_type = fna[-1]
                if fna_type != 'xml':
                    continue
                i_n = [x for x in fna if x in dinv]
                if i_n:
                    inv = dinv[i_n[0]]
                else:
                    self.env.cr.execute("SELECT id,number FROM account_invoice WHERE number in %s AND ei_state IN "  # TODO not secure about states
                                        "('supplier_accep','dian_accep')" % str(tuple([str(x) for x in fna[:-1]])))
                    inv = self.env.cr.fetchall()
                    if len(inv) > 1:
                        raise Warning('Se encontró mas de una referencia para el documento %s, por favor validar'
                                      % fname)
                    if not inv:
                        continue
                if att_xml:
                    data_attach = {
                        'name': fname,
                        'datas_fname': fname,
                        'res_model': 'account.invoice',
                        'res_id': inv[0][0],
                        'mimetype': 'application/' + fna_type,
                        'file_type': 'application/' + fna_type,
                        'type': 'binary'
                        }
                    attachment = self.env['ir.attachment'].sudo().create(data_attach)
                    url = self.env['ir.config_parameter'].get_param('web.base.url') + '/web/binary/saveas?model' \
                                                            '=ir.attachment&field=datas&filename_field=name&id=' + \
                                                            str(attachment.id)
                    file_path = attachment._get_path(url)[0].split("/")
                    folder = file_path[0]
                    doc = file_path[1]
                    sftp.get(fname, doc)
                    info = open(doc, "r").read()
                    p = config['data_dir']
                    db = self.env.cr.dbname
                    path = p + '/filestore/' + db + '/'
                    dest = path + folder + '/'
                    final_path = dest + doc

                    shutil.move(doc, final_path)
                    sftp.remove(fname)
                    self.env['ir.attachment'].sudo().search([('id', '=', attachment.id)]).\
                        write({'store_fname': attachment._get_path(url)[0]})
                else:
                    doc = fname
                    sftp.get(fname, doc)
                    info = open(doc, "r").read()
                    sftp.remove(fname)

                dct = 'Se genera la lectura del archivo ' + fname + ' y se adjunta al documento %s, ' \
                                                                    'sin novedad.' % inv[0][1]
                self._create_ei_order_log(inv[0][0], fname, 'log'+fna[-1], 'ak', dct, info, 'close', 'ack_cus',
                                          ol_nam=inv[0][1])
                self.env.cr.execute("UPDATE account_invoice SET ei_state='ack_cus' WHERE id=%s" % inv[0][0])
                self.env.cr.commit()
            sftp.close()
            transport.close()

    @api.multi
    def ei_read_decision_folder(self):
        company = self.env.user.company_id
        if company.electronic_invoice and company.ei_database == self._cr.dbname:
            transport = self._sftp_connect(company, u'Aceptación/Rechazo', company.ei_decision_folder)
            if not transport:
                return
            sftp, transport = transport[0], transport[1]

            files = sftp.listdir()
            if self:
                files = filter(lambda x: self.number.replace('/', '').replace('-', '') in x, files)

            dinv = {}
            att_xml = company.attach_invoice_xml
            for fname in files:
                fna = re.split('[_.]+', fname)
                fna_type = fna[-1]
                if fna_type != 'xml':
                    continue
                i_n = [x for x in fna if x in dinv]
                if i_n:
                    inv = dinv[i_n[0]]
                else:
                    self.env.cr.execute("SELECT id,number FROM account_invoice WHERE number in %s AND ei_state in"
                                        "('supplier_accep','dian_accep','ack_cus')" % str(tuple([str(x) for x in fna[:-1]])))
                    inv = self.env.cr.fetchall()
                    if len(inv) > 1:
                        raise Warning('Se encontró mas de una referencia para el documento %s, por favor validar'
                                      % fname)
                    if not inv:
                        continue
                if att_xml:
                    data_attach = {
                        'name': fname,
                        'datas_fname': fname,
                        'res_model': 'account.invoice',
                        'res_id': inv[0][0],
                        'mimetype': 'application/' + fna_type,
                        'file_type': 'application/' + fna_type,
                        'type': 'binary'
                        }
                    attachment = self.env['ir.attachment'].sudo().create(data_attach)
                    url = self.env['ir.config_parameter'].get_param('web.base.url') + '/web/binary/saveas?model' \
                                                            '=ir.attachment&field=datas&filename_field=name&id=' + \
                                                            str(attachment.id)
                    file_path = attachment._get_path(url)[0].split("/")
                    folder = file_path[0]
                    doc = file_path[1]
                    sftp.get(fname, doc)
                    info = open(doc, "r").read()
                    p = config['data_dir']
                    db = self.env.cr.dbname
                    path = p + '/filestore/' + db + '/'
                    dest = path + folder + '/'
                    final_path = dest + doc

                    shutil.move(doc, final_path)
                    sftp.remove(fname)
                    self.env['ir.attachment'].sudo().search([('id', '=', attachment.id)]).\
                        write({'store_fname': attachment._get_path(url)[0]})
                else:
                    doc = fname
                    sftp.get(fname, doc)
                    info = open(doc, "r").read()
                    sftp.remove(fname)

                inv_st = 'cus_rejec' if 'REJECTED' in info else 'cus_accep'
                dct = 'Se genera la lectura del archivo ' + fname + ' y se adjunta al documento %s, ' \
                                                                    'sin novedad.' % inv[0][1]
                self._create_ei_order_log(inv[0][0], fname, 'log'+fna[-1], 'ds', dct, info, 'close', inv_st,
                                          ol_nam=inv[0][1])
                self.env.cr.execute("UPDATE account_invoice SET ei_state='%s' WHERE id=%s" % (inv_st,
                                                                                              inv[0][0]))
                self.env.cr.commit()
            sftp.close()
            transport.close()

    @api.multi
    def ei_account_invoice_documents(self):
        if self.env.user.company_id.ei_database == self._cr.dbname:
            self.ei_automatic_acceptance()
            self.ei_read_error_folder()
            self.ei_read_voucher_folder()
            self.ei_read_dian_result_folder()
            self.ei_read_ack_folder()
            # self.ei_read_decision_folder()
        else:
            raise Warning('No es posible realizar esta acción, verifique la Base de Datos de Facturación Electrónica '
                          'configurada en la Compañía')

    @api.multi
    def action_cancel(self):
        if self.env.user.company_id.electronic_invoice and self.type != 'in_invoice' and \
                self.state in ['open', 'paid'] and self.ei_state != 'pending' and\
                    self.ei_order_log_ids and self.ei_state not in ['dian_rejec', 'supplier_rejec']:
            raise Warning(u'Esta Factura No Puede ser Cancelada, debido a que el tercero %s tiene activa la politica '
                          u'de Facturacion Electrónica y la Factura %s ya tiene generado el archivo XML de Factura '
                          u'Electrónica.' % (self.partner_id.name, self.number))
        return super(AccountInvoice, self).action_cancel()

    @api.multi
    def action_number(self):
        today = datetime.today().strftime('%Y-%m-%d')
        vat_excempted_products = []
        for line in self.invoice_line:
            vat_excemption_config = self.env['vat.excemption.products.config'].search(
                [('products_ids', '=', line.product_id.id)]
            ).filtered(
                lambda vat_conf: (self.date_invoice or today)  in [
                    conf.name for conf in vat_conf.excempted_days_ids]
            )
            vat_tax = line.invoice_line_tax_id.filtered(
                        lambda tax: 0.19 == tax.amount and 'iva' in tax.name.lower()
                    )
            if vat_excemption_config and vat_tax:
                vat_excempted_products.append(line.product_id.name)
        if vat_excempted_products:
            raise Warning(
                "Se encontraron productos excentos por dia sin IVA, por favor actualizar los impuestos: "
                + ", ".join(vat_excempted_products)
            )
        res = super(AccountInvoice, self).action_number()
        if self.type not in ('in_invoice', 'in_refund') and self.company_id.xml_automatic_generation and \
                self.journal_id.invoice_prefix and self.journal_id.ei_start_date:
            self._gen_xml_invoice()
        return res


class AccountInvoiceRefund(models.TransientModel):
    _inherit = 'account.invoice.refund'

    @api.multi
    def invoice_refund(self):
        res = super(AccountInvoiceRefund, self).invoice_refund()
        inv_orig = self.env['account.invoice'].browse(self._context['active_id'])
        invoices = res['domain'][1][2]
        for inv in self.env['account.invoice'].browse(invoices):
            if hasattr(inv, 'n_oc') and inv_orig:
                inv.n_oc = getattr(inv_orig, 'n_oc', None)
        return res
