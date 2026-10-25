from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = 'product.category'

    ras_categorie = fields.Selection(
        [('soumis', 'Soumis à la RAS'),
         ('exclu', 'Exclu de la RAS')],
        string="Catégorie RAS"
    )

    ras_motif_exclusion_id = fields.Many2one(
        'ras.motif.exclusion',
        string="Motif d'exclusion"
    )

    ras_categorie_remuneration_id = fields.Many2one(
        'ras.categorie.remuneration',
        string="Catégorie de rémunération RAS",
        help="Qualifie la rémunération pour la RAS et porte les codes DGI "
             "repris dans les fichiers de déclaration."
    )

    ras_soumis_tva = fields.Boolean(
        string="RAS TVA",
        compute='_compute_ras_soumis',
        store=True,
        readonly=False,
        help="Pré-coché selon la catégorie de rémunération, modifiable."
    )

    ras_soumis_is = fields.Boolean(
        string="RAS IS",
        compute='_compute_ras_soumis',
        store=True,
        readonly=False,
        help="Pré-coché selon la catégorie de rémunération, modifiable."
    )

    @api.depends('ras_categorie_remuneration_id')
    def _compute_ras_soumis(self):
        for categorie in self:
            remuneration = categorie.ras_categorie_remuneration_id
            categorie.ras_soumis_tva = remuneration.ras_soumis_tva if remuneration else True
            categorie.ras_soumis_is = remuneration.ras_soumis_is if remuneration else True

    def write(self, vals):
        res = super().write(vals)
        # Si un des champs RAS a été modifié sur la catégorie,
        # on met à jour automatiquement les produits liés
        if any(field in vals for field in ('ras_categorie', 'ras_motif_exclusion_id', 'ras_categorie_remuneration_id', 'ras_soumis_tva', 'ras_soumis_is')):
            for categorie in self:
                produits = self.env['product.template'].search([('categ_id', '=', categorie.id)])
                produits.write({
                    'ras_categorie': categorie.ras_categorie,
                    'ras_motif_exclusion_id': categorie.ras_motif_exclusion_id.id,
                    'ras_categorie_remuneration_id': categorie.ras_categorie_remuneration_id.id,
                    'ras_soumis_tva': categorie.ras_soumis_tva,
                    'ras_soumis_is': categorie.ras_soumis_is,
                })
        return res