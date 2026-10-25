from odoo import models, fields, api


class AccountTax(models.Model):
    _inherit = 'account.tax'

    ras_is_retenue_source = fields.Boolean(
        string="Retenue à la source",
        help="Coche cette case pour que cette taxe soit configurée comme "
             "une taxe de type Retenue à la Source"
    )

    ras_type = fields.Selection(
        [('tva', 'RAS TVA'),
         ('is', 'RAS IS'),
         ('ir', 'RAS IR'),
         ('export', 'RAS Non-résident')],
        string="Type de RAS"
    )

    ras_taux_legal = fields.Float(
        string="Taux de retenue légal (%)",
        aggregator=None,  # pas de somme des taux dans les listes regroupées
    )

    # Idem pour le montant natif de la taxe (un total de pourcentages n'a pas de sens)
    amount = fields.Float(aggregator=None)

    ras_taxe_tva_reference_id = fields.Many2one(
        'account.tax',
        string="Taxe TVA de référence",
        domain=[('amount_type', '=', 'percent')],
        help="Taxe TVA sur laquelle s'applique le taux de retenue légal"
    )

    @api.onchange('ras_type', 'ras_taux_legal', 'ras_taxe_tva_reference_id')
    def _onchange_ras_compute_amount(self):
        for tax in self:
            if tax.ras_type == 'tva' and tax.ras_taxe_tva_reference_id:
                tax.amount = -(
                    tax.ras_taux_legal * tax.ras_taxe_tva_reference_id.amount
                ) / 100
            elif tax.ras_type in ('is', 'ir', 'export'):
                tax.amount = -tax.ras_taux_legal

    @api.model
    def _ras_format_taux(self, taux):
        """7.0 -> '7', 7.5 -> '7,5'"""
        return ('%g' % taux).replace('.', ',')

    # Taxes RAS par défaut d'une société (mêmes valeurs que
    # data/account_tax_data.xml, qui ne couvre que la société principale).
    # (type de RAS, taux légal, taux de la TVA de référence ou None)
    RAS_TAXES_PAR_DEFAUT = [
        ('tva', 75.0, 20.0), ('tva', 75.0, 14.0), ('tva', 75.0, 10.0), ('tva', 75.0, 7.0),
        ('tva', 100.0, 20.0), ('tva', 100.0, 14.0), ('tva', 100.0, 10.0), ('tva', 100.0, 7.0),
        ('is', 5.0, None),
        ('ir', 10.0, None),
        ('export', 10.0, None),
    ]

    # Compte « État - RAS … à reverser » de chaque type de RAS
    RAS_COMPTES = {
        'tva': ('445820', "État - RAS TVA à reverser"),
        'is': ('445830', "État - RAS IS à reverser"),
        'ir': ('445840', "État - RAS IR à reverser"),
        'export': ('445850', "État - RAS Non-résident à reverser"),
    }

    RAS_LIBELLES = {
        'tva': "RAS TVA",
        'is': "RAS IS",
        'ir': "RAS IR",
        'export': "RAS Non-résident",
    }

    @api.model
    def _ras_get_tax_group(self, company):
        """Groupe de taxes « Retenue à la source » de la société (créé si absent)."""
        autre_ras = self.search(
            [('ras_is_retenue_source', '=', True),
             ('company_id', '=', company.id)],
            limit=1,
        )
        if autre_ras.tax_group_id:
            return autre_ras.tax_group_id
        TaxGroup = self.env['account.tax.group']
        return TaxGroup.search(
            [('company_id', '=', company.id),
             ('name', '=', "Retenue à la source")],
            limit=1,
        ) or TaxGroup.create({
            'name': "Retenue à la source",
            'company_id': company.id,
        })

    @api.model
    def _ras_get_or_create_tax(self, company, ras_type, taux, tva_rate=None):
        """Retourne la taxe RAS (type, taux légal[, TVA de référence]) de la
        société, en la créant si elle n'existe pas. Retourne (taxe, créée)."""
        domain = [
            ('ras_is_retenue_source', '=', True),
            ('ras_type', '=', ras_type),
            ('ras_taux_legal', '=', taux),
            ('company_id', '=', company.id),
        ]
        tva_reference = self.browse()
        if ras_type == 'tva':
            tva_reference = self.search([
                ('company_id', '=', company.id),
                ('type_tax_use', '=', 'purchase'),
                ('amount_type', '=', 'percent'),
                ('amount', '=', tva_rate),
                ('ras_is_retenue_source', '=', False),
            ], order='id', limit=1)
            if not tva_reference:
                # Pas de TVA à ce taux dans le plan comptable de la société
                return self.browse(), False
            domain.append(('ras_taxe_tva_reference_id.amount', '=', tva_rate))

        tax = self.search(domain, limit=1)
        if tax:
            return tax, False

        if ras_type == 'tva':
            name = "RAS TVA %s%% (%s%%)" % (
                self._ras_format_taux(taux), self._ras_format_taux(tva_rate))
            amount = -(taux * tva_rate) / 100.0
        else:
            name = "%s %s%%" % (self.RAS_LIBELLES[ras_type], self._ras_format_taux(taux))
            amount = -taux

        tax = self.create({
            'name': name,
            'company_id': company.id,
            'country_id': company.account_fiscal_country_id.id,
            'type_tax_use': 'purchase',
            'amount_type': 'percent',
            'amount': amount,
            'tax_group_id': self._ras_get_tax_group(company).id,
            'ras_is_retenue_source': True,
            'ras_type': ras_type,
            'ras_taux_legal': taux,
            'ras_taxe_tva_reference_id': tva_reference.id or False,
        })
        tax._ras_affecter_compte()
        return tax, True

    @api.model
    def _ras_get_or_create_export_tax(self, company, taux):
        """Taxe RAS Non-résident au taux donné (créée si absente)."""
        return self._ras_get_or_create_tax(company, 'export', taux)

    @api.model
    def _ras_create_default_taxes(self, company):
        """Crée pour la société toutes les taxes RAS par défaut manquantes
        (idem fichier data) + les taxes Non-résident des pays ayant une
        convention fiscale. Utilisé pour les sociétés autres que la
        société principale (multi-sociétés)."""
        created = self.browse()
        for ras_type, taux, tva_rate in self.RAS_TAXES_PAR_DEFAUT:
            tax, is_new = self._ras_get_or_create_tax(company, ras_type, taux, tva_rate)
            if is_new:
                created |= tax
        pays = self.env['res.country'].sudo().search([
            ('ras_convention_fiscale', '=', True),
            ('ras_taux_conventionnel', '>', 0),
        ])
        for taux in set(pays.mapped('ras_taux_conventionnel')):
            tax, is_new = self._ras_get_or_create_export_tax(company, taux)
            if is_new:
                created |= tax
        self.search([
            ('ras_is_retenue_source', '=', True),
            ('company_id', '=', company.id),
        ])._ras_affecter_compte()
        return created

    # ------------------------------------------------------------------
    # Comptes « État - RAS … à reverser »
    # ------------------------------------------------------------------
    @api.model
    def _ras_get_or_create_compte(self, company, ras_type):
        """Compte de la RAS du type donné pour la société (créé si absent)."""
        code, nom = self.RAS_COMPTES[ras_type]
        Account = self.env['account.account'].sudo().with_company(company)
        compte = Account.search([
            *Account._check_company_domain(company),
            ('code', '=', code),
        ], limit=1)
        if not compte:
            compte = Account.create({
                'code': code,
                'name': nom,
                'account_type': 'liability_current',
                'company_ids': [(6, 0, company.ids)],
            })
        return compte

    def _ras_affecter_compte(self):
        """Renseigne le compte RAS sur les lignes « Taxe » (factures et
        avoirs) des taxes RAS qui n'en ont pas encore."""
        for tax in self.filtered(lambda t: t.ras_is_retenue_source and t.ras_type in self.RAS_COMPTES):
            lignes = (tax.invoice_repartition_line_ids | tax.refund_repartition_line_ids).filtered(
                lambda r: r.repartition_type == 'tax' and not r.account_id
            )
            if lignes:
                lignes.write({'account_id': self._ras_get_or_create_compte(tax.company_id, tax.ras_type).id})

    @api.model
    def _ras_installer_comptes(self):
        """À l'installation / mise à jour : comptes RAS pour les sociétés
        ayant un plan comptable, affectés à leurs taxes RAS."""
        for company in self.env['res.company'].sudo().search([('chart_template', '!=', False)]):
            self.sudo().search([
                ('ras_is_retenue_source', '=', True),
                ('company_id', '=', company.id),
            ])._ras_affecter_compte()

    def _ras_compte(self):
        """Compte de la taxe RAS (ligne de répartition « Taxe » des
        factures), sur lequel la retenue est comptabilisée au paiement."""
        self.ensure_one()
        return self.invoice_repartition_line_ids.filtered(
            lambda r: r.repartition_type == 'tax'
        )[:1].account_id
