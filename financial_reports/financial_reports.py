# -*- coding: utf-8 -*-
import logging
from datetime import datetime

# import pandas as pd
import xlsxwriter
from openerp import models, fields, api, _
from openerp.exceptions import Warning
from openerp.http import request

_logger = logging.getLogger('FINANCIAL REPORTS')


class FPAAccountAccount(models.Model):
    _inherit = 'account.account'

    name = fields.Char(translate=True)


class fpa_financial_reports_country(models.Model):
    _inherit = 'res.country'

    code = fields.Char(size=3, oldname='code')


class fpa_financial_reports_concepts(models.Model):
    _name = "fpa.financial.reports.concepts"

    name = fields.Char(string="Concepto", required=True, help='Conceptos para organizar el informe', translate=True)
    code = fields.Char(string='Codigo concepto')
    sequence = fields.Integer(string="Secuencia", required=True, help='Secuencia en la cual se muestran en el pdf')
    tipo = fields.Boolean(string="¿Filtrar por tipo de cuenta?",
                          help='Marque esta opción si se desea que el concepto contenga tipos de cuenta y no cuentas especificas.que este concepto solo se muestre en el resumen final de informe.')
    account_ids = fields.Many2many('account.account', 'fpa_financial_reports_concepts_account', string='Cuentas',
                                   help='Cuentas que se desean filtrar en el informe, estas cuentas tienen prioridad sobre las indicadas en la ejecución del informe.',
                                   domain="[('type','!=','view')]")
    resume = fields.Boolean(string="¿Solo en Resumen?",
                            help='Marque esta opción si se desea que este concepto solo se muestre en el resumen final de informe. Solo aplica a informes con resumen al final.')
    detail = fields.Boolean(string="¿Con detalle?",
                            help='Marque esta opción si se desea que este concepto se muestre con detalle.')
    accumulated = fields.Boolean(string="¿Acumulado?",
                                 help='Marque esta opción si se desea que este concepto se muestre con saldos acumulados. Solo aplica para el reporte de Conversión de Estados de Resutados.',
                                 default='True')
    cierre = fields.Boolean(string="Cierre", default=True,
                            help='Marque esta opción si necesita que las cuentas del concepto se calculen con la TRM de cierre del periodo de cada movimiento, caso contrario no marcarla. Esta opción, aplica al reporte de Conversión de Estado de Resultados.')
    before = fields.Boolean(string="¿Antes del detalle?",
                            help='Marque esta opción si se desea que este concepto se muestre antes del detalle de cuentas con su respectivo total, caso contrario se mostrará al final de los movimientos.')
    financial_reports = fields.Many2one('fpa.financial.reports', string='Informe financiero', required=True,
                                        ondelete='cascade')


class financialniveles(models.Model):
    _name = "fpa.niveles"

    code = fields.Char(string='Código', required=True)
    name = fields.Char(string='Descripción', required=True, translate=True)
    financial_reports = fields.Many2one('fpa.financial.reports', string='Informe financiero', required=True,
                                        ondelete='cascade')
    help = fields.Text(string='Ayuda', required=True, translate=True)


class fpt_financial_reports_period(models.Model):
    _name = "fpa.financial.reports.period"

    name = fields.Char(string='Etiqueta', required=True)
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)


class fpt_financial_reports_concepts_columns(models.Model):
    _name = "fpa.financial.reports.columns"

    code = fields.Char(string='Codigo concepto')


class fpt_financial_reports_concepts_columns(models.Model):
    _name = "fpa.financial.reports.concepts.columns"

    line_id = fields.Many2one('fpa.financial.reports.concepts', string='Concepto',
                              help='Conceptos del informe, sirve para organizar la información en los informes.',
                              copy=True)
    financial_reports = fields.Many2one('fpa.financial.reports', string='Informe financiero', required=True,
                                        ondelete='cascade')
    code = fields.Char(string='Codigo concepto')
    name = fields.Char(string="Concepto", required=True, help='Conceptos para organizar el informe')
    line_ids = fields.One2many('fpa.financial.reports.concepts.columns.lines', 'parent_id', string='Aplicación',
                               help='Conceptos (medios).', copy=True, ondelete='cascade')
    application_type = fields.Selection([('none', 'No Aplica'), ('account', 'Cuentas Contables'),
                                         ('hr', 'Conceptos de Nomina')], string='Tipo de Aplicacion',
                                        default='none', track_visibility='onchange',
                                        help='Campo que indica si se usarán Cuentas Contables o Conceptos de Nómina en '
                                             'la generación del informe de Medios Magnéticos. Por ejemplo, el informe '
                                             '1001 debe estar parametrizado con "Cuentas Contables" mientras que el '
                                             '2276 debe estar con "Conceptos de Nómina"')


class hr_payslip_concepts_code(models.Model):
    _name = 'hr.payslip.concepts.code'

    name = fields.Char('Nombre', required=True)
    code = fields.Char('Código', required=True)
    column_line_id = fields.Many2one('fpa.financial.reports.concepts.columns.lines', 'Linea de Aplicación', required=True,
                                     ondelete='cascade')


class fpt_financial_reports_concepts_columns_lines(models.Model):
    _name = "fpa.financial.reports.concepts.columns.lines"

    name = fields.Char(string='Descripcion')
    col = fields.Selection(
        [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('E', 'E'), ('F', 'F'), ('G', 'G'), ('H', 'H'), ('I', 'I'),
         ('J', 'J'), ('K', 'K'), ('L', 'L'), ('M', 'M'), ('N', 'N'), ('O', 'O'), ('P', 'P'), ('Q', 'Q'), ('R', 'R'),
         ('S', 'S'), ('T', 'T'), ('U', 'U'), ('V', 'V'), ('W', 'W'), ('X', 'X'), ('Y', 'Y'), ('Z', 'Z'), ('AA', 'AA'),
         ('AB', 'AB'), ('AC', 'AC'), ('AD', 'AD'), ('AE', 'AE')], default='A', string='Columna',
        help='Columnas para la hoja de calculo.', required=True)
    type = fields.Selection([('d', 'Debito'), ('c', 'Credito'), ('sf', 'Saldo final'), ('b', 'Base'), ('t', 'Total')],
                            string='Tipo de calculo', help='El tipo de cálculo, "Total", debe ser usado únicamente en '
                                                           'reportes que usen los Conceptos de Nómina; los demás tipos,'
                                                           'Débito-Crédito-Saldo Final-Base, aplican para los reportes '
                                                           'que usen Cuentas Contables.')
    account_ids = fields.Many2many('account.account', 'fpa_financial_reports_concepts_col_account', string='Cuentas',
                                   help='Cuentas que se desean filtrar en el informe, estas cuentas tienen prioridad sobre las indicadas en la ejecución del informe.',
                                   domain="[('type','!=','view')]")
    concept_ids = fields.One2many('hr.payslip.concepts.code', 'column_line_id', string='Conceptos',
                                  help='Conceptos que se desean filtrar en el informe. Se buscará según el Código '
                                       'Indicado')
    parent_id = fields.Many2one('fpa.financial.reports.concepts.columns', string='Conceptos(Medios)', required=True,
                                ondelete='cascade')
    application_type = fields.Selection([('none', 'No Aplica'), ('account', 'Cuentas Contables'),
                                         ('hr', 'Conceptos de Nomina')], string='Tipo de Aplicacion',
                                        default='none', track_visibility='onchange',
                                        help='Campo que indica si se usarán Cuentas Contables o Conceptos de Nómina en '
                                             'la generación del informe de Medios Magnéticos. Por ejemplo, el informe '
                                             '1001 debe estar parametrizado con "Cuentas Contables" mientras que el '
                                             '2276 debe estar con "Conceptos de Nómina"')


class fpt_financial_reports_period_range(models.Model):
    _name = "fpa.financial.reports.period_range"

    name = fields.Char(string='Nombre', required=True)
    period_ids = fields.Many2many('fpa.financial.reports.period', 'fpa_period_range_period', string='Rango de Periodos',
                                  required=True)


class fpt_financial_reports(models.Model):
    _name = 'fpa.financial.reports'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _translate = True

    name = fields.Char(string="Nombre del reporte", size=100, translate=True, track_visibility='onchange',
                       help='Nombre del informe, este se mostrará en los formatos asociados.')
    categ = fields.Selection([('lib', 'Libros Oficiales'), ('ana', 'Analíticos'), ('fic', 'Financieros (Comparativos)'),
                              ('fi', 'Financieros'), ('ve', 'Ventas'), ('pro', 'Producción'), ('com', 'Compras'),
                              ('in', 'Inventarios'), ('te', 'Tesorería'), ('co', 'Contables'),
                              ('ex', 'Información Exógena'), ('inv', 'Inventario'), ('oth', 'Otros'),
                              ('au', 'Auditoria'), ('imp', 'Impuestos')], default='fi', string='Categoria',
                             track_visibility='onchange', help='Categoría asociada al informe, sirve para organizar '
                                                               'la vista de los informes.')
    type = fields.Selection([('con', 'Con conceptos'), ('sco', 'Sin conceptos'), ('ex', 'Exportacion')], default='con',
                            string='Tipo', track_visibility='onchange',
                            help='Tipo que permite diferencias la configuración de cada informe.')
    export_type_date = fields.Selection([('none', 'No Aplica'), ('range', 'Rango'), ('cut', 'Corte')],
                                        string='Fecha Exportacion', default='none', track_visibility='onchange',
                                        help='Campo usado para indicar el método de selección de fechas en la '
                                             'exportación del informe.')
    application_type = fields.Selection([('none', 'No Aplica'), ('account', 'Cuentas Contables'),
                                         ('hr', 'Conceptos de Nomina')], string=u'Tipo de Aplicación',
                                        default='none', track_visibility='onchange',
                                        help='Campo que indica si se usarán Cuentas Contables o Conceptos de Nómina en '
                                             'la generación del informe de Medios Magnéticos. Por ejemplo, el informe '
                                             '1001 debe estar parametrizado con "Cuentas Contables" mientras que el '
                                             '2276 debe estar con "Conceptos de Nómina"')
    concepts_ids = fields.One2many('fpa.financial.reports.concepts', 'financial_reports', string='Detalle',
                                   help='Conceptos del informe, sirve para organizar la información en los informes.',
                                   copy=True, ondelete='cascade')
    niveles_ids = fields.One2many('fpa.niveles', 'financial_reports', string='Niveles',
                                  help='Defina los niveles que desea ver en la generacion.', copy=True, readonly=True,
                                  ondelete='cascade')
    action = fields.Char(string="Accion", help='Acción asociada a la generación del informe.', invisible=True)
    model_wzr = fields.Char(string="Modelo Wizard",
                            help='Modelo asociado al wizard del informe. Se utiliza para que la generación sea dinamica.',
                            invisible=True)
    model = fields.Char(string="Modelo",
                        help='Modelo asociado al wizard del informe. Se utiliza para que la generación sea dinamica.',
                        invisible=True)
    view = fields.Char(string="Vista",
                       help='Vista del wizard asociada al informe. Se utiliza para que la generación sea dinamica.',
                       invisible=True)
    tree = fields.Char(string="Tree",
                       help='Vista lista asociada al informe. Se utiliza para que la consulta sea dinamica.',
                       invisible=True)
    domain = fields.Char(string="Dominio vista tree",
                         help='Dominio para la vista lista. Se utiliza para que la consulta sea dinamica.',
                         invisible=True)
    form = fields.Char(string="Form",
                       help='Vista formulario para la coniguración del informe. No es útil, porque cada informa tiene solo una vista formulario, por lo tanto el sistema lo abre automaticamente.',
                       invisible='True')
    template = fields.Char(string="Plantilla QWEB", help='Plantilla qweb asociada al informe.')
    title = fields.Char(string="Titulo", translate=True, track_visibility='onchange', help='Titulos mostrados en el xlsx.')
    field_hidden = fields.Char(string="Campos a ocultar", help='indique las columnas de campos a ocultar.')
    consulta = fields.Text(string="Consulta PDF", track_visibility='onchange',
                           help='Consulta sql ejecutada para generar los formatos. Esta consulta se genera sobre la tabla temporal donde se analiza la información.')
    consulta_xlsx = fields.Text(string="Consulta XLSX", track_visibility='onchange',
                                help='Consulta sql ejecutada para generar los formatos. Esta consulta se genera sobre la tabla temporal donde se analiza la información para el formato XLSX.')
    formato = fields.Char(string="Formato", help='Formatos disponibles parar generar los informes.')
    account_filter = fields.Boolean(string="Filtro adicional de cuentas",
                                    help='Marque esta opción si el informe debe tener disponible un filtro adicional por cuenta contable.')
    partner_filter = fields.Boolean(string="Filtro adicional de terceros",
                                    help='Marque esta opción si el informe debe tener disponible un filtro adicional por terceros.')
    journal_filter = fields.Boolean(string="Filtro adicional de diarios",
                                    help='Marque esta opción si el informe debe tener disponible un filtro adicional por diarios.')
    analytic_filter = fields.Boolean(string="Filtro adicional de cuentas analiticas",
                                     help='Marque esta opción si el informe debe tener disponible un filtro adicional por cuenta analitica.')
    sign = fields.Boolean(string="Invertir signo", help='Marque esta opción si el informe debe invertir los signos.')
    analyze = fields.Boolean(string="Analizar",
                             help='Marque esta opción si desea analizar la información luego de generarla (se le '
                                  'mostrara la vista lista/gráfica correspondiente al informe). Caso contrario se le mostrará la pantalla donde podrá exportar o analizar.')
    equivalente = fields.Boolean(string="Equivalente NIIF",
                                 help='Marque esta opción si el informe debe mostrar su equivalente en NIIF.')
    clase = fields.Boolean(string="Clase",
                           help='Marque esta opción si el informe debe mostrar la clase como una columna adicional. Aplica al Balance General.')
    search_default = fields.Char(string="Search por defecto (tree)",
                                 help='Establecer search por defecto para cada informe.')
    title_color = fields.Char(string="Color titulos",
                              help='El color indicado en este campo, se mostrará en el titulo del xlsx.')
    view_color = fields.Char(string="Color resumen",
                             help='El color indicado en este campo, se mostrará en el los resúmenes contenido del xlsx.')
    format_money = fields.Char(string="Formato Dinero",
                               help='Sirve para establecer el formato para los datos de tipo moneda, se mostrará en el xlsx. Ejemplo: $#,##0')
    format_date = fields.Char(string="Formato Fecha",
                              help='Sirve para establecer el formato para los datos de tipo fecha, se mostrará en el xlsx. Ejemplo: dd/mm/yy')
    from_merge = fields.Many2one('fpa.financial.reports.concepts', string='Concepto a mezclar',
                                 help='Seleccione el concepto que desea mezclar.')
    to_merge = fields.Many2one('fpa.financial.reports.concepts', string='Concepto destino para mezclar',
                               help='Seleccione el concepto destino que va a mezclar.')
    numeric = fields.Char(string="Columnas moneda ", track_visibility='onchange',
                          help='Indicar las columnas que deben tener formato money en el xlsx, ejemplo: A,B,C,D.')
    unidades = fields.Char(string="Unidades", default='1',
                           help='Indicar las unidades a mostrar en las columnas monto, es decir, se divirá cada resultado por el valor indicado acá. Ejemplo: Si indica 1000, y el resultado de una columna es 5450000, el valor mostrado será 5450.')
    porc = fields.Char(string="Columnas % ",
                       help='Indicar las columnas que deben tener formato porcentaje en el xlsx, ejemplo: A,B,C,D.')
    nivel = fields.Selection([('clase', 'Clase'), ('grupo', 'Grupo'), ('cuenta', 'Cuenta'), ('subcuenta', 'Subcuenta')],
                             string="Nivel", track_visibility='onchange',
                             help='Numero de niveles, el cual tendra en cuenta para la creacion de Conceptos.',
                             default='')
    indentacion = fields.Integer(string="Indentacion", help='Espacios por nivel', default=4)
    export = fields.Boolean(string="Exportacion",
                            help='Marque esta opcion si el reporte es solo de exportacion (Ejemplo: medios magneticos)')
    query = fields.Text(string="Consulta SQL", help='Consulta sql ejecutada para generar los formatos de exportacion.')
    tope_min = fields.Float(string='Tope minimo')
    account_ids = fields.Many2many('account.account', 'fpa_financial_reports_accounts', string='Cuentas')
    detalle = fields.Boolean(string="Detalle", help='Marque si desea que el ultimo nivel quede con detalle')
    codigo = fields.Boolean(string="Código", help='Agrega el codigo de la cuenta en el nombre del Concepto')
    accumulated = fields.Boolean(string="Acumulado",
                                 help='Agrega el concepto con la marca de acumulado. Solo aplica para el reporte de Conversión de Estados Financieros')
    columns_ids = fields.One2many('fpa.financial.reports.concepts.columns', 'financial_reports', string='Columnas',
                                  help='Conceptos (medios).', copy=True, ondelete='cascade')
    cierre = fields.Boolean(string="Cierre", default=True,
                            help='Marque esta opción si necesita que las cuentas del concepto se calculen con la TRM de cierre del periodo de cada movimiento, caso contrario no marcarla. Esta opción, aplica al reporte de Conversión de Estado de Resultados.')
    mode = fields.Char(string='Modo de vista', default='tree', required=True)
    sum_column = fields.Boolean(string="Totalizar", default=False,
                                help="Totaliza el valor de las columnas tipo Moneda en el documento .xlsx")
    fields = fields.Char(string="Campos", help='Estos son los campos agregados en la consulta sql. No se utiliza.',
                         invisible=True)

    @api.multi
    def update_concepts(self):
        self.columns_ids.unlink()
        for x in self.concepts_ids:
            self.columns_ids.create({'col': 'O', 'concept_id': x.id, 'financial_reports': self.id, 'debit': True})
        return True

    @api.multi
    def create_concepts(self):
        self._cr.execute(''' DELETE FROM fpa_financial_reports_concepts WHERE financial_reports = %s''', (self.id,))
        cont2 = 0
        detalle = False
        fpa_report_obj = self.env['fpa.financial.reports.concepts']
        if self.nivel and self.account_ids.sorted(lambda x: x.name):
            nivel_clase = ''.rjust(self.indentacion * 0, ' ')
            for clase in self.account_ids:
                if self.nivel == "clase" and self.detalle:
                    detalle = True
                cont2 += 1
                if self.codigo:
                    name_clase = nivel_clase + '[' + clase.code + '] ' + clase.name
                else:
                    name_clase = nivel_clase + '' + clase.name
                self._cr.execute('''insert into fpa_financial_reports_concepts (detail,name,sequence,before,financial_reports) values 
                    (%s,%s,%s,%s,%s) RETURNING id''',
                                 (detalle, name_clase, cont2, True, self.id))
                clase_id = self._cr.fetchone()[0]
                clase_account = clase.code + '%'
                detalle = False
                accounts_clase = [x.id for x in self.env['account.account'].search([('code', 'like', clase_account), (
                    'type', 'in', ['other', 'receivable', 'payable', 'consolidation'])])]
                fpa_report_obj.browse(clase_id).write({'account_ids': [(6, 0, accounts_clase)]})

                if self.nivel in ['grupo', 'cuenta', 'subcuenta']:
                    grupos = self.env['account.account'].search([('parent_id', '=', clase.id)])
                    nivel_grupo = ''.rjust(self.indentacion * 1, ' ')
                    for grupo in grupos:
                        cont2 += 1
                        if self.nivel == "grupo" and self.detalle:
                            detalle = True
                        if self.codigo:
                            name_grupo = nivel_grupo + '[' + grupo.code + '] ' + grupo.name
                        else:
                            name_grupo = nivel_grupo + '' + grupo.name
                        self._cr.execute('''insert into fpa_financial_reports_concepts (detail,name,sequence,before,financial_reports) values 
                            (%s,%s,%s,%s,%s)  RETURNING id''',
                                         (detalle, name_grupo, cont2, True, self.id))
                        grupo_id = self._cr.fetchone()[0]
                        grupo_account = grupo.code + '%'
                        detalle = False
                        accounts_grupo = [x.id for x in self.env['account.account'].search(
                            [('code', 'like', grupo_account),
                             ('type', 'in', ['other', 'receivable', 'payable', 'consolidation'])])]
                        fpa_report_obj.browse(grupo_id).write({'account_ids': [(6, 0, accounts_grupo)]})
                        if self.nivel in ['cuenta', 'subcuenta']:
                            nivel_cuenta = ''.rjust(self.indentacion * 2, ' ')
                            cuentas = self.env['account.account'].search([('parent_id', '=', grupo.id)])
                            for cuenta in cuentas:
                                if self.nivel == "cuenta" and self.detalle:
                                    detalle = True
                                cont2 += 1
                                if self.codigo:
                                    name_cuenta = nivel_cuenta + '[' + cuenta.code + '] ' + cuenta.name
                                else:
                                    name_cuenta = nivel_cuenta + '' + cuenta.name
                                self._cr.execute('''insert into fpa_financial_reports_concepts (detail,name,sequence,before,financial_reports) values 
                                    (%s,%s,%s,%s,%s) RETURNING id''',
                                                 (detalle, name_cuenta, cont2, True, self.id))
                                cuenta_id = self._cr.fetchone()[0]
                                cuenta_account = cuenta.code + '%'
                                detalle = False
                                accounts_grupo = [x.id for x in self.env['account.account'].search(
                                    [('code', 'like', cuenta_account),
                                     ('type', 'in', ['other', 'receivable', 'payable', 'consolidation'])])]
                                fpa_report_obj.browse(cuenta_id).write({'account_ids': [(6, 0, accounts_grupo)]})
                                if self.nivel in ['subcuenta']:
                                    nivel_subcuenta = ''.rjust(self.indentacion * 3, ' ')
                                    subcuentas = self.env['account.account'].search([('parent_id', '=', cuenta.id)])
                                    for subcuenta in subcuentas:
                                        if self.detalle:
                                            detalle = True
                                        cont2 += 1
                                        if self.codigo:
                                            name_subcuenta = nivel_subcuenta + '[' + subcuenta.code + '] ' + subcuenta.name
                                        else:
                                            name_subcuenta = nivel_subcuenta + '' + subcuenta.name
                                        self._cr.execute('''insert into fpa_financial_reports_concepts (detail,name,sequence,before,financial_reports) values 
                                            (%s,%s,%s,%s,%s) RETURNING id''',
                                                         (detalle, name_subcuenta, cont2, True, self.id))

                                        subcuenta_id = self._cr.fetchone()[0]
                                        subcuenta_account = subcuenta.code + '%'
                                        detalle = False
                                        subaccounts_grupo = [x.id for x in self.env['account.account'].search(
                                            [('code', 'like', subcuenta_account),
                                             ('type', 'in', ['other', 'receivable', 'payable', 'consolidation'])])]
                                        fpa_report_obj.browse(subcuenta_id).write(
                                            {'account_ids': [(6, 0, subaccounts_grupo)]})
        return True

    @api.multi
    def generate(self):
        if self._context is None:
            self._context = {}
        ir_model_data = self.env['ir.model.data']
        try:
            compose_form_id = ir_model_data.get_object_reference('financial_reports', str(self.view))[1]
        except ValueError:
            compose_form_id = False
        return {
            'name': _(self.name),
            'res_model': str(self.model_wzr),
            'type': 'ir.actions.act_window',
            'view_id': compose_form_id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
        }

    @api.multi
    def view_function(self, generate=True):
        ir_model_data = self.env['ir.model.data']
        try:
            compose_form_id = ir_model_data.get_object_reference('financial_reports', self.mode)[1]
        except ValueError:
            compose_form_id = False
        dominio = self.domain % (self.env.user.id, self.env.user.company_id.id, self.id)
        if self.analyze or generate:
            return {
                'name': _(self.name),
                'res_model': self.model,
                'type': 'ir.actions.act_window',
                'view_id': compose_form_id,
                'view_mode': self.mode,
                'view_type': 'form',
                'domain': dominio,
                'target': 'current',
                'context': self.search_default,
                }
        else:
            return True

    def _get_unidades(self):
        unidades = float(self.unidades)
        result = 'Expresado en unidades'
        valor = 10.0
        if unidades >= valor ** 3 and unidades < valor ** 6:
            result = 'Expresado en unidades de MILES'
        elif unidades >= valor ** 6 and unidades < valor ** 9:
            result = 'Expresado en unidades de MILLONES'
        elif unidades >= valor ** 9 and unidades < valor ** 12:
            result = 'Expresado en unidades de MILLARDOS'
        elif unidades >= valor ** 12 and unidades < valor ** 15:
            result = 'Expresado en unidades de BILLONES'
        elif unidades >= valor ** 15 and unidades < valor ** 18:
            result = 'Expresado en unidades de BILLARDOS'
        elif unidades >= valor ** 18 and unidades < valor ** 21:
            result = 'Expresado en unidades de TRILLONES'
        elif unidades >= valor ** 21 and unidades < valor ** 24:
            result = 'Expresado en unidades de TRILLARDOS'
        elif unidades >= valor ** 24:
            result = 'Expresado en unidades de CUATRILLARDOS'
        return _(result)

    def print_format(self, formato, params):
        if self.export and formato == 'xlsx':
            _logger.info('por aqui voy')
            if not params:
                raise Warning('Debe indicar las fechas para la consulta')
            query = self.query.format(date_from=params['date_from'], date_to=params['date_to'], financial_id=self.id,
                                      company_id=self.env.user.company_id.id)
            query = query.replace('@porc', str('%'))  # sustituir @porc por %
            query = query.replace('@min', str('<'))  # sustituir @min por <
            query = query.replace('@may', str('>'))  # sustituir @min por >
            _logger.info(query)
            self.env.cr.execute(query)
            datos = self.env.cr.fetchall()
            actual = str(datetime.now()).replace('-', '').replace(':', '').replace('.', '').replace(' ', '')
            data_attach = {
                'name': self.name + '_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.' + formato,
                'datas': '.',
                'datas_fname': self.name + '_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.',
                'res_model': 'fpa.financial.reports',
                'res_id': self.id,
            }
            self.env['ir.attachment'].search(
                [('res_model', '=', 'fpa.financial.reports'), ('company_id', '=', self.env.user.company_id.id), (
                    'name', 'like',
                    '%' + self.name + '%' + self.env.user.name + '%')]).unlink()  # elimina adjuntos del usuario

            # crea adjunto en blanco
            attachments = self.env['ir.attachment'].create(data_attach)

            headers = dict(request.httprequest.__dict__.get('headers'))

            if headers.get('Origin', False):
                url = dict(request.httprequest.__dict__.get('headers')).get(
                    'Origin') + '/web/binary/saveas?model=ir.attachment&field=datas&filename_field=name&id=' + str(
                    attachments.id)
            else:
                url = dict(request.httprequest.__dict__.get('headers')).get(
                    'Referer') + '/binary/saveas?model=ir.attachment&field=datas&filename_field=name&id=' + str(
                    attachments.id)
            path = attachments.store_fname
            self.env['ir.attachment'].search([['store_fname', '=', path]]).write(
                {'store_fname': attachments._get_path(path)[0]})
            wb = xlsxwriter.Workbook(attachments._get_path(path)[1])
            ws = wb.add_worksheet(_('Auditoria Movimientos Contables'))

            ws.set_column('A:R', 18)
            bold = wb.add_format({'bold': True})
            bold.set_align('center')
            bold2 = wb.add_format({'fg_color': self.title_color})
            bold2.set_bold()
            bold2.set_align('center')
            text3 = wb.add_format({'bold': False})
            text3.set_font_size(10)
            money_format = wb.add_format({'num_format': self.format_money})
            money_format.set_font_size(10)

            ws.merge_range('E1:J1', self.name, bold)
            if params['date_from']:
                ws.write('F2', _('Desde: '), bold)
                ws.write('G2', params['date_from'])
                ws.write('H2', _('Hasta: '), bold)
                ws.write('I2', params['date_to'])
            else:
                ws.write('F2', _('Hasta: '), bold)
                ws.write('G2', params['date_to'])
            ws.write('G3', _('Fecha de impresion'), bold)
            ws.write('H3', str(datetime.now())[:19])

            titulos = self.title.split(',')
            abc = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
                   'U', 'V', 'W', 'X', 'Y', 'Z']
            num = [x for x in range(0, 101)]
            resultado = zip(abc, num)
            for i, l in enumerate(titulos):
                for pos in resultado:
                    if i == pos[1]:
                        position = pos[0]
                        break
                ws.write(position + str(5), l, bold2)
            for x, line in enumerate(datos):
                for y, f in enumerate(titulos):
                    for pos in resultado:
                        if y == pos[1]:
                            position = pos[0]
                            break
                    if position in (self.numeric):
                        ws.write(position + str(6 + x), line[y] or 0.0, money_format)
                    else:
                        ws.write(position + str(6 + x), line[y] or '', text3)
            wb.close()
            return {'type': 'ir.actions.act_url', 'url': str(url), 'target': 'self'}
        else:
            if formato == 'xlsx':
                # sql = self.consulta_xlsx.format() (self.env.user.lang,self.env.user.id, self.env.user.company_id.id, self.id)
                sql = self.consulta_xlsx.format(date_from=params['date_from'], date_to=params['date_to'],
                                                financial_id=self.id,
                                                company_id=self.env.user.company_id.id, lang=self.env.user.lang,
                                                user_id=self.env.user.id)
            else:
                sql = self.consulta.format(user_id=self.env.user.id, company_id=self.env.user.company_id.id,
                                           financial_id=self.id)
            self.env.cr.execute(sql)
            datos = self.env.cr.fetchall()

            actual = str(datetime.now()).replace('-', '').replace(':', '').replace('.', '').replace(' ', '')
            data_attach = {
                'name': self.name + '_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.' + formato,
                'datas': '.',
                'datas_fname': self.name + '_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.',
                'res_model': 'fpa.financial.reports',
                'res_id': self.id,
            }
            # elimina adjuntos del usuario
            self.env['ir.attachment'].search(
                [('res_model', '=', 'fpa.financial.reports'), ('company_id', '=', self.env.user.company_id.id),
                 ('name', 'like', '%' + self.name + '%' + self.env.user.name + '%')]).unlink()

            # crea adjunto en blanco
            attachments = self.env['ir.attachment'].create(data_attach)

            headers = dict(request.httprequest.__dict__.get('headers'))

            if headers.get('Origin', False):
                url = dict(request.httprequest.__dict__.get('headers')).get(
                    'Origin') + '/web/binary/saveas?model=ir.attachment&field=datas&filename_field=name&id=' + str(
                    attachments.id)
            else:
                url = dict(request.httprequest.__dict__.get('headers')).get(
                    'Referer') + '/binary/saveas?model=ir.attachment&field=datas&filename_field=name&id=' + str(
                    attachments.id)
            path = attachments.store_fname
            self.env['ir.attachment'].search([['store_fname', '=', path]]).write(
                {'store_fname': attachments._get_path(path)[0]})
            titulos = _(self.title).split(',')
            header = self.env[self.model.replace('.line', '')].search(
                [('financial_id', '=', self.id), ('user_id', '=', self.env.user.id),
                 ('company_id', '=', self.env.user.company_id.id)])

            try:
                if header.amount_label_comparative:
                    titulos = [w.replace('Comparativo', header.amount_label_comparative) for w in titulos]
            except:
                pass
            if formato == 'xlsx':
                title = ''
                wb = xlsxwriter.Workbook(attachments._get_path(path)[1])
                ws = wb.add_worksheet(_('DATOS'))
                ws.set_column('A:A', 20)
                bold = wb.add_format({'bold': True})
                bold2 = wb.add_format({'fg_color': self.title_color})
                bold2.set_bold()
                bold3 = wb.add_format({'bold': True})
                bold3.set_font_color(self.view_color)
                money_format = wb.add_format({'num_format': self.format_money})
                money_format_bold = wb.add_format({'num_format': self.format_money})
                money_format_bold.set_font_color(self.view_color)
                money_format_bold.set_bold()
                bold.set_align('center')
                if not header.chart_account_id == False:
                    ws.merge_range('A1:B1', _('Plan de cuentas: '), bold)
                    ws.merge_range('C1:D1', header.chart_account_id.name)
                ws.write('A2', _('Desde: '), bold)
                ws.write('B2', header.date_from)
                ws.write('C2', _('Hasta: '), bold)
                ws.write('D2', header.date_to)
                ws.write('A3', _('Estado:'), bold)
                ws.write('C3', _(header.estado))
                ws.write('A4', _('Fecha de impresion'), bold)
                ws.write('B4', str(datetime.now()))

                ws.merge_range('A5:D5', self._get_unidades(), bold)
                abc = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S',
                       'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
                num = [x for x in range(0, 101)]
                resultado = zip(abc, num)
                position = ''
                # Agrega titulos
                for i, l in enumerate(titulos):
                    for pos in resultado:
                        if i == pos[1]:
                            position = pos[0]
                            break
                    title = position
                    ws.write(position + str(8), _(l), bold2)

                ws.merge_range('A6:' + title + '6', _(self.name), bold)
                # agrega contenido
                detail = False
                desc = 0
                next = -1
                if len(self.concepts_ids) > 0:
                    for x, line in enumerate(datos):
                        for y, f in enumerate(titulos):
                            for pos in resultado:
                                if y == pos[1]:
                                    position = pos[0]
                                    break
                            if line[len(line) - 1]:  # agregar estilos especiales a las de resumen ==> if bold:
                                if position in (self.numeric):
                                    ws.write(position + str(desc), line[y], money_format_bold)
                                elif self.porc and position in tuple(self.porc):
                                    ws.write(position + str(desc), str(line[y]) + '%', bold3)
                                else:
                                    for concept in self.concepts_ids:
                                        if _(concept.name) == _(line[y]):
                                            if desc > 0:
                                                desc += 1
                                            else:
                                                desc = 9 + x
                                            detail = concept.detail or False
                                            ws.write(position + str(desc), _(line[y]), bold3)

                            if detail:
                                if desc > 0 and x != next:
                                    desc += 1
                                next = x
                                if position in (self.numeric):
                                    ws.write(position + str(desc), line[y], money_format)
                                elif self.porc and position in tuple(self.porc):
                                    ws.write(position + str(desc), str(line[y]) + '%')
                                else:
                                    ws.write(position + str(desc), '    ' + (_(line[y]) or ''))
                else:
                    for x, line in enumerate(datos):
                        for y, f in enumerate(titulos):
                            for pos in resultado:
                                if y == pos[1]:
                                    position = pos[0]
                                    break
                            if line[len(line) - 1]:
                                if position in (self.numeric):
                                    ws.write(position + str(9 + x), line[y] or 0.0, money_format_bold)
                                elif self.porc and position in tuple(self.porc):
                                    ws.write(position + str(9 + x), (line[y]) + '%', bold3)
                                else:
                                    ws.write(position + str(9 + x), _(line[y]), bold3)
                            else:
                                if position in (self.numeric):
                                    ws.write(position + str(9 + x), line[y] or 0.0, money_format)
                                elif self.porc and position in tuple(self.porc):
                                    ws.write(position + str(9 + x), '    ' + str(line[y] or '0.0') + '%')
                                else:
                                    ws.write(position + str(9 + x), '    ' + (_(line[y] or '') or ''))
                if self.sum_column:
                    for p in self.numeric.split(','):
                        csum = p + str(x+10)
                        cini = p + '9'
                        cfin = p + str(x+9)
                        ws.write_formula(csum, '{=SUM('+cini+':'+cfin+')}', money_format_bold)

                wb.close()
                return {'type': 'ir.actions.act_url', 'url': str(url), 'target': 'self'}
            elif formato == 'pdf':
                if len(datos) > 16000:
                    raise Warning("Máximo de longitud alcanzado en formato PDF. Se recomienda generar en XLSX")
                ids = []
                i = 0
                for res in datos:
                    i += 1
                    ids.append(res[0])
                datas = {}
                datas['ids'] = ids
                datas['model'] = self.model
                _logger.info('self.template')
                _logger.info(self.template)
                return {
                    'type': 'ir.actions.report.xml',
                    'report_name': self.template,
                    'datas': datas,
                }

    @api.multi
    def popup_wizard(self):
        if self._context is None:
            self._context = {}
        ir_model_data = self.env['ir.model.data']
        try:
            compose_form_id = ir_model_data.get_object_reference('financial_reports', 'fpa_export_wizard_view_ept')[1]
        except ValueError:
            compose_form_id = False
        return {
            'name': _(self.name),
            'res_model': 'fpa.export.wizard.ept',
            'type': 'ir.actions.act_window',
            'view_id': compose_form_id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
        }


class fpa_export_wizard(models.TransientModel):
    _name = 'fpa.export.wizard.ept'

    def _get_formato(self):
        _logger.info('get_formato')
        context = dict(self._context) or {}
        res = []
        formato = False
        if context and context.get('active_id', False):
            export_id = context.get('active_id', False)
            report = self.env['fpa.financial.reports']
            report_obj = report.browse(export_id)
            formato = report_obj.formato
            res = []
            for x in formato.split(','):
                res.append((x, x))
        return res

    format_report = fields.Selection(_get_formato, "Formato", required=True, default='xlsx')
    message = fields.Char("Message", readonly=True)
    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')
    date_cut = fields.Date(related='date_to', string='Hasta')
    export = fields.Boolean(string='Medios')
    export_type_date = fields.Selection([('none', 'No Aplica'), ('range', 'Rango'), ('cut', 'Corte')],
                                        string='Tipo Fecha Exportación',
                                        help='Campo usado en los informes de medios magnéticos para indicar el método '
                                             'de selección de fechas en la generación del informe.')

    @api.onchange('format_report')
    def set_format(self):
        ctx = self._context.copy()
        if ctx and ctx.get('active_id', False):
            export_id = ctx.get('active_id', False)
            report = self.env['fpa.financial.reports']
            report_obj = report.browse(export_id)
            self.export = report_obj.export
            self.export_type_date = report_obj.export_type_date

    @api.multi
    def download_file(self):
        context = dict(self._context) or {}
        if context and context.get('active_id', False):
            export_id = context.get('active_id', False)

            report = self.env['fpa.financial.reports']
            report_obj = report.browse(export_id)
            format_report = self.read(['format_report'])
            res = []
            if format_report[0]['format_report'] == 'pdf':
                res = report_obj.print_format('pdf', params=None)
                if not res:
                    self.message = "Los datos supera los limites de la generacion a pdf, por favor genere el informe en xlsx."
                    raise Warning(self.message)

            elif format_report[0]['format_report'] == 'xlsx':
                dic = {}
                dic['date_from'] = self.date_from
                dic['date_to'] = self.date_to
                res = report_obj.print_format('xlsx', params=dic)
            return res


class account_account_structure(models.Model):
    _name = "account.account.estructure"

    account_id = fields.Many2one('account.account', string='Cuenta', ondelete='cascade')
    digits = fields.Integer(string='Digitos', required=True)
    sequence = fields.Integer(string='Secuencia', required=True)
    description = fields.Char(string='Descripcion', required=True)

    _sql_constraints = [('nivel_unique_cuenta', 'unique(account_id,sequence,digits)',
                         'No puede crear niveles repetidas para una cuenta.')]


class account_account_extended_structu(models.Model):
    _inherit = "account.account"

    structure_id = fields.One2many('account.account.estructure', 'account_id', string='Estructura',
                                   help='Permite definir la estructura de las cuentas de tipo vista para ser mostradas correctamente en los informes. La secuencia se debe definir en orden inverso, por ejemplo: secuencia 3 para las de nivel 1 (1 Activo), secuencia 2 para las de nivel 2 (11 Dispnible) y secuencia 1 para las de nivel 3 (1105 Caja).')
