"""Scénario de crise (stress test) : que devient la capacité de remboursement si l'activité baisse ?

Hypothèses, volontairement simples et explicites :
- les ventes baissent du pourcentage choisi ;
- les achats consommés (marchandises, matières) baissent au même rythme : charges variables ;
- les autres achats et charges externes ne baissent que pour leur part variable (réglable) ;
- les impôts et taxes, les salaires, les amortissements et les frais financiers restent fixes ;
- l'impôt sur les bénéfices est recalculé (25 % du résultat courant positif, 0 en cas de perte) ;
- en option, le délai clients s'allonge, ce qui augmente le BFR et pèse sur la trésorerie.

Le seuil de résistance est la baisse de chiffre d'affaires maximale qui laisse le taux de couverture
des remboursements au-dessus du seuil retenu (1,25 par défaut).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from .analyse import Ratios, analyser_historique, calculer_sig
from .modele import ComptesAnnuels
from .scoring import Notation, noter
from .simulation_pret import ResultatSimulation, simuler

TAUX_IS = 0.25


@dataclass
class Scenario:
    baisse_ca: float = 0.10                 # 0,10 = −10 % de chiffre d'affaires
    part_variable_charges_externes: float = 0.5
    allongement_delai_clients_jours: float = 0.0


def appliquer(c: ComptesAnnuels, s: Scenario) -> ComptesAnnuels:
    k = 1 - s.baisse_ca
    r = copy.deepcopy(c)
    for champ in ("ventes_marchandises", "production_vendue", "achats_marchandises", "achats_matieres",
                  "variation_stock_marchandises", "variation_stock_matieres", "stocks", "creances_clients",
                  "dettes_fournisseurs"):
        setattr(r, champ, getattr(c, champ) * k)
    r.autres_achats_charges_externes = c.autres_achats_charges_externes * (1 - s.baisse_ca * s.part_variable_charges_externes)

    # Allongement du délai clients : créances supplémentaires, financées par la trésorerie
    supplement = r.chiffre_affaires * 1.2 * s.allongement_delai_clients_jours / 360
    r.creances_clients += supplement

    # Impôt recalculé sur le résultat courant du scénario
    r.impot_benefices = 0.0
    rcai = calculer_sig(r).resultat_courant_avant_impot
    r.impot_benefices = max(0.0, rcai) * TAUX_IS

    # Le bilan reste équilibré : le résultat va aux capitaux propres, l'écart passe par la trésorerie
    r.capitaux_propres += calculer_sig(r).resultat_net - calculer_sig(c).resultat_net
    ecart = r.total_actif - r.total_passif
    disponibilites = r.disponibilites - ecart
    if disponibilites >= 0:
        r.disponibilites = disponibilites
    else:
        r.disponibilites = 0.0
        r.concours_bancaires_courants += -disponibilites
    r.verifier_equilibre()
    return r


@dataclass
class ResultatStress:
    scenario: Scenario
    ratios: Ratios
    notation: Notation
    simulation: ResultatSimulation
    besoin_tresorerie: float     # trésorerie consommée par rapport à la situation normale


def tester(c: ComptesAnnuels, precedent: ComptesAnnuels | None, s: Scenario, montant: float, taux: float,
           duree_mois: int, duree_residuelle_ans: float = 5.0) -> ResultatStress:
    stresse = appliquer(c, s)
    ratios = analyser_historique([precedent, stresse] if precedent else [stresse])[-1]
    dettes_lmt = c.emprunts_bancaires + c.autres_dettes_financieres
    sim = simuler(ratios, dettes_lmt, montant, taux, duree_mois, duree_residuelle_ans)
    normal = analyser_historique([precedent, c] if precedent else [c])[-1]
    return ResultatStress(s, ratios, noter(ratios), sim, normal.tresorerie_nette - ratios.tresorerie_nette)


def couverture_selon_baisse(c: ComptesAnnuels, precedent: ComptesAnnuels | None, montant: float, taux: float,
                            duree_mois: int, duree_residuelle_ans: float = 5.0, part_variable: float = 0.5,
                            baisses=None) -> list[tuple[float, float | None]]:
    baisses = baisses if baisses is not None else [i / 100 for i in range(0, 51, 2)]
    sortie = []
    for b in baisses:
        r = tester(c, precedent, Scenario(b, part_variable), montant, taux, duree_mois, duree_residuelle_ans)
        sortie.append((b, r.simulation.taux_couverture if r.ratios.caf > 0 else 0.0))
    return sortie


def seuil_resistance(c: ComptesAnnuels, precedent: ComptesAnnuels | None, montant: float, taux: float,
                     duree_mois: int, duree_residuelle_ans: float = 5.0, part_variable: float = 0.5,
                     couverture_minimale: float = 1.25) -> float | None:
    """Baisse de CA maximale (entre 0 et 60 %) qui garde le taux de couverture au-dessus du seuil.
    None si le seuil n'est pas respecté même sans baisse d'activité."""
    def couv(b):
        r = tester(c, precedent, Scenario(b, part_variable), montant, taux, duree_mois, duree_residuelle_ans)
        return r.simulation.taux_couverture if r.ratios.caf > 0 else 0.0

    if couv(0.0) < couverture_minimale:
        return None
    if couv(0.6) >= couverture_minimale:
        return 0.6
    bas, haut = 0.0, 0.6
    for _ in range(30):
        milieu = (bas + haut) / 2
        if couv(milieu) >= couverture_minimale:
            bas = milieu
        else:
            haut = milieu
    return bas
