# -*- coding: utf-8 -*-
{
    'name': 'Mejoras varias para nómina',
    'version': '2.0',
    'author': 'Avancys SAS',
    'website': 'http://www.avancys.com.co',
    'category': 'Payroll',
    'depends': ['hr_agroz'],
    'description': '''
        Contiene:
        - Retiros masivos (Finalización de contrato)
        - Nóminas retroactivas
        - Reliquidación de nóminas
        - Riesgo según el cargo
        - Validación de tercero por cuenta bancaria (Tercero requerido en cuenta bancaria)
        - Referencia del contrato automatica
        - Desprendible de nómina
        - Incapacidad de prórrroga
        - Restricción unica para cuentas bancarias por propietario
        - Prenómina dinamica (muestra todas reglas las reglas que tienen marcada la opción de ver en nómina)
        - Restricción de dias por año en el tipo de ausencia. Aplicable para Calamidades domesticas por ejemplo.
        - Identificación de dependientes en el empleado
        - Deducibles en el contrato (configurables por tipo)
        
        NOTA: Se debe instalar en postgresql la extensión tablefunc mediante: CREATE extension tablefunc;
    ''',
    'init_xml': [],
    'data': [
        "data/cron_data.xml",
        "reports/desprendible.xml",
        "views/hr_payroll_extended_misc_view.xml",
        "views/hr_holidays_extended_view.xml",
        "views/hr_contract_extended_view.xml",
        "views/hr_payroll_prenomina_view.xml",
    ],
    'auto_install': True,
    'installable': True,
    'application': False,
}
