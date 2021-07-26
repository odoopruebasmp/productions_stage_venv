# -*- coding: utf-8 -*-
from openerp import http

# class ConsultorFuncional(http.Controller):
#     @http.route('/consultor_funcional/consultor_funcional/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/consultor_funcional/consultor_funcional/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('consultor_funcional.listing', {
#             'root': '/consultor_funcional/consultor_funcional',
#             'objects': http.request.env['consultor_funcional.consultor_funcional'].search([]),
#         })

#     @http.route('/consultor_funcional/consultor_funcional/objects/<model("consultor_funcional.consultor_funcional"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('consultor_funcional.object', {
#             'object': obj
#         })