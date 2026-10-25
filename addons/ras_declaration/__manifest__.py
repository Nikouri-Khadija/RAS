{
    'name': 'Déclaration RAS - Retenue à la Source (Maroc)',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': "Déclaration XML de la RAS TVA et attestations de retenue "
               "à la source, à partir de la RAS calculée au paiement",
    'author': "Nikouri Khadija",
    'depends': ['ras_payment'],
    'data': [
        'security/ir.model.access.csv',
        'views/ras_declaration_views.xml',
        'wizard/ras_declaration_wizard_views.xml',
        'report/ras_attestation_report.xml',
        'wizard/ras_attestation_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
