"""Palette et feuille de style de l'application.

Deux familles de couleurs, jamais mélangées :
- la palette pastel identifie les séries des graphiques ;
- les couleurs d'appréciation (favorable, à surveiller, défavorable) portent un jugement.
Les couleurs claires servent de fond ; le texte reste toujours dans une teinte foncée lisible.
"""

# Séries des graphiques : bleu ciel, pêche, vert sauge (+ une teinte plus soutenue pour les contours et les lignes)
SERIES = [
    {"nom": "Bleu ciel", "fond": "#A8D0E6", "trait": "#5E9DC2"},
    {"nom": "Pêche", "fond": "#FFC8A2", "trait": "#E59563"},
    {"nom": "Vert sauge", "fond": "#C7DDB5", "trait": "#86AD69"},
]

# Appréciations : fond très clair, accent (pastilles, barres) et texte foncé de la même teinte
APPRECIATIONS = {
    "rouge": {"fond": "#FDECEC", "accent": "#FF8F8F", "texte": "#9B2C2C", "bord": "#F8CFCF",
              "point": "Point faible", "avis": "Défavorable"},
    "orange": {"fond": "#FEF6E0", "accent": "#FDE2A6", "texte": "#7A5A0C", "bord": "#F6E1AE",
               "point": "À surveiller", "avis": "À surveiller"},
    "vert": {"fond": "#F1F9E6", "accent": "#A8E063", "texte": "#3E6B1F", "bord": "#D4EDB5",
             "point": "Point fort", "avis": "Favorable"},
}
SENS_VERS_COULEUR = {"negatif": "rouge", "vigilance": "orange", "positif": "vert"}

GRIS_ENTETE = "#EEF1F4"
ENCRE = "#1F2933"
ENCRE_SECONDAIRE = "#52606D"

CSS = f"""
<style>
.block-container {{ padding-top: 2.2rem; max-width: 1280px; }}
h1, h2, h3, h4 {{ color: {ENCRE}; letter-spacing: -0.01em; }}

/* ---------- En-tête ---------- */
.entete {{ position: relative; overflow: hidden; background: {GRIS_ENTETE}; border-radius: 16px 16px 0 0;
          padding: 28px 32px 20px 32px; }}
.entete svg.decor {{ position: absolute; right: -10px; top: 0; height: 100%; width: 36%; opacity: .5; pointer-events: none; }}
.entete .surtitre {{ font-size: .78rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #5E9DC2; }}
.entete h1 {{ margin: 2px 0 6px 0; padding: 0; font-size: 2.1rem; font-weight: 700; }}
.entete .sous-titre {{ color: {ENCRE_SECONDAIRE}; font-size: .98rem; max-width: min(600px, 60%); line-height: 1.45; }}
.entete .societe {{ margin-top: 16px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; position: relative; }}
.etiquette {{ display: inline-block; background: rgba(255,255,255,.85); border: 1px solid #DDE3E9; border-radius: 999px;
             padding: 3px 12px; font-size: .84rem; color: {ENCRE}; }}
.etiquette.forte {{ font-weight: 600; }}

/* ---------- Onglets façon barre de navigation ---------- */
.stTabs [role="tablist"] {{ gap: 6px; background: {GRIS_ENTETE}; padding: 4px 26px 14px 26px;
    border-radius: 0 0 16px 16px; margin-top: -1rem; border: none; }}
.stTabs [role="tablist"]::after, .stTabs [role="tablist"]::before {{ display: none !important; }}
.stTabs [data-testid="stTab"] {{ height: auto; padding: 8px 20px; border-radius: 999px; background: transparent;
    color: {ENCRE_SECONDAIRE}; transition: background .15s ease; border: none !important; }}
.stTabs [data-testid="stTab"] p {{ font-size: .95rem; font-weight: 500; }}
.stTabs [data-testid="stTab"]:hover {{ background: rgba(255,255,255,.65); }}
.stTabs [data-testid="stTab"][aria-selected="true"] {{ background: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(31,41,51,.10); }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color: {ENCRE}; font-weight: 650; }}
.stTabs .react-aria-SelectionIndicator {{ display: none !important; }}
.stTabs [data-testid="stTabPanel"] {{ padding-top: 1.4rem; }}

/* ---------- Cartes ---------- */
.carte {{ background: #FFFFFF; border: 1px solid #E4E8EC; border-radius: 14px; padding: 16px 18px; min-height: 148px; }}
.carte .libelle {{ font-size: .82rem; color: {ENCRE_SECONDAIRE}; }}
.carte .valeur {{ font-size: 1.75rem; font-weight: 650; color: {ENCRE}; line-height: 1.25; margin-top: 2px; }}
.carte .detail {{ font-size: .8rem; color: {ENCRE_SECONDAIRE}; margin-top: 4px; }}
.variation {{ display: inline-block; border-radius: 999px; padding: 1px 9px; font-size: .78rem; font-weight: 600; margin-top: 6px; }}
[data-testid="stMetric"] {{ background: #FFFFFF; border: 1px solid #E4E8EC; border-radius: 14px; padding: 14px 18px; }}

/* ---------- Blocs d'appréciation ---------- */
.bloc {{ border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; border: 1px solid transparent; }}
.bloc .titre {{ font-size: .74rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 3px; }}
.bloc .texte {{ font-size: .95rem; line-height: 1.45; }}
.pastille {{ display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: .78rem; font-weight: 600; white-space: nowrap; }}

/* ---------- Tableaux maison ---------- */
table.tab {{ width: 100%; border-collapse: separate; border-spacing: 0; font-size: .9rem; background: #FFF;
            border: 1px solid #E4E8EC; border-radius: 12px; overflow: hidden; }}
table.tab th {{ background: #F7F9FA; color: {ENCRE_SECONDAIRE}; font-weight: 600; font-size: .78rem; text-transform: uppercase;
               letter-spacing: .04em; text-align: left; padding: 10px 12px; border-bottom: 1px solid #E4E8EC; }}
table.tab th, table.tab td {{ border-left: none !important; border-right: none !important; border-top: none !important; }}
table.tab td {{ padding: 10px 12px; border-bottom: 1px solid #F0F2F4; vertical-align: middle; color: {ENCRE}; }}
table.tab tr:last-child td {{ border-bottom: none; }}
table.tab tr:hover td {{ background: #FAFBFC; }}
table.tab td.nombre, table.tab th.nombre {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
table.tab .en {{ font-size: .76rem; color: #8A96A3; font-style: italic; }}
table.tab .def {{ font-size: .78rem; color: {ENCRE_SECONDAIRE}; margin-top: 2px; max-width: 460px; line-height: 1.35; }}
.jauge {{ background: #EEF1F4; border-radius: 999px; height: 7px; width: 100%; min-width: 70px; overflow: hidden; }}
.jauge > div {{ height: 100%; border-radius: 999px; }}

/* ---------- Divers ---------- */
.section {{ font-size: 1.15rem; font-weight: 650; color: {ENCRE}; margin: 18px 0 10px 0; display: flex; align-items: center; gap: 10px; }}
.section::before {{ content: ""; width: 4px; height: 18px; border-radius: 4px; background: #A8D0E6; display: inline-block; }}
.etapes {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 8px 0 4px 0; }}
.etape {{ flex: 1 1 150px; background: #FFF; border: 1px solid #E4E8EC; border-radius: 12px; padding: 12px 14px; }}
.etape .num {{ display: inline-flex; width: 24px; height: 24px; border-radius: 50%; background: #A8D0E6; color: {ENCRE};
              font-size: .8rem; font-weight: 700; align-items: center; justify-content: center; margin-bottom: 6px; }}
.etape .t {{ font-weight: 600; font-size: .92rem; color: {ENCRE}; }}
.etape .d {{ font-size: .8rem; color: {ENCRE_SECONDAIRE}; margin-top: 2px; line-height: 1.35; }}
.puce-techno {{ display: inline-block; background: #F4F6F8; border: 1px solid #E4E8EC; border-radius: 8px; padding: 4px 10px;
               margin: 0 6px 6px 0; font-size: .82rem; color: {ENCRE}; }}
.projet {{ background: linear-gradient(135deg, #F4F9FC 0%, #FBF7F2 100%); border: 1px solid #E4E8EC; border-radius: 14px; padding: 20px 24px; }}
.projet p {{ color: {ENCRE}; line-height: 1.55; margin: 0 0 10px 0; }}
.signature {{ font-size: .85rem; color: {ENCRE_SECONDAIRE}; }}
section[data-testid="stSidebar"] .resume {{ font-size: .84rem; color: {ENCRE_SECONDAIRE}; line-height: 1.45; margin-bottom: 10px; }}

/* ---------- Barre latérale : marque et volets dépliants ---------- */
section[data-testid="stSidebar"] .marque {{ display: flex; align-items: center; gap: 12px; margin: 4px 0 18px 2px; }}
section[data-testid="stSidebar"] .marque-titre {{ font-weight: 700; font-size: 1.05rem; color: {ENCRE}; line-height: 1.2; }}
section[data-testid="stSidebar"] .marque-sous {{ font-size: .78rem; color: {ENCRE_SECONDAIRE}; }}
section[data-testid="stSidebar"] [data-testid="stExpander"] details {{ background: #FFFFFF; border: 1px solid #E4E8EC;
    border-radius: 12px; box-shadow: 0 1px 2px rgba(31,41,51,.04); margin-bottom: 10px; overflow: hidden; }}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary {{ padding: 12px 14px; font-weight: 600;
    transition: background .15s ease; }}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{ background: #F7F9FA; }}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p {{ font-size: .95rem; font-weight: 600; color: {ENCRE}; }}
section[data-testid="stSidebar"] [data-testid="stExpander"] details[open] summary {{ border-bottom: 1px solid #EEF1F4; }}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {{ color: #5E9DC2; }}
section[data-testid="stSidebar"] [data-testid="stExpanderDetails"] {{ padding-top: 12px; }}
section[data-testid="stSidebar"] hr {{ display: none; }}

/* Choix de la source : des cartes plutôt que des boutons radio */
section[data-testid="stSidebar"] [role="radiogroup"] {{ display: flex; flex-direction: column; gap: 6px; width: 100%; }}
section[data-testid="stSidebar"] [role="radiogroup"] > div {{ width: 100%; }}
section[data-testid="stSidebar"] [role="radiogroup"] label {{ width: 100% !important; box-sizing: border-box; margin: 0; padding: 9px 12px;
    border: 1px solid #E4E8EC; border-radius: 10px; background: #FFFFFF; transition: all .15s ease; }}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ border-color: #A8D0E6; background: #F7FAFC; }}
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{ border-color: #5E9DC2;
    background: #F1F7FB; box-shadow: inset 3px 0 0 #5E9DC2; }}
section[data-testid="stSidebar"] .mode-emploi {{ padding-left: 18px; margin: 0; font-size: .85rem; color: {ENCRE_SECONDAIRE}; }}
section[data-testid="stSidebar"] .mode-emploi li {{ margin-bottom: 8px; line-height: 1.4; }}
section[data-testid="stSidebar"] .mode-emploi b {{ color: {ENCRE}; }}
</style>
"""
