"""Récupère les comptes publics d'une entreprise à partir de son SIREN, puis l'analyse.

Usage :
  python recuperer.py 552032534
  python recuperer.py "552 032 534" --sans-analyse

Étapes :
  1. Identité de l'entreprise (API Recherche d'entreprises, sans compte)
  2. Comptes annuels saisis par l'INPI (compte gratuit data.inpi.fr, identifiants dans .env)
  3. Création d'un Excel pré-rempli dans le dossier « dossiers/ » (non publié sur GitHub)
  4. Analyse crédit, si au moins un exercice complet est disponible

Les données brutes reçues de l'INPI sont conservées dans dossiers/<siren>/ pour vérification.
"""

import argparse
import re
import sys
from pathlib import Path

from analyse_credit.export_excel import ecrire_classeur
from analyse_credit.sources.annuaire import nettoyer_siren
from analyse_credit.sources.http import ErreurSource
from analyse_credit.sources.inpi import lire_identifiants
from analyse_credit.sources.pipeline import recuperer
from analyser import afficher_rapport

RACINE = Path(__file__).resolve().parent


def nom_fichier(texte: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", texte or "").strip("_")[:40] or "entreprise"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("siren", help="SIREN (9 chiffres) ou SIRET (14 chiffres)")
    parser.add_argument("--sans-analyse", action="store_true", help="crée seulement l'Excel")
    args = parser.parse_args()

    try:
        siren = nettoyer_siren(args.siren)
        identifiants = lire_identifiants(RACINE)
    except (ValueError, ErreurSource) as e:
        sys.exit(f"❌ {e}")

    print(f"\n🔎 SIREN {siren}")
    res = recuperer(siren, identifiants, RACINE / "dossiers" / siren)

    f = res.fiche
    if f:
        etat = "active" if f["active"] else "FERMÉE"
        print(f"   {f['raison_sociale']} — NAF {f['code_naf']} — {f['commune']} — {etat}")
        print(f"   Effectif : {f['tranche_effectif'] or 'non renseigné'}  |  Fiche : {f['lien']}")
    if res.erreur_inpi:
        sys.exit(f"❌ {res.erreur_inpi}")
    print(f"   {res.nb_depots} dépôt(s) de comptes trouvé(s) à l'INPI")

    dossier = res.dossier()
    excel = ecrire_classeur(RACINE / "dossiers" / f"{siren}_{nom_fichier(res.raison_sociale)}.xlsx", dossier,
                            res.avertissements or None)
    print(f"\n📄 Excel créé : {excel.relative_to(RACINE)}")
    print(f"   Exercices complets : {', '.join(str(e['exercice']) for e in res.complets) or 'aucun'}")
    if res.incomplets:
        print(f"   Exercices incomplets : {', '.join(str(e['exercice']) for e in res.incomplets)}")

    if res.avertissements:
        print("\n⚠️  Points à vérifier (également listés dans l'onglet « À vérifier » de l'Excel) :")
        for a in res.avertissements:
            print(f"   • {a}")

    if args.sans_analyse:
        return
    if not res.complets:
        print("\nAnalyse impossible sans compte de résultat : complétez l'Excel puis lancez\n"
              f"   python analyser.py \"{excel.relative_to(RACINE)}\"")
        return
    afficher_rapport(res.dossier(inclure_incomplets=False))


if __name__ == "__main__":
    main()
