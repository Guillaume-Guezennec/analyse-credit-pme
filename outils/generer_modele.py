"""Génère le modèle Excel vierge et l'exemple rempli.

Usage : python outils/generer_modele.py
  -> modeles/modele_liasse.xlsx      (modèle vierge à remplir)
  -> exemples/menuiserie_azur.xlsx   (exemple rempli à partir du fichier JSON)
"""

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from analyse_credit.export_excel import ecrire_classeur  # noqa: E402

if __name__ == "__main__":
    for chemin, dossier in (
        (RACINE / "modeles" / "modele_liasse.xlsx", None),
        (RACINE / "exemples" / "menuiserie_azur.xlsx",
         json.loads((RACINE / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))),
    ):
        ecrire_classeur(chemin, dossier)
        print(f"Fichier créé : {chemin.relative_to(RACINE)}")
