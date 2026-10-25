from odoo import models, fields, api


class AccountMoveRasWizard(models.TransientModel):
    _name = 'account.move.ras.wizard'
    _description = "Assistant de calcul de la RAS"

    move_id = fields.Many2one(
        'account.move',
        string="Facture",
        required=True,
        readonly=True,
    )

    # Fenêtre « Payer » depuis laquelle l'assistant a été ouvert
    register_id = fields.Many2one(
        'account.payment.register',
        string="Paiement",
        readonly=True,
    )

    partner_id = fields.Many2one(
        related='move_id.partner_id',
        string="Fournisseur",
        readonly=True,
    )

    currency_id = fields.Many2one(
        related='move_id.currency_id',
        readonly=True,
    )

    amount_total = fields.Monetary(
        string="Total de la facture",
        related='move_id.amount_total',
        currency_field='currency_id',
        readonly=True,
    )

    warning_message = fields.Char(
        string="Avertissement",
        readonly=True,
    )

    ras_non_applicable = fields.Boolean(
        string="RAS non applicable",
        readonly=True,
    )

    line_ids = fields.One2many(
        'account.move.ras.wizard.line',
        'wizard_id',
        string="Lignes soumises à la RAS",
    )

    ras_tva_id = fields.Many2one(
        'account.tax',
        string="Taux RAS TVA Global",
        domain=[
            ('ras_is_retenue_source', '=', True),
            ('ras_type', '=', 'tva'),
        ],
    )

    ras_is_id = fields.Many2one(
        'account.tax',
        string="Taux RAS IS",
        domain=[
            ('ras_is_retenue_source', '=', True),
            ('ras_type', '=', 'is'),
        ],
    )

    ras_ir_id = fields.Many2one(
        'account.tax',
        string="Taux RAS IR",
        domain=[
            ('ras_is_retenue_source', '=', True),
            ('ras_type', '=', 'ir'),
        ],
    )

    ras_export_id = fields.Many2one(
        'account.tax',
        string="Taux RAS Non-résident",
        domain=[
            ('ras_is_retenue_source', '=', True),
            ('ras_type', '=', 'export'),
        ],
    )

    partner_non_resident = fields.Boolean(
        string="Fournisseur non-résident",
        compute='_compute_partner_non_resident',
    )

    montant_ras_tva = fields.Monetary(
        string="Montant RAS TVA",
        compute='_compute_montant_ras',
        currency_field='currency_id',
        readonly=True,
    )

    montant_ras_is = fields.Monetary(
        string="Montant RAS IS",
        compute='_compute_montant_ras',
        currency_field='currency_id',
        readonly=True,
    )

    montant_ras_ir = fields.Monetary(
        string="Montant RAS IR",
        compute='_compute_montant_ras',
        currency_field='currency_id',
        readonly=True,
    )

    montant_ras_export = fields.Monetary(
        string="Montant RAS Non-résident",
        compute='_compute_montant_ras',
        currency_field='currency_id',
        readonly=True,
    )

    montant_ras = fields.Monetary(
        string="Total RAS",
        compute='_compute_montant_ras',
        currency_field='currency_id',
        readonly=True,
    )

    @api.depends('move_id.partner_id.ras_residence_fiscale')
    def _compute_partner_non_resident(self):
        for wizard in self:
            wizard.partner_non_resident = (
                wizard.move_id.partner_id.ras_residence_fiscale
                == 'non_resident'
            )

    @api.model
    def _get_ras_tva_line_data(self, move, line):

        partner = move.partner_id
        product = line.product_id

        messages = []
        applicable = True
        preselected_tax = self.env['account.tax']

        if (
            not product
            or product.ras_categorie != 'soumis'
            or not product.ras_soumis_tva
        ):
            applicable = False
            messages.append("Produit non soumis à la RAS TVA.")

        tva_reference_tax = line.tax_ids.filtered(
            lambda t: (
                t.amount_type == 'percent'
                and not t.ras_is_retenue_source
            )
        )[:1]

        # Sans TVA facturée sur la ligne, pas de RAS TVA
        if applicable and not tva_reference_tax:
            applicable = False
            messages.append("Pas de TVA sur la ligne : pas de RAS TVA.")

        # Seuil TTC de la facture (en devise société), paramétré sur la société
        seuil = move.company_id.ras_seuil_tva
        if applicable and abs(move.amount_total_signed) < seuil:
            applicable = False
            messages.append(
                "Facture de moins de %s TTC : pas de RAS TVA."
                % move.company_id.currency_id.format(seuil)
            )

        if applicable:

            if partner.ras_attestation_fiscale == 'valide':
                taux_legal = 75.0
            else:
                taux_legal = 100.0

            # Recherche par TAUX de la TVA de référence (et non par
            # identifiant) : une seule RAS TVA 75%/100% (20%) couvre
            # toutes les variantes de TVA 20% du plan comptable.
            domain = [
                ('ras_is_retenue_source', '=', True),
                ('ras_type', '=', 'tva'),
                ('ras_taux_legal', '=', taux_legal),
                ('company_id', '=', move.company_id.id),
                (
                    'ras_taxe_tva_reference_id.amount',
                    '=',
                    tva_reference_tax.amount
                ),
            ]

            preselected_tax = self.env['account.tax'].search(
                domain,
                limit=1
            )

            if not preselected_tax:
                messages.append(
                    "Aucune taxe RAS TVA à %s%% configurée pour "
                    "la TVA de référence %s%%."
                    % (
                        taux_legal,
                        tva_reference_tax.amount
                    )
                )

        vals = {
            'invoice_line_id': line.id,
            'product_id': product.id if product else False,
            'base_amount': line.price_subtotal,
            'tva_reference_id': (
                tva_reference_tax.id
                if tva_reference_tax
                else False
            ),
            'tax_ids': [
                (6, 0, preselected_tax.ids)
            ],
            'ras_tva_applicable': applicable,
            'ras_is_applicable': False,
            'ras_is': bool(
                product
                and product.ras_categorie == 'soumis'
                and product.ras_soumis_is
            ),
            'ras_ir_applicable': False,
            'ras_export_applicable': False,
            'ras_export_taux': 0.0,
        }

        return (
            vals,
            applicable,
            (
                "%s : %s"
                % (
                    product.display_name,
                    "; ".join(messages)
                )
                if messages
                else False
            ),
        )

    @api.model
    def _get_ras_is_line_data(self, move, line):

        partner = move.partner_id
        company = move.company_id
        product = line.product_id

        messages = []
        applicable = True

        if (
            not product
            or product.ras_categorie != 'soumis'
            or not product.ras_soumis_is
        ):
            applicable = False
            messages.append(
                "Produit non soumis à la RAS IS."
            )

        if applicable:

            if partner.ras_type_fournisseur == 'personne_physique':
                applicable = False
                messages.append(
                    "Fournisseur personne physique : pas de RAS IS."
                )

            elif not partner.ras_soumis_is:
                applicable = False
                messages.append(
                    "Fournisseur non soumis à l'IS."
                )

        if applicable and not company.ras_oblige_retenue_is:
            applicable = False
            messages.append(
                "La société n'est pas tenue de pratiquer "
                "la retenue à la source IS."
            )

        return (
            applicable,
            (
                "%s : %s"
                % (
                    product.display_name,
                    "; ".join(messages)
                )
                if messages
                else False
            ),
        )

    # Taux de RAS IR selon le régime fiscal du fournisseur (personne physique)
    RAS_IR_TAUX_PAR_REGIME = {
        'rnr': 10.0,
        'rns': 10.0,
    }

    @api.model
    def _get_ras_ir_taux(self, partner):
        return self.RAS_IR_TAUX_PAR_REGIME.get(partner.ras_regime_fiscal, 10.0)

    @api.model
    def _get_ras_ir_line_data(self, move, line):

        partner = move.partner_id
        company = move.company_id
        product = line.product_id

        messages = []
        applicable = True

        if not product or product.ras_categorie != 'soumis':
            applicable = False
            messages.append(
                "Produit non soumis à la RAS IR."
            )

        if applicable:

            if partner.ras_type_fournisseur == 'societe':
                applicable = False
                messages.append(
                    "Fournisseur personne morale : pas de RAS IR."
                )

            elif partner.ras_regime_fiscal in self.RAS_IR_TAUX_PAR_REGIME:
                # RNR / RNS (10 %)
                pass

            elif partner.ras_regime_fiscal in (
                'auto_entrepreneur',
                'cpu'
            ):
                applicable = False
                messages.append(
                    "Fournisseur auto-entrepreneur ou CPU : pas de RAS IR."
                )

            else:
                applicable = False
                messages.append(
                    "Régime fiscal du fournisseur non défini "
                    "ou non concerné par la RAS IR."
                )

        if applicable and not company.ras_oblige_retenue_ir:
            applicable = False
            messages.append(
                "La société n'est pas tenue de pratiquer "
                "la retenue à la source IR."
            )

        return (
            applicable,
            (
                "%s : %s"
                % (
                    product.display_name,
                    "; ".join(messages)
                )
                if messages
                else False
            ),
        )

    RAS_EXPORT_TAUX_DROIT_COMMUN = 10.0

    @api.model
    def _get_ras_export_line_data(self, move, line):
        """RAS Non-résident (produits bruts versés aux non-résidents).

        Retourne (applicable, message) pour une ligne.
        """
        partner = move.partner_id
        product = line.product_id

        messages = []
        applicable = True

        if not product or product.ras_categorie != 'soumis':
            applicable = False
            messages.append(
                "Produit non soumis à la RAS Non-résident."
            )

        if applicable and partner.ras_residence_fiscale != 'non_resident':
            applicable = False
            messages.append(
                "Fournisseur résident : pas de RAS Non-résident."
            )

        return (
            applicable,
            (
                "%s : %s"
                % (
                    product.display_name,
                    "; ".join(messages)
                )
                if messages
                else False
            ),
        )

    @api.model
    def _get_ras_export_tax(self, move):
        """Taxe RAS Non-résident à présélectionner pour la facture.

        Taux :
          - convention fiscale sur le pays + attestation de résidence
            valide -> taux conventionnel du pays
          - sinon -> taux de droit commun (10 %)
        Retourne (taxe, messages).
        """
        partner = move.partner_id
        Tax = self.env['account.tax']
        messages = []
        taux_defaut = self.RAS_EXPORT_TAUX_DROIT_COMMUN
        taux = taux_defaut

        if (
            partner.ras_convention_fiscale
            and partner.ras_attestation_residence_valide == 'valide'
        ):
            if partner.ras_taux_conventionnel:
                taux = partner.ras_taux_conventionnel
            else:
                messages.append(
                    "Convention fiscale sans taux conventionnel "
                    "renseigné sur le pays : taux de droit commun "
                    "(%s%%) appliqué." % taux_defaut
                )
        elif partner.ras_convention_fiscale:
            messages.append(
                "Attestation de résidence fiscale non valide : "
                "taux de droit commun (%s%%) appliqué." % taux_defaut
            )

        tax, created = Tax._ras_get_or_create_export_tax(
            move.company_id, taux
        )
        if created:
            messages.append(
                "Taxe « %s » créée automatiquement." % tax.name
            )

        return tax, messages

    @api.model
    def default_get(self, fields_list):

        res = super().default_get(fields_list)

        move_id = (
            res.get('move_id')
            or self.env.context.get('active_id')
        )

        res['ras_non_applicable'] = False
        res['warning_message'] = False
        res['line_ids'] = []

        if not move_id:
            return res

        move = self.env['account.move'].browse(move_id)

        res['move_id'] = move_id

        toutes_les_lignes = move.invoice_line_ids.filtered(
            lambda l: l.product_id
        )

        if not toutes_les_lignes:

            res['ras_non_applicable'] = True
            res['warning_message'] = (
                "Cette facture ne contient aucune ligne "
                "avec un article défini."
            )

            return res

        lines_vals = []

        au_moins_une_applicable = False
        au_moins_une_applicable_is = False
        au_moins_une_applicable_ir = False
        au_moins_une_applicable_export = False

        control_messages = []
        preselected_tax_ids = set()

        non_resident = (
            move.partner_id.ras_residence_fiscale == 'non_resident'
        )

        # ------------------------------------------------------------
        # Fournisseur NON-RÉSIDENT : RAS Non-résident uniquement
        # (RAS TVA / IS / IR écartées)
        # ------------------------------------------------------------
        if non_resident:

            for line in toutes_les_lignes:

                vals, _applicable, _msg = (
                    self._get_ras_tva_line_data(
                        move,
                        line
                    )
                )

                # Pas de RAS TVA / IS / IR sur un non-résident
                vals['tax_ids'] = [(6, 0, [])]
                vals['ras_tva_applicable'] = False
                vals['ras_is_applicable'] = False
                vals['ras_is'] = False
                vals['ras_ir_applicable'] = False

                applicable_export, msg_export = (
                    self._get_ras_export_line_data(
                        move,
                        line
                    )
                )

                if applicable_export:
                    au_moins_une_applicable_export = True

                if msg_export:
                    control_messages.append(msg_export)

                vals['ras_export_applicable'] = applicable_export

                lines_vals.append(
                    (0, 0, vals)
                )

            if au_moins_une_applicable_export:
                export_tax, msgs = self._get_ras_export_tax(move)
                control_messages.extend(msgs)
                if export_tax:
                    res['ras_export_id'] = export_tax.id
                    # Taux pré-rempli sur chaque ligne applicable
                    # (modifiable ligne par ligne selon la nature du produit)
                    for _cmd, _id, vals in lines_vals:
                        if vals.get('ras_export_applicable'):
                            vals['ras_export_taux'] = export_tax.ras_taux_legal

            res['line_ids'] = lines_vals

            info = (
                "Fournisseur non-résident : RAS Non-résident appliquée, "
                "RAS TVA / IS / IR écartées."
            )

            res['warning_message'] = (
                " | ".join([info] + control_messages)
            )

            return res

        # ------------------------------------------------------------
        # Fournisseur RÉSIDENT : RAS TVA / IS / IR
        # ------------------------------------------------------------
        for line in toutes_les_lignes:

            vals, applicable, msg = (
                self._get_ras_tva_line_data(
                    move,
                    line
                )
            )

            if applicable:
                au_moins_une_applicable = True

            if msg:
                control_messages.append(msg)

            line_tax_ids = (
                vals['tax_ids'][0][2]
                if vals.get('tax_ids')
                else []
            )

            preselected_tax_ids.update(line_tax_ids)

            applicable_is, msg_is = (
                self._get_ras_is_line_data(
                    move,
                    line
                )
            )

            if applicable_is:
                au_moins_une_applicable_is = True

            if msg_is:
                control_messages.append(msg_is)

            vals['ras_is_applicable'] = applicable_is

            applicable_ir, msg_ir = (
                self._get_ras_ir_line_data(
                    move,
                    line
                )
            )

            if applicable_ir:
                au_moins_une_applicable_ir = True

            if msg_ir:
                control_messages.append(msg_ir)

            vals['ras_ir_applicable'] = applicable_ir

            lines_vals.append(
                (0, 0, vals)
            )

        res['line_ids'] = lines_vals

        if len(preselected_tax_ids) == 1:

            res['ras_tva_id'] = (
                next(iter(preselected_tax_ids))
            )

        if au_moins_une_applicable_is:

            ras_is_tax = self.env['account.tax'].search(
                [
                    ('ras_is_retenue_source', '=', True),
                    ('ras_type', '=', 'is'),
                    ('ras_taux_legal', '=', 5.0),
                ],
                limit=1,
            )

            if ras_is_tax:
                res['ras_is_id'] = ras_is_tax.id

        if au_moins_une_applicable_ir:

            taux_ir = self._get_ras_ir_taux(move.partner_id)

            ras_ir_tax = self.env['account.tax'].search(
                [
                    ('ras_is_retenue_source', '=', True),
                    ('ras_type', '=', 'ir'),
                    ('ras_taux_legal', '=', taux_ir),
                    ('company_id', '=', move.company_id.id),
                ],
                limit=1,
            )

            if ras_ir_tax:
                res['ras_ir_id'] = ras_ir_tax.id
            else:
                control_messages.append(
                    "Aucune taxe RAS IR à %s%% configurée." % taux_ir
                )

        if control_messages:

            res['warning_message'] = (
                " | ".join(control_messages)
            )

        elif (
            au_moins_une_applicable
            or au_moins_une_applicable_is
            or au_moins_une_applicable_ir
        ):

            res['warning_message'] = (
                "Les taux de RAS ont été présélectionnés automatiquement."
            )

        return res

    @api.onchange('ras_tva_id')
    def _onchange_ras_tva_id(self):

        for wizard in self:

            if wizard.ras_tva_id:

                # La taxe globale remplace la RAS TVA des seules lignes
                # soumises (un ajout la ferait retenir deux fois)
                for line in wizard.line_ids.filtered('ras_tva_applicable'):

                    line.tax_ids = [
                        (6, 0, [wizard.ras_tva_id.id])
                    ]

            wizard._log_totals()

    @api.onchange('ras_is_id')
    def _onchange_ras_is_id(self):

        for wizard in self:

            if not wizard.ras_is_id:
                wizard._log_totals()
                continue

            if not any(
                wizard.line_ids.mapped(
                    'ras_is_applicable'
                )
            ):

                message = (
                    "Le taux RAS IS sélectionné ne remplit pas "
                    "les conditions d'application habituelles "
                    "(il sera néanmoins appliqué manuellement)."
                )

                if (
                    not wizard.warning_message
                    or message not in wizard.warning_message
                ):

                    wizard.warning_message = (
                        "%s | %s"
                        % (
                            wizard.warning_message,
                            message
                        )
                        if wizard.warning_message
                        else message
                    )

            wizard._log_totals()

    @api.onchange('ras_ir_id')
    def _onchange_ras_ir_id(self):

        for wizard in self:

            if not wizard.ras_ir_id:
                wizard._log_totals()
                continue

            if not any(
                wizard.line_ids.mapped(
                    'ras_ir_applicable'
                )
            ):

                message = (
                    "Le taux RAS IR sélectionné ne remplit pas "
                    "les conditions d'application habituelles "
                    "(il sera néanmoins appliqué manuellement)."
                )

                if (
                    not wizard.warning_message
                    or message not in wizard.warning_message
                ):

                    wizard.warning_message = (
                        "%s | %s"
                        % (
                            wizard.warning_message,
                            message
                        )
                        if wizard.warning_message
                        else message
                    )

            wizard._log_totals()

    @api.onchange('ras_export_id')
    def _onchange_ras_export_id(self):

        for wizard in self:

            if not wizard.ras_export_id:
                wizard._log_totals()
                continue

            lignes_applicables = wizard.line_ids.filtered(
                'ras_export_applicable'
            )

            # Le taux global est reporté sur les lignes concernées
            # (toutes les lignes si application manuelle)
            taux = (
                wizard.ras_export_id.ras_taux_legal
                or abs(wizard.ras_export_id.amount)
            )
            for line in (lignes_applicables or wizard.line_ids):
                line.ras_export_taux = taux

            if not lignes_applicables:

                message = (
                    "Le taux RAS Non-résident sélectionné ne remplit pas "
                    "les conditions d'application habituelles "
                    "(il sera néanmoins appliqué manuellement)."
                )

                if (
                    not wizard.warning_message
                    or message not in wizard.warning_message
                ):

                    wizard.warning_message = (
                        "%s | %s"
                        % (
                            wizard.warning_message,
                            message
                        )
                        if wizard.warning_message
                        else message
                    )

            wizard._log_totals()

    @api.depends(
        'line_ids.montant_ras_tva',
        'line_ids.montant_ras_is',
        'line_ids.montant_ras_ir',
        'line_ids.montant_ras_export',
        'line_ids.montant_ras',
    )
    def _compute_montant_ras(self):

        for wizard in self:

            wizard.montant_ras_tva = sum(
                wizard.line_ids.mapped(
                    'montant_ras_tva'
                )
            )

            wizard.montant_ras_is = sum(
                wizard.line_ids.mapped(
                    'montant_ras_is'
                )
            )

            wizard.montant_ras_ir = sum(
                wizard.line_ids.mapped(
                    'montant_ras_ir'
                )
            )

            wizard.montant_ras_export = sum(
                wizard.line_ids.mapped(
                    'montant_ras_export'
                )
            )

            wizard.montant_ras = (
                wizard.montant_ras_tva
                + wizard.montant_ras_is
                + wizard.montant_ras_ir
                + wizard.montant_ras_export
            )

    def _log_totals(self):

        for wizard in self:
            wizard._compute_montant_ras()

    def action_enregistrer(self):

        self.ensure_one()

        self.line_ids._compute_montant_ras()
        self._compute_montant_ras()

        for line in self.line_ids:

            if not line.invoice_line_id:
                continue

            line.invoice_line_id.write({
                'ras_amount_tva': line.montant_ras_tva,
                'ras_amount_is': line.montant_ras_is,
                'ras_amount_ir': line.montant_ras_ir,
                'ras_amount_export': line.montant_ras_export,
                'ras_amount': line.montant_ras,
            })

        if self.move_id:

            self.move_id.invalidate_recordset([
                'ras_amount_tva',
                'ras_amount_is',
                'ras_amount_ir',
                'ras_amount_export',
                'ras_amount',
            ])

            self.move_id._compute_ras_amount()

        if not self.register_id:
            return {
                'type': 'ir.actions.act_window_close'
            }

        self.register_id._ras_appliquer(self._ras_montants_par_taxe())
        return self.register_id._ras_action_ouvrir()

    def action_retour_paiement(self):
        """Retour à la fenêtre « Payer » sans modifier la RAS."""
        self.ensure_one()
        if not self.register_id:
            return {
                'type': 'ir.actions.act_window_close'
            }
        return self.register_id._ras_action_ouvrir()

    def _ras_montants_par_taxe(self):
        """Montants RAS regroupés par taxe RAS : {taxe: montant}.

        Mêmes calculs que les lignes de l'assistant ; la taxe porte le
        compte sur lequel la retenue est comptabilisée au paiement.
        """
        self.ensure_one()
        montants = {}

        def ajouter(tax, montant):
            if tax and montant:
                montants[tax] = montants.get(tax, 0.0) + montant

        for line in self.line_ids:

            taux_tva = (
                line.tva_reference_id.amount
                if line.tva_reference_id
                else 0.0
            )
            montant_tva = line.base_amount * (taux_tva / 100.0)

            for tax in line.tax_ids:
                taux_legal = tax.ras_taux_legal or abs(tax.amount)
                ajouter(tax, abs(montant_tva * (taux_legal / 100.0)))

            ajouter(self.ras_is_id, line.montant_ras_is)
            ajouter(self.ras_ir_id, line.montant_ras_ir)

            if line.montant_ras_export:
                # Taux modifiable par ligne : taxe Non-résident de ce taux
                tax_export, _cree = (
                    self.env['account.tax']._ras_get_or_create_export_tax(
                        self.move_id.company_id, line.ras_export_taux
                    )
                )
                ajouter(tax_export, line.montant_ras_export)

        return montants


class AccountMoveRasWizardLine(models.TransientModel):
    _name = 'account.move.ras.wizard.line'
    _description = "Ligne RAS du wizard"

    wizard_id = fields.Many2one(
        'account.move.ras.wizard',
        ondelete='cascade',
    )

    currency_id = fields.Many2one(
        related='wizard_id.currency_id',
        readonly=True,
    )

    invoice_line_id = fields.Many2one(
        'account.move.line',
        string="Ligne de facture",
        readonly=True,
    )

    product_id = fields.Many2one(
        'product.product',
        string="Article",
        readonly=True,
    )

    base_amount = fields.Monetary(
        string="Base HT",
        currency_field='currency_id',
        readonly=True,
    )

    tva_reference_id = fields.Many2one(
        'account.tax',
        string="TVA de la ligne",
        readonly=True,
    )

    tax_ids = fields.Many2many(
        'account.tax',
        string="Taxe RAS TVA à appliquer",
        domain=[
            ('ras_is_retenue_source', '=', True),
            ('ras_type', '=', 'tva'),
        ],
    )

    ras_tva_applicable = fields.Boolean(
        string="RAS TVA applicable",
        readonly=True,
    )

    ras_is_applicable = fields.Boolean(
        string="RAS IS applicable",
        readonly=True,
    )

    ras_is = fields.Boolean(
        string="RAS IS",
        help="Applique la RAS IS sur la ligne. Pré-coché selon la catégorie "
             "de produit (case RAS IS), modifiable.",
    )

    ras_ir_applicable = fields.Boolean(
        string="RAS IR applicable",
        readonly=True,
    )

    ras_export_applicable = fields.Boolean(
        string="RAS Non-résident applicable",
        readonly=True,
    )

    ras_export_taux = fields.Float(
        string="Taux (%)",
        digits=(5, 2),
        help="Pré-rempli avec le taux de la taxe RAS Non-résident choisie. "
             "Modifiable si la nature du produit relève d'un autre taux "
             "prévu par la convention.",
    )

    montant_ras_export = fields.Monetary(
        string="Montant RAS Non-résident",
        compute='_compute_montant_ras',
        currency_field='currency_id',
        readonly=True,
    )

    montant_ras_tva = fields.Monetary(
        string="Montant RAS TVA",
        compute='_compute_montant_ras',
        currency_field='currency_id',
        readonly=True,
    )

    montant_ras_is = fields.Monetary(
        string="Montant RAS IS",
        compute='_compute_montant_ras',
        currency_field='currency_id',
        readonly=True,
    )

    montant_ras_ir = fields.Monetary(
        string="Montant RAS IR",
        compute='_compute_montant_ras',
        currency_field='currency_id',
        readonly=True,
    )

    montant_ras = fields.Monetary(
        string="Montant RAS",
        compute='_compute_montant_ras',
        currency_field='currency_id',
        readonly=True,
    )

    @api.depends(
        'base_amount',
        'tva_reference_id',
        'tax_ids',
        'ras_is_applicable',
        'ras_is',
        'ras_ir_applicable',
        'ras_export_taux',
        'wizard_id.ras_is_id',
        'wizard_id.ras_ir_id',
    )
    def _compute_montant_ras(self):

        for line in self:

            ras_tva = 0.0
            ras_is = 0.0
            ras_ir = 0.0
            ras_export = 0.0

            taux_tva = (
                line.tva_reference_id.amount
                if line.tva_reference_id
                else 0.0
            )

            montant_tva = (
                line.base_amount
                * (taux_tva / 100.0)
            )

            for tax in line.tax_ids:

                taux_legal = (
                    tax.ras_taux_legal
                    if tax.ras_taux_legal
                    else abs(tax.amount)
                )

                montant = abs(
                    montant_tva
                    * (taux_legal / 100.0)
                )

                ras_tva += montant

            if line.wizard_id.ras_is_id and line.ras_is:

                tax_is = line.wizard_id.ras_is_id

                taux_is = (
                    tax_is.ras_taux_legal
                    if tax_is.ras_taux_legal
                    else abs(tax_is.amount)
                )

                ras_is = abs(
                    line.base_amount
                    * (taux_is / 100.0)
                )

            if line.wizard_id.ras_ir_id:

                tax_ir = line.wizard_id.ras_ir_id

                taux_ir = (
                    tax_ir.ras_taux_legal
                    if tax_ir.ras_taux_legal
                    else abs(tax_ir.amount)
                )

                ras_ir = abs(
                    line.base_amount
                    * (taux_ir / 100.0)
                )

            # 4. Calcul RAS Non-résident (sur Base HT, taux de la ligne)
            if line.ras_export_taux:

                ras_export = abs(
                    line.base_amount
                    * (line.ras_export_taux / 100.0)
                )

            line.montant_ras_tva = ras_tva
            line.montant_ras_is = ras_is
            line.montant_ras_ir = ras_ir
            line.montant_ras_export = ras_export

            line.montant_ras = (
                ras_tva
                + ras_is
                + ras_ir
                + ras_export
            )
