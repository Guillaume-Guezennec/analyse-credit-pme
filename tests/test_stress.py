"""Tests du scénario de crise."""

import json
from pathlib import Path

import pytest

from analyse_credit import ComptesAnnuels, calculer_sig
from analyse_credit.stress import Scenario, appliquer, seuil_resistance
from analyse_credit.stress import tester as simuler_crise

RACINE = Path(__file__).parent.parent


@pytest.fixture
def exercices():
    data = json.loads((RACINE / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))
    return [ComptesAnnuels.depuis_dict(e) for e in data["exercices"]]


def test_sans_baisse_rien_ne_change(exercices):
    c = exercices[-1]
    r = appliquer(c, Scenario(0.0))
    assert calculer_sig(r).ebe == pytest.approx(calculer_sig(c).ebe)
    assert r.disponibilites == pytest.approx(c.disponibilites)


def test_levier_operationnel(exercices):
    """Les charges fixes font baisser l'EBE beaucoup plus vite que le chiffre d'affaires."""
    c = exercices[-1]
    r = appliquer(c, Scenario(0.10, 0.5))
    baisse_ebe = 1 - calculer_sig(r).ebe / calculer_sig(c).ebe
    assert baisse_ebe > 0.5
    r.verifier_equilibre()


def test_allongement_delai_clients_pese_sur_la_tresorerie(exercices):
    sans = simuler_crise(exercices[-1], exercices[-2], Scenario(0.1, 0.5, 0), 100_000, 0.04, 84)
    avec = simuler_crise(exercices[-1], exercices[-2], Scenario(0.1, 0.5, 30), 100_000, 0.04, 84)
    assert avec.ratios.tresorerie_nette < sans.ratios.tresorerie_nette
    assert avec.ratios.caf == pytest.approx(sans.ratios.caf)  # sans effet sur la CAF


def test_seuil_de_resistance(exercices):
    c = exercices[0]  # 2023 : entreprise saine
    seuil = seuil_resistance(c, None, 40_000, 0.04, 84)
    assert seuil is not None and 0 < seuil < 0.6
    r = simuler_crise(c, None, Scenario(seuil), 40_000, 0.04, 84)
    assert r.simulation.taux_couverture == pytest.approx(1.25, abs=0.01)
    assert seuil_resistance(exercices[-1], exercices[-2], 250_000, 0.042, 84) is None  # déjà non soutenable
