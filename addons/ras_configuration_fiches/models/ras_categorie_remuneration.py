import re
import unicodedata

from odoo import models, fields, api


class RasCategorieRemuneration(models.Model):
    """Référentiel paramétrable des catégories de rémunération RAS.

    Chaque catégorie porte les codes exigés par la DGI dans les fichiers de
    déclaration : nature d'opération (RAS TVA) et nature de rémunération
    (RAS IS). Les codes sont modifiables par l'utilisateur.
    """
    _name = 'ras.categorie.remuneration'
    _description = "Catégorie de rémunération RAS"
    _order = 'sequence, name'

    name = fields.Char(string="Libellé", required=True, translate=True)
    code = fields.Char(
        string="Code interne",
        compute='_compute_code',
        store=True,
        readonly=False,
        help="Généré automatiquement à partir du libellé."
    )
    code_dgi_tva = fields.Selection(
        [('1', "1 - Achat de biens d'équipement"),
         ('2', "2 - Achat de travaux"),
         ('3', "3 - Achat de services")],
        string="Code DGI XML TVA",
        default='3',
        help="Nature de l'opération (balise refNatOpt) reprise dans le "
             "fichier de déclaration de la RAS TVA."
    )
    code_dgi_is = fields.Char(
        string="Code DGI XML IS",
        help="Code « nature de rémunération » repris dans le fichier de "
             "déclaration de la RAS IS."
    )
    ras_soumis_tva = fields.Boolean(string="RAS TVA", default=True)
    ras_soumis_is = fields.Boolean(string="RAS IS", default=True)
    sequence = fields.Integer(string="Séquence", default=10)
    active = fields.Boolean(string="Actif", default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', "Ce code interne existe déjà."),
    ]

    @api.depends('name')
    def _compute_code(self):
        """Code technique déduit du libellé : « Autres rémunérations » -> autres_remunerations."""
        for rec in self:
            if rec.code:
                continue
            texte = unicodedata.normalize('NFKD', rec.name or '')
            texte = texte.encode('ascii', 'ignore').decode('ascii').lower()
            rec.code = re.sub(r'[^a-z0-9]+', '_', texte).strip('_') or 'categorie'

    @api.depends('name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name
