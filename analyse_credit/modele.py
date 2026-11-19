"""Modèle de données : comptes annuels simplifiés d'une PME (plan comptable général français).

Les postes reprennent, de façon simplifiée, ceux de la liasse fiscale
(formulaires 2033 / 2050 à 2053). Tous les montants sont en euros.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass
class ComptesAnnuels:
    exercice: int  # année de clôture

    # ---------------- Compte de résultat ----------------
    ventes_marchandises: float = 0.0
    production_vendue: float = 0.0          # biens et services
    production_stockee: float = 0.0
    production_immobilisee: float = 0.0
    subventions_exploitation: float = 0.0
    reprises_provisions: float = 0.0        # reprises sur amortissements et provisions d'exploitation
    autres_produits: float = 0.0

    achats_marchandises: float = 0.0
    variation_stock_marchandises: float = 0.0   # stock initial - stock final
    achats_matieres: float = 0.0
    variation_stock_matieres: float = 0.0
    autres_achats_charges_externes: float = 0.0
    impots_taxes: float = 0.0
    salaires: float = 0.0
    charges_sociales: float = 0.0
    dotations_amortissements_provisions: float = 0.0
    autres_charges: float = 0.0

    produits_financiers: float = 0.0
    charges_financieres: float = 0.0        # essentiellement intérêts d'emprunts

    produits_exceptionnels: float = 0.0
    charges_exceptionnelles: float = 0.0
    plus_values_cession: float = 0.0        # produits de cession - VNC des actifs cédés (inclus dans l'exceptionnel)
    dotations_financieres_exceptionnelles: float = 0.0  # incluses dans les charges financières et exceptionnelles
    reprises_financieres_exceptionnelles: float = 0.0   # incluses dans les produits financiers et exceptionnels

    participation_salaries: float = 0.0
    impot_benefices: float = 0.0

    # ---------------- Bilan actif (valeurs nettes) ----------------
    immobilisations_incorporelles: float = 0.0
    immobilisations_corporelles: float = 0.0
    immobilisations_financieres: float = 0.0
    stocks: float = 0.0
    creances_clients: float = 0.0
    autres_creances: float = 0.0
    valeurs_mobilieres_placement: float = 0.0
    disponibilites: float = 0.0
    charges_constatees_avance: float = 0.0

    # ---------------- Bilan passif ----------------
    capitaux_propres: float = 0.0
    provisions_risques_charges: float = 0.0
    emprunts_bancaires: float = 0.0          # dettes auprès des établissements de crédit HORS concours bancaires courants
    concours_bancaires_courants: float = 0.0  # découverts, soldes créditeurs de banque
    autres_dettes_financieres: float = 0.0   # dont comptes courants d'associés
    dettes_fournisseurs: float = 0.0
    dettes_fiscales_sociales: float = 0.0
    autres_dettes: float = 0.0
    produits_constates_avance: float = 0.0

    # ---------------- Informations complémentaires (annexe), utilisées par les retraitements bancaires ----------------
    redevances_credit_bail: float = 0.0      # loyers de crédit-bail de l'exercice (inclus dans les charges externes)
    encours_credit_bail: float = 0.0         # redevances restant à payer à la clôture
    comptes_courants_bloques: float = 0.0    # dont comptes courants d'associés bloqués (inclus dans autres dettes financières)
    dividendes_verses: float = 0.0           # dividendes distribués pendant l'exercice
    dividendes_deduits_caf: float = 0.0      # renseigné par les retraitements : dividendes retirés de la CAF

    # ---------------- Totaux ----------------
    @property
    def chiffre_affaires(self) -> float:
        return self.ventes_marchandises + self.production_vendue

    @property
    def actif_immobilise(self) -> float:
        return (self.immobilisations_incorporelles + self.immobilisations_corporelles
                + self.immobilisations_financieres)

    @property
    def actif_circulant(self) -> float:
        return (self.stocks + self.creances_clients + self.autres_creances
                + self.valeurs_mobilieres_placement + self.disponibilites
                + self.charges_constatees_avance)

    @property
    def total_actif(self) -> float:
        return self.actif_immobilise + self.actif_circulant

    @property
    def dettes_financieres(self) -> float:
        return self.emprunts_bancaires + self.concours_bancaires_courants + self.autres_dettes_financieres

    @property
    def total_passif(self) -> float:
        return (self.capitaux_propres + self.provisions_risques_charges + self.dettes_financieres
                + self.dettes_fournisseurs + self.dettes_fiscales_sociales + self.autres_dettes
                + self.produits_constates_avance)

    def verifier_equilibre(self, tolerance: float = 1.0) -> None:
        ecart = self.total_actif - self.total_passif
        if abs(ecart) > tolerance:
            raise ValueError(
                f"Bilan {self.exercice} déséquilibré : actif {self.total_actif:,.0f} € "
                f"≠ passif {self.total_passif:,.0f} € (écart {ecart:,.0f} €)"
            )

    @classmethod
    def depuis_dict(cls, donnees: dict) -> "ComptesAnnuels":
        connus = {f.name for f in fields(cls)}
        inconnus = set(donnees) - connus
        if inconnus:
            raise KeyError(f"Postes inconnus : {', '.join(sorted(inconnus))}")
        return cls(**donnees)
