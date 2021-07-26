# -*- coding: utf-8 -*-
{
    'name': 'Sale Margin Extended',
    'version': '1.0',
    'category': 'sale',
    'complexity': "normal",
    'description': """Modulo para gestionar la visibilidad del margen y el costo en los pedidos de venta
    """,
    'author': 'Avancys',
    'website': 'http://www.avancys.com',
    'depends': ['sale_margin','sale_extended','inventory_account'],
    'data' : [
        'sale_margin_extended_view.xml',        
        ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: