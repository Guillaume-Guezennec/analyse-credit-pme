"""Enchaînement complet : identité (annuaire) + comptes détaillés (INPI) -> dossier prêt à analyser.

Utilisé à la fois par la ligne de commande (recuperer.py) et par l'application web (app.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .annuaire import identite, nettoyer_siren
from .conversion_inpi import assembler
from .http import ErreurSource
from .inpi import ClientINPI

NB_DEPOTS_MAX = 4  # au-delà, les exercices sont trop anciens pour une analyse crédit


@dataclass
class Resultat:
    siren: str
    fiche: dict = field(default_factory=dict)
    complets: list[dict] = field(default_factory=list)
    incomplets: list[dict] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)
    effectif: int | None = None
    nb_depots: int = 0
    erreur_inpi: str | None = None

    @property
    def raison_sociale(self) -> str:
        return self.fiche.get("raison_sociale") or self.siren

    def dossier(self, inclure_incomplets: bool = True) -> dict:
        exercices = self.complets or (self.incomplets if inclure_incomplets else [])
        return {
            "entreprise": {
                "raison_sociale": self.raison_sociale,
                "activite": f"NAF {self.fiche['code_naf']}" if self.fiche.get("code_naf") else "",
                "code_naf": self.fiche.get("code_naf") or "",
                "effectif": self.effectif or self.fiche.get("tranche_effectif") or "",
            },
            "exercices": exercices,
        }


def comparer_avec_annuaire(exercices: list[dict], fiche: dict) -> list[str]:
    """Vérifie que le CA extrait correspond à celui publié par l'annuaire des entreprises."""
    alertes = []
    for e in exercices:
        publie = (fiche.get("finances") or {}).get(e["exercice"], {}).get("ca")
        calcule = e.get("ventes_marchandises", 0) + e.get("production_vendue", 0)
        if publie and calcule and abs(publie - calcule) > max(1000, 0.01 * publie):
            alertes.append(f"{e['exercice']} : chiffre d'affaires extrait ({calcule:,.0f} €) différent de celui "
                           f"de l'annuaire des entreprises ({publie:,.0f} €).".replace(",", " "))
    return alertes


def recuperer(siren: str, identifiants: tuple[str, str] | None,
              dossier_brut: Path | None = None) -> Resultat:
    """identifiants=None : seule l'identité est récupérée (pas de compte INPI disponible)."""
    siren = nettoyer_siren(siren)
    res = Resultat(siren)
    try:
        res.fiche = identite(siren)
    except ErreurSource as e:
        res.avertissements.append(f"Identité indisponible : {e}")

    if identifiants is None:
        res.erreur_inpi = "Comptes détaillés non récupérés : aucun identifiant INPI configuré."
        return res
    try:
        client = ClientINPI(*identifiants)
        depots = [d for d in client.liste_bilans_saisis(siren)
                  if (d.get("typeBilan") or "").upper() != "K"][:NB_DEPOTS_MAX]
    except ErreurSource as e:
        res.erreur_inpi = str(e)
        return res
    res.nb_depots = len(depots)
    if not depots:
        res.erreur_inpi = ("Aucun compte annuel saisi à l'INPI pour cette entreprise (comptes non déposés, "
                           "disponibles seulement en PDF, ou entreprise trop récente).")
        return res

    bilans = []
    for depot in depots:
        try:
            bilan = client.bilan_saisi(depot["id"])
        except ErreurSource as e:
            res.avertissements.append(f"Dépôt {depot.get('dateCloture')} illisible : {e}")
            continue
        if dossier_brut is not None:
            dossier_brut.mkdir(parents=True, exist_ok=True)
            (dossier_brut / f"inpi_{depot.get('dateCloture', depot['id'])}.json").write_text(
                json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
        bilans.append(bilan)

    res.complets, res.incomplets, avert, res.effectif = assembler(bilans)
    res.avertissements += avert + comparer_avec_annuaire(res.complets, res.fiche)
    return res
