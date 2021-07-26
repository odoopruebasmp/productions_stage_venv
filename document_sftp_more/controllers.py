# -*- coding: utf-8 -*-
from openerp import http

# class DocumentSftpMore(http.Controller):
#     @http.route('/document_sftp_more/document_sftp_more/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/document_sftp_more/document_sftp_more/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('document_sftp_more.listing', {
#             'root': '/document_sftp_more/document_sftp_more',
#             'objects': http.request.env['document_sftp_more.document_sftp_more'].search([]),
#         })

#     @http.route('/document_sftp_more/document_sftp_more/objects/<model("document_sftp_more.document_sftp_more"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('document_sftp_more.object', {
#             'object': obj
#         })