# Analyse crédit automatisée de PME

Outil Python qui reproduit l'analyse financière d'un chargé d'affaires entreprises à partir des comptes annuels d'une PME française :

- **Soldes intermédiaires de gestion** (marge commerciale, valeur ajoutée, EBE, résultat d'exploitation, résultat net)
- **Capacité d'autofinancement** (méthode additive, vérifiée par la méthode soustractive dans les tests)
- **Bilan fonctionnel** : FRNG, BFR, trésorerie nette
- **Ratios bancaires** : autonomie financière, gearing, levier DFN/EBE, capacité de remboursement, délais clients et fournisseurs, liquidité
- **Notation du risque** de A à E, avec des feux tricolores par critère
- **Simulation d'un nouveau prêt** : mensualité, tableau d'amortissement, taux de couverture des annuités par la CAF

> Projet réalisé avec l'aide de Claude (Anthropic). Les seuils de notation sont des repères pédagogiques usuels : ils ne reproduisent la grille d'aucune banque et doivent être adaptés au secteur.

## Lancer l'analyse

Nécessite Python 3.10 ou plus récent.

```bash
pip install -r requirements.txt
python analyser.py exemples/menuiserie_azur.json
python -m pytest
```

## Structure

```
analyse_credit/
  modele.py           # postes de la liasse fiscale simplifiée
  analyse.py          # SIG, CAF, bilan fonctionnel, ratios
  scoring.py          # grille de notation et seuils (commentés)
  simulation_pret.py  # mensualités et soutenabilité d'un prêt
exemples/
  menuiserie_azur.json  # dossier fictif sur 3 exercices
tests/
```

## Feuille de route

- [x] Étape 1 : moteur d'analyse et notation
- [ ] Étape 2 : import depuis un modèle Excel de liasse fiscale
- [ ] Étape 3 : récupération automatique des comptes publics à partir du SIREN (INPI, API Recherche d'entreprises)
- [ ] Étape 4 : application web (Streamlit) avec graphiques
- [ ] Étape 5 : génération de la note de crédit en PDF
- [ ] Étape 6 : modèle de prédiction des défaillances (BODACC)

## Licence

MIT. Voir le fichier `LICENSE`.
