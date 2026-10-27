# SPDX-License-Identifier: GPL-3.0-or-later
"""Vue des courbes (EX-52) : toute grandeur de sortie en fonction de t ou d'une autre grandeur,
avec min, max et moyenne. Les grandeurs sont les colonnes du CSV (`resultats/export.py`)."""

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from meca3d.ihm import textes, theme
from meca3d.modele.etude import Etude
from meca3d.moteur.base import ResultatsBruts
from meca3d.resultats.export import colonnes_resultats, statistiques

GRANDEUR_TEMPS = "t (s)"
GRANDEUR_PAR_DEFAUT = "C (N·m)"


class VueCourbes(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._colonnes: dict[str, np.ndarray] = {}
        self._x = np.zeros(0)
        self._y = np.zeros(0)
        self._couleurs = theme.couleurs(theme.Theme.CLAIR)
        disposition = QVBoxLayout(self)
        choix = QHBoxLayout()
        self.choix_x = QComboBox()
        self.choix_y = QComboBox()
        choix.addWidget(QLabel(textes.COURBE_X))
        choix.addWidget(self.choix_x, 1)
        choix.addWidget(QLabel(textes.COURBE_Y))
        choix.addWidget(self.choix_y, 1)
        self.etiquette_stats = QLabel(textes.COURBE_VIDE)
        self.figure = Figure(figsize=(6, 4))
        self.canevas = FigureCanvasQTAgg(self.figure)
        disposition.addLayout(choix)
        disposition.addWidget(self.etiquette_stats)
        disposition.addWidget(self.canevas, 1)
        self.choix_x.currentIndexChanged.connect(self._sur_choix)
        self.choix_y.currentIndexChanged.connect(self._sur_choix)
        self._dessiner()

    # --- interrogation -----------------------------------------------------------------------
    def grandeurs(self) -> list[str]:
        return list(self._colonnes)

    def donnees_courbe(self) -> tuple[np.ndarray, np.ndarray]:
        """Abscisses et ordonnées de la courbe affichée."""
        return self._x, self._y

    def statistiques(self) -> tuple[float, float, float]:
        """(min, max, moyenne) de la grandeur en ordonnée."""
        s = statistiques(self._y)
        return s.minimum, s.maximum, s.moyenne

    # --- mise à jour -------------------------------------------------------------------------
    def definir_couleurs(self, couleurs: theme.Couleurs) -> None:
        """Couleurs du thème (R12) : fond, axes, grille et trace."""
        self._couleurs = couleurs
        self._dessiner()

    def afficher(self, etude: Etude | None, resultats: ResultatsBruts | None) -> None:
        """Recalcule les grandeurs (post-traitement) et conserve les choix en cours."""
        precedent_x, precedent_y = self.choix_x.currentText(), self.choix_y.currentText()
        self._colonnes = (
            {} if etude is None or resultats is None else colonnes_resultats(etude, resultats)
        )
        noms = list(self._colonnes)
        for combo, precedent, defaut in (
            (self.choix_x, precedent_x, GRANDEUR_TEMPS),
            (self.choix_y, precedent_y, GRANDEUR_PAR_DEFAUT),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(noms)
            choisi = precedent if precedent in self._colonnes else defaut
            if choisi not in self._colonnes and len(noms) > 1:
                choisi = noms[1]
            combo.setCurrentIndex(max(combo.findText(choisi), 0))
            combo.blockSignals(False)
        self._sur_choix(0)

    def _sur_choix(self, _: int) -> None:
        x = self._colonnes.get(self.choix_x.currentText())
        y = self._colonnes.get(self.choix_y.currentText())
        self._x = np.zeros(0) if x is None else np.array(x)
        self._y = np.zeros(0) if y is None else np.array(y)
        self._dessiner()

    def _dessiner(self) -> None:
        c = self._couleurs
        self.figure.clear()
        self.figure.set_facecolor(c.panneau)
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(c.panneau)
        if len(self._y) == 0:
            self.etiquette_stats.setText(textes.COURBE_VIDE)
            ax.set_axis_off()
            self.canevas.draw_idle()
            return
        nom_y = self.choix_y.currentText()
        ax.plot(self._x, self._y, linewidth=1.5, color=c.trace)
        ax.set_xlabel(self.choix_x.currentText(), color=c.texte)
        ax.set_ylabel(nom_y, color=c.texte)
        ax.tick_params(colors=c.texte_secondaire, labelcolor=c.texte)
        for bord in ax.spines.values():
            bord.set_color(c.bordure)
        ax.grid(True, color=c.grille, linewidth=0.8)
        self.figure.tight_layout()
        mini, maxi, moyenne = self.statistiques()
        self.etiquette_stats.setText(
            textes.etiquette_statistiques(mini, maxi, moyenne, textes.unite_de(nom_y))
        )
        self.canevas.draw_idle()
