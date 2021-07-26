# -*- coding: utf-8 -*-

from openerp import models, fields, api
import xlsxwriter
import xlwt


class product_template(models.Model):
    _inherit = 'product.template'

    log_sftp = fields.Text('Log SFTP', copy=False)

class product_product(models.Model):
    _inherit = 'product.product'

    log_sftp = fields.Text('Log SFTP', copy=False)

    @api.model
    def create(self, vals):
        res = super(product_product, self).create(vals)
        res.sftp_send()
        return res

    @api.multi
    def sftp_send(self):
        if self.type == 'product':
            sm_obj = self.env['sftp.more']
            with sm_obj.sftp_connection('out') as (sftp, transport, directory):
                sp_file = self.sftp_document()
                sftp.put(sp_file, sp_file)


    @api.multi
    def sftp_document(self):
        code = self.code or self.name
        sp_file = 'matmass_' + code.replace(' ','_').replace('-','_') + '.xls'
        log_sftp = 'Enviado: ' + str(fields.Datetime.now()) + '\n' + 'Datos enviados: '
        wb = xlwt.Workbook()
        ws = wb.add_sheet('matmass')
        header = ['Codigo de Producto', 'ID Cliente', 'Codigo de Familia', 'Nivel de Identificacion de Carga',	
                  'El Producto Maneja Lote', 'Unidad de Medida para Almacenamiento', 'Status de Recibo', 
                  'Unidad de Medida de Reserva', 'Maneja Fecha de Vencimiento', 'Unidad de Medida Visible',	
                  'Unidad de Medida para Reporte', 'Descripcion del Producto', 'Maneja Documento1',	
                  'Maneja Documento2', 'Talla', 'Color', 'Codigo Origen Proveedor']
        for i, l in enumerate(header):
            ws.write(0, i, l)
        categ = self.division_id.name
        lot = self.check_track_more()
        uom = self.uom_id.name
        name = self.name
        sheet = [code, 'MOREPRODUCTS', categ, '', lot, uom, 'Disponible', uom, 'No', uom, uom, name,
                 'NO', 'NO', '', '', '']
        for i, l in enumerate(sheet):
            if not l:
                l = ''
            ws.write(1, i, l)
        log_sftp = log_sftp + '\n' + 'Codigo de Producto: ' + code + \
                   '\n' + 'Categoria: ' + categ + \
                   '\n' + 'Maneja lote: ' + lot + \
                   '\n' + 'Unidad de medida: ' + uom + \
                   '\n' + 'Nombre: ' + name
        self.log_sftp = log_sftp
        wb.save(sp_file)
        return sp_file

    @api.multi
    def check_track_more(self):
        if self.track_all:
            return 'SI'
        else:
            if self.track_incoming:
                return 'SI'
            elif self.track_outgoing:
                return 'SI'
            elif self.track_production:
                return 'SI'
            else:
                return 'NO'
