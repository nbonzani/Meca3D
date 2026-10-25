# SPDX-License-Identifier: GPL-3.0-or-later
"""Vue « Animation » (EX-53) : lecture, pause, vitesse, curseur temporel, arrêt avec restauration
de la pose, et trajectoire d'un capteur de point (EX-52).

Aucune logique ici : `cao/animation.py` pilote SolidCraft. La lecture avance par un QTimer dans le
fil de l'interface (une requête `engine.batch` dure environ 17 ms, fenêtre SolidCraft visible) ; le
tracé et l'effacement des trajectoires, plus longs, sont lancés par la fenêtre (QThreadPool).
"""

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from meca3d.cao.animation import Animateur
from meca3d.cao.canal import CanalSolidCraft, ErreurCanal
from meca3d.ihm import textes
from meca3d.modele.capteurs import CapteurPoint
from meca3d.modele.etude import Etude
from meca3d.moteur.base import ResultatsBruts

RESOLUTION_CURSEUR = 1000
INDEX_VITESSE_PAR_DEFAUT = 3  # ×1
PERIODE_TIC_MS = 1  # le tic suivant suit immédiatement l'image envoyée (≈ 17 ms par requête)


class VueAnimation(QWidget):
    """Commandes d'animation. `fournisseur_canal` rend le canal courant (ou None)."""

    trajectoire_demandee = pyqtSignal(str)  # nom du capteur de point
    effacement_demande = pyqtSignal()
    erreur = pyqtSignal(str)

    def __init__(self, fournisseur_canal: Callable[[], CanalSolidCraft | None]) -> None:
        super().__init__()
        self._fournisseur_canal = fournisseur_canal
        self._etude: Etude | None = None
        self._resultats: ResultatsBruts | None = None
        self._animateur: Animateur | None = None
        self._autorise = False
        self._occupe = False

        self.bouton_lecture = QPushButton(textes.ANIMATION_LECTURE)
        self.bouton_arret = QPushButton(textes.ANIMATION_ARRET)
        self.selecteur_vitesse = QComboBox()
        for libelle, _ in textes.ANIMATION_VITESSES:
            self.selecteur_vitesse.addItem(libelle)
        self.selecteur_vitesse.setCurrentIndex(INDEX_VITESSE_PAR_DEFAUT)
        self.curseur = QSlider(Qt.Orientation.Horizontal)
        self.curseur.setRange(0, RESOLUTION_CURSEUR)
        self.etiquette_temps = QLabel(textes.animation_temps(0.0, 0.0))
        self.etiquette_etat = QLabel()
        self.etiquette_etat.setWordWrap(True)
        self.choix_capteur = QComboBox()
        self.bouton_trajectoire = QPushButton(textes.ANIMATION_TRACER)
        self.bouton_effacer = QPushButton(textes.ANIMATION_EFFACER)

        commandes = QHBoxLayout()
        commandes.addWidget(self.bouton_lecture)
        commandes.addWidget(self.bouton_arret)
        commandes.addWidget(QLabel(textes.ANIMATION_VITESSE))
        commandes.addWidget(self.selecteur_vitesse)
        commandes.addStretch(1)
        temps = QHBoxLayout()
        temps.addWidget(self.curseur, 1)
        temps.addWidget(self.etiquette_temps)
        trajectoire = QHBoxLayout()
        trajectoire.addWidget(QLabel(textes.ANIMATION_TRAJECTOIRE_CAPTEUR))
        trajectoire.addWidget(self.choix_capteur, 1)
        trajectoire.addWidget(self.bouton_trajectoire)
        trajectoire.addWidget(self.bouton_effacer)
        aide = QLabel(textes.ANIMATION_AIDE)
        aide.setWordWrap(True)
        disposition = QVBoxLayout(self)
        disposition.addWidget(aide)
        disposition.addLayout(commandes)
        disposition.addLayout(temps)
        disposition.addLayout(trajectoire)
        disposition.addWidget(self.etiquette_etat)
        disposition.addStretch(1)

        self.minuteur = QTimer(self)
        self.minuteur.setInterval(PERIODE_TIC_MS)
        self.minuteur.timeout.connect(self._tic)
        self.bouton_lecture.clicked.connect(self._sur_lecture)
        self.bouton_arret.clicked.connect(self.arreter)
        self.selecteur_vitesse.currentIndexChanged.connect(self._sur_vitesse)
        self.curseur.valueChanged.connect(self._sur_curseur)
        self.bouton_trajectoire.clicked.connect(self._sur_tracer)
        self.bouton_effacer.clicked.connect(self.effacement_demande.emit)
        self._actualiser()

    # --- interrogation ---------------------------------------------------------------------
    @property
    def en_lecture(self) -> bool:
        return self.minuteur.isActive()

    @property
    def vitesse(self) -> float:
        return textes.ANIMATION_VITESSES[self.selecteur_vitesse.currentIndex()][1]

    @property
    def duree(self) -> float:
        return (
            0.0 if self._resultats is None else float(self._resultats.t[-1] - self._resultats.t[0])
        )

    # --- données ---------------------------------------------------------------------------
    def definir(self, etude: Etude | None, resultats: ResultatsBruts | None) -> None:
        """Nouvelles données : une animation en cours est arrêtée et la pose restaurée, sauf si
        l'étude et les résultats sont les mêmes (seuls les capteurs sont relus)."""
        if etude is not self._etude or resultats is not self._resultats:
            self.arreter()
            self._animateur = None
            self._etude, self._resultats = etude, resultats
            self._afficher_position(0.0)
        self._remplir_capteurs()
        self._actualiser()

    def autoriser(self, autorise: bool) -> None:
        """Connexion disponible et aucune autre opération sur le canal."""
        self._autorise = autorise
        if not autorise and self.en_lecture:
            self.arreter()
        self._actualiser()

    def definir_occupe(self, occupe: bool) -> None:
        """Tracé ou effacement de trajectoire en cours (le canal est utilisé ailleurs)."""
        self._occupe = occupe
        self._actualiser()

    def animateur(self) -> Animateur | None:
        """L'animateur des résultats courants (créé à la demande), None sans résultat ni canal."""
        if self._animateur is None:
            canal = self._fournisseur_canal()
            if self._etude is None or self._resultats is None or canal is None:
                return None
            self._animateur = Animateur(canal, self._etude, self._resultats)
        return self._animateur

    def _remplir_capteurs(self) -> None:
        precedent = self.choix_capteur.currentText()
        noms = (
            []
            if self._etude is None
            else [c.nom for c in self._etude.capteurs if isinstance(c, CapteurPoint)]
        )
        self.choix_capteur.blockSignals(True)
        self.choix_capteur.clear()
        self.choix_capteur.addItems(noms)
        if precedent in noms:
            self.choix_capteur.setCurrentText(precedent)
        self.choix_capteur.blockSignals(False)

    def _actualiser(self) -> None:
        pret = self._autorise and self._resultats is not None and not self._occupe
        for w in (self.bouton_lecture, self.bouton_arret, self.selecteur_vitesse, self.curseur):
            w.setEnabled(pret)
        a_capteur = self.choix_capteur.count() > 0
        self.bouton_trajectoire.setEnabled(pret and a_capteur)
        self.bouton_effacer.setEnabled(pret)
        self.bouton_lecture.setText(
            textes.ANIMATION_PAUSE if self.en_lecture else textes.ANIMATION_LECTURE
        )
        if pret:
            self.etiquette_etat.setText("" if a_capteur else textes.ANIMATION_PAS_DE_CAPTEUR)
        elif self._resultats is None:
            self.etiquette_etat.setText(textes.ANIMATION_INACTIVE + textes.ANIMATION_SANS_RESULTAT)
        elif not self._autorise:
            self.etiquette_etat.setText(textes.ANIMATION_INACTIVE + textes.ANIMATION_SANS_CONNEXION)
        else:
            self.etiquette_etat.setText(textes.ANIMATION_INACTIVE + textes.ANIMATION_OCCUPEE)

    def _afficher_position(self, instant: float) -> None:
        duree = self.duree
        self.curseur.blockSignals(True)
        valeur = 0 if duree <= 0.0 else round(RESOLUTION_CURSEUR * instant / duree)
        self.curseur.setValue(valeur)
        self.curseur.blockSignals(False)
        self.etiquette_temps.setText(textes.animation_temps(instant, duree))

    # --- commandes -------------------------------------------------------------------------
    def _echec(self, e: Exception) -> None:
        self.minuteur.stop()
        self._actualiser()
        self.erreur.emit(str(e))

    def _sur_lecture(self) -> None:
        animateur = self.animateur()
        if animateur is None:
            return
        try:
            if self.en_lecture:
                self.minuteur.stop()
                animateur.pause()
            else:
                animateur.vitesse = self.vitesse
                animateur.lire()
                self.minuteur.start()
        except (ErreurCanal, ValueError) as e:
            self._echec(e)
            return
        self._actualiser()

    def _tic(self) -> None:
        animateur = self._animateur
        if animateur is None:
            self.minuteur.stop()
            return
        try:
            continue_ = animateur.avancer()
        except (ErreurCanal, ValueError) as e:
            self._echec(e)
            return
        self._afficher_position(animateur.position)
        if not continue_:
            self.minuteur.stop()
            self._actualiser()

    def _sur_vitesse(self) -> None:
        if self._animateur is not None:
            self._animateur.vitesse = self.vitesse

    def _sur_curseur(self, valeur: int) -> None:
        animateur = self.animateur()
        if animateur is None:
            return
        instant = self.duree * valeur / RESOLUTION_CURSEUR
        try:
            animateur.aller_a(instant)
        except (ErreurCanal, ValueError) as e:
            self._echec(e)
            return
        self.etiquette_temps.setText(textes.animation_temps(instant, self.duree))

    def arreter(self) -> None:
        """Arrête la lecture, restaure la pose initiale et remet le curseur à zéro."""
        self.minuteur.stop()
        if self._animateur is not None:
            try:
                self._animateur.reinitialiser()
            except ErreurCanal as e:
                self.erreur.emit(str(e))
        self._afficher_position(0.0)
        self._actualiser()

    def _sur_tracer(self) -> None:
        nom = self.choix_capteur.currentText()
        if nom:
            self.arreter()
            self.trajectoire_demandee.emit(nom)
