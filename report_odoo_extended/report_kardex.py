# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import xlsxwriter

from openerp import models, fields, api
import openerp.addons.decimal_precision as dp
from openerp.http import request
from openerp.addons.avancys_orm import avancys_orm


class StockReportKardexLine(models.Model):
    _name = 'stock.report.kardex.line'
    _order = "product_id,date desc"

    product_id = fields.Many2one('product.product', string="Producto")
    default_code = fields.Char(string='Referencia Interna')
    product_name = fields.Char(string='Descripcion')
    date = fields.Datetime(string='Fecha')
    location_id = fields.Char(string='Ubicacion Origen')
    location_dest_id = fields.Char(string='Ubicacion Destino')
    type_move = fields.Char(string='Tipo de movimiento')
    qty_start = fields.Float(string='Saldo Inicial', digits_compute=dp.get_precision('Product UoM'))
    qty = fields.Float(string='Interno', digits_compute=dp.get_precision('Product UoM'))
    qty_in = fields.Float(string='Entrada', digits_compute=dp.get_precision('Product UoM'))
    qty_out = fields.Float(string='Salida', digits_compute=dp.get_precision('Product UoM'))
    qty_end = fields.Float(string='Saldo Final', digits_compute=dp.get_precision('Product UoM'))
    cost_move = fields.Float(string='Costo Unitario Movimiento', digits=dp.get_precision('Account'))
    cost_total_move = fields.Float(string='Costo Total Movimiento', digits=dp.get_precision('Account'))
    cost_promedio = fields.Float(string='Costo Promedio', digits=dp.get_precision('Account'))
    cost_promedio_total = fields.Float(string='Costo Valorizado', digits=dp.get_precision('Account'))
    move_id = fields.Many2one('stock.move', string='Movimiento')
    name = fields.Char(string="Documento Referencia")
    origin = fields.Char(string="Documento Origen")


class StockReportKardexWizard(models.TransientModel):
    _name = 'stock.report.kardex.wizard'

    date_start = fields.Datetime(string='Fecha Inicial', required=True,
                                 default=datetime.now() - timedelta(days=datetime.now().day - 1) - timedelta(
                                     hours=datetime.now().hour - 5))
    date_end = fields.Datetime(string='Fecha Final', required=True, default=datetime.now())
    print_report = fields.Selection([('print', 'Excel'), ('analizar', 'Analizar')], string='Visualizacion',
                                    required=True, default='print')
    product_ids = fields.Many2many('product.product', string='Productos')
    location_ids = fields.Many2many('stock.location', string='Ubicaciones')
    title = fields.Char(string='titulos', default='REFERENCIA INTERNA, NOMBRE PRODUCTO, DOCUMENTO REFERENCIA , '
                                                  'DOCUMENTO ORIGEN, TIPO MOVIMIENTO, FECHA, UBICACION ORIGEN, '
                                                  'UBICACION DESTINO, SALDO INICIAL, ENTRADAS, INTERNOS, SALIDAS, '
                                                  'SALDO FINAL, COSTO UNITARIO MOVIMIENTO, COSTO TOTAL MOVIMIENTO, '
                                                  'COSTO PROMEDIO, VALORIZADO TOTAL')

    @api.multi
    def kardex_compute(self):
        location_obj = self.env['stock.location']
        move_obj = self.env['stock.move']
        dt_start = self.date_start
        dt_end = self.date_end

        # ELIMINANDO REGISTROS
        self._cr.execute(''' DELETE FROM stock_report_kardex_line''')

        if self.product_ids:
            product_list = self.product_ids
        else:
            product_list = self.env['product.product'].search([('type', '=', 'product'), ('is_asset', '=', False)])

        if self.location_ids:
            # noinspection PyProtectedMember
            location_ids = self.location_ids._ids
        else:
            location_ids = [x.id for x in location_obj.search([('usage', '=', 'internal'), '|', ('active', '=', True),
                                                               ('active', '=', False)])]
        location_ids = list(location_ids) + [0]

        for product in product_list:
            qty_in = qty_out = 0
            product_id = product.id
            default_code = product.default_code or 'Indefinido'
            product_name = product.name or 'Indefinido'

            self._cr.execute('''SELECT SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    location_dest_id in %s
                                    AND product_id = %s
                                    AND (date < %s AND state = 'done')''',
                             (tuple(location_ids), product.id, dt_start))
            result = self._cr.fetchall()
            for res in result:
                if isinstance(res[0], (list, tuple)):
                    qty_in = res[0][0] or 0.0
                else:
                    qty_in = res[0] or 0.0
            self._cr.execute('''SELECT SUM(product_qty)
                                FROM 
                                    stock_move
                                WHERE  
                                    location_id in %s
                                    AND product_id = %s
                                    AND (date < %s AND state = 'done')''',
                             (tuple(location_ids), product.id, dt_start))
            result = self._cr.fetchall()
            for res in result:
                if isinstance(res[0], (list, tuple)):
                    qty_out = res[0][0] or 0.0
                else:
                    qty_out = res[0] or 0.0

            qty_start = qty_in - qty_out

            # CALCULA MOVIMIENTOS EN EL PERIODO DADO
            move_ids = move_obj.search(
                ['|', ('location_id', 'in', location_ids), ('location_dest_id', 'in', location_ids),
                 ('product_id', '=', product.id), ('date', '>=', dt_start), ('date', '<=', dt_end),
                 ('state', '=', 'done')])

            if move_ids:
                sorted_lines = sorted(move_ids, key=lambda x: x.date)
                for move in sorted_lines:
                    if move.location_dest_id.id in location_ids and move.location_id.id not in location_ids:
                        qty_end = qty_start + move.product_qty
                        type_move = 'Ingreso'
                        qty = 0.0
                        qty_out = 0.0
                        qty_in = move.product_qty
                    elif move.location_dest_id.id not in location_ids and move.location_id.id in location_ids:
                        qty_end = qty_start - move.product_qty
                        type_move = 'Salida'
                        qty = 0.0
                        qty_out = move.product_qty
                        qty_in = 0.0
                    else:
                        qty_end = qty_start
                        type_move = 'Interno'
                        qty = move.product_qty
                        qty_out = 0.0
                        qty_in = 0.0

                    location_id = move.location_id.name
                    location_dest_id = move.location_dest_id.name
                    type_move = type_move
                    cost_move = move.cost
                    cost_total_move = move.cost * move.product_qty

                    cost_promedio = move.costo_promedio
                    if cost_promedio == 0.0:
                        cost_promedio = move.cost

                    cost_promedio_total = cost_promedio * qty_end

                    date = move.date
                    name = move.picking_id and move.picking_id.name or move.inventory_id and move.inventory_id.name or \
                           move.name
                    origin = move.origin

                    dlines = {
                        'name': name,
                        'origin': origin,
                        'product_id': product_id,
                        'default_code': default_code,
                        'product_name': product_name,
                        'date': date,
                        'location_id': location_id,
                        'location_dest_id': location_dest_id,
                        'type_move': type_move,
                        'qty_start': qty_start,
                        'qty_in': qty_in,
                        'qty': qty,
                        'qty_out': qty_out,
                        'qty_end': qty_end,
                        'cost_move': cost_move,
                        'cost_total_move': cost_total_move,
                        'cost_promedio': cost_promedio,
                        'cost_promedio_total': cost_promedio_total,
                        'date_start': dt_start,
                        'date_end': dt_end,
                        'move_id': move.id
                    }
                    avancys_orm.direct_create(self._cr, self._uid, 'stock_report_kardex_line', [dlines])
                    qty_start = qty_end
            elif qty_start > 0.0:
                val = 'SIN MOVIMIENTOS'
                dlines = {
                    'name': val,
                    'origin': val,
                    'product_id': product_id,
                    'default_code': default_code,
                    'product_name': product_name,
                    'date': dt_start,
                    'location_id': val,
                    'qty_start': qty_start,
                    'qty_end': qty_start,
                    'date_start': dt_start,
                    'date_end': dt_end,
                }
                avancys_orm.direct_create(self._cr, self._uid, 'stock_report_kardex_line', [dlines])

        if self.print_report == 'print':
            self._cr.execute(''' SELECT 
                                    default_code,
                                    product_name,
                                    name,
                                    origin,
                                    type_move,
                                    date,
                                    location_id,
                                    location_dest_id,
                                    qty_start,
                                    qty_in,
                                    qty,
                                    qty_out,
                                    qty_end,
                                    cost_move,
                                    cost_total_move,
                                    cost_promedio,
                                    cost_promedio_total
                                FROM 
                                    stock_report_kardex_line
                                ORDER BY 
                                    product_id, date ''')

            datos = self._cr.fetchall()
            url = self.printfast(datos)
            return {'type': 'ir.actions.act_url', 'url': str(url), 'target': 'self'}
        else:
            return {
                'name': 'Analisis de Inventario',
                'view_type': 'form',
                'view_mode': 'graph,tree',
                'view_id': False,
                'res_model': 'stock.report.kardex.line',
                'type': 'ir.actions.act_window',
                'context': {'search_default_group_principal': True}
            }

    @api.multi
    def printfast(self, datos):
        actual = str(datetime.now() - timedelta(hours=5))[0:19]
        data_attach = {
            'name': 'Kardex_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.xlsx',
            'datas': '.',
            'datas_fname': 'Kardex_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.',
            'res_model': 'stock.report.kardex.wizard',
            'res_id': self.id,
        }
        self.env['ir.attachment'].search(
            [('res_model', '=', 'stock.report.kardex.wizard'), ('company_id', '=', self.env.user.company_id.id), (
                'name', 'like',
                '%Valorizado%' + self.env.user.name + '%')]).unlink()  # elimina adjuntos del usuario

        # crea adjunto en blanco
        attachments = self.env['ir.attachment'].create(data_attach)

        headers = dict(request.httprequest.__dict__.get('headers'))

        if headers.get('Origin', False):
            url = dict(request.httprequest.__dict__.get('headers')).get(
                'Origin') + '/web/binary/saveas?model=ir.attachment&field=datas&filename_field=name&id=' + str(
                attachments.id)
        else:
            url = dict(request.httprequest.__dict__.get('headers')).get(
                'Referer') + '/binary/saveas?model=ir.attachment&field=datas&filename_field=name&id=' + str(
                attachments.id)
        path = attachments.store_fname
        self.env['ir.attachment'].search([['store_fname', '=', path]]).write(
            {'store_fname': attachments._get_path(path)[0]})
        wb = xlsxwriter.Workbook(attachments._get_path(path)[1])
        bold = wb.add_format({'bold': True})
        bold2 = wb.add_format({'bold': True, 'fg_color': '#ffffff'})
        bold3 = wb.add_format({'bold': False, 'fg_color': '#F2F2F2'})
        bold4 = wb.add_format({'bold': True, 'fg_color': '#2E86C1'})
        bold.set_align('center')
        bold2.set_align('center')
        bold3.set_align('center')
        bold4.set_align('center')
        money_format = wb.add_format({'num_format': '$#,##0'})
        money_format.set_align('right')
        ws = wb.add_worksheet('KARDEX')
        ws.set_column('A:A', 20)

        abc = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U',
               'V', 'W', 'X', 'Y', 'Z']

        ws.merge_range('A1:Q1', 'INFORME KARDEX', bold2)
        ws.merge_range('A2:Q2', 'FECHA CONSULTA: ' + actual, bold2)

        ws.merge_range('A3:E4', '', bold2)
        ws.write('F3', 'DESDE:', bold2)
        ws.write('G3', self.date_start, bold2)
        ws.merge_range('H3:I4', '', bold2)
        ws.write('J3', 'DESDE:', bold2)
        ws.write('K3', self.date_end, bold2)
        ws.merge_range('L3:Q4', '', bold2)

        ws.merge_range('A4:Q4', '')
        # ws.merge_range('A4:F4', 'INFORMACION DEL MOVIMIENTO',bold5)
        # ws.merge_range('G4:H4', 'UBICACIONES',bold5)
        # ws.merge_range('I4:M4', 'CANTIDADES',bold5)
        # ws.merge_range('N4:Q4', 'COSTOS',bold5)

        titulos = self.title.split(',')

        num = [x for x in range(0, 101)]
        resultado = zip(abc, num)
        for i, l in enumerate(titulos):
            for pos in resultado:
                if i == pos[1]:
                    position = pos[0]
                    break
            ws.write(position + str(5), l, bold4)
        filter_auto = 'A5:' + str(abc[len(titulos) - 1]) + '5'
        ws.autofilter(filter_auto)
        for x, line in enumerate(datos):
            for y, f in enumerate(titulos):
                for pos in resultado:
                    if y == pos[1]:
                        position = pos[0]
                        break

                if position in ('I', 'J', 'K', 'L', 'M'):
                    ws.write(position + str(6 + x), line[y] or int(0), bold3)
                elif position in ('N', 'O', 'P', 'Q'):
                    ws.write(position + str(6 + x), line[y] or int(0), money_format)
                else:
                    ws.write(position + str(6 + x), line[y] or '')
        wb.close()
        return url
