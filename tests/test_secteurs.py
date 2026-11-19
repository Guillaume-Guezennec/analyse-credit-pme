"""Tests de la comparaison sectorielle."""

import json
from pathlib import Path

import pytest

from analyse_credit import ComptesAnnuels, analyser_historique
from analyse_credit.secteurs import (comparer, constats_sectoriels, normaliser_naf, percentile, section,
                                     tranche_ca, trouver_groupe)

RACINE = Path(__file__).parent.parent


@pytest.fixture
def exemple():
    data = json.loads((RACINE / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))
    comptes = [ComptesAnnuels.depuis_dict(e) for e in data["exercices"]]
    return comptes, analyser_historique(comptes)


def test_naf_et_tranches():
    assert normaliser_naf("16.23Z") == "1623Z"
    assert section("1623Z") == "C" and section("7010Z") == "M"
    assert tranche_ca(2_990_000) == "2M-10M" and tranche_ca(500_000) == "<2M"


def test_groupe_le_plus_fin_puis_repli():
    g = trouver_groupe("16.23Z", 2_990_000)
    assert g.code == "1623Z" and g.cohorte >= 50
    assert trouver_groupe(None, 2_990_000).niveau == "ensemble"
    assert trouver_groupe("99.99Q", 2_990_000) is not None  # code inconnu : repli sans erreur


def test_percentile_interpole():
    points = [1, 2, 3, 4, 5]
    assert percentile(3, points) == 50
    assert percentile(2.5, points) == pytest.approx(37.5)
    assert percentile(0, points) == 5 and percentile(10, points) == 95


def test_comparaison_exemple(exemple):
    comptes, historique = exemple
    c = comparer(historique[-1], comptes[-1], "16.23Z")
    rn = next(p for p in c.positions if p.champ == "part_ca_resultat_net")
    assert rn.score <= 10  # rentabilité parmi les plus faibles du secteur
    textes = [x.texte for x in constats_sectoriels(c)]
    assert any("Rentabilité nette" in t for t in textes)
    assert not any("Capacité de remboursement" in t for t in textes)  # déjà commentée par l'analyse principale
