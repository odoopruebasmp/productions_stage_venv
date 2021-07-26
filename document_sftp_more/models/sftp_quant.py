# -*- coding: utf-8 -*-
import xlsxwriter
from openerp import models, fields, api, exceptions, _
import openerp.addons.decimal_precision as dp
from openerp.exceptions import ValidationError
from datetime import datetime, timedelta
import xlwt


class sftp_quant(models.Model):
    _name = 'sftp.quant'
    _order = 'id desc'

    name = fields.Char('Nombre', default=str(datetime.strptime(fields.Datetime.now(), "%Y-%m-%d %H:%M:%S")
                    - timedelta(hours=5)), readonly=True)
    user_id = fields.Many2one('res.users', 'Usuario', default=lambda self: self.env.user, readonly=True)
    company_id = fields.Many2one('res.company', 'Compañia', readonly=True)
    sftp_line = fields.One2many('sftp.quant.line', 'sftp_id', 'Lineas', readonly=True)
    bool_product = fields.Boolean('Producto', readonly=True)
    bool_location = fields.Boolean('Ubicacion', readonly=True)
    bool_send = fields.Boolean('Enviado', readonly=True)

    @api.multi
    def copy(self):
        raise ValidationError("Este documento no puede ser duplicado")

    @api.multi
    def action_send(self):
        if self.bool_send:
            raise ValidationError("Este documento fue enviado el %s" % self.name)
        sftp_obj = self.env['sftp.more']
        with sftp_obj.sftp_connection('out') as (sftp, transport, directory):
            sp_file = self.sftp_document()
            sftp.put(sp_file, sp_file)
            self.bool_send = True
        return True

    @api.multi
    def sftp_document(self):
        sp_file = 'stock_compare_' + str(self.id) + '.xls'
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Stock compare')
        header = ['Cliente', 'Producto', 'Estado', 'Cantidad']
        for i, l in enumerate(header):
            ws.write(0, i, l)
        for k, p in enumerate(self.sftp_line):
            sheet = ['MOREPRODUCTS', p.product_id.default_code, p.location_id.state_dlx, p.qty]
            for i, l in enumerate(sheet):
                if not l:
                    l = ''
                ws.write(k + 1, i, l)
        wb.save(sp_file)
        return sp_file


class sftp_quant_line(models.Model):
    _name = 'sftp.quant.line'

    sftp_id = fields.Many2one('sftp.quant', 'SFTP')
    product_id = fields.Many2one('product.product', 'Producto')
    location_id = fields.Many2one('stock.location', 'Ubicacion')
    lot_id = fields.Many2one('stock.production.lot', 'Lote')
    qty = fields.Float('Cantidad', digits=dp.get_precision('Product Unit of Measure'))
    uom_id = fields.Many2one('product.uom', 'Unidad de medida')