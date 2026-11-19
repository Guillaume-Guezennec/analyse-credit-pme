"""Entraîne le modèle de prédiction des défaillances et mesure sa fiabilité.

Usage : python3 outils/entrainer_modele.py   (après outils/construire_base.py)

Méthode : grille de score, l'approche classique en banque. Chaque ratio est découpé en tranches
(déciles calculés sur la base d'apprentissage) ; une régression logistique attribue un poids à
chaque tranche. Le modèle reste ainsi lisible ratio par ratio, et il capte les effets non linéaires
(une liquidité trop faible est risquée, une liquidité très élevée ne l'est pas davantage).

Validation temporelle : apprentissage sur les exercices 2019 à 2021, test sur 2022 et 2023, des
années que le modèle n'a jamais vues. Un modèle de boosting d'arbres sert de point de comparaison.

Sorties :
  analyse_credit/modele_defaillance.json   paramètres du modèle (sans donnée d'entreprise)
  docs/modele_defaillance.md               rapport de validation
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

RACINE = Path(__file__).resolve().parent.parent
BASE = RACINE / "donnees" / "base_apprentissage.parquet"

VARIABLES = {
    # nom dans la base : (libellé, unité)
    "marge_ebe": ("Marge d'EBE (EBE / CA)", "%"),
    "rn_sur_ca": ("Rentabilité nette (résultat net / CA)", "%"),
    "autonomie_financiere": ("Autonomie financière", "%"),
    "taux_d_endettement": ("Endettement (dettes financières / capitaux propres)", "%"),
    "ratio_de_liquidite": ("Liquidité générale", "%"),
    "poids_bfr_exploitation_sur_ca_jours": ("BFR d'exploitation", "jours de CA"),
    "credit_clients_jours": ("Délai clients", "jours"),
    "credit_fournisseurs_jours": ("Délai fournisseurs", "jours"),
    "croissance_ca": ("Croissance du chiffre d'affaires", "%"),
    "log_ca": ("Taille de l'entreprise", "log10 du CA"),
}
# Ratios écartés car redondants avec la marge d'EBE et la rentabilité nette : CAF / CA et capacité de
# remboursement. Avec eux, certains poids changeaient de sens et devenaient impossibles à expliquer.
PLANCHERS = {"autonomie_financiere": 0.0}  # le risque des capitaux propres négatifs est porté par l'endettement
NB_TRANCHES = 10
ANNEES_APPRENTISSAGE = (2019, 2020, 2021)
ANNEES_TEST = (2022, 2023)


# ----------------------------------------------------------------------------- grille de score

def bornes(serie: pd.Series) -> list[float]:
    q = serie.dropna().quantile(np.linspace(0, 1, NB_TRANCHES + 1)[1:-1]).round(4)
    return sorted(set(float(x) for x in q))


def encoder(df: pd.DataFrame, grille: dict) -> np.ndarray:
    """Une colonne par tranche (plus une tranche « non disponible ») et par variable."""
    lignes, colonnes, decalage = [], [], 0
    n = len(df)
    for var, b in grille.items():
        x = df[var].to_numpy(dtype=float)
        idx = np.where(np.isnan(x), len(b) + 1, np.searchsorted(b, x, side="right"))
        lignes.append(np.arange(n))
        colonnes.append(idx + decalage)
        decalage += len(b) + 2
    lignes, colonnes = np.concatenate(lignes), np.concatenate(colonnes)
    # Matrice creuse : une seule tranche active par variable, ce qui économise beaucoup de mémoire
    return sparse.csr_matrix((np.ones(len(lignes), dtype=np.float32), (lignes, colonnes)), shape=(n, decalage))


def ajuster_grille(train: pd.DataFrame):
    grille = {v: bornes(train[v]) for v in VARIABLES}
    modele = LogisticRegression(C=0.3, max_iter=3000, solver="lbfgs")
    modele.fit(encoder(train, grille), train["defaillance"])
    return grille, modele


def poids_par_variable(grille, modele) -> dict:
    coefs, i, sortie = modele.coef_[0], 0, {}
    for var, b in grille.items():
        n = len(b) + 2
        sortie[var] = [round(float(c), 5) for c in coefs[i:i + n]]
        i += n
    return sortie


# ----------------------------------------------------------------------------- indicateurs

def mesures(y, p) -> dict:
    auc = roc_auc_score(y, p)
    seuil = np.quantile(p, 0.9)
    ordre = np.argsort(-p)
    cumul = np.cumsum(y[ordre]) / y.sum()
    faux = np.cumsum(1 - y[ordre]) / (1 - y).sum()
    return {
        "auc": round(float(auc), 4),
        "gini": round(float(2 * auc - 1), 4),
        "ks": round(float(np.max(cumul - faux)), 4),
        "auc_pr": round(float(average_precision_score(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 5),
        "capture_10pct": round(float(y[p >= seuil].sum() / y.sum()), 4),
        "taux_observe": round(float(y.mean()), 5),
        "taux_predit": round(float(p.mean()), 5),
    }


def deciles(y, p) -> pd.DataFrame:
    d = pd.DataFrame({"y": y, "p": p})
    d["decile"] = pd.qcut(d["p"].rank(method="first"), 10, labels=range(1, 11))
    t = d.groupby("decile", observed=True).agg(bilans=("y", "size"), defaillances=("y", "sum"),
                                               taux_observe=("y", "mean"), taux_predit=("p", "mean"))
    t["part_des_defaillances"] = t["defaillances"] / t["defaillances"].sum()
    return t


# ----------------------------------------------------------------------------- programme

def main():
    base = pd.read_parquet(BASE)
    base = base.replace([np.inf, -np.inf], np.nan)
    for var, plancher in PLANCHERS.items():
        base[var] = base[var].clip(lower=plancher)
    train = base[base["annee"].isin(ANNEES_APPRENTISSAGE)]
    test = base[base["annee"].isin(ANNEES_TEST)]
    print(f"Apprentissage : {len(train):,} bilans ({train.defaillance.sum():,} défaillances)".replace(",", " "))
    print(f"Test          : {len(test):,} bilans ({test.defaillance.sum():,} défaillances)".replace(",", " "))

    grille, logit = ajuster_grille(train)
    p_logit = logit.predict_proba(encoder(test, grille))[:, 1]

    hgb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
                                         min_samples_leaf=200, l2_regularization=1.0, random_state=0)
    hgb.fit(train[list(VARIABLES)], train["defaillance"])
    p_hgb = hgb.predict_proba(test[list(VARIABLES)])[:, 1]

    y = test["defaillance"].to_numpy()
    m_logit, m_hgb = mesures(y, p_logit), mesures(y, p_hgb)
    par_annee = {a: mesures(test.loc[test.annee == a, "defaillance"].to_numpy(), p_logit[test.annee.to_numpy() == a])
                 for a in ANNEES_TEST}
    print("Grille de score :", m_logit)
    print("Boosting        :", m_hgb)

    # Modèle final : réestimé sur toutes les années, puis constante recalée sur le taux récent (2022-2023)
    grille_f, logit_f = ajuster_grille(base)
    X = encoder(base, grille_f)
    taux_recent = test["defaillance"].mean()
    p_recent = logit_f.predict_proba(encoder(test, grille_f))[:, 1]
    lo = lambda q: np.log(q / (1 - q))
    decalage = float(lo(taux_recent) - lo(p_recent.mean()))
    constante = float(logit_f.intercept_[0] + decalage)

    # Contribution de référence d'une variable : moyenne de ses poids pondérée par la population
    poids = poids_par_variable(grille_f, logit_f)
    reference, i = {}, 0
    for var, b in grille_f.items():
        n = len(b) + 2
        reference[var] = round(float((np.asarray(X[:, i:i + n].mean(axis=0)).ravel() * np.array(poids[var])).sum()), 5)
        i += n

    t_dec = deciles(y, p_logit)
    modele = {
        "description": "Grille de score de défaillance à 24 mois (ouverture de redressement ou de liquidation "
                       "judiciaire), PME françaises de 0,1 à 100 M€ de chiffre d'affaires.",
        "sources": ["Ratios financiers BCE/INPI (data.economie.gouv.fr)", "BODACC, procédures collectives (DILA)"],
        "date_entrainement": date.today().isoformat(),
        "nb_bilans": int(len(base)), "nb_defaillances": int(base["defaillance"].sum()),
        "taux_reference": round(float(taux_recent), 5),
        "constante": round(constante, 5),
        "variables": {v: {"libelle": VARIABLES[v][0], "unite": VARIABLES[v][1], "bornes": grille_f[v],
                          "poids": poids[v], "reference": reference[v], "plancher": PLANCHERS.get(v)} for v in VARIABLES},
        "validation": {"apprentissage": list(ANNEES_APPRENTISSAGE), "test": list(ANNEES_TEST),
                       "grille_de_score": m_logit, "boosting_comparaison": m_hgb,
                       "par_annee": {str(k): v for k, v in par_annee.items()},
                       "deciles": [{"decile": int(d), "bilans": int(r.bilans), "defaillances": int(r.defaillances),
                                    "taux_observe": round(float(r.taux_observe), 5)} for d, r in t_dec.iterrows()]},
    }
    (RACINE / "analyse_credit" / "modele_defaillance.json").write_text(
        json.dumps(modele, ensure_ascii=False, indent=1), encoding="utf-8")

    # Rapport
    t = t_dec
    lignes_dec = "\n".join(
        f"| {int(d)} | {int(r.bilans):,} | {int(r.defaillances):,} | {r.taux_observe * 100:.2f} % | {r.taux_predit * 100:.2f} % "
        f"| {r.part_des_defaillances * 100:.1f} % |".replace(",", " ").replace(".", ",")
        for d, r in t.iloc[::-1].iterrows())
    pct = lambda x: f"{x * 100:.1f} %"
    rapport = f"""# Modèle de prédiction des défaillances : rapport de validation

*Généré par `outils/entrainer_modele.py` le {date.today().strftime('%d/%m/%Y')}.*

## Objectif et données

Estimer la probabilité qu'une PME fasse l'objet d'un **jugement d'ouverture de redressement ou de liquidation judiciaire dans les 24 mois** suivant la clôture de ses comptes.

- **Bilans** : base publique « Ratios financiers BCE/INPI » (data.economie.gouv.fr), comptes publics clos de 2019 à 2023, chiffre d'affaires de 0,1 à 100 M€. Un bilan par société et par année.
- **Défaillances** : annonces de procédures collectives publiées au BODACC (DILA) de 2019 à 2025.
- **Base finale** : {len(base):,} bilans, dont {int(base['defaillance'].sum()):,} suivis d'une défaillance ({base['defaillance'].mean() * 100:.2f} %). Les sociétés déjà en procédure à la date de clôture sont écartées.

## Méthode

Grille de score : chacun des {len(VARIABLES)} ratios est découpé en {NB_TRANCHES} tranches (déciles), plus une tranche « non disponible », et une régression logistique attribue un poids à chaque tranche. C'est la méthode usuelle des banques : elle capte les effets non linéaires tout en restant explicable ratio par ratio.

**Validation temporelle** : apprentissage sur les exercices {ANNEES_APPRENTISSAGE[0]} à {ANNEES_APPRENTISSAGE[-1]} ({len(train):,} bilans), test sur {ANNEES_TEST[0]} et {ANNEES_TEST[-1]} ({len(test):,} bilans), deux années que le modèle n'a jamais vues.

## Résultats sur les années de test

| Indicateur | Grille de score | Boosting d'arbres (comparaison) |
|---|---|---|
| AUC | {m_logit['auc']:.3f} | {m_hgb['auc']:.3f} |
| Gini (2 × AUC − 1) | {m_logit['gini']:.3f} | {m_hgb['gini']:.3f} |
| KS | {m_logit['ks']:.3f} | {m_hgb['ks']:.3f} |
| Part des défaillances dans les 10 % de bilans les plus risqués | {pct(m_logit['capture_10pct'])} | {pct(m_hgb['capture_10pct'])} |
| AUC précision-rappel | {m_logit['auc_pr']:.3f} | {m_hgb['auc_pr']:.3f} |

**Lecture** : une AUC de 0,5 correspond au hasard, 1 à un classement parfait ; au-delà de 0,8, un score est généralement considéré comme bien discriminant. Le boosting d'arbres, plus complexe, ne gagne que quelques points : la grille de score, explicable ratio par ratio, est retenue.

Le taux prédit est inférieur au taux observé sur les années de test, car les défaillances ont fortement augmenté après les années d'apprentissage (fin des aides liées au Covid). C'est pourquoi la constante du modèle déployé est recalée sur le taux récent (voir plus bas).

## Classement par décile de risque (années de test)

| Décile (10 = plus risqué) | Bilans | Défaillances | Taux observé | Taux prédit | Part des défaillances |
|---|---|---|---|---|---|
{lignes_dec}

## Modèle déployé

Le modèle utilisé dans l'application est réestimé sur l'ensemble des années, puis sa constante est recalée sur le taux de défaillance récent ({taux_recent * 100:.2f} % sur 2022-2023). Le fichier `analyse_credit/modele_defaillance.json` ne contient que les tranches et les poids, aucune donnée d'entreprise.

## Limites

- Les ratios de la base publique suivent leurs propres définitions ; ceux de l'outil en sont proches mais pas toujours identiques (par exemple, délais calculés hors taxes ou toutes taxes comprises). La probabilité affichée est donc un ordre de grandeur.
- Seules les entreprises qui publient leurs comptes sont couvertes. Les comptes confidentiels, fréquents chez les petites entreprises, sont absents.
- La période d'apprentissage inclut les années Covid, marquées par des aides publiques qui ont retardé de nombreuses défaillances.
- Un score de défaillance ne remplace pas l'analyse du dossier : il ignore le dirigeant, le marché, les garanties et l'historique bancaire.
"""
    (RACINE / "docs" / "modele_defaillance.md").write_text(rapport, encoding="utf-8")
    print("\n" + t.round(4).to_string())
    print("\nModèle et rapport enregistrés.")


if __name__ == "__main__":
    main()
