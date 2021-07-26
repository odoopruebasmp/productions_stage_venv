import sys
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.tools import safe_eval
from openerp.tools.safe_eval import _import
from openerp.tools.safe_eval import _SAFE_OPCODES
from openerp.tools.safe_eval import test_expr
from openerp.tools.safe_eval import _import
from openerp.tools.safe_eval import _SAFE_OPCODES
from openerp.tools.safe_eval import test_expr
from openerp.tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta
from opcode import HAVE_ARGUMENT, opmap, opname
from types import CodeType
import logging

_logger = logging.getLogger(__name__)

class mail_thread(osv.AbstractModel):
    _inherit = 'mail.thread'
    
    def _convert_for_display(self, cr, uid, value, col_info, context=None):
        if not value and col_info['type'] == 'boolean':
            return 'False'
        if not value:
            return ''
        if col_info['type'] == 'many2one':
            return value[1]
        elif col_info['type'] in ('one2many', 'many2many'):
            rel_object = self.pool.get(col_info['relation'])
            return rel_object.name_get(cr, uid, value, context=context)
        elif col_info['type'] == 'selection':
            return dict(col_info['selection'])[value]
        return value
    
    def message_track(self, cr, uid, ids, tracked_fields, initial_values, context=None):

        def convert_for_display(value, col_info):
            if not value and col_info['type'] == 'boolean':
                return 'False'
            if not value:
                return ''
            if col_info['type'] == 'many2one':
                return value[1]
            if col_info['type'] == 'selection':
                return dict(col_info['selection'])[value]
            return value

        def format_message(message_description, tracked_values):
            message = ''
            if message_description:
                message = '<span>%s</span>' % message_description
            for name, change in tracked_values.items():
                message += '<div> &nbsp; &nbsp; &bull; <b>%s</b>: ' % change.get('col_info')
                old_value = change.get('old_value')
                new_value = change.get('new_value')
                table = type(old_value) == list or type(new_value) == list
                if table:
                    message += '<table><tr><td>'
                if old_value:
                    if type(old_value) == list:
                        if new_value and type(new_value) == list:
                            old_value = set(old_value) - set(new_value)
                        old_value = '<br/>'.join([i[1] if len(i) > 1 else i for i in old_value])
                    message += '%s' % old_value
                    if table:
                        message += '</td><td> &rarr; </td><td>'
                    else:
                        message += ' &rarr; '
                if type(new_value) == list:
                    if old_value and type(old_value) == list:
                        new_value = set(new_value) - set(old_value)
                    new_value = '<br/>'.join([i[1] if len(i) > 1 else i for i in new_value])


                message += '%s' % new_value
                if table:
                    message += '</td></tr></table>'
                message += '</div>'
            return message

        if not tracked_fields:
            return True

        for record in self.read(cr, uid, ids, tracked_fields.keys(), context=context):
            initial = initial_values[record['id']]
            changes = []
            tracked_values = {}

            # generate tracked_values data structure: {'col_name': {col_info, new_value, old_value}}
            for col_name, col_info in tracked_fields.items():
                many_true = 'one2many' == col_info['type'] or 'many2many' == col_info['type']
                if many_true:
                    initial_value = not many_true and self._convert_for_display(cr, uid, initial[col_name], col_info, context=context) or False
                    record_value = self._convert_for_display(cr, uid, record[col_name], col_info, context=context)
                    if record_value == initial_value and getattr(self._all_columns[col_name].column, 'track_visibility', None) == 'always':
                        tracked_values[col_name] = dict(col_info=col_info['string'],
                                                            new_value=record_value)
                    elif record_value != initial_value or many_true:
                        if getattr(self._all_columns[col_name].column, 'track_visibility', None) in ['always', 'onchange']:
                            tracked_values[col_name] = dict(col_info=col_info['string'],
                                                                old_value=initial_value,
                                                                new_value=record_value)
                        if col_name in tracked_fields:
                            changes.append(col_name)
                
                else:
                    if record[col_name] == initial[col_name] and getattr(self._all_columns[col_name].column, 'track_visibility', None) == 'always':
                        tracked_values[col_name] = dict(col_info=col_info['string'],
                                                            new_value=convert_for_display(record[col_name], col_info))
                    elif record[col_name] != initial[col_name]:
                        if getattr(self._all_columns[col_name].column, 'track_visibility', None) in ['always', 'onchange']:
                            tracked_values[col_name] = dict(col_info=col_info['string'],
                                                                old_value=convert_for_display(initial[col_name], col_info),
                                                                new_value=convert_for_display(record[col_name], col_info))
                        if col_name in tracked_fields:
                            changes.append(col_name)
                        
            if not changes:
                continue

            # find subtypes and post messages or log if no subtype found
            subtypes = []
            for field, track_info in self._track.items():
                if field not in changes:
                    continue
                for subtype, method in track_info.items():
                    if method(self, cr, uid, record, context):
                        subtypes.append(subtype)

            posted = False
            for subtype in subtypes:
                try:
                    subtype_rec = self.pool.get('ir.model.data').get_object(cr, uid, subtype.split('.')[0], subtype.split('.')[1])
                except ValueError, e:
                    _logger.debug('subtype %s not found, giving error "%s"' % (subtype, e))
                    continue
                message = format_message(subtype_rec.description if subtype_rec.description else subtype_rec.name, tracked_values)
                self.message_post(cr, uid, record['id'], body=message, subtype=subtype, context=context)
                posted = True
            if not posted:
                message = format_message('', tracked_values)
                self.message_post(cr, uid, record['id'], body=message, context=context)
        return True
        
#