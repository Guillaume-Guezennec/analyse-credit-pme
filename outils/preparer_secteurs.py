"""Prépare le fichier compact des références sectorielles utilisé par l'application.

Usage : python3 outils/preparer_secteurs.py   (après outils/telecharger_secteurs.py)

Pour chaque groupe d'entreprises comparables (code NAF à un niveau donné × tranche de chiffre
d'affaires), on garde l'exercice le plus récent qui compte au moins 100 entreprises (à défaut,
le plus récent disponible), et seulement les ratios utilisés par l'outil.
Sortie : analyse_credit/secteurs.csv.gz (quelques centaines de Ko, publié avec le code).
"""

from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
RATIOS = ["marge_ebe", "part_ca_resultat_net", "caf_sur_ca", "autonomie_financiere", "taux_d_endettement",
          "capacite_de_remboursement", "ratio_de_liquidite", "poids_bfr_exploitation_sur_ca_jours",
          "credit_clients_jours", "credit_fournisseurs_jours"]
QUANTILES = ["q10", "q25", "q50", "q75", "q90"]

if __name__ == "__main__":
    d = pd.read_csv(RACINE / "donnees" / "secteurs.csv.gz", sep=";", dtype={"classe_naf": str})
    d["solide"] = d["cohorte"] >= 100
    d = d.sort_values(["classe_naf", "classe_ca", "solide", "exercice"])
    d = d.groupby(["classe_naf", "classe_ca"], as_index=False).tail(1)
    colonnes = ["classe_naf", "classe_ca", "exercice", "cohorte"] + [f"{r}_{q}" for r in RATIOS for q in QUANTILES]
    sortie = RACINE / "analyse_credit" / "secteurs.csv.gz"
    d[colonnes].sort_values(["classe_naf", "classe_ca"]).to_csv(sortie, sep=";", index=False, compression="gzip")
    print(f"{len(d)} groupes enregistrés dans {sortie.relative_to(RACINE)} ({sortie.stat().st_size // 1000} Ko)")
    print(d["exercice"].value_counts().sort_index().to_string())
