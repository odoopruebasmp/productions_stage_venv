# -*- coding: utf-8 -*-
#################################################################################
# Author      : Acespritech Solutions Pvt. Ltd. (<www.acespritech.com>)
# Copyright(c): 2012-Present Acespritech Solutions Pvt. Ltd.
# All Rights Reserved.
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################
{
    'name': 'Ticket para POS',
    'version': '1.0',
    'category': 'Point of Sale',
    'summary': 'Ticket para POS',
    'description': """
Diseño personalizado de ticket.
""",
    'author': "Avancys SAS",
    'website': 'http://www.avancys.com',
    'price': 0.00, 
    'currency': 'COP',
    'depends': ['web', 'point_of_sale', 'base', 'sale', 'purchase'],
    'images': ['static/images/main_screenshot.png'],
    'data': [
    ],
    'demo': [],
    'test': [],
    'qweb': ['static/src/xml/pos.xml'],
    'installable': True,
    'auto_install': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: