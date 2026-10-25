# SPDX-License-Identifier: GPL-3.0-or-later
"""Arbre de l'étude à trois branches (EX-61) ; les éléments incomplets sont signalés."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from meca3d.graphe.mobilite import ResultatMobilite
from meca3d.ihm import textes
from meca3d.modele.etude import Etude
from meca3d.modele.liaison import Statut

ROLE_GENRE = Qt.ItemDataRole.UserRole
ROLE_NOM = Qt.ItemDataRole.UserRole + 1
ROLE_INCOMPLET = Qt.ItemDataRole.UserRole + 2
COULEUR_INCOMPLET = QColor("#b45309")

GENRE_BRANCHE = "branche"
GENRE_RUBRIQUE = "rubrique"
GENRE_SOLIDE = "solide"
GENRE_LIAISON = "liaison"
GENRE_PILOTE = "pilote"

STRUCTURE: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        textes.BRANCHE_MODELE,
        (textes.RUBRIQUE_SOLIDES, textes.RUBRIQUE_LIAISONS, textes.RUBRIQUE_GRAPHE),
    ),
    (
        textes.BRANCHE_DONNEES,
        (
            textes.RUBRIQUE_PILOTES,
            textes.RUBRIQUE_PESANTEUR,
            textes.RUBRIQUE_ACTIONS,
            textes.RUBRIQUE_RESSORTS,
        ),
    ),
    (
        textes.BRANCHE_RESULTATS,
        (textes.RUBRIQUE_CAPTEURS, textes.RUBRIQUE_COURBES, textes.RUBRIQUE_ANIMATION),
    ),
)


def _enfants(item: QTreeWidgetItem) -> list[QTreeWidgetItem]:
    return [c for i in range(item.childCount()) if (c := item.child(i)) is not None]


class ArbreEtude(QTreeWidget):
    """Les trois branches existent toujours ; leurs éléments suivent l'étude."""

    selection_changee = pyqtSignal(str, str)  # genre, nom

    def __init__(self) -> None:
        super().__init__()
        self.setHeaderHidden(True)
        self._branches: dict[str, QTreeWidgetItem] = {}
        self._rubriques: dict[str, QTreeWidgetItem] = {}
        for nom_branche, rubriques in STRUCTURE:
            branche = self._creer(self._racine(), nom_branche, GENRE_BRANCHE, nom_branche)
            self._branches[nom_branche] = branche
            for nom_rubrique in rubriques:
                self._rubriques[nom_rubrique] = self._creer(
                    branche, nom_rubrique, GENRE_RUBRIQUE, nom_rubrique
                )
        self.expandAll()
        self.currentItemChanged.connect(self._sur_selection)

    def _racine(self) -> QTreeWidgetItem:
        racine = self.invisibleRootItem()
        assert racine is not None
        return racine

    # --- construction -----------------------------------------------------------------------
    @staticmethod
    def _creer(parent: QTreeWidgetItem, texte: str, genre: str, nom: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem(parent, [texte])
        item.setData(0, ROLE_GENRE, genre)
        item.setData(0, ROLE_NOM, nom)
        item.setData(0, ROLE_INCOMPLET, False)
        return item

    def _marquer(self, item: QTreeWidgetItem, incomplet: bool) -> None:
        item.setData(0, ROLE_INCOMPLET, incomplet)
        base = (
            str(item.data(0, ROLE_NOM))
            if item.data(0, ROLE_GENRE)
            in (
                GENRE_BRANCHE,
                GENRE_RUBRIQUE,
            )
            else item.text(0).removeprefix(textes.MARQUE_INCOMPLET)
        )
        item.setText(0, (textes.MARQUE_INCOMPLET if incomplet else "") + base)
        item.setForeground(0, QBrush(COULEUR_INCOMPLET) if incomplet else QBrush())

    def _ajouter(
        self, rubrique: str, texte: str, genre: str, nom: str, incomplet: bool = False
    ) -> QTreeWidgetItem:
        item = self._creer(self._rubriques[rubrique], texte, genre, nom)
        self._marquer(item, incomplet)
        return item

    def mettre_a_jour(self, etude: Etude | None, mobilite: ResultatMobilite | None) -> None:
        """Reconstruit les éléments ; conserve la sélection et l'état déplié."""
        courant = self.currentItem()
        selection = (
            None
            if courant is None
            else (str(courant.data(0, ROLE_GENRE)), str(courant.data(0, ROLE_NOM)))
        )
        self.blockSignals(True)
        for rubrique in self._rubriques.values():
            rubrique.takeChildren()
        if etude is not None:
            for solide in etude.solides:
                item = self._ajouter(textes.RUBRIQUE_SOLIDES, solide.nom, GENRE_SOLIDE, solide.nom)
                if solide.fixe:
                    item.setToolTip(0, textes.BATI)
            for liaison in etude.liaisons:
                incomplet = liaison.statut is not Statut.VALIDEE
                texte = textes.libelle_liaison(liaison.nom, liaison.type, liaison.statut)
                self._ajouter(
                    textes.RUBRIQUE_LIAISONS, texte, GENRE_LIAISON, liaison.nom, incomplet
                )
            for pilote in etude.pilotes:
                texte = f"{pilote.liaison} : {pilote.loi.texte}"
                self._ajouter(textes.RUBRIQUE_PILOTES, texte, GENRE_PILOTE, pilote.liaison)
        self._marquer_rubriques(etude, mobilite)
        self.expandAll()
        if selection is not None:
            self._restaurer(selection)
        self.blockSignals(False)

    def _marquer_rubriques(self, etude: Etude | None, mobilite: ResultatMobilite | None) -> None:
        for nom, rubrique in self._rubriques.items():
            incomplet = any(self.est_incomplet(c) for c in _enfants(rubrique))
            if etude is not None and nom == textes.RUBRIQUE_PILOTES and mobilite is not None:
                incomplet = incomplet or len(etude.pilotes) != mobilite.m
            if etude is not None and nom == textes.RUBRIQUE_GRAPHE:
                incomplet = mobilite is None or mobilite.h > 0
            self._marquer(rubrique, incomplet)
        for branche in self._branches.values():
            self._marquer(branche, any(self.est_incomplet(c) for c in _enfants(branche)))

    def _restaurer(self, selection: tuple[str, str]) -> None:
        genre, nom = selection
        for item in self._tous():
            if (str(item.data(0, ROLE_GENRE)), str(item.data(0, ROLE_NOM))) == (genre, nom):
                self.setCurrentItem(item)
                return

    def _tous(self) -> list[QTreeWidgetItem]:
        resultat: list[QTreeWidgetItem] = []
        for branche in self._branches.values():
            resultat.append(branche)
            for rubrique in _enfants(branche):
                resultat.append(rubrique)
                resultat.extend(_enfants(rubrique))
        return resultat

    # --- interrogation (utilisée par la fenêtre et les tests) --------------------------------
    def branches(self) -> list[str]:
        return [str(b.data(0, ROLE_NOM)) for b in _enfants(self._racine())]

    def item_branche(self, nom: str) -> QTreeWidgetItem:
        return self._branches[nom]

    def item_rubrique(self, nom: str) -> QTreeWidgetItem:
        return self._rubriques[nom]

    def rubriques(self, branche: str) -> list[str]:
        return [str(c.data(0, ROLE_NOM)) for c in _enfants(self._branches[branche])]

    def elements(self, rubrique: str) -> list[str]:
        textes_ = [c.text(0) for c in _enfants(self._rubriques[rubrique])]
        return [t.removeprefix(textes.MARQUE_INCOMPLET) for t in textes_]

    def item_liaison(self, nom: str) -> QTreeWidgetItem:
        for item in _enfants(self._rubriques[textes.RUBRIQUE_LIAISONS]):
            if item.data(0, ROLE_NOM) == nom:
                return item
        raise KeyError(f"Liaison absente de l'arbre : {nom}")

    @staticmethod
    def est_incomplet(item: QTreeWidgetItem) -> bool:
        return bool(item.data(0, ROLE_INCOMPLET))

    def selectionner_liaison(self, nom: str) -> None:
        self.setCurrentItem(self.item_liaison(nom))

    def _sur_selection(self, courant: QTreeWidgetItem | None, _: QTreeWidgetItem | None) -> None:
        if courant is not None:
            self.selection_changee.emit(
                str(courant.data(0, ROLE_GENRE)), str(courant.data(0, ROLE_NOM))
            )
