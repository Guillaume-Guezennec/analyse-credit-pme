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
import json
import re
import sys
from pathlib import Path

from analyse_credit.export_excel import ecrire_classeur
from analyse_credit.sources.annuaire import identite, nettoyer_siren
from analyse_credit.sources.conversion_inpi import assembler
from analyse_credit.sources.http import ErreurSource
from analyse_credit.sources.inpi import ClientINPI, lire_identifiants
from analyser import afficher_rapport

RACINE = Path(__file__).resolve().parent
NB_DEPOTS_MAX = 4  # au-delà, les exercices sont trop anciens pour une analyse crédit


def nom_fichier(texte: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", texte or "").strip("_")[:40] or "entreprise"


def comparer_avec_annuaire(exercices, fiche):
    """Vérifie que le CA extrait correspond à celui publié par l'annuaire des entreprises."""
    alertes = []
    for e in exercices:
        publie = (fiche.get("finances") or {}).get(e["exercice"], {}).get("ca")
        calcule = e.get("ventes_marchandises", 0) + e.get("production_vendue", 0)
        if publie and calcule and abs(publie - calcule) > max(1000, 0.01 * publie):
            alertes.append(f"{e['exercice']} : chiffre d'affaires extrait ({calcule:,.0f} €) différent de celui "
                           f"de l'annuaire des entreprises ({publie:,.0f} €).".replace(",", " "))
    return alertes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("siren", help="SIREN (9 chiffres) ou SIRET (14 chiffres)")
    parser.add_argument("--sans-analyse", action="store_true", help="crée seulement l'Excel")
    args = parser.parse_args()

    try:
        siren = nettoyer_siren(args.siren)
    except ValueError as e:
        sys.exit(f"❌ {e}")

    print(f"\n🔎 SIREN {siren}")

    # 1. Identité
    fiche = {}
    try:
        fiche = identite(siren)
        etat = "active" if fiche["active"] else "FERMÉE"
        print(f"   {fiche['raison_sociale']} — NAF {fiche['code_naf']} — {fiche['commune']} — {etat}")
        print(f"   Effectif : {fiche['tranche_effectif'] or 'non renseigné'}  |  Fiche : {fiche['lien']}")
    except ErreurSource as e:
        print(f"   ⚠️  Identité indisponible : {e}")

    # 2. Comptes INPI
    try:
        client = ClientINPI(*lire_identifiants(RACINE))
        depots = client.liste_bilans_saisis(siren)
    except ErreurSource as e:
        sys.exit(f"❌ {e}")

    depots = [d for d in depots if (d.get("typeBilan") or "").upper() != "K"][:NB_DEPOTS_MAX]
    if not depots:
        sys.exit("❌ Aucun compte annuel saisi n'est disponible à l'INPI pour cette entreprise "
                 "(comptes non déposés, déposés sous forme de PDF uniquement, ou entreprise trop récente).")
    print(f"   {len(depots)} dépôt(s) de comptes trouvé(s) à l'INPI")

    dossier_brut = RACINE / "dossiers" / siren
    dossier_brut.mkdir(parents=True, exist_ok=True)
    bilans = []
    for depot in depots:
        try:
            bilan = client.bilan_saisi(depot["id"])
        except ErreurSource as e:
            print(f"   ⚠️  Dépôt {depot.get('dateCloture')} illisible : {e}")
            continue
        (dossier_brut / f"inpi_{depot.get('dateCloture', depot['id'])}.json").write_text(
            json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
        bilans.append(bilan)

    complets, incomplets, avertissements, effectif = assembler(bilans)
    avertissements += comparer_avec_annuaire(complets, fiche)

    # 3. Excel pré-rempli (exercices complets en priorité, sinon exercices partiels à compléter)
    raison_sociale = fiche.get("raison_sociale") or (bilans[0].get("denomination") if bilans else None) or siren
    dossier = {
        "entreprise": {
            "raison_sociale": raison_sociale,
            "activite": f"NAF {fiche.get('code_naf')}" if fiche.get("code_naf") else "",
            "code_naf": fiche.get("code_naf") or "",
            "effectif": effectif or fiche.get("tranche_effectif") or "",
        },
        "exercices": complets or incomplets,
    }
    excel = ecrire_classeur(RACINE / "dossiers" / f"{siren}_{nom_fichier(raison_sociale)}.xlsx", dossier,
                            avertissements or None)
    print(f"\n📄 Excel créé : {excel.relative_to(RACINE)}")
    print(f"   Exercices complets : {', '.join(str(e['exercice']) for e in complets) or 'aucun'}")
    if incomplets:
        print(f"   Exercices incomplets : {', '.join(str(e['exercice']) for e in incomplets)}")

    if avertissements:
        print("\n⚠️  Points à vérifier (également listés dans l'onglet « À vérifier » de l'Excel) :")
        for a in avertissements:
            print(f"   • {a}")

    # 4. Analyse
    if args.sans_analyse:
        return
    if not complets:
        print("\nAnalyse impossible sans compte de résultat : complétez l'Excel puis lancez\n"
              f"   python analyser.py \"{excel.relative_to(RACINE)}\"")
        return
    afficher_rapport({"entreprise": dossier["entreprise"], "exercices": complets})


if __name__ == "__main__":
    main()
