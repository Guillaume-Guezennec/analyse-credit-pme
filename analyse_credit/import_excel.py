"""Lecture du modèle Excel de liasse fiscale simplifiée (modeles/modele_liasse.xlsx).

Chaque ligne utile porte un code dans la colonne A (masquée) : le programme se
repère grâce à ces codes, et non grâce à la position des lignes. On peut donc
ajouter des lignes vides ou des commentaires sans casser l'import.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .postes import CODES_POSTES, INFOS_DEMANDE, INFOS_ENTREPRISE

FEUILLE_DOSSIER = "Dossier"
FEUILLE_COMPTES = "Comptes"
PREMIERE_COLONNE_EXERCICE = 3  # colonne C
NB_EXERCICES_MAX = 3  # colonnes C, D et E


def _nombre(valeur, ou: str) -> float:
    if valeur is None or valeur == "":
        return 0.0
    if isinstance(valeur, (int, float)):
        return float(valeur)
    texte = str(valeur).replace(" ", "").replace("\xa0", "").replace(" ", "").replace("€", "").replace(",", ".")
    try:
        return float(texte)
    except ValueError:
        raise ValueError(f"Valeur non numérique « {valeur} » ({ou})") from None


def lire_dossier(chemin: str | Path) -> dict:
    """Renvoie un dictionnaire au même format que les fichiers JSON d'exemple."""
    classeur = load_workbook(chemin, data_only=True)
    for nom in (FEUILLE_DOSSIER, FEUILLE_COMPTES):
        if nom not in classeur.sheetnames:
            raise ValueError(f"Onglet « {nom} » introuvable : utilisez le modèle modeles/modele_liasse.xlsx")

    # --- Onglet Dossier : codes en colonne A, valeurs en colonne C
    infos = {}
    for ligne in classeur[FEUILLE_DOSSIER].iter_rows(min_col=1, max_col=3, values_only=True):
        code, _, valeur = ligne
        if code:
            infos[str(code)] = valeur

    entreprise = {code: infos.get(code) for code, _, _ in INFOS_ENTREPRISE}
    if not entreprise.get("raison_sociale"):
        raise ValueError("La raison sociale n'est pas renseignée (onglet Dossier)")

    demande = None
    if infos.get("montant"):
        demande = {}
        for code, libelle, nature in INFOS_DEMANDE:
            v = infos.get(code)
            if nature == "texte":
                demande[code] = v or ""
            else:
                demande[code] = _nombre(v, f"Dossier, {libelle}")
        if demande["taux_annuel"] > 1:  # saisi « 4,2 » au lieu de « 4,2 % »
            demande["taux_annuel"] /= 100
        demande["duree_mois"] = int(demande["duree_mois"])
        if demande["duree_mois"] <= 0:
            raise ValueError("La durée du prêt doit être supérieure à 0 mois (onglet Dossier)")

    # --- Onglet Comptes : une colonne par exercice
    feuille = classeur[FEUILLE_COMPTES]
    lignes = {}
    for ligne in feuille.iter_rows(min_col=1, max_col=PREMIERE_COLONNE_EXERCICE + NB_EXERCICES_MAX - 1):
        code = ligne[0].value
        if code:
            lignes[str(code)] = ligne

    if "exercice" not in lignes:
        raise ValueError("Ligne des exercices introuvable dans l'onglet Comptes")

    exercices = []
    for i in range(PREMIERE_COLONNE_EXERCICE - 1, PREMIERE_COLONNE_EXERCICE - 1 + NB_EXERCICES_MAX):
        annee = lignes["exercice"][i].value
        if annee in (None, ""):
            continue
        annee = int(_nombre(annee, "ligne Exercice"))
        donnees = {"exercice": annee}
        for code in CODES_POSTES:
            if code in lignes:
                cellule = lignes[code][i]
                donnees[code] = _nombre(cellule.value, f"Comptes, cellule {cellule.coordinate}")
        exercices.append(donnees)

    if not exercices:
        raise ValueError("Aucun exercice renseigné : indiquez au moins une année dans l'onglet Comptes")

    dossier = {"entreprise": entreprise, "exercices": exercices}
    if demande:
        dossier["demande_credit"] = demande
    return dossier
