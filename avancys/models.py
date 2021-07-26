# -*- coding: utf-8 -*-

import pytz
import datetime
from datetime import timedelta
from openerp import models, fields, api
from openerp.exceptions import ValidationError, MissingError


class idea(models.Model):
     _name = 'avancys.idea'

     def _get_user(self):
        return self._uid

     @api.one
     @api.constrains('name', 'datefrom','groupIdea_ids')
     def _check_idea(self):
        if self.votes >0:
            raise ValidationError("Ya posee un voto por lo que no puede modificarse.")

        if self.create_uid.id != self._uid:
            raise ValidationError("Solo el usuario creador (%s) puede modificar la idea."%self.create_uid.name)

     @api.onchange('datefrom')
     def on_change_set_dateto(self):
         if self.datefrom:
            self.dateto = self._set_date_day(self.datefrom, 30)

     def _set_date_day(self, dates, param):
            date_to = datetime.datetime.strptime(dates, "%Y-%m-%d %H:%M:%S") + timedelta(days=param)
            return date_to

     @api.model
     def create(self, values):
         values['dateto'] = self._set_date_day(values['datefrom'], 30)
         result = super(idea, self).create(values)
         return result

     @api.multi
     def write(self, values):
	if values.get('datefrom')!=None:
     	 values['dateto'] = self._set_date_day(values['datefrom'],30)
        result = super(idea,self).write(values)
	return result

     @api.multi
     def unlink(self):
         if self.votes > 0:
             raise ValidationError("La Idea no se puede eliminar ya que posee al menos (1) voto asociado.")
         else:
             return models.Model.unlink(self)

     create_uid= fields.Many2one('res.users', 'Creador', required=True, readonly=True, default=_get_user)
     name = fields.Char(string='Nombre', required=True)
     description = fields.Text(string='Descripción')
     votes = fields.Integer(string='Votos', readonly=True)
     notes = fields.Float(string="Calificación promedio", readonly=True)
     groupIdea_ids = fields.Many2one('avancys.group_idea', required=True, ondelete='set null', readonly=False, string='Grupos de Ideas')
     datefrom = fields.Datetime(string='Fecha inicial', required=True)
     dateto = fields.Datetime(string='Fecha final', readonly=True, store=True, required=True)

     _sql_constraints = [
                     ('idea_name_unique',
                      'unique(name)',
                      'Selecciona otro nombre de idea, ya existe una con el mismo nombre.')]

     """@api.one
     def set_notes(self,val):
        self.notes = val"""

class groupIdea(models.Model):
    _name='avancys.group_idea'

    name = fields.Char(string='Nombre grupo', required=True)
    description = fields.Char(string='Descripción')
    idea_ids = fields.One2many('avancys.idea', 'groupIdea_ids', string='Ideas')

    _sql_constraints = [
                     ('group_idea_name_unique',
                      'unique(name)',
                      'Selecciona otro nombre de grupo, ya existe uno con el mismo nombre.')]

class usuarios(models.Model):
    _name = 'avancys.users'

    def _get_user(self):
        return self._uid

    create_uid=fields.Many2one('res.users', 'Persona', required=True, readonly=True, default=_get_user)
    votes = fields.Integer(string='Votos',default=0, required=True)
    notes = fields.Float(string='Promedio',default=0, required=True)

class votes(models.Model):
    _name='avancys.votes'

    def _get_user(self):
        return self._uid

    @api.multi
    def unlink(self):
        for w in self:
            if w.state == 'procesado':
                raise ValidationError("El voto se encuentra procesado, no puede eliminarse.")
        return models.Model.unlink(self)

    @api.depends('notes','idea_ids','create_uid')
    @api.one
    def votar(self):
        notes = 0
        #Incrementa la cantidad de votos
        self.idea_ids.votes = self.idea_ids.votes + 1
        vote = self.env['avancys.votes'].search([('idea_ids','=',self.idea_ids.id),('state','=','procesado')])
        #acumular notes de votos para idea
        for x in vote:
            notes = notes + x.notes
        #Calcula promedio
        self.idea_ids.notes = (notes + self.notes) / self.idea_ids.votes
        ##############
        ## Calcular promedio de votos y cantidad de votos por persona para grafico
        ##############
        #Lista de votos por persona
        votesusers = self.env['avancys.votes'].search([('create_uid','=',self.create_uid.id),('state','=','procesado')])
        votes_total= len(votesusers) + 1
        if votes_total > 1: #modificar
            notesperson = 0
            promperson = 0
            #acumulo las calificaciones de votos procesados anteriormente por este usuario
            for x in votesusers:
                notesperson = notesperson + x.notes
            #calculo el promedio considerando el voto actual calificacion actual
            promperson = (notesperson + self.notes) / votes_total
            #busca usuarios en avancys.users
            users = self.env['avancys.users'].search([('create_uid','=',self.create_uid.id)])
            users.write({'votes':votes_total,'notes':promperson})
        else:#Ingresa un voto
            #ingresa en avancys.users
            votesuser_new = self.env['avancys.users'].create({'create_uid':self.id,'votes':votes_total,'notes':self.notes})
        #Cambia el estado del voto
        self.state = 'procesado'

    @api.one
    @api.constrains('notes', 'idea_ids','state')
    def _check_votes(self):
        #Obtener zona horaria usuario
        user = self.env['res.users'].search([('id','=',self._uid)])

        #Defecto
        tz = pytz.timezone('America/Caracas')
        if user.partner_id.tz:
            tz = pytz.timezone(user.partner_id.tz)
        else:
            raise MissingError('El usuario no tiene zona horaria configurada.')

        #Aplicar zona horaria del usuario en fechas
        date_from = \
            pytz.utc.localize(datetime.datetime.strptime(self.idea_ids.datefrom,'%Y-%m-%d %H:%M:%S')).astimezone(tz)
        date_to = \
            pytz.utc.localize(datetime.datetime.strptime(self.idea_ids.dateto,'%Y-%m-%d %H:%M:%S')).astimezone(tz)
        #dates = \
        #    pytz.utc.localize(datetime.datetime.strptime(self.dates,'%Y-%m-%d %H:%M:%S')).astimezone(tz)
        #valide la fecha de la votación más no la de inicio del proceso de votación
	dates = pytz.utc.localize(datetime.datetime.now()).astimezone(tz)

        votes_user = self.env['avancys.votes'].search([('create_uid','=',self.create_uid.id),('idea_ids','=',self.idea_ids.id)])

        print date_from
        print date_to
        #Validaciones de fechas
        if not (date_from <= dates and dates <= date_to):
            raise ValidationError("La fecha de votaciones para la Idea indicada debe ser entre:\n"
                                  "{:%d/%m/%Y %H:%M:%S} y {:%d/%m/%Y %H:%M:%S}".format(
                                            date_from, date_to))
        #Validacion de calificación entre 1 y 10
        elif not (0 <= self.notes and self.notes <= 10):
            raise ValidationError("La calificación debe ser un valor decimal entre 0 y 10 inclusive.")
        #validacion de cantidad de votos por usuario e idea
        elif len(votes_user) > 1:
            raise ValidationError("El usuario posee una votacion para la idea. Seleccione otra idea y haga su votación.")
        elif self.create_uid.id != self._uid:
            raise ValidationError("No puedo votar por otra persona.")

    def _get_dates(self):
        return datetime.datetime.now()

    #Campos
    create_uid=fields.Many2one('res.users', 'Persona', required=True, readonly=True, default=_get_user)
    notes = fields.Float(string='Calificación', require=True)
    idea_ids = fields.Many2one('avancys.idea',string='Idea', required=True)
    state = fields.Selection([('borrador', 'Borrador'), ('procesado', 'Procesado')], default='borrador')
    dates = fields.Datetime(string='Fecha', required=True, readonly=True, default=_get_dates)

class group(models.Model):
    _name='avancys.group'

    name=fields.Char(string='Nombre', require=True)
    users_ids= fields.Many2many(comodel_name='res.users',
                            relation='avancys_group_users',
                            column1='users_ids',
                            column2='group_ids')

    _sql_constraints = [
                     ('group_name_unique',
                      'unique(name)',
                      'Selecciona otro nombre de grupo, ya existe uno con el mismo nombre.')]
