# -*- coding: utf-8 -*-
import unicodedata
from datetime import datetime, timedelta
from html2text import html2text
from openerp import models, api, fields
from openerp.exceptions import Warning


class AvancysNotification(models.Model):
    _name = 'avancys.notification'

    user_id = fields.Many2one('res.users', 'Usuario')
    notification = fields.Char('Notificacion')
    tittle = fields.Char('Titulo')
    url = fields.Char('Url')
    date = fields.Datetime('Fecha de generacion')
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('sent', 'Enviada')
    ])
    persistent = fields.Boolean('Notificacion persistente')
    constructor_id = fields.Many2one('notification.constructor', 'constructor')
    modelo_id = fields.Integer('ID Registro')

    @api.model
    def get_notifications(self):
        notifications = self.env['avancys.notification'].search([
            ('user_id', '=', self.env.uid),
            ('state', '=', 'pending'),
            ('date', '<=', datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S'))
        ])
        data = []
        for message in notifications:
            data.append(
                {
                    'user_id': message.user_id.name,
                    'tittle': message.tittle,
                    'notification': message.notification,
                    'url': message.url,
                    'date': message.date,
                    'state': message.state
                }
            )
            if message.persistent is True:
                message.unlink()
            else:
                message.state = 'sent'
        return data


class NotificationConstructor(models.Model):
    _name = 'notification.constructor'

    name = fields.Char('Descripcion')
    table = fields.Many2one('ir.model', 'Modelo')
    field_user = fields.Char('Campo usuario')
    is_partner = fields.Boolean('Es contacto')
    tittle = fields.Char(
        'Titulo de la notificacion',
        help="""Si es un constructor agrupado asignar un texto plano,
            sino asignar el campo o el simbolo '-' seguido de texto plano""")
    field_notification = fields.Char(
        'Campo notificacion',
        help="""Si es un constructor agrupado asignar un texto plano,
            sino asignar el campo o el simbolo '-' seguido de texto plano""")
    notification_html = fields.Boolean('Es html')
    url = fields.Char('Url', help="Especificar direccion desde /web... comodin {id} si se requiere ir a un registro")
    url_id = fields.Char('ID URL', help="'id' o Campo tipo objeto relacionado")
    grouped = fields.Boolean('Agrupado')
    persistent = fields.Boolean('Notificacion Persistente')
    condition_ids = fields.One2many('notification.constructor.line', 'constructor_id', string="Condiciones")
    user_from = fields.Char('Remitente', help='Permite mapeo de campos a un nivel, ej: message_id.email_from')

    @api.model
    def get_notification(self):
        self.env.cr.execute("SELECT id FROM notification_constructor")
        notif_constructor_obj = self.env['notification.constructor']
        constructors = self.env.cr.fetchall()
        for cons in constructors:
            notif_constructor_obj.browse(cons).create_notifications()

    @api.multi
    def create_notifications(self):
        avancys_notif_obj = self.env['avancys.notification']
        dominio = []
        for line in self.condition_ids:
            if line.c2[0:3] == "now":
                if line.c2[4:5] == '+':
                    date = datetime.now() + timedelta(minutes=int(line.c2[6:len(line.c2)]))
                elif line.c2[4:5] == '-':
                    date = datetime.now() - timedelta(minutes=int(line.c2[6:len(line.c2)]))
                elif len(line.c2) == 3:
                    date = datetime.now()
                else:
                    raise Warning('Las condiciones de fecha no son validas')
                date = datetime.strftime(date, '%Y-%m-%d %H:%M:%S')
                crit = (str(line.c1), str(line.operator), date)
            else:
                if str(line.c2) == 'True':
                    cond = True
                elif str(line.c2) == 'False':
                    cond = False
                else:
                    cond = str(line.c2)
                crit = (str(line.c1), str(line.operator), cond)
            dominio.append(crit)
        modelo_ids = self.env[self.table.model].search(dominio)
        notif_data = []
        orm2sql = self.env['avancys.orm2sql']

        if not self.grouped:
            for i in modelo_ids:
                for user in getattr(i, self.field_user):
                    if self.is_partner:
                        user_notification = user.system_user_id.id
                    else:
                        user_notification = user.id
                    if self.persistent:
                        user_constructor = avancys_notif_obj.search([
                            ('constructor_id', '=', self.id),
                            ('user_id', '=', user_notification),
                            ('modelo_id', '=', i.id),
                            ('state', '=', 'pending')])
                    else:
                        user_constructor = avancys_notif_obj.search([
                            ('constructor_id', '=', self.id),
                            ('user_id', '=', user_notification),
                            ('modelo_id', '=', i.id)])
                    if len(user_constructor) > 0:
                        continue

                    if self.tittle[0] == '-':
                        tittle = self.tittle[1:len(self.tittle)]
                    else:
                        if '.' in self.tittle:
                            tittle = getattr(getattr(i, self.tittle.split('.')[0])[0], self.tittle.split('.')[1])
                        else:
                            tittle = getattr(i, self.tittle)

                        try:
                            tittle = tittle[0].display_name
                        except:
                            if tittle:
                                if len(tittle) == 0:
                                    tittle = False
                                else:
                                    pass
                            else:
                                tittle = False

                    user_from = False
                    if self.user_from:
                        if '.' in self.user_from:
                            user_from = getattr(
                                getattr(i, self.user_from.split('.')[0])[0], self.user_from.split('.')[1])
                        else:
                            user_from = getattr(i, self.user_from)
                        try:
                            user_from = user_from[0].display_name
                        except:
                            if len(user_from) == 0:
                                user_from = False
                            else:
                                pass
                        if tittle and user_from:
                            if len(user_from.split(' ')) > 2:
                                user_from = user_from.split(' ')[0] + ' ' + user_from.split(' ')[1]
                            tittle = user_from + ': ' + tittle
                        elif user_from:
                            tittle = user_from

                    if self.field_notification[0] == '-':
                        field_notification = self.field_notification[1:len(self.tittle)]
                    else:

                        if '.' in self.field_notification:
                            field_notification = getattr(i, self.field_notification.split('.')[0])
                            field_notification = getattr(field_notification[0], self.field_notification.split('.')[1])
                        else:
                            field_notification = getattr(i, self.field_notification)

                        try:
                            field_notification = field_notification[0].display_name
                        except:
                            if len(field_notification) == 0:
                                field_notification = False
                            else:
                                pass
                        if self.notification_html:
                            if field_notification:
                                field_notification = html2text(field_notification).replace('\n', '')
                            else:
                                field_notification = ''

                    if self.url:
                        if not self.url_id:
                            raise Warning(
                                "Debe especificar un campo relacionado al id para la url, por lo general es 'id'")
                        if self.url_id == 'id':
                            url_id = i.id
                        else:
                            url_id = getattr(i, self.url_id)[0].id
                        url = self.url.replace('{id}', str(url_id))
                    else:
                        url = False

                    if user_notification is False:
                        continue

                    notif_data.append({
                        'user_id': user_notification,
                        'tittle': tittle,
                        'notification': field_notification,
                        'url': url,
                        'state': 'pending',
                        'date': orm2sql.local_date(datetime.strftime(datetime.now(), '%Y-%m-%d') + " 00:00:00"),
                        'constructor_id': self.id,
                        'persistent': self.persistent,
                        'modelo_id': i.id,
                    })
        else:
            users = []
            for i in modelo_ids:
                for user in getattr(i, self.field_user):
                    if self.is_partner:
                        user_notification = user[0].system_user_id.id
                    else:
                        user_notification = user[0].id
                    if len(user) > 0:
                        if user_notification not in users:
                            users.append(user_notification)
            for user in users:
                if self.persistent:
                    user_constructor = avancys_notif_obj.search([
                        ('constructor_id', '=', self.id),
                        ('user_id', '=', user),
                        ('state', '=', 'pending')])
                else:
                    user_constructor = avancys_notif_obj.search([
                        ('constructor_id', '=', self.id),
                        ('user_id', '=', user)])
                if len(user_constructor) > 0:
                    continue
                if user is False:
                    continue
                notif_data.append({
                    'user_id': user,
                    'tittle': self.tittle,
                    'notification': self.field_notification,
                    'url': self.url,
                    'state': 'pending',
                    'date': orm2sql.local_date(datetime.strftime(datetime.now(), '%Y-%m-%d') + " 00:00:00"),
                    'constructor_id': self.id,
                    'persistent': self.persistent,
                })
        orm2sql.sqlcreate(self.env.uid, self.env.cr, 'avancys_notification', notif_data)
        return


class NotificationConstructorLine(models.Model):
    _name = 'notification.constructor.line'

    c1 = fields.Char('Campo de busqueda')
    operator = fields.Char('Operador')
    c2 = fields.Char(
        'Condicion',
        help='''
            Para relacionar la fecha actual, asignar la palabra 'now' y agregar el operador = o - con espacios
            intermedios, ej. 'now + 60' para compararla con la hora actual + 1 hora
        ''')
    constructor_id = fields.Many2one('notification.constructor', 'Constructor')
