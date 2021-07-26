# -*- coding: utf-8 -*-
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP - Spanish number to text script
#    Based on original OpenERP /tools/amount_to_text.py
#    Copyright (C) 2012 KM Sistemas de informaciOn, S.L. All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

#-------------------------------------------------------------
#SPANISH
#-------------------------------------------------------------
from openerp.tools.translate import _

units_29 = ( 'CERO', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS',
          'SIETE', 'OCHO', 'NUEVE', 'DIEZ', 'ONCE', 'DOCE',
          'TRECE', 'CATORCE', 'QUINCE', 'DIECISEIS', 'DIECISIETE', 'DIECIOCHO',
          'DIECINUEVE', 'VEINTE', 'VEINTIUN', 'VEINTIDOS', 'VEINTITRES', 'VEINTICUATRO',
          'VEINTICINCO', 'VEINTISEIS', 'VEINTISIETE', 'VEINTIOCHO', 'VEINTINUEVE' )       

tens = ( 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA', 'CIEN')       

# La numeraciOn comentada es anglosajona, donde un billOn son mil millones. Sin embargo, en la española
# el billOn es un millOn de millones.
#denom = ( '',
#          'MIL', 'MILLON', 'BillOn', 'TrillOn', 'CuatrillOn', 'QuintillOn',  'SextillOn',
#          'SeptillOn', 'OctillOn', 'NonillOn', 'DecillOn', 'UndecillOn', 'DodecillOn',  'TredecillOn',
#          'CuatridecillOn', 'QuindecillOn', 'SexdecillOn', 'SeptidecillOn', 'OctodecillOn',
#          'NonidecillOn', 'VigillOn' )
#denom_plural = ( '',
#          'Mil', 'Millones', 'Billones', 'Trillones', 'Cuatrillones', 'Quintillones',  'Sextillones',
#          'Septillones', 'Octillones', 'Nonillones', 'Decillones', 'Undecillones', 'Dodecillones',  'Tredecillones',
#          'Cuatridecillones', 'Quindecillones', 'Sexdecillones', 'Septidecillones', 'Octodecillones',
#          'Nonidecillones', 'Vigillones' )

denom = ('',
          'MIL', 'MILLON', 'MIL MILLONES', 'BILLON', 'MIL BILLONES', 'TRILLON', 'MIL TRILLONES',
          'CUATRILLON', 'MIL CUATRILLONES', 'QUINTILLON', 'MIL QUINTILLONES', 'SEXTILLON', 'MIL SEXTILLONES', 'SEPTILLON',
          'MIL SEPTILLONES', 'OCTILLON', 'MIL OCTILLONES', 'NONILLON', 'MIL NONILLONES', 'DECILLON', 'MIL DECILLONES' )

denom_plural = ('',
          'MIL', 'MILLONES', 'MIL MILLONES', 'BILLONES', 'MIL BILLONES', 'TRILLONES', 'MIL TRILLONES',
          'CUATRILLONES', 'MIL CUATRILLONES', 'QUINTILLONES', 'MIL QUINTILLONES', 'SEXTILLONES', 'MIL SEXTILLONES', 'SEPTILLONES',
          'MIL SEPTILLONES', 'OCTILLONES', 'MIL OCTILLONES', 'NONILLONES', 'MIL NONILLONES', 'DECILLONES', 'MIL DECILLONES' )

# convertir valores inferiores a 100 a texto español.
def _convert_nn(val):
    if val < 30:
        return units_29[val]
    for (dcap, dval) in ((k, 30 + (10 * v)) for (v, k) in enumerate(tens)):
        if dval + 10 > val:
            if val % 10:
                return dcap + ' Y ' + units_29[val % 10]
            return dcap

# convertir valores inferiores a 1000 a texto español.
def _convert_nnn(val):
    word = ''
    (mod, quotient) = (val % 100, val // 100)
    if quotient > 0:
        if quotient == 1:
            if mod == 0:
                word = 'CIEN'
            else:
                word = 'CIENTO'
        elif quotient == 5:
                word = 'QUINIENTOS'
        elif quotient == 9:
            word = 'NOVECIENTOS'
        else:
            word = units_29[quotient] + 'CIENTOS'
        if mod > 0:
            word = word + ' '
    if mod > 0:
        word = word + _convert_nn(mod)
    return word

def spanish_number(val):
    if val < 100:
        return _convert_nn(val)
    if val < 1000:
        return _convert_nnn(val)
    #valores a partir de mil
    for (didx, dval) in ((v - 1, 1000 ** v) for v in range(len(denom))):
        if dval > val:
            mod = 1000 ** didx
            l = val // mod
            r = val - (l * mod)
            
            # Varios casos especiales:
            # Si l==1 y didx==1 (caso concreto del "mil"), no queremos que diga "un mil", sino "mil".
            # Si se trata de un millOn y Ordenes superiores (didx>0), sI queremos el "un".
            # Si l > 1 no queremos que diga "cinco millOn", sino "cinco millones".
            if l == 1: 
                if didx == 1:
                    ret = denom[didx]
                else:
                    ret = _convert_nnn(l) + ' ' + denom[didx]
            else:        
                ret = _convert_nnn(l) + ' ' + denom_plural[didx]
         
            if r > 0:
                ret = ret + ' ' + spanish_number(r)
            return ret

def amount_to_text_es(number, currency):
    print ""
    print "ddddddddddddddd"
    print "rrrrrrrrrrrrrrrr"
    print ""
    number = '%.2f' % number
    # Nota: el nombre de la moneda viene dado en el informe como "euro". AquI se convierte a
    # uppercase y se pone en plural añadiendo una "s" al final del nombre. Esto no cubre todas
    # las posibilidades (nombres compuestos de moneda), pero sirve para las mAs comunes.
    units_name = " PESOS M/L"
    int_part, dec_part = str(number).split('.')       
    start_word = spanish_number(int(int_part))
    end_word = spanish_number(int(dec_part))
    cents_number = int(dec_part)
    cents_name = (cents_number > 1) and 'CENTIMOS' or 'CENTIMO'
    final_result = start_word +' ' + units_name
    
    # Añadimos la "s" de plural al nombre de la moneda si la parte entera NO es UN euro
    if int(int_part) != 1:
        final_result += 'S'
        
    if int(dec_part) > 0:
        final_result += ' CON ' + end_word +' '+cents_name
    return final_result


#-------------------------------------------------------------
# Generic functions
#-------------------------------------------------------------

_translate_funcs = {'es' : amount_to_text_es}

def amount_to_text(nbr, lang='es', currency='Pesos'):
    """
    Converts an integer to its textual representation, using the language set in the context if any.
    Example:
        1654: thousands six cent cinquante-quatre.
    """
    from openerp import netsvc
    
    if not _translate_funcs.has_key(lang):
        print "WARNING: no translation function found for lang: '%s'" % (lang,)
        lang = 'co'
    return _translate_funcs[lang](abs(nbr), currency)

#if __name__=='__main__':
#    from sys import argv
#    
#    lang = 'nl'
#    if len(argv) < 2:
#        for i in range(1,200):
#            print i, ">>", amount_to_text(i, lang)
#        for i in range(200,999999,139):
#            print i, ">>", amount_to_text(i, lang)
#    else:
#        print amount_to_text(int(argv[1]), lang)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
