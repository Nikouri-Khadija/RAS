from odoo import models, fields, api
from odoo.tools import float_round

# Types de RAS dont le fichier XML de déclaration est développé
TYPES_DECLARATION = [
    ('tva', "RAS TVA"),
    ('is', "RAS IS"),
]

PERIODES = {
    '1': {'1': "Janvier", '2': "Février", '3': "Mars", '4': "Avril",
          '5': "Mai", '6': "Juin", '7': "Juillet", '8': "Août",
          '9': "Septembre", '10': "Octobre", '11': "Novembre",
          '12': "Décembre"},
    '2': {'1': "1er trimestre", '2': "2e trimestre",
          '3': "3e trimestre", '4': "4e trimestre"},
}


class RasDeclaration(models.Model):
    _name = 'ras.declaration'
    _description = "Déclaration RAS générée"
    _order = 'date_generation desc, id desc'

    name = fields.Char(
        string="Référence",
        compute='_compute_name',
        store=True,
    )
    type_declaration = fields.Selection(
        TYPES_DECLARATION,
        string="Type",
        required=True,
        default='tva',
    )
    company_id = fields.Many2one(
        'res.company',
        string="Société",
        required=True,
        default=lambda self: self.env.company,
    )
    annee = fields.Char(string="Année", required=True)
    periode = fields.Char(string="Période", required=True)
    regime = fields.Selection(
        [('1', "Mensuel"), ('2', "Trimestriel")],
        string="Régime",
        required=True,
    )
    periode_libelle = fields.Char(
        string="Période déclarée",
        compute='_compute_periode_libelle',
    )

    date_generation = fields.Datetime(
        string="Date de génération",
        default=fields.Datetime.now,
        readonly=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string="Généré par",
        default=lambda self: self.env.user,
        readonly=True,
    )

    move_ids = fields.Many2many(
        'account.move',
        string="Factures déclarées",
        readonly=True,
    )
    nb_factures = fields.Integer(
        string="Factures",
        compute='_compute_nb_factures',
        store=True,
    )
    total_base = fields.Monetary(
        string="Total des bases",
        currency_field='currency_id',
        readonly=True,
    )
    total_retenu = fields.Monetary(
        string="Total retenu",
        currency_field='currency_id',
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )

    fichier = fields.Binary(
        string="Fichier ZIP",
        attachment=True,
        readonly=True,
    )
    nom_fichier = fields.Char(string="Nom du fichier", readonly=True)

    # Références du versement au Trésor (saisies à l'impression de
    # l'attestation)
    date_reversement = fields.Date(
        string="Date de reversement",
        readonly=True,
    )
    reference_quittance = fields.Char(
        string="Réf. Versement DGI",
        readonly=True,
    )

    @api.depends('type_declaration', 'annee', 'periode')
    def _compute_name(self):
        for decl in self:
            decl.name = "%s %s-%s" % (
                dict(TYPES_DECLARATION).get(decl.type_declaration, "RAS"),
                decl.annee or '',
                str(decl.periode or '').zfill(2),
            )

    @api.depends('regime', 'periode')
    def _compute_periode_libelle(self):
        for decl in self:
            decl.periode_libelle = PERIODES.get(
                decl.regime, {}
            ).get(decl.periode, decl.periode or '')

    @api.depends('move_ids')
    def _compute_nb_factures(self):
        for decl in self:
            decl.nb_factures = len(decl.move_ids)

    def action_voir_factures(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Factures déclarées",
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.move_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Attestation de retenue à la source
    # ------------------------------------------------------------------
    def action_attestation(self):
        """Ouvre la saisie des références du versement avant impression."""
        self.ensure_one()
        return {
            'name': "Attestation RAS",
            'type': 'ir.actions.act_window',
            'res_model': 'ras.attestation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_declaration_id': self.id},
        }

    @api.model
    def _mois_paiement(self, move):
        """(année, mois) du dernier paiement lettré avec la facture."""
        dates = move._get_reconciled_payments().mapped('date')
        date = max(dates) if dates else move.invoice_date
        return (date.year, date.month)

    def _attestation_lignes(self, moves):
        """Une ligne par opération (catégorie de rémunération), mois de
        paiement et taux de RAS."""
        # Montant de RAS du type déclaré : ras_amount_tva, ras_amount_is...
        champ = 'ras_amount_%s' % self.type_declaration
        groupes = {}
        for move in moves:
            mois = self._mois_paiement(move)
            for line in move.invoice_line_ids.filtered(champ):
                retenu_ligne = line[champ]
                if self.type_declaration == 'tva':
                    # RAS TVA : la retenue se calcule sur le montant de TVA
                    tva = line.tax_ids.filtered(
                        lambda t: t.amount_type == 'percent'
                        and not t.ras_is_retenue_source
                    )[:1]
                    base = line.price_subtotal * (
                        tva.amount if tva else 0.0
                    ) / 100.0
                else:
                    # RAS IS / IR : la retenue se calcule sur le montant HT
                    base = line.price_subtotal
                taux_ras = float_round(
                    retenu_ligne / base * 100.0, precision_digits=0
                ) if base else 0.0
                operation = line._ras_categorie_remuneration().name or ''
                cle = (operation, mois, taux_ras)
                total_base, retenu = groupes.get(cle, (0.0, 0.0))
                groupes[cle] = (total_base + base, retenu + retenu_ligne)
        return [
            {
                'operation': operation,
                'mois_paiement': '%02d/%d' % (mois[1], mois[0]),
                'base_calcul': base,
                'taux_ras': taux_ras,
                'montant_ras': retenu,
            }
            for (operation, mois, taux_ras), (base, retenu)
            in sorted(groupes.items(), key=lambda g: (g[0][1], g[0][0]))
        ]

    def attestation_par_fournisseur(self):
        """Une attestation par fournisseur, avec ses opérations."""
        self.ensure_one()
        return [
            {
                'partner': partner,
                'lignes': self._attestation_lignes(
                    self.move_ids.filtered(lambda m: m.partner_id == partner)
                ),
            }
            for partner in self.move_ids.partner_id.sorted('display_name')
        ]

    def _titre_type_ras(self):
        """« de la TVA », « de l'IS »... selon le type déclaré."""
        self.ensure_one()
        return {
            'tva': "de la TVA",
            'is': "de l'IS",
            'ir': "de l'IR",
        }.get(self.type_declaration, '')

    @api.model
    def _date_en_lettres(self, date):
        """27/01/2026 -> « 27 janvier 2026 »."""
        return "%d %s %d" % (
            date.day, PERIODES['1'][str(date.month)].lower(), date.year
        )
