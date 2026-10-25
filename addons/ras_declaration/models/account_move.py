from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _ras_comptabilisee(self, ras_type):
        """Montant de RAS du type donné (tva, is…) réellement comptabilisé
        dans les paiements de la facture (lignes sur les comptes des taxes
        RAS de ce type)."""
        self.ensure_one()
        taxes = self.env['account.tax'].search([
            ('ras_is_retenue_source', '=', True),
            ('ras_type', '=', ras_type),
            ('company_id', '=', self.company_id.id),
        ])
        comptes = self.env['account.account'].browse(
            {tax._ras_compte().id for tax in taxes} - {False}
        )
        lignes = self._get_reconciled_payments().move_id.line_ids.filtered(
            lambda l: l.account_id in comptes
        )
        return sum(lignes.mapped('credit')) - sum(lignes.mapped('debit'))
