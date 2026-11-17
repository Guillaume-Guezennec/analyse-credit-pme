"""Graphiques Plotly aux couleurs pastel de l'application.

Toujours un seul axe vertical par graphique, une légende dès deux séries,
et une infobulle au survol qui donne la valeur et sa variation sur un an.
"""

from __future__ import annotations

import plotly.graph_objects as go

from .theme import ENCRE, ENCRE_SECONDAIRE, SERIES

POLICE = dict(family="Source Sans Pro, sans-serif", color=ENCRE)


def _fr(x: float, decimales: int = 0) -> str:
    return f"{x:,.{decimales}f}".replace(",", " ").replace(".", ",")


def _mise_en_page(fig, titre: str, unite: str, hauteur: int = 340):
    fig.update_layout(
        title=dict(text=f"<b>{titre}</b>", font=dict(size=15, color=ENCRE), x=0, xanchor="left"),
        height=hauteur + 30, font=POLICE, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=44, b=8), separators=", ",
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5, title=None,
                    font=dict(size=12, color=ENCRE_SECONDAIRE), itemclick="toggle", itemdoubleclick="toggleothers"),
        hoverlabel=dict(bgcolor="white", bordercolor="#E4E8EC", font=dict(color=ENCRE, size=13)),
        yaxis=dict(title=dict(text=unite, font=dict(size=12, color=ENCRE_SECONDAIRE)), zeroline=True,
                   zerolinecolor="#C9D1D9", zerolinewidth=1.2, gridcolor="#EEF1F4", tickfont=dict(color=ENCRE_SECONDAIRE)),
        xaxis=dict(type="category", tickfont=dict(color=ENCRE_SECONDAIRE), showgrid=False),
    )
    return fig


def _variations(valeurs, unite):
    sortie = [""]
    for prec, val in zip(valeurs, valeurs[1:]):
        if prec is None or val is None:
            sortie.append("")
            continue
        diff = val - prec
        texte = f"{'+' if diff >= 0 else '−'}{_fr(abs(diff))} {unite} sur un an"
        if unite == "k€" and prec:
            texte += f" ({'+' if diff >= 0 else '−'}{_fr(abs(diff / prec) * 100, 1)} %)"
        sortie.append(f"<br><span style='font-size:11px'>{texte}</span>")
    return sortie


def barres(annees, series: dict, titre: str):
    """series : nom -> valeurs en euros (affichées en k€)."""
    fig = go.Figure()
    x = [str(a) for a in annees]
    for i, (nom, valeurs) in enumerate(series.items()):
        c = SERIES[i % len(SERIES)]
        y = [v / 1000 if v is not None else None for v in valeurs]
        fig.add_bar(name=nom, x=x, y=y, marker=dict(color=c["fond"], line=dict(color=c["trait"], width=1.2),
                                                    cornerradius=5),
                    customdata=_variations(y, "k€"),
                    hovertemplate=f"<b>{nom}</b> : %{{y:,.0f}} k€%{{customdata}}<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.32, bargroupgap=0.1, hovermode="x unified")
    return _mise_en_page(fig, titre, "k€")


def lignes(annees, series: dict, titre: str, unite: str = "jours"):
    fig = go.Figure()
    x = [str(a) for a in annees]
    for i, (nom, valeurs) in enumerate(series.items()):
        c = SERIES[i % len(SERIES)]
        fig.add_scatter(name=nom, x=x, y=valeurs, mode="lines+markers",
                        line=dict(color=c["trait"], width=3, shape="spline", smoothing=0.6),
                        marker=dict(size=11, color=c["fond"], line=dict(width=2.5, color=c["trait"])),
                        customdata=_variations(valeurs, "j"),
                        hovertemplate=f"<b>{nom}</b> : %{{y:.0f}} j%{{customdata}}<extra></extra>")
    fig.update_layout(hovermode="x unified")
    return _mise_en_page(fig, titre, unite)


def cascade(etapes: list[tuple[str, float, str]], titre: str):
    """Cascade horizontale, lue de haut en bas. etapes : (libellé, montant en €, 'absolute', 'relative' ou 'total')."""
    libelles = [e[0] for e in etapes]
    fig = go.Figure(go.Waterfall(
        orientation="h", y=libelles, x=[e[1] / 1000 for e in etapes], measure=[e[2] for e in etapes],
        increasing=dict(marker=dict(color=SERIES[2]["fond"], line=dict(color=SERIES[2]["trait"], width=1.2))),
        decreasing=dict(marker=dict(color=SERIES[1]["fond"], line=dict(color=SERIES[1]["trait"], width=1.2))),
        totals=dict(marker=dict(color=SERIES[0]["fond"], line=dict(color=SERIES[0]["trait"], width=1.2))),
        connector=dict(line=dict(color="#C9D1D9", width=1, dash="dot")),
        text=[f"{'+' if e[1] > 0 and e[2] == 'relative' else ''}{_fr(e[1] / 1000)} k€".replace("-", "−") for e in etapes],
        textposition="outside", textfont=dict(color=ENCRE, size=12), cliponaxis=False,
        hovertemplate="<b>%{y}</b> : %{x:,.0f} k€<extra></extra>",
    ))
    fig.update_layout(showlegend=False, hovermode="closest")
    fig = _mise_en_page(fig, titre, "", hauteur=430)
    fig.update_layout(margin=dict(l=8, r=60, t=44, b=8))
    fig.update_yaxes(type="category", autorange="reversed", showgrid=False, zeroline=False,
                     tickfont=dict(size=12, color=ENCRE), title=None)
    cumul, positions = 0.0, []
    for _, montant, mesure in etapes:
        cumul = montant if mesure in ("absolute", "total") else cumul + montant
        positions.append(cumul / 1000)
    haut, bas = max(positions + [0]), min(positions + [0])
    marge = (haut - bas) * 0.18
    fig.update_xaxes(type="linear", range=[bas - marge, haut + marge * 0.8], showgrid=True, gridcolor="#EEF1F4",
                     zeroline=True, zerolinecolor="#C9D1D9", title=dict(text="k€", font=dict(size=12)))
    fig.update_yaxes(ticklabelstandoff=10)
    return fig


def financement(caf: float, existantes: float, nouveau: float):
    fig = go.Figure()
    fig.add_bar(name="CAF disponible", x=["Ressources"], y=[caf / 1000],
                marker=dict(color=SERIES[0]["fond"], line=dict(color=SERIES[0]["trait"], width=1.2), cornerradius=5),
                hovertemplate="<b>CAF</b> : %{y:,.0f} k€<extra></extra>")
    fig.add_bar(name="Prêts existants", x=["Remboursements"], y=[existantes / 1000],
                marker=dict(color=SERIES[1]["fond"], line=dict(color=SERIES[1]["trait"], width=1.2), cornerradius=5),
                hovertemplate="<b>Prêts existants</b> : %{y:,.0f} k€ par an<extra></extra>")
    fig.add_bar(name="Nouveau prêt", x=["Remboursements"], y=[nouveau / 1000],
                marker=dict(color=SERIES[2]["fond"], line=dict(color=SERIES[2]["trait"], width=1.2), cornerradius=5),
                hovertemplate="<b>Nouveau prêt</b> : %{y:,.0f} k€ par an<extra></extra>")
    if caf > 0:
        plafond = caf / 1.25 / 1000
        fig.add_hline(y=plafond, line_dash="dash", line_width=1.5, line_color=ENCRE_SECONDAIRE,
                      annotation_text=f"Plafond soutenable (CAF / 1,25) : {_fr(plafond)} k€",
                      annotation_position="top right", annotation_bgcolor="rgba(255,255,255,0.9)",
                      annotation_font=dict(size=12, color=ENCRE))
    fig.update_layout(barmode="stack", bargap=0.5, hovermode="closest")
    fig.update_layout(legend=dict(traceorder="normal"))
    return _mise_en_page(fig, "Capacité de remboursement annuelle", "k€")


def amortissement(par_an):
    """par_an : DataFrame indexé par année avec les colonnes Capital et Intérêts (en €)."""
    fig = go.Figure()
    x = [f"Année {a}" for a in par_an.index]
    for i, col in enumerate(["Capital", "Intérêts"]):
        c = SERIES[i]
        fig.add_bar(name=f"{col} remboursé" if col == "Capital" else "Intérêts payés", x=x, y=par_an[col] / 1000,
                    marker=dict(color=c["fond"], line=dict(color=c["trait"], width=1.2), cornerradius=4),
                    hovertemplate=f"<b>{col}</b> : %{{y:,.1f}} k€<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.35, hovermode="x unified")
    fig = _mise_en_page(fig, "Échéancier annuel du nouveau prêt", "k€", hauteur=320)
    fig.update_layout(legend=dict(traceorder="normal"))
    return fig
