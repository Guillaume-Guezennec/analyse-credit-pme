"""Tests des retraitements bancaires."""

import json
from pathlib import Path

import pytest

from analyse_credit import ComptesAnnuels, analyser_historique, calculer_caf, calculer_sig
from analyse_credit.retraitements import Parametres, retraiter

RACINE = Path(__file__).parent.parent


@pytest.fixture
def comptes_2025():
    data = json.loads((RACINE / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))
    return ComptesAnnuels.depuis_dict(data["exercices"][-1])


def test_credit_bail_neutre_sur_le_resultat(comptes_2025):
    r = retraiter(comptes_2025, Parametres(comptes_courants=False, dividendes=False)).comptes
    avant, apres = calculer_sig(comptes_2025), calculer_sig(r)
    assert apres.resultat_net == pytest.approx(avant.resultat_net)       # le résultat ne change pas
    assert apres.ebe == pytest.approx(avant.ebe + 52_000)                 # les loyers sortent des charges externes
    assert r.dettes_financieres == pytest.approx(comptes_2025.dettes_financieres + 150_000)
    r.verifier_equilibre()


def test_caf_augmente_de_la_part_amortissement(comptes_2025):
    r = retraiter(comptes_2025, Parametres(comptes_courants=False, dividendes=False)).comptes
    interets = 150_000 * 0.04
    assert calculer_caf(r) == pytest.approx(calculer_caf(comptes_2025) + 52_000 - interets)


def test_comptes_courants_bloques_en_fonds_propres(comptes_2025):
    r = retraiter(comptes_2025, Parametres(credit_bail=False, dividendes=False)).comptes
    assert r.capitaux_propres == comptes_2025.capitaux_propres + 50_000
    assert r.autres_dettes_financieres == comptes_2025.autres_dettes_financieres - 50_000


def test_dividendes_deduits_de_la_caf():
    c = ComptesAnnuels(exercice=2024, production_vendue=1_000_000, autres_achats_charges_externes=800_000,
                       dividendes_verses=30_000, capitaux_propres=200_000, disponibilites=200_000)
    r = retraiter(c).comptes
    assert calculer_caf(r) == pytest.approx(calculer_caf(c) - 30_000)


def test_sans_annexe_aucun_retraitement():
    c = ComptesAnnuels(exercice=2024, production_vendue=500_000, capitaux_propres=100_000, disponibilites=100_000)
    assert not retraiter(c).applique


def test_comptes_origine_inchanges(comptes_2025):
    avant = comptes_2025.autres_achats_charges_externes
    retraiter(comptes_2025)
    assert comptes_2025.autres_achats_charges_externes == avant
