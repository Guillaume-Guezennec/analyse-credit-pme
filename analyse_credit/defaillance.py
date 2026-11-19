"""Probabilité de défaillance à 24 mois, à partir de la grille de score entraînée sur données publiques.

Le modèle (analyse_credit/modele_defaillance.json) est produit par outils/entrainer_modele.py.
Chaque ratio de l'entreprise est placé dans sa tranche ; la somme des poids donne le score, transformé
en probabilité. La contribution d'un ratio est l'écart entre le poids de sa tranche et le poids moyen
de ce ratio dans la population : positive, elle aggrave le risque ; négative, elle le réduit.
"""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .analyse import Ratios
from .modele import ComptesAnnuels

FICHIER = Path(__file__).with_name("modele_defaillance.json")

CLASSES = [  # (probabilité maximale, libellé, couleur d'appréciation)
    (0.005, "Risque faible", "vert"),
    (0.015, "Risque proche de la moyenne", "vert"),
    (0.04, "Risque élevé", "orange"),
    (1.01, "Risque très élevé", "rouge"),
]


@lru_cache(maxsize=1)
def charger_modele() -> dict:
    return json.loads(FICHIER.read_text(encoding="utf-8"))


def variables_entreprise(r: Ratios, c: ComptesAnnuels) -> dict[str, float | None]:
    """Calcule les ratios selon les définitions de la base publique (montants hors taxes, en %)."""
    ca = r.chiffre_affaires

    def div(a, b, facteur=1.0):
        return None if not b else a / b * facteur

    achats = c.achats_marchandises + c.achats_matieres + c.autres_achats_charges_externes
    return {
        "marge_ebe": div(r.ebe, ca, 100),
        "rn_sur_ca": div(r.resultat_net, ca, 100),
        "autonomie_financiere": None if r.autonomie_financiere is None else r.autonomie_financiere * 100,
        "taux_d_endettement": div(c.dettes_financieres, c.capitaux_propres, 100),
        "ratio_de_liquidite": None if r.liquidite_generale is None else r.liquidite_generale * 100,
        "poids_bfr_exploitation_sur_ca_jours": r.bfr_jours_ca,
        "credit_clients_jours": div(c.creances_clients, ca, 360),
        "credit_fournisseurs_jours": div(c.dettes_fournisseurs, achats, 360),
        "croissance_ca": None if r.croissance_ca is None else r.croissance_ca * 100,
        "log_ca": math.log10(ca) if ca and ca > 0 else None,
    }


@dataclass
class Facteur:
    variable: str
    libelle: str
    valeur: float | None
    unite: str
    contribution: float  # > 0 : aggrave le risque


@dataclass
class Prevision:
    probabilite: float
    classe: str
    couleur: str
    multiple_moyenne: float
    taux_moyen: float
    facteurs: list[Facteur]

    @property
    def aggravants(self) -> list[Facteur]:
        return [f for f in sorted(self.facteurs, key=lambda f: -f.contribution) if f.contribution > 0.05]

    @property
    def attenuants(self) -> list[Facteur]:
        return [f for f in sorted(self.facteurs, key=lambda f: f.contribution) if f.contribution < -0.05]


def prevoir(r: Ratios, c: ComptesAnnuels) -> Prevision:
    modele = charger_modele()
    valeurs = variables_entreprise(r, c)
    score = modele["constante"]
    facteurs = []
    for nom, v in modele["variables"].items():
        x = valeurs.get(nom)
        if x is not None and v.get("plancher") is not None:
            x = max(x, v["plancher"])
        bornes, poids = v["bornes"], v["poids"]
        tranche = len(bornes) + 1 if x is None else bisect_right(bornes, x)
        score += poids[tranche]
        facteurs.append(Facteur(nom, v["libelle"], valeurs.get(nom), v["unite"], poids[tranche] - v["reference"]))
    p = 1 / (1 + math.exp(-score))
    classe, couleur = next((lib, coul) for seuil, lib, coul in CLASSES if p < seuil)
    taux = modele["taux_reference"]
    return Prevision(p, classe, couleur, p / taux, taux, facteurs)


def resume_validation() -> dict:
    m = charger_modele()
    v = m["validation"]["grille_de_score"]
    return {"auc": v["auc"], "capture_10pct": v["capture_10pct"], "nb_bilans": m["nb_bilans"],
            "nb_defaillances": m["nb_defaillances"], "taux_reference": m["taux_reference"],
            "annees_test": m["validation"]["test"]}
