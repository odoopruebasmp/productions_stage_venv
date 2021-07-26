from openerp.osv import osv, fields
import openerp.addons.decimal_precision as dp
import openerp.report
import openerp.tools
import re
import sys
from openerp.tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp import netsvc
from calendar import monthrange
from datetime import datetime, timedelta
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parents
from openerp.report.report_sxw import rml_tag
from amount_to_text_es import amount_to_text_es
from openerp.tools.amount_to_text_en import amount_to_text as amount_to_text_en
from openerp.tools.amount_to_text import amount_to_text_fr
from openerp.tools.amount_to_text import amount_to_text_nl

units_29 = ( 'CERO', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS',
          'SIETE', 'OCHO', 'NUEVE', 'DIEZ', 'ONCE', 'DOCE',
          'TRECE', 'CATORCE', 'QUINCE', 'DIECISEIS', 'DIECISIETE', 'DIECIOCHO',
          'DIECINUEVE', 'VEINTE', 'VEINTIUN', 'VEINTIDOS', 'VEINTITRES', 'VEINTICUATRO',
          'VEINTICINCO', 'VEINTISEIS', 'VEINTISIETE', 'VEINTIOCHO', 'VEINTINUEVE' )       

tens = ( 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA', 'CIEN')       

denom = ('',
          'MIL', 'MILLON', 'MIL MILLONES', 'BILLON', 'MIL BILLONES', 'TRILLON', 'MIL TRILLONES',
          'CUATRILLON', 'MIL CUATRILLONES', 'QUINTILLON', 'MIL QUINTILLONES', 'SEXTILLON', 'MIL SEXTILLONES', 'SEPTILLON',
          'MIL SEPTILLONES', 'OCTILLON', 'MIL OCTILLONES', 'NONILLON', 'MIL NONILLONES', 'DECILLON', 'MIL DECILLONES' )

denom_plural = ('',
          'MIL', 'MILLONES', 'MIL MILLONES', 'BILLONES', 'MIL BILLONES', 'TRILLONES', 'MIL TRILLONES',
          'CUATRILLONES', 'MIL CUATRILLONES', 'QUINTILLONES', 'MIL QUINTILLONES', 'SEXTILLONES', 'MIL SEXTILLONES', 'SEPTILLONES',
          'MIL SEPTILLONES', 'OCTILLONES', 'MIL OCTILLONES', 'NONILLONES', 'MIL NONILLONES', 'DECILLONES', 'MIL DECILLONES' )

denomm = ('',
          'MIL', 'MILLON', 'MIL', 'BILLON', 'MIL', 'TRILLON', 'MIL',
          'CUATRILLON', 'MIL', 'QUINTILLON', 'MIL', 'SEXTILLON', 'MIL', 'SEPTILLON',
          'MIL', 'OCTILLON', 'MIL', 'NONILLON', 'MIL', 'DECILLON', 'MIL' )

denomm_plural = ('',
          'MIL', 'MILLONES', 'MIL', 'BILLONES', 'MIL', 'TRILLONES', 'MIL',
          'CUATRILLONES', 'MIL', 'QUINTILLONES', 'MIL', 'SEXTILLONES', 'MIL', 'SEPTILLONES',
          'MIL', 'OCTILLONES', 'MIL', 'NONILLONES', 'MIL', 'DECILLONES', 'MIL' )

def setCompany_expanded(self, company_id):
    if company_id:
        self.localcontext['avancys_amount_to_text_decimal'] = avancys_amount_to_text_decimal
        self.localcontext['avancys_amount_to_text'] = avancys_amount_to_text
        self.localcontext['company'] = company_id
        self.localcontext['logo'] = company_id.logo
        self.rml_header = company_id.rml_header
        self.rml_header2 = company_id.rml_header2
        self.rml_header3 = company_id.rml_header3
        self.logo = company_id.logo


def _convert_nn(val):
    if val < 30:
        return units_29[val]
    for (dcap, dval) in ((k, 30 + (10 * v)) for (v, k) in enumerate(tens)):
        if dval + 10 > val:
            if val % 10:
                return dcap + ' Y ' + units_29[val % 10]
            return dcap


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
        elif quotient == 7:
            word = 'SETECIENTOS'
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
                # Se busca descartar todos aquellos montos que corresponden a fracciones de mil para corregir el "Un mil"
                if didx%2 != 0:
                    # Este if busca tratar los montos superiones a los miles de millones:
                    if (mod/1000000000) >= 1:
                        # A partir de encontrar algun munto superior a los miles de millones se busca dejar solo un denominador de la fraccion es decir solo "mil" o billones, trillones .....
                        ret = denomm[didx]
                        # En este if se busca encontrar si la siguiente fraccion aun se encuentra bajo la misma denominacion previa a la fraccion de mil "Ej: mil doscientos millones" corrigiendo el "mil millones doscientos millones"
                        if r < mod / 1000 and ret[-3:]=='MIL':
                            ret = ret + ' ' + denomm_plural[didx - 1]
                    else:
                        ret = denom[didx]
                else:
                    if (mod/1000000000) >= 1:
                        ret = _convert_nnn(l) + ' ' + denomm[didx]
                        if r < mod / 1000 and ret[-3:]=='MIL':
                            ret = ret + ' ' + denomm[didx - 1]
                    else:
                        ret = _convert_nnn(l) + ' ' + denom[didx]
            else:

                if (mod/1000000000) >= 1:
                    ret = _convert_nnn(l) + ' ' + denomm_plural[didx]
                    if r < mod / 1000 and ret[-3:]=='MIL':
                        ret = ret + ' ' + denomm_plural[didx - 1]
                else:
                    ret = _convert_nnn(l) + ' ' + denom_plural[didx]

            if r > 0:
                ret = ret + ' ' + spanish_number(r)
            return ret


def avancys_amount_to_text_decimal(amount, lang=None, currency=''):
    if not lang:
        lang = 'es_CO'
    lang_options = re.split('(_)',lang)
    lang=lang_options[0]
    lang_country=lang_options[0]

    #spanish
    if lang == 'es':
        number = '%.2f' % amount
        if currency == 'COP':
            units_name = "PESO"
        elif currency == 'USD':
            units_name = " DOLARE"
        else:
            units_name = "PESO"

        text=""
        int_part, dec_part = str(number).split('.')
        start_word = spanish_number(int(int_part))
        end_word = spanish_number(int(dec_part))
        cents_number = int(dec_part)
        cents_name = (cents_number > 1) and 'CENTAVOS MCTE' or 'CENTAVO MCTE'
        if start_word[:3] == 'MIL' and start_word[4:6] == 'UN':
            start_word = start_word.replace("MILLON", "MILLONES")
        if start_word[-3:] == 'NES' or start_word[-2:] == 'ON':
            final_result = start_word + ' ' + 'DE' + ' ' + units_name
        else:
            final_result = start_word + ' ' + units_name
        if int(int_part) != 1:
            final_result += 'S'
            if units_name == 'PESO' and cents_number==0:
                final_result += ' MCTE'
        if int(dec_part) > 0:
            final_result += ' CON ' + end_word +' '+cents_name
        text = final_result

    #english
    if lang == 'en':
        text = amount_to_text_en(float(amount))+' of Dolar'

    return text

def avancys_amount_to_text(amount, lang=None, currency=''):
    print "xxxxxxxxxxxxxxxxx"
    if not lang:
        lang = 'es_CO'
    lang_options = re.split('(_)',lang)
    lang=lang_options[0]
    lang_country=lang_options[0]

    #spanish
    if lang == 'es':
        text = amount_to_text_es(int(amount))
    #english
    if lang == 'en':
        text = amount_to_text_en(int(amount))
    #french
    if lang == 'fr':
        text = amount_to_text_fr(int(amount),currency)
    #dutch
    if lang == 'nl':
        text = amount_to_text_nl(int(amount),currency)

    if currency == 'COP':
        text += "PESOS MCTE"
    elif currency == 'USD':
        text += "DOLARES"

    return text

#sys.modules['openerp.report.report_sxw'].rml_parse.setCompany = setCompany_expanded

