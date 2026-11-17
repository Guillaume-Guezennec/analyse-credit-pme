"""Petits composants HTML réutilisables (en-tête, cartes, blocs d'appréciation, tableaux).

Le HTML est écrit sur une seule ligne : Streamlit interprète le Markdown, et une ligne
indentée y serait affichée comme du code.
"""

from __future__ import annotations

from html import escape

from .theme import APPRECIATIONS, SERIES, SENS_VERS_COULEUR

DECOR_ENTETE = (
    '<svg class="decor" viewBox="0 0 520 200" preserveAspectRatio="xMaxYMid slice" xmlns="http://www.w3.org/2000/svg">'
    '<g stroke="#D5DCE3" stroke-width="1">'
    + "".join(f'<line x1="40" x2="520" y1="{y}" y2="{y}"/>' for y in (40, 80, 120, 160))
    + "</g>"
    + "".join(
        f'<rect x="{x}" y="{200 - h}" width="26" height="{h}" rx="5" fill="{SERIES[i % 3]["fond"]}"/>'
        for i, (x, h) in enumerate([(90, 70), (130, 95), (170, 80), (210, 120), (250, 105), (290, 140),
                                    (330, 125), (370, 160), (410, 150), (450, 185)]))
    + '<polyline points="103,118 143,96 183,108 223,72 263,84 303,52 343,64 383,30 423,40 463,14" fill="none" '
      'stroke="#5E9DC2" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    + "".join(f'<circle cx="{x}" cy="{y}" r="5" fill="#FFFFFF" stroke="#5E9DC2" stroke-width="2.5"/>'
              for x, y in [(223, 72), (303, 52), (383, 30), (463, 14)])
    + "</svg>"
)


def entete(titre: str, sous_titre: str, etiquettes: list[tuple[str, bool]] | None = None) -> str:
    puces = "".join(f'<span class="etiquette{" forte" if forte else ""}">{escape(t)}</span>' for t, forte in etiquettes or [])
    societe = f'<div class="societe">{puces}</div>' if puces else ""
    return (f'<div class="entete">{DECOR_ENTETE}<div style="position:relative">'
            f'<div class="surtitre">Outil d\'aide à la décision de crédit</div>'
            f'<h1>{escape(titre)}</h1><div class="sous-titre">{escape(sous_titre)}</div>{societe}</div></div>')


def section(titre: str) -> str:
    return f'<div class="section">{escape(titre)}</div>'


def bloc(couleur: str, texte: str, titre: str | None = None) -> str:
    a = APPRECIATIONS[couleur]
    titre = titre or a["point"]
    return (f'<div class="bloc" style="background:{a["fond"]};border-color:{a["bord"]};color:{a["texte"]}">'
            f'<div class="titre">{escape(titre)}</div><div class="texte">{escape(texte)}</div></div>')


def bloc_constat(sens: str, texte: str) -> str:
    return bloc(SENS_VERS_COULEUR[sens], texte)


def pastille(couleur: str, texte: str | None = None) -> str:
    a = APPRECIATIONS[couleur]
    return (f'<span class="pastille" style="background:{a["fond"]};color:{a["texte"]};border:1px solid {a["bord"]}">'
            f'{escape(texte or a["avis"])}</span>')


def jauge(part: float, couleur: str) -> str:
    part = max(0.0, min(1.0, part))
    return f'<div class="jauge"><div style="width:{part * 100:.0f}%;background:{APPRECIATIONS[couleur]["accent"]}"></div></div>'


def carte(libelle: str, valeur: str, detail: str = "", variation: str | None = None,
          favorable: bool | None = None, aide: str = "") -> str:
    var = ""
    if variation:
        if favorable is None:
            style = "background:#F1F3F5;color:#52606D"
        else:
            a = APPRECIATIONS["vert" if favorable else "rouge"]
            style = f'background:{a["fond"]};color:{a["texte"]}'
        var = f'<span class="variation" style="{style}">{escape(variation)}</span>'
    titre_aide = f' title="{escape(aide)}"' if aide else ""
    return (f'<div class="carte"{titre_aide}><div class="libelle">{escape(libelle)}</div>'
            f'<div class="valeur">{escape(valeur)}</div>{var}'
            f'{f"<div class=detail>{escape(detail)}</div>" if detail else ""}</div>')


def carte_note(note: str, score: float, libelle: str, exercice: int) -> str:
    couleur = "vert" if note in ("A", "B") else "orange" if note == "C" else "rouge"
    a = APPRECIATIONS[couleur]
    return (f'<div class="carte" style="background:{a["fond"]};border-color:{a["bord"]}">'
            f'<div class="libelle" style="color:{a["texte"]}">Note de risque {exercice}</div>'
            f'<div style="display:flex;align-items:baseline;gap:10px;margin-top:2px">'
            f'<span style="font-size:2.6rem;font-weight:750;color:{a["texte"]};line-height:1">{note}</span>'
            f'<span style="font-size:1.05rem;color:{a["texte"]};font-weight:600">{score:.0f} / 100</span></div>'
            f'<div style="margin-top:8px">{jauge(score / 100, couleur)}</div>'
            f'<div class="detail" style="color:{a["texte"]}">{escape(libelle)}</div></div>')


def sparkline(valeurs: list[float | None], largeur: int = 90, hauteur: int = 26) -> str:
    points = [(i, v) for i, v in enumerate(valeurs) if v is not None]
    if len(points) < 2:
        return ""
    vs = [v for _, v in points]
    bas, haut = min(vs), max(vs)
    ecart = (haut - bas) or 1
    n = len(valeurs) - 1 or 1
    coords = [(4 + i * (largeur - 8) / n, hauteur - 4 - (v - bas) / ecart * (hauteur - 8)) for i, v in points]
    trace = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    x, y = coords[-1]
    return (f'<svg width="{largeur}" height="{hauteur}" viewBox="0 0 {largeur} {hauteur}">'
            f'<polyline points="{trace}" fill="none" stroke="{SERIES[0]["trait"]}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{SERIES[0]["trait"]}"/></svg>')


def tableau(entetes: list[tuple[str, bool]], lignes: list[list[str]]) -> str:
    """entetes : (libellé, aligné à droite). Les cellules sont du HTML déjà échappé."""
    th = "".join(f'<th class="{"nombre" if droite else ""}">{escape(t)}</th>' for t, droite in entetes)
    corps = "".join("<tr>" + "".join(f'<td class="{"nombre" if entetes[i][1] else ""}">{c}</td>'
                                     for i, c in enumerate(ligne)) + "</tr>" for ligne in lignes)
    return f'<table class="tab"><thead><tr>{th}</tr></thead><tbody>{corps}</tbody></table>'


def etapes(liste: list[tuple[str, str]]) -> str:
    return '<div class="etapes">' + "".join(
        f'<div class="etape"><div class="num">{i}</div><div class="t">{escape(t)}</div><div class="d">{escape(d)}</div></div>'
        for i, (t, d) in enumerate(liste, start=1)) + "</div>"
