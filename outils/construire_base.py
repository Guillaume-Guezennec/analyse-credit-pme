"""Construit la base d'apprentissage du modèle de défaillance à partir des fichiers de « donnees/ ».

Usage : python3 outils/construire_base.py   (après outils/telecharger_donnees.py)

Une ligne = un bilan (une société, un exercice). La cible vaut 1 si un jugement d'ouverture de
redressement ou de liquidation judiciaire est prononcé dans les 24 mois qui suivent la date de clôture.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "donnees"
HORIZON_MOIS = 24
ANNEES_CIBLES = range(2019, 2024)   # exercices utilisables (2018 sert seulement à calculer la croissance)

NATURES_DEFAILLANCE = (
    "Jugement d'ouverture de liquidation judiciaire",
    "Jugement d'ouverture d'une procédure de redressement judiciaire",
)


def charger_ratios() -> pd.DataFrame:
    morceaux = []
    for f in sorted(DONNEES.glob("ratios_*.csv.gz")):
        d = pd.read_csv(f, sep=";", dtype={"siren": str})
        morceaux.append(d)
    r = pd.concat(morceaux, ignore_index=True)
    r = r[r["confidentiality"] == "Public"].copy()
    r["date_cloture"] = pd.to_datetime(r["date_cloture_exercice"], errors="coerce")
    r = r.dropna(subset=["date_cloture"])
    # Exercice clos en début d'année : rattaché à l'année précédente
    r["annee"] = r["date_cloture"].dt.year - (r["date_cloture"].dt.month <= 3).astype(int)
    # Un bilan par société et par année, de préférence le bilan complet
    r["rang"] = r["type_bilan"].map({"C": 0, "S": 1}).fillna(2)
    r = r.sort_values(["siren", "annee", "rang", "date_cloture"]).drop_duplicates(["siren", "annee"], keep="first")
    return r.drop(columns=["rang"])


def charger_defaillances() -> pd.DataFrame:
    lignes = []
    for f in sorted(DONNEES.glob("bodacc_*.csv.gz")):
        d = pd.read_csv(f, sep=";", dtype=str, usecols=["registre", "dateparution", "jugement"])
        for registre, parution, jugement in d.itertuples(index=False):
            if not isinstance(jugement, str) or "ouverture" not in jugement:
                continue
            try:
                j = json.loads(jugement)
            except ValueError:
                continue
            if j.get("nature") not in NATURES_DEFAILLANCE or not isinstance(registre, str):
                continue
            siren = "".join(ch for ch in registre.split(",")[-1] if ch.isdigit())
            if len(siren) == 9:
                lignes.append((siren, j.get("date") or parution))
    d = pd.DataFrame(lignes, columns=["siren", "date_jugement"])
    d["date_jugement"] = pd.to_datetime(d["date_jugement"], errors="coerce")
    return d.dropna().drop_duplicates()


def construire() -> pd.DataFrame:
    r = charger_ratios()
    print(f"Bilans publics retenus : {len(r):,}".replace(",", " "))

    # Croissance du chiffre d'affaires par rapport à l'exercice précédent de la même société
    prec = r[["siren", "annee", "chiffre_d_affaires"]].copy()
    prec["annee"] += 1
    r = r.merge(prec.rename(columns={"chiffre_d_affaires": "ca_precedent"}), on=["siren", "annee"], how="left")
    r["croissance_ca"] = np.where(r["ca_precedent"] > 0, (r["chiffre_d_affaires"] / r["ca_precedent"] - 1) * 100, np.nan)

    r = r[r["annee"].isin(ANNEES_CIBLES)].copy()

    defaillances = charger_defaillances()
    print(f"Jugements d'ouverture (redressement ou liquidation) : {len(defaillances):,}".replace(",", " "))
    jointure = r[["siren", "annee", "date_cloture"]].merge(defaillances, on="siren", how="inner")
    fin = jointure["date_cloture"] + pd.DateOffset(months=HORIZON_MOIS)
    dans_fenetre = (jointure["date_jugement"] > jointure["date_cloture"]) & (jointure["date_jugement"] <= fin)
    positifs = jointure[dans_fenetre][["siren", "annee"]].drop_duplicates()
    positifs["defaillance"] = 1
    r = r.merge(positifs, on=["siren", "annee"], how="left")
    r["defaillance"] = r["defaillance"].fillna(0).astype(int)

    # Une société déjà en procédure à la clôture n'est pas un cas de prédiction : on l'écarte
    anterieurs = jointure[jointure["date_jugement"] <= jointure["date_cloture"]][["siren", "annee"]].drop_duplicates()
    anterieurs["deja"] = 1
    r = r.merge(anterieurs, on=["siren", "annee"], how="left")
    r = r[r["deja"].isna()].drop(columns=["deja"])

    r["rn_sur_ca"] = np.where(r["chiffre_d_affaires"] > 0, r["resultat_net"] / r["chiffre_d_affaires"] * 100, np.nan)
    r["log_ca"] = np.log10(r["chiffre_d_affaires"].clip(lower=1))
    return r


if __name__ == "__main__":
    base = construire()
    sortie = DONNEES / "base_apprentissage.parquet"
    base.to_parquet(sortie, index=False)
    print(f"\nBase : {len(base):,} bilans, dont {base['defaillance'].sum():,} suivis d'une défaillance "
          f"({base['defaillance'].mean() * 100:.2f} %)".replace(",", " "))
    print(base.groupby("annee")["defaillance"].agg(["count", "sum", "mean"]).round(4).to_string())
    print(f"Enregistrée dans {sortie.relative_to(RACINE)}")
