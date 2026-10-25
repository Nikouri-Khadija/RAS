import base64
import io
import zipfile

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import float_round

from ..models.ras_declaration import TYPES_DECLARATION
from .ras_declaration_xml import construire_xml_tva, construire_xml_is

MOIS = [
    ('1', "1 - Janvier"), ('2', "2 - Février"), ('3', "3 - Mars"),
    ('4', "4 - Avril"), ('5', "5 - Mai"), ('6', "6 - Juin"),
    ('7', "7 - Juillet"), ('8', "8 - Août"), ('9', "9 - Septembre"),
    ('10', "10 - Octobre"), ('11', "11 - Novembre"), ('12', "12 - Décembre"),
]

TRIMESTRES = [
    ('1', "1 - 1er trimestre (janvier - mars)"),
    ('2', "2 - 2e trimestre (avril - juin)"),
    ('3', "3 - 3e trimestre (juillet - septembre)"),
    ('4', "4 - 4e trimestre (octobre - décembre)"),
]


class RasDeclarationWizard(models.TransientModel):
    _name = 'ras.declaration.wizard'
    _description = "Assistant de déclaration RAS"

    # ------------------------------------------------------------------
    # Champs
    # ------------------------------------------------------------------
    type_declaration = fields.Selection(
        TYPES_DECLARATION,
        string="Type de déclaration",
        default='tva',
        required=True,
    )

    annee = fields.Char(
        string="Année",
        required=True,
    )

    regime = fields.Selection(
        [('1', "1 - Mensuel"),
         ('2', "2 - Trimestriel")],
        string="Régime",
        default='1',
        required=True,
    )

    periode_mois = fields.Selection(
        MOIS,
        string="Période",
        help="Mois de la déclaration ; le chiffre est celui repris dans le "
             "fichier XML.",
    )

    periode_trimestre = fields.Selection(
        TRIMESTRES,
        string="Période",
        help="Trimestre de la déclaration ; le chiffre est celui repris dans "
             "le fichier XML.",
    )

    periode = fields.Char(
        string="Période déclarée",
        compute='_compute_periode',
        help="Valeur reprise dans le fichier XML.",
    )

    move_ids = fields.Many2many(
        'account.move',
        string="Factures à déclarer",
        readonly=True,
    )

    nb_factures = fields.Integer(
        string="Factures retenues",
        compute='_compute_totaux',
    )
    total_base = fields.Monetary(
        string="Total des bases",
        compute='_compute_totaux',
        currency_field='currency_id',
    )
    total_retenu = fields.Monetary(
        string="Total retenu",
        compute='_compute_totaux',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_totaux',
    )

    message = fields.Text(
        string="Informations",
        compute='_compute_totaux',
    )

    deja_declare = fields.Boolean(
        string="Factures déjà déclarées",
        compute='_compute_deja_declare',
    )
    message_deja_declare = fields.Text(
        string="Détail des factures déjà déclarées",
        compute='_compute_deja_declare',
    )

    fichier = fields.Binary(string="Fichier", readonly=True, attachment=False)
    nom_fichier = fields.Char(string="Nom du fichier", readonly=True)
    declaration_id = fields.Many2one(
        'ras.declaration',
        string="Déclaration",
        readonly=True,
    )
    etat = fields.Selection(
        [('choix', "Choix"),
         ('genere', "Généré")],
        default='choix',
    )

    @api.onchange('type_declaration')
    def _onchange_type_declaration(self):
        # La RAS IS se déclare au mois (référence année + mois)
        if self.type_declaration == 'is':
            self.regime = '1'

    @api.depends('regime', 'periode_mois', 'periode_trimestre')
    def _compute_periode(self):
        for wizard in self:
            wizard.periode = (
                wizard.periode_mois if wizard.regime == '1'
                else wizard.periode_trimestre
            )

    # ------------------------------------------------------------------
    # Valeurs par défaut : factures sélectionnées, année et période
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        moves = self.env['account.move'].browse(
            self.env.context.get('active_ids', [])
        ).filtered(lambda m: m.move_type in ('in_invoice', 'in_refund'))

        res['move_ids'] = [(6, 0, moves.ids)]

        dates = [
            d for d in (self._date_paiement(m) for m in moves) if d
        ] or moves.filtered('invoice_date').mapped('invoice_date')
        if dates:
            date_ref = max(dates)
        else:
            date_ref = fields.Date.context_today(self)
        res['annee'] = str(date_ref.year)
        res['periode_mois'] = str(date_ref.month)
        res['periode_trimestre'] = str((date_ref.month - 1) // 3 + 1)
        return res

    # ------------------------------------------------------------------
    # Factures effectivement déclarées
    # ------------------------------------------------------------------
    def _champ_ras(self):
        """Montant de RAS du type déclaré : ras_amount_tva, ras_amount_is…"""
        return 'ras_amount_%s' % self.type_declaration

    def _libelle_type(self):
        return dict(TYPES_DECLARATION).get(self.type_declaration, "RAS")

    def _factures_a_declarer(self):
        """Factures comptabilisées, payées, dont le paiement a réellement
        retenu la RAS du type déclaré.

        La déclaration ne concerne que les factures payées : la retenue est
        due au moment du paiement. Les factures non payées restent en
        instance et seront déclarées sur la période de leur règlement.
        """
        self.ensure_one()
        champ = self._champ_ras()
        return self.move_ids.filtered(
            lambda m: m.state == 'posted'
            and m[champ]
            and m.payment_state in ('paid', 'in_payment')
            and self._date_paiement(m)
            and m._ras_comptabilisee(self.type_declaration)
        )

    @api.depends('move_ids', 'type_declaration')
    def _compute_totaux(self):
        for wizard in self:
            factures = wizard._factures_a_declarer()
            champ = wizard._champ_ras()
            wizard.nb_factures = len(factures)
            wizard.total_base = sum(
                factures.mapped(
                    lambda m: sum(
                        l.price_subtotal
                        for l in m.invoice_line_ids
                        if l[champ]
                    )
                )
            )
            wizard.total_retenu = sum(factures.mapped(champ))
            wizard.currency_id = (
                factures[:1].currency_id or wizard.env.company.currency_id
            )

            ignorees = wizard.move_ids - factures
            wizard.message = (
                "%s facture(s) écartée(s) : seules les factures payées avec "
                "%s retenue sont déclarées (%s)." % (
                    len(ignorees),
                    wizard._libelle_type(),
                    ", ".join(m.name or "brouillon" for m in ignorees[:5])
                    + (", …" if len(ignorees) > 5 else ""),
                )
                if ignorees else False
            )

    # ------------------------------------------------------------------
    # Factures déjà déclarées
    # ------------------------------------------------------------------
    def _declarations_existantes(self, factures):
        """Déclarations déjà générées, du même type, contenant l'une des
        factures ; renvoie {facture: déclarations}."""
        self.ensure_one()
        if not factures:
            return {}
        declarations = self.env['ras.declaration'].search([
            ('type_declaration', '=', self.type_declaration),
            ('move_ids', 'in', factures.ids),
        ])
        resultat = {}
        for declaration in declarations:
            for move in declaration.move_ids & factures:
                resultat.setdefault(
                    move, self.env['ras.declaration']
                )
                resultat[move] |= declaration
        return resultat

    @api.depends('move_ids', 'type_declaration')
    def _compute_deja_declare(self):
        for wizard in self:
            existantes = wizard._declarations_existantes(
                wizard._factures_a_declarer()
            )
            wizard.deja_declare = bool(existantes)
            wizard.message_deja_declare = "\n".join(
                "%s déjà déclarée dans : %s" % (
                    move.name,
                    ", ".join(
                        "%s (générée le %s)" % (
                            d.name,
                            fields.Datetime.context_timestamp(
                                wizard, d.date_generation
                            ).strftime('%d/%m/%Y %H:%M'),
                        )
                        for d in declarations
                    ),
                )
                for move, declarations in sorted(
                    existantes.items(), key=lambda kv: kv[0].name or ''
                )
            ) or False

    # ------------------------------------------------------------------
    # Contrôles
    # ------------------------------------------------------------------
    def _verifier_donnees(self, factures):
        """Contrôles bloquants avant génération."""
        self.ensure_one()
        erreurs = []

        if not self.periode:
            erreurs.append("Choisissez la période de la déclaration.")

        if not factures:
            erreurs.append(
                "Aucune facture à déclarer : la déclaration ne concerne que "
                "les factures comptabilisées, intégralement payées et "
                "dont le paiement a retenu la %s." % self._libelle_type()
            )

        if self.type_declaration == 'is' and self.regime != '1':
            erreurs.append("La RAS IS se déclare au mois : choisissez le "
                           "régime mensuel.")

        societes = factures.mapped('company_id')
        if len(societes) > 1:
            erreurs.append(
                "Sélectionnez des factures d'une seule société."
            )

        societe = societes[:1] or self.env.company
        if not societe.ras_identifiant_fiscal:
            erreurs.append(
                "Renseignez l'identifiant fiscal (IF) de la société %s."
                % societe.name
            )

        for partenaire in factures.mapped('partner_id'):
            if not partenaire.ras_identifiant_fiscal:
                erreurs.append(
                    "Fournisseur %s : identifiant fiscal (IF) manquant."
                    % partenaire.display_name
                )

        if erreurs:
            raise UserError("\n".join(erreurs))

    # ------------------------------------------------------------------
    # Données du fichier
    # ------------------------------------------------------------------
    @api.model
    def _date_paiement(self, move):
        """Date du dernier paiement lettré avec la facture, ou None si la
        facture n'est pas payée (la balise reste vide dans le fichier)."""
        dates = move._get_reconciled_payments().mapped('date')
        return max(dates) if dates else None

    def _lignes_fichier_tva(self, factures):
        """Une ligne par fournisseur / facture / taux de TVA."""
        self.ensure_one()
        lignes = []

        for move in factures.sorted(lambda m: (m.invoice_date, m.name)):
            date_paiement = self._date_paiement(move)
            # Regroupement des lignes de la facture par taux de TVA
            par_taux = {}
            for line in move.invoice_line_ids.filtered('ras_amount_tva'):
                tva = line.tax_ids.filtered(
                    lambda t: t.amount_type == 'percent'
                    and not t.ras_is_retenue_source
                )[:1]
                taux_tva = tva.amount if tva else 0.0
                cle = (taux_tva, line._ras_code_dgi('tva'))
                base, retenu = par_taux.get(cle, (0.0, 0.0))
                par_taux[cle] = (
                    base + line.price_subtotal,
                    retenu + line.ras_amount_tva,
                )

            for (taux_tva, nature), (base, retenu) in sorted(par_taux.items()):
                montant_tva = base * taux_tva / 100.0
                taux_ras = (
                    float_round(retenu / montant_tva * 100.0, precision_digits=0)
                    if montant_tva else 0.0
                )
                lignes.append({
                    'if_fournisseur': move.partner_id.ras_identifiant_fiscal,
                    'num_facture': move.ref or move.name,
                    'date_paiement': date_paiement,
                    'date_operation': move.invoice_date,
                    'nature': nature,
                    'montant_ht': '%.2f' % base,
                    'taux_tva': '%g' % taux_tva,
                    'taux_ras': '%g' % taux_ras,
                })
        return lignes

    def _lignes_fichier_is(self, factures):
        """Une ligne par bénéficiaire / facture / taux de RAS IS."""
        self.ensure_one()
        lignes = []
        for move in factures.sorted(lambda m: (m.partner_id.name or '', m.invoice_date, m.name)):
            partenaire = move.partner_id
            par_cle = {}
            for line in move.invoice_line_ids.filtered('ras_amount_is'):
                base = line.price_subtotal
                taux = float_round(
                    line.ras_amount_is / base * 100.0, precision_digits=2
                ) if base else 0.0
                cle = (taux, line._ras_code_dgi('is'))
                total_base, retenu = par_cle.get(cle, (0.0, 0.0))
                par_cle[cle] = (total_base + base, retenu + line.ras_amount_is)
            for (taux, nature), (base, retenu) in sorted(par_cle.items()):
                lignes.append({
                    'nom': partenaire.name,
                    'if_beneficiaire': partenaire.ras_identifiant_fiscal,
                    'ice_beneficiaire': partenaire.company_registry,
                    'type_beneficiaire': (
                        'PP' if partenaire.ras_type_fournisseur == 'personne_physique'
                        else 'PM'
                    ),
                    'nature': nature,
                    'base': '%.2f' % base,
                    'taux': '%g' % taux,
                    'montant': '%.2f' % retenu,
                    'date_paiement': self._date_paiement(move),
                    'reference': move.ref or move.name,
                })
        return lignes

    def _contenu_xml(self, factures):
        """Contenu du fichier XML de déclaration, selon le type."""
        self.ensure_one()
        societe = factures[:1].company_id or self.env.company
        if self.type_declaration == 'is':
            lignes = self._lignes_fichier_is(factures)
            entete = {
                'identifiant_fiscal': societe.ras_identifiant_fiscal,
                'reference': '%s%s' % (self.annee, str(self.periode).zfill(2)),
                'type_declaration': 'Ordinaire',
                'date_generation': fields.Date.context_today(self),
                'total_base': '%.2f' % sum(float(l['base']) for l in lignes),
                'total_montant': '%.2f' % sum(float(l['montant']) for l in lignes),
            }
            return construire_xml_is(entete, lignes)
        entete = {
            'identifiant_fiscal': societe.ras_identifiant_fiscal,
            'annee': self.annee,
            'periode': self.periode,
            'regime': self.regime,
        }
        return construire_xml_tva(entete, self._lignes_fichier_tva(factures))

    def _nom_fichier(self, factures, extension='xml'):
        societe = factures[:1].company_id or self.env.company
        return "RAS_%s_%s_%s_%s.%s" % (
            self.type_declaration.upper(),
            societe.ras_identifiant_fiscal or 'IF',
            self.annee,
            str(self.periode).zfill(2),
            extension,
        )

    # ------------------------------------------------------------------
    # Génération du fichier
    # ------------------------------------------------------------------
    def _zip_du_xml(self, nom_xml, contenu_xml):
        """Archive ZIP contenant le fichier XML."""
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(nom_xml, contenu_xml.encode('utf-8'))
        return tampon.getvalue()

    def action_generer(self):
        self.ensure_one()
        factures = self._factures_a_declarer()
        self._verifier_donnees(factures)

        if (
            self._declarations_existantes(factures)
            and not self.env.context.get('ras_forcer_redeclaration')
        ):
            raise UserError(
                "Certaines factures ont déjà été déclarées :\n%s\n\n"
                "Utilisez « Forcer la redéclaration » pour les déclarer "
                "à nouveau." % self.message_deja_declare
            )

        contenu_xml = self._contenu_xml(factures)
        nom_xml = self._nom_fichier(factures, 'xml')
        contenu_zip = self._zip_du_xml(nom_xml, contenu_xml)

        nom_zip = self._nom_fichier(factures, 'zip')
        fichier_b64 = base64.b64encode(contenu_zip)

        # Historique : une déclaration par génération
        declaration = self.env['ras.declaration'].create({
            'type_declaration': self.type_declaration,
            'company_id': (factures[:1].company_id or self.env.company).id,
            'annee': self.annee,
            'periode': self.periode,
            'regime': self.regime,
            'move_ids': [(6, 0, factures.ids)],
            'total_base': self.total_base,
            'total_retenu': self.total_retenu,
            'fichier': fichier_b64,
            'nom_fichier': nom_zip,
        })

        self.write({
            'fichier': fichier_b64,
            'nom_fichier': nom_zip,
            'declaration_id': declaration.id,
            'etat': 'genere',
        })

        context = dict(self.env.context)
        context.pop('ras_forcer_redeclaration', None)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ras.declaration.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def action_forcer_redeclaration(self):
        """Génère la déclaration en incluant les factures déjà déclarées."""
        self.ensure_one()
        return self.with_context(
            ras_forcer_redeclaration=True
        ).action_generer()
