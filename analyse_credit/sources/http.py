"""Petites fonctions HTTP sans dépendance externe (bibliothèque standard uniquement)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

AGENT = "analyse-credit-pme (projet pédagogique open source)"


class ErreurSource(Exception):
    """Erreur lors de l'interrogation d'une source de données."""


def requete_json(url: str, methode: str = "GET", corps: dict | None = None,
                 entetes: dict | None = None, delai: float = 20.0, essais: int = 3):
    donnees = json.dumps(corps).encode("utf-8") if corps is not None else None
    tous_entetes = {"Accept": "application/json", "User-Agent": AGENT}
    if corps is not None:
        tous_entetes["Content-Type"] = "application/json"
    tous_entetes.update(entetes or {})

    for essai in range(1, essais + 1):
        req = urllib.request.Request(url, data=donnees, headers=tous_entetes, method=methode)
        try:
            with urllib.request.urlopen(req, timeout=delai) as reponse:
                return json.loads(reponse.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and essai < essais:  # trop de requêtes : on patiente puis on réessaie
                time.sleep(2 * essai)
                continue
            messages = {
                400: "requête incorrecte",
                401: "identifiants refusés ou session expirée",
                403: "accès refusé (habilitations insuffisantes)",
                404: "aucune donnée trouvée",
                429: "quota de requêtes dépassé, réessayez plus tard",
            }
            raise ErreurSource(f"{url} : erreur {e.code} ({messages.get(e.code, 'erreur du serveur')})") from None
        except urllib.error.URLError as e:
            if essai < essais:
                time.sleep(essai)
                continue
            raise ErreurSource(f"{url} : connexion impossible ({e.reason})") from None
    raise ErreurSource(f"{url} : échec après {essais} essais")
