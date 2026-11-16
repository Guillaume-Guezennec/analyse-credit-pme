"""Identité d'une entreprise via l'API Recherche d'entreprises (annuaire-entreprises.data.gouv.fr).

API publique de l'État, gratuite et sans clé. Elle fournit l'identité (nom, activité,
effectif, siège) et un résumé financier (chiffre d'affaires, résultat net) par année.
Documentation : https://recherche-entreprises.api.gouv.fr/docs/
"""

from __future__ import annotations

import urllib.parse

from .http import ErreurSource, requete_json

URL = "https://recherche-entreprises.api.gouv.fr/search"

TRANCHES_EFFECTIF = {
    "NN": "Non employeuse", "00": "0 salarié", "01": "1 ou 2 salariés", "02": "3 à 5 salariés",
    "03": "6 à 9 salariés", "11": "10 à 19 salariés", "12": "20 à 49 salariés",
    "21": "50 à 99 salariés", "22": "100 à 199 salariés", "31": "200 à 249 salariés",
    "32": "250 à 499 salariés", "41": "500 à 999 salariés", "42": "1 000 à 1 999 salariés",
    "51": "2 000 à 4 999 salariés", "52": "5 000 à 9 999 salariés", "53": "10 000 salariés et plus",
}


def nettoyer_siren(siren: str) -> str:
    """Retire espaces et points, puis vérifie le format et la clé de contrôle (algorithme de Luhn)."""
    s = "".join(ch for ch in str(siren) if ch.isdigit())
    if len(s) == 14:  # SIRET fourni : les 9 premiers chiffres forment le SIREN
        s = s[:9]
    if len(s) != 9:
        raise ValueError(f"SIREN invalide « {siren} » : il doit comporter 9 chiffres")
    total = 0
    for i, ch in enumerate(reversed(s)):
        n = int(ch) * (2 if i % 2 else 1)
        total += n - 9 if n > 9 else n
    if total % 10 != 0:
        raise ValueError(f"SIREN invalide « {siren} » : la clé de contrôle ne correspond pas")
    return s


def interpreter(resultat: dict) -> dict:
    """Transforme une réponse brute de l'API en fiche d'identité simplifiée."""
    siege = resultat.get("siege") or {}
    tranche = resultat.get("tranche_effectif_salarie")
    finances = {}
    for annee, valeurs in (resultat.get("finances") or {}).items():
        valeurs = valeurs or {}
        finances[int(annee)] = {
            "ca": valeurs.get("ca"),
            # L'API renvoie parfois 0 quand le résultat n'est pas publié : on le signale comme inconnu
            "resultat_net": valeurs.get("resultat_net") or None,
        }
    return {
        "siren": resultat.get("siren"),
        "raison_sociale": resultat.get("nom_raison_sociale") or resultat.get("nom_complet"),
        "code_naf": resultat.get("activite_principale"),
        "tranche_effectif": TRANCHES_EFFECTIF.get(tranche, tranche) if tranche else None,
        "date_creation": resultat.get("date_creation"),
        "active": resultat.get("etat_administratif") == "A",
        "categorie": resultat.get("categorie_entreprise"),
        "commune": siege.get("libelle_commune"),
        "code_postal": siege.get("code_postal"),
        "finances": dict(sorted(finances.items())),
        "lien": f"https://annuaire-entreprises.data.gouv.fr/entreprise/{resultat.get('siren')}",
    }


def identite(siren: str) -> dict:
    siren = nettoyer_siren(siren)
    reponse = requete_json(f"{URL}?{urllib.parse.urlencode({'q': siren, 'per_page': 1})}")
    for resultat in reponse.get("results", []):
        if resultat.get("siren") == siren:
            return interpreter(resultat)
    raise ErreurSource(f"Aucune entreprise trouvée pour le SIREN {siren}")
