from odoo import models, fields


class ResCountry(models.Model):
    _inherit = 'res.country'

    ras_convention_fiscale = fields.Boolean(
        string="Convention fiscale avec le Maroc",
        help="Coche cette case si une convention de non-double imposition "
             "est en vigueur entre le Maroc et ce pays."
    )
    ras_taux_conventionnel = fields.Float(
        string="Taux conventionnel RAS Non-résident (%)",
        help="Taux réduit de retenue à la source prévu par la convention "
             "fiscale. Appliqué à la place du taux de droit commun (10 %) "
             "lorsque le fournisseur fournit une attestation de résidence "
             "fiscale valide."
    )
