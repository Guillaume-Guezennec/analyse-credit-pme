"""Liste des postes du modèle Excel, avec leur libellé et une aide à la saisie.

Le code (1re valeur) correspond exactement au nom du champ dans ComptesAnnuels.
Ce fichier sert à la fois à générer le modèle Excel et à le relire.
"""

SECTIONS = [
    ("COMPTE DE RÉSULTAT — Produits d'exploitation", [
        ("ventes_marchandises", "Ventes de marchandises", "Négoce : biens revendus en l'état (compte 707)"),
        ("production_vendue", "Production vendue (biens et services)", "Comptes 701 à 706"),
        ("production_stockee", "Production stockée", "Variation des stocks de produits finis et en-cours (peut être négative)"),
        ("production_immobilisee", "Production immobilisée", "Travaux faits par l'entreprise pour elle-même"),
        ("subventions_exploitation", "Subventions d'exploitation", ""),
        ("reprises_provisions", "Reprises sur amortissements et provisions", "Reprises d'exploitation uniquement"),
        ("autres_produits", "Autres produits", ""),
    ]),
    ("COMPTE DE RÉSULTAT — Charges d'exploitation", [
        ("achats_marchandises", "Achats de marchandises", ""),
        ("variation_stock_marchandises", "Variation de stock de marchandises", "Stock initial − stock final : négatif si le stock augmente"),
        ("achats_matieres", "Achats de matières premières et approvisionnements", ""),
        ("variation_stock_matieres", "Variation de stock de matières premières", "Stock initial − stock final : négatif si le stock augmente"),
        ("autres_achats_charges_externes", "Autres achats et charges externes", "Loyers, sous-traitance, énergie, honoraires…"),
        ("impots_taxes", "Impôts, taxes et versements assimilés", "Hors impôt sur les bénéfices"),
        ("salaires", "Salaires et traitements", ""),
        ("charges_sociales", "Charges sociales", ""),
        ("dotations_amortissements_provisions", "Dotations aux amortissements et provisions", "Dotations d'exploitation"),
        ("autres_charges", "Autres charges", ""),
    ]),
    ("COMPTE DE RÉSULTAT — Financier, exceptionnel, impôt", [
        ("produits_financiers", "Produits financiers", ""),
        ("charges_financieres", "Charges financières", "Principalement les intérêts des emprunts"),
        ("produits_exceptionnels", "Produits exceptionnels", "Y compris les produits de cession d'actifs"),
        ("charges_exceptionnelles", "Charges exceptionnelles", "Y compris la valeur nette comptable des actifs cédés"),
        ("plus_values_cession", "dont plus-values de cession", "Produit de cession − VNC. Sert au calcul de la CAF"),
        ("participation_salaries", "Participation des salariés", ""),
        ("impot_benefices", "Impôt sur les bénéfices", ""),
    ]),
    ("BILAN — Actif (valeurs nettes)", [
        ("immobilisations_incorporelles", "Immobilisations incorporelles", "Fonds commercial, logiciels…"),
        ("immobilisations_corporelles", "Immobilisations corporelles", "Terrains, constructions, matériel…"),
        ("immobilisations_financieres", "Immobilisations financières", "Participations, dépôts et cautionnements"),
        ("stocks", "Stocks et en-cours", "Tous stocks confondus"),
        ("creances_clients", "Créances clients", ""),
        ("autres_creances", "Autres créances", "TVA déductible, créances sociales et fiscales…"),
        ("valeurs_mobilieres_placement", "Valeurs mobilières de placement", ""),
        ("disponibilites", "Disponibilités", "Soldes débiteurs des comptes bancaires et caisse"),
        ("charges_constatees_avance", "Charges constatées d'avance", ""),
    ]),
    ("BILAN — Passif", [
        ("capitaux_propres", "Capitaux propres", "Total, y compris le résultat de l'exercice"),
        ("provisions_risques_charges", "Provisions pour risques et charges", ""),
        ("emprunts_bancaires", "Emprunts auprès des établissements de crédit", "HORS découverts : ils vont sur la ligne suivante"),
        ("concours_bancaires_courants", "Concours bancaires courants (découverts)", "Soldes créditeurs de banque, souvent détaillés en annexe"),
        ("autres_dettes_financieres", "Emprunts et dettes financières divers", "Dont comptes courants d'associés"),
        ("dettes_fournisseurs", "Dettes fournisseurs", ""),
        ("dettes_fiscales_sociales", "Dettes fiscales et sociales", ""),
        ("autres_dettes", "Autres dettes", "Dettes sur immobilisations, divers"),
        ("produits_constates_avance", "Produits constatés d'avance", ""),
    ]),
]

INFOS_ENTREPRISE = [
    ("raison_sociale", "Raison sociale", "texte"),
    ("activite", "Activité", "texte"),
    ("code_naf", "Code NAF", "texte"),
    ("effectif", "Effectif", "nombre"),
]

INFOS_DEMANDE = [
    ("objet", "Objet du financement", "texte"),
    ("montant", "Montant demandé (€)", "euros"),
    ("taux_annuel", "Taux annuel", "pourcentage"),
    ("duree_mois", "Durée (en mois)", "nombre"),
]

CODES_POSTES = [code for _, postes in SECTIONS for code, _, _ in postes]
