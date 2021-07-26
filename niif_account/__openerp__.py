{
    'name': 'NIIF ACCOUT (CARTERA)',
    'version': '1.11',
    'category': 'Account',
    'complexity': "normal",
    'description': """
        Este modulo permite ejecutar un proceso mensual que calcula el deterioro y recuperacion de cartera.
    """,
    'author':'Avancys',
    'website':'www.avancys.com',
    'depends': [
        'inventory_account',
        'account_loan',
        'financial_reports',
        ],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'deterioro_cartera_view.xml',
        'account_view.xml',
        'account_loan_view.xml',
        'account_tax_view.xml',
    ],
    'demo_xml': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
