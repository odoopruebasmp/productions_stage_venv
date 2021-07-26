# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from openerp import models, fields, api
from openerp.exceptions import Warning
from contextlib import contextmanager
import tempfile
import paramiko
import pandas
import math
import os
import logging
_logger = logging.getLogger(__name__)


class ftp_more(models.Model):
    _name = 'sftp.more'
    _order = 'name'

    name = fields.Datetime(
        'Nombre',
        default=str(datetime.strptime(fields.Datetime.now(), "%Y-%m-%d %H:%M:%S")
                    - timedelta(hours=5)),
        readonly=True
    )
    user_id = fields.Many2one('res.users', 'Usuario',
                              default=lambda self: self.env.user, readonly=True)
    date = fields.Date('Fecha', default=fields.Date.today(), readonly=True)
    type = fields.Selection([('receive', 'Recibir'), ('send', 'Enviar')], 'Tipo',
                            help='*Recibir, verifica y actualiza los picking de acuerdo a las cantidades segun Blue. '
                                 '*Enviar, envia los pickings a Blue')
    filter = fields.Selection([('assigned', 'Listo para transferir'),
                               ('confirmed', 'Esperando disponibilidad'),
                               ('draft', 'Borrador'),
                               ('partially_available', 'Parcialmente disponible')], 'Filtro estado',
                              help='Se filtratan los pickings de aceurdo al estado seleccionado')
    filter2 = fields.Selection([('incoming', 'Incoming'),
                                ('internal', 'Internal'),
                                ('outgoing', 'Outgoing'),
                                ('return', 'Return')], 'Filtro tipo',
                               help='Se filtratan los pickings de aceurdo al tipo seleccionado')
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Terminado')], 'Estado', default='draft', readonly=True,
                             copy=False)
    picking_receives = fields.One2many(
        'stock.picking', 'sftp_receive_id', readonly=True)
    picking_sends = fields.One2many(
        'stock.picking', 'sftp_send_id', readonly=True)

    @api.multi
    def _sftp_connect(self, type_op):
        try:
            os.chdir('/tmp')
        except (IOError, OSError):
            raise Warning(u'Error en conexión a Ruta temporal de escritura')
        if type_op == 'in':
            directory = tempfile.mkdtemp('in')
            try:
                os.chdir(directory)
            except OSError:
                raise Warning(
                    u'No se pudo conectar a la carpeta temporal de entrada')
        else:
            directory = tempfile.mkdtemp('out')
            try:
                os.chdir(directory)
            except OSError:
                raise Warning(
                    u'No se pudo conectar a la carpeta temporal de salida')
        r_host = 'sftpmore.blulogistics.net'
        r_user = 'sftp_more'
        r_pwd = 'Bl5M4r22019+'
        r_port = 22
        # noinspection PyTypeChecker
        transport = paramiko.Transport((r_host, r_port))
        try:
            transport.connect(username=r_user, password=r_pwd)
        except paramiko.AuthenticationException:
            transport.close()
            raise Warning(u'Error de Autenticación en conexión a servidor')
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            if type_op == 'in':
                sftp.chdir('/TEST/OUT')
            else:
                sftp.chdir('/TEST/IN')
        except (IOError, OSError):
            sftp.close()
            raise Warning(u'Error en conexión a Ruta de lectura')
        return sftp, transport, directory

    @contextmanager
    def sftp_connection(self, type_op):
        sftp, transport, directory = self._sftp_connect(type_op)
        try:
            yield (sftp, transport, directory)
        finally:
            sftp.close()
            transport.close()

    @api.multi
    def action_confirm(self):
        if self.type == 'receive':
            self.action_receive()
            self.state = 'done'
        else:
            self.action_send()
            self.state = 'done'
        return True

    @api.multi
    def action_send(self):
        domain = [('state', '=', self.filter), ('picking_type_id.sftp_type',
                                                '=', self.filter2), ('bool_send', '=', False)]
        pickings = self.env['stock.picking'].search(domain, limit=9)
        picking_ids = [x.id for x in pickings]
        self.sftp_send(picking_ids)

    @api.model
    def action_receive_cron(self):
        _logger.info('ACCION PROGRAMADA: LEER DOCUMENTOS SFTP')
        self.action_receive()

    @api.multi
    def action_receive(self):
        self._cr.execute("DELETE FROM picking_move_product")
        with self.sftp_connection('in') as (sftp, transport, directory):
            origins = ()
            origins_per_doc = {}
            backup = []
            for doc in sftp.listdir():
                sftp.get(doc, doc)
                try:
                    data = pandas.read_excel(doc)
                    backup.append(doc)
                    print('Good', doc)
                except Exception as e:
                    print('Bad', doc, e)
                    continue
                values = data.values
                doc_origins = ()
                for value in values:
                    len_val = len(value)
                    if len_val == 16:
                        origin = value[2].split(' - ')
                        origins = origins + (origin[0],)
                        value = {'picking_id': origin[0],
                                 'move_id': value[7],
                                 'qty': str(value[-1]),
                                 'type_id': 'outgoing'}
                        self.env['picking.move.product'].create(value)
                    if len_val == 11:
                        origins = origins + (value[2],)
                        value = {'picking_id': value[2],
                                 'move_id': value[3],
                                 'qty': str(value[-1]),
                                 'type_id': 'incoming'}
                        self.env['picking.move.product'].create(value)
                    if len_val == 6:
                        origins = origins + (value[2],)
                        value = {'picking_id': value[2],
                                 'move_id': value[1],
                                 'qty': str(value[-1]),
                                 'type_id': 'internal'}
                        self.env['picking.move.product'].create(value)
                    doc_origins += origins
                origins_per_doc[doc] = tuple(sorted(set(doc_origins)))
            received = self.sftp_receive(origins)
            if received:
                to_backup = filter(
                    lambda d: d in backup and self.env['stock.picking'].search(
                        [
                            ('origin', 'in', origins_per_doc[d]),
                            ('bool_receive', '=', True),
                            ('state', 'in', ('done',))
                        ]),
                    os.listdir(directory)
                )
                sftp.chdir('/TEST/BKUP')
                for doc in to_backup:
                    sftp.put(doc, doc)
                sftp.chdir('/TEST/OUT')
                for doc in to_backup:
                    sftp.remove(doc)
        sp = self.env['stock.picking'].search(
            [('state', '=', 'done'), ('date_done', '=', False)])
        sp.write({'date_done': str(datetime.strptime(
            fields.Datetime.now(), "%Y-%m-%d %H:%M:%S") - timedelta(hours=5))})

    @api.multi
    def sftp_send(self, pickings):
        with self.sftp_connection('out') as (sftp, transport, directory):
            for picking in self.env['stock.picking'].browse(pickings):
                sp_file = picking.sftp_document()
                sftp.put(directory+'/'+sp_file, sp_file)
                picking.bool_send = True
                picking.sftp_send_id = self.id
                picking.log_sftp = str(datetime.strptime(fields.Datetime.now(
                ), "%Y-%m-%d %H:%M:%S") - timedelta(hours=5)) + ': Enviado correctamente'
        return True

    @api.multi
    def sftp_receive(self, origins):
        pmp_obj = self.env['picking.move.product']
        sp_obj = self.env['stock.picking']
        sl_obj = self.env['stock.location']
        std_obj = self.pool['stock.transfer_details']
        stdi_obj = self.pool.get('stock.transfer_details_items')
        for sl in sl_obj.search([('name', '=', 'Novedades de compras')], limit=1):
            dest = sl.id
        pickings = sp_obj.search([('origin', 'in', origins), ('bool_receive', '=', False),
                                  ('state', 'not in', ('done', 'cancel'))])
        for picking in pickings:
            log_sftp_receive = 'Cantidad Recibida: '
            # Flag
            flag = False
            # State
            if picking.state == 'draft':
                picking.action_confirm()
            if picking.state == 'confirmed':
                picking.action_assign()
            if picking.state == 'partially_available':
                picking.rereserve_pick()
            # Wizard
            vals = {'picking_id': picking.id,
                    'item_ids': []}
            std = std_obj.create(self._cr, self._uid, vals, context=None)
            vals = {'transfer_id': std,
                    'date': str(datetime.strptime(fields.Datetime.now(), "%Y-%m-%d %H:%M:%S") - timedelta(hours=5))}
            # Moves
            product_qtys = {}
            for move_line in picking.move_lines:
                product_qtys[move_line.product_id.default_code] = product_qtys.get(
                    move_line.product_id.default_code, 0) + move_line.product_qty
            product_qtys_moved = {}
            for move_line in picking.move_lines:
                domain = [('picking_id', '=', picking.origin),
                          ('move_id', '=', move_line.product_id.default_code)]
                pmp = pmp_obj.search(domain)
                if not pmp:
                    continue
                float_qty = 0.0
                for qty in pmp:
                    if math.isnan(float(qty.qty)):
                        continue
                    float_qty += float(qty.qty)
                if float_qty > product_qtys.get(move_line.product_id.default_code, 0):
                    raise Warning('Se esta recibiendo mas de la cantidad enviada para el producto %s'
                                  % move_line.product_id.default_code)
                product_qtys_moved[move_line.product_id.default_code] = float_qty

            for move in picking.move_lines:
                if not move.bool_receive and move.state not in ('done', 'cancel'):

                    if round(product_qtys_moved.get(move.product_id.default_code, 0.0), 1) <= 0.0:
                        continue
                    # Flag
                    flag = True

                    # Wizard
                    # move.product_uom_qty = float_qty
                    moved_qty = min(move.product_qty, product_qtys_moved.get(move.product_id.default_code, 0))
                    vals.update({'product_id': move.product_id.id,
                                 'product_uom_id': move.product_uom_id.id,
                                 'quantity': moved_qty,
                                 'sourceloc_id': move.location_id.id,
                                 'destinationloc_id': move.location_dest_id.id})
                    product_qtys_moved[move.product_id.default_code] = product_qtys_moved.get(move.product_id.default_code, 0) - move.product_qty
                    stdi_obj.create(self._cr, self._uid,
                                    vals, context=None)
                    move.bool_receive = True
                    move.bool_transfer = True
                    name = move.product_id.default_code or ''
                    log_sftp_receive += '\n' + \
                        '[' + name + '] ' + move.product_id.name + \
                        ': ' + str(moved_qty)
            picking.sftp_receive_id = self.id
            picking.bool_receive = True
            if not picking.log_sftp:
                picking.log_sftp = str(
                    datetime.strptime(fields.Datetime.now(),
                                      "%Y-%m-%d %H:%M:%S")
                    - timedelta(hours=5)) + ': Recibido correctamente'
            else:
                picking.log_sftp = picking.log_sftp + '\n' + str(datetime.strptime(fields.Datetime.now(), "%Y-%m-%d %H:%M:%S") - timedelta(hours=5)) + \
                    ': Recibido correctamente'
            picking.log_sftp_receive = log_sftp_receive
            if flag:
                std_obj.browse(self._cr, self._uid, std).do_detailed_transfer()
            if picking.picking_type_id.sftp_type == 'incoming':
                domain = [('backorder_id', '=', picking.id),
                          ('state', 'not in', ('cancel', 'done'))]
                for partial in sp_obj.search(domain, limit=1):
                    for move in partial.move_lines:
                        move.write({'location_dest_id': dest})
        return True
