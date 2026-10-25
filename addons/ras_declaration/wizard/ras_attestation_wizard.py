from odoo import models, fields, api


class RasAttestationWizard(models.TransientModel):
    _name = 'ras.attestation.wizard'
    _description = "Attestation RAS : références du versement"

    declaration_id = fields.Many2one(
        'ras.declaration',
        string="Déclaration",
        required=True,
        readonly=True,
    )
    date_reversement = fields.Date(
        string="Date de reversement",
        required=True,
    )
    reference_quittance = fields.Char(
        string="Réf. Versement DGI",
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        # Références déjà saisies lors d'une impression précédente
        res = super().default_get(fields_list)
        declaration = self.env['ras.declaration'].browse(
            res.get('declaration_id')
        )
        if declaration:
            res.setdefault('date_reversement', declaration.date_reversement)
            res.setdefault(
                'reference_quittance', declaration.reference_quittance
            )
        return res

    def action_generer(self):
        self.ensure_one()
        # Les comptables ne modifient pas les déclarations : seules ces
        # références sont enregistrées, depuis cet assistant.
        self.declaration_id.sudo().write({
            'date_reversement': self.date_reversement,
            'reference_quittance': self.reference_quittance,
        })
        return self.env.ref(
            'ras_declaration.action_report_ras_attestation'
        ).report_action(self.declaration_id, config=False)
