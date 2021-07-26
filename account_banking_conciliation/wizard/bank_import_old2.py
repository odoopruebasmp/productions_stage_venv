# -*- coding: utf-8 -*-
import base64
from datetime import datetime
import time
from openerp import models, api, fields
from openerp.exceptions import Warning
from openerp.tools.misc import DEFAULT_SERVER_DATE_FORMAT


class BankingImport(models.TransientModel):
    _name = 'account.banking.bank.import'

    journal_id = fields.Many2one('account.journal', 'Diario', required=True)
    period_id = fields.Many2one('account.period', 'Periodo', required=True)
    file = fields.Binary('Archivo', required=True)
    log = fields.Text('Log', readonly=True)
    parser = fields.Selection([
        ('helm', 'Helm'),
        ('bancolombia', 'Bancolombia'),
        ('davivienda', 'Davivienda'),
        ('caja_social', 'Caja Social'),
        ('avvillas', 'AV Villas'),
        ('popular', 'Popular'),
        ('Sudameris', 'Sudameris'),
        ('occidente', 'Occidente'),
        ('bogota', 'Bogota'),
        ('bbva', 'BBVA')], 'Formato Banco', required=True)

    @api.multi
    def import_statements_file(self):
        BankStatement = self.env['account.bank.statement']
        debit_account = self.journal_id.default_debit_account_id.id
        credit_account = self.journal_id.default_credit_account_id.id
        orm2sql = self.env['avancys.orm2sql']
        statement_name = self.parser.upper() + '_' + time.strftime('%Y-%m-%d')

        statement_vals = {
            'name': statement_name,
            'balance_start': 0,
            'balance_end_real': 0,
            'date': time.strftime('%Y-%m-%d'),
            'period_id': self.period_id.id,
            'file': self.file,
            'file_name': statement_name + '.txt',
            'journal_id': self.journal_id.id,
        }
        statement = BankStatement.create(statement_vals)
        statement_lines = []
        sequence = 0

        # BANCO DE BOGOTA
        if self.parser == 'bogota':
            lines = base64.decodestring(self.file).split('\r\n')
            for line in lines:
                line_dict = {}
                if len(line) == 240:
                    sequence += 1
                    date = line[17:25]
                    line_dict['date'] = (
                        date[0:4] + '-' + date[4:6] + '-' + date[6:8])
                    line_dict['ref'] = line[120:len(line)]
                    descripcion = orm2sql.delete_spaces(
                        line_dict['ref'], right=True)
                    line_dict['name'] = descripcion
                    line_dict['ref'] = orm2sql.delete_spaces(
                        line[82:88], right=True)
                    line_dict['sequence'] = sequence
                    valor = orm2sql.delete_spaces(line[35:52], left=True)
                    if line[119] == 'C':
                        line_dict['amount'] = float(valor) / 100
                        line_dict['account_id'] = credit_account
                    elif line[119] == 'D':
                        line_dict['amount'] = - float(valor) / 100
                        line_dict['account_id'] = debit_account
                    line_dict['statement_id'] = statement.id
                    line_dict['state'] = 'draft'

                    statement_lines.append(line_dict)

        # BANCO CAJA SOCIAL
        if self.parser == 'caja_social':
            lines = base64.decodestring(self.file).split('\r\n')
            for line in lines:
                line_dict = {}
                sequence += 1
                campos = line.split(';')
                if len(campos) == 36:
                    line_dict['date'] = (
                        '20' + campos[3][6:8] + '-' +
                        campos[3][3:5] + '-' +
                        campos[3][0:2])
                    line_dict['name'] = str(campos[18])
                    line_dict['ref'] = str(campos[18])
                    line_dict['sequence'] = sequence
                    if float(campos[10]) < 0:
                        line_dict['amount'] = float(campos[10])
                        line_dict['account_id'] = debit_account
                    else:
                        line_dict['amount'] = float(campos[10])
                        line_dict['account_id'] = credit_account
                    line_dict['statement_id'] = statement.id
                    line_dict['state'] = 'draft'

                    statement_lines.append(line_dict)

        # BANCO HELM
        if self.parser == 'helm':
            lines = base64.decodestring(self.file).split('\n')
            for line in lines:
                line_dict = {}
                if len(line) == 126:
                    if sequence == 0:
                        statement.balance_start = float(line[41:74])
                    else:
                        statement.balance_end_real = float(line[41:74])
                if len(line) == 122:
                    sequence += 1
                    date = line[0:8]
                    line_dict['date'] = (
                        date[0:4] + '-' + date[4:6] + '-' + date[6:8])
                    line_dict['ref'] = line[83:90]
                    descripcion = line[90:122]
                    line_dict['name'] = descripcion
                    line_dict['sequence'] = sequence
                    valor = line[41:74]
                    if line[74:75] == 'C':
                        line_dict['amount'] = float(valor)
                        line_dict['account_id'] = credit_account
                    elif line[74:75] == 'D':
                        line_dict['amount'] = - float(valor)
                        line_dict['account_id'] = debit_account
                    line_dict['statement_id'] = statement.id
                    line_dict['state'] = 'draft'

                    statement_lines.append(line_dict)

        orm2sql.sqlcreate(
            self.env.uid, self.env.cr, 'account_bank_statement_line',
            statement_lines, company=True, progress=True)
        statement.button_dummy()

        domain = [('id', 'in', [statement.id])]
        return {
            'domain': domain,
            'name': 'Imported statement',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'account.bank.statement',
            'type': 'ir.actions.act_window',
        }
