"""Commentaires automatiques : traduit l'évolution des ratios en constats rédigés.

Les règles sont volontairement simples et explicites, pour que chaque phrase
puisse être justifiée par un chiffre. Elles complètent l'analyse humaine sans la remplacer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .analyse import Ratios


@dataclass
class Constat:
    sens: str   # "positif", "vigilance" ou "negatif"
    texte: str


def _eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", " ")


def _dec(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _pts(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",")


def commenter(historique: list[Ratios]) -> list[Constat]:
    if not historique:
        return []
    d = historique[-1]
    p = historique[0] if len(historique) > 1 else None
    constats: list[Constat] = []

    # Activité et rentabilité
    if p and p.chiffre_affaires:
        var_ca = d.chiffre_affaires / p.chiffre_affaires - 1
        if p.ebe > 0 and d.ebe is not None:
            var_ebe = d.ebe / p.ebe - 1
            if var_ca > 0.02 and var_ebe < -0.10:
                constats.append(Constat("negatif",
                    f"Effet ciseaux : le chiffre d'affaires progresse de {_pts(var_ca)} entre {p.exercice} et {d.exercice}, "
                    f"mais l'EBE recule de {_pts(-var_ebe)}. Les charges augmentent plus vite que les ventes."))
            elif var_ca > 0.02 and var_ebe >= 0:
                constats.append(Constat("positif",
                    f"Croissance rentable : chiffre d'affaires +{_pts(var_ca)} et EBE {'+' if var_ebe >= 0 else ''}{_pts(var_ebe)} "
                    f"entre {p.exercice} et {d.exercice}."))
            elif var_ca < -0.05:
                constats.append(Constat("vigilance",
                    f"Activité en recul : chiffre d'affaires {_pts(var_ca)} entre {p.exercice} et {d.exercice}."))
    if d.ebe <= 0:
        constats.append(Constat("negatif", f"EBE négatif en {d.exercice} ({_eur(d.ebe)}) : l'activité ne couvre pas ses charges courantes."))
    elif d.taux_ebe is not None and d.taux_ebe < 0.04:
        constats.append(Constat("vigilance", f"Marge d'EBE faible en {d.exercice} ({_pts(d.taux_ebe)}) : peu de marge de manœuvre en cas de choc."))
    if d.resultat_net < 0:
        constats.append(Constat("negatif", f"Exercice {d.exercice} déficitaire ({_eur(d.resultat_net)})."))

    # Cycle d'exploitation
    if p and p.bfr_jours_ca is not None and d.bfr_jours_ca is not None and d.bfr_jours_ca - p.bfr_jours_ca >= 10:
        detail = ""
        if p.delai_clients_jours is not None and d.delai_clients_jours is not None and d.delai_clients_jours - p.delai_clients_jours >= 5:
            detail = (f" Principal facteur : le délai clients passe de {p.delai_clients_jours:.0f} à "
                      f"{d.delai_clients_jours:.0f} jours.")
        constats.append(Constat("vigilance",
            f"Le BFR s'alourdit : de {p.bfr_jours_ca:.0f} à {d.bfr_jours_ca:.0f} jours de chiffre d'affaires.{detail}"))

    # Trésorerie
    if d.tresorerie_nette < 0:
        constats.append(Constat("negatif",
            f"Trésorerie nette négative en {d.exercice} ({_eur(d.tresorerie_nette)}) : le BFR n'est plus couvert par le fonds de roulement "
            "et l'entreprise dépend de ses découverts."))
    elif d.tresorerie_nette > 0 and d.frng > 0:
        constats.append(Constat("positif", f"Trésorerie nette positive ({_eur(d.tresorerie_nette)}) : le fonds de roulement finance le BFR."))

    # Structure et endettement
    if d.autonomie_financiere is not None:
        if d.autonomie_financiere >= 0.30:
            constats.append(Constat("positif", f"Structure financière solide : capitaux propres à {_pts(d.autonomie_financiere)} du bilan."))
        elif d.autonomie_financiere < 0.15:
            constats.append(Constat("negatif", f"Fonds propres insuffisants : {_pts(d.autonomie_financiere)} du bilan seulement."))
    if d.capacite_remboursement is None:
        constats.append(Constat("negatif", "CAF nulle ou négative : l'entreprise ne peut pas rembourser ses dettes sur ses propres flux."))
    elif d.capacite_remboursement > 5:
        constats.append(Constat("negatif",
            f"Endettement élevé : {_dec(d.capacite_remboursement)} années de CAF pour rembourser les dettes financières (repère : moins de 3 à 4 ans)."))
    elif d.capacite_remboursement <= 3:
        constats.append(Constat("positif", f"Capacité de remboursement confortable : {_dec(d.capacite_remboursement)} années de CAF."))
    if d.poids_charges_financieres is not None and d.ebe > 0 and d.poids_charges_financieres > 0.30:
        constats.append(Constat("vigilance", f"Les intérêts absorbent {_pts(d.poids_charges_financieres)} de l'EBE."))

    return constats
