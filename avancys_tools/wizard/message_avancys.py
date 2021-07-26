from openerp.osv import osv, fields

class avancys_message_notificacion(osv.osv_memory):
    _name = 'avancys.message.notificacion'
    
    _columns = {
        'message': fields.text('Message', readonly=True),
        'title': fields.char('Title', size=128, readonly=True),
    }
    
    def _get_title(self, cr, uid, context=None):
        if context is None:
            context = {}
        return context.get('title', '')
    
    def _get_message(self, cr, uid, context=None):
        if context is None:
            context = {}
        return context.get('message', '')

    _defaults = {
        'message': _get_message,
        'title': _get_title,
    }
    
    def new_message(self, cr, uid, message, title,context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        ctx.update({'message': message,'title': title})
        return {'view_type' : 'form',
                'view_mode' : 'form',
                'view_id' : False,
                'res_model' : 'avancys.message.notificacion',
                'type' : 'ir.actions.act_window',
                'target' : 'new',
                'context' : ctx,}
    

#