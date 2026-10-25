# SPDX-License-Identifier: GPL-3.0-or-later
"""Panneau des propriétés : liaison (EX-11, EX-12, EX-13) ou résumé de l'élément sélectionné."""

import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from meca3d import unites
from meca3d.ihm import textes
from meca3d.modele.liaison import DIRECTION_REQUISE, Liaison, Statut, TypeLiaison

BORNE_SAISIE = 1.0e6


def _champ(suffixe: str, decimales: int) -> QDoubleSpinBox:
    champ = QDoubleSpinBox()
    champ.setRange(-BORNE_SAISIE, BORNE_SAISIE)
    champ.setDecimals(decimales)
    if suffixe:
        champ.setSuffix(suffixe)
    return champ


def _trois_champs(suffixe: str, decimales: int) -> tuple[QWidget, list[QDoubleSpinBox]]:
    conteneur = QWidget()
    disposition = QHBoxLayout(conteneur)
    disposition.setContentsMargins(0, 0, 0, 0)
    champs = [_champ(suffixe, decimales) for _ in range(3)]
    for nom, champ in zip("xyz", champs, strict=True):
        disposition.addWidget(QLabel(nom))
        disposition.addWidget(champ)
    return conteneur, champs


class PanneauProprietes(QWidget):
    """Les modifications sont faites par les méthodes de `Liaison` ; le signal `modifiee`
    prévient la fenêtre, qui recalcule m, h et l'arbre."""

    modifiee = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._liaison: Liaison | None = None
        self._rafraichit = False
        disposition = QVBoxLayout(self)
        self.titre = QLabel(textes.TITRE_PROPRIETES)
        self.resume = QLabel(textes.PROPRIETES_VIDE)
        self.resume.setWordWrap(True)
        disposition.addWidget(self.titre)
        disposition.addWidget(self.resume)

        self.zone_liaison = QWidget()
        zone = QVBoxLayout(self.zone_liaison)
        zone.setContentsMargins(0, 0, 0, 0)
        self.etiquette_type_sc = QLabel()
        self.etiquette_type_sc.setWordWrap(True)
        self.choix_type = QComboBox()
        self.choix_type.addItem(textes.CHOIX_TYPE_VIDE, None)
        for type_liaison in TypeLiaison:
            self.choix_type.addItem(textes.LIBELLES_TYPE[type_liaison], type_liaison)
        self.etiquette_statut = QLabel()
        self.bouton_valider = QPushButton(textes.BOUTON_VALIDER)

        self.groupe_axe = QGroupBox(textes.GROUPE_AXE)
        axe = QVBoxLayout(self.groupe_axe)
        self.choix_axe = QComboBox()
        for libelle, code in textes.AXES_MONDE:
            self.choix_axe.addItem(libelle, code)
        conteneur_axe, self.saisie_axe = _trois_champs("", 4)
        self.bouton_axe = QPushButton(textes.BOUTON_AXE)
        for w in (self.choix_axe, conteneur_axe, self.bouton_axe):
            axe.addWidget(w)

        self.groupe_direction = QGroupBox(textes.GROUPE_DIRECTION)
        direction = QVBoxLayout(self.groupe_direction)
        conteneur_dir, self.saisie_direction = _trois_champs("", 4)
        self.bouton_direction = QPushButton(textes.BOUTON_DIRECTION)
        direction.addWidget(conteneur_dir)
        direction.addWidget(self.bouton_direction)

        self.groupe_centre = QGroupBox(textes.GROUPE_CENTRE)
        centre = QVBoxLayout(self.groupe_centre)
        conteneur_centre, self.saisie_centre = _trois_champs(" mm", 3)
        self.bouton_centre = QPushButton(textes.BOUTON_CENTRE)
        centre.addWidget(conteneur_centre)
        centre.addWidget(self.bouton_centre)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #b91c1c;")
        for w in (
            self.etiquette_type_sc,
            self.choix_type,
            self.etiquette_statut,
            self.bouton_valider,
            self.groupe_axe,
            self.groupe_direction,
            self.groupe_centre,
            self.message,
        ):
            zone.addWidget(w)
        disposition.addWidget(self.zone_liaison)
        disposition.addStretch(1)
        self.zone_liaison.hide()

        self.choix_type.currentIndexChanged.connect(self._sur_choix_type)
        self.bouton_valider.clicked.connect(self._valider)
        self.bouton_axe.clicked.connect(self._appliquer_axe)
        self.bouton_direction.clicked.connect(self._appliquer_direction)
        self.bouton_centre.clicked.connect(self._deplacer_centre)

    # --- affichage ---------------------------------------------------------------------------
    def afficher_texte(self, titre: str, texte: str) -> None:
        self._liaison = None
        self.zone_liaison.hide()
        self.titre.setText(titre)
        self.resume.setText(texte)
        self.resume.show()

    def afficher_liaison(self, liaison: Liaison) -> None:
        self._liaison = liaison
        self.titre.setText(liaison.nom)
        self.resume.hide()
        self.message.setText("")
        self.zone_liaison.show()
        self.rafraichir()
        assert liaison.axe is not None
        self._remplir(self.saisie_axe, tuple(float(x) for x in liaison.axe))
        self._remplir(self.saisie_centre, tuple(float(x) for x in unites.m_vers_mm(liaison.centre)))
        if liaison.direction is not None:
            self._remplir(self.saisie_direction, tuple(float(x) for x in liaison.direction))

    @staticmethod
    def _remplir(champs: list[QDoubleSpinBox], valeurs: tuple[float, ...]) -> None:
        for champ, valeur in zip(champs, valeurs, strict=True):
            champ.setValue(valeur)

    def rafraichir(self) -> None:
        """Recale les contrôles sur l'état de la liaison, sans émettre de signal."""
        liaison = self._liaison
        if liaison is None:
            return
        self._rafraichit = True
        try:
            self.etiquette_type_sc.setText(
                textes.etiquette_type_solidcraft(liaison.type_sc, liaison.proposition)
            )
            self.choix_type.setCurrentIndex(self.choix_type.findData(liaison.type))
            self.etiquette_statut.setText(textes.etiquette_statut(liaison.statut))
            self.bouton_valider.setEnabled(
                liaison.type is not None and liaison.statut is not Statut.VALIDEE
            )
            self.groupe_direction.setVisible(liaison.type in DIRECTION_REQUISE)
        finally:
            self._rafraichit = False

    # --- actions de l'élève ------------------------------------------------------------------
    def _signaler(self, erreur: Exception | None) -> None:
        self.message.setText("" if erreur is None else str(erreur))
        if erreur is None:
            self.modifiee.emit()

    def _sur_choix_type(self, _: int) -> None:
        liaison = self._liaison
        if self._rafraichit or liaison is None:
            return
        type_choisi = self.choix_type.currentData()
        if type_choisi is None or type_choisi == liaison.type:
            return
        liaison.choisir(type_choisi)
        self.rafraichir()
        self._signaler(None)

    def _valider(self) -> None:
        if self._liaison is None:
            return
        try:
            self._liaison.valider()
        except ValueError as e:
            self._signaler(e)
            return
        self.rafraichir()
        self._signaler(None)

    def _appliquer_axe(self) -> None:
        if self._liaison is None:
            return
        code = self.choix_axe.currentData()
        try:
            if code == "vecteur":
                self._liaison.reorienter_axe([c.value() for c in self.saisie_axe])
            else:
                self._liaison.reorienter_axe(str(code))
        except ValueError as e:
            self._signaler(e)
            return
        self.rafraichir()
        self._signaler(None)

    def _appliquer_direction(self) -> None:
        if self._liaison is None:
            return
        try:
            self._liaison.definir_direction([c.value() for c in self.saisie_direction])
        except ValueError as e:
            self._signaler(e)
            return
        self.rafraichir()
        self._signaler(None)

    def _deplacer_centre(self) -> None:
        if self._liaison is None:
            return
        try:
            self._liaison.deplacer_centre(
                unites.mm_vers_m(np.array([c.value() for c in self.saisie_centre]))
            )
        except ValueError as e:
            self._signaler(e)
            return
        self._signaler(None)
