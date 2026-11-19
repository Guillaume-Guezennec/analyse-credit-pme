"""Télécharge les données publiques nécessaires au modèle de prédiction des défaillances.

Usage (depuis le dossier du projet) :
    python3 outils/telecharger_donnees.py

Deux sources publiques et gratuites, sans compte :
  1. Ratios financiers (BCE / INPI), data.economie.gouv.fr : un bilan par société et par exercice.
  2. BODACC, annonces de procédures collectives (redressements, liquidations) publiées par la DILA.

Les fichiers sont enregistrés, compressés, dans le dossier « donnees/ » (exclu de GitHub).
Le téléchargement se fait par tranches annuelles : en cas de coupure, relancez simplement
la commande, les tranches déjà récupérées ne sont pas téléchargées à nouveau.
"""

from __future__ import annotations

import csv
import gzip
import io
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "donnees"
AGENT = "analyse-credit-pme (projet pédagogique open source)"

RATIOS = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/ratios_inpi_bce"
BODACC = "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales"

CHAMPS_RATIOS = [
    "siren", "date_cloture_exercice", "type_bilan", "confidentiality",
    "chiffre_d_affaires", "marge_brute", "ebe", "ebit", "resultat_net",
    "marge_ebe", "resultat_courant_avant_impots_sur_ca", "caf_sur_ca",
    "taux_d_endettement", "capacite_de_remboursement", "couverture_des_interets",
    "ratio_de_liquidite", "autonomie_financiere", "ratio_de_vetuste",
    "poids_bfr_exploitation_sur_ca_jours", "rotation_des_stocks_jours",
    "credit_clients_jours", "credit_fournisseurs_jours",
]
CHAMPS_BODACC = ["registre", "dateparution", "familleavis", "jugement"]

# Comptes clos de 2018 à 2023 ; défaillances publiées de 2019 à 2025 (fenêtre de 2 ans après la clôture)
ANNEES_RATIOS = range(2018, 2024)
ANNEES_BODACC = range(2019, 2026)
CA_MIN, CA_MAX = 100_000, 100_000_000  # PME et petites ETI


def journal(message: str):
    print(message, flush=True)


def ouvrir(url: str, delai: int = 900):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    return urllib.request.urlopen(req, timeout=delai)


def sonder(base: str, select: list[str], nom: str):
    """Vérifie que la source répond et que les champs attendus existent, avant le gros téléchargement."""
    url = f"{base}/records?" + urllib.parse.urlencode({"limit": 1, "select": ",".join(select)})
    try:
        with ouvrir(url, 60) as r:
            r.read()
        journal(f"  {nom} : source accessible, champs vérifiés")
    except Exception as e:
        sys.exit(f"\n❌ {nom} : la source ne répond pas comme prévu ({e}).\n"
                 "Vérifiez votre connexion internet, puis réessayez. Si l'erreur persiste, envoyez ce message à Claude.")


def exporter(base: str, where: str, select: list[str], fichier: Path, nom: str):
    if fichier.exists() and fichier.stat().st_size > 0:
        journal(f"  {nom} : déjà téléchargé ({fichier.stat().st_size // 1_000_000} Mo compressés)")
        return
    url = f"{base}/exports/csv?" + urllib.parse.urlencode(
        {"where": where, "select": ",".join(select), "delimiter": ";"})
    temporaire = fichier.with_suffix(".tmp")
    for essai in range(1, 6):
        try:
            debut, total = time.time(), 0
            with ouvrir(url) as r, gzip.open(temporaire, "wb") as sortie:
                while True:
                    morceau = r.read(1 << 20)
                    if not morceau:
                        break
                    sortie.write(morceau)
                    total += len(morceau)
                    print(f"\r  {nom} : {total // 1_000_000} Mo reçus ({time.time() - debut:.0f} s)", end="", flush=True)
            print()
            temporaire.replace(fichier)
            return
        except Exception as e:  # coupures réseau : on recommence
            print()
            journal(f"  {nom} : coupure ({e}), nouvel essai {essai}/5 dans {10 * essai} s…")
            time.sleep(10 * essai)
    sys.exit(f"❌ {nom} : téléchargement impossible après 5 essais. Relancez la commande plus tard.")


def compter_lignes(fichier: Path) -> int:
    with gzip.open(fichier, "rt", encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f, delimiter=";")) - 1


def main():
    DOSSIER.mkdir(exist_ok=True)
    journal("Vérification des sources…")
    sonder(RATIOS, CHAMPS_RATIOS, "Ratios financiers")
    sonder(BODACC, CHAMPS_BODACC, "BODACC")

    journal("\n1/2 Ratios financiers des entreprises (quelques minutes par année)")
    for annee in ANNEES_RATIOS:
        where = (f"date_cloture_exercice>=date'{annee}-01-01' and date_cloture_exercice<date'{annee + 1}-01-01' "
                 f"and chiffre_d_affaires>={CA_MIN} and chiffre_d_affaires<={CA_MAX} "
                 f"and (type_bilan='C' or type_bilan='S')")
        exporter(RATIOS, where, CHAMPS_RATIOS, DOSSIER / f"ratios_{annee}.csv.gz", f"Ratios {annee}")

    journal("\n2/2 Procédures collectives publiées au BODACC")
    for annee in ANNEES_BODACC:
        where = (f"familleavis='collective' and dateparution>=date'{annee}-01-01' "
                 f"and dateparution<date'{annee + 1}-01-01'")
        exporter(BODACC, where, CHAMPS_BODACC, DOSSIER / f"bodacc_{annee}.csv.gz", f"BODACC {annee}")

    journal("\nRésumé :")
    for f in sorted(DOSSIER.glob("*.csv.gz")):
        journal(f"  {f.name:24} {compter_lignes(f):>10,} lignes".replace(",", " "))
    journal("\n✅ Téléchargement terminé. Vous pouvez prévenir Claude.")


if __name__ == "__main__":
    main()
