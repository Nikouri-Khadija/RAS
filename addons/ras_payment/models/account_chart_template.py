from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _post_load_data(self, template_code, company, template_data):
        # Multi-sociétés : dès qu'une société charge son plan comptable,
        # elle reçoit les taxes RAS par défaut (le fichier data ne couvre
        # que la société principale).
        res = super()._post_load_data(template_code, company, template_data)
        self.env['account.tax'].sudo()._ras_create_default_taxes(company)
        return res
