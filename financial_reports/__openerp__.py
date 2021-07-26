# -*- coding: utf-8 -*-
{
    'name': 'Reportes Avancys',
    'version': '0.1',
    'author' : 'Avancys',
    'website': 'http://www.avancys.com.co',
    'category': 'Accounting',
    'depends': ['account_analytic_avancys','avancys_orm2sql','hr_payroll_extended'],
    'description': '''
        Agrega informes:\n
        * Analíticos:
            - Libro auxiliar analítico
        * Auditoría:
            - Detalles registros contables
        * Contables:
            - Balance de pruebas
            - Libro auxiliar
            - Mayor y balance
            - Libro diario
            - Inventario y balance
            - Libro auxiliar (Equivalente NIIF)
            - Equivalente NIIF
            - Libro auxiliar (Moneda Extranjera)
        * Información Exógena:
            - 1001 - Pagos o abonos en cuenta y retenciones practicadas
            - 1003 - Retenciones en la fuente que le practicaron
            - 1007 - Ingresos Recibidos 
            - 1008 - Saldo de cuentas por cobrar 
            - 1009 - Saldo de cuentas por pagar 
            - 1012 - Información de declaraciones tributarias, acciones, inversiones en bonos títulos valores y cu 
            - 2276 - Información Certificado de Ingresos y Retenciones para personas naturales Empleados 
        * Financieros:
            - Balance general
            - Estado de resultados integrales por centro de costo
            - Estado de resultados integrales por función
            - Cambios en situación financiera
            - Cambios en el patrimonio
            - Flujo de caja (Anual)
            - Estado de resultados integrales por naturaleza
            - Estado de resultados Integrales por centro de costo nivel 3
        * Financieros (Comparativos):
            - Balance general (Comparativo)
            - Flujo de efectivo (Método directo)
            - Flujo de efectivo (Método indirecto)
            - Estado de resultados integrales (Comparativo)
            - Estado de resultados integrales por centro de costo (Comparativo)
        * Impuestos:
            - Libro auxiliar de impuestos
            - Ventas - Devoluciones de impuestos por municipio       
    ''',
    'init_xml': [],
    'data': [
        "security/security.xml",
        "financial_reports_view.xml",        
        "menus.xml",
        #VIEWS        
        # "accounting/menus.xml",
        "accounting/views/balance_pruebas_view.xml",
        "accounting/views/auxiliar_view.xml",
        "accounting/views/auxiliar_fc_view.xml",
        "accounting/views/auxiliar_analitico_view.xml",
        "accounting/views/auxiliar_equivalente_view.xml",
        "accounting/views/estado_resultados_view.xml",
        "accounting/views/estado_resultados_comparativo_view.xml",
        "accounting/views/estado_resultados_comparativo_cc_view.xml",
        "accounting/views/estado_resultados_cc_view.xml",
        "accounting/views/flujocaja_view.xml",
        "accounting/views/balance_general_view.xml",
        "accounting/views/foreing_currency_view.xml",
        "accounting/views/mayor_balance_view.xml",
        "accounting/views/diario_view.xml",
        "accounting/views/equity_changes_view.xml",
        "accounting/views/inventario_balance_view.xml",
        "accounting/views/auxiliar_taxes_view.xml",
        "accounting/views/sale_munic_taxes_view.xml",
        # REPORTS
        "accounting/reports/formatos_papel.xml",
        "accounting/reports/report_balance_pruebas.xml",
        "accounting/reports/report_estado_resultados.xml",
        "accounting/reports/report_pyg_c_cc.xml",
        "accounting/reports/report_flujocaja.xml",
        "accounting/reports/report_auxiliar.xml",
        "accounting/reports/report_auxiliar_fc.xml",
        "accounting/reports/report_auxiliar_analitico.xml",
        "accounting/reports/report_auxiliar_equivalente.xml",
        "accounting/reports/report_mayor_balance.xml",
        "accounting/reports/report_diario.xml",
        "accounting/reports/report_inventario_balance.xml",
        "accounting/reports/report_fpa_c_line.xml",
        "accounting/reports/report_equity.xml",
        "accounting/reports/report_sale_munic_taxes.xml",
        #DATA
        "accounting/data/data_er_balance_general.xml",
        "accounting/data/data_equivalente_niif.xml",
        "accounting/data/data_er_balance_general_comparativo.xml",
        "accounting/data/data_er_flujo_efectivo_dir.xml",
        "accounting/data/data_er_flujo_efectivo_indir.xml",
        "accounting/data/data_estado_resultados_comparativo.xml",
        "accounting/data/data_estado_resultados_comparativo_cc.xml",
        "accounting/data/data_estado_resultados_cc.xml",
        "accounting/data/data_estado_resultados_funciones.xml",
        "accounting/data/data_estado_resultados_naturaleza.xml",
        "accounting/data/data_situacion_financiera.xml",
        "accounting/data/data_foreing_currency.xml",
        "accounting/data/data_equity_changes.xml",
        "accounting/data/data_flujocaja.xml",
        "accounting/data/data_detalle_contable.xml",
        "accounting/data/data_auxiliar_taxes.xml",
        "accounting/data/data_sale_munic_taxes.xml",
        "medios/data/data_1001.xml",
        "medios/data/data_1003.xml",
        "medios/data/data_1005.xml",
        "medios/data/data_1006.xml",
        "medios/data/data_1007.xml",
        "medios/data/data_1008.xml",
        "medios/data/data_1009.xml",
        "medios/data/data_1012.xml",
        "medios/data/data_2276.xml",
        "accounting/data/data_balance_pruebas.xml",
        "accounting/data/data_auxiliar.xml",
        "accounting/data/data_auxiliar_fc.xml",
        "accounting/data/data_auxiliar_analitico.xml",
        "accounting/data/data_auxiliar_equivalente.xml",
        "accounting/data/data_mayor_balance.xml",
        "accounting/data/data_diario.xml",
        "accounting/data/data_inventario_balance.xml",
        "security/ir.model.access.csv",
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}
