# Modèle de prédiction des défaillances : rapport de validation

*Généré par `outils/entrainer_modele.py` le 19/11/2026.*

## Objectif et données

Estimer la probabilité qu'une PME fasse l'objet d'un **jugement d'ouverture de redressement ou de liquidation judiciaire dans les 24 mois** suivant la clôture de ses comptes.

- **Bilans** : base publique « Ratios financiers BCE/INPI » (data.economie.gouv.fr), comptes publics clos de 2019 à 2023, chiffre d'affaires de 0,1 à 100 M€. Un bilan par société et par année.
- **Défaillances** : annonces de procédures collectives publiées au BODACC (DILA) de 2019 à 2025.
- **Base finale** : 1,435,768 bilans, dont 15,353 suivis d'une défaillance (1.07 %). Les sociétés déjà en procédure à la date de clôture sont écartées.

## Méthode

Grille de score : chacun des 10 ratios est découpé en 10 tranches (déciles), plus une tranche « non disponible », et une régression logistique attribue un poids à chaque tranche. C'est la méthode usuelle des banques : elle capte les effets non linéaires tout en restant explicable ratio par ratio.

**Validation temporelle** : apprentissage sur les exercices 2019 à 2021 (925,175 bilans), test sur 2022 et 2023 (510,593 bilans), deux années que le modèle n'a jamais vues.

## Résultats sur les années de test

| Indicateur | Grille de score | Boosting d'arbres (comparaison) |
|---|---|---|
| AUC | 0.813 | 0.837 |
| Gini (2 × AUC − 1) | 0.625 | 0.674 |
| KS | 0.483 | 0.521 |
| Part des défaillances dans les 10 % de bilans les plus risqués | 44.3 % | 48.5 % |
| AUC précision-rappel | 0.062 | 0.079 |

**Lecture** : une AUC de 0,5 correspond au hasard, 1 à un classement parfait ; au-delà de 0,8, un score est généralement considéré comme bien discriminant. Le boosting d'arbres, plus complexe, ne gagne que quelques points : la grille de score, explicable ratio par ratio, est retenue.

Le taux prédit est inférieur au taux observé sur les années de test, car les défaillances ont fortement augmenté après les années d'apprentissage (fin des aides liées au Covid). C'est pourquoi la constante du modèle déployé est recalée sur le taux récent (voir plus bas).

## Classement par décile de risque (années de test)

| Décile (10 = plus risqué) | Bilans | Défaillances | Taux observé | Taux prédit | Part des défaillances |
|---|---|---|---|---|---|
| 10 | 51 060 | 3 313 | 6,49 % | 4,14 % | 44,3 % |
| 9 | 51 059 | 1 529 | 2,99 % | 1,53 % | 20,4 % |
| 8 | 51 059 | 963 | 1,89 % | 0,91 % | 12,9 % |
| 7 | 51 059 | 607 | 1,19 % | 0,61 % | 8,1 % |
| 6 | 51 059 | 388 | 0,76 % | 0,42 % | 5,2 % |
| 5 | 51 060 | 270 | 0,53 % | 0,30 % | 3,6 % |
| 4 | 51 059 | 171 | 0,33 % | 0,21 % | 2,3 % |
| 3 | 51 059 | 131 | 0,26 % | 0,14 % | 1,8 % |
| 2 | 51 059 | 78 | 0,15 % | 0,09 % | 1,0 % |
| 1 | 51 060 | 33 | 0,06 % | 0,04 % | 0,4 % |

## Modèle déployé

Le modèle utilisé dans l'application est réestimé sur l'ensemble des années, puis sa constante est recalée sur le taux de défaillance récent (1.47 % sur 2022-2023). Le fichier `analyse_credit/modele_defaillance.json` ne contient que les tranches et les poids, aucune donnée d'entreprise.

## Limites

- Les ratios de la base publique suivent leurs propres définitions ; ceux de l'outil en sont proches mais pas toujours identiques (par exemple, délais calculés hors taxes ou toutes taxes comprises). La probabilité affichée est donc un ordre de grandeur.
- Seules les entreprises qui publient leurs comptes sont couvertes. Les comptes confidentiels, fréquents chez les petites entreprises, sont absents.
- La période d'apprentissage inclut les années Covid, marquées par des aides publiques qui ont retardé de nombreuses défaillances.
- Un score de défaillance ne remplace pas l'analyse du dossier : il ignore le dirigeant, le marché, les garanties et l'historique bancaire.
