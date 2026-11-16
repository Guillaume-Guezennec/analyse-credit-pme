"""Notation du risque de crédit à partir des ratios.

IMPORTANT : les seuils ci-dessous sont des repères usuels d'analyse financière,
fixés à titre pédagogique. Ils ne reproduisent la grille d'aucune banque et
doivent être adaptés au secteur d'activité de l'entreprise.
"""

from __future__ import annotations

from dataclasses import dataclass

from .analyse import Ratios


@dataclass
class Critere:
    nom: str
    attribut: str
    poids: int
    seuil_bon: float
    seuil_alerte: float
    plus_haut_mieux: bool
    explication: str


CRITERES = [
    Critere("Capacité de remboursement", "capacite_remboursement", 25, 3.0, 5.0, False,
            "Nombre d'années de CAF pour rembourser les dettes financières. "
            "Repère courant : moins de 3 à 4 ans."),
    Critere("Autonomie financière", "autonomie_financiere", 20, 0.30, 0.15, True,
            "Part des capitaux propres dans le total du bilan. Au-delà de 25-30 %, "
            "la structure est jugée solide."),
    Critere("Taux d'EBE", "taux_ebe", 15, 0.10, 0.04, True,
            "Rentabilité opérationnelle avant amortissements et frais financiers."),
    Critere("Levier DFN / EBE", "levier_dfn_ebe", 15, 2.5, 4.0, False,
            "Endettement net rapporté à l'EBE. Au-delà de 4, l'entreprise est fortement endettée."),
    Critere("Poids des frais financiers", "poids_charges_financieres", 10, 0.15, 0.30, False,
            "Part de l'EBE absorbée par les intérêts."),
    Critere("Liquidité générale", "liquidite_generale", 10, 1.3, 1.0, True,
            "Actif circulant / dettes à court terme. En dessous de 1, risque de tension de trésorerie."),
    Critere("Rentabilité nette", "rentabilite_nette", 5, 0.03, 0.0, True,
            "Résultat net rapporté au chiffre d'affaires."),
]


@dataclass
class NoteCritere:
    critere: Critere
    valeur: float | None
    points: float
    feu: str  # "vert", "orange", "rouge"


@dataclass
class Notation:
    score: float      # sur 100
    note: str         # A à E
    libelle: str
    details: list[NoteCritere]


ECHELLE = [
    (80, "A", "Risque faible"),
    (65, "B", "Risque modéré"),
    (50, "C", "Risque moyen, à surveiller"),
    (35, "D", "Risque élevé"),
    (0, "E", "Risque très élevé"),
]


def _evaluer(c: Critere, valeur: float | None) -> tuple[float, str]:
    """Vert = 100 % des points, rouge = 0, orange = interpolation linéaire entre les seuils."""
    if valeur is None:  # ex. CAF négative ou EBE nul : on retient le cas le plus défavorable
        return 0.0, "rouge"
    if c.attribut in ("levier_dfn_ebe", "poids_charges_financieres") and valeur < 0:
        # DFN négative (trésorerie excédentaire) : favorable si l'EBE est positif
        return float(c.poids), "vert"
    bon, alerte = c.seuil_bon, c.seuil_alerte
    favorable = valeur >= bon if c.plus_haut_mieux else valeur <= bon
    defavorable = valeur <= alerte if c.plus_haut_mieux else valeur >= alerte
    if favorable:
        return float(c.poids), "vert"
    if defavorable:
        return 0.0, "rouge"
    part = (valeur - alerte) / (bon - alerte)
    return c.poids * part, "orange"


def noter(r: Ratios, ebe_negatif_eliminatoire: bool = True) -> Notation:
    details = []
    for c in CRITERES:
        valeur = getattr(r, c.attribut)
        if c.attribut == "levier_dfn_ebe" and r.ebe <= 0:
            valeur = None
        points, feu = _evaluer(c, valeur)
        details.append(NoteCritere(c, valeur, points, feu))
    score = round(sum(d.points for d in details), 1)
    if ebe_negatif_eliminatoire and r.ebe <= 0:
        score = min(score, 34.0)  # un EBE négatif plafonne la note à E
    for seuil, note, libelle in ECHELLE:
        if score >= seuil:
            return Notation(score, note, libelle, details)
    raise AssertionError("inaccessible")
