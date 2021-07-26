UNIDADES = ( '', 'UN ', 'DOS ', 'TRES ', 'CUATRO ', 'CINCO ', 'SEIS ', 'SIETE ', 'OCHO ', 'NUEVE ', 'DIEZ ', 'ONCE ', 'DOCE ', 'TRECE ', 'CATORCE ', 'QUINCE ', 'DIECISEIS ', 'DIECISIETE ', 'DIECIOCHO ', 'DIECINUEVE ', 'VEINTE ')
DECENAS = ('VENTI', 'TREINTA ', 'CUARENTA ', 'CINCUENTA ', 'SESENTA ', 'SETENTA ', 'OCHENTA ', 'NOVENTA ', 'CIEN ')
CENTENAS = ('CIENTO ', 'DOSCIENTOS ', 'TRESCIENTOS ', 'CUATROCIENTOS ', 'QUINIENTOS ', 'SEISCIENTOS ', 'SETECIENTOS ', 'OCHOCIENTOS ', 'NOVECIENTOS '  )       
 
def amount_to_text_es(number_in):
    convertido = ''
    if number_in < 0:
        convertido = 'MENOS '
    number_str = str(number_in) if (type(number_in) != 'str') else number_in
    number_str =  number_str.zfill(12)
    billones, millones, miles, cientos = number_str[:3], number_str[3:6], number_str[6:9], number_str[9:]
    if(billones):
        if(billones == '001'):
            convertido += 'UN MILLARDOS '
        elif(int(billones) > 0):
            convertido += '%s MIL MILLONES ' % __convertNumber(billones)
    if(millones):
        if(millones == '001'):
            convertido += 'UN MILLON '
        elif(int(millones) > 0):
            convertido += '%sMILLONES ' % __convertNumber(millones)
    if(miles):
        if(miles == '001'):
            convertido += 'MIL '
        elif(int(miles) > 0):
            convertido += '%sMIL ' % __convertNumber(miles)
    if(cientos):
        if(cientos == '001'):
            convertido += 'UN '
        elif(int(cientos) > 0):
            convertido += '%s ' % __convertNumber(cientos)
    return convertido
 
def __convertNumber(n):
    output = ''
    if(n == '100'):
        output = "CIEN "
    elif(n[0] != '0'):
        output = CENTENAS[int(n[0])-1]
    k = int(n[1:])
    if(k <= 20):
        output += UNIDADES[k]
    else:
        if((k > 30) & (n[2] != '0')):
            output += '%sY %s' % (DECENAS[int(n[1])-2], UNIDADES[int(n[2])])
        else:
            output += '%s%s' % (DECENAS[int(n[1])-2], UNIDADES[int(n[2])])
    return output
 
