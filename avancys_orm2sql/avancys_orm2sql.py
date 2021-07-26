# -*- coding: utf-8 -*-
from __future__ import print_function
from openerp import models, fields, api
from datetime import datetime
import unicodedata
import pytz
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import progressbar

progressbar.streams.wrap_stderr()


class AvancysOrm2Sql(models.Model):
    _name = 'avancys.orm2sql'
    _description = 'ORM to SQL tool'

    def init(self, cr):
        self.currency_rate_closing(cr)

    def currency_rate_closing(self, cr):
        '''
        Llamar para crear procedimiento almacenado que devuelva tasa de cierre de la fecha indicada

        ejemplo de uso del procedimiento almacenado:
        SELECT currency_rate_closed('2017-03-05',3)

        RETORNA: 2900
        '''
        cr.execute(''' CREATE OR REPLACE FUNCTION currency_rate_closed(date_move date, currency integer)
                    RETURNS NUMERIC AS
                    $$
                    DECLARE 
                    result VARCHAR;
                    BEGIN
                    result = (SELECT rcr.rate
                    FROM res_currency_rate rcr
                    WHERE rcr.date_sin_hora::varchar like substring(date_move::varchar from 0 for 8)||'%'
                    AND rcr.currency_id = currency
                    ORDER BY date_sin_hora DESC 
                    LIMIT 1);
                    RETURN result;
                    END; $$ 
                    LANGUAGE plpgsql; 
                    ''')
        cr.commit()

    def widgets(self):
        fct = progressbar.FormatCustomText('Item: %(item)s', dict(item=" "))
        widgets = [
            '[', progressbar.Percentage(), '] ',
            progressbar.Bar(),
            progressbar.FormatLabel('[%(value)d de %(max_value)s en %(elapsed)s] '),
            progressbar.ETA(), ' ', fct]
        return widgets

    @api.model
    def get_database(self):
        self._cr.execute('SELECT current_database()')
        db = self._cr.fetchall()[0][0]
        return db

    def printProgressBar(self, iteration, total, b=False, start=False):
        '''
        Llamar para mostrar barra de progreso en log

        @params:
            iteracion: numero de proceso
            total: cantidad total de procesos a ejecutar
            b: pasar True si queremos hacer saltos de lineas entre iteracion
            start: tiempo de inicio del proceso

        ejemplo de uso:
        i, l = 0, len(listado_ids)
        start = datetime.now()
        orm2sql.printProgressBar(i, l, start=start)
        for id in listado_ids:
            i += 1
            orm2sql.printProgressBar(i, l, start=start)
        '''
        if total == 0:
            return False
        if iteration == 1 and start:
            print("Iniciando proceso en %s" % start)
        percent = (
            "{0:." + str(0) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(10 * iteration // total)
        bar = '▰' * filledLength + '▱' * (10 - filledLength)
        if b is False:
            print('\n%s |%s| %s%% %s %s de %s procesos' % (
                'Progreso', bar, percent,
                'Completado', iteration, total), end='\n')
        else:
            print('%s |%s| %s%% %s %s de %s procesos' % (
                'Progreso', bar, percent, 'Completado', iteration, total))
        # Print New Line on Complete
        if iteration == total:
            if start:
                end = datetime.now()
                total_time = (end - start).seconds
                print('Total tiempo utilizado: %s segundos' % total_time)
            print()

    def sqlcreate(
            self, user, cursor, modelo, datalist,
            company=False, commit=False, progress=False):
        '''
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
        '''
        if progress:
            i, bar = 0, progressbar.ProgressBar(max_value=len(datalist), redirect_stdout=True,
                                                redirect_stderr=True, widgets=self.widgets()).start()
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
            SQL = '''
                INSERT INTO "%s"
                (%s) values %s RETURNING id
            ''' % (
                modelo,
                ', '.join('"' + v + '"' for v in datos),
                tuple(v for k, v in datos.iteritems()))
            cursor.execute(SQL)
            fetches.append(cursor.fetchone())
            if commit:
                cursor.commit()
            if progress:
                i += 1
                bar.update(i, bar.widgets[7].update_mapping(item=False))
        return fetches

    def sqlupdate(self, cursor, modelo, sqlset, where):
        '''
        Llamar para realizar update de tablas en SQL
        @params:
            cursor - req: self.env.cr o cr en api vieja
            modelo - req: Nombre de la tabla a modificar en string
            set - req: diccionario con los campos a actualizar
            where - req: tupla de dos indices con el campo y el valor
        '''
        for campo in sqlset:
            SQL = '''
                UPDATE "%s"
                SET "%s" = '%s'
                WHERE "%s" = %s
            ''' % (modelo, campo, sqlset[campo], where[0], where[1])
            cursor.execute(SQL)

    def delete_spaces(self, text, left=False, right=False):
        '''
        Llamar para eliminar los espacios contenidos en los strings
        @params:
            text - req: string para el recorte
            left: enviar True si el recorte se debe realizar por la izquierda
            right: enviar True si el recorte se debe realizar por la derecha
        '''
        if right:
            while text[len(text) - 1] == ' ':
                text = text[0: len(text) - 1]
                if text == '':
                    break
        if left:
            while text[0] == ' ':
                text = text[1: len(text)]
                if text == '':
                    break
        return text

    def local_date(self, date, timezone='America/Bogota'):
        # Requires a date with '%Y-%m-%d %H:%M:%S' string format
        # Normalmente esta funcion agrega 5 horas a la hora recibida
        # Si se requiere hacer la operacion inversa, en los parametros de la funcion enviar timezone='UTC'
        local = pytz.timezone(timezone)
        date = datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT)
        date = local.localize(date, is_dst=None)
        if timezone == 'America/Bogota':
            date = date.astimezone(pytz.utc)
        else:
            date = date.astimezone(pytz.timezone('America/Bogota'))
        date = date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        return date


class AvancysAuthentication(models.Model):
    _name = 'avancys.authentication'
    _description = 'Codigo de activacion de servicio avancys'

    project_id = fields.Integer('Id de proyecto')
    activation_code = fields.Char('Codigo de activación')
    name = fields.Char('Configuracion')
