"""Simulation d'un nouveau prêt et test de sa soutenabilité."""

from __future__ import annotations

from dataclasses import dataclass

from .analyse import Ratios


def _v(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def mensualite(montant: float, taux_annuel: float, duree_mois: int) -> float:
    """Mensualité constante d'un prêt amortissable."""
    if taux_annuel == 0:
        return montant / duree_mois
    t = taux_annuel / 12
    return montant * t / (1 - (1 + t) ** -duree_mois)


def tableau_amortissement(montant: float, taux_annuel: float, duree_mois: int) -> list[dict]:
    m = mensualite(montant, taux_annuel, duree_mois)
    restant = montant
    lignes = []
    for mois in range(1, duree_mois + 1):
        interets = restant * taux_annuel / 12
        capital = m - interets
        restant = max(restant - capital, 0.0)
        lignes.append({"mois": mois, "mensualite": m, "interets": interets,
                       "capital": capital, "capital_restant": restant})
    return lignes


def montant_maximal(caf: float, annuites_existantes: float, taux_annuel: float, duree_mois: int,
                    couverture_minimale: float = 1.25) -> float:
    """Montant le plus élevé empruntable en gardant CAF / annuités totales >= couverture_minimale."""
    plafond_annuel = caf / couverture_minimale - annuites_existantes
    if plafond_annuel <= 0:
        return 0.0
    mensualite_max = plafond_annuel / 12
    if taux_annuel == 0:
        return mensualite_max * duree_mois
    t = taux_annuel / 12
    return mensualite_max * (1 - (1 + t) ** -duree_mois) / t


@dataclass
class ResultatSimulation:
    mensualite: float
    annuite_nouveau_pret: float
    cout_total_interets: float
    annuites_existantes_estimees: float
    taux_couverture: float | None      # CAF / total des annuités
    capacite_remboursement_apres: float | None
    soutenable: bool
    commentaire: str


def simuler(r: Ratios, dettes_lmt_existantes: float, montant: float, taux_annuel: float,
            duree_mois: int, duree_residuelle_existante_ans: float = 5.0,
            couverture_minimale: float = 1.25) -> ResultatSimulation:
    """Teste si la CAF couvre les annuités existantes et celle du nouveau prêt.

    Sans échéancier détaillé, le remboursement annuel des dettes existantes est
    approché par : dettes LMT / durée résiduelle moyenne (hypothèse à ajuster).
    """
    m = mensualite(montant, taux_annuel, duree_mois)
    annuite = m * 12
    interets = m * duree_mois - montant
    existantes = dettes_lmt_existantes / duree_residuelle_existante_ans if duree_residuelle_existante_ans else 0.0
    total = annuite + existantes
    couverture = r.caf / total if total else None
    cap_apres = (dettes_lmt_existantes + montant) / r.caf if r.caf > 0 else None

    soutenable = couverture is not None and couverture >= couverture_minimale
    if couverture is None or r.caf <= 0:
        commentaire = "CAF nulle ou négative : l'entreprise ne peut pas rembourser sur ses flux."
    elif soutenable:
        commentaire = (f"La CAF couvre {_v(couverture)} fois les annuités : marge de sécurité suffisante "
                       f"(seuil retenu {_v(couverture_minimale)}).")
    elif couverture >= 1:
        commentaire = (f"La CAF couvre les annuités ({_v(couverture)} x) mais sans marge suffisante : "
                       "allonger la durée, réduire le montant ou demander un apport.")
    else:
        commentaire = (f"La CAF ne couvre pas les annuités ({_v(couverture)} x) : le projet "
                       "dégraderait la trésorerie.")
    return ResultatSimulation(m, annuite, interets, existantes, couverture, cap_apres, soutenable, commentaire)
