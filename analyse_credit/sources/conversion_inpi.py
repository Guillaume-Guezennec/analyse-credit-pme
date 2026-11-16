"""Conversion des comptes annuels saisis par l'INPI vers le modèle ComptesAnnuels.

Chaque poste de la liasse fiscale est identifié par un code (ex. « FA » = ventes de
marchandises dans les comptes complets, « 210 » dans les comptes simplifiés). Chaque
ligne contient jusqu'à quatre montants (m1 à m4) dont le sens dépend de la page :
par exemple, à l'actif des comptes complets, m3 = net N et m4 = net N-1.

Pour se prémunir d'une erreur de colonne, chaque bloc (actif, passif, compte de
résultat) est validé par un contrôle comptable : la somme des postes doit retrouver
le total de la liasse, et le résultat net recalculé doit égaler celui déclaré.
Plusieurs dispositions de colonnes sont essayées, et la première qui passe le
contrôle est retenue. Sinon, un avertissement est émis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..analyse import calculer_sig
from ..modele import ComptesAnnuels

# ---------------------------------------------------------------------------
# Correspondance des postes. Format : champ -> liste de (page, code[, signe])
# ---------------------------------------------------------------------------

COMPLET = {
    "actif": {
        "champs": {
            "immobilisations_incorporelles": [(1, c) for c in ("AB", "CX", "AF", "AH", "AJ", "AL")],
            "immobilisations_corporelles": [(1, c) for c in ("AN", "AP", "AR", "AT", "AV", "AX")],
            "immobilisations_financieres": [(1, c) for c in ("CS", "CU", "BB", "BD", "BF", "BH")],
            "stocks": [(1, c) for c in ("BL", "BN", "BP", "BR", "BT")],
            "creances_clients": [(1, "BX")],
            # Avances versées, autres créances, capital non appelé ou non versé, comptes de régularisation
            "autres_creances": [(1, c) for c in ("BV", "BZ", "AA", "CB", "CW", "CM", "CN")],
            "valeurs_mobilieres_placement": [(1, "CD")],
            "disponibilites": [(1, "CF")],
            "charges_constatees_avance": [(1, "CH")],
        },
        "total": (1, "CO"),
        "candidats": [{1: ("m3", "m4")}, {1: ("m1", "m2")}],
    },
    "passif": {
        "champs": {
            # Les autres fonds propres (titres participatifs, avances conditionnées) sont assimilés aux capitaux propres
            "capitaux_propres": [(2, "DL"), (2, "DO")],
            "provisions_risques_charges": [(2, "DR")],
            "emprunts_bancaires": [(2, "DU"), (2, "EH", -1)],
            "concours_bancaires_courants": [(2, "EH")],
            "autres_dettes_financieres": [(2, "DS"), (2, "DT"), (2, "DV")],
            "dettes_fournisseurs": [(2, "DX")],
            "dettes_fiscales_sociales": [(2, "DY")],
            "autres_dettes": [(2, "DW"), (2, "DZ"), (2, "EA"), (2, "ED")],
            "produits_constates_avance": [(2, "EB")],
        },
        "total": (2, "EE"),
        "candidats": [{2: ("m1", "m2")}, {2: ("m3", "m4")}],
    },
    "resultat": {
        "champs": {
            "ventes_marchandises": [(3, "FA")],
            "production_vendue": [(3, "FD"), (3, "FG")],
            "production_stockee": [(3, "FM")],
            "production_immobilisee": [(3, "FN")],
            "subventions_exploitation": [(3, "FO")],
            "reprises_provisions": [(3, "FP")],
            "autres_produits": [(3, "FQ")],
            "achats_marchandises": [(3, "FS")],
            "variation_stock_marchandises": [(3, "FT")],
            "achats_matieres": [(3, "FU")],
            "variation_stock_matieres": [(3, "FV")],
            "autres_achats_charges_externes": [(3, "FW")],
            "impots_taxes": [(3, "FX")],
            "salaires": [(3, "FY")],
            "charges_sociales": [(3, "FZ")],
            "dotations_amortissements_provisions": [(3, c) for c in ("GA", "GB", "GC", "GD")],
            "autres_charges": [(3, "GE")],
            # Les quotes-parts de résultat sur opérations en commun (GH, GI) sont rattachées au financier
            "produits_financiers": [(3, "GP"), (3, "GH")],
            "charges_financieres": [(3, "GU"), (3, "GI")],
            "produits_exceptionnels": [(4, "HD")],
            "charges_exceptionnelles": [(4, "HH")],
            "participation_salaries": [(4, "HJ")],
            "impot_benefices": [(4, "HK")],
            # Approximation : produits de cession (HB) - valeur nette des actifs cédés (HF)
            "plus_values_cession": [(4, "HB"), (4, "HF", -1)],
            "dotations_financieres_exceptionnelles": [(3, "GQ"), (4, "HG")],
            "reprises_financieres_exceptionnelles": [(3, "GM"), (4, "HC")],
        },
        "total": (4, "HN"),
        "candidats": [
            {3: ("m3", "m4"), 4: ("m1", "m2")},
            {3: ("m1", "m2"), 4: ("m1", "m2")},
            {3: ("m3", "m4"), 4: ("m3", "m4")},
        ],
    },
    "effectif": [(11, "YP"), (16, "YP")],
}

SIMPLIFIE = {
    "actif": {
        "champs": {
            "immobilisations_incorporelles": [(1, "010"), (1, "014")],
            "immobilisations_corporelles": [(1, "028")],
            "immobilisations_financieres": [(1, "040")],
            "stocks": [(1, "050"), (1, "060")],
            "creances_clients": [(1, "068")],
            "autres_creances": [(1, "064"), (1, "072")],
            "valeurs_mobilieres_placement": [(1, "080")],
            "disponibilites": [(1, "084"), (1, "088")],
            "charges_constatees_avance": [(1, "092")],
        },
        "total": (1, "110"),
        "candidats": [{1: ("m3", "m4")}, {1: ("m1", "m2")}],
    },
    "passif": {
        "champs": {
            "capitaux_propres": [(1, "142")],
            "provisions_risques_charges": [(1, "154")],
            # Le bilan simplifié ne distingue pas les découverts des emprunts
            "emprunts_bancaires": [(1, "156")],
            "dettes_fournisseurs": [(1, "166")],
            # Les dettes fiscales et sociales sont comprises dans « autres dettes » (ligne 172)
            "autres_dettes": [(1, "164"), (1, "172")],
            "produits_constates_avance": [(1, "174")],
        },
        "total": (1, "180"),
        "candidats": [{1: ("m3", "m4")}, {1: ("m1", "m2")}],
    },
    "resultat": {
        "champs": {
            "ventes_marchandises": [(2, "210")],
            "production_vendue": [(2, "214"), (2, "218")],
            "production_stockee": [(2, "222")],
            "production_immobilisee": [(2, "224")],
            "subventions_exploitation": [(2, "226")],
            "autres_produits": [(2, "230")],
            "achats_marchandises": [(2, "234")],
            "variation_stock_marchandises": [(2, "236")],
            "achats_matieres": [(2, "238")],
            "variation_stock_matieres": [(2, "240")],
            "autres_achats_charges_externes": [(2, "242")],
            "impots_taxes": [(2, "244")],
            "salaires": [(2, "250")],
            "charges_sociales": [(2, "252")],
            "dotations_amortissements_provisions": [(2, "254"), (2, "256")],
            "autres_charges": [(2, "262")],
            "produits_financiers": [(2, "280")],
            "produits_exceptionnels": [(2, "290")],
            "charges_financieres": [(2, "294")],
            "charges_exceptionnelles": [(2, "300")],
            "impot_benefices": [(2, "306")],
        },
        "total": (2, "310"),
        "candidats": [{2: ("m1", "m2")}, {2: ("m3", "m4")}],
    },
    "effectif": [(2, "376"), (5, "376")],
}

CORRESPONDANCES = {"C": COMPLET, "S": SIMPLIFIE}
LIBELLES_TYPES = {"C": "complets", "S": "simplifiés", "K": "consolidés", "B": "de banque",
                  "AC": "agricoles complets", "AS": "agricoles simplifiés"}


# ---------------------------------------------------------------------------
# Lecture du JSON
# ---------------------------------------------------------------------------

def montant(valeur) -> float:
    """Les montants INPI sont des chaînes de 15 caractères (ex. « -000000001127414 »)."""
    if valeur in (None, ""):
        return 0.0
    try:
        return float(str(valeur).strip())
    except ValueError:
        return 0.0


def lire_liasses(bilan: dict) -> dict[tuple[int, str], dict[str, float]]:
    pages = (((bilan.get("bilanSaisi") or {}).get("bilan") or {}).get("detail") or {}).get("pages") or []
    resultat = {}
    for page in pages:
        try:
            numero = int(page.get("numero"))
        except (TypeError, ValueError):
            continue
        for ligne in page.get("liasses") or []:
            code = str(ligne.get("code", "")).strip()
            if code:
                resultat[(numero, code)] = {m: montant(ligne.get(m)) for m in ("m1", "m2", "m3", "m4")}
    return resultat


def _annee(date: str | None) -> int | None:
    if not date:
        return None
    chiffres = "".join(ch for ch in str(date) if ch.isdigit())
    return int(chiffres[:4]) if len(chiffres) >= 4 else None


# ---------------------------------------------------------------------------
# Extraction d'un bloc avec contrôle
# ---------------------------------------------------------------------------

def _valeurs(champs, liasses, colonnes, rang):
    """rang 0 = exercice N, 1 = exercice N-1."""
    sortie = {}
    for nom, postes in champs.items():
        total = 0.0
        for poste in postes:
            page, code = poste[0], poste[1]
            signe = poste[2] if len(poste) > 2 else 1
            if page in colonnes and (page, code) in liasses:
                total += signe * liasses[(page, code)][colonnes[page][rang]]
        sortie[nom] = total
    return sortie


def _controle(nom_bloc, valeurs, total_declare):
    tolerance = max(2.0, abs(total_declare) * 0.001)
    if nom_bloc == "resultat":
        exploitation = {k: v for k, v in valeurs.items()}
        calcule = calculer_sig(ComptesAnnuels(exercice=0, **exploitation)).resultat_net
    else:
        # Les postes « dont » (concours bancaires) sont neutralisés par le signe négatif sur DU
        calcule = sum(valeurs.values())
    return abs(calcule - total_declare) <= tolerance, calcule


@dataclass
class Bloc:
    valeurs: dict[str, float]
    controle_ok: bool
    present: bool


def extraire_bloc(nom_bloc, spec, liasses, rang) -> Bloc:
    page_total, code_total = spec["total"]
    tous_codes = {(p[0], p[1]) for postes in spec["champs"].values() for p in postes} | {spec["total"]}
    if not any(c in liasses for c in tous_codes):
        return Bloc({}, False, False)

    premier = None
    for colonnes in spec["candidats"]:
        valeurs = _valeurs(spec["champs"], liasses, colonnes, rang)
        if (page_total, code_total) in liasses:
            total = liasses[(page_total, code_total)][colonnes.get(page_total, ("m1", "m2"))[rang]]
        else:
            total = None
        if not any(valeurs.values()) and not total:
            continue  # colonne vide : on essaie la disposition suivante
        if premier is None:
            premier = valeurs
        if total is not None and _controle(nom_bloc, valeurs, total)[0]:
            return Bloc(valeurs, True, True)
    if premier is None:
        return Bloc({}, False, False)
    return Bloc(premier, False, True)


# ---------------------------------------------------------------------------
# Conversion d'un bilan complet (exercices N et N-1)
# ---------------------------------------------------------------------------

@dataclass
class ExerciceExtrait:
    annee: int
    rang: int                     # 0 si l'exercice est le N du dépôt, 1 s'il s'agit du N-1
    blocs: dict[str, Bloc]
    duree_mois: int | None = None
    source: str = ""

    @property
    def complet(self) -> bool:
        return all(self.blocs.get(b) and self.blocs[b].present for b in ("actif", "passif", "resultat"))

    def en_dict(self) -> dict:
        donnees = {"exercice": self.annee}
        for bloc in self.blocs.values():
            donnees.update(bloc.valeurs)
        return donnees


@dataclass
class Conversion:
    type_bilan: str
    exercices: list[ExerciceExtrait] = field(default_factory=list)
    effectif: int | None = None
    avertissements: list[str] = field(default_factory=list)


def convertir_bilan(bilan: dict) -> Conversion:
    identite = (((bilan.get("bilanSaisi") or {}).get("bilan") or {}).get("identite")) or {}
    type_bilan = (bilan.get("typeBilan") or identite.get("codeTypeBilan") or "").upper()
    date_cloture = identite.get("dateClotureExercice") or bilan.get("dateCloture")
    annee = _annee(date_cloture)
    conv = Conversion(type_bilan)
    libelle = f"comptes {LIBELLES_TYPES.get(type_bilan, type_bilan)} clos le {date_cloture}"

    if type_bilan not in CORRESPONDANCES:
        conv.avertissements.append(f"{libelle} : type non pris en charge, dépôt ignoré.")
        return conv
    if annee is None:
        conv.avertissements.append(f"Dépôt sans date de clôture lisible, ignoré.")
        return conv

    confidentialite = str(identite.get("codeConfidentialite") or bilan.get("confidentiality") or "0")
    liasses = lire_liasses(bilan)
    if not liasses:
        motif = "comptes confidentiels" if confidentialite == "1" else "données non saisies par l'INPI"
        conv.avertissements.append(f"{libelle} : aucun montant disponible ({motif}).")
        return conv

    spec = CORRESPONDANCES[type_bilan]
    durees = (identite.get("dureeExerciceN"), identite.get("dureeExerciceNMoins1"))
    for rang in (0, 1):
        blocs = {nom: extraire_bloc(nom, spec[nom], liasses, rang) for nom in ("actif", "passif", "resultat")}
        if not any(b.present for b in blocs.values()):
            continue
        try:
            duree = int(durees[rang]) if durees[rang] else None
        except (TypeError, ValueError):
            duree = None
        ex = ExerciceExtrait(annee - rang, rang, blocs, duree, libelle)
        conv.exercices.append(ex)
        for nom, bloc in blocs.items():
            if bloc.present and not bloc.controle_ok:
                conv.avertissements.append(
                    f"{ex.annee} ({libelle}) : le contrôle du bloc « {nom} » n'est pas vérifié "
                    "(somme des postes ≠ total de la liasse). Vérifiez les montants dans l'Excel.")
        if not blocs["resultat"].present and rang == 0:
            motif = " (compte de résultat déclaré confidentiel)" if confidentialite in ("2", "4") else ""
            conv.avertissements.append(f"{ex.annee} : compte de résultat indisponible{motif}. "
                                       "Complétez-le dans l'Excel à partir de la liasse fournie par le client.")
        if duree and duree != 12:
            conv.avertissements.append(f"{ex.annee} : exercice de {duree} mois. Les flux ne sont pas "
                                       "comparables à une année pleine.")
    if type_bilan == "S":
        conv.avertissements.append(
            f"{annee} : comptes simplifiés. Les découverts bancaires ne sont pas distingués des emprunts, "
            "et les dettes fiscales et sociales sont regroupées dans les autres dettes.")

    for page, code in spec["effectif"]:
        if (page, code) in liasses and liasses[(page, code)]["m1"]:
            conv.effectif = int(liasses[(page, code)]["m1"])
            break
    return conv


def assembler(bilans: list[dict], nb_exercices: int = 3) -> tuple[list[dict], list[dict], list[str], int | None]:
    """Fusionne plusieurs dépôts. Pour une même année, les chiffres publiés comme exercice N
    priment sur ceux repris en N-1 dans le dépôt suivant (qui peuvent avoir été retraités).

    Renvoie : (exercices complets, exercices incomplets, avertissements, effectif)
    """
    par_annee: dict[int, ExerciceExtrait] = {}
    avertissements: list[str] = []
    effectif = None
    types_vus = set()
    for bilan in bilans:
        conv = convertir_bilan(bilan)
        avertissements.extend(conv.avertissements)
        if conv.type_bilan in CORRESPONDANCES:
            types_vus.add(conv.type_bilan)
        if effectif is None and conv.effectif:
            effectif = conv.effectif
        for ex in conv.exercices:
            actuel = par_annee.get(ex.annee)
            if actuel is None or (ex.rang, not ex.complet) < (actuel.rang, not actuel.complet):
                par_annee[ex.annee] = ex

    annees = sorted(par_annee, reverse=True)
    complets = [par_annee[a] for a in annees if par_annee[a].complet][:nb_exercices]
    incomplets = [par_annee[a] for a in annees if not par_annee[a].complet][:nb_exercices]
    if len(types_vus) > 1:
        avertissements.append("Les dépôts mélangent comptes complets et simplifiés : "
                              "certains postes ne sont pas comparables d'une année à l'autre.")
    return ([e.en_dict() for e in sorted(complets, key=lambda e: e.annee)],
            [e.en_dict() for e in sorted(incomplets, key=lambda e: e.annee)],
            avertissements, effectif)
