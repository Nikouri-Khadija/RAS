from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Identifiant fiscal, repris dans les déclarations de retenue à la
    # source. L'ICE est le champ standard d'Odoo (« Company Registry »,
    # libellé « ICE » par la localisation marocaine).
    ras_identifiant_fiscal = fields.Char(
        string="Identifiant fiscal (IF)",
        help="Identifiant fiscal de la société, repris dans les fichiers de "
             "déclaration des retenues à la source."
    )

    ras_seuil_tva = fields.Monetary(
        string="Seuil RAS TVA (TTC)",
        currency_field='currency_id',
        default=5000.0,
        help="Montant TTC de la facture à partir duquel la RAS TVA "
             "s'applique. En dessous, pas de RAS TVA."
    )

    ras_oblige_retenue_is = fields.Boolean(
        string="Obligation de pratiquer la RAS IS",
        default=True,
        help=(
            "Indique si la société est tenue de pratiquer la retenue à la "
            "source au titre de l'IS."
        ),
    )
    ras_oblige_retenue_ir = fields.Boolean(
        string="Obligation de pratiquer la RAS IR",
        default=True,
        help=(
            "Indique si la société est tenue de pratiquer la retenue à la "
            "source au titre de l'IR."
        ),
    )