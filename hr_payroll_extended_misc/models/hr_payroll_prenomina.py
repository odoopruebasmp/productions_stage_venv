# -*- coding: utf-8 -*-
import logging
from openerp import models, fields, api
from datetime import datetime, timedelta
from openerp.http import request
import xlsxwriter
import copy

_logger = logging.getLogger('PRENOMINA')


class HRPayrlipRunPrenomina(models.Model):
    _name = 'hr.payslip.prenomina'

    @api.multi
    def download_prenomina(self):
        model = self.env.context.get('active_model', False)
        # header = []  # conceptos
        self.env.cr.execute(''' select id, code FROM hr_salary_rule WHERE appears_on_payslip AND active ORDER BY sequence, id''')

        header = self.env.cr.dictfetchall()
        #header = self.env['hr.salary.rule'].search([('appears_on_payslip', '=', True)], order='sequence, id asc')
        htemp = []
        #for x in header:
            #_logger.info(x)
            #htemp.append('R'+ str(x.get('id') + x.get('code'))
        header = ['R' + str(x.get('id')) + x.get('code') for x in header]
        header = ['Identificacion', 'Nombre', 'Contrato', 'Referencia'] + header
        ids = []
        data = False
        if model == 'hr.payslip.run':  # procesamiento de nomina
            for run in self.env['hr.payslip.run'].browse(self.env.context.get('active_ids', None)):
                for payslip in run.slip_ids:
                    if payslip.id not in ids:
                        ids.append(payslip.id)
            data = self._get_prenomina(ids, header)

        #############################################################
        #############################################################
        ###################         XLSX          ###################
        #############################################################
        #############################################################

        actual = str(datetime.now()).replace('-', '').replace(':', '').replace('.', '').replace(' ', '')
        data_attach = {
            'name': 'PRENOMINA_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.xlsx',
            'datas': '.',
            'datas_fname': 'PRENOMINA_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.',
            'res_model': 'hr.payslip.prenomina',
            'res_id': self.id,
        }
        # elimina adjuntos del usuario
        self.env['ir.attachment'].search(
            [('res_model', '=', 'hr.payslip.prenomina'), ('company_id', '=', self.env.user.company_id.id),
             ('name', 'like', '%PRENOMINA%' + self.env.user.name + '%')]).unlink()

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
        ws = wb.add_worksheet('DATOS')
        ws.set_column('A:A', 20)
        bold = wb.add_format({'bold': True})
        bold.set_align('center')
        ws.merge_range('A1:B1', 'PRENOMINA: ', bold)
        _logger.info('PRENOMINA')
        # TITULOS
        abc = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
               'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']  # 26
        abc_temp = copy.copy(abc)
        if len(header) > 52:
            # 2digitos
            for x in abc_temp:
                for y in abc_temp:
                    abc.append(x + y)
        if len(header) > 702:
            # 2digitos
            for x in abc_temp:
                for y in abc_temp:
                    for z in abc_temp:
                        abc.append(x + y + z)
        if len(header) > 18278:
            # 2digitos
            for x in abc_temp:
                for y in abc_temp:
                    for z in abc_temp:
                        for a in abc_temp:
                            abc.append(x + y + z + a)
        num = [x for x in range(0, len(header))]
        resultado = zip(abc, num)
        position = ''
        _logger.info(header)
        # recorre id de conceptos
        for i, l in enumerate(header):
            for pos in resultado:
                if i == pos[1]:
                    position = pos[0]
                    break
            title = position
            ws.write(position + str(3), l, bold)
        for datas in data:
            for x, line in enumerate(datas):
                _logger.info(line)
                if line:
                    for y, f in enumerate(header):
                        for pos in resultado:
                            if y == pos[1]:
                                position = pos[0]
                                break
                        ws.write(position + str(3 + x + 1), line[y] or '0.0')

        wb.close()
        return {'type': 'ir.actions.act_url', 'url': str(url), 'target': 'self'}
        return True

    @api.one
    def _get_prenomina(self, ids, header):
        titles = 'NOMINA TEXT,'
        titles += ' NUMERIC, '.join(header)
        titles += ' NUMERIC'
        data = True
        sql = '''SELECT rp.ref, rp.display_name, hc.name as contract, a.* 
                    FROM ( 
                        SELECT * FROM crosstab('SELECT hp.number::text, hsr.code::text,COALESCE(hpl.total,0)::numeric as total
                                                FROM hr_salary_rule hsr
                                                INNER JOIN hr_payslip hp ON hp.id in {slip_ids}
                                                LEFT JOIN hr_payslip_line hpl ON hpl.salary_rule_id = hsr.id AND hp.id = hpl.slip_id
                                                    WHERE hsr.appears_on_payslip AND hsr.active order by hp.id, hsr.sequence, hsr.id') AS final_result({titles})) as a
                                        INNER JOIN hr_payslip hp ON hp.number = a.nomina
                                        INNER JOIN hr_contract hc ON hc.id = hp.contract_id
                                        INNER JOIN hr_employee he ON he.id = hc.employee_id
                                        INNER JOIN res_partner rp ON rp.employee_id = he.id                                        
                                        ORDER BY a.nomina'''.format(slip_ids=tuple(ids), titles=titles)
        self.env.cr.execute(sql)
        data = self.env.cr.fetchall()
        return data
