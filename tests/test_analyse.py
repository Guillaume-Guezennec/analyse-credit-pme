import json
from pathlib import Path

import pytest

from analyse_credit import (ComptesAnnuels, analyser_historique, calculer_bilan_fonctionnel,
                            calculer_caf, calculer_sig, mensualite, noter, tableau_amortissement)

EXEMPLE = Path(__file__).parent.parent / "exemples" / "menuiserie_azur.json"


@pytest.fixture
def exercices():
    data = json.loads(EXEMPLE.read_text(encoding="utf-8"))
    return [ComptesAnnuels.depuis_dict(e) for e in data["exercices"]]


def test_bilans_equilibres(exercices):
    for e in exercices:
        e.verifier_equilibre()


def test_sig_2023(exercices):
    sig = calculer_sig(exercices[0])
    assert sig.marge_commerciale == 125_000
    assert sig.valeur_ajoutee == 1_165_000
    assert sig.ebe == 245_000
    assert sig.resultat_exploitation == 142_000
    assert sig.resultat_net == 84_000


def test_caf_additive_egale_soustractive(exercices):
    """Les deux méthodes de calcul de la CAF doivent donner le même résultat."""
    exercices[1].dotations_financieres_exceptionnelles = 7_000
    exercices[1].reprises_financieres_exceptionnelles = 2_000
    for c in exercices:
        sig = calculer_sig(c)
        soustractive = (sig.ebe + c.autres_produits - c.autres_charges + c.produits_financiers
                        - c.charges_financieres + (c.produits_exceptionnels - c.charges_exceptionnelles
                                                   - c.plus_values_cession)
                        - c.participation_salaries - c.impot_benefices
                        + c.dotations_financieres_exceptionnelles - c.reprises_financieres_exceptionnelles)
        assert calculer_caf(c, sig) == pytest.approx(soustractive)


def test_identite_tresorerie(exercices):
    """Trésorerie nette = FRNG - BFR."""
    for c in exercices:
        bf = calculer_bilan_fonctionnel(c)
        assert bf.tresorerie_nette == pytest.approx(bf.frng - bf.bfr)


def test_bilan_desequilibre_detecte(exercices):
    c = exercices[0]
    c.disponibilites += 10_000
    with pytest.raises(ValueError):
        c.verifier_equilibre()


def test_mensualite_et_amortissement():
    m = mensualite(100_000, 0.04, 120)
    assert m == pytest.approx(1012.45, abs=0.01)
    tableau = tableau_amortissement(100_000, 0.04, 120)
    assert tableau[-1]["capital_restant"] == pytest.approx(0, abs=0.01)
    assert sum(l["capital"] for l in tableau) == pytest.approx(100_000)


def test_degradation_notation(exercices):
    historique = analyser_historique(exercices)
    notes = [noter(r).score for r in historique]
    assert notes[0] > notes[-1]  # le dossier fictif se dégrade en 2025


def test_ebe_negatif_plafonne_la_note():
    c = ComptesAnnuels(exercice=2025, production_vendue=100_000, salaires=150_000,
                       capitaux_propres=50_000, disponibilites=50_000)
    r = analyser_historique([c])[0]
    assert noter(r).note == "E"
