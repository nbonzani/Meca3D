# SPDX-License-Identifier: GPL-3.0-or-later
"""Fenêtre principale (SPEC § 5, EX-61) : arbre, onglets, propriétés, barre d'état, commandes.

Aucune logique métier ici : `modele/`, `graphe/` et `cao/` décident ; la simulation passe par
`moteur/processus.py` (processus séparé) ; connexion et import (E/S réseau) par un QThreadPool.
"""

import sys
from collections.abc import Callable

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QSplitter,
    QTabWidget,
    QToolBar,
)

from meca3d.cao.canal import CanalSolidCraft, ErreurCanal
from meca3d.cao.solidcraft import importer, reimporter
from meca3d.graphe.graphe import depuis_etude
from meca3d.graphe.mobilite import (
    Mode,
    ResultatMobilite,
    calculer_mobilite,
    verifier_avant_simulation,
)
from meca3d.ihm import textes
from meca3d.ihm.arbre import (
    GENRE_LIAISON,
    GENRE_PILOTE,
    GENRE_RUBRIQUE,
    GENRE_SOLIDE,
    ArbreEtude,
)
from meca3d.ihm.proprietes import PanneauProprietes
from meca3d.ihm.vue_graphe import VueGraphe
from meca3d.modele.etude import ErreurValidation, Etude, simulation_possible
from meca3d.modele.liaison import Statut
from meca3d.moteur.base import ErreurMoteur, ResultatsBruts
from meca3d.moteur.processus import (
    CalculEnCours,
    EtatCalcul,
    ModeSimulation,
    cinematique_disponible,
)

PERIODE_SCRUTATION_MS = 50  # minuteur de lecture de la progression du processus de calcul
RESOLUTION_PROGRESSION = 1000


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
        self.etude: Etude | None = None
        self.mobilite: ResultatMobilite | None = None
        self.resultats: ResultatsBruts | None = None
        self.calcul: CalculEnCours | None = None
        self.canal: CanalSolidCraft | None = None
        self.dernier_message = ""
        self.hyperstatique_autorise = False  # EX-23 : réglage de session, décoché par défaut
        self.fabrique_canal: Callable[[], CanalSolidCraft] = CanalSolidCraft
        self.confirmer: Callable[[str, str], bool] = self._confirmer_dialogue
        self._pool = QThreadPool(self)
        self._taches: list[_Tache] = []
        self._connexion_en_cours = False
        self._import_en_cours = False

        self.arbre = ArbreEtude()
        self.proprietes = PanneauProprietes()
        self.vue_graphe = VueGraphe()
        self.journal = QPlainTextEdit()
        self.journal.setReadOnly(True)
        self.onglets = QTabWidget()
        self.onglets.addTab(self.vue_graphe, textes.ONGLET_GRAPHE)
        self.onglets.addTab(self.journal, textes.ONGLET_JOURNAL)
        separateur = QSplitter(Qt.Orientation.Horizontal)
        separateur.addWidget(self.arbre)
        separateur.addWidget(self.onglets)
        separateur.addWidget(self.proprietes)
        separateur.setSizes([280, 600, 320])
        self.setCentralWidget(separateur)

        self._creer_actions()
        self._creer_menus()
        self._creer_barre_etat()

        self.minuteur = QTimer(self)
        self.minuteur.setInterval(PERIODE_SCRUTATION_MS)
        self.minuteur.timeout.connect(self._scruter_calcul)
        self.arbre.selection_changee.connect(self._sur_selection)
        self.proprietes.modifiee.connect(self._actualiser)
        self._actualiser()

    # --- construction ------------------------------------------------------------------------
    def _action(self, texte: str, info: str = "", cochable: bool = False) -> QAction:
        action = QAction(texte, self)
        action.setToolTip(info or texte)
        action.setStatusTip(info)
        action.setCheckable(cochable)
        return action

    def _creer_actions(self) -> None:
        self.action_quitter = self._action(textes.ACTION_QUITTER)
        self.action_connecter = self._action(textes.ACTION_CONNECTER)
        self.action_importer = self._action(textes.ACTION_IMPORTER)
        self.action_simuler = self._action(textes.ACTION_SIMULER, textes.INFO_SIMULER)
        self.action_simuler_cinematique = self._action(textes.ACTION_SIMULER_CINEMATIQUE)
        self.action_annuler = self._action(textes.ACTION_ANNULER)
        self.action_valider_toutes = self._action(textes.ACTION_VALIDER_TOUTES)
        self.action_validation_en_bloc = self._action(
            textes.ACTION_VALIDATION_EN_BLOC, textes.INFO_VALIDATION_EN_BLOC, cochable=True
        )
        self.action_hyperstatique = self._action(
            textes.ACTION_HYPERSTATIQUE, textes.INFO_HYPERSTATIQUE, cochable=True
        )
        self.action_quitter.triggered.connect(self.close)
        self.action_connecter.triggered.connect(self.connecter)
        self.action_importer.triggered.connect(self.importer)
        self.action_simuler.triggered.connect(self._sur_simuler)
        self.action_simuler_cinematique.triggered.connect(self._sur_simuler_cinematique)
        self.action_annuler.triggered.connect(self.annuler)
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
        assert fichier and solidcraft and simulation and enseignant
        fichier.addAction(self.action_quitter)
        solidcraft.addAction(self.action_connecter)
        solidcraft.addAction(self.action_importer)
        simulation.addAction(self.action_simuler)
        simulation.addAction(self.action_simuler_cinematique)
        simulation.addAction(self.action_annuler)
        enseignant.addAction(self.action_validation_en_bloc)
        enseignant.addAction(self.action_hyperstatique)
        outils = QToolBar("Commandes", self)
        outils.setMovable(False)
        for action in (
            self.action_connecter,
            self.action_importer,
            self.action_valider_toutes,
            self.action_simuler,
            self.action_simuler_cinematique,
            self.action_annuler,
        ):
            outils.addAction(action)
        self.addToolBar(outils)

    def _creer_barre_etat(self) -> None:
        barre = self.statusBar()
        assert barre is not None
        self.etiquette_connexion = QLabel(textes.CONNEXION_ABSENTE)
        self.etiquette_m = QLabel(textes.etiquette_m(None))
        self.etiquette_h = QLabel(textes.etiquette_h(None))
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
    def charger_etude(self, etude: Etude) -> None:
        self.etude = etude
        self.resultats = None
        self._actualiser()

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
        self.arbre.mettre_a_jour(etude, self.mobilite)
        self.vue_graphe.afficher(etude, self.mobilite)
        self.proprietes.rafraichir()
        self._maj_actions()

    def _maj_actions(self) -> None:
        etude = self.etude
        libre = self.calcul is None
        simulable = etude is not None and bool(etude.liaisons) and simulation_possible(etude)
        self.action_simuler.setEnabled(simulable and libre)
        self.action_simuler.setToolTip(
            textes.INFO_SIMULER if simulable else textes.INFO_SIMULER_INACTIF
        )
        cinematique = cinematique_disponible()
        self.action_simuler_cinematique.setEnabled(simulable and libre and cinematique)
        self.action_simuler_cinematique.setToolTip(
            textes.INFO_SIMULER_INACTIF if cinematique else textes.INFO_CINEMATIQUE_INDISPONIBLE
        )
        self.action_annuler.setEnabled(not libre)
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
        self.action_importer.setEnabled(connecte and not self._import_en_cours and libre)

    # --- sélection ---------------------------------------------------------------------------
    def _sur_selection(self, genre: str, nom: str) -> None:
        etude = self.etude
        if etude is None:
            return
        if genre == GENRE_LIAISON:
            self.proprietes.afficher_liaison(etude.liaison(nom))
        elif genre == GENRE_SOLIDE:
            s = etude.solide(nom)
            texte = (
                f"Masse : {s.masse:.4g} kg\n"
                f"Centre de gravité : ({s.cdg[0]:.4g} ; {s.cdg[1]:.4g} ; {s.cdg[2]:.4g}) m\n"
                f"Inertie au centre de gravité, en repère monde (kg·m²) :\n{s.inertie}"
            )
            self.proprietes.afficher_texte(nom + (" (bâti)" if s.fixe else ""), texte)
        elif genre == GENRE_PILOTE:
            pilote = next(p for p in etude.pilotes if p.liaison == nom)
            self.proprietes.afficher_texte(
                f"Loi d'entrée de {nom}", f"f(t) = {pilote.loi.texte}  (t en s ; rad ou m)"
            )
        elif genre == GENRE_RUBRIQUE:
            self._afficher_rubrique(nom, etude)

    def _afficher_rubrique(self, nom: str, etude: Etude) -> None:
        if nom == textes.RUBRIQUE_GRAPHE:
            self.onglets.setCurrentWidget(self.vue_graphe)
            self.proprietes.afficher_texte(nom, self.vue_graphe.resume())
        elif nom == textes.RUBRIQUE_PESANTEUR:
            g = etude.pesanteur
            etat = "" if g.actif else " (désactivée)"
            v = tuple(float(x) for x in g.vecteur)
            self.proprietes.afficher_texte(nom, f"g = {v} m/s²{etat}")
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
        self._actualiser()

    def _sur_hyperstatique(self, coche: bool) -> None:
        self.hyperstatique_autorise = coche

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
        self._actualiser()
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
        self._import_en_cours = True
        self._message(textes.MSG_IMPORT_EN_COURS)
        self._maj_actions()

        def travail() -> object:
            return importer(canal) if ancienne is None else reimporter(canal, ancienne)

        self._lancer(travail, self._import_reussi, self._import_echoue)

    def _import_reussi(self, etude: object) -> None:
        assert isinstance(etude, Etude)
        self._import_en_cours = False
        self.charger_etude(etude)
        self._message(textes.msg_import_termine(len(etude.solides), len(etude.liaisons)))
        for avertissement in getattr(etude, "avertissements", []):
            self._message(avertissement)

    def _import_echoue(self, message: str) -> None:
        self._import_en_cours = False
        self._message(message)
        if self.canal is not None and not self.canal.connecte:
            self.canal = None
            self.etiquette_connexion.setText(textes.CONNEXION_ABSENTE)
        self._maj_actions()

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
        if self.calcul is not None:
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
        self.resultats = None
        self.calcul = CalculEnCours(etude, mode)
        self.calcul.demarrer()
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
        elif isinstance(calcul.erreur, ErreurMoteur):
            self._message(textes.MSG_CALCUL_ECHEC + str(calcul.erreur))
        self._maj_actions()
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
        self.barre_progression.hide()
        self._message(textes.MSG_CALCUL_ANNULE)
        self._maj_actions()

    def closeEvent(self, a0: QCloseEvent | None) -> None:  # noqa: N802 - nom imposé par Qt
        self.annuler()
        self._pool.waitForDone(2000)
        if self.canal is not None:
            self.canal.fermer()
        super().closeEvent(a0)


def lancer() -> int:
    """Ouvre la fenêtre principale (`python -m meca3d` sans argument)."""
    application = QApplication.instance() or QApplication(sys.argv)
    fenetre = FenetrePrincipale()
    fenetre.show()
    return application.exec()
