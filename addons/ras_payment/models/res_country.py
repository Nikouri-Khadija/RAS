from odoo import models, api


class ResCountry(models.Model):
    _inherit = 'res.country'

    def _ras_ensure_export_taxes(self):
        """Crée la taxe RAS Non-résident correspondant au taux conventionnel
        du pays, pour chaque société ayant un plan comptable."""
        Tax = self.env['account.tax'].sudo()
        companies = self.env['res.company'].sudo().search(
            [('chart_template', '!=', False)]
        )
        for country in self:
            taux = country.ras_taux_conventionnel
            if not country.ras_convention_fiscale or not taux:
                continue
            for company in companies:
                Tax._ras_get_or_create_export_tax(company, taux)

    @api.model_create_multi
    def create(self, vals_list):
        countries = super().create(vals_list)
        countries._ras_ensure_export_taxes()
        return countries

    def write(self, vals):
        res = super().write(vals)
        if 'ras_taux_conventionnel' in vals or 'ras_convention_fiscale' in vals:
            self._ras_ensure_export_taxes()
        return res
