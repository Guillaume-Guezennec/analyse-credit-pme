"""Lance l'analyse crédit d'un dossier JSON et affiche le rapport dans le terminal.

Usage : python analyser.py exemples/menuiserie_azur.json
        python analyser.py exemples/menuiserie_azur.xlsx
"""

import json
import sys

from analyse_credit import ComptesAnnuels, analyser_historique, noter, simuler
from analyse_credit.import_excel import lire_dossier


def eur(x):
    return "n.d." if x is None else f"{x:,.0f} €".replace(",", " ")


def pct(x):
    return "n.d." if x is None else f"{x * 100:.1f} %"


def nb(x, unite=""):
    return "n.d." if x is None else f"{x:.2f}{unite}"


def jours(x):
    return "n.d." if x is None else f"{x:.0f} j"


FEUX = {"vert": "🟢", "orange": "🟠", "rouge": "🔴"}


def main(chemin):
    if chemin.lower().endswith((".xlsx", ".xlsm")):
        dossier = lire_dossier(chemin)
    else:
        with open(chemin, encoding="utf-8") as f:
            dossier = json.load(f)

    exercices = [ComptesAnnuels.depuis_dict(e) for e in dossier["exercices"]]
    historique = analyser_historique(exercices)
    dernier = historique[-1]
    comptes_dernier = sorted(exercices, key=lambda e: e.exercice)[-1]

    print(f"\n=== {dossier['entreprise']['raison_sociale']} ===")
    print(dossier["entreprise"].get("activite") or "", "\n")

    lignes = [
        ("Chiffre d'affaires", "chiffre_affaires", eur),
        ("Croissance du CA", "croissance_ca", pct),
        ("EBE", "ebe", eur),
        ("Taux d'EBE", "taux_ebe", pct),
        ("Résultat net", "resultat_net", eur),
        ("CAF", "caf", eur),
        ("FRNG", "frng", eur),
        ("BFR", "bfr", eur),
        ("BFR en jours de CA", "bfr_jours_ca", jours),
        ("Trésorerie nette", "tresorerie_nette", eur),
        ("Dette financière nette", "dette_financiere_nette", eur),
        ("Autonomie financière", "autonomie_financiere", pct),
        ("Gearing (DFN / CP)", "gearing", nb),
        ("Levier DFN / EBE", "levier_dfn_ebe", lambda x: nb(x, " ans")),
        ("Capacité de remboursement", "capacite_remboursement", lambda x: nb(x, " ans")),
        ("Frais financiers / EBE", "poids_charges_financieres", pct),
        ("Délai clients", "delai_clients_jours", jours),
        ("Délai fournisseurs", "delai_fournisseurs_jours", jours),
        ("Liquidité générale", "liquidite_generale", nb),
    ]
    entete = f"{'':30}" + "".join(f"{r.exercice:>16}" for r in historique)
    print(entete)
    print("-" * len(entete))
    for libelle, attr, fmt in lignes:
        print(f"{libelle:30}" + "".join(f"{fmt(getattr(r, attr)):>16}" for r in historique))

    notation = noter(dernier)
    print(f"\n--- Notation {dernier.exercice} : {notation.note} ({notation.score}/100) — {notation.libelle}")
    for d in notation.details:
        print(f"  {FEUX[d.feu]} {d.critere.nom:28} {d.points:5.1f} / {d.critere.poids}")

    demande = dossier.get("demande_credit")
    if demande:
        dettes_lmt = comptes_dernier.emprunts_bancaires + comptes_dernier.autres_dettes_financieres
        s = simuler(dernier, dettes_lmt, demande["montant"], demande["taux_annuel"], demande["duree_mois"])
        print(f"\n--- Demande : {demande['objet']}")
        print(f"  {eur(demande['montant'])} sur {demande['duree_mois']} mois à {demande['taux_annuel'] * 100:.2f} %")
        print(f"  Mensualité : {eur(s.mensualite)}  |  coût des intérêts : {eur(s.cout_total_interets)}")
        print(f"  Annuités totales estimées : {eur(s.annuite_nouveau_pret + s.annuites_existantes_estimees)}")
        print(f"  Capacité de remboursement après prêt : {nb(s.capacite_remboursement_apres, ' ans')}")
        print(f"  {'✅' if s.soutenable else '⚠️'}  {s.commentaire}\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "exemples/menuiserie_azur.json")
