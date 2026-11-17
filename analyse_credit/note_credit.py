"""Génération de la note de crédit au format PDF (3 pages, présentation de comité de crédit).

Usage :
    from analyse_credit.note_credit import generer_note
    pdf = generer_note(dossier, montant=250_000, taux=0.042, duree_mois=84)   # -> bytes
"""

from __future__ import annotations

import io
from datetime import date
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .analyse import analyser_historique
from .commentaires import commenter
from .modele import ComptesAnnuels
from .scoring import noter
from .simulation_pret import montant_maximal, simuler

# ----------------------------------------------------------------------------- palette (identique à l'application)

ENCRE = colors.HexColor("#1F2933")
ENCRE_2 = colors.HexColor("#52606D")
GRIS = colors.HexColor("#EEF1F4")
TRAIT = colors.HexColor("#E4E8EC")
SERIES = [("#A8D0E6", "#5E9DC2"), ("#FFC8A2", "#E59563"), ("#C7DDB5", "#86AD69")]
APPRECIATIONS = {
    "rouge": ("#FDECEC", "#9B2C2C", "Point faible", "Défavorable"),
    "orange": ("#FEF6E0", "#7A5A0C", "À surveiller", "À surveiller"),
    "vert": ("#F1F9E6", "#3E6B1F", "Point fort", "Favorable"),
}
SENS = {"negatif": "rouge", "vigilance": "orange", "positif": "vert"}

LARGEUR = A4[0] - 36 * mm


# ----------------------------------------------------------------------------- texte et formats

def _t(texte) -> str:
    """Rend un texte compatible avec les polices PDF standard et l'échappe pour les paragraphes."""
    s = str(texte)
    for a, b in ((" ", "\xa0"), ("−", "-"), ("—", "-"), ("–", "-"), ("’", "'"), ("≥", ">="), ("≤", "<=")):
        s = s.replace(a, b)
    return escape(s)


def _nombre(x, decimales=0):
    return f"{x:,.{decimales}f}".replace(",", "\xa0").replace(".", ",")


def eur(x):
    return "n.d." if x is None else _nombre(x) + "\xa0€"


def keur(x):
    return "n.d." if x is None else _nombre(x / 1000) + "\xa0k€"


def pct(x):
    return "n.d." if x is None else _nombre(x * 100, 1) + "\xa0%"


def nb(x, unite=""):
    return "n.d." if x is None else _nombre(x, 2) + unite


def jours(x):
    return "n.d." if x is None else _nombre(x) + "\xa0j"


# ----------------------------------------------------------------------------- styles

def _style(nom, **kw):
    base = dict(fontName="Helvetica", fontSize=9.5, leading=13, textColor=ENCRE, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(nom, **base)


S = {
    "surtitre": _style("surtitre", fontName="Helvetica-Bold", fontSize=8, textColor=colors.HexColor("#5E9DC2"), leading=10),
    "titre": _style("titre", fontName="Helvetica-Bold", fontSize=20, leading=24),
    "sous": _style("sous", fontSize=9.5, textColor=ENCRE_2),
    "h2": _style("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16, spaceBefore=10, spaceAfter=6),
    "corps": _style("corps"),
    "petit": _style("petit", fontSize=8, leading=10.5, textColor=ENCRE_2),
    "cellule": _style("cellule", fontSize=8.8, leading=11.5),
    "cellule_d": _style("cellule_d", fontSize=8.8, leading=11.5, alignment=2),
    "entete_tab": _style("entete_tab", fontName="Helvetica-Bold", fontSize=7.8, leading=10, textColor=ENCRE_2),
    "entete_tab_d": _style("entete_tab_d", fontName="Helvetica-Bold", fontSize=7.8, leading=10, textColor=ENCRE_2, alignment=2),
}


def P(texte, style="corps", **kw):
    st = S[style] if not kw else ParagraphStyle(f"{style}_{id(kw)}", parent=S[style], **kw)
    return Paragraph(texte, st)


def titre_section(texte):
    """Titre précédé d'une petite barre bleu ciel, comme dans l'application."""
    t = Table([["", P(_t(texte), "h2", spaceBefore=0, spaceAfter=0)]], colWidths=[3, LARGEUR - 3])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(SERIES[0][0])),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 7), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return KeepTogether([Spacer(1, 7), t, Spacer(1, 5)])


def bloc(couleur, texte, titre=None, largeur=LARGEUR):
    fond, encre, point, _ = APPRECIATIONS[couleur]
    contenu = [P(_t((titre or point).upper()), "petit", fontName="Helvetica-Bold", textColor=colors.HexColor(encre),
                 fontSize=7.3, leading=9),
               P(_t(texte), "corps", textColor=colors.HexColor(encre), fontSize=9, leading=12)]
    t = Table([[contenu]], colWidths=[largeur])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fond)),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(fond).clone() if False else colors.HexColor(fond)),
        ("ROUNDEDCORNERS", [5, 5, 5, 5]),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def tableau(lignes, largeurs, droite=(), entete=True, styles_sup=()):
    """lignes : liste de listes de chaînes (déjà converties avec _t) ou de flowables."""
    donnees = []
    for i, ligne in enumerate(lignes):
        cellules = []
        for j, c in enumerate(ligne):
            if isinstance(c, str):
                if entete and i == 0:
                    c = P(c, "entete_tab_d" if j in droite else "entete_tab")
                else:
                    c = P(c, "cellule_d" if j in droite else "cellule")
            cellules.append(c)
        donnees.append(cellules)
    t = Table(donnees, colWidths=largeurs, repeatRows=1 if entete else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, TRAIT),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.6, TRAIT),
    ]
    if entete:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F7F9FA"))]
    t.setStyle(TableStyle(style + list(styles_sup)))
    return t


def pastille(couleur, texte=None):
    fond, encre, _, avis = APPRECIATIONS[couleur]
    t = Table([[P(_t(texte or avis), "cellule", fontName="Helvetica-Bold", fontSize=7.8, leading=9.5,
                  textColor=colors.HexColor(encre), alignment=1)]])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fond)), ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


# ----------------------------------------------------------------------------- graphique

def graphique_rentabilite(historique) -> Drawing:
    largeur, hauteur = LARGEUR, 62 * mm
    d = Drawing(largeur, hauteur)
    d.add(String(0, hauteur - 10, "Rentabilité (k€)", fontName="Helvetica-Bold", fontSize=9.5, fillColor=ENCRE))
    series = [("EBE", [r.ebe / 1000 for r in historique]), ("CAF", [r.caf / 1000 for r in historique]),
              ("Résultat net", [r.resultat_net / 1000 for r in historique])]
    bc = VerticalBarChart()
    bc.x, bc.y, bc.width, bc.height = 30, 22, largeur - 40, hauteur - 48
    bc.data = [v for _, v in series]
    bc.categoryAxis.categoryNames = [str(r.exercice) for r in historique]
    bas = min(0, min(min(v) for v in bc.data))
    haut = max(max(v) for v in bc.data)
    bc.valueAxis.valueMin = bas * 1.15 if bas < 0 else 0
    bc.valueAxis.valueMax = haut * 1.15
    bc.valueAxis.labels.fontName = bc.categoryAxis.labels.fontName = "Helvetica"
    bc.valueAxis.labels.fontSize = bc.categoryAxis.labels.fontSize = 7.5
    bc.valueAxis.labels.fillColor = bc.categoryAxis.labels.fillColor = ENCRE_2
    bc.valueAxis.strokeColor = colors.white
    bc.valueAxis.gridStrokeColor = GRIS
    bc.valueAxis.visibleGrid = True
    bc.categoryAxis.strokeColor = colors.HexColor("#C9D1D9")
    bc.categoryAxis.labelAxisMode = "low"
    bc.groupSpacing, bc.barSpacing = 14, 2
    for i, (fond, trait) in enumerate(SERIES):
        bc.bars[i].fillColor = colors.HexColor(fond)
        bc.bars[i].strokeColor = colors.HexColor(trait)
        bc.bars[i].strokeWidth = 0.7
    d.add(bc)
    leg = Legend()
    leg.x, leg.y = largeur - 200, hauteur - 6
    leg.alignment = "right"
    leg.columnMaximum = 1
    leg.fontName, leg.fontSize = "Helvetica", 7.5
    leg.dx = leg.dy = 7
    leg.deltax = 62
    leg.colorNamePairs = [(colors.HexColor(SERIES[i][0]), nom) for i, (nom, _) in enumerate(series)]
    d.add(leg)
    return d


# ----------------------------------------------------------------------------- conclusion proposée

def proposition_avis(notation, simulation, maximum, constats, montant) -> tuple[str, str]:
    textes = " ".join(c.texte for c in constats)
    pistes = []
    if maximum > 0 and not simulation.soutenable:
        pistes.append(f"ramener le montant à environ {keur(maximum)}, ou allonger la durée")
    if "BFR s'alourdit" in textes or "délai clients" in textes:
        pistes.append("traiter le poste clients (relances, affacturage) pour libérer de la trésorerie")
    if "Effet ciseaux" in textes:
        pistes.append("comprendre la baisse de marge et la capacité à répercuter les hausses de coûts sur les prix")
    if "Fonds propres insuffisants" in textes or not simulation.soutenable:
        pistes.append("étudier un apport en fonds propres ou en compte courant d'associé")
    pistes.append("examiner les garanties possibles (nantissement du matériel financé, caution, Bpifrance)")

    if simulation.soutenable and notation.note in ("A", "B"):
        return "vert", ("Proposition d'avis favorable. La situation financière est saine et la capacité "
                        "d'autofinancement couvre les remboursements avec une marge suffisante. Points à confirmer "
                        "lors de l'entretien : " + "; ".join(pistes[-1:]) + ".")
    if simulation.soutenable:
        return "orange", ("Proposition d'avis favorable sous conditions. Le financement est soutenable, mais "
                          f"la note {notation.note} appelle une vigilance. Pistes à étudier : " + "; ".join(pistes) + ".")
    return "rouge", (f"En l'état, le financement de {keur(montant)} n'est pas soutenable : la capacité "
                     "d'autofinancement ne couvre pas les remboursements. Avant de reconsidérer la demande, pistes à "
                     "étudier avec le client : " + "; ".join(pistes) + ".")


# ----------------------------------------------------------------------------- document

def generer_note(dossier: dict, montant: float | None = None, taux: float | None = None,
                 duree_mois: int | None = None, duree_residuelle_ans: float = 5.0,
                 auteur: str = "", date_note: date | None = None) -> bytes:
    exercices = [ComptesAnnuels.depuis_dict(e) for e in dossier["exercices"]]
    historique = analyser_historique(exercices)
    dernier = historique[-1]
    comptes = sorted(exercices, key=lambda e: e.exercice)[-1]
    notation = noter(dernier)
    constats = commenter(historique)
    ent = dossier.get("entreprise", {})
    demande = dossier.get("demande_credit") or {}
    montant = montant if montant is not None else float(demande.get("montant") or 150_000)
    taux = taux if taux is not None else float(demande.get("taux_annuel") or 0.04)
    duree_mois = duree_mois or int(demande.get("duree_mois") or 84)
    dettes_lmt = comptes.emprunts_bancaires + comptes.autres_dettes_financieres
    sim = simuler(dernier, dettes_lmt, montant, taux, duree_mois, duree_residuelle_ans)
    maximum = montant_maximal(dernier.caf, sim.annuites_existantes_estimees, taux, duree_mois)
    date_note = date_note or date.today()
    raison = ent.get("raison_sociale") or "Entreprise"

    tampon = io.BytesIO()

    def decor(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(GRIS)
        canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(ENCRE)
        canvas.drawString(18 * mm, A4[1] - 7.5 * mm, "NOTE DE CRÉDIT")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(ENCRE_2)
        canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 7.5 * mm, _t(raison).replace("&amp;", "&")[:80])
        canvas.setStrokeColor(TRAIT)
        canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(18 * mm, 9 * mm, "Document généré par Analyse crédit PME (analyse-credit-pme.streamlit.app). "
                                           "Aide à la décision à vocation pédagogique, à compléter par l'analyse du chargé d'affaires.")
        canvas.drawRightString(A4[0] - 18 * mm, 5.5 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm,
                            bottomMargin=18 * mm, title=f"Note de crédit - {raison}", author=auteur or "Analyse crédit PME",
                            subject="Analyse financière et proposition d'avis")
    h = []

    # ---------------- Page 1 : présentation et synthèse
    h.append(P("OUTIL D'AIDE À LA DÉCISION DE CRÉDIT", "surtitre"))
    h.append(Spacer(1, 3))
    h.append(P(_t(raison), "titre"))
    infos = [x for x in (ent.get("activite"), f"Effectif : {ent['effectif']}" if ent.get("effectif") else None,
                         f"Exercices analysés : {historique[0].exercice} à {dernier.exercice}"
                         if len(historique) > 1 else f"Exercice analysé : {dernier.exercice}") if x]
    h.append(P(_t(" · ".join(infos)), "sous"))
    h.append(P(_t(f"Note établie le {date_note.strftime('%d/%m/%Y')}" + (f" par {auteur}" if auteur else "")), "petit"))

    h.append(titre_section("Demande de financement"))
    lignes_demande = [
        ["Objet", _t(demande.get("objet") or "Financement simulé")],
        ["Montant", _t(eur(montant))],
        ["Conditions", _t(f"{pct(taux)} sur {duree_mois} mois, mensualité de {eur(sim.mensualite)}")],
        ["Coût total des intérêts", _t(eur(sim.cout_total_interets))],
    ]
    h.append(tableau(lignes_demande, [45 * mm, LARGEUR - 45 * mm], entete=False,
                     styles_sup=[("TEXTCOLOR", (0, 0), (0, -1), ENCRE_2)]))

    h.append(titre_section("Synthèse"))
    fond_note, encre_note = APPRECIATIONS["vert" if notation.note in "AB" else "orange" if notation.note == "C" else "rouge"][:2]
    couleur_fin = "rouge" if sim.taux_couverture is None or sim.taux_couverture < 1 else (
        "orange" if sim.taux_couverture < 1.25 else "vert")
    fond_fin, encre_fin = APPRECIATIONS[couleur_fin][:2]
    carte_note = [P(_t(f"Note de risque {dernier.exercice}"), "petit", textColor=colors.HexColor(encre_note)),
                  P(f"<font size=30>{notation.note}</font>&nbsp;&nbsp;<font size=11>{notation.score:.0f} / 100</font>", "corps",
                    fontName="Helvetica-Bold", textColor=colors.HexColor(encre_note), leading=34),
                  P(_t(notation.libelle), "corps", textColor=colors.HexColor(encre_note))]
    carte_fin = [P("Financement demandé", "petit", textColor=colors.HexColor(encre_fin)),
                 P(_t({"vert": "Soutenable", "orange": "Soutenable sans marge", "rouge": "Non soutenable"}[couleur_fin]),
                   "corps", fontName="Helvetica-Bold", fontSize=15, leading=22, textColor=colors.HexColor(encre_fin)),
                 P(_t(f"Taux de couverture : {nb(sim.taux_couverture, ' x')} (seuil 1,25 x)"), "corps",
                   textColor=colors.HexColor(encre_fin)),
                 P(_t(f"Montant maximal finançable : {keur(maximum)}" if maximum > 0
                     else "Aucune capacité d'emprunt supplémentaire"), "corps", textColor=colors.HexColor(encre_fin))]
    cles = [["Chiffre d'affaires", _t(keur(dernier.chiffre_affaires))], ["EBE", _t(f"{keur(dernier.ebe)} ({pct(dernier.taux_ebe)})")],
            ["CAF", _t(keur(dernier.caf))], ["Trésorerie nette", _t(keur(dernier.tresorerie_nette))],
            ["Dettes / CAF", _t(nb(dernier.capacite_remboursement, " ans"))]]
    t_cles = tableau(cles, [30 * mm, 34 * mm], droite=(1,), entete=False,
                     styles_sup=[("TEXTCOLOR", (0, 0), (0, -1), ENCRE_2), ("TOPPADDING", (0, 0), (-1, -1), 3),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 3)])
    l1 = 50 * mm
    l2 = LARGEUR - l1 - 64 * mm - 12
    synth = Table([[carte_note, carte_fin, t_cles]], colWidths=[l1, l2, 64 * mm + 12])
    synth.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(fond_note)), ("BACKGROUND", (1, 0), (1, 0), colors.HexColor(fond_fin)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (1, 0), 10), ("TOPPADDING", (0, 0), (1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (1, 0), 9), ("LEFTPADDING", (2, 0), (2, 0), 12), ("RIGHTPADDING", (2, 0), (2, 0), 0),
        ("TOPPADDING", (2, 0), (2, 0), 0), ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    h.append(synth)

    h.append(titre_section("Points clés de l'analyse"))
    ordre = {"negatif": 0, "vigilance": 1, "positif": 2}
    for c in sorted(constats, key=lambda c: ordre[c.sens]):
        h.append(bloc(SENS[c.sens], c.texte))
        h.append(Spacer(1, 4))

    # ---------------- Page 2 : analyse financière
    h.append(PageBreak())
    h.append(titre_section("Analyse financière"))
    annees = [str(r.exercice) for r in historique]
    lignes = [["Indicateur"] + annees]
    groupes = [
        ("Activité et rentabilité", [("Chiffre d'affaires", "chiffre_affaires", keur), ("Croissance du CA", "croissance_ca", pct),
                                     ("EBE", "ebe", keur), ("Taux d'EBE", "taux_ebe", pct),
                                     ("Résultat net", "resultat_net", keur), ("CAF", "caf", keur)]),
        ("Équilibre financier", [("Fonds de roulement", "frng", keur), ("BFR", "bfr", keur),
                                 ("BFR en jours de CA", "bfr_jours_ca", jours), ("Trésorerie nette", "tresorerie_nette", keur)]),
        ("Structure et endettement", [("Autonomie financière", "autonomie_financiere", pct),
                                      ("Dette financière nette", "dette_financiere_nette", keur),
                                      ("Gearing (DFN / capitaux propres)", "gearing", nb),
                                      ("Levier DFN / EBE", "levier_dfn_ebe", lambda x: nb(x, " ans")),
                                      ("Capacité de remboursement", "capacite_remboursement", lambda x: nb(x, " ans")),
                                      ("Frais financiers / EBE", "poids_charges_financieres", pct)]),
        ("Exploitation et liquidité", [("Délai clients", "delai_clients_jours", jours),
                                       ("Délai fournisseurs", "delai_fournisseurs_jours", jours),
                                       ("Liquidité générale", "liquidite_generale", nb)]),
    ]
    styles_groupes = []
    for titre, items in groupes:
        styles_groupes.append(("BACKGROUND", (0, len(lignes)), (-1, len(lignes)), GRIS))
        lignes.append([f"<b>{_t(titre)}</b>"] + [""] * len(annees))
        for lib, attr, fmt in items:
            lignes.append([_t(lib)] + [_t(fmt(getattr(r, attr))) for r in historique])
    col = (LARGEUR - 70 * mm) / len(annees)
    h.append(tableau(lignes, [70 * mm] + [col] * len(annees), droite=tuple(range(1, len(annees) + 1)),
                     styles_sup=styles_groupes + [("TOPPADDING", (0, 0), (-1, -1), 3.2),
                                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2)]))
    h.append(Spacer(1, 10))
    h.append(graphique_rentabilite(historique))

    # ---------------- Page 3 : notation, financement, avis
    h.append(PageBreak())
    h.append(titre_section(f"Détail de la notation {dernier.exercice}"))
    formats = {"capacite_remboursement": lambda x: nb(x, " ans"), "autonomie_financiere": pct, "taux_ebe": pct,
               "levier_dfn_ebe": lambda x: nb(x, " ans"), "poids_charges_financieres": pct, "liquidite_generale": nb,
               "rentabilite_nette": pct}
    lignes_note = [["Critère", "Valeur", "Appréciation", "Points"]]
    for d in notation.details:
        fmt = formats.get(d.critere.attribut, nb)
        lignes_note.append([_t(d.critere.nom), _t(fmt(d.valeur)), pastille(d.feu),
                            _t(f"{_nombre(d.points, 1)} / {d.critere.poids}")])
    lignes_note.append([f"<b>Total</b>", "", "", f"<b>{_nombre(notation.score, 0)} / 100 (note {notation.note})</b>"])
    h.append(tableau(lignes_note, [62 * mm, 28 * mm, 34 * mm, LARGEUR - 124 * mm], droite=(1, 3),
                     styles_sup=[("BACKGROUND", (0, -1), (-1, -1), GRIS)]))
    h.append(P(_t("Seuils indicatifs : capacité de remboursement favorable sous 3 ans et défavorable au-delà de 5 ans, "
                  "autonomie financière favorable au-delà de 30 %. Barème : A >= 80, B >= 65, C >= 50, D >= 35, E < 35."),
               "petit", spaceBefore=4))

    h.append(titre_section("Capacité de remboursement"))
    lignes_fin = [
        ["", "Montant annuel"],
        ["CAF du dernier exercice", _t(keur(dernier.caf))],
        [_t(f"Remboursements existants estimés (dettes MLT / {_nombre(duree_residuelle_ans, 1)} ans)"),
         _t(keur(sim.annuites_existantes_estimees))],
        ["Annuité du nouveau prêt", _t(keur(sim.annuite_nouveau_pret))],
        ["<b>Taux de couverture (CAF / annuités)</b>", f"<b>{_t(nb(sim.taux_couverture, ' x'))}</b>"],
        ["Dettes financières / CAF après le prêt", _t(nb(sim.capacite_remboursement_apres, " ans"))],
        [_t(f"Montant maximal finançable ({pct(taux)}, {duree_mois} mois, couverture de 1,25 x)"), _t(keur(maximum))],
    ]
    h.append(tableau(lignes_fin, [LARGEUR - 40 * mm, 40 * mm], droite=(1,)))

    h.append(titre_section("Proposition d'avis"))
    couleur_avis, texte_avis = proposition_avis(notation, sim, maximum, constats, montant)
    h.append(bloc(couleur_avis, texte_avis, "Proposition générée par l'outil, à valider"))
    h.append(Spacer(1, 8))
    lignes_vides = [[P("Avis du chargé d'affaires", "petit", fontName="Helvetica-Bold")]] + [[""] for _ in range(3)] + [
        [P("Date et signature :", "petit")]]
    avis = Table(lignes_vides, colWidths=[LARGEUR], rowHeights=[16] + [18] * 3 + [18])
    avis.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, TRAIT), ("LINEBELOW", (0, 1), (-1, 3), 0.4, TRAIT),
                              ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    h.append(KeepTogether(avis))

    h.append(titre_section("Méthode et limites"))
    h.append(P(_t("Analyse établie à partir des comptes annuels : soldes intermédiaires de gestion, capacité "
                  "d'autofinancement (méthode additive), bilan fonctionnel et ratios. La notation repose sur sept critères "
                  "pondérés dont les seuils sont des repères pédagogiques usuels, à adapter au secteur. Sans échéancier "
                  "détaillé, les remboursements existants sont estimés. L'analyse est uniquement financière : elle ne "
                  "remplace ni la connaissance du dirigeant et du marché, ni l'étude des garanties et de l'historique bancaire."),
               "petit"))

    doc.build(h, onFirstPage=decor, onLaterPages=decor)
    return tampon.getvalue()
