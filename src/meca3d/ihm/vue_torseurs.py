# SPDX-License-Identifier: GPL-3.0-or-later
"""Tableau des torseurs de liaison à l'instant choisi par un curseur temporel (EX-50).

Torseur statique {i→j} ou j→i, ou torseur cinématique {V j/i}, en base de liaison ou en base
monde. Affichage lisible (`resultats.affichage`) : composantes nulles par construction « 0 »
exact (en base de liaison), 4 chiffres significatifs, bruit numérique sous 1e-9 fois le maximum
du tableau affiché ramené à « 0 ». En base monde, seul le seuil relatif s'applique (une
composante nulle en base de liaison ne l'est plus une fois le torseur tourné). Les unités sont
dans les en-têtes de colonnes.
"""

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from meca3d.ihm import textes
from meca3d.modele.etude import Etude
from meca3d.moteur.base import ResultatsBruts
from meca3d.resultats.affichage import formater_tableau
from meca3d.resultats.export import COMPOSANTES_CINEMATIQUES, COMPOSANTES_STATIQUES
from meca3d.resultats.torseurs import (
    masque_nul_par_construction,
    torseur_cinematique,
    torseur_statique,
)


class VueTorseurs(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._etude: Etude | None = None
        self._resultats: ResultatsBruts | None = None
        self._valeurs: dict[str, np.ndarray] = {}
        self._nuls: dict[str, np.ndarray] = {}
        self._composantes: tuple[str, ...] = COMPOSANTES_STATIQUES
        disposition = QVBoxLayout(self)
        options = QHBoxLayout()
        self.choix_torseur = QComboBox()
        for libelle, code in textes.TORSEURS:
            self.choix_torseur.addItem(libelle, code)
        self.choix_sens = QComboBox()
        for libelle, code in textes.SENS:
            self.choix_sens.addItem(libelle, code)
        self.choix_base = QComboBox()
        for libelle, code in textes.BASES_LIAISON:
            self.choix_base.addItem(libelle, code)
        self.choix_base.setCurrentIndex(self.choix_base.findData("monde"))
        for w in (self.choix_torseur, self.choix_sens, self.choix_base):
            options.addWidget(w)
        self.curseur = QSlider(Qt.Orientation.Horizontal)
        self.curseur.setRange(0, 0)
        self.etiquette_instant = QLabel(textes.TORSEUR_VIDE)
        self.etiquette_info = QLabel()
        self.table = QTableWidget(0, 6)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        disposition.addLayout(options)
        disposition.addWidget(self.curseur)
        disposition.addWidget(self.etiquette_instant)
        disposition.addWidget(self.etiquette_info)
        disposition.addWidget(self.table, 1)
        for combo in (self.choix_torseur, self.choix_sens, self.choix_base):
            combo.currentIndexChanged.connect(self._sur_option)
        self.curseur.valueChanged.connect(self._sur_curseur)

    # --- interrogation -----------------------------------------------------------------------
    def instant(self) -> float:
        if self._resultats is None:
            return 0.0
        return float(self._resultats.t[self.curseur.value()])

    def liaisons(self) -> list[str]:
        return [] if self._etude is None else [x.nom for x in self._etude.liaisons]

    def valeur(self, liaison: str, composante: str) -> float:
        k = self._composantes.index(composante)
        return float(self._valeurs[liaison][self.curseur.value(), k])

    def cellule(self, liaison: str, composante: str) -> str:
        item = self.table.item(self.liaisons().index(liaison), self._composantes.index(composante))
        return "" if item is None else item.text()

    # --- mise à jour -------------------------------------------------------------------------
    def afficher(self, etude: Etude | None, resultats: ResultatsBruts | None) -> None:
        self._etude, self._resultats = etude, resultats
        self.curseur.blockSignals(True)
        n = 0 if resultats is None else len(resultats.t)
        self.curseur.setRange(0, max(n - 1, 0))
        self.curseur.setValue(min(self.curseur.value(), max(n - 1, 0)))
        self.curseur.blockSignals(False)
        efforts = resultats is not None and bool(resultats.forces)
        if resultats is not None and not efforts:
            self.choix_torseur.blockSignals(True)
            self.choix_torseur.setCurrentIndex(self.choix_torseur.findData("cinematique"))
            self.choix_torseur.blockSignals(False)
        self.etiquette_info.setText(
            textes.TORSEUR_STATIQUE_ABSENT if resultats is not None and not efforts else ""
        )
        self._calculer()

    def _calculer(self) -> None:
        etude, resultats = self._etude, self._resultats
        self._valeurs = {}
        self._nuls = {}
        cinematique = self.choix_torseur.currentData() == "cinematique" or (
            resultats is not None and not resultats.forces
        )
        self._composantes = COMPOSANTES_CINEMATIQUES if cinematique else COMPOSANTES_STATIQUES
        if etude is not None and resultats is not None:
            base = str(self.choix_base.currentData())
            sens_ij = self.choix_sens.currentData() == "i_vers_j"
            for liaison in etude.liaisons:
                i = liaison.solide_a if sens_ij else liaison.solide_b
                if cinematique:
                    tors = torseur_cinematique(etude, resultats, liaison.nom, i=i, base=base)
                else:
                    tors = torseur_statique(etude, resultats, liaison.nom, de=i, base=base)
                self._valeurs[liaison.nom] = tors
                if base == "liaison":
                    self._nuls[liaison.nom] = masque_nul_par_construction(
                        etude, liaison.nom, statique=not cinematique
                    )
        self.table.setColumnCount(len(self._composantes))
        self.table.setHorizontalHeaderLabels(list(self._composantes))
        self._remplir_table()

    def _remplir_table(self) -> None:
        noms = list(self._valeurs)
        self.table.setRowCount(len(noms))
        self.table.setVerticalHeaderLabels(noms)
        if self._resultats is None:
            self.etiquette_instant.setText(textes.TORSEUR_VIDE)
            return
        k = self.curseur.value()
        self.etiquette_instant.setText(textes.etiquette_instant(self.instant()))
        instant = np.array([self._valeurs[nom][k] for nom in noms])
        nuls = np.array([self._nuls.get(nom, np.zeros(instant.shape[1], bool)) for nom in noms])
        for r, ligne in enumerate(formater_tableau(instant, nuls)):
            for c, texte in enumerate(ligne):
                self.table.setItem(r, c, QTableWidgetItem(texte))
        self.table.resizeColumnsToContents()

    def _sur_option(self, _: int) -> None:
        self._calculer()

    def _sur_curseur(self, _: int) -> None:
        self._remplir_table()
