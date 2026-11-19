"""Retraitements bancaires : passer des comptes comptables à une vision « banquier » de l'entreprise.

1. Crédit-bail : le loyer est sorti des charges externes et traité comme un emprunt. L'EBE augmente du
   montant des redevances ; celles-ci sont réparties entre intérêts (encours × taux) et amortissement ;
   l'encours restant dû est ajouté aux dettes financières et, en contrepartie, aux immobilisations.
   Le résultat net est inchangé ; la CAF augmente de la part d'amortissement.
2. Comptes courants d'associés bloqués : reclassés des dettes financières vers les fonds propres
   (quasi-fonds propres), puisque les associés se sont engagés à ne pas les retirer.
3. Dividendes : déduits de la CAF, car l'argent distribué ne sert pas à rembourser les prêts.

Les comptes d'origine ne sont jamais modifiés : on travaille sur une copie.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .modele import ComptesAnnuels


@dataclass
class Parametres:
    credit_bail: bool = True
    comptes_courants: bool = True
    dividendes: bool = True
    taux_credit_bail: float = 0.04   # taux implicite des contrats, pour séparer intérêts et amortissement


@dataclass
class Ajustement:
    retraitement: str
    poste: str
    montant: float


@dataclass
class Resultat:
    comptes: ComptesAnnuels
    ajustements: list[Ajustement] = field(default_factory=list)

    @property
    def applique(self) -> bool:
        return bool(self.ajustements)


def retraiter(c: ComptesAnnuels, p: Parametres | None = None) -> Resultat:
    p = p or Parametres()
    r = copy.deepcopy(c)
    aj: list[Ajustement] = []

    if p.credit_bail and (c.redevances_credit_bail or c.encours_credit_bail):
        interets = c.encours_credit_bail * p.taux_credit_bail
        amortissement = max(c.redevances_credit_bail - interets, 0.0)
        interets = c.redevances_credit_bail - amortissement
        r.autres_achats_charges_externes -= c.redevances_credit_bail
        r.dotations_amortissements_provisions += amortissement
        r.charges_financieres += interets
        r.emprunts_bancaires += c.encours_credit_bail
        r.immobilisations_corporelles += c.encours_credit_bail
        aj += [Ajustement("Crédit-bail", "Charges externes (loyers retirés)", -c.redevances_credit_bail),
               Ajustement("Crédit-bail", "Dotations aux amortissements", amortissement),
               Ajustement("Crédit-bail", "Charges financières (intérêts)", interets),
               Ajustement("Crédit-bail", "Dettes financières (encours ajouté)", c.encours_credit_bail)]

    if p.comptes_courants and c.comptes_courants_bloques:
        montant = min(c.comptes_courants_bloques, c.autres_dettes_financieres)
        r.autres_dettes_financieres -= montant
        r.capitaux_propres += montant
        aj += [Ajustement("Comptes courants bloqués", "Dettes financières", -montant),
               Ajustement("Comptes courants bloqués", "Capitaux propres (quasi-fonds propres)", montant)]

    if p.dividendes and c.dividendes_verses:
        r.dividendes_deduits_caf = c.dividendes_verses
        aj.append(Ajustement("Dividendes", "CAF (dividendes déduits)", -c.dividendes_verses))

    r.verifier_equilibre()
    return Resultat(r, aj)


def retraiter_tout(exercices: list[ComptesAnnuels], p: Parametres | None = None) -> list[Resultat]:
    return [retraiter(c, p) for c in exercices]
