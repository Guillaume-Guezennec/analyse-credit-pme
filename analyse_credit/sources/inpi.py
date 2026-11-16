"""Client de l'API comptes annuels de l'INPI (Registre national des entreprises).

Accès gratuit après création d'un compte sur https://data.inpi.fr
Documentation technique : « Accéder aux comptes annuels PDF et saisis », INPI, v4, mai 2024.

Les identifiants sont lus dans les variables d'environnement INPI_USERNAME et
INPI_PASSWORD, ou dans un fichier .env à la racine du projet (jamais publié sur GitHub).
"""

from __future__ import annotations

import os
from pathlib import Path

from .http import ErreurSource, requete_json

BASE = "https://registre-national-entreprises.inpi.fr"


def lire_identifiants(racine: Path | None = None) -> tuple[str, str]:
    utilisateur = os.environ.get("INPI_USERNAME")
    mot_de_passe = os.environ.get("INPI_PASSWORD")
    fichier = (racine or Path.cwd()) / ".env"
    if (not utilisateur or not mot_de_passe) and fichier.exists():
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            if "=" in ligne and not ligne.lstrip().startswith("#"):
                cle, valeur = ligne.split("=", 1)
                valeur = valeur.strip().strip('"').strip("'")
                if cle.strip() == "INPI_USERNAME":
                    utilisateur = utilisateur or valeur
                elif cle.strip() == "INPI_PASSWORD":
                    mot_de_passe = mot_de_passe or valeur
    if not utilisateur or not mot_de_passe:
        raise ErreurSource(
            "Identifiants INPI manquants. Créez un compte gratuit sur data.inpi.fr, puis un fichier .env "
            "à la racine du projet contenant :\nINPI_USERNAME=votre@email.fr\nINPI_PASSWORD=votre_mot_de_passe")
    return utilisateur, mot_de_passe


class ClientINPI:
    def __init__(self, utilisateur: str, mot_de_passe: str):
        reponse = requete_json(f"{BASE}/api/sso/login", methode="POST",
                               corps={"username": utilisateur, "password": mot_de_passe})
        self._jeton = reponse.get("token")
        if not self._jeton:
            raise ErreurSource("Connexion à l'INPI refusée : vérifiez vos identifiants")

    def _get(self, chemin: str):
        return requete_json(f"{BASE}{chemin}", entetes={"Authorization": f"Bearer {self._jeton}"})

    def liste_bilans_saisis(self, siren: str) -> list[dict]:
        """Liste des comptes annuels saisis disponibles, du plus récent au plus ancien."""
        documents = self._get(f"/api/companies/{siren}/attachments")
        bilans = [b for b in documents.get("bilansSaisis", []) if not b.get("deleted")]
        return sorted(bilans, key=lambda b: b.get("dateCloture") or "", reverse=True)

    def bilan_saisi(self, identifiant: str) -> dict:
        return self._get(f"/api/bilans-saisis/{identifiant}")
