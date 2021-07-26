# -*- encoding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2012 Serpent Consulting services
#                  All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import osv, fields
from openerp.tools.translate import _
import csv
import tempfile

class journal_entry_import_fast(osv.TransientModel):
    
    _name = 'journal.entry.import.fast'
    
    _columns = {
        'file': fields.binary('File'),
        'company_id':fields.many2one('res.company', 'Company'),
        'force_validate': fields.boolean('Forzar validacion', default=True)
    }
    
    def check_data(self, cr, uid, line, count,context=None):
        if not line[11]:
            raise osv.except_osv(_('Error !'), _('value is not proper, Please check CSV line %d,'%(count+1)))
    
    def read_file(self, cr, uid, ids, context=None):
        if not context: context = {}
        data_dict = {}
        account_journal = self.pool.get('account.journal')
        account_period = self.pool.get('account.period')
        partner_obj = self.pool.get('res.partner')
        account_obj = self.pool.get('account.account')
        analytic_obj = self.pool.get('account.analytic.account')
        ot_obj = self.pool.get('mrp.repair')
        
        rec = self.browse(cr, uid, ids[0], context)
        file_path = tempfile.gettempdir()+'/journal_import.csv'
        f = open(file_path,'wb')
        f.write(rec.file.decode('base64'))
        f.close()
        move_line = []
        line_count = 0
        records = []
        data_dict = {}
        partner_dict, account_dict,analytic_account = {}, {}, {}
        data_reader = csv.reader(open(file_path))
        for line in data_reader:
            line_dict = {}
            if line_count == 0:
                line_count += 1
                continue
            #self.check_data(cr, uid, line, line_count, context)
            if line[0] and line_count != 0:
                if data_dict:
                    data_dict['line_id'] = move_line
                    move_line = []
                    records.append(data_dict)
                    data_dict = {}
                journal_ids = account_journal.search(cr, uid, [('name', '=', line[0])])
                if journal_ids:
                    data_dict['journal_id'] = journal_ids[0]
                else:
                    raise osv.except_osv(_('Error!'), _('No journals with name %s,'%(line[0])))
                period_ids = account_period.search(cr, uid, [('code', '=', line[1])])
                if period_ids:
                    data_dict['period_id'] = period_ids[0]
                else:
                    raise osv.except_osv(_('Error!'), _('No periods with code %s,'%(line[1])))
                if line[3].__len__() > 64:
                    data_dict['ref'] = line[3][0:64]
                else:
                    data_dict['ref'] = line[3]
                data_dict['date'] = line[4]
                data_dict['narration'] = line[2]
            #account.move.line
            if line[5].__len__() > 64:
                line_dict['name'] = line[5][0:64]
            else:
                line_dict['name'] = line[5]
            line_dict['date'] = line[6]
            if line[7].__len__() > 32:
                line_dict['ref'] = line[7][0:32]
            else:
                line_dict['ref'] = line[7]
            if line[8].__len__() > 32:
                line_dict['ref1'] = line[8][0:32]
            else:
                line_dict['ref1'] = line[8]
            if line[9].__len__() > 32:
                line_dict['ref2'] = line[9][0:32]
            else:
                line_dict['ref2'] = line[9]
                
            if line[10]:
                if not partner_dict.get(line[10]):
                    partner_ids = partner_obj.search(cr, uid, [('ref', '=', line[10])])
                    if partner_ids:
                        line_dict['partner_id'] = partner_ids[0]
                        partner_dict[line[10]] = partner_ids[0]
                    else:
                        raise osv.except_osv(_('Error!'), _('No record found for partner with ref %s,'%(line[10])))
                else:
                    line_dict['partner_id'] = partner_dict.get(line[10])
            
            if line[11]:
                if not account_dict.get(line[11]):
                    account_ids = account_obj.search(cr, uid, [('code', '=', line[11])])
                    if account_ids:
                        line_dict['account_id'] = account_ids[0]
                        account_dict[line[11]] = account_ids[0]
                    else:
                        raise osv.except_osv(_('Error!'), _('No record found for Account with ref %s,'%(line[11])))
                else:
                    line_dict['account_id'] = account_dict.get(line[11])
            
            if line[14]:
                if not analytic_account.get(line[14]):
                    account_ids = analytic_obj.search(cr, uid, [('name', '=', line[14])])
                    if account_ids:
                        line_dict['analytic_account_id'] = account_ids[0]
                        analytic_account[line[14]] = account_ids[0]
                    else:
                        raise osv.except_osv(_('Error!'), _('No record found for Account with ref %s,'%(line[14])))
                else:
                    line_dict['analytic_account_id'] = analytic_account.get(line[14])
                
            line_dict['debit'] = line[12]
            line_dict['credit'] = line[13]
            try:
                line_dict['date_maturity'] = line[15]
            except:
                line_dict['date_maturity'] = False
                
            try:
                line_dict['date_cartera'] = line[16]
            except:
                line_dict['date_cartera'] = False



            try:
                if line[17]:
                    ot_ids = ot_obj.search(cr, uid, [('name', '=', line[17])])
                    if ot_ids:
                        line_dict['ot'] = ot_ids[0]
                    else:
                        raise osv.except_osv(_('Error!'), _('No se encuentra la OT %s,'%(line[17])))
                else:
                    line_dict['ot'] = False
            except:
                line_dict['ot'] = False
            move_line.append((0, 0, line_dict))
            line_count += 1
        data_dict['line_id'] = move_line
        if data_dict:
            data_dict['line_id'] = move_line
            move_line = []
            records.append(data_dict)
            data_dict = {}
        return records
    
    def import_csv(self, cr, uid, ids, context = None):
        account_move_obj = self.pool.get('account.move')
        all_vals = self.read_file(cr, uid, ids, context)
        rec = self.browse(cr, uid, ids[0], context=context)
        m_ids = []
        
        
        for vals in all_vals:
            fv = rec.force_validate
            if fv:
                if vals.get('journal_id', False):
                    journal = self.pool.get('account.journal').browse(cr, uid, vals.get('journal_id'), context)
                    if journal.sequence_id:
                        name = self.pool.get('ir.sequence').next_by_id(cr, uid, journal.sequence_id.id, context=context)
                    else:
                        raise Warning("El diario id: {d} no tiene una secuencia asociada".format(d=journal.id))
                else:
                    raise Warning("No se ha definido un diario en el asiento a importar")
            else:
                name = '/'
            cr.execute('''insert into account_move (company_id,date,ref, journal_id, narration, name, state,period_id) values (%s,%s, %s, %s, %s, %s, %s, %s) RETURNING id''' ,
           (rec.company_id.id,vals.get('date'),vals.get('ref'),vals.get('journal_id'),vals.get('narration'),name, 'posted' if fv else 'draft', vals.get('period_id')))
            move_id = cr.fetchone()[0]
            m_ids.append(move_id)
            for line_t in vals.get('line_id'):             
                line = line_t[2]
                if line.get('ot', False):                    
                    cr.execute('''insert into account_move_line (company_id, state, credit, date_maturity, date, name, debit, ref1, ref2, ref, move_id, journal_id, account_id, period_id, partner_id,analytic_account_id,date_cartera,ot) values 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, %s,%s,%s,%s,%s,%s) ''' ,
                    (rec.company_id.id, 'valid' if fv else 'draft', line.get('credit',False) or 0.0, line.get('date_maturity', False) or None,line.get('date'), line.get('name'), line.get('debit',False) or 0.0, line.get('ref1'),line.get('ref2'),line.get('ref'),move_id, vals.get('journal_id'),line.get('account_id'),
                    vals.get('period_id'), line.get('partner_id'), line.get('analytic_account_id', False) or None, line.get('date_cartera',False) or None, line.get('ot',False) or None))
                else:
                    cr.execute('''insert into account_move_line (company_id, state, credit, date_maturity, date, name, debit, ref1, ref2, ref, move_id, journal_id, account_id, period_id, partner_id,analytic_account_id,date_cartera) values 
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, %s,%s,%s,%s,%s) ''' ,
                    (rec.company_id.id, 'valid' if fv else 'draft', line.get('credit',False) or 0.0, line.get('date_maturity', False) or None,line.get('date'), line.get('name'), line.get('debit',False) or 0.0, line.get('ref1'),line.get('ref2'),line.get('ref'),move_id, vals.get('journal_id'),line.get('account_id'),
                    vals.get('period_id'), line.get('partner_id'), line.get('analytic_account_id', False) or None, line.get('date_cartera',False) or None))

        domain = [('id','in',m_ids)]
        return {
            'domain': domain,
            'name': 'Imported Journal Entries',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'account.move',
            'type': 'ir.actions.act_window'
        }
