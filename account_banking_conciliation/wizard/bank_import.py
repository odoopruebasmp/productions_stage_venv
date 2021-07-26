# coding=utf-8
from datetime import datetime
import time
import base64
import openerp.addons.decimal_precision as dp

from openerp import models, fields, api, _
from openerp.exceptions import Warning


class BankingImport(models.TransientModel):
    _name = 'account.banking.bank.import'

    journal_id = fields.Many2one('account.journal', 'Diario', required=True)
    period_id = fields.Many2one('account.period', 'Periodo', required=True)
    file = fields.Binary('Archivo', required=True)
    log = fields.Text('Log', readonly=True)
    parser = fields.Many2one('account.banking.parser')

    @api.multi
    def import_statements_file(self):
        bank_statement_obj = self.env['account.bank.statement']
        debit_account = self.journal_id.default_debit_account_id.id
        credit_account = self.journal_id.default_credit_account_id.id
        orm2sql = self.env['avancys.orm2sql']
        precision = self.env['decimal.precision'].precision_get('Account')
        parser = self.parser
        res_bank = self.env['res.partner.bank']

        statement_name = parser.name.upper() + '_' + time.strftime('%Y-%m-%d')

        statement_vals = {
            'name': statement_name,
            'balance_start': 0,
            'balance_end_real': 0,
            'date': time.strftime('%Y-%m-%d'),
            'period_id': self.period_id.id,
            'file': self.file,
            'file_name': statement_name + '.txt',
            'journal_id': self.journal_id.id,
            'match_dom': parser.match_dom,
        }
        statement = bank_statement_obj.create(statement_vals)
        statement_lines = []
        sequence = 0
        line_break = False
        if parser.line_break == 'n':
            line_break = '\n'
        elif parser.line_break == 'rn':
            line_break = '\r\n'
        if not line_break:
            raise Warning('No se ha definido un salto de linea para el archivo')

        lines = base64.decodestring(self.file).split(line_break)

        # Extraccion del detalle de las lineas
        for line in lines:
            line_data = {}
            line_len = False
            sline = False
            # Estructura de archivo
            if parser.separator_type == 'none':
                line_len = len(line)
                sline = line
            elif parser.separator_type == 'delimited':
                line_len = len(line.split(str(parser.separator)))
                sline = line.split(str(parser.separator))
            if line_len is False:
                raise Warning("No se ha definido un separador valido")
            else:
                # Estructura validada
                if line_len != parser.line_len:
                    # Dodge si el tamaño no es correcto
                    print "El tamaño de la linea [{l}] no corresponde al cuerpo".format(l=line_len)
                    continue
                else:
                    # Extraccion de datos de linea
                    sequence += 1
                    line_data['sequence'] = sequence

                    # Fecha
                    date_pos = parser.date_pos.split('-')
                    if len(date_pos) != 2:
                        raise Warning('La posicion de la fecha no esta configurada correctamente')

                    date_fragment = sline[int(date_pos[0]):int(date_pos[1])]
                    if parser.separator_type == 'delimited':
                        date_fragment = date_fragment[0]
                    line_date = datetime.strptime(date_fragment, parser.date_format)
                    line_data['date'] = datetime.strftime(line_date, '%Y-%m-%d')

                    # Referencia
                    ref_pos = parser.ref_pos.split('-')
                    if parser.ref_pos and len(ref_pos) != 2:
                        raise Warning('La posicion de la referencia no está configurada correctamente')
                    ref_line = sline[int(ref_pos[0]): int(ref_pos[1])]
                    if parser.separator_type == 'delimited':
                        ref_line = ref_line[0]
                    line_data['ref'] = orm2sql.delete_spaces(ref_line, right=True)

                    # Comunicacion
                    name_pos = parser.name_pos.split('-')
                    if parser.name_pos and len(name_pos) != 2:
                        raise Warning('La posicion de la comunicacion no está configurada correctamente')
                    name_line = sline[int(name_pos[0]): int(name_pos[1])]
                    if parser.separator_type == 'delimited':
                        name_line = name_line[0]
                    line_data['name'] = orm2sql.delete_spaces(name_line, right=True)

                    # Signo
                    if parser.signal_bool:
                        sig_pos = parser.signal_position.split('-')
                        if parser.signal_position and len(sig_pos) != 2:
                            raise Warning('La posicion del signo de la transacción no está configurada correctamente')
                        signal_line = sline[int(sig_pos[0]): int(sig_pos[1])]
                        if parser.separator_type == 'delimited':
                            signal_line = signal_line[0]
                        if parser.signal_declaration and parser.signal_declaration.split(','):
                            if signal_line == parser.signal_declaration.split(',')[0]:
                                signal_line = 1
                            elif signal_line == parser.signal_declaration.split(',')[1]:
                                signal_line = -1
                        else:
                            raise Warning('No está configurada correctamente la definicion de signos')
                    else:
                        signal_line = 1

                    # Valor
                    amount_pos = parser.amount_pos.split('-')
                    if parser.amount_pos and len(amount_pos) != 2:
                        raise Warning('La posicion del monto no está configurada correctamente')
                    amount_line = sline[int(amount_pos[0]): int(amount_pos[1])]
                    if parser.separator_type == 'delimited':
                        amount_line = amount_line[0]
                    if parser.amount_format == 'i.d':
                        amount_line = float(amount_line) * signal_line
                    elif parser.amount_format == 'id':
                        amount_line = float(amount_line)/100 * signal_line
                    elif parser.amount_format == 'i,d':
                        amount_line = float(amount_line.replace(',', '.')) * signal_line
                    if amount_line < 0:
                        account_line = debit_account
                    else:
                        account_line = credit_account
                    line_data['amount'] = round(amount_line, precision)
                    line_data['account_id'] = account_line

                    # Cuenta bancaria
                    account_pos = parser.account_pos.split('-')
                    if parser.account_pos and len(account_pos) != 2:
                        raise Warning('La posicion de la comunicacion no está configurada correctamente')
                    bank_account_line = sline[int(account_pos[0]): int(account_pos[1])]
                    if parser.separator_type == 'delimited':
                        bank_account_line = bank_account_line[0]
                    bank_line = res_bank.search([('acc_number', '=', str(bank_account_line))])
                    if not bank_line:
                        raise Warning('No se encontró la cuenta No. {num} creada en el sistema'.format(
                            num=bank_account_line))
                    line_data['bank_account_id'] = bank_line[0].id

                    # Estado
                    line_data['state'] = 'draft'

                    # Extracto
                    line_data['statement_id'] = statement.id

                    print line_data
                    statement_lines.append(line_data)
        if len(statement_lines) < 1:
            raise Warning("No se detectaron lineas en el cuerpo del archivo")
        orm2sql.sqlcreate(
            self.env.uid, self.env.cr, 'account_bank_statement_line', statement_lines, company=True, progress=True)

        domain = [('id', 'in', [statement.id])]
        form = self.env['ir.model.data']._get_id('account_banking_conciliation',
                                                 'account_banking_conciliation_statement_form')
        view = self.env['ir.model.data'].browse(form).res_id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Extracto importado',
            'view_type': 'form',
            'view_mode': 'tree, form',
            'res_model': 'account.bank.statement',
            'view_id': [view],
            'domain': domain,
            'views': [(False, 'tree'), (view, 'form')]
        }


class BankingParser(models.Model):
    _name = 'account.banking.parser'

    name = fields.Char('Formato de banco')
    separator_type = fields.Selection([('none', 'Ninguno'), ('delimited', 'Delimitado')], 'Tipo de separador')
    separator = fields.Char('Separador')
    date_pos = fields.Char('Posicion fecha')
    date_format = fields.Char('Formato de fecha')
    ref_pos = fields.Char('Posicion referencia')
    name_pos = fields.Char('Posicion comunicacion')
    signal_bool = fields.Boolean('Signo fuera del valor')
    signal_position = fields.Char('Posicion signo')
    signal_declaration = fields.Char('Declaracion de signo')
    amount_pos = fields.Char('Posicion valor')
    amount_format = fields.Selection([('i.d', 'entero.decimal'), ('id', 'enterodecimal'), ('i,d', 'entero,decimal')],
                                     'Formato de valor')
    account_pos = fields.Char('Posicion cuenta')
    line_break = fields.Selection([('rn', 'rn'), ('n', 'n')],  string='Salto de linea')
    line_len = fields.Integer('Largo de linea')
    match_dom = fields.Char('Dominio adicional',
                            help="ej. (ref,=,ref) campo de account_move vs campo de transaccion")

