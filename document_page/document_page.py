# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.tools.translate import _
from openerp.osv import osv, fields
from openerp import addons, netsvc, SUPERUSER_ID
import math
import difflib

class ir_attachment(osv.osv):
    _inherit = 'ir.attachment'
    
    def create(self, cr, uid, vals, context=None):
        direc_obj = self.pool.get('document.directory')
        model_obj = self.pool.get('ir.model')
        if vals.get('res_model') and vals.get('res_id'):            
            modelo = self.pool.get(vals.get('res_model'))
            models = model_obj.search(cr, uid, [('model','=',vals.get('res_model'))],context=context)
            objecto = modelo.browse(cr, uid, [vals.get('res_id')], context=context)
            directorio = direc_obj.search(cr, uid, ['|',('ressource_parent_type_id','=',models[0]),('ressource_type_id','=',models[0])],context=context)
            directorio = direc_obj.browse(cr, uid, directorio, context=context)
            for direc in directorio:
                if direc.type == "directory":
                    vals.update({'parent_id': direc.id})
                elif direc.type == "ressource":
                    if not direc_obj.search(cr, SUPERUSER_ID, [('ressource_parent_type_id','=',models[0]),('type','=','directory'),('name','=',objecto.name)],context=context):
                        res = {
                            'name': objecto.name,
                            'parent_id': direc.id,
                            'type': 'directory',
                            'ressource_parent_type_id': models[0],
                        }
                        p = direc_obj.create(cr, uid, res, context=context)
                        vals.update({'parent_id': p})
        return super(ir_attachment, self).create(cr, uid, vals, context=context)
    

class document_page(osv.osv):
    _name = "document.page"
    _description = "Document Page"
    _order = 'name'

    def _get_page_index(self, cr, uid, page, link=True):
        index = []
        for subpage in page.child_ids:
            index += ["<li>"+ self._get_page_index(cr, uid, subpage) +"</li>"]
        r = ''
        if link:
            r = '<a href="#id=%s">%s</a>'%(page.id,page.name)
        if index:
            r += "<ul>" + "".join(index) + "</ul>"
        return r

    def _get_display_content(self, cr, uid, ids, name, args, context=None):
        res = {}
        for page in self.browse(cr, uid, ids, context=context):
            if page.type == "category":
               content = self._get_page_index(cr, uid, page, link=False)
            else:
               content = page.content
            res[page.id] =  content
        return res

    _columns = {
        'name': fields.char('Title', required=True),
        'type':fields.selection([('content','Content'), ('category','Category')], 'Type', help="Page type"),        
        'parent_id': fields.many2one('document.page', 'Category', domain=[('type','=','category')]),
        'child_ids': fields.one2many('document.page', 'parent_id', 'Children'),
        'content': fields.text("Content"),
        'display_content': fields.function(_get_display_content, string='Displayed Content', type='text'),
        'history_ids': fields.one2many('document.page.history', 'page_id', 'History'),
        'create_date': fields.datetime("Created on", select=True, readonly=True),
        'create_uid': fields.many2one('res.users', 'Author', select=True, readonly=True),
        'write_uid': fields.many2one('res.users', "Last Contributor", select=True),
        'write_date': fields.datetime("Last edited on", select=True, readonly=True),
        'groups_ids':fields.many2many('res.groups', 'relacion_groups_pages', 'groups_page_ids', 'page_groups_ids', 'Grupos'),
    }
    _defaults = {
        'type':'content',
        'nivel':'general',
    }

    def onchange_parent_id(self, cr, uid, ids, parent_id, content, context=None):
        res = {}
        if parent_id and not content:
            parent = self.browse(cr, uid, parent_id, context=context)
            if parent.type == "category":
                res['value'] = {
                    'content': parent.content,
                }
        return res

    def create_history(self, cr, uid, ids, vals, context=None):
        for i in ids:
            history = self.pool.get('document.page.history')
            if vals.get('content'):
                res = {
                    'content': vals.get('content', ''),
                    'page_id': i,
                }
                history.create(cr, uid, res)

    def create(self, cr, uid, vals, context=None):
        page_id = super(document_page, self).create(cr, uid, vals, context)
        self.create_history(cr, uid, [page_id], vals, context)
        return page_id

    def write(self, cr, uid, ids, vals, context=None):
        result = super(document_page, self).write(cr, uid, ids, vals, context)
        self.create_history(cr, uid, ids, vals, context)
        return result
    
    
class res_groups(osv.osv):
    _inherit = 'res.groups'
    
    _columns = {
        'page_ids': fields.many2many('document.page', 'relacion_groups_pages', 'page_groups_ids', 'groups_page_ids', 'Grupos'),
        }
    
class document_page_history(osv.osv):
    _name = "document.page.history"
    _description = "Document Page History"
    _order = 'id DESC'
    _rec_name = "create_date"

    _columns = {
          'page_id': fields.many2one('document.page', 'Page'),
          'summary': fields.char('Summary', size=256, select=True),
          'content': fields.text("Content"),
          'create_date': fields.datetime("Date"),
          'create_uid': fields.many2one('res.users', "Modified By"),
    }

    def getDiff(self, cr, uid, v1, v2, context=None):
        history_pool = self.pool.get('document.page.history')
        text1 = history_pool.read(cr, uid, [v1], ['content'])[0]['content']
        text2 = history_pool.read(cr, uid, [v2], ['content'])[0]['content']
        line1 = line2 = ''
        if text1:
            line1 = text1.splitlines(1)
        if text2:
            line2 = text2.splitlines(1)
        if (not line1 and not line2) or (line1 == line2):
            raise osv.except_osv(_('Warning!'), _('There are no changes in revisions.'))
        diff = difflib.HtmlDiff()
        return diff.make_table(line1, line2, "Revision-%s" % (v1), "Revision-%s" % (v2), context=True)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
