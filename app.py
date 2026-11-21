"""Application web d'analyse crédit de PME.

Lancement local : streamlit run app.py
"""

from __future__ import annotations

import json
import tempfile
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from analyse_credit import (ComptesAnnuels, analyser_historique, calculer_sig, montant_maximal, noter, simuler,
                            tableau_amortissement)
from analyse_credit.commentaires import commenter
from analyse_credit.defaillance import charger_modele, prevoir
from analyse_credit.secteurs import comparer, constats_sectoriels
from analyse_credit.retraitements import Parametres, retraiter_tout
from analyse_credit.stress import Scenario, couverture_selon_baisse, seuil_resistance, tester
from analyse_credit.export_excel import ecrire_classeur
from analyse_credit.glossaire import GLOSSAIRE
from analyse_credit.import_excel import lire_dossier
from analyse_credit.note_credit import generer_note
from analyse_credit.scoring import CRITERES
from analyse_credit.sources.annuaire import nettoyer_siren
from analyse_credit.sources.http import ErreurSource
from analyse_credit.sources.inpi import lire_identifiants
from analyse_credit.sources.pipeline import recuperer
from interface import composants as ui
from interface import graphiques as gr
from interface.theme import CSS, SERIES

RACINE = Path(__file__).resolve().parent
DEPOT_GITHUB = "https://github.com/Guillaume-Guezennec/analyse-credit-pme"
TITRE = "Analyse crédit PME"
SOUS_TITRE = ("Analyse financière automatisée à partir des comptes annuels : SIG, CAF, équilibre financier, "
              "ratios bancaires, notation et simulation de prêt.")

st.set_page_config(page_title=TITRE, layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


def html(contenu: str):
    st.markdown(contenu, unsafe_allow_html=True)


# ----------------------------------------------------------------------------- formats

def eur(x):
    return "n.d." if x is None else f"{x:,.0f}".replace(",", " ").replace("-", "−") + " €"


def keur(x):
    return "n.d." if x is None else f"{x / 1000:,.0f}".replace(",", " ").replace("-", "−") + " k€"


def pct(x):
    return "n.d." if x is None else f"{x * 100:.1f} %".replace(".", ",").replace("-", "−")


def nb(x, unite=""):
    return "n.d." if x is None else f"{x:.2f}".replace(".", ",").replace("-", "−") + unite


def jours(x):
    return "n.d." if x is None else f"{x:.0f} j"


FORMATS = {
    "chiffre_affaires": keur, "croissance_ca": pct, "ebe": keur, "taux_ebe": pct, "resultat_net": keur,
    "rentabilite_nette": pct, "caf": keur, "frng": keur, "bfr": keur, "bfr_jours_ca": jours,
    "tresorerie_nette": keur, "dette_financiere_nette": keur, "autonomie_financiere": pct, "gearing": nb,
    "rentabilite_capitaux_propres": pct, "levier_dfn_ebe": lambda x: nb(x, " ans"),
    "capacite_remboursement": lambda x: nb(x, " ans"), "poids_charges_financieres": pct,
    "delai_clients_jours": jours, "delai_fournisseurs_jours": jours, "liquidite_generale": nb,
}
FAMILLES = {
    "Activité et rentabilité": ["chiffre_affaires", "croissance_ca", "ebe", "taux_ebe", "resultat_net",
                                "rentabilite_nette", "caf", "rentabilite_capitaux_propres"],
    "Équilibre financier": ["frng", "bfr", "bfr_jours_ca", "tresorerie_nette"],
    "Structure et endettement": ["autonomie_financiere", "dette_financiere_nette", "gearing", "levier_dfn_ebe",
                                 "capacite_remboursement", "poids_charges_financieres"],
    "Cycle d'exploitation et liquidité": ["delai_clients_jours", "delai_fournisseurs_jours", "liquidite_generale"],
}


def valeur_facteur(f) -> str:
    if f.valeur is None:
        return "non disponible"
    if f.variable == "log_ca":
        return "CA de " + keur(10 ** f.valeur)
    if f.unite == "%":
        return f"{f.valeur:.1f} %".replace(".", ",").replace("-", "−")
    if f.unite.startswith("jours"):
        return f"{f.valeur:.0f} j" + (" de CA" if "CA" in f.unite else "")
    return nb(f.valeur)


def variation(attr, actuel, precedent, fmt, hausse_favorable=True):
    a, p = getattr(actuel, attr), getattr(precedent, attr) if precedent else None
    if a is None or p is None:
        return None, None
    diff = a - p
    texte = ("+" if diff >= 0 else "") + fmt(diff) + " sur un an"
    return texte, (diff >= 0) == hausse_favorable if diff else None


# ----------------------------------------------------------------------------- données

@st.cache_data(show_spinner=False)
def charger_exemple():
    return json.loads((RACINE / "exemples" / "menuiserie_azur.json").read_text(encoding="utf-8"))


def identifiants_inpi():
    try:
        if "INPI_USERNAME" in st.secrets and "INPI_PASSWORD" in st.secrets:
            return st.secrets["INPI_USERNAME"], st.secrets["INPI_PASSWORD"]
    except Exception:  # pas de fichier secrets : on tente le .env local
        pass
    try:
        return lire_identifiants(RACINE)
    except ErreurSource:
        return None


@st.cache_data(show_spinner=False, ttl=3600)
def chercher_siren(siren: str, avec_inpi: bool):
    res = recuperer(siren, identifiants_inpi() if avec_inpi else None)
    return {"dossier": res.dossier(), "complets": bool(res.complets), "fiche": res.fiche,
            "avertissements": res.avertissements, "erreur_inpi": res.erreur_inpi}


def classeur_en_memoire(dossier=None, avertissements=None) -> bytes:
    with tempfile.TemporaryDirectory() as dossier_tmp:
        return ecrire_classeur(Path(dossier_tmp) / "dossier.xlsx", dossier, avertissements).read_bytes()


# ----------------------------------------------------------------------------- barre latérale

with st.sidebar:
    html('<div class="marque"><svg width="34" height="34" viewBox="0 0 34 34"><rect width="34" height="34" rx="9" '
         'fill="#EEF1F4"/><rect x="7" y="17" width="5" height="10" rx="1.5" fill="#A8D0E6"/><rect x="14.5" y="12" '
         'width="5" height="15" rx="1.5" fill="#FFC8A2"/><rect x="22" y="8" width="5" height="19" rx="1.5" '
         'fill="#C7DDB5"/></svg><div><div class="marque-titre">Analyse crédit PME</div>'
         '<div class="marque-sous">Aide à la décision de crédit</div></div></div>')

    with st.expander("Données à analyser", expanded=True, icon=":material/folder_open:"):
        source = st.radio("Source des comptes", ["Exemple (entreprise fictive)", "Fichier Excel", "Recherche par SIREN"],
                          label_visibility="collapsed")
        dossier, fiche, avertissements, info = None, {}, [], None

        if source.startswith("Exemple"):
            dossier = charger_exemple()
            st.caption("Menuiserie Azur : PME fictive de 18 salariés dont la rentabilité se dégrade malgré la croissance.")

        elif source == "Fichier Excel":
            st.download_button("Télécharger le modèle vierge", (RACINE / "modeles" / "modele_liasse.xlsx").read_bytes(),
                               "modele_liasse.xlsx", width="stretch")
            fichier = st.file_uploader("Déposer le modèle rempli", type=["xlsx"])
            st.caption("Le fichier est analysé en mémoire et n'est pas conservé.")
            if fichier:
                try:
                    dossier = lire_dossier(fichier)
                except (ValueError, KeyError) as e:
                    st.error(f"Fichier non lisible : {e}")

        else:
            saisie = st.text_input("SIREN ou SIRET", placeholder="552 032 534")
            avec_inpi = identifiants_inpi() is not None
            if saisie:
                try:
                    siren = nettoyer_siren(saisie)
                    with st.spinner("Interrogation de l'annuaire des entreprises et de l'INPI…"):
                        r = chercher_siren(siren, avec_inpi)
                    fiche, avertissements = r["fiche"], r["avertissements"]
                    if r["dossier"]["exercices"]:
                        dossier = r["dossier"]
                        if not r["complets"]:
                            info = ("Compte de résultat indisponible (confidentiel) : téléchargez l'Excel pré-rempli, "
                                    "complétez-le, puis importez-le.")
                    else:
                        info = r["erreur_inpi"]
                except ValueError as e:
                    st.error(str(e))
            if not avec_inpi:
                st.caption("Version de démonstration : seule l'identité de l'entreprise est récupérée. Les comptes "
                           "détaillés nécessitent un accès à l'API de l'INPI (voir l'onglet Projet et méthode).")

    with st.expander("Retraitements bancaires", icon=":material/tune:"):
        st.caption("Passer des comptes publiés à la vision du banquier : crédit-bail traité comme un emprunt, comptes "
                   "courants bloqués reclassés en quasi-fonds propres, dividendes déduits de la CAF.")
        avec_retraitements = st.toggle("Appliquer les retraitements", value=True)
        rt_cb = st.checkbox("Crédit-bail", value=True, disabled=not avec_retraitements)
        rt_cc = st.checkbox("Comptes courants bloqués", value=True, disabled=not avec_retraitements)
        rt_div = st.checkbox("Dividendes", value=True, disabled=not avec_retraitements)
        taux_cb = st.number_input("Taux implicite du crédit-bail (%)", 0.0, 15.0, 4.0, 0.5,
                                  disabled=not avec_retraitements,
                                  help="Sert à séparer les loyers entre intérêts et amortissement.") / 100
    parametres_rt = Parametres(rt_cb, rt_cc, rt_div, taux_cb) if avec_retraitements else None

    with st.expander("Mode d'emploi", icon=":material/menu_book:"):
        html('<ol class="mode-emploi">'
             '<li><b>Choisir les données</b> : l\'exemple, un modèle Excel rempli à partir de la liasse, ou un SIREN.</li>'
             '<li><b>Lire la Synthèse</b> : note, points forts et points faibles, score de défaillance.</li>'
             '<li><b>Approfondir</b> dans Ratios détaillés : retraitements, cascade des SIG, comparaison au secteur.</li>'
             '<li><b>Tester le financement</b> dans Simulation de prêt, scénario de crise compris, puis télécharger '
             'la note de crédit en PDF.</li></ol>')

    with st.expander("Le projet en bref", icon=":material/info:"):
        html('<div class="resume">Un outil qui reproduit l\'analyse d\'un chargé d\'affaires entreprises : des comptes '
             'annuels à la décision de crédit, en quelques secondes et avec des contrôles à chaque étape. '
             'Réalisé par Guillaume Guezennec avec l\'aide de Claude (Anthropic).</div>')
        st.link_button("Code source sur GitHub", DEPOT_GITHUB, width="stretch", icon=":material/code:")
        st.link_button("Rapport du modèle de défaillance", f"{DEPOT_GITHUB}/blob/main/docs/modele_defaillance.md",
                       width="stretch", icon=":material/description:")

    st.caption("Données publiques : annuaire des entreprises, INPI, BODACC, Bercy. Outil pédagogique.")


# ----------------------------------------------------------------------------- calculs

historique, exercices, erreur = [], [], None
exercices_bruts, historique_brut, resultats_rt = [], [], []
if dossier:
    try:
        exercices_bruts = sorted((ComptesAnnuels.depuis_dict(e) for e in dossier["exercices"]), key=lambda e: e.exercice)
        historique_brut = analyser_historique(exercices_bruts)
        exercices, historique = exercices_bruts, historique_brut
        if parametres_rt:
            resultats_rt = retraiter_tout(exercices_bruts, parametres_rt)
            if any(r.applique for r in resultats_rt):
                exercices = [r.comptes for r in resultats_rt]
                historique = analyser_historique(exercices)
            else:
                resultats_rt = []
    except (ValueError, KeyError, TypeError) as e:
        erreur = f"Analyse impossible : {e}"

# ----------------------------------------------------------------------------- en-tête

etiquettes = []
if fiche:
    etiquettes += [(fiche.get("raison_sociale") or "", True), (f"SIREN {fiche.get('siren')}", False),
                   (f"NAF {fiche.get('code_naf')}", False)]
    if fiche.get("commune"):
        etiquettes.append((fiche["commune"].title(), False))
    if fiche.get("tranche_effectif"):
        etiquettes.append((fiche["tranche_effectif"], False))
    etiquettes.append(("Active" if fiche.get("active") else "Fermée", False))
elif dossier:
    ent = dossier.get("entreprise", {})
    etiquettes.append((ent.get("raison_sociale", ""), True))
    if ent.get("activite"):
        etiquettes.append((ent["activite"], False))
if historique:
    etiquettes.append((f"Exercices {historique[0].exercice} à {historique[-1].exercice}"
                       if len(historique) > 1 else f"Exercice {historique[0].exercice}", False))
if resultats_rt:
    etiquettes.append(("Comptes retraités", False))
html(ui.entete(TITRE, SOUS_TITRE, etiquettes))

onglets = st.tabs(["Synthèse", "Ratios détaillés", "Simulation de prêt", "Projet et méthode"])
onglet_synthese, onglet_ratios, onglet_pret, onglet_projet = onglets

# ----------------------------------------------------------------------------- projet et méthode (toujours visible)

with onglet_projet:
    html(ui.section("Pourquoi ce projet"))
    html('<div class="projet">'
         '<p>Quand une entreprise demande un crédit, le banquier suit toujours la même démarche : récupérer les comptes, '
         'les retraiter, calculer une vingtaine de ratios, juger la solidité financière et vérifier que le prêt est '
         'remboursable. Fait à la main, ce travail est long et exposé aux erreurs de saisie.</p>'
         '<p>J\'ai voulu automatiser cette partie répétitive pour consacrer le temps gagné à l\'essentiel : comprendre '
         'l\'entreprise, son dirigeant et son projet. Ce projet m\'a aussi permis d\'apprendre à concevoir un outil avec '
         'l\'intelligence artificielle : j\'ai défini le besoin métier et validé chaque choix financier, Claude '
         '(Anthropic) a écrit le code.</p>'
         '<div class="signature">Guillaume Guezennec · Master Grande École, ESSCA</div></div>')

    html(ui.section("Comment ça marche"))
    html(ui.etapes([
        ("Données", "SIREN (annuaire de l'État et INPI) ou modèle Excel de liasse fiscale."),
        ("Contrôles", "Bilan équilibré, totaux de la liasse retrouvés, résultat net recalculé."),
        ("Analyse", "SIG, CAF, bilan fonctionnel et une vingtaine de ratios sur plusieurs années."),
        ("Notation", "Sept critères pondérés, note de A à E, constats rédigés et score statistique de défaillance."),
        ("Décision", "Simulation du prêt, taux de couverture et montant maximal finançable."),
    ]))

    html(ui.section("Modèle de prédiction des défaillances"))
    m = charger_modele()
    v = m["validation"]["grille_de_score"]
    nb_bilans = f"{m['nb_bilans']:,}".replace(",", "\u202f")
    nb_def = f"{m['nb_defaillances']:,}".replace(",", "\u202f")
    html('<div class="projet"><p>Le score statistique est une <b>grille de score</b>, la méthode classique des banques : '
         'chaque ratio est découpé en dix tranches et chaque tranche reçoit un poids, estimé par une régression '
         f'logistique sur <b>{nb_bilans} bilans</b> de PME (base publique Ratios financiers BCE/INPI) croisés avec '
         f'<b>{nb_def} défaillances</b> publiées au BODACC. Le modèle a été entraîné sur les exercices 2019 à 2021, '
         'puis testé sur 2022 et 2023, deux années qu\'il n\'avait jamais vues.</p></div>')
    st.write("")
    k1, k2, k3, k4 = st.columns(4)
    for col, contenu in zip((k1, k2, k3, k4), (
            ui.carte("AUC sur les années de test", nb(v["auc"], ""), "0,5 = hasard, 1 = classement parfait"),
            ui.carte("Défaillances repérées", pct(v["capture_10pct"]), "dans les 10 % de bilans jugés les plus risqués"),
            ui.carte("Taux moyen 2022-2023", pct(m["taux_reference"]), "de PME défaillantes dans les 2 ans"),
            ui.carte("Comparaison", nb(m["validation"]["boosting_comparaison"]["auc"], ""),
                     "AUC d'un boosting d'arbres, plus précis mais non explicable"))):
        with col:
            html(contenu)
    st.plotly_chart(gr.deciles_defaillance(m["validation"]["deciles"]), width="stretch")
    st.caption("Lecture : parmi les 10 % d'entreprises jugées les plus risquées (décile 10), environ 6,5 % ont fait "
               "défaut dans les 2 ans, contre moins de 0,1 % pour les 10 % les plus sûres. Rapport complet : "
               f"[docs/modele_defaillance.md]({DEPOT_GITHUB}/blob/main/docs/modele_defaillance.md).")

    html(ui.section("Grille de notation"))
    lignes_grille = []
    poids_max = max(c.poids for c in CRITERES)
    for c in CRITERES:
        fmt = FORMATS.get(c.attribut, nb)
        barre = (f'<div class="jauge"><div style="width:{c.poids / poids_max * 100:.0f}%;'
                 f'background:{SERIES[0]["fond"]}"></div></div>')
        lignes_grille.append([f"<b>{escape(c.nom)}</b><div class='def'>{escape(c.explication)}</div>",
                              f"{c.poids} pts{barre}", ui.pastille("vert", fmt(c.seuil_bon)),
                              ui.pastille("rouge", fmt(c.seuil_alerte))])
    html(ui.tableau([("Critère", False), ("Poids", False), ("Seuil favorable", False), ("Seuil d'alerte", False)],
                    lignes_grille))
    st.caption("Entre les deux seuils, les points sont attribués proportionnellement. Barème : A ≥ 80, B ≥ 65, "
               "C ≥ 50, D ≥ 35, E < 35. Un EBE négatif plafonne la note à E.")

    col_g, col_d = st.columns(2)
    with col_g:
        html(ui.section("Contrôles de fiabilité"))
        for t in ["Le bilan doit être équilibré, sinon l'analyse est refusée.",
                  "Données INPI : la somme des postes doit retrouver les totaux de la liasse, et le résultat net "
                  "recalculé doit égaler celui déclaré.",
                  "Le chiffre d'affaires est comparé à celui de l'annuaire officiel des entreprises.",
                  "Plus de 30 tests automatiques vérifient chaque calcul après chaque modification."]:
            html(ui.bloc("vert", t, "Contrôle"))
    with col_d:
        html(ui.section("Limites assumées"))
        for t in ["Les seuils de notation sont des repères pédagogiques : ils ne reproduisent la grille d'aucune banque "
                  "et doivent être adaptés au secteur.",
                  "L'analyse est uniquement financière : elle ne voit ni le dirigeant, ni le marché, ni les garanties.",
                  "Beaucoup de PME publient des comptes confidentiels : il faut alors la liasse fournie par le client."]:
            html(ui.bloc("orange", t, "Limite"))

    html(ui.section("Sources et technologies"))
    st.markdown("Identité : [API Recherche d'entreprises](https://recherche-entreprises.api.gouv.fr/docs/) · "
                "Comptes détaillés : API comptes annuels de l'[INPI](https://data.inpi.fr) · "
                f"Code, tests et documentation : [GitHub]({DEPOT_GITHUB})")
    html("".join(f'<span class="puce-techno">{t}</span>' for t in
                 ["Python", "Streamlit", "Plotly", "pandas", "scikit-learn", "openpyxl", "API de l'État", "API INPI",
                  "BODACC", "pytest",
                  "Git et GitHub", "Claude (Anthropic)"]))

# ----------------------------------------------------------------------------- absence de données

if info and historique:
    with onglet_synthese:
        st.info(info)
if avertissements:
    with onglet_synthese:
        with st.expander(f"{len(avertissements)} point(s) à vérifier sur les données"):
            for a in avertissements:
                st.markdown(f"- {a}")
        if dossier:
            st.download_button("Télécharger l'Excel pré-rempli", classeur_en_memoire(dossier, avertissements),
                               f"{fiche.get('siren', 'dossier')}.xlsx")

if not historique:
    if erreur:
        message = erreur
    elif source == "Fichier Excel":
        message = "Téléchargez le modèle, remplissez-le avec la liasse fiscale, puis déposez-le dans la barre latérale."
    elif fiche:
        message = ("Entreprise trouvée, mais ses comptes détaillés ne sont pas récupérés dans cette version en ligne "
                   "(accès à l'API de l'INPI non configuré). Seuls les chiffres de l'annuaire sont affichés ci-dessous. "
                   "Pour voir une analyse complète, choisissez l'exemple ou importez un fichier Excel.")
    else:
        message = info or "Saisissez un SIREN dans la barre latérale."
    for onglet in (onglet_synthese, onglet_ratios, onglet_pret):
        with onglet:
            (st.error if erreur else st.info)(message)
            if fiche.get("finances"):
                st.markdown("**Chiffres publiés dans l'annuaire des entreprises**")
                st.dataframe(pd.DataFrame({str(a): {"Chiffre d'affaires": eur(v.get("ca")),
                                                    "Résultat net": eur(v.get("resultat_net"))}
                                           for a, v in fiche["finances"].items()}))
    st.stop()

dernier = historique[-1]
precedent = historique[-2] if len(historique) > 1 else None
comptes_dernier = sorted(exercices, key=lambda e: e.exercice)[-1]
notation = noter(dernier)
# Score de défaillance et comparaison sectorielle : sur les comptes bruts, comme les données publiques
prevision = prevoir(historique_brut[-1], exercices_bruts[-1])
code_naf = (dossier.get("entreprise", {}).get("code_naf") or fiche.get("code_naf") or "")
comparaison = comparer(historique_brut[-1], exercices_bruts[-1], code_naf)
annees = [r.exercice for r in historique]
feux = {d.critere.attribut: d.feu for d in notation.details}

# ----------------------------------------------------------------------------- synthèse

with onglet_synthese:
    texte_pdf, zone_pdf = st.columns([3, 1], vertical_alignment="center")
    texte_pdf.caption("Synthèse de l'analyse. La note de crédit complète (5 pages, format comité de crédit) "
                      "reprend les paramètres de l'onglet Simulation de prêt.")
    zone_pdf = zone_pdf.empty()
    cols = st.columns([1.25, 1, 1, 1, 1])
    with cols[0]:
        html(ui.carte_note(notation.note, notation.score, notation.libelle, dernier.exercice))
    indicateurs = [
        ("chiffre_affaires", f"Chiffre d'affaires {dernier.exercice}", f"Croissance : {pct(dernier.croissance_ca)}"),
        ("ebe", "EBE", f"Taux d'EBE : {pct(dernier.taux_ebe)}"),
        ("caf", "CAF", f"Résultat net : {keur(dernier.resultat_net)}"),
        ("tresorerie_nette", "Trésorerie nette", f"BFR : {jours(dernier.bfr_jours_ca)} de CA"),
    ]
    for col, (attr, libelle, detail) in zip(cols[1:], indicateurs):
        texte, favorable = variation(attr, dernier, precedent, keur)
        with col:
            html(ui.carte(libelle, keur(getattr(dernier, attr)), detail, texte, favorable, GLOSSAIRE[attr][2]))

    html(ui.section("Points clés"))
    ordre = {"negatif": 0, "vigilance": 1, "positif": 2}
    constats = sorted(commenter(historique) + constats_sectoriels(comparaison), key=lambda c: ordre[c.sens])
    g, d = st.columns(2)
    for i, c in enumerate(constats):
        with (g if i % 2 == 0 else d):
            html(ui.bloc_constat(c.sens, c.texte))

    html(ui.section("Score statistique de défaillance"))
    st.caption("Probabilité d'ouverture d'un redressement ou d'une liquidation judiciaire dans les 24 mois, estimée par "
               "une grille de score entraînée sur 1,4 million de bilans de PME et les procédures collectives publiées "
               "au BODACC. Méthode et validation dans l'onglet Projet et méthode.")
    s1, s2, s3 = st.columns([1.1, 1.45, 1.45])
    with s1:
        html(ui.carte("Probabilité de défaillance à 2 ans", pct(prevision.probabilite),
                      f"Moyenne des PME : {pct(prevision.taux_moyen)}",
                      f"{prevision.classe} ({nb(prevision.multiple_moyenne, ' x')} la moyenne)",
                      prevision.couleur == "vert"))
    plus_fort = max([abs(f.contribution) for f in prevision.facteurs] + [0.01])
    with s2:
        st.markdown("**Ce qui augmente le risque**")
        html(ui.facteurs([(f.libelle, valeur_facteur(f), f.contribution) for f in prevision.aggravants[:4]],
                         "rouge", plus_fort))
    with s3:
        st.markdown("**Ce qui réduit le risque**")
        html(ui.facteurs([(f.libelle, valeur_facteur(f), f.contribution) for f in prevision.attenuants[:4]],
                         "vert", plus_fort))
    html(ui.bloc("orange",
                 "La note de A à E mesure la capacité à porter un nouveau crédit (rentabilité, endettement, couverture "
                 "des remboursements). Le score statistique mesure le risque de procédure collective à 2 ans, observé sur "
                 "des entreprises comparables. Les deux peuvent diverger : une entreprise solide peut être trop endettée "
                 "pour un prêt supplémentaire, sans être pour autant proche de la défaillance.", "Bien lire ces deux indicateurs"))

    html(ui.section("Évolution sur la période"))
    c1, c2 = st.columns(2)
    c1.plotly_chart(gr.barres(annees, {"EBE": [r.ebe for r in historique], "CAF": [r.caf for r in historique],
                                       "Résultat net": [r.resultat_net for r in historique]}, "Rentabilité"),
                    width="stretch")
    c2.plotly_chart(gr.barres(annees, {"Fonds de roulement": [r.frng for r in historique],
                                       "BFR": [r.bfr for r in historique],
                                       "Trésorerie nette": [r.tresorerie_nette for r in historique]},
                              "Équilibre financier"), width="stretch")
    c3, c4 = st.columns(2)
    c3.plotly_chart(gr.lignes(annees, {"Délai clients": [r.delai_clients_jours for r in historique],
                                       "Délai fournisseurs": [r.delai_fournisseurs_jours for r in historique],
                                       "BFR en jours de CA": [r.bfr_jours_ca for r in historique]},
                              "Cycle d'exploitation"), width="stretch")
    with c4:
        st.markdown(f"**Détail de la notation {dernier.exercice}**")
        lignes_note = []
        for det in notation.details:
            fmt = FORMATS.get(det.critere.attribut, nb)
            lignes_note.append([escape(det.critere.nom), fmt(det.valeur), ui.pastille(det.feu),
                                f"{det.points:.1f} / {det.critere.poids}".replace(".", ",")
                                + ui.jauge(det.points / det.critere.poids, det.feu)])
        html(ui.tableau([("Critère", False), ("Valeur", True), ("Appréciation", False), ("Points", False)], lignes_note))

    st.caption("Passez le curseur sur les graphiques pour voir les valeurs et leur variation sur un an ; "
               "cliquez sur un élément de la légende pour le masquer.")

# ----------------------------------------------------------------------------- ratios détaillés

with onglet_ratios:
    html(ui.section("Retraitements bancaires"))
    if resultats_rt:
        st.caption("Les comptes sont retraités pour refléter la vision du banquier. Tous les ratios, la notation et "
                   "la simulation de prêt utilisent les comptes retraités ; la comparaison sectorielle et le score de "
                   "défaillance restent calculés sur les comptes bruts, comme les données publiques auxquelles ils se "
                   "comparent. Désactivable dans la barre latérale.")
        rb, rr = historique_brut[-1], historique[-1]
        nb_, nr_ = noter(rb), noter(rr)
        lignes_av = []
        for lib, attr, fmt in [("EBE", "ebe", keur), ("CAF", "caf", keur), ("Résultat net", "resultat_net", keur),
                               ("Dette financière nette", "dette_financiere_nette", keur),
                               ("Autonomie financière", "autonomie_financiere", pct),
                               ("Capacité de remboursement", "capacite_remboursement", lambda x: nb(x, " ans")),
                               ("Levier DFN / EBE", "levier_dfn_ebe", lambda x: nb(x, " ans"))]:
            lignes_av.append([escape(lib), fmt(getattr(rb, attr)), f"<b>{fmt(getattr(rr, attr))}</b>"])
        lignes_av.append(["<b>Note</b>", f"{nb_.note} ({nb_.score:.0f}/100)", f"<b>{nr_.note} ({nr_.score:.0f}/100)</b>"])
        ga, da = st.columns([1, 1.15])
        with ga:
            st.markdown(f"**Effet sur les indicateurs {rr.exercice}**")
            html(ui.tableau([("Indicateur", False), ("Comptes bruts", True), ("Retraités", True)], lignes_av))
        with da:
            st.markdown(f"**Écritures de retraitement {rr.exercice}**")
            lignes_aj = [[escape(a.retraitement), escape(a.poste),
                          ("+" if a.montant > 0 else "") + keur(a.montant)] for a in resultats_rt[-1].ajustements]
            html(ui.tableau([("Retraitement", False), ("Poste", False), ("Montant", True)], lignes_aj)
                 if lignes_aj else '<div class="detail">Aucun retraitement pour cet exercice.</div>')
    elif parametres_rt is None:
        st.info("Retraitements désactivés : l'analyse porte sur les comptes tels qu'ils sont publiés.")
    else:
        st.info("Aucune information d'annexe (crédit-bail, comptes courants bloqués, dividendes) : les comptes ne "
                "sont pas retraités. Ces informations se saisissent dans le modèle Excel.")

    sig = calculer_sig(comptes_dernier)
    c = comptes_dernier
    production = c.ventes_marchandises + sig.production_exercice
    achats = c.achats_marchandises + c.variation_stock_marchandises + c.achats_matieres + c.variation_stock_matieres
    etapes_cascade = [
        ("Production et ventes", production, "absolute"),
        ("Achats consommés", -achats, "relative"),
        ("Charges externes", -c.autres_achats_charges_externes, "relative"),
        ("Impôts et taxes, subventions", c.subventions_exploitation - c.impots_taxes, "relative"),
        ("Charges de personnel", -(c.salaires + c.charges_sociales), "relative"),
        ("EBE", sig.ebe, "total"),
        ("Amortissements et autres", sig.resultat_exploitation - sig.ebe, "relative"),
        ("Résultat d'exploitation", sig.resultat_exploitation, "total"),
        ("Résultat financier", c.produits_financiers - c.charges_financieres, "relative"),
        ("Exceptionnel et impôt", sig.resultat_net - sig.resultat_courant_avant_impot, "relative"),
        ("Résultat net", sig.resultat_net, "total"),
    ]
    html(ui.section(f"Du chiffre d'affaires au résultat net ({dernier.exercice})"))
    gc, dc = st.columns([2.2, 1])
    gc.plotly_chart(gr.cascade(etapes_cascade, "Soldes intermédiaires de gestion"), width="stretch")
    with dc:
        base = production or 1
        lignes_sig = [[escape(lib), keur(val), pct(val / base)] for lib, val in [
            ("Marge commerciale", sig.marge_commerciale), ("Production de l'exercice", sig.production_exercice),
            ("Valeur ajoutée", sig.valeur_ajoutee), ("EBE", sig.ebe),
            ("Résultat d'exploitation", sig.resultat_exploitation),
            ("Résultat courant avant impôt", sig.resultat_courant_avant_impot), ("Résultat net", sig.resultat_net)]]
        html(ui.tableau([("Solde", False), ("Montant", True), ("% production", True)], lignes_sig))
        st.caption("En vert les éléments qui augmentent le résultat, en pêche ceux qui le diminuent, "
                   "en bleu les soldes.")

    html(ui.section("Comparaison avec le secteur"))
    if comparaison and comparaison.positions:
        st.caption(f"Entreprises comparables : {comparaison.groupe.description}. Source : indicateurs sectoriels "
                   "financiers BCE/INPI publiés par Bercy. Chaque point situe l'entreprise parmi ces entreprises : "
                   "à droite, mieux que la plupart ; à gauche, moins bien." + (
                       "" if code_naf else " Code NAF non renseigné : comparaison avec l'ensemble des entreprises."))
        st.plotly_chart(gr.positionnement(comparaison.positions), width="stretch")
        unites = {"%": " %", "ans": " ans", "jours": " j", "jours de CA": " j"}

        def f(x, u):
            return f"{x:,.1f}".replace(",", "\u202f").replace(".", ",").replace("-", "−") + unites.get(u, "")

        lignes_sect = []
        for p in comparaison.positions:
            avis = ui.pastille(p.couleur, {"vert": "Meilleur que le secteur", "rouge": "Moins bon que le secteur",
                                           "orange": "Un peu en dessous"}[p.couleur]) if p.couleur else (
                '<span style="color:#8A96A3">Dans la norme</span>' if p.sens else '<span style="color:#8A96A3">Neutre</span>')
            lignes_sect.append([escape(p.libelle.split(" (")[0]), f(p.valeur, p.unite), f(p.mediane, p.unite),
                                f"{f(p.quantiles[1], p.unite)} à {f(p.quantiles[3], p.unite)}", avis])
        html(ui.tableau([("Ratio", False), ("Entreprise", True), ("Médiane du secteur", True),
                         ("Moitié centrale du secteur", True), ("Appréciation", False)], lignes_sect))
        st.caption("Les ratios suivent ici les définitions de la base publique, pour comparer à l'identique. Certains "
                   "diffèrent donc légèrement de ceux du reste de l'outil : par exemple, la capacité de remboursement "
                   "y rapporte toutes les dettes financières à la CAF, découverts compris.")
    else:
        st.info("Aucune référence sectorielle disponible pour cette entreprise.")

    export = []
    for famille, attributs in FAMILLES.items():
        html(ui.section(famille))
        lignes_ratios = []
        for a in attributs:
            libelle, anglais, definition = GLOSSAIRE[a]
            valeurs = [getattr(r, a) for r in historique]
            avis = ui.pastille(feux[a]) if a in feux else '<span style="color:#A0AAB4">—</span>'
            lignes_ratios.append([f"<b>{escape(libelle)}</b> <span class='en'>{escape(anglais)}</span>"
                                  f"<div class='def'>{escape(definition)}</div>"]
                                 + [FORMATS[a](v) for v in valeurs] + [ui.sparkline(valeurs), avis])
            export.append({"Famille": famille, "Indicateur": libelle, "Anglais": anglais,
                           **{str(r.exercice): FORMATS[a](getattr(r, a)) for r in historique}})
        html(ui.tableau([("Indicateur", False)] + [(str(an), True) for an in annees]
                        + [("Tendance", False), (f"Appréciation {dernier.exercice}", False)], lignes_ratios))
    st.write("")
    st.download_button("Télécharger les ratios (CSV)",
                       pd.DataFrame(export).to_csv(index=False, sep=";").encode("utf-8-sig"), "ratios.csv")

# ----------------------------------------------------------------------------- simulation de prêt

with onglet_pret:
    demande = dossier.get("demande_credit") or {}
    if demande.get("objet"):
        html(ui.section(f"Demande : {demande['objet']}"))
    else:
        html(ui.section("Paramètres du financement"))
    p1, p2, p3, p4 = st.columns(4)
    montant = p1.number_input("Montant (€)", 5_000, 50_000_000, int(demande.get("montant") or 150_000), 5_000)
    taux = p2.number_input("Taux annuel (%)", 0.0, 15.0, float(demande.get("taux_annuel") or 0.04) * 100, 0.05,
                           format="%.2f") / 100
    duree = p3.slider("Durée (mois)", 12, 240, int(demande.get("duree_mois") or 84), 12)
    residuelle = p4.number_input("Durée résiduelle des prêts existants (ans)", 1.0, 20.0, 5.0, 0.5,
                                 help="Sans échéancier détaillé, le remboursement annuel des dettes existantes "
                                      "est estimé par : dettes à moyen et long terme / durée résiduelle.")
    dettes_lmt = comptes_dernier.emprunts_bancaires + comptes_dernier.autres_dettes_financieres
    s = simuler(dernier, dettes_lmt, montant, taux, duree, residuelle)
    maximum = montant_maximal(dernier.caf, s.annuites_existantes_estimees, taux, duree)

    couverture = s.taux_couverture
    couleur = "rouge" if couverture is None or couverture < 1 else "orange" if couverture < 1.25 else "vert"
    k = st.columns(5)
    cartes = [
        ui.carte("Mensualité", eur(s.mensualite), f"Soit {keur(s.annuite_nouveau_pret)} par an"),
        ui.carte("Coût total des intérêts", eur(s.cout_total_interets), f"Sur {duree // 12} ans et {duree % 12} mois"
                 if duree % 12 else f"Sur {duree // 12} ans"),
        ui.carte("Taux de couverture (DSCR)", nb(couverture, " x"), "Seuil retenu : 1,25 x",
                 "Suffisant" if couleur == "vert" else "Insuffisant", couleur == "vert", GLOSSAIRE["taux_couverture"][2]),
        ui.carte("Dettes / CAF après prêt", nb(s.capacite_remboursement_apres, " ans"), "Repère : moins de 3 à 4 ans"),
        ui.carte("Montant maximal finançable", keur(maximum), f"À {pct(taux)} sur {duree} mois, DSCR de 1,25 x"),
    ]
    for col, contenu in zip(k, cartes):
        with col:
            html(contenu)
    st.write("")
    titres = {"vert": "Financement soutenable", "orange": "Soutenable sans marge de sécurité",
              "rouge": "Financement non soutenable"}
    conseil = ""
    if couleur != "vert":
        conseil = (f" Pour respecter le seuil, le montant devrait être ramené à {keur(maximum)}, ou la durée allongée."
                   if maximum > 0 else " Les remboursements existants absorbent déjà toute la capacité de l'entreprise.")
    html(ui.bloc(couleur, s.commentaire + conseil, titres[couleur]))

    g1, g2 = st.columns(2)
    g1.plotly_chart(gr.financement(dernier.caf, s.annuites_existantes_estimees, s.annuite_nouveau_pret), width="stretch")
    tableau = pd.DataFrame(tableau_amortissement(montant, taux, duree))
    tableau["annee"] = (tableau["mois"] - 1) // 12 + 1
    par_an = tableau.groupby("annee").agg(Mensualités=("mensualite", "sum"), Intérêts=("interets", "sum"),
                                          Capital=("capital", "sum"), Restant=("capital_restant", "last"))
    g2.plotly_chart(gr.amortissement(par_an), width="stretch")

    html(ui.section("Scénario de crise"))
    st.caption("Que devient la capacité de remboursement si l'activité baisse ? Les achats consommés baissent au même "
               "rythme que les ventes, les charges externes pour leur seule part variable ; salaires, impôts et taxes, "
               "amortissements et frais financiers restent fixes.")
    c1, c2, c3 = st.columns(3)
    baisse = c1.slider("Baisse du chiffre d'affaires", 0, 40, 10, 1, format="%d %%") / 100
    part_var = c2.slider("Part variable des charges externes", 0, 100, 50, 5, format="%d %%",
                         help="Sous-traitance, transport, énergie de production : variables. Loyers, assurances, "
                              "honoraires : fixes.") / 100
    delai = c3.slider("Allongement du délai clients", 0, 60, 0, 5, format="%d jours",
                      help="Les clients paient plus tard : la trésorerie se dégrade, sans effet sur la CAF.")
    comptes_prec = exercices[-2] if len(exercices) > 1 else None
    crise = tester(comptes_dernier, comptes_prec, Scenario(baisse, part_var, delai), montant, taux, duree, residuelle)
    seuil = seuil_resistance(comptes_dernier, comptes_prec, montant, taux, duree, residuelle, part_var)

    def couleur_couv(x):
        return "rouge" if x is None or x < 1 else "orange" if x < 1.25 else "vert"

    lignes_crise = []
    for lib, a, b in [("Chiffre d'affaires", keur(dernier.chiffre_affaires), keur(crise.ratios.chiffre_affaires)),
                      ("EBE", keur(dernier.ebe), keur(crise.ratios.ebe)),
                      ("Taux d'EBE", pct(dernier.taux_ebe), pct(crise.ratios.taux_ebe)),
                      ("CAF", keur(dernier.caf), keur(crise.ratios.caf)),
                      ("Trésorerie nette", keur(dernier.tresorerie_nette), keur(crise.ratios.tresorerie_nette))]:
        lignes_crise.append([escape(lib), a, f"<b>{b}</b>"])
    lignes_crise.append(["Taux de couverture", ui.pastille(couleur_couv(s.taux_couverture), nb(s.taux_couverture, " x")),
                         ui.pastille(couleur_couv(crise.simulation.taux_couverture),
                                     nb(crise.simulation.taux_couverture if crise.ratios.caf > 0 else 0, " x"))])
    lignes_crise.append(["Note", f"{notation.note} ({notation.score:.0f}/100)",
                         f"<b>{crise.notation.note} ({crise.notation.score:.0f}/100)</b>"])
    gc, dc = st.columns([1, 1.25])
    with gc:
        html(ui.tableau([("Indicateur", False), ("Situation actuelle", True), (f"Crise (−{baisse * 100:.0f} %)", True)],
                        lignes_crise))
        st.write("")
        if seuil is None:
            html(ui.bloc("rouge", "Le taux de couverture est déjà sous 1,25 sans baisse d'activité : le financement "
                                  "n'a aucune marge de résistance.", "Seuil de résistance"))
        else:
            couleur_seuil = "vert" if seuil >= 0.15 else "orange" if seuil >= 0.05 else "rouge"
            html(ui.bloc(couleur_seuil, f"Le financement reste soutenable tant que la baisse du chiffre d'affaires ne "
                                        f"dépasse pas {seuil * 100:.0f} %.",
                         "Seuil de résistance"))
        if delai:
            st.caption(f"L'allongement de {delai} jours du délai clients consomme environ {keur(crise.besoin_tresorerie)} "
                       "de trésorerie supplémentaire (y compris la baisse de résultat).")
    with dc:
        st.plotly_chart(gr.courbe_stress(couverture_selon_baisse(comptes_dernier, comptes_prec, montant, taux, duree,
                                                                 residuelle, part_var), baisse, seuil),
                        width="stretch")

    html(ui.section("Sensibilité du taux de couverture"))
    st.caption("Taux de couverture obtenu pour le même montant, selon la durée et le taux. "
               "Vert : au moins 1,25 x ; jaune : entre 1 et 1,25 x ; rouge : moins de 1 x.")
    taux_testes = sorted({max(0.0, round(taux + d, 4)) for d in (-0.01, -0.005, 0, 0.005, 0.01)})
    durees_testees = sorted({60, 84, 120, 180, duree})
    lignes_sens = []
    for dm in durees_testees:
        ligne = [f"<b>{dm} mois</b>" + (" <span class='en'>(choisi)</span>" if dm == duree else "")]
        for t in taux_testes:
            dscr = simuler(dernier, dettes_lmt, montant, t, dm, residuelle).taux_couverture
            c_cell = "rouge" if dscr is None or dscr < 1 else "orange" if dscr < 1.25 else "vert"
            ligne.append(ui.pastille(c_cell, nb(dscr, " x")))
        lignes_sens.append(ligne)
    html(ui.tableau([("Durée", False)] + [(pct(t) + (" (choisi)" if t == round(taux, 4) else ""), False)
                                         for t in taux_testes], lignes_sens))

    with st.expander("Tableau d'amortissement annuel"):
        st.dataframe(par_an.apply(lambda col: col.map(eur)).rename_axis("Année"), width="stretch")
        st.download_button("Télécharger le tableau mensuel (CSV)",
                           tableau.drop(columns="annee").to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           "tableau_amortissement.csv")

# ----------------------------------------------------------------------------- note de crédit PDF

try:
    pdf = generer_note(dossier, montant, taux, duree, residuelle, retraitements=parametres_rt,
                       scenario=Scenario(baisse, part_var, delai))
    nom_pdf = "note_credit_" + "".join(ch if ch.isalnum() else "_" for ch in
                                       (dossier.get("entreprise", {}).get("raison_sociale") or "pme"))[:40] + ".pdf"
    zone_pdf.download_button("Télécharger la note de crédit (PDF)", pdf, nom_pdf, mime="application/pdf",
                             type="primary", width="stretch", key="pdf_synthese")
    with onglet_pret:
        st.download_button("Télécharger la note de crédit avec ces paramètres (PDF)", pdf, nom_pdf,
                           mime="application/pdf", type="primary", key="pdf_pret")
except Exception as e:  # la note ne doit jamais empêcher l'affichage de l'analyse
    zone_pdf.caption(f"Note PDF indisponible : {e}")
