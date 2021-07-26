from openerp import models, fields, api, _
import re
from openerp.http import request

class AvancysHelp(models.Model):
    _name = 'avancys.help'

    @api.model
    def get_video_url(self, pattern):
        res = {
            'url': '//www.youtube.com/embed/H3h3f6DZWdI?ecver=1',
            'menu_name': False
        }
        c = re.findall(r'menu_id=(.*?)&', pattern)
        if c:
            url = self.env['ir.ui.menu'].browse(int(c[0]))[0].video_url
            res['menu_name'] = _(self.env['ir.ui.menu'].browse(int(c[0]))[0].name)
            if url:
                res['url'] = str(url)
        return res

    @api.model
    def get_tour(self, pattern):
        # a = request
        res = []
        menu_id = False
        c = re.findall(r'menu_id=(.*?)&', pattern)
        if c:
            menu_id = self.env['ir.ui.menu'].browse(int(c[0]))[0]
        else:
            c = re.search(r'action=.*', pattern)
            if c:
                menu_id = self.env['ir.ui.menu'].search([('action', '=', int(c.group().split('=')[1]))])[0]
        if menu_id:
            view_type = re.findall(r'view_type=(.*?)&', pattern)
            if view_type:
                view_type = view_type[0]
                tour = self.env['avancys.help.tour'].search([
                    ('menu_id', '=', menu_id.id), ('view_type', '=', view_type), ('state', '=', 'active')])
                if tour:
                    steps = tour[0].step_ids
                    for s in steps:
                        tsconfig = {
                            'element': s.element,
                            'title': s.title,
                            'content': s.content,
                            'backdrop': s.backdrop,
                            'placement': s.placement,
                        }
                        if s.advanced:
                            adicionales = s.advanced.split(',')
                            for a in adicionales:
                                parg = a.split(':')
                                if parg[1] == 'true':
                                    parg[1] = True
                                elif parg[1] == 'false':
                                    parg[1] = False
                                tsconfig[parg[0]] = parg[1]
                        res.append(tsconfig)

        return res


class AvancysHelpTour(models.Model):
    _name = 'avancys.help.tour'
    view_type = fields.Selection([('form', 'Formulario'), ('tree', 'Arbol'), ('calendar', 'Calendario'),
                                  ('kanban', 'Kanban'), ('gantt', 'Gantt')], string="Tipo de vista")
    state = fields.Selection([('inactive', 'Inactivo'), ('active', 'Activo')], default='active')
    step_ids = fields.One2many('avancys.help.tour.step', 'tour_id', string="Tour steps")
    menu_id = fields.Many2one('ir.ui.menu', 'Menu')

    @api.multi
    def activate(self):
        self.state = 'active'

    @api.multi
    def inactivate(self):
        self.state = 'inactive'


class AvancysHelpTourStep(models.Model):
    _name = 'avancys.help.tour.step'
    element = fields.Char('Elemento (jquery selector)')
    title = fields.Char('Titulo')
    content = fields.Text('Contenido')
    backdrop = fields.Boolean('Enfoque')
    placement = fields.Selection([('right', 'Derecha'), ('left', 'Izquierda'), ('bottom', 'Abajo'), ('top', 'Arriba')],
                                 string="Ubicacion")
    advanced = fields.Text('Opciones avanzadas (dict)')
    sequence = fields.Integer('Secuencia')
    tour_id = fields.Many2one('avancys.help.tour', 'Tour')


class IrUiView(models.Model):
    _inherit = 'ir.ui.menu'

    video_url = fields.Char('URL tutorial')
    tour_ids = fields.One2many('avancys.help.tour', 'menu_id', string="Tour steps")



