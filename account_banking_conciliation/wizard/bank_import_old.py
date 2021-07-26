# -*- coding: utf-8 -*-
import base64
from datetime import datetime
from openerp.osv import orm, fields, osv
from openerp.tools.translate import _
import re
import time
import csv
import xlrd
import tempfile
from openerp.addons.edi import EDIMixin
from openerp.tools.misc import DEFAULT_SERVER_DATE_FORMAT

class banking_import(osv.TransientModel):
    _name = 'account.banking.bank.import'
    
    _columns = {
        'journal_id': fields.many2one('account.journal', 'Diario', required=True),
        'period_id': fields.many2one('account.period', 'Periodo', required=True),
        'company_id': fields.many2one('res.company', 'Company', select=1, help='Let this field empty if this location is shared between companies'),
        'file': fields.binary('Archivo', required=True),
        'log': fields.text('Log', readonly=True),
        'parser': fields.selection([
            ('helm','Helm'),
            ('bancolombia','Bancolombia'),
            ('davivienda','Davivienda'),
            ('Caja_Social','Caja Social'),
            ('AVVillas','AVVillas'),
            ('Popular','Popular'),
            ('Sudameris','Sudameris'),
            ('Occidente','Occidente'),
            ('Bogota','Bogotá'),
            ('BBVA','BBVA'),
        ], 'Formato Banco', required=True),
    }
    
    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.banking.bank.import', context=c),
    }
    
    def is_valid(self, line):
        if line and len(line)==8:
            return bool(line[1] and line[3] and line[4] and (line[5] or line[6] or line[7]))
    
    def make_log(self, cr, uid, ids, log_count, context=None):
        if not context: context = {}
        report = []
        if log_count:
            report = [
                '%s: %s' % (_('Total number of statements'),
                            log_count.get('st_cnt')),
                '%s: %s' % (_('Total number of transactions'),
                            log_count.get('total_cnt')),
                '%s: %s' % (_('Number of errors found'),
                            log_count.get('error_cnt')),
                '%s: %s' % (_('Number of statements skipped due to errors'),
                            log_count.get('st_error_cnt')),
                '%s: %s' % (_('Number of transactions skipped due to errors'),
                            log_count.get('skipped_cnt')),
                '%s: %s' % (_('Number of statements loaded'),
                            log_count.get('st_cnt') - log_count.get('st_error_cnt')),
                '%s: %s' % (_('Number of transactions loaded'),
                            log_count.get('total_cnt') - log_count.get('error_cnt')),
                '%s: %s' % (_('Number of transactions matched'),
                            '0'),
                '%s: %s' % (_('Number of bank costs invoices created'),
                            '0'),
                '',
                '%s:' % ('Error report'),
                '',
            ]
        return report
    
    def import_statements_file(self, cr, uid, ids, context):
        if not context: context = {}
        context.update({'journal_type': 'bank'})
        statement_obj = self.pool.get('account.bank.statement')
        journal_pool = self.pool.get('account.journal')
        account_period = self.pool.get('account.period')
        statement_file_obj = self.pool.get('account.banking.imported.file')
        banking_import = self.browse(cr, uid, ids, context)[0]
        statements_file = banking_import.file
        journal_id = banking_import.journal_id.id
        period_id = banking_import.period_id
        company_id = banking_import.company_id.id
        debit_account = banking_import.journal_id.default_debit_account_id.id
        credit_account = banking_import.journal_id.default_credit_account_id.id
        parser_code = banking_import.parser
        
        if not debit_account:
            raise osv.except_osv(_('Error !'), _('El diario %d, No tiene una Cuenta deudora por defecto'%(journal_id)))
        if not credit_account:
            raise osv.except_osv(_('Error !'), _('El diario %d, No tiene una Cuenta acreedora por defecto'%(journal_id)))
        
        # Banco Davivienda
        
        if parser_code == 'davivienda':
            result = []
            log_list = []
            dialect = csv.excel()
            dialect.quotechar = '"'
            dialect.delimiter = ','
            lines = base64.decodestring(statements_file).split('\n')
            line_count = 0
            ending_amount = 0.0
            statement_name = (parser_code)+'_'+time.strftime('%Y-%m-%d')
            st_cnt, st_error_cnt, total_cnt, skipped_cnt, error_cnt  = 0, 0, 0, 0, 0
            statement_vals = {
                'journal_id': journal_id,
            }
            statement = statement_obj.create(cr, uid, statement_vals, context=context)
            
            for line in csv.reader(lines, dialect=dialect):
                if line:
                    line_dict = {}
                    line_count +=1
                    if line_count <= 3 or len(line)== 1 or line[0] == '':
                        continue
                    if len(line)!= 11:
                        raise osv.except_osv(_('Error !'), _('El archivo seleccionado no tiene el formato seleccionado!'))
                    line_dict['date'] = datetime.strptime(line[0],'%y/%m/%d').strftime(DEFAULT_SERVER_DATE_FORMAT)
                    line_dict['ref'] = line[5]
                    line_dict['name'] = line[3]
                    if line[3] in ['DE','NC']:
                        line_dict['amount'] = float(line[8])
                    else:
                        line_dict['amount'] = float(line[8])*-1
                    
                    line_dict['statement_origin_id'] = statement
                    line_dict['statement_id'] = statement
                    if line_dict['amount'] < 0: 
                        line_dict['account_id'] = credit_account
                    else:
                        line_dict['account_id'] = debit_account
                    result.append((0, 0, line_dict))
            statement_vals = {
                'name': statement_name,
                'balance_start': 0,
                'balance_end_real': 0,
                'file': statements_file,
                'line_ids': result,
                'file_name': statement_name+'.txt'
            }
            statement_obj.write(cr, uid, [statement], statement_vals, context=context)
            statement_obj.button_dummy(cr, uid, [statement], context=context)
            
            if not statement:
                st_error_cnt += 1
            st_cnt += 1
            log_count = {
                "total_cnt": line_count,
                "skipped_cnt": skipped_cnt,
                "error_cnt": error_cnt,
                "st_cnt": st_cnt,
                "st_error_cnt": st_error_cnt
            }
            log = self.make_log(cr, uid, ids, log_count, context)
            text_log = '\n'.join(log)
            domain = [('id','in',[statement])]
            return {
                'domain': domain,
                'name': 'Imported statement',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.bank.statement',
                'type': 'ir.actions.act_window', 
            }
            
        # Banco Bancolombia
        
        if parser_code == 'bancolombia':
            result = []
            log_list = []
            dialect = csv.excel()
            dialect.quotechar = '"'
            dialect.delimiter = ','
            lines = base64.decodestring(statements_file).split('\n')
            line_count = 0
            ending_amount = 0.0
            statement_name = (parser_code)+'_'+time.strftime('%Y-%m-%d')
            st_cnt, st_error_cnt, total_cnt, skipped_cnt, error_cnt  = 0, 0, 0, 0, 0
            statement_vals = {
                'journal_id': journal_id,
            }
            statement = statement_obj.create(cr, uid, statement_vals, context=context)
            
            for line in csv.reader(lines, dialect=dialect):
                if line:
                    if len(line)!= 10:
                        raise osv.except_osv(_('Error !'), _('El archivo seleccionado no tiene el formato seleccionado!'))
                    line_dict = {}
                    line_count +=1
                    line_dict['date'] = datetime.strptime(line[3].lstrip(), '%Y%m%d').strftime(DEFAULT_SERVER_DATE_FORMAT)
                    line_dict['ref'] = ''
                    line_dict['name'] = line[7].lstrip()
                    line_dict['amount'] = float(line[5].lstrip())
                    line_dict['statement_origin_id'] = statement
                    line_dict['statement_id'] = statement
                    if line_dict['amount'] < 0: 
                        line_dict['account_id'] = credit_account
                    else:
                        line_dict['account_id'] = debit_account
                    result.append((0, 0, line_dict))
            statement_vals = {
                'name': statement_name,
                'balance_start': 0,
                'balance_end_real': 0,
                'file': statements_file,
                'line_ids': result,
                'file_name': statement_name+'.txt'
            }
            statement_obj.write(cr, uid, [statement], statement_vals, context=context)
            statement_obj.button_dummy(cr, uid, [statement], context=context)
            
            if not statement:
                st_error_cnt += 1
            st_cnt += 1
            log_count = {
                "total_cnt": line_count,
                "skipped_cnt": skipped_cnt,
                "error_cnt": error_cnt,
                "st_cnt": st_cnt,
                "st_error_cnt": st_error_cnt
            }
            log = self.make_log(cr, uid, ids, log_count, context)
            text_log = '\n'.join(log)
            domain = [('id','in',[statement])]
            return {
                'domain': domain,
                'name': 'Imported statement',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.bank.statement',
                'type': 'ir.actions.act_window', 
            }
            
        # Banco Helm
        
        if parser_code == 'helm':
            result = []
            log_list = []
            dialect = csv.excel()
            dialect.quotechar = '"'
            dialect.delimiter = ','
            lines = base64.decodestring(statements_file).split('\n')
            line_count = 0
            ending_amount = 0.0
            statement_name = (parser_code)+'_'+time.strftime('%Y-%m-%d')
            st_cnt, st_error_cnt, total_cnt, skipped_cnt, error_cnt  = 0, 0, 0, 0, 0
            
            statement_vals = {
                'journal_id': journal_id,
            }
            statement = statement_obj.create(cr, uid, statement_vals, context=context)
            
            for line in csv.reader(lines, dialect=dialect):
                if line and len(line)!= 8:
                    raise osv.except_osv(_('Error !'), _('El archivo seleccionado no tiene el formato seleccionado!'))
                line_dict = {}
                line_count +=1
                if line_count == 3:
                    year = line[0][-4:]
                if line_count <= 8:
                    continue
                total_cnt += 1
                if not self.is_valid(line):
                    skipped_cnt += 1
                    error_cnt += 1
                elif self.is_valid(line):
                    if line_count == 9 and 'SALDO ANTERIOR' in line[4]:
                        begin_amount = line[7]
                    tr_date = line[1].strip()[:2] +'/'+ line[1].strip()[-2:] +'/'+ year
                    if line[5]: 
                        line_dict['account_id'] = credit_account
                    elif line[6]:
                        line_dict['account_id'] = debit_account
                    else:
                        continue
                    line_dict['date'] = datetime.strptime(tr_date, '%d/%m/%Y').strftime(DEFAULT_SERVER_DATE_FORMAT)
                    line_dict['ref'] = line[3]
                    line_dict['name'] = line[4]
                    amount = 0
                    if line[5]:
                        try:
                            amount = -float(line[5])
                        except:
                            amount = 0
                    if amount == 0 and line[6]:
                        try:
                            amount = float(line[6])
                        except:
                            amount = 0
                    line_dict['amount'] = amount
                    line_dict['statement_origin_id'] = statement
                    line_dict['statement_id'] = statement
                    result.append((0, 0, line_dict))
                    ending_amount = line[7]
            
            statement_vals = {
                'name': statement_name,
                'balance_start': begin_amount,
                'balance_end_real': ending_amount,
                'file': statements_file,
                'line_ids': result,
                'file_name': statement_name+'.txt'
            }
            statement_obj.write(cr, uid, [statement], statement_vals, context=context)
            statement_obj.button_dummy(cr, uid, [statement], context=context)
            
            if not statement:
                st_error_cnt += 1
            st_cnt += 1
            log_count = {
                "total_cnt": total_cnt,
                "skipped_cnt": skipped_cnt,
                "error_cnt": error_cnt,
                "st_cnt": st_cnt,
                "st_error_cnt": st_error_cnt
            }
            log = self.make_log(cr, uid, ids, log_count, context)
            text_log = '\n'.join(log)
            domain = [('id','in',[statement])]
            return {
                'domain': domain,
                'name': 'Imported statement',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.bank.statement',
                'type': 'ir.actions.act_window', 
            }
            
        # Banco Caja Social
            
        if parser_code == 'Caja_Social':
            result = []
            log_list = []
            dialect = csv.excel()
            dialect.quotechar = '"'
            dialect.delimiter = ','
            lines = base64.decodestring(statements_file).split('\n')
            line_count = 0
            ending_amount = 0.0
            begin_amount = 0
            ending_amount = 0
            period = 0
            date_obj = time.strftime('%Y-%m-%d')
            date_line = time.strftime('%Y-%m-%d')
            st_cnt, st_error_cnt, total_cnt, skipped_cnt, error_cnt  = 0, 0, 0, 0, 0
            
            statement_vals = {
                'journal_id': journal_id,
            }
            statement = statement_obj.create(cr, uid, statement_vals, context=context)
            
            for line in csv.reader(lines, dialect=dialect):
                line_count +=1
                
                if line and len(line)!= 10:
                    raise osv.except_osv(_('Error !'), _('El archivo seleccionado no tiene el formato seleccionado!'))
                line_dict = {}
                if line_count == 0:
                    continue
                if line_count <= 9:
                    total_cnt += 1
                if not line and len(line)==10:
                    skipped_cnt += 1
                    error_cnt += 1
                    
                elif line and len(line)==10 and line[0] and line[2] and line[4] and not ('Fecha Saldo' in line[0]):
                
                    if 'SALDO INICIAL' in line[2] and line_count==3:
                        begin_amount = line[4]
                    
                    if 'SALDO FINAL' in line[2]:
                        ending_amount = line[4]
                        date_obj = line[0][-4:]+'-'+line[0][3:5]+'-'+line[0][0:2]
                        period = line[0][3:5]+'/'+line[0][-4:]
                        period_ids = account_period.search(cr, uid, [('code', '=', period), ('company_id','=', company_id)])
                        if period_ids:
                            period_id = period_ids[0]
                        else:
                            raise osv.except_osv(_('Error !'), _('El periodo con el codigo "%s" no existe!')%(period))
                        
                if line and len(line)==10 and line[1] and line[2] and line[3] and not ('Fecha Saldo' in line[0]):
                    if line[3] < 0:
                        line_dict['account_id'] = credit_account
                    elif line[3] > 0:
                        line_dict['account_id'] = debit_account
                    
                    if line_count >= 3 and line[1]:
                        date_line = line[1][-4:]+'-'+line[1][3:5]+'-'+line[1][0:2]
                    line_dict['date'] = date_line
                    line_dict['ref'] = line[6]
                    line_dict['name'] = line[2]
                    amount = 0
                    if line[3] > 0 and line_count >= 3:
                        amount = line[3]
                    line_dict['amount'] = amount
                    line_dict['sequence'] = line_count
                    line_dict['statement_origin_id'] = statement
                    line_dict['statement_id'] = statement
                    result.append((0, 0, line_dict))
                    
            statement_vals = {
                'name': (parser_code)+'_'+date_obj,
                'balance_start': begin_amount,
                'balance_end_real': ending_amount,
                'date': date_obj,
                'period_id': period_id,
                'file': statements_file,
                'line_ids': result,
                'file_name': (parser_code)+'_'+date_obj+'.txt'
            }
            statement_obj.write(cr, uid, [statement], statement_vals, context=context)
            statement_obj.button_dummy(cr, uid, [statement], context=context)
            
            if not statement:
                st_error_cnt += 1
            st_cnt += 1
            log_count = {
                "total_cnt": total_cnt,
                "skipped_cnt": skipped_cnt,
                "error_cnt": error_cnt,
                "st_cnt": st_cnt,
                "st_error_cnt": st_error_cnt
            }
            log = self.make_log(cr, uid, ids, log_count, context)
            text_log = '\n'.join(log)
            domain = [('id','in',[statement])]
            return {
                'domain': domain,
                'name': 'Imported statement',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.bank.statement',
                'type': 'ir.actions.act_window', 
            }
        
        # Banco AVVillas
            
        if parser_code == 'AVVillas':
            result = []
            log_list = []
            dialect = csv.excel()
            dialect.quotechar = '"'
            dialect.delimiter = ','
            lines = base64.decodestring(statements_file).split('\n')
            line_count = 0
            period = 0
            date = time.strftime('%Y-%m-%d')
            st_cnt, st_error_cnt, total_cnt, skipped_cnt, error_cnt  = 0, 0, 0, 0, 0
            
            statement_vals = {
                'journal_id': journal_id,
            }
            statement = statement_obj.create(cr, uid, statement_vals, context=context)
            
            for line in csv.reader(lines, dialect=dialect):
                line_count +=1
                if line and len(line)!= 10:
                    raise osv.except_osv(_('Error !'), _('El archivo seleccionado no tiene el formato seleccionado!'))
                line_dict = {}
                if line_count == 0:
                    continue
                if line_count <= 9:
                    total_cnt += 1
                if not line and len(line)==10:
                    skipped_cnt += 1
                    error_cnt += 1
                if line and len(line)==10 and line[1] and line[2] and line_count >= 3:
                    date = line[1][0:4]+'-'+line[1][4:6]+'-'+line[1][6:8]
                    period = line[0][4:6]+'/'+line[0][0:4]
                    period_ids = account_period.search(cr, uid, [('code', '=', period), ('company_id','=', company_id)])
                    if period_ids:
                        period_id = period_ids[0]
                    else:
                        raise osv.except_osv(_('Error !'), _('El periodo con el codigo "%s" no existe!')%(period))
                    if ('C' in line[8]):
                        line_dict['amount'] = float(line[5])
                        line_dict['account_id'] = credit_account
                    elif ('D' in line[8]):
                        line_dict['amount'] = -float(line[5])
                        line_dict['account_id'] = debit_account
                    
                    line_dict['date'] = date
                    line_dict['ref'] = line[9]
                    line_dict['name'] = line[3]
                    line_dict['sequence'] = line_count
                    line_dict['statement_origin_id'] = statement
                    line_dict['statement_id'] = statement
                    result.append((0, 0, line_dict))
                    
            statement_vals = {
                'name': (parser_code)+'_'+date,
                'date': date,
                'period_id': period_id,
                'file': statements_file,
                'line_ids': result,
                'file_name': (parser_code)+'_'+date+'.txt'
            }
            statement_obj.write(cr, uid, [statement], statement_vals, context=context)
            statement_obj.button_dummy(cr, uid, [statement], context=context)
            
            if not statement:
                st_error_cnt += 1
            st_cnt += 1
            log_count = {
                "total_cnt": total_cnt,
                "skipped_cnt": skipped_cnt,
                "error_cnt": error_cnt,
                "st_cnt": st_cnt,
                "st_error_cnt": st_error_cnt
            }
            log = self.make_log(cr, uid, ids, log_count, context)
            text_log = '\n'.join(log)
            domain = [('id','in',[statement])]
            return {
                'domain': domain,
                'name': 'Imported statement',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.bank.statement',
                'type': 'ir.actions.act_window', 
            }

        # Banco Popular
            
        if parser_code == 'Popular':
            result = []
            log_list = []
            dialect = csv.excel()
            dialect.quotechar = '"'
            dialect.delimiter = ','
            lines = base64.decodestring(statements_file).split('\n')
            line_count = 0
            period = 0
            date = time.strftime('%Y-%m-%d')
            st_cnt, st_error_cnt, total_cnt, skipped_cnt, error_cnt  = 0, 0, 0, 0, 0
            
            statement_vals = {
                'journal_id': journal_id,
            }
            statement = statement_obj.create(cr, uid, statement_vals, context=context)
            
            for line in csv.reader(lines, dialect=dialect):
                line_count +=1
                if line and len(line)!= 12:
                    raise osv.except_osv(_('Error !'), _('El archivo seleccionado no tiene el formato seleccionado!'))
                line_dict = {}
                if line_count == 0:
                    continue
                if line_count <= 11:
                    total_cnt += 1
                if not line and len(line)==12:
                    skipped_cnt += 1
                    error_cnt += 1
                        
                if line and len(line)==12 and line[1] and line[2] and line_count >= 3:
                    date = line[0][0:4]+'-'+line[0][4:6]+'-'+line[0][6:8]
                    period = line[0][4:6]+'/'+line[0][0:4]
                    period_ids = account_period.search(cr, uid, [('code', '=', period), ('company_id','=', company_id)])
                    if period_ids:
                        period_id = period_ids[0]
                    else:
                        raise osv.except_osv(_('Error !'), _('El periodo con el codigo "%s" no existe!')%(period))
                    
                    if ('C' in line[11]):
                        line_dict['amount'] = -float(line[8])
                        line_dict['account_id'] = credit_account
                    elif ('D' in line[11]):
                        line_dict['amount'] = float(line[8])
                        line_dict['account_id'] = debit_account
                    
                    line_dict['date'] = date
                    line_dict['ref'] = line[3]
                    line_dict['name'] = line[5]
                    line_dict['sequence'] = line_count
                    line_dict['statement_origin_id'] = statement
                    line_dict['statement_id'] = statement
                    result.append((0, 0, line_dict))
                    
            statement_vals = {
                'name': (parser_code)+'_'+date,
                'date': date,
                'period_id': period_id,
                'file': statements_file,
                'line_ids': result,
                'file_name': (parser_code)+'_'+date+'.txt'
            }
            statement_obj.write(cr, uid, [statement], statement_vals, context=context)
            statement_obj.button_dummy(cr, uid, [statement], context=context)
            
            if not statement:
                st_error_cnt += 1
            st_cnt += 1
            log_count = {
                "total_cnt": total_cnt,
                "skipped_cnt": skipped_cnt,
                "error_cnt": error_cnt,
                "st_cnt": st_cnt,
                "st_error_cnt": st_error_cnt
            }
            log = self.make_log(cr, uid, ids, log_count, context)
            text_log = '\n'.join(log)
            domain = [('id','in',[statement])]
            return {
                'domain': domain,
                'name': 'Imported statement',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.bank.statement',
                'type': 'ir.actions.act_window', 
            }
            
        # Banco Sudameris
            
        if parser_code == 'Sudameris':
            result = []
            log_list = []
            dialect = csv.excel()
            dialect.quotechar = '"'
            dialect.delimiter = ','
            lines = base64.decodestring(statements_file).split('\n')
            line_count = 0
            ending_amount = 0.0
            begin_amount = 0
            ending_amount = 0
            period = 0
            date = time.strftime('%Y-%m-%d')
            st_cnt, st_error_cnt, total_cnt, skipped_cnt, error_cnt  = 0, 0, 0, 0, 0
            
            statement_vals = {
                'journal_id': journal_id,
            }
            statement = statement_obj.create(cr, uid, statement_vals, context=context)
            
            for line in csv.reader(lines, dialect=dialect):
                line_count +=1
                
                if line and len(line)!= 7:
                    raise osv.except_osv(_('Error !'), _('El archivo seleccionado no tiene el formato seleccionado!'))
                line_dict = {}
                if line_count == 0:
                    continue
                if line_count <= 6:
                    total_cnt += 1
                if not line and len(line)==7:
                    skipped_cnt += 1
                    error_cnt += 1
                    
                if line and len(line)==7 and line[0] and line[4] and line_count >= 4:
                    if 'Saldo Inicial' in line[4]:
                        begin_amount = line[5]
                
                    if 'Saldo Final' in line[4]:
                        ending_amount = line[5]
                        
                if line and len(line)==7 and line[0] and line[4] and line_count >=6 and not ('****' in line[0]):
                        
                    date = '20'+line[0][-2:]+'-'+line[0][3:5]+'-'+line[0][0:2]
                    period = line[0][3:5]+'/'+'20'+line[0][-2:]
                    period_ids = account_period.search(cr, uid, [('code', '=', period), ('company_id','=', company_id)])
                    if period_ids:
                        period_id = period_ids[0]
                    else:
                        raise osv.except_osv(_('Error !'), _('El periodo con el codigo "%s" no existe!')%(period))
                    amount = 0
                    if ('C' in line[2]):
                        line_dict['amount'] = -float(line[4])
                        line_dict['account_id'] = credit_account
                    elif ('D' in line[2]):
                        line_dict['amount'] = float(line[4])
                        line_dict['account_id'] = debit_account
                    
                    line_dict['date'] = date
                    line_dict['ref'] = line[6]
                    line_dict['name'] = line[1]
                    line_dict['sequence'] = line_count
                    line_dict['statement_origin_id'] = statement
                    line_dict['statement_id'] = statement
                    result.append((0, 0, line_dict))
                    
            statement_vals = {
                'name': (parser_code)+'_'+date,
                'balance_start': begin_amount,
                'balance_end_real': ending_amount,
                'date': date,
                'period_id': period_id,
                'file': statements_file,
                'line_ids': result,
                'file_name': (parser_code)+'_'+date+'.txt'
            }
            statement_obj.write(cr, uid, [statement], statement_vals, context=context)
            statement_obj.button_dummy(cr, uid, [statement], context=context)
            
            if not statement:
                st_error_cnt += 1
            st_cnt += 1
            log_count = {
                "total_cnt": total_cnt,
                "skipped_cnt": skipped_cnt,
                "error_cnt": error_cnt,
                "st_cnt": st_cnt,
                "st_error_cnt": st_error_cnt
            }
            log = self.make_log(cr, uid, ids, log_count, context)
            text_log = '\n'.join(log)
            domain = [('id','in',[statement])]
            return {
                'domain': domain,
                'name': 'Imported statement',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.bank.statement',
                'type': 'ir.actions.act_window', 
            }
            
        # Banco Occidente
        if parser_code == 'Occidente':
	    if not context: context = {}
	    rec = self.browse(cr, uid, ids[0], context)
            file_path = tempfile.gettempdir()+'/occidente.xlsx'
            data = rec.file
            f = open(file_path,'wb')
            f.write(data.decode('base64'))
            f.close()
            book = xlrd.open_workbook(file_path)
            sh = book.sheet_by_index(0)
            result = []
            log_list = []
            line_count = 0
            ending_amount = 0.0
            begin_amount = 0
            ending_amount = 0
            period = 0
            date = time.strftime('%Y-%m-%d')
            st_cnt, st_error_cnt, total_cnt, skipped_cnt, error_cnt  = 0, 0, 0, 0, 0
            
            statement_vals = {
                'journal_id': journal_id,
            }
            statement = statement_obj.create(cr, uid, statement_vals, context=context)
            
            fuera = False
            for line in range(sh.nrows):
                if line >= 9:
                    line_dict = {}
                    
                    if sh.cell_value(rowx=line, colx=0) and sh.cell_value(rowx=line, colx=1) and sh.cell_value(rowx=line, colx=2):
		        if 'Saldo Inicial' in str(sh.cell_value(rowx=line, colx=0)):
                            begin_amount = str(sh.cell_value(rowx=line, colx=1)).replace(',','').replace('$','').strip(' ')
                        if 'Saldo Final' in str(sh.cell_value(rowx=line, colx=0)):
                            ending_amount = str(sh.cell_value(rowx=line, colx=1)).replace(',','').replace('$','').strip(' ')
		        if 'Saldo Inicial' in str(sh.cell_value(rowx=line, colx=0)):
		            fuera = True
		        if not fuera:
			    if period_id.date_start[0:4] != str(sh.cell_value(rowx=line, colx=0))[0:4]:
				raise osv.except_osv(_('Error !'), _('El periodo indicado no coincide con el año de los movimientos a importar! linea: %s')%(line))
			    if period_id.date_start[5:7] != str(sh.cell_value(rowx=line, colx=0))[4:6]:
				raise osv.except_osv(_('Error !'), _('El periodo indicado no coincide con el mes de los movimientos a importar! linea: %s')%(line))    
				
			    date = str(sh.cell_value(rowx=line, colx=0))[0:4]+'-'+str(sh.cell_value(rowx=line, colx=0))[4:6]+'-'+str(sh.cell_value(rowx=line, colx=0))[6:8]
			    amount = 0
			    if float(str(sh.cell_value(rowx=line, colx=5)).replace(',','').replace('$','').strip(' ')) > 0:
				line_dict['amount'] = float(str(sh.cell_value(rowx=line, colx=5)).replace(',','').replace('$','').strip(' '))
				line_dict['account_id'] = credit_account
			    elif float(str(sh.cell_value(rowx=line, colx=4)).replace(',','').replace('$','').strip(' ')) > 0:
				line_dict['amount'] = -float(str(sh.cell_value(rowx=line, colx=4)).replace(',','').replace('$','').strip(' '))
				line_dict['account_id'] = debit_account
			    
			    line_dict['date'] = date
			    line_dict['ref'] = str(sh.cell_value(rowx=line, colx=1)).replace('.0','')
			    line_dict['name'] = sh.cell_value(rowx=line, colx=2)
			    line_dict['sequence'] = line
			    line_dict['statement_origin_id'] = statement
			    line_dict['statement_id'] = statement
			    result.append((0, 0, line_dict))
                    
            statement_vals = {
                'name': (parser_code)+'_'+date,
                'balance_start': begin_amount,
                'balance_end_real': ending_amount,
                'date': date,
                'period_id': period_id.id,
                'file': statements_file,
                'line_ids': result,
                'file_name': (parser_code)+'_'+date+'.txt'
            }
            statement_obj.write(cr, uid, [statement], statement_vals, context=context)
            statement_obj.button_dummy(cr, uid, [statement], context=context)
            
            if not statement:
                st_error_cnt += 1
            st_cnt += 1
            log_count = {
                "total_cnt": total_cnt,
                "skipped_cnt": skipped_cnt,
                "error_cnt": error_cnt,
                "st_cnt": st_cnt,
                "st_error_cnt": st_error_cnt
            }
            log = self.make_log(cr, uid, ids, log_count, context)
            text_log = '\n'.join(log)
            domain = [('id','in',[statement])]
            return {
                'domain': domain,
                'name': 'Imported statement',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.bank.statement',
                'type': 'ir.actions.act_window', 
            }
	  
	# Banco Bogota
        if parser_code == 'Bogota':
            result = []
            log_list = []
            dialect = csv.excel()
            dialect.quotechar = '"'
            dialect.delimiter = ','
            lines = base64.decodestring(statements_file).split('\n')
            line_count = 0
            ending_amount = 0.0
            begin_amount = 0
            ending_amount = 0
            period = 0
            date = time.strftime('%Y-%m-%d')
            st_cnt, st_error_cnt, total_cnt, skipped_cnt, error_cnt  = 0, 0, 0, 0, 0
            
            statement_vals = {
                'journal_id': journal_id,
            }
            statement = statement_obj.create(cr, uid, statement_vals, context=context)
            
            for line in csv.reader(lines, dialect=dialect):
                line_count +=1
                if not period_id.id:
		    raise osv.except_osv(_('Error !'), _('Debe seleccionar un periodo!'))

                if line and len(line)!= 7:
                    raise osv.except_osv(_('Error !'), _('El archivo seleccionado no tiene el formato seleccionado!'))

                line_dict = {}
                if line_count == 0:
                    continue
                if line_count <= 6:
                    total_cnt += 1
                if not line and len(line)==7:
                    skipped_cnt += 1
                    error_cnt += 1
                
                if line and len(line)==7 and line[0] and line[1] and line_count == 4:
		    if line[0]>0:
			begin_amount = line[0].replace('$','').replace(',','')
		    if line[1]>0:
			ending_amount = line[1].replace('$','').replace(',','')
                        
                if line and len(line)==7 and line[0] and line[4] and line_count >=6 and not ('****' in line[0]):
		    if line[0][:2] != period_id.date_start[5:7]:
		        raise osv.except_osv(_('Error !'), _('El mes del extracto bancario no coincide con el indicado en el periodo.!'))    
                    date = period_id.fiscalyear_id.date_start[:4]+'-'+line[0][:2]+'-'+line[0][-2:]
                    line_dict['amount'] = float(line[3].replace('$','').replace(',',''))
                    line_dict['account_id'] = debit_account
                    if line_dict['amount'] ==0.0:
		        line_dict['amount'] = -float(line[4].replace('$','').replace(',',''))
		        line_dict['account_id'] = credit_account
                    if line_dict['amount'] == 0.0:
                        raise osv.except_osv(_('Error !'), _('Debito y Crédito no deben ser ceros!'))
                    line_dict['date'] = date
                    line_dict['name'] = line[1].strip()
                    line_dict['sequence'] = line_count
                    line_dict['statement_origin_id'] = statement
                    line_dict['statement_id'] = statement
                    result.append((0, 0, line_dict))
                    
            statement_vals = {
                'name': (parser_code)+'_'+date,
                'balance_start': begin_amount,
                'balance_end_real': ending_amount,
                'date': date,
                'period_id': period_id.id,
                'file': statements_file,
                'line_ids': result,
                'file_name': (parser_code)+'_'+date+'.txt'
            }
            statement_obj.write(cr, uid, [statement], statement_vals, context=context)
            statement_obj.button_dummy(cr, uid, [statement], context=context)
            
            if not statement:
                st_error_cnt += 1
            st_cnt += 1
            log_count = {
                "total_cnt": total_cnt,
                "skipped_cnt": skipped_cnt,
                "error_cnt": error_cnt,
                "st_cnt": st_cnt,
                "st_error_cnt": st_error_cnt
            }
            log = self.make_log(cr, uid, ids, log_count, context)
            text_log = '\n'.join(log)
            domain = [('id','in',[statement])]
            return {
                'domain': domain,
                'name': 'Imported statement',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.bank.statement',
                'type': 'ir.actions.act_window', 
            }
	  
       # Banco BBVA
        if parser_code == 'BBVA':
            result = []
            log_list = []
            dialect = csv.excel()
            dialect.quotechar = '"'
            dialect.delimiter = '	'
            lines = base64.decodestring(statements_file).split('\n')
            line_count = 0
            ending_amount = 0.0
            movimiento=0
            begin_amount = 0.0
            ending_amount = 0.0
            period = 0
            date = time.strftime('%Y-%m-%d')
            st_cnt, st_error_cnt, total_cnt, skipped_cnt, error_cnt  = 0, 0, 0, 0, 0
            
            statement_vals = {
                'journal_id': journal_id,
            }
            statement = statement_obj.create(cr, uid, statement_vals, context=context)
            
            for line in csv.reader(lines, dialect=dialect):
                line_count +=1
                if not period_id.id:
		    raise osv.except_osv(_('Error !'), _('Debe seleccionar un periodo!'))

                line_dict = {}
                if line_count == 0:
                    continue
                if line_count <= 6:
                    total_cnt += 1
                if not line and len(line)==8:
                    skipped_cnt += 1
                    error_cnt += 1
                
                if line and len(line)==8 and ('Saldo Inicial' in line[0] or 'Saldo Final' in line[5]):
		    begin_amount = float(line[2].replace('$','').replace(',','')) or 0.0
		    ending_amount = float(line[7].replace('$','').replace(',','')) or 0.0

		if line and len(line)==8 and line[2] and line[3] and line[5] and line[6] and line[7]  and line_count >=11:
		    movimiento += 1
		    if line[0][3:5] != period_id.date_start[5:7] and line[0][-2:] != period_id.date_start[2:4]:
		        raise osv.except_osv(_('Error !'), _('El mes del extracto bancario no coincide con el indicado en el periodo.!'))    
                    date = period_id.fiscalyear_id.date_start[:4]+'-'+line[0][3:5]+'-'+line[0][:2]
                    amount = float(line[5].replace('$','').replace(',','')) or 0.0
                    line_dict['amount'] = amount
                    if amount >0:
		        line_dict['account_id'] = debit_account  
		    elif amount <0:
		        line_dict['account_id'] = credit_account
		    else:
		        raise osv.except_osv(_('Error !'), _('Debito y Crédito no deben ser ceros!'))

                    line_dict['date'] = date
                    line_dict['ref'] = line[7]
                    line_dict['name'] = (line[3] + ' - ' + line[4]).strip()
                    line_dict['sequence'] = movimiento
                    line_dict['statement_origin_id'] = statement
                    line_dict['statement_id'] = statement
                    result.append((0, 0, line_dict))
                    
            if not begin_amount or not ending_amount:
	        raise osv.except_osv(_('Error !'), _('El archivo seleccionado no tiene el formato seleccionado!'))
            statement_vals = {
                'name': (parser_code)+'_'+date,
                'balance_start': begin_amount,
                'balance_end_real': ending_amount,
                'date': date,
                'period_id': period_id.id,
                'file': statements_file,
                'line_ids': result,
                'file_name': (parser_code)+'_'+date+'.txt'
            }
            statement_obj.write(cr, uid, [statement], statement_vals, context=context)
            statement_obj.button_dummy(cr, uid, [statement], context=context)
            
            if not statement:
                st_error_cnt += 1
            st_cnt += 1
            log_count = {
                "total_cnt": total_cnt,
                "skipped_cnt": skipped_cnt,
                "error_cnt": error_cnt,
                "st_cnt": st_cnt,
                "st_error_cnt": st_error_cnt
            }
            log = self.make_log(cr, uid, ids, log_count, context)
            text_log = '\n'.join(log)
            domain = [('id','in',[statement])]
            return {
                'domain': domain,
                'name': 'Imported statement',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': False,
                'res_model': 'account.bank.statement',
                'type': 'ir.actions.act_window', 
            }