from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

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

    ras_soumis_tva = fields.Boolean(string="RAS TVA", default=True)
    ras_soumis_is = fields.Boolean(string="RAS IS", default=True)

    @api.onchange('categ_id')
    def _onchange_categ_id_ras(self):
        for product in self:
            if product.categ_id:
                product.ras_categorie = product.categ_id.ras_categorie
                product.ras_motif_exclusion_id = product.categ_id.ras_motif_exclusion_id
                product.ras_categorie_remuneration_id = product.categ_id.ras_categorie_remuneration_id
                product.ras_soumis_tva = product.categ_id.ras_soumis_tva
                product.ras_soumis_is = product.categ_id.ras_soumis_is