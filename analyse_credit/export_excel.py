"""Création de classeurs Excel au format du modèle de saisie (vierge ou pré-rempli)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from .postes import INFOS_DEMANDE, INFOS_ENTREPRISE, SECTIONS

POLICE = "Arial"
BLEU_SAISIE = Font(name=POLICE, size=10, color="0000FF")
NORMAL = Font(name=POLICE, size=10)
GRAS = Font(name=POLICE, size=10, bold=True)
AIDE = Font(name=POLICE, size=9, italic=True, color="666666")
TITRE = Font(name=POLICE, size=14, bold=True, color="1F3864")
SECTION = Font(name=POLICE, size=10, bold=True, color="FFFFFF")
FOND_SAISIE = PatternFill("solid", fgColor="FFFF99")
FOND_SECTION = PatternFill("solid", fgColor="1F3864")
FOND_CONTROLE = PatternFill("solid", fgColor="E7E6E6")
# Mise en forme conditionnelle : Excel lit la couleur de fond (bgColor), on renseigne donc les deux
FOND_VERT = PatternFill(fill_type="solid", start_color="FFC6EFCE", end_color="FFC6EFCE")
FOND_ROUGE = PatternFill(fill_type="solid", start_color="FFFFC7CE", end_color="FFFFC7CE")
FIN = Side(style="thin", color="BFBFBF")
BORDURE = Border(left=FIN, right=FIN, top=FIN, bottom=FIN)
FORMAT_EUROS = '#,##0 "€";-#,##0 "€";"-"'
COLONNES_EXERCICES = ["C", "D", "E"]


def onglet_mode_emploi(wb):
    ws = wb.active
    ws.title = "Mode d'emploi"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 100
    lignes = [
        ("Modèle de saisie — Analyse crédit PME", TITRE),
        ("", NORMAL),
        ("À quoi sert ce fichier ?", GRAS),
        ("Il rassemble les comptes annuels d'une entreprise (liasse fiscale simplifiée) pour les analyser "
         "avec l'outil analyse-credit-pme : SIG, CAF, BFR, ratios bancaires, notation et simulation de prêt.", NORMAL),
        ("", NORMAL),
        ("Comment le remplir ?", GRAS),
        ("1. Onglet « Dossier » : renseignez l'entreprise et, si besoin, la demande de crédit.", NORMAL),
        ("2. Onglet « Comptes » : indiquez les années en haut des colonnes (de la plus ancienne à la plus récente), "
         "puis recopiez les montants de la liasse fiscale, en euros.", NORMAL),
        ("3. Vérifiez le bloc « Contrôles » en bas de l'onglet Comptes : le statut doit afficher « Bilan équilibré ».", NORMAL),
        ("4. Lancez l'analyse : python analyser.py mon_fichier.xlsx", NORMAL),
        ("", NORMAL),
        ("Légende", GRAS),
        ("Cellules jaunes, texte bleu : à remplir. Les autres cellules sont calculées automatiquement.", NORMAL),
        ("Une cellule vide est lue comme 0. Une ou deux années suffisent, l'outil s'adapte.", NORMAL),
        ("Ne modifiez pas la colonne A masquée : elle contient les codes que le programme utilise pour lire le fichier.", NORMAL),
        ("", NORMAL),
        ("Confidentialité", GRAS),
        ("N'enregistrez jamais les comptes d'un client réel dans un dossier publié sur GitHub. "
         "Le fichier .gitignore du projet bloque par défaut les fichiers Excel, sauf le modèle et l'exemple fictif.", NORMAL),
    ]
    for i, (texte, police) in enumerate(lignes, start=2):
        c = ws.cell(row=i, column=2, value=texte)
        c.font = police
        c.alignment = Alignment(wrap_text=True, vertical="top")


def onglet_dossier(wb, dossier=None):
    ws = wb.create_sheet("Dossier")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].hidden = True
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 55
    ws["B1"] = "Dossier"
    ws["B1"].font = TITRE
    entreprise = (dossier or {}).get("entreprise", {})
    demande = (dossier or {}).get("demande_credit", {})

    ligne = 3
    for titre, champs, valeurs in (("Entreprise", INFOS_ENTREPRISE, entreprise),
                                   ("Demande de crédit (facultatif)", INFOS_DEMANDE, demande)):
        for col in "BC":
            ws[f"{col}{ligne}"].fill = FOND_SECTION
        ws[f"B{ligne}"] = titre
        ws[f"B{ligne}"].font = SECTION
        ligne += 1
        for code, libelle, nature in champs:
            ws[f"A{ligne}"] = code
            ws[f"B{ligne}"] = libelle
            ws[f"B{ligne}"].font = NORMAL
            c = ws[f"C{ligne}"]
            c.value = valeurs.get(code)
            c.font = BLEU_SAISIE
            c.fill = FOND_SAISIE
            c.border = BORDURE
            if nature == "euros":
                c.number_format = FORMAT_EUROS
            elif nature == "pourcentage":
                c.number_format = "0.00%"
                c.comment = Comment("Saisir par exemple 4,2 %", "Modèle")
            elif nature == "nombre":
                c.number_format = "0"
            ligne += 1
        ligne += 1


def onglet_comptes(wb, dossier=None):
    ws = wb.create_sheet("Comptes")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].hidden = True
    ws.column_dimensions["B"].width = 50
    for col in COLONNES_EXERCICES:
        ws.column_dimensions[col].width = 16
    ws.column_dimensions["F"].width = 60

    ws["B1"] = "Comptes annuels (en euros)"
    ws["B1"].font = TITRE
    ws["B2"] = "Cellules jaunes à remplir. Colonnes de l'exercice le plus ancien (C) au plus récent (E)."
    ws["B2"].font = AIDE

    exercices = sorted((dossier or {}).get("exercices", []), key=lambda e: e["exercice"])
    if len(exercices) > len(COLONNES_EXERCICES):
        exercices = exercices[-len(COLONNES_EXERCICES):]

    # Ligne des années
    ws["A4"] = "exercice"
    ws["B4"] = "Exercice (année de clôture)"
    ws["B4"].font = GRAS
    ws["F4"] = "Aide à la saisie"
    ws["F4"].font = GRAS
    for i, col in enumerate(COLONNES_EXERCICES):
        c = ws[f"{col}4"]
        c.value = exercices[i]["exercice"] if i < len(exercices) else None
        c.font = Font(name=POLICE, size=10, bold=True, color="0000FF")
        c.fill = FOND_SAISIE
        c.border = BORDURE
        c.alignment = Alignment(horizontal="center")
        c.number_format = "0"

    ligne = 6
    rang = {}
    actif, passif = [], []
    for titre, postes in SECTIONS:
        for col in ["B", *COLONNES_EXERCICES, "F"]:
            ws[f"{col}{ligne}"].fill = FOND_SECTION
        ws[f"B{ligne}"] = titre
        ws[f"B{ligne}"].font = SECTION
        ligne += 1
        for code, libelle, aide in postes:
            rang[code] = ligne
            if titre.startswith("BILAN — Actif"):
                actif.append(ligne)
            elif titre.startswith("BILAN — Passif"):
                passif.append(ligne)
            ws[f"A{ligne}"] = code
            ws[f"B{ligne}"] = libelle
            ws[f"B{ligne}"].font = NORMAL
            for i, col in enumerate(COLONNES_EXERCICES):
                c = ws[f"{col}{ligne}"]
                if i < len(exercices):
                    v = exercices[i].get(code, 0)
                    c.value = v if v else None
                c.font = BLEU_SAISIE
                c.fill = FOND_SAISIE
                c.border = BORDURE
                c.number_format = FORMAT_EUROS
            ws[f"F{ligne}"] = aide
            ws[f"F{ligne}"].font = AIDE
            ligne += 1
        ligne += 1

    # --- Contrôles (formules)
    for col in ["B", *COLONNES_EXERCICES, "F"]:
        ws[f"{col}{ligne}"].fill = FOND_SECTION
    ws[f"B{ligne}"] = "CONTRÔLES (calculés automatiquement)"
    ws[f"B{ligne}"].font = SECTION
    ligne += 1

    def r(code):
        return rang[code]

    def somme(col, lignes_):
        return "+".join(f"{col}{n}" for n in lignes_)

    controles = [
        ("Chiffre d'affaires", lambda c: f"={c}{r('ventes_marchandises')}+{c}{r('production_vendue')}",
         "Ventes de marchandises + production vendue"),
        ("Excédent brut d'exploitation (EBE)", lambda c: (
            f"={c}{r('ventes_marchandises')}-{c}{r('achats_marchandises')}-{c}{r('variation_stock_marchandises')}"
            f"+{c}{r('production_vendue')}+{c}{r('production_stockee')}+{c}{r('production_immobilisee')}"
            f"-{c}{r('achats_matieres')}-{c}{r('variation_stock_matieres')}-{c}{r('autres_achats_charges_externes')}"
            f"+{c}{r('subventions_exploitation')}-{c}{r('impots_taxes')}-{c}{r('salaires')}-{c}{r('charges_sociales')}"),
         "Valeur ajoutée + subventions − impôts et taxes − charges de personnel"),
        ("Résultat net calculé", None, "À comparer avec le résultat net de la liasse"),
        ("Total actif", lambda c: f"={somme(c, actif)}", ""),
        ("Total passif", lambda c: f"={somme(c, passif)}", ""),
        ("Écart actif − passif", None, "Doit être égal à 0"),
        ("Statut", None, ""),
    ]
    debut = ligne
    lignes_ctrl = {}
    for libelle, formule, aide in controles:
        lignes_ctrl[libelle] = ligne
        ws[f"B{ligne}"] = libelle
        ws[f"B{ligne}"].font = GRAS if libelle == "Statut" else NORMAL
        ws[f"F{ligne}"] = aide
        ws[f"F{ligne}"].font = AIDE
        for col in COLONNES_EXERCICES:
            c = ws[f"{col}{ligne}"]
            c.fill = FOND_CONTROLE
            c.border = BORDURE
            c.font = NORMAL
            c.number_format = FORMAT_EUROS
            if formule:
                c.value = formule(col)
        ligne += 1

    ebe_l = lignes_ctrl["Excédent brut d'exploitation (EBE)"]
    rn_l = lignes_ctrl["Résultat net calculé"]
    ecart_l = lignes_ctrl["Écart actif − passif"]
    statut_l = lignes_ctrl["Statut"]
    for col in COLONNES_EXERCICES:
        ws[f"{col}{rn_l}"] = (
            f"={col}{ebe_l}+{col}{r('reprises_provisions')}+{col}{r('autres_produits')}"
            f"-{col}{r('dotations_amortissements_provisions')}-{col}{r('autres_charges')}"
            f"+{col}{r('produits_financiers')}-{col}{r('charges_financieres')}"
            f"+{col}{r('produits_exceptionnels')}-{col}{r('charges_exceptionnelles')}"
            f"-{col}{r('participation_salaries')}-{col}{r('impot_benefices')}")
        ws[f"{col}{ecart_l}"] = f"={col}{lignes_ctrl['Total actif']}-{col}{lignes_ctrl['Total passif']}"
        c = ws[f"{col}{statut_l}"]
        c.value = (f'=IF({col}$4="","",IF(ABS({col}{ecart_l})<=1,"Bilan équilibré","Bilan déséquilibré"))')
        c.number_format = "General"
        c.font = GRAS
        c.alignment = Alignment(horizontal="center")

    plage = f"C{statut_l}:E{statut_l}"
    ws.conditional_formatting.add(plage, FormulaRule(formula=[f'C{statut_l}="Bilan équilibré"'], fill=FOND_VERT, font=Font(color="FF006100", bold=True)))
    ws.conditional_formatting.add(plage, FormulaRule(formula=[f'C{statut_l}="Bilan déséquilibré"'], fill=FOND_ROUGE, font=Font(color="FF9C0006", bold=True)))
    ws.freeze_panes = "C5"
    return debut


def ecrire_classeur(chemin: str | Path, dossier: dict | None = None, avertissements: list[str] | None = None) -> Path:
    """Écrit un classeur au format du modèle. Sans dossier, produit le modèle vierge."""
    chemin = Path(chemin)
    wb = Workbook()
    onglet_mode_emploi(wb)
    onglet_dossier(wb, dossier)
    onglet_comptes(wb, dossier)
    if avertissements:
        ws = wb.create_sheet("À vérifier", 1)
        ws.sheet_view.showGridLines = False
        ws.column_dimensions["B"].width = 110
        ws["B2"] = "Points à vérifier avant l'analyse"
        ws["B2"].font = TITRE
        for i, texte in enumerate(avertissements, start=4):
            c = ws.cell(row=i, column=2, value=f"• {texte}")
            c.font = NORMAL
            c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.active = wb.sheetnames.index("Dossier" if dossier is None else "Comptes")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    wb.save(chemin)
    return chemin
