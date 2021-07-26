# -*- coding: utf-8 -*-
from openerp import models, fields, api
from openerp.addons import decimal_precision as dp
from openerp.exceptions import Warning
from datetime import datetime
import os
from lxml import etree
import paramiko
import re


class IrCron(models.Model):
    _inherit = 'ir.cron'

    @api.multi
    def manual_read(self):
        model = self.model
        method = self.function
        eval("self.env['" + model + "']." + method + "()")


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.multi
    def _get_nov_loc(self):
        nov_loc = self.env['stock.location'].search([('name', '=', 'Novedades Avisos de Recibo')])
        return nov_loc

    receipt_notice = fields.Boolean('Avisos de Recibo', help='Gestión de Avisos de Recibo')
    # Avisos de recibo
    rn_read_folder = fields.Char('Lectura Aviso Recibo', help='Carpeta entrada de archivos de avisos de recibos que '
                                                               'validan las remisiones')
    rn_process_folder = fields.Char('Escritura Procesados', help='Carpeta salida documentos validados con la remisión '
                                                                 'del sistema')
    rn_error_folder = fields.Char('Escritura Erróneos', help='Carpeta salida documentos que presentan inconsistencias '
                                                             'con la remisión del sistema referenciada')
    stock_picking_id_key = fields.Many2one('ir.model.fields', 'LLave Recibo', domain=[('ttype', '=', 'char'),
                                           ('model_id.model', '=', 'stock.picking')], help='Campo Enlace entre la '
                                           'órden de entrega del Aviso de Recibo y la remisión del sistema')
    product_id_key = fields.Many2one('ir.model.fields', 'LLave Producto', domain=[('ttype', '=', 'char'),
                                     ('model_id.model', '=', 'product.product')], help='Campo Enlace entre el '
                                     'producto del Aviso de Recibo y el de la remisión del sistema')
    novelty_location_id = fields.Many2one('stock.location', 'Ubicación de Novedades', default=_get_nov_loc,
                                          help='Ubicación en la que serán creadas las Transferencias de novedades al '
                                               'pulsar botón de "Crear factura borrador" en las transferencias de '
                                               'inventario')
    # Servidor RN
    rn_sftp_url = fields.Char('Dirección', size=25, help='Dirección IP servidor Avisos de Recibo')
    rn_sftp_port = fields.Char('Puerto', size=4, help='Puerto para conexión SFTP en servidor de Avisos de Recibo')
    rn_sftp_user = fields.Char('Usuario', size=25, help='Usuario para conexión SFTP en servidor de Avisos de Recibo')
    rn_sftp_pwd = fields.Char('Contraseña', size=20, help='Contraseña para conexión SFTP en servidor de Avisos de '
                                                          'Recibo')
    rn_temporal_files = fields.Char('Dirección local transferencia', help='Directorio temporal de transferencia de '
                                                                          'archivos de AR en el servidor local')

    @api.multi
    def write(self, vals):
        res = super(ResCompany, self).write(vals)
        if self.ei_temporal_files == self.rn_temporal_files:
            raise Warning('Error de Parametrización. La ruta de la carpeta para los archivos locales de transferencia '
                          'de Avisos de Recibo no puede ser igual a la de Facturación Electrónica. Por favor validar.')
        return res


class ResPartner(models.Model):
    _inherit = 'res.partner'

    receipt_notice = fields.Boolean('Aviso de recibo', help="Marque el check si el cliente contará con avisos "
                                                            "de recibo para el proceso de Facturación Electrónica")
    cop_rn = fields.Boolean('Aviso de recibo COP', related='company_id.receipt_notice', readonly=True)


class StockMove(models.Model):
    _inherit = 'stock.move'

    received_amount = fields.Float('Cantidad Recibida', digits=dp.get_precision('Product Unit of Measure'),
                                 readonly=True, help="Cantidad recibida indicada en el documento de acuse de recibo y "
                                 "que se tendra en cuenta para la generacion de la factura de venta.", copy=False)
    novelty_amount = fields.Float('Novedad', digits=dp.get_precision('Product Unit of Measure'), readonly=True,
                                  help="Es la cantidad que registra el sistema como enviada 'product_qty', menos la "
                                  "cantidad recibida indicada en el documento de acuse de recibo. Cantidad Enviada - "
                                  "Cantidad Recibida", copy=False)
    novelty_state = fields.Selection([('pending', 'Pendiente'), ('in_progress', 'En Progreso'), ('done', 'Resuelto')],
                                     string='Estado Novedad', readonly=True, copy=False)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(StockMove, self).fields_view_get(
                view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            if 'default_picking_id' in self._context and self._context['default_picking_id']:
                p_id = self._context['default_picking_id']
                self.env.cr.execute('SELECT novelty_state FROM stock_move WHERE picking_id = %s' % p_id)
                nov_stt = self.env.cr.fetchone()
                if not (nov_stt and nov_stt[0]):
                    res['arch'] = res['arch'].replace('Novedad">', 'Novedad" invisible="1" modifiers="{&quot;invisible'
                                                                       '&quot;: true}">')
            else:
                res['arch'] = res['arch'].replace('Novedad">', 'Novedad" invisible="1" modifiers="{&quot;invisible'
                                                               '&quot;: true}">')

        if view_type == 'tree':
            if not self.env.user.company_id.receipt_notice and 'received_amount' in res['arch']:
                doc = etree.XML(res['arch'])
                for f in ['received_amount', 'novelty_amount']:
                    doc.remove(doc.xpath("//field[@name='%s']" % f)[0])
                for b in ['change_move_nov_state', 'change_move_nov_state']:
                    doc.remove(doc.xpath("//button[@name='%s']" % b)[0])
                res['arch'] = etree.tostring(doc)
        return res


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    novelty_picking_type_id = fields.Many2one('stock.picking.type', 'Tipo de Nota de Entrega para las Novedades',
                                              help='Generadas al leer el txt de factura electrónica en las '
                                                   'transferencias de inventario')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.multi
    def _create_ei_order_log(self, info, logs, name_file, datet, msg, deliv_order, st, recadv, dst, company, sftp, fname):
        dlog = {
            'data': info,
            'type_doc': 'rn',
            'name_file': name_file,
            'transaction_date': datet,
            'description': msg + deliv_order,
            'type_log': 'txt',
            'state': st,
            'name': deliv_order,
            'document_state': dst
            }
        if logs:
            dlog['picking_id'] = logs
        if not msg:
            p = deliv_order.find('--')
            dlog['description'] = deliv_order[:p]
            dlog['name'] = deliv_order[p:]
        self.env['ei.order.log'].sudo().create(dlog)
        if dst != 'done' and recadv:  # TODO
            recadv.close()
            sftp.chdir()
            error_folder = company.rn_error_folder if company.rn_error_folder[:-1] == '/' else \
                company.rn_error_folder + '/'
            sftp.put(fname, error_folder + name_file)

    electronic_invoice = fields.Boolean('Factura Electronica', related='partner_id.electronic_invoice', readonly=True)
    receipt_notice = fields.Char('Aviso de Recibo', copy=False, readonly=True, help="Aviso de Recibo "
                                    "correspondiente a la recepción de productos por parte del cliente.")
    recadv_file = fields.Char('Archivo Recadv', copy=False, readonly=True, help="Nombre del Archivo Recadv")
    document_date = fields.Datetime('Fecha Documento', readonly=True, help="Fecha del documento", copy=False)
    delivery_order = fields.Char('N° Orden de Entrega', copy=False, readonly=True, help="Número de la orden "
                                        "de entrega, correspondiente a la orden de venta")
    cust_accep_number = fields.Char('Número Aceptación', copy=False, readonly=True, help="Número de Aceptación "
                                                                                                   "del Cliente")
    order_lines = fields.Integer('Líneas de Pedido', copy=False, readonly=True, help="Cantidad de lineas de "
                                                                                            "Pedido")
    transaction_date = fields.Datetime('Fecha Transacción', readonly=True, help="Fecha de Captura de datos del "
                                                                                "Documento Recadv", copy=False)
    rn_transaction_status = fields.Selection([('done', 'Transferido'), ('pending', 'No Transferido')],
                                             string='Estado Aviso Recibo', index=True, default="pending", help='Estado '
                                             'del Log del Aviso de recibo asociado a esta transferencia', copy=False)
    rn_order_log_ids = fields.One2many('ei.order.log', 'picking_id', string='Logs AR')
    novelty_id = fields.Many2one('stock.picking', 'Documento Novedad', readonly=True)
    novelty_state = fields.Selection([('cancel', 'Cancelado'), ('open', 'Abierto'), ('done', 'Resuelto')],
                                     string='Estado Novedad', readonly=True, copy=False)
    refund_document_id = fields.Many2one('stock.picking', 'Documento Reintegro', readonly=True, help='Transferencia de'
                                        ' inventario con la que se reintegró la mercancía producto de esta novedad')

    @api.multi
    def ei_stock_picking_recadv(self):
        cp = self.env.user.company_id
        cp_elect_inv = cp if cp.electronic_invoice and cp.receipt_notice else []
        for company in cp_elect_inv:
            stock_picking_key = company.stock_picking_id_key.name
            product_key = company.product_id_key.name
            r_host = company.rn_sftp_url
            r_user = company.rn_sftp_user
            r_pwd = company.rn_sftp_pwd
            r_port = int(company.rn_sftp_port)
            # noinspection PyTypeChecker
            transport = paramiko.Transport((r_host, r_port))
            try:
                transport.connect(username=r_user, password=r_pwd)
            except paramiko.AuthenticationException:
                raise Warning('Error de Autenticación en conexión a servidor de Avisos de Recibo, por favor validar '
                              'credenciales')
            sftp = paramiko.SFTPClient.from_transport(transport)
            re_path = company.rn_read_folder
            try:
                sftp.chdir(re_path)
            except IOError:
                raise Warning(u"Error en conexión a Ruta de lectura de Avisos de Recibo, '%s'. Revisar parametrización "
                              u"en Compañía o existencia de carpeta en el servidor local" % re_path)
            try:
                os.chdir(company.rn_temporal_files)
            except IOError:
                raise Warning(u"Error en conexión a Ruta local de transferencia de AR, '%s'. Revisar parametrización "
                              u"en Compañía o estado servidor SFTP" % company.rn_temporal_files)
            files = sftp.listdir()
            if self:
                if self.receipt_notice and self.rn_transaction_status == 'done':
                    raise Warning('Esta transferencia ya tiene un Aviso de Recibo asociado, y el estado del Log es '
                                  'Transferido, por favor validar.')
                if any('service' == x.product_id.type for x in self.move_lines):
                    raise Warning('No es posible leer avisos de recibo para transferencias que incluyan productos de '
                                  'tipo Servicio. Por favor validar')
                b = False
                pk = eval("self." + stock_picking_key)
                for fname in files:
                    # Move to temporal path
                    sftp.get(fname, fname)
                    recadv = open(fname, "r")
                    info = recadv.read()
                    dev_ord = re.search("ON:" + pk, info)
                    if dev_ord:
                        files = [fname]
                        os.remove(fname)
                        b = True
                        break
                    os.remove(fname)
                if not b:
                    msg = u'El sistema no logró encontrar una coincidencia para la referencia '
                    self._create_ei_order_log("", False, "", datetime.now(), msg, pk,
                                           'open', None, 'pending', company, sftp, None)
                    sftp.close()
                    transport.close()
                    return True
            re_path = company.rn_read_folder
            pc_path = company.rn_process_folder
            for fname in files:
                # Move to temporal path
                sftp.chdir()
                sftp.chdir(re_path)
                sftp.get(fname, fname)
                recadv = open(fname, "r")
                info = recadv.read()

                # Receipt Notice
                if 'RECADV' not in info:
                    continue
                rec_not = re.search("BGM\+352::9\+(.*)\+9'", info).group(1)
                if len(rec_not) > 15:
                    rec_not = re.search("BGM\+352::9\+(.*)\+9'DTM", info).group(1)
                date_rn = (re.search("DTM\+137:(.*):102'D", info) or re.search("DTM\+137:(.*):203'D", info))
                try:
                    date_rn = datetime.strptime(date_rn.group(1), '%Y%m%d')  # Date RN
                except ValueError:
                    date_rn = datetime.strptime(date_rn.group(1), '%Y%m%d%H%M%S')
                deliv_order = re.search("ON:(.*)'\RFF\+AAJ", info).group(1)  # Delivery order number
                cust_accept = re.search("AIJ:(.*)'NAD\+BY", info)  # Customer acceptance number
                if cust_accept:
                    cust_accept = cust_accept.group(1)
                datet = datetime.now()
                pickings = self.env['stock.picking'].search([(stock_picking_key, '=', deliv_order)])
                if pickings:
                    pickings = pickings.filtered(lambda p: p.state == 'done' and p.rn_transaction_status == 'pending')
                    if not pickings:
                        msg = u'El sistema no logró encontrar al menos una Remisión, en Estado Transferido y ' \
                              'pendiente para lectura de Aviso de Recibo'
                        self._create_ei_order_log(info, False, fname, datet, msg, deliv_order,
                                               'open', recadv, 'pending', company, sftp, fname)
                        continue
                    for picking in pickings:
                        sp_lines = info.find("LIN+")
                        if sp_lines != -1:
                            sp_lines = info.split("LIN+")
                            sp_lines = sp_lines[1:]
                            log = ''
                            novelty = False
                            b = False
                            moves = []
                            for sp_line in sp_lines:
                                item_id = re.search("\+\+(.*):EN", sp_line) or re.search("\+\+(.*):UP", sp_line)
                                item_id = item_id.group(1)
                                if ':EN' in item_id:
                                    item_id = item_id[:item_id.index(':')]
                                # item_name = re.search("\+\+:::(.*)'\QTY\+194:", sp_line).group(1)
                                if 'QTY+194' in sp_line:
                                    received_amount = re.search("QTY\+194:(.*)", sp_line)
                                    received_amount = float(received_amount.group(1)[:received_amount.group(1).
                                                            index(':')])
                                else:
                                    received_amount = 0.0
                                self.env.cr.execute("SELECT id FROM product_product WHERE %s = '%s'" % (product_key,
                                                                                                        item_id))
                                product_id = self.env.cr.fetchall()
                                product_id = [x[0] if x else None for x in product_id]
                                if not product_id:
                                    novelty = True
                                    log += 'El sistema no logra encontrar un producto con la referencia ' + \
                                           item_id
                                    continue
                                if len(product_id) > 1:
                                    novelty = True
                                    log += 'El sistema encontro mas de un producto con la referencia ' + \
                                         item_id + ' por favor verificar la configuracion de los productos'
                                    continue
                                self.env.cr.execute("SELECT id,product_qty FROM stock_move WHERE product_id = %s AND "
                                                    "picking_id = %s" % (product_id[0], picking.id))
                                move = self.env.cr.fetchall()
                                if not move:
                                    novelty = True
                                    log += 'El sistema no logra encontrar un movimiento con la referencia ' + \
                                         item_id + ' en el picking ' + picking.name
                                    continue
                                if len(move) > 1:
                                    novelty = True
                                    log += 'El sistema encontro mas de un movimiento para la referencia ' + \
                                           item_id + ' en el picking ' + picking.name + ' por favor verificar la orden.'
                                    continue
                                self._cr.execute("UPDATE stock_move SET received_amount = %s, novelty_amount = %s "
                                                 "WHERE id = %s" % (received_amount, move[0][1] - received_amount,
                                                                    move[0][0]))
                                moves.append(move[0][0])
                                b = True
                            if b and novelty:
                                deliv_order = log + '--' + deliv_order
                                self._create_ei_order_log(info, picking.id, fname, datet, '', deliv_order,
                                                       'open', recadv, 'done', company, sftp, fname)
                                picking.write({
                                    'rn_transaction_status': 'done',
                                    'transaction_date': datet,
                                    'receipt_notice': rec_not,
                                    'cust_accep_number': cust_accept,
                                    'document_date': date_rn,
                                    'delivery_order': deliv_order,
                                    'recadv_file': fname,
                                    'order_lines': len(sp_lines)
                                    })
                                self._cr.execute("UPDATE stock_move SET novelty_amount = -product_qty "
                                                 "WHERE received_amount = 0 AND picking_id = %s" % picking.id)
                                continue
                            if not b:
                                msg = 'El sistema no logro encontrar ninguna coincidencia para la referencia, ' \
                                      'por favor validar el recadv vs el pedido. Picking '
                                self._create_ei_order_log(info, False, fname, datet, msg, deliv_order,
                                                       'open', recadv, 'pending', company, sftp, fname)
                                picking.write({
                                    'rn_transaction_status': 'pending',
                                    'transaction_date': datet,
                                    'receipt_notice': rec_not,
                                    'cust_accep_number': cust_accept,
                                    'document_date': date_rn,
                                    'delivery_order': deliv_order,
                                    'recadv_file': fname,
                                    'order_lines': len(sp_lines)
                                    })
                                self._cr.execute("UPDATE stock_move SET received_amount = 0, "
                                                 "novelty_amount = -product_qty WHERE received_amount = 0 AND "
                                                 "picking_id = %s" % picking.id)
                                continue
                        self._cr.execute("UPDATE stock_move SET received_amount = 0, novelty_amount = -product_qty "
                                         "WHERE received_amount = 0.0 AND picking_id = %s" % picking.id)
                        picking.write({
                            'rn_transaction_status': 'done',
                            'transaction_date': datet,
                            'receipt_notice': rec_not,
                            'cust_accep_number': cust_accept,
                            'document_date': date_rn,
                            'delivery_order': deliv_order,
                            'recadv_file': fname,
                            'order_lines': len(sp_lines)
                            })
                        msg = 'El acuse de recibo coincide con el numero de referencia '
                        self._create_ei_order_log(info, picking.id, fname, datet, msg, deliv_order,
                                                  'close', recadv, 'done', company, sftp, fname)
                        sftp.remove(fname)
                        sftp.chdir()
                        sftp.chdir(pc_path)
                        sftp.put(fname, fname)
                else:
                    msg = u'El sistema no logró encontrar una coincidencia para la referencia '
                    self._create_ei_order_log(info, False, fname, datet, msg, deliv_order,
                                           'open', recadv, 'pending', company, sftp, fname)
                    continue
                self.env.cr.commit()  # Por el movimiento de archivos
            sftp.close()
            transport.close()
        return True
