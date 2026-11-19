"""Télécharge les indicateurs sectoriels financiers (BCE / INPI) publiés par Bercy.

Usage (depuis le dossier du projet) :
    python3 outils/telecharger_secteurs.py

Ces données donnent, pour chaque secteur d'activité, tranche de chiffre d'affaires et année,
la distribution (percentiles) de chaque ratio financier. Elles permettent de situer une
entreprise par rapport à des entreprises comparables.
Le fichier est enregistré, compressé, dans « donnees/secteurs.csv.gz » (exclu de GitHub).
"""

from __future__ import annotations

import gzip
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "donnees"
SOURCE = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/ratios_inpi_bce_sectors"
AGENT = "analyse-credit-pme (projet pédagogique open source)"


def main():
    DOSSIER.mkdir(exist_ok=True)
    fichier = DOSSIER / "secteurs.csv.gz"
    url = f"{SOURCE}/exports/csv?" + urllib.parse.urlencode({"delimiter": ";"})
    print("Téléchargement des indicateurs sectoriels…", flush=True)
    for essai in range(1, 6):
        try:
            debut, total = time.time(), 0
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=900) as r, gzip.open(fichier.with_suffix(".tmp"), "wb") as sortie:
                while True:
                    morceau = r.read(1 << 20)
                    if not morceau:
                        break
                    sortie.write(morceau)
                    total += len(morceau)
                    print(f"\r  {total // 1_000_000} Mo reçus ({time.time() - debut:.0f} s)", end="", flush=True)
            print()
            fichier.with_suffix(".tmp").replace(fichier)
            break
        except Exception as e:  # coupures réseau : on recommence
            print(f"\n  coupure ({e}), nouvel essai {essai}/5 dans {10 * essai} s…", flush=True)
            time.sleep(10 * essai)
    else:
        sys.exit("❌ Téléchargement impossible après 5 essais. Relancez la commande plus tard.")

    with gzip.open(fichier, "rt", encoding="utf-8-sig") as f:
        entete = f.readline().strip()
        lignes = sum(1 for _ in f)
    print(f"\nColonnes : {entete[:300]}")
    print(f"Lignes   : {lignes:,}".replace(",", " "))
    print("\n✅ Téléchargement terminé. Vous pouvez prévenir Claude.")


if __name__ == "__main__":
    main()
