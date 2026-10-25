{
    'name': 'RAS au paiement - Retenue à la Source (Maroc)',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': "Calcul de la Retenue à la Source (TVA, IS, IR, Non-résident) "
               "au moment du paiement des factures fournisseurs",
    'author': "Nikouri Khadija",
    'depends': ['account', 'ras_configuration_fiches'],
    'data': [
        'security/ir.model.access.csv',
        'data/account_tax_data.xml',
        'data/ras_compte_data.xml',
        'views/account_tax_views.xml',
        'views/ras_tax_menu_views.xml',
        'views/account_move_views.xml',
        'wizard/ras_wizard_views.xml',
        'wizard/account_payment_register_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
