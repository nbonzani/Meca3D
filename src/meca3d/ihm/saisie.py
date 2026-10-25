# SPDX-License-Identifier: GPL-3.0-or-later
"""Éditeurs de saisie des données d'entrée (EX-30 à EX-33, EX-50, EX-51).

Les widgets ne portent aucune logique métier : ils construisent des objets de `modele/` (qui
valident) et les placent dans l'`Etude`. Les points sont saisis en coordonnées pièce (repère du
composant, D15) et convertis en repère monde par `Solide.vers_monde` (R9).
"""

from collections.abc import Sequence
from typing import Any

import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from meca3d import unites
from meca3d.ihm import textes
from meca3d.modele.actions import (
    ActionExterieure,
    ErreurAction,
    ErreurLoi,
    LoiEntree,
    NatureAction,
    Pesanteur,
    RepereAction,
    RessortAmortisseur,
)
from meca3d.modele.capteurs import (
    BaseCapteur,
    Capteur,
    CapteurLiaison,
    CapteurPoint,
    ErreurCapteur,
    SensTorseur,
)
from meca3d.modele.etude import Etude
from meca3d.modele.solide import Solide

BORNE_SAISIE = 1.0e6
STYLE_ERREUR = "color: #b91c1c;"
ERREURS_SAISIE = (ErreurAction, ErreurCapteur, ErreurLoi, ValueError)


def champ(suffixe: str, decimales: int, minimum: float = -BORNE_SAISIE) -> QDoubleSpinBox:
    c = QDoubleSpinBox()
    c.setRange(minimum, BORNE_SAISIE)
    c.setDecimals(decimales)
    if suffixe:
        c.setSuffix(suffixe)
    return c


def trois_champs(suffixe: str, decimales: int) -> tuple[QWidget, list[QDoubleSpinBox]]:
    conteneur = QWidget()
    disposition = QHBoxLayout(conteneur)
    disposition.setContentsMargins(0, 0, 0, 0)
    champs = [champ(suffixe, decimales) for _ in range(3)]
    for nom, c in zip("xyz", champs, strict=True):
        disposition.addWidget(QLabel(nom))
        disposition.addWidget(c)
    return conteneur, champs


def _valeurs(champs: Sequence[QDoubleSpinBox]) -> np.ndarray:
    return np.array([c.value() for c in champs], dtype=float)


def point_monde(solide: Solide, champs_mm: Sequence[QDoubleSpinBox]) -> tuple[float, float, float]:
    """Point saisi en coordonnées pièce (mm) -> repère monde (m), par `Solide.vers_monde`."""
    p = solide.vers_monde(unites.mm_vers_m(_valeurs(champs_mm)))
    return float(p[0]), float(p[1]), float(p[2])


def remplir_point(
    champs_mm: Sequence[QDoubleSpinBox], solide: Solide, monde: Sequence[float]
) -> None:
    """Affiche un point stocké en repère monde en coordonnées pièce (mm)."""
    local = unites.m_vers_mm(solide.vers_local(np.array(monde, dtype=float)))
    for c, v in zip(champs_mm, local, strict=True):
        c.setValue(float(v))


def _groupe(titre: str, contenu: QWidget) -> QGroupBox:
    groupe = QGroupBox(titre)
    QVBoxLayout(groupe).addWidget(contenu)
    return groupe


def _combo(elements: Sequence[tuple[str, Any]]) -> QComboBox:
    combo = QComboBox()
    for libelle, donnee in elements:
        combo.addItem(libelle, donnee)
    return combo


def _remplir_solides(combo: QComboBox, solides: Sequence[Solide]) -> None:
    precedent = combo.currentText()
    combo.clear()
    for s in solides:
        combo.addItem(s.nom)
    index = combo.findText(precedent)
    combo.setCurrentIndex(max(index, 0))


def _nom_libre(prefixe: str, existants: set[str]) -> str:
    i = 1
    while f"{prefixe}{i}" in existants:
        i += 1
    return f"{prefixe}{i}"


class _EditeurBase(QWidget):
    """Socle : étude courante, message d'erreur, signal de modification."""

    modifiee = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.etude: Etude | None = None
        self.corps = QVBoxLayout(self)
        self.corps.setContentsMargins(0, 0, 0, 0)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet(STYLE_ERREUR)

    def definir_etude(self, etude: Etude | None) -> None:
        self.etude = etude

    def _erreur(self, erreur: Exception | str) -> None:
        self.message.setText(str(erreur))

    def _termine(self) -> None:
        self.message.setText("")
        self.modifiee.emit()


class EditeurLoi(QWidget):
    """Loi d'entrée f(t) : saisie texte, validation à chaque frappe (EX-30), aperçu de la valeur,
    de la vitesse et de l'accélération à l'instant choisi."""

    changee = pyqtSignal()

    def __init__(
        self,
        libelle: str = textes.CHAMP_LOI,
        unites_apercu: tuple[str, str, str] = textes.UNITES_GRANDEUR["angle"],
        avec_apercu: bool = True,
    ) -> None:
        super().__init__()
        self._unites = unites_apercu
        self._touche = False
        self._loi: LoiEntree | None = None
        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(0, 0, 0, 0)
        ligne = QHBoxLayout()
        ligne.addWidget(QLabel(libelle))
        self.champ = QLineEdit()
        ligne.addWidget(self.champ, 1)
        disposition.addLayout(ligne)
        self.etiquette_erreur = QLabel()
        self.etiquette_erreur.setWordWrap(True)
        self.etiquette_erreur.setStyleSheet(STYLE_ERREUR)
        disposition.addWidget(self.etiquette_erreur)
        self.zone_apercu = QWidget()
        apercu = QHBoxLayout(self.zone_apercu)
        apercu.setContentsMargins(0, 0, 0, 0)
        apercu.addWidget(QLabel(textes.CHAMP_T_APERCU))
        self.champ_t = champ(" s", 3, 0.0)
        self.champ_t.setValue(0.5)
        apercu.addWidget(self.champ_t)
        disposition.addWidget(self.zone_apercu)
        self.etiquette_apercu = QLabel()
        self.etiquette_apercu.setWordWrap(True)
        disposition.addWidget(self.etiquette_apercu)
        if not avec_apercu:
            self.zone_apercu.hide()
            self.etiquette_apercu.hide()
        self.champ.textChanged.connect(self._sur_texte)
        self.champ_t.valueChanged.connect(self._sur_instant)

    @property
    def valide(self) -> bool:
        return self._loi is not None

    def loi(self) -> LoiEntree | None:
        return self._loi

    def texte(self) -> str:
        return self.champ.text()

    def definir_unites(self, unites_apercu: tuple[str, str, str]) -> None:
        self._unites = unites_apercu
        self._apercu()

    def definir_texte(self, texte: str) -> None:
        """Remplit le champ par programme (sans message d'erreur tant que rien n'est tapé)."""
        self.champ.blockSignals(True)
        self.champ.setText(texte)
        self.champ.blockSignals(False)
        self._touche = False
        self._valider()

    def _sur_texte(self, _: str) -> None:
        self._touche = True
        self._valider()
        self.changee.emit()

    def _sur_instant(self, _: float) -> None:
        self._apercu()

    def _valider(self) -> None:
        texte = self.champ.text()
        self._loi = None
        self.etiquette_erreur.setText("")
        if not texte.strip():
            if self._touche:
                self.etiquette_erreur.setText(
                    "La loi d'entrée est vide : saisir une expression de t."
                )
        else:
            try:
                self._loi = LoiEntree(texte)
            except ErreurLoi as e:
                self.etiquette_erreur.setText(str(e))
            except Exception as e:  # noqa: BLE001 - toute expression refusée devient un message
                self.etiquette_erreur.setText(f"Expression refusée ({type(e).__name__}).")
        self._apercu()

    def _apercu(self) -> None:
        loi = self._loi
        if loi is None:
            self.etiquette_apercu.setText("")
            return
        t = self.champ_t.value()
        try:
            valeurs = (loi.valeur(t), loi.vitesse(t), loi.acceleration(t))
        except (ArithmeticError, ValueError, TypeError) as e:
            self.etiquette_apercu.setText(textes.loi_non_evaluable(t, type(e).__name__))
            return
        self.etiquette_apercu.setText(textes.apercu_loi(*valeurs, self._unites))


class EditeurPesanteur(_EditeurBase):
    """Vecteur g (EX-31), activable et désactivable."""

    def __init__(self) -> None:
        super().__init__()
        self.case_active = QCheckBox(textes.CASE_PESANTEUR)
        conteneur, self.saisie = trois_champs("", 4)
        self.bouton = QPushButton(textes.BOUTON_PESANTEUR)
        self.corps.addWidget(self.case_active)
        self.corps.addWidget(_groupe(textes.GROUPE_PESANTEUR, conteneur))
        self.corps.addWidget(self.bouton)
        self.corps.addWidget(self.message)
        self.bouton.clicked.connect(self._appliquer)

    def afficher(self) -> None:
        self.message.setText("")
        if self.etude is None:
            return
        g = self.etude.pesanteur
        self.case_active.setChecked(g.actif)
        for c, v in zip(self.saisie, g.vecteur, strict=True):
            c.setValue(float(v))

    def _appliquer(self) -> None:
        if self.etude is None:
            return
        vecteur = tuple(float(c.value()) for c in self.saisie)
        self.etude.pesanteur = Pesanteur(vecteur=vecteur, actif=self.case_active.isChecked())
        self._termine()


class EditeurAction(_EditeurBase):
    """Force ou couple appliqué en un point d'un solide mobile (EX-32)."""

    def __init__(self) -> None:
        super().__init__()
        self._edite: ActionExterieure | None = None
        self.champ_nom = QLineEdit()
        self.choix_solide = QComboBox()
        self.choix_nature = _combo(
            [
                (textes.NATURES[0][0], NatureAction.FORCE),
                (textes.NATURES[1][0], NatureAction.COUPLE),
            ]
        )
        self.choix_repere = _combo(
            [
                (textes.REPERES[0][0], RepereAction.MONDE),
                (textes.REPERES[1][0], RepereAction.SOLIDE),
            ]
        )
        conteneur_point, self.saisie_point = trois_champs(" mm", 3)
        self.groupe_composantes = QGroupBox()
        composantes = QVBoxLayout(self.groupe_composantes)
        self.editeurs = [EditeurLoi(f"{axe} :", avec_apercu=False) for axe in "xyz"]
        for e in self.editeurs:
            composantes.addWidget(e)
        self.bouton_ajouter = QPushButton(textes.BOUTON_AJOUTER)
        self.bouton_supprimer = QPushButton(textes.BOUTON_SUPPRIMER)
        for etiquette, w in (
            (textes.CHAMP_NOM, self.champ_nom),
            (textes.CHAMP_SOLIDE, self.choix_solide),
            (textes.CHAMP_NATURE, self.choix_nature),
            (textes.CHAMP_REPERE, self.choix_repere),
        ):
            self.corps.addWidget(QLabel(etiquette))
            self.corps.addWidget(w)
        self.corps.addWidget(_groupe(textes.GROUPE_POINT_PIECE, conteneur_point))
        self.corps.addWidget(self.groupe_composantes)
        self.corps.addWidget(self.bouton_ajouter)
        self.corps.addWidget(self.bouton_supprimer)
        self.corps.addWidget(self.message)
        self.choix_nature.currentIndexChanged.connect(self._sur_nature)
        self.bouton_ajouter.clicked.connect(self._enregistrer)
        self.bouton_supprimer.clicked.connect(self._supprimer)
        self._sur_nature(0)

    def _nature(self) -> NatureAction:
        return NatureAction(self.choix_nature.currentData())

    def _sur_nature(self, _: int) -> None:
        force = self._nature() is NatureAction.FORCE
        self.groupe_composantes.setTitle(
            textes.GROUPE_COMPOSANTES_FORCE if force else textes.GROUPE_COMPOSANTES_COUPLE
        )
        unite = ("N", "N/s", "N/s²") if force else ("N·m", "N·m/s", "N·m/s²")
        for e in self.editeurs:
            e.definir_unites(unite)

    def _solides_mobiles(self) -> list[Solide]:
        return [] if self.etude is None else [s for s in self.etude.solides if not s.fixe]

    def afficher_nouveau(self) -> None:
        """Mode création : formulaire vide, nom libre proposé."""
        self._edite = None
        self.message.setText("")
        _remplir_solides(self.choix_solide, self._solides_mobiles())
        existants = {a.nom for a in self.etude.actions} if self.etude else set()
        self.champ_nom.setText(_nom_libre("A", existants))
        for c in self.saisie_point:
            c.setValue(0.0)
        for e in self.editeurs:
            e.definir_texte("0")
        self.bouton_ajouter.setText(textes.BOUTON_AJOUTER)
        self.bouton_supprimer.setVisible(False)

    def afficher_action(self, action: ActionExterieure) -> None:
        """Mode édition : le point est relu en coordonnées pièce."""
        if self.etude is None:
            return
        self._edite = action
        self.message.setText("")
        _remplir_solides(self.choix_solide, self._solides_mobiles())
        self.choix_solide.setCurrentIndex(max(self.choix_solide.findText(action.solide), 0))
        self.champ_nom.setText(action.nom)
        self.choix_nature.setCurrentIndex(self.choix_nature.findData(action.nature))
        self.choix_repere.setCurrentIndex(self.choix_repere.findData(action.repere))
        remplir_point(self.saisie_point, self.etude.solide(action.solide), action.point)
        for e, texte in zip(self.editeurs, action.composantes, strict=True):
            e.definir_texte(str(texte))
        self.bouton_ajouter.setText(textes.BOUTON_APPLIQUER)
        self.bouton_supprimer.setVisible(True)

    def _enregistrer(self) -> None:
        etude = self.etude
        if etude is None or not self._solides_mobiles():
            return
        nom = self.champ_nom.text()
        autres = [a for a in etude.actions if a is not self._edite]
        if nom in {a.nom for a in autres}:
            self._erreur(textes.MSG_NOM_EXISTE)
            return
        try:
            solide = etude.solide(self.choix_solide.currentText())
            action = ActionExterieure(
                nom=nom,
                solide=solide.nom,
                nature=self._nature(),
                composantes=tuple(e.texte() for e in self.editeurs),
                repere=RepereAction(self.choix_repere.currentData()),
                point=point_monde(solide, self.saisie_point),
            )
        except ERREURS_SAISIE as e:
            self._erreur(e)
            return
        if self._edite is None:
            etude.actions.append(action)
        else:
            etude.actions[etude.actions.index(self._edite)] = action
        self._termine()
        self.afficher_nouveau()

    def _supprimer(self) -> None:
        if self.etude is None or self._edite is None:
            return
        self.etude.actions.remove(self._edite)
        self._termine()
        self.afficher_nouveau()


class EditeurRessort(_EditeurBase):
    """Ressort-amortisseur linéaire entre deux points de deux solides (EX-33)."""

    def __init__(self) -> None:
        super().__init__()
        self._edite: RessortAmortisseur | None = None
        self.champ_nom = QLineEdit()
        self.choix_solide_1 = QComboBox()
        self.choix_solide_2 = QComboBox()
        conteneur_1, self.saisie_point_1 = trois_champs(" mm", 3)
        conteneur_2, self.saisie_point_2 = trois_champs(" mm", 3)
        self.saisie_raideur = champ(" N/m", 3, 0.0)
        self.saisie_longueur_libre = champ(" mm", 3, 0.0)
        self.saisie_amortissement = champ(" N·s/m", 3, 0.0)
        self.bouton_ajouter = QPushButton(textes.BOUTON_AJOUTER)
        self.bouton_supprimer = QPushButton(textes.BOUTON_SUPPRIMER)
        for etiquette, w in (
            (textes.CHAMP_NOM, self.champ_nom),
            (textes.CHAMP_SOLIDE_1, self.choix_solide_1),
        ):
            self.corps.addWidget(QLabel(etiquette))
            self.corps.addWidget(w)
        self.corps.addWidget(_groupe(textes.GROUPE_POINT_1, conteneur_1))
        self.corps.addWidget(QLabel(textes.CHAMP_SOLIDE_2))
        self.corps.addWidget(self.choix_solide_2)
        self.corps.addWidget(_groupe(textes.GROUPE_POINT_2, conteneur_2))
        for etiquette, w in (
            (textes.CHAMP_RAIDEUR, self.saisie_raideur),
            (textes.CHAMP_LONGUEUR_LIBRE, self.saisie_longueur_libre),
            (textes.CHAMP_AMORTISSEMENT, self.saisie_amortissement),
        ):
            self.corps.addWidget(QLabel(etiquette))
            self.corps.addWidget(w)
        self.corps.addWidget(self.bouton_ajouter)
        self.corps.addWidget(self.bouton_supprimer)
        self.corps.addWidget(self.message)
        self.bouton_ajouter.clicked.connect(self._enregistrer)
        self.bouton_supprimer.clicked.connect(self._supprimer)

    def _remplir_solides(self) -> None:
        solides = [] if self.etude is None else self.etude.solides
        _remplir_solides(self.choix_solide_1, solides)
        _remplir_solides(self.choix_solide_2, solides)

    def afficher_nouveau(self) -> None:
        self._edite = None
        self.message.setText("")
        self._remplir_solides()
        existants = {r.nom for r in self.etude.ressorts} if self.etude else set()
        self.champ_nom.setText(_nom_libre("R", existants))
        for c in (*self.saisie_point_1, *self.saisie_point_2):
            c.setValue(0.0)
        for c in (self.saisie_raideur, self.saisie_longueur_libre, self.saisie_amortissement):
            c.setValue(0.0)
        self.bouton_ajouter.setText(textes.BOUTON_AJOUTER)
        self.bouton_supprimer.setVisible(False)

    def afficher_ressort(self, ressort: RessortAmortisseur) -> None:
        if self.etude is None:
            return
        self._edite = ressort
        self.message.setText("")
        self._remplir_solides()
        self.champ_nom.setText(ressort.nom)
        self.choix_solide_1.setCurrentIndex(max(self.choix_solide_1.findText(ressort.solide_1), 0))
        self.choix_solide_2.setCurrentIndex(max(self.choix_solide_2.findText(ressort.solide_2), 0))
        remplir_point(self.saisie_point_1, self.etude.solide(ressort.solide_1), ressort.point_1)
        remplir_point(self.saisie_point_2, self.etude.solide(ressort.solide_2), ressort.point_2)
        self.saisie_raideur.setValue(ressort.raideur)
        self.saisie_longueur_libre.setValue(float(unites.m_vers_mm(ressort.longueur_libre)))
        self.saisie_amortissement.setValue(ressort.amortissement)
        self.bouton_ajouter.setText(textes.BOUTON_APPLIQUER)
        self.bouton_supprimer.setVisible(True)

    def _enregistrer(self) -> None:
        etude = self.etude
        if etude is None or not etude.solides:
            return
        nom = self.champ_nom.text()
        if nom in {r.nom for r in etude.ressorts if r is not self._edite}:
            self._erreur(textes.MSG_NOM_EXISTE)
            return
        try:
            s1 = etude.solide(self.choix_solide_1.currentText())
            s2 = etude.solide(self.choix_solide_2.currentText())
            ressort = RessortAmortisseur(
                nom=nom,
                solide_1=s1.nom,
                point_1=point_monde(s1, self.saisie_point_1),
                solide_2=s2.nom,
                point_2=point_monde(s2, self.saisie_point_2),
                raideur=self.saisie_raideur.value(),
                longueur_libre=float(unites.mm_vers_m(self.saisie_longueur_libre.value())),
                amortissement=self.saisie_amortissement.value(),
            )
        except (*ERREURS_SAISIE, KeyError) as e:
            self._erreur(e)
            return
        if self._edite is None:
            etude.ressorts.append(ressort)
        else:
            etude.ressorts[etude.ressorts.index(self._edite)] = ressort
        self._termine()
        self.afficher_nouveau()

    def _supprimer(self) -> None:
        if self.etude is None or self._edite is None:
            return
        self.etude.ressorts.remove(self._edite)
        self._termine()
        self.afficher_nouveau()


class EditeurCapteur(_EditeurBase):
    """Capteur de liaison (torseur, EX-50) ou de point (EX-51)."""

    def __init__(self) -> None:
        super().__init__()
        self._edite: Capteur | None = None
        self.choix_genre = _combo(list(textes.GENRES_CAPTEUR))
        self.champ_nom = QLineEdit()
        # capteur de liaison
        self.groupe_liaison = QWidget()
        liaison = QVBoxLayout(self.groupe_liaison)
        liaison.setContentsMargins(0, 0, 0, 0)
        self.choix_liaison = QComboBox()
        self.choix_sens = _combo(
            [(textes.SENS[0][0], SensTorseur.I_VERS_J), (textes.SENS[1][0], SensTorseur.J_VERS_I)]
        )
        self.choix_base_liaison = _combo(
            [
                (textes.BASES_LIAISON[0][0], BaseCapteur.LIAISON),
                (textes.BASES_LIAISON[1][0], BaseCapteur.MONDE),
            ]
        )
        for etiquette, w in (
            (textes.CHAMP_LIAISON, self.choix_liaison),
            (textes.CHAMP_SENS, self.choix_sens),
            (textes.CHAMP_BASE, self.choix_base_liaison),
        ):
            liaison.addWidget(QLabel(etiquette))
            liaison.addWidget(w)
        # capteur de point
        self.groupe_point = QWidget()
        point = QVBoxLayout(self.groupe_point)
        point.setContentsMargins(0, 0, 0, 0)
        self.choix_solide = QComboBox()
        conteneur_point, self.saisie_point = trois_champs(" mm", 3)
        self.choix_reference = QComboBox()
        self.choix_base_point = _combo(
            [
                (textes.BASES_POINT[0][0], BaseCapteur.REFERENCE),
                (textes.BASES_POINT[1][0], BaseCapteur.MONDE),
            ]
        )
        point.addWidget(QLabel(textes.CHAMP_SOLIDE))
        point.addWidget(self.choix_solide)
        point.addWidget(_groupe(textes.GROUPE_POINT_CAPTEUR, conteneur_point))
        point.addWidget(QLabel(textes.CHAMP_REFERENCE))
        point.addWidget(self.choix_reference)
        point.addWidget(QLabel(textes.CHAMP_BASE))
        point.addWidget(self.choix_base_point)
        self.bouton_ajouter = QPushButton(textes.BOUTON_AJOUTER)
        self.bouton_supprimer = QPushButton(textes.BOUTON_SUPPRIMER)
        self.corps.addWidget(self.choix_genre)
        self.corps.addWidget(QLabel(textes.CHAMP_NOM))
        self.corps.addWidget(self.champ_nom)
        self.corps.addWidget(self.groupe_liaison)
        self.corps.addWidget(self.groupe_point)
        self.corps.addWidget(self.bouton_ajouter)
        self.corps.addWidget(self.bouton_supprimer)
        self.corps.addWidget(self.message)
        self.choix_genre.currentIndexChanged.connect(self._sur_genre)
        self.bouton_ajouter.clicked.connect(self._enregistrer)
        self.bouton_supprimer.clicked.connect(self._supprimer)
        self._sur_genre(0)

    def _genre(self) -> str:
        return str(self.choix_genre.currentData())

    def _sur_genre(self, _: int) -> None:
        liaison = self._genre() == "liaison"
        self.groupe_liaison.setVisible(liaison)
        self.groupe_point.setVisible(not liaison)

    def _remplir(self) -> None:
        etude = self.etude
        solides = [] if etude is None else etude.solides
        _remplir_solides(self.choix_solide, solides)
        _remplir_solides(self.choix_reference, solides)
        precedent = self.choix_liaison.currentText()
        self.choix_liaison.clear()
        for x in [] if etude is None else etude.liaisons:
            self.choix_liaison.addItem(x.nom)
        self.choix_liaison.setCurrentIndex(max(self.choix_liaison.findText(precedent), 0))

    def afficher_nouveau(self) -> None:
        self._edite = None
        self.message.setText("")
        self._remplir()
        existants = {c.nom for c in self.etude.capteurs} if self.etude else set()
        self.champ_nom.setText(_nom_libre("C", existants))
        for c in self.saisie_point:
            c.setValue(0.0)
        self.bouton_ajouter.setText(textes.BOUTON_AJOUTER)
        self.bouton_supprimer.setVisible(False)

    def afficher_capteur(self, capteur: Capteur) -> None:
        if self.etude is None:
            return
        self._edite = capteur
        self.message.setText("")
        self._remplir()
        self.champ_nom.setText(capteur.nom)
        if isinstance(capteur, CapteurLiaison):
            self.choix_genre.setCurrentIndex(self.choix_genre.findData("liaison"))
            self.choix_liaison.setCurrentIndex(max(self.choix_liaison.findText(capteur.liaison), 0))
            self.choix_sens.setCurrentIndex(self.choix_sens.findData(capteur.sens))
            self.choix_base_liaison.setCurrentIndex(self.choix_base_liaison.findData(capteur.base))
        else:
            self.choix_genre.setCurrentIndex(self.choix_genre.findData("point"))
            self.choix_solide.setCurrentIndex(max(self.choix_solide.findText(capteur.solide), 0))
            self.choix_reference.setCurrentIndex(
                max(self.choix_reference.findText(capteur.solide_reference), 0)
            )
            self.choix_base_point.setCurrentIndex(self.choix_base_point.findData(capteur.base))
            remplir_point(self.saisie_point, self.etude.solide(capteur.solide), capteur.point)
        self.bouton_ajouter.setText(textes.BOUTON_APPLIQUER)
        self.bouton_supprimer.setVisible(True)

    def _construire(self, etude: Etude) -> Capteur:
        nom = self.champ_nom.text()
        if self._genre() == "liaison":
            return CapteurLiaison(
                nom,
                self.choix_liaison.currentText(),
                SensTorseur(self.choix_sens.currentData()),
                BaseCapteur(self.choix_base_liaison.currentData()),
            )
        solide = etude.solide(self.choix_solide.currentText())
        return CapteurPoint(
            nom,
            solide.nom,
            point_monde(solide, self.saisie_point),
            self.choix_reference.currentText(),
            BaseCapteur(self.choix_base_point.currentData()),
        )

    def _enregistrer(self) -> None:
        etude = self.etude
        if etude is None:
            return
        nom = self.champ_nom.text()
        if nom in {c.nom for c in etude.capteurs if c is not self._edite}:
            self._erreur(textes.MSG_NOM_EXISTE)
            return
        try:
            capteur = self._construire(etude)
        except (*ERREURS_SAISIE, KeyError) as e:
            self._erreur(e)
            return
        if self._edite is None:
            etude.capteurs.append(capteur)
        else:
            etude.capteurs[etude.capteurs.index(self._edite)] = capteur
        self._termine()
        self.afficher_nouveau()

    def _supprimer(self) -> None:
        if self.etude is None or self._edite is None:
            return
        self.etude.capteurs.remove(self._edite)
        self._termine()
        self.afficher_nouveau()
