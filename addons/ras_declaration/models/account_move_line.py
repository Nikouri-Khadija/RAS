from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _ras_categorie_remuneration(self):
        """Catégorie de rémunération RAS de la ligne (via l'article)."""
        self.ensure_one()
        product = self.product_id
        if not product:
            return self.env['ras.categorie.remuneration']
        return (
            product.ras_categorie_remuneration_id
            or product.categ_id.ras_categorie_remuneration_id
        )

    def _ras_code_dgi(self, ras_type='tva'):
        """Code DGI de la ligne pour le fichier de déclaration du type donné :
        nature d'opération (RAS TVA) ou nature de rémunération (RAS IS).
        Vide si l'article n'a pas de catégorie.
        """
        self.ensure_one()
        categorie = self._ras_categorie_remuneration()
        return (categorie['code_dgi_%s' % ras_type] if categorie else '') or ''
