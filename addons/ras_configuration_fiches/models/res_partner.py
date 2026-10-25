from dateutil.relativedelta import relativedelta
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Identifiant fiscal, repris dans les déclarations de retenue à la
    # source. L'ICE est le champ standard d'Odoo.
    ras_identifiant_fiscal = fields.Char(
        string="Identifiant fiscal (IF)",
        help="Identifiant fiscal du fournisseur, repris dans les fichiers de "
             "déclaration des retenues à la source."
    )

    # --- Type du fournisseur ---
    ras_type_fournisseur = fields.Selection(
        [('personne_physique', 'Personne physique'),
         ('societe', 'Personne morale')],
        string="Type de fournisseur"
    )

    # --- Résidence fiscale (RAS Non-résident) ---
    ras_residence_fiscale = fields.Selection(
        [('resident', 'Résident'),
         ('non_resident', 'Non-résident')],
        string="Résidence fiscale",
        compute='_compute_ras_residence_fiscale',
        store=True,
        readonly=False,
        help="Déduit automatiquement du pays de l'adresse "
             "(pays différent du Maroc = non-résident). Modifiable si besoin."
    )
    ras_convention_fiscale = fields.Boolean(
        related='country_id.ras_convention_fiscale',
        string="Convention fiscale applicable",
    )
    ras_taux_conventionnel = fields.Float(
        related='country_id.ras_taux_conventionnel',
        string="Taux conventionnel (%)",
    )
    ras_date_delivrance_attestation_residence = fields.Date(
        string="Date de délivrance (attestation résidence)"
    )
    ras_date_limite_validite_attestation_residence = fields.Date(
        string="Date limite de validité (attestation résidence)",
        compute='_compute_ras_date_limite_validite_residence',
        store=True
    )
    ras_attestation_residence_valide = fields.Selection(
        [('valide', 'Valide'),
         ('non_valide', 'Non valide')],
        string="Attestation de résidence fiscale",
        compute='_compute_ras_attestation_residence_valide',
        store=True
    )
    ras_document_attestation_residence = fields.Binary(
        string="Document attestation résidence"
    )
    ras_document_attestation_residence_filename = fields.Char()

    # --- Attestation de régularité fiscale (ARF) pour RAS TVA ---
    ras_date_delivrance_attestation = fields.Date(
        string="Date de délivrance (ARF)"
    )
    ras_date_limite_validite_attestation = fields.Date(
        string="Date limite de validité (ARF)",
        compute='_compute_ras_date_limite_validite',
        store=True
    )
    ras_attestation_fiscale = fields.Selection(
        [('valide', 'Valide'),
         ('non_valide', 'Non valide')],
        string="Attestation fiscale (ARF)",
        compute='_compute_ras_attestation_fiscale',
        store=True
    )
    ras_document_attestation = fields.Binary(
        string="Document attestation (ARF)"
    )
    ras_document_attestation_filename = fields.Char()

    # --- IS / IR ---
    ras_soumis_is = fields.Boolean(
        string="Soumis à l'IS", default=True
    )
    ras_regime_fiscal = fields.Selection(
        [('rnr', 'RNR'),
         ('rns', 'RNS'),
         ('cpu', 'CPU'),
         ('auto_entrepreneur', 'Auto-entrepreneur')],
        string="Régime fiscal",
        help="Détermine la RAS IR : RNR / RNS → 10 %, "
             "CPU et Auto-entrepreneur → pas de RAS IR."
    )

    @api.depends('ras_date_delivrance_attestation')
    def _compute_ras_date_limite_validite(self):
        for partner in self:
            if partner.ras_date_delivrance_attestation:
                partner.ras_date_limite_validite_attestation = (
                    partner.ras_date_delivrance_attestation + relativedelta(months=6)
                )
            else:
                partner.ras_date_limite_validite_attestation = False

    @api.depends('ras_date_limite_validite_attestation')
    def _compute_ras_attestation_fiscale(self):
        today = fields.Date.context_today(self)
        for partner in self:
            if (partner.ras_date_limite_validite_attestation
                    and partner.ras_date_limite_validite_attestation >= today):
                partner.ras_attestation_fiscale = 'valide'
            elif partner.ras_date_limite_validite_attestation:
                partner.ras_attestation_fiscale = 'non_valide'
            else:
                partner.ras_attestation_fiscale = False

    @api.depends('country_id')
    def _compute_ras_residence_fiscale(self):
        for partner in self:
            if partner.country_id and partner.country_id.code != 'MA':
                partner.ras_residence_fiscale = 'non_resident'
            else:
                partner.ras_residence_fiscale = 'resident'

    @api.depends('ras_date_delivrance_attestation_residence')
    def _compute_ras_date_limite_validite_residence(self):
        for partner in self:
            if partner.ras_date_delivrance_attestation_residence:
                partner.ras_date_limite_validite_attestation_residence = (
                    partner.ras_date_delivrance_attestation_residence
                    + relativedelta(months=12)
                )
            else:
                partner.ras_date_limite_validite_attestation_residence = False

    @api.depends('ras_date_limite_validite_attestation_residence')
    def _compute_ras_attestation_residence_valide(self):
        today = fields.Date.context_today(self)
        for partner in self:
            limite = partner.ras_date_limite_validite_attestation_residence
            if limite and limite >= today:
                partner.ras_attestation_residence_valide = 'valide'
            elif limite:
                partner.ras_attestation_residence_valide = 'non_valide'
            else:
                partner.ras_attestation_residence_valide = False

    @api.model
    def _cron_ras_maj_statut_attestations(self):
        """Tâche planifiée quotidienne : met à jour le statut des
        attestations (ARF et résidence fiscale) des fournisseurs dont la
        date limite de validité est atteinte, pour que le wizard applique
        le bon taux (100 % sans ARF valide, droit commun sans attestation
        de résidence valide)."""
        today = fields.Date.context_today(self)
        partners = self.search([
            '|',
            '&', ('ras_attestation_fiscale', '=', 'valide'),
                 ('ras_date_limite_validite_attestation', '<', today),
            '&', ('ras_attestation_residence_valide', '=', 'valide'),
                 ('ras_date_limite_validite_attestation_residence', '<', today),
        ])
        partners._compute_ras_attestation_fiscale()
        partners._compute_ras_attestation_residence_valide()
        return True
