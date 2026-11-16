"""Calculs d'analyse financière : SIG, CAF, bilan fonctionnel et ratios bancaires."""

from __future__ import annotations

from dataclasses import dataclass

from .modele import ComptesAnnuels

JOURS = 360  # convention bancaire usuelle


def _div(a: float, b: float) -> float | None:
    """Division sûre : renvoie None si le dénominateur est nul."""
    return None if b == 0 else a / b


@dataclass
class SIG:
    """Soldes intermédiaires de gestion (méthode PCG)."""
    marge_commerciale: float
    production_exercice: float
    consommations_tiers: float
    valeur_ajoutee: float
    ebe: float
    resultat_exploitation: float
    resultat_courant_avant_impot: float
    resultat_exceptionnel: float
    resultat_net: float


def calculer_sig(c: ComptesAnnuels) -> SIG:
    marge = c.ventes_marchandises - (c.achats_marchandises + c.variation_stock_marchandises)
    production = c.production_vendue + c.production_stockee + c.production_immobilisee
    consommations = c.achats_matieres + c.variation_stock_matieres + c.autres_achats_charges_externes
    va = marge + production - consommations
    ebe = va + c.subventions_exploitation - c.impots_taxes - c.salaires - c.charges_sociales
    rex = ebe + c.reprises_provisions + c.autres_produits - c.dotations_amortissements_provisions - c.autres_charges
    rcai = rex + c.produits_financiers - c.charges_financieres
    rexc = c.produits_exceptionnels - c.charges_exceptionnelles
    rn = rcai + rexc - c.participation_salaries - c.impot_benefices
    return SIG(marge, production, consommations, va, ebe, rex, rcai, rexc, rn)


def calculer_caf(c: ComptesAnnuels, sig: SIG | None = None) -> float:
    """Capacité d'autofinancement, méthode additive (à partir du résultat net)."""
    sig = sig or calculer_sig(c)
    return (sig.resultat_net + c.dotations_amortissements_provisions
            - c.reprises_provisions - c.plus_values_cession)


@dataclass
class BilanFonctionnel:
    ressources_stables: float
    frng: float              # fonds de roulement net global
    bfr: float               # besoin en fonds de roulement
    tresorerie_nette: float  # = FRNG - BFR


def calculer_bilan_fonctionnel(c: ComptesAnnuels) -> BilanFonctionnel:
    ressources_stables = (c.capitaux_propres + c.provisions_risques_charges
                          + c.emprunts_bancaires + c.autres_dettes_financieres)
    frng = ressources_stables - c.actif_immobilise
    actif_exploitation = c.stocks + c.creances_clients + c.autres_creances + c.charges_constatees_avance
    passif_exploitation = (c.dettes_fournisseurs + c.dettes_fiscales_sociales + c.autres_dettes
                           + c.produits_constates_avance)
    bfr = actif_exploitation - passif_exploitation
    tresorerie = c.disponibilites + c.valeurs_mobilieres_placement - c.concours_bancaires_courants
    return BilanFonctionnel(ressources_stables, frng, bfr, tresorerie)


@dataclass
class Ratios:
    exercice: int
    chiffre_affaires: float
    croissance_ca: float | None
    taux_ebe: float | None                 # EBE / CA
    rentabilite_nette: float | None        # RN / CA
    rentabilite_capitaux_propres: float | None  # RN / CP
    autonomie_financiere: float | None     # CP / total bilan
    dette_financiere_nette: float
    gearing: float | None                  # DFN / CP
    levier_dfn_ebe: float | None           # DFN / EBE (en années)
    capacite_remboursement: float | None   # dettes financières LMT / CAF (en années)
    poids_charges_financieres: float | None  # charges financières / EBE
    delai_clients_jours: float | None
    delai_fournisseurs_jours: float | None
    bfr_jours_ca: float | None
    liquidite_generale: float | None
    caf: float
    ebe: float
    resultat_net: float
    bfr: float
    frng: float
    tresorerie_nette: float


def calculer_ratios(c: ComptesAnnuels, precedent: ComptesAnnuels | None = None,
                    taux_tva: float = 0.20) -> Ratios:
    sig = calculer_sig(c)
    caf = calculer_caf(c, sig)
    bf = calculer_bilan_fonctionnel(c)
    ca = c.chiffre_affaires

    dfn = c.dettes_financieres - c.disponibilites - c.valeurs_mobilieres_placement
    dettes_lmt = c.emprunts_bancaires + c.autres_dettes_financieres
    achats = c.achats_marchandises + c.achats_matieres + c.autres_achats_charges_externes
    dettes_ct = (c.concours_bancaires_courants + c.dettes_fournisseurs + c.dettes_fiscales_sociales
                 + c.autres_dettes + c.produits_constates_avance)
    actif_ct = c.actif_circulant

    croissance = None
    if precedent is not None and precedent.chiffre_affaires:
        croissance = ca / precedent.chiffre_affaires - 1

    delai_cli = _div(c.creances_clients, ca * (1 + taux_tva))
    delai_fou = _div(c.dettes_fournisseurs, achats * (1 + taux_tva))
    bfr_j = _div(bf.bfr, ca)

    return Ratios(
        exercice=c.exercice,
        chiffre_affaires=ca,
        croissance_ca=croissance,
        taux_ebe=_div(sig.ebe, ca),
        rentabilite_nette=_div(sig.resultat_net, ca),
        rentabilite_capitaux_propres=_div(sig.resultat_net, c.capitaux_propres),
        autonomie_financiere=_div(c.capitaux_propres, c.total_actif),
        dette_financiere_nette=dfn,
        gearing=_div(dfn, c.capitaux_propres),
        levier_dfn_ebe=_div(dfn, sig.ebe),
        capacite_remboursement=_div(dettes_lmt, caf) if caf > 0 else None,
        poids_charges_financieres=_div(c.charges_financieres, sig.ebe),
        delai_clients_jours=None if delai_cli is None else delai_cli * JOURS,
        delai_fournisseurs_jours=None if delai_fou is None else delai_fou * JOURS,
        bfr_jours_ca=None if bfr_j is None else bfr_j * JOURS,
        liquidite_generale=_div(actif_ct, dettes_ct),
        caf=caf,
        ebe=sig.ebe,
        resultat_net=sig.resultat_net,
        bfr=bf.bfr,
        frng=bf.frng,
        tresorerie_nette=bf.tresorerie_nette,
    )


def analyser_historique(exercices: list[ComptesAnnuels], taux_tva: float = 0.20) -> list[Ratios]:
    """Calcule les ratios de chaque exercice, du plus ancien au plus récent."""
    tries = sorted(exercices, key=lambda e: e.exercice)
    resultats = []
    for i, c in enumerate(tries):
        c.verifier_equilibre()
        resultats.append(calculer_ratios(c, tries[i - 1] if i else None, taux_tva))
    return resultats
