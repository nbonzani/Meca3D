# SPDX-License-Identifier: GPL-3.0-or-later
"""Fenêtre principale (SPEC § 5, EX-61) : arbre, onglets, propriétés, barre d'état, commandes.

Aucune logique métier ici : `modele/`, `graphe/` et `cao/` décident ; la simulation passe par
`moteur/processus.py` (processus séparé) ; connexion et import (E/S réseau) par un QThreadPool.
"""

import os
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path

from PyQt6.QtCore import (
    QElapsedTimer,
    QObject,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QAction, QCloseEvent, QShowEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from meca3d.cao.canal import CanalSolidCraft, ErreurCanal
from meca3d.cao.solidcraft import importer, reimporter, structure_a_change
from meca3d.graphe.graphe import depuis_etude
from meca3d.graphe.mobilite import (
    Mode,
    ResultatMobilite,
    calculer_mobilite,
    verifier_avant_simulation,
)
from meca3d.ihm import textes, theme
from meca3d.ihm.arbre import (
    GENRE_ACTION,
    GENRE_CAPTEUR,
    GENRE_COUPLAGE,
    GENRE_LIAISON,
    GENRE_PILOTE,
    GENRE_RESSORT,
    GENRE_RUBRIQUE,
    GENRE_SOLIDE,
    ArbreEtude,
)
from meca3d.ihm.etapes import BarreEtapes, etats_etapes
from meca3d.ihm.proprietes import PanneauProprietes
from meca3d.ihm.vue_animation import VueAnimation
from meca3d.ihm.vue_courbes import VueCourbes
from meca3d.ihm.vue_graphe import VueGraphe
from meca3d.ihm.vue_torseurs import VueTorseurs
from meca3d.modele.capteurs import CapteurPoint
from meca3d.modele.etude import (
    ErreurEtude,
    ErreurValidation,
    Etude,
    ecrire_etude,
    lire_etude,
    simulation_possible,
)
from meca3d.modele.liaison import Statut
from meca3d.moteur.base import ErreurMoteur, ResultatsBruts
from meca3d.moteur.processus import (
    CalculEnCours,
    EtatCalcul,
    ModeSimulation,
    ProcessusPrechauffe,
)
from meca3d.resultats.export import colonnes_resultats, ecrire_csv

PERIODE_SCRUTATION_MS = 50  # minuteur de lecture de la progression du processus de calcul
RESOLUTION_PROGRESSION = 1000
TAILLE_ICONES = 20  # px, barre de commandes

# Icônes Tabler (ihm/icones/) des commandes de la barre
ICONES = {
    "action_nouveau": "file-plus",
    "action_ouvrir": "folder-open",
    "action_enregistrer": "device-floppy",
    "action_connecter": "plug-connected",
    "action_importer": "file-import",
    "action_valider_toutes": "checks",
    "action_simuler": "player-play",
    "action_simuler_cinematique": "route",
    "action_annuler": "player-stop",
    "action_exporter_csv": "file-spreadsheet",
}


class _SignauxTache(QObject):
    reussi = pyqtSignal(object)
    echec = pyqtSignal(str)


class _Tache(QRunnable):
    """Opération potentiellement longue (réseau) exécutée dans le QThreadPool."""

    def __init__(self, travail: Callable[[], object]) -> None:
        super().__init__()
        self.signaux = _SignauxTache()
        self._travail = travail

    def run(self) -> None:
        try:
            resultat = self._travail()
        except (ErreurCanal, OSError, ValueError) as e:
            self.signaux.echec.emit(str(e))
        else:
            self.signaux.reussi.emit(resultat)


def dossier_exemples() -> Path | None:
    """Dossier `exemples` livré : à côté de l'exécutable, ou à la racine du dépôt (sources)."""
    candidats = [Path(sys.executable).parent / "exemples"] if getattr(sys, "frozen", False) else []
    candidats.append(Path(__file__).resolve().parents[3] / "exemples")
    return next((c for c in candidats if c.is_dir()), None)


def _connecter_canal(fabrique: Callable[[], CanalSolidCraft]) -> CanalSolidCraft:
    canal = fabrique()
    canal.connecter()
    canal.requete("document.inspect")  # vérifie le jeton et la réponse (EX-01, EX-02)
    return canal


class FenetrePrincipale(QMainWindow):
    calcul_termine = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(textes.TITRE_FENETRE)
        self.resize(1200, 750)
        self._etude: Etude | None = None
        self.mobilite: ResultatMobilite | None = None
        self.resultats: ResultatsBruts | None = None
        self.calcul: CalculEnCours | None = None
        self.canal: CanalSolidCraft | None = None
        self.dernier_message = ""
        self._hyper_session = False  # EX-23 sans étude : décoché par défaut
        self.chemin_etude: Path | None = None
        self.modifiee = False  # modifications non enregistrées
        self.structure_modifiee = False  # EX-06 : la maquette a changé depuis l'import
        self.verifications = 0  # nombre de vérifications de structure terminées
        self.prechauffe: ProcessusPrechauffe | None = None
        self.fabrique_canal: Callable[[], CanalSolidCraft] = CanalSolidCraft
        self.confirmer: Callable[[str, str], bool] = self._confirmer_dialogue
        self.dialogue_ouvrir: Callable[[], Path | None] = self._dialogue_ouvrir
        self.dialogue_enregistrer: Callable[[str], Path | None] = self._dialogue_enregistrer
        self.dialogue_csv: Callable[[str], Path | None] = self._dialogue_csv
        self._pool = QThreadPool(self)
        self._taches: list[_Tache] = []
        self._connexion_en_cours = False
        self._import_en_cours = False
        self._verification_en_cours = False
        self._simulation_en_attente = False
        self._etude_avant_import: Etude | None = None
        self.theme = theme.Theme.CLAIR

        self.arbre = ArbreEtude()
        self.proprietes = PanneauProprietes()
        self.vue_graphe = VueGraphe()
        self.vue_courbes = VueCourbes()
        self.vue_torseurs = VueTorseurs()
        self.vue_animation = VueAnimation(lambda: self.canal)
        self.journal = QPlainTextEdit()
        self.journal.setReadOnly(True)
        self.onglets = QTabWidget()
        self.onglets.addTab(self.vue_graphe, textes.ONGLET_GRAPHE)
        self.onglets.addTab(self.vue_courbes, textes.ONGLET_COURBES)
        self.onglets.addTab(self.vue_torseurs, textes.ONGLET_TORSEURS)
        self.onglets.addTab(self.vue_animation, textes.ONGLET_ANIMATION)
        self.onglets.addTab(self.journal, textes.ONGLET_JOURNAL)
        self.separateur = QSplitter(Qt.Orientation.Horizontal)
        self.separateur.addWidget(self.arbre)
        self.separateur.addWidget(self.onglets)
        self.separateur.addWidget(self.proprietes)
        self.separateur.setSizes([280, 600, 320])
        # bandeau « maquette modifiée » (EX-06), au-dessus de la zone de travail
        self.bandeau = QFrame()
        self.bandeau.setObjectName("bandeau")
        ligne_bandeau = QHBoxLayout(self.bandeau)
        self.etiquette_bandeau = QLabel(textes.BANDEAU_MODIFIEE)
        self.bouton_reimporter = QPushButton(textes.BOUTON_REIMPORTER)
        ligne_bandeau.addWidget(self.etiquette_bandeau, 1)
        ligne_bandeau.addWidget(self.bouton_reimporter)
        self.bandeau.hide()
        self.etapes = BarreEtapes()
        centre = QWidget()
        colonne = QVBoxLayout(centre)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        colonne.addWidget(self.etapes)
        colonne.addWidget(self.bandeau)
        colonne.addWidget(self.separateur, 1)
        self.setCentralWidget(centre)

        self._creer_actions()
        self._creer_menus()
        self._creer_barre_etat()

        self.minuteur = QTimer(self)
        self.minuteur.setInterval(PERIODE_SCRUTATION_MS)
        self.minuteur.timeout.connect(self._scruter_calcul)
        self.arbre.selection_changee.connect(self._sur_selection)
        self.proprietes.modifiee.connect(self._sur_modification)
        self.proprietes.capteurs_modifies.connect(self._sur_capteurs_modifies)
        self.bouton_reimporter.clicked.connect(self.importer)
        self.vue_animation.trajectoire_demandee.connect(self.tracer_trajectoire)
        self.vue_animation.effacement_demande.connect(self.effacer_trajectoires)
        self.vue_animation.erreur.connect(self._message)
        self.etapes.etape_choisie.connect(self._sur_etape)
        self.definir_theme(theme.Theme.CLAIR)
        self._actualiser()

    # --- construction ------------------------------------------------------------------------
    def _action(self, texte: str, info: str = "", cochable: bool = False) -> QAction:
        action = QAction(texte, self)
        action.setToolTip(info or texte)
        action.setStatusTip(info)
        action.setCheckable(cochable)
        return action

    def _creer_actions(self) -> None:
        self.action_nouveau = self._action(textes.ACTION_NOUVEAU)
        self.action_ouvrir = self._action(textes.ACTION_OUVRIR)
        self.action_enregistrer = self._action(textes.ACTION_ENREGISTRER)
        self.action_enregistrer_sous = self._action(textes.ACTION_ENREGISTRER_SOUS)
        self.action_exporter_csv = self._action(textes.ACTION_EXPORTER_CSV)
        self.action_quitter = self._action(textes.ACTION_QUITTER)
        self.action_connecter = self._action(textes.ACTION_CONNECTER)
        self.action_importer = self._action(textes.ACTION_IMPORTER)
        self.action_simuler = self._action(textes.ACTION_SIMULER, textes.INFO_SIMULER)
        self.action_simuler_cinematique = self._action(
            textes.ACTION_SIMULER_CINEMATIQUE, textes.INFO_SIMULER_CINEMATIQUE
        )
        self.action_annuler = self._action(textes.ACTION_ANNULER)
        self.action_reglages = self._action(textes.ACTION_REGLAGES, textes.INFO_REGLAGES)
        self.action_valider_toutes = self._action(textes.ACTION_VALIDER_TOUTES)
        self.action_validation_en_bloc = self._action(
            textes.ACTION_VALIDATION_EN_BLOC, textes.INFO_VALIDATION_EN_BLOC, cochable=True
        )
        self.action_hyperstatique = self._action(
            textes.ACTION_HYPERSTATIQUE, textes.INFO_HYPERSTATIQUE, cochable=True
        )
        self.action_theme_sombre = self._action(textes.ACTION_THEME_SOMBRE, cochable=True)
        self.action_theme_sombre.toggled.connect(self._sur_theme_sombre)
        self.action_quitter.triggered.connect(self.close)
        self.action_nouveau.triggered.connect(self._sur_nouveau)
        self.action_ouvrir.triggered.connect(self._sur_ouvrir)
        self.action_enregistrer.triggered.connect(self._sur_enregistrer)
        self.action_enregistrer_sous.triggered.connect(self._sur_enregistrer_sous)
        self.action_exporter_csv.triggered.connect(self._sur_exporter_csv)
        self.action_connecter.triggered.connect(self.connecter)
        self.action_importer.triggered.connect(self.importer)
        self.action_simuler.triggered.connect(self._sur_simuler)
        self.action_simuler_cinematique.triggered.connect(self._sur_simuler_cinematique)
        self.action_annuler.triggered.connect(self.annuler)
        self.action_reglages.triggered.connect(self.afficher_reglages)
        self.action_valider_toutes.triggered.connect(self.valider_toutes)
        self.action_validation_en_bloc.triggered.connect(self._sur_validation_en_bloc)
        self.action_hyperstatique.triggered.connect(self._sur_hyperstatique)

    def _creer_menus(self) -> None:
        barre = self.menuBar()
        assert barre is not None
        fichier = barre.addMenu(textes.MENU_FICHIER)
        solidcraft = barre.addMenu(textes.MENU_SOLIDCRAFT)
        simulation = barre.addMenu(textes.MENU_SIMULATION)
        enseignant = barre.addMenu(textes.MENU_ENSEIGNANT)
        affichage = barre.addMenu(textes.MENU_AFFICHAGE)
        assert fichier and solidcraft and simulation and enseignant and affichage
        fichier.addAction(self.action_nouveau)
        fichier.addAction(self.action_ouvrir)
        fichier.addAction(self.action_enregistrer)
        fichier.addAction(self.action_enregistrer_sous)
        fichier.addSeparator()
        fichier.addAction(self.action_exporter_csv)
        fichier.addSeparator()
        fichier.addAction(self.action_quitter)
        solidcraft.addAction(self.action_connecter)
        solidcraft.addAction(self.action_importer)
        simulation.addAction(self.action_simuler)
        simulation.addAction(self.action_simuler_cinematique)
        simulation.addAction(self.action_annuler)
        simulation.addSeparator()
        simulation.addAction(self.action_reglages)
        enseignant.addAction(self.action_validation_en_bloc)
        enseignant.addAction(self.action_hyperstatique)
        affichage.addAction(self.action_theme_sombre)
        outils = QToolBar(textes.TITRE_BARRE_COMMANDES, self)
        outils.setMovable(False)
        outils.setIconSize(QSize(TAILLE_ICONES, TAILLE_ICONES))
        outils.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        groupes = (
            (self.action_ouvrir, self.action_enregistrer),
            (self.action_connecter, self.action_importer, self.action_valider_toutes),
            (self.action_simuler, self.action_simuler_cinematique, self.action_annuler),
            (self.action_exporter_csv,),
        )
        for rang, groupe in enumerate(groupes):
            if rang:
                outils.addSeparator()
            for action in groupe:
                outils.addAction(action)
        # simulations : libellé à côté de l'icône ; Simuler (dynamique) est l'action principale
        for action in (self.action_simuler, self.action_simuler_cinematique):
            bouton = outils.widgetForAction(action)
            if isinstance(bouton, QToolButton):
                bouton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        bouton_principal = outils.widgetForAction(self.action_simuler)
        if bouton_principal is not None:
            bouton_principal.setObjectName("actionPrincipale")
        self.barre_commandes = outils
        self.addToolBar(outils)

    def _creer_barre_etat(self) -> None:
        barre = self.statusBar()
        assert barre is not None
        self.etiquette_connexion = QLabel(textes.CONNEXION_ABSENTE)
        self.etiquette_m = QLabel(textes.etiquette_m(None))
        self.etiquette_h = QLabel(textes.etiquette_h(None))
        for pastille in (self.etiquette_connexion, self.etiquette_m, self.etiquette_h):
            pastille.setProperty("etat", theme.ETAT_NEUTRE)
        self.barre_progression = QProgressBar()
        self.barre_progression.setRange(0, RESOLUTION_PROGRESSION)
        self.barre_progression.setMaximumWidth(200)
        self.barre_progression.hide()
        for w in (
            self.barre_progression,
            self.etiquette_m,
            self.etiquette_h,
            self.etiquette_connexion,
        ):
            barre.addPermanentWidget(w)

    # --- présentation (R12) -------------------------------------------------------------------
    def definir_theme(self, choix: theme.Theme) -> None:
        """Applique le thème clair ou sombre à la fenêtre, aux icônes et aux figures."""
        self.theme = choix
        self.setPalette(theme.palette(choix))
        self.setStyleSheet(theme.feuille_de_style(choix))
        for attribut, nom in ICONES.items():
            action: QAction = getattr(self, attribut)
            couleur = theme.TEXTE_ACTION_PRINCIPALE if action is self.action_simuler else None
            action.setIcon(theme.icone(nom, choix, couleur))
        couleurs = theme.couleurs(choix)
        self.arbre.definir_couleur_incomplet(couleurs.incomplet)
        self.vue_graphe.definir_couleurs(couleurs)
        self.vue_courbes.definir_couleurs(couleurs)
        self.action_theme_sombre.blockSignals(True)
        self.action_theme_sombre.setChecked(choix is theme.Theme.SOMBRE)
        self.action_theme_sombre.blockSignals(False)

    def _sur_theme_sombre(self, coche: bool) -> None:
        self.definir_theme(theme.Theme.SOMBRE if coche else theme.Theme.CLAIR)

    @staticmethod
    def _pastille(etiquette: QLabel, etat: str) -> None:
        """Change l'état (propriété QSS « etat ») d'une pastille de la barre d'état."""
        if etiquette.property("etat") == etat:
            return
        etiquette.setProperty("etat", etat)
        style = etiquette.style()
        if style is not None:
            style.unpolish(etiquette)
            style.polish(etiquette)

    def _sur_etape(self, rang: int) -> None:
        """Clic sur une étape : sa branche de l'arbre et son onglet de travail."""
        branches = (textes.BRANCHE_MODELE, textes.BRANCHE_DONNEES, None, textes.BRANCHE_RESULTATS)
        vues = (self.vue_graphe, None, self.journal, self.vue_courbes)
        branche, vue = branches[rang], vues[rang]
        if branche is not None:
            self.arbre.selectionner_branche(branche)
        else:  # étape Simulation : ses réglages (EX-40)
            self.afficher_reglages()
        if vue is not None:
            self.onglets.setCurrentWidget(vue)

    def afficher_reglages(self) -> None:
        """Réglages de simulation de l'étude dans le panneau des propriétés (EX-40)."""
        if self.etude is None:
            self._message(textes.MSG_PAS_D_ETUDE)
            return
        self.proprietes.afficher_reglages()

    def _maj_etapes(self, simulable: bool) -> None:
        arbre = self.arbre
        self.etapes.definir_etats(
            etats_etapes(
                etude_ouverte=self.etude is not None,
                modele_incomplet=arbre.est_incomplet(arbre.item_branche(textes.BRANCHE_MODELE)),
                donnees_incompletes=arbre.est_incomplet(arbre.item_branche(textes.BRANCHE_DONNEES)),
                simulable=simulable,
                resultats=self.resultats is not None,
            )
        )

    # --- messages ----------------------------------------------------------------------------
    def _message(self, texte: str) -> None:
        self.dernier_message = texte
        self.journal.appendPlainText(texte)
        barre = self.statusBar()
        if barre is not None:
            barre.showMessage(texte.splitlines()[0] if texte else "", 15000)

    def _confirmer_dialogue(self, titre: str, texte: str) -> bool:
        reponse = QMessageBox.question(self, titre, texte)
        return reponse == QMessageBox.StandardButton.Yes

    # --- étude -------------------------------------------------------------------------------
    @property
    def etude(self) -> Etude | None:
        """Étude ouverte (propriété : les tests relisent l'attribut après chaque commande)."""
        return self._etude

    @property
    def hyperstatique_autorise(self) -> bool:
        """EX-23 : champ de l'étude ouverte (réglage de session s'il n'y a pas d'étude)."""
        if self.etude is not None:
            return self.etude.hyperstatique_autorise
        return self._hyper_session

    @hyperstatique_autorise.setter
    def hyperstatique_autorise(self, valeur: bool) -> None:
        self._hyper_session = valeur
        if self.etude is not None:
            self.etude.hyperstatique_autorise = valeur

    def charger_etude(self, etude: Etude) -> None:
        self._remplacer_etude(etude)

    def _remplacer_etude(self, etude: Etude | None) -> None:
        self._etude = etude
        self.resultats = None
        self.modifiee = False
        self.structure_modifiee = False
        self.proprietes.definir_etude(etude)
        if etude is None:
            self.proprietes.afficher_texte(textes.TITRE_PROPRIETES, textes.PROPRIETES_VIDE)
        self._afficher_resultats(basculer=False)
        self._actualiser()

    def _afficher_resultats(self, basculer: bool) -> None:
        """Alimente les courbes et le tableau des torseurs (vides sans résultat)."""
        self.vue_courbes.afficher(self.etude, self.resultats)
        self.vue_torseurs.afficher(self.etude, self.resultats)
        self.vue_animation.definir(self.etude, self.resultats)
        if basculer and self.resultats is not None:
            self.onglets.setCurrentWidget(self.vue_courbes)

    def _sur_modification(self) -> None:
        """Une donnée de l'étude a changé : les résultats ne la reflètent plus."""
        self.modifiee = True
        self.annuler()  # un calcul en cours porte sur l'ancien état de l'étude
        if self.resultats is not None:
            self.resultats = None
            self._afficher_resultats(basculer=False)
        self._actualiser()

    def _sur_capteurs_modifies(self) -> None:
        """Un capteur est post-traité : les résultats restent valables, les vues sont refaites."""
        self.modifiee = True
        self._afficher_resultats(basculer=False)
        self._actualiser()

    def _maj_titre(self) -> None:
        nom = None if self.chemin_etude is None else self.chemin_etude.name
        self.setWindowTitle(textes.titre_fenetre(nom, self.modifiee and self.etude is not None))

    def _maj_bandeau(self) -> None:
        self.bandeau.setVisible(self.etude is not None and self.structure_modifiee)

    def _calculer_mobilite(self) -> ResultatMobilite | None:
        if self.etude is None or not self.etude.liaisons:
            return None
        try:
            return calculer_mobilite(depuis_etude(self.etude))
        except (ValueError, KeyError):  # type manquant, seconde direction à saisir...
            return None

    def _actualiser(self) -> None:
        etude = self.etude
        self.mobilite = self._calculer_mobilite()
        m = None if self.mobilite is None else self.mobilite.m
        h = None if self.mobilite is None else self.mobilite.h
        self.etiquette_m.setText(textes.etiquette_m(m))
        self.etiquette_h.setText(textes.etiquette_h(h))
        self._pastille(self.etiquette_m, theme.etat_m(m))
        self._pastille(self.etiquette_h, theme.etat_h(h))
        self.arbre.mettre_a_jour(etude, self.mobilite)
        self.vue_graphe.afficher(etude, self.mobilite)
        self.proprietes.rafraichir()
        self._maj_bandeau()
        self._maj_titre()
        self._maj_actions()

    def _maj_actions(self) -> None:
        etude = self.etude
        libre = self.calcul is None and not self._simulation_en_attente
        simulable = etude is not None and bool(etude.liaisons) and simulation_possible(etude)
        self.action_simuler.setEnabled(simulable and libre)
        self.action_simuler.setToolTip(
            textes.INFO_SIMULER if simulable else textes.INFO_SIMULER_INACTIF
        )
        self.action_simuler_cinematique.setEnabled(simulable and libre)
        self.action_simuler_cinematique.setToolTip(
            textes.INFO_SIMULER_CINEMATIQUE if simulable else textes.INFO_SIMULER_INACTIF
        )
        self.action_annuler.setEnabled(self.calcul is not None)
        self.action_exporter_csv.setEnabled(self.resultats is not None)
        self.action_enregistrer.setEnabled(etude is not None)
        self.action_enregistrer_sous.setEnabled(etude is not None)
        self.action_hyperstatique.blockSignals(True)
        self.action_hyperstatique.setChecked(self.hyperstatique_autorise)
        self.action_hyperstatique.blockSignals(False)
        en_bloc = etude is not None and etude.validation_en_bloc
        self.action_validation_en_bloc.blockSignals(True)
        self.action_validation_en_bloc.setChecked(en_bloc)
        self.action_validation_en_bloc.blockSignals(False)
        self.action_valider_toutes.setVisible(en_bloc)
        a_valider = etude is not None and any(
            x.statut is Statut.PROPOSEE and x.type is not None for x in etude.liaisons
        )
        self.action_valider_toutes.setEnabled(en_bloc and a_valider)
        self.action_connecter.setEnabled(not self._connexion_en_cours)
        connecte = self.canal is not None and self.canal.connecte
        peut_importer = (
            connecte and not self._import_en_cours and not self._verification_en_cours and libre
        )
        self.action_importer.setEnabled(peut_importer)
        self._pastille(self.etiquette_connexion, theme.ETAT_OK if connecte else theme.ETAT_NEUTRE)
        self._maj_etapes(simulable)
        self.bouton_reimporter.setEnabled(peut_importer)
        self.vue_animation.autoriser(
            connecte and not self._import_en_cours and not self._verification_en_cours
        )

    # --- sélection ---------------------------------------------------------------------------
    def _sur_selection(self, genre: str, nom: str) -> None:
        etude = self.etude
        if etude is None:
            return
        if genre in (GENRE_LIAISON, GENRE_PILOTE):
            self.proprietes.afficher_liaison(etude.liaison(nom))
        elif genre == GENRE_COUPLAGE:
            self.proprietes.afficher_couplage(next(c for c in etude.couplages if c.nom == nom))
        elif genre == GENRE_ACTION:
            self.proprietes.afficher_action(next(a for a in etude.actions if a.nom == nom))
        elif genre == GENRE_RESSORT:
            self.proprietes.afficher_ressort(next(r for r in etude.ressorts if r.nom == nom))
        elif genre == GENRE_CAPTEUR:
            self.proprietes.afficher_capteur(next(c for c in etude.capteurs if c.nom == nom))
        elif genre == GENRE_SOLIDE:
            s = etude.solide(nom)
            texte = (
                f"Masse : {s.masse:.4g} kg\n"
                f"Centre de gravité : ({s.cdg[0]:.4g} ; {s.cdg[1]:.4g} ; {s.cdg[2]:.4g}) m\n"
                f"Inertie au centre de gravité, en repère monde (kg·m²) :\n{s.inertie}"
            )
            self.proprietes.afficher_texte(nom + (" (bâti)" if s.fixe else ""), texte)
        elif genre == GENRE_RUBRIQUE:
            self._afficher_rubrique(nom, etude)

    def _afficher_rubrique(self, nom: str, etude: Etude) -> None:
        if nom == textes.RUBRIQUE_GRAPHE:
            self.onglets.setCurrentWidget(self.vue_graphe)
            self.proprietes.afficher_texte(nom, self.vue_graphe.resume())
        elif nom == textes.RUBRIQUE_COUPLAGES:
            self.proprietes.afficher_couplage(None)
        elif nom == textes.RUBRIQUE_PESANTEUR:
            self.proprietes.afficher_pesanteur()
        elif nom == textes.RUBRIQUE_ACTIONS:
            self.proprietes.afficher_action(None)
        elif nom == textes.RUBRIQUE_RESSORTS:
            self.proprietes.afficher_ressort(None)
        elif nom == textes.RUBRIQUE_CAPTEURS:
            self.proprietes.afficher_capteur(None)
        elif nom == textes.RUBRIQUE_COURBES:
            self.onglets.setCurrentWidget(self.vue_courbes)
            self.proprietes.afficher_texte(nom, textes.COURBES_AIDE)
        elif nom == textes.RUBRIQUE_ANIMATION:
            self.onglets.setCurrentWidget(self.vue_animation)
            self.proprietes.afficher_texte(nom, textes.ANIMATION_AIDE)
        elif nom == textes.RUBRIQUE_PILOTES and self.mobilite is not None:
            self.proprietes.afficher_texte(
                nom,
                f"{len(etude.pilotes)} loi(s) d'entrée pour une mobilité m = {self.mobilite.m}.",
            )
        else:
            self.proprietes.afficher_texte(nom, textes.AUCUN_ELEMENT)

    # --- commandes enseignant et validation --------------------------------------------------
    def _sur_validation_en_bloc(self, coche: bool) -> None:
        if self.etude is None:
            self.action_validation_en_bloc.setChecked(False)
            return
        self.etude.validation_en_bloc = coche
        self.modifiee = True
        self._actualiser()

    def _sur_hyperstatique(self, coche: bool) -> None:
        self.hyperstatique_autorise = coche
        if self.etude is not None:
            self.modifiee = True
            self._maj_titre()

    def valider_toutes(self) -> None:
        etude = self.etude
        if etude is None:
            return
        if not self.confirmer(textes.TITRE_CONFIRMATION_BLOC, textes.TEXTE_CONFIRMATION_BLOC):
            return
        try:
            validees = etude.valider_toutes()
        except ErreurValidation as e:
            self._message(str(e))
            return
        self._message(textes.MSG_BLOC_FAIT + (", ".join(validees) or textes.AUCUN_ELEMENT))
        self._sur_modification()
        self.proprietes.rafraichir()

    # --- connexion et import (QThreadPool) ---------------------------------------------------
    def _lancer(
        self,
        travail: Callable[[], object],
        reussite: Callable[[object], None],
        echec: Callable[[str], None],
    ) -> None:
        tache = _Tache(travail)
        tache.setAutoDelete(False)
        tache.signaux.reussi.connect(reussite)
        tache.signaux.echec.connect(echec)
        self._taches.append(tache)
        self._pool.start(tache)

    def connecter(self) -> None:
        if self._connexion_en_cours:
            return
        if self.canal is not None:
            self.canal.fermer()
            self.canal = None
        self._connexion_en_cours = True
        self.etiquette_connexion.setText(textes.CONNEXION_EN_COURS)
        self._maj_actions()
        fabrique = self.fabrique_canal
        self._lancer(
            lambda: _connecter_canal(fabrique), self._connexion_reussie, self._connexion_echouee
        )

    def _connexion_reussie(self, canal: object) -> None:
        assert isinstance(canal, CanalSolidCraft)
        self._connexion_en_cours = False
        self.canal = canal
        self.etiquette_connexion.setText(textes.connexion_etablie(canal.port))
        self._message(textes.connexion_etablie(canal.port))
        self._maj_actions()
        self.verifier_structure()  # EX-06 : la maquette ouverte est-elle celle de l'étude ?

    def _connexion_echouee(self, message: str) -> None:
        self._connexion_en_cours = False
        self.canal = None
        self.etiquette_connexion.setText(textes.CONNEXION_ABSENTE)
        self._message(message)
        self._maj_actions()

    def importer(self) -> None:
        canal = self.canal
        if canal is None or self._import_en_cours:
            return
        ancienne = self.etude if self.etude is not None and self.etude.liaisons else None
        self._etude_avant_import = ancienne
        self._import_en_cours = True
        self._message(textes.MSG_IMPORT_EN_COURS)
        self._maj_actions()

        def travail() -> object:
            return importer(canal) if ancienne is None else reimporter(canal, ancienne)

        self._lancer(travail, self._import_reussi, self._import_echoue)

    def _import_reussi(self, etude: object) -> None:
        assert isinstance(etude, Etude)
        self._import_en_cours = False
        ancienne, self._etude_avant_import = self._etude_avant_import, None
        reportes = [] if ancienne is None else etude.reporter_saisies(ancienne)
        self.charger_etude(etude)
        self.modifiee = True  # l'étude importée n'est pas encore enregistrée
        self._actualiser()
        self._message(textes.msg_import_termine(len(etude.solides), len(etude.liaisons)))
        for avertissement in [*getattr(etude, "avertissements", []), *reportes]:
            self._message(avertissement)

    def _import_echoue(self, message: str) -> None:
        self._import_en_cours = False
        self._message(message)
        if self.canal is not None and not self.canal.connecte:
            self.canal = None
            self.etiquette_connexion.setText(textes.CONNEXION_ABSENTE)
        self._maj_actions()

    # --- trajectoires dans SolidCraft (EX-52) --------------------------------------------------
    def tracer_trajectoire(self, nom_capteur: str) -> None:
        """Trace dans la maquette, par une spline 3D, la trajectoire d'un capteur de point."""
        capteur = next(
            (
                c
                for c in (self.etude.capteurs if self.etude is not None else [])
                if isinstance(c, CapteurPoint) and c.nom == nom_capteur
            ),
            None,
        )
        animateur = self.vue_animation.animateur()
        if capteur is None or animateur is None:
            return
        self.vue_animation.arreter()
        self.vue_animation.definir_occupe(True)

        def travail() -> object:
            return animateur.tracer_trajectoire(
                capteur.point,
                capteur.solide,
                reference=capteur.solide_reference,
                nom=f"Trajectoire_{capteur.nom}",
            )

        def reussite(nom: object) -> None:
            self.vue_animation.definir_occupe(False)
            self._message(textes.MSG_TRAJECTOIRE_TRACEE.format(nom=nom))

        def echec(message: str) -> None:
            self.vue_animation.definir_occupe(False)
            self._message(message)

        self._lancer(travail, reussite, echec)

    def effacer_trajectoires(self) -> None:
        """Efface de la maquette les trajectoires tracées par Meca3D (`timeline.delete`)."""
        animateur = self.vue_animation.animateur()
        if animateur is None or not animateur.trajectoires:
            self._message(textes.MSG_AUCUNE_TRAJECTOIRE)
            return
        self.vue_animation.arreter()
        self.vue_animation.definir_occupe(True)

        def reussite(nombre: object) -> None:
            self.vue_animation.definir_occupe(False)
            self._message(textes.MSG_TRAJECTOIRES_EFFACEES.format(nombre=nombre))

        def echec(message: str) -> None:
            self.vue_animation.definir_occupe(False)
            self._message(message)

        self._lancer(animateur.effacer_trajectoires, reussite, echec)

    # --- EX-06, R3 : la structure de la maquette a-t-elle changé ? ---------------------------
    def verifier_structure(self, suite: Callable[[], None] | None = None) -> None:
        """Compare la signature mémorisée à celle de la maquette ouverte (réseau : QThreadPool),
        affiche le bandeau si elle diffère, puis appelle `suite`. Sans canal, sans étude ou si le
        canal est occupé, `suite` est appelée tout de suite."""
        etude, canal = self.etude, self.canal
        libre = not (self._import_en_cours or self._verification_en_cours)
        if etude is None or not etude.liaisons or canal is None or not canal.connecte or not libre:
            if suite is not None:
                suite()
            return
        self._verification_en_cours = True
        self._maj_actions()

        def travail() -> object:
            return structure_a_change(canal, etude)

        def reussite(changee: object) -> None:
            self._verification_en_cours = False
            if etude is self.etude:
                self.structure_modifiee = bool(changee)
            self.verifications += 1
            self._maj_bandeau()
            self._maj_actions()
            if suite is not None:
                suite()

        def echec(message: str) -> None:
            self._verification_en_cours = False
            self._message(textes.MSG_VERIFICATION_IMPOSSIBLE + message)
            self.verifications += 1
            self._maj_actions()
            if suite is not None:
                suite()

        self._lancer(travail, reussite, echec)

    # --- fichiers : étude (EX-60) et CSV (EX-52) ---------------------------------------------
    def _dialogue_ouvrir(self) -> Path | None:
        depart = self.chemin_etude.parent if self.chemin_etude else dossier_exemples()
        nom, _ = QFileDialog.getOpenFileName(
            self,
            textes.ACTION_OUVRIR.replace("&", ""),
            "" if depart is None else str(depart),
            textes.FILTRE_ETUDE,
        )
        return Path(nom) if nom else None

    def _dialogue_enregistrer(self, suggestion: str) -> Path | None:
        nom, _ = QFileDialog.getSaveFileName(
            self, textes.ACTION_ENREGISTRER_SOUS.replace("&", ""), suggestion, textes.FILTRE_ETUDE
        )
        return Path(nom) if nom else None

    def _dialogue_csv(self, suggestion: str) -> Path | None:
        nom, _ = QFileDialog.getSaveFileName(
            self, textes.ACTION_EXPORTER_CSV, suggestion, textes.FILTRE_CSV
        )
        return Path(nom) if nom else None

    def _sur_nouveau(self) -> None:
        self.nouvelle_etude()

    def _sur_ouvrir(self) -> None:
        self.ouvrir_etude()

    def _sur_enregistrer(self) -> None:
        self.enregistrer_etude()

    def _sur_enregistrer_sous(self) -> None:
        self.enregistrer_sous()

    def _sur_exporter_csv(self) -> None:
        self.exporter_csv()

    def _abandon_confirme(self) -> bool:
        if self.etude is None or not self.modifiee:
            return True
        return self.confirmer(textes.TITRE_CONFIRMATION_ABANDON, textes.TEXTE_CONFIRMATION_ABANDON)

    def nouvelle_etude(self) -> bool:
        if self.calcul is not None or not self._abandon_confirme():
            return False
        self.chemin_etude = None
        self._remplacer_etude(None)
        return True

    def ouvrir_etude(self, chemin: Path | None = None) -> bool:
        """EX-60 : un fichier illisible ou incohérent donne un message, jamais d'étude partielle."""
        if self.calcul is not None:
            return False
        if chemin is None:
            chemin = self.dialogue_ouvrir()
            if chemin is None:
                return False
        if not self._abandon_confirme():
            return False
        try:
            etude = lire_etude(chemin)
        except ErreurEtude as e:
            self._message(str(e))
            return False
        self.chemin_etude = chemin
        self._remplacer_etude(etude)
        self._message(textes.MSG_ETUDE_OUVERTE + chemin.name)
        return True

    def enregistrer_etude(self) -> bool:
        if self.chemin_etude is None:
            return self.enregistrer_sous()
        return self._ecrire_etude(self.chemin_etude)

    def enregistrer_sous(self, chemin: Path | None = None) -> bool:
        if self.etude is None:
            self._message(textes.MSG_PAS_D_ETUDE)
            return False
        if chemin is None:
            suggestion = "etude.meca3d" if self.chemin_etude is None else str(self.chemin_etude)
            chemin = self.dialogue_enregistrer(suggestion)
            if chemin is None:
                return False
        if chemin.suffix != ".meca3d":
            chemin = chemin.with_suffix(".meca3d")
        return self._ecrire_etude(chemin)

    def _ecrire_etude(self, chemin: Path) -> bool:
        if self.etude is None:
            return False
        try:
            ecrire_etude(self.etude, chemin)
        except OSError as e:
            self._message(f"Enregistrement impossible : {e}")
            return False
        self.chemin_etude = chemin
        self.modifiee = False
        self._maj_titre()
        self._message(textes.MSG_ETUDE_ENREGISTREE + chemin.name)
        return True

    def exporter_csv(self, chemin: Path | None = None) -> bool:
        """EX-52 : exporte les grandeurs des courbes (mêmes colonnes que `meca3d simuler`)."""
        if self.etude is None or self.resultats is None:
            self._message(textes.MSG_PAS_DE_RESULTAT)
            return False
        if chemin is None:
            chemin = self.dialogue_csv("resultats.csv")
            if chemin is None:
                return False
        try:
            ecrire_csv(chemin, colonnes_resultats(self.etude, self.resultats))
        except OSError as e:
            self._message(f"Export impossible : {e}")
            return False
        self._message(textes.MSG_CSV_ECRIT + chemin.name)
        return True

    # --- simulation (processus séparé) -------------------------------------------------------
    def _sur_simuler(self) -> None:
        self.simuler(ModeSimulation.DYNAMIQUE)

    def _sur_simuler_cinematique(self) -> None:
        self.simuler(ModeSimulation.CINEMATIQUE)

    def simuler(self, mode: ModeSimulation = ModeSimulation.DYNAMIQUE) -> None:
        etude = self.etude
        if etude is None:
            self._message(textes.MSG_PAS_D_ETUDE)
            return
        if self.calcul is not None or self._simulation_en_attente:
            return
        if self.mobilite is None:
            self._message(textes.MSG_MOBILITE_INDISPONIBLE)
            return
        # EX-22 : garde-fou avant tout lancement, aucun appel au moteur en cas de refus
        decision = verifier_avant_simulation(
            self.mobilite, Mode(mode.value), len(etude.pilotes), self.hyperstatique_autorise
        )
        if not decision.autorise:
            self._message(decision.message)
            return
        if decision.message:
            self._message(decision.message)
        # R3 : vérifier la maquette (réseau, hors du fil IHM) avant de lancer le calcul
        self._simulation_en_attente = True
        self._maj_actions()
        self.verifier_structure(partial(self._demarrer_calcul, mode))

    def _demarrer_calcul(self, mode: ModeSimulation) -> None:
        self._simulation_en_attente = False
        etude = self.etude
        if etude is None or self.calcul is not None:
            self._maj_actions()
            return
        self.resultats = None
        self._afficher_resultats(basculer=False)
        self.calcul = CalculEnCours(etude, mode)
        self.calcul.demarrer(self.prechauffe)  # processus préchauffé s'il est prêt (R6)
        self.barre_progression.setValue(0)
        self.barre_progression.show()
        self.minuteur.start()
        self._message(textes.MSG_CALCUL_LANCE)
        self._maj_actions()

    def _scruter_calcul(self) -> None:
        calcul = self.calcul
        if calcul is None:
            self.minuteur.stop()
            return
        for progression in calcul.interroger():
            self.barre_progression.setValue(round(progression.fraction * RESOLUTION_PROGRESSION))
        if calcul.etat is EtatCalcul.EN_COURS:
            return
        self.minuteur.stop()
        self.barre_progression.hide()
        self.calcul = None
        if calcul.etat is EtatCalcul.TERMINE and calcul.resultats is not None:
            self.resultats = calcul.resultats
            self._message(textes.msg_calcul_termine(len(calcul.resultats.t)))
            for avertissement in calcul.resultats.avertissements:
                self._message(avertissement)
            self._afficher_resultats(basculer=True)
        elif isinstance(calcul.erreur, ErreurMoteur):
            self._message(textes.MSG_CALCUL_ECHEC + str(calcul.erreur))
        self._maj_actions()
        self._prechauffer()
        self.calcul_termine.emit()

    def annuler(self) -> None:
        """EX-42 : annule le calcul en cours ; retour à l'état prêt, sans résultat."""
        calcul = self.calcul
        if calcul is None:
            return
        self.minuteur.stop()
        calcul.annuler()
        self.calcul = None
        self.resultats = None
        self._afficher_resultats(basculer=False)
        self.barre_progression.hide()
        self._message(textes.MSG_CALCUL_ANNULE)
        self._maj_actions()
        self._prechauffer()

    # --- préchauffage du processus de calcul (R6) --------------------------------------------
    def prechauffe_pret(self) -> bool:
        """Le processus préchauffé a fini ses imports : le prochain calcul démarre sans délai."""
        return self.prechauffe is not None and self.prechauffe.pret

    def _prechauffer(self) -> None:
        """Prépare le processus du prochain calcul, si la fenêtre est ouverte (visible)."""
        if not self.isVisible():
            return
        if self.prechauffe is not None and self.prechauffe.disponible:
            return
        self.prechauffe = ProcessusPrechauffe()
        self.prechauffe.demarrer()

    def showEvent(self, a0: QShowEvent | None) -> None:  # noqa: N802 - nom imposé par Qt
        super().showEvent(a0)
        self._prechauffer()

    def closeEvent(self, a0: QCloseEvent | None) -> None:  # noqa: N802 - nom imposé par Qt
        self.annuler()
        self._pool.waitForDone(2000)  # un tracé de trajectoire en cours doit se terminer
        self.vue_animation.arreter()  # restaure la pose de la maquette (EX-53)
        if self.prechauffe is not None:
            self.prechauffe.arreter()
        self._pool.waitForDone(2000)
        if self.canal is not None:
            self.canal.fermer()
        super().closeEvent(a0)


VARIABLE_AUTOTEST = "MECA3D_AUTOTEST_DELAI_S"
CODE_AUTOTEST_DELAI = 3  # le processus de calcul n'a pas été prêt dans le délai
PERIODE_AUTOTEST_MS = 100


def _armer_autotest(fenetre: FenetrePrincipale, delai: float) -> list[int]:
    """Auto-test (vérification de l'exécutable, EX-63) : ferme la fenêtre dès que le processus de
    calcul préchauffé est prêt, ou au bout de `delai` s (code 3). Rend le code de sortie."""
    code = [CODE_AUTOTEST_DELAI]
    chrono = QElapsedTimer()
    chrono.start()
    minuteur = QTimer(fenetre)

    def verifier() -> None:
        if fenetre.prechauffe_pret():
            code[0] = 0
        elif chrono.elapsed() < delai * 1000.0:
            return
        minuteur.stop()
        fenetre.close()

    minuteur.timeout.connect(verifier)
    minuteur.start(PERIODE_AUTOTEST_MS)
    return code


def lancer() -> int:
    """Ouvre la fenêtre principale (`python -m meca3d` sans argument). Avec la variable
    MECA3D_AUTOTEST_DELAI_S, la fenêtre se ferme seule (vérification de l'exécutable)."""
    application = QApplication.instance() or QApplication(sys.argv)
    if isinstance(application, QApplication):
        application.setStyle("Fusion")  # rendu homogène de la feuille de style (R12)
    fenetre = FenetrePrincipale()
    delai = os.environ.get(VARIABLE_AUTOTEST)
    code = _armer_autotest(fenetre, float(delai)) if delai else None
    fenetre.show()
    sortie = application.exec()
    return sortie if code is None else code[0]
