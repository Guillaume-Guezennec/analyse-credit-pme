"""Tests de l'application web et des commentaires automatiques."""

import io
import json
from pathlib import Path

import pytest

from analyse_credit import ComptesAnnuels, analyser_historique
from analyse_credit.commentaires import commenter
from analyse_credit.import_excel import lire_dossier

RACINE = Path(__file__).parent.parent


def historique_exemple():
    data = json.loads((RACINE / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))
    return analyser_historique([ComptesAnnuels.depuis_dict(e) for e in data["exercices"]])


def test_commentaires_detectent_les_signaux_du_cas_exemple():
    textes = " ".join(c.texte for c in commenter(historique_exemple()))
    assert "Effet ciseaux" in textes
    assert "BFR s'alourdit" in textes
    assert "Trésorerie nette négative" in textes
    assert "7,3 années" in textes


def test_import_excel_depuis_la_memoire():
    """Dans l'application, le fichier déposé est lu en mémoire, sans être enregistré sur le disque."""
    contenu = (RACINE / "exemples" / "menuiserie_azur.xlsx").read_bytes()
    assert lire_dossier(io.BytesIO(contenu))["entreprise"]["code_naf"] == "16.23Z"


def test_application_demarre_sans_erreur():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=60).run()
    assert not at.exception
    contenu = " ".join(m.value for m in at.markdown)
    assert "Note de risque" in contenu and "Point faible" in contenu and "Montant maximal finançable" in contenu
    assert any("note de crédit" in b.label.lower() for b in at.get("download_button"))
    for source in ("Fichier Excel", "Recherche par SIREN"):
        at.sidebar.radio[0].set_value(source).run()
        assert not at.exception


def test_note_de_credit_pdf():
    from pypdf import PdfReader
    from analyse_credit.note_credit import generer_note
    dossier = json.loads((RACINE / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))
    pdf = generer_note(dossier)
    assert pdf[:4] == b"%PDF"
    lecteur = PdfReader(io.BytesIO(pdf))
    assert len(lecteur.pages) == 3
    texte = " ".join(page.extract_text() for page in lecteur.pages)
    for attendu in ("Menuiserie Azur", "Non soutenable", "Effet ciseaux", "Détail de la notation", "Proposition d'avis"):
        assert attendu in texte


def test_note_de_credit_un_seul_exercice():
    from analyse_credit.note_credit import generer_note
    dossier = json.loads((RACINE / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))
    dossier["exercices"] = dossier["exercices"][:1]
    dossier.pop("demande_credit")
    assert generer_note(dossier, montant=60_000, taux=0.04, duree_mois=60)[:4] == b"%PDF"
