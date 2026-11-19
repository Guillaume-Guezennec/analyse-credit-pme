"""Tests du score statistique de défaillance."""

import copy
import json
from pathlib import Path

import pytest

from analyse_credit import ComptesAnnuels, analyser_historique
from analyse_credit.defaillance import charger_modele, prevoir, variables_entreprise

RACINE = Path(__file__).parent.parent


@pytest.fixture
def exemple():
    data = json.loads((RACINE / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))
    comptes = [ComptesAnnuels.depuis_dict(e) for e in data["exercices"]]
    return comptes, analyser_historique(comptes)


def test_modele_coherent():
    m = charger_modele()
    assert m["validation"]["grille_de_score"]["auc"] > 0.75
    for v in m["variables"].values():
        assert len(v["poids"]) == len(v["bornes"]) + 2  # tranches + tranche « non disponible »
        assert v["bornes"] == sorted(v["bornes"])
    taux = [d["taux_observe"] for d in m["validation"]["deciles"]]
    assert taux == sorted(taux)  # le risque observé croît d'un décile à l'autre


def test_prevision_exemple(exemple):
    comptes, historique = exemple
    p = prevoir(historique[-1], comptes[-1])
    assert 0.002 < p.probabilite < 0.10
    assert len(p.facteurs) == len(charger_modele()["variables"])
    assert any("Rentabilité nette" in f.libelle for f in p.aggravants)


def test_definitions_alignees_sur_la_base_publique(exemple):
    comptes, historique = exemple
    v = variables_entreprise(historique[-1], comptes[-1])
    assert v["marge_ebe"] == pytest.approx(149_000 / 2_990_000 * 100)
    assert v["autonomie_financiere"] == pytest.approx(671_000 / 2_120_000 * 100)
    assert v["taux_d_endettement"] == pytest.approx(850_000 / 671_000 * 100)


def test_une_meilleure_liquidite_reduit_le_risque(exemple):
    comptes, historique = exemple
    base = prevoir(historique[-1], comptes[-1]).probabilite
    c = copy.deepcopy(comptes[-1])
    c.disponibilites += 600_000
    c.capitaux_propres += 600_000
    r = analyser_historique([comptes[-2], c])[-1]
    assert prevoir(r, c).probabilite < base
