# SPDX-License-Identifier: GPL-3.0-or-later
"""Barre des étapes numérotées Modèle → Données → Simulation → Résultats (R12).

L'état de chaque étape se déduit de ce que la fenêtre sait déjà (marques de l'arbre, EX-61 ;
simulation possible, EX-11 et EX-22 ; résultats présents) : aucune règle métier nouvelle.
"""

from enum import Enum

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from meca3d.ihm import textes


class EtatEtape(Enum):
    A_FAIRE = "a_faire"
    INCOMPLET = "incomplet"
    PRET = "pret"
    FAIT = "fait"


def etats_etapes(
    etude_ouverte: bool,
    modele_incomplet: bool,
    donnees_incompletes: bool,
    simulable: bool,
    resultats: bool,
) -> list[EtatEtape]:
    """États des quatre étapes, dans l'ordre de la démarche."""
    if not etude_ouverte:
        return [EtatEtape.A_FAIRE] * 4
    modele = EtatEtape.INCOMPLET if modele_incomplet else EtatEtape.FAIT
    donnees = EtatEtape.INCOMPLET if donnees_incompletes else EtatEtape.FAIT
    if resultats:
        simulation = EtatEtape.FAIT
    else:
        simulation = EtatEtape.PRET if simulable else EtatEtape.A_FAIRE
    return [modele, donnees, simulation, EtatEtape.FAIT if resultats else EtatEtape.A_FAIRE]


class BarreEtapes(QWidget):
    """Quatre boutons numérotés ; un clic émet le rang (0 à 3) de l'étape choisie."""

    etape_choisie = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("barreEtapes")
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(6, 0, 6, 0)
        ligne.setSpacing(0)
        self._boutons: list[QToolButton] = []
        self._etats: list[EtatEtape] = [EtatEtape.A_FAIRE] * len(textes.ETAPES)
        for rang, nom in enumerate(textes.ETAPES):
            if rang:
                fleche = QLabel(textes.FLECHE_ETAPE)
                fleche.setObjectName("flecheEtape")
                ligne.addWidget(fleche)
            bouton = QToolButton()
            bouton.setText(textes.libelle_etape(rang, nom))
            bouton.setProperty("etape", rang)
            bouton.clicked.connect(self._sur_clic)
            ligne.addWidget(bouton)
            self._boutons.append(bouton)
        ligne.addStretch(1)
        self.definir_etats(self._etats)

    def _sur_clic(self) -> None:
        emetteur = self.sender()
        if isinstance(emetteur, QToolButton):
            self.etape_choisie.emit(self._boutons.index(emetteur))

    def definir_etats(self, etats: list[EtatEtape]) -> None:
        self._etats = list(etats)
        for bouton, nom, etat in zip(self._boutons, textes.ETAPES, etats, strict=True):
            if bouton.property("etat") != etat.value:
                bouton.setProperty("etat", etat.value)
                style = bouton.style()
                if style is not None:
                    style.unpolish(bouton)
                    style.polish(bouton)
            bouton.setToolTip(textes.info_etape(nom, textes.LIBELLES_ETAT_ETAPE[etat.value]))

    # --- interrogation (tests) ---------------------------------------------------------------
    def libelles(self) -> list[str]:
        return [b.text() for b in self._boutons]

    def etats(self) -> list[EtatEtape]:
        return list(self._etats)

    def bouton(self, rang: int) -> QToolButton:
        return self._boutons[rang]
