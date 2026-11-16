import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from analyse_credit import ComptesAnnuels, analyser_historique
from analyse_credit.import_excel import lire_dossier

RACINE = Path(__file__).parent.parent


def test_exemple_excel_identique_au_json():
    """L'exemple Excel doit donner exactement les mêmes données que l'exemple JSON."""
    depuis_excel = lire_dossier(RACINE / "exemples" / "menuiserie_azur.xlsx")
    depuis_json = json.loads((RACINE / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))
    assert depuis_excel["entreprise"] == depuis_json["entreprise"]
    d_xl, d_js = depuis_excel["demande_credit"], depuis_json["demande_credit"]
    assert d_xl["objet"] == d_js["objet"]
    assert d_xl["duree_mois"] == d_js["duree_mois"]
    assert d_xl["montant"] == pytest.approx(d_js["montant"])
    assert d_xl["taux_annuel"] == pytest.approx(d_js["taux_annuel"])
    for e_xl, e_js in zip(depuis_excel["exercices"], depuis_json["exercices"]):
        complet = {k: 0.0 for k in e_xl}
        complet.update(e_js)
        assert e_xl == pytest.approx(complet)


def test_analyse_depuis_excel():
    dossier = lire_dossier(RACINE / "exemples" / "menuiserie_azur.xlsx")
    historique = analyser_historique([ComptesAnnuels.depuis_dict(e) for e in dossier["exercices"]])
    assert historique[-1].ebe == 149_000


def test_modele_vierge_signale_absence_de_donnees():
    with pytest.raises(ValueError, match="raison sociale"):
        lire_dossier(RACINE / "modeles" / "modele_liasse.xlsx")


def test_valeur_texte_refusee(tmp_path):
    wb = load_workbook(RACINE / "exemples" / "menuiserie_azur.xlsx")
    ws = wb["Comptes"]
    for row in ws.iter_rows(min_col=1, max_col=3):
        if row[0].value == "salaires":
            row[2].value = "beaucoup"
    chemin = tmp_path / "faux.xlsx"
    wb.save(chemin)
    with pytest.raises(ValueError, match="non numérique"):
        lire_dossier(chemin)
