from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    ras_move_id = fields.Many2one(
        'account.move',
        string="Facture soumise au calcul de la RAS",
        compute='_compute_ras_move_id',
    )

    ras_ligne_ids = fields.One2many(
        'account.payment.register.ras',
        'register_id',
        string="Retenue à la source",
    )

    ras_montant = fields.Monetary(
        string="Montant RAS",
        compute='_compute_ras_montant',
        currency_field='currency_id',
    )

    @api.depends('line_ids', 'can_edit_wizard')
    def _compute_ras_move_id(self):
        """Le calcul de la RAS se fait sur le paiement d'une seule facture
        fournisseur comptabilisée."""
        for wizard in self:
            moves = wizard.line_ids.move_id
            wizard.ras_move_id = (
                moves
                if wizard.can_edit_wizard
                and len(moves) == 1
                and moves.move_type in ('in_invoice', 'in_refund')
                and moves.state == 'posted'
                else False
            )

    @api.depends('ras_ligne_ids.montant')
    def _compute_ras_montant(self):
        for wizard in self:
            wizard.ras_montant = sum(wizard.ras_ligne_ids.mapped('montant'))

    # ------------------------------------------------------------------
    # Ouverture de l'assistant RAS depuis la fenêtre « Payer »
    # ------------------------------------------------------------------
    def action_calculer_ras(self):
        self.ensure_one()
        if not self.ras_move_id:
            raise UserError(
                "La RAS se calcule sur le paiement d'une seule facture "
                "fournisseur comptabilisée."
            )
        return {
            'name': "Calcul de la RAS",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.ras.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.ras_move_id.id,
                'default_register_id': self.id,
            },
        }

    def _ras_action_ouvrir(self):
        """Réouvre la fenêtre « Payer »."""
        self.ensure_one()
        return {
            'name': "Payer",
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.register',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _ras_appliquer(self, montants_par_taxe):
        """Reprend la RAS calculée : montant proposé = reste dû − RAS, et
        l'écart est soldé sur les comptes RAS (facture « Payée »).

        :param montants_par_taxe: {taxe RAS: montant}
        """
        self.ensure_one()
        move = self.ras_move_id

        if self.currency_id != move.currency_id:
            raise UserError(
                "La RAS est calculée dans la devise de la facture (%s) : "
                "payez dans cette même devise." % move.currency_id.name
            )

        lignes = []
        for tax, montant in montants_par_taxe.items():
            montant = move.currency_id.round(montant)
            if move.currency_id.is_zero(montant):
                continue
            compte = tax._ras_compte()
            if not compte:
                raise UserError(
                    "Aucun compte comptable sur la taxe « %s ». "
                    "Renseignez-le dans Comptabilité → Configuration → "
                    "Taux RAS (onglet Définition, ligne « Taxe »)."
                    % tax.name
                )
            lignes.append((0, 0, {
                'tax_id': tax.id,
                'name': tax.name,
                'account_id': compte.id,
                'montant': montant,
            }))

        reste_du = abs(move.amount_residual)
        total_ras = sum(l[2]['montant'] for l in lignes)
        if move.currency_id.compare_amounts(total_ras, reste_du) > 0:
            raise UserError(
                "La RAS (%s) dépasse le montant restant dû de la facture "
                "(%s)." % (total_ras, reste_du)
            )

        net = reste_du - total_ras
        vals = {
            'ras_ligne_ids': [(5, 0, 0)] + lignes,
            'amount': net,
            'custom_user_amount': net if lignes else False,
        }
        if lignes:
            vals.update({
                'payment_difference_handling': 'reconcile',
                'writeoff_account_id': lignes[0][2]['account_id'],
                'writeoff_label': "Retenue à la source",
            })
        self.write(vals)

    # ------------------------------------------------------------------
    # Écriture du paiement : une ligne par taxe RAS
    # ------------------------------------------------------------------
    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)

        if not self.ras_ligne_ids:
            return payment_vals

        if (
            self.payment_difference_handling != 'reconcile'
            or self.currency_id.compare_amounts(
                self.payment_difference, self.ras_montant
            ) != 0
        ):
            raise UserError(
                "Le montant du paiement a été modifié après le calcul de "
                "la RAS. Cliquez de nouveau sur « Calculer la RAS »."
            )

        signe = 1 if self.payment_type == 'inbound' else -1
        payment_vals['write_off_line_vals'] = [
            {
                'name': ligne.name,
                'account_id': ligne.account_id.id,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
                'amount_currency': signe * ligne.montant,
                'balance': self.currency_id._convert(
                    signe * ligne.montant,
                    self.company_id.currency_id,
                    self.company_id,
                    self.payment_date,
                ),
            }
            for ligne in self.ras_ligne_ids
        ]
        return payment_vals


class AccountPaymentRegisterRas(models.TransientModel):
    _name = 'account.payment.register.ras'
    _description = "Ligne de RAS du paiement"

    register_id = fields.Many2one(
        'account.payment.register',
        required=True,
        ondelete='cascade',
    )
    currency_id = fields.Many2one(related='register_id.currency_id')
    tax_id = fields.Many2one('account.tax', string="Taxe RAS", readonly=True)
    name = fields.Char(string="Libellé", readonly=True)
    account_id = fields.Many2one(
        'account.account',
        string="Compte",
        readonly=True,
    )
    montant = fields.Monetary(
        string="Montant",
        currency_field='currency_id',
        readonly=True,
    )
