"""Comparaison sectorielle : situe les ratios de l'entreprise parmi des entreprises comparables.

Les références viennent des « Indicateurs sectoriels financiers (BCE / INPI) » publiés par Bercy :
pour chaque groupe (code NAF × tranche de chiffre d'affaires × année), les percentiles 10, 25, 50,
75 et 90 de chaque ratio. Le groupe retenu est le plus fin disponible : sous-classe NAF, puis classe,
groupe, division, section, et à défaut l'ensemble des entreprises.
"""

from __future__ import annotations

import csv
import gzip
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .analyse import Ratios
from .modele import ComptesAnnuels

FICHIER = Path(__file__).with_name("secteurs.csv.gz")
QUANTILES = (10, 25, 50, 75, 90)

# (champ de la base, libellé, unité, sens : +1 plus haut = mieux, -1 plus bas = mieux, 0 neutre)
INDICATEURS = [
    ("marge_ebe", "Taux d'EBE", "%", +1),
    ("part_ca_resultat_net", "Rentabilité nette", "%", +1),
    ("caf_sur_ca", "CAF / chiffre d'affaires", "%", +1),
    ("autonomie_financiere", "Autonomie financière", "%", +1),
    ("taux_d_endettement", "Endettement (dettes financières / capitaux propres)", "%", -1),
    ("capacite_de_remboursement", "Capacité de remboursement (dettes / CAF)", "ans", -1),
    ("ratio_de_liquidite", "Liquidité générale", "%", +1),
    ("poids_bfr_exploitation_sur_ca_jours", "BFR d'exploitation", "jours de CA", -1),
    ("credit_clients_jours", "Délai clients", "jours", -1),
    ("credit_fournisseurs_jours", "Délai fournisseurs", "jours", 0),
]

SECTIONS_NAF = [  # (division minimale, division maximale, section)
    (1, 3, "A"), (5, 9, "B"), (10, 33, "C"), (35, 35, "D"), (36, 39, "E"), (41, 43, "F"), (45, 47, "G"),
    (49, 53, "H"), (55, 56, "I"), (58, 63, "J"), (64, 66, "K"), (68, 68, "L"), (69, 75, "M"), (77, 82, "N"),
    (84, 84, "O"), (85, 85, "P"), (86, 88, "Q"), (90, 93, "R"), (94, 96, "S"), (97, 98, "T"), (99, 99, "U"),
]
NIVEAUX = {5: "sous-classe", 4: "classe", 3: "groupe", 2: "division", 1: "section"}


@lru_cache(maxsize=1)
def references() -> dict[tuple[str, str], dict]:
    with gzip.open(FICHIER, "rt", encoding="utf-8") as f:
        return {(l["classe_naf"], l["classe_ca"]): l for l in csv.DictReader(f, delimiter=";")}


def normaliser_naf(code: str | None) -> str:
    return "".join(ch for ch in str(code or "").upper() if ch.isalnum())


def section(naf: str) -> str | None:
    try:
        division = int(naf[:2])
    except ValueError:
        return None
    return next((s for a, b, s in SECTIONS_NAF if a <= division <= b), None)


def tranche_ca(ca: float) -> str:
    if ca < 2e6:
        return "<2M"
    if ca < 10e6:
        return "2M-10M"
    if ca < 50e6:
        return "10M-50M"
    return ">50M"


@dataclass
class Groupe:
    code: str
    niveau: str
    tranche: str
    exercice: int
    cohorte: int
    ligne: dict

    @property
    def description(self) -> str:
        portee = "toutes tailles" if self.tranche == "*" else f"CA {self.tranche.replace('M', ' M€')}"
        if self.niveau == "ensemble":
            return f"ensemble des entreprises ({portee}), exercice {self.exercice}, {self.cohorte} entreprises"
        return f"NAF {self.code} ({self.niveau}, {portee}), exercice {self.exercice}, {self.cohorte} entreprises"


def trouver_groupe(code_naf: str | None, ca: float) -> Groupe | None:
    refs = references()
    naf = normaliser_naf(code_naf)
    candidats = []
    for n in (5, 4, 3, 2):
        if len(naf) >= n:
            candidats.append((naf[:n], NIVEAUX[n]))
    if naf and section(naf):
        candidats.append((section(naf), "section"))
    candidats.append(("*", "ensemble"))
    for code, niveau in candidats:
        for tranche in (tranche_ca(ca), "*"):
            ligne = refs.get((code, tranche))
            if ligne:
                return Groupe(code, niveau, tranche, int(ligne["exercice"]), int(ligne["cohorte"]), ligne)
    return None


def valeurs_entreprise(r: Ratios, c: ComptesAnnuels) -> dict[str, float | None]:
    """Ratios calculés selon les définitions de la base publique (en %, ou en jours / années)."""
    ca = r.chiffre_affaires

    def div(a, b, facteur=1.0):
        return None if not b else a / b * facteur

    achats = c.achats_marchandises + c.achats_matieres + c.autres_achats_charges_externes
    return {
        "marge_ebe": div(r.ebe, ca, 100),
        "part_ca_resultat_net": div(r.resultat_net, ca, 100),
        "caf_sur_ca": div(r.caf, ca, 100),
        "autonomie_financiere": None if r.autonomie_financiere is None else r.autonomie_financiere * 100,
        "taux_d_endettement": div(c.dettes_financieres, c.capitaux_propres, 100),
        "capacite_de_remboursement": div(c.dettes_financieres, r.caf) if r.caf > 0 else None,
        "ratio_de_liquidite": None if r.liquidite_generale is None else r.liquidite_generale * 100,
        "poids_bfr_exploitation_sur_ca_jours": r.bfr_jours_ca,
        "credit_clients_jours": div(c.creances_clients, ca, 360),
        "credit_fournisseurs_jours": div(c.dettes_fournisseurs, achats, 360),
    }


def percentile(valeur: float, points: list[float]) -> float:
    """Position approximative (0 à 100) par interpolation linéaire entre les percentiles publiés."""
    if valeur <= points[0]:
        return 5.0
    if valeur >= points[-1]:
        return 95.0
    for (q1, v1), (q2, v2) in zip(zip(QUANTILES, points), zip(QUANTILES[1:], points[1:])):
        if v1 <= valeur <= v2:
            return q1 + (q2 - q1) * ((valeur - v1) / (v2 - v1) if v2 > v1 else 0.5)
    return 50.0


@dataclass
class Position:
    champ: str
    libelle: str
    unite: str
    sens: int
    valeur: float
    quantiles: list[float]
    percentile: float

    @property
    def mediane(self) -> float:
        return self.quantiles[2]

    @property
    def score(self) -> float:
        """Position orientée : 100 = parmi les meilleurs du secteur, 0 = parmi les moins bons."""
        return 100 - self.percentile if self.sens < 0 else self.percentile

    @property
    def couleur(self) -> str | None:
        if self.sens == 0:
            return None
        return "vert" if self.score >= 75 else "rouge" if self.score <= 25 else "orange" if self.score < 40 else None

    @property
    def lecture(self) -> str:
        p = self.percentile
        if p <= 10:
            zone = "parmi les 10 % les plus bas"
        elif p < 25:
            zone = "dans le quart le plus bas"
        elif p <= 75:
            zone = "dans la moitié centrale"
        elif p < 90:
            zone = "dans le quart le plus haut"
        else:
            zone = "parmi les 10 % les plus hauts"
        return zone


@dataclass
class Comparaison:
    groupe: Groupe
    positions: list[Position]

    def plus_faibles(self, n=2) -> list[Position]:
        return [p for p in sorted(self.positions, key=lambda p: p.score) if p.sens and p.score <= 25][:n]

    def plus_forts(self, n=2) -> list[Position]:
        return [p for p in sorted(self.positions, key=lambda p: -p.score) if p.sens and p.score >= 75][:n]


def comparer(r: Ratios, c: ComptesAnnuels, code_naf: str | None) -> Comparaison | None:
    groupe = trouver_groupe(code_naf, r.chiffre_affaires)
    if groupe is None:
        return None
    valeurs = valeurs_entreprise(r, c)
    positions = []
    for champ, libelle, unite, sens in INDICATEURS:
        v = valeurs.get(champ)
        try:
            points = [float(groupe.ligne[f"{champ}_q{q}"]) for q in QUANTILES]
        except (KeyError, ValueError):
            continue
        if v is None:
            continue
        positions.append(Position(champ, libelle, unite, sens, v, points, percentile(v, points)))
    return Comparaison(groupe, positions)


def _nombre(x: float, unite: str) -> str:
    if unite == "%":
        return f"{x:.1f} %".replace(".", ",").replace("-", "−")
    if unite == "ans":
        return f"{x:.1f} ans".replace(".", ",")
    return f"{x:.0f} jours"


# Ratios déjà commentés par l'analyse principale avec la définition de l'outil : les reprendre avec la
# définition de Bercy (légèrement différente) donnerait deux chiffres pour une même notion.
DEJA_COMMENTES = {"capacite_de_remboursement", "poids_bfr_exploitation_sur_ca_jours", "caf_sur_ca"}


def constats_sectoriels(comparaison: "Comparaison | None"):
    """Deux points faibles et un point fort au plus, rédigés à partir de la position dans le secteur."""
    from .commentaires import Constat
    if comparaison is None:
        return []
    sortie = []
    utiles = Comparaison(comparaison.groupe, [p for p in comparaison.positions if p.champ not in DEJA_COMMENTES])
    comparaison = utiles
    for p in comparaison.plus_faibles(2):
        sortie.append(Constat("negatif", f"{p.libelle.split(' (')[0]} {p.lecture} du secteur : "
                                         f"{_nombre(p.valeur, p.unite)} contre une médiane de {_nombre(p.mediane, p.unite)}."))
    for p in comparaison.plus_forts(1):
        sortie.append(Constat("positif", f"{p.libelle.split(' (')[0]} {p.lecture} du secteur : "
                                         f"{_nombre(p.valeur, p.unite)} contre une médiane de {_nombre(p.mediane, p.unite)}."))
    return sortie
