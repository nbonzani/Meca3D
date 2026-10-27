# SPDX-License-Identifier: GPL-3.0-or-later
"""Panneau des propriétés : liaison (EX-11 à EX-13) avec sa loi d'entrée (EX-30), son frottement
(EX-15) et le pas d'une hélicoïdale (EX-10), couplage (EX-14, EX-16), pesanteur (EX-31), actions
(EX-32), ressorts (EX-33), capteurs (EX-50, EX-51), réglages de simulation (EX-40) ou résumé."""

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from meca3d import unites
from meca3d.ihm import textes
from meca3d.ihm.saisie import (
    ROLE_ERREUR,
    EditeurAction,
    EditeurCapteur,
    EditeurCouplage,
    EditeurLoi,
    EditeurPesanteur,
    EditeurReglages,
    EditeurRessort,
    champ,
    trois_champs,
)
from meca3d.modele.actions import (
    ActionExterieure,
    LoiEntree,
    Pilote,
    RessortAmortisseur,
    grandeurs_pilotables,
)
from meca3d.modele.capteurs import Capteur
from meca3d.modele.couplage import Couplage
from meca3d.modele.etude import Etude
from meca3d.modele.liaison import (
    AXES_MONDE,
    DIRECTION_REQUISE,
    LIAISONS_FROTTANTES,
    Liaison,
    Statut,
    TypeLiaison,
)

TOLERANCE_AXE_NOMME = 1e-9
DECIMALES_EPSILON = 5


class PanneauProprietes(QWidget):
    """Les modifications sont faites par les méthodes de `Liaison` et par les éditeurs de
    `saisie.py` ; `modifiee` prévient la fenêtre (m, h, arbre, résultats périmés) et
    `capteurs_modifies` aussi, sans invalider les résultats (le post-traitement est refait)."""

    modifiee = pyqtSignal()
    capteurs_modifies = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._liaison: Liaison | None = None
        self._rafraichit = False
        self.etude: Etude | None = None
        sortie = QVBoxLayout(self)
        sortie.setContentsMargins(0, 0, 0, 0)
        defilement = QScrollArea()
        defilement.setWidgetResizable(True)
        defilement.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        contenu = QWidget()
        defilement.setWidget(contenu)
        sortie.addWidget(defilement)
        disposition = QVBoxLayout(contenu)
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
        conteneur_axe, self.saisie_axe = trois_champs("", 4)
        self.bouton_axe = QPushButton(textes.BOUTON_AXE)
        for w in (self.choix_axe, conteneur_axe, self.bouton_axe):
            axe.addWidget(w)

        self.groupe_direction = QGroupBox(textes.GROUPE_DIRECTION)
        direction = QVBoxLayout(self.groupe_direction)
        conteneur_dir, self.saisie_direction = trois_champs("", 4)
        self.bouton_direction = QPushButton(textes.BOUTON_DIRECTION)
        direction.addWidget(conteneur_dir)
        direction.addWidget(self.bouton_direction)

        self.groupe_centre = QGroupBox(textes.GROUPE_CENTRE)
        centre = QVBoxLayout(self.groupe_centre)
        conteneur_centre, self.saisie_centre = trois_champs(" mm", 3)
        self.bouton_centre = QPushButton(textes.BOUTON_CENTRE)
        centre.addWidget(conteneur_centre)
        centre.addWidget(self.bouton_centre)

        # loi d'entrée de la liaison pilote (EX-30)
        self.groupe_pilote = QGroupBox(textes.GROUPE_PILOTE)
        pilote = QVBoxLayout(self.groupe_pilote)
        self.etiquette_loi = QLabel()
        self.etiquette_loi.setWordWrap(True)
        self.choix_grandeur = QComboBox()
        for libelle, code in textes.GRANDEURS:
            self.choix_grandeur.addItem(libelle, code)
        self.editeur_pilote = EditeurLoi()
        self.bouton_pilote = QPushButton(textes.BOUTON_APPLIQUER_LOI)
        self.bouton_retirer_pilote = QPushButton(textes.BOUTON_RETIRER_LOI)
        for w in (
            self.etiquette_loi,
            self.choix_grandeur,
            self.editeur_pilote,
            self.bouton_pilote,
            self.bouton_retirer_pilote,
        ):
            pilote.addWidget(w)

        # frottement de Coulomb (EX-15) : 0 vaut « non renseigné » ou « défaut » (None)
        self.groupe_frottement = QGroupBox(textes.GROUPE_FROTTEMENT)
        frottement = QVBoxLayout(self.groupe_frottement)
        self.saisie_frottement = champ("", 3, 0.0)
        self.etiquette_rayon_axe = QLabel(textes.CHAMP_RAYON_AXE)
        self.etiquette_rayon_axe.setWordWrap(True)
        self.saisie_rayon_axe = champ(" mm", 3, 0.0)
        self.saisie_rayon_axe.setSpecialValueText(textes.VALEUR_NON_RENSEIGNEE)
        self.etiquette_epsilon = QLabel()
        self.saisie_epsilon = champ("", DECIMALES_EPSILON, 0.0)
        self.saisie_epsilon.setSpecialValueText(textes.VALEUR_DEFAUT)
        self.saisie_epsilon.setToolTip(textes.AIDE_EPSILON)
        self.bouton_frottement = QPushButton(textes.BOUTON_FROTTEMENT)
        for w in (
            QLabel(textes.CHAMP_FROTTEMENT),
            self.saisie_frottement,
            self.etiquette_rayon_axe,
            self.saisie_rayon_axe,
            self.etiquette_epsilon,
            self.saisie_epsilon,
            self.bouton_frottement,
        ):
            frottement.addWidget(w)

        # pas de l'hélicoïdale (EX-10)
        self.groupe_pas = QGroupBox(textes.GROUPE_PAS)
        pas = QVBoxLayout(self.groupe_pas)
        self.saisie_pas = champ(" mm/tour", 3, 0.0)
        self.saisie_pas.setSpecialValueText(textes.VALEUR_NON_RENSEIGNEE)
        self.bouton_pas = QPushButton(textes.BOUTON_PAS)
        pas.addWidget(self.saisie_pas)
        pas.addWidget(self.bouton_pas)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setProperty("role", ROLE_ERREUR)
        for w in (
            self.etiquette_type_sc,
            self.choix_type,
            self.etiquette_statut,
            self.bouton_valider,
            self.groupe_axe,
            self.groupe_direction,
            self.groupe_centre,
            self.groupe_frottement,
            self.groupe_pas,
            self.groupe_pilote,
            self.message,
        ):
            zone.addWidget(w)
        disposition.addWidget(self.zone_liaison)

        self.editeur_pesanteur = EditeurPesanteur()
        self.editeur_action = EditeurAction()
        self.editeur_ressort = EditeurRessort()
        self.editeur_capteur = EditeurCapteur()
        self.editeur_reglages = EditeurReglages()
        self.editeur_couplage = EditeurCouplage()
        self._editeurs = (
            self.editeur_pesanteur,
            self.editeur_action,
            self.editeur_ressort,
            self.editeur_capteur,
            self.editeur_reglages,
            self.editeur_couplage,
        )
        for editeur in self._editeurs:
            disposition.addWidget(editeur)
            editeur.hide()
            if editeur is not self.editeur_capteur:
                editeur.modifiee.connect(self.modifiee)
        self.editeur_capteur.modifiee.connect(self.capteurs_modifies)
        disposition.addStretch(1)
        self.zone_liaison.hide()

        self.choix_type.currentIndexChanged.connect(self._sur_choix_type)
        self.choix_axe.currentIndexChanged.connect(self._sur_choix_axe)
        self.bouton_valider.clicked.connect(self._valider)
        self.bouton_axe.clicked.connect(self._appliquer_axe)
        self.bouton_direction.clicked.connect(self._appliquer_direction)
        self.bouton_centre.clicked.connect(self._deplacer_centre)
        self.bouton_pilote.clicked.connect(self._appliquer_loi)
        self.bouton_retirer_pilote.clicked.connect(self._retirer_loi)
        self.bouton_frottement.clicked.connect(self._appliquer_frottement)
        self.bouton_pas.clicked.connect(self._appliquer_pas)
        self.choix_grandeur.currentIndexChanged.connect(self._sur_choix_grandeur)

    # --- étude -------------------------------------------------------------------------------
    def definir_etude(self, etude: Etude | None) -> None:
        self.etude = etude
        for editeur in self._editeurs:
            editeur.definir_etude(etude)

    # --- affichage ---------------------------------------------------------------------------
    def _montrer(self, widget: QWidget | None) -> None:
        self._liaison = None
        for w in (self.resume, self.zone_liaison, *self._editeurs):
            w.setVisible(w is widget)

    def afficher_texte(self, titre: str, texte: str) -> None:
        self._montrer(self.resume)
        self.titre.setText(titre)
        self.resume.setText(texte)

    def afficher_pesanteur(self) -> None:
        self._montrer(self.editeur_pesanteur)
        self.titre.setText(textes.TITRE_PESANTEUR)
        self.editeur_pesanteur.afficher()

    def afficher_action(self, action: ActionExterieure | None) -> None:
        self._montrer(self.editeur_action)
        self.titre.setText(textes.TITRE_ACTION)
        if action is None:
            self.editeur_action.afficher_nouveau()
        else:
            self.editeur_action.afficher_action(action)

    def afficher_ressort(self, ressort: RessortAmortisseur | None) -> None:
        self._montrer(self.editeur_ressort)
        self.titre.setText(textes.TITRE_RESSORT)
        if ressort is None:
            self.editeur_ressort.afficher_nouveau()
        else:
            self.editeur_ressort.afficher_ressort(ressort)

    def afficher_capteur(self, capteur: Capteur | None) -> None:
        self._montrer(self.editeur_capteur)
        self.titre.setText(textes.TITRE_CAPTEUR)
        if capteur is None:
            self.editeur_capteur.afficher_nouveau()
        else:
            self.editeur_capteur.afficher_capteur(capteur)

    def afficher_reglages(self) -> None:
        self._montrer(self.editeur_reglages)
        self.titre.setText(textes.TITRE_REGLAGES)
        self.editeur_reglages.afficher()

    def afficher_couplage(self, couplage: Couplage | None) -> None:
        self._montrer(self.editeur_couplage)
        self.titre.setText(textes.TITRE_COUPLAGE)
        if couplage is None:
            self.editeur_couplage.afficher_nouveau()
        else:
            self.editeur_couplage.afficher_couplage(couplage)

    def afficher_liaison(self, liaison: Liaison) -> None:
        self._montrer(self.zone_liaison)
        self._liaison = liaison
        self.titre.setText(liaison.nom)
        self.message.setText("")
        self.rafraichir()
        assert liaison.axe is not None
        self._remplir(self.saisie_axe, tuple(float(x) for x in liaison.axe))
        self._remplir(self.saisie_centre, tuple(float(x) for x in unites.m_vers_mm(liaison.centre)))
        if liaison.direction is not None:
            self._remplir(self.saisie_direction, tuple(float(x) for x in liaison.direction))
        self._charger_frottement()
        self._charger_pilote()

    @staticmethod
    def _remplir(champs: list, valeurs: tuple[float, ...]) -> None:  # type: ignore[type-arg]
        for champ_saisie, valeur in zip(champs, valeurs, strict=True):
            champ_saisie.setValue(valeur)

    @staticmethod
    def _code_axe(axe: np.ndarray) -> str:
        """R8 : « x », « y » ou « z » si l'axe est un axe du repère monde, sinon « vecteur »."""
        for code, vecteur in AXES_MONDE.items():
            if np.allclose(axe, vecteur, atol=TOLERANCE_AXE_NOMME, rtol=0.0):
                return code
        return "vecteur"

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
            assert liaison.axe is not None
            code = self._code_axe(liaison.axe)
            self.choix_axe.setCurrentIndex(self.choix_axe.findData(code))
            for champ_axe in self.saisie_axe:
                champ_axe.setEnabled(code == "vecteur")
            self._rafraichir_frottement()
            self._rafraichir_pilote()
        finally:
            self._rafraichit = False

    # --- frottement (EX-15) et pas de l'hélicoïdale (EX-10) -----------------------------------
    def _rafraichir_frottement(self) -> None:
        liaison = self._liaison
        if liaison is None:
            return
        self.groupe_frottement.setVisible(liaison.type in LIAISONS_FROTTANTES)
        pivot = liaison.type is TypeLiaison.PIVOT
        self.etiquette_rayon_axe.setVisible(pivot)
        self.saisie_rayon_axe.setVisible(pivot)
        self.etiquette_epsilon.setText(
            textes.CHAMP_EPSILON_ROTATION if pivot else textes.CHAMP_EPSILON_TRANSLATION
        )
        self.saisie_epsilon.setSuffix(" rad/s" if pivot else " m/s")
        self.groupe_pas.setVisible(liaison.type is TypeLiaison.HELICOIDALE)

    def _charger_frottement(self) -> None:
        liaison = self._liaison
        if liaison is None:
            return
        self.saisie_frottement.setValue(liaison.frottement)
        rayon = liaison.rayon_axe
        self.saisie_rayon_axe.setValue(0.0 if rayon is None else float(unites.m_vers_mm(rayon)))
        self.saisie_epsilon.setValue(0.0 if liaison.epsilon is None else liaison.epsilon)
        pas = liaison.pas
        self.saisie_pas.setValue(0.0 if pas is None else float(unites.m_vers_mm(pas)))

    def _appliquer_frottement(self) -> None:
        liaison = self._liaison
        if liaison is None:
            return
        rayon_mm, epsilon = self.saisie_rayon_axe.value(), self.saisie_epsilon.value()
        try:
            liaison.regler_frottement(
                self.saisie_frottement.value(),
                float(unites.mm_vers_m(rayon_mm)) if rayon_mm > 0.0 else None,
                epsilon if epsilon > 0.0 else None,
            )
        except ValueError as e:
            self._signaler(e)
            return
        self._charger_frottement()
        self._signaler(None)

    def _appliquer_pas(self) -> None:
        liaison = self._liaison
        if liaison is None:
            return
        try:
            liaison.definir_pas(float(unites.mm_vers_m(self.saisie_pas.value())))
        except ValueError as e:
            self._signaler(e)
            return
        self._signaler(None)

    # --- loi d'entrée (EX-30) ----------------------------------------------------------------
    def _pilote_de(self, liaison: Liaison) -> Pilote | None:
        if self.etude is None:
            return None
        return next((p for p in self.etude.pilotes if p.liaison == liaison.nom), None)

    def _grandeur_courante(self, liaison: Liaison) -> str:
        grandeurs = grandeurs_pilotables(liaison.type)
        if len(grandeurs) > 1:
            return str(self.choix_grandeur.currentData())
        return grandeurs[0] if grandeurs else "angle"

    def _rafraichir_pilote(self) -> None:
        liaison = self._liaison
        if liaison is None:
            return
        grandeurs = grandeurs_pilotables(liaison.type)
        self.groupe_pilote.setVisible(bool(grandeurs))
        self.choix_grandeur.setVisible(len(grandeurs) > 1)
        pilote = self._pilote_de(liaison)
        if pilote is not None and pilote.grandeur in grandeurs:
            self.choix_grandeur.setCurrentIndex(self.choix_grandeur.findData(pilote.grandeur))
        grandeur = self._grandeur_courante(liaison)
        self.editeur_pilote.definir_unites(textes.UNITES_GRANDEUR[grandeur])
        if pilote is None:
            self.etiquette_loi.setText(textes.LOI_ACTUELLE + textes.AUCUNE_LOI)
        else:
            reelle = pilote.grandeur or (grandeurs[0] if grandeurs else "angle")
            self.etiquette_loi.setText(
                textes.LOI_ACTUELLE + textes.loi_pilote(pilote.loi.texte, reelle)
            )
        self.bouton_retirer_pilote.setEnabled(pilote is not None)

    def _charger_pilote(self) -> None:
        """Remplit l'éditeur avec la loi actuelle (à l'affichage ou après Appliquer / Retirer)."""
        liaison = self._liaison
        if liaison is None:
            return
        pilote = self._pilote_de(liaison)
        self.editeur_pilote.definir_texte("" if pilote is None else pilote.loi.texte)

    def _sur_choix_grandeur(self, _: int) -> None:
        if self._rafraichit or self._liaison is None:
            return
        self.editeur_pilote.definir_unites(
            textes.UNITES_GRANDEUR[self._grandeur_courante(self._liaison)]
        )

    def _appliquer_loi(self) -> None:
        liaison, etude = self._liaison, self.etude
        if liaison is None or etude is None:
            return
        loi = self.editeur_pilote.loi()
        if loi is None:
            self.message.setText(
                self.editeur_pilote.etiquette_erreur.text() or textes.MSG_LOI_A_SAISIR
            )
            return
        grandeurs = grandeurs_pilotables(liaison.type)
        if not grandeurs:
            return
        if liaison.valeur_pose is None:
            self.message.setText(textes.MSG_POSE_INCONNUE)
            return
        grandeur = None if len(grandeurs) == 1 else self._grandeur_courante(liaison)
        nouveau = Pilote(liaison=liaison.nom, loi=LoiEntree(loi.texte), grandeur=grandeur)
        for i, existant in enumerate(etude.pilotes):
            if existant.liaison == liaison.nom:
                etude.pilotes[i] = nouveau
                break
        else:
            etude.pilotes.append(nouveau)
        self._charger_pilote()
        self._signaler(None)

    def _retirer_loi(self) -> None:
        liaison, etude = self._liaison, self.etude
        if liaison is None or etude is None:
            return
        etude.pilotes = [p for p in etude.pilotes if p.liaison != liaison.nom]
        self._charger_pilote()
        self._signaler(None)

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

    def _sur_choix_axe(self, _: int) -> None:
        """Un axe nommé s'affiche dans les champs (figés) ; « Vecteur saisi » les libère."""
        if self._rafraichit or self._liaison is None:
            return
        code = str(self.choix_axe.currentData())
        if code in AXES_MONDE:
            self._remplir(self.saisie_axe, AXES_MONDE[code])
        for champ_axe in self.saisie_axe:
            champ_axe.setEnabled(code == "vecteur")

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
