"""Tests de la récupération des données publiques, sans connexion internet.

Les réponses de l'INPI sont simulées à partir du dossier fictif Menuiserie Azur,
au format décrit dans la documentation technique de l'API comptes annuels (v4).
"""

import json
from pathlib import Path

import pytest

from analyse_credit import ComptesAnnuels, analyser_historique
from analyse_credit.sources.annuaire import interpreter, nettoyer_siren
from analyse_credit.sources.conversion_inpi import assembler, convertir_bilan, montant
from analyse_credit.sources.inpi import lire_identifiants
from analyse_credit.sources.http import ErreurSource

EXEMPLE = json.loads((Path(__file__).parent.parent / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))
ANNEES = {e["exercice"]: e for e in EXEMPLE["exercices"]}


def fmt(x):
    """Format INPI : 15 caractères, zéros de tête, signe éventuel."""
    x = int(round(x))
    return ("-" if x < 0 else "") + f"{abs(x):0{15 - (x < 0)}d}"


def totaux(e):
    c = ComptesAnnuels(**e)
    from analyse_credit.analyse import calculer_sig
    return c.total_actif, c.total_passif, calculer_sig(c).resultat_net


def ligne(code, *valeurs):
    return {"code": code, **{f"m{i + 1}": fmt(v) for i, v in enumerate(valeurs)}}


def bilan_complet(n, n1, passif_colonnes_3_4=False, cr_confidentiel=False, duree=12):
    """Construit un faux bilan saisi « comptes complets » pour l'exercice n (avec n1 en N-1)."""
    a, b = ANNEES[n], ANNEES[n1]
    actif_codes = {"AH": "immobilisations_incorporelles", "AT": "immobilisations_corporelles",
                   "BH": "immobilisations_financieres", "BL": "stocks", "BX": "creances_clients",
                   "BZ": "autres_creances", "CD": "valeurs_mobilieres_placement", "CF": "disponibilites",
                   "CH": "charges_constatees_avance"}
    # Actif : m1 brut, m2 amortissements, m3 net N, m4 net N-1
    page1 = [ligne(code, a.get(ch, 0) * 1.5, a.get(ch, 0) * 0.5, a.get(ch, 0), b.get(ch, 0))
             for code, ch in actif_codes.items()]
    page1.append(ligne("CO", 0, 0, totaux(a)[0], totaux(b)[0]))

    def p(e):
        return {"DL": e["capitaux_propres"], "DR": e["provisions_risques_charges"],
                "DU": e["emprunts_bancaires"] + e["concours_bancaires_courants"],
                "EH": e["concours_bancaires_courants"], "DV": e["autres_dettes_financieres"],
                "DX": e["dettes_fournisseurs"], "DY": e["dettes_fiscales_sociales"], "EA": e["autres_dettes"],
                "EB": e.get("produits_constates_avance", 0), "EE": totaux(e)[1]}
    pa, pb = p(a), p(b)
    page2 = [ligne(c, 0, 0, pa[c], pb[c]) if passif_colonnes_3_4 else ligne(c, pa[c], pb[c])
             for c in pa]

    cr3 = {"FA": "ventes_marchandises", "FD": "production_vendue", "FP": "reprises_provisions",
           "FQ": "autres_produits", "FS": "achats_marchandises", "FT": "variation_stock_marchandises",
           "FU": "achats_matieres", "FV": "variation_stock_matieres", "FW": "autres_achats_charges_externes",
           "FX": "impots_taxes", "FY": "salaires", "FZ": "charges_sociales",
           "GA": "dotations_amortissements_provisions", "GE": "autres_charges", "GP": "produits_financiers",
           "GU": "charges_financieres"}
    # Compte de résultat : m1 France, m2 export, m3 total N, m4 total N-1 (10 % d'export sur la production)
    page3 = []
    for code, ch in cr3.items():
        export = a.get(ch, 0) * 0.1 if code == "FD" else 0
        page3.append(ligne(code, a.get(ch, 0) - export, export, a.get(ch, 0), b.get(ch, 0)))
    page4 = [ligne("HK", a["impot_benefices"], b["impot_benefices"]),
             ligne("HN", totaux(a)[2], totaux(b)[2])]

    pages = [{"numero": "01", "liasses": page1}, {"numero": "02", "liasses": page2}]
    if not cr_confidentiel:
        pages += [{"numero": "03", "liasses": page3}, {"numero": "04", "liasses": page4}]
    pages.append({"numero": "11", "liasses": [ligne("YP", 18)]})
    return {
        "id": f"bilan-{n}", "siren": "123456782", "denomination": "MENUISERIE AZUR", "typeBilan": "C",
        "dateCloture": f"{n}-12-31", "confidentiality": "2" if cr_confidentiel else "0",
        "bilanSaisi": {"bilan": {
            "identite": {"dateClotureExercice": f"{n}1231", "dureeExerciceN": f"{duree:03d}",
                         "dureeExerciceNMoins1": "012", "codeConfidentialite": "2" if cr_confidentiel else "0"},
            "detail": {"pages": pages}}},
    }


def bilan_simplifie(n, n1):
    a, b = ANNEES[n], ANNEES[n1]

    def actif(e):
        return {"014": e["immobilisations_incorporelles"], "028": e["immobilisations_corporelles"],
                "040": e["immobilisations_financieres"], "050": e["stocks"], "068": e["creances_clients"],
                "072": e["autres_creances"], "084": e["disponibilites"], "092": e["charges_constatees_avance"],
                "110": totaux(e)[0]}

    def passif(e):
        return {"142": e["capitaux_propres"], "154": e["provisions_risques_charges"],
                "156": e["emprunts_bancaires"] + e["concours_bancaires_courants"] + e["autres_dettes_financieres"],
                "166": e["dettes_fournisseurs"], "172": e["dettes_fiscales_sociales"] + e["autres_dettes"],
                "180": totaux(e)[1]}

    def cr(e):
        return {"210": e["ventes_marchandises"], "214": e["production_vendue"],
                "230": e["autres_produits"] + e["reprises_provisions"], "234": e["achats_marchandises"],
                "236": e["variation_stock_marchandises"], "238": e["achats_matieres"],
                "240": e["variation_stock_matieres"], "242": e["autres_achats_charges_externes"],
                "244": e["impots_taxes"], "250": e["salaires"], "252": e["charges_sociales"],
                "254": e["dotations_amortissements_provisions"], "262": e["autres_charges"],
                "280": e["produits_financiers"], "294": e["charges_financieres"],
                "306": e["impot_benefices"], "310": totaux(e)[2]}

    aa, ab, pa, pb, ca, cb = actif(a), actif(b), passif(a), passif(b), cr(a), cr(b)
    page1 = [ligne(c, aa[c] * 1.2, aa[c] * 0.2, aa[c], ab[c]) for c in aa]
    page1 += [ligne(c, 0, 0, pa[c], pb[c]) for c in pa]
    page2 = [ligne(c, ca[c], cb[c]) for c in ca] + [ligne("376", 18)]
    return {"id": f"s-{n}", "typeBilan": "S", "dateCloture": f"{n}-12-31",
            "bilanSaisi": {"bilan": {"identite": {"dateClotureExercice": f"{n}-12-31", "codeConfidentialite": "0"},
                                     "detail": {"pages": [{"numero": 1, "liasses": page1},
                                                          {"numero": 2, "liasses": page2}]}}}}


# ----------------------------------------------------------------------------- tests

def test_montant_format_inpi():
    assert montant("-000000001127414") == -1127414
    assert montant("000000000000000") == 0
    assert montant(None) == 0


def test_comptes_complets_n_et_n_moins_1():
    conv = convertir_bilan(bilan_complet(2025, 2024))
    assert [e.annee for e in conv.exercices] == [2025, 2024]
    assert all(b.controle_ok for e in conv.exercices for b in e.blocs.values())
    assert conv.effectif == 18
    e2025 = conv.exercices[0].en_dict()
    assert e2025["emprunts_bancaires"] == 680_000        # découverts retirés des emprunts
    assert e2025["concours_bancaires_courants"] == 120_000
    assert e2025["production_vendue"] == 2_690_000      # France + export


def test_analyse_identique_a_la_saisie_manuelle():
    complets, incomplets, avertissements, _ = assembler([bilan_complet(2025, 2024), bilan_complet(2024, 2023)])
    assert [e["exercice"] for e in complets] == [2023, 2024, 2025]
    assert not incomplets and not avertissements
    auto = analyser_historique([ComptesAnnuels.depuis_dict(e) for e in complets])
    manuel = analyser_historique([ComptesAnnuels.depuis_dict(e) for e in EXEMPLE["exercices"]])
    for ra, rm in zip(auto, manuel):
        assert ra.ebe == pytest.approx(rm.ebe)
        assert ra.caf == pytest.approx(rm.caf)
        assert ra.bfr == pytest.approx(rm.bfr)
        assert ra.tresorerie_nette == pytest.approx(rm.tresorerie_nette)


def test_detection_automatique_des_colonnes():
    """Si le passif est livré en colonnes 3-4, le contrôle d'équilibre permet de le détecter."""
    conv = convertir_bilan(bilan_complet(2025, 2024, passif_colonnes_3_4=True))
    assert conv.exercices[0].blocs["passif"].controle_ok
    assert conv.exercices[0].en_dict()["capitaux_propres"] == 671_000


def test_compte_de_resultat_confidentiel():
    complets, incomplets, avertissements, _ = assembler([bilan_complet(2025, 2024, cr_confidentiel=True)])
    assert complets == []
    assert [e["exercice"] for e in incomplets] == [2024, 2025]
    assert any("confidentiel" in a for a in avertissements)


def test_exercice_court_signale():
    _, _, avertissements, _ = assembler([bilan_complet(2025, 2024, duree=9)])
    assert any("9 mois" in a for a in avertissements)


def test_comptes_simplifies():
    complets, _, avertissements, effectif = assembler([bilan_simplifie(2025, 2024)])
    assert [e["exercice"] for e in complets] == [2024, 2025]
    assert effectif == 18
    assert any("simplifiés" in a for a in avertissements)
    r = analyser_historique([ComptesAnnuels.depuis_dict(e) for e in complets])[-1]
    assert r.ebe == 149_000
    assert r.resultat_net == -25_000


def test_type_non_pris_en_charge():
    bilan = bilan_complet(2025, 2024)
    bilan["typeBilan"] = "B"
    complets, _, avertissements, _ = assembler([bilan])
    assert complets == [] and "non pris en charge" in avertissements[0]


@pytest.mark.parametrize("saisie,attendu", [("552 032 534", "552032534"), ("55203253400041", "552032534")])
def test_siren_valide(saisie, attendu):
    assert nettoyer_siren(saisie) == attendu


@pytest.mark.parametrize("saisie", ["552032535", "1234", "abc"])
def test_siren_invalide(saisie):
    with pytest.raises(ValueError):
        nettoyer_siren(saisie)


def test_annuaire_interpretation():
    fiche = interpreter({"siren": "552032534", "nom_raison_sociale": "DANONE", "activite_principale": "70.10Z",
                         "tranche_effectif_salarie": "32", "etat_administratif": "A",
                         "siege": {"libelle_commune": "PARIS"},
                         "finances": {"2024": {"ca": 27376000000, "resultat_net": 0}}})
    assert fiche["tranche_effectif"] == "250 à 499 salariés"
    assert fiche["finances"][2024] == {"ca": 27376000000, "resultat_net": None}
    assert fiche["active"]


def test_identifiants_absents(tmp_path, monkeypatch):
    monkeypatch.delenv("INPI_USERNAME", raising=False)
    monkeypatch.delenv("INPI_PASSWORD", raising=False)
    with pytest.raises(ErreurSource, match="data.inpi.fr"):
        lire_identifiants(tmp_path)
    (tmp_path / ".env").write_text("INPI_USERNAME=moi@exemple.fr\nINPI_PASSWORD='secret'\n")
    assert lire_identifiants(tmp_path) == ("moi@exemple.fr", "secret")
