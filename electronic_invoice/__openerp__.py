# -*- coding: utf-8 -*-
{
    'name': 'Factura Electrónica CO',
    'version': '1.0',
    'author': 'Avancys SAS',
    'website': 'www.avancys.com',
    'category': 'Accounting & Finance',
    'depends': ['inventory_account'],
    'summary': 'Control proceso generación Factura Electrónica',
    'description': '''
    - Generación de XML de Facturación Electrónica, automática o manual según política en la compañía, para Facturas de Venta, Notas Crédito y Notas Débito
    - Envío de archivos adjuntos (orden compra de cliente, remisión) junto a XML de Factura Electrónica
    - Generación masiva se XML de facturación electrónica
    - Cargue automático de los documentos PDF y XML generadas por Carvajal a las Facturas del sistema
    - Control de registros para las operaciones de Facturación Electrónica
    - Adición de campos 53 y 54 del formulario RUT - DIAN, en el modelo res.partner.
    ''',
    'init_xml': [],
    'data': [
        'data/ei_cron.xml',
        'security/ei_security.xml',
        'wizard/change_ei_state.xml',
        'wizard/generate_ei_xml.xml',
        'views/electronic_invoice.xml',
        'views/tributary_information.xml',
        'views/vat_exemption_products.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
