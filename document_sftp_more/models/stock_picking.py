# -*- coding: utf-8 -*-

from openerp import models, fields, api
import xlsxwriter
from openerp.exceptions import Warning
import xlwt


class stock_picking(models.Model):
    _inherit = 'stock.picking'

    sftp_receive_id = fields.Many2one('sftp.more', 'SFTP Recibidos', copy=False)
    sftp_send_id = fields.Many2one('sftp.more', 'SFTP Enviados', copy=False)
    bool_receive = fields.Boolean('Leido', copy=False)
    bool_send = fields.Boolean('Escrito', copy=False)
    # Log de info
    log_sftp = fields.Text('Log SFTP', copy=False)
    log_sftp_send = fields.Text('Log SFTP Enviado', copy=False)
    log_sftp_receive = fields.Text('Log SFTP Recibido', copy=False)
    # Bool dinamico
    bool_show = fields.Boolean('Mostrar', copy=False)
    # Fecha de entrega 
    scheduled_time_ol = fields.Datetime('Fecha de entrega OL', default=fields.Datetime.now())

    @api.multi
    def sftp_document(self):
        sp_file = self.document_name()
        sale = self.name_sale()
        log_sftp_send = 'Cantidad Enviada: '
        wb = xlwt.Workbook()
        ws = wb.add_sheet('A Sheet')
        if self.picking_type_id.sftp_type in ('incoming', 'return'):
            header = ['ID Cliente',	'Tipo de Factura',	'Orden del cliente', 'Codigo de Producto', 
                      'Estatus de Recibo',	'Cantidad Esperada', 'Cliente que devuelve', 'Documento1', 
                      'Documento 2 (PO, Lote Proveedor)', 'Proveedor Cliente']
        elif self.picking_type_id.sftp_type == 'outgoing':
            header = ['ID Cliente', 'Tipo de Factura', 'Orden de Despacho del Cliente', 'Direccion Destinatario',
                      'Ciudad - Departamento', 'Telefono Destinatario', 'Nombre Destinatario', 'Codigo de Producto',
                      'Numero de Lote', 'Estado de Inventario', 'Cantidad Ordenada', 'Fecha de Entrega AAAAMMDDHHSS',
                      'Clasificador', 'Documento1', 'Documento2']
        else:
            header = ['Cliente', 'Producto', 'Estado origen', 'Estado Final', 'Cantidad']
        for i, l in enumerate(header):
            ws.write(0, i, l)
        count = 0
        for k, p in enumerate(self.move_lines):
            sheet = []
            if self.picking_type_id.sftp_type in ('incoming', 'return'):
                if p.product_id.type == 'product':
                    type_stock = 'REMISION' if self.picking_type_id.sftp_type == 'incoming' else 'DEVOLUCION'
                    partner_stock = self.partner_id.display_name if self.picking_type_id.sftp_type == 'return' else ''
                    supplier_stock = self.partner_id.display_name if self.picking_type_id.sftp_type == 'incoming' else ''
                    sheet = ['MOREPRODUCTS', type_stock, self.origin, p.product_id.default_code, p.location_dest_id.state_dlx,
                            p.product_uom_qty, partner_stock, '', '', supplier_stock]
                    code = p.product_id.default_code or '' 
                    log_sftp_send += '\n' + '[' + code + '] ' + p.product_id.name + ': ' + str(p.product_uom_qty)
            elif self.picking_type_id.sftp_type == 'outgoing':
                qty = p.quant_qty()
                if qty > 0:
                    date = p.date_more()
                    carrier = p.picking_id.carrier_id.partner_id.name if p.picking_id.carrier_id else ''
                    sheet = ['MOREPRODUCTS', 'FACTURA', sale, p.partner_id.street, p.partner_name(),
                            p.partner_id.phone, p.partner_id.display_name, p.product_id.default_code, p.lot_names(),
                            p.location_id.state_dlx, qty, date, carrier, '', '']
                    code = p.product_id.default_code or '' 
                    log_sftp_send += '\n' + '[' + code + '] ' + p.product_id.name + ': ' + str(qty)
            else:
                sheet = ['MOREPRODUCTS', p.product_id.default_code, p.location_id.state_dlx, p.location_dest_id.state_dlx, p.product_uom_qty]
                code = p.product_id.default_code or '' 
                log_sftp_send += '\n' + '[' + code + '] ' + p.product_id.name + ': ' + str(p.product_uom_qty)
            if sheet:
                for i, l in enumerate(sheet):
                    if not l:
                        l = ''
                    ws.write(count + 1, i, l)
                count += 1
        self.log_sftp_send = log_sftp_send
        wb.save(sp_file)
        return sp_file

    @api.multi
    def picking_send(self):
        if self.bool_send:
            raise Warning(u'Este registro ya fue enviado a Blu')
        else:
            code = self.picking_type_id.sftp_type
            if code == 'outgoing':
                if self.state in ('draft', 'cancel', 'confirmed'):
                    raise Warning(u'Debe comprobar disponibilidad primero')
                else:
                    self.env['sftp.more'].sftp_send([self.id])
            elif code == 'internal':
                if self.state != 'done':
                    raise Warning(u'Debe transferir primero')
                else:
                    self.env['sftp.more'].sftp_send([self.id])
            else:
                self.env['sftp.more'].sftp_send([self.id])
        return True

    @api.multi
    def picking_receive(self):
        self.env['sftp.more'].action_receive()
        return True

    @api.multi
    def document_name(self):
        origin = self.origin or ''
        code = self.picking_type_id.sftp_type
        if code == 'incoming':
            return 'inbound_' + origin + '.xls'
        elif code == 'return':
            return 'inbound_dev_' + origin + '.xls'
        elif code == 'outgoing':
            return 'outbound_' + origin + '.xls'
        else:
            return 'change_state_' + str(self.id) + '.xls'
    
    @api.multi
    def name_sale(self):
        name = self.origin 
        if name:
            so = self.env['sale.order'].search([('name', '=', name)]) 
            if so:
                name = so.name + ' - ' + so.n_oc
        return name

    @api.multi
    def unlink(self):
        sent = self.filtered(lambda picking: picking.bool_send)
        if sent:
            raise Warning("No se puede eliminar registros enviados a Blu: %s"
                          % ', '.join(pick.name for pick in sent))
        return super(stock_picking, self).unlink()


class stock_location(models.Model):
    _inherit = 'stock.location'

    state_dlx = fields.Char('Estado DLX')


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    sftp_type = fields.Selection([('outgoing', "Ventas / DCompras"),  
                                  ('incoming', "Compras"), 
                                  ('internal', "Internas"), 
                                  ('return', "Devolucion ventas")], 'Tipo de interfaz', required=True)
