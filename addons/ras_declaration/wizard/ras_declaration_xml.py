"""Construction des fichiers XML de déclaration de la RAS (TVA, IS).

Les noms de balises sont regroupés ici : ils seront alignés sur le schéma
officiel de la DGI sans toucher au reste du module.
"""
from xml.sax.saxutils import escape

# --- Noms des balises (cahier des charges SIMPL-TVA) ---
BALISE_RACINE = 'VersementRetenueSources'
BALISE_IF = 'identifiantFiscal'
BALISE_ANNEE = 'annee'
BALISE_PERIODE = 'periode'
BALISE_REGIME = 'regime'
BALISE_FOURNISSEURS = 'fournisseurs'
BALISE_FOURNISSEUR = 'fournisseur'
BALISE_IF_FOURNISSEUR = 'ifuFournisseur'
BALISE_NUM_FACTURE = 'numFacture'
BALISE_DATE_PAIEMENT = 'datePaiement'
BALISE_DATE_OPERATION = 'dateOperation'
BALISE_NATURE = 'refNatOpt'
BALISE_MONTANT_HT = 'montantHT'
BALISE_TAUX_TVA = 'tauxTva'
BALISE_TAUX_RAS = 'tauxRetenuSource'


def _balise(nom, valeur, indent=0):
    return '%s<%s>%s</%s>' % (' ' * indent, nom, escape(str(valeur or '')), nom)


def construire_xml_tva(entete, lignes):
    """Retourne le contenu du fichier XML de déclaration de la RAS TVA.

    entete : dict avec identifiant_fiscal, annee, periode, regime
    lignes : liste de dicts (une par fournisseur / facture / taux de TVA)
    """
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<%s>' % BALISE_RACINE]
    out.append(_balise(BALISE_IF, entete['identifiant_fiscal'], 2))
    out.append(_balise(BALISE_ANNEE, entete['annee'], 2))
    out.append(_balise(BALISE_PERIODE, entete['periode'], 2))
    out.append(_balise(BALISE_REGIME, entete['regime'], 2))
    out.append('  <%s>' % BALISE_FOURNISSEURS)

    for ligne in lignes:
        out.append('    <%s>' % BALISE_FOURNISSEUR)
        out.append(_balise(BALISE_IF_FOURNISSEUR, ligne['if_fournisseur'], 6))
        out.append(_balise(BALISE_NUM_FACTURE, ligne['num_facture'], 6))
        out.append(_balise(BALISE_DATE_PAIEMENT, ligne['date_paiement'], 6))
        out.append(_balise(BALISE_DATE_OPERATION, ligne['date_operation'], 6))
        out.append(_balise(BALISE_NATURE, ligne['nature'], 6))
        out.append(_balise(BALISE_MONTANT_HT, ligne['montant_ht'], 6))
        out.append(_balise(BALISE_TAUX_TVA, ligne['taux_tva'], 6))
        out.append(_balise(BALISE_TAUX_RAS, ligne['taux_ras'], 6))
        out.append('    </%s>' % BALISE_FOURNISSEUR)

    out.append('  </%s>' % BALISE_FOURNISSEURS)
    out.append('</%s>' % BALISE_RACINE)
    return '\n'.join(out)


# --- Noms des balises (cahier des charges EDI SIMPL-IS) ---
IS_RACINE = 'EDI'
IS_ENTETE = 'Entete'
IS_IF = 'IdFiscal'
IS_REFERENCE = 'Reference'
IS_TYPE_DECLARATION = 'TypeDeclaration'
IS_DATE_GENERATION = 'DateGeneration'
IS_DECLARATION = 'Declaration'
IS_RAS = 'RAS'
IS_CODE_IMPOT = 'CodeImpot'
IS_LIGNE = 'LigneRAS'
IS_NOM = 'NomBeneficiaire'
IS_IF_BENEFICIAIRE = 'IFBeneficiaire'
IS_ICE_BENEFICIAIRE = 'ICEBeneficiaire'
IS_TYPE_BENEFICIAIRE = 'TypeBeneficiaire'
IS_NATURE = 'NatureRemuneration'
IS_BASE = 'BaseImposable'
IS_TAUX = 'TauxRetenue'
IS_MONTANT = 'MontantRetenue'
IS_DATE_PAIEMENT = 'DatePaiement'
IS_REFERENCE_PAIEMENT = 'ReferencePaiement'
IS_TOTAL_BASE = 'TotalBaseImposable'
IS_TOTAL_MONTANT = 'TotalMontantRetenue'


def construire_xml_is(entete, lignes):
    """Retourne le contenu du fichier XML de déclaration de la RAS IS.

    entete : dict avec identifiant_fiscal, reference, type_declaration,
             date_generation
    lignes : liste de dicts (une par bénéficiaire / facture / taux)
    """
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<%s>' % IS_RACINE]
    out.append('  <%s>' % IS_ENTETE)
    out.append(_balise(IS_IF, entete['identifiant_fiscal'], 4))
    out.append(_balise(IS_REFERENCE, entete['reference'], 4))
    out.append(_balise(IS_TYPE_DECLARATION, entete['type_declaration'], 4))
    out.append(_balise(IS_DATE_GENERATION, entete['date_generation'], 4))
    out.append('  </%s>' % IS_ENTETE)
    out.append('  <%s>' % IS_DECLARATION)
    out.append('    <%s>' % IS_RAS)
    out.append(_balise(IS_CODE_IMPOT, 'IS', 6))

    for ligne in lignes:
        out.append('      <%s>' % IS_LIGNE)
        out.append(_balise(IS_NOM, ligne['nom'], 8))
        out.append(_balise(IS_IF_BENEFICIAIRE, ligne['if_beneficiaire'], 8))
        out.append(_balise(IS_ICE_BENEFICIAIRE, ligne['ice_beneficiaire'], 8))
        out.append(_balise(IS_TYPE_BENEFICIAIRE, ligne['type_beneficiaire'], 8))
        out.append(_balise(IS_NATURE, ligne['nature'], 8))
        out.append(_balise(IS_BASE, ligne['base'], 8))
        out.append(_balise(IS_TAUX, ligne['taux'], 8))
        out.append(_balise(IS_MONTANT, ligne['montant'], 8))
        out.append(_balise(IS_DATE_PAIEMENT, ligne['date_paiement'], 8))
        out.append(_balise(IS_REFERENCE_PAIEMENT, ligne['reference'], 8))
        out.append('      </%s>' % IS_LIGNE)

    out.append(_balise(IS_TOTAL_BASE, entete['total_base'], 6))
    out.append(_balise(IS_TOTAL_MONTANT, entete['total_montant'], 6))
    out.append('    </%s>' % IS_RAS)
    out.append('  </%s>' % IS_DECLARATION)
    out.append('</%s>' % IS_RACINE)
    return '\n'.join(out)
