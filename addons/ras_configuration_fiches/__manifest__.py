{
    'name': 'Configuration des Fiches RAS',
    'version': '18.0.1.1.0',
    'category': 'Accounting/Localizations',
    'summary': "Champs de configuration RAS TVA sur les fiches Fournisseur, Société et Produit",
    'author': 'Nikouri Khadija',
    'description': """
Ce module ajoute les champs de configuration nécessaires à la gestion
de la Retenue à la Source (RAS TVA) au Maroc 
    """,
    'depends': ['base', 'account', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/ras_categorie_remuneration_data.xml',
        'data/ras_motif_exclusion_data.xml',
        'views/ras_categorie_remuneration_views.xml',
        'views/res_country_views.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/product_category_views.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
}
