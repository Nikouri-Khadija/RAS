from odoo import models, fields


class RasMotifExclusion(models.Model):
    """Motifs d'exclusion de la RAS, paramétrables depuis la catégorie de
    produit (création directe dans le champ, sans menu dédié)."""
    _name = 'ras.motif.exclusion'
    _description = "Motif d'exclusion RAS"
    _order = 'sequence, name'

    name = fields.Char(string="Libellé", required=True, translate=True)
    sequence = fields.Integer(string="Séquence", default=10)
    active = fields.Boolean(string="Actif", default=True)
