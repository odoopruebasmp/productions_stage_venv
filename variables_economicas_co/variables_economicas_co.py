from openerp.osv import osv,fields
from openerp import api,models
from openerp import fields as fields2
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID

class variables_economicas(models.Model):
    _name = "variables.economicas"
    
    def getValue(self, cr, code, date, context=None):
        ids = self.search(cr, SUPERUSER_ID, [('code', '=', code)], context=context)
        for variable in self.browse(cr, SUPERUSER_ID, ids, context=context):
            for valor1 in variable.valores_ids:
                if valor1.date_from <= date and valor1.date_to >= date:
                    return valor1.valor
        raise osv.except_osv(_('Error de Configuracion!'),_("No se encontro un valor para la variable '%s' en esa fecha") % (code,))

    def check_valores(self, cr, uid, ids, context=None):
        for variable in self.browse(cr, uid, ids, context):
            for valor1 in variable.valores_ids:
                find = False
                for valor2 in variable.valores_ids:
                        if (valor2.date_from >= valor1.date_from and valor2.date_from <= valor1.date_to) or (valor2.date_to >= valor1.date_from and valor2.date_to <= valor1.date_to):
                            if find:
                                return False
                            find = True
        return True
    
    name = fields2.Char(string='Nombre')
    code = fields2.Char('Codigo')
    currency_id = fields2.Many2one('res.currency', string='Moneda',required=True)
    valores_ids = fields2.One2many('variables.economicas.line', 'variable_id', string='Valores')
    
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codgigo tiene que ser unico!'),
    ]
    
    _constraints = [
        (check_valores, 'Hay fechas que se sobrelapan dentro de este registro', ['valores_ids']),
    ]
    
    
class variables_economicas_line(models.Model):
    _name = "variables.economicas.line"
    
    valor = fields2.Float(string='Valor', digits=dp.get_precision('Variable Economica'),required=True)
    date_from = fields2.Datetime(string='Fecha desde',required=True)
    date_to = fields2.Datetime(string='Fecha hasta',required=True)
    variable_id= fields2.Many2one('variables.economicas', string='Variable')
    
    
class tabla_retefuente(models.Model):
    _name = "variables.economicas.retefuente"
    
    def get_valor_pesos(self, cr, uid, date, salario, context=None):
        var_eco = self.pool.get('variables.economicas')
        ids = self.search(cr, uid, [('date_from', '<=', date),('date_to', '>=', date)], context=None)
        #solo es posible que devuelva 1 id
        tradicional=0
        minima=0
        for retefte in self.browse(cr, uid, ids, context):
            valor_uvt = var_eco.getValue(cr, 'UVT', date, context=context)
            salario_uvt = salario/valor_uvt#round((salario/valor_uvt), dp.get_precision('Variable Economica'))#salario/valor_uvt#
            
            if salario_uvt > 0:
                for marginal in retefte.marginal_ids:
                    if salario_uvt > marginal.valor_desde and ( marginal.valor_hasta ==0 or salario_uvt <= marginal.valor_hasta):
                        tradicional = ((salario_uvt-marginal.valor_desde)*marginal.tarifa/100+marginal.ajuste)*valor_uvt
                        break
            
            for linea in retefte.valores_ids:
                if salario_uvt > linea.valor_desde and (salario_uvt <= linea.valor_hasta or linea.valor_hasta <= 1):
                    if linea.valor_hasta <= 1:
                        minima = (linea.valor_hasta*salario_uvt-linea.valor_impuesto)*valor_uvt
                    else:
                        minima = linea.valor_impuesto*valor_uvt
                    break
                elif salario_uvt==0:
                    minima = 0
                    break
                    
        result = {
            'tradicional': tradicional,
            'minima': minima,
        }
                    
        return result
        
    def check_valores(self, cr, uid, ids, context=None):
        find = False
        for valor1 in self.browse(cr, uid, ids, context):
            find = False
            for valor2 in self.browse(cr, uid, ids, context):
                if (valor2.date_from >= valor1.date_from and valor2.date_from <= valor1.date_to) or (valor2.date_to >= valor1.date_from and valor2.date_to <= valor1.date_to):
                    if find:
                        return False
                    find = True
        return True
    

    name= fields2.Char(string='Nombre')
    date_from = fields2.Datetime(string='Fecha desde',required=True)
    date_to= fields2.Datetime(string='Fecha hasta',required=True)
    valores_ids = fields2.One2many('variables.economicas.retefuente.line', 'retefuente_id', string='Valores')
    marginal_ids = fields2.One2many('variables.economicas.retefuente.marginal.line', 'retefuente_id', string='Marginal')
    
    
    _constraints = [
        (check_valores, 'Hay fechas que se sobrelapan dentro de este registro', ['valores_ids']),
    ]
    
    
class linea_tabla_retefuente(models.Model):
    _name = "variables.economicas.retefuente.line"
    
    valor_desde = fields2.Float(string='Valor desde (UVT)', digits= dp.get_precision('Variable Economica'),required=True)
    valor_hasta = fields2.Float(string='Valor hasta (UVT)', digits= dp.get_precision('Variable Economica'),required=True)
    valor_impuesto = fields2.Float(string='Impuesto (UVT)', digits= dp.get_precision('Variable Economica'),required=True)
    retefuente_id = fields2.Many2one('variables.economicas.retefuente', string='Retefuente')
    
    
class tabla_tarifa_marginal_line(models.Model):
    _name = "variables.economicas.retefuente.marginal.line"
    
    valor_desde =fields2.Float(string='Valor desde(UVT)', digits= dp.get_precision('Variable Economica'),required=True)
    valor_hasta = fields2.Float(string='Valor hasta (UVT)', digits= dp.get_precision('Variable Economica'),required=True)
    tarifa = fields2.Float(string='Tarifa (%)', digitse= dp.get_precision('Variable Economica'),required=True)
    ajuste = fields2.Float(string='Ajuste (UVT)', digits= dp.get_precision('Variable Economica'),required=True)
    retefuente_id= fields2.Many2one('variables.economicas.retefuente', string='Retefuente')


